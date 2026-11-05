# -*- coding: utf-8 -*-
"""回归：选中建筑类型后 panel_rect=None 时 draw_ghost 不崩溃（用户报告的崩溃场景）"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
from pygame.math import Vector2 as vec
import map_layout_editor as mle

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


ed = mle.MapLayoutEditor(0)

# 场景1：第一帧（panel_rect 尚为 None）就选了类型 → draw_ghost 不崩
ed.selected_type = "Skyscraper"
ed.panel_rect = None
try:
    ed.draw_ghost()
    check("panel_rect=None 时 draw_ghost 安全", True)
except AttributeError as ex:
    check(f"panel_rect=None 时 draw_ghost 安全 (仍崩: {ex})", False)

# 场景2：模拟多帧主循环（选中类型 + 鼠标位置任意），跑 5 帧不崩
ed.selected_type = "Skyscraper"
try:
    for _ in range(5):
        ed.panel_rect = None           # 每帧开头清空（与 run 主循环一致）
        ed.draw_background()
        ed.draw_buildings()
        ed.draw_spawn_points()
        ed.draw_ghost()
        ed.draw_panel()
        ed.draw_status()
    check("选中类型后 5 帧主循环无崩溃", True)
except Exception as ex:
    check(f"选中类型后 5 帧主循环无崩溃 ({type(ex).__name__}: {ex})", False)

# 场景3：handle_panel_click 对空面板点击安全
ed.panel_rect = None
try:
    r = ed.handle_panel_click((10, 10), 1)
    check("panel_rect=None 时 handle_panel_click 安全", r is False)
except AttributeError as ex:
    check(f"panel_rect=None 时 handle_panel_click 安全 (仍崩: {ex})", False)

# 场景4：鼠标在面板内时 ghost 不绘制（逻辑仍正确）
ed.panel_rect = pygame.Rect(0, 0, mle.PANEL_W, 900)
pygame.mouse.get_pos = lambda: (100, 300)      # 面板内
ed.selected_type = "OilDerrick"
try:
    ed.draw_ghost()
    check("面板内 hover 时 draw_ghost 正常跳过", True)
except Exception as ex:
    check(f"面板内 hover 时 draw_ghost 正常跳过 ({ex})", False)

pygame.quit()
print(f"\n{'ALL PASS' if not fails else f'FAILED: {fails}'}")
sys.exit(1 if fails else 0)
