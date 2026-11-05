# -*- coding: utf-8 -*-
"""水域波纹开关冒烟：WaterFX 过滤/JSON 解析与回环/运行时湖传播/编辑器切换。"""
import os
import sys
import json
import tempfile

os.environ['SDL_VIDEODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from pygame.math import Vector2 as vec
from pygame import Rect

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


from maps.environment import WaterFX
from maps import map_data as md

TRI = [[0, 0], [400, 0], [200, 400]]

# ---- 1 WaterFX._waters 过滤：waves=False 排除，缺省/True 保留 ----
lakes = [
    {"from_terrain": True, "poly": TRI, "rect": Rect(0, 0, 400, 400), "waves": False},
    {"from_terrain": True, "poly": TRI, "rect": Rect(0, 0, 400, 400)},
    {"from_terrain": True, "poly": TRI, "rect": Rect(0, 0, 400, 400), "waves": True},
]
ws = WaterFX._waters(lakes)
check("1 _waters排除waves=False且保留缺省/True",
      len(ws) == 2 and all(l.get('waves', True) for l in ws))

# ---- 2 关波纹水域不生成波纹；开波纹正常生成 ----
fx = WaterFX()
fx_off = WaterFX()
for i in range(40):
    fx_off.update_and_draw(pygame.Surface((800, 600)), vec(0, 0), 1.0, lakes[:1])
on_lakes = [{"from_terrain": True, "poly": TRI, "rect": Rect(0, 0, 400, 400)}]
for i in range(40):
    fx.update_and_draw(pygame.Surface((800, 600)), vec(0, 0), 1.0, on_lakes)
check("2 关波纹0生成/开波纹有生成",
      len(fx_off.ripples) == 0 and len(fx.ripples) > 0,
      (len(fx_off.ripples), len(fx.ripples)))

# ---- 3 JSON 解析：waves:false → False；缺省 → True ----
tmp = os.path.join(tempfile.gettempdir(), "_smoke_waves_layout.json")
data = {"map": "WildernessMap", "bases": [],
        "terrain": [
            {"type": "water", "points": TRI, "waves": False},
            {"type": "water", "points": TRI},
        ]}
json.dump(data, open(tmp, "w", encoding="utf-8"))
orig = md._map_layout_path
md._map_layout_path = lambda cls: tmp
m2 = md.WildernessMap(None)
m2.game = None
applied = m2.apply_layout_override()
md._map_layout_path = orig
tp = m2.terrain_polys
check("3 JSON解析波纹标志(显式False/缺省True)",
      applied and len(tp) == 2 and tp[0].get('waves') is False and tp[1].get('waves') is True,
      [(t.get('waves'),) for t in tp])

# ---- 4 apply_terrain_polys 传播到运行时湖 ----
class _StubGame:
    lakes = []
g = _StubGame()
m2.apply_terrain_polys(g)
lk = [l for l in g.lakes if isinstance(l, dict) and l.get('from_terrain')]
check("4 运行时湖携带waves标志",
      len(lk) == 2 and lk[0]['waves'] is False and lk[1]['waves'] is True,
      [(l.get('waves'),) for l in lk])

# ---- 5 导出回环保留 waves ----
exp = m2.export_layout()["terrain"]
check("5 export_layout回环保留waves",
      exp[0]["waves"] is False and exp[1]["waves"] is True,
      [(t["waves"],) for t in exp])
os.remove(tmp)

# ---- 6 编辑器：选中水域出现波纹开关且点击切换 ----
from map_layout_editor import MapLayoutEditor
ed = MapLayoutEditor(0)
m = ed.map_obj
m.terrain_polys = [{"type": "water", "poly": TRI, "rect": Rect(0, 0, 400, 400)}]
ed.selected_terrain = 0
ed.selected_type = None
kinds = [k for k, _ in ed.panel_items()]
check("6a 选中水域时面板出现twaves条目", "twaves" in kinds, kinds)
ed._panel_hits = [("twaves:toggle", Rect(0, 0, 50, 20))]
ed.handle_panel_click((10, 10), 1)
check("6b 点击切换为否", m.terrain_polys[0]['waves'] is False and ed.dirty)
ed.handle_panel_click((10, 10), 1)
check("6c 再点切回是", m.terrain_polys[0]['waves'] is True)

# ---- 7 选中非水域不出现开关 ----
m.terrain_polys = [{"type": "land", "poly": TRI, "rect": Rect(0, 0, 400, 400)}]
ed.selected_terrain = 0
kinds = [k for k, _ in ed.panel_items()]
check("7 选中陆地不出现波纹开关", "twaves" not in kinds)

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
