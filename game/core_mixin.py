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

class GameCoreMixin:
    @property
    def my_money(self):
        if hasattr(self, 'team_resources') and self.my_team in self.team_resources:
            return self.team_resources[self.my_team]
        return self.cmd_exp


    @my_money.setter
    def my_money(self, value):
        if hasattr(self, 'team_resources') and self.my_team in self.team_resources:
            self.team_resources[self.my_team] = value
        else:
            self.cmd_exp = value


    def __init__(self):
        pygame.init()
        icon_path = resource_path("picture/chinarising.png")
        if os.path.exists(icon_path):
            try:
                icon_surf = pygame.image.load(icon_path)
                pygame.display.set_icon(icon_surf)
            except Exception as e:
                print(f"Failed to load icon: {e}")
        
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("War Command")   
        # 基础设置
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN | pygame.SCALED, vsync=1)
        pygame.display.set_caption("War Commander: Final Edition")
        self.clock = pygame.time.Clock()
        
        # 网络与玩家数据
        self.net = NetworkManager()
        self.is_online = False
        self.my_role = "HOST"
        self.player_info = None # {uid, name}
        
        self.my_team = "team_0"
        self.teams_config = {} 
        self.lobby_players = [] 

        self.client_id_to_team = {}
        self.sent_join_info = False
        self.is_spectator = False
        self.max_cmd_exp  = 30000
        # 大厅配置
        self.lobby_config = {
            "money": 2000,
            "rate": 0
        }
        
        # UI 组件
        self.dic_ui = DictionaryUI(self)
        self.chat_box = ChatBox(self)
        self.sidebar = Sidebar(self)
        from panels.ui_sidebar import Minimap
        self.minimap = Minimap(self)
        self.auth_ui = LoginUI(self)
        self.lobby_ui = LobbyUI(self)
        from panels.updatelog import UpdateLogUI
        self.update_log = UpdateLogUI(self) 
        from panels.warstory import WarStoryUI
        self.story_ui = WarStoryUI(self)   
        from panels.basesetting import BaseSettingUI
        self.setting_ui = BaseSettingUI(self)   
        from panels.selfdefine import SkirmishUI
        self.skirmish_ui = SkirmishUI(self)   
        from maps.environment import EnvironmentManager
        self.env_manager= EnvironmentManager(self)   
        # 游戏状态
        self.state = "AUTH" 
        self.running = True
        self.difficulty = "NORMAL"
        self.winner = None 
        self.game_over = False
        self.game_over_timer = 0
        self.disconnect_message = ""
        self.rematch_requested = False
        self.opponent_wants_rematch = False
        self.maps = [CrossfireMap,StormCoastMap,DragonValleyMap,BroadcastCenterMap,WildernessMap]
        self.current_map = None
        self.map_id = 0
        self.map_seed = 0
        self.my_faction = None 
        self.faction_icons = {}
        
        # 资源与单位
        self.team_resources = {"team_0": 2000, "team_1": 2000,"team_2": 2000,"team_3": 2000}

        
        self.current_income_rate = 0
        self.current_voltage = 0
        self.max_voltage = 0
        
        self.all_units = []
        self.all_buildings = []
        self.projectiles = []
        self.particles = pygame.sprite.Group()
        self.floating_texts = pygame.sprite.Group()
        self.lakes = []
        self.command_lines = []
        self.net_events = []
        self.broadcast_msgs = []
        
        self.player_base = None 
        self.bases = {} 
        
        self.my_start_pos = vec(0, 0)
        self.camera_offset = vec(0, 0)
        self.zoom = 1.0
        self.selected_entity = None
        self.multi_selected_units = []
        self.selection_rect = None
        self.selection_start = None
        self.place_building_type = None
        
        # 技能状态
        self.call_airstrike_mode = False
        self.call_missile_mode = False
        self.call_airdrop_mode = False
        self.bombardment_mode = False
        self.paused = False
        self.master_volume = 0.4
        
        # 其他
        self.frame_count = 0
        self.loading_progress = 0
        self.data_saved = False
        
        self.ai_commander = AICommander(self) 
        
        # 加载资源
        self.load_resources()
        self.init_level() 


    def load_resources(self):
        # 字体
        self.font = get_font(14)
        self.title_font = get_font(60)
        self.ui_font = get_font(20, bold=True)
        self.info_font = get_font(12)
        self.alert_font = get_font(40)
        self.font_header = get_font(80)
        self.font_sub = get_font(20, bold=True)
        self.font_btn = get_font(40)
        
        # 登录界面按钮
        start_y, gap = 300, 70
        self.login_buttons = [
            BFButton(50, start_y, "MULTIPLAYER - HOST", self.font_btn, "HOST"),
            BFButton(50, start_y + gap, "MULTIPLAYER - JOIN", self.font_btn, "JOIN"),
            BFButton(50, start_y + gap*2, "SINGLEPLAYER", self.font_btn, "SINGLE"),
            BFButton(50, start_y + gap*3, "QUIT GAME", self.font_btn, "QUIT")
        ]
        self.input_ip = InputBox(450, start_y + gap + 5, 250, 40, '127.0.0.1')
        
        # 背景图
        self.bg_images = []
        for i in range(1, 6):
            try:
                path = resource_path(f"bg{i}.jpg")
                img = pygame.image.load(path).convert()
                img = pygame.transform.scale(img, (SCREEN_WIDTH, SCREEN_HEIGHT))
                overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
                overlay.fill((0,0,0)); overlay.set_alpha(80)
                img.blit(overlay, (0,0))
                self.bg_images.append(img)
            except: pass
        self.sidebar_surf = pygame.Surface((400, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.sidebar_surf.fill((0, 0, 0, 200))


        btn_x = 50
        start_y = 250 # 稍微靠下一点，避开标题
        gap = 60 # 间距大一点
        w, h = 300, 40 # 按钮宽一点
        
        self.btn_easy = pygame.Rect(btn_x, start_y, w, h)
        self.btn_normal = pygame.Rect(btn_x, start_y + gap, w, h)
        self.btn_hard = pygame.Rect(btn_x, start_y + gap*2, w, h)
        self.btn_bombard = pygame.Rect(btn_x, start_y + gap*3, w, h)
        self.btn_cards = pygame.Rect(btn_x, start_y + gap*4, w, h)
        self.btn_tutorial = pygame.Rect(btn_x, start_y + gap*5, w, h)
        self.btn_quit = pygame.Rect(btn_x, start_y + gap*6, w, h)
        # 游戏内按钮
        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        self.btn_restart = pygame.Rect(cx - 100, cy + 50, 200, 50)
        self.btn_close_tut = pygame.Rect(cx - 50, cy + 200, 100, 40)
        self.btn_pause = pygame.Rect(cx+200, 10, 40, 40)
        self.btn_resume = pygame.Rect(cx - 100, cy - 20, 200, 50)
        self.btn_ingame_exit = pygame.Rect(cx - 100, cy + 50, 200, 50)
        self.btn_vol_down = pygame.Rect(cx - 80, cy + 120, 40, 40)
        self.btn_vol_up   = pygame.Rect(cx + 40, cy + 120, 40, 40)
        # 阵营图标
        base_dir = os.path.dirname(os.path.abspath(__file__))
        try:
            for fac in ["CHINA", "USA", "RUSSIA"]:
                path = os.path.join(base_dir, "picture", f"{fac.lower()}.png")
                if os.path.exists(path):
                    img = pygame.image.load(path).convert_alpha()
                    self.faction_icons[fac] = pygame.transform.scale(img, (60, 40))
        except: pass
        
        # 音乐
        self.music_files = {}
        try:
            pygame.mixer.init()
            self.music_dir = resource_path("music")
            self.common_music = {
                "menu": os.path.join(self.music_dir, "menu_bgm.mp3"),
                "loading": os.path.join(self.music_dir, "loading.mp3"),
                "victory": os.path.join(self.music_dir, "victory.mp3"),
                "defeat": os.path.join(self.music_dir, "defeat.mp3")
            }
            self.current_music_state = "SILENT"
        except Exception as e: print(f"Music Init Error: {e}")


    def reset_lobby_data(self):
        # 1. 停止网络 (如果还在运行)
        if self.is_online and hasattr(self, 'net'):
            self.net.stop_hosting()
            self.is_online = False
            self.my_role = None
            
        # 2. 清理大厅数据
        self.lobby_players = []
        
        # 3. 清理聊天框
        if hasattr(self, 'chat_box'):
            self.chat_box.messages = [] 
            self.chat_box.text = ""
            
        # 4. 重置标志位
        self.sent_join_info = False 
        self.rematch_requested = False
        self.opponent_wants_rematch = False
        
        # 5. 重置游戏状态 (可选，防止上一局的数据残留)
        self.winner = None
        self.game_over = False


    def reset_game(self):
        self.game_over = False
        self.last_packet_time = pygame.time.get_ticks()
        self.winner = None
        
        # 1. 初始化 AI 列表 (不再是单个对象)
        self.ai_commanders = [] 
        
        # 2. 重置倒计时和音乐
        if pygame.mixer.get_init():
            pygame.mixer.music.fadeout(1000)
        self.game_over_timer = 0
        self.disconnect_message = ""
        self.is_spectator = False
        #fraction
        if not self.is_online:
            # 获取当前选择的阵营 (默认为 USA)
            p_fac = getattr(self, 'my_faction', 'USA')
            
            # 导入随机阵营生成器 (给 AI 用)
            from core.factions import get_random_faction
            ai_fac, _ = get_random_faction()
            
            # 情况 A: 第一次进入游戏，config 为空
            if not self.teams_config:
                self.teams_config = {
                    "team_0": {"name": "Player", "faction": p_fac},
                    "team_1": {"name": "AI", "faction": ai_fac}
                }
                # 默认我是 team_0
                self.my_team = "team_0"
                
            elif "team_0" in self.teams_config:
                self.teams_config["team_0"]["faction"] = p_fac
                # (可选) 让 AI 也换个阵营
                self.teams_config["team_1"]["faction"] = ai_fac        
        # 3. 资源与科技
        self.team_resources = {}
        self.team_tech_levels = {}
        
        # 如果 teams_config 为空(尚未SETUP)，先给个默认值防止报错
        current_teams = self.teams_config.keys() if self.teams_config else ["team_0", "team_1"]
        start_money = self.lobby_config.get("money", 2000)
        
        for tid in current_teams:
            self.team_resources[tid] = start_money
            self.team_tech_levels[tid] = {"infantry": 0, "armor": 0, "air": 0}

        self.max_cmd_exp=30000        
        self.active_alert = None
        self.zoom = 1.0
        self.dragging = False
        self.last_mouse_pos = vec(0, 0)
        self.show_info_panel = False
        self.base_menu_mode = "main" 
        if not hasattr(self, 'client_id_to_team'):
            self.client_id_to_team = {} 
        start_money = self.lobby_config.get("money", 5000) # 读取配置
        for tid in current_teams:
            self.team_resources[tid] = start_money       
        # 5. 清空实体列表
        self.all_units = []
        self.all_buildings = []
        self.projectiles = []
        self.broadcast_msgs = [] 
        self.particles = pygame.sprite.Group()
        self.floating_texts = pygame.sprite.Group() 
        self.bases = {} 
        self.player_base = None 
  
        self.selected_entity = None
        self.place_building_type = None 
        # 实例化地图
        MapClass = self.maps[self.map_id]
        self.current_map = MapClass(self)        
        # 7. 技能状态重置
        self.call_airstrike_mode = False
        self.call_missile_mode = False
        self.call_airdrop_mode = False
        
        # 8. 初始化关卡 (生成单位和建筑)
        self.init_level()        
        target_pos = vec(0, 0)
        if self.player_base:
            target_pos = vec(self.player_base.pos)
        elif self.current_map:
            target_pos = vec(self.current_map.width/2, self.current_map.height/2)
            
        if self.current_map:
            scale_w = SCREEN_WIDTH / self.current_map.width
            scale_h = SCREEN_HEIGHT / self.current_map.height
            start_zoom = min(scale_w, scale_h) * 0.9 
            self.zoom = max(start_zoom, 0.1)
            map_center = vec(self.current_map.width/2, self.current_map.height/2)
            center_screen = vec(SCREEN_WIDTH/2, SCREEN_HEIGHT/2)
            self.camera_offset = map_center - (center_screen / self.zoom)
        else:
            # 兜底
            self.zoom = 0.5
            self.camera_offset = vec(0, 0)
        self.opening_animation_done = False             

        self.data_saved = False 
        self.frame_count = 0
        self.loading_progress = 0
        self.current_income_rate = CMD_EXP_RATE * self.lobby_config["rate"] 

        self.has_received_first_snapshot = False         
        # 10. 初始化 AI (放在最后，确保基地已生成)
        if not self.is_online:
            for tid in current_teams:
                if tid != self.my_team:
                    self.ai_commanders.append(AICommander(self, team=tid))


    def play_music(self, path, loops=-1, volume=0.4):
        if not os.path.exists(path):
            print(f"[Music] File not found: {path}")
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play(loops)
        except Exception as e:
            print(f"[Music] Play error: {e}")


    def check_music_state(self):
        if not pygame.mixer.get_init(): return 
        if not hasattr(self, 'music_dir'): return

        def play(config_key, loop_count=-1):
            fname = None
            if self.current_map and hasattr(self.current_map, 'music_config'):
                fname = self.current_map.music_config.get(config_key)
            
            if not fname:
                defaults = {
                    "intro": "intro.mp3", "loop": "battle_loop.mp3",
                    "final1": "phase1_loop.mp3", "final2": "phase2_loop.mp3",
                    "final3": "final_rush.mp3", "end_win": "victory.mp3", "end_lose": "defeat.mp3",
                    "menu": "menu_bgm.mp3" 
                }
                fname = defaults.get(config_key)
            
            if fname:
                path = os.path.join(self.music_dir, fname)
                # 避免重复加载同一首歌
                if getattr(self, 'current_music_path', None) == path and pygame.mixer.music.get_busy():
                    return

                if os.path.exists(path):
                    try:
                        pygame.mixer.music.load(path)
                        pygame.mixer.music.play(loop_count)
                        self.current_music_path = path
                    except Exception as e:
                        print(f"[Music] Load error: {e}")
        if self.state in ["LOGIN", "LOBBY", "MENU", "TUTORIAL"]:
            if self.current_music_state != "MENU":
                # 强制停止当前
                pygame.mixer.music.stop()
                play("menu", -1)
                self.current_music_state = "MENU"
            return
        # === 1. 游戏结束 (GAMEOVER) [最高优先级] ===
        if self.state == "GAMEOVER":
            if self.current_music_state != "END_THEME":
                key = "end_win" 
                
                # (或者如果你没有在 defaults 字典里定义 "end_win" 对应 "victory.mp3")
                # 你可以直接写死文件名，但用 play 函数更优雅
                # 只要确保 play("end_win", 0) 会去放 victory.mp3
                
                print(f"[Music] Game Over -> Playing {key}")
                play(key, 0) # 不循环
                self.current_music_state = "END_THEME"
            return 

        # === 2. 非游戏状态 (菜单/登录/大厅) ===
        # [修改] 只要不是 PLAYING 和 LOADING (LOADING有专门音乐)，就播菜单音乐
        if self.state not in ["PLAYING", "LOADING", "GAMEOVER"]:
            if self.current_music_state != "MENU":
                print("[Music] Back to Menu -> Playing menu_bgm")
                play("menu", -1)
                
                self.current_music_state = "MENU"
            return
        # === 2. 非游戏状态 (菜单) ===
        if self.state != "PLAYING":
            if self.current_music_state != "MENU":
                # 菜单音乐通常不随地图变，直接用 self.music_files 里的
                if "menu" in self.music_files:
                    try:
                        pygame.mixer.music.load(self.music_files["menu"])
                        pygame.mixer.music.play(-1)
                    except: pass
                self.current_music_state = "MENU"
            return

        alive_teams = set()

        # 检查所有建筑 (基地)
        for b in self.all_buildings:
            if b.alive and getattr(b, 'b_type', '') == 'base' and b.team != 'neutral':
                alive_teams.add(b.team)

        # 检查所有单位
        for u in self.all_units:
            if not u.alive or u.team == 'neutral': continue
            
            if u.__class__.__name__ == "MCV":
                alive_teams.add(u.team)
            if hasattr(u, 'cargo') and u.cargo:
                for item in u.cargo:
                    # 兼容不同格式
                    inner_u = None
                    if isinstance(item, Unit):
                        inner_u = item
                    elif isinstance(item, dict) and 'unit' in item:
                        inner_u = item['unit']
                    
                    if inner_u and inner_u.__class__.__name__ == "MCV":
                        alive_teams.add(inner_u.team)
        total_start_teams = len(self.teams_config) if self.teams_config else 2 

        current_alive_count = len(alive_teams)
        if not self.is_online or self.my_role == "HOST":
            if self.frame_count > 300 and current_alive_count < total_start_teams:
                if self.current_music_state != "FINAL3":
                    play("final3", -1)
                    self.current_music_state = "FINAL3"
                return
        else:
            if self.current_music_state == "FINAL3":
                print(f"[Music] A Team Eliminated ({current_alive_count}/{total_start_teams}) -> FINAL RUSH")
                play("final3", -1)
                self.current_music_state = "FINAL3"
        # === 4. 开场逻辑 (Intro -> Loop) ===
        # 如果刚从菜单进来
        if self.current_music_state == "MENU":
            play("intro", 0) # 播一次
            self.current_music_state = "INTRO"
            return

        # 如果 Intro 播完了 -> 切到 Loop (Battle)
        if self.current_music_state == "INTRO":
            if pygame.mixer.music.get_busy(): return # 还在播就等待
            play("loop", -1)
            self.current_music_state = "BATTLE"
            return

        valid_states = ["BATTLE", "FINAL1", "FINAL2"]
        if self.current_music_state not in valid_states: return

        # 计算血量比
        min_hp_ratio = 1.0
        for b in self.all_buildings:
            if b.alive and hasattr(b, 'b_type') and b.b_type == "base":
                max_hp = getattr(b, 'max_hp', 5000)
                if max_hp > 0:
                    ratio = b.hp / max_hp
                    if ratio < min_hp_ratio: min_hp_ratio = ratio
        
        # 决策
        desired = "BATTLE"
        if min_hp_ratio <= 0.35: desired = "FINAL2" # Phase 2
        elif min_hp_ratio <= 0.60 : desired = "FINAL1" # Phase 1
        
        # 执行切换
        if desired != self.current_music_state:
            print(f"[Music] Crisis: {min_hp_ratio:.1%} -> {desired}")
            
            if desired == "FINAL1": play("final1", -1)
            elif desired == "FINAL2": play("final2", -1)
            else: play("loop", -1) # 回复到 BATTLE
            
            self.current_music_state = desired


    def load_menu_backgrounds(self):
        for i in range(1, 6): # bg1.jpg 到 bg5.jpg
            fname = f"bg{i}.jpg"
            try:
                path = resource_path(fname)
                img = pygame.image.load(path).convert()
                img = pygame.transform.scale(img, (SCREEN_WIDTH, SCREEN_HEIGHT))
                # 加个遮罩让文字更清晰
                overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
                overlay.fill((0, 0, 0))
                overlay.set_alpha(80)
                img.blit(overlay, (0, 0))
                self.bg_images.append(img)
            except:
                pass # 没图就不加


    def generate_background(self):
        bg = pygame.Surface((WORLD_WIDTH, WORLD_HEIGHT))
        # 1. 基础草地色
        bg.fill((30, 34, 30)) # 更深沉的泥土草地色
        
        # 2. 绘制网格线 (战术感)
        for x in range(0, WORLD_WIDTH, 100):
            pygame.draw.line(bg, (40, 45, 40), (x, 0), (x, WORLD_HEIGHT), 2)
        for y in range(0, WORLD_HEIGHT, 100):
            pygame.draw.line(bg, (40, 45, 40), (0, y), (WORLD_WIDTH, y), 2)
            
        # 3. 随机绘制一些深色植被斑块 (代替原来的噪点)
        for _ in range(200):
            x = random.randint(0, WORLD_WIDTH)
            y = random.randint(0, WORLD_HEIGHT)
            r = random.randint(50, 150)
            # 画一个稍微亮一点或暗一点的圆
            color = (35, 40, 35)
            pygame.draw.circle(bg, color, (x, y), r)
            
        return bg


    def run(self):
        try:
            while self.running:
                self.handle_input()
                self.update()
                self.draw()
                self.clock.tick(FPS)
        except Exception as e:
            import traceback
            print("CRASHED!")
            traceback.print_exc()
        finally:
            print("Exiting game loop.")
            pygame.quit()

