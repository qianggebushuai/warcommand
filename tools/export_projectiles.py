# -*- coding: utf-8 -*-
"""
弹射物立绘导出工具
==================
程序绘制生成 sprites/projectiles/<键>.png（弹头统一朝右 +x，2 倍世界尺寸），
运行时 Projectile.draw 按 d_type / png_key 加载并随速度方向旋转，缺失回退圆球。

用法：
    python tools/export_projectiles.py          # 导出全部
    python tools/export_projectiles.py 键1 键2  # 只重导指定键

美术修改：直接编辑对应 PNG（改尺寸=改显示大小，保持弹头朝右即可）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sprites', 'projectiles')

# 键: (世界宽, 世界高, 绘制规格)。PNG 输出为 2 倍尺寸。
# 绘制规格: style=shell(弹体+尖头+尾翼) / bomb(椭圆弹体+十字尾翼) / tracer(曳光细弹)
#   body/nose/fin/highlight: 颜色；tip_len: 头锥长比例；glow: 尾部引擎光
SPECS = {
    # ---- 基础弹种（d_type 同名）----
    'rifle':          (10, 3, dict(style='tracer', body=(200, 180, 120), nose=(240, 220, 160), fin=None, glow=None)),
    'bullet':         (12, 5, dict(style='tracer', body=(255, 230, 120), nose=(255, 255, 200), fin=None, glow=(255, 200, 80))),
    'heavy':          (14, 6, dict(style='shell',  body=(200, 170, 90),  nose=(235, 210, 140), fin=(150, 120, 60), glow=None)),
    'rocket':         (20, 8, dict(style='shell',  body=(160, 160, 165), nose=(255, 130, 40),  fin=(110, 110, 115), glow=(255, 170, 60))),
    'tank_shell':     (20, 6, dict(style='shell',  body=(150, 165, 180), nose=(210, 220, 230), fin=(110, 120, 130), glow=None)),
    'heavy_shell':    (24, 10, dict(style='shell', body=(70, 72, 78),    nose=(120, 124, 132), fin=(50, 52, 56),   glow=None)),
    'behemoth_bomb':  (16, 11, dict(style='bomb',  body=(110, 120, 80),  nose=(140, 150, 100), fin=(85, 92, 62),    glow=None)),
    'ac130_vis':      (16, 10, dict(style='bomb',  body=(90, 90, 95),    nose=(130, 130, 138), fin=(70, 70, 75),    glow=None)),
    'ac130_howitzer_vis': (28, 15, dict(style='bomb', body=(95, 102, 82), nose=(140, 148, 120), fin=(65, 72, 58),  glow=None)),
    # ---- 单位专属（发射点传 png_key 区分）----
    'rocket_wz10':    (20, 8, dict(style='shell',  body=(180, 185, 190), nose=(220, 60, 50),    fin=(120, 124, 130), glow=(255, 150, 50))),
    'rocket_mi24':    (20, 8, dict(style='shell',  body=(150, 140, 135), nose=(200, 90, 40),    fin=(100, 92, 88),   glow=(255, 160, 60))),
    'rocket_rpg':     (19, 8, dict(style='shell',  body=(120, 130, 100), nose=(95, 150, 70),    fin=(90, 98, 74),    glow=(255, 180, 80))),
    'rocket_mech':    (21, 9, dict(style='shell',  body=(130, 140, 160), nose=(80, 110, 220),   fin=(95, 102, 120),  glow=(120, 170, 255))),
    'rocket_himars':  (22, 7, dict(style='shell',  body=(170, 175, 165), nose=(240, 200, 60),   fin=(115, 118, 110), glow=(255, 200, 90))),
    'rocket_drone':   (18, 8, dict(style='shell',  body=(200, 120, 50),  nose=(255, 220, 120),  fin=(150, 85, 35),   glow=(255, 120, 40))),
    'shell_type99':   (20, 6, dict(style='shell',  body=(90, 110, 90),   nose=(170, 190, 170),  fin=(65, 80, 65),    glow=None)),
    'shell_m1a2':     (20, 6, dict(style='shell',  body=(185, 170, 140), nose=(225, 215, 190),  fin=(135, 124, 100), glow=None)),
    'shell_battleship':(24, 10, dict(style='shell', body=(55, 60, 70),    nose=(150, 160, 175),  fin=(40, 44, 52),    glow=None)),
    'shell_train':    (21, 7, dict(style='shell',  body=(105, 95, 85),   nose=(190, 175, 150),  fin=(75, 68, 60),    glow=None)),
}
SCALE = 2  # PNG 输出倍率（世界尺寸 * 2），draw 端按 zoom*0.5 还原


def _draw_shell(surf, w, h, spec):
    """弹体+尖头+尾翼，弹头朝右，图心居中"""
    cx, cy = w // 2, h // 2
    body_r = int(h * 0.30)                      # 弹身半径
    body_l, body_r_edge = int(w * 0.18), int(w * 0.68)
    nose_tip = int(w * 0.96)
    fin_x = body_l
    # 尾翼（先画，压在弹身下面）
    if spec.get('fin'):
        fh = int(h * 0.48)
        pygame.draw.polygon(surf, spec['fin'],
                            [(fin_x, cy - body_r + 1), (fin_x - int(w * 0.14), cy - body_r - fh),
                             (fin_x + int(w * 0.06), cy - body_r - fh + 1), (fin_x + int(w * 0.10), cy - body_r + 1)])
        pygame.draw.polygon(surf, spec['fin'],
                            [(fin_x, cy + body_r - 1), (fin_x - int(w * 0.14), cy + body_r + fh),
                             (fin_x + int(w * 0.06), cy + body_r + fh - 1), (fin_x + int(w * 0.10), cy + body_r - 1)])
    # 弹身（圆角矩形：矩形+两端圆）
    pygame.draw.rect(surf, spec['body'], (body_l, cy - body_r, body_r_edge - body_l, body_r * 2))
    pygame.draw.circle(surf, spec['body'], (body_r_edge, cy), body_r)
    pygame.draw.circle(surf, spec['body'], (body_l, cy), body_r)
    # 头锥
    pygame.draw.polygon(surf, spec['nose'],
                        [(body_r_edge - body_r + 2, cy - body_r + 1), (body_r_edge - body_r + 2, cy + body_r - 1),
                         (nose_tip, cy)])
    # 上侧高光
    hl = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.line(hl, (255, 255, 255, 90), (body_l + 2, cy - body_r + 2), (body_r_edge, cy - body_r + 2), 2)
    surf.blit(hl, (0, 0))
    # 尾部引擎光
    if spec.get('glow'):
        g = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.circle(g, (*spec['glow'], 200), (body_l - 1, cy), max(2, body_r - 1))
        pygame.draw.circle(g, (*spec['glow'], 120), (body_l - 3, cy), body_r + 1)
        surf.blit(g, (0, 0), special_flags=pygame.BLEND_ADD)


def _draw_bomb(surf, w, h, spec):
    """航空炸弹：椭圆弹体+头锥+十字尾翼"""
    cx, cy = w // 2, h // 2
    rx, ry = int(w * 0.30), int(h * 0.34)
    # 十字尾翼（左侧）
    fx = cx - rx
    fh = int(h * 0.46)
    pygame.draw.polygon(surf, spec['fin'],
                        [(fx + 2, cy - ry + 2), (fx - int(w * 0.14), cy - fh), (fx + int(w * 0.10), cy - fh)])
    pygame.draw.polygon(surf, spec['fin'],
                        [(fx + 2, cy + ry - 2), (fx - int(w * 0.14), cy + fh), (fx + int(w * 0.10), cy + fh)])
    # 弹体
    pygame.draw.ellipse(surf, spec['body'], (cx - rx, cy - ry, rx * 2, ry * 2))
    # 头锥（右侧，弧形用小椭圆近似）
    pygame.draw.ellipse(surf, spec['nose'], (cx + rx - int(w * 0.22), cy - ry + 1, int(w * 0.24), ry * 2 - 2))
    # 挂环高光
    hl = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.line(hl, (255, 255, 255, 80), (cx - rx + 3, cy - ry + 3), (cx + rx - 5, cy - ry + 3), 2)
    surf.blit(hl, (0, 0))


def _draw_tracer(surf, w, h, spec):
    """细长曳光弹：亮弹身+白芯+尾部光点"""
    cx, cy = w // 2, h // 2
    r = max(2, int(h * 0.32))
    pygame.draw.rect(surf, spec['body'], (int(w * 0.15), cy - r, int(w * 0.70), r * 2))
    pygame.draw.polygon(surf, spec['nose'],
                        [(int(w * 0.85), cy - r), (int(w * 0.85), cy + r), (int(w * 0.98), cy)])
    core = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.line(core, (255, 255, 255, 160), (int(w * 0.2), cy), (int(w * 0.75), cy), 1)
    surf.blit(core, (0, 0))
    if spec.get('glow'):
        g = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.circle(g, (*spec['glow'], 170), (int(w * 0.12), cy), r + 1)
        surf.blit(g, (0, 0), special_flags=pygame.BLEND_ADD)


_STYLE_FN = {'shell': _draw_shell, 'bomb': _draw_bomb, 'tracer': _draw_tracer}


def export(key, force=False):
    world_w, world_h, spec = SPECS[key]
    w, h = world_w * SCALE, world_h * SCALE
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, key + '.png')
    if os.path.exists(path) and not force:
        print(f'[skip] {key}.png 已存在（删掉可重新生成）')
        return
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    _STYLE_FN[spec['style']](surf, w, h, spec)
    pygame.image.save(surf, path)
    print(f'[ok] {key}.png  {w}x{h}（世界 {world_w}x{world_h}）')


def main():
    pygame.init()
    keys = sys.argv[1:] or list(SPECS)
    for k in keys:
        if k not in SPECS:
            print(f'[!] 未知键: {k}，可选: {", ".join(SPECS)}')
            continue
        export(k, force=True)
    print(f'完成，输出目录: {OUT_DIR}')


if __name__ == '__main__':
    main()
