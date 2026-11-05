# -*- coding: utf-8 -*-
"""训练本地检测模型并接入（路线 C 完整一条龙）。

流程：
    1) dataset/autoplay/labels.jsonl（游戏内自动标注采集）→ YOLO 格式
    2) ultralytics YOLOv8n 训练（CPU 也可跑，建议 epochs>=60）
    3) best.pt → ONNX 导出
    4) 拷贝为 ai_autoplay/detector.onnx + detector_names.json（类名映射）
       —— vision.load_detector() 会自动加载，agent 扫描时检测结果自动并入上下文

前置：游戏内 F10 开启自动游玩且 config.json "record_dataset": true，
     玩几局采集几百帧后再训练（数据越多越准）。

用法：
    python tools/train_detector.py                 # 默认 epochs=60
    python tools/train_detector.py --epochs 120    # 加大轮数
    python tools/train_detector.py --device 0      # 指定 GPU
依赖：pip install ultralytics onnx onnxruntime
"""
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DET_DIR = os.path.join(ROOT, 'ai_autoplay')
DATASET_DIR = os.path.join(ROOT, 'dataset', 'autoplay')


def main():
    epochs = 60
    if '--epochs' in sys.argv:
        epochs = int(sys.argv[sys.argv.index('--epochs') + 1])
    imgsz = int(sys.argv[sys.argv.index('--imgsz') + 1]) if '--imgsz' in sys.argv else 640
    batch = int(sys.argv[sys.argv.index('--batch') + 1]) if '--batch' in sys.argv else 8
    device = sys.argv[sys.argv.index('--device') + 1] if '--device' in sys.argv else ''

    jsonl = os.path.join(DATASET_DIR, 'labels.jsonl')
    if not os.path.exists(jsonl):
        print('[train] 未找到 %s' % jsonl)
        print('[train] 请先在 ai_autoplay/config.json 设 "record_dataset": true，')
        print('[train] 游戏内 F10 开启自动游玩，打几局采集训练数据后再运行本脚本。')
        sys.exit(1)
    n_frames = sum(1 for _ in open(jsonl, encoding='utf-8'))
    if n_frames < 50:
        print('[train] 仅采集到 %d 帧（建议 >=300 帧），继续训练但效果有限。' % n_frames)

    # ---- 1. 导出 YOLO 格式 ----
    print('[train] 步骤 1/3：导出 YOLO 数据集…')
    r = subprocess.call([sys.executable,
                         os.path.join(ROOT, 'tools', 'export_yolo_dataset.py')])
    if r != 0:
        print('[train] 导出失败')
        sys.exit(1)
    data_yaml = os.path.join(ROOT, 'dataset', 'yolo', 'data.yaml')

    # ---- 2. 训练 ----
    print('[train] 步骤 2/3：训练 YOLOv8n（epochs=%d imgsz=%d batch=%d）…' % (epochs, imgsz, batch))
    try:
        from ultralytics import YOLO
    except ImportError:
        print('[train] 缺少 ultralytics：pip install ultralytics onnx onnxruntime')
        sys.exit(1)
    model = YOLO('yolov8n.pt')       # 首次运行自动下载预训练权重
    model.train(data=data_yaml, epochs=epochs, imgsz=imgsz, batch=batch,
                device=device if device else None,
                project=os.path.join(ROOT, 'dataset', 'runs'),
                name='detector', exist_ok=True)

    # ---- 3. 导出 ONNX 并接入 ----
    print('[train] 步骤 3/3：导出 ONNX…')
    best_pt = os.path.join(ROOT, 'dataset', 'runs', 'detector', 'weights', 'best.pt')
    if not os.path.exists(best_pt):
        # ultralytics 可能加了版本后缀（detector2/3…），取最新的
        import glob
        cands = sorted(glob.glob(os.path.join(ROOT, 'dataset', 'runs',
                                              'detector*', 'weights', 'best.pt')),
                       key=os.path.getmtime)
        if not cands:
            print('[train] 未找到训练产物 best.pt')
            sys.exit(1)
        best_pt = cands[-1]
    best = YOLO(best_pt)
    onnx_path = best.export(format='onnx', imgsz=640)   # 返回导出文件路径
    dst = os.path.join(DET_DIR, 'detector.onnx')
    shutil.copy(onnx_path, dst)

    # 类名映射（id → 类名），供检测后处理还原类名
    names = {int(k): v for k, v in best.names.items()}
    with open(os.path.join(DET_DIR, 'detector_names.json'), 'w', encoding='utf-8') as f:
        json.dump(names, f, ensure_ascii=False, indent=1)

    print('[train] 完成：%s' % dst)
    print('[train] 类别数 %d：%s' % (len(names), names))
    print('[train] 重启游戏后 agent 自动加载检测器（HUD 显示检测数量）。')


if __name__ == '__main__':
    main()
