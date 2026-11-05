# -*- coding: utf-8 -*-
"""特殊单位增强冒烟：回血 / 死亡定时刷新 / 战列舰↔通讯站重绑 / 布局 JSON round-trip"""
import os
import sys
import json
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
from pygame.math import Vector2 as vec
pygame.init()
pygame.display.set_mode((1, 1))

from units import ArmoredTrain, Battleship
from units.base import TRAIN_TRACK_X
from core.base_classes import CommStation
from core.settings import (SPECIAL_REGEN_INTERVAL, SPECIAL_RESPAWN_FRAMES,
                           TRAIN_REGEN, BATTLESHIP_REGEN)
from game.special_units_mixin import SpecialUnitManager

fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + extra)
    if not cond:
        fails.append(name)


class MockParticles(pygame.sprite.Group):
    def add(self, *a, **k): pass


class FakeGame:
    """最小 game 替身：满足单位构造/更新与管理器所需的属性访问"""
    def __init__(self):
        self.current_map = None
        self.all_units = []
        self.all_buildings = []
        self.projectiles = []
        self.particles = MockParticles()
        self.frame_count = 0
        self.is_online = False
        self.my_role = "HOST"
        self.net_events = []
        self.team_tech_levels = {}
        # 全图水域（战列舰 is_naval 移动判定需要）
        self.lakes = [{'rect': pygame.Rect(0, 0, 9999, 9999), 'parts': [], 'type': 'water'}]


class SpecMap:
    """携带 special_specs 的极简 current_map 替身"""
    def __init__(self, specs):
        self.special_specs = specs
        self.initial_units = []


# =====================================================================
# 1. 回血：战列舰 / 列车车头 / 车厢，且封顶 max_hp
# =====================================================================
g = FakeGame()
bs = Battleship(g, vec(1000, 2800))
g.all_units.append(bs)
bs.hp = 1000
for _ in range(SPECIAL_REGEN_INTERVAL * 3):
    bs.update()
check("战列舰回血 3 周期", bs.hp == 1000 + BATTLESHIP_REGEN * 3, f" (hp={bs.hp})")
check("战列舰 hp 保持 int", isinstance(bs.hp, int))
bs.hp = bs.max_hp - 3
for _ in range(SPECIAL_REGEN_INTERVAL * 3):
    bs.update()
check("战列舰回血封顶 max_hp", bs.hp == bs.max_hp, f" (hp={bs.hp})")

tr = ArmoredTrain(g, vec(TRAIN_TRACK_X, 800))
g.all_units.append(tr)
tr.hp = 100
for _ in range(SPECIAL_REGEN_INTERVAL * 2):
    tr.update()
check("列车车头回血 2 周期", tr.hp == 100 + TRAIN_REGEN * 2, f" (hp={tr.hp})")
car = tr.carriages[0]
car.hp = 50
for _ in range(SPECIAL_REGEN_INTERVAL * 2):
    car.update()
check("车厢回血 2 周期", car.hp == 50 + TRAIN_REGEN * 2, f" (hp={car.hp})")

# =====================================================================
# 2. 战列舰死亡 → respawn_frames 后在 spawn 重生 → 绑定通讯站 → 向 target 移动
# =====================================================================
g2 = FakeGame()
station = CommStation(g2, vec(2000, 1000))
g2.all_buildings.append(station)
bs2 = Battleship(g2, vec(2400, 2800))
g2.all_units.append(bs2)
spec = {"type": "Battleship", "spawn": vec(2400, 2800), "target": vec(2400, 1200),
        "respawn_frames": 30}
g2.current_map = SpecMap([spec])
mgr = SpecialUnitManager(g2)
mgr.register_from_map()
check("注册表绑定到现有战列舰", mgr.specs and mgr.specs[0]["unit"] is bs2)
check("初始战列舰绑定通讯站(station→bs)",
      station.linked_battleship is bs2 and getattr(bs2, 'linked_station', None) is station)

bs2.die()
g2.frame_count = 100
mgr.update()
check("战列舰死亡清空通讯站反向引用", station.linked_battleship is None)
check("死亡后未到刷新时间不重生",
      len([u for u in g2.all_units if isinstance(u, Battleship) and u.alive]) == 0)
for f in range(spec["respawn_frames"] - 1):
    g2.frame_count = 101 + f
    mgr.update()
check("respawn_frames-1 帧仍未重生",
      len([u for u in g2.all_units if isinstance(u, Battleship) and u.alive]) == 0)
g2.frame_count = 101 + spec["respawn_frames"] - 1
mgr.update()
new_bs = [u for u in g2.all_units if isinstance(u, Battleship) and u.alive]
check("到时在 spawn 点重生战列舰", len(new_bs) == 1)
if new_bs:
    nb = new_bs[0]
    check("重生位置=spawn 点", nb.pos.distance_to(spec["spawn"]) < 1.0, f" (pos={nb.pos})")
    check("重生战列舰重新绑定通讯站",
          station.linked_battleship is nb and getattr(nb, 'linked_station', None) is station)
    check("重生后收到向 target 移动的指令", nb.target_pos is not None
          and nb.target_pos.distance_to(spec["target"]) < 1.0)
    # 移动验证：船头对准目标方向（target 在正上方 → angle 90），推进若干帧观察位移
    nb.angle = 90
    d0 = nb.pos.distance_to(spec["target"])
    for _ in range(20):
        g2.frame_count += 1
        nb.update()
    check("重生战列舰向 target 移动", nb.pos.distance_to(spec["target"]) < d0,
          f" (dist {d0:.0f} -> {nb.pos.distance_to(spec['target']):.0f})")

# =====================================================================
# 3. 列车死亡 → 重生 → 车厢数正确 + 收到行进指令
# =====================================================================
g3 = FakeGame()
tr3 = ArmoredTrain(g3, vec(TRAIN_TRACK_X, 800))
g3.all_units.append(tr3)
tspec = {"type": "Train", "spawn": vec(TRAIN_TRACK_X, 800), "target": vec(TRAIN_TRACK_X, 2000),
         "respawn_frames": 20}
g3.current_map = SpecMap([tspec])
mgr3 = SpecialUnitManager(g3)
mgr3.register_from_map()
check("注册表绑定到现有列车", mgr3.specs and mgr3.specs[0]["unit"] is tr3)
tr3.die()
check("列车死亡车厢全灭", all(not c.alive for c in tr3.carriages))
g3.frame_count = 50
mgr3.update()
g3.frame_count = 50 + tspec["respawn_frames"]
mgr3.update()
new_tr = mgr3.specs[0]["unit"]
check("列车到时重生", isinstance(new_tr, ArmoredTrain) and new_tr.alive)
check("重生列车车厢数=3", new_tr is not None and len(new_tr.carriages) == 3,
      f" ({len(new_tr.carriages) if new_tr else 0})")
check("重生列车收到铁轨行进指令",
      new_tr is not None and new_tr.target_pos is not None
      and abs(new_tr.target_pos.y - tspec["target"][1] if isinstance(tspec["target"], (list, tuple))
              else new_tr.target_pos.y - tspec["target"].y) < 1.0)

# =====================================================================
# 4. 布局 JSON special_units 分区 round-trip（编辑器保存 → 地图应用读取）
# =====================================================================
JSON_PATH = os.path.join(ROOT, 'config', 'map_layouts', 'StormCoastMap.json')
BACKUP = JSON_PATH + '.bak'
had_json = os.path.exists(JSON_PATH)
if had_json:
    shutil.copy(JSON_PATH, BACKUP)
try:
    import map_layout_editor as mle
    ed = mle.MapLayoutEditor(1)   # StormCoastMap
    # JSON 无 special_units 分区（或无 JSON）→ 从硬编码 initial_units 预载默认标记
    pre = ed.map_obj.special_specs
    check("编辑器预载硬编码特殊单位标记", pre is not None and len(pre) >= 1
          and pre[0]["type"] == "Battleship", f" ({len(pre) if pre else 0} 条)")
    n0 = len(pre)
    # 两步放置一艘新战列舰：刷新点 → 目标点
    ed.selected_type = "special:Battleship"
    ed.place_special(vec(3000, 3000))
    ed.place_special(vec(3000, 2600))
    check("编辑器两步放置特殊单位", len(ed.map_obj.special_specs) == n0 + 1 and ed.dirty)
    # 右键删除命中目标点
    removed = ed.delete_at(vec(3000, 2600))
    check("右键删除特殊单位标记", removed == "特殊单位:Battleship"
          and len(ed.map_obj.special_specs) == n0)
    # 再放一个带 target 的战列舰 spec 后保存
    ed.place_special(vec(3000, 3000))
    ed.place_special(vec(3000, 2600))
    ed.map_obj.save_layout()
    pygame.quit()
    with open(JSON_PATH, encoding='utf-8') as f:
        data = json.load(f)
    su = data.get("special_units", [])
    check("JSON 含 special_units 分区", len(su) == n0 + 1, f" ({len(su)} 条)")
    check("JSON 条目含 type/spawn（target 可选）",
          all(("type" in e and "spawn" in e) for e in su)
          and any("target" in e for e in su))

    # 游戏端：新地图实例应用 JSON → special_specs/initial_units 以 JSON 为准
    pygame.init()
    pygame.display.set_mode((1, 1))
    from maps.map_data import StormCoastMap
    m2 = StormCoastMap(FakeGame())
    m2.generate(seed=7)
    check("无 JSON 应用前 initial_units=硬编码", len(m2.initial_units) == 1
          and m2.initial_units[0][0] == "Battleship")
    m2.apply_layout_override()
    check("地图应用读取 special_units 分区", m2.special_specs is not None
          and len(m2.special_specs) == n0 + 1)
    check("initial_units 被 JSON spec 替换",
          len(m2.initial_units) == n0 + 1
          and all(t == "Battleship" for t, _ in m2.initial_units)
          and vec(m2.initial_units[-1][1]).distance_to(vec(3000, 3000)) < 1.0)
except Exception as ex:
    import traceback
    traceback.print_exc()
    check("编辑器/JSON round-trip 无异常", False, f" ({ex})")
finally:
    if had_json:
        shutil.move(BACKUP, JSON_PATH)
    elif os.path.exists(JSON_PATH):
        os.remove(JSON_PATH)
    print("[Cleanup] StormCoastMap.json 已还原")

# =====================================================================
# 5. StormCoastMap 实际加载路径：spec 注册成功 + initial 战列舰有绑定
# =====================================================================
from game.level_mixin import LevelMixin


class LoadGame(FakeGame):
    """带 LevelMixin 的加载用替身（仿 _smoke_ore_layout）"""
    def __init__(self):
        super().__init__()
        self.current_map = None
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
        self.player_base = None
        self.my_start_pos = None
        self.bases = {}


for name in ('init_level', 'update_loading', 'apply_map_data', '_register_special_units'):
    setattr(LoadGame, name, LevelMixin.__dict__[name])
from game.world_mixin import WorldMixin
LoadGame.update_game_world = WorldMixin.__dict__['update_game_world']
LoadGame.play_music = lambda self, *a, **k: None
LoadGame.check_music_state = lambda self: None
LoadGame.music_dir = "music"
LoadGame.current_music_state = ""
# update_game_world 所需状态
LoadGame.game_over = False
LoadGame.winner = None
LoadGame.state = "PLAYING"
LoadGame.bombardment_mode = False
LoadGame.active_alert = None
LoadGame.floating_texts = pygame.sprite.Group()

g4 = LoadGame()
g4.current_map = StormCoastMap(g4)
g4.current_map.generate(seed=7)   # StormCoastMap 在 generate 中才写入 initial_units（真实流程时序）
g4.init_level()
check("init_level 后特殊单位注册表非空", len(g4.special_units.specs) >= 1
      and g4.special_units.specs[0]["type"] == "Battleship")
init_bs = g4.special_units.specs[0]["unit"]
check("initial 战列舰挂 spec 引用", init_bs is not None
      and getattr(init_bs, 'special_spec', None) is g4.special_units.specs[0])
st4 = [b for b in g4.all_buildings
       if getattr(b, 'b_type', '') == 'comm_station']
check("initial 战列舰绑定通讯站",
      st4 and getattr(init_bs, 'linked_station', None) in st4
      and st4[0].linked_battleship is init_bs)

# update_loading 全路径（Host/Single：generate → apply_layout_override → apply_map_data）
# 布局 JSON 是用户可用编辑器改写的数据文件（用户可放任意数量标记）→ 测试期间换成
# 受控内容（恰好 1 艘战列舰+目标点），结束还原，保证测试不依赖用户编辑器数据
import json as _json
_layout_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", "map_layouts", "StormCoastMap.json")
with open(_layout_path, encoding="utf-8") as _f:
    _orig_layout_text = _f.read()
_layout_data = _json.loads(_orig_layout_text)
_layout_data["special_units"] = [{"type": "Battleship", "spawn": [2400, 2800],
                                  "target": [2200, 2600]}]
with open(_layout_path, "w", encoding="utf-8") as _f:
    _json.dump(_layout_data, _f, ensure_ascii=False, indent=2)

g4.map_seed = 1234
g4.loading_progress = 0.45
try:
    while not g4.data_saved and g4.loading_progress < 0.52:
        g4.update_loading()
        if not g4.data_saved:
            g4.loading_progress += 0.003
    if not g4.data_saved:
        g4.loading_progress += 0.003
    bs_alive = [u for u in g4.all_units if isinstance(u, Battleship) and u.alive]
    check("update_loading 后战列舰存在且注册表同步", len(bs_alive) == 1
          and g4.special_units.specs[0]["unit"] is bs_alive[0])
    st_alive = [b for b in g4.all_buildings
                if getattr(b, 'b_type', '') == 'comm_station' and b.alive]
    check("apply_map_data 重建后绑定仍有效",
          st_alive and getattr(bs_alive[0], 'linked_station', None) in st_alive
          and st_alive[0].linked_battleship is bs_alive[0])

    # 主更新链挂点：update_game_world 内驱动管理器（死亡→计时→重生）
    # 前 120 帧是开局保护早退分支，不跑管理器 → 帧数需 120 + respawn_frames + 余量
    bs_alive[0].die()
    for _ in range(120 + SPECIAL_RESPAWN_FRAMES + 50):
        g4.frame_count += 1
        g4.update_game_world()
    bs2_alive = [u for u in g4.all_units if isinstance(u, Battleship) and u.alive]
    check("update_game_world 驱动死亡刷新重生战列舰", len(bs2_alive) == 1,
          f" ({len(bs2_alive)})")
finally:
    # 还原用户布局数据（测试期间临时换过受控内容）
    with open(_layout_path, "w", encoding="utf-8") as _f:
        _f.write(_orig_layout_text)

pygame.quit()
print("\n" + ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
