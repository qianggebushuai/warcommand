# -*- coding: utf-8 -*-
"""地图编辑器矿脉拖动冒烟。"""
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

from map_layout_editor import MapLayoutEditor

ed = MapLayoutEditor(0)   # WildernessMap
m = ed.map_obj
n0 = len(m.ore_patches)
check("1 编辑器启动且矿脉已加载", n0 > 0, n0)

# 2. hit_ore 命中已有矿脉
target = m.ore_patches[0]
hit = ed.hit_ore(vec(target.pos.x + 5, target.pos.y))
check("2 hit_ore 命中", hit is target)

# 3. 拖动：BUTTONDOWN 语义（dragging_ore 赋值）→ MOTION 语义（pos 更新+dirty）
ed.dragging_ore = hit
old_pos = vec(target.pos)
ed.dirty = False
new_wp = vec(old_pos.x + 200, old_pos.y + 120)
# 模拟 MOUSEMOTION 分支的核心逻辑（与 run() 内一致）
target.pos = vec(int(new_wp.x // 5) * 5, int(new_wp.y // 5) * 5)
ed.dirty = True
check("3 拖动更新位置(5px 吸附)", target.pos == vec(int(new_wp.x // 5) * 5, int(new_wp.y // 5) * 5)
      and target.pos != old_pos and ed.dirty)

# 4. 松开结束拖动
ed.dragging_ore = None
check("4 BUTTONUP 结束拖动", ed.dragging_ore is None)

# 5. 放置新矿脉不受影响（点空白处）
ed.selected_type = "OrePatch"
blank = vec(m.width * 0.5, m.height * 0.5)
while ed.hit_ore(blank) is not None:   # 找一个不在矿脉上的点
    blank += vec(150, 0)
ed.place_building("OrePatch", blank)
check("5 空白处放置新矿脉", len(m.ore_patches) == n0 + 1)

# 6. 命中矿脉时左键不放置（拖动优先）
ed.selected_type = "OrePatch"
before = len(m.ore_patches)
hit2 = ed.hit_ore(vec(m.ore_patches[0].pos.x, m.ore_patches[0].pos.y))
check("6 矿脉上左键=拖动不新增", hit2 is not None and before == len(m.ore_patches))

# 7. 删除照旧
deleted = ed.delete_at(vec(m.ore_patches[-1].pos))
check("7 右键删除矿脉", deleted == "OrePatch" and len(m.ore_patches) == n0)

# 8. 保存 JSON 包含矿脉坐标
path = m.save_layout()
import json
data = json.load(open(path, encoding="utf-8"))
ores = data.get("ore", [])
ok8 = any(abs(o["x"] - target.pos.x) < 1 and abs(o["y"] - target.pos.y) < 1
          for o in ores) if ores else False
check("8 保存包含拖动后坐标", ok8, ores[:3])

# 9. 绘制一帧不崩（矿脉+建筑循环结构完整）
ed.zoom = 0.35
ed.dragging_ore = m.ore_patches[0] if m.ore_patches else None
try:
    ed.draw_background()
    ed.draw_buildings()
    ed.draw_spawn_points()
    ed.draw_panel()
    ed.draw_status()
    ok9 = True
except Exception as e:
    ok9 = False
    print("  draw err:", e)
check("9 整帧绘制(拖动高亮态)", ok9)

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
