# -*- coding: utf-8 -*-
"""单帧插桩：看 stationary 分支是否进入、横船代码是否执行"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import pygame
from pygame.math import Vector2 as vec
pygame.init()
pygame.display.set_mode((1, 1))

from units.ships import Battleship


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
ship = Battleship(g, vec(0, 0), "team_0")
ship.target_entity = MockTarget((500, 0))
ship.attack_cooldown = 999999

import math
for i in range(5):
    dist = ship.pos.distance_to(ship.target_entity.pos)
    print("frame %d: angle=%.2f dist=%.0f range=%.0f alive=%s" %
          (i, ship.angle, dist, ship.attack_range, ship.target_entity.alive))
    ship.update()

# 手动复算横船分支
diff = ship.target_entity.pos - ship.pos
target_angle = math.degrees(math.atan2(-diff.y, diff.x))
d_to_t = (target_angle - ship.angle + 180) % 360 - 180
desired = target_angle + (90 if d_to_t >= 0 else -90)
d = (desired - ship.angle + 180) % 360 - 180
print("target_angle=%.2f d_to_t=%.2f desired=%.2f d=%.2f" % (target_angle, d_to_t, desired, d))

pygame.quit()
