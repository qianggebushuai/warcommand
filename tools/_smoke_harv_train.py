# -*- coding: utf-8 -*-
"""冒烟：①侧栏工厂矿车选项（三处下单路径时长映射）②列车刷新还原队伍不再卡住。"""
import os
import sys

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from pygame.math import Vector2 as vec

pygame.init()
pygame.display.set_mode((1600, 900))

PASS = TOTAL = 0
def check(name, cond, detail=""):
    global PASS, TOTAL
    TOTAL += 1
    if cond:
        PASS += 1
    print(("PASS  " if cond else "FAIL  ") + name + ("  " + str(detail) if not cond else ""))

from map_layout_editor import MapLayoutEditor
from core import settings
from core.settings import HARVESTER_COST, BUILD_TIME_HARVESTER
from units.buildings import FactoryBuilding
from units.vehicles import ArmoredTrain
from panels.ui_sidebar import Sidebar
from game.special_units_mixin import SpecialUnitManager

g = MapLayoutEditor(0).game
g.all_units = []
g.all_buildings = []
TEAM = "team_0"
g.my_team = TEAM
g.team_resources = {TEAM: 50000}
g.player_base = None

# ---- ① 侧栏 UNIT 标签存在 Harvester 项（factory 前置、价格=HARVESTER_COST）----
side = Sidebar(g)
h_items = [it for it in side.all_items["UNIT"] if it.payload == "harvester"]
check("1 侧栏UNIT存在harvester项且factory前置/实价",
      len(h_items) == 1 and h_items[0].cost == HARVESTER_COST
      and h_items[0].req_building == "factory",
      [(it.payload, it.cost, it.req_building) for it in h_items])

# ---- ② auto_queue_unit('harvester') → factory 队列 + BUILD_TIME_HARVESTER + 扣款 ----
fac = FactoryBuilding(g, vec(500, 500), TEAM)
fac.is_upgraded = True
g.all_buildings = [fac]
g.team_resources[TEAM] = 10000
ok = side.auto_queue_unit("harvester", HARVESTER_COST)
check("2 auto_queue_unit排矿车入factory队列(BUILD_TIME_HARVESTER)",
      ok and ("harvester", BUILD_TIME_HARVESTER) in fac.production_queue,
      (ok, fac.production_queue))
check("3 扣款=HARVESTER_COST",
      g.team_resources[TEAM] == 10000 - HARVESTER_COST, g.team_resources[TEAM])
fac.production_queue.clear()
fac.current_production = None

# ---- ③ 列车死亡→刷新还原生前队伍→向目标点移动 ----
class _MgrGame:
    def __init__(self):
        self.frame_count = 0
        self.all_units = []
        self.all_buildings = []
        self.particles = pygame.sprite.Group()
        self.is_online = False
        self.my_role = "HOST"

mg = _MgrGame()
mgr = SpecialUnitManager(mg)
spawn_pos = vec(2000, 600)
target = vec(2000, 2600)
train = ArmoredTrain(mg, spawn_pos)
mg.all_units.append(train)
train.change_team(TEAM)  # 玩家夺取
spec = {"type": "Train", "spawn": vec(spawn_pos), "target": vec(target),
        "respawn_frames": 30, "unit": train, "dead_at": None, "last_team": None}
mgr.specs = [spec]
train.special_spec = spec

# 移动 5 帧确认活列车会向目标走（基线：先下发目标点，有目标且非中立才移动）
train.move_to(target)
y0 = train.pos.y
for _ in range(5):
    train.update()
moved_alive = train.pos.y > y0

# 击杀（不调 die()，模拟扫描式检测）→ 快进 40 帧
train.alive = False
for _ in range(40):
    mg.frame_count += 1
    mgr.update()

new_train = [u for u in mg.all_units if isinstance(u, ArmoredTrain) and u.alive]
check("4 列车刷新后队伍还原(非中立)",
      len(new_train) == 1 and new_train[0].team == TEAM,
      [(u.team,) for u in new_train])
check("5 车厢队伍同步还原",
      all(c.team == TEAM for c in new_train[0].carriages),
      [(c.team,) for c in new_train[0].carriages])

# 刷新后的列车会移动：update 后 y 朝 target 前进
t2 = new_train[0]
y1 = t2.pos.y
for _ in range(5):
    t2.update()
check("6 刷新列车向目标点移动", t2.pos.y > y1, (y1, t2.pos.y))

check("7 对照：活列车移动机制正常", moved_alive)

# ---- ④ 中立列车死亡→刷新保持中立，且中立态即向目标点行驶（进场效果）----
train3 = ArmoredTrain(mg, vec(3000, 600))
mg.all_units.append(train3)
spec3 = {"type": "Train", "spawn": vec(3000, 600), "target": vec(3000, 2000),
         "respawn_frames": 30, "unit": train3, "dead_at": None, "last_team": None}
mgr.specs.append(spec3)
train3.special_spec = spec3
train3.alive = False
for _ in range(40):
    mg.frame_count += 1
    mgr.update()
t3 = [u for u in mg.all_units if isinstance(u, ArmoredTrain) and u.alive
      and u is not t2]
check("8 中立列车刷新保持中立(初始态不变)",
      len(t3) == 1 and t3[0].team == "neutral",
      [(u.team,) for u in t3])
y2 = t3[0].pos.y
for _ in range(5):
    t3[0].update()
check("9 中立列车带目标点即行驶(刷新出场即进场)",
      t3[0].pos.y > y2, (y2, t3[0].pos.y))

# ---- ⑤ 矿车交付：送最近矿场而非工厂；无矿场不执行换矿 ----
from units.vehicles import Harvester
from units.buildings import MiningRig

class _MgrGame:
    def __init__(self):
        self.frame_count = 0
        self.all_units = []
        self.all_buildings = []
        self.particles = pygame.sprite.Group()
        self.is_online = False
        self.my_role = "HOST"
        self.team_resources = {}
        self.show_alert = lambda *a, **k: None

mg.team_resources = {TEAM: 0}
mg.show_alert = lambda *a, **k: None
mg.current_map = None   # getattr(None,'ore_patches',[])=[] → 卸货后 IDLE 找矿不崩
h = Harvester(mg, vec(5000, 5000), TEAM, None)   # home=None：证明不再回 home 卸货
mg.all_units.append(h)
h.ore_cargo = 100
h.state = "RETURNING"
h._update_mining_ai()
check("10 无矿场不换矿(货舱保留原地待命)",
      h.ore_cargo == 100 and h.state == "RETURNING" and h.pos == vec(5000, 5000),
      (h.ore_cargo, h.state, h.pos))

rig_far = MiningRig(mg, vec(5600, 5000), TEAM)   # 距矿车 600
rig_near = MiningRig(mg, vec(5200, 5000), TEAM)  # 距矿车 200
mg.all_buildings += [rig_far, rig_near]
for _ in range(150):
    h._update_mining_ai()
check("11 交付到最近矿场并到账",
      h.ore_cargo == 0 and mg.team_resources[TEAM] == 100,
      (h.ore_cargo, mg.team_resources[TEAM]))
check("12 停在近矿场旁(非工厂/远矿场)",
      h.pos.distance_to(vec(5200, 5000)) < 80,
      (h.pos, h.pos.distance_to(vec(5200, 5000))))

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
