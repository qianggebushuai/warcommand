# -*- coding: utf-8 -*-
"""程序化绘制图鉴/设置横幅（军事 HUD 风），输出到 picture/。"""
import os
import sys
import math
import random

os.environ['SDL_VIDEODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
pygame.display.set_mode((100, 100))
random.seed(42)


def vgrad(w, h, top, bottom):
    surf = pygame.Surface((w, h))
    for y in range(h):
        t = y / max(1, h - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        pygame.draw.line(surf, c, (0, y), (w, y))
    return surf


def hud_corners(surf, color, x0, y0, x1, y1, L=18, t=2):
    """四角 HUD 角框"""
    for (cx, cy, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        pygame.draw.line(surf, color, (cx, cy), (cx + dx * L, cy), t)
        pygame.draw.line(surf, color, (cx, cy), (cx, cy + dy * L), t)


def hexagon(surf, color, pos, r, width):
    pts = [(pos[0] + r * math.cos(math.radians(60 * i - 30)),
            pos[1] + r * math.sin(math.radians(60 * i - 30))) for i in range(6)]
    if width <= 0:
        pygame.draw.polygon(surf, color, pts)
    else:
        pygame.draw.polygon(surf, color, pts, width)


# ---------- 图鉴横幅：全息数据库风（青色 HUD） ----------
W, H = 960, 110
surf = vgrad(W, H, (13, 22, 32), (22, 36, 48)).convert()
# 透视网格
grid = (58, 96, 110)
for x in range(0, W, 48):
    pygame.draw.line(surf, grid, (x, 0), (x, H), 1)
for y in range(0, H, 27):
    pygame.draw.line(surf, grid, (0, y), (W, y), 1)
# 扫描亮带
band = pygame.Surface((W, 14), pygame.SRCALPHA)
band.fill((80, 200, 215, 26))
surf.blit(band, (0, 62))
# 伪数据列（右侧）
for i in range(26):
    x = W - 320 + (i % 13) * 24
    y = 14 + (i // 13) * 22
    h = random.randint(6, 16)
    c = (70, 170, 185) if random.random() < 0.7 else (130, 220, 230)
    pygame.draw.rect(surf, c, (x, y + (16 - h) // 2, 10, h), 0 if random.random() < 0.5 else 1)
# 六边形群（左）
for i, (hx, hr, hw) in enumerate(((52, 30, 2), (96, 20, 1), (136, 12, 0))):
    hexagon(surf, (60, 150, 165), (hx, H // 2 + (i % 2) * 12 - 6), hr, hw)
hexagon(surf, (90, 210, 220), (52, H // 2 - 6), 10, 0)
# 顶部/底部亮线
pygame.draw.line(surf, (90, 210, 220), (0, 1), (W, 1), 1)
pygame.draw.line(surf, (50, 120, 135), (0, H - 2), (W, H - 2), 2)
hud_corners(surf, (120, 225, 235), 2, 2, W - 3, H - 3)
# 小装饰刻度
for x in range(220, W - 340, 60):
    pygame.draw.line(surf, (70, 140, 155), (x, H - 12), (x, H - 6), 1)
surf = pygame.transform.smoothscale(surf, (768, 88))  # 稍降分辨率贴合 UI
pygame.image.save(surf, os.path.join('picture', 'banner_database.png'))
print('banner_database.png', surf.get_size())

# ---------- 设置横幅：工业金属风（琥珀线条+齿轮） ----------
W, H = 800, 100
surf = vgrad(W, H, (26, 29, 35), (38, 43, 52)).convert()
# 拉丝金属横纹
for y in range(0, H, 4):
    c = (46, 51, 60) if y % 8 == 0 else (32, 36, 43)
    pygame.draw.line(surf, c, (0, y), (W, y), 1)
# 铆钉
for x in range(24, W, 56):
    pygame.draw.circle(surf, (58, 64, 75), (x, 12), 3)
    pygame.draw.circle(surf, (16, 18, 22), (x, 12), 3, 1)
# 电路走线（右）
amber = (214, 150, 58)
for i, yy in enumerate((30, 50, 70)):
    x0 = W - 300 + i * 40
    pygame.draw.line(surf, amber, (x0, yy), (W - 60, yy), 2)
    pygame.draw.line(surf, amber, (W - 60, yy), (W - 40, yy + (i - 1) * 14), 2)
    pygame.draw.circle(surf, (240, 180, 90), (x0, yy), 3)
    pygame.draw.circle(surf, (240, 180, 90), (W - 40, yy + (i - 1) * 14), 3, 1)
# 齿轮（左）
gx, gy = 60, H // 2
for tooth in range(10):
    a = math.radians(tooth * 36)
    x1 = gx + math.cos(a) * 30
    y1 = gy + math.sin(a) * 30
    x2 = gx + math.cos(a) * 40
    y2 = gy + math.sin(a) * 40
    pygame.draw.line(surf, amber, (x1, y1), (x2, y2), 5)
pygame.draw.circle(surf, amber, (gx, gy), 30, 3)
pygame.draw.circle(surf, amber, (gx, gy), 10, 2)
pygame.draw.circle(surf, (150, 105, 42), (gx, gy), 4)
# 顶/底强调线
pygame.draw.line(surf, amber, (0, 0), (W, 0), 3)
pygame.draw.line(surf, (120, 84, 34), (0, H - 2), (W, H - 2), 2)
hud_corners(surf, (230, 170, 90), 2, 2, W - 3, H - 3, L=14, t=2)
surf = pygame.transform.smoothscale(surf, (640, 80))
pygame.image.save(surf, os.path.join('picture', 'banner_settings.png'))
print('banner_settings.png', surf.get_size())

# ---------- 矿车图标（俯视工程车，Harvester 图鉴用） ----------
W, H = 150, 100
surf = pygame.Surface((W, H), pygame.SRCALPHA).convert()
# 阴影
pygame.draw.ellipse(surf, (20, 24, 20, 90), (18, 62, 114, 26))
# 车体（黄色工程车）
body = pygame.Rect(30, 22, 90, 44)
pygame.draw.rect(surf, (218, 168, 40), body, border_radius=8)
pygame.draw.rect(surf, (150, 112, 24), body, 3, border_radius=8)
# 矿斗（后部深槽）
hopper = pygame.Rect(64, 28, 48, 32)
pygame.draw.rect(surf, (70, 60, 44), hopper, border_radius=5)
pygame.draw.rect(surf, (40, 34, 24), hopper, 2, border_radius=5)
# 矿石
for ox, oy in ((76, 36), (90, 44), (100, 34), (84, 50)):
    pygame.draw.circle(surf, (110, 96, 78), (ox, oy), 5)
    pygame.draw.circle(surf, (140, 124, 100), (ox - 1, oy - 2), 2)
# 驾驶舱（前部）
cab = pygame.Rect(34, 28, 24, 32)
pygame.draw.rect(surf, (240, 196, 70), cab, border_radius=5)
pygame.draw.rect(surf, (150, 112, 24), cab, 2, border_radius=5)
pygame.draw.rect(surf, (110, 190, 205), (38, 32, 16, 12), border_radius=3)
# 六轮
for wx in (44, 72, 100):
    for wy in (18, 70):
        pygame.draw.circle(surf, (30, 30, 32), (wx, wy), 9)
        pygame.draw.circle(surf, (70, 70, 74), (wx, wy), 9, 2)
        pygame.draw.circle(surf, (95, 95, 100), (wx, wy), 4)
# 高亮边
hud_corners(surf, (120, 200, 120), 4, 4, W - 5, H - 5, L=12, t=2)
surf = pygame.transform.smoothscale(surf, (300, 200))
pygame.image.save(surf, os.path.join('picture', 'icon_harvester.png'))
print('icon_harvester.png', surf.get_size())
