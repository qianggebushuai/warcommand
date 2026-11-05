# -*- coding: utf-8 -*-
"""建筑 PNG 化全链路验证：实例化所有建筑 -> init 自动导出 PNG -> 二次实例化走加载路径"""
import os, sys
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, r'g:\网游克星\真正的网游克星\warcommand')
import pygame
pygame.init()
pygame.display.set_mode((1, 1))

from core.base_classes import (OilDerrick, Skyscraper, Shipyard, TechCenter, EMPGenerator,
                               AncientTemple, CivilianHouse, CommStation, Bridge,
                               BroadcastDish, ConcreteRubble)
from units.buildings import (BaseBuilding, FactoryBuilding, Barracks, RadarBuilding,
                             PowerPlant, MiningRig, Airfield, ResearchCenter, Bastion,
                             Lighthouse, ShroudGen)
from units.defenses import AntiAirTurret, CoastalGun


class P:
    def add(self, *a, **k): pass
    def add_explosion(self, *a, **k): pass


class G:
    current_map = None
    all_units = []
    all_buildings = []
    particles = P()
    my_faction = 'CHINA'
    enemy_faction = 'USA'
    my_team = 'team_0'
    team_resources = {}
    net_events = []
    is_online = False
    teams_config = {'team_0': {'faction': 'CHINA'}, 'team_1': {'faction': 'USA'}}
    show_alert = lambda self, *a, **k: None
    screen_shake = 0


game = G()
vec = pygame.math.Vector2

cases = [
    ('OilDerrick', lambda: OilDerrick(game, vec(1000, 1000))),
    ('Skyscraper', lambda: Skyscraper(game, vec(1000, 1000))),
    ('Shipyard', lambda: Shipyard(game, vec(1000, 1000), 'team_0')),
    ('TechCenter', lambda: TechCenter(game, vec(1000, 1000), 'team_0')),
    ('EMPGenerator', lambda: EMPGenerator(game, vec(1000, 1000))),
    ('AncientTemple', lambda: AncientTemple(game, vec(1000, 1000))),
    ('CivilianHouse', lambda: CivilianHouse(game, vec(1000, 1000))),
    ('CommStation', lambda: CommStation(game, vec(1000, 1000))),
    ('BridgeH', lambda: Bridge(game, vec(1000, 1000), 'horizontal')),
    ('BridgeV', lambda: Bridge(game, vec(1000, 1000), 'vertical')),
    ('BroadcastDish', lambda: BroadcastDish(game, vec(1000, 1000))),
    ('ConcreteRubble', lambda: ConcreteRubble(game, vec(1000, 1000))),
    ('BaseBuilding', lambda: BaseBuilding(game, vec(1000, 1000), 'team_0')),
    ('FactoryBuilding', lambda: FactoryBuilding(game, vec(1000, 1000), 'team_0')),
    ('Barracks', lambda: Barracks(game, vec(1000, 1000), 'team_0')),
    ('RadarBuilding', lambda: RadarBuilding(game, vec(1000, 1000), 'team_0')),
    ('PowerPlant', lambda: PowerPlant(game, vec(1000, 1000), 'team_0')),
    ('MiningRig', lambda: MiningRig(game, vec(1000, 1000), 'team_0')),
    ('Airfield', lambda: Airfield(game, vec(1000, 1000), 'team_0')),
    ('ResearchCenter', lambda: ResearchCenter(game, vec(1000, 1000), 'team_0')),
    ('Bastion', lambda: Bastion(game, vec(1000, 1000), 'team_0')),
    ('Lighthouse', lambda: Lighthouse(game, vec(1000, 1000))),
    ('AntiAirTurret', lambda: AntiAirTurret(game, vec(1000, 1000), 'team_0')),
    ('CoastalGun', lambda: CoastalGun(game, vec(1000, 1000), 'team_0')),
]

surf = pygame.Surface((800, 600))
fails = []
for name, ctor in cases:
    try:
        b = ctor()
        # 动态部分：draw 两个 zoom 档位（惰性生成 image 的类在此触发；保证建筑在视口内）
        b.draw(surf, vec(1000 - 400, 1000 - 300), 1.0)
        b.draw(surf, vec(1000 - 400, 1000 - 300), 0.5)
        img = getattr(b, 'image', None)
        if img is None or img.get_width() < 10:
            fails.append(name + ': no image after draw')
            continue
        print('%-16s OK  image=%dx%d  draw@zoom1/0.5 ok' % (name, img.get_width(), img.get_height()))
    except Exception as e:
        import traceback
        fails.append(name + ': ' + repr(e))
        traceback.print_exc()

print()
print('=== FAILS ===' if fails else '=== ALL PASS ===')
for f in fails:
    print(' ', f)
