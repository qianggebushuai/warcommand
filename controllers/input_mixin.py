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
from core.sfx import SFXManager

class InputMixin:
    def select_entity(self, world_pos):
        self.selected_entity = None
        
        # [修改] 直接使用正确的 my_team (例如 "team_0")
        target_team = self.my_team 

        # 1. 优先检查建筑
        for b in self.all_buildings:
            if b.rect.collidepoint(world_pos):
                # 只有是我方的才选中 (或者你可以允许选中敌方查看血量，看你设计)
                if b.team == target_team:
                    self.selected_entity = b
                    SFXManager.instance().play("select", 0.7)
                    return # 选中一个就退出，避免重叠冲突

        # 2. 检查单位
        for unit in self.all_units:
            if unit.rect.collidepoint(world_pos):
                if unit.team == target_team:
                    self.selected_entity = unit
                    SFXManager.instance().play("select", 0.7)
                    return


    def handle_input(self):
        if self.state == "AUTH":
            self.auth_ui.handle_input()
            return
        
        # === 0. 登录界面 (LOGIN) ===
        if self.state == "LOGIN":
            self.handle_login_input() 

            return
        if self.state == "LOBBY":
            self.lobby_ui.handle_input()
            return
        if self.state == "SKIRMISH":
            self.skirmish_ui.handle_input()
            return
        if self.state == "DIC":
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.running = False
                self.dic_ui.handle_event(event)
            return
        if self.state == "WAITING":
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.running = False
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    m_pos = pygame.mouse.get_pos()
                    if self.lobby_ui["cancel_wait"].collidepoint(m_pos):
                        self.net.stop_hosting()
                        self.state = "LOBBY"
                        self.is_online = False
            return

        # === 3. 加载界面 (LOADING) ===
        if self.state == "LOADING":
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.running = False
            return

        # === 4. 菜单界面 (MENU) ===
        if self.state == "MENU":
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.running = False
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.state = "LOGIN"

                # 图鉴/设置入口（面板打开时优先拦截事件；未激活时点右上角按钮打开）
                if hasattr(self, 'dic_ui') and self.dic_ui.handle_event(event):
                    continue
                if self.setting_ui.handle_event(event):
                    continue

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    m_pos = pygame.mouse.get_pos()
                    if self.btn_easy.collidepoint(m_pos):
                        # 竞技场（争锋频道）：押注军费观战两军对垒
                        self.arena_enter()
                    elif self.btn_fog.collidepoint(m_pos):
                        # 迷雾竞技场：开战前看不到敌军，自费布防
                        self.arena_enter("fog")
                    elif self.btn_normal.collidepoint(m_pos):     self.state = "SKIRMISH"
                    elif self.btn_hard.collidepoint(m_pos):self.state = "STORY"
                    elif self.btn_bombard.collidepoint(m_pos): self.bombardment_mode = not self.bombardment_mode
                    elif self.btn_tutorial.collidepoint(m_pos): self.state = "TUTORIAL"
                    elif self.btn_quit.collidepoint(m_pos): self.state = "LOGIN"; self.is_online = False 
                    if hasattr(self, 'faction_btn_rect') and self.faction_btn_rect.collidepoint(m_pos):
                        # 循环切换: USA -> CHINA -> RUSSIA
                        factions = ["USA", "CHINA", "RUSSIA"]
                        curr = getattr(self, 'my_faction', 'USA')
                        try:
                            idx = factions.index(curr)
                        except: idx = 0
                        
                        next_idx = (idx + 1) % len(factions)
                        self.my_faction = factions[next_idx]
                        
                        # [关键] 更新 teams_config (如果已经初始化了)
                        if self.teams_config and "team_0" in self.teams_config:
                            self.teams_config["team_0"]["faction"] = self.my_faction
            return

        # === 5. 教程界面 (TUTORIAL) ===
        if self.state == "TUTORIAL":
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.running = False
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.btn_close_tut.collidepoint(pygame.mouse.get_pos()): self.state = "MENU"
            return

        # === 6. 游戏结束界面 (GAMEOVER) ===
        if self.state == "GAMEOVER":
            for event in pygame.event.get():
                
                if event.type == pygame.QUIT: 
                    self.running = False
                    if self.is_online:
                        self.net.stop_hosting() # [必须加] 
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    m_pos = pygame.mouse.get_pos()
                    
                    # 退出按钮
                    if self.btn_quit.collidepoint(m_pos):
                        self.net.stop_hosting()
                        self.state = "LOGIN"
                        if self.is_online:
                            self.is_online = False
                            self.net = NetworkManager() # 重置网络
                            try: self.net.socket.close()
                            except: pass
                        
                        # 重置音乐状态，让 check_music_state 重新加载
                        self.current_music_state = "FORCE_RESET"
                    
                    # 重赛/重启按钮
                    elif self.btn_restart.collidepoint(m_pos):

                        if self.is_online:
                            # 联机重赛逻辑
                            if not getattr(self, 'rematch_requested', False):
                                self.rematch_requested = True
                                self.net.send({"type": "REMATCH_REQ"})
                                if getattr(self, 'opponent_wants_rematch', False):
                                    self.start_rematch()
                            self.reset_lobby_data()
                        else:
                            self.reset_game()
                            self.state = "LOADING" 

            return
        if self.state == "STORY":
            self.story_ui.handle_input()

            return
        # === 竞技场 (ARENA：争锋频道) ===
        if self.state == "ARENA":
            self.handle_arena_input()
            return
        # === 7. 游戏进行中 (PLAYING) ===
    # === 7. 游戏进行中 (PLAYING) ===
        if self.state == "PLAYING":
            # [关键] 提前定义 my_team
            my_team =self.my_team

            # --- WASD 移动 (见 controllers/camera_mixin.update_camera_pan) ---
            self.update_camera_pan()

            raw_mouse_pos = pygame.mouse.get_pos()
            world_mouse_pos = self.screen_to_world(raw_mouse_pos)
            
            for event in pygame.event.get():
                self.chat_box.handle_event(event)
                if self.chat_box.active:
                    if event.type == pygame.QUIT: self.running = False
                    continue

                if event.type == pygame.QUIT: 
                    self.running = False
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    # 暂停菜单逻辑
                    self.paused = not self.paused
                
                # 缩放控制（滚轮在侧栏列表上时改为滚动建造列表）
                if event.type == pygame.MOUSEWHEEL:
                    m_pos = pygame.mouse.get_pos()
                    if self.sidebar.rect.collidepoint(m_pos) and not self.minimap.rect.collidepoint(m_pos):
                        self.sidebar.scroll(-event.y * 45)
                    else:
                        self.zoom_at(event.y > 0)
                
                # 键盘按键
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_PLUS or event.key == pygame.K_KP_PLUS: self.zoom = min(2.0, self.zoom + 0.1)
                    elif event.key == pygame.K_MINUS or event.key == pygame.K_KP_MINUS: self.zoom = max(0.5, self.zoom - 0.1)
                    elif event.key == pygame.K_z:
                        if self.selected_entity and isinstance(self.selected_entity, Unit):
                            if self.selected_entity.team == self.my_team:
                                target_type = type(self.selected_entity)
                                
                                self.multi_selected_units = []
                                
                                count = 0
                                for u in self.all_units:
                                    if u.alive and u.team == self.my_team and isinstance(u, target_type):
                                        
                                        self.multi_selected_units.append(u)
                                        count += 1

                    #  E 键 
                    elif event.key == pygame.K_e:
                        target_units = self.multi_selected_units if self.multi_selected_units else []
                        if not target_units and self.selected_entity and isinstance(self.selected_entity, Unit):
                            target_units = [self.selected_entity]
                            
                        target_buildings = []
                        if self.selected_entity and isinstance(self.selected_entity, Building):
                            target_buildings = [self.selected_entity]

                        # 1. 处理单位技能
                        for u in target_units:
                            if not u or not u.alive or u.team != my_team: continue
                            from units import APC, DroneCarrier, HeavyTransport, MissileCruiser, ShockwaveVehicle
                            if isinstance(u, APC):
                                if self.is_online and self.my_role == "CLIENT":
                                    self.net.send({"type": "REQ_APC_LOAD", "uid": u.uid})
                                else:
                                    u.load_units()
                            if isinstance(u, HeavyTransport):
                                if self.is_online and self.my_role == "CLIENT":
                                    self.net.send({"type": "REQ_HEAVYTRANSPORT_LOAD", "uid": u.uid})
                                else:
                                    u.load_units()
                            if isinstance(u, TankCarrier):
                                if self.is_online and self.my_role == "CLIENT":
                                    self.net.send({"type": "REQ_TANKCARRIER_LOAD", "uid": u.uid})
                                else:
                                    u.load_units()
                            if isinstance(u, DroneCarrier):
                                if self.is_online and self.my_role == "CLIENT":
                                    self.net.send({"type": "REQ_TOGGLE", "uid": u.uid})
                                else:
                                    u.toggle_mode()
                            if isinstance(u, MissileCruiser):
                                u.toggle_mode() 
                            if isinstance(u, ShockwaveVehicle):
                                if self.is_online and self.my_role == "CLIENT":
                                    self.net.send({"type": "REQ_TOGGLE", "uid": u.uid})
                                else:
                                    u.activate_shockwave()
                            else:
                                 continue    
                        for b in target_buildings:
                            if not b or not b.alive or b.team != my_team: continue
                            
                            if getattr(b, 'b_type', '') == 'prototype_gen' and b.weapon_obj:
                                if not getattr(b, 'is_ready', False):
                                    self.show_alert("WEAPON CHARGING...")
                                    continue
                                b.weapon_obj.toggle_mode()
                    elif event.key == pygame.K_r:
                        from units import APC,HeavyTransport
                        target_list = self.multi_selected_units if self.multi_selected_units else [self.selected_entity]
                        
                        for u in target_list:
                            if not u or not u.alive or u.team != my_team: continue
                            
                            if isinstance(u, APC):
                                if self.is_online and self.my_role == "CLIENT":
                                    self.net.send({"type": "REQ_APC_UNLOAD", "uid": u.uid})
                                else:
                                    u.unload_units()
                            elif isinstance(u, HeavyTransport):
                                if self.is_online and self.my_role == "CLIENT":
                                    self.net.send({"type": "REQ_HEAVYTRANSPORT_UNLOAD", "uid": u.uid})
                                else:
                                    u.unload_units()
                            elif isinstance(u, TankCarrier):
                                if self.is_online and self.my_role == "CLIENT":
                                    self.net.send({"type": "REQ_TANKCARRIER_UNLOAD", "uid": u.uid})
                                else:
                                    u.unload_units()
                            elif hasattr(u, 'toggle_mode'):
                                if self.is_online and self.my_role == "CLIENT":
                                    self.net.send({"type": "REQ_TOGGLE", "uid": u.uid})
                                else:
                                    u.toggle_mode()
                    elif event.key == pygame.K_F10:
                        # AI 自动游玩总开关（ai_autoplay 包）
                        try:
                            from ai_autoplay.agent import AutoPlayManager
                            if getattr(self, 'autoplay', None) is None:
                                self.autoplay = AutoPlayManager(self)
                            self.autoplay.toggle()
                        except Exception as _ap_err:
                            print('[AutoPlay] 启动失败: %s' % _ap_err)
                    elif event.key == pygame.K_F9:
                        # F9：AI HUD 面板显隐（红点不受影响，常显）
                        if getattr(self, 'autoplay', None) is not None:
                            self.autoplay.hud_visible = not self.autoplay.hud_visible
                            print('[AutoPlay] HUD %s' %
                                  ('显示' if self.autoplay.hud_visible else '隐藏'))
                    elif event.key == pygame.K_F8:
                        # F8：人工示范录制开关（玩家手动玩，系统每 6s 落盘样本）
                        if getattr(self, 'autoplay', None) is not None \
                                and getattr(self.autoplay, 'demo', None) is not None:
                            self.autoplay.demo.toggle()
                    elif event.key == pygame.K_F7:
                        print("\n=== DEBUG DUMP ===")
                        print(f"Role: {self.my_role}, Frame: {self.frame_count}")
                        
                        print(f"--- UNITS ({len(self.all_units)}) ---")
                        for u in self.all_units:
                            # 打印关键信息：UID, 类名, 阵营, 存活状态, 位置
                            print(f"UID: {u.uid[:6]} | Cls: {u.__class__.__name__} | Team: {u.team} | Alive: {u.alive} | Pos: {u.pos}")
                        
                        print(f"--- BUILDINGS ({len(self.all_buildings)}) ---")
                        for b in self.all_buildings:
                            print(f"UID: {b.uid[:6]} | Cls: {b.__class__.__name__} | Team: {b.team} | Alive: {b.alive} | Pos: {b.pos}")
                        
                        print("==================\n")
                    # MCV 展开
                    elif event.key == pygame.K_q:
                        
                        target_list = self.multi_selected_units if self.multi_selected_units else [self.selected_entity]
                        
                        for u in target_list:
                            if not u or not u.alive or u.team != self.my_team: continue
                            
                            if isinstance(u, MCV):
                                if self.is_online and self.my_role == "CLIENT":
                                    self.net.send({"type": "REQ_DEPLOY", "uid": u.uid})
                                else:
                                    u.deploy()
                            elif isinstance(u, BaseBuilding):
                                if self.is_online and self.my_role == "CLIENT":
                                    self.net.send({"type": "REQ_UNDEPLOY", "uid": u.uid})
                                else:
                                    u.undeploy()
                                    if self.selected_entity == u:
                                        self.selected_entity = None
                # 鼠标按下
                if event.type == pygame.MOUSEBUTTONDOWN:


                    if event.button == 1: # 左键
                        m_pos = pygame.mouse.get_pos()
                        w_x = m_pos[0] / self.zoom + self.camera_offset.x
                        w_y = m_pos[1] / self.zoom + self.camera_offset.y
                        
                        print(f"[Click] Screen: {m_pos} -> World: ({int(w_x)}, {int(w_y)})")                        
                        if self.sidebar.handle_event(event):
                            continue 
                        if self.minimap.handle_event(event): 
                            continue
                        # 暂停按钮
                        if self.btn_pause.collidepoint(m_pos):
                            self.paused = not self.paused 
                            continue
                        
                        # 暂停菜单点击
                        if self.paused: 
                            if self.btn_ingame_exit.collidepoint(m_pos):
                                self.state = "LOGIN"; self.paused = False; self.is_online = False; self.net = NetworkManager()
                            elif self.btn_resume.collidepoint(m_pos):
                                self.paused = False
                            elif self.btn_vol_down.collidepoint(m_pos):
                                self.master_volume = max(0.0, self.master_volume - 0.1)
                                from game.core_mixin import MUSIC_MUTE
                                pygame.mixer.music.set_volume(
                                    0.0 if MUSIC_MUTE else self.master_volume)
                            elif self.btn_vol_up.collidepoint(m_pos):
                                self.master_volume = min(1.0, self.master_volume + 0.1)
                                from game.core_mixin import MUSIC_MUTE
                                pygame.mixer.music.set_volume(
                                    0.0 if MUSIC_MUTE else self.master_volume)
                            continue 

                        # 信息面板开关
                        if 10 <= raw_mouse_pos[0] <= 90 and 40 <= raw_mouse_pos[1] <= 65:
                            self.show_info_panel = not self.show_info_panel
                            continue
                        
                        # 技能释放
                        if self.call_airstrike_mode or self.call_missile_mode or self.call_airdrop_mode:
                            self.handle_support_click(world_mouse_pos)
                            continue 

                        # 放置建筑
                        if self.place_building_type:
                            self.handle_build_click(world_mouse_pos)
                            continue 
                        
                        # 菜单点击 (旧版环形菜单，如果保留的话)
                        if self.selected_entity and isinstance(self.selected_entity, Building) and self.selected_entity.team == my_team:
                            menu_center = to_screen(self.selected_entity.pos, self.camera_offset, self.zoom)
                            if self.handle_menu_click(raw_mouse_pos, menu_center): continue 
                        
                        self.selection_start = m_pos 
                        prev_selection = self.selected_entity
                        prev_multi = list(self.multi_selected_units)
                        self.select_entity(world_mouse_pos)
                        if self.selected_entity is None:
                            self.multi_selected_units = []
                        else:
                            self.multi_selected_units = []
                            self.base_menu_mode = "main"
                    if event.button == 2: # 中键拖动
                        print("yes")
                        if self.sidebar.handle_event(event):
                            continue 

                        self.dragging = True
                        self.last_mouse_pos = vec(pygame.mouse.get_pos())                    
                    # 右键 (移动/攻击)
                    if event.button == 3: 
                        self.place_building_type = None
                        self.call_airstrike_mode = False
                        self.call_missile_mode = False
                        self.call_airdrop_mode = False 
                        self.base_menu_mode = "main" 
                        
                        target_pos = world_mouse_pos
                        
                        clicked_entity = None
                        
                        # 1. 检查是否选中了工程师
                        is_eng_selected = False
                        from units import CombatEngineer                         
                        if self.selected_entity and isinstance(self.selected_entity, CombatEngineer):
                            is_eng_selected = True
                        elif self.multi_selected_units:
                            for u in self.multi_selected_units:
                                if isinstance(u, CombatEngineer):
                                    is_eng_selected = True; break
                        
                        # 2. 搜索建筑 (允许友军)
                        for b in self.all_buildings:
                            if b.alive and b.rect.collidepoint(target_pos):
                                # 如果是工程师，允许点任何建筑 (友军修，敌军占)
                                if is_eng_selected:
                                    clicked_entity = b
                                    break
                                # 如果不是工程师，只认敌人
                                elif b.team != my_team:
                                    clicked_entity = b
                                    break
                                elif getattr(b, 'can_garrison', False):
                                    clicked_entity = b
                                    break                        
                        # 3. 搜索单位 (如果没点到建筑)
                        if not clicked_entity:
                            for u in self.all_units:
                                # 单位通常只能打敌人 (即使是工程师也不能修坦克，除非你想做维修车)
                                if u.alive and u.rect.collidepoint(target_pos) and u.team != my_team:
                                    clicked_entity = u
                                    break
                        
                        # [修正] 执行逻辑
                        units_to_command = []
                        
                        # 检查当前选中的对象 (不管是多选还是单选)
                        selection_pool = self.multi_selected_units if self.multi_selected_units else [self.selected_entity]
                        
                        for obj in selection_pool:
                            if obj and obj.alive and obj.team == self.my_team:
                                # 是单位
                                if isinstance(obj, Unit):
                                    units_to_command.append(obj)
                                # 是有攻击能力的建筑 (Bunker, AA Turret)
                                elif isinstance(obj, Building) and getattr(obj, 'damage', 0) > 0:
                                    units_to_command.append(obj)
                        
                        # [DemoRecorder] 右键指挥单位 → 示范录制钩子：
                        # 点敌方实体 → attack，点空地 → move
                        if units_to_command:
                            _demo = getattr(self, 'autoplay', None)
                            _demo = getattr(_demo, 'demo', None)
                            if _demo is not None:
                                _demo.on_right_click(
                                    target_pos, clicked_entity, self.my_team)
                            uids = [u.uid for u in units_to_command]
                            
                            # === Client 逻辑 ===
                            if self.is_online and self.my_role == "CLIENT":
                                if clicked_entity:
                                    # 发送攻击指令 (这对建筑也有效，因为 Host 会处理)
                                    self.net.send({"type": "REQ_ATTACK", "uids": uids, "target_uid": clicked_entity.uid})
                                    # 反馈 (红线)
                                    dest = clicked_entity.pos
                                    for u in units_to_command:
                                        self.command_lines.append([vec(u.pos), vec(dest), 60])
                                else:
                                    # 点击地面 -> 移动指令
                                    # [注意] 建筑不能移动，所以我们要过滤一下
                                    # 只把能动的单位 ID 发过去，或者发过去让 Host 忽略
                                    mobile_uids = [u.uid for u in units_to_command if isinstance(u, Unit)]
                                    if mobile_uids:
                                        self.net.send({"type": "REQ_MOVE", "uids": mobile_uids, "x": int(target_pos.x), "y": int(target_pos.y)})
                                        # 反馈 (绿线)
                                        for u in units_to_command:
                                            if isinstance(u, Unit):
                                                self.command_lines.append([vec(u.pos), vec(target_pos), 60])

                            # === Host / Single 逻辑 ===
                            else:
                                for u in units_to_command:
                                    # 情况 1: 点击了实体 (攻击/修/占)
                                    if clicked_entity:
                                        # 工程师特殊处理
                                        from units import CombatEngineer
                                        if isinstance(u, CombatEngineer):
                                            u.set_target(clicked_entity)
                                        
                                        # 普通单位/建筑攻击
                                        else:
                                            # 空军特例
                                            if isinstance(u, Unit) and u.is_air and not u.can_attack_air and clicked_entity.is_air:
                                                u.move_to(clicked_entity.pos) # 追着看
                                            else:
                                                # [核心] 建筑和单位都有 set_target 方法 (如果是 Entity 子类)
                                                # 只要实现了 set_target 就能打
                                                if hasattr(u, 'set_target'):
                                                    u.set_target(clicked_entity)
                                    
                                    # 情况 2: 点击了地面 (移动)
                                    else:
                                        # 只有单位能动
                                        if isinstance(u, Unit):
                                            u.move_to(target_pos)
                                    
                                    # 画线反馈
                                    dest = clicked_entity.pos if clicked_entity else target_pos
                                    # 建筑只画攻击线，不画移动线
                                    if clicked_entity or isinstance(u, Unit):
                                        self.command_lines.append([vec(u.pos), vec(dest), 60])

                # 鼠标释放 (框选结束)
                if event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.sidebar.end_scrollbar_drag()
                    if event.button == 2: self.dragging = False
                    if event.button == 1:
                        if self.selection_start and self.selection_rect:
                            self.handle_box_selection()
                        self.selection_start = None
                        self.selection_rect = None
                        self.dragging = False

                # 鼠标移动 (拖拽镜头/框选/滚动条)
                if event.type == pygame.MOUSEMOTION:
                    if self.sidebar.dragging_scrollbar:
                        self.sidebar.update_scrollbar_drag(pygame.mouse.get_pos())
                    elif self.dragging and not self.selection_start:
                        self.handle_camera_drag(pygame.mouse.get_pos())

                    if self.selection_start and pygame.mouse.get_pressed()[0]:
                        m_pos = pygame.mouse.get_pos()
                        if (vec(m_pos) - vec(self.selection_start)).length() > 10:
                            x = min(self.selection_start[0], m_pos[0])
                            y = min(self.selection_start[1], m_pos[1])
                            w = abs(self.selection_start[0] - m_pos[0])
                            h = abs(self.selection_start[1] - m_pos[1])
                            self.selection_rect = pygame.Rect(x, y, w, h)


    def handle_box_selection(self):
        self.multi_selected_units = []
        self.selected_entity = None 
        
     
        # 或者沿用动态判断：   # [修改] 使用 self.my_team
        # 注意：在单机模式下 self.my_team 可能没被 update 设置，
        # 建议在 reset_game 或 init_level 里初始化好 self.my_team = "team_0" (Host/Single)
        target_team = self.my_team if hasattr(self, 'my_team') else ("enemy" if self.is_online and self.my_role == "CLIENT" else "player")
        
        for u in self.all_units:
            if u.team == target_team and u.alive:
                screen_pos = to_screen(u.pos, self.camera_offset, self.zoom)
                if self.selection_rect.collidepoint(screen_pos):
                    self.multi_selected_units.append(u)
        
        if len(self.multi_selected_units) == 1:
            self.selected_entity = self.multi_selected_units[0]
            self.multi_selected_units = []


    def handle_battleship_call(self, team_id):
        # 1. 找到该队伍控制的通讯站
        target_station = None
        for b in self.all_buildings:
            if b.team == team_id and getattr(b, 'b_type', '') == "comm_station":
                print("wdjwdjwidwidwidwid")           
                target_station = b
                break
        
        # 2. [修改] 遍历所有单位，把所有战列舰都变成我的
        from units import Battleship # 确保类型检查正确
        count = 0
        
        for u in self.all_units:
            # 只要是活着的战列舰
            if u.alive and isinstance(u, Battleship):
                # 无论它之前是谁的，现在都是我的
                u.team = team_id
                
                # 重置状态，防止发呆或继续攻击旧目标
                u.target_entity = None
                u.target_pos = None
                u.ai_mode = "GUARD"
                
                # 特效
                from core.base_classes import FloatingText
                self.particles.add(FloatingText(u.pos, "SYSTEM ONLINE", CYAN))
                count += 1
        
        if count > 0:
            # 获取玩家名字用于显示
            owner_name = team_id
            if self.teams_config and team_id in self.teams_config:
                owner_name = self.teams_config[team_id].get('name', team_id)
                
            self.show_alert(f"{owner_name} ACTIVATED {count} BATTLESHIP(S)!")
        else:
            self.show_alert("NO BATTLESHIPS AVAILABLE!")


    def handle_support_click(self, pos):
        RADAR_RANGE = 2000 
        
        has_range = False
        for b in self.all_buildings:
            if b.team == self.my_team and b.alive and getattr(b, 'b_type', '') == 'radar':
                if b.pos.distance_to(pos) <= RADAR_RANGE:
                    has_range = True; break
        
        if not has_range:
            self.show_alert("OUT OF RADAR RANGE!")
            # 不重置状态，允许玩家重点
            return 
        req_type = "ac130"
        if self.call_missile_mode: req_type = "missile"
        elif self.call_airdrop_mode: req_type = "airdrop"
        
        # 2. 客户端逻辑
        if self.is_online and self.my_role == "CLIENT":
            self.net.send({
                "type": "REQ_SUPPORT",
                "s_type": req_type,
                "x": int(pos.x),
                "y": int(pos.y)
            })
        
        else:
            # Host / Single 逻辑
            cost_map = {"ac130": AC130_COST, "missile": MISSILE_COST, "airdrop": AIRDROP_COST}
            cost = cost_map.get(req_type, 0)
            
            # [修改] 使用 self.my_team
            current_money = self.team_resources.get(self.my_team, 0)
            
            if current_money >= cost:
                self.team_resources[self.my_team] -= cost
                
                if req_type == "ac130":
                    self.all_units.append(AC130(self, pos, self.my_team))
                elif req_type == "missile":
                    self.all_units.append(CruiseMissile(self, pos, self.my_team))
                elif req_type == "airdrop": 
                    self.all_units.append(ParatrooperPlane(self, pos, self.my_team))
                elif self.place_building_type == "battleship_call": # 或者是单独的状态标记
                    req_type = "battleship_call"
            else:
                self.show_alert("INSUFFICIENT FUNDS")

        # 4. 重置状态
        self.call_airstrike_mode = False
        self.call_missile_mode = False
        self.call_airdrop_mode = False
        self.selected_entity = None


    def handle_build_click(self, pos):
        if self.place_building_type == "cruiser_missile":
            if self.selected_entity and isinstance(self.selected_entity, MissileCruiser):
                # Client 发请求
                if self.is_online and self.my_role == "CLIENT":
                    self.net.send({
                        "type": "REQ_SKILL", # 统一类型
                        "uid": self.selected_entity.uid,
                        "x": int(pos.x),
                        "y": int(pos.y),
                        "skill": "cruiser_missile" # 标识一下
                    })
                else:
                    self.selected_entity.start_charge(pos)
            
            self.place_building_type = None
            return  
        if self.place_building_type in ["skill_iron_curtain", "skill_nuke"]:
            target_gen = None
            for b in self.all_buildings:
                if b.team == self.my_team and getattr(b, 'b_type', '') == 'prototype_gen':
                    if b.weapon_obj and b.weapon_obj.is_aiming:
                    # 再次确认类型匹配
                        if (self.place_building_type == "skill_iron_curtain" and b.loaded_weapon == "iron_curtain") or (self.place_building_type == "skill_nuke" and b.loaded_weapon == "nuke_silo"):
                            target_gen = b
                            break
            
            if target_gen and target_gen.weapon_obj:
                # 联机模式发送请求
                if self.is_online and self.my_role == "CLIENT":
                    self.net.send({
                        "type": "REQ_SKILL",
                        "skill": self.place_building_type,
                        "uid": target_gen.uid,
                        "x": int(pos.x),
                        "y": int(pos.y)
                    })
                else:
                    # 单机/Host 直接执行
                    target_gen.weapon_obj.activate(pos)
                
                # 重置状态
                self.place_building_type = None
                return # 结束处理      
        cost_map = {
            "factory": FACTORY_COST, "radar": RADAR_COST, "mining": MINING_COST,
            "airfield": AIRFIELD_COST, "research": RESEARCH_COST,
            "missile_def": MISSILE_DEFENSE_COST, "aa_turret": AA_TURRET_COST,
            "laser_turret": LASER_TURRET_COST, 
            "power_plant": POWER_PLANT_COST,
            "shipyard":SHIPYARDCOST , "tech_center": TECH_CENTER_COST,
            "bunker": BUNKER_COST, "shroud_gen": BLACKSHRODCOST,"prototype_gen":PROTOTYPECOST,"iron_curtain":IRONCURTAINCOST,"nuke_silo":NUKESILOCOST,"ciws":CIWS_COST,
            "barracks": BARRACKS_COST
        }
        cost = cost_map.get(self.place_building_type, 0)

        # 2. 水域判定
        from maps.map_data import lake_contains, island_contains
        in_water = False
        if hasattr(self, 'lakes'):
            # 先假设不在水里

            # 第一步：检查是否在任何 Lake 范围内
            for lake in self.lakes:
                if lake_contains(lake, pos.x, pos.y):
                    in_water = True

                    if hasattr(self.current_map, 'islands'):
                        for isle in self.current_map.islands:
                            if island_contains(isle, pos.x, pos.y):
                                in_water = False
                                break

                    break # 判定结束
        
        # 3. 建造位置合法性
        is_shipyard = (self.place_building_type == "shipyard")

        # 悬崖禁建：悬崖仅空中单位可通行，任何建筑落上去单位都进不出
        if hasattr(self, 'lakes'):
            from maps.map_data import lake_contains
            for lake in self.lakes:
                if isinstance(lake, dict) and lake.get('type') == 'cliff' \
                        and lake_contains(lake, pos.x, pos.y):
                    self.show_alert("CANNOT BUILD ON CLIFF!")
                    self.place_building_type = None; return

        if is_shipyard:
            if not in_water:
                self.show_alert("MUST BUILD ON WATER!")
                self.place_building_type = None; return
            
            # [新增] 船厂距离检查
            # 必须在己方基地 (Base) 1000 范围内
            near_base = False
            for b in self.all_buildings:
                if b.team == self.my_team and b.alive and getattr(b, 'b_type', '') == 'base':
                    if b.pos.distance_to(pos) <= 1000:
                        near_base = True; break
            
            if not near_base:
                self.show_alert("TOO FAR FROM BASE (1000)")
                self.place_building_type = None; return

        # 4. 电力检查 (地堡、电站、黑幕不需要电)
        if self.place_building_type not in ["power_plant", "bunker", "shroud_gen"]:
            if self.current_voltage + POWER_COST > self.max_voltage:
                self.show_alert("LOW POWER!")
                self.place_building_type = None
                return
        build_size = 40
        if self.place_building_type == "bunker": build_size = 30
        elif self.place_building_type == "shipyard": build_size = 40
        
        build_rect = pygame.Rect(pos.x - build_size//2, pos.y - build_size//2, build_size, build_size)
        
        collision = False
        # 查建筑
        for b in self.all_buildings:
            if b.alive and b.rect.colliderect(build_rect):
                collision = True; break
        # 查单位
        if not collision:
            for u in self.all_units:
                if u.alive and u.rect.colliderect(build_rect):
                    collision = True; break
        
        if collision:
            self.show_alert("CANNOT BUILD HERE (BLOCKED)")
            self.place_building_type = None
            return
        # [新增] 5. 判断建造模式
        is_instant = getattr(self, 'is_instant_build', False)

        if is_instant:
            # === 秒造模式逻辑 ===
            
            # 距离限制 (只能在基地附近)
            near_base = False
            for b in self.all_buildings:
                # 只要是我方建筑附近 500 范围内都可以造
                if b.team == self.my_team and b.pos.distance_to(pos) < 500: 
                    near_base = True; break
            
            if not near_base:
                self.show_alert("TOO FAR FROM BASE")
                return # 不取消放置状态，允许重新点

            # 执行秒造
            if self.is_online and self.my_role == "CLIENT":
                self.net.send({
                    "type": "REQ_BUILD_INSTANT", # 新协议
                    "b_type": self.place_building_type,
                    "x": int(pos.x), "y": int(pos.y)
                })
            else:
                # Host / Single
                # 钱在开始读条时已经扣过了，这里不需要扣
                self.spawn_building_instantly(self.place_building_type, pos, self.my_team)
            
            # 消耗 Ready 状态
            if hasattr(self, 'sidebar'):
                self.sidebar.consume_ready(self.place_building_type)
            
            self.is_instant_build = False

        else:
            # === 工程师模式逻辑 ===
            
            # 工程师限额检查
            if self.place_building_type != "shipyard":
                my_team = self.my_team
                eng_count = 0
                for u in self.all_units:
                    if isinstance(u, Engineer) and u.team == my_team and u.alive:
                        eng_count += 1
                
                if eng_count >= MAX_ENGINEERS:
                    self.show_alert(f"MAX ENGINEERS ({MAX_ENGINEERS})")
                    self.place_building_type = None
                    return

            # 执行工程师建造
            if self.is_online and self.my_role == "CLIENT":
                self.net.send({
                    "type": "REQ_BUILD", 
                    "b_type": self.place_building_type,
                    "x": int(pos.x),
                    "y": int(pos.y)
                })
            else:
                # Host/Single 本地逻辑
                current_money = self.team_resources.get(self.my_team, 0)
                
                if current_money >= cost:
                    self.team_resources[self.my_team] -= cost
                    
                    if is_shipyard:
                        from core.base_classes import Shipyard
                        self.all_buildings.append(Shipyard(self, pos, self.my_team))
                    else:
                        # [修改] 智能选择工程师出发点
                        spawn_origin = vec(0,0)
                        
                        # 1. 定义依赖关系 (请确保这里的键值对与您的实际 b_type 一致)
                        # Tech Lab 通常是 "research", Tech Center 是 "tech_center"
                        dependency_map = {
                            "laser_turret": "research",  # 需要 T2 科技
                            "aa_turret": "radar",        # 需要雷达
                            "missile_def": "radar",
                            "shroud_gen": "research",
                            "prototype_gen": "tech_center" # T3
                        }
                        
                        target_type = self.place_building_type
                        required_origin = dependency_map.get(target_type, "base")
                        
                        # 2. 寻找最佳出发建筑
                        candidates = []
                        for b in self.all_buildings:
                            # 找己方、存活、且类型匹配的建筑
                            # 注意: 对于 Host 来说，self.my_team 就是当前操作者的队伍
                            if b.team == self.my_team and b.alive and getattr(b, 'b_type', '') == required_origin:
                                candidates.append(b)
                        
                        if candidates:
                            # 选离建造点最近的
                            best_b = min(candidates, key=lambda b: b.pos.distance_to(pos))
                            spawn_origin = best_b.pos
                        else:
                            # 3. 回退逻辑 (如果没有特定建筑，找基地)
                            if self.player_base and self.player_base.alive:
                                spawn_origin = self.player_base.pos
                            elif getattr(self, 'my_start_pos', None):
                                spawn_origin = self.my_start_pos
                            else:
                                # 最后的兜底：找任意一个活着的己方建筑
                                any_b = next((b for b in self.all_buildings if b.team == self.my_team and b.alive), None)
                                if any_b: spawn_origin = any_b.pos

                        # 4. 生成工程师
                        eng = Engineer(self, spawn_origin, self.my_team, pos)
                        eng.target_type = self.place_building_type
                        self.all_units.append(eng)
                else:
                    self.show_alert("INSUFFICIENT FUNDS")

        self.place_building_type = None 

