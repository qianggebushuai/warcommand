# -*- coding: utf-8 -*-
"""复现 CrossfireMap update_effects 崩溃（islands 含地形 dict 条目 + collidelist）。"""
import os
import sys

os.environ['SDL_VIDEODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from pygame.math import Vector2 as vec

pygame.init()
pygame.display.set_mode((1600, 900))

import random
random.seed(12345)

from maps.map_data import CrossfireMap


class DummyGame:
    pass


m = CrossfireMap(DummyGame())
m.generate(12345)
n_islands0 = len(getattr(m, 'islands', []))
m.apply_layout_override()
n_terrain = len(getattr(m, 'terrain_polys', []))
n_islands1 = len(getattr(m, 'islands', []))
print(f"islands: generate后={n_islands0} apply后={n_islands1} terrain_polys={n_terrain}")
assert n_islands1 > n_islands0, "terrain land 条目未注入 islands（复现前提不成立）"


class FakeEnv:
    def set_weather(self, w):
        pass


class FakeGame:
    current_music_state = None
    env_manager = FakeEnv()
    camera_offset = vec(0, 0)
    zoom = 1.0
    screen = None


g = FakeGame()
g.screen = pygame.display.get_surface()
for f in range(600):   # update_effects 崩溃分支 random<0.4 每帧，600 帧必触发
    m.update_effects(g)
print("update_effects x600 OK — 无 TypeError，崩溃已修复")
