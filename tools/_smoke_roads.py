# -*- coding: utf-8 -*-
"""道路背景层冒烟：纹理/贴条缓存/点线距/屏幕绘制/编辑器两点放置与删除/JSON 回环。"""
import os
import sys
import json
import tempfile

os.environ['SDL_VIDEODRIVER'] = 'dummy'
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
        print("PASS  " + name)
    else:
        print("FAIL  " + name + "  " + str(detail))


from game.roads import (ROAD_TILE, get_road_tile, build_road_strip,
                        seg_dist, draw_roads_screen)

# ---- 1 沥青纹理生成 ----
t = get_road_tile()
cols = {tuple(t.get_at((x, y))) for x in range(0, ROAD_TILE, 5) for y in range(0, ROAD_TILE, 5)}
check("1 沥青纹理64x64且含噪点(颜色多样)",
      t.get_size() == (ROAD_TILE, ROAD_TILE) and len(cols) > 5, len(cols))

# ---- 2 水平贴条尺寸 + 缓存复用 ----
r = {"start": vec(100, 500), "end": vec(740, 500), "width": 64}
s1, p1 = build_road_strip(r)
s2, p2 = build_road_strip(r)
check("2 水平贴条尺寸正确且缓存复用",
      s1.get_width() >= 640 + ROAD_TILE and s1.get_height() == 64
      and s1 is s2 and p1 == p2, (s1.get_size(), p1))

# ---- 3 垂直贴条（旋转后宽高互换） ----
rv = {"start": vec(500, 100), "end": vec(500, 740), "width": 64}
sv, _ = build_road_strip(rv)
check("3 垂直贴条旋转后宽高互换", sv.get_width() == 64 and sv.get_height() >= 640,
      sv.get_size())

# ---- 4 点到线段距离 ----
d1 = seg_dist(vec(300, 520), r["start"], r["end"])    # 中线旁 20px
d2 = seg_dist(vec(900, 500), r["start"], r["end"])    # 端点外 → 到端点
check("4 点到线段距离正确", abs(d1 - 20) < 1e-6 and abs(d2 - 160) < 1e-6, (d1, d2))

# ---- 5 屏幕绘制不崩（视口内/视口外/双缩放） ----
surf = pygame.Surface((800, 600))
roads2 = [r, {"start": vec(5000, 5000), "end": vec(5600, 5000), "width": 48}]
draw_roads_screen(surf, roads2, vec(0, 0), 1.0)
draw_roads_screen(surf, roads2, vec(0, 0), 0.5)
check("5 draw_roads_screen 视口内外/双缩放不崩", True)

# ---- 6 编辑器：两点放置 → 删除 → 防误删 ----
from map_layout_editor import MapLayoutEditor
ed = MapLayoutEditor(0)
m = ed.map_obj
m.roads = []
ed.selected_type = "road"
ed.road_width = 96
ed.place_road(vec(1000, 1000))
check("6a 第一次点击=定起点不建路",
      len(m.roads) == 0 and ed.road_pending == vec(1000, 1000))
ed.place_road(vec(2000, 1000))
check("6b 第二次点击成路(宽96)",
      len(m.roads) == 1 and m.roads[0]["width"] == 96 and ed.road_pending is None)
ed.place_road(vec(3000, 3000))
ed.place_road(vec(3010, 3010))
check("6c 过短(<24px)丢弃", len(m.roads) == 1 and ed.road_pending is None)
ed.place_road(vec(3000, 3000))
ed.place_road(vec(3200, 3000))
n_before = len(m.roads)
ok = ed.delete_road_at(vec(3100, 3005))     # 第二条路中线上方 5px
check("6d 右键删除命中最近道路", ok and len(m.roads) == n_before - 1,
      (n_before, len(m.roads)))
check("6e 远离道路不误删", not ed.delete_road_at(vec(3100, 3300)))

# ---- 7 JSON 导出→解析回环（临时文件，不动真实布局） ----
import maps.map_data as md
tmp = os.path.join(tempfile.gettempdir(), "_smoke_roads_layout.json")
exp = m.export_layout()
# 只留道路+出生点分区（neutral/ore/terrain 会实例化游戏对象，与本测试无关）
slim = {"map": exp.get("map"), "bases": exp.get("bases", []), "roads": exp["roads"]}
json.dump(slim, open(tmp, "w", encoding="utf-8"))
orig = md._map_layout_path
md._map_layout_path = lambda cls: tmp
m2 = type(m)(None)
applied = m2.apply_layout_override()
md._map_layout_path = orig
rt = [{"start": [float(r["start"].x), float(r["start"].y)],
       "end": [float(r["end"].x), float(r["end"].y)], "width": r["width"]}
      for r in m.roads]
got = [{"start": [r["start"].x, r["start"].y],
        "end": [r["end"].x, r["end"].y], "width": r["width"]} for r in m2.roads]
check("7 JSON导出→apply解析回环一致", applied and got == rt, (got, rt))
os.remove(tmp)

# ---- 8 面板含道路条目 ----
items = ed.panel_items()
kinds = [k for k, _ in items]
check("8 面板含道路工具+路宽档位", "road" in kinds and "roadwidth" in kinds)

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
