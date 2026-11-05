# -*- coding: utf-8 -*-
"""主界面（LOGIN/MENU）图鉴+设置入口按钮冒烟。"""
import os
import sys

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
# settings 常量在导入时读取显示模式，须先设真实分辨率
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
from core.dic import DictionaryUI
from panels.basesetting import BaseSettingUI

class G:
    state = "LOGIN"
    master_volume = 0.5
    fullscreen = False

    def apply_display_mode(self, fs, size=None):
        self.fullscreen = fs

g = G()
screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
dic = DictionaryUI(g)
st = BaseSettingUI(g)

CLICK = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (0, 0)})

# 1. 两入口按钮并排右上角且不重叠
r1, r2 = dic.btn_open, st.btn_open
check("1a 图鉴入口在右上角", r1.right <= SCREEN_WIDTH - 40 and r1.top >= 10)
check("1b 设置入口在右上角", r2.right <= SCREEN_WIDTH - 15 and r2.top >= 10)
check("1c 两入口不重叠", not r1.colliderect(r2.inflate(6, 6)))

# 2. MENU 状态整页渲染（菜单按钮无 mock——只渲染两入口面板层）
g.state = "MENU"
try:
    dic.draw(screen)   # 未激活→画书本按钮
    st.draw(screen)    # 未激活→画齿轮
    ok2 = True
except Exception as e:
    ok2 = False
    print("  menu render err:", e)
check("2 MENU 状态渲染两入口", ok2)

# 3. MENU 点击图鉴按钮 → 打开并记住来源
CLICK.pos = dic.btn_open.center
ok3 = dic.handle_event(CLICK) and dic.active and g.state == "DIC"
check("3 点击图鉴打开并切 DIC 状态", ok3)

# 4. 关闭图鉴 → 回到主菜单（不再是硬编码 LOGIN）
dic.close()
check("4 关闭图鉴回到 MENU", g.state == "MENU" and not dic.active)

# 5. MENU 点击设置齿轮 → 打开设置面板
CLICK.pos = st.btn_open.center
ok5 = st.handle_event(CLICK) is True and st.active
check("5 点击设置齿轮打开面板", ok5)

# 6. 设置激活时拦截事件，点关闭恢复
CLICK.pos = (0, 0)
ok6 = st.handle_event(CLICK) is True  # 激活时吞掉无关点击
# basesetting 关闭判定用 mouse.get_pos()（真实运行无误），无头测试直接伪造鼠标位置
_orig_gpos = pygame.mouse.get_pos
pygame.mouse.get_pos = lambda: st.btn_close.center
st.handle_event(pygame.event.Event(
    pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": st.btn_close.center}))
pygame.mouse.get_pos = _orig_gpos
check("6 设置面板激活拦截+关闭", ok6 and not st.active)

# 7. LOGIN 状态渲染两入口
g.state = "LOGIN"
try:
    dic.draw(screen)
    st.draw(screen)
    ok7 = True
except Exception as e:
    ok7 = False
    print("  login render err:", e)
check("7 LOGIN 状态渲染两入口", ok7)

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
