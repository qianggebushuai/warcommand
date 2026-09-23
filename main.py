import pygame
import os
import random
from core.settings import *
from core.base_classes import *
from units import *
from network import NetworkManager
from ai_logic import AICommander
from core.factions import get_random_faction
import fractions
import sys 
import pygame.scrap
import time
from maps import *
from core.dic import *
from ui_sidebar import Sidebar
from ui_login import LoginUI
from ui_lobby import LobbyUI
import json 
from core.utils import resource_path, get_font
# main.py
class ChatBox:
    def __init__(self, game):
        self.game = game
        self.active = False
        self.text = ""
        self.messages = [] 
        self.font = get_font(14) # 使用支持中文的字体
        self.input_rect = pygame.Rect(SCREEN_WIDTH - 320, 50, 300, 30)
        self.history_rect = pygame.Rect(SCREEN_WIDTH - 320, 90, 300, 200)
        


    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if self.active:
                if event.key == pygame.K_RETURN:
                    if self.text.strip():
                        self.send_chat()
                        self.text = ""
                    self.active = False 
                    pygame.key.stop_text_input()
                    
                elif event.key == pygame.K_BACKSPACE:
                    self.text = self.text[:-1]
                    
                elif event.key == pygame.K_ESCAPE:
                    self.active = False
                    pygame.key.stop_text_input()
            else:
                # 激活聊天框
                if event.key == pygame.K_t: 
                    self.active = True
                    pygame.key.start_text_input()
        if event.type == pygame.TEXTINPUT and self.active:
            self.text += event.text
    def add_message(self, text, sender_name, is_self=False):
        # [修改] 颜色逻辑
        if is_self:
            name_color = (0, 255, 255) # 自己是青色
        elif sender_name == "System":
            name_color = YELLOW
        else:
            # 根据名字生成随机颜色 (确定性随机)
            import hashlib
            h = int(hashlib.md5(sender_name.encode()).hexdigest(), 16)
            r = (h & 0xFF)
            g = (h >> 8) & 0xFF
            b = (h >> 16) & 0xFF
            # 避免太黑
            name_color = (max(100, r), max(100, g), max(100, b))
        
        # 消息内容颜色
        msg_color = WHITE
        
        # 存储结构变一下，或者直接拼成字符串
        # 格式: "[Name]: Text"
        display_text = f"[{sender_name}]: {text}"
        self.messages.append({"text": display_text, "color": name_color}) # 整条消息用名字颜色，或者分开画

    def send_chat(self):
        my_name = self.game.player_info['name']
        self.add_message(self.text, my_name, is_self=True)
        
        if self.game.is_online:
            self.game.net.send({
                "type": "CHAT", 
                "text": self.text, 
                "name": my_name
            })

    def draw(self, screen):
        s = pygame.Surface((300, 200), pygame.SRCALPHA)
        s.fill((0, 0, 0, 100))
        screen.blit(s, (self.history_rect.x, self.history_rect.y))
        
        y = self.history_rect.bottom - 25
        for msg in reversed(self.messages):
            # 简单的自动换行略过，假设消息不长
            txt_surf = self.font.render(msg['text'], True, msg['color'])
            screen.blit(txt_surf, (self.history_rect.x + 5, y))
            y -= 25
            if y < self.history_rect.top: break

        # 2. 绘制输入框 (激活时)
        if self.active:
            pygame.draw.rect(screen, (50, 50, 50), self.input_rect)
            pygame.draw.rect(screen, WHITE, self.input_rect, 2)
            
            # 绘制输入内容 (加光标)
            txt_surf = self.font.render(self.text + "|", True, WHITE)
            screen.blit(txt_surf, (self.input_rect.x + 5, self.input_rect.y + 5))
class BFButton:
    def __init__(self, x, y, text, font, action_code):
        self.x = x
        self.y = y
        self.text = text
        self.font = font
        self.action_code = action_code # 用于标识点击了哪个按钮
        # 预渲染文字
        self.surf_normal = font.render(text, True, (180, 180, 180)) # 灰色未选中
        self.surf_hover = font.render(text, True, (255, 255, 255))  # 白色选中
        self.rect = self.surf_normal.get_rect(topleft=(x, y))
        self.is_hovered = False

    def check_hover(self, mouse_pos):
        self.is_hovered = self.rect.collidepoint(mouse_pos)
        return self.is_hovered

    def draw(self, screen):
        if self.is_hovered:
            screen.blit(self.surf_hover, (self.x, self.y))
            pygame.draw.rect(screen, (255, 100, 0), (self.x - 10, self.y + 5, 4, self.rect.height - 10))
        else:
            screen.blit(self.surf_normal, (self.x, self.y))
class InputBox:
    def __init__(self, x, y, w, h, text=''):
        self.rect = pygame.Rect(x, y, w, h)
        self.color_inactive = (100, 100, 100)
        self.color_active = (255, 255, 255) # 激活时变白
        self.color = self.color_inactive
        self.text = text
        self.font = get_font(24)
        self.txt_surface = self.font.render(text, True, self.color)
        self.active = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            # 点击切换激活状态
            if self.rect.collidepoint(event.pos):
                print("[Debug] InputBox ACTIVATED!")
                self.active = not self.active
            else:
                self.active = False
            self.color = self.color_active if self.active else self.color_inactive
            
        if event.type == pygame.KEYDOWN:
            if self.active:
                if event.key == pygame.K_RETURN:
                    pass # 回车不做处理，由外部逻辑决定
                
                elif event.key == pygame.K_BACKSPACE:
                    self.text = self.text[:-1]
                elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
                    try:
                        # Pygame 2.2+ 用法
                        clipboard_content = pygame.scrap.get(pygame.SCRAP_TEXT)
                        
                        if clipboard_content:
                            # 2.2+ 可能返回 bytes 或 str，需要判断
                            if isinstance(clipboard_content, bytes):
                                paste_text = clipboard_content.decode('utf-8')
                            else:
                                paste_text = str(clipboard_content)
                                
                            paste_text = paste_text.strip().replace('\0', '')
                            if paste_text.isascii(): # 过滤
                                self.text += paste_text
                    except Exception as e:
                        print(f"Paste error: {e}")
                
                else:
                    # 普通打字
                    self.text += event.unicode
                
                # 更新渲染文字
                self.txt_surface = self.font.render(self.text, True, self.color)

    def draw(self, screen):
        # 战地风格：只画底边线
        pygame.draw.line(screen, self.color, (self.rect.x, self.rect.bottom), (self.rect.right, self.rect.bottom), 2)
        screen.blit(self.txt_surface, (self.rect.x + 5, self.rect.y + 5))
        
        # 标签提示
        label = get_font(24).render("SERVER ADDRESS (IP:PORT)", True, (150, 150, 150))
        screen.blit(label, (self.rect.x, self.rect.y - 20))
class Game: 
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
        from ui_sidebar import Minimap
        self.minimap = Minimap(self)
        self.auth_ui = LoginUI(self)
        self.lobby_ui = LobbyUI(self)
        from updatelog import UpdateLogUI
        self.update_log = UpdateLogUI(self) 
        from warstory import WarStoryUI
        self.story_ui = WarStoryUI(self)   
        from basesetting import BaseSettingUI
        self.setting_ui = BaseSettingUI(self)   
        from selfdefine import SkirmishUI
        self.skirmish_ui = SkirmishUI(self)   
        from environment import EnvironmentManager
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
            from factions import get_random_faction
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
    def screen_to_world(self, pos):
        return vec(pos[0] / self.zoom + self.camera_offset.x, pos[1] / self.zoom + self.camera_offset.y)  
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
                            
                            from factions import get_random_faction
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

        if self.current_map and self.current_map.bases_config:
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

        
    def perform_rebuild_base(self, cost, team, spawn_pos):
        # 1. [修改] 扣钱：不再区分 my_team 还是 enemy，直接查字典
        if team in self.team_resources:
            self.team_resources[team] -= cost
        
        # 2. 生成基地 (保持不变)
        from base_classes import BaseBuilding 
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
        from base_classes import FloatingText
        self.particles.add(FloatingText(spawn_pos, "BASE REBUILT!", GREEN_HAT))
    def sync_client_state(self, snapshot):
        # 1. 同步资源
        if 'res' in snapshot:
            self.team_resources = snapshot['res']

        # 2. 同步子弹
        self.projectiles = [] 
        if 'projs' in snapshot:
            for p_data in snapshot['projs']:
                # [关键] 读取 bsv
                bsv = p_data.get('bsv', 0)
                
                # 创建对象 (使用关键字参数防止错位)
                p = Projectile(
                    game=self, 
                    pos=vec(p_data['x'], p_data['y']), 
                    target=None, # Client 不保存 target 引用
                    team="neutral", 
                    damage=0, 
                    d_type=p_data['type'],
                    breakshellvalue=bsv # 传入等级
                )
                if 'lt' in p_data: p.life_time = p_data['lt']
                if 'ml' in p_data: p.max_life = p_data['ml']                
                if "tx" in p_data:
                    p.target_dest = vec(p_data["tx"], p_data["ty"])
                
                self.projectiles.append(p)
        # 3. 同步单位
        server_uids = set()
        
        # [第一步] 更新或生成存在的单位
        for data in snapshot['units']:
            uid = data['uid']
            server_uids.add(uid)
            
            found_unit = None
            for u in self.all_units:
                if u.uid == uid:
                    found_unit = u
                    break
            
            if found_unit:
                u = found_unit
                # 更新属性
                u.team = data['team']
                u.pos = vec(data['x'], data['y'])
                u.hp = data['hp']
                u.shield = data['sh']
                u.max_shield = data['msh']
                if 'angle' in data: u.angle = data['angle']
                if 'ta' in data: u.turret_angle = data['ta']
                u.update_rect()
                if "st" in data: 
                    u.state = data["st"]
                    u.deploy_timer = data.get("dt", 0)
                    u.pack_timer = data.get("pt", 0)
                if "bt" in data:
                    u.build_timer = data["bt"]
                    if "btt" in data: u.build_time_total = data["btt"]
                    u.is_building = (u.build_timer > 0)
                
                if u.__class__.__name__ == "DroneCarrier":
                    if 'st_c' in data: u.carrier_state = data['st_c']
                elif u.__class__.__name__ == "StealthHeli":
                    if 'st_h' in data:
                        u.stealth_mode = data['st_h']
                        u.is_stealth = u.stealth_mode
                elif u.__class__.__name__ == "APC":
                    if 'rep' in data: u.is_repairing = data['rep']
                elif u.__class__.__name__ == "TerminatorIFV":
                    if 'ph' in data: u.phase = data['ph']
                elif u.__class__.__name__ == "ShockwaveVehicle":
                    if 'sc' in data: u.shock_cooldown = data['sc']
                elif u.__class__.__name__ == "AC130":
                    if 'ox' in data: u.orbit_center = vec(data['ox'], data['oy'])
                    if 'oa' in data: u.orbit_angle = data['oa']
                    if 'st_a' in data: u.state = data['st_a']
                elif u.__class__.__name__ == "FighterJet":
                    if 'ammo' in data: 
                        u.ammo = data['ammo']
                    if 'st_f' in data: 
                        u.state = data['st_f']
                elif u.__class__.__name__ == "AttackPlane":
                    if 'bomb' in data: 
                        u.has_bomb = data['bomb']
                    if 'st_f' in data: 
                        u.state = data['st_f']
                elif u.__class__.__name__ == "LaserDestroyer":
                    if 'cl' in data: u.charge_level = data['cl']
                elif u.__class__.__name__ == "ShipMissile":
                    if 'wob' in data: u.wobble_timer=data['wob']
                elif u.__class__.__name__ == "MegaRocket":
                    if "tx" in data and "ty" in data:
                        u.target_dest = vec(data["tx"], data["ty"])  
                elif u.__class__.__name__ == "TankCarrier":
                    has_tank = data.get("lt", False)
                    
                    if has_tank:
                        if not u.loaded_tank:
                            u.loaded_tank = True 
                        if 'tta' in data:
                            u.turret_angle = data['tta']
                    else:
                        u.loaded_tank = None            
            else:
                self.spawn_unit_by_name(data['cls'], vec(data['x'], data['y']), data['team'], uid,target_pos=(1000,1000))

        for u in self.all_units[:]:
            if u.uid not in server_uids:
                self.all_units.remove(u)
        server_b_uids = set()
        if 'buildings' in snapshot:
            for b_data in snapshot['buildings']:
                uid = b_data['uid']
                server_b_uids.add(uid)
                
                found_b = None
                for b in self.all_buildings:
                    if b.uid == uid:
                        found_b = b
                        break
                
                # [优化] 如果没找到，先生成，然后统一走更新逻辑
                if not found_b:
                    found_b = self.spawn_building_by_data(b_data)
                
                if found_b:
                    found_b.hp = b_data['hp']
                    found_b.team = b_data['team'] 
                    found_b.progress = b_data.get('prog', 0.0)
                    if 'cap' in b_data: found_b.capture_progress = b_data['cap']
                    if 'ang' in b_data: found_b.angle = b_data['ang'] # 移动到这里通用
                    
                    found_b.synced_queue_len = b_data.get('q_len', 0)
                    found_b.is_upgraded = b_data.get('upg', False)

                    # 2. 倒塌状态
                    if b_data.get('collapsed', False) and not getattr(found_b, 'is_collapsed', False):
                        if hasattr(found_b, 'start_collapse'): found_b.start_collapse()

                    # 3. 特殊建筑逻辑
                    b_type = getattr(found_b, 'b_type', '')
                    
                    if b_type == 'bastion' and 't_angs' in b_data:
                        if hasattr(found_b, 'turrets'):
                            for i, angle in enumerate(b_data['t_angs']):
                                if i < len(found_b.turrets):
                                    found_b.turrets[i]['angle'] = angle
                                    
                    if b_type == "prototype_gen":
                        found_b.loaded_weapon = b_data.get("lw")
                        found_b.charge_timer = b_data.get("ct")
                        found_b.charge_time_total = b_data.get("ctt")
                        found_b.is_ready = b_data.get("rdy", False)
                        
                        # 同步武器对象 (同上文修正)
                        if found_b.loaded_weapon:
                            if not found_b.weapon_obj or found_b.weapon_obj.b_type != found_b.loaded_weapon:
                                if found_b.loaded_weapon == "iron_curtain":
                                    found_b.weapon_obj = IronCurtain(self, found_b.pos, found_b.team, found_b)
                                elif found_b.loaded_weapon == "nuke_silo":
                                    found_b.weapon_obj = NukeSilo(self, found_b.pos, found_b.team, found_b)
                        else:
                            found_b.weapon_obj = None

            for b in self.all_buildings[:]:
                if b.uid not in server_b_uids:
                    # [修复] 摩天大楼和寺庙废墟不移除
                    if hasattr(b, 'b_type') and b.b_type in ["skyscraper", "temple"]: continue
                    self.all_buildings.remove(b)
                if hasattr(b, 'b_type') and b.b_type == "laser_turret" and 't_uids' in b_data:
                    # 根据 UID 列表重建 targets 列表
                    b.targets = []
                    for tid in b_data['t_uids']:
                        for u in self.all_units:
                            if u.uid == tid: b.targets.append(u); break

        # 5. 同步特效
        if 'fx' in snapshot:
            for evt in snapshot['fx']:
                if evt['type'] == 'EXPLOSION':
                    pos = vec(evt['x'], evt['y'])
                    d_type = evt.get('dt', 'normal')

                    if d_type == "heavy_shell":
                        for i in range(12):
                            Particle(self.particles, pos, (200, 200, 255), 4, 30, 8) # 蓝白冲击波
                        # 火球
                        for _ in range(20): 
                            Particle(self.particles, pos, ORANGE, random.uniform(2, 5), 50, 12)
                        # 烟雾
                        for _ in range(15): 
                            Particle(self.particles, pos, (80, 80, 80), random.uniform(1, 3), 80, 15)                   
                    elif d_type == "behemoth_bomb" or d_type == "missile":
                        for i in range(36):
                            angle = i * 10
                            speed = 6
                            vel = vec(speed, 0).rotate(angle)
                            Particle(self.particles, pos, WHITE, speed, 40, 10)
                        for _ in range(40): Particle(self.particles, pos, ORANGE, random.uniform(1, 4), 60, 15)
                        for _ in range(20): Particle(self.particles, pos, (50, 50, 50), random.uniform(2, 5), 80, 20)
                    elif d_type == "rocket" :
                        for _ in range(15): Particle(self.particles, pos, ORANGE, random.uniform(2, 5), 30, 6)
                        for _ in range(10): Particle(self.particles, pos, (50, 50, 50), random.uniform(1, 3), 40, 8)                        
                    elif d_type == "tank_shell" or d_type == "heavy":
                        for _ in range(8): Particle(self.particles, pos, ORANGE, 2, 20, 4)
                    elif d_type == "launch_smoke":
                        for _ in range(5):
                            Particle(self.particles, pos, (255, 200, 50), 2, 20, 8)
                        # 发射烟雾 
                        for _ in range(8):
                            p = Particle(self.particles, pos, (200, 200, 200, 150), 1, 60, 10)
                            p.vel = vec(random.uniform(-1,1), random.uniform(-1,1))
                    elif d_type == "mech_death" or d_type == "air_crash":
                        count = 15
                        color = ORANGE
                        speed = 3 
                        size = 5 
                        for _ in range(count):
                            Particle(self.particles, pos, color, random.uniform(0.5, speed), random.randint(20, 40), size)
                        for _ in range(5): Particle(self.particles,pos, (50, 50, 50), 1, 60, 6)
                    elif d_type == "normal":
                        count =  10
                        color = RED
                        speed = 1.5
                        size =  3
                        for _ in range(count):
                            Particle(self.particles, pos, color, random.uniform(0.5, speed), random.randint(20, 40), size)
                    else:
                        for _ in range(3): Particle(self.particles, pos, WHITE, 1, 15, 2)
                    
                    if d_type == "intercept":
                         Particle(self.particles, pos, CYAN, 0, 10, 10)
                if evt['type'] == 'FX_TARGET_LOCK':
                    pos = vec(evt['x'], evt['y'])
                    duration = evt.get('duration', 300)
                    from base_classes import TargetMarker
                    self.particles.add(TargetMarker(self, pos, duration))
                if evt['type'] == 'FX_SHOCKWAVE':
                    pos = vec(evt['x'], evt['y'])
                    base_angle = evt.get('angle', 0)
                    
                    for i in range(18): 
                        angle = base_angle - 90 + i * 10
                        vel = vec(5, 0).rotate(angle) # 注意这里是否需要负号，取决于 draw
                        Particle(self.particles, pos, (0, 255, 255), 5, 30, 5)
                if evt['type'] == 'FX_TEXT':
                    pos = vec(evt['x'], evt['y'])
                    text = evt['text']
                    
                    c_map = {"RED": RED, "CYAN": CYAN, "GREEN": GREEN_HAT, "YELLOW": YELLOW}
                    color = c_map.get(evt['color'], WHITE)
                    
                    self.particles.add(FloatingText(pos, text, color))
        # 6. 同步胜负状态
        if snapshot.get("game_over"):
            self.game_over = True
            self.winner = snapshot["winner"]
            self.state = "GAMEOVER"
            self.game_over_timer = 1800 
        #7. 同步音乐状态
        if "music_state" in snapshot:
            server_music_state = snapshot["music_state"]
            
            if not hasattr(self, 'current_music_state'):
                self.current_music_state = "MENU"
            
            if self.current_music_state != server_music_state:
                self.current_music_state = server_music_state
        if not self.has_received_first_snapshot and self.player_base:
            print("[Client] First Snapshot Received -> Init Camera")
            
            self.has_received_first_snapshot = True
            if self.state == "PLAYING" and not self.opening_animation_done:
                pass
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
                    return # 选中一个就退出，避免重叠冲突

        # 2. 检查单位
        for unit in self.all_units:
            if unit.rect.collidepoint(world_pos):
                if unit.team == target_team:
                    self.selected_entity = unit
                    return
    def spawn_unit(self, u_type, origin_pos, team):
        # 1. 寻找最佳生成点
        spawn_pos = vec(origin_pos)+(0,100)
        
        # 2. 寻找源头建筑
        source_building = None
        for b in self.all_buildings:
            if b.pos.distance_to(origin_pos) < 60: 
                source_building = b; break
        
        # 3. 智能选点
        if source_building:
            # 初始偏移距离 (从建筑半径开始)
            current_dist = source_building.radius + 40 
            max_dist = 500 # 防止死循环
            found = False
            
            # 尝试向外扩张
            while current_dist < max_dist and not found:
                # 尝试 8 个方向 (上下左右 + 斜向)
                angles = [90, 270, 0, 180, 45, 135, 225, 315]
                
                for angle in angles:
                    test_offset = vec(current_dist, 0).rotate(angle)
                    test_pos = source_building.pos + test_offset
                    
                    # 检查是否重叠
                    # 使用稍微大一点的 rect (比如 40x40) 模拟单位体积
                    test_rect = pygame.Rect(test_pos.x - 20, test_pos.y - 20, 40, 40)
                    collision_idx = test_rect.collidelist([b.rect for b in self.all_buildings])
                    if collision_idx != -1:
                        print(f"Collided with {self.all_buildings[collision_idx].b_type} at dist {current_dist}")                    
                    # 检查所有建筑 (包括源头，防止半径算小了卡在自己身上)
                    # 以及其他单位 (防止卡在别的坦克里)
                    collided = False
                    
                    # 查建筑
                    if test_rect.collidelist([b.rect for b in self.all_buildings]) != -1:
                        collided = True
                    
                    # 查单位 (可选，如果不想让单位叠在一起)
                    if not collided:
                        for u in self.all_units:
                            if u.alive and u.rect.colliderect(test_rect):
                                collided = True; break
                    
                    if not collided:
                        spawn_pos = test_pos
                        found = True
                        break # 找到方向了，跳出 angle 循环
                
                if found: break # 找到位置了，跳出 distance 循环
                
                # 没找到，扩大一圈继续找
                current_dist += 40 
            
            # 如果实在找不到 (被围死了)，只能强行生成在默认位置
            if not found:
                spawn_pos += vec(0, source_building.radius + 60)
                
        else:
            # 野外生成 (保持随机)
            spawn_pos += vec(random.randint(-20, 20), random.randint(-20, 20))
        if u_type == "rifleman": self.all_units.append(Rifleman(self, spawn_pos, team))
        elif u_type == "rocket": self.all_units.append(RocketTrooper(self, spawn_pos, team))
        elif u_type == "shotgunner": self.all_units.append(Shotgunner(self, spawn_pos, team))
        elif u_type == "armored": self.all_units.append(ArmoredCar(self, spawn_pos, team))
        elif u_type == "helicopter": self.all_units.append(Helicopter(self, spawn_pos, team))
        elif u_type == "wz10": self.all_units.append(WZ10(self, spawn_pos, team))
        elif u_type == "m1a2": self.all_units.append(M1A2(self, spawn_pos, team))
        elif u_type == "kirov":
            self.all_units.append(KirovAirship(self, spawn_pos, team))
            msg = "L30 REPORTING!" if team == self.my_team else "AIRSHIP DETECTED!"
            self.show_alert(msg)
        elif u_type == "sniper": self.all_units.append(Sniper(self, spawn_pos, team))
        elif u_type == "mech": self.all_units.append(HeavyMech(self, spawn_pos, team))
        elif u_type == "combat_engineer":
            from units import CombatEngineer
            self.all_units.append(CombatEngineer(self, spawn_pos, team))
        elif u_type == "missile_boat": 
            # 确保导入了 MissileBoat
            self.all_units.append(MissileBoat(self, spawn_pos, team))
        elif u_type == "apc":
            from units import APC
            self.all_units.append(APC(self, spawn_pos, team))
        elif u_type == "type99":
            from units import Type99
            self.all_units.append(Type99(self, spawn_pos, team))
        elif u_type == "himars":
            from units import HIMARS
            self.all_units.append(HIMARS(self, spawn_pos, team))
        elif u_type == "mi24":
            from units import Mi24
            self.all_units.append(Mi24(self, spawn_pos, team))
        elif u_type == "dronecarrier":
            from units import DroneCarrier
            self.all_units.append(DroneCarrier(self, spawn_pos, team))
        elif u_type == "stealheli":
            from units import StealthHeli
            self.all_units.append(StealthHeli(self, spawn_pos, team))
        elif u_type == "bmpt":
            from units import TerminatorIFV
            self.all_units.append(TerminatorIFV(self, spawn_pos, team))
        elif u_type == "waver":
            from units import ShockwaveVehicle
            self.all_units.append(ShockwaveVehicle(self, spawn_pos, team))
        elif u_type == "fighterjet":
            self.all_units.append(FighterJet(self, spawn_pos, team))
        elif u_type == "heavytransport":
            self.all_units.append(HeavyTransport(self, spawn_pos, team))
        elif u_type == "attackplane":
            self.all_units.append(AttackPlane(self, spawn_pos, team))
        elif u_type == "laserdestroyer":
            self.all_units.append(LaserDestroyer(self, spawn_pos, team))
        elif u_type == "antiairfrigate":
            self.all_units.append(AAFrigate(self, spawn_pos, team))
        elif u_type == "missilecruiser":
            self.all_units.append(MissileCruiser(self, spawn_pos, team))
        elif u_type == "megarocket":
            self.all_units.append(MegaRocket(self, spawn_pos, team))
        elif u_type == "tankcarrier":
            self.all_units.append(TankCarrier(self, spawn_pos, team))
            print("spawn")

    def spawn_unit_by_name(self, class_name, pos, team, server_uid,target_pos):

        """
        根据类名字符串创建对应的单位实例，并强制覆盖为服务器指定的 UID。
        """
        new_u = None
        
        # --- 步兵 ---
        if class_name == "Rifleman":
            new_u = Rifleman(self, pos, team)
        elif class_name == "RocketTrooper":
            new_u = RocketTrooper(self, pos, team)
        elif class_name == "Engineer":
            # 工程师通常带有目标，这里仅做同步位置，目标可能需要额外处理或忽略
            # 为了防止报错，给个默认空目标位置
            new_u = Engineer(self, pos, team, pos) 
        elif class_name == "Shotgunner":
            new_u = Shotgunner(self, pos, team)
        # --- 地面载具 ---
        elif class_name == "ArmoredCar":
            new_u = ArmoredCar(self, pos, team)
        elif class_name == "M1A2":
            new_u = M1A2(self, pos, team)
        elif class_name == "Harvester":
            temp_base = self.player_base if self.player_base else self.all_buildings[0]
            new_u = Harvester(self, pos, team, temp_base)

        # --- 空中单位 ---
        elif class_name == "Helicopter":
            new_u = Helicopter(self, pos, team)
        elif class_name == "WZ10":
            new_u = WZ10(self, pos, team)
        elif class_name == "KirovAirship":
            new_u = KirovAirship(self, pos, team)

        elif class_name == "ArmoredTrain":
            from units import ArmoredTrain
            new_u = ArmoredTrain(self, pos)
        elif class_name == "TrainCarriage":
            from units import TrainCarriage
            new_u = TrainCarriage(self, pos, team, None, 0) 
        elif class_name == "Battleship":
            new_u = Battleship(self, pos, team)
        elif class_name == "ScavengerWalker":
            from units import ScavengerWalker
            new_u = ScavengerWalker(self, pos)        
        # --- 特殊单位 / 技能 ---
        elif class_name == "AC130":
            # AC130 需要 orbit_center，网络同步过来的是当前 pos
            # 我们可以把当前 pos 当作轨道中心（虽然会有误差，但在客户端仅作显示通常足够）
            new_u = AC130(self, pos, team)
        elif class_name == "CruiseMissile":
            new_u = CruiseMissile(self, pos, team)
        elif class_name == "ShipMissile":
            new_u = ShipMissile(self, pos, team)            
        elif class_name == "ParatrooperPlane":
            new_u = ParatrooperPlane(self, pos, team)
            new_u.pos = vec(pos) 
        elif class_name == "Sniper": new_u = Sniper(self, pos, team)
        elif class_name == "HeavyMech": new_u = HeavyMech(self, pos, team)
        elif class_name == "MissileBoat": new_u = MissileBoat(self, pos, team)
        elif class_name == "CombatEngineer":
            from units import CombatEngineer
            new_u = CombatEngineer(self, pos, team)
        elif class_name == "APC":
            from units import APC
            new_u = APC(self, pos, team)
        elif class_name == "Type99":
            from units import Type99
            new_u = Type99(self, pos, team)
        elif class_name == "HIMARS":
            from units import HIMARS
            new_u = HIMARS(self, pos, team)
        elif class_name == "Mi24":
            from units import Mi24
            new_u = Mi24(self, pos, team)
        elif class_name == "StealthHeli":
            from units import StealthHeli
            new_u = StealthHeli(self, pos, team)
        elif class_name == "DroneCarrier":
            from units import DroneCarrier
            new_u = DroneCarrier(self, pos, team)
        elif class_name == "SuicideDrone":
            from units import SuicideDrone
            new_u = SuicideDrone(self, pos, team)
        elif class_name == "TerminatorIFV":
            from units import TerminatorIFV
            new_u = TerminatorIFV(self, pos, team)
        elif class_name == "ShockwaveVehicle":
            from units import ShockwaveVehicle
            new_u = ShockwaveVehicle(self, pos, team)
        elif class_name == "FighterJet":
            new_u = FighterJet(self, pos, team)
        elif class_name == "HeavyTransport":
            new_u = HeavyTransport(self, pos, team)
        elif class_name == "AttackPlane":
            new_u = AttackPlane(self, pos, team)
        elif class_name == "AAFrigate":
            new_u = AAFrigate(self, pos, team)
        elif class_name == "LaserDestroyer":
            new_u = LaserDestroyer(self, pos, team)
        elif class_name == "MissileCruiser":
            new_u = MissileCruiser(self, pos, team)
        elif class_name == "MegaRocket":                 
            new_u = MegaRocket(self, pos, team, target_pos) 
        elif class_name == "TankCarrier":                 
            new_u = TankCarrier(self, pos, team) 
        elif class_name == "MCV":
            new_u = MCV(self, pos, team)
        if new_u:
            new_u.uid = server_uid  
            self.all_units.append(new_u)
    def spawn_building_instantly(self, b_type, pos, team):
        
        new_b = None
        if b_type == "factory": new_b = FactoryBuilding(self, pos, team)
        elif b_type == "radar": new_b = RadarBuilding(self, pos, team)
        elif b_type == "mining": new_b = MiningRig(self, pos, team)
        elif b_type == "airfield": new_b = Airfield(self, pos, team)
        elif b_type == "power_plant": new_b = PowerPlant(self, pos, team)
        elif b_type == "research": new_b = ResearchCenter(self, pos, team)
        elif b_type == "tech_center": new_b = TechCenter(self, pos, team)
        elif b_type == "aa_turret": new_b = AntiAirTurret(self, pos, team)
        elif b_type == "laser_turret": new_b = LaserTurret(self, pos, team)
        elif b_type == "missile_def": new_b = MissileDefenseSystem(self, pos, team)
        elif b_type == "bunker": new_b = Bunker(self, pos, team)
        elif b_type == "shroud_gen": new_b = ShroudGen(self, pos, team)
        elif b_type == "shipyard": new_b = Shipyard(self, pos, team)
        elif b_type == "prototype_gen": new_b = PrototypeGen(self, pos, team)
        elif b_type == "ciws": new_b = CIWS(self, pos, team)        
        if new_b:
            self.all_buildings.append(new_b)
            # 播放音效或特效
            from base_classes import FloatingText
            self.particles.add(FloatingText(pos, "CONSTRUCTED", GREEN_HAT))
    def spawn_building_by_data(self, data):
        pos = vec(data['x'], data['y'])
        team = data['team']
        b_type = data['type'] # 建筑类型
        uid = data['uid']
        cls_name = data.get('cls', '')
        
        new_b = None
        # 根据 b_type 或 类名创建
        if b_type == "base": new_b = BaseBuilding(self, pos, team)
        elif b_type == "factory": new_b = FactoryBuilding(self, pos, team)
        elif b_type == "radar": new_b = RadarBuilding(self, pos, team)
        elif b_type == "mining": new_b = MiningRig(self, pos, team)
        elif b_type == "airfield": new_b = Airfield(self, pos, team)
        elif b_type == "research": new_b = ResearchCenter(self, pos, team)
        elif b_type == "missile_def": new_b = MissileDefenseSystem(self, pos, team)
        elif b_type == "aa_turret": new_b = AntiAirTurret(self, pos, team)
        elif b_type == "laser_turret": new_b = LaserTurret(self, pos, team)
        elif b_type == "bunker": new_b = Bunker(self, pos, team)        
        elif b_type == "house":
            from base_classes import CivilianHouse
            vid = data.get("vid", 0) # 获取 ID
            new_b = CivilianHouse(self, pos, variant_id=vid) 
        elif "OilDerrick" in cls_name: new_b = OilDerrick(self, pos)
        elif "MercenaryFactory" in cls_name: new_b = MercenaryFactory(self, pos)
        elif b_type == "power_plant":
            new_b = PowerPlant(self, pos, team)
        elif b_type == "shipyard":
            new_b = Shipyard(self, pos, team)
        elif b_type == "shroud_gen":
            new_b = ShroudGen(self, pos, team)
        elif  b_type== 'tech_center': 
            new_b = TechCenter(self, pos, team)
        elif cls_name == "CIWS" or b_type == "ciws":
            new_b = CIWS(self, pos,team)  
        if cls_name == "AncientTemple" or b_type == "temple":
            from base_classes import AncientTemple
            new_b = AncientTemple(self, pos)
        elif cls_name == "EMPGenerator":
            from base_classes import EMPGenerator
            new_b = EMPGenerator(self, pos)
        elif cls_name == "Lighthouse":
            
            new_b = Lighthouse(self, pos)
        # [修复] 确保 Skyscraper 也能被识别
        elif cls_name == "Skyscraper" or b_type == "skyscraper":
            from base_classes import Skyscraper
            new_b = Skyscraper(self, pos)
        elif cls_name == "CoastalGun" or b_type == "coastal_gun":
            new_b = CoastalGun(self, pos)
        elif cls_name == "Bastion" or b_type == "bastion":
            new_b = Bastion(self, pos)       
        elif cls_name == "PrototypeGen" or b_type == "prototype_gen":
            new_b = PrototypeGen(self, pos)    
        elif cls_name == "IronCurtain" or b_type == "iron_curtain":
            new_b = IronCurtain(self, pos)
        elif cls_name == "NukeSilo" or b_type == "nuke_silo":
            new_b = NukeSilo(self, pos)  
                                         
        elif cls_name == "CommStation" or b_type == "CommStation":
            from base_classes import CommStation
            new_b = CommStation(self, pos)
        extra = data.get('extra', {})
        
        if cls_name == "Bridge":
            from base_classes import Bridge
            orient = extra.get('orient', 'horizontal')
            new_b = Bridge(self, pos, orient)
        if new_b:
            new_b.uid = uid # 覆盖ID
            new_b.hp = data['hp'] # 同步血量
            self.all_buildings.append(new_b)
    def upgrade_tech(self, tech_type):
        self.tech_levels[tech_type] += 1
        self.particles.add(FloatingText(self.player_base.pos, f"{tech_type.upper()} UPGRADED!", YELLOW, 120))

    def spawn_engineer(self, target_pos, b_type):
        # 1. 确定出生点
        # 优先从基地出来，如果基地没了，就从初始点出来 (虽然没基地一般也造不了东西，但为了不崩)
        if self.player_base and self.player_base.alive:
            origin = self.player_base.pos
        else:
            origin = self.my_start_pos
            
        spawn_pos = origin + vec(0, 30)
        
        # 2. [修改] 传入正确的 team
        eng = Engineer(self, spawn_pos, self.my_team, target_pos)
        
        eng.target_type = b_type 
        self.all_units.append(eng)

    def issue_command(self, world_pos):
        target_entity = None
        
        my_team = self.my_team
        
        # 1. 搜索目标 (建筑)
        for b in self.all_buildings:
            # [修改] 只要不是我的队伍，且活着，就是潜在目标
            # 这包括 team="enemy" (对Client来说是Player) 和 team="neutral" (摩天大楼)
            if b.team != my_team and b.alive:
                if b.rect.collidepoint(world_pos):
                    target_entity = b
                    break
        
        # 2. 搜索目标 (单位)
        if not target_entity:
            for u in self.all_units:
                if u.team != my_team and u.rect.collidepoint(world_pos) and u.alive:
                    target_entity = u
                    break
        
        # 3. 执行指令
        if target_entity:
            # 如果选中了单位
            if self.selected_entity:
                # 检查防空
                if target_entity.is_air and not getattr(self.selected_entity, 'can_attack_air', False):
                    self.selected_entity.move_to(target_entity.pos)
                else:
                    if isinstance(u, CombatEngineer):
                        u.set_target(target_entity)
                    else:
                        self.selected_entity.set_target(target_entity)
        else:
            # 地面移动
            if self.selected_entity:
                self.selected_entity.move_to(world_pos)

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
                from factions import get_random_faction
                
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
            # === 开场动画逻辑 (Opening Animation - Snap Focus) ===
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
    def handle_online_playing(self):
        current_time = pygame.time.get_ticks()
        if not self.net.connected: # 简化超时判断
            self.state = "LOGIN"; self.reset_lobby_data(); return

        msgs = self.net.get_messages()
        if msgs: self.last_packet_time = current_time
        
        if self.my_role == "HOST":

            for msg in msgs:
                sender_addr = msg.get('_sender')
                # 如果 sender_addr 为空或不在表中，默认是 Host 自己 (team_0)
                # 注意：如果 Host 是单机调试网络功能，可能 sender_addr 为 None
                team_id = self.client_id_to_team.get(sender_addr, "team_0")
                if msg['type'] == 'CHAT':
                    self.chat_box.add_message(msg['text'], msg.get('name', 'Unknown'))
                
                # 移动/攻击/特殊操作
                elif msg['type'] == 'REQ_MOVE':
                    uids = msg['uids']
                    
                    # [必须加上这行]
                    target = vec(msg['x'], msg['y'])
                    for u in self.all_units:
                        if u.uid in msg['uids']:
                            print(f" - Found unit {u.uid}, Team: {u.team}")
                            if u.team == team_id: 
                                u.move_to(target)
                            else:
                                print(f" - [Reject] Team mismatch! Unit: {u.team}, Client: {team_id}")
                elif msg['type'] == 'REQ_ATTACK':
                    target = None
                    for x in self.all_units + self.all_buildings:
                        if x.uid == msg['target_uid']: target = x; break
                    
                    if target:
                        # [必须修改] 把 all_buildings 也加进去
                        all_commandable = self.all_units + self.all_buildings
                        
                        for u in all_commandable:
                            if u.uid in msg['uids'] and u.team == team_id:
                                if hasattr(u, 'set_target'):
                                    u.set_target(target)
                elif msg['type'] == 'REQ_SPAWN':
                    cost_map = {
                        "rifleman": RIFLEMAN_COST, "rocket": ROCKET_COST, "shotgunner": SHOTGUNNER_COST,"sniper": SNIPER_COST,
                        "armored": ARMORED_COST, "m1a2": M1A2_COST, "mech": MECH_COST,
                        "helicopter": HELICOPTER_COST, "wz10": WZ10_COST, "kirov": KIROV_COST,
                        "missile_boat": 600, "combat_engineer": 150, "apc": APC_COST,
                        "type99": TYPE99_COST, "himars": HIMARS_COST, "mi24": HIND_COST,
                        "dronecarrier": DRONECARRIER_COST, "stealheli": STEALHELI_COST, "bmpt": TERMINATOR_COST,"waver":SHOCKWAVE_COST,"fighterjet":FIGHTER_COST,"heavytransport":HEAVYTRANSPORT_COST,
                        "attackplane":ATTACKER_COST,"antiairfrigate":AABOAT_COST,"laserdestroyer":LASER_SHIP_COST,"missilecruiser":MissileCruiser_COST,"tankcarrier":TANKCARRIER_COST,
                    }
                    cost = cost_map.get(msg['u_type'], 0)
                    
                    if self.team_resources[team_id] >= cost:
                        b_uid = msg.get('b_uid')
                        target_building = None
                        if b_uid:
                            for b in self.all_buildings:
                                if b.uid == b_uid: target_building = b; break
                        
                        if target_building and target_building.team == team_id and hasattr(target_building, 'queue_unit'):
                            time_cost = BUILD_TIME_INFANTRY
                            u_type = msg['u_type']
                            if u_type in ["armored", "m1a2", "mech", "type99", "himars"]: time_cost = BUILD_TIME_TANK
                            elif u_type in ["helicopter", "wz10", "mi24","stealheli","heavytransport","fighterjet","attackplane"]: time_cost = BUILD_TIME_AIR
                            elif u_type == "kirov": time_cost = BUILD_TIME_AIRSHIP
                            elif u_type == "rifleman": time_cost = BUILD_TIME_INFANTRY
                            elif u_type == "rocket": time_cost = BUILD_TIME_INFANTRY*2
                            elif "shotgunner" in u_type: time_cost =  BUILD_TIME_INFANTRY*3
                            else: time_cost = BUILD_TIME_TANK                           
                            if target_building.queue_unit(msg['u_type'], time_cost):
                                self.team_resources[team_id]  -= cost

                        else:
                            self.team_resources[team_id] -= cost
                            self.spawn_unit(msg['u_type'], vec(msg['x'], msg['y']),team_id)
                
                elif msg['type'] == 'REQ_BUILD':
                    b_type = msg['b_type']
                    cost_map = {
                        "factory": FACTORY_COST, "radar": RADAR_COST, "mining": MINING_COST, 
                        "airfield": AIRFIELD_COST, "research": RESEARCH_COST, 
                        "missile_def": MISSILE_DEFENSE_COST, "aa_turret": AA_TURRET_COST, 
                        "laser_turret": LASER_TURRET_COST, "power_plant": POWER_PLANT_COST,
                        "shipyard": SHIPYARDCOST, "tech_center": TECH_CENTER_COST,"bunker":BUNKER_COST,
                        "shroud_gen":BLACKSHRODCOST,"prototype_gen":PROTOTYPECOST,"ciws":CIWS_COST
                    }
                    cost = cost_map.get(msg['b_type'], 0)

                    if self.team_resources[team_id] >= cost:
                        self.team_resources[team_id] -= cost
                        
                        if msg['b_type'] == "shipyard":
                            from base_classes import Shipyard
                            self.all_buildings.append(Shipyard(self, vec(msg['x'], msg['y']), team_id))
                        else:
                            spawn_origin = vec(0, 0)
                            found_origin = False
                            
                            dependency_map = {
                                "laser_turret": "research", 
                                "aa_turret": "radar",          
                                "missile_def": "radar",
                                "shroud_gen": "research",
                                "ciws":"research"
                                
                            }
                            
                            required_origin_type = dependency_map.get(b_type, "base") # 默认为 base
                            
                            candidates = []
                            for b in self.all_buildings:
                                if b.team == team_id and b.alive and getattr(b, 'b_type', '') == required_origin_type:
                                    candidates.append(b)
                            
                            if candidates:
                                print(f"[Build] No candidate found for {required_origin_type}, fallback to base.")
                                target_pos = vec(msg['x'], msg['y'])
                                best_b = min(candidates, key=lambda b: b.pos.distance_to(target_pos))
                                spawn_origin = best_b.pos
                                found_origin = True
                            else:
                                print(f"[Build] No candidate found for {required_origin_type}, fallback to base.")
                            if not found_origin:
                                # 回退到找基地
                                if team_id in self.bases and self.bases[team_id].alive:
                                    spawn_origin = self.bases[team_id].pos
                                else:
                                    # 基地也没了? 随便找个活着的建筑
                                    any_b = next((b for b in self.all_buildings if b.team == team_id and b.alive), None)
                                    if any_b: spawn_origin = any_b.pos
                            
                            # 生成工程师
                            eng = Engineer(self, spawn_origin, team_id, vec(msg['x'], msg['y']))
                            eng.target_type = b_type
                            self.all_units.append(eng)
                elif msg['type'] == 'REQ_BUILD_INSTANT':
                    b_type = msg['b_type']
                    pos = vec(msg['x'], msg['y'])
                    
                    self.spawn_building_instantly(b_type, pos, team_id)               
                elif msg['type'] == 'REQ_BUILD_PROTOTYPE':
                    p_type = msg['p_type'] 
                    cost_map = {
                        "iron_curtain": 2500,
                        "nuke_silo": 3000
                    }
                    cost = cost_map.get(p_type, 99999)
                    
                    # 1. 检查资金
                    if self.team_resources[team_id] >= cost:
                        
                        # 2. 寻找一个属于该玩家且空闲的 PrototypeGen
                        target_gen = None
                        for b in self.all_buildings:
                            if b.team == team_id and getattr(b, 'b_type', '') == 'prototype_gen':
                                # 必须没有挂载武器
                                if not getattr(b, 'loaded_weapon', None):
                                    target_gen = b
                                    break
                        
                        if target_gen:
                            # 扣钱
                            self.team_resources[team_id] -= cost
                            target_gen.build_prototype(p_type)
                        else:
                            pass
                elif msg['type'] == 'REQ_UPGRADE':
                    tech = msg['tech']
                    cost = 0
                    if tech == "airfield_unlock": cost = UPGRADE_AIRFIELD_COST
                    elif tech == "factory_unlock": cost = UPGRADE_FACTORY_COST
                    if cost > 0 and self.team_resources[team_id] >= cost:
                        for b in self.all_buildings:
                            # 必须是该队伍的建筑
                            if b.uid == msg['uid'] and b.team == team_id: 
                                b.is_upgraded = True
                                self.team_resources[team_id] -= cost
                                break
                
                elif msg['type'] == 'REQ_SUPPORT':
                    s_type = msg['s_type']; pos = vec(msg['x'], msg['y'])
                    cost = 0
                    if s_type == "ac130": cost = AC130_COST
                    elif s_type == "missile": cost = MISSILE_COST
                    elif s_type == "airdrop": cost = AIRDROP_COST
                    if self.team_resources[team_id] >= cost:
                        self.team_resources[team_id] -= cost
                        if s_type == "ac130": self.all_units.append(AC130(self, pos, team_id))
                        elif s_type == "missile": self.all_units.append(CruiseMissile(self, pos, team_id))
                        elif s_type == "airdrop": self.all_units.append(ParatrooperPlane(self, pos, team_id))                    
                    if s_type == "battleship_call":
                        # 不需要扣钱，直接调用
                        self.handle_battleship_call(team_id)    
            
                elif msg['type'] == 'REQ_SELL':
                    for b in self.all_buildings:
                        if b.uid == msg['uid'] and b.team == team_id: # 只能卖自己的
                            b.alive = False
                            self.team_resources[team_id] += msg['refund']
                            break
                
                elif msg['type'] == 'REQ_DEPLOY':
                    for u in self.all_units:
                        if u.uid == msg['uid']:
                            if u.team == team_id:
                                if u.alive and isinstance(u, MCV):
                                    success = u.deploy()
                                    if success:
                                        print(f"[Host] Team {team_id} deployed MCV {u.uid}")
                                    else:
                                        pass
                            else:
                                print(f"[Host Warning] Team {team_id} tried to deploy {u.team}'s MCV!")
                            break                
                elif msg['type'] == 'REQ_UNDEPLOY':
                    for b in self.all_buildings:
                        # [修正] 增加队伍检查，防止收起别人的基地
                        if b.uid == msg['uid'] and b.team == team_id and b.alive: 
                            b.undeploy()
                            print(f"[Host] Team {team_id} undeployed Base {b.uid}")
                            break
                
                elif msg['type'] == 'REQ_APC_LOAD':
                    for u in self.all_units:
                        if u.uid == msg['uid'] and u.team == team_id and isinstance(u, APC): u.load_units(); break
                
                elif msg['type'] == 'REQ_APC_UNLOAD':
                    for u in self.all_units:
                        if u.uid == msg['uid'] and u.team == team_id and isinstance(u, APC): u.unload_units(); break  
                elif msg['type'] == 'REQ_TANKCARRIER_LOAD':
                    for u in self.all_units:
                        if u.uid == msg['uid'] and u.team == team_id and isinstance(u, TankCarrier): u.load_units(); break   
                elif msg['type'] == 'REQ_TANKCARRIER_UNLOAD':
                    for u in self.all_units:
                        if u.uid == msg['uid'] and u.team == team_id and isinstance(u,TankCarrier ): u.unload_units(); break       
                elif msg['type'] == 'REQ_HEAVYTRANSPORT_LOAD':
                    for u in self.all_units:
                        if u.uid == msg['uid'] and u.team == team_id and isinstance(u, HeavyTransport): u.load_units(); break
                
                elif msg['type'] == 'REQ_HEAVYTRANSPORT_UNLOAD':
                    for u in self.all_units:
                        if u.uid == msg['uid'] and u.team == team_id and isinstance(u,HeavyTransport): u.unload_units(); break                          
                elif msg['type'] == 'REQ_TOGGLE':
                    for u in self.all_units:
                        # 必须检查 UID 和 Team (防止控制别人的兵)
                        if u.uid == msg['uid'] and u.team == team_id:
                            if hasattr(u, 'toggle_mode'):
                                u.toggle_mode()
                            break            
                elif msg['type'] == 'REQ_SKILL': # 合并后的通用类型
                    uid = msg['uid']
                    target_pos = vec(msg['x'], msg['y'])
                    skill_type = msg.get('skill', None) 
                    
                    found = False
                    
                    for u in self.all_units:
                        if u.uid == uid and u.team == team_id and u.alive:
                            if u.__class__.__name__ == "MissileCruiser":
                                u.start_charge(target_pos)
                                found = True
                            break
                    
                    if not found:
                        for b in self.all_buildings:
                            if b.uid == uid and b.team == team_id and b.alive:
                                if getattr(b, 'b_type', '') == 'prototype_gen' and b.weapon_obj:
                                    current_weapon = b.loaded_weapon 

                                    if skill_type and current_weapon in skill_type:
                                        b.weapon_obj.activate(target_pos)
                                        found = True
                                break
                elif msg['type'] == 'REQ_REBUILD_BASE':
                    cost = 5000
                    if self.team_resources[team_id] >= cost:
                        self.team_resources[team_id] -= cost
                        
                        from base_classes import BaseBuilding
                        
                        spawn_pos = vec(WORLD_WIDTH // 2, WORLD_HEIGHT // 2)                        
                        
                        new_base = BaseBuilding(self, spawn_pos, team_id)
                        self.all_buildings.append(new_base)

                        if not hasattr(self, 'bases'): self.bases = {}
                        self.bases[team_id] = new_base
                        
                        print(f"[Host] Team {team_id} rebuilt base at {spawn_pos}")

            self.update_game_world()
            
            for tid in self.team_resources:
                if self.team_resources[tid] < self.max_cmd_exp:
                    self.team_resources[tid] += self.current_income_rate
            

            self.send_snapshot()

        elif self.my_role == "CLIENT":
            for msg in msgs:
                if msg['type'] == 'CHAT':
                    self.chat_box.add_message(msg['text'], msg.get('name', 'Unknown'))
                elif msg['type'] == 'SNAPSHOT':
                    self.sync_client_state(msg)
            self.update_game_world()            
            self.particles.update()
            self.floating_texts.update()
            
            # [修复 3] 客户端移除旧的胜负判定，完全依赖 Host 的 Snapshot
            if self.game_over:
                self.state = "GAMEOVER"

    def handle_setup_packet(self, msg):

        if 'lakes_data' in msg: self.synced_lakes = msg['lakes_data']
        random.seed(msg.get('seed', 0))
        self.map_seed = msg.get('seed', 0)
        self.map_id = msg.get('map_id', 0)
        
        # [修改] 接收多人信息
        self.my_team = msg.get('your_team') # 默认 team_1
        self.teams_config = msg.get('teams_config', {})
        if self.my_team is None:
            print("[Client] ERROR: Host did not assign a team!")
            self.my_team = "team_1" # 强行修补 (不推荐，但能救急)        
        # 从 config 中提取自己的 faction 用于 UI 显示
        if self.my_team in self.teams_config:
            self.my_faction = self.teams_config[self.my_team]['faction']
        print(f"[Client] My Team is: {self.my_team}")        
        # enemy_faction 不再单一，可以设为 None 或显示列表
        # self.enemy_faction = ... 
        
        self.reset_game()
        self.state = "LOADING"
    def send_snapshot(self):
        # 1. 建筑数据
        buildings_data = []
        for b in self.all_buildings:
            progress = 0.0
            
            # 计算生产进度 (工厂/机场)
            if hasattr(b, 'current_production') and b.current_production:
                total = b.current_production['total_time']
                current = b.current_production['timer']
                if total > 0: progress = (total - current) / total           
            # 计算建造进度 (工程师正在建造的地基? 不，这里通常是 Unit 的属性)
            # 如果有 spawn_timer (如油井生产资源，或者旧版逻辑)
            elif hasattr(b, 'spawn_timer') and hasattr(b, 'build_time_total') and b.build_time_total > 0:
                 progress = b.spawn_timer / b.build_time_total
            
            cap_prog = getattr(b, 'capture_progress', 0.0)
            
            # 额外数据 (桥梁方向)
            extra = {}
            if getattr(b, 'b_type', '') == 'bridge': 
                extra['orient'] = getattr(b, 'orientation', 'horizontal')
            q_len = len(b.production_queue) if hasattr(b, 'production_queue') else 0
            if getattr(b, 'current_production', None):
                q_len += 1
            b_data = {
                "uid": b.uid,
                "cls": b.__class__.__name__,
                "type": getattr(b, 'b_type', 'unknown'),
                "team": b.team,
                "x": int(b.pos.x), "y": int(b.pos.y),
                "hp": b.hp,
                "prog": progress,
                "cap": cap_prog,
                "extra": extra,
                "collapsed": getattr(b, 'is_collapsed', False),
                "upg": getattr(b, 'is_upgraded', False),
                "q_len": q_len,
    
            }
            b_type = getattr(b, 'b_type', '')
            

            if b_type in ["bunker", "aa_turret", "coastal_gun","ciws"]:
                b_data["ang"] = getattr(b, 'angle', 0) 
            if b_type in ["bastion"]:
                if hasattr(b, 'turrets'):
                    turret_angles = [t['angle'] for t in b.turrets]
                    b_data["t_angs"] = turret_angles                
            if b.b_type == "house":
                b_data["gc"] = len(b.garrison)     
            if b.b_type == "lighthouse":
                b_data["gc"] = len(b.garrison)  
            if b.b_type == "laser_turret":
                b_data["t_uids"] = [t.uid for t in b.targets]
            if b.b_type == "prototype_gen":
                b_data["lw"] = getattr(b, 'loaded_weapon', None)
                b_data["ct"] = getattr(b, 'charge_timer', 0)
                b_data["ctt"] = getattr(b, 'charge_time_total', 0)
                b_data["rdy"] = getattr(b, 'is_ready', False)
            if getattr(b, 'b_type', '') == "house":
                b_data["vid"] = getattr(b, 'variant_id', 0)

            buildings_data.append(b_data)        
        # 2. 单位数据
        units_data = []
        for u in self.all_units:
            u_data = {
                "uid": u.uid, "cls": u.__class__.__name__, "team": u.team, 
                "x": int(u.pos.x), "y": int(u.pos.y), "hp": u.hp, "angle": getattr(u, 'angle', 0),"ta": getattr(u, 'turret_angle', 0), "sh": getattr(u, 'shield', 0),
                "msh": getattr(u, 'max_shield', 0),
            }
            if u.__class__.__name__ == "Harvester":
                u_data["st"] = getattr(u, 'state', "IDLE")
            if u.__class__.__name__ == "DroneCarrier":
                u_data["st_c"] = getattr(u, 'carrier_state', "MOBILE")
            if u.__class__.__name__ == "APC":
                u_data["rep"] = getattr(u, 'is_repairing', False)            
            if u.__class__.__name__ == "StealthHeli":
                u_data["st_h"] = getattr(u, 'stealth_mode', True) 
            if u.__class__.__name__ == "ShockwaveVehicle":
                u_data["sc"] = getattr(u, 'shock_cooldown', 0)  
            if u.__class__.__name__ == "AC130":
                u_data["ox"] = int(u.orbit_center.x)
                u_data["oy"] = int(u.orbit_center.y)
                u_data["oa"] = u.orbit_angle
                u_data["st_a"] = u.state # 状态也同步
            if u.__class__.__name__ == "LaserDestroyer":
                u_data["cl"] = getattr(u, 'charge_level', 0)
            if u.__class__.__name__ == "FighterJet":
                u_data["bomb"] = getattr(u, 'has_bomb', False)  
                u_data["st_f"] = getattr(u, 'state', "ORBITING") 
            if u.__class__.__name__ == "AttackPlane":
                u_data["bomb"] = getattr(u, 'has_bomb', False)  
                u_data["st_f"] = getattr(u, 'state', "ORBITING")            
            if u.__class__.__name__ == "ShipMissile":
                u_data["wob"] = getattr(u, 'wobble_timer', 0)  
            if u.__class__.__name__ == "MegaRocket":
                # 获取目标点
                td = getattr(u, 'target_dest', None)
                if td:
                    # 拆解为基本类型 (int 或 float)
                    u_data["tx"] = int(td.x)
                    u_data["ty"] = int(td.y)
                else:
                    # 默认值
                    u_data["tx"] = 0
                    u_data["ty"] = 0 
            if u.__class__.__name__ == "TankCarrier":
                u_data["lt"] = bool(u.loaded_tank)
                if u.loaded_tank:
                    u_data["tta"] = getattr(u, 'turret_angle', 0)                       
            if isinstance(u, Engineer): 
                u_data["bt"] = u.build_timer
                u_data["btt"] = u.build_time_total
            
            if isinstance(u, HIMARS):
                u_data["st"] = u.state
                u_data["dt"] = u.deploy_timer
                u_data["pt"] = u.pack_timer
                
            units_data.append(u_data)

        # 3. 投射物数据
        projs_data = []
        for p in self.projectiles:
            p_data = {
                "x": int(p.pos.x), 
                "y": int(p.pos.y), 
                "type": p.d_type,
                "bsv": getattr(p, 'breakshellvalue', 0),
                "lt": getattr(p, 'life_time', 0),
                "ml": getattr(p, 'max_life', 0)
            }
            
            # [新增] 同步目标位置 (用于激光和导弹绘制)
            if p.target:
                p_data["tx"] = int(p.target.pos.x)
                p_data["ty"] = int(p.target.pos.y)
            elif p.target_dest:
                p_data["tx"] = int(p.target_dest.x)
                p_data["ty"] = int(p.target_dest.y)
                
            projs_data.append(p_data)

        # 4. 构建并发送
        snapshot = {
            "type": "SNAPSHOT",
            "units": units_data,
            "buildings": buildings_data,
            "projs": projs_data,
            "fx": list(self.net_events), 
            "msgs": self.broadcast_msgs,
            
            # [修改] 直接发送完整的资源字典
            "res": self.team_resources, 
            
            "game_over": self.game_over,
            "winner": self.winner,
            "music_state": getattr(self, 'current_music_state', 'MENU') 
        }
        self.net.send(snapshot)
        
        # 5. 清理一次性数据
        self.net_events = [] 
        self.broadcast_msgs = []
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

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    m_pos = pygame.mouse.get_pos()
                    if self.btn_easy.collidepoint(m_pos): self.difficulty = "EASY"; self.reset_game(); self.state = "LOADING" ; self.play_music(self.common_music["loading"])
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
        # === 7. 游戏进行中 (PLAYING) ===
    # === 7. 游戏进行中 (PLAYING) ===
        if self.state == "PLAYING":
            # [关键] 提前定义 my_team
            my_team =self.my_team

            # --- WASD 移动 ---
            if not self.chat_box.active: # 聊天时禁用移动
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
                
                # 缩放控制
                if event.type == pygame.MOUSEWHEEL:
                    old_zoom = self.zoom
                    if event.y > 0: self.zoom = min(2.0, self.zoom + 0.1)
                    else: self.zoom = max(0.5, self.zoom - 0.1)
                    if self.zoom != old_zoom:
                        center_world = self.screen_to_world((SCREEN_WIDTH/2, SCREEN_HEIGHT/2))
                        new_off_x = center_world.x - (SCREEN_WIDTH/2) / self.zoom
                        new_off_y = center_world.y - (SCREEN_HEIGHT/2) / self.zoom
                        self.camera_offset = vec(new_off_x, new_off_y)
                
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
                    elif event.key == pygame.K_F8:
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
                                pygame.mixer.music.set_volume(self.master_volume)
                            elif self.btn_vol_up.collidepoint(m_pos):
                                self.master_volume = min(1.0, self.master_volume + 0.1)
                                pygame.mixer.music.set_volume(self.master_volume)
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
                        
                        if units_to_command:
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
                    if event.button == 2: self.dragging = False
                    if event.button == 1: 
                        if self.selection_start and self.selection_rect:
                            self.handle_box_selection()
                        self.selection_start = None
                        self.selection_rect = None
                        self.dragging = False
                
                # 鼠标移动 (拖拽镜头/框选)
                if event.type == pygame.MOUSEMOTION:
                    if self.dragging and not self.selection_start:
                        m_pos = pygame.mouse.get_pos()
                        delta = vec(m_pos) - self.last_mouse_pos
                        self.camera_offset -= delta / self.zoom
                        self.last_mouse_pos = vec(m_pos)
                        map_w = self.current_map.width if self.current_map else WORLD_WIDTH
                        map_h = self.current_map.height if self.current_map else WORLD_HEIGHT
                        self.camera_offset.x = max(-500, min(self.camera_offset.x, map_w - SCREEN_WIDTH/self.zoom + 500))
                        self.camera_offset.y = max(-500, min(self.camera_offset.y, map_h - SCREEN_HEIGHT/self.zoom + 500))

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
                from base_classes import FloatingText
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
            "bunker": BUNKER_COST, "shroud_gen": BLACKSHRODCOST,"prototype_gen":PROTOTYPECOST,"iron_curtain":IRONCURTAINCOST,"nuke_silo":NUKESILOCOST,"ciws":CIWS_COST
        }
        cost = cost_map.get(self.place_building_type, 0)

        # 2. 水域判定
        in_water = False
        if hasattr(self, 'lakes'):
            # 先假设不在水里
            
            # 第一步：检查是否在任何 Lake 范围内
            for lake in self.lakes:
                r = lake['rect'] if isinstance(lake, dict) else lake
                if r.collidepoint(pos):
                    in_water = True
                    
                    if hasattr(self.current_map, 'islands'):
                        # 创建一个小的检测点
                        pt_rect = pygame.Rect(int(pos.x), int(pos.y), 1, 1)
                        
                        if pt_rect.collidelist(self.current_map.islands) != -1:
                            in_water = False
                    
                    break # 判定结束
        
        # 3. 建造位置合法性
        is_shipyard = (self.place_building_type == "shipyard")
        
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
                        from base_classes import Shipyard
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
                title_font=pygame.font.SysFont("SimHei",60,bold=True)  
                location_font=pygame.font.SysFont("SimHei", 18) 
                desc_font = pygame.font.SysFont("SimHei", 24)

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

            # 4. 绘制预览图 (右侧或居中)
            if self.current_map.preview_image:
                preview = pygame.transform.scale(self.current_map.preview_image, (800, 500))
                
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
        
        t = self.ui_font.render(f"LOADING... {int(self.loading_progress*100)}%", True, WHITE)
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
            
            else:
                # Host / Single
                self.current_map.generate(seed=self.map_seed)
                self.apply_map_data()

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

        # 3. 实例化基地 (核心修复)
        if self.current_map and self.current_map.bases_config:
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
    def start_rematch(self):
        # 只有 Host 负责发起 SETUP
        if self.my_role == "HOST":
            # 重新随机地图
            self.map_id = random.randint(0, len(self.maps)-1)
            seed = random.randint(0, 1000000)
            random.seed(seed)
            
            # 生成新地图数据
            MapClass = self.maps[self.map_id]
            self.current_map = MapClass(self)
            self.current_map.generate(seed)
            from factions import get_random_faction
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
    def handle_lobby_network(self):
        msgs = self.net.get_messages()
        for msg in msgs:
            if msg['type'] == 'CHAT':
                self.chat_box.add_message(msg['text'], msg['team'])
            
            # Host 逻辑
            if self.my_role == "HOST":
                if msg['type'] == 'JOIN_REQUEST':
                    # 将玩家加入列表
                    new_player = {"id": msg['_sender'], "name": msg['name'], "ready": False}
                    self.lobby_players.append(new_player)
                    # 广播更新
                    self.broadcast_lobby_state()
                
                elif msg['type'] == 'LOBBY_READY':
                    # 更新玩家准备状态
                    for p in self.lobby_players:
                        if p['id'] == msg['_sender']:
                            p['ready'] = msg['status']
                            break
                    self.broadcast_lobby_state()

            # Client 逻辑
            elif self.my_role == "CLIENT":
                if msg['type'] == 'LOBBY_STATE':
                    self.lobby_players = msg['players']
                    self.map_id = msg['map_id']
                
                elif msg['type'] == 'LOBBY_START':
                    if 'config' in msg:
                        self.lobby_config = msg['config']
                        
                    self.state = "WAITING"

    def broadcast_lobby_state(self):
        host_info = {"id": "host", "name": self.player_info['name'], "ready": True}
        all_players = [host_info] + self.lobby_players
        
        self.net.send({
            "type": "LOBBY_STATE",
            "players": all_players,
            "map_id": self.map_id
        })

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

if __name__ == "__main__":
    game = Game()
    game.run()