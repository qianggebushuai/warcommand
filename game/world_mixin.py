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

class WorldMixin:
    def update_game_world(self):
        """处理通用的游戏物理逻辑：移动、碰撞、轰炸、输赢判断"""
        self.frame_count += 1
       
        # 1. 开局保护 (防止过早判负)
        if self.frame_count < 120: # 给足2秒
            for u in self.all_units: u.update()
            for b in self.all_buildings: b.update()
            # 也要更新特效，不然画面是静止的
            self.particles.update()
            self.floating_texts.update()
            return  

        # 2. [修改] 电力计算 (使用正确的 my_team)
        my_team = self.my_team
        
        current_usage = 0
        max_cap = getattr(self, 'INITIAL_POWER_CAP', 500) # 确保有默认值
        
        # [调试] 统计一下
        my_buildings_count = 0
        power_plants_count = 0
        
        for b in self.all_buildings:
            if b.team == my_team and b.alive:
                my_buildings_count += 1
                b_type = getattr(b, 'b_type', '')
                
                usage = getattr(b, 'power_usage', 0)
                current_usage += usage
                
                if b_type == "power_plant":
                    power_plants_count += 1
                    max_cap += 300
        
        self.current_voltage = current_usage
        self.max_voltage = max_cap
        
        # 3. 轰炸模式逻辑 (保持不变)
        if self.bombardment_mode and self.frame_count % 120 == 0: 
            target_x = random.randint(100, WORLD_WIDTH - 100)
            target_y = random.randint(100, WORLD_HEIGHT - 100)
            target_pos = vec(target_x, target_y)
            missile = CruiseMissile(self, target_pos, "neutral")
            spawn_offset = vec(random.randint(-1000, 1000), -1500)
            missile.pos = target_pos + spawn_offset
            self.all_units.append(missile)
            if self.frame_count % 600 == 0: 
                self.show_alert("MISSILE SHOWER INCOMING!")

        if self.game_over: return 


        should_check_win = (not self.is_online) or (self.my_role == "HOST")
        
        if should_check_win:
            
            # --- [A] 个人淘汰检测 (Host/Single 自己检查自己) ---
            # 统计我方剩余资产
            my_assets = 0
            for b in self.all_buildings:
                if b.alive and b.team == self.my_team: my_assets += 1
            for u in self.all_units:
                if u.alive and u.team == self.my_team: my_assets += 1
            if my_assets == 0 and not getattr(self, 'is_spectator', False):
                if not self.is_online:
                    self.game_over = True
                    self.winner = "ENEMY"
                    self.state = "GAMEOVER"
                    return 

                self.is_spectator = True                
                self.show_alert("YOU HAVE BEEN ELIMINATED!", duration=300)
                return
                     

            # --- [B] 全局胜负判定 (多人模式下统计所有人) ---
            # 1. 检查建筑 (非中立)
            alive_teams = set()
            # 1. 检查建筑 (非中立)
            for b in self.all_buildings:
                if b.alive and b.team != "neutral": 
                    alive_teams.add(b.team)
            # 2. 检查单位 (非中立)
            for u in self.all_units:
                if u.alive and u.team != "neutral": 
                    alive_teams.add(u.team)
           
            if self.frame_count > 300 and len(alive_teams) <= 1:
                
                if len(alive_teams) == 0 and self.is_online and len(getattr(self, 'client_id_to_team', {})) > 0:
                    print("[Warning] No alive teams found, waiting for sync...")
                else:
                    self.game_over = True
                    self.state = "GAMEOVER"
                    
                    if len(alive_teams) == 1:
                        self.winner = list(alive_teams)[0]
                    else:
                        self.winner = "DRAW"
                    return # 结束本帧
        for u in self.all_units[:]:
            u.update()
            if not u.alive: self.all_units.remove(u)         
        for b in self.all_buildings[:]:
            b.update()
            
            is_special = False
            if hasattr(b, 'b_type') and b.b_type in ["skyscraper", "temple", "bridge"]: 
                is_special = True
            
            if not b.alive and not is_special: 
                self.all_buildings.remove(b)
                
        for p in self.projectiles[:]:
            p.update()
            if not p.alive: self.projectiles.remove(p)
        
        # 6. 更新特效
        self.particles.update()
        self.floating_texts.update()
        if self.current_map and hasattr(self.current_map, 'update'):
            self.current_map.update()        
        if self.active_alert:
            self.active_alert[1] -= 1
            if self.active_alert[1] <= 0: self.active_alert = None


    def update(self):
        self.check_music_state()      
        if self.state == "LOADING":
            self.update_loading(); return
        
        if self.state == "LOBBY":
            self.lobby_ui.update()
            
            if self.is_online and self.my_role == "CLIENT":
                if not getattr(self, 'sent_join_info', False):
                    info = self.player_info if self.player_info else {"name": "Guest", "uid": -1}
                    self.net.send({"type": "JOIN_REQUEST", "uid": info['uid'], "name": info['name']})
                    self.sent_join_info = True

            if self.is_online:
                msgs = self.net.get_messages()
                for msg in msgs:
                    if msg['type'] == 'CHAT':
                        self.chat_box.add_message(msg['text'], msg.get('name', 'Unknown'), is_self=False)
                    
                    if self.my_role == "HOST":
                        if msg['type'] == 'JOIN_REQUEST':
                            new_name = msg['name']; pid = msg['_sender']
                            exists = False
                            for p in self.lobby_players:
                                if p['id'] == pid: exists = True; break
                            if not exists:
                                self.lobby_players.append({"id": pid, "name": new_name, "ready": False})
                                self.broadcast_lobby_state()
                        
                        elif msg['type'] == 'LOBBY_READY':
                            pid = msg['_sender']
                            for p in self.lobby_players:
                                if p['id'] == pid: p['ready'] = msg['status']; break
                            self.broadcast_lobby_state()
                            
                        elif msg['type'] == 'LOBBY_START':
                            self.net.allow_join = False
                            self.state = "WAITING"
                            
                        elif msg['type'] == 'PLAYER_LEFT':
                            self.lobby_players = [p for p in self.lobby_players if p['id'] != msg['id']]
                            self.broadcast_lobby_state()
                    
                    elif self.my_role == "CLIENT":
                        if msg['type'] == 'LOBBY_STATE':
                            self.lobby_players = msg['players']
                            self.map_id = msg['map_id']
                        elif msg['type'] == 'LOBBY_START':
                            self.state = "WAITING"
            return

        if self.state in ["LOGIN", "MENU", "TUTORIAL", "AUTH"]: return

        # === GAMEOVER ===
        if self.state == "GAMEOVER":
            if self.is_online:
                msgs = self.net.get_messages()
                for msg in msgs:
                    if msg['type'] == 'CHAT':
                        self.chat_box.add_message(msg['text'], msg.get('name', 'Unknown'), is_self=False)
                    elif msg['type'] == 'REMATCH_REQ':
                        self.opponent_wants_rematch = True
                        self.chat_box.add_message("Opponent wants a rematch!", "System")
                        if self.rematch_requested: self.start_rematch()
                    elif self.my_role == "CLIENT" and msg['type'] == 'SETUP':
                        self.handle_setup_packet(msg)
            else:
                pass 
            return 
            
        # === WAITING (HOST 分配队伍) ===
        if self.state == "WAITING":
            if self.is_online and self.my_role == "HOST":
                print("[Host] Starting Game Setup (Multiplayer)...")
                
                seed = random.randint(0, 1000000)
                random.seed(seed)
                
                MapClass = self.maps[self.map_id]
                self.current_map = MapClass(self)
                self.current_map.generate(seed)
                
                lakes_data = []
                if hasattr(self.current_map, 'lakes'):
                    for l in self.current_map.lakes:
                        r = l['rect']
                        lakes_data.append({'rect': (r.x,r.y,r.w,r.h), 'parts': l['parts'], 'type': l.get('type', 'water')})
                
                # [关键修改] 分配 Team 和 阵营
                from core.factions import get_random_faction
                
                # 1. Host 自己
                self.my_team = "team_0"
                fac, _ = get_random_faction()
                self.my_faction = fac # 设置本地属性
                
                self.teams_config = {
                    "team_0": {"name": self.player_info['name'], "faction": fac}
                }
                print(f"[Host Debug] Connected Clients: {list(self.net.clients.keys())}")
                print(f"[Host Debug] Lobby Players: {self.lobby_players}")                
                client_team_map = {} 
                
                for i, p in enumerate(self.lobby_players):
                    team_id = f"team_{i+1}"
                    fac, _ = get_random_faction()
                    
                    self.teams_config[team_id] = {
                        "name": p['name'],
                        "faction": fac
                    }
                    client_team_map[p['id']] = team_id
       
                # [核心修复] 保存映射表到 Game 实例
                self.client_id_to_team = client_team_map
                # 3. 发送 SETUP (单发)
                base_setup = {
                    "type": "SETUP",
                    "map_id": self.map_id,
                    "seed": seed,
                    "lakes_data": lakes_data,
                    "teams_config": self.teams_config
                }
                for pid, tid in client_team_map.items():
                    # 检查 ID 是否匹配
                    if pid in self.net.clients:
                        print(f"[Host] Sending SETUP to {pid} (MATCHED)")
                    else:
                        print(f"[Host] ERROR: {pid} not found in connections!")
                        
                    data = base_setup.copy()                         
                # 遍历所有连接，发送包含 "your_team" 的包
                # (NetworkManager 需要 send_to 方法)
                for pid, tid in client_team_map.items():
                    data = base_setup.copy()
                    data['your_team'] = tid
                    self.net.send_to(pid, data)
                
                self.reset_game()
                self.state = "LOADING"
            
            # Client WAITING
            if self.is_online and self.my_role == "CLIENT":
                msgs = self.net.get_messages()
                for msg in msgs:
                    if msg['type'] == 'SETUP':
                        self.handle_setup_packet(msg)
            return

        # === PLAYING ===
        if self.state == "PLAYING":
            self.current_map.update()
            self.env_manager.update()
            # === 开场动画镜头定位 (见 controllers/camera_mixin.update_opening_camera) ===
            self.update_opening_camera()
            if self.paused and not self.is_online: return

            if not self.is_online:
                if hasattr(self, 'ai_commanders'): 
                    for ai in self.ai_commanders:
                        ai.update()
                elif hasattr(self, 'ai_commander'): # 兼容旧代码
                    self.ai_commander.update()
                
                self.update_game_world()
                
                # [修改] 给所有队伍加钱 (自然增长)
                if hasattr(self, 'team_resources'):
                    for tid in self.team_resources:
                        multiplier = self.lobby_config.get("rate", 0.0)
                        curr = self.team_resources[tid]
                        limit = getattr(self, 'max_cmd_exp', 50000)
                        if curr < limit:
                            self.team_resources[tid] +=multiplier 
            else:
                self.handle_online_playing()
            
            self.sidebar.update()

