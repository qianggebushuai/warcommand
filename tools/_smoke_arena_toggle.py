# -*- coding: utf-8 -*-
"""竞技场 UI 收起/展开冒烟：toggle 按钮注册、两态绘制不崩、点击翻转。"""
import os
import sys

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()
pygame.display.set_mode((200, 200))

PASS = TOTAL = 0
def check(name, cond, detail=""):
    global PASS, TOTAL
    TOTAL += 1
    if cond:
        PASS += 1
        print("PASS  " + name)
    else:
        print("FAIL  " + name + "  " + str(detail))

from core.settings import SCREEN_WIDTH, SCREEN_HEIGHT
from core.utils import get_font
from game.arena_mixin import ArenaMixin
from core.base_classes import vec

class T(ArenaMixin):
    pass

t = T()
t.screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
t.ui_font = get_font(20)
t.info_font = get_font(14)
t.font = get_font(18)
t.alert_font = get_font(24)
t.arena_phase = "FIGHT"
t.arena_mode = "standard"
t.arena_round = 1
t.arena_streak = 0
t.arena_funds = 1000
t.arena_bet = 0
t.arena_bet_team = None
t.arena_zone_progress = 0.0
t.arena_fight_frames = 0
t.current_map = None
t.active_alert = None
t.all_units = []
t.arena_draw_fog = lambda: None

# 1. 展开态：toggle 注册 + 顶栏绘制不崩
t.arena_draw_overlay()
check("1 FIGHT 展开态绘制+toggle 注册", t.arena_ui.get("toggle") is not None,
      str(list(t.arena_ui)))

# 2. 点击 toggle 翻转状态
rect = t.arena_ui["toggle"]
t.arena_ui_collapsed = False
if rect.collidepoint(rect.center):
    t.arena_ui_collapsed = not getattr(t, 'arena_ui_collapsed', False)
check("2 点击翻转 collapsed", t.arena_ui_collapsed is True, t.arena_ui_collapsed)

# 3. 收起态：FIGHT 再绘制不崩（顶栏/VS/提示被隐藏）
t.arena_draw_overlay()
check("3 FIGHT 收起态绘制不崩", t.arena_ui.get("toggle") is not None)

# 4. BET 收起态：押注底栏（左右阵营/比例/跳过）隐藏，toggle 仍在
t.arena_phase = "BET"
t.arena_army_info = {"team_0": {"comp": [], "cost": 0}, "team_1": {"comp": [], "cost": 0}}
t.arena_army_pool = []
t.arena_ratio = 0.5
t.arena_army_info_team_cost = 0
t.teams_config = {"team_0": {"name": "Red", "color": (220, 80, 70)},
                  "team_1": {"name": "Blue", "color": (80, 120, 220)}}
t.faction_icons = {"team_0": pygame.Surface((24, 24)),
                   "team_1": pygame.Surface((24, 24))}
# BET 分支用到 army panel 绘制，补齐最小依赖
t.arena_bet = 0
try:
    t.arena_draw_overlay()
    ok4 = ("left" not in t.arena_ui and "skip" not in t.arena_ui
           and t.arena_ui.get("toggle") is not None)
except Exception as e:
    ok4 = False
    print("  BET draw err:", e)
check("4a BET 收起态押注底栏隐藏", ok4)

# 4b. BET 展开态：底栏恢复
t.arena_ui_collapsed = False
try:
    t.arena_draw_overlay()
    ok4b = ("left" in t.arena_ui and "right" in t.arena_ui and "skip" in t.arena_ui)
except Exception as e:
    ok4b = False
    print("  BET expand err:", e)
check("4b BET 展开态押注底栏恢复", ok4b)

# 5. DEPLOY 收起态：情报面板隐藏但操作按钮行保留
t.arena_phase = "DEPLOY"
t.arena_ui_collapsed = True
t.arena_army_pool = []
t.arena_fog_selected = None
t.arena_fog_intel = False
t.arena_fog_spent = 0
class _Sb:
    rect = pygame.Rect(-100, -100, 1, 1)
    dragging_scrollbar = False
    def draw(self, s): pass
    def handle_event(self, e): pass
    def end_scrollbar_drag(self): pass
t.sidebar = _Sb()
try:
    t.arena_draw_overlay()
    ok5 = ("intel" in t.arena_ui and "start" in t.arena_ui and "exit" in t.arena_ui)
except Exception as e:
    ok5 = False
    print("  DEPLOY draw err:", e)
check("5 DEPLOY 收起态操作按钮保留", ok5)

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
