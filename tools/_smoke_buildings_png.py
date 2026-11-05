# -*- coding: utf-8 -*-
"""无头冒烟：5 个重构建筑类 实例化 + 双 zoom draw + PNG 导出/加载双路径"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import pygame
pygame.init()
from pygame.math import Vector2

from units.buildings import RadarBuilding, PowerPlant, Airfield, ResearchCenter, Bastion


class MockParticles(object):
    def add(self, *a, **k):
        pass


class MockGame(object):
    def __init__(self):
        self.current_map = None
        self.all_units = []
        self.all_buildings = []
        self.particles = MockParticles()
        self.my_faction = 'CHINA'
        self.enemy_faction = 'USA'
        self.my_team = 'team_0'
        self.team_resources = {}
        self.net_events = []
        self.is_online = False
        self.teams_config = {'team_0': {'faction': 'CHINA'}}
        self.projectiles = []
        self.frame_count = 0


g = MockGame()
targets = [RadarBuilding, PowerPlant, Airfield, ResearchCenter, Bastion]
for cls in targets:
    name = cls.__name__
    b = cls(g, Vector2(400, 300), "team_0")
    assert hasattr(b, 'image'), name + ": missing self.image"
    w, h = b.image.get_width(), b.image.get_height()
    assert w > 10 and h > 10, name + ": bad image size %dx%d" % (w, h)
    ax, ay = b._image_anchor()
    print("%s image=%dx%d anchor=(%d,%d)" % (name, w, h, ax, ay))
    for zoom in (1.0, 0.5):
        surf = pygame.Surface((800, 600))
        b.draw(surf, Vector2(0, 0), zoom)

    # 第二次实例化：命中内存 PNG 缓存（suppress_draws + inject 路径）再各 draw 一次
    b2 = cls(g, Vector2(500, 380), "team_0")
    assert hasattr(b2, 'image') and b2.image.get_width() > 10, name + ": PNG-hit image missing"
    for zoom in (1.0, 0.5):
        surf = pygame.Surface((800, 600))
        b2.draw(surf, Vector2(0, 0), zoom)
    print("%s OK（首次现场绘制+自动导出、二次 PNG 注入两条路径均通过）" % name)

print("ALL SMOKE TESTS PASSED")
