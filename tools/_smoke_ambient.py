# -*- coding: utf-8 -*-
"""常驻战场氛围冒烟：云影/飞鸟/炮火/尘埃 update+draw 长跑不崩、触发器生效（无头）"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['SDL_VIDEODRIVER'] = 'dummy'

import pygame
pygame.init()
screen = pygame.display.set_mode((1280, 720))

from pygame.math import Vector2 as vec
from maps.environment import EnvironmentManager


class MockMap:
    width = 4000
    height = 3000


class MockGame:
    zoom = 0.8
    camera_offset = vec(300, 200)
    current_map = MockMap()
    lakes = []


env = EnvironmentManager(MockGame())

# 初始状态
assert len(env.ambient_clouds) == 5 and len(env.dust) == 16
print('1. 初始化：5 云影 + 16 尘埃 OK')

# 长跑 700 帧（触发炮火至少一次；鸟间隔 400-900 帧也可能出）
for i in range(700):
    env.update()
    env.draw(screen)
print('2. 700 帧 update+draw 无崩溃')

# 加速触发：清计时器强制刷鸟与炮火
env.bird_timer = 1
env.update()
assert len(env.birds) >= 5, '鸟群未生成'
print('3. 鸟群生成 OK（%d 只）' % len(env.birds))

# 云影世界漂移 + 回绕
c = env.ambient_clouds[0]
x0 = c['x']
env.update()
assert c['x'] > x0
c['x'] = env.ambient_bounds[0] + c['w'] + 1
env.update()
assert c['x'] < 0, '云影未回绕'
print('5. 云影漂移与回绕 OK')

# 缩放缓存生效（zoom 档位）
env._ambient_scaled(c, 640, 400)
assert len(env._ambient_scale_cache) >= 1
print('6. 云影缩放缓存 OK')

# 与 storm 天气共存
env.set_weather('storm')
env.target_intensity = 1.0
env.intensity = 1.0
for i in range(30):
    env.update()
    env.draw(screen)
print('7. 氛围层与 storm 天气共存 OK')

print('ALL PASS')
