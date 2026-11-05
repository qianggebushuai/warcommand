# -*- coding: utf-8 -*-
"""视觉层：屏幕截图、UI 地标计算、地面真值投影（训练数据标注）。

三条识别路线（按优先级，见 docs/ai_autoplay.md）：
A. VLM 端到端：整帧截图 + 策略文案 + 指令生成规则 → 直接输出 JSON 指令
   （agent.py 默认路线，无需专门训练）；
B. 微调多模态模型：用本模块 project_entities() 自动标注的游戏截图训练
   （LoRA SFT），替换路线 A 的 model 名即可；
C. 专用检测器（YOLO 等）：只负责"识别 UI/单位 + 求屏幕坐标"，坐标再交给
   规则/LLM 组装指令——load_detector() 预留了加载点。
"""
import io
import os

import pygame

from core.utils import resource_path

# ---- UI 地标（与 panels/ui_sidebar.py 的布局常量保持一致） ----------------
SIDEBAR_WIDTH = 220
MINIMAP_AREA_H = 220
TAB_HEIGHT = 40


def ui_landmarks(screen_w, screen_h):
    """固定 UI 的屏幕区域（像素矩形），作为识别先验写进模型上下文。"""
    rx = screen_w - SIDEBAR_WIDTH
    return {
        'minimap': (rx, 0, SIDEBAR_WIDTH, MINIMAP_AREA_H),                 # 小地图
        'build_tabs': (rx, MINIMAP_AREA_H, SIDEBAR_WIDTH, TAB_HEIGHT),     # 建筑/单位/费用/杂项 标签
        'build_items': (rx, MINIMAP_AREA_H + TAB_HEIGHT,
                        SIDEBAR_WIDTH, screen_h - MINIMAP_AREA_H - TAB_HEIGHT),  # 建造队列/冷却条
        'viewport': (0, 0, rx, screen_h),                                  # 游戏主视口
    }


def capture_png_bytes(surface):
    """把当前屏幕 surface 编码为 PNG 字节（供 VLM base64 / 数据集落盘）。"""
    buf = io.BytesIO()
    pygame.image.save(surface, buf, 'frame.png')
    return buf.getvalue()


def project_entities(game):
    """地面真值投影：把游戏内实体位置换算成屏幕坐标框（训练数据自动标注）。

    返回 [{class, team, hp_ratio, x, y, w, h, world_pos}]。
    游戏本身知道每个实体的世界坐标与相机参数，因此标注零成本——
    这是"通过训练让多模态模型认识游戏 UI/单位"的数据来源。
    """
    sw, sh = pygame.display.get_surface().get_size()
    offset = getattr(game, 'camera_offset', None)
    zoom = getattr(game, 'zoom', 1.0)
    if offset is None:
        return []
    from core.base_classes import to_screen
    labels = []
    try:
        entities = (list(getattr(game, 'all_units', []) or [])
                    + list(getattr(game, 'all_buildings', []) or []))
    except TypeError:
        return []
    for e in entities:
        if not getattr(e, 'alive', True):
            continue
        try:
            sp = to_screen(e.pos, offset, zoom)
        except Exception:
            continue
        # 框取实体视觉尺寸：建筑 radius 可能远小于 rect 宽高（如 radius=15 视觉 120px）
        rect = getattr(e, 'rect', None)
        vis = max(getattr(e, 'radius', 14) * 2,
                  rect.w if rect is not None else 0,
                  rect.h if rect is not None else 0, 24)
        r = max(12, int(vis * zoom / 2) + 6)
        x0, y0 = int(sp[0] - r), int(sp[1] - r)
        if not (-r < sp[0] < sw and -r < sp[1] < sh):
            continue
        hp = getattr(e, 'hp', 0)
        mx = getattr(e, 'max_hp', 1) or 1
        # 类名带阵营后缀（M1A2_usa/M1A2_rus/M1A2_chn…）——检测器输出可直接区分敌我
        cls = e.__class__.__name__
        fac = str(getattr(e, 'faction', '') or '').upper()
        suffix = {'USA': 'usa', 'RUSSIA': 'rus', 'CHINA': 'chn'}.get(fac)
        if suffix:
            cls = '%s_%s' % (cls, suffix)
        labels.append({
            'class': cls,
            'team': getattr(e, 'team', 'unknown'),
            'hp_ratio': round(max(0.0, min(1.0, hp / float(mx))), 2),
            'x': max(0, x0), 'y': max(0, y0),
            'w': min(sw - max(0, x0), r * 2), 'h': min(sh - max(0, y0), r * 2),
            'world_pos': [int(e.pos.x), int(e.pos.y)],
        })
    return labels


class DatasetRecorder:
    """训练数据采集：截图 + 自动标注逐帧落盘（JSONL + PNG）。"""

    def __init__(self, out_dir=None):
        self.out_dir = out_dir or resource_path(
            os.path.join('dataset', 'autoplay'))
        self.img_dir = os.path.join(self.out_dir, 'images')
        os.makedirs(self.img_dir, exist_ok=True)
        self.frames = 0

    def save(self, png_bytes, labels, meta):
        name = 'frame_%08d' % self.frames
        with open(os.path.join(self.img_dir, name + '.png'), 'wb') as f:
            f.write(png_bytes)
        with open(os.path.join(self.out_dir, 'labels.jsonl'), 'a', encoding='utf-8') as f:
            import json
            f.write(json.dumps({'image': name + '.png', 'entities': labels,
                                'meta': meta}, ensure_ascii=False) + '\n')
        self.frames += 1
        return self.frames


def load_detector():
    """路线 C：加载本地检测模型（tools/train_detector.py 训练产出的 YOLO ONNX）。

    返回 None 表示未配置——agent 自动回退路线 A/B。
    实现约定：detect(png_bytes) -> [{'class','x','y','w','h','conf'}]
    （x,y 为框左上角屏幕像素；类名经 detector_names.json 还原）
    """
    p = resource_path(os.path.join('ai_autoplay', 'detector.onnx'))
    if not os.path.exists(p):
        return None
    try:
        import onnxruntime                                     # 可选依赖
        import numpy as np
        names_path = resource_path(os.path.join('ai_autoplay', 'detector_names.json'))
        names = {}
        try:
            import json
            with open(names_path, encoding='utf-8') as f:
                names = {int(k): v for k, v in json.load(f).items()}
        except Exception:
            pass
        return _OnnxDetector(p, onnxruntime, np, names)
    except Exception:
        return None


class _OnnxDetector:
    """YOLOv8 ONNX 推理：letterbox 预处理 + 输出解析 + NMS + 坐标还原。

    兼容 ultralytics 导出的 (1, 4+nc, N) 张量布局；
    x,y,w,h 为输入分辨率下的像素（中心点），NMS 后转回原图左上角坐标。
    """

    INPUT_SIZE = 640
    CONF_THRES = 0.35
    IOU_THRES = 0.45

    def __init__(self, path, ort, np, names=None):
        self.np = np
        self.names = names or {}
        self.sess = ort.InferenceSession(path)
        self.in_name = self.sess.get_inputs()[0].name
        self.in_h = self.sess.get_inputs()[0].shape[2] or self.INPUT_SIZE
        self.in_w = self.sess.get_inputs()[0].shape[3] or self.INPUT_SIZE

    def _preprocess(self, png_bytes):
        """截图 → letterbox 到网络输入尺寸的 float32 NCHW RGB。"""
        import pygame
        img = pygame.image.load(io.BytesIO(png_bytes))
        arr = pygame.surfarray.array3d(img)                    # (W,H,3)
        arr = arr.transpose((1, 0, 2))                         # HWC RGB
        self.np_arr = self.np.asarray(arr, dtype=self.np.float32)
        orig_h, orig_w = self.np_arr.shape[:2]
        scale = min(self.in_w / orig_w, self.in_h / orig_h)
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        resized = pygame.transform.smoothscale(img, (new_w, new_h))
        resized_np = self.np.asarray(
            pygame.surfarray.array3d(resized).transpose((1, 0, 2)),
            dtype=self.np.float32)
        canvas = self.np.full((self.in_h, self.in_w, 3), 114.0, dtype=self.np.float32)
        self.pad_x, self.pad_y = (self.in_w - new_w) // 2, (self.in_h - new_h) // 2
        canvas[self.pad_y:self.pad_y + new_h, self.pad_x:self.pad_x + new_w] = resized_np
        blob = canvas.transpose((2, 0, 1))[None] / 255.0       # NCHW
        self._scale, self._orig_w, self._orig_h = scale, orig_w, orig_h
        return self.np.ascontiguousarray(blob)

    def _postprocess(self, out):
        np = self.np
        # ultralytics ONNX: (1, 4+nc, N) → 转置为 (N, 4+nc)
        pred = out[0]
        if pred.shape[0] < pred.shape[-1]:
            pred = pred.T
        boxes = pred[:, :4]                                    # cx,cy,w,h（输入分辨率）
        scores = pred[:, 4:]
        cls_ids = scores.argmax(axis=1)
        confs = scores.max(axis=1)
        keep = confs >= self.CONF_THRES
        boxes, cls_ids, confs = boxes[keep], cls_ids[keep], confs[keep]

        # 简易 NMS（逐类贪心 IoU）
        order = confs.argsort()[::-1]
        sel = []
        ious = []
        while order.size:
            i = order[0]
            sel.append(i)
            if order.size == 1:
                break
            rest = order[1:]
            bb, rb = boxes[i], boxes[rest]
            x1 = np.maximum(bb[0] - bb[2] / 2, rb[:, 0] - rb[:, 2] / 2)
            y1 = np.maximum(bb[1] - bb[3] / 2, rb[:, 1] - rb[:, 3] / 2)
            x2 = np.minimum(bb[0] + bb[2] / 2, rb[:, 0] + rb[:, 2] / 2)
            y2 = np.minimum(bb[1] + bb[3] / 2, rb[:, 1] + rb[:, 3] / 2)
            inter = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
            union = bb[2] * bb[3] + rb[:, 2] * rb[:, 3] - inter
            order = rest[inter / np.maximum(union, 1e-9) < self.IOU_THRES]

        scale, px, py = self._scale, self.pad_x, self.pad_y
        dets = []
        for i in sel:
            cx, cy, w, h = boxes[i]
            ox = (cx - px) / scale                             # 还原到原图像素
            oy = (cy - py) / scale
            ow, oh = w / scale, h / scale
            cid = int(cls_ids[i])
            dets.append({'class': self.names.get(cid, str(cid)),
                         'conf': round(float(confs[i]), 3),
                         'x': int(max(0, ox - ow / 2)),
                         'y': int(max(0, oy - oh / 2)),
                         'w': int(ow), 'h': int(oh)})
        return dets

    def detect(self, png_bytes):
        blob = self._preprocess(png_bytes)
        out = self.sess.run(None, {self.in_name: blob})[0]
        return self._postprocess(out)
