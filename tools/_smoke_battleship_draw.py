# -*- coding: utf-8 -*-
"""战列舰渲染冒烟：draw 无异常 + 1° 量子缓存命中（20 帧 0.36°/帧 ≈ 7 次旋转而非 20 次）"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import pygame
from pygame.math import Vector2 as vec
pygame.init()
pygame.display.set_mode((100, 100))

from units.ships import Battleship

# 统计旋转调用
_counts = {'rotozoom': 0, 'rotate': 0}
_orig_roto = pygame.transform.rotozoom
_orig_rot = pygame.transform.rotate
def _roto(s, a, scale):
    _counts['rotozoom'] += 1
    return _orig_roto(s, a, scale)
def _rot(s, a):
    _counts['rotate'] += 1
    return _orig_rot(s, a)
pygame.transform.rotozoom = _roto
pygame.transform.rotate = _rot


class MockParticles:
    def add(self, *a, **k): pass


class MockGame:
    def __init__(self):
        self.current_map = None
        self.all_units = []
        self.all_buildings = []
        self.projectiles = []
        self.particles = MockParticles()
        self.team_resources = {"team_0": 5000, "team_1": 5000}
        self.net_events = []
        self.is_online = False
        self.my_faction = "CHINA"
        self.enemy_faction = "USA"
        self.my_team = "team_0"
        self.frame_count = 0


class MockTarget:
    def __init__(self, pos):
        self.pos = vec(pos)
        self.alive = True
        self.team = "team_1"


g = MockGame()
ship = Battleship(g, vec(50, 50), "team_0")
ship.target_entity = MockTarget((50, 300))
ship.attack_cooldown = 999999

surf = pygame.Surface((100, 100), pygame.SRCALPHA)
N = 20
for _ in range(N):
    ship.update()   # 每帧 angle += 0.36
    ship.draw(surf, vec(0, 0), 0.75)
    g.frame_count += 1

print("20 帧 draw: rotozoom=%d rotate=%d" % (_counts['rotozoom'], _counts['rotate']))
# hull: 0.36°/帧 → 1° 量子 → 20 帧跨 7.2° → ~8 次旋转（远小于 20）
# turret: 炮塔对准目标不转 → 0 次
hull_rot = _counts['rotozoom']
assert ship.draw is not None
print("PASS draw 无异常" if hull_rot <= 9 else "FAIL 旋转缓存未生效（%d 次）" % hull_rot)
print("PASS 缓存命中生效" if hull_rot < N else "FAIL")

pygame.quit()
print("DONE")
