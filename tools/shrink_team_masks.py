# -*- coding: utf-8 -*-
"""把 sprites/units/*/mask/*.png 的白色区域边缘向内收缩（缩小阵营染色区域）。

用法（在项目根目录）:
    python tools/shrink_team_masks.py [收缩像素，默认 3]

对已存在的 mask PNG 做腐蚀后原位覆盖；base/ 不动。
小面积遮罩自动降级（腐蚀后面积 <25% 即停），避免细条/标志被腐蚀消失。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import pygame
from units.sprite_cache import shrink_mask

MASK_ROOT = os.path.join(ROOT, 'sprites', 'units')

pygame.init()
pygame.display.set_mode((1, 1))

px = int(sys.argv[1]) if len(sys.argv) > 1 else 3

total = 0
changed = 0
for cls in sorted(os.listdir(MASK_ROOT)):
    mdir = os.path.join(MASK_ROOT, cls, 'mask')
    if not os.path.isdir(mdir):
        continue
    for fn in sorted(os.listdir(mdir)):
        if not fn.lower().endswith('.png'):
            continue
        path = os.path.join(mdir, fn)
        total += 1
        try:
            surf = pygame.image.load(path).convert_alpha()
            before = pygame.surfarray.array_alpha(surf)
            before_n = int((before > 0).sum())
            shrunk = shrink_mask(surf.copy(), px)
            after_n = int((pygame.surfarray.array_alpha(shrunk) > 0).sum())
            if after_n < before_n:
                pygame.image.save(shrunk, path)
                changed += 1
                print('%-24s %-18s %6d -> %6d (-%d%%)' % (
                    cls, fn, before_n, after_n,
                    int(100 * (before_n - after_n) / max(1, before_n))))
        except Exception as e:
            print('FAIL %s/%s: %s' % (cls, fn, e))

print('\n共 %d 个 mask，收缩 %d 个（边缘 %dpx）' % (total, changed, px))
