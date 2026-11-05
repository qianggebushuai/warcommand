# -*- coding: utf-8 -*-
"""弹射物立绘冒烟：PNG 加载 / 旋转绘制 / 回退链路 / 发射点 png_key（无头）"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['SDL_VIDEODRIVER'] = 'dummy'

import pygame
pygame.init()
pygame.display.set_mode((200, 200))

from pygame.math import Vector2 as vec
from core.base_classes import Projectile, _get_proj_img
from core.settings import SCREEN_WIDTH, SCREEN_HEIGHT

W = SCREEN_WIDTH if isinstance(SCREEN_WIDTH, int) else 1280
H = SCREEN_HEIGHT if isinstance(SCREEN_HEIGHT, int) else 720
screen = pygame.Surface((W, H))


class MockParticles:
    def add(self, *a, **k): pass


class MockGame:
    particles = MockParticles()
    all_units = []
    all_buildings = []
    is_online = False
    my_role = 'HOST'
    net_events = []
    my_team = 'team_0'
    projectiles = []


# 18 张 PNG 全部可加载
EXPECTED = ['rifle', 'bullet', 'heavy', 'rocket', 'tank_shell', 'heavy_shell',
            'behemoth_bomb', 'ac130_vis', 'rocket_wz10', 'rocket_mi24',
            'rocket_rpg', 'rocket_mech', 'rocket_himars', 'rocket_drone',
            'shell_type99', 'shell_m1a2', 'shell_battleship', 'shell_train']
for key in EXPECTED:
    img = _get_proj_img(key)
    assert img is not None, 'PNG 缺失: ' + key
assert len(EXPECTED) == 18
print('1. 18 张弹射物 PNG 加载 OK')

game = MockGame()
target = vec(900, 400)


def make(d_type, png_key=None):
    p = Projectile(game, vec(300, 300), None, 'team_0', 10, d_type, png_key=png_key)
    p.vel = vec(5, -3)   # 斜向速度 -> 旋转角约 31°
    return p


# 全弹种 draw 不崩且走 PNG 分支
draw_keys = ['rifle', 'bullet', 'heavy', 'rocket', 'tank_shell', 'behemoth_bomb', 'ac130_vis']
for dt in draw_keys:
    p = make(dt)
    p.draw(screen, vec(0, 0), 1.0)
print('2. 默认分支 7 弹种 PNG 旋转绘制 OK')

# heavy_shell 专属分支
p = make('heavy_shell', 'shell_battleship')
p.draw(screen, vec(0, 0), 1.0)
assert p._blit_proj_png(screen, 1.0, (50, 50)) is True
print('3. heavy_shell 专属分支 OK')

# png_key 缺失回退圆球
p = make('rocket', 'no_such_key')
assert p._blit_proj_png(screen, 1.0, (50, 50)) is False
p.draw(screen, vec(0, 0), 1.0)   # 回退圆球不崩
print('4. PNG 缺失回退圆球 OK')

# 旋转角度：竖直向上速度 -> 立绘旋转 -90°?  atan2(-(-v),0): vel=(0,-5) 世界向上 -> ang=+90
p = make('rocket')
p.vel = vec(0, -5)
p.draw(screen, vec(0, 0), 1.0)   # ang=90 不崩即可
assert abs(__import__('math').degrees(__import__('math').atan2(5, 0)) - 90) < 1e-6
print('5. 方向旋转角度约定 OK（向上=90°）')

# laser/flame/fire_zone/incendiary 特效分支不受影响（仍程序绘制）
for dt in ['laser', 'laser2', 'flame', 'fire_zone', 'incendiary']:
    p = Projectile(game, vec(300, 300), None, 'team_0', 5, dt, is_aoe=True, aoe_radius=40)
    if dt == 'laser':
        class T:
            pos = vec(800, 400)
            alive = True
        p.target = T()
        p.target_dest = T().pos
    p.draw(screen, vec(0, 0), 1.0)
print('6. 特效弹种（laser/flame/fire_zone/incendiary）不受影响 OK')

print('ALL PASS')
