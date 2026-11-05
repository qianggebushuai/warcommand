# -*- coding: utf-8 -*-
"""AI 补矿车（经济自平衡）+ 菜单/设置界面闪烁修复 冒烟（不改任何布局 JSON，只读不写）。"""
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
from units import Harvester
from units.buildings import FactoryBuilding
from ai.ai_logic import AICommander
from core import settings
from core.settings import (AI_UNIT_CAP_BASE, AI_UNIT_CAP_PER_HARVESTER,
                           AI_HARVESTER_TARGET, BUILD_TIME_TANK,
                           BUILD_TIME_HARVESTER, HARVESTER_COST)
from game.menu_mixin import MenuMixin
from panels.basesetting import BaseSettingUI

ed = MapLayoutEditor(0)
g = ed.game
g.all_units = []
g.all_buildings = []
g.team_resources = {"team_0": 50000}

TEAM = "team_0"
cmd = AICommander(g, TEAM)
cmd.state = "DEVELOP"


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


def make_factory():
    f = FactoryBuilding(g, vec(500, 500), TEAM)
    f.is_upgraded = True   # 关闭升级扣款副作用，保证资金断言稳定
    g.all_buildings = [f]
    return f


def trigger_production():
    """production_cooldown 置 29 后调用一次，即触发 30 帧节流的造兵逻辑"""
    cmd.production_cooldown = 29
    cmd.ai_military_production()


# ---- ① 矿车 2<4 且 factory 有钱 → 30 帧后 factory 队列出现 harvester ----
g.all_units = [_FakeHarv() for _ in range(2)]
f1 = make_factory()
g.team_resources[TEAM] = 10000
trigger_production()
check("1 矿车2<4且有钱→factory队列出现harvester(BUILD_TIME_HARVESTER)",
      ("harvester", BUILD_TIME_HARVESTER) in f1.production_queue, f1.production_queue)

# ---- ② 排矿车扣款（units.json HARVESTER_COST=800，AI 与玩家同价）----
check("2 排矿车扣款=HARVESTER_COST", g.team_resources[TEAM] == 10000 - HARVESTER_COST,
      g.team_resources[TEAM])

# ---- ③ 矿车 4（达目标）→ 不补矿车 ----
g.all_units = [_FakeHarv() for _ in range(AI_HARVESTER_TARGET)]
f2 = make_factory()
g.team_resources[TEAM] = 10000
trigger_production()
check("3 矿车达目标数→不补矿车",
      all(t != "harvester" for t, _ in f2.production_queue), f2.production_queue)

# ---- ④ 战斗单位达 cap（16+8*n_harv）但矿车不足 → 仍优先补矿车 ----
n_harv = 2
cap2 = AI_UNIT_CAP_BASE + AI_UNIT_CAP_PER_HARVESTER * n_harv
g.all_units = [_Soldier() for _ in range(cap2)] + [_FakeHarv() for _ in range(n_harv)]
f3 = make_factory()
g.team_resources[TEAM] = 10000
trigger_production()
check("4 战斗单位达cap但矿车不足→仍优先补矿车(绕过上限)",
      f3.production_queue == [("harvester", BUILD_TIME_HARVESTER)], f3.production_queue)

# ---- ⑤ 矿车满且达 cap → 战斗单位与矿车都不排 ----
cap4 = AI_UNIT_CAP_BASE + AI_UNIT_CAP_PER_HARVESTER * AI_HARVESTER_TARGET
g.all_units = ([_Soldier() for _ in range(cap4)]
               + [_FakeHarv() for _ in range(AI_HARVESTER_TARGET)])
f4 = make_factory()
g.team_resources[TEAM] = 10000
trigger_production()
check("5 矿车满且达cap→两者都不排且不扣款",
      f4.production_queue == [] and g.team_resources[TEAM] == 10000,
      (f4.production_queue, g.team_resources[TEAM]))

# ---- ⑥ AI_HARVESTER_TARGET 常量存在且 units.json ai 分区三键一致 ----
_cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "units.json")
data = json.load(open(_cfg_path, encoding="utf-8"))
ai_sec = data.get("ai", {})
check("6 AI_HARVESTER_TARGET=4 且 units.json ai 分区三键一致",
      settings.AI_HARVESTER_TARGET == 4
      and ai_sec.get("AI_HARVESTER_TARGET") == 4
      and ai_sec.get("AI_UNIT_CAP_BASE") == settings.AI_UNIT_CAP_BASE
      and ai_sec.get("AI_UNIT_CAP_PER_HARVESTER") == settings.AI_UNIT_CAP_PER_HARVESTER
      and len(ai_sec) == 3, (ai_sec, settings.AI_HARVESTER_TARGET))

# ---- ⑦ spawn_unit 认识 "harvester"（工厂排产完成路径可生成矿车）----
from game.spawner_mixin import SpawnerMixin
class _SpawnGame(SpawnerMixin):
    def __init__(self):
        self.all_units = []
        self.all_buildings = []
sg = _SpawnGame()
fac7 = FactoryBuilding(sg, vec(3000, 3000), TEAM)
sg.all_buildings = [fac7]
sg.spawn_unit("harvester", vec(3000, 3000), TEAM)
new_harvs = [u for u in sg.all_units if isinstance(u, Harvester)]
check("7 spawn_unit('harvester')生成矿车且home=源头建筑",
      len(new_harvs) == 1 and new_harvs[0].home_building is fac7,
      [type(u).__name__ for u in sg.all_units])


class _DrawStub:
    def draw(self, s):
        pass


class _MenuStub(MenuMixin):
    """最小菜单替身：只提供 draw_menu/draw_login 触及的属性"""
    def __init__(self, bgs):
        self.screen = pygame.display.get_surface()
        self.bg_images = bgs
        self.sidebar_surf = pygame.Surface((400, 900))
        f = pygame.font.Font(None, 20)
        self.font_header = self.font_sub = self.font_btn = f
        self.ui_font = self.font = f
        self.btn_easy = pygame.Rect(50, 200, 200, 40)
        self.btn_fog = pygame.Rect(50, 250, 200, 40)
        self.btn_normal = pygame.Rect(50, 300, 200, 40)
        self.btn_hard = pygame.Rect(50, 350, 200, 40)
        self.btn_bombard = pygame.Rect(50, 400, 200, 40)
        self.btn_tutorial = pygame.Rect(50, 450, 200, 40)
        self.btn_quit = pygame.Rect(50, 500, 200, 40)
        self.bombardment_mode = False
        self.faction_icons = {}
        self.login_buttons = []
        self.input_ip = _DrawStub()
        self.update_log = _DrawStub()
        self.setting_ui = _DrawStub()
        self.disconnect_message = ""


# ---- ⑧⑨ 菜单整帧调用不抛错且 bg_images 不被 set_alpha 污染 ----
bgs = [pygame.Surface((1600, 900)), pygame.Surface((1600, 900))]
bgs[0].fill((30, 40, 50))
bgs[1].fill((60, 30, 20))
menu = _MenuStub(bgs)
_orig_ticks = pygame.time.get_ticks
pygame.time.get_ticks = lambda: 17500  # 强制落入 7~10s 过渡窗口（走黑幕分支）
errs = []
try:
    menu.draw_menu()
except Exception as e:
    errs.append(("draw_menu", repr(e)))
try:
    menu.draw_login()
except Exception as e:
    errs.append(("draw_login", repr(e)))
pygame.time.get_ticks = _orig_ticks
check("8 过渡窗口内 draw_menu/draw_login 整帧调用不抛错", not errs, errs)
check("9 bg_images 未被 set_alpha 污染且黑幕已缓存",
      all(s.get_alpha() in (None, 255) for s in bgs)
      and getattr(menu, '_fade_veil', None) is not None,
      [(s.get_alpha()) for s in bgs])

# ---- ⑩ basesetting._overlay 缓存存在且两次 draw 为同一对象 ----
class _SettingGameStub:
    """BaseSettingUI.draw 触及的最小 game 替身"""
    master_volume = 0.5
    fullscreen = False
    window_size = (1280, 720)
bs = BaseSettingUI(_SettingGameStub())
bs.active = True
screen = pygame.display.get_surface()
try:
    bs.draw(screen)
    ov1 = bs._overlay
    bs.draw(screen)
    same = ov1 is bs._overlay
    is_srcalpha = bool(ov1.get_flags() & pygame.SRCALPHA)
    alpha_ok = ov1.get_at((0, 0)).a == 150
except Exception as e:
    same = is_srcalpha = alpha_ok = False
    print("draw err:", repr(e))
check("10 basesetting._overlay 缓存(SRCALPHA/150)且两次draw同一对象",
      same and is_srcalpha and alpha_ok,
      (same, is_srcalpha, alpha_ok))

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
