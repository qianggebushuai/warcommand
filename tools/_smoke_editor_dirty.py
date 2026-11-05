# -*- coding: utf-8 -*-
"""编辑器 dirty 标记无头冒烟：验证状态机转换与保存链路真实生效"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
from pygame.math import Vector2 as vec

from map_layout_editor import MapLayoutEditor

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


ed = MapLayoutEditor(0)
m = ed.map_obj

# 1. 初始干净
check("初始 dirty=False", ed.dirty is False)

# 2. 放置建筑 → dirty
n0 = len(m.neutral_buildings)
ed.place_building("Skyscraper", vec(2100, 1300))
check("放置后 dirty=True", ed.dirty is True)
check("建筑数+1", len(m.neutral_buildings) == n0 + 1)

# 3. 保存（模拟 K_s 分支逻辑）→ dirty 复位 + JSON 落盘含新建筑
m.save_layout()
ed.dirty = False
import json
with open(os.path.join(ROOT, "config", "map_layouts", "WildernessMap.json"), encoding="utf-8") as f:
    data = json.load(f)
check("保存后 JSON 含新摩天楼", any(b["cls"] == "Skyscraper" and b["x"] == 2100 and b["y"] == 1300
                                    for b in data["neutral"]))

# 4. 重载应用 → 新建筑真实生效（游戏端同款链路）
m2 = type(m)(None)
m2.generate(seed=0)
m2.apply_layout_override()
found = [b for b in m2.neutral_buildings if b.__class__.__name__ == "Skyscraper"
         and abs(b.pos.x - 2100) < 1 and abs(b.pos.y - 1300) < 1]
check("游戏端 apply 后新建筑存在", len(found) == 1)

# 5. 删除 → dirty
ed.delete_at(vec(2100, 1300))
check("删除后 dirty=True", ed.dirty is True)
check("建筑数复原", len(m.neutral_buildings) == n0)

# 6. 移动出生点 → dirty
m.bases_config[0] = vec(999, 888)
ed.dirty = True
check("出生点移动置 dirty", ed.dirty is True)

# 7. 还原 json（移除冒烟塞入的建筑）——直接保存当前干净状态
m.save_layout()
with open(os.path.join(ROOT, "config", "map_layouts", "WildernessMap.json"), encoding="utf-8") as f:
    data = json.load(f)
check("JSON 还原（无冒烟建筑）", not any(b["x"] == 2100 and b["y"] == 1300 for b in data["neutral"]))
check("JSON 保留原建筑数", len(data["neutral"]) == n0)

pygame.quit()
print(f"\n{'ALL PASS' if not fails else f'FAILED: {fails}'}")
sys.exit(1 if fails else 0)
