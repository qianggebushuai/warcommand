# -*- coding: utf-8 -*-
"""图鉴补全 + 设置/图鉴横幅冒烟。"""
import os
import sys

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
# 注意：core.settings 的 SCREEN_WIDTH 等常量在导入时读取当前显示模式，
# 必须先用真实分辨率建窗再导入，否则 detail_w 会算出负数（布局断言全部失真）
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

from core.settings import SCREEN_WIDTH, SCREEN_HEIGHT
from core.utils import resource_path, get_font
from core.dic import DIC_DATA, DictionaryUI

# 1. 无空占位条目
empty = [i for i, d in enumerate(DIC_DATA) if not d.get("name") or not d.get("img")]
check("1 无空占位条目", not empty, empty)

# 2. 所有图片可加载（picture 或 sprites）
bad = []
for d in DIC_DATA:
    img = d["img"]
    p = resource_path(img) if img.startswith("sprites/") else resource_path("picture/" + img)
    if not os.path.exists(p):
        bad.append(img)
check("2 全部条目图片存在(%d 条)" % len(DIC_DATA), not bad, bad)

# 3. 数值完整（stats 非全零、desc 非空）
bad3 = [d["name"] for d in DIC_DATA if not d.get("desc") or d["stats"].count("0 |") >= 4]
check("3 全部条目有描述与数值", not bad3, bad3)

# 4. 类型筛选覆盖：每类至少 1 条
types = {}
for d in DIC_DATA:
    types[d["type"]] = types.get(d["type"], 0) + 1
need = ["地面步兵", "地面载具", "空中载具", "固定翼", "海上载具", "生产建筑", "防御建筑"]
check("4 七大分类齐备", all(t in types for t in need),
      {t: types.get(t, 0) for t in need})

# 5. get_image 真实加载（含 sprites 路径条目）
class G:
    state = "LOGIN"
    master_volume = 0.5
ui = DictionaryUI(G())
sprites_ok = all(ui.get_image(d["img"]) is not None for d in DIC_DATA)
check("5 get_image 全部加载成功", sprites_ok,
      [d["img"] for d in DIC_DATA if ui.get_image(d["img"]) is None][:5])

# 6. 图鉴整页绘制不崩（含横幅）
ui.active = True
screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
try:
    ui.draw(screen)
    ok6 = True
except Exception as e:
    ok6 = False
    print("  dic draw err:", e)
check("6 图鉴整页绘制", ok6)

# 7. 横幅图存在
check("7 两张横幅图存在",
      os.path.exists(resource_path("picture/banner_database.png"))
      and os.path.exists(resource_path("picture/banner_settings.png")))

# 8. 设置面板横幅 + 绘制不崩
from panels.basesetting import BaseSettingUI
bs = BaseSettingUI(G())
ok8 = bs.banner is not None
try:
    bs.active = True
    bs.draw(screen)
except Exception as e:
    ok8 = False
    print("  setting draw err:", e)
check("8 设置面板横幅+绘制", ok8)

# 9. history 全部补全（非空、非占位符）
bad9 = [d["name"] for d in DIC_DATA
        if not d.get("history") or d["history"] in ("......", "档案缺失。")]
check("9 全部条目有 history(%d 条)" % len(DIC_DATA), not bad9, bad9)

# 10. 布局无重叠：横幅(右区 y15-103) 不遮筛选按钮(y112)；详情各行不越界
banner_bottom = 15 + 88
check("10a 横幅不遮挡筛选按钮", banner_bottom <= ui.btn_faction.y)
check("10b faction 右对齐不越屏",
      ui.detail_x + ui.detail_w <= SCREEN_WIDTH)
name = "FA18E超级大黄蜂式战斗轰炸机"
f = ui.font_title if ui.font_title.size(name)[0] <= ui.detail_w - 10 else ui.font_detail_h
check("10c 最长名字（适配字号后）不越详情区", ui.detail_x + f.size(name)[0] <= ui.detail_x + ui.detail_w)

# 11. 筛选到建筑类再绘制（分类视图 + history 渲染路径）
ui.filter_type = "防御建筑"
ui.apply_filter()
try:
    ui.draw(screen)
    ok11 = all(d["history"] for d in ui.visible_data)
except Exception as e:
    ok11 = False
    print("  filter draw err:", e)
check("11 建筑分类筛选+绘制", ok11)

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
