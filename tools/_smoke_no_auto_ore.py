# -*- coding: utf-8 -*-
"""回归：MiningRig 建成不再自动生成矿坑"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
from pygame.math import Vector2 as vec
pygame.init()
pygame.display.set_mode((1, 1))

from units.buildings import MiningRig


class MockParticles:
    def add(self, *a, **k): pass


class MockMap:
    def __init__(self):
        self.width = 4800
        self.height = 3200
        self.ore_patches = []


class MockGame:
    def __init__(self):
        self.current_map = MockMap()
        self.all_units = []
        self.all_buildings = []
        self.particles = MockParticles()
        self.my_faction = "CHINA"
        self.enemy_faction = "USA"
        self.my_team = "team_0"
        self.team_resources = {"team_0": 5000}
        self.net_events = []
        self.is_online = False


g = MockGame()
n0 = len(g.current_map.ore_patches)
rig = MiningRig(g, vec(2400, 1600), "team_0")
# 模拟三条旧生成路径的直接调用已不可能（方法已删）；确认属性不存在且 patch 数不变
ok1 = not hasattr(rig, 'ensure_ore_field') or not callable(getattr(rig, 'ensure_ore_field', None))
print("PASS 方法已删除" if not hasattr(rig, 'ensure_ore_field') else "FAIL 方法仍存在")
print("PASS 不自动生成矿坑" if len(g.current_map.ore_patches) == n0 == 0
      else "FAIL 自动生成了 %d 个矿坑" % (len(g.current_map.ore_patches) - n0))

pygame.quit()
