# -*- coding: utf-8 -*-
"""欧式建筑冒烟：注册表/实例化/外观尺寸/变体确定性/draw 不崩/布局工厂/JSON 回环。"""
import os
import sys
import json
import shutil
import tempfile

os.environ['SDL_VIDEODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from pygame.math import Vector2 as vec

pygame.init()
pygame.display.set_mode((1600, 900))    # 先开窗口再 import（SCREEN_WIDTH 陷阱）

PASS = TOTAL = 0


def check(name, cond, detail=""):
    global PASS, TOTAL
    TOTAL += 1
    if cond:
        PASS += 1
        print("PASS  " + name)
    else:
        print("FAIL  " + name + "  " + str(detail))


class _StubGame:
    def __init__(self):
        self.all_buildings = []
        self.all_units = []
        self.particles = pygame.sprite.Group()
        self.projectiles = []
        self.is_online = False
        self.my_role = "HOST"
        self.net_events = []
        self.show_alert = lambda *a, **k: None
        self.ui_font = pygame.font.Font(None, 20)
        self.current_map = None


g = _StubGame()

from core.base_classes import (EuropeanChurch, HalfTimberHouse, ClockTower,
                               Windmill, CivilianHouse)
import maps.map_data as md

EURO = {
    "EuropeanChurch": (EuropeanChurch, (76, 96)),
    "HalfTimberHouse": (HalfTimberHouse, (64, 64)),
    "ClockTower": (ClockTower, (56, 88)),
    "Windmill": (Windmill, (70, 84)),
}

# ---- 1 注册表条目：存在 + team=False + cls 指向正确类 ----
reg_ok = all(name in md.LAYOUT_BUILDING_TYPES
             and md.LAYOUT_BUILDING_TYPES[name]["cls"] is cls
             and md.LAYOUT_BUILDING_TYPES[name]["team"] is False
             for name, (cls, _) in EURO.items())
check("1 LAYOUT_BUILDING_TYPES 注册 4 项(team=False)", reg_ok)

# ---- 2 实例化：尺寸正确（PNG 注入走 logical_size）+ 非空像素 ----
from core.utils import logical_size
ok2, sizes = True, {}
for name, (cls, size) in EURO.items():
    b = cls(g, vec(3000, 3000), 0)
    img = b.image
    sizes[name] = logical_size(img)
    # 采样非透明像素数（生成图应有大量实体像素）
    w, h = img.get_size()
    opaque = sum(1 for x in range(0, w, 3) for y in range(0, h, 3)
                 if img.get_at((x, y))[3] > 0)
    if sizes[name] != size or opaque < 150:
        ok2 = False
        print("  %s size=%s opaque~%d" % (name, sizes[name], opaque))
check("2 四类实例化 尺寸/非空像素", ok2, sizes)

# ---- 3 变体确定性：同 variant 两实例字节一致；不同 variant 不同 ----
a1 = EuropeanChurch(g, vec(3000, 3000), 2).image
a2 = EuropeanChurch(g, vec(3000, 3000), 2).image
a3 = EuropeanChurch(g, vec(3000, 3000), 1).image
b1 = pygame.image.tostring(a1, "RGBA")
b2 = pygame.image.tostring(a2, "RGBA")
b3 = pygame.image.tostring(a3, "RGBA")
check("3 变体确定性(同variant一致/异variant不同)",
      b1 == b2 and b1 != b3)
# 3b PNG 引用：image 已由 sprite_cache 注入（downscale 后逻辑尺寸登记生效）
check("3b PNG 缓存注入(逻辑尺寸=SIZE)", all(logical_size(cls(g, vec(3000, 3000), 0).image) == sz
                                            for cls, sz in EURO.values()))

# ---- 4 与普通民居外观不同（同 variant 对比） ----
ch = CivilianHouse(g, vec(3000, 3000), 2).image
check("4 教堂外观 ≠ 普通民居",
      pygame.image.tostring(a1, "RGBA") != pygame.image.tostring(ch, "RGBA"))

# ---- 5 draw 不崩（zoom 1.0 / 0.7，含血条与阴影路径） ----
surf = pygame.Surface((1600, 900))
try:
    insts = [cls(g, vec(3000, 3000), 0) for cls, _ in EURO.values()]
    for b in insts:
        b.draw(surf, vec(2600, 2600), 1.0)
        b.draw(surf, vec(2600, 2600), 0.7)
    ok5 = True
except Exception as e:
    ok5 = False
    print("draw err:", repr(e))
check("5 四类 draw(zoom 1.0/0.7) 不崩", ok5)

# ---- 6 make_layout_building 返回正确类 ----
m = md.WildernessMap(g)
w = m.make_layout_building("Windmill", vec(1234, 567))
check("6 make_layout_building(Windmill) 类型/坐标",
      isinstance(w, Windmill) and abs(w.pos.x - 1234) < 2 and abs(w.pos.y - 567) < 2)

# ---- 7 JSON 回环：写临时布局 → apply_layout_override 还原类与坐标 ----
tmp = tempfile.mkdtemp(prefix="wc_euro_smoke_")
path = os.path.join(tmp, "WildernessMap.json")
orig_path_fn = md._map_layout_path
md._map_layout_path = lambda name: path
try:
    data = {"map": "WildernessMap", "bases": [], "ore": [], "terrain": [], "roads": [],
            "neutral": [
                {"cls": "EuropeanChurch", "x": 100, "y": 200},
                {"cls": "HalfTimberHouse", "x": 300, "y": 400},
                {"cls": "ClockTower", "x": 500, "y": 600},
                {"cls": "Windmill", "x": 700, "y": 800},
            ]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    m2 = md.WildernessMap(g)
    m2.apply_layout_override()
    got = [(type(b).__name__, int(b.pos.x), int(b.pos.y)) for b in m2.neutral_buildings]
    want = [("EuropeanChurch", 100, 200), ("HalfTimberHouse", 300, 400),
            ("ClockTower", 500, 600), ("Windmill", 700, 800)]
    check("7 JSON 回环 4 类还原", got == want, got)
    # ---- 8 export_layout 能把实例序列化回 neutral 条目 ----
    exp = m2.export_layout()["neutral"]
    names = {e["cls"] for e in exp}
    check("8 export_layout 序列化 cls 名", names == set(EURO), names)
finally:
    md._map_layout_path = orig_path_fn
    shutil.rmtree(tmp, ignore_errors=True)

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
