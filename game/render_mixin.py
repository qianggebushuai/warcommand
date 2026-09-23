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

class RenderMixin:
    def show_alert(self, text, duration=180):
        # 本地显示
        self.active_alert = [text, duration]
        
        # 如果是房主，且在线，放入广播队列
        if self.is_online and self.my_role == "HOST":
            if not hasattr(self, 'broadcast_msgs'): self.broadcast_msgs = []
            self.broadcast_msgs.append(text) 


    def draw_button(self, rect, text, hover_color=(100,100,100), normal_color=(50,50,50)):
        m_pos = pygame.mouse.get_pos()
        color = hover_color if rect.collidepoint(m_pos) else normal_color
        pygame.draw.rect(self.screen, color, rect)
        pygame.draw.rect(self.screen, WHITE, rect, 2)
        txt_surf = self.ui_font.render(text, True, WHITE)
        txt_rect = txt_surf.get_rect(center=rect.center)
        self.screen.blit(txt_surf, txt_rect)
        return rect.collidepoint(m_pos)


    def draw_world_elements(self):
        # 1. 绘制背景
        self.screen.fill(GRASS_COLOR)
        view_rect = pygame.Rect(self.camera_offset.x, self.camera_offset.y, SCREEN_WIDTH/self.zoom, SCREEN_HEIGHT/self.zoom)
        safe_x = max(0, int(view_rect.x))
        safe_y = max(0, int(view_rect.y))
        safe_w = min(WORLD_WIDTH - safe_x, int(view_rect.width) + 1)
        safe_h = min(WORLD_HEIGHT - safe_y, int(view_rect.height) + 1)
        if safe_w > 0 and safe_h > 0:
            sub_bg = self.bg_surface.subsurface((safe_x, safe_y, safe_w, safe_h))
            scaled_bg = pygame.transform.scale(sub_bg, (int(safe_w * self.zoom), int(safe_h * self.zoom)))
            screen_x = int((safe_x - self.camera_offset.x) * self.zoom)
            screen_y = int((safe_y - self.camera_offset.y) * self.zoom)
            self.screen.blit(scaled_bg, (screen_x, screen_y))

        # 2. 绘制实体
        for b in self.all_buildings: 
            b.draw(self.screen, self.camera_offset, self.zoom)
            
            # --- 【新增功能】绘制建造/生产进度条 ---
            # 获取进度 (兼容本地单机模式的 spawn_timer 和 联机模式的 progress)
            prog = 0.0
            if hasattr(b, 'progress'): # 客户端联机数据
                prog = b.progress
            elif hasattr(b, 'spawn_timer') and hasattr(b, 'build_time_total') and b.build_time_total > 0: # 主机/单机本地数据
                prog = b.spawn_timer / b.build_time_total
            
            # 如果有进度，画条
            if prog > 0:
                # 转换坐标
                screen_pos = to_screen(b.pos, self.camera_offset, self.zoom)
                bar_w = scale(60, self.zoom)
                bar_h = scale(8, self.zoom)
                # 稍微向上偏移，避免挡住建筑
                bar_x = screen_pos[0] - bar_w // 2
                bar_y = screen_pos[1] - scale(50, self.zoom) 
                
                # 画黑底
                pygame.draw.rect(self.screen, BLACK, (bar_x, bar_y, bar_w, bar_h))
                # 画进度 (绿色)
                fill_w = int(bar_w * prog)
                pygame.draw.rect(self.screen, (0, 255, 0), (bar_x, bar_y, fill_w, bar_h))
                # 画白框
                pygame.draw.rect(self.screen, WHITE, (bar_x, bar_y, bar_w, bar_h), 1)

        # 3. 选中与菜单 [关键修改]
        if self.selected_entity and self.selected_entity.alive:
            spos = to_screen(self.selected_entity.pos, self.camera_offset, self.zoom)
            srad = scale(self.selected_entity.radius + 10, self.zoom)
            pygame.draw.circle(self.screen, YELLOW, spos, srad, 2)
            
            # --- 修改开始 ---
            # 动态判断：如果是客户端，我控制 enemy；否则我控制 player
            my_control_team =self.my_team
            
            # 只有选中的是【我方控制的建筑】时，才画菜单
            # 原代码是: if self.selected_entity.team == "player" ... (这就导致红方不显示)
            if isinstance(self.selected_entity, Building) and self.selected_entity.team == my_control_team:
                self.draw_building_menu(self.selected_entity)
            # --- 修改结束 ---

        # 4. 建造预览
        if self.place_building_type:
            m_screen_pos = pygame.mouse.get_pos()
            
            # [修改] 统一逻辑：寻找连线起点
            base_ref = None
            
            # 优先用 player_base (我的基地)
            if self.player_base and self.player_base.alive:
                base_ref = self.player_base
            else:
                # 基地没了，找任意一个属于我方且活着的建筑
                for b in self.all_buildings:
                    if b.team == self.my_team and b.alive:
                        base_ref = b
                        break
            
            if base_ref:
                base_screen_pos = to_screen(base_ref.pos, self.camera_offset, self.zoom)
                pygame.draw.line(self.screen, (255, 255, 0, 100), base_screen_pos, m_screen_pos, 1)
            
            # 简单的预览文字
            txt = self.font.render(f"Build: {self.place_building_type}", True, WHITE)
            self.screen.blit(txt, (m_screen_pos[0]+20, m_screen_pos[1]+20))

        # 5. 瞄准光标
        if self.call_airstrike_mode:
            m_pos = pygame.mouse.get_pos()
            pygame.draw.circle(self.screen, RED, m_pos, int(AC130_ORBIT_RADIUS * self.zoom), 1)
            t = self.font.render("AC-130 Target", True, RED)
            self.screen.blit(t, (m_pos[0]+10, m_pos[1]))
        if self.call_missile_mode:
            m_pos = pygame.mouse.get_pos()
            pygame.draw.circle(self.screen, ORANGE, m_pos, int(40 * self.zoom), 2)
            pygame.draw.line(self.screen, ORANGE, (m_pos[0]-10, m_pos[1]), (m_pos[0]+10, m_pos[1]), 2)
            pygame.draw.line(self.screen, ORANGE, (m_pos[0], m_pos[1]-10), (m_pos[0], m_pos[1]+10), 2)
            t = self.font.render("Missile Target", True, ORANGE)
            self.screen.blit(t, (m_pos[0]+10, m_pos[1]))


    def draw_ui(self):
        self.chat_box.draw(self.screen)
        self.sidebar.draw(self.screen)
        self.minimap.draw(self.screen)        
        # 暂停图标
        pause_color = YELLOW if self.paused else WHITE
        pygame.draw.rect(self.screen, UI_BG, self.btn_pause)
        pygame.draw.rect(self.screen, pause_color, (self.btn_pause.x + 10, self.btn_pause.y + 10, 8, 20))
        pygame.draw.rect(self.screen, pause_color, (self.btn_pause.x + 22, self.btn_pause.y + 10, 8, 20))
        
        UI_OFFSET_X = 230         
        
        # === 2. 经验条 / 资源条 ===
        bar_x = UI_OFFSET_X + 10
        # 获取当前资金 (兼容单机和多人)
        # 如果是单机/旧版，可能还在用 cmd_exp
        # 如果是多人，用 team_resources
        current_money = 0
        if hasattr(self, 'team_resources') and self.my_team in self.team_resources:
            current_money = self.team_resources[self.my_team]
            
        # 背景框
        pygame.draw.rect(self.screen, BLACK, (bar_x, 10, 300, 20))
        # 进度条
        fill_width = (current_money / self.max_cmd_exp) * 300
        pygame.draw.rect(self.screen, MARKER_BLUE, (bar_x, 10, fill_width, 20))
        pygame.draw.rect(self.screen, WHITE, (bar_x, 10, 300, 20), 2)
        # 文字
        exp_text = self.font.render(f"FUNDS: {int(current_money)}", True, WHITE)
        self.screen.blit(exp_text, (bar_x + 310, 10))

        # === 3. 电力条 ===
        # 电力在 update_game_world 里已经根据 my_team 算好了，直接用
        pwr_y = 35
        pct = min(1.0, self.current_voltage / self.max_voltage) if self.max_voltage > 0 else 1.0
        pygame.draw.rect(self.screen, BLACK, (bar_x, pwr_y, 300, 10))
        color = YELLOW if pct < 0.9 else RED
        pygame.draw.rect(self.screen, color, (bar_x, pwr_y, 300 * pct, 10))
        pygame.draw.rect(self.screen, WHITE, (bar_x, pwr_y, 300, 10), 1)
        
        txt = self.info_font.render(f"PWR: {self.current_voltage}/{self.max_voltage}", True, WHITE)
        self.screen.blit(txt, (bar_x + 310, pwr_y - 2))   
        # [修改] 暂停菜单逻辑
        if self.paused:
            # 1. 半透明遮罩
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            overlay.set_alpha(150)
            overlay.fill(BLACK)
            self.screen.blit(overlay, (0, 0))

            # 2. 暂停文字
            txt = self.title_font.render("GAME PAUSED", True, YELLOW)
            rect = txt.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 50))
            self.screen.blit(txt, rect)
            
            # 3. 绘制退出按钮
            self.draw_button(self.btn_resume, "RESUME")
            self.draw_button(self.btn_ingame_exit, "EXIT TO LOGIN")
            self.draw_button(self.btn_vol_down, "-")
            self.draw_button(self.btn_vol_up, "+")
            
            # 显示当前音量
            vol_str = f"VOL: {int(self.master_volume * 100)}%"
            t = self.ui_font.render(vol_str, True, WHITE)
            self.screen.blit(t, t.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 140)))
            return # 暂停时不绘制其他UI        
        if self.show_info_panel:
            panel_rect = pygame.Rect(10, 70, 250, 180) 
            s = pygame.Surface((250, 180))
            s.set_alpha(220)
            s.fill(BLACK)
            self.screen.blit(s, (10, 70))
            pygame.draw.rect(self.screen, WHITE, panel_rect, 1)
            lines = [
                "Unit Stats (HP | Dmg)",
                f"Rifle: {RIFLEMAN_STATS[2]} | {DMG_RIFLE}",
                f"Rocket:{ROCKET_STATS[2]} | {DMG_ROCKET}",
                f"Tank:  {ARMORED_STATS[2]} | {DMG_ARMORED}x3",
                f"Heli:  {HELICOPTER_STATS[2]} | {DMG_HELICOPTER}",
                f"M1A2:  {M1A2_STATS[2]} | {DMG_M1A2}",
            ]
            for i, line in enumerate(lines):
                t = self.info_font.render(line, True, WHITE)
                self.screen.blit(t, (15, 75 + i * 20))

        if self.active_alert:
            alert_surf = self.alert_font.render(self.active_alert[0], True, RED)
            rect = alert_surf.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//4))
            if (pygame.time.get_ticks() // 500) % 2 == 0:
                self.screen.blit(alert_surf, rect)
        if self.my_faction and self.my_faction in self.faction_icons:
            icon = self.faction_icons[self.my_faction]
            # 侧边栏宽 220，放在 230, SCREEN_HEIGHT - 50
            self.screen.blit(icon, (230, SCREEN_HEIGHT - 50))
            
            # 也可以画个框
            pygame.draw.rect(self.screen, WHITE, (230, SCREEN_HEIGHT - 50, 60, 40), 2)


    def draw_world(self):
        # 1. 绘制背景 (纹理)
        if self.current_map:
            self.current_map.draw_background(self.screen, self.camera_offset, self.zoom)
            if hasattr(self.current_map, 'draw_overlay'):
                self.current_map.draw_downlay(self.screen, (self.camera_offset.x * self.zoom, self.camera_offset.y * self.zoom))
        else:
            self.screen.fill((30, 34, 30))

        # 2. 绘制额外的水面层 (用于覆盖在背景之上，或者动态效果)
        for lake in self.lakes:
            l_type = lake.get('type', 'water') # 默认为水
            
            if l_type == 'water':
                
                if lake.get('parts'): 
                    for part in lake['parts']:
                        ox, oy, w, h = part
                        center_screen = to_screen(vec(ox, oy), self.camera_offset, self.zoom)
                        sw = int(scale(w, self.zoom))
                        sh = int(scale(h, self.zoom))
                        
                        # 屏幕外剔除
                        if not (-sw < center_screen[0] < SCREEN_WIDTH+sw and -sh < center_screen[1] < SCREEN_HEIGHT+sh):
                            continue

                        rect = pygame.Rect(center_screen[0]-sw//2, center_screen[1]-sh//2, sw, sh)
                        
                        # 绘制
                        if isinstance(self.current_map, WildernessMap):
                            # 荒野地图：实心蓝
                            pygame.draw.ellipse(self.screen, (60, 120, 200), rect)
                        else:
                            pass 


        if self.current_map:
            self.current_map.update_effects(self)

        # 3. 绘制建筑 
        for b in self.all_buildings: 
            b.draw(self.screen, self.camera_offset, self.zoom)
            
            prog = 0.0
            
            if self.is_online and self.my_role == "CLIENT":
                if hasattr(b, 'progress'): prog = b.progress
            else:
                if hasattr(b, 'current_production') and b.current_production:
                    total = b.current_production['total_time']
                    current = b.current_production['timer']
                    if total > 0:
                        prog = (total - current) / total
            
            # 3. 绘制进度条
            if prog > 0:
                screen_pos = to_screen(b.pos, self.camera_offset, self.zoom)
                bar_w = scale(60, self.zoom)
                bar_h = scale(8, self.zoom)
                # 位置: 建筑上方 50 像素
                bar_x = screen_pos[0] - bar_w // 2
                bar_y = screen_pos[1] - scale(50, self.zoom) 
                
                # 黑底
                pygame.draw.rect(self.screen, BLACK, (bar_x, bar_y, bar_w, bar_h))
                # 绿条
                fill_w = int(bar_w * prog)
                pygame.draw.rect(self.screen, (0, 255, 0), (bar_x, bar_y, fill_w, bar_h))
                # 白框
                pygame.draw.rect(self.screen, WHITE, (bar_x, bar_y, bar_w, bar_h), 1)
        for u in self.all_units:
            if u.is_air:
                spos = to_screen(u.pos, self.camera_offset, self.zoom)
                sw = scale(20, self.zoom)
                sh = scale(10, self.zoom)
                offset_y = 50 if isinstance(u, (AC130, KirovAirship, CruiseMissile)) else 30
                pygame.draw.ellipse(self.screen, (0,0,0,100), (spos[0]-sw//2, spos[1]+scale(offset_y, self.zoom), sw, sh))
        ground_units = [u for u in self.all_units if not u.is_air]
        air_units = [u for u in self.all_units if u.is_air]
        fixed_wings = [u for u in self.all_units if getattr(u, 'is_fixed_wing', False)]        
        for u in ground_units: 
            u.draw(self.screen, self.camera_offset, self.zoom)

        if self.current_map and hasattr(self.current_map, 'overlay_surface'):
            self.current_map.draw_overlay(self.screen, self.camera_offset, self.zoom)  

        for u in air_units: 
            u.draw(self.screen, self.camera_offset, self.zoom)
            
        for p in self.projectiles: p.draw(self.screen, self.camera_offset, self.zoom)
        for p in self.particles: p.draw(self.screen, self.camera_offset, self.zoom)
        for t in self.floating_texts: t.draw(self.screen, self.camera_offset, self.zoom)

        for u in fixed_wings:
            if u.alive:
                u.draw(self.screen, self.camera_offset, self.zoom)

        shroud_active = False
        for b in self.all_buildings:
            if b.alive and getattr(b, 'b_type', '') == 'shroud_gen' and b.team != self.my_team:
                shroud_active = True; break
        
        if shroud_active:
            self.draw_shroud()

        if self.selected_entity and self.selected_entity.alive:
            spos = to_screen(self.selected_entity.pos, self.camera_offset, self.zoom)
            srad = scale(self.selected_entity.radius + 10, self.zoom)
            pygame.draw.circle(self.screen, YELLOW, spos, srad, 2)
            my_team =self.my_team
            
            # 只有选中的是【我方建筑】时，才绘制菜单
            if isinstance(self.selected_entity, Building) and self.selected_entity.team == my_team:
                self.draw_building_menu(self.selected_entity)
        for line in self.command_lines[:]:
            start, end, timer = line
            # 计算屏幕坐标
            s_start = to_screen(start, self.camera_offset, self.zoom)
            s_end = to_screen(end, self.camera_offset, self.zoom)
            
            # 随着时间变淡或变细
            alpha = int(255 * (timer / 60))
            color = (0, 255, 0, alpha) # 绿色
            
            # Pygame draw.line 不支持 alpha，需要用 Surface
            # 这里简单画一条变细的线
            width = max(1, int(3 * (timer / 60)))
            pygame.draw.line(self.screen, (0, 255, 0), s_start, s_end, width)
            
            # 画个小叉或圈在终点
            if timer > 50: # 刚开始显示一下终点标记
                pygame.draw.circle(self.screen, (0, 255, 0), s_end, 5, 1)

            line[2] -= 1
            if line[2] <= 0:
                self.command_lines.remove(line)
        if self.place_building_type == "cruiser_missile":
            m_pos = pygame.mouse.get_pos()
            
            # 画一个大红圈 (半径 150)
            radius = int(150 * self.zoom)
            
            # 1. 范围指示 (半透明红)
            s = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 0, 0, 50), (radius, radius), radius)
            pygame.draw.circle(s, (255, 0, 0), (radius, radius), radius, 2) # 边框
            
            # 2. 十字准星
            pygame.draw.line(s, (255, 0, 0), (radius-20, radius), (radius+20, radius), 2)
            pygame.draw.line(s, (255, 0, 0), (radius, radius-20), (radius, radius+20), 2)
            
            self.screen.blit(s, (m_pos[0]-radius, m_pos[1]-radius))
            
            txt = self.font.render("LEFT CLICK TO LAUNCH", True, RED)
            self.screen.blit(txt, (m_pos[0]+20, m_pos[1]+20))
        if self.place_building_type == "skill_iron_curtain":
            m_pos = pygame.mouse.get_pos()
            
            # 半径 100 (根据 zoom 缩放)
            # 注意: activate 里的逻辑半径是 150，这里最好保持一致，或者稍微小一点表示核心区
            # 如果逻辑是 150，这里最好也画 150。你要求画 100，那就按 100 画。
            radius = int(100 * self.zoom)
            
            # 1. 范围指示 (半透明红)
            s = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
            # 填充: 红色半透明
            pygame.draw.circle(s, (255, 50, 50, 60), (radius, radius), radius)
            # 边框: 亮红
            pygame.draw.circle(s, (255, 100, 100), (radius, radius), radius, 2)
            
            # 2. 铁幕网格特效 (Grid Effect)
            # 画几条经纬线，模拟球体护盾感
            pygame.draw.ellipse(s, (255, 50, 50), (0, radius//2, radius*2, radius), 1)
            pygame.draw.line(s, (255, 50, 50), (radius, 0), (radius, radius*2), 1)
            
            self.screen.blit(s, (m_pos[0]-radius, m_pos[1]-radius))
            
            # 3. 提示文字
            txt = self.font.render("IRON CURTAIN READY", True, (255, 100, 100))
            self.screen.blit(txt, (m_pos[0]+20, m_pos[1]+20))
        if getattr(self.current_map, 'name', '') == "VERDUN HEIGHTS":
            # 1. 飘过的浓烟 (Smoke Drifts)
            if self.frame_count % 10 == 0:
                # 随机生成一些半透明的深灰色粒子，随风飘动
                sx = random.randint(0, WORLD_WIDTH)
                sy = random.randint(0, WORLD_HEIGHT)
                # 利用 Particle 系统
                # 颜色 (50, 50, 50, 50)，速度慢，寿命长，大尺寸
                Particle(self.particles, vec(sx, sy), (50, 50, 50, 100), 0.5, 300, random.randint(50, 100))
            
            # 2. 地面余烬 (Embers) - 向上飘的小火星
            if self.frame_count % 5 == 0:
                ex = self.camera_offset.x + random.randint(0, 1000)
                ey = self.camera_offset.y + random.randint(0, 1000)
                # 橙色/黄色，向上飘，寿命短
                p = Particle(self.particles, vec(ex, ey), (255, 100, 0), 1.0, 60, 2)
                p.vel = vec(random.uniform(-0.5, 0.5), -1) # 向上
        elif getattr(self.current_map, 'name', '') == "DRAGON VALLEY":

            # 2. 萤火虫 (Fireflies) - 绿色/青色微光
            if self.frame_count % 4 == 0:
                fx = self.camera_offset.x + random.randint(0, 1300)
                fy = self.camera_offset.y + random.randint(0, 800)
                
                # 随机荧光色 (绿、青、黄绿)
                color = random.choice([(100, 255, 100), (50, 255, 200), (200, 255, 150)])
                
                # 小尺寸，寿命中等
                p = Particle(self.particles, vec(fx, fy), color, 0.5, 90, random.randint(2, 4))
                # 随机无规则漫游速度
                p.vel = vec(random.uniform(-0.6, 0.6), random.uniform(-0.6, 0.6))

        for u in self.multi_selected_units:
            if u.alive:
                spos = to_screen(u.pos, self.camera_offset, self.zoom)
                # 画两层圈，更有质感
                pygame.draw.circle(self.screen, YELLOW, spos, scale(u.radius + 5, self.zoom), 1)
                pygame.draw.circle(self.screen, (255, 255, 100), spos, scale(u.radius + 7, self.zoom), 1)

        if self.selection_rect and pygame.mouse.get_pressed()[0]: # 只有左键按住时才画
            # 这里的 rect 是屏幕坐标，直接画
            pygame.draw.rect(self.screen, (0, 255, 0), self.selection_rect, 1)
            # 半透明填充
            s = pygame.Surface((self.selection_rect.width, self.selection_rect.height), pygame.SRCALPHA)
            s.fill((0, 255, 0, 50)) # 淡淡的绿色填充
            self.screen.blit(s, (self.selection_rect.x, self.selection_rect.y))
        # 4. 建造预览
        if self.place_building_type:
            m_screen_pos = pygame.mouse.get_pos()
            
            # [修改] 统一寻找连线起点 (优先用 player_base，没有就找任意我方建筑)
            base_ref = None
            
            if self.player_base and self.player_base.alive:
                base_ref = self.player_base
            else:
                # 基地没了，找个别的建筑连线 (比如工厂)
                for b in self.all_buildings:
                    if b.team == self.my_team and b.alive:
                        base_ref = b
                        break
            
            # 绘制连线
            if base_ref:
                base_screen_pos = to_screen(base_ref.pos, self.camera_offset, self.zoom)
                pygame.draw.line(self.screen, (255, 255, 0, 100), base_screen_pos, m_screen_pos, 1)



            # 简单的预览文字
            txt = self.font.render(f"Build: {self.place_building_type}", True, WHITE)
            self.screen.blit(txt, (m_screen_pos[0]+20, m_screen_pos[1]+20))
        self.env_manager.draw(self.screen)
        # 5. 瞄准光标
        if self.call_airstrike_mode:
            m_pos = pygame.mouse.get_pos()
            pygame.draw.circle(self.screen, RED, m_pos, int(AC130_ORBIT_RADIUS * self.zoom), 1)
            t = self.font.render("AC-130 Target", True, RED)
            self.screen.blit(t, (m_pos[0]+10, m_pos[1]))
        if self.call_missile_mode:
            m_pos = pygame.mouse.get_pos()
            pygame.draw.circle(self.screen, ORANGE, m_pos, int(40 * self.zoom), 2)
            t = self.font.render("Missile Target", True, ORANGE)
            self.screen.blit(t, (m_pos[0]+10, m_pos[1]))
        if self.call_airdrop_mode:
            m_pos = pygame.mouse.get_pos()
            # 画个绿色同心圆
            pygame.draw.circle(self.screen, (0, 255, 0), m_pos, 30, 2)
            pygame.draw.circle(self.screen, (0, 255, 0), m_pos, 10, 1)
            t = self.font.render("Airdrop Zone", True, (0, 255, 0))
            self.screen.blit(t, (m_pos[0]+10, m_pos[1]))


    def draw_shroud(self):
        sw, sh = self.screen.get_size()
        mini_w, mini_h = sw // 10 + 1, sh // 10 + 1
        
        # 1. 创建黑雾层 (初始全透明)
        fog_surf = pygame.Surface((mini_w, mini_h), pygame.SRCALPHA)
        fog_surf.fill((0, 0, 0, 0))
        
        scale_factor = self.zoom / 10.0
        shroud_radius = 1500
        
        for b in self.all_buildings:
            if b.alive and getattr(b, 'b_type', '') == 'shroud_gen' and b.team != self.my_team:
                sp = to_screen(b.pos, self.camera_offset, self.zoom)
                
                # 剔除屏幕外的
                if -1000 < sp[0] < sw+1000 and -1000 < sp[1] < sh+1000:
                    mp = (int(sp[0]/10), int(sp[1]/10))
                    r = int(shroud_radius * scale_factor)
                    pygame.draw.circle(fog_surf, (0, 0, 0, 255), mp, r)

        vision_surf = pygame.Surface((mini_w, mini_h), pygame.SRCALPHA)
        vision_surf.fill((0, 0, 0, 0))
        
        vision_radius = 300 
        
        # 单位视野
        for u in self.all_units:
            if u.alive and u.team == self.my_team:
                sp = to_screen(u.pos, self.camera_offset, self.zoom)
                if -500 < sp[0] < sw+500 and -500 < sp[1] < sh+500:
                    mp = (int(sp[0]/10), int(sp[1]/10))
                    r = int(vision_radius * scale_factor)
                    pygame.draw.circle(vision_surf, (255, 255, 255, 255), mp, r)
        
        # 建筑视野
        for b in self.all_buildings:
            if b.alive and b.team == self.my_team:
                sp = to_screen(b.pos, self.camera_offset, self.zoom)
                if -500 < sp[0] < sw+500 and -500 < sp[1] < sh+500:
                    mp = (int(sp[0]/10), int(sp[1]/10))
                    r = int((vision_radius + 100) * scale_factor)
                    pygame.draw.circle(vision_surf, (255, 255, 255, 255), mp, r)

        # (0,0,0,255) - (255,255,255,255) -> Alpha变成0 (透明)
        fog_surf.blit(vision_surf, (0,0), special_flags=pygame.BLEND_RGBA_SUB)
        
        # 6. 放大并绘制
        full_fog = pygame.transform.smoothscale(fog_surf, (sw, sh))
        self.screen.blit(full_fog, (0, 0))


    def draw_building_menu(self, building):
        c = to_screen(building.pos, self.camera_offset, self.zoom)
        cx, cy = c
        def draw_btn_bg(x, y, color):
            pygame.draw.circle(self.screen, DARK_GRAY, (cx+x, cy+y), 20)
            pygame.draw.circle(self.screen, color, (cx+x, cy+y), 10)
            return (cx+x, cy+y)



        if building.b_type == "base":
            if self.base_menu_mode == "main":
                # 1. 兵营 (上) (0, -80)
                cen = draw_btn_bg(0, -80, (60, 60, 60)) 
                pygame.draw.circle(self.screen, WHITE, cen, 6) 
                pygame.draw.rect(self.screen, BLUE, (cen[0]-6, cen[1], 12, 6)) 
                
                # 2. 工厂 (右上) (70, -40)
                cen = draw_btn_bg(70, -40, GRAY)     
                pygame.draw.rect(self.screen, (50, 50, 50), (cen[0]-5, cen[1]-5, 10, 10))
                
                # 3. 机场 (右下) (70, 40)
                cen = draw_btn_bg(70, 40, (100, 100, 100)) 
                pygame.draw.line(self.screen, WHITE, (cen[0]-5, cen[1]), (cen[0]+5, cen[1]), 2)
                pygame.draw.line(self.screen, WHITE, (cen[0], cen[1]-5), (cen[0], cen[1]+5), 2)
                
                # 4. 雷达 (下) (0, 80)
                cen = draw_btn_bg(0, 80, (50, 50, 60)) 
                pygame.draw.arc(self.screen, WHITE, (cen[0]-6, cen[1]-6, 12, 12), 0, 3.14, 1)
                
                # 5. [新增] 电站 (左下) (-70, 40)
                cen = draw_btn_bg(-70, 40, (255, 200, 0)) 
                lx, ly = cen
                pygame.draw.lines(self.screen, BLACK, False, [(lx+3, ly-8), (lx-5, ly), (lx+5, ly), (lx-3, ly+8)], 2)
                
                # 6. 矿场 (左上) (-70, -40)
                cen = draw_btn_bg(-70, -40, (150, 120, 50)) 
                pygame.draw.line(self.screen, YELLOW, (cen[0], cen[1]-5), (cen[0], cen[1]+5), 2)
                
                # 7. 科研 (正左) (-90, 0)
                cen = draw_btn_bg(-90, 0, (30, 30, 80))
                pygame.draw.circle(self.screen, (0, 200, 255), cen, 4)
                # [新增] 造船厂 (右侧) (80, 0)
                # 原来雷达是 (0, 80)，工厂是 (70, -40)，机场是 (70, 40)
                # 我们可以把造船厂放在正右方
                cen = draw_btn_bg(90, 0, (0, 100, 200)) # 蓝色背景
                # 画个锚
                lx, ly = cen
                pygame.draw.circle(self.screen, WHITE, (lx, ly-5), 3, 1)
                pygame.draw.line(self.screen, WHITE, (lx, ly-2), (lx, ly+8), 2)
                pygame.draw.arc(self.screen, WHITE, (lx-6, ly+2, 12, 10), 3.14, 0, 2)

                # [新增] 收起图标
                cen = draw_btn_bg(0, -120, (200, 100, 50))
                # 画个箭头变车
                pygame.draw.polygon(self.screen, WHITE, [(cen[0], cen[1]-5), (cen[0]-5, cen[1]+5), (cen[0]+5, cen[1]+5)])
            elif self.base_menu_mode == "recruit":
                draw_btn_bg(-60, 0, BLUE) 
                draw_btn_bg(60, 0, (128, 0, 128)) 
                draw_btn_bg(0, -60, RED) 


        elif building.b_type == "airfield":
            center = draw_btn_bg(0, -80, (60, 80, 60))
            rcx, rcy = center
            pygame.draw.line(self.screen, WHITE, (rcx-6, rcy), (rcx+6, rcy), 2)
            pygame.draw.line(self.screen, WHITE, (rcx, rcy-6), (rcx, rcy+6), 2)
            center = draw_btn_bg(60, -20, (20, 30, 20))
            pygame.draw.circle(self.screen, RED, center, 4)
            if not getattr(building, 'is_upgraded', False):
                cen = draw_btn_bg(-60, 60, YELLOW)
                pygame.draw.line(self.screen, BLACK, (cen[0], cen[1]-5), (cen[0], cen[1]+5), 2)
                pygame.draw.line(self.screen, BLACK, (cen[0]-5, cen[1]), (cen[0]+5, cen[1]), 2)
            else:
                my_team = self.my_team
                if self.has_tech_center(my_team):
                    cen = draw_btn_bg(-60, 60, RED)
                    pygame.draw.polygon(self.screen, BLACK, [(cen[0]-5, cen[1]), (cen[0]+5, cen[1]), (cen[0], cen[1]+5)])

# main.py -> draw_building_menu

        elif building.b_type == "factory":
            draw_btn_bg(0, -80, (100, 100, 120)) # Armored
            draw_btn_bg(80, -20, (130, 120, 100)) # M1A2
            # [新增] 工程师图标 (右下)
            cen = draw_btn_bg(60, 60, (200, 200, 50)) # 黄色
            pygame.draw.circle(self.screen, BLACK, cen, 6, 2) # 扳手圈
            
            # [新增] APC 图标 (左上偏下)
            cen = draw_btn_bg(-80, -20, (100, 120, 100))
            pygame.draw.rect(self.screen, BLACK, (cen[0]-5, cen[1]-5, 10, 10))            
            if not getattr(building, 'is_upgraded', False):
                # 升级按钮 (黄色/红色)
                cen = draw_btn_bg(-60, 60, YELLOW)
                # 画个箭头向上表示升级
                pygame.draw.line(self.screen, BLACK, (cen[0], cen[1]+5), (cen[0], cen[1]-5), 2)
                pygame.draw.line(self.screen, BLACK, (cen[0]-4, cen[1]-2), (cen[0], cen[1]-6), 2)
                pygame.draw.line(self.screen, BLACK, (cen[0]+4, cen[1]-2), (cen[0], cen[1]-6), 2)
            else:
                # 升级后显示新兵种
                # 狙击手 (左下)
                cen = draw_btn_bg(-60, 60, (50, 200, 50)) 
                pygame.draw.circle(self.screen, BLACK, cen, 3) # 瞄准镜
                pygame.draw.circle(self.screen, BLACK, cen, 8, 1) 
                
                # 机甲 (正下)
                cen = draw_btn_bg(0, 80, (100, 100, 150))
                pygame.draw.rect(self.screen, BLACK, (cen[0]-4, cen[1]-6, 8, 12))

        # main.py -> draw_building_menu -> radar 部分
        elif building.b_type == "radar":
            # 1. AC130 按钮 (上)
            center = draw_btn_bg(0, -80, (50, 50, 50)) 
            px, py = center
            pygame.draw.line(self.screen, WHITE, (px-8, py), (px+8, py), 3)
            pygame.draw.line(self.screen, WHITE, (px-2, py-6), (px-2, py+6), 2)
            pygame.draw.line(self.screen, WHITE, (px-7, py-3), (px-7, py+3), 2)
            
            # 2. 导弹按钮 (下)
            center = draw_btn_bg(0, 80, ORANGE)
            rcx, rcy = center
            pygame.draw.polygon(self.screen, WHITE, [(rcx, rcy-8), (rcx-5, rcy+5), (rcx+5, rcy+5)])
            
            # 3. [修复] 空降按钮 (左) - 确保这个被画出来
            cen = draw_btn_bg(-80, 0, (200, 200, 200)) 
            pygame.draw.arc(self.screen, BLACK, (cen[0]-6, cen[1]-6, 12, 12), 0, 3.14, 2)
            pygame.draw.line(self.screen, BLACK, (cen[0]-6, cen[1]), (cen[0], cen[1]+6), 1)
            pygame.draw.line(self.screen, BLACK, (cen[0]+6, cen[1]), (cen[0], cen[1]+6), 1)
        elif building.b_type == "research":
            cen = draw_btn_bg(0, -80, (200, 200, 220))
            pygame.draw.arc(self.screen, BLUE, (cen[0]-8, cen[1]-8, 16, 16), 0, 3.14, 2)
            cen = draw_btn_bg(80, -20, (60, 70, 60))
            pygame.draw.line(self.screen, BLACK, (cen[0]-2, cen[1]+5), (cen[0]-2, cen[1]-5), 2)
            pygame.draw.line(self.screen, BLACK, (cen[0]+2, cen[1]+5), (cen[0]+2, cen[1]-5), 2)
            cen = draw_btn_bg(-80, -20, (0, 150, 150))
            pygame.draw.circle(self.screen, CYAN, cen, 4)
            cen = draw_btn_bg(-60, 60, (100, 150, 100))
            pygame.draw.line(self.screen, WHITE, (cen[0], cen[1]-5), (cen[0], cen[1]+5), 2)
            cen = draw_btn_bg(0, 80, (100, 100, 150))
            pygame.draw.rect(self.screen, WHITE, (cen[0]-4, cen[1]-4, 8, 8), 1)
            cen = draw_btn_bg(60, 60, (150, 150, 100))
            pygame.draw.line(self.screen, WHITE, (cen[0]-5, cen[1]), (cen[0]+5, cen[1]), 2)
        elif building.b_type == "shipyard":
            # 导弹艇 (正下)
            cen = draw_btn_bg(0, 60, (50, 100, 150))
            # 画个小船
            pygame.draw.polygon(self.screen, WHITE, [
                (cen[0]-8, cen[1]-2), (cen[0]+8, cen[1]-2),
                (cen[0]+5, cen[1]+5), (cen[0]-5, cen[1]+5)
            ])
            pygame.draw.line(self.screen, WHITE, (cen[0], cen[1]-2), (cen[0], cen[1]-8), 2)
        if building.b_type != "base": # 基地通常不让卖，防止游戏直接输掉
            pygame.draw.circle(self.screen, (50, 0, 0), c, 18) # 深红底
            pygame.draw.circle(self.screen, RED, c, 18, 2)
            # 画一个 X
            pygame.draw.line(self.screen, WHITE, (cx-8, cy-8), (cx+8, cy+8), 2)
            pygame.draw.line(self.screen, WHITE, (cx-8, cy+8), (cx+8, cy-8), 2)


    def draw(self):
        if self.state == "AUTH":
            self.auth_ui.draw()
            pygame.display.flip(); return
    
        if self.state == "LOGIN":
            self.draw_login()
            return        
            
        if self.state == "LOBBY":
            self.lobby_ui.draw() 
            return
            
        if self.state == "WAITING":
            self.screen.fill(BLACK)
            txt = self.title_font.render("WAITING FOR PLAYERS...", True, WHITE)
            self.screen.blit(txt, (SCREEN_WIDTH//2 - 200, SCREEN_HEIGHT//2))
            pygame.display.flip(); return

        if self.state == "MENU":
            self.draw_menu()
            if hasattr(self, 'dic_ui'): self.dic_ui.draw(self.screen) # 画图鉴按钮
            pygame.display.flip(); return
            
        if self.state == "DIC": # 图鉴界面
            if hasattr(self, 'dic_ui'): self.dic_ui.draw(self.screen)
            pygame.display.flip(); return
        if self.state == "SKIRMISH":
            self.skirmish_ui.draw(self.screen); return
        if self.state == "LOADING":
            self.draw_loading()
            return
        if self.state=="STORY":
            self.story_ui.draw(self.screen)
        # 2. 游戏内界面 (PLAYING / GAMEOVER)
        if self.state in ["PLAYING", "GAMEOVER"]:
            
            # 画世界 (必须先有 map)
            if self.current_map:
                self.draw_world()
            else:
                self.screen.fill(BLACK)

            # 画 UI 或 结算
            if getattr(self, 'is_spectator', False) and not self.game_over:
                txt = self.title_font.render("SPECTATING", True, RED)
                self.screen.blit(txt, (SCREEN_WIDTH//2 - 100, 50))
                # 观战也画 UI (小地图等)
                self.draw_ui()
                
            elif self.state == "GAMEOVER":
                self.draw_gameover()
                
            else: # PLAYING
                self.draw_ui()
        
        pygame.display.flip()

