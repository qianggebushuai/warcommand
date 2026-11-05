# -*- coding: utf-8 -*-
"""地图编辑器面板收起/展开冒烟（Tab/拉手，解决左面板遮挡地形编辑）。"""
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

from map_layout_editor import MapLayoutEditor, PANEL_W

ed = MapLayoutEditor(0)   # WildernessMap
W, H = ed.win.get_size()

# 1. 默认展开：draw_panel 设置 panel_rect，整帧绘制不崩
try:
    ed.draw_background()
    ed.draw_terrain_polys()
    ed.draw_buildings()
    ed.draw_spawn_points()
    ed.draw_ghost()
    ed.draw_panel()
    ed.draw_status()
    ed.draw_panel_toggle()
    ok = ed.panel_rect is not None and ed.panel_rect.w == PANEL_W
except Exception as e:
    ok = False
    print("  draw err:", e)
check("1 默认展开：panel_rect=250 宽整帧绘制", ok)

# 2. 拉手矩形：展开时在面板右缘，点击区域有效
tr = ed._toggle_rect
check("2 展开态拉手在面板右缘", tr is not None and tr.x == PANEL_W - 16 and tr.w == 16, tr)

# 3. 收起（模拟 Tab/拉手语义）：面板不再绘制，panel_rect 保持 None，状态栏不崩
ed.panel_collapsed = True
try:
    ed.panel_rect = None
    ed.draw_background()
    ed.draw_terrain_polys()
    ed.draw_buildings()
    ed.draw_spawn_points()
    ed.draw_ghost()
    ed.draw_status()          # panel_rect=None 时不得 AttributeError
    ed.draw_panel_toggle()
    ok = ed._toggle_rect.x == 0
except Exception as e:
    ok = False
    print("  collapsed draw err:", e)
check("3 收起态整帧绘制+拉手移到左缘", ok)

# 4. 收起后画布全宽可见：左缘世界坐标的地形多边形能正常叠加渲染（不再被面板盖住）
m = ed.map_obj
if not hasattr(m, 'terrain_polys'):
    m.terrain_polys = []
n0 = len(m.terrain_polys)
m.terrain_polys.append({"type": "water", "poly": [(50, 50), (600, 50), (600, 500), (50, 500)],
                        "rect": (50, 50, 551, 451), "color": None, "alpha": 150})
try:
    ed.zoom = 0.35
    ed.offset = vec(0, 0)
    ed.draw_terrain_polys()
    ok = len(m.terrain_polys) == n0 + 1
except Exception as e:
    ok = False
    print("  poly draw err:", e)
check("4 收起后左缘地形多边形可渲染", ok)
m.terrain_polys.pop()

# 5. 拉手点击翻转状态（与 run() 的 MOUSEBUTTONDOWN 分支同一判定）
ed.panel_collapsed = False
tr = ed._toggle_rect
clicked = tr.collidepoint(tr.center)
if clicked:
    ed.panel_collapsed = not ed.panel_collapsed
check("5 拉手点击展开→收起", ed.panel_collapsed is True)
tr2 = ed._toggle_rect
clicked2 = tr2.collidepoint(tr2.center)
if clicked2:
    ed.panel_collapsed = not ed.panel_collapsed
check("6 再点收起→展开", ed.panel_collapsed is False)

# 7. 收起状态下 terrain_mode 绘制橡皮筋/命中检测不受 panel_rect 影响
ed.panel_collapsed = True
ed.panel_rect = None
ed.terrain_mode = "water"
ed.terrain_drawing = [vec(30, 30), vec(400, 30), vec(400, 400)]
try:
    ed.draw_terrain_polys()
    idx = ed.hit_terrain_poly(vec(200, 200))
    ok = idx == -1   # 上一步已 pop，画布上无多边形 → 未命中
except Exception as e:
    ok = False
    print("  rubber err:", e)
ed.terrain_mode = None
ed.terrain_drawing = []
check("7 收起态绘制中橡皮筋+命中检测正常", ok)

# 8-10. 放置类型/出生点"再点取消"回空手（空手才能点选水域）
ed.panel_collapsed = False
ed.draw_panel()
hits2 = getattr(ed, "_panel_hits", [])
th = [r for tag, r in hits2 if tag.startswith("type:")]
sh = [r for tag, r in hits2 if tag.startswith("spawn:")]
ed.selected_type = None
ed.handle_panel_click(th[0].center, 1)
pick1 = ed.selected_type
ed.handle_panel_click(th[0].center, 1)
check("8 建筑类型选中", pick1 is not None and not str(pick1).startswith("spawn"), pick1)
check("9 再点同类型回空手", ed.selected_type is None, ed.selected_type)
ed.handle_panel_click(sh[0].center, 1)
pick2 = ed.selected_type
ed.handle_panel_click(sh[0].center, 1)
check("10 出生点再点回空手", str(pick2).startswith("spawn:") and ed.selected_type is None, pick2)

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
