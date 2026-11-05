# -*- coding: utf-8 -*-
"""AI 单位射程攻击冒烟：停在最大射程开火，不挤建筑墙边。"""
import os
import sys

os.environ['SDL_VIDEODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from pygame.math import Vector2 as vec

PASS = TOTAL = 0
def check(name, cond, detail=""):
    global PASS, TOTAL
    TOTAL += 1
    if cond:
        PASS += 1
        print("PASS  " + name)
    else:
        print("FAIL  " + name + "  " + str(detail))

# SCREEN_WIDTH import 陷阱：先建真窗口再 import 项目模块
pygame.init()
pygame.display.set_mode((1600, 900))

from map_layout_editor import MapLayoutEditor
from units.base import Unit

ed = MapLayoutEditor(0)
ed.game.frame_count = 0
ed.game.all_units = []
ed.game.all_buildings = []


class FakeTarget:
    """最小实体替身：足够 set_target / update / perform_attack 消费"""
    def __init__(self, pos, radius=150, team="team_1"):
        self.pos = vec(pos)
        self.radius = radius
        self.team = team
        self.alive = True
        self.hp = 10000
        self.is_air = False


class _Probe(Unit):
    def __init__(self, game, pos, attack_range=300):
        super().__init__(game, pos, "team_0")
        self.speed = 3
        self.attack_range = attack_range
        self.detectrange = 300


def fresh_probe(pos):
    p = _Probe(ed.game, vec(pos))
    ed.game.all_units.append(p)
    return p

# ---- 1. 边缘射程：dist > attack_range 但 <= range+radius 即开火 ----
b1 = FakeTarget((900, 300), radius=150)          # 距 (480,300) 为 420
p1 = fresh_probe((480, 300))
p1.attack_range = 300
p1.set_target(b1)
p1.update()
check("1 边缘射程开火(420>300 但<=450)", p1.attack_cooldown > 0, p1.attack_cooldown)

# ---- 2. 射程外只推进不开火 ----
ed.game.all_units = []
b2 = FakeTarget((1480, 300), radius=150)         # 距 (480,300) 为 1000 > 450
p2 = fresh_probe((480, 300))
p2.attack_range = 300
p2.set_target(b2)
p2.update()
check("2 射程外不开火且在推进", p2.attack_cooldown == 0 and p2.target_entity is b2,
      (p2.attack_cooldown, p2.pos))

# ---- 3. 推进到射程环即停即打（不冲到中心/墙边）----
ed.game.all_units = []
b3 = FakeTarget((1800, 300), radius=150)         # 距 (600,300) 为 1200
p3 = fresh_probe((600, 300))
p3.attack_range = 300
p3.set_target(b3)
fire_dist = None
for _ in range(600):
    p3.update()
    ed.game.frame_count += 1
    if p3.attack_cooldown > 0:
        fire_dist = p3.pos.distance_to(b3.pos)
        break
check("3 推进后在射程环开火", fire_dist is not None and 300 < fire_dist <= 460,
      fire_dist)
check("3b 未冲进建筑半径内", fire_dist is not None and fire_dist >= b3.radius,
      fire_dist)

# ---- 4. 索敌半径固定 300 侦察圈（长射程单位玩家可控，不自动远距索敌） ----
ed.game.all_units = []
enemy = FakeTarget((1100, 300), radius=15)       # 距 (500,300) 为 600
ed.game.all_units.append(enemy)
art = _Probe(ed.game, vec(500, 300), attack_range=700)
check("4a 火炮单位600px不自动索敌(可控性)", art.find_nearest_enemy() is None)
near = FakeTarget((750, 300), radius=15)         # 距 (500,300) 为 250 < 300
ed.game.all_units.append(near)
check("4b 侦察圈内仍自动索敌", art.find_nearest_enemy() is near)

# ---- 5-7. AI _engage_orders 下令语义 ----
from ai.ai_logic import AICommander
cmd = AICommander(ed.game, "team_1")

ed.game.all_units = []
p5 = fresh_probe((500, 300))
building = FakeTarget((1800, 300), radius=150)
cmd._engage_orders([p5], building)
check("5 实体目标→set_target(ATTACK)", p5.ai_mode == "ATTACK" and p5.target_entity is building)

p6 = fresh_probe((500, 500))
cmd._engage_orders([p6], vec(1000, 500))
check("6 坐标目标→move_to散布", p6.ai_mode == "MOVE" and p6.target_pos is not None)

air_target = FakeTarget((600, 600), radius=15)
air_target.is_air = True
p7 = fresh_probe((500, 600))
p7.can_attack_air = False
p7.set_target(air_target)
check("7 不能打空的目标回退move_to", p7.target_entity is None and p7.target_pos is not None)

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
