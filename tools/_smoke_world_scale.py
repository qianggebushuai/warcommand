# -*- coding: utf-8 -*-
"""世界层 75% 降分辨率渲染管线冒烟：换屏/复原、世界段与覆盖段分流、放大回画布。"""
import os
import sys

os.environ['SDL_VIDEODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from pygame.math import Vector2 as vec

pygame.init()
pygame.display.set_mode((1600, 900))

PASS = TOTAL = 0


def check(name, ok, detail=""):
    global PASS, TOTAL
    TOTAL += 1
    if ok:
        PASS += 1
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}  {detail}")


from core.settings import WORLD_SCALE, SCREEN_WIDTH, SCREEN_HEIGHT


class StubEnv:
    def __init__(self):
        self.drawn_on = []

    def draw(self, screen):
        self.drawn_on.append(screen)


from game.render_mixin import RenderMixin


class StubGame(RenderMixin):
    """draw_world 所需的最小游戏对象（空场景）。"""

    def __init__(self):
        self.screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
        self._canvas = self.screen
        self._world_surf = None
        if WORLD_SCALE < 0.999:
            self._world_surf = pygame.Surface(
                (int(SCREEN_WIDTH * WORLD_SCALE), int(SCREEN_HEIGHT * WORLD_SCALE))).convert()
        self.zoom = 1.0
        self.camera_offset = vec(0, 0)
        self.current_map = None          # 世界段走 fill((30,34,30)) 分支
        self.water_fx = None
        self.lakes = []
        self.all_buildings = []
        self.all_units = []
        self.projectiles = []
        self.particles = pygame.sprite.Group()
        self.floating_texts = pygame.sprite.Group()
        self.command_lines = []
        self.place_building_type = None
        self.call_airstrike_mode = False
        self.call_missile_mode = False
        self.call_airdrop_mode = False
        self.is_online = False
        self.my_role = "HOST"
        self.my_team = "team_0"
        self.selected_entity = None
        self.multi_selected_units = []
        self.selection_rect = None
        self.player_base = None
        self.env_manager = StubEnv()


g = StubGame()

# 1. 降分辨率管线：世界段画在 _world_surf，放大后画布底色一致
g.draw_world()
check("1 世界段换屏+放大回画布(底色一致)",
      g.screen.get_at((10, 10))[:3] == (30, 34, 30), g.screen.get_at((10, 10)))
check("2 zoom/screen 复原", g.zoom == 1.0 and g.screen is g._canvas, (g.zoom, g.screen is g._canvas))

# 2. 覆盖段（env_manager.draw）收到的是全分辨率画布而非 _world_surf
check("3 环境层画在全分辨率画布", g.env_manager.drawn_on and
      all(s is g._canvas for s in g.env_manager.drawn_on),
      [id(s) for s in g.env_manager.drawn_on])

# 3. zoom 缩放档：0.5 zoom 下管线照常
g2 = StubGame()
g2.zoom = 0.5
g2.draw_world()
check("4 缩放档下复原", g2.zoom == 0.5 and g2.screen is g2._canvas, (g2.zoom,))

# 4. _world_surf=None（等价 WORLD_SCALE=1.0）走原路径直绘画布
g3 = StubGame()
g3._world_surf = None
g3.draw_world()
check("5 None 档直绘画布", g3.screen.get_at((10, 10))[:3] == (30, 34, 30) and g3.screen is g3._canvas,
      g3.screen.get_at((10, 10)))
check("6 None 档环境层也直绘画布", g3.env_manager.drawn_on and
      all(s is g3._canvas for s in g3.env_manager.drawn_on),
      [id(s) for s in g3.env_manager.drawn_on])

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
