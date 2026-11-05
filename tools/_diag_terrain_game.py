# -*- coding: utf-8 -*-
"""复现主游戏真实加载时序，验证 poly 水域是否进 game.lakes。"""
import os
import sys

os.environ['SDL_VIDEODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from pygame.math import Vector2 as vec
pygame.init()
pygame.display.set_mode((1600, 900))

from maps.map_data import WildernessMap, lake_contains
from maps.map_data import TERRAIN_POLY_COLORS, point_in_poly

class MockGame:
    def __init__(self):
        self.current_map = None
        self.lakes = []
        self.all_buildings = []
        self.frame_count = 0
        self.zoom = 1.0

g = MockGame()

# === 复刻 core_mixin:484-491 时序 ===
g.current_map = WildernessMap(g)          # MapClass(self)
m = g.current_map

# === 复刻 init_level else 分支（generate 前，构造期） ===
g.lakes = m.lakes                          # 空列表引用
import random
random.seed(1)
for _ in range(5):                         # init_level 的随机湖
    cx = random.randint(200, 7000); cy = random.randint(200, 4000)
    w, h = random.randint(100, 300), random.randint(100, 300)
    g.lakes.append({'rect': pygame.Rect(cx-w//2, cy-h//2, w, h), 'parts': [(cx, cy, w, h)]})
print("构造期: game.lakes =", len(g.lakes), "current_map.lakes =", len(m.lakes),
      "同引用:", g.lakes is m.lakes)

# === 复刻 update_loading:293-301（Host/Single，含新增对齐行） ===
m.generate(seed=12345)
g.lakes = m.lakes                          # level_mixin:296 对齐（generate 重置视觉湖后）
print("generate 后: current_map.lakes =", len(m.lakes), "game.lakes =", len(g.lakes),
      "同引用:", g.lakes is m.lakes)
m.apply_layout_override()
print("apply 后: game.lakes =", len(g.lakes),
      "poly条目:", len([l for l in g.lakes if isinstance(l, dict) and l.get('from_terrain')]),
      "current_map.terrain_polys =", len(m.terrain_polys))

from units.base import Unit
class P(Unit):
    def __init__(self, game, pos):
        super().__init__(game, pos, "team_0")

if m.terrain_polys:
    pts = m.terrain_polys[0]['poly']
    cx = sum(p[0] for p in pts)/len(pts); cy = sum(p[1] for p in pts)/len(pts)
    hit = any(lake_contains(l, cx, cy) for l in g.lakes)
    print(f"poly中心({cx:.0f},{cy:.0f}) 在 game.lakes 判定: {hit}")
    u = P(g, vec(300, 300))
    print("can_pass(poly中心):", u.check_move_validity(vec(cx, cy)))
else:
    print("!! terrain_polys 为空 —— JSON 未生效")

# 修复点验证：官方视觉湖（generate 画的）也应有判定——取官方湖中心测试
u2 = P(g, vec(300, 300))
official = [l for l in m.lakes if not (isinstance(l, dict) and l.get('from_terrain'))]
ok_official = 0
for l in official:
    r = l['rect'] if isinstance(l, dict) else l
    c = vec(r.x + r.w/2, r.y + r.h/2)
    if u2.check_move_validity(c) is False:
        ok_official += 1
print(f"官方视觉湖中心拦截: {ok_official}/{len(official)}（应为全部）")
print("game.lakes 与 current_map.lakes 同引用:", g.lakes is m.lakes)
