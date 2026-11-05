# -*- coding: utf-8 -*-
"""定位 25 个中立建筑来源：在 update_loading 各步骤间插桩统计"""
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import random
import pygame
from maps.map_data import WildernessMap

pygame.init()
pygame.display.set_mode((1, 1))


class MockParticles:
    def add(self, *a, **k): pass


class FakeGame:
    def __init__(self):
        self.current_map = None
        self.all_buildings = []
        self.all_units = []
        self.lakes = []
        self.teams_config = {"team_0": {"name": "Player"}, "team_1": {"name": "AI"}}
        self.my_team = "team_0"
        self.my_role = "SINGLE"
        self.is_online = False
        self.arena_active = False
        self.lobby_config = {"money": 5000, "rate": 1.0}
        self.map_seed = 0
        self.loading_progress = 0.0
        self.data_saved = False
        self.state = "LOADING"
        self.particles = MockParticles()
        self.player_base = None
        self.my_start_pos = None

    def dump(self, tag):
        c = Counter(b.__class__.__name__ for b in self.all_buildings)
        print(f"[{tag}] all_buildings={dict(c)} map.neutral={len(self.current_map.neutral_buildings)} "
              f"hasattr_map_data={hasattr(self, 'map_data')}")


from game.level_mixin import LevelMixin
for name in ('init_level', 'apply_map_data'):
    setattr(FakeGame, name, LevelMixin.__dict__[name])

g = FakeGame()
g.current_map = WildernessMap(g)
g.init_level()
g.dump("init_level 后")

# 手动逐条复刻 update_loading 的 Host/Single 分支
g.map_seed = random.randint(0, 1000000)
g.current_map.generate(seed=g.map_seed)
g.dump("generate 后")
g.apply_map_data()
g.dump("apply_map_data 后")
g.current_map.apply_layout_override()
g.dump("apply_layout 后")
g.current_map.generate_ore_patches()
g.dump("ore_patches 后")

pygame.quit()
