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
from core.i18n import tr

class LevelMixin:
    def init_level(self):
        mid_y = WORLD_HEIGHT // 2

        start_money = self.lobby_config.get("money", 5000)
        self.team_resources = {}
        for team_id in self.teams_config.keys():
            self.team_resources[team_id] = start_money   

        if hasattr(self, 'synced_lakes') and self.synced_lakes:
            self.lakes = []
            for d in self.synced_lakes:
                r = d['rect']
                rect = pygame.Rect(r[0], r[1], r[2], r[3])
                self.lakes.append({
                    'rect': rect, 'parts': d['parts'], 'type': d.get('type', 'water')
                })
            if self.current_map: self.current_map.lakes = self.lakes
            # 网络快照覆盖会丢掉地形多边形水域条目——幂等恢复（t2 的 from_terrain 清旧追加）
            if self.current_map is not None and hasattr(self.current_map, 'terrain_polys') and self.current_map.terrain_polys:
                self.current_map.apply_terrain_polys(self)
            print(f"[Map] Applied {len(self.lakes)} synced lakes.")
        else:
            self.lakes = []
            if self.current_map: self.lakes = self.current_map.lakes 
            if not self.lakes:
                # 默认生成
                for _ in range(random.randint(5, 8)):
                    cx = random.randint(200, WORLD_WIDTH - 200)
                    cy = random.randint(200, WORLD_HEIGHT - 200)
                    w, h = random.randint(100, 300), random.randint(100, 300)
                    rect = pygame.Rect(cx-w//2, cy-h//2, w, h)
                    self.lakes.append({'rect': rect, 'parts': [(cx, cy, w, h)]})

        lake_rects = [lake['rect'] for lake in self.lakes]

        self.all_buildings = []
        self.bases = {} 
        if not self.teams_config:
            self.teams_config = {"team_0": {"name": "Player"}, "team_1": {"name": "AI"}}
            if self.my_role == "HOST" or not self.is_online: 
                self.my_team = "team_0"
            elif self.my_role == "CLIENT":
                self.my_team = "team_1"

        if getattr(self, 'arena_active', False):
            # 竞技场无基地：不生成 BaseBuilding，bases_config 仅作双方出兵锚点
            if self.current_map and self.current_map.bases_config:
                self.my_start_pos = vec(self.current_map.bases_config[0])
        elif self.current_map and self.current_map.bases_config:
            sorted_teams = sorted(self.teams_config.keys())
            
            for i, team_id in enumerate(sorted_teams):
                # [修改] 使用取模运算，防止出生点不够时崩溃/不生成
                config_idx = i % len(self.current_map.bases_config)
                config_item = self.current_map.bases_config[config_idx]
                
                if isinstance(config_item, tuple): spawn_pos = config_item[1]
                else: spawn_pos = config_item
                
                # 强制转换为 vec
                if not isinstance(spawn_pos, pygame.math.Vector2):
                    spawn_pos = vec(spawn_pos)
                
                # 如果出生点被复用了，稍微偏移一点防止完全重叠
                if i >= len(self.current_map.bases_config):
                    spawn_pos += vec(50, 50)

                print(f"[Init] Base created for {team_id} at {spawn_pos}. My Team: {self.my_team}")                    
                
                # 创建基地
                base = BaseBuilding(self, spawn_pos, team_id)
                base.uid = f"base_{team_id}" 

                self.all_buildings.append(base)
                self.bases[team_id] = base
                
                # 如果这是我的基地，设置视角和初始点
                if team_id == self.my_team:
                    self.player_base = base
                    self.my_start_pos = spawn_pos
        else:
            # 兜底逻辑 (没有地图配置时)
            # 生成两个默认基地
            p1_pos = vec(400, mid_y)
            p2_pos = vec(WORLD_WIDTH - 400, mid_y)
            
            b1 = BaseBuilding(self, p1_pos, "team_0")
            b2 = BaseBuilding(self, p2_pos, "team_1")
            self.all_buildings.extend([b1, b2])
            self.bases["team_0"] = b1
            self.bases["team_1"] = b2
            
            if self.my_team == "team_0": 
                self.player_base = b1; self.my_start_pos = p1_pos
            else: 
                self.player_base = b2; self.my_start_pos = p2_pos

        # 3. 生成中立建筑 (保持不变)
        if not self.is_online or self.my_role == "HOST":
            if self.current_map:
                if hasattr(self.current_map, 'neutral_buildings'):
                    self.all_buildings.extend(self.current_map.neutral_buildings)
                if hasattr(self.current_map, 'neutral_units'):
                    self.all_units.extend(self.current_map.neutral_units)
            else:
                for _ in range(6):
                    rx, ry = random.randint(500, WORLD_WIDTH-500), random.randint(200, WORLD_HEIGHT-200)
                    if pygame.Rect(rx-40, ry-40, 80, 80).collidelist(lake_rects) == -1:
                        self.all_buildings.append(OilDerrick(self, vec(rx, ry)))
                        
        # 4. 生成初始单位 (如火车)
        if hasattr(self.current_map, 'initial_units'):
            for u_type, pos in self.current_map.initial_units:
                if u_type == "scavenger":
                    self.all_units.append(ScavengerWalker(self, pos))
                elif u_type == "train":
                    self.all_units.append(ArmoredTrain(self, pos))
                elif u_type == "Battleship":
                    self.all_units.append(Battleship(self, pos))

        # 5. 特殊单位刷新注册（列车/战列舰死亡定时重生 + 通讯站绑定）
        self._register_special_units()


    def _register_special_units(self):
        """特殊单位（列车/战列舰）刷新注册：init_level / apply_map_data 末尾调用。
        spec 来源：布局 JSON special_units 分区（apply_layout_override 写入
        map.special_specs）或地图硬编码 initial_units 推导的默认 spec。"""
        from game.special_units_mixin import SpecialUnitManager
        if not hasattr(self, 'special_units'):
            self.special_units = SpecialUnitManager(self)
        self.special_units.register_from_map()       


    def perform_rebuild_base(self, cost, team, spawn_pos):
        # 1. [修改] 扣钱：不再区分 my_team 还是 enemy，直接查字典
        if team in self.team_resources:
            self.team_resources[team] -= cost
        
        # 2. 生成基地 (保持不变)
        from core.base_classes import BaseBuilding 
        new_base = BaseBuilding(self, spawn_pos, team)
        self.all_buildings.append(new_base)
        
        # 3. [修改] 更新引用：废弃 enemy_base，使用 bases 字典
        # 确保字典存在
        if not hasattr(self, 'bases'): self.bases = {}
        
        # 把新基地存入字典 (所有人通用)
        self.bases[team] = new_base        
        # 仅当这个队伍是"我"的时候，更新便捷引用 self.player_base
        if team == self.my_team:
            self.player_base = new_base
        
        # 4. 特效 (保持不变)
        from core.base_classes import FloatingText
        self.particles.add(FloatingText(spawn_pos, tr("w.base_rebuilt"), GREEN_HAT))


    def draw_loading(self):
        self.screen.fill(BLACK)
        font_path = resource_path(os.path.join("fonts", "simhei.ttf"))        
        # 1. 绘制地图预览 (居中放大)
        if self.current_map:
            # 1. 准备字体
            try:
                if os.path.exists(font_path):                  
                    title_font =get_font(60,bold=True)
                    desc_font = get_font(24)
                    location_font=get_font(18)
            except:
                title_font=get_font(60,bold=True)
                location_font=get_font(18)
                desc_font = get_font(24)

            # 2. 绘制标题 (左上角)
            map_name = getattr(self.current_map, 'name_cn', self.current_map.name)
            location_name = getattr(self.current_map, 'name_cn', self.current_map.location)
            name_surf = title_font.render(map_name, True, WHITE)

            location_surf =location_font.render(location_name, True, WHITE) 
            self.screen.blit(name_surf, (50, 50))  
            self.screen.blit(location_surf, (220,120))         
            # 绘制位置调整
            # 3. 绘制描述 (自动换行，支持中文)
            desc_text = getattr(self.current_map, 'description', "")
            
            # 使用正确的字体对象
            # (之前加载的 desc_font)
            
            lines = []
            curr_line = ""
            max_width = 300
            
            # 逐字遍历 (针对中文优化)
            for char in desc_text:
                # 试探性添加一个字符
                test_line = curr_line + char
                
                # 计算宽度
                if desc_font.size(test_line)[0] < max_width:
                    curr_line = test_line
                else:
                    # 超出宽度，换行
                    lines.append(curr_line)
                    curr_line = char # 新行从当前字符开始
            
            # 添加最后一行
            if curr_line:
                lines.append(curr_line)
            
            # 绘制
            text_start_y = 150 # 稍微往下一点，避开 location
            for i, line in enumerate(lines):
                s = desc_font.render(line, True, (200, 200, 200))
                self.screen.blit(s, (50, text_start_y + i*30))

            # 4. 绘制预览图 (按屏幕比例放大，右侧居中)
            if self.current_map.preview_image:
                src = self.current_map.preview_image
                # 宽度取屏幕的 60%（上限 1280），保持原图纵横比
                pw = min(1280, int(SCREEN_WIDTH * 0.6))
                ph = max(1, int(src.get_height() * pw / src.get_width()))
                # 过高则按高度反算
                if ph > SCREEN_HEIGHT - 160:
                    ph = SCREEN_HEIGHT - 160
                    pw = max(1, int(src.get_width() * ph / src.get_height()))
                preview = pygame.transform.smoothscale(src, (pw, ph))

                # 计算位置：放在右边
                preview_rect = preview.get_rect(right=SCREEN_WIDTH - 50, centery=SCREEN_HEIGHT//2)

                self.screen.blit(preview, preview_rect)
                pygame.draw.rect(self.screen, WHITE, preview_rect, 2)

        # 2. 进度条
        bar_w, bar_h = 600, 20
        bar_x = (SCREEN_WIDTH - bar_w) // 2
        bar_y = SCREEN_HEIGHT - 100
        
        pygame.draw.rect(self.screen, (50, 50, 50), (bar_x, bar_y, bar_w, bar_h))
        pygame.draw.rect(self.screen, MARKER_BLUE, (bar_x, bar_y, bar_w * self.loading_progress, bar_h))
        pygame.draw.rect(self.screen, WHITE, (bar_x, bar_y, bar_w, bar_h), 2)
        
        t = self.ui_font.render(tr("common.loading", pct=int(self.loading_progress*100)), True, WHITE)
        self.screen.blit(t, (bar_x, bar_y - 30))
        
        pygame.display.flip()


    def update_loading(self):
        self.loading_progress += 0.003
        
        if 0.49 < self.loading_progress < 0.51 and not self.data_saved:
            
            # Client 逻辑
            if self.is_online and self.my_role == "CLIENT":
                self.apply_map_data() 
                
                # [关键检查] 确保 current_map.lakes 不为空
                if self.current_map and not self.current_map.lakes:
                    self.current_map.lakes = self.lakes
                
                self.current_map.generate(seed=self.map_seed, visual_only=True)
                # 客户端：generate 后覆盖布局保持 map 层与主机一致（实体由网络同步）
                if not getattr(self, 'arena_active', False) and self.current_map is not None:
                    self.current_map.apply_layout_override()
                    # 布局 JSON 已带矿脉时跳过随机生成（与主机一致）
                    if not getattr(self.current_map, 'layout_has_ore', False):
                        self.current_map.generate_ore_patches()
            
            else:
                # Host / Single
                if not self.map_seed:
                    self.map_seed = random.randint(0, 1000000)  # 单机每局随机种子
                self.current_map.generate(seed=self.map_seed)
                # generate 重置了地图 lakes（画进背景的视觉湖）——判定容器 game.lakes
                # 对齐过去，防构造期 init_level 的随机矩形湖与视觉湖错位
                self.lakes = self.current_map.lakes
                # [布局编辑器] 布局覆盖必须在 apply_map_data 之前：
                # apply_map_data 会把 map.neutral_buildings 收进 all_buildings、
                # 并按 bases_config 重建基地——覆盖晚了JSON布局就进不了游戏
                if not getattr(self, 'arena_active', False) and self.current_map is not None:
                    self.current_map.apply_layout_override()
                self.apply_map_data()
                # [红警式矿脉] 布局确定后按 seed 确定性生成地面矿脉（避开 JSON 出生点）；
                # 布局 JSON 已带矿脉（layout_has_ore）时改由布局矿脉接管
                if not getattr(self, 'arena_active', False) and self.current_map is not None:
                    if not getattr(self.current_map, 'layout_has_ore', False):
                        self.current_map.generate_ore_patches()

            self.data_saved = True


        if self.loading_progress >= 1.0:
            self.state = "PLAYING"
            
            # [核心修改] 1. 切换音乐
            if self.current_map:
                intro_file = self.current_map.music_config.get("intro", "intro.mp3")
                intro_path = os.path.join(self.music_dir, intro_file)
                self.play_music(intro_path, 0)
                self.current_music_state = "INTRO"
            self.check_music_state() 
            
            if not self.player_base:
                for b in self.all_buildings:
                    if b.team == self.my_team and getattr(b, 'b_type', '') == 'base':
                        self.player_base = b
                        break
            
            # [修改] 初始化视角为地图中心 (作为动画起点)
            if self.current_map:
                w, h = self.current_map.width, self.current_map.height
                min_zoom = min(SCREEN_WIDTH / w, SCREEN_HEIGHT / h) * 0.9
                self.zoom = max(min_zoom, 0.1) # 初始缩放 (远景)
                
                scr_center = vec(SCREEN_WIDTH/2, SCREEN_HEIGHT/2)
                map_center = vec(w/2, h/2)
                self.camera_offset = map_center - (scr_center / self.zoom)
            
            self.target_zoom = 1.0
            self.opening_animation_done = False

            # 竞技场模式：加载完成后进入 ARENA 状态并开启第一轮
            if getattr(self, 'arena_active', False):
                self.state = "ARENA"
                self.arena_start_round()


    def apply_map_data(self):
        if hasattr(self, 'map_data') and self.map_data and self.current_map:
            if 'w' in self.map_data and 'h' in self.map_data:
                self.current_map.width = self.map_data['w']
                self.current_map.height = self.map_data['h']
                print(f"[Client] Map Size Applied: {self.current_map.width}x{self.current_map.height}")
        # 1. 清空旧数据
        self.all_buildings = []
        self.all_units = []
        self.projectiles = []
        self.particles = pygame.sprite.Group()
        self.floating_texts = pygame.sprite.Group()
        
        # 2. 处理湖泊
        if hasattr(self, 'synced_lakes'):
            self.lakes = []
            for d in self.synced_lakes:
                r = d['rect']
                rect = pygame.Rect(r[0], r[1], r[2], r[3])
                self.lakes.append({
                    'rect': rect, 
                    'parts': d['parts'], 
                    'type': d.get('type', 'water')
                })
            
            if self.current_map:
                self.current_map.lakes = self.lakes
        else:
            self.lakes = self.current_map.lakes if self.current_map else []

        # 3. 实例化基地 (核心修复) —— 竞技场无基地，跳过
        if getattr(self, 'arena_active', False):
            pass
        elif self.current_map and self.current_map.bases_config:
            team_list = sorted(self.teams_config.keys()) if getattr(self, 'teams_config', None) else ["team_0", "team_1"]
            
            for i, team_id in enumerate(team_list):
                # 防止地图出生点不够
                if i < len(self.current_map.bases_config):
                    config_item = self.current_map.bases_config[i]
                    if isinstance(config_item, tuple) and isinstance(config_item[0], str):
                        raw_pos = config_item[1]
                    else:
                        raw_pos = config_item
                    
                    # 强制转换
                    if isinstance(raw_pos, (list, tuple)):
                        spawn_pos = vec(raw_pos[0], raw_pos[1])
                    else:
                        spawn_pos = vec(raw_pos)
                    
                    # 创建基地
                    base = BaseBuilding(self, spawn_pos, team_id)
                    self.all_buildings.append(base)
                    
                    # 更新引用 (self.bases)
                    if not hasattr(self, 'bases'): self.bases = {}
                    self.bases[team_id] = base
                    
                    # 更新我的视角
                    if team_id == self.my_team:
                        self.player_base = base
                        self.my_start_pos = base.pos

        # 4. 加入中立建筑
        if self.current_map and self.current_map.neutral_buildings:
            self.all_buildings.extend(self.current_map.neutral_buildings)
            
        # 5. 生成初始单位
        if self.current_map and hasattr(self.current_map, 'initial_units'):
            for u_type, pos in self.current_map.initial_units:
                # [修复] 同样确保 pos 是 vec
                unit_pos = vec(pos)
                if u_type == "scavenger":
                    self.all_units.append(ScavengerWalker(self, unit_pos))
                elif u_type == "train":
                    self.all_units.append(ArmoredTrain(self, unit_pos))
                elif u_type == "Battleship":
                    self.all_units.append(Battleship(self, unit_pos))

        # 6. 特殊单位刷新注册（apply_map_data 重建了实体，注册表需同步重建）
        self._register_special_units()


    def start_rematch(self):
        # 只有 Host 负责发起 SETUP
        if self.my_role == "HOST":
            # 重新随机地图
            self.map_id = random.randint(0, len(self.maps)-1)
            seed = random.randint(0, 1000000)
            self.map_seed = seed  # [修复] 保存种子，保证重赛两侧地图/矿脉一致
            random.seed(seed)
            
            # 生成新地图数据
            MapClass = self.maps[self.map_id]
            self.current_map = MapClass(self)
            self.current_map.generate(seed)
            from core.factions import get_random_faction
            host_fac, _ = get_random_faction()
            client_fac, _ = get_random_faction()
            
            self.my_faction = host_fac
            self.enemy_faction = client_fac            
            lakes_data = []
            for l in self.current_map.lakes:
                r = l['rect']
                lakes_data.append({
                    'rect': (r.x, r.y, r.w, r.h), 
                    'parts': l['parts'],
                    'type': l.get('type', 'water')
                })
            
            # 发送 SETUP (Client 收到后会重置)
            self.net.send({
                "type": "SETUP",
                "map_id": self.map_id,
                "seed": seed,
                "lakes_data": lakes_data,
                "p_fac": host_fac,
                "e_fac": client_fac
            })
            
            # Host 自己重置
            self.reset_game()
            self.state = "LOADING"
            
        #以此重置标志位
        self.rematch_requested = False
        self.opponent_wants_rematch = False


    def has_active_base(self, team_id):
        for b in self.all_buildings:
            # 这里必须用传入的 team_id，绝对不能写死 "player"
            if b.team == team_id and b.alive:
                if getattr(b, 'b_type', '') in ["base", "factory", "airfield", "shipyard"]:
                    return True
        
        for u in self.all_units:
            if u.team == team_id and u.alive:
                # 检查类名或属性
                if u.__class__.__name__ == "MCV":
                    return True
                
        return False


    def has_tech_center(self, team):
        for b in self.all_buildings:
            if b.team == team and b.alive and getattr(b, 'b_type', '') == "tech_center":
                return True
        return False

