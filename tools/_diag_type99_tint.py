# -*- coding: utf-8 -*-
"""诊断 Type99 染色：mask alpha 分布 + 染色前后像素 diff"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import numpy as np
import pygame
pygame.init()
pygame.display.set_mode((1, 1))

from units.sprite_cache import load_parts, _tint_part, team_rgb, base_dir, mask_dir
from core.settings import TEAM_COLORS

print("TEAM_COLORS['team_0'] =", TEAM_COLORS.get('team_0'))
rgb = team_rgb('team_0')

base, masks = load_parts('Type99', 'team_0', 'CHINA')
for attr, m in masks.items():
    a = pygame.surfarray.array_alpha(m)
    rgb3 = pygame.surfarray.array3d(m)
    opaque = int((a > 0).sum())
    print("\nType99.%s: size=%s alpha>0=%d alpha统计 min=%d max=%d mean=%.0f"
          % (attr, m.get_size(), opaque, a.min(), a.max(), a.mean() if opaque else 0))
    if opaque:
        xs, ys = np.where(a > 0)
        print("  白区 RGB 样本:", [tuple(rgb3[x, y]) for x, y in list(zip(xs, ys))[:3]])
        b = base[attr]
        t = _tint_part(b, m, rgb)
        diff = (np.abs(pygame.surfarray.array3d(t).astype(int) -
                       pygame.surfarray.array3d(b).astype(int)).sum(axis=2) > 20) & (a > 0)
        print("  染色后与 base diff 像素（mask 白区内）=%d" % int(diff.sum()))

pygame.quit()
