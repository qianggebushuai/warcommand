import pygame
from core.settings import *
import os
import sys
from ui_login import BFInput
from core.utils import resource_path, get_font

# 辅助函数


class SkirmishUI:
    def __init__(self, game):
        self.game = game
        self.font = get_font(20)
        self.font_title = get_font(40, bold=True)
        
        # 布局
        self.panel_x = 50
        self.panel_y = 50
        self.panel_w = SCREEN_WIDTH - 100
        self.panel_h = SCREEN_HEIGHT - 100
        
        # --- 1. 地图选择 (左侧) ---
        self.map_rect = pygame.Rect(self.panel_x + 20, self.panel_y + 80, 400, 300)
        self.map_prev = pygame.Rect(self.map_rect.x, self.map_rect.bottom + 10, 40, 40)
        self.map_next = pygame.Rect(self.map_rect.right - 40, self.map_rect.bottom + 10, 40, 40)
        
        # --- 2. 设置区域 (右侧) ---
        self.setting_x = self.panel_x + 450
        self.setting_y = self.panel_y + 80
        
        # A. 经济设置
        # 初始资金
        self.input_money = BFInput(self.setting_x + 150, self.setting_y, 100, 30, text="5000")
        # 增长倍率
        self.input_rate = BFInput(self.setting_x + 150, self.setting_y + 50, 100, 30, text="1.0")
        
        # B. 阵营选择
        self.btn_faction = pygame.Rect(self.setting_x + 150, self.setting_y + 100, 150, 30)
        
        # C. AI 数量
        self.ai_count = 1
        self.btn_ai_minus = pygame.Rect(self.setting_x + 150, self.setting_y + 150, 30, 30)
        self.btn_ai_plus = pygame.Rect(self.setting_x + 220, self.setting_y + 150, 30, 30)
        
        # D. 模式选择 (Checkboxes)
        # "cards", "normal" (默认), "economy", "bombard"
        self.modes = {
            "normal": True, # 基础模式，默认勾选
            "cards": False,
            "economy": False,
            "bombard": False
        }
        self.mode_rects = {}
        for i, mode in enumerate(["normal", "cards", "economy", "bombard"]):
            r = pygame.Rect(self.setting_x + 20, self.setting_y + 220 + i*40, 20, 20)
            self.mode_rects[mode] = r

        # --- 3. 底部按钮 ---
        self.btn_start = pygame.Rect(SCREEN_WIDTH - 250, SCREEN_HEIGHT - 100, 200, 50)
        self.btn_back = pygame.Rect(50, SCREEN_HEIGHT - 100, 150, 50)

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: self.game.running = False
            
            self.input_money.handle_event(event)
            self.input_rate.handle_event(event)
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                m_pos = pygame.mouse.get_pos()
                
                # 地图切换
                if self.map_prev.collidepoint(m_pos):
                    self.game.map_id = (self.game.map_id - 1) % len(self.game.maps)
                elif self.map_next.collidepoint(m_pos):
                    self.game.map_id = (self.game.map_id + 1) % len(self.game.maps)
                
                # 阵营切换
                elif self.btn_faction.collidepoint(m_pos):
                    factions = ["USA", "CHINA", "RUSSIA"]
                    curr = getattr(self.game, 'my_faction', 'USA')
                    try: idx = factions.index(curr)
                    except: idx = 0
                    self.game.my_faction = factions[(idx + 1) % len(factions)]
                
                # AI 数量
                elif self.btn_ai_minus.collidepoint(m_pos):
                    self.ai_count = max(1, self.ai_count - 1)
                elif self.btn_ai_plus.collidepoint(m_pos):
                    # 限制最大 AI 数 (取决于地图 max_players - 1)
                    map_max = getattr(self.game.maps[self.game.map_id], 'max_players', 4)
                    self.ai_count = min(map_max - 1, self.ai_count + 1)
                

                        
                # 开始游戏
                elif self.btn_start.collidepoint(m_pos):
                    self.start_game()
                    
                # 返回
                elif self.btn_back.collidepoint(m_pos):
                    self.game.state = "MENU"
                # 模式勾选
                for mode, rect in self.mode_rects.items():
                    if rect.collidepoint(m_pos):
                        self.modes[mode] = not self.modes[mode]
    def start_game(self):
        # 1. 应用设置
        try:
            money = int(self.input_money.text)
            rate = float(self.input_rate.text)
        except: money=2000; rate=0.0
        selected_map_id = self.game.map_id        
        self.game.lobby_config["money"] = money
        self.game.lobby_config["rate"] = rate
        
        # 2. 生成 teams_config
        # P1: 玩家
        self.game.teams_config = {
            "team_0": {"name": "Player", "faction": self.game.my_faction}
        }
        self.game.my_team = "team_0"
        
        # AI
        from factions import get_random_faction
        for i in range(self.ai_count):
            tid = f"team_{i+1}"
            fac, _ = get_random_faction()
            self.game.teams_config[tid] = {"name": f"AI-{i+1}", "faction": fac}
            
        # 3. 应用模式 (暂存到 game 属性里)
        self.game.game_modes = self.modes.copy()
        if self.modes['bombard']: self.game.bombardment_mode = True
        
        # 4. 启动
        self.game.reset_game()
        self.game.map_id = selected_map_id
        self.game.state = "LOADING"

    def draw(self, screen):
        screen.fill((30, 35, 40))
        
        # 标题
        t = self.font_title.render("CUSTOM SKIRMISH", True, WHITE)
        screen.blit(t, (self.panel_x, 30))
        
        # --- 地图 ---
        pygame.draw.rect(screen, BLACK, self.map_rect)
        pygame.draw.rect(screen, WHITE, self.map_rect, 2)
        
        MapClass = self.game.maps[self.game.map_id]
        
        # 1. 尝试获取实例
        current_instance = None
        
        # 检查是否已有缓存
        if hasattr(MapClass, 'temp_instance'):
            current_instance = MapClass.temp_instance
        else:
            # 尝试创建并缓存
            try:
                current_instance = MapClass(self.game)
                MapClass.temp_instance = current_instance
            except Exception as e:
                print(f"[ERROR] Failed to init map {MapClass.__name__}: {e}")
        
        # 2. 读取属性
        if current_instance:
            map_name = getattr(current_instance, 'name', 'unknown')
            preview = current_instance.preview_image
        else:
            map_name = "Load Error"
            preview = None
        if preview:
            scaled = pygame.transform.scale(preview, (380, 200))
            screen.blit(scaled, (self.map_rect.x + 10, self.map_rect.y + 50))            
        # 地图名
        t_map = self.font.render(map_name, True, WHITE)
        screen.blit(t_map, (self.map_rect.x + 10, self.map_rect.y + 10))
        
        # 翻页按钮
        pygame.draw.rect(screen, (100, 100, 100), self.map_prev)
        pygame.draw.rect(screen, (100, 100, 100), self.map_next)
        screen.blit(self.font.render("<", True, WHITE), (self.map_prev.x+10, self.map_prev.y+5))
        screen.blit(self.font.render(">", True, WHITE), (self.map_next.x+10, self.map_next.y+5))

        # --- 设置 ---
        def draw_label(txt, y):
            s = self.font.render(txt, True, WHITE)
            screen.blit(s, (self.setting_x, y))
            
        draw_label("Start Money:", self.setting_y + 5)
        self.input_money.draw(screen)
        
        draw_label("Income Rate:", self.setting_y + 55)
        self.input_rate.draw(screen)
        
        draw_label("My Faction:", self.setting_y + 105)
        pygame.draw.rect(screen, (60, 60, 70), self.btn_faction)
        fac_txt = self.font.render(getattr(self.game, 'my_faction', 'USA'), True, YELLOW)
        screen.blit(fac_txt, (self.btn_faction.x + 10, self.btn_faction.y + 5))
        
        draw_label("AI Count:", self.setting_y + 155)
        pygame.draw.rect(screen, (100, 100, 100), self.btn_ai_minus)
        pygame.draw.rect(screen, (100, 100, 100), self.btn_ai_plus)
        screen.blit(self.font.render("-", True, WHITE), (self.btn_ai_minus.x+10, self.btn_ai_minus.y+5))
        screen.blit(self.font.render("+", True, WHITE), (self.btn_ai_plus.x+8, self.btn_ai_plus.y+5))
        screen.blit(self.font.render(str(self.ai_count), True, WHITE), (self.setting_x + 190, self.setting_y + 155))
        
        # 模式勾选
        draw_label("Game Modes:", self.setting_y + 200)
        for mode, rect in self.mode_rects.items():
            # 外框
            pygame.draw.rect(screen, BLACK, rect)
            pygame.draw.rect(screen, WHITE, rect, 2)
            
            if self.modes[mode]:
                # [修改] 选中时填充绿色实心方块 (留点边距)
                inner_rect = rect.inflate(-6, -6)
                pygame.draw.rect(screen, GREEN_HAT, inner_rect)
            
            screen.blit(self.font.render(mode.upper(), True, WHITE), (rect.right + 10, rect.y))

        # --- 底部 ---
        pygame.draw.rect(screen, (50, 150, 50), self.btn_start)
        screen.blit(self.font.render("START GAME", True, WHITE), (self.btn_start.x+40, self.btn_start.y+15))
        
        pygame.draw.rect(screen, (150, 50, 50), self.btn_back)
        screen.blit(self.font.render("BACK", True, WHITE), (self.btn_back.x+50, self.btn_back.y+15))
        
        pygame.display.flip()