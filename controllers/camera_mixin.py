import pygame
import os
import random
import math
import json
import time
import sys
import fractions
import pygame.scrap
from core.settings import *
from core.base_classes import *
from units import *
from core.dic import *
from maps import *
from panels.widgets import ChatBox, BFButton, InputBox
from panels.ui_sidebar import Sidebar, Minimap
from panels.ui_login import LoginUI
from panels.ui_lobby import LobbyUI
from panels.basesetting import BaseSettingUI
from panels.selfdefine import SkirmishUI
from panels.updatelog import UpdateLogUI
from panels.warstory import WarStoryUI
from maps.environment import EnvironmentManager
from network import NetworkManager
from ai.ai_logic import AICommander
from core.factions import get_random_faction
from core.utils import resource_path, get_font

class CameraMixin:

    def screen_to_world(self, pos):
        return vec(pos[0] / self.zoom + self.camera_offset.x, pos[1] / self.zoom + self.camera_offset.y)

    # ============ 以下方法自 handle_input / update 抽出，代码逐行保持不变 ============

    def update_camera_pan(self):
        """WASD/方向键平移镜头并限制边界（原 handle_input 内嵌逻辑，逐行不变）"""
        if self.chat_box.active:  # 聊天时禁用移动
            return
        keys = pygame.key.get_pressed()
        camera_speed = 15 / self.zoom
        move_vec = vec(0, 0)
        if keys[pygame.K_w] or keys[pygame.K_UP]:    move_vec.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  move_vec.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  move_vec.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: move_vec.x += 1
        if move_vec.length() > 0:
            self.camera_offset += move_vec.normalize() * camera_speed
            map_w = self.current_map.width if self.current_map else WORLD_WIDTH
            map_h = self.current_map.height if self.current_map else WORLD_HEIGHT
            self.camera_offset.x = max(-500, min(self.camera_offset.x, map_w - SCREEN_WIDTH/self.zoom + 500))
            self.camera_offset.y = max(-500, min(self.camera_offset.y, map_h - SCREEN_HEIGHT/self.zoom + 500))

    def zoom_at(self, zoom_in):
        """以屏幕中心为锚点缩放（原 handle_input 滚轮逻辑，逐行不变）"""
        old_zoom = self.zoom
        if zoom_in: self.zoom = min(2.0, self.zoom + 0.1)
        else: self.zoom = max(0.5, self.zoom - 0.1)
        if self.zoom != old_zoom:
            center_world = self.screen_to_world((SCREEN_WIDTH/2, SCREEN_HEIGHT/2))
            new_off_x = center_world.x - (SCREEN_WIDTH/2) / self.zoom
            new_off_y = center_world.y - (SCREEN_HEIGHT/2) / self.zoom
            self.camera_offset = vec(new_off_x, new_off_y)

    def handle_camera_drag(self, m_pos):
        """中键拖拽平移镜头并限制边界（原 handle_input 内嵌逻辑，逐行不变）"""
        delta = vec(m_pos) - self.last_mouse_pos
        self.camera_offset -= delta / self.zoom
        self.last_mouse_pos = vec(m_pos)
        map_w = self.current_map.width if self.current_map else WORLD_WIDTH
        map_h = self.current_map.height if self.current_map else WORLD_HEIGHT
        self.camera_offset.x = max(-500, min(self.camera_offset.x, map_w - SCREEN_WIDTH/self.zoom + 500))
        self.camera_offset.y = max(-500, min(self.camera_offset.y, map_h - SCREEN_HEIGHT/self.zoom + 500))

    def update_opening_camera(self):
        """开场动画：镜头缩放并定位到己方基地（原 update 内嵌逻辑，逐行不变）"""
        data_ready = True
        if self.is_online and self.my_role == "CLIENT":
            data_ready = self.has_received_first_snapshot

        if not self.opening_animation_done and data_ready:

            # 1. 确定目标中心 (实时搜索)
            target_center_world = None

            # 遍历所有建筑，寻找己方基地
            for b in self.all_buildings:
                if b.team == self.my_team and getattr(b, 'b_type', '') == 'base':
                    target_center_world = vec(b.pos)
                    break

            # 如果没找到 (比如还没同步过来，或者已经被推平了)，回退到地图中心
            if not target_center_world:
                if self.current_map:
                    target_center_world = vec(self.current_map.width/2, self.current_map.height/2)
                else:
                    target_center_world = vec(0, 0)
            # 2. 目标缩放
            final_zoom = 1.0

            # 3. 缩放动画
            if abs(self.zoom - final_zoom) > 0.005:
                self.zoom += (final_zoom - self.zoom) * 0.05
                screen_center = vec(SCREEN_WIDTH/2, SCREEN_HEIGHT/2)
                self.camera_offset = target_center_world - (screen_center / self.zoom)

            else:
                # 结束
                self.zoom = final_zoom
                screen_center = vec(SCREEN_WIDTH/2, SCREEN_HEIGHT/2)
                self.camera_offset = target_center_world - (screen_center / self.zoom)
                self.opening_animation_done = True
                print("[Game] Camera Snapped to Base.")

