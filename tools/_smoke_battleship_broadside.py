# -*- coding: utf-8 -*-
"""战列舰横船机动回归：射程内停船后船体与目标方向垂直（±90°），炮塔照常"""
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


fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + extra)
    if not cond:
        fails.append(name)


def norm(a):
    return (a + 180) % 360 - 180


# 场景1：目标正东，船初始船头对准目标（angle=0）→ 应转到 ±90
g = MockGame()
ship = Battleship(g, vec(0, 0), "team_0")
ship.target_entity = MockTarget((500, 0))
ship.attack_cooldown = 999999   # 冒烟不真开火
for _ in range(700):
    ship.update()
    g.frame_count += 1
check("正对目标→横船垂直(|angle∓90|<2)", abs(norm(ship.angle - 90)) < 2 or abs(norm(ship.angle + 90)) < 2,
      " (final angle=%.1f)" % ship.angle)

# 场景2：目标正东，船尾对目标（angle=180）→ 就近舷转到 ±90
ship2 = Battleship(g, vec(0, 0), "team_0")
ship2.target_entity = MockTarget((500, 0))
ship2.attack_cooldown = 999999
ship2.angle = 180.0
for _ in range(700):
    ship2.update()
    g.frame_count += 1
check("背对目标→就近舷垂直", abs(norm(ship2.angle - 90)) < 2 or abs(norm(ship2.angle + 90)) < 2,
      " (final angle=%.1f)" % ship2.angle)

# 场景3：目标移动到另一侧，船体跟随横船（目标改到正北）
ship.target_entity = MockTarget((0, -500))
for _ in range(700):
    ship.update()
    g.frame_count += 1
check("目标变向→重新横船垂直", abs(norm(ship.angle)) < 2 or abs(norm(abs(ship.angle) - 180)) < 2,
      " (final angle=%.1f)" % ship.angle)

# 场景4：期间位置不动（停船横转，不驶向目标）
check("横转期间保持原地", (ship.pos - vec(0, 0)).length() < 5, " (pos=%.0f,%.0f)" % (ship.pos.x, ship.pos.y))

pygame.quit()
print("\n" + ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
