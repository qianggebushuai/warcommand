import pygame
from core.settings import *
import os
import sys
from core.utils import resource_path, get_font
# main.py
class BaseSettingUI:
    def __init__(self, game):
        self.game = game
        self.active = False
        
        # 弹窗尺寸
        self.w, self.h = 400, 300
        self.rect = pygame.Rect((SCREEN_WIDTH-self.w)//2, (SCREEN_HEIGHT-self.h)//2, self.w, self.h)
        
        # 入口按钮 (右上角齿轮)
        self.btn_open = pygame.Rect(SCREEN_WIDTH - 60, 20, 40, 40)
        
        # 控件
        self.slider_vol = pygame.Rect(self.rect.x + 150, self.rect.y + 80, 200, 10)
        self.check_fullscreen = pygame.Rect(self.rect.x + 150, self.rect.y + 130, 20, 20)
        self.btn_close = pygame.Rect(self.rect.x + 150, self.rect.y + 220, 100, 40)
        
        self.dragging_vol = False
        
        # 字体
        self.font = get_font(20)

    def handle_event(self, event):
        if not self.active:
            if event.type == pygame.MOUSEBUTTONDOWN and self.btn_open.collidepoint(event.pos):
                self.active = True
                return True
            return False

        m_pos = pygame.mouse.get_pos()
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.btn_close.collidepoint(m_pos):
                self.active = False
                # 保存设置 (可选)
                
            # 音量滑块
            if self.slider_vol.inflate(0, 20).collidepoint(m_pos):
                self.dragging_vol = True
                self.update_volume(m_pos[0])
                
            # 全屏切换
            if self.check_fullscreen.collidepoint(m_pos):
                pygame.display.toggle_fullscreen()
                # 更新状态记录 (如果有的话)
                
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging_vol = False
            
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging_vol:
                self.update_volume(m_pos[0])
                
        return True # 激活时拦截所有事件

    def update_volume(self, mouse_x):
        # 映射 mouse_x 到 0.0 - 1.0
        ratio = (mouse_x - self.slider_vol.x) / self.slider_vol.width
        ratio = max(0.0, min(1.0, ratio))
        self.game.master_volume = ratio
        pygame.mixer.music.set_volume(ratio)

    def draw(self, screen):
        # 1. 绘制入口按钮 (齿轮)
        if not self.active:
            pygame.draw.circle(screen, (80, 80, 90), self.btn_open.center, 18)
            pygame.draw.circle(screen, WHITE, self.btn_open.center, 18, 2)
            pygame.draw.circle(screen, (80, 80, 90), self.btn_open.center, 6)
            return

        # 2. 绘制弹窗背景
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0,0))
        
        pygame.draw.rect(screen, (40, 45, 50), self.rect, border_radius=10)
        pygame.draw.rect(screen, WHITE, self.rect, 2, border_radius=10)
        
        # 标题
        t = self.font.render("SETTINGS", True, WHITE)
        screen.blit(t, (self.rect.x + 20, self.rect.y + 20))
        
        # 音量
        v_label = self.font.render("Volume:", True, WHITE)
        screen.blit(v_label, (self.rect.x + 40, self.rect.y + 75))
        
        pygame.draw.rect(screen, (100, 100, 100), self.slider_vol)
        fill_w = self.game.master_volume * self.slider_vol.width
        pygame.draw.rect(screen, GREEN_HAT, (self.slider_vol.x, self.slider_vol.y, fill_w, 10))
        # 滑块头
        thumb_x = self.slider_vol.x + fill_w
        pygame.draw.circle(screen, WHITE, (int(thumb_x), self.slider_vol.centery), 8)
        
        # 全屏
        f_label = self.font.render("Fullscreen:", True, WHITE)
        screen.blit(f_label, (self.rect.x + 40, self.rect.y + 130))
        pygame.draw.rect(screen, BLACK, self.check_fullscreen)
        pygame.draw.rect(screen, WHITE, self.check_fullscreen, 2)
        # 检查是否全屏 (Pygame 没有直接属性，可以用 display.get_surface().get_flags() & FULLSCREEN)
        is_fs = (pygame.display.get_surface().get_flags() & pygame.FULLSCREEN)
        if is_fs:
            pygame.draw.line(screen, GREEN_HAT, self.check_fullscreen.topleft, self.check_fullscreen.bottomright, 2)
            pygame.draw.line(screen, GREEN_HAT, self.check_fullscreen.topright, self.check_fullscreen.bottomleft, 2)

        # 关闭按钮
        pygame.draw.rect(screen, (150, 50, 50), self.btn_close, border_radius=5)
        c_txt = self.font.render("CLOSE", True, WHITE)
        screen.blit(c_txt, (self.btn_close.x + 20, self.btn_close.y + 10))