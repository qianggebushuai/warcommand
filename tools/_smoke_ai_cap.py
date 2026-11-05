# -*- coding: utf-8 -*-
"""AI 出兵上限/出兵速度对齐/建筑 hp 配置化 冒烟（不改任何布局 JSON，只读不写）。"""
import os
import sys
import json

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
from units import Harvester, Engineer
from units.buildings import BaseBuilding, Barracks, FactoryBuilding, PowerPlant, Airfield
from ai.ai_logic import AICommander
from core import settings
from core.settings import (AI_UNIT_CAP_BASE, AI_UNIT_CAP_PER_HARVESTER,
                           AI_HARVESTER_TARGET,
                           BUILD_TIME_INFANTRY, BUILD_TIME_TANK, BUILD_TIME_AIRSHIP,
                           BASE_HP, BARRACKS_HP, POWER_PLANT_HP, FACTORY_HP,
                           M1A2_COST, TYPE99_COST, RIFLEMAN_COST, KIROV_COST)

ed = MapLayoutEditor(0)
g = ed.game
g.all_units = []
g.all_buildings = []
g.team_resources = {"team_0": 50000}

TEAM = "team_0"
cmd = AICommander(g, TEAM)   # ① AICommander 可构造


class _Soldier(Unit):
    """最小战斗单位替身（计入 n_combat）"""
    def __init__(self, team=TEAM):
        super().__init__(g, vec(100, 100), team)
        self.unit_type = "rifleman"
        self.speed = 0


class _FakeHarv(Harvester):
    """矿车替身（isinstance 命中即可，绕过重初始化）"""
    def __init__(self, team=TEAM):
        self.team = team
        self.alive = True


class _FakeEng(Engineer):
    """工程师替身（按 ai_logic :330 过滤不计入 n_combat）"""
    def __init__(self, team=TEAM):
        self.team = team
        self.alive = True


def make_factory():
    f = FactoryBuilding(g, vec(500, 500), TEAM)
    f.is_upgraded = True   # 关闭升级扣款副作用，保证资金断言稳定
    g.all_buildings = [f]
    return f


def trigger_production():
    """production_cooldown 置 29 后调用一次，即触发 30 帧节流的造兵逻辑"""
    cmd.production_cooldown = 29
    cmd.ai_military_production()


# ---- ② cap 数学：矿车达补车目标(AI_HARVESTER_TARGET)→不触发补车分支，
#      cap = BASE + N*PER；低于 cap 正常排兵 ----
harvs = [_FakeHarv() for _ in range(AI_HARVESTER_TARGET)]
cap = AI_UNIT_CAP_BASE + AI_UNIT_CAP_PER_HARVESTER * AI_HARVESTER_TARGET
g.all_units = [_Soldier() for _ in range(cap - 1)] + harvs
f = make_factory()
trigger_production()
check("1 %d矿车cap=BASE+%d*PER 且低于上限时排兵" % (AI_HARVESTER_TARGET, AI_HARVESTER_TARGET),
      len(f.production_queue) >= 1, (cap, f.production_queue))

# ---- ② 达到 cap：30 帧后不排兵（production_queue 空）----
g.all_units = [_Soldier() for _ in range(cap)] + harvs
f2 = make_factory()
trigger_production()
check("2 达到上限后 30 帧不排兵", f2.production_queue == [], f2.production_queue)

# ---- Engineer 不计入 n_combat（:330 同款过滤）：39 士兵+5 工程师仍可排兵 ----
g.all_units = [_Soldier() for _ in range(cap - 1)] + [_FakeEng() for _ in range(5)] + harvs
f3 = make_factory()
trigger_production()
check("3 工程师不计入部队上限", len(f3.production_queue) >= 1, f3.production_queue)

# ---- 敌方矿车不计入 cap：己方矿车达补车目标(不触发补车分支)，
#      己方士兵达 cap(含敌方矿车虚增后仍未达) → 不排兵 ----
g.all_units = ([_Soldier() for _ in range(cap)]
               + [_FakeHarv() for _ in range(AI_HARVESTER_TARGET)]
               + [_FakeHarv("team_1") for _ in range(3)])
f4 = make_factory()
trigger_production()
check("4 敌方矿车不提升上限", f4.production_queue == [], f4.production_queue)

# ---- ③ 出兵速度对齐玩家：rifleman/m1a2/type99/kirov 的 time_cost 引用 BUILD_TIME_* ----
barr = Barracks(g, vec(700, 500), TEAM)
g.all_units = []
g.team_resources[TEAM] = 10000
cmd.try_queue_unit(barr, "rifleman")
check("5 rifleman 排队时长==BUILD_TIME_INFANTRY 且扣 RIFLEMAN_COST",
      barr.production_queue == [("rifleman", BUILD_TIME_INFANTRY)]
      and g.team_resources[TEAM] == 10000 - RIFLEMAN_COST,
      (barr.production_queue, g.team_resources[TEAM]))

fac = make_factory()
g.team_resources[TEAM] = 10000
cmd.try_queue_unit(fac, "m1a2")
check("6 m1a2 排队时长==BUILD_TIME_TANK 且扣 M1A2_COST",
      fac.production_queue == [("m1a2", BUILD_TIME_TANK)]
      and g.team_resources[TEAM] == 10000 - M1A2_COST,
      (fac.production_queue, g.team_resources[TEAM]))

fac2 = make_factory()
g.team_resources[TEAM] = 10000
cmd.try_queue_unit(fac2, "type99")
check("7 type99 排队时长==BUILD_TIME_TANK 且扣 TYPE99_COST(与玩家同价)",
      fac2.production_queue == [("type99", BUILD_TIME_TANK)]
      and g.team_resources[TEAM] == 10000 - TYPE99_COST,
      (fac2.production_queue, g.team_resources[TEAM]))

air = Airfield(g, vec(900, 500), TEAM)
g.team_resources[TEAM] = 10000
cmd.try_queue_unit(air, "kirov")
check("8 kirov 排队时长==BUILD_TIME_AIRSHIP 且扣 KIROV_COST",
      air.production_queue == [("kirov", BUILD_TIME_AIRSHIP)]
      and g.team_resources[TEAM] == 10000 - KIROV_COST,
      (air.production_queue, g.team_resources[TEAM]))

# ---- ④ 建筑 hp 引用 settings 常量 ----
base = BaseBuilding(g, vec(100, 100), TEAM)
check("9 BaseBuilding().hp==BASE_HP 且 max_hp 同步",
      base.hp == BASE_HP and base.max_hp == BASE_HP, (base.hp, BASE_HP))
barr2 = Barracks(g, vec(150, 100), TEAM)
check("10 Barracks().hp==BARRACKS_HP 且 max_hp 同步",
      barr2.hp == BARRACKS_HP and barr2.max_hp == BARRACKS_HP, (barr2.hp, BARRACKS_HP))
pp = PowerPlant(g, vec(200, 100), TEAM)
check("11 PowerPlant().hp==POWER_PLANT_HP（回归不破坏既有配置化）",
      pp.hp == POWER_PLANT_HP and pp.max_hp == POWER_PLANT_HP, (pp.hp, POWER_PLANT_HP))
check("12 FactoryBuilding().hp==FACTORY_HP 且 max_hp 同步",
      fac.hp == FACTORY_HP and fac.max_hp == FACTORY_HP, (fac.hp, FACTORY_HP))

# ---- ⑤ units.json：ai 分区两键 + buildings 新键 >=13 ----
_cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "units.json")
data = json.load(open(_cfg_path, encoding="utf-8"))
ai_sec = data.get("ai", {})
new_bld_keys = ["BASE_HP", "MERCENARY_FACTORY_HP", "FACTORY_HP", "BARRACKS_HP",
                "RADAR_HP", "MINING_RIG_HP", "AIRFIELD_HP", "RESEARCH_CENTER_HP",
                "SHROUD_GEN_HP", "PROTOTYPE_GEN_HP", "IRON_CURTAIN_HP",
                "LIGHTHOUSE_HP", "BASTION_HP"]
present = [k for k in new_bld_keys if k in data.get("buildings", {})]
check("13 units.json ai 分区两键且与 settings 默认一致",
      ai_sec.get("AI_UNIT_CAP_BASE") == 16 == settings.AI_UNIT_CAP_BASE
      and ai_sec.get("AI_UNIT_CAP_PER_HARVESTER") == 8 == settings.AI_UNIT_CAP_PER_HARVESTER,
      (ai_sec, settings.AI_UNIT_CAP_BASE, settings.AI_UNIT_CAP_PER_HARVESTER))
check("14 units.json buildings 分区新增建筑血量键 >=13", len(present) >= 13, present)

# ---- ⑥ config_center 分区表含 'ai' ----
import config_center
check("15 config_center 分区表含 'ai'(电脑AI) 页签",
      'ai' in config_center.TAB_KEYS and config_center.TAB_NAMES.get('ai') == u'电脑AI',
      config_center.TAB_KEYS)

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
