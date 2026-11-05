# -*- coding: utf-8 -*-
"""冒烟：矿车选矿最多 + 手动指令后不再发呆（无头）"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame
pygame.init()

from pygame.math import Vector2 as vec
from units.vehicles import Harvester
from maps.map_data import OrePatch


class MockHome:
    pos = vec(2000, 2000)
    alive = True
    b_type = 'mining'


class MockParticles:
    def add(self, *a, **k):
        pass


class MockGame:
    my_team = 'team_0'
    my_role = 'HOST'
    is_online = False
    team_resources = {'team_0': 0}
    all_buildings = [MockHome()]
    all_units = []
    particles = MockParticles()
    current_map = None


g = MockGame()
g.current_map = type('M', (), {'ore_patches': []})()
home = MockHome()
h = Harvester(g, vec(1000, 1000), 'team_0', home)

# ---- 1. 选矿最多（不是最近）----
far_rich = OrePatch(g, vec(1400, 1000)); far_rich.amount = 4000    # 远但富
near_poor = OrePatch(g, vec(1030, 1000)); near_poor.amount = 25    # 近但贫
g.current_map.ore_patches = [near_poor, far_rich]
h.state = "IDLE"; h.mine_timer = 0
h._update_mining_ai()
assert h.state == "MOVING_TO_ORE" and h.ore_patch is far_rich, '应选矿最多的矿脉'
print('1. IDLE 自动选取矿最多的矿井 OK')

# ---- 2. 完整两轮采集不卡死（手动打断也不发呆）----
for rnd in range(2):
    # MINING 采满
    h.state = "MINING"; h.ore_patch = far_rich; h.ore_cargo = 0.0
    h._update_mining_ai()
    assert h.state in ("MINING", "RETURNING")
    for _ in range(600):
        h._update_mining_ai()
        if h.state == "RETURNING":
            break
    assert h.state == "RETURNING", '满载应返家'
    # 传送回家卸货
    h.pos = vec(home.pos.x - 30, home.pos.y)
    h._update_mining_ai()
    assert h.state == "IDLE" and h.ore_cargo == 0.0, '卸货后 IDLE'
    # IDLE 立即再找矿（不发呆）
    h._update_mining_ai()
    assert h.state == "MOVING_TO_ORE", '第 %d 轮卸货后应立即再出发' % (rnd + 1)
print('2. 两轮采集无缝衔接（卸货后立即再出发）OK')

# ---- 3. 手动指令打断后恢复采矿（发呆修复）----
h.pos = vec(1200, 1000)
h.target_pos = vec(1210, 1010)          # 模拟基类到达后残留的 target_pos
h.ai_mode = "MOVE"
h.state = "MANUAL"
for _ in range(3):
    h.update()                            # ai_mode=GUARD 复位 + IDLE 找矿
assert h.ai_mode == "GUARD" and h.state == "MOVING_TO_ORE", \
    '手动到位后应复位并恢复采矿, got %s/%s' % (h.ai_mode, h.state)
print('3. 手动指令打断后恢复自动采矿（发呆修复）OK')

print('ALL PASS')
