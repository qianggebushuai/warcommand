# -*- coding: utf-8 -*-
"""AI 建造选址诊断：在真实地图上反复调用 execute_build，统计工程师下单成功率。

定位"AI 不出工程师建造建筑"：
  1. 各地图选址 45 次尝试的成功率（岛屿/湖泊判定是否误杀全部候选点）
  2. game.lakes 与 current_map.lakes 是否一致（AI 用 game.lakes，玩家用 current_map）
  3. dict 岛屿（地形编辑器 land 多边形）在 AI 的 Rect 过滤下是否全部丢失
"""
import os
import sys

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()
pygame.display.set_mode((100, 100))

from pygame.math import Vector2 as vec
import ai.ai_logic as ai_mod
from ai.ai_logic import AICommander
from units.buildings import BaseBuilding


class FakeEng:
    last = None
    def __init__(self, game, pos, team, build_pos):
        self.build_pos = vec(build_pos)
        self.team = team
        self.target_type = None
        self.alive = True
        FakeEng.last = self


ai_mod.Engineer = FakeEng


def try_build_on_map(map_cls, n_trials=60):
    """在真实地图上模拟 AI 基地，统计 execute_build 的下单成功率与失败原因。"""
    class G:
        frame_count = 0
        is_online = False
        my_team = "team_0"
        all_units = []
        all_buildings = []
        team_resources = {"team_1": 20000}
        show_alert = lambda self, *a, **k: None

    g = G()
    m = map_cls(g)
    try:
        m.generate(visual_only=True)
    except TypeError:
        m.generate()
    # 应用布局 JSON（出生点/地形多边形）——真实游戏路径
    m.apply_layout_override()
    if getattr(m, 'terrain_polys', []):
        m.apply_terrain_polys(g)
    g.current_map = m
    g.lakes = getattr(m, 'lakes', [])

    # 玩家/基地位置取 bases_config[1]（AI 通常拿第二个出生点）
    spawn = vec(m.bases_config[1]) if len(getattr(m, 'bases_config', [])) > 1 \
        else vec(m.width / 2, m.height / 2)
    base = BaseBuilding(g, spawn, "team_1")
    g.all_buildings.append(base)

    ai = AICommander(g, team="team_1")
    ai.my_base_pos = spawn

    ok = 0
    fails = {"bounds": 0, "water": 0, "blocked": 0, "island_dict": 0}
    for _ in range(n_trials):
        g.all_units = []          # 清掉上一次的假工程师
        g.team_resources["team_1"] = 20000
        FakeEng.last = None
        ai.build_timer = 30
        ai.ai_economy_management()
        if FakeEng.last is not None:
            ok += 1
    return ok, n_trials, m


maps_cls = None
from maps.map_data import (WildernessMap, StormCoastMap, FrozenArchipelagoMap,
                           DragonValleyMap, CrossfireMap, BroadcastCenterMap,
                           VerdunMap, PARISMAP, BERINGMAP)
maps_cls = [WildernessMap, StormCoastMap, FrozenArchipelagoMap, DragonValleyMap,
            CrossfireMap, BroadcastCenterMap, VerdunMap, PARISMAP, BERINGMAP]

print("地图                    下单/尝试  岛屿属性  islands类型        lakes数")
for mc in maps_cls:
    try:
        ok, n, m = try_build_on_map(mc)
        isles = getattr(m, 'islands', None)
        if isles is None:
            kind = "无属性"
        elif not isles:
            kind = "空列表"
        else:
            n_rect = sum(1 for i in isles if isinstance(i, pygame.Rect))
            kind = "%d.Rect+%d.dict" % (n_rect, len(isles) - n_rect)
        nlakes = len(getattr(m, 'lakes', []) or [])
        print("%-22s %2d/%-2d      %-6s    %-16s   %d" %
              (getattr(mc, 'name_static', mc.__name__), ok, n,
               "有" if isles is not None else "无", kind, nlakes))
    except Exception as e:
        import traceback
        print("%-22s 异常: %s" % (getattr(mc, 'name_static', mc.__name__), e))
        traceback.print_exc()
