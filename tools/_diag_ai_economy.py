# -*- coding: utf-8 -*-
"""AI 经济诊断：模拟 AICommander.update() 长时间运行，观察建造是否停滞及原因。"""
import os
import sys

os.environ['SDL_VIDEODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from pygame.math import Vector2 as vec

pygame.init()
pygame.display.set_mode((1600, 900))

import ai.ai_logic as AIL
from ai.ai_logic import AICommander
from units import Engineer

BUILT = []          # (frame, type)
CUR_TYPE = ['factory']   # Engineer 建成的假建筑统一按 factory 计（模拟真实产能开销）


class FakeBuilding:
    def __init__(self, game, pos, team):
        self.game = game
        self.pos = vec(pos)
        self.team = team
        self.alive = True
        self.hp = self.max_hp = 5000
        self.radius = 60
        self.rect = pygame.Rect(int(pos.x) - 60, int(pos.y) - 60, 120, 120)
        self.b_type = CUR_TYPE[0]
        self.is_upgraded = False
        self.upgrades_available = []
        BUILT.append((game.frame_count, CUR_TYPE[0]))

    @staticmethod
    def get_cost():
        return 800

    def queue_unit(self, u_type, t):
        return True


for name in ("RadarBuilding", "MiningRig", "Airfield", "ResearchCenter",
             "MissileDefenseSystem", "AntiAirTurret", "PowerPlant",
             "LaserTurret", "Bunker", "Barracks", "FactoryBuilding"):
    setattr(AIL, name, FakeBuilding)


class FakeMap:
    width = 4000
    height = 4000
    lakes = []


class Game:
    def __init__(self):
        self.frame_count = 0
        self.all_units = []
        self.all_buildings = []
        self.projectiles = []
        self.particles = pygame.sprite.Group()
        self.floating_texts = pygame.sprite.Group()
        self.team_resources = {"team_0": 2000, "team_1": 8000}
        self.current_map = FakeMap()
        self.lakes = []
        self.is_online = False
        self.max_cmd_exp = 50000


class FakeBase(FakeBuilding):
    def __init__(self, game, pos, team):
        CUR_TYPE[0] = 'base'
        super().__init__(game, pos, team)
        CUR_TYPE[0] = 'factory'


class FakeUnit:
    def __init__(self, game, pos, team):
        self.game = game
        self.pos = vec(pos)
        self.team = team
        self.alive = True
        self.is_air = False
        self.hp = self.max_hp = 100
        self.unit_type = 'rifleman'
        game.all_units.append(self)


def run_scenario(name, income, enemy_near_base, frames=9000):
    global BUILT
    BUILT = []
    g = Game()
    base = FakeBase(g, vec(2000, 2000), "team_1")
    g.all_buildings.append(base)
    cmd = AICommander(g, "team_1")
    enemies = [FakeUnit(g, vec(2000 + 400, 2000 + i * 30), "team_0")
               for i in range(enemy_near_base)] if enemy_near_base else []

    errs = []
    import io, contextlib
    buf = io.StringIO()
    money_log = []
    with contextlib.redirect_stdout(buf):        # 吞掉 [AI team] Building 打印
        for f in range(frames):
            g.frame_count += 1
            g.team_resources["team_1"] = min(50000, g.team_resources["team_1"] + income)
            for u in list(g.all_units):          # 模拟主循环单位更新（工程师走位+建造）
                if not getattr(u, 'alive', True):
                    continue                     # 死单位跳过（否则死工程师每帧重复建造）
                if hasattr(u, 'update'):
                    try:
                        u.update()
                    except Exception:
                        import traceback
                        if len(errs) < 3:
                            errs.append(traceback.format_exc())
            try:
                cmd.update()
            except Exception:
                import traceback
                if len(errs) < 3:
                    errs.append(traceback.format_exc())
            if f % 300 == 0:
                money_log.append(int(g.team_resources["team_1"]))
    my_b = [b for b in g.all_buildings if b.team == "team_1" and b.alive]
    eng_alive = [u for u in g.all_units if isinstance(u, Engineer) and u.alive]
    print("=== %s ===" % name)
    print("  建成建筑数: %d  末段资金: %s  状态: %s" % (len(my_b), money_log[-3:], cmd.state))
    print("  建造时间线(前10): %s" % BUILT[:10])
    print("  存活工程师: %d  异常: %d" % (len(eng_alive), len(errs)))
    for e in errs:
        print(e)
    return len(my_b)


n1 = run_scenario("A 和平(收入3/帧, 无敌人)", income=3, enemy_near_base=0)
n2 = run_scenario("B 被袭(收入3/帧, 基地旁3敌)", income=3, enemy_near_base=3)
n3 = run_scenario("C 和平(收入1/帧 贫困)", income=1, enemy_near_base=0)
print("\n结论: 和平建造%s / 被袭建造%s / 贫困建造%s" %
      ("正常" if n1 > 8 else "停滞", "正常" if n2 > 5 else "停滞", "正常" if n3 > 5 else "停滞"))
