# -*- coding: utf-8 -*-
"""无头冒烟：8 个重构后的建筑类 实例化 + draw(zoom=1/0.5) + image/锚点断言"""
import os, sys
ROOT = r"g:\网游克星\真正的网游克星\warcommand"
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
pygame.init()
pygame.display.set_mode((1, 1))

from core.base_classes import (Skyscraper, Shipyard, TechCenter, EMPGenerator,
                               AncientTemple, CommStation, Bridge, BroadcastDish)


class _Particles:
    def add(self, *a, **k):
        pass


class MockGame:
    def __init__(self):
        self.current_map = None
        self.all_units = []
        self.all_buildings = []
        self.particles = _Particles()
        self.my_faction = 'CHINA'
        self.enemy_faction = 'USA'
        self.my_team = 'team_0'
        self.team_resources = {}
        self.net_events = []
        self.is_online = False
        self.teams_config = {'team_0': {'faction': 'CHINA'}}


game = MockGame()
pos = pygame.math.Vector2(400, 300)

cases = [
    ('Skyscraper', Skyscraper(game, pos)),
    ('Shipyard', Shipyard(game, pos, 'team_0')),
    ('TechCenter', TechCenter(game, pos, 'team_0')),
    ('EMPGenerator', EMPGenerator(game, pos)),
    ('AncientTemple', AncientTemple(game, pos)),
    ('CommStation', CommStation(game, pos)),
    ('Bridge-H', Bridge(game, pos, 'horizontal')),
    ('Bridge-V', Bridge(game, pos, 'vertical')),
    ('BroadcastDish', BroadcastDish(game, pos)),
]

failures = []
for name, b in cases:
    try:
        surf = pygame.Surface((800, 600))
        b.pos = pygame.math.Vector2(400, 300)
        # 1) zoom=1 绘制（首绘应惰性生成 image 并走 blit 路径）
        b.draw(surf, pygame.math.Vector2(0, 0), 1.0)
        assert hasattr(b, 'image'), '%s: no self.image after draw' % name
        img = b.image
        assert img.get_width() > 10 and img.get_height() > 10, '%s: image too small %s' % (name, img.get_size())
        ox, oy = b._image_anchor()
        assert 0 < ox < img.get_width() and 0 < oy < img.get_height(), \
            '%s: anchor %s out of image %s' % (name, (ox, oy), img.get_size())
        # 2) zoom=0.5 绘制
        b.draw(surf, pygame.math.Vector2(0, 0), 0.5)
        # 3) 无图回退路径（_draw_static 现场绘制）不抛异常
        b.image = None
        b._img_scaled_cache = None
        b.draw(surf, pygame.math.Vector2(0, 0), 1.0)
        # 4) 缓存 blit 路径恢复
        b.image = img
        b.draw(surf, pygame.math.Vector2(0, 0), 2.0)
        print('PASS %-13s image=%-12s anchor=%s' % (name, str(img.get_size()), str((ox, oy))))
    except Exception as e:
        import traceback
        failures.append(name)
        print('FAIL %-13s %r' % (name, e))
        traceback.print_exc()

# Bridge 两种朝向的图尺寸必须不同且与 self.width/height 一致
bh = dict(cases)['Bridge-H']
bv = dict(cases)['Bridge-V']
assert bh.image.get_size() == (600, 300), bh.image.get_size()
assert bv.image.get_size() == (200, 300), bv.image.get_size()
print('PASS Bridge orientation image sizes: H=%s V=%s' % (bh.image.get_size(), bv.image.get_size()))

print('RESULT: %s' % ('ALL PASS' if not failures else 'FAILED: %s' % failures))
sys.exit(1 if failures else 0)
