# -*- coding: utf-8 -*-
"""程序化绘制巨型电磁塔立绘（俯视巴黎铁塔风格）→ picture/tesla_tower.png（256×256）。

结构自下而上：
- 底部能量光晕 + 右下投影；
- 四条从四角向中心内弯的塔腿（二次贝塞尔多段线，宽度渐减，段间微桁架斜撑）；
- 三层方形平台（由大到小，依次旋转 45°：轴对齐 → 菱形 → 轴对齐），顶层带微网格桁架纹；
- 中心立柱 + 塔顶发光线圈球（同心圆电蓝渐变 + 外圈半透明光晕 + 白炽核心）。
配色：深钢灰主体 + 电蓝高光。运行：python tools/gen_tesla_art.py
"""
import os
import math
import pygame

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

W = H = 320
CX = CY = W // 2

# --- 色板：深钢灰主体 + 电蓝高光 ---
STEEL_DARK = (52, 56, 62)
STEEL_MID = (86, 92, 100)
STEEL_LIGHT = (120, 126, 136)
EDGE_DARK = (28, 31, 36)
GRID_LINE = (62, 68, 76)
ELEC_DIM = (70, 130, 190)
ELEC_MID = (110, 190, 245)
ELEC_BRIGHT = (150, 220, 255)
ELEC_CORE = (228, 246, 255)

pygame.init()
pygame.display.set_mode((W, H))   # dummy 驱动，仅为 convert_alpha 提供环境

surf = pygame.Surface((W, H), pygame.SRCALPHA)


def rot(px, py, deg):
    """平面点旋转（度）"""
    a = math.radians(deg)
    return (px * math.cos(a) - py * math.sin(a), px * math.sin(a) + py * math.cos(a))


def quad_points(p0, p1, p2, n):
    """二次贝塞尔曲线采样 n+1 个点"""
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        pts.append((x, y))
    return pts


def blit_rgba(layer):
    """把半透明图层混到主画布（draw 系列不混合 alpha，须分层 blit）"""
    surf.blit(layer, (0, 0))


# 1) 底部能量光晕（同心半透明环，分层混合）
glow = pygame.Surface((W, H), pygame.SRCALPHA)
for r, a in ((148, 20), (128, 28), (106, 38)):
    pygame.draw.circle(glow, (*ELEC_MID, a), (CX, CY), r)
blit_rgba(glow)

# 2) 投影（与塔身完全同心的椭圆——禁止偏移，否则深色团偏一侧会让塔身视觉上偏向对侧）
shadow = pygame.Surface((W, H), pygame.SRCALPHA)
pygame.draw.ellipse(shadow, (0, 0, 0, 85), (CX - 70, CY - 70, 140, 140))
blit_rgba(shadow)

# 3) 四条从四角向中心内弯的塔腿（二次曲线多段线，宽度渐减 + 桁架横撑）
#    俯视巴黎铁塔的关键：塔脚外撇很宽、腿身大幅内弯收拢到塔心
LEG_FOOT = 150       # 塔脚到中心距离（四角 45° 方向）
LEG_TIP = 14         # 塔腿末端到中心距离
for i in range(4):
    ang = math.radians(45 + 90 * i)
    dx, dy = math.cos(ang), math.sin(ang)
    p0 = (CX + dx * LEG_FOOT, CY + dy * LEG_FOOT)
    p2 = (CX + dx * LEG_TIP, CY + dy * LEG_TIP)
    # 控制点贴近塔脚一侧 → 腿先沿对角线外撇再急收向塔心（凹弧造型）
    p1 = (CX + dx * LEG_FOOT * 0.30, CY + dy * LEG_FOOT * 0.30)
    pts = quad_points(p0, p1, p2, 14)
    nx, ny = -dy, dx
    for k in range(len(pts) - 1):
        f = k / (len(pts) - 1)
        w = max(2, int(round(10 - 8 * f)))           # 宽度 10→2 渐减
        col = STEEL_DARK if f < 0.5 else STEEL_MID   # 越靠塔心越亮
        pygame.draw.line(surf, col, pts[k], pts[k + 1], w)
        pygame.draw.line(surf, EDGE_DARK, pts[k], pts[k + 1], 1)
        # 桁架横撑：垂直腿身的短杆（中段最明显，双根成人字纹）
        if 0 < k < len(pts) - 2:
            mx = (pts[k][0] + pts[k + 1][0]) / 2
            my = (pts[k][1] + pts[k + 1][1]) / 2
            amp = LEG_FOOT * 0.14 * math.sin(f * math.pi) + 4
            pygame.draw.line(surf, STEEL_LIGHT,
                             (mx - nx * amp, my - ny * amp),
                             (mx + nx * amp, my + ny * amp), 1)
    # 塔脚基座（小方墩）
    foot = (p0[0] + dx * -5, p0[1] + dy * -5)
    pygame.draw.circle(surf, STEEL_DARK, (int(foot[0]), int(foot[1])), 8)
    pygame.draw.circle(surf, EDGE_DARK, (int(foot[0]), int(foot[1])), 8, 2)

# 4) 三层方形平台：由大到小，依次旋转 45°（放大占满画布中心）
for k, side in enumerate((104, 74, 50)):
    deg = 45 * k
    half = side / 2
    corners = []
    for ux, uy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        rx, ry = rot(ux * half, uy * half, deg)
        corners.append((CX + rx, CY + ry))
    fill = STEEL_MID if k in (0, 2) else STEEL_LIGHT
    pygame.draw.polygon(surf, fill, corners)
    pygame.draw.polygon(surf, EDGE_DARK, corners, 3)
    # 顶缘电蓝高光描边（上移 1px 的细线）
    hl = [(p[0], p[1] - 1) for p in corners]
    pygame.draw.polygon(surf, ELEC_DIM, hl, 1)
    # 顶层平台微网格桁架纹
    if k == 2:
        step = side // 4
        for gx in range(-2, 3):
            off = gx * step
            x0, y0 = rot(off, -half, deg)
            x1, y1 = rot(off, half, deg)
            pygame.draw.line(surf, GRID_LINE, (CX + x0, CY + y0), (CX + x1, CY + y1), 1)
            x0, y0 = rot(-half, off, deg)
            x1, y1 = rot(half, off, deg)
            pygame.draw.line(surf, GRID_LINE, (CX + x0, CY + y0), (CX + x1, CY + y1), 1)

# 5) 中心立柱
pygame.draw.circle(surf, STEEL_DARK, (CX, CY), 14)
pygame.draw.circle(surf, EDGE_DARK, (CX, CY), 14, 2)
pygame.draw.circle(surf, STEEL_MID, (CX, CY), 9)

# 6) 塔顶发光线圈球：同心圆电蓝渐变（自外向内变亮）+ 半透明光晕环 + 白炽核心
for r, col in ((28, (40, 90, 140)), (20, ELEC_DIM), (14, ELEC_MID),
               (8, ELEC_BRIGHT), (4, ELEC_CORE)):
    pygame.draw.circle(surf, col, (CX, CY), r)
halo = pygame.Surface((W, H), pygame.SRCALPHA)
for r, a in ((36, 70), (44, 42), (52, 22)):
    pygame.draw.circle(halo, (*ELEC_BRIGHT, a), (CX, CY), r, 4)
# 线圈外四道电弧刻痕（45° 方向短放电）
for i in range(4):
    a = math.radians(45 + 90 * i)
    x0, y0 = CX + math.cos(a) * 34, CY + math.sin(a) * 34
    x1, y1 = CX + math.cos(a) * 46, CY + math.sin(a) * 46
    xm, ym = (x0 + x1) / 2 + math.cos(a + math.pi / 2) * 5, (y0 + y1) / 2 + math.sin(a + math.pi / 2) * 5
    pygame.draw.lines(halo, (*ELEC_BRIGHT, 200), False, [(x0, y0), (xm, ym), (x1, y1)], 2)
blit_rgba(halo)

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "picture", "tesla_tower.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
pygame.image.save(surf, out)
print("saved:", out)
