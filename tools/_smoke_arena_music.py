# -*- coding: utf-8 -*-
"""冒烟：竞技场不使用循环战斗音乐（无头）"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame
pygame.init()
pygame.mixer.init()

from game.core_mixin import GameCoreMixin as CoreMixin


class MockGame(CoreMixin):
    def __init__(self):
        self.state = "ARENA"
        self.arena_active = True
        self.current_music_state = "BATTLE"
        self.current_music_path = "music/battle_loop.mp3"
        self.all_buildings = []
        self.all_units = []
        self.teams_config = ["team_0", "team_1"]
        self.is_online = False
        self.my_role = "HOST"
        self.frame_count = 9999
        self.music_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "music")
        self.music_files = {}
        self.current_map = None


g = MockGame()

# 1. 竞技场 -> 切入专用循环 BGM（arena_bgm.ogg）
pygame.mixer.music.stop()
g.check_music_state()
assert g.current_music_state == "ARENA_BGM" and pygame.mixer.music.get_busy()
print('1. 竞技场切入专用循环 BGM OK')

# 2. 连续调用不重启（同一首持续播放）
cur = g.current_music_path
g.check_music_state(); g.check_music_state()
assert g.current_music_state == "ARENA_BGM" and g.current_music_path == cur
print('2. 连续调用不重启 OK')

# 3. GAMEOVER 结算音乐不受影响（短路在 GAMEOVER 分支之后）
g.state = "GAMEOVER"
g.check_music_state()
assert g.current_music_state == "END_THEME"
print('3. GAMEOVER 结算音乐分支不受影响 OK')

print('ALL PASS')
