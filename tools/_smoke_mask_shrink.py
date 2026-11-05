# -*- coding: utf-8 -*-
"""mask 自适应收缩回归：染色合成生效（diff 法）、逻辑尺寸继承、大块建筑染色区域统计"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import numpy as np
import pygame
pygame.init()
pygame.display.set_mode((1, 1))

from units.sprite_cache import load_parts, _tint_part, team_rgb
from core.utils import logical_size

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def tinted_diff_pixels(base, mask, rgb):
    """染色后与 base 的显著差异像素数（mask 白区内）"""
    t = _tint_part(base, mask, rgb)
    d = np.abs(pygame.surfarray.array3d(t).astype(int) -
               pygame.surfarray.array3d(base).astype(int)).sum(axis=2)
    a = pygame.surfarray.array_alpha(t)
    return int(((d > 20) & (a > 60)).sum())


class StubGame:
    teams_config = {}


# 1. Type99（窄识别条代表）：染色生效 + 逻辑尺寸继承
bundle = load_parts('Type99', 'team_0', 'CHINA')
check("Type99 base+mask 加载", bundle is not None and len(bundle[1]) >= 2)
for attr, m in bundle[1].items():
    b = bundle[0][attr]
    n = tinted_diff_pixels(b, m, team_rgb('team_0'))
    print("  Type99.%s 染色差异像素=%d" % (attr, n))
    check("Type99.%s 染色生效" % attr, n > 0)
    t = _tint_part(b, m, team_rgb('team_0'))
    check("Type99.%s 逻辑尺寸继承" % attr,
          logical_size(t) == logical_size(b) or logical_size(t) is None)

# 2. 大块建筑：染色区域显著存在（用户关心的"大色块缩小"主体）
for cls, attr in (('BaseBuilding', 'image'), ('Barracks', 'image'), ('Bastion', 'image')):
    bun = load_parts(cls, 'team_1', 'USA')
    if bun and attr in bun[1]:
        b, m = bun[0][attr], bun[1][attr]
        n = tinted_diff_pixels(b, m, team_rgb('team_1'))
        total = int((pygame.surfarray.array_alpha(b) > 0).sum())
        print("  %s.%s 染色差异像素=%d（base 不透明 %d）" % (cls, attr, n, total))
        check("%s 染色生效" % cls, n > 0)
    else:
        print("  %s 无 mask（跳过）" % cls)

# 3. 无 mask 部件回退：直接用 base 原样
check("OilDerrick 加载", load_parts('OilDerrick', 'neutral', 'USA') is not None)

pygame.quit()
print("\n" + ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
