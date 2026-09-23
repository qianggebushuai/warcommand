import pygame
import random
import math
from settings import *
from base_classes import vec, to_screen, scale

class EnvironmentManager:
    def __init__(self, game):
        self.game = game
        self.active_weather = None # "storm", "sandstorm", etc.
        self.intensity = 0.0 # 0.0 ~ 1.0 (淡入淡出)
        self.target_intensity = 0.0
        
        # 暴风雨粒子
        self.rain_drops = [] 
        self.ripples = []   
        
        # 滤镜层
        self.filter_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        
        # 雷电
        self.lightning_timer = 0
        self.flash_alpha = 0

    def set_weather(self, weather_type):
        if self.active_weather != weather_type:
            self.active_weather = weather_type
            if weather_type:
                self.target_intensity = 1.0
                print(f"[Env] Weather changing to {weather_type}")
            else:
                self.target_intensity = 0.0

    def update(self):
        fade_speed = 0.0001 
        
        if self.intensity < self.target_intensity:
            self.intensity += fade_speed
        elif self.intensity > self.target_intensity:
            self.intensity -= fade_speed
            
        if self.intensity <= 0 and self.target_intensity == 0:
            self.active_weather = None
            return

        if self.active_weather == "storm":
            self.update_storm()

    def update_storm(self):
        # 1. 生成雨滴
        count = int(10 * self.intensity) 
        for _ in range(count):
            x = random.randint(-200, SCREEN_WIDTH)
            y = random.randint(-100, 0)
            
            speed = random.randint(15, 25)
            length = random.randint(10, 20)
            
            target_y = random.randint(int(SCREEN_HEIGHT * 0.2), SCREEN_HEIGHT)
            
            self.rain_drops.append([x, y, speed, length, target_y])
            
        new_drops = []
        for r in self.rain_drops:
            # r = [x, y, speed, length, target_y]
            r[0] += 3 # 右
            r[1] += r[2] # 下
            
            if r[1] >= r[4]:
                wx = r[0] / self.game.zoom + self.game.camera_offset.x
                wy = r[1] / self.game.zoom + self.game.camera_offset.y
                
                in_water = False
                if hasattr(self.game, 'lakes'):
                    pt = pygame.Rect(int(wx), int(wy), 1, 1)
                    lake_rects = [l['rect'] if isinstance(l, dict) else l for l in self.game.lakes]
                    if pt.collidelist(lake_rects) != -1:
                        in_water = True
                        if hasattr(self.game.current_map, 'islands'):
                            if pt.collidelist(self.game.current_map.islands) != -1:
                                in_water = False
                
                # 只有水里才生波纹
                if in_water and random.random() < 0.5 * self.intensity:
                    # 存世界坐标！以便随镜头缩放
                    self.ripples.append([wx, wy, 2, 150]) # x, y, r, alpha (World Coords)
            else:
                new_drops.append(r)
        self.rain_drops = new_drops
        
        # 更新波纹
        for rip in self.ripples:
            rip[2] += 0.5 # 世界半径变大
            rip[3] -= 5
        self.ripples = [r for r in self.ripples if r[3] > 0]
        # 4. 雷电逻辑
        if self.flash_alpha > 0:
            self.flash_alpha -= 10
        else:
            if random.random() < 0.005 * self.intensity: # 小概率打雷
                self.flash_alpha = 180

    def draw(self, screen):
        if self.intensity <= 0: return
        zoom = self.game.zoom
        offset = self.game.camera_offset        
        if self.active_weather == "storm":
            # 1. 灰暗滤镜
            # 强度越高越黑 (0, 0, 50) 深蓝灰
            alpha = int(100 * self.intensity)
            self.filter_surf.fill((20, 30, 50, alpha))
            screen.blit(self.filter_surf, (0, 0))
            
            rain_color = (200, 200, 255, int(150 * self.intensity))
            for r in self.rain_drops:
                start = (r[0], r[1])
                # end = start - velocity * length_factor
                # 速度是 (3, speed)
                end = (r[0] - 3, r[1] - r[3]) # 拖尾在左上
                pygame.draw.line(screen, (200, 200, 255), start, end, 1)

            # 3. 绘制波纹 (世界坐标 -> 屏幕坐标)
            for rip in self.ripples:
                # 转换坐标
                sx = int((rip[0] - offset.x) * zoom)
                sy = int((rip[1] - offset.y) * zoom)
                sr = int(rip[2] * zoom)
                
                if sr > 0:
                    alpha = rip[3]
                    if alpha > 20:
                        c_val = min(255, alpha + 40)
                        color = (c_val, c_val, 255)
                        pygame.draw.circle(screen, color, (sx, sy), sr, 1)
            # 4. 雷电闪光 (全屏白)
            if self.flash_alpha > 0:
                s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                s.fill((255, 255, 255, int(self.flash_alpha)))
                screen.blit(s, (0,0), special_flags=pygame.BLEND_RGBA_ADD)