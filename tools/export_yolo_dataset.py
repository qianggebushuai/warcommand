# -*- coding: utf-8 -*-
"""把 ai_autoplay 采集的训练数据（dataset/autoplay/labels.jsonl + images/）
导出为 YOLO 目标检测训练格式（images/ + labels/*.txt + data.yaml）。

用法：
    python tools/export_yolo_dataset.py            # 全类自动编号
    python tools/export_yolo_dataset.py --out myds # 指定输出目录

训练示例（ultralytics）：
    pip install ultralytics
    yolo detect train data=dataset/yolo/data.yaml model=yolov8n.pt epochs=100
训练后的 best.onnx 放到 ai_autoplay/detector.onnx 即可被
ai_autoplay.vision.load_detector() 加载（路线 C）。
"""
import json
import os
import sys
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'dataset', 'autoplay')
OUT = os.path.join(ROOT, 'dataset', 'yolo')

if __name__ == '__main__':
    out = OUT
    if '--out' in sys.argv:
        out = os.path.abspath(sys.argv[sys.argv.index('--out') + 1])
    jsonl = os.path.join(SRC, 'labels.jsonl')
    if not os.path.exists(jsonl):
        print('未找到 %s，请先在 ai_autoplay/config.json 开启 record_dataset 采集' % jsonl)
        sys.exit(1)

    classes = OrderedDict()
    n_img = 0
    img_out = os.path.join(out, 'images')
    lbl_out = os.path.join(out, 'labels')
    os.makedirs(img_out, exist_ok=True)
    os.makedirs(lbl_out, exist_ok=True)

    with open(jsonl, encoding='utf-8') as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            img_path = os.path.join(SRC, 'images', rec['image'])
            if not os.path.exists(img_path):
                continue
            # 取画面尺寸（用 pygame 读一次头；也可以在采集时缓存）
            import pygame
            os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
            if not pygame.get_init():
                pygame.init()
            surf = pygame.image.load(img_path)
            W, H = surf.get_size()
            lines = []
            for e in rec.get('entities', []):
                cname = e['class']
                if cname not in classes:
                    classes[cname] = len(classes)
                cx = (e['x'] + e['w'] / 2.0) / W
                cy = (e['y'] + e['h'] / 2.0) / H
                nw, nh = e['w'] / float(W), e['h'] / float(H)
                lines.append('%d %.4f %.4f %.4f %.4f' % (classes[cname], cx, cy, nw, nh))
            base = rec['image'][:-4]
            with open(os.path.join(img_out, rec['image']), 'wb') as fsrc, \
                 open(img_path, 'rb') as fdst:
                fsrc.write(fdst.read())
            with open(os.path.join(lbl_out, base + '.txt'), 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            n_img += 1

    with open(os.path.join(out, 'data.yaml'), 'w', encoding='utf-8') as f:
        f.write('path: %s\ntrain: images\nval: images\nnames:\n' % out)
        for name, idx in classes.items():
            f.write('  %d: %s\n' % (idx, name))
    print('导出 %d 张图，%d 个类别 → %s' % (n_img, len(classes), out))
