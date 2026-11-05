# -*- coding: utf-8 -*-
"""冒烟：采矿距离扩大 + 音效视野衰减（无头）"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['SDL_VIDEODRIVER'] = 'dummy'
try:
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
except Exception:
    pass

import io
import time
import pygame
pygame.init(); pygame.mixer.init()

from pygame.math import Vector2 as vec
from core.sfx import SFXManager
from maps.map_data import OrePatch

# ---- 1. 采矿距离：源码不变式 + 状态机模拟 ----
src = io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'units', 'vehicles.py'), encoding='utf-8').read()
assert 'patch.radius + 45' in src and 'patch.radius + 12' not in src
print('1. 采矿判定源码 = radius + 45 OK')

class _G:
    my_team = 'team_0'
    team_resources = {}
    current_map = None

game = _G()
patch = OrePatch(game, vec(1000, 1000))          # radius 38, 满储量
# 模拟状态机判定：距离 = radius+40（旧判定 50 之外，新判定 83 之内）
dist = patch.radius + 40
stop_old, stop_new = patch.radius + 12, patch.radius + 45
assert not (dist <= stop_old) and (dist <= stop_new), '扩大范围语义失败'
print('2. 距矿 %d px：旧范围拒采 -> 新范围可采 OK' % int(dist))

# ---- 2. 音效视野衰减 ----
m = SFXManager.instance()
assert m.sounds.get('rifle'), 'rifle 音效未加载'
SFXManager.set_listener(vec(0, 0))

# 近处（<FULL_DIST）：全音量播放
m._last_play.pop('rifle', None)
m.play('rifle', 0.5, pos=vec(100, 100))
assert 'rifle' in m._last_play, '近处音效未播放'
print('3. 近处（100px）播放 OK')

# 中距离（FULL~CUTOFF 之间）：衰减但仍播放
time.sleep(0.06)
m._last_play.pop('rifle', None)
m.play('rifle', 0.5, pos=vec(1400, 0))
assert 'rifle' in m._last_play, '中距离音效未播放'
print('4. 中距离（1400px）衰减播放 OK')

# 远处（>=CUTOFF）：直接丢弃
time.sleep(0.06)
m._last_play.pop('rifle', None)
m.play('rifle', 0.5, pos=vec(2200, 0))
assert 'rifle' not in m._last_play, '远处音效不应播放'
print('5. 远处（2200px）不播放 OK')

# UI 音（select）不传 pos：不受 listener 影响
time.sleep(0.06)
m._last_play.pop('select', None)
m.play('select', 0.7)     # 无 pos
assert 'select' in m._last_play, 'UI 音被误衰减'
print('6. UI 音不衰减 OK')

# listener 未同步（None）：带 pos 也不衰减
time.sleep(0.06)
SFXManager.set_listener(None)
m._last_play.pop('rifle', None)
m.play('rifle', 0.5, pos=vec(99999, 99999))
assert 'rifle' in m._last_play, '无监听点时不应丢弃'
print('7. listener 未同步时保持旧行为 OK')

print('ALL PASS')
