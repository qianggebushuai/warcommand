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

class MenuMixin:
    def draw_login(self):

        if self.bg_images:
            # 定义时间参数
            cycle_time = 10000  # 每张图停留总时间 (10秒)
            fade_time = 3000    # 过渡时间 (3秒)
            
            current_time = pygame.time.get_ticks()
            
            # 计算当前索引和下一张索引
            current_idx = (current_time // cycle_time) % len(self.bg_images)
            next_idx = (current_idx + 1) % len(self.bg_images)
            
            # 获取当前周期内的时间进度 (0 ~ 10000)
            time_in_cycle = current_time % cycle_time
            
            # A. 绘制当前底图 (始终不透明，作为背景)
            img_current = self.bg_images[current_idx]
            img_current.set_alpha(255) # 确保不透明
            self.screen.blit(img_current, (0, 0))
            
            # B. 如果进入了最后 3 秒，绘制下一张图 (逐渐变实)
            # 例如：时间到了 7000ms ~ 10000ms
            if time_in_cycle > (cycle_time - fade_time):
                # 计算过渡进度 (0.0 ~ 1.0)
                progress = (time_in_cycle - (cycle_time - fade_time)) / fade_time
                alpha = int(255 * progress) # 0 -> 255
                
                img_next = self.bg_images[next_idx]
                img_next.set_alpha(alpha) # 设置透明度
                self.screen.blit(img_next, (0, 0))
                
        else:
            self.screen.fill((20, 25, 30)) # 没图时的默认色
        if hasattr(self, 'dic_ui'):
            self.dic_ui.draw(self.screen)
        # 2. 绘制左侧半透明侧边栏
        self.screen.blit(self.sidebar_surf, (0, 0))
        
        # 3. 绘制大标题
        title = self.font_header.render("WAR COMMANDER", True, WHITE)
        self.screen.blit(title, (40, 80))
        
        subtitle = self.font_sub.render("INFINITE WAR:CHINA RISING", True, (255, 100, 0)) 
        self.screen.blit(subtitle, (45, 160))
        subtitle = self.font_sub.render("MULTIPLE IS ON UPDATING!", True, (255, 100, 0)) 
        self.screen.blit(subtitle, (45, 190))        
        # 4. 绘制线条装饰
        pygame.draw.line(self.screen, WHITE, (40, 185), (300, 185), 2)
        
        # 5. 更新并绘制按钮
        m_pos = pygame.mouse.get_pos()
        for btn in self.login_buttons:
            btn.check_hover(m_pos)
            btn.draw(self.screen)





        # 6. 显示 IP 输入框
        self.input_ip.draw(self.screen)
        # [新增] 绘制断线提示信息 (在屏幕下方)
        if self.disconnect_message:
            msg_surf = self.ui_font.render(self.disconnect_message, True, RED)
            rect = msg_surf.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT - 80))
            # 画一个黑色背景框让文字更清晰
            bg_rect = rect.inflate(20, 10)
            pygame.draw.rect(self.screen, BLACK, bg_rect)
            pygame.draw.rect(self.screen, RED, bg_rect, 2)
            self.screen.blit(msg_surf, rect)        
        # 7. 底部提示
        ver = self.font.render("v0.8.0 | Press ESC to Quit", True, (100, 100, 100))
        self.screen.blit(ver, (20, SCREEN_HEIGHT - 30))
        self.update_log.draw(self.screen)

        self.setting_ui.draw(self.screen)     
        pygame.display.flip()


    def handle_login_input(self):
        events = pygame.event.get()
        for event in events:

            if event.type == pygame.QUIT: 
                self.running = False
           
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.display.toggle_fullscreen()
            
            self.input_ip.handle_event(event)
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                m_pos = pygame.mouse.get_pos()
                for btn in self.login_buttons:
                    if btn.rect.collidepoint(m_pos):
                        code = btn.action_code
                        
                        # === HOST ===
                        if code == "HOST":
                            self.reset_lobby_data()
                            if self.net.start_host():
                                self.is_online = True
                                self.my_role = "HOST"
                                
                                # [新增] 初始化 Host 身份
                                self.my_team = "team_0"
                                self.teams_config = {} # 将在 WAITING 阶段填充
                                
                                self.map_id = random.randint(0, len(self.maps)-1)
                                print(f"[Host] Selected Map ID: {self.map_id}")
                                self.reset_game()
                                self.state = "LOBBY"
                                
                        # === JOIN ===
                        elif code == "JOIN":
                            self.reset_lobby_data()
                            full_text = self.input_ip.text.strip()
                            target_ip = '127.0.0.1'
                            target_port = 9999
                            if full_text:
                                if ":" in full_text:
                                    try:
                                        parts = full_text.split(":")
                                        target_ip = parts[0]
                                        target_port = int(parts[1])
                                    except: pass
                                else:
                                    target_ip = full_text
                            
                            print(f"Connecting to {target_ip}:{target_port}...")
                            
                            if self.net.connect(target_ip, target_port):
                                self.is_online = True
                                self.my_role = "CLIENT"
                                
                                # [注意] Client 的 my_team 在这里未知，等待 SETUP 包
                                self.my_team = None 
                                
                                self.difficulty = "NORMAL"
                                self.reset_game()
                                self.state = "LOBBY"
                                self.camera_offset = vec(0, 0) # 暂时归零，等收到 SETUP 再定位
                        
                        # === SINGLE ===
                        elif code == "SINGLE":
                            print("[UI] Singleplayer Selected")
                            self.reset_lobby_data()
                            self.is_online = False
                            self.my_role = "HOST" # 单机也是 Host 逻辑
                            self.state = "MENU" 
                            
                            # [关键修复] 设置单机 Team ID
                            self.my_team = "team_0"
                            
                            from core.factions import get_random_faction
                            self.my_faction, _ = get_random_faction()
                            self.enemy_faction, _ = get_random_faction() # AI 阵营
                            
                            # [新增] 初始化单机 Teams Config
                            self.teams_config = {
                                "team_0": {"name": "Player", "faction": self.my_faction},
                                "team_1": {"name": "AI", "faction": self.enemy_faction}
                            }                            
                        # === QUIT ===
                        elif code == "QUIT":
                            self.running = False
                            if self.is_online:
                                try: self.net.stop_hosting()
                                except: pass
            if self.update_log.handle_event(event):
                continue 
            if self.dic_ui.handle_event(event): continue 
            if self.setting_ui.handle_event(event) :continue


    def draw_menu(self):
        # 1. 绘制动态背景 (和 Login 界面一致)
        if self.bg_images:
            # 复用 draw_login 里的淡入淡出逻辑
            cycle_time = 10000
            fade_time = 3000
            current_time = pygame.time.get_ticks()
            
            idx = (current_time // cycle_time) % len(self.bg_images)
            next_idx = (idx + 1) % len(self.bg_images)
            time_in = current_time % cycle_time
            
            img_curr = self.bg_images[idx]
            img_curr.set_alpha(255)
            self.screen.blit(img_curr, (0, 0))
            
            if time_in > (cycle_time - fade_time):
                progress = (time_in - (cycle_time - fade_time)) / fade_time
                alpha = int(255 * progress)
                img_next = self.bg_images[next_idx]
                img_next.set_alpha(alpha)
                self.screen.blit(img_next, (0, 0))
        else:
            self.screen.fill(MENU_BG_COLOR)
            
        # 2. 左侧半透明栏
        self.screen.blit(self.sidebar_surf, (0, 0)) 
        
        # 3. 标题
        title = self.font_header.render("SINGLE PLAYER", True, WHITE)
        self.screen.blit(title, (40, 50))
        
        # 4. 按钮绘制 (战地风格)
        def draw_bf_btn(rect, text, hover):
            # 这里的 rect 已经在 load_resources 里改成左侧对齐了 (x=50)
            color = WHITE if hover else (180, 180, 180)
            # 文字
            txt_surf = self.font_btn.render(text, True, color)
            self.screen.blit(txt_surf, (rect.x + 20, rect.y))
            
            # 选中时的装饰 (左侧橙色竖条)
            if hover:
                pygame.draw.rect(self.screen, ORANGE, (rect.x, rect.y + 5, 5, 30))

        m_pos = pygame.mouse.get_pos()
        
        draw_bf_btn(self.btn_easy, "PVE - EASY", self.btn_easy.collidepoint(m_pos))
        draw_bf_btn(self.btn_normal, "PVE - DEFINE", self.btn_normal.collidepoint(m_pos))
        draw_bf_btn(self.btn_hard, "CAMPAIGN", self.btn_hard.collidepoint(m_pos))
        
        # Bombard 状态
        txt_b = "BOMBARD: ON" if self.bombardment_mode else "BOMBARD: OFF"
        draw_bf_btn(self.btn_bombard, txt_b, self.btn_bombard.collidepoint(m_pos))
        
        draw_bf_btn(self.btn_tutorial, "TUTORIAL", self.btn_tutorial.collidepoint(m_pos))
        draw_bf_btn(self.btn_quit, "BACK TO LOGIN", self.btn_quit.collidepoint(m_pos))
        
        # 5. 阵营选择器 (右下角)
        icon_x = SCREEN_WIDTH - 100
        icon_y = SCREEN_HEIGHT - 100
        
        current_fac = getattr(self, 'my_faction', 'USA')
        if current_fac in self.faction_icons:
            icon = self.faction_icons[current_fac]
            rect = icon.get_rect(center=(icon_x, icon_y))
            self.screen.blit(icon, rect)
            
            self.faction_btn_rect = rect.inflate(10, 10)
            pygame.draw.rect(self.screen, WHITE, self.faction_btn_rect, 2)
            
            txt = self.font.render(f"FACTION: {current_fac}", True, YELLOW)
            # 文字居中对齐图标
            txt_rect = txt.get_rect(center=(icon_x, icon_y + 40))
            self.screen.blit(txt, txt_rect)

        # 6. 图鉴入口 (如果有)
        if hasattr(self, 'dic_ui'):
            self.dic_ui.draw(self.screen)

        pygame.display.flip()


    def draw_tutorial(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.fill((20, 20, 25))
        self.screen.blit(overlay, (0, 0))
        
        lines = [
            "TUTORIAL",
            "- WASD to Move Camera, Scroll to Zoom.",
            "- Left Click to Select Unit, Right Click to Move/Attack.",
            "- Click Base to Build Structures or Recruit Infantry.",
            "- Build Factory for Tanks, Airfield for Aircraft.",
            "- Build Radar for Special Support (AC130, Missile).",
            "- Capture Oil Derricks & Factories for extra resources.",
            "- Research Center unlocks defenses & upgrades.",
            "- Survive and Destroy Enemy Base!",
        ]
        
        for i, line in enumerate(lines):
            color = YELLOW if i == 0 else WHITE
            font = self.title_font if i == 0 else self.ui_font
            surf = font.render(line, True, color)
            rect = surf.get_rect(center=(SCREEN_WIDTH//2, 100 + i*50))
            self.screen.blit(surf, rect)
            
        self.draw_button(self.btn_close_tut, "BACK")
        pygame.display.flip()


    def draw_gameover(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(150)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))        
        cx, cy = SCREEN_WIDTH//2, SCREEN_HEIGHT//2
        
        is_victory = False
        res_text = "DEFEAT"
        res_color = RED                
        
        # [修改] 新的胜负判定逻辑
        # 1. 检查赢家是不是我自己
        if self.winner == self.my_team:
            is_victory = True
            res_text = "VICTORY!"
            res_color = BLUE
            
        # 2. 兼容旧逻辑 ("PLAYER" 通常指 team_0)
        elif self.winner == "PLAYER" and self.my_team == "team_0":
            is_victory = True
            res_text = "VICTORY!"
            res_color = BLUE
            
        # 3. 平局
        elif self.winner == "DRAW":
            res_text = "DRAW!"
            res_color = YELLOW
            
        else:
            # 输了，尝试显示是谁赢了
            if self.winner and self.winner.startswith("team_"):
                # 如果有 config，显示名字
                winner_name = self.winner
                if self.winner in self.teams_config:
                    winner_name = self.teams_config[self.winner].get('name', self.winner)
                res_text = f"{winner_name} WINS!"
            
        title = self.title_font.render(res_text, True, res_color)
        t_rect = title.get_rect(center=(cx, cy - 100))
        self.screen.blit(title, t_rect)
        
        if self.is_online:
            label = "REQUEST REMATCH"
            if getattr(self, 'rematch_requested', False):
                label = "WAITING..."
            if getattr(self, 'opponent_wants_rematch', False):
                label = "ACCEPT REMATCH!" # 对方点了，我这里变绿
                
            self.draw_button(self.btn_restart, label)
        else:
            self.draw_button(self.btn_restart, "RESTART")
            

        self.draw_button(self.btn_quit, "QUIT")
        pygame.display.flip()


    def handle_menu_click(self, screen_m_pos, screen_center_pos):
        c = vec(screen_center_pos)
        world_center = self.selected_entity.pos
        my_team = self.my_team       
        # --- 内部辅助函数 ---
        def check(off_x, off_y, cost, action_type, payload):

            btn_r = pygame.Rect(c.x + off_x - 20, c.y + off_y - 20, 40, 40)
            
            if btn_r.collidepoint(screen_m_pos):
                # UI 逻辑
                if action_type == "UI":
                    if payload == "recruit": self.base_menu_mode = "recruit"
                    elif payload == "main": self.base_menu_mode = "main"
                    return True
                
                # 建造逻辑 (检查电力)
                if action_type == "BUILD_MODE":
                    # [新增] 电力检查
                    # 只有房主或单机才检查，客户端由服务器判断
                    if self.my_role == "HOST" or not self.is_online:
                        if payload != "power_plant" and self.current_voltage + POWER_COST > self.max_voltage:
                            self.show_alert("LOW POWER!")
                            return True # 拦截，不进入建造模式
                    
                    self.place_building_type = payload
                    return True

                # === 游戏操作同步逻辑 ===
                
                # [分支 1] 客户端
                # [分支 1] 客户端
                if self.is_online and self.my_role == "CLIENT":
                    if action_type == "SPAWN":
                        self.net.send({
                            "type": "REQ_SPAWN", 
                            "u_type": payload, 
                            "b_uid": self.selected_entity.uid, # [修改] 加入建筑 ID
                            "x": int(world_center.x), 
                            "y": int(world_center.y)
                        })
                        return True
                    elif action_type == "UPGRADE":
                        self.net.send({"type": "REQ_UPGRADE", "tech": payload, "uid": self.selected_entity.uid})
                        return True
                    elif action_type == "SUPPORT":
                        if payload == "ac130": self.call_airstrike_mode = True
                        elif payload == "missile": self.call_missile_mode = True
                        elif payload == "airdrop": self.call_airdrop_mode = True 
                        return True
                    if action_type == "ACTION" and payload == "undeploy":
                        self.net.send({"type": "REQ_UNDEPLOY", "uid": self.selected_entity.uid})
                        return True
                # [分支 2] 房主 / 单机
                else:
                    # 支援技能
                    if action_type == "SUPPORT":
                        if payload == "ac130": self.call_airstrike_mode = True
                        elif payload == "missile": self.call_missile_mode = True
                        elif payload == "airdrop": self.call_airdrop_mode = True 
                        return True
                    mymoney=self.team_resources[my_team]
                    # 建造/升级/造兵需要立刻扣钱
                    if cost > 0 and   mymoney< cost: return True
                    
                    # [新增] 造兵队列逻辑
                    if action_type == "SPAWN":
                        # 检查队列是否已满
                        if hasattr(self.selected_entity, 'queue_unit'):
                            # 根据兵种决定时间
                            time_cost = BUILD_TIME_INFANTRY
                            if payload in ["armored", "m1a2", "mech"]: time_cost = BUILD_TIME_TANK
                            elif payload in ["helicopter", "wz10", "kirov", "plane"]: time_cost = BUILD_TIME_AIR
                            
                            # 尝试加入队列，如果成功才扣钱
                            if self.selected_entity.queue_unit(payload, time_cost):
                                if cost > 0:  mymoney-= cost
                            else:
                                self.show_alert("QUEUE FULL")
                        else:
                            # 兼容旧逻辑(如基地直接招募步兵可能没队列)
                            if cost > 0: self.cmd_exp -= cost
                            team = "player"
                            self.spawn_unit(payload, world_center, team)
                    
                    elif action_type == "UPGRADE":
                        if cost > 0: mymoney -= cost
                        # 处理特殊升级
                        if payload == "airfield_unlock" or payload == "factory_unlock":
                            self.selected_entity.is_upgraded = True
                        else:
                            self.upgrade_tech(payload)
                    
                    return True
            return False

        # --- 卖出按钮 ---
        btn_r = pygame.Rect(c.x - 15, c.y - 15, 30, 30)
        if btn_r.collidepoint(screen_m_pos):
            b_type = self.selected_entity.b_type
            # 加上 power_plant 的退款
            cost_map = {"factory": FACTORY_COST, "radar": RADAR_COST, "mining": MINING_COST, 
                        "airfield": AIRFIELD_COST, "research": RESEARCH_COST, 
                        "missile_def": MISSILE_DEFENSE_COST, "aa_turret": AA_TURRET_COST,
                        "laser_turret": LASER_TURRET_COST, "power_plant": POWER_PLANT_COST, "shroud_gen":BLACKSHRODCOST,"base": 2500 ,"ciws":CIWS_COST}
            
            base_cost = cost_map.get(b_type, 0)
            refund = int(base_cost * REFUND_RATE)
            
            if self.is_online and self.my_role == "CLIENT":
                self.net.send({"type": "REQ_SELL", "uid": self.selected_entity.uid, "refund": refund})
            else:
                self.team_resources[my_team] += refund
                self.selected_entity.alive = False
                self.particles.add(FloatingText(self.selected_entity.pos, f"+{refund}", YELLOW))
            
            self.selected_entity = None
            return True

        # --- 各建筑菜单配置 (保持你原有的配置) ---

        # 1. 基地 (加一个电站建造按钮)
        if self.selected_entity.b_type == "base":
            if self.base_menu_mode == "main":
                # --- 使用环形布局坐标 ---
                # 1. 兵营 (上) -> (0, -80)
                if check(0, -80, 0, "UI", "recruit"): return True
                
                # 2. 工厂 (右上) -> (70, -40)
                if check(70, -40, 100, "BUILD_MODE", "factory"): return True
                
                # 3. 机场 (右下) -> (70, 40)
                if check(70, 40, AIRFIELD_COST, "BUILD_MODE", "airfield"): return True
                
                # 4. 雷达 (下) -> (0, 80)
                if check(0, 80, RADAR_COST, "BUILD_MODE", "radar"): return True
                
                # 5. 电站 (左下) -> (-70, 40)
                if check(-70, 40, POWER_PLANT_COST, "BUILD_MODE", "power_plant"): return True
                
                # 6. 矿场 (左上) -> (-70, -40)
                if check(-70, -40, MINING_COST, "BUILD_MODE", "mining"): return True
                
                # 7. 科研 (正左) -> (-90, 0)
                if check(-90, 0, RESEARCH_COST, "BUILD_MODE", "research"): return True

                if check(90, 0, 500, "BUILD_MODE", "shipyard"): return True
                if check(0, -120, 0, "ACTION", "undeploy"):
                    self.selected_entity.undeploy()
                    self.selected_entity = None # 取消选中
                    return True                
            elif self.base_menu_mode == "recruit":
                if check(-60, 0, RIFLEMAN_COST, "SPAWN", "rifleman"): return True
                if check(60, 0, ROCKET_COST, "SPAWN", "rocket"): return True
                if check(0, -60, 0, "UI", "main"): return True

        # 2. 工厂
        elif self.selected_entity.b_type == "factory":
            if check(0, -80, ARMORED_COST, "SPAWN", "armored"): return True
            if check(80, -20, M1A2_COST, "SPAWN", "m1a2"): return True
            if check(60, 60, 500, "SPAWN", "combat_engineer"): return True
            
            # [新增] APC 
            if check(-80, -20, 500, "SPAWN", "apc"): return True            
            if not getattr(self.selected_entity, 'is_upgraded', False):
                if self.is_online and self.my_role == "CLIENT":
                    btn_r = pygame.Rect(c.x - 60 - 20, c.y + 60 - 20, 40, 40)
                    if btn_r.collidepoint(screen_m_pos):
                        self.net.send({"type": "REQ_UPGRADE", "tech": "factory_unlock", "uid": self.selected_entity.uid})
                        return True
                else:
                    if check(-60, 60, UPGRADE_FACTORY_COST, "UPGRADE", "factory_unlock"): 
                        self.selected_entity.is_upgraded = True 
                        return True
            else:
                if check(-60, 60, SNIPER_COST, "SPAWN", "sniper"): return True
                if check(0, 80, MECH_COST, "SPAWN", "mech"): return True

        # 3. 机场
        elif self.selected_entity.b_type == "airfield":
            if check(0, -80, HELICOPTER_COST, "SPAWN", "helicopter"): return True
            if check(60, -20, WZ10_COST, "SPAWN", "wz10"): return True
            
            if not getattr(self.selected_entity, 'is_upgraded', False):
                if self.is_online and self.my_role == "CLIENT":
                    btn_r = pygame.Rect(c.x - 60 - 20, c.y + 60 - 20, 40, 40)
                    if btn_r.collidepoint(screen_m_pos):
                        self.net.send({"type": "REQ_UPGRADE", "tech": "airfield_unlock", "uid": self.selected_entity.uid})
                        return True
                else:
                    if check(-60, 60, UPGRADE_AIRFIELD_COST, "UPGRADE", "airfield_unlock"): 
                        self.selected_entity.is_upgraded = True 
                        return True
            else:
                my_team = self.my_team
                if self.has_tech_center(my_team):
                    if check(-60, 60, KIROV_COST, "SPAWN", "kirov"): return True
        elif self.selected_entity.b_type == "shipyard":
            # 导弹艇造价假设 600
            if check(0, 60, 600, "SPAWN", "missile_boat"): return True
        # 4. 雷达
        elif self.selected_entity.b_type == "radar":
            if check(0, -80, AC130_COST, "SUPPORT", "ac130"): return True
            if check(0, 80, MISSILE_COST, "SUPPORT", "missile"): return True
            if check(-80, 0, AIRDROP_COST, "SUPPORT", "airdrop"): return True

        # 5. 科研中心
        elif self.selected_entity.b_type == "research":
            if check(0, -80, MISSILE_DEFENSE_COST, "BUILD_MODE", "missile_def"): return True
            if check(80, -20, AA_TURRET_COST, "BUILD_MODE", "aa_turret"): return True
            if check(-80, -20, LASER_TURRET_COST, "BUILD_MODE", "laser_turret"): return True
            if check(-60, 60, UPGRADE_INFANTRY_COST, "UPGRADE", "infantry"): return True
            if check(0, 80, UPGRADE_ARMOR_COST, "UPGRADE", "armor"): return True
            if check(60, 60, UPGRADE_AIR_COST, "UPGRADE", "air"): return True
            
        return False

