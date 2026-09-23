import pygame
import os
import sys
from core.settings import *
from panels.ui_login import BFInput
from core.utils import resource_path, get_font
# 辅助函数：资源路径
class LobbyUI:
    def __init__(self, game):
        self.game = game
        self.font = get_font(20)
        self.font_title =get_font(40)
        
        # 布局配置
        self.panel_x = 50
        self.panel_y = 50
        self.panel_w = SCREEN_WIDTH - 100
        self.panel_h = SCREEN_HEIGHT - 100
        
        # 左侧：玩家列表
        self.player_list_rect = pygame.Rect(self.panel_x + 20, self.panel_y + 80, 300, 400)
        
        # 中间：地图选择 (仅 Host 可操作)
        self.map_rect = pygame.Rect(self.panel_x + 340, self.panel_y + 80, 400, 300)
        self.map_prev_btn = pygame.Rect(self.panel_x + 340, self.panel_y + 390, 40, 40)
        self.map_next_btn = pygame.Rect(self.panel_x + 700, self.panel_y + 390, 40, 40)
        
        self.map_preview_surface = None
        self.current_map_idx = 0
        
        # 右侧/下方：按钮
        self.btn_start = pygame.Rect(SCREEN_WIDTH - 250, SCREEN_HEIGHT - 120, 200, 50)
        self.btn_ready = pygame.Rect(SCREEN_WIDTH - 250, SCREEN_HEIGHT - 120, 200, 50) # Client 用
        self.btn_leave = pygame.Rect(50, SCREEN_HEIGHT - 120, 150, 50)
        self.settings_rect = pygame.Rect(self.panel_x + 340, self.panel_y + 450, 400, 100)
        
        # 初始资金输入框
        self.input_money = BFInput(self.settings_rect.x + 120, self.settings_rect.y + 10, 100, 30, text="5000")
        
        self.input_rate = BFInput(self.settings_rect.x + 120, self.settings_rect.y + 50, 100, 30, text="0.0")
        
        self.game.chat_box.history_rect = pygame.Rect(self.panel_x + 340, self.panel_y + 560, 400, 100)
        self.game.chat_box.input_rect = pygame.Rect(self.panel_x + 340, self.panel_y + 670, 400, 30)        

        self.map_mode = "1v1"
        self.btn_mode_switch = pygame.Rect(self.panel_x + 340, self.panel_y + 40, 150, 30)        
        # 状态数据
        self.players = [] 
        self.is_host = (self.game.my_role == "HOST")
        self.selected_map_name = "Unknown"
        self.is_ready = False

    def update(self):
        # 实时更新数据
        self.is_host = (self.game.my_role == "HOST")
        
        # 尝试获取当前地图的预览图
        if self.game.maps:
            # 确保索引安全
            self.current_map_idx = self.game.map_id % len(self.game.maps)
            map_class = self.game.maps[self.current_map_idx]
            # 实例化一个临时的 map 对象来获取 info (这可能有点重，建议在 Map 类上加静态 info)
            # 或者我们在 Game 初始化时就预加载所有 Map 的预览图
            # 这里简单处理：如果 game.current_map 已经对应，就用它的
            
            # 为了性能，我们在 handle_input 切换地图时再更新 preview
            pass

    def handle_input(self):
        for event in pygame.event.get():
            if self.is_host:
                self.input_money.handle_event(event)
                self.input_rate.handle_event(event)
            if event.type == pygame.QUIT:
                self.game.running = False
                return True
            
            # 聊天输入
            self.game.chat_box.handle_event(event)
            if self.game.chat_box.active: continue # 输入时屏蔽其他键

            if event.type == pygame.MOUSEBUTTONDOWN:
                m_pos = pygame.mouse.get_pos()
                
                if self.btn_leave.collidepoint(m_pos):
                    if self.is_host:
                        # [新增] 广播踢人消息 (可选，其实直接关服Client就会断开)
                        # self.game.net.send({"type": "LOBBY_CLOSE"}) 
                        self.game.net.stop_hosting()
                    else:
                        self.game.net.stop_hosting() # Client 断开
                    
                    self.game.is_online = False
                    self.game.state = "LOGIN"
                    self.game.reset_lobby_data() # 清理数据
                    return True
                # 2. Host 操作
                if self.is_host:
                    # 切换模式
                    if self.btn_mode_switch.collidepoint(m_pos):
                        self.map_mode = "FFA" if self.map_mode == "1v1" else "1v1"
                        self.current_map_idx = 0 # 重置索引
                        self.update_selected_map() # 重新计算当前地图
                        self.send_update()
                    # 开始游戏
                    if self.btn_start.collidepoint(m_pos):
                        try:
                            money = int(self.input_money.text)
                            rate = float(self.input_rate.text)
                        except:
                            money = 5000; rate = 0.0
                        
                        # 2. 更新 Game 配置
                        self.game.lobby_config["money"] = money
                        self.game.lobby_config["rate"] = rate
                        
                        # 3. 发送 LOBBY_START (带上配置)
                        self.game.net.send({
                            "type": "LOBBY_START",
                            "config": self.game.lobby_config # [新增]
                        })
                        # 本地开始逻辑在 update 网络消息里处理，或者直接调
                        self.game.state = "WAITING"                        
                    # 切换地图
                    if self.map_prev_btn.collidepoint(m_pos):
                        self.game.map_id = (self.game.map_id - 1) % len(self.game.maps)
                        self.send_update()
                    elif self.map_next_btn.collidepoint(m_pos):
                        self.game.map_id = (self.game.map_id + 1) % len(self.game.maps)
                        self.send_update()
                        
                # 3. Client 操作
                else:
                    # 准备按钮
                    if self.btn_ready.collidepoint(m_pos):
                        self.is_ready = not self.is_ready
                        # 发送状态给 Host
                        self.game.net.send({"type": "LOBBY_READY", "status": self.is_ready})

        return False
    def update_selected_map(self):
        # 筛选符合当前模式的地图
        filtered_maps = [m for m in self.game.maps if (m.max_players > 2) == (self.map_mode == "FFA")]
        if not filtered_maps: return # 防止为空
        
        # 确保索引有效
        self.current_map_idx = self.current_map_idx % len(filtered_maps)
        # 获取真实的 map_id (在全局列表中的索引)
        real_map_class = filtered_maps[self.current_map_idx]
        self.game.map_id = self.game.maps.index(real_map_class)
    def send_update(self):
        """ Host 广播大厅状态 (地图变更等) """
        if self.is_host:
            self.game.broadcast_lobby_state()
            self.game.net.send({
                "type": "LOBBY_UPDATE",
                "map_id": self.game.map_id
                # 玩家列表由 Host 的 net_manager 维护并广播，或者这里发
            })

    def draw(self):
        screen = self.game.screen
        
        # 1. 背景 (半透明黑色)
        screen.fill((30, 35, 40))
        
        # 面板框
        pygame.draw.rect(screen, (50, 55, 60), (self.panel_x, self.panel_y, self.panel_w, self.panel_h))
        pygame.draw.rect(screen, WHITE, (self.panel_x, self.panel_y, self.panel_w, self.panel_h), 2)
        
        # 标题
        title = self.font_title.render("MULTIPLAYER LOBBY", True, WHITE)
        screen.blit(title, (self.panel_x + 20, self.panel_y + 20))
        
        # 2. 玩家列表
        pygame.draw.rect(screen, (30, 30, 35), self.player_list_rect)
        pygame.draw.rect(screen, (100, 100, 100), self.player_list_rect, 1)
        
        y = self.player_list_rect.y + 10
        
        # [修改] 确定 Host 的名字
        host_name = "Unknown Host"
        
        if self.is_host:
            # 如果我是 Host，名字就是我自己
            host_name = self.game.player_info['name']
        else:
            # 如果我是 Client，从同步列表里找 host
            if hasattr(self.game, 'lobby_players'):
                for p in self.game.lobby_players:
                    if p.get('id') == 'host':
                        host_name = p.get('name', 'Unknown')
                        break
            
            # 还没连上或数据没到
            if not self.game.lobby_players: host_name = "Connecting..."

        # 绘制 Host
        screen.blit(self.font.render(f"[HOST] {host_name}", True, YELLOW), (self.player_list_rect.x + 10, y))
        y += 30
        
        # [修改] 显示其他玩家 (Clients)
        if hasattr(self.game, 'lobby_players'):
            for p in self.game.lobby_players:
                # 跳过 Host，避免重复
                if p.get('id') == 'host': continue
                
                p_name = p.get('name', 'Unknown')
                is_me = (p_name == self.game.player_info['name'])
                
                # 颜色逻辑
                if is_me: color = (0, 255, 255) # 青色
                else: color = WHITE 
                
                # [修改] 拼接字符串，防止重叠
                txt = p_name
                if p.get('ready'): 
                    txt += "   [READY]"
                
                screen.blit(self.font.render(txt, True, color), (self.player_list_rect.x + 10, y))
                y += 30

        # 3. 地图选择
        pygame.draw.rect(screen, BLACK, self.map_rect)
        pygame.draw.rect(screen, WHITE, self.map_rect, 2)
        
        if self.game.maps:
            idx = self.game.map_id % len(self.game.maps)
            MapClass = self.game.maps[idx]
            
            # [修改] 不要实例化！直接读取类属性 (需要在 Map 类里定义，或者用 getattr 安全获取)
            # 假设你的 Map 类定义了 name = "xxx" 和 max_players = 4
            map_name = getattr(MapClass, 'name', "Unknown Map")
            max_players = getattr(MapClass, 'max_players', 2)
            
            # 显示地图名
            t_map = self.font_title.render(map_name, True, WHITE)
            t_rect = t_map.get_rect(center=self.map_rect.center)
            # 往上挪一点，给预览图腾地方
            t_rect.y -= 80 
            screen.blit(t_map, t_rect)
            
            # 显示人数限制
            p_color = GREEN_HAT if len(self.players) <= max_players else RED
            t_players = self.font.render(f"Max Players: {max_players}", True, p_color)
            screen.blit(t_players, (t_rect.centerx - t_players.get_width()//2, t_rect.bottom + 10))
            preview = None
            if hasattr(MapClass, 'preview_image_static'): # 假设你存了个静态图
                preview = MapClass.preview_image_static
            else:
                # 临时生成一次并缓存
                temp = MapClass(self.game) # 这一步依然慢，建议在游戏启动时统一加载
                preview = temp.preview_image
                MapClass.preview_image_static = preview # 存起来下次用
            
            if preview:
                # 缩放并绘制
                scaled = pygame.transform.scale(preview, (380, 200))
                screen.blit(scaled, (self.map_rect.x + 10, self.map_rect.y + 50))
            if self.is_host:
                pygame.draw.rect(screen, (100, 100, 100), self.map_prev_btn)
                pygame.draw.rect(screen, (100, 100, 100), self.map_next_btn)
                screen.blit(self.font.render("<", True, WHITE), (self.map_prev_btn.x + 15, self.map_prev_btn.y + 10))
                screen.blit(self.font.render(">", True, WHITE), (self.map_next_btn.x + 15, self.map_next_btn.y + 10))
        if self.is_host:
            pygame.draw.rect(screen, (80, 80, 100), self.btn_mode_switch)
            txt = self.font.render(f"Mode: {self.map_mode}", True, WHITE)
            screen.blit(txt, (self.btn_mode_switch.x + 10, self.btn_mode_switch.y + 5))
        # 4. 底部按钮
        pygame.draw.rect(screen, (150, 50, 50), self.btn_leave)
        l_txt = self.font.render("LEAVE", True, WHITE)
        screen.blit(l_txt, (self.btn_leave.x + 40, self.btn_leave.y + 15))
        
        if self.is_host:
            pygame.draw.rect(screen, (50, 150, 50), self.btn_start)
            s_txt = self.font.render("START GAME", True, WHITE)
            screen.blit(s_txt, (self.btn_start.x + 40, self.btn_start.y + 15))
        else:
            color = (50, 150, 50) if self.is_ready else (100, 100, 100)
            pygame.draw.rect(screen, color, self.btn_ready)
            r_txt = "READY!" if self.is_ready else "NOT READY"
            t = self.font.render(r_txt, True, WHITE)
            screen.blit(t, (self.btn_ready.x + 50, self.btn_ready.y + 15))
        # 标签
        l_money = self.font.render("Start Money:", True, WHITE)
        screen.blit(l_money, (self.settings_rect.x + 10, self.settings_rect.y + 15))
        
        l_rate = self.font.render("Income Rate:", True, WHITE)
        screen.blit(l_rate, (self.settings_rect.x + 10, self.settings_rect.y + 55))
        
        # 输入框 (如果是 Client，显示为不可编辑状态，或者直接画文字)
        if self.is_host:
            self.input_money.draw(screen)
            self.input_rate.draw(screen)
        else:
            m_txt = self.game.lobby_config.get("money", 5000)
            r_txt = self.game.lobby_config.get("rate",0.0)
            screen.blit(self.font.render(str(m_txt), True, GRAY), (self.settings_rect.x + 120, self.settings_rect.y + 15))
            screen.blit(self.font.render(str(r_txt), True, GRAY), (self.settings_rect.x + 120, self.settings_rect.y + 55))
        # 5. 聊天框 (复用)
        original_rect = self.game.chat_box.history_rect
        # 放在地图下方
        self.game.chat_box.history_rect = pygame.Rect(self.panel_x + 640, self.panel_y + 450, 400, 150)
        self.game.chat_box.input_rect = pygame.Rect(self.panel_x + 640, self.panel_y + 610, 400, 30)
        
        self.game.chat_box.draw(screen)
        

        self.game.chat_box.history_rect = original_rect
        
        pygame.display.flip()