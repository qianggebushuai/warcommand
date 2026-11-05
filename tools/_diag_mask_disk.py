# -*- coding: utf-8 -*-
"""检查磁盘 mask PNG 原始 alpha 分布（未降采样）"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import numpy as np
import pygame
pygame.init()
pygame.display.set_mode((1, 1))

for cls in ('Type99', 'Bastion', 'BaseBuilding', 'Barracks'):
    mdir = os.path.join(ROOT, 'sprites', 'units', cls, 'mask')
    if not os.path.isdir(mdir):
        print(cls, ': 无 mask 目录')
        continue
    for fn in sorted(os.listdir(mdir)):
        if not fn.endswith('.png'):
            continue
        m = pygame.image.load(os.path.join(mdir, fn)).convert_alpha()
        a = pygame.surfarray.array_alpha(m)
        solid = int((a >= 250).sum())
        semi = int(((a > 0) & (a < 250)).sum())
        print('%-14s %-18s size=%s solid=%d semi=%d' % (cls, fn, m.get_size(), solid, semi))

pygame.quit()
