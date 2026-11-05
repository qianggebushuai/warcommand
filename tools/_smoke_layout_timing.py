# -*- coding: utf-8 -*-
"""无头实测单机（SkirmishUI）布局应用时序：
reset_game 等价序列 → init_level → update_loading 窗口，统计各层建筑数量与位置"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import random
import pygame
from pygame.math import Vector2 as vec
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

    # 复刻 SkirmishUI.start_game → reset_game 的关键序列
    def reset_like(self):
        self.all_units = []
        self.all_buildings = []
        self.bases = {}
        self.player_base = None
        self.current_map = WildernessMap(self)      # 不 generate（与 core_mixin:484 一致）
        self.init_level()                            # core_mixin:491

    def run_loading_window(self):
        """推 update_loading 到 0.49-0.51 窗口完成（不进 PLAYING）"""
        self.loading_progress = 0.0
        self.data_saved = False
        for _ in range(400):
            self.update_loading()
            if self.data_saved:
                break
            self.loading_progress += 0.003 if self.loading_progress < 0.4 else 0.003
            # update_loading 自带 +0.003，这里防止不进窗口（幂等）

    def stats(self, tag):
        m = self.current_map
        neutral_in_all = [b for b in self.all_buildings
                          if getattr(b, 'b_type', '') not in ('base',) and b.__class__.__name__ != 'BaseBuilding']
        bases_in_all = [b for b in self.all_buildings if b.__class__.__name__ == 'BaseBuilding']
        print(f"--- {tag} ---")
        print(f"  all_buildings: total={len(self.all_buildings)}, bases={len(bases_in_all)}, "
              f"neutral={len(neutral_in_all)}")
        for b in bases_in_all:
            print(f"    base {b.team}: ({int(b.pos.x)}, {int(b.pos.y)})")
        print(f"  map.neutral_buildings={len(m.neutral_buildings)}, "
              f"map.bases_config={[f'({int(p.x)},{int(p.y)})' for p in m.bases_config]}")


from game.level_mixin import LevelMixin
for name in ('init_level', 'update_loading', 'apply_map_data', 'perform_rebuild_base',
             'draw_loading', 'draw_loading_middle'):
    if hasattr(LevelMixin, name):
        setattr(FakeGame, name, LevelMixin.__dict__[name])

# ---- mock update_loading 依赖 ----
FakeGame.play_music = lambda self, *a, **k: None
FakeGame.check_music_state = lambda self: None
FakeGame.music_dir = "music"
FakeGame.current_music_state = ""

g = FakeGame()
print("== 阶段1：reset_game 等价序列（map 未 generate 即 init_level）==")
g.reset_like()
g.stats("init_level 后")

print("\n== 阶段2：update_loading 推进到 0.49-0.51 窗口 ==")
g.map_seed = random.randint(0, 1000000)   # 单机随机种子（update_loading 内部逻辑同款）
g.loading_progress = 0.45
g.data_saved = False
while not g.data_saved and g.loading_progress < 0.52:
    g.update_loading()
    if not g.data_saved:
        g.loading_progress += 0.003
g.stats("loading 窗口完成后")

# ---- 判定 ----
m = g.current_map
neutral_in_all = [b for b in g.all_buildings if b.__class__.__name__ != 'BaseBuilding']
json_expect = 18   # 当前 WildernessMap.json 的 neutral 数
print("\n== 判定 ==")
print(f"map 层 JSON 应用: {'PASS' if len(m.neutral_buildings) == json_expect else 'FAIL'} "
      f"(map.neutral={len(m.neutral_buildings)}, json={json_expect})")
print(f"游戏层 all_buildings 中立建筑: {'PASS' if len(neutral_in_all) == json_expect else 'FAIL'} "
      f"(all={len(neutral_in_all)})")
json_bases = [(999, 888), (4400, 1600), (2400, 400), (2400, 2800)]
base_ok = any(abs(b.pos.x - 999) < 2 and abs(b.pos.y - 888) < 2 for b in g.all_buildings
              if b.__class__.__name__ == 'BaseBuilding')
print(f"游戏层出生点 JSON(P1=999,888): {'PASS' if base_ok else 'FAIL'}")

pygame.quit()
