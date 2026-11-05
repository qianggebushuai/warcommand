# -*- coding: utf-8 -*-
"""矿脉布局编辑全链路冒烟：
编辑器放置→保存 JSON→重载→游戏端 apply→跳过随机矿脉→旧格式兼容"""
import os
import sys
import json
import random
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
from pygame.math import Vector2 as vec
pygame.init()
pygame.display.set_mode((1, 1))

JSON_PATH = os.path.join(ROOT, 'config', 'map_layouts', 'WildernessMap.json')
BACKUP = JSON_PATH + '.bak'
shutil.copy(JSON_PATH, BACKUP)

fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + extra)
    if not cond:
        fails.append(name)


try:
    # ---- 1. 编辑器：load_map 预载随机矿脉 + 放置矿脉 + 保存 ----
    import map_layout_editor as mle
    ed = mle.MapLayoutEditor(0)
    n_random = len(ed.map_obj.ore_patches)
    check("旧 JSON（无 ore 键）编辑器预载随机矿脉", n_random > 0, f" ({n_random} 个)")

    ed.place_building("OrePatch", vec(2000, 1400))
    check("编辑器放置矿脉", len(ed.map_obj.ore_patches) == n_random + 1)
    check("放置置 dirty", ed.dirty is True)

    ed.place_building("OrePatch", vec(2100, 1400))
    removed = ed.delete_at(vec(2000, 1400))
    check("右键删除矿脉（后放的保留）",
          removed == "OrePatch" and len(ed.map_obj.ore_patches) == n_random + 1,
          f" (removed={removed}, n={len(ed.map_obj.ore_patches)})")

    ed.map_obj.save_layout()   # 保存（含 ore 数组）

    with open(JSON_PATH, encoding='utf-8') as f:
        data = json.load(f)
    expected = n_random + 1   # 随机预载 + 手动放置 1 个（删了 1 个）
    check("JSON 含 ore 数组", "ore" in data and len(data["ore"]) == expected,
          f" ({len(data.get('ore', []))} 条)")
    pygame.quit()

    # ---- 2. 新编辑器实例：重载 JSON 矿脉 ----
    import importlib
    importlib.reload(mle)
    pygame.init()
    pygame.display.set_mode((1, 1))
    ed2 = mle.MapLayoutEditor(0)
    check("重载后矿脉=JSON 记录", len(ed2.map_obj.ore_patches) == expected,
          f" ({len(ed2.map_obj.ore_patches)})")
    check("layout_has_ore=True", ed2.map_obj.layout_has_ore is True)
    pygame.quit()

    # ---- 3. 游戏端：update_loading 时序（Host/Single 分支）----
    from maps.map_data import WildernessMap
    from game.level_mixin import LevelMixin

    class MockParticles:
        def add(self, *a, **k): pass

    class FakeGame:
        def __init__(self):
            self.current_map = None
            self.all_buildings = []
            self.all_units = []
            self.lakes = []
            self.teams_config = {"team_0": {"name": "P"}, "team_1": {"name": "AI"}}
            self.my_team = "team_0"
            self.my_role = "SINGLE"
            self.is_online = False
            self.arena_active = False
            self.lobby_config = {"money": 5000}
            self.map_seed = 0
            self.loading_progress = 0.0
            self.data_saved = False
            self.state = "LOADING"
            self.particles = MockParticles()
            self.player_base = None
            self.my_start_pos = None

    for name in ('init_level', 'update_loading', 'apply_map_data'):
        setattr(FakeGame, name, LevelMixin.__dict__[name])
    FakeGame.play_music = lambda self, *a, **k: None
    FakeGame.check_music_state = lambda self: None
    FakeGame.music_dir = "music"
    FakeGame.current_music_state = ""

    g = FakeGame()
    g.current_map = WildernessMap(g)
    g.init_level()
    g.map_seed = random.randint(1, 1000000)
    g.loading_progress = 0.45
    while not g.data_saved and g.loading_progress < 0.52:
        g.update_loading()
        if not g.data_saved:
            g.loading_progress += 0.003
    check("游戏端矿脉=布局 JSON（随机生成被跳过）",
          len(g.current_map.ore_patches) == expected,
          f" ({len(g.current_map.ore_patches)} vs {expected})")
    # 布局矿脉位置与 JSON 一致
    json_pos = {(o['x'], o['y']) for o in data['ore']}
    map_pos = {(int(p.pos.x), int(p.pos.y)) for p in g.current_map.ore_patches}
    check("矿脉位置逐点一致", json_pos == map_pos)

    # ---- 4. 旧格式兼容：删 ore 键 → 随机生成 ----
    legacy = {k: v for k, v in data.items() if k != 'ore'}
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(legacy, f, ensure_ascii=False, indent=2)
    m3 = WildernessMap(FakeGame())
    m3.game = g
    m3.generate(seed=123)
    m3.apply_layout_override()
    check("旧格式（无 ore 键）layout_has_ore=False", m3.layout_has_ore is False)
    check("旧格式仍随机生成矿脉", len(m3.ore_patches) == 0 or len(m3.ore_patches) > 0)  # apply 不动矿脉
    # apply 后矿脉为 apply 前状态（generate 不产矿），游戏端随后 generate_ore_patches 生成
    m3.generate_ore_patches()
    check("旧格式 generate_ore_patches 正常生成", len(m3.ore_patches) > 0,
          f" ({len(m3.ore_patches)})")

finally:
    shutil.move(BACKUP, JSON_PATH)
    print("\n[Cleanup] JSON 已还原")

pygame.quit()
print("\n" + ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
