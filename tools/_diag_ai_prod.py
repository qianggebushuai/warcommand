# -*- coding: utf-8 -*-
"""AI 生产全链路仿真：真实建筑类+真实工程师+真实排队生产+真实资金流。

量化两个指标：
  1. 科技中心(research)建成时间 —— 验证"AI 不造高级建筑"
  2. 出兵速率(单位/分钟)与工厂/机场数量 —— 验证"工厂机场出兵慢"
"""
import os
import sys

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io
import contextlib
import pygame
from pygame.math import Vector2 as vec

pygame.init()
pygame.display.set_mode((100, 100))

import ai.ai_logic as AIL
from ai.ai_logic import AICommander
from units import Engineer, Harvester
from units.buildings import (BaseBuilding, PowerPlant, FactoryBuilding, Airfield,
                             MiningRig, RadarBuilding, ResearchCenter, Bunker,
                             AntiAirTurret, Barracks)


class FakeMap:
    width = 4000
    height = 4000
    lakes = []


class FakeUnit:
    def __init__(self, game, pos, team, u_type='rifleman'):
        self.game = game
        self.pos = vec(pos)
        self.team = team
        self.alive = True
        self.is_air = False
        self.hp = self.max_hp = 100
        self.radius = 15
        self.unit_type = u_type
        self.rect = pygame.Rect(int(pos.x) - 15, int(pos.y) - 15, 30, 30)
        self.move_orders = 0
        # AI 控兵路径需要的最小属性集
        self.ai_mode = "GUARD"
        self.target_pos = None
        self.target_entity = None

    def set_target(self, entity):
        self.target_entity = entity

    def move_to(self, p):
        self.move_orders += 1


class Game:
    def __init__(self):
        self.frame_count = 0
        self.all_units = []
        self.all_buildings = []
        self.projectiles = []
        self.particles = pygame.sprite.Group()
        self.floating_texts = pygame.sprite.Group()
        self.team_resources = {"team_0": 2000, "team_1": 5000}
        self.current_map = FakeMap()
        self.lakes = []
        self.is_online = False
        self.max_cmd_exp = 50000
        self.current_voltage = 0      # 电网负载（defenses.py 断电检查用）
        self.max_voltage = 99999
        self.prod_log = []          # (frame, u_type)
        self.show_alert = lambda *a, **k: None

    def spawn_unit(self, u_type, pos, team):
        # 矿车用真实类：AI 的矿车计数用 isinstance(Harvester)，FakeUnit 会
        # 永远数不到 → AI 无限补矿车（仿真伪影，真实游戏 spawn 出的是真矿车）
        if u_type == 'harvester':
            u = Harvester(self, vec(pos), team, None)
        else:
            u = FakeUnit(self, pos, team, u_type)
        self.all_units.append(u)
        self.prod_log.append((self.frame_count, u_type))
        return u


BUILD_CLS = {
    'power_plant': PowerPlant, 'factory': FactoryBuilding, 'airfield': Airfield,
    'mining': MiningRig, 'radar': RadarBuilding, 'research': ResearchCenter,
    'bunker': Bunker, 'aa_turret': AntiAirTurret, 'barracks': Barracks,
    'base': BaseBuilding,
}


def run(name, income, frames):
    g = Game()
    base = BaseBuilding(g, vec(2000, 2000), "team_1")
    g.all_buildings.append(base)
    cmd = AICommander(g, "team_1")

    built_log = []      # (frame, b_type) —— 每 30 帧快照差分
    prev_ids = {id(base)}
    prev_frame = [0]

    def snapshot():
        cur_ids = {id(b) for b in g.all_buildings}
        for b in g.all_buildings:
            if id(b) not in prev_ids:
                built_log.append((g.frame_count, getattr(b, 'b_type', '?')))
        prev_ids.clear(); prev_ids.update(cur_ids)
        prev_frame[0] = g.frame_count

    errs = []
    buf = io.StringIO()
    money_log = []
    harv_max = 0
    with contextlib.redirect_stdout(buf):
        for f in range(frames):
            g.frame_count += 1
            g.team_resources["team_1"] += income
            for u in list(g.all_units):
                if not getattr(u, 'alive', True):
                    continue
                if isinstance(u, Engineer):
                    try:
                        u.update()
                    except Exception:
                        if len(errs) < 3:
                            errs.append('ENG: ' + traceback_fmt())
                # FakeUnit 不动，节省 O(n^2)
            for b in list(g.all_buildings):
                if getattr(b, 'alive', True):
                    try:
                        b.update()
                    except Exception:
                        if len(errs) < 3:
                            errs.append('BLD: ' + traceback_fmt())
            try:
                cmd.update()
            except Exception:
                if len(errs) < 3:
                    errs.append('AI: ' + traceback_fmt())
            if g.frame_count % 30 == 0:
                snapshot()
                # 矿车并发峰值（存活+正在生产=常驻上限，验证"矿车不再刷屏"）
                # 真实 Harvester（矿场自动生成，无 unit_type 属性）与工厂排产的
                # FakeUnit（unit_type='harvester'）都要计入
                n_h = sum(1 for u in g.all_units
                          if u.team == "team_1" and getattr(u, 'alive', True)
                          and (isinstance(u, Harvester)
                               or getattr(u, 'unit_type', '') == 'harvester'))
                n_q = 0
                for b in g.all_buildings:
                    if b.team != "team_1" or not getattr(b, 'alive', True):
                        continue
                    cp = getattr(b, 'current_production', None)
                    if cp and cp.get('type') == 'harvester':
                        n_q += 1
                    n_q += sum(1 for t, _ in getattr(b, 'production_queue', [])
                               if t == 'harvester')
                harv_max = max(harv_max, n_h + n_q)
            if f % 600 == 0:
                money_log.append(int(g.team_resources["team_1"]))

    def ts(fr):
        return "%d:%02d" % (fr // 3600, fr % 3600 // 60)

    my_b = [b for b in g.all_buildings if b.team == "team_1" and b.alive]
    counts = {}
    for b in my_b:
        counts[getattr(b, 'b_type', '?')] = counts.get(getattr(b, 'b_type', '?'), 0) + 1
    fac = counts.get('factory', 0)
    air = counts.get('airfield', 0)
    n_units = len(g.prod_log)
    rate = n_units / (frames / 3600.0)
    res_t = next((ts(fr) for fr, t in built_log if t == 'research'), None)
    print("=== %s ===" % name)
    print("  建成: %s" % {k: v for k, v in sorted(counts.items())})
    print("  科技中心落地: %s  首工厂: %s  首机场: %s" % (
        res_t or "未建成",
        next((ts(fr) for fr, t in built_log if t == 'factory'), '-'),
        next((ts(fr) for fr, t in built_log if t == 'airfield'), '-')))
    print("  出兵: %d 个 (速率 %.1f/分钟)  末资金: %d  异常: %d" % (
        n_units, rate, g.team_resources["team_1"], len(errs)))
    # 兵种构成（验证"坦克/高级兵产出正常、矿车不刷屏"）
    comp = {}
    for _, t in g.prod_log:
        comp[t] = comp.get(t, 0) + 1
    comp_str = ", ".join("%s:%d" % (k, v) for k, v in
                         sorted(comp.items(), key=lambda kv: -kv[1]))
    print("  构成: %s" % comp_str)
    print("  矿车并发峰值(存活+排队): %d (目标 AI_HARVESTER_TARGET=4)" % harv_max)
    print("  资金曲线: %s" % money_log[:12])
    for b in my_b:
        if getattr(b, 'b_type', '') == 'prototype_gen':
            print("  原型机: loaded=%s weapon=%s ready=%s" % (
                getattr(b, 'loaded_weapon', None),
                type(getattr(b, 'weapon_obj', None)).__name__,
                getattr(b, 'is_ready', None)))
    for e in errs[:1]:
        print(e)
    return counts, rate, res_t


def traceback_fmt():
    import traceback
    return traceback.format_exc(limit=2)


if __name__ == '__main__':
    run("A 富裕(收入3/帧) 10分钟", income=3, frames=36000)
    run("B 中等(收入1.2/帧) 10分钟", income=1.2, frames=36000)
    run("C 贫困(收入0.5/帧) 10分钟", income=0.5, frames=36000)
