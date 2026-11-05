# -*- coding: utf-8 -*-
"""建筑立绘审计：把所有建筑类的当前立绘（PNG 或现场渲染）拼成对比图，供人眼审计视角。"""
import os
import sys
import glob
import traceback
import tempfile

os.environ['SDL_VIDEODRIVER'] = 'dummy'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame
from pygame.math import Vector2 as vec

pygame.init()
pygame.display.set_mode((1600, 900))

import units
from core import base_classes as bc
from core.settings import TEAM_COLORS

OUT = os.path.join(tempfile.gettempdir(), 'wc_audit')
os.makedirs(OUT, exist_ok=True)


class StubGame:
    def __init__(self):
        self.teams_config = {'team_0': {'name': 'P', 'faction': 'USA'},
                             'team_1': {'name': 'E', 'faction': 'RUSSIA'}}
        self.team_tech_levels = {}
        self.my_faction = 'USA'
        self.enemy_faction = 'RUSSIA'
        self.my_team = 'team_0'
        self.team_resources = {'team_0': 10000, 'team_1': 10000}
        self.all_buildings = []
        self.all_units = []
        self.projectiles = []
        self.particles = pygame.sprite.Group()
        self.is_online = False
        self.my_role = 'HOST'
        self.net_events = []
        self.show_alert = lambda *a, **k: None
        self.ui_font = pygame.font.Font(None, 20)
        self.current_map = None
        self.current_voltage = 0
        self.max_voltage = 100
        self.selected_entity = None


g = StubGame()
pos = vec(3000, 3000)

# 现场渲染类：名字 -> (类, 构造参数)
LIVE = [
    ('EuropeanChurch', bc.EuropeanChurch, ()),
    ('HalfTimberHouse', bc.HalfTimberHouse, ()),
    ('ClockTower', bc.ClockTower, ()),
    ('Windmill', bc.Windmill, ()),
    ('CivilianHouse', bc.CivilianHouse, ()),
    ('Skyscraper', bc.Skyscraper, ()),
    ('OilDerrick', bc.OilDerrick, ()),
    ('Shipyard', bc.Shipyard, ('team_0',)),
    ('TechCenter', bc.TechCenter, ('team_0',)),
    ('EMPGenerator', bc.EMPGenerator, ()),
    ('AncientTemple', bc.AncientTemple, ()),
    ('CommStation', bc.CommStation, ()),
    ('BroadcastDish', bc.BroadcastDish, ()),
    ('Bridge_h', bc.Bridge, ('horizontal',)),
    ('MercFactory', bc.MercenaryFactory, ()),
    ('Bunker', units.Bunker, ('team_0',)),
    ('AntiAirTurret', units.AntiAirTurret, ('team_0',)),
    ('LaserTurret', units.LaserTurret, ('team_0',)),
    ('MissileDefenseSystem', units.MissileDefenseSystem, ('team_0',)),
    ('CIWS', units.CIWS, ('team_0',)),
    ('CoastalGun', units.CoastalGun, ('team_0',)),
    ('BaseBuilding', units.BaseBuilding, ('team_0',)),
    ('FactoryBuilding', units.FactoryBuilding, ('team_0',)),
    ('Barracks', units.Barracks, ('team_0',)),
    ('RadarBuilding', units.RadarBuilding, ('team_0',)),
    ('PowerPlant', units.PowerPlant, ('team_0',)),
    ('MiningRig', units.MiningRig, ('team_0',)),
    ('Airfield', units.Airfield, ('team_0',)),
    ('ResearchCenter', units.ResearchCenter, ('team_0',)),
    ('ShroudGen', units.ShroudGen, ('team_0',)),
    ('PrototypeGen', units.PrototypeGen, ('team_0',)),
    ('IronCurtain', units.IronCurtain, ('team_0', 'parent')),
    ('NukeSilo', units.NukeSilo, ('team_0', 'parent')),
    ('Lighthouse', units.Lighthouse, ()),
    ('Bastion', units.Bastion, ()),
    ('TeslaTower', units.TeslaTower, ()),
    ('MercFactoryU', units.MercenaryFactory, ('team_0',)),
]

CELL_W, CELL_H, LBL_H = 300, 250, 22
COLS = 5


def render_live(cls, extra, team=None):
    """实例化并取立绘：有 self.image 直接用；否则 draw 到画布上裁剪。"""
    args = [g, pos] + [None if e == 'parent' else e for e in extra]
    try:
        b = cls(*args)
    except TypeError:
        b = cls(g, pos)
    except Exception:
        raise
    img = getattr(b, 'image', None)
    if isinstance(img, pygame.Surface):
        return img
    # draw-time 渲染
    canvas = pygame.Surface((700, 700), pygame.SRCALPHA)
    try:
        b.draw(canvas, vec(3000 - 350, 3000 - 350), 1.0)
    except Exception:
        b.draw(canvas, vec(2750, 2750), 1.0)
    # 找非空包围盒
    import pygame.surfarray as sa
    a = sa.array_alpha(canvas)
    ys, xs = (a > 10).nonzero()
    if len(xs) == 0:
        return None
    rect = pygame.Rect(int(xs.min()), int(ys.min()),
                       int(xs.max() - xs.min()) + 1, int(ys.max() - ys.min()) + 1)
    return canvas.subsurface(rect.clamp(canvas.get_rect())).copy()


def main():
    tiles = []
    for name, cls, extra in LIVE:
        try:
            img = render_live(cls, extra, 'team_0' if 'team_0' in str(extra) or cls.__module__.startswith('units.') and name not in ('Lighthouse', 'Bastion', 'TeslaTower') else None)
            if img is not None:
                tiles.append((name, img))
                continue
            tiles.append((name, None))
        except Exception as e:
            print('FAIL', name, repr(e))
            traceback.print_exc(limit=2)
            tiles.append((name, None))

    # PNG 目录里的建筑（实际被引用的图）
    spr_root = os.path.join(ROOT, 'sprites', 'units')
    png_classes = ['Airfield', 'AncientTemple', 'Barracks', 'BaseBuilding', 'Bastion',
                   'BroadcastDish', 'CivilianHouse', 'CIWS', 'CoastalGun', 'CommStation',
                   'ConcreteRubble', 'EMPGenerator', 'FactoryBuilding', 'IronCurtain',
                   'Lighthouse', 'MiningRig', 'NukeSilo', 'OilDerrick', 'PowerPlant',
                   'PrototypeGen', 'RadarBuilding', 'ResearchCenter', 'Shipyard',
                   'ShroudGen', 'Skyscraper', 'TechCenter', 'TeslaTower']
    for cn in png_classes:
        d = os.path.join(spr_root, cn, 'base')
        pngs = sorted(glob.glob(os.path.join(d, '*.png')))
        if not pngs:
            d = os.path.join(spr_root, cn)
            pngs = sorted(glob.glob(os.path.join(d, '*.png')))
        if pngs:
            try:
                img = pygame.image.load(pngs[0]).convert_alpha()
                tiles.append((cn + '_png', img))
            except Exception as e:
                print('FAIL png', cn, e)

    # 拼图
    rows = (len(tiles) + COLS - 1) // COLS
    per_sheet = 25
    sheet_i = 0
    for start in range(0, len(tiles), per_sheet):
        chunk = tiles[start:start + per_sheet]
        rows = (len(chunk) + COLS - 1) // COLS
        sheet = pygame.Surface((COLS * CELL_W, rows * (CELL_H + LBL_H)))
        sheet.fill((34, 38, 44))
        fnt = pygame.font.Font(None, 22)
        for i, (name, img) in enumerate(chunk):
            r, c = divmod(i, COLS)
            ox, oy = c * CELL_W, r * (CELL_H + LBL_H)
            pygame.draw.rect(sheet, (60, 64, 72), (ox, oy, CELL_W, LBL_H))
            sheet.blit(fnt.render(name, True, (255, 220, 120)), (ox + 6, oy + 4))
            if img is None:
                continue
            iw, ih = img.get_size()
            k = min((CELL_W - 20) / iw, (CELL_H - 20) / ih, 1.0)
            img2 = pygame.transform.smoothscale(img, (max(1, int(iw * k)), max(1, int(ih * k))))
            sheet.blit(img2, (ox + (CELL_W - img2.get_width()) // 2,
                              oy + LBL_H + (CELL_H - img2.get_height()) // 2))
        p = os.path.join(OUT, 'sheet_%d.png' % sheet_i)
        pygame.image.save(sheet, p)
        print('SAVED', p)
        sheet_i += 1


main()
