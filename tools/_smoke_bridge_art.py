# -*- coding: utf-8 -*-
"""桥立绘重绘冒烟：桥面用道路同款沥青+黄虚线衔接，护栏/桥台/桥墩/断桥残段绘制不崩。"""
import os
import sys

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


class _StubGame:
    def __init__(self):
        self.all_buildings = []
        self.particles = pygame.sprite.Group()
        self.is_online = False
        self.my_role = "HOST"
        self.net_events = []
        self.show_alert = lambda *a, **k: None
        self.ui_font = pygame.font.Font(None, 20)


g = _StubGame()
import units  # 触发 enable_sprite_cache_for：Bridge 的 PNG 包装必须真实生效
from core.base_classes import Bridge
from core.utils import logical_size

# ---- 1 横桥基准图：画布 632x332（桥体 600x300 + IMG_PAD 外扩）+ 中线黄虚线过桥心 + 桥面沥青 + 基座混凝土 ----
b = Bridge(g, vec(3000, 3000), "horizontal")
img = b.generate_image()
c = img.get_at((316, 166))          # 桥心 = 黄虚线段（世界x=300，300%48=12<24）
deck_px = img.get_at((316, 116))    # 桥面沥青（避开护栏/立柱）
base_px = img.get_at((316, 36))     # 顶部混凝土基座
tip = img.get_at((145, 16))         # 外凸桥墩帽（pad=16，墩帽画布 y=13..23，世界 y=-3..7）
check("1 横桥画布632x332 中线黄/桥面沥青/基座混凝土/外凸桥墩",
      img.get_size() == (632, 332)
      and c.r > 150 and c.g > 120 and c.b < 90
      and deck_px.r == deck_px.g and 30 <= deck_px.r <= 110
      and abs(base_px.r - 112) <= 6 and abs(base_px.g - 110) <= 6
      and abs(tip.r - 92) <= 12 and abs(tip.g - 90) <= 12,
      (tuple(c), tuple(deck_px), tuple(base_px), tuple(tip)))

# ---- 2 竖桥基准图：画布 232x332 + 竖向中线黄虚线 ----
b2 = Bridge(g, vec(3000, 3000), "vertical")
img2 = b2.generate_image()
c2 = img2.get_at((116, 166))        # 竖中线（世界y=150，150%48=6<24 → 黄段）
base2 = img2.get_at((36, 166))      # 侧边混凝土
check("2 竖桥画布232x332 中线黄/侧边混凝土",
      img2.get_size() == (232, 332)
      and c2.r > 150 and c2.g > 120 and c2.b < 90
      and abs(base2.r - 112) <= 6, (tuple(c2), tuple(base2)))

# ---- 3 完好桥 draw 不崩（视口内） ----
surf = pygame.Surface((1600, 900))
try:
    b.draw(surf, vec(2500, 2600), 1.0)
    b2.draw(surf, vec(2500, 2600), 0.7)
    ok = True
except Exception as e:
    ok = False
    print("draw err:", repr(e))
check("3 完好桥横/竖+缩放draw不崩", ok)

# ---- 4 断桥：中段露水 + 残段绘制不崩（缺口露真实水面——无阴影填充） ----
b.take_damage(99999)
check("4a 受击断裂进入is_broken", b.is_broken and b.hp == 0)
surf.fill((30, 60, 120))            # 模拟桥下真实水面（旧版深蓝填充矩形已删）
try:
    b.draw(surf, vec(2500, 2600), 1.0)
    ok = True
except Exception as e:
    ok = False
    print("broken draw err:", repr(e))
water = surf.get_at((500, 400))     # 桥心（缺口处）= 真实水面透出
check("4b 断桥draw不崩且中段露真实水面",
      ok and water.b > water.r and water.b > 80, tuple(water))

# ---- 5 修复回完好再画不崩 ----
b.restore_bridge()
try:
    b.draw(surf, vec(2500, 2600), 1.0)
    ok = True
except Exception as e:
    ok = False
    print("restored draw err:", repr(e))
check("5 修复后回完好绘制不崩", ok and not b.is_broken)

# ---- 6 可变长度：默认尺寸不变 + 自定义长度调整宽/高与碰撞箱 ----
import maps.map_data as md
bh = Bridge(g, vec(3000, 3000), "horizontal")
check("6a 默认横桥 600x300（向后兼容）",
      (bh.width, bh.height) == (600, 300) and bh.rect == pygame.Rect(3000 - 300, 3000 - 150, 600, 300))
b800 = Bridge(g, vec(3000, 3000), "horizontal", 800)
check("6b 横桥 length=800 → 碰撞箱 800x300 居中",
      (b800.width, b800.height) == (800, 300)
      and b800.rect == pygame.Rect(3000 - 400, 3000 - 150, 800, 300))
b456 = Bridge(g, vec(3000, 3000), "vertical", 456)
check("6c 竖桥 length=456 → 碰撞箱 200x456 居中",
      (b456.width, b456.height) == (200, 456)
      and b456.rect == pygame.Rect(3000 - 100, 3000 - 228, 200, 456)
      and b456.sprite_key == "vertical_456")
check("6d 碰撞箱命中判定随长度伸缩",
      b800.rect.collidepoint(3350, 3000) and not b800.rect.collidepoint(3450, 3000)
      and b456.rect.collidepoint(3000, 3180) and not b456.rect.collidepoint(3000, 3240))

# ---- 7 可变长度基准图尺寸随长度 + draw 不崩（完好/断桥） ----
img800 = b800.generate_image()
img456 = b456.generate_image()
check("7a 可变长度基准图尺寸", img800.get_size() == (832, 332) and img456.get_size() == (232, 488))
try:
    b800.draw(surf, vec(2500, 2600), 1.0)
    b456.draw(surf, vec(2500, 2600), 0.5)
    b456.take_damage(99999)
    b456.draw(surf, vec(2500, 2600), 0.5)   # 断桥残段随长度伸缩
    ok = True
except Exception as e:
    ok = False
    print("varlen draw err:", repr(e))
check("7b 可变长度桥 draw(完好/断桥)不崩", ok)

# ---- 8 JSON 布局回环：extra=[orientation, length] 还原尺寸/中心 ----
bj = md.GameMapBase.make_layout_building(g, vec(1234, 567), ["vertical", 456]) \
    if hasattr(md, 'GameMapBase') else None
if bj is None:
    # 注册表链路兜底：直接模拟 make_layout_building 的构造方式
    meta = md.LAYOUT_BUILDING_TYPES["Bridge"]
    bj = meta["cls"](g, vec(1234, 567), "vertical", 456)
check("8 布局 JSON extra 还原竖桥 200x456",
      isinstance(bj, Bridge) and (bj.width, bj.height) == (200, 456)
      and bj.rect.center == (1234, 567))
# 旧版 JSON（extra 只有 orientation）向后兼容
meta = md.LAYOUT_BUILDING_TYPES["Bridge"]
bold = meta["cls"](g, vec(10, 20), "horizontal")
check("8b 旧 JSON 仅 orientation 兼容", (bold.width, bold.height) == (600, 300))

# ---- 9 PNG 变体注入（真实包装链路）：清缓存强制走加载 → 逻辑尺寸=画布、
#      同 key 同图、降采样后桥墩/中线/基座仍在、无中立染色抹平 ----
import units.sprite_cache as sc
sc._surface_cache.pop('Bridge', None)      # 前面未命中时缓存了 None，弹掉让下一构造真实加载 PNG
p1 = Bridge(g, vec(3000, 3000), "horizontal", 800).image
p2 = Bridge(g, vec(3000, 3000), "horizontal", 800).image
ratio = p1.get_width() / 832.0             # 注入图按 0.75 降采样存储，采样坐标按 raw/logical 比例换算
dash_p = p1.get_at((int(316 * ratio), int(166 * ratio)))   # 中线黄段
tip_p = p1.get_at((int(145 * ratio), int(16 * ratio)))     # 外凸桥墩帽
base_p = p1.get_at((int(145 * ratio), int(60 * ratio)))    # 基座混凝土
check("9 PNG 按 sprite_key 变体注入（逻辑尺寸/桥墩/中线/基座保真）",
      logical_size(p1) == (832, 332) and logical_size(p2) == (832, 332)
      and pygame.image.tostring(p1, "RGBA") == pygame.image.tostring(p2, "RGBA")
      and dash_p.r > 150 and dash_p.g > 120 and dash_p.b < 90
      and abs(tip_p.r - 92) <= 14 and abs(base_p.r - 112) <= 8
      and abs(tip_p.r - base_p.r) > 8,
      (logical_size(p1), tuple(dash_p), tuple(tip_p), tuple(base_p)))
pv = Bridge(g, vec(3000, 3000), "vertical", 456).image
check("9b 竖桥注入画布 232x488", logical_size(pv) == (232, 488), logical_size(pv))

# ---- 10 海军桥下通行：桥不算海军的建筑碰撞（船不再被跨河桥卡死） ----
g.lakes = [{'rect': pygame.Rect(2600, 2850, 800, 300), 'poly': [(2600, 2850), (3400, 2850), (3400, 3150), (2600, 3150)],
            'type': 'water', 'from_terrain': True}]
g.all_units = []
from units.base import Unit
import units.base as ub

class _NProbe(Unit):
    def __init__(self, game, pos):
        super().__init__(game, pos, "team_0")

    def draw(self, surface, offset, zoom):
        from units.base import to_screen, scale
        spos = to_screen(self.pos, offset, zoom)
        pygame.draw.circle(surface, (255, 0, 255), (int(spos[0]), int(spos[1])), int(scale(30, zoom)))

g.current_map = type("M", (), {"islands": []})()
n = _NProbe(g, vec(3000, 3000))
n.is_naval = True
n.is_air = False
g.all_buildings = [b]
# (3000,3000) 在水面上且在桥 rect 内：海军 True（桥下通行），地面 True（on_bridge）
check("10a 海军可过桥下水域", n.check_move_validity(vec(3000, 3000)) is True)
ground = _NProbe(g, vec(3000, 3000))
check("10b 地面单位仍可走桥面", ground.check_move_validity(vec(3000, 3000)) is True)
# 水面但桥外（膨胀后桥 rect x≤3310，3350 已出桥）：海军 True / 地面 False
check("10c 海军桥外水面通行/地面入水被挡",
      n.check_move_validity(vec(3350, 2960)) is True
      and ground.check_move_validity(vec(3350, 2960)) is False)
# 海军仍被普通建筑阻挡（非桥）
fake = type("B", (), {"alive": True, "b_type": "", "rect": pygame.Rect(2950, 2950, 100, 100)})()
g.all_buildings = [b, fake]
check("10d 海军仍被普通建筑阻挡", n.check_move_validity(vec(3000, 3000)) is False)

# ---- 11 渲染层级：船 < 桥 < 陆军（render_mixin 的桥覆盖层逻辑） ----
surf3 = pygame.Surface((1600, 900))
surf3.fill((0, 255, 0))                     # 绿色底
center = (500, 400)                          # 桥中心屏幕坐标（offset 2500,2600 zoom 1）
b.draw(surf3, vec(2500, 2600), 1.0)          # 建筑层
deck_px = surf3.get_at(center)
n2 = _NProbe(g, vec(3000, 3000))
n2.is_naval = True
n2.draw(surf3, vec(2500, 2600), 1.0)         # 海军画在桥上（旧层级问题的复现）
ship_px = surf3.get_at(center)
b.draw(surf3, vec(2500, 2600), 1.0)          # 桥覆盖层 → 船被桥面盖住
covered_px = surf3.get_at(center)
land = _NProbe(g, vec(3000, 3000))
land.draw(surf3, vec(2500, 2600), 1.0)       # 陆军最后画 → 桥面之上
land_px = surf3.get_at(center)
def _close(c1, c2, tol=14):
    return all(abs(a - b) <= tol for a, b in zip(c1[:3], c2[:3]))

check("11 层级 船<桥<陆军",
      ship_px[:3] == (255, 0, 255)            # 船确实画在了桥面上
      and _close(covered_px, deck_px)          # 桥重画后盖住船（桥面纹理每次绘制微有随机，按容差比较）
      and covered_px[:3] != (255, 0, 255)
      and land_px[:3] == (255, 0, 255),        # 陆军仍露在桥面之上
      (tuple(deck_px), tuple(ship_px), tuple(covered_px), tuple(land_px)))

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
