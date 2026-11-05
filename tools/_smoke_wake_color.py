# -*- coding: utf-8 -*-
"""浪花随水域变色 + 编辑器选中水域改色 冒烟。"""
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

from maps.map_data import water_color_at, TERRAIN_POLY_COLORS, point_in_poly
from map_layout_editor import MapLayoutEditor

# ---- 固定测试水域（够大：战列舰尾流偏移 -550 也留在水内）----
POLY = [(200, 900), (2000, 900), (2000, 1400), (200, 1400)]
CUSTOM = (10, 200, 90)
entry = {"type": "water", "poly": POLY, "rect": pygame.Rect(200, 900, 1801, 501),
         "color": list(CUSTOM), "alpha": 120, "from_terrain": True}

# 1-5. water_color_at 取色规则
check("1 水内取自定义色RGB", water_color_at([entry], 1200, 1150) == CUSTOM)
check("2 水外返回None", water_color_at([entry], 3000, 3000) is None)
official_rect = pygame.Rect(200, 900, 1801, 501)   # 官方矩形湖：无 poly 不参与
check("3 官方Rect湖不取色", water_color_at([official_rect], 1200, 1150) is None)
no_color = {"type": "water", "poly": POLY, "rect": entry["rect"], "from_terrain": True}
expect = tuple(TERRAIN_POLY_COLORS["water"][:3])
check("4 无color字段回退默认水色", water_color_at([no_color], 1200, 1150) == expect)
slope_entry = {"type": "slope", "poly": POLY, "rect": entry["rect"], "from_terrain": True}
check("5 非water类型忽略", water_color_at([slope_entry], 1200, 1150) is None)

# 6-10. 真实战列舰 create_water_trail 颜色跟随
ed = MapLayoutEditor(0)
m = ed.map_obj
ed.game.lakes = [entry]                      # 注入测试水域（game.lakes 语义）
ed.game.current_map = m
ed.game.particles = pygame.sprite.Group()    # 换真 Group 以便检查粒子颜色

from units.ships import Battleship
ship = Battleship(ed.game, vec(1200, 1150), "team_0")
check("6 战列舰实例化且is_naval", ship.is_naval and ship.trail_size == 4)

ship.create_water_trail(ship.offset_distance, ship.trail_size, ship.spread)
ps = ed.game.particles.sprites()
check("7 水内浪花=水域自定义色", len(ps) > 0 and all(p.color == CUSTOM for p in ps),
      [(p.pos.x, p.pos.y, p.color) for p in ps[:3]])

ed.game.particles.empty()
ship.pos = vec(3000, 3000)                   # 移出水外
ship.create_water_trail(ship.offset_distance, ship.trail_size, ship.spread)
ps2 = ed.game.particles.sprites()
check("8 水外浪花=默认色", len(ps2) > 0 and all(p.color == (0, 60, 150) for p in ps2))

ed.game.particles.empty()
m.name = "龙之谷"                            # 无 poly 水域的地图特判回退
ship.create_water_trail(ship.offset_distance, ship.trail_size, ship.spread)
ps3 = ed.game.particles.sprites()
check("9 龙之谷特判回退", len(ps3) > 0 and all(p.color == (0, 100, 255) for p in ps3))
del m.name

check("10 粒子alpha=1(纯RGB不透明)", all(len(p.color) == 3 for p in ps))

# 11. 战列舰舰艏三角航迹表达式（ships.py 同款）：内=自定义 外=兜底白
wc_in = water_color_at(ed.game.lakes, 1200, 1150) or (200, 200, 255)
wc_out = water_color_at(ed.game.lakes, 3000, 3000) or (200, 200, 255)
check("11 舰艏航迹取色表达式", wc_in == CUSTOM and wc_out == (200, 200, 255))

# 12-15. 编辑器：选中水域→面板改颜色/透明度
m.terrain_polys = [dict(entry)]
ed.selected_type = None
ed.terrain_mode = None
ed.select_terrain_at(vec(1200, 1150))        # 空手左键点水域中心（run() 同款真实路径）
sp = ed._selected_poly()
check("12 空手点击选中水域+吸取色", sp is not None and ed.terrain_color == list(CUSTOM)
      and ed.terrain_alpha == 120)

ed.panel_collapsed = False
ed.draw_panel()                              # 生成面板点击热区
hits = getattr(ed, "_panel_hits", [])
tc = [r for tag, r in hits if tag.startswith("tcolor:")]
ta = [r for tag, r in hits if tag.startswith("talpha")]
check("13 面板热区生成(色块+透明度)", len(tc) >= 8 and len(ta) == 2, (len(tc), len(ta)))

picked = [(tag.split(":")[1]) for tag, r in hits if tag.startswith("tcolor:")][0]
ed.handle_panel_click(tc[0].center, 1)       # 点第一个色块 → 选中 poly 换色
check("14 色块点击改选中poly颜色", sp["color"] == [int(c) for c in picked.split(",")],
      (sp.get("color"), picked))

before = sp["alpha"]
ed.handle_panel_click([r for tag, r in hits if tag == "talpha:-"][0].center, 1)
check("15 透明度-生效(10下限保护)", sp["alpha"] == max(10, before - 15), (before, sp["alpha"]))

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
