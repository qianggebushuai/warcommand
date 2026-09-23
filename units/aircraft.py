import pygame
import random
import math
from core.settings import *
from core.base_classes import *
from .base import *

class Helicopter(Unit):
    def __init__(self, game, pos, team):
        self.max_hp = HELICOPTER_STATS[2]
        self.hp = self.max_hp
        super().__init__(game, pos, team)
        self.speed = HELICOPTER_STATS[1]
        self.attack_range = HELICOPTER_STATS[0]
        self.is_mechanical = True
        self.is_air = True
        self.can_attack_air = True
        self.radius = 15
        self.rect = pygame.Rect(pos.x - 15, pos.y - 15, 30, 30)
        self.is_crashing = False
        self.crash_timer = 0
        self.spin_angle = 0 
    def take_damage(self, amount, damage_type="normal", breakshellvalue =0):
        if self.is_crashing: return 
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.is_crashing = True
            self.crash_timer = 60 
            self.speed = 2 
    def update(self):
        if self.is_crashing:
            self.crash_timer -= 1
            self.spin_angle += 25 
            self.pos += vec(random.uniform(-2, 2), random.uniform(-2, 2))
            if self.crash_timer <= 0:
                self.die() 
                self.game.particles.add(FloatingText(self.pos, "man!", WHITE))
                return
        else:
            super().update()
        self.update_rect()
    def perform_attack(self, target):
        if self.is_crashing: return
        if self.attack_cooldown <= 0:
            base_vec = (target.pos - self.pos).normalize()
            offset_angle = random.uniform(-5, 5)
            fire_vec = base_vec.rotate(offset_angle)
            dmg = DMG_HELICOPTER * self.tech_bonus_dmg
            proj = Projectile(self.game, self.pos, None, self.team, dmg, "heavy", breakshellvalue=self.breakarmorvalue)
            proj.vel = fire_vec * BULLET_SPEED
            self.game.projectiles.append(proj)
            self.attack_cooldown = 4 
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        w, h = 80, 80 
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        
        C_BODY_TOP = (220, 225, 230)  
        C_BODY_BOT = (60, 65, 70)     
        C_DETAIL   = (100, 100, 105)  
        C_CAMERA   = (20, 20, 25)     
        C_LENS     = (0, 100, 50)     
        C_SKIDS    = (40, 40, 45)     
        C_ROTOR    = (30, 30, 30, 200)
        
        
        pygame.draw.line(surf, C_SKIDS, (cx-10, cy-12), (cx+15, cy-12), 3) 
        pygame.draw.line(surf, C_SKIDS, (cx-5, cy-12), (cx, cy-5), 2)      
        pygame.draw.line(surf, C_SKIDS, (cx+10, cy-12), (cx+10, cy-5), 2)  
        pygame.draw.line(surf, C_SKIDS, (cx-10, cy+12), (cx+15, cy+12), 3)
        pygame.draw.line(surf, C_SKIDS, (cx-5, cy+12), (cx, cy+5), 2)
        pygame.draw.line(surf, C_SKIDS, (cx+10, cy+12), (cx+10, cy+5), 2)

        
        pygame.draw.rect(surf, C_BODY_TOP, (cx-35, cy-2, 40, 4))
        
        body_pts_top = [
            (cx+25, cy),    
            (cx+15, cy-10), 
            (cx-15, cy-10), 
            (cx-25, cy),    
        ]
        pygame.draw.polygon(surf, C_BODY_TOP, body_pts_top)
        
        body_pts_bot = [
            (cx+25, cy),    
            (cx+15, cy+8),  
            (cx-15, cy+8),  
            (cx-25, cy)     
        ]
        pygame.draw.polygon(surf, C_BODY_BOT, body_pts_bot)
        
        pygame.draw.rect(surf, C_DETAIL, (cx-5, cy-6, 10, 3))
        pygame.draw.rect(surf, C_DETAIL, (cx-5, cy+3, 10, 3))

        cam_x, cam_y = cx + 20, cy 
        pygame.draw.circle(surf, C_BODY_BOT, (cam_x-2, cam_y), 5)
        pygame.draw.circle(surf, C_CAMERA, (cam_x+2, cam_y), 6)
        pygame.draw.circle(surf, C_LENS, (cam_x+4, cam_y), 2)

        tail_x = cx - 35
        pygame.draw.polygon(surf, C_BODY_BOT, [(tail_x, cy-2), (tail_x-5, cy-12), (tail_x+2, cy-2)])
        pygame.draw.polygon(surf, C_BODY_BOT, [(tail_x, cy+2), (tail_x-5, cy+12), (tail_x+2, cy+2)])
        
        if self.alive or self.is_crashing:
            tr_speed = 30
            tr_angle = (pygame.time.get_ticks() * tr_speed) % 360
            tr_pos = (tail_x - 2, cy - 8) 
            pygame.draw.circle(surf, (200, 200, 200, 100), tr_pos, 8)

        if self.alive or self.is_crashing:
            rotor_speed = 20 if self.alive else 5
            rotor_angle = (pygame.time.get_ticks() * rotor_speed * 0.1) % 360
            
            rotor_len = 35 
            num_blades = 3 
            
            pygame.draw.circle(surf, (50, 50, 50), (cx, cy), 4)
            
            for i in range(num_blades):
                ang = rotor_angle + i * (360/num_blades)
                rad = math.radians(ang)
                
                ex = cx + math.cos(rad) * rotor_len
                ey = cy + math.sin(rad) * rotor_len
                
                pygame.draw.line(surf, C_ROTOR, (cx, cy), (ex, ey), 3)
                pygame.draw.circle(surf, (200, 200, 200, 150), (int(ex), int(ey)), 2)

        scaled_img = scale_img(surf, zoom)
        
        draw_angle = self.spin_angle if self.is_crashing else self.angle
        
        rotated_img = pygame.transform.rotate(scaled_img, draw_angle)
        
        new_rect = rotated_img.get_rect(center=screen_pos)
        surface.blit(rotated_img, new_rect.topleft)
        
        self.draw_health_and_marker(surface, offset, zoom)


class WZ10(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = WZ10_STATS[2]
        self.hp = self.max_hp

        self.speed = WZ10_STATS[1]
        self.attack_range = WZ10_STATS[0]
        self.is_mechanical = True
        self.is_air = True
        self.can_attack_air = True 
        self.armor=5

        self.rect = pygame.Rect(pos.x - 35, pos.y - 35, 70, 70)
        self.is_crashing = False
        self.crash_timer = 0
        self.spin_angle = 0
        self.radius = 20
        self.original_image = pygame.Surface((140, 140), pygame.SRCALPHA)
        
        C_BODY       = (50, 60, 50)     
        C_BODY_LIGHT = (70, 80, 70)     
        C_GLASS      = (20, 30, 40)     
        C_WEAPON     = (30, 30, 35)     
        C_MISSILE    = (60, 70, 60)     
        C_ROTOR      = (20, 20, 20)     
        C_TEAM       = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        
        
        pygame.draw.rect(self.original_image, C_WEAPON, (60, 45, 20, 50))
        
        pygame.draw.rect(self.original_image, C_MISSILE, (65, 38, 15, 6)) 
        pygame.draw.circle(self.original_image, (40, 40, 40), (62, 41), 3) 
        pygame.draw.rect(self.original_image, C_MISSILE, (65, 96, 15, 6))
        pygame.draw.circle(self.original_image, (40, 40, 40), (62, 99), 3)

        body_points = [
            (110, 72), 
            (95, 60),  
            (60, 55),  
            (30, 65),  
            (5, 65),   
            (30, 75),  
            (60, 85),  
            (95, 80)   
        ]
        pygame.draw.polygon(self.original_image, C_BODY, body_points)
        
        pygame.draw.line(self.original_image, C_BODY_LIGHT, (110, 72), (30, 70), 2)
        
        pygame.draw.polygon(self.original_image, C_GLASS, [(105, 68), (95, 63), (95, 75), (105, 75)])
        pygame.draw.polygon(self.original_image, C_GLASS, [(92, 63), (80, 58), (80, 75), (92, 75)])
        
        pygame.draw.rect(self.original_image, C_BODY, (15, 60, 10, 20))
        pygame.draw.polygon(self.original_image, C_BODY_LIGHT, [(10, 70), (0, 60), (5, 80)])
        
        pygame.draw.rect(self.original_image, (40, 40, 45), (55, 60, 25, 8)) 
        pygame.draw.rect(self.original_image, (40, 40, 45), (55, 72, 25, 8)) 
        pygame.draw.circle(self.original_image, (10, 10, 10), (80, 64), 3)
        pygame.draw.circle(self.original_image, (10, 10, 10), (80, 76), 3)

        pygame.draw.rect(self.original_image, (20, 20, 20), (100, 70, 15, 2))

        pygame.draw.rect(self.original_image, C_TEAM, (35, 68, 10, 4))
    def take_damage(self, amount, damage_type="normal",breakshellvalue=0):
        if self.is_crashing: return 
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.is_crashing = True
            self.crash_timer = 90 
            self.speed = 1.5 
    def perform_attack(self, target):
        if self.is_crashing: return
        if isinstance(target, AC130):
            self.target_entity = None 
            return
        if self.attack_cooldown <= 0:
            dmg = DMG_WZ10 * self.tech_bonus_dmg
            rocket = Projectile(self.game, self.pos, target, self.team, dmg,"rocket", is_aoe=True, aoe_radius=40, breakshellvalue=self.breakarmorvalue)
            rocket.target_dest = vec(target.pos)
            self.game.projectiles.append(rocket)
            self.attack_cooldown = 30 
    def update(self):
        if self.is_crashing:
            self.crash_timer -= 1
            self.spin_angle += 15 
            self.pos += vec(random.uniform(-1, 1), random.uniform(-1, 1))
            if self.crash_timer <= 0:
                self.die() 
                self.game.particles.add(FloatingText(self.pos, "man!", WHITE))
                return
            self.update_rect()
        else:
            super().update()
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 200 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return           
        scaled_img = scale_img(self.original_image, zoom)
        
        draw_angle = self.spin_angle if self.is_crashing else self.angle
        rotated_image = pygame.transform.rotate(scaled_img, draw_angle)
        rect = rotated_image.get_rect(center=screen_pos)
        
        shadow_dist = scale(30, zoom)
        shadow_w = rect.width * 0.8
        shadow_h = rect.height * 0.8
        
        shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 60), (0, 0, shadow_w, shadow_h))
        shadow_rect = shadow_surf.get_rect(center=(screen_pos[0] + shadow_dist, screen_pos[1] + shadow_dist))
        
        surface.blit(shadow_surf, shadow_rect)
        
        surface.blit(rotated_image, rect.topleft)
        
        if self.alive or self.is_crashing:
            rotor_speed = 30 if self.alive else 5
            rotor_angle = (pygame.time.get_ticks() * rotor_speed * 0.05) % 360
            
            rx, ry = screen_pos
            
            disk_r = scale(55, zoom)
            s_disk = pygame.Surface((disk_r*2, disk_r*2), pygame.SRCALPHA)
            pygame.draw.circle(s_disk, (0, 0, 0, 30), (disk_r, disk_r), disk_r) 
            pygame.draw.circle(s_disk, (255, 255, 255, 10), (disk_r, disk_r), disk_r-2, 2) 
            surface.blit(s_disk, (rx - disk_r, ry - disk_r))
            
            blade_len = scale(55, zoom)
            num_blades = 5
            
            for i in range(num_blades):
                angle_deg = rotor_angle + i * (360/num_blades)
                rad = math.radians(angle_deg)
                
                end_x = rx + math.cos(rad) * blade_len
                end_y = ry - math.sin(rad) * blade_len 
                
                pygame.draw.line(surface, (10, 10, 10, 200), (rx, ry), (end_x, end_y), int(scale(3, zoom)))
                pygame.draw.line(surface, (100, 100, 100, 150), (rx, ry), (end_x, end_y), 1)
            
            pygame.draw.circle(surface, (50, 50, 50), (int(rx), int(ry)), int(scale(4, zoom)))
            
            body_rad = math.radians(self.angle)
            tail_dist = scale(50, zoom)
            tail_x = rx - math.cos(body_rad) * tail_dist
            tail_y = ry + math.sin(body_rad) * tail_dist
            
            tr_r = scale(10, zoom)
            pygame.draw.circle(surface, (200, 200, 200, 100), (int(tail_x), int(tail_y)), int(tr_r))

        self.draw_health_and_marker(surface, offset, zoom)


class AC130(Unit):
    def __init__(self, game, orbit_center, team):
        self.orbit_center = vec(orbit_center)
        self.entry_target = self.orbit_center + vec(0, -AC130_ORBIT_RADIUS)
        spawn_pos = self.calculate_spawn_pos(game, self.entry_target)
        super().__init__(game, spawn_pos, team)
        
        self.hp = AC130_STATS[2]
        self.max_hp = self.hp
        self.armor=5
        self.is_mechanical = True
        self.is_air = True
        self.state = "APPROACHING" 
        self.orbit_angle = -90 
        self.timer = AC130_DURATION
        self.radius = 50
        self.collision=False 
        self.original_image = pygame.Surface((200, 200), pygame.SRCALPHA)
        
        C_BODY_BASE   = (90, 95, 100)       
        C_BODY_SHADOW = (60, 65, 70)        
        C_BODY_HILITE = (120, 125, 130)     
        C_WING_SURF   = (80, 85, 90)        
        C_JET_INTAKE  = (20, 20, 20)        
        C_JET_METAL   = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])     
        C_JET_EXHAUST = (40, 30, 25)        
        C_GLASS_DARK  = (10, 25, 40)        
        C_RADOME      = (40, 40, 45)        
        C_GUN_BARREL  = (15, 15, 15)        
        C_SENSOR      = (200, 200, 200)     
        

        
        
        dx = -20
        
        engine_y_locs = [40, 65, 135, 160]
        engine_x_offset = [70, 80, 80, 70] 
        
        for i, y in enumerate(engine_y_locs):
            x = engine_x_offset[i]
            pylon_dir = 1 if y > 100 else -1
            pygame.draw.polygon(self.original_image, C_BODY_SHADOW, [(x+4, y), (x-4, y), (x, 100 + 10*pylon_dir)])
            pygame.draw.rect(self.original_image, C_BODY_BASE, (x-10, y-6, 24, 12), border_radius=3)
            pygame.draw.ellipse(self.original_image, C_JET_METAL, (x+11, y-6, 4, 12))
            pygame.draw.ellipse(self.original_image, C_JET_INTAKE, (x+12, y-5, 3, 10))
            pygame.draw.polygon(self.original_image, C_JET_EXHAUST, [(x-10, y-4), (x-10, y+4), (x-15, y+2), (x-15, y-2)])

        wing_points = [
            (60 + 20 + dx, 25), (60 + dx, 25),      
            (90 + dx, 90), (140 + dx, 90),          
            (140 + dx, 110), (90 + dx, 110), 
            (60 + dx, 175), (60 + 20 + dx, 175)
        ]
        pygame.draw.polygon(self.original_image, C_WING_SURF, wing_points)
        
        tail_x = 25 + dx 
        pygame.draw.polygon(self.original_image, C_BODY_SHADOW, [(tail_x, 100), (tail_x+30, 100), (tail_x+10, 85), (tail_x-5, 85)])
        pygame.draw.polygon(self.original_image, C_WING_SURF, [(tail_x-5, 65), (tail_x+15, 75), (tail_x+15, 125), (tail_x-5, 135)])

        body_points = [
            (185+dx, 100),              
            (170+dx, 92), (120+dx, 90), 
            (50+dx, 94), (20+dx, 100),  
            (50+dx, 106), (120+dx, 110),
            (170+dx, 108)               
        ]
        pygame.draw.polygon(self.original_image, C_BODY_BASE, body_points)
        
        pygame.draw.polygon(self.original_image, C_RADOME, [(185+dx, 100), (178+dx, 96), (178+dx, 104)])
        
        pygame.draw.rect(self.original_image, C_BODY_HILITE, (60+dx, 94, 100, 12), border_radius=4)
        
        g1_x, g1_y = 145+dx, 110
        pygame.draw.rect(self.original_image, C_GUN_BARREL, (g1_x, g1_y, 2, 12))
        
        g2_x, g2_y = 115+dx, 112
        pygame.draw.polygon(self.original_image, C_GUN_BARREL, [(g2_x, g2_y), (g2_x+4, g2_y), (g2_x+3, g2_y+14), (g2_x+1, g2_y+14)])

        pygame.draw.circle(self.original_image, (255, 0, 0), (80+dx, 25), 2)
        pygame.draw.circle(self.original_image, (0, 255, 0), (80+dx, 175), 2)
    def calculate_spawn_pos(self, game, target):
        if game.current_map:
            w, h = game.current_map.width, game.current_map.height
        else:
            w, h = WORLD_WIDTH, WORLD_HEIGHT
            
        x, y = target.x, target.y
        d_left = x; d_right = w - x; d_top = y; d_bottom = h - y
        min_dist = min(d_left, d_right, d_top, d_bottom)
        
        offset = 300
        if min_dist == d_left:   return vec(-offset, y)
        if min_dist == d_right:  return vec(w + offset, y)
        if min_dist == d_top:    return vec(x, -offset)
        return vec(x, h + offset)
    def update(self):
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        
        
        if self.state == "APPROACHING":
            dist = self.pos.distance_to(self.entry_target)
            if dist < 10: 
                self.state = "CIRCLING"
            else:
                direction = (self.entry_target - self.pos).normalize()
                self.pos += direction * 3 
                self.angle = math.degrees(math.atan2(-direction.y, direction.x))

        elif self.state == "CIRCLING":
            self.timer -= 1
            if self.timer <= 0: self.state = "LEAVING"
            
            self.orbit_angle += 0.5 
            offset = vec(AC130_ORBIT_RADIUS, 0).rotate(self.orbit_angle)
            self.pos = self.orbit_center + offset
            self.angle = self.orbit_angle + 90
            
            if not self.game.is_online or self.game.my_role == "HOST":
                if self.attack_cooldown <= 0:
                    self.fire_barrage()
                    self.attack_cooldown = 5

        elif self.state == "LEAVING":
            direction = vec(1, 0).rotate(self.angle) 
            self.pos += direction * 4
            if not (-500 < self.pos.x < self.game.current_map.width + 500 and 
                    -500 < self.pos.y < self.game.current_map.height + 500):
                self.alive = False
        
        self.update_rect() 

    def fire_barrage(self):
        radius_sq = (AC130_ORBIT_RADIUS + 100) ** 2 
        targets = []
        possible = self.game.all_units + self.game.all_buildings
        for e in possible:
            if e.team != self.team and e.team != "neutral" and e.alive:
                if self.orbit_center.distance_squared_to(e.pos) <= radius_sq:
                    targets.append(e)
        
        impact_pos = None
        if targets:
            target = random.choice(targets)
            impact_pos = target.pos + vec(random.randint(-20, 20), random.randint(-20, 20))
        else:
            rnd_angle = random.uniform(0, 360)
            rnd_dist = random.uniform(0, AC130_ORBIT_RADIUS)
            offset = vec(rnd_dist, 0).rotate(rnd_angle)
            impact_pos = self.orbit_center + offset
        bomb = Projectile(self.game, self.pos, None, self.team, DMG_AC130, "ac130", is_aoe=True, aoe_radius=40)
        bomb.target_dest = impact_pos 
        bomb.vel = (impact_pos - self.pos).normalize() * 40 
        self.game.projectiles.append(bomb)
        vis = Projectile(self.game, self.pos, None, self.team, 0, "ac130_vis")
        vis.target_dest = impact_pos
        vis.vel = (impact_pos - self.pos).normalize() * 18
        self.game.projectiles.append(vis)

    def draw(self, surface, offset, zoom):

        screen_center = to_screen(self.orbit_center, offset, zoom)
        scaled_radius = scale(AC130_ORBIT_RADIUS, zoom)
        
        s_circle = pygame.Surface((scaled_radius*2, scaled_radius*2), pygame.SRCALPHA)
        pygame.draw.circle(s_circle, (255, 50, 50, 50), (scaled_radius, scaled_radius), scaled_radius, 2)
        surface.blit(s_circle, (screen_center[0]-scaled_radius, screen_center[1]-scaled_radius))
        
        screen_pos = to_screen(self.pos, offset, zoom)
        scaled_img = scale_img(self.original_image, zoom)
        rot_img = pygame.transform.rotate(scaled_img, -self.angle)
        
        rect = rot_img.get_rect(center=screen_pos)
        surface.blit(rot_img, rect)
        
        self.draw_health_and_marker(surface, offset, zoom)


class KirovAirship(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.speed = KIROV_STATS[1]
        self.attack_range = KIROV_STATS[0]
        self.hp = KIROV_STATS[2]
        self.max_hp = self.hp
        self.is_mechanical = True
        self.is_air = True
        self.can_attack_air = False 
        self.armor=15
        self.radius = 49
        self.rect = pygame.Rect(pos.x - 80, pos.y - 80, 160, 160)
        
        self.deployed = False
        self.deploy_timer = 600 
        self.is_crashing = False
        self.crash_timer = 0
        self.spin_angle = 0

        self.original_image = pygame.Surface((300, 160), pygame.SRCALPHA)
        
        C_HULL_BASE    = (50, 60, 70)     
        C_HULL_PLATE   = (80, 90, 100)    
        C_HULL_HILITE  = (120, 130, 140)  
        C_ENGINE_DARK  = (30, 30, 35)     
        C_GLOW_ENGINE  = (0, 200, 255)    
        C_GLOW_CORE    = (0, 100, 200)    
        C_WINDOW       = (100, 255, 200)  
        C_TURRET       = (90, 95, 100)    
        
        accent = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        engine_positions = [
            (60, 20),  
            (60, 120) 
        ]
        
        for ex, ey in engine_positions:
            pylon_dir = 1 if ey > 80 else -1
            pygame.draw.polygon(self.original_image, C_HULL_BASE, 
                               [(ex, ey), (ex+30, ey), (ex+15, 80 + 30*pylon_dir)])
            
            pygame.draw.rect(self.original_image, C_ENGINE_DARK, (ex-10, ey, 50, 20), border_radius=5)
            pygame.draw.ellipse(self.original_image, (150, 150, 160), (ex+35, ey+2, 8, 16))
            pygame.draw.rect(self.original_image, (20, 20, 25), (ex-15, ey+2, 5, 16))
            
            pygame.draw.rect(self.original_image, C_GLOW_ENGINE, (ex+10, ey+8, 20, 4)) 

        hull_points = [
            (280, 80),   
            (240, 50), (100, 45), 
            (40, 60), (20, 80),   
            (40, 100),            
            (100, 115), (240, 110)
        ]
        pygame.draw.polygon(self.original_image, C_HULL_BASE, hull_points)
        
        deck_points = [
            (270, 80),
            (230, 55), (110, 55),
            (50, 70), (50, 90),
            (110, 105), (230, 105)
        ]
        pygame.draw.polygon(self.original_image, C_HULL_PLATE, deck_points)
        
        pygame.draw.line(self.original_image, C_HULL_HILITE, (50, 80), (270, 80), 2)
        
        pygame.draw.rect(self.original_image, C_ENGINE_DARK, (20, 65, 30, 30))
        pygame.draw.ellipse(self.original_image, C_GLOW_ENGINE, (15, 70, 10, 20))
        
        bridge_x, bridge_y = 80, 80
        pygame.draw.circle(self.original_image, C_HULL_BASE, (bridge_x, bridge_y), 18)
        pygame.draw.rect(self.original_image, C_HULL_HILITE, (bridge_x-10, bridge_y-12, 25, 24), border_radius=4)
        pygame.draw.rect(self.original_image, C_WINDOW, (bridge_x+5, bridge_y-8, 4, 16))
        
        gun_x, gun_y = 200, 80
        pygame.draw.circle(self.original_image, C_TURRET, (gun_x, gun_y), 12)
        pygame.draw.rect(self.original_image, (40,40,40), (gun_x, gun_y-4, 30, 3))
        pygame.draw.rect(self.original_image, (40,40,40), (gun_x, gun_y+1, 30, 3))
        


        pygame.draw.rect(self.original_image, (0,0,0), (120, 78, 40, 4)) 
        pygame.draw.rect(self.original_image, C_GLOW_CORE, (122, 79, 36, 2)) 
        
        pygame.draw.polygon(self.original_image, accent, [(240, 60), (250, 80), (240, 100), (235, 100), (245, 80), (235, 60)])

        self.original_image.set_alpha(255)

    def update(self):
        if self.is_crashing:
            self.crash_timer -= 1
            self.spin_angle += 2 
            self.pos += vec(random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5))
            
            if random.randint(0, 10) == 0:
                offset = vec(random.randint(-60, 60), random.randint(-20, 20))
                self.game.particles.add(Particle(self.game.particles, self.pos + offset, ORANGE, 2, 30, 8))

            if self.crash_timer <= 0:
                self.die() 
                p=Projectile(self.game, self.pos, None, self.team, 800, "behemoth_bomb", is_aoe=True, aoe_radius=100)
                p.on_hit(None)
                return
            self.update_rect()
            return

        if not self.deployed:
            self.deploy_timer -= 1
            if self.deploy_timer > 0:
                return 
            else:
                self.deployed = True
                self.game.particles.add(FloatingText(self.pos, "AIRSHIP READY", GREEN_HAT))
                if hasattr(self.game, 'net_events'):
                    self.game.net_events.append({
                        "type": "FX_TEXT", 
                        "x": int(self.pos.x), "y": int(self.pos.y),
                        "text": "AIRSHIP READY",
                        "color": "GREEN_HAT" 
                    })               

        super().update()

    def perform_attack(self, target):
        if not self.deployed: return
        if self.attack_cooldown <= 0:
            bomb = Projectile(self.game, self.pos, target, self.team, DMG_KIROV_BOMB, "behemoth_bomb", is_aoe=True, aoe_radius=100, breakshellvalue=self.breakarmorvalue)
            bomb.speed = 5 
            self.game.projectiles.append(bomb)
            self.attack_cooldown = 180 

    def take_damage(self, amount, damage_type="normal",breakshellvalue=0):
        if self.is_crashing: return 
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.is_crashing = True
            self.crash_timer = 180 
            self.speed = 0.2 

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = screen_pos
        
        margin = 400 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return   
        scaled_img = scale_img(self.original_image, zoom)
        
        drop_offset = 0
        if not self.deployed:
            progress = 1 - (self.deploy_timer / 600) 
            
            alpha = int(50 + 205 * progress)
            scaled_img.set_alpha(alpha)
            
            drop_height = scale(150, zoom) * (1 - progress)
            cy -= drop_height 
            
            bar_w = scale(120, zoom)
            bar_h = scale(4, zoom)
            bar_x = cx - bar_w // 2
            bar_y = cy - scale(100, zoom) 
            
            pygame.draw.rect(surface, (0, 50, 100), (bar_x, bar_y, bar_w, bar_h)) 
            pygame.draw.rect(surface, (0, 255, 255), (bar_x, bar_y, bar_w * progress, bar_h)) 
            pygame.draw.line(surface, (0, 255, 255), (cx, bar_y - 5), (cx, bar_y + 10), 1)
        
        else:
            scaled_img.set_alpha(255)

        shadow_alpha = 60 if not self.deployed else 80
        
        s_w = scaled_img.get_width() * 0.7
        s_h = scaled_img.get_height() * 0.7
        shadow_surf = pygame.Surface((s_w, s_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, shadow_alpha), (0, 0, s_w, s_h))
        
        shadow_dist = scale(60, zoom)
        shadow_rect = shadow_surf.get_rect(center=(screen_pos[0] + shadow_dist, screen_pos[1] + shadow_dist))
        surface.blit(shadow_surf, shadow_rect)

        if self.alive and self.deployed and not self.is_crashing:
            rad = math.radians(self.angle)
            back_x = -math.cos(rad)
            back_y = math.sin(rad)
            
            thrust_dist = scale(70, zoom) 
            
            glow_x = cx + back_x * thrust_dist
            glow_y = cy + back_y * thrust_dist
            
            pulse = (math.sin(time.time() * 20) + 1.5) 
            glow_radius = int(scale(15 * pulse, zoom))
            
            s_glow = pygame.Surface((glow_radius*4, glow_radius*4), pygame.SRCALPHA)
            pygame.draw.circle(s_glow, (0, 100, 255, 50), (glow_radius*2, glow_radius*2), glow_radius*2)
            pygame.draw.circle(s_glow, (100, 200, 255, 100), (glow_radius*2, glow_radius*2), glow_radius)
            surface.blit(s_glow, (glow_x - glow_radius*2, glow_y - glow_radius*2))


        draw_angle = self.spin_angle if self.is_crashing else self.angle
        
        rotated_image = pygame.transform.rotate(scaled_img, draw_angle)
        
        new_rect = rotated_image.get_rect(center=(cx, cy))
        surface.blit(rotated_image, new_rect.topleft)
        
        if self.is_crashing:
            import random
            for _ in range(2):
                rx = random.randint(new_rect.left, new_rect.right)
                ry = random.randint(new_rect.top, new_rect.bottom)
                pygame.draw.circle(surface, (50, 50, 50), (rx, ry), random.randint(5, 10))
                if random.random() < 0.3:
                    pygame.draw.circle(surface, (255, 100, 0), (rx, ry), random.randint(3, 6))

        if self.deployed:
            self.draw_health_and_marker(surface, offset, zoom, -scale(100, zoom))


class ParatrooperPlane(Unit):
    def __init__(self, game, drop_pos, team):
        self.drop_target = vec(drop_pos)
        
        angle = random.uniform(0, 360)
        spawn_dist = 2000 
        start_pos = self.drop_target + vec(spawn_dist, 0).rotate(angle)
        
        super().__init__(game, start_pos, team)
        
        self.hp = 2000 
        self.max_hp = 2000
        self.speed = 12 
        self.is_mechanical = True
        self.is_air = True
        self.radius = 60
        self.rect = pygame.Rect(self.pos.x - 60, self.pos.y - 60, 120, 120)
        
        self.vel = (self.drop_target - self.pos).normalize() * self.speed
        self.angle = angle + 180 
        
        self.drop_timer = 0
        self.dropped_count = 0
        self.max_drop = PARATROOPER_COUNT
        self.is_dropping = False
        self.life_time = 1200 
        self.original_image = pygame.Surface((280, 240), pygame.SRCALPHA)
        
        C_BODY_BASE   = (60, 65, 70)      
        C_BODY_HILITE = (90, 95, 100)     
        C_WING        = (55, 60, 65)      
        C_WING_EDGE   = (80, 85, 90)      
        C_ENGINE      = (50, 50, 55)      
        C_INTAKE      = (10, 10, 10)      
        C_GLASS       = (10, 25, 40)      
        C_DETAIL      = (30, 30, 30)      
        
        
        
        pod_positions = [
            (80, 30), (100, 65),  
            (100, 175), (80, 210) 
        ]
        
        for px, py in pod_positions:
            pylon_end_y = 120 - 20 if py < 120 else 120 + 20
            pygame.draw.line(self.original_image, C_WING, (px+10, py+5), (px+30, pylon_end_y), 6)
            
            pygame.draw.rect(self.original_image, C_ENGINE, (px, py, 25, 6))
            pygame.draw.ellipse(self.original_image, (150,150,160), (px-2, py, 4, 6)) 
            pygame.draw.ellipse(self.original_image, C_INTAKE, (px-1, py+1, 2, 4))   
            
            pygame.draw.rect(self.original_image, C_ENGINE, (px, py+6, 25, 6))
            pygame.draw.ellipse(self.original_image, (150,150,160), (px-2, py+6, 4, 6))
            pygame.draw.ellipse(self.original_image, C_INTAKE, (px-1, py+7, 2, 4))
            
            pygame.draw.rect(self.original_image, (30,20,10), (px+25, py+1, 3, 4))
            pygame.draw.rect(self.original_image, (30,20,10), (px+25, py+7, 3, 4))

        wing_l_pts = [(180, 110), (130, 110), (60, 20), (100, 20)]
        pygame.draw.polygon(self.original_image, C_WING, wing_l_pts)
        wing_r_pts = [(180, 130), (130, 130), (60, 220), (100, 220)]
        pygame.draw.polygon(self.original_image, C_WING, wing_r_pts)
        
        pygame.draw.line(self.original_image, C_WING_EDGE, (180, 110), (100, 20), 2)
        pygame.draw.line(self.original_image, C_WING_EDGE, (180, 130), (100, 220), 2)
        
        pygame.draw.line(self.original_image, C_DETAIL, (140, 110), (80, 20), 1)
        pygame.draw.line(self.original_image, C_DETAIL, (140, 130), (80, 220), 1)
        
        pygame.draw.rect(self.original_image, C_ENGINE, (75, 18, 20, 6))
        pygame.draw.rect(self.original_image, C_ENGINE, (75, 216, 20, 6))

        body_points = [
            (240, 115), 
            (230, 108), (180, 105), 
            (40, 110),  
            (20, 120),  
            (40, 130),  
            (180, 135), (230, 132), 
            (240, 125)  
        ]
        pygame.draw.polygon(self.original_image, C_BODY_BASE, body_points)
        
        pygame.draw.rect(self.original_image, C_BODY_HILITE, (50, 115, 170, 10), border_radius=5)
        
        tail_wing_pts = [(50, 115), (25, 90), (45, 90), (60, 115), 
                         (60, 125), (45, 150), (25, 150), (50, 125)] 
        pygame.draw.polygon(self.original_image, C_WING, tail_wing_pts)
        
        pygame.draw.polygon(self.original_image, (50, 55, 60), [(60, 118), (30, 118), (20, 120), (60, 122)])

        cockpit_x = 205
        pygame.draw.polygon(self.original_image, C_GLASS, [(cockpit_x, 112), (cockpit_x+10, 115), (cockpit_x+10, 125), (cockpit_x, 128)])
        pygame.draw.polygon(self.original_image, C_GLASS, [(cockpit_x, 112), (195, 110), (195, 115)]) 
        pygame.draw.polygon(self.original_image, C_GLASS, [(cockpit_x, 128), (195, 130), (195, 125)]) 

        accent = (0, 150, 255) if self.team == "player" else (220, 50, 50)
        pygame.draw.rect(self.original_image, accent, (35, 112, 10, 16))
        pygame.draw.line(self.original_image, accent, (160, 110), (120, 50), 3)
        pygame.draw.line(self.original_image, accent, (160, 130), (120, 190), 3)

    def update(self):
        self.pos += self.vel
        self.life_time -= 1
        
        dist_from_target = self.pos.distance_to(self.drop_target)
        if self.life_time <= 0 or (dist_from_target > 2500 and self.dropped_count >= self.max_drop):
            self.alive = False
            return

        if dist_from_target < 500 and not self.is_dropping:
            self.is_dropping = True
        
        if self.is_dropping and self.dropped_count < self.max_drop:
            self.drop_timer += 1
            if self.drop_timer >= 3: 
                self.drop_timer = 0
                self.spawn_paratrooper()
                self.dropped_count += 1
        
        self.update_rect()

    def spawn_paratrooper(self):
        offset = vec(random.randint(-10, 10), random.randint(-10, 10))
        spawn_pos = self.pos + offset
        
        u_type = Rifleman if random.random() < 0.7 else RocketTrooper
        unit = u_type(self.game, spawn_pos, self.team)
        
        unit.deploy_timer = 120 
        
        land_offset = vec(random.randint(-100, 100), random.randint(-100, 100))
        unit.target_pos = spawn_pos + land_offset 
        
        self.game.all_units.append(unit)
    def draw(self, surface, offset, zoom):
        shadow_offset = scale(60, zoom)
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 300 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return           
        scaled_img = scale_img(self.original_image, zoom)
        rotated_img = pygame.transform.rotate(scaled_img, -self.angle)
        
        shadow_surf = rotated_img.copy()
        shadow_surf.fill((0, 0, 0, 100), special_flags=pygame.BLEND_RGBA_MULT)
        shadow_rect = shadow_surf.get_rect(center=(screen_pos[0] + shadow_offset//2, screen_pos[1] + shadow_offset))
        surface.blit(shadow_surf, shadow_rect)
        
        rect = rotated_img.get_rect(center=screen_pos)
        surface.blit(rotated_img, rect)
        
        self.draw_health_and_marker(surface, offset, zoom)


class FighterJet(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.faction = "USA" 
        if game.teams_config and team in game.teams_config:
            self.faction = game.teams_config[team].get('faction', 'USA')
        self.max_hp = FIGHTER_STATS[2]
        self.hp = self.max_hp
        self.speed = FIGHTER_STATS[1]
        self.radius = 20
        self.rect = pygame.Rect(pos.x-20, pos.y-20, 40, 40)
        self.attack_range=FIGHTER_STATS[0]

        self.is_air = True
        self.is_mechanical = True
        self.is_fixed_wing = True 
        self.can_attack_air = True
        self.canvas_size = 120       
        self.ammo = AMMO_CAPACITY
        self.max_ammo = AMMO_CAPACITY
        self.reload_timer = 0
        
        self.state = "SPAWNING"
        
        self.orbit_center = None 
        self.orbit_angle = 0     
        self.home_base = None    

        self.collision=False        
        self.find_home_base()
        print(f"[Fighter Init] Team: {self.team}, HomeBase: {self.home_base}")        
        if not self.game.is_online or self.game.my_role == "HOST":
            if self.home_base:
                old_pos = vec(self.pos)

                self.orbit_center = self.home_base.pos
                self.pos = self.get_nearest_edge(self.home_base.pos)
                self.angle = math.degrees(math.atan2(-(self.orbit_center.y - self.pos.y), self.orbit_center.x - self.pos.x))
            print(f"[Fighter Init] Moved from {old_pos} to {self.pos}")
        else:
            if self.home_base:
                self.orbit_center = self.home_base.pos
            else:
                self.orbit_center = self.pos 
        if self.faction == "CHINA":
            self.image = self._generate_j35()
        elif self.faction == "USA":
            self.image = self._generate_f35()
        elif self.faction == "RUSSIA":
            self.image = self._generate_su57()
        else:
            self.image = self._generate_j35() 
    def find_home_base(self):
        min_dist = 99999
        for b in self.game.all_buildings:
            if b.team == self.team and getattr(b, 'b_type', '') == 'airfield' and b.alive:
                dist = self.pos.distance_to(b.pos)
                if dist < min_dist:
                    min_dist = dist
                    self.home_base = b
        if not self.home_base:
            self.orbit_center = self.pos

    def get_nearest_edge(self, target_pos):
        if self.game.current_map:
            w = self.game.current_map.width
            h = self.game.current_map.height
        else:
            w, h = WORLD_WIDTH, WORLD_HEIGHT 
            
        x, y = target_pos.x, target_pos.y
        
        d_left = x
        d_right = w - x
        d_top = y
        d_bottom = h - y
        
        m = min(d_left, d_right, d_top, d_bottom)
        
        if m == d_left: return vec(0, y)
        if m == d_right: return vec(w, y)
        if m == d_top: return vec(x, 0)
        return vec(x, h)

    def set_target(self, entity):
        if isinstance(entity, Building) and entity.team == self.team:
            self.orbit_center = entity.pos
            self.target_entity = entity 
            self.state = "RETURNING"
            return

        super().set_target(entity) 
        if self.ammo > 0:
            if self.state != "ORBITING":
                self.state = "ATTACKING"

    def check_orbit_exit(self):
        target = self.target_entity
        
        if not target or not target.alive:
            target = self.find_nearest_enemy()
            
        if not target or target.team == self.team:
            return

        flight_dir = vec(1, 0).rotate(self.angle)
        
        to_target = (target.pos - self.pos).normalize()
        
        if flight_dir.dot(to_target) > 0.98:
            self.target_entity = target
            self.state = "ATTACKING"

    def update(self):
        if self.game.is_online and self.game.my_role == "CLIENT":
            self.update_rect(); return
        if self.attack_cooldown > 0: self.attack_cooldown -= 1

        if self.game.frame_count % 60 == 0: 
            self.hp= min(self.hp+10,self.max_hp) 
        if self.state in ["SPAWNING", "RETURNING"]:
            self.target_entity=None
            dist = self.pos.distance_to(self.orbit_center)
            
            if dist < ORBIT_RADIUS + 10:
                self.state = "ORBITING"
                diff = self.pos - self.orbit_center
                self.orbit_angle = math.degrees(math.atan2(diff.y, diff.x))
            else:
                self.move_towards(self.orbit_center)

        elif self.state == "ORBITING":
            self.orbit_angle += 2 
            
            offset = vec(ORBIT_RADIUS, 0).rotate(self.orbit_angle)
            self.pos = self.orbit_center + offset
            
            self.angle = self.orbit_angle + 90 
            
            is_at_airfield = False
            if self.home_base and self.orbit_center.distance_to(self.home_base.pos) < 50: 
                is_at_airfield = True
            elif self.target_entity and getattr(self.target_entity, 'b_type', '') == 'airfield':
                is_at_airfield = True
                
            if is_at_airfield and self.ammo < self.max_ammo:
                self.reload_timer += 1
                if self.reload_timer > 60:
                    self.ammo += 1
                    self.reload_timer = 0
                    if hasattr(self.game, 'net_events'):
                        self.game.net_events.append({
                            "type": "FX_TEXT", 
                            "x": int(self.pos.x), "y": int(self.pos.y),
                            "text": "+AMMO",
                            "color": "GREEN" 
                        })
                    self.game.particles.add(FloatingText(self.pos, "+AMMO", GREEN_HAT))
            self.check_orbit_exit()
            target = self.target_entity
            
            if target and target.team != self.team:
                self.target_entity = target 
                
                flight_dir = vec(1,0).rotate(-self.angle)
                
                to_target = (target.pos - self.pos).normalize()
                
                if flight_dir.dot(to_target) > 0.9: 
                    self.state = "ATTACKING"
        elif self.state == "ATTACKING":
            if self.ammo <= 0:
                self.target_entity=None
                self.state = "RETURNING"; return

            target = self.target_entity 
            if not target or not target.alive:
                self.state = "RECOVER"; return 

            dist = self.pos.distance_to(target.pos)
            
            if dist < 100: 
                self.state = "BREAKING"
                self.break_timer = 60 
                return
            self.move_towards(target.pos) 
            if self.attack_cooldown <= 0 and dist<self.attack_range:
                self.fire_missile(target)

        elif self.state == "BREAKING":
            if not hasattr(self, 'break_timer'):
                self.break_timer = 60 
            self.break_timer -= 1
            
            velocity = vec(self.speed * 1.2, 0).rotate(self.angle) 
            self.pos += velocity
            
            if self.break_timer <= 0:
                self.state = "RECOVER"

        elif self.state == "RECOVER":
            if self.target_entity and self.target_entity.alive:
                dist = self.pos.distance_to(self.target_entity.pos)
                if dist > self.attack_range * 0.8: 
                    self.state = "ATTACKING" 
                else:
                    velocity = vec(self.speed, 0).rotate(self.angle)
                    self.pos += velocity
            else:

                self.state = "RETURNING"
        self.update_rect()

    def move_towards(self, target_pos):
        diff = target_pos - self.pos
        target_angle = math.degrees(math.atan2(diff.y, diff.x)) 
        
        delta = (target_angle - self.angle + 180) % 360 - 180
        turn_rate = 4
        
        if abs(delta) < turn_rate:
            self.angle = target_angle
        else:
            self.angle += turn_rate if delta > 0 else -turn_rate
            
        velocity = vec(self.speed, 0).rotate(self.angle)
        self.pos += velocity
    def fire_missile(self,target):
        self.ammo -= 1
        proj = Projectile(self.game, self.pos, target, self.team, 60,"heavy", breakshellvalue=self.breakarmorvalue)
        proj.speed = 15 
        self.game.projectiles.append(proj)
        self.attack_cooldown = 5
    def draw_ammo_bar(self, surface, screen_pos, zoom):
        bar_w = scale(40, zoom)
        bar_h = scale(4, zoom)
        bx = screen_pos[0] - bar_w // 2
        by = screen_pos[1] - scale(30, zoom)
        
        pct = self.ammo / self.max_ammo
        
        c = GREEN_HAT if pct > 0.5 else RED
        
        pygame.draw.rect(surface, (0, 0, 0), (bx, by, bar_w, bar_h))
        pygame.draw.rect(surface, c, (bx, by, bar_w * pct, bar_h))
        pygame.draw.rect(surface, (200, 200, 200), (bx, by, bar_w, bar_h), 1)
        self.canvas_size = 120 
        
    def _draw_gradient_body(self, surf, pts, color):
        """绘制带有简单光影立体感的机身"""
        pygame.draw.polygon(surf, color, pts)
        
        highlight = (min(255, color[0]+40), min(255, color[1]+40), min(255, color[2]+40))
        center_x = sum([p[0] for p in pts]) / len(pts)
        center_y = sum([p[1] for p in pts]) / len(pts)
        
        high_pts = []
        for p in pts:
            dx = center_x - p[0]
            dy = center_y - p[1]
            high_pts.append((p[0] + dx*0.4, p[1] + dy*0.6)) 
        
        if len(high_pts) > 2:
            s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            pygame.draw.polygon(s, (*highlight, 80), high_pts) 
            surf.blit(s, (0,0))

    def _draw_serrated_nozzle(self, surf, start, width, length, color):
        """绘制锯齿状隐身喷口"""
        
        teeth = 3
        pts = []
        pts.append((start[0], start[1] - width/2))
        
        step = width / teeth
        for i in range(teeth):
            y_top = start[1] - width/2 + i * step
            y_bot = y_top + step
            x_out = start[0] - length
            x_in = start[0] - length + 3
            
            pts.append((x_out, y_top))
            pts.append((x_in, (y_top+y_bot)/2))
            
        pts.append((start[0] - length, start[1] + width/2))
        pts.append((start[0], start[1] + width/2))
        
        pygame.draw.polygon(surf, color, pts)
        pygame.draw.lines(surf, (30,30,30), True, pts, 1)

    def _generate_j35(self):
        s = self.canvas_size
        cx, cy = s//2, s//2
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        
        C_MAIN = (150, 160, 170)
        C_DARK = (110, 120, 130)
        C_TRIM = (190, 200, 210) 
        C_GLASS = (180, 150, 50) 
        C_NOZZLE = (60, 60, 65)
        
        body_pts = [
            (cx+55, cy),    
            (cx+20, cy-8),  
            (cx-30, cy-10), 
            (cx-45, cy-6),  
            (cx-45, cy+6),
            (cx-30, cy+10),
            (cx+20, cy+8)
        ]
        self._draw_gradient_body(surf, body_pts, C_MAIN)
        
        pygame.draw.polygon(surf, C_DARK, [(cx+15, cy-5), (cx-5, cy-9), (cx-5, cy-5)])
        pygame.draw.polygon(surf, C_DARK, [(cx+15, cy+5), (cx-5, cy+9), (cx-5, cy+5)])

        wing_l = [(cx+5, cy-5), (cx-25, cy-42), (cx-38, cy-42), (cx-25, cy-8)]
        wing_r = [(cx+5, cy+5), (cx-25, cy+42), (cx-38, cy+42), (cx-25, cy+8)]
        
        pygame.draw.polygon(surf, C_MAIN, wing_l)
        pygame.draw.polygon(surf, C_MAIN, wing_r)
        
        pygame.draw.line(surf, C_DARK, (cx-25, cy-42), (cx-20, cy-10), 1)
        pygame.draw.line(surf, C_DARK, (cx-25, cy+42), (cx-20, cy+10), 1)
        pygame.draw.line(surf, C_TRIM, wing_l[0], wing_l[1], 1)
        pygame.draw.line(surf, C_TRIM, wing_r[0], wing_r[1], 1)

        stab_l = [(cx-25, cy-6), (cx-50, cy-25), (cx-45, cy-6)]
        stab_r = [(cx-25, cy+6), (cx-50, cy+25), (cx-45, cy+6)]
        pygame.draw.polygon(surf, C_MAIN, stab_l)
        pygame.draw.polygon(surf, C_MAIN, stab_r)
        
        pygame.draw.line(surf, C_DARK, (cx-20, cy-6), (cx-40, cy-14), 4)
        pygame.draw.line(surf, C_DARK, (cx-20, cy+6), (cx-40, cy+14), 4)

        self._draw_serrated_nozzle(surf, (cx-45, cy-4), 6, 8, C_NOZZLE)
        self._draw_serrated_nozzle(surf, (cx-45, cy+4), 6, 8, C_NOZZLE)

        canopy_rect = (cx+10, cy-5, 20, 10)
        pygame.draw.ellipse(surf, C_GLASS, canopy_rect)
        pygame.draw.ellipse(surf, (200,200,200), (cx+15, cy-3, 10, 4)) 

        return surf

    def _generate_f35(self):
        s = self.canvas_size
        cx, cy = s//2, s//2
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        
        C_BODY = (90, 95, 100)
        C_RAM  = (130, 135, 140) 
        C_NOZZLE = (40, 40, 40)
        C_GLASS = (40, 60, 70)
        
        body_pts = [
            (cx+48, cy),     
            (cx+15, cy-12),  
            (cx-20, cy-12),  
            (cx-40, cy-6),   
            (cx-40, cy+6),
            (cx-20, cy+12),
            (cx+15, cy+12)
        ]
        self._draw_gradient_body(surf, body_pts, C_BODY)
        
        pygame.draw.lines(surf, C_RAM, False, [(cx+20, cy-8), (cx+5, cy-14), (cx-5, cy-12)], 2)
        pygame.draw.lines(surf, C_RAM, False, [(cx+20, cy+8), (cx+5, cy+14), (cx-5, cy+12)], 2)

        wing_l = [(cx+5, cy-8), (cx-20, cy-38), (cx-32, cy-38), (cx-22, cy-8)]
        wing_r = [(cx+5, cy+8), (cx-20, cy+38), (cx-32, cy+38), (cx-22, cy+8)]
        pygame.draw.polygon(surf, C_BODY, wing_l)
        pygame.draw.polygon(surf, C_BODY, wing_r)
        
        pygame.draw.line(surf, C_RAM, wing_l[0], wing_l[1], 2) 
        pygame.draw.line(surf, C_RAM, wing_r[0], wing_r[1], 2)
        pygame.draw.lines(surf, C_RAM, False, [(cx-25, cy-38), (cx-22, cy-25), (cx-28, cy-8)], 1)
        pygame.draw.lines(surf, C_RAM, False, [(cx-25, cy+38), (cx-22, cy+25), (cx-28, cy+8)], 1)

        stab_l = [(cx-25, cy-6), (cx-45, cy-25), (cx-40, cy-6)]
        stab_r = [(cx-25, cy+6), (cx-45, cy+25), (cx-40, cy+6)]
        pygame.draw.polygon(surf, C_BODY, stab_l)
        pygame.draw.polygon(surf, C_BODY, stab_r)
        pygame.draw.polygon(surf, C_RAM, stab_l, 1)
        pygame.draw.polygon(surf, C_RAM, stab_r, 1)
        
        pygame.draw.line(surf, (70,75,80), (cx-28, cy-8), (cx-45, cy-18), 5)
        pygame.draw.line(surf, (70,75,80), (cx-28, cy+8), (cx-45, cy+18), 5)

        self._draw_serrated_nozzle(surf, (cx-40, cy), 12, 10, C_NOZZLE)
        
        pygame.draw.polygon(surf, (30,30,40), [(cx+35, cy), (cx+40, cy-3), (cx+45, cy), (cx+40, cy+3)])
        
        pygame.draw.circle(surf, C_RAM, (cx, cy), 8, 1)
        
        pygame.draw.ellipse(surf, C_GLASS, (cx+15, cy-6, 16, 12))

        return surf

    def _generate_su57(self):
        s = self.canvas_size
        cx, cy = s//2, s//2
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        
        C_BASE = (130, 150, 170)
        C_CAMO_DARK = (100, 120, 140)
        C_CAMO_LIGHT = (180, 190, 200)
        C_METAL = (180, 180, 180) 
        C_GLASS = (160, 140, 80)  
        
        body_pts = [
            (cx+50, cy),    
            (cx+20, cy-6),  
            (cx-20, cy-8),  
            (cx-40, cy-4),  
            (cx-40, cy+4),
            (cx-20, cy+8),
            (cx+20, cy+6)
        ]
        pygame.draw.polygon(surf, C_BASE, body_pts)
        
        pts_wing_l = [(cx+15, cy-10), (cx-25, cy-45), (cx-35, cy-45), (cx-25, cy-10)]
        pts_wing_r = [(cx+15, cy+10), (cx-25, cy+45), (cx-35, cy+45), (cx-25, cy+10)]
        pygame.draw.polygon(surf, C_BASE, pts_wing_l)
        pygame.draw.polygon(surf, C_BASE, pts_wing_r)
        
        pygame.draw.polygon(surf, C_BASE, [(cx+15, cy-10), (cx+30, cy-8), (cx+20, cy-6)])
        pygame.draw.polygon(surf, C_BASE, [(cx+15, cy+10), (cx+30, cy+8), (cx+20, cy+6)])

        eng_l = pygame.Rect(cx-35, cy-14, 50, 8)
        pygame.draw.rect(surf, C_BASE, eng_l)
        eng_r = pygame.Rect(cx-35, cy+6, 50, 8)
        pygame.draw.rect(surf, C_BASE, eng_r)
        
        for _ in range(15):
            rx = random.randint(cx-10, cx+10)
            ry = random.randint(cy-10, cy+20)
            size = random.randint(4, 8)
            color = C_CAMO_DARK if random.random() > 0.5 else C_CAMO_LIGHT
            if abs(ry - cy) < 30:
                pygame.draw.rect(surf, color, (rx, ry, size, size))

        pygame.draw.polygon(surf, C_BASE, [(cx-40, cy-3), (cx-60, cy), (cx-40, cy+3)])
        
        pygame.draw.circle(surf, C_METAL, (cx-35, cy-10), 4)
        pygame.draw.circle(surf, C_METAL, (cx-35, cy+10), 4)
        pygame.draw.circle(surf, (20,20,20), (cx-35, cy-10), 2)
        pygame.draw.circle(surf, (20,20,20), (cx-35, cy+10), 2)

        pygame.draw.polygon(surf, C_CAMO_DARK, [(cx-25, cy-12), (cx-45, cy-22), (cx-40, cy-12)])
        pygame.draw.polygon(surf, C_CAMO_DARK, [(cx-25, cy+12), (cx-45, cy+22), (cx-40, cy+12)])

        pygame.draw.ellipse(surf, C_GLASS, (cx+15, cy-5, 16, 10))
        pygame.draw.circle(surf, (50, 50, 50), (cx+32, cy), 2)

        return surf


    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 300 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return              
        scaled_img = scale_img(self.image, zoom)
        rot_img = pygame.transform.rotate(scaled_img, -self.angle)
        
        rect = rot_img.get_rect(center=screen_pos)
        surface.blit(rot_img, rect)
        
        valid_states = ["ATTACKING", "BREAKING", "RETURNING", "ORBITING", "SPAWNING"]
        
        if self.state in valid_states:
            rear_vec = vec(-1, 0).rotate(self.angle)
            
            if self.faction== "USA":
                fire_pos = self.pos + rear_vec * 40
                self._draw_afterburner(surface, fire_pos, offset, zoom, size=6)
            else: 
                offset_l = vec(0, -6).rotate(self.angle)
                offset_r = vec(0, 6).rotate(self.angle)
                if self.faction == "RUSSIA":
                    offset_l *= 1.5
                    offset_r *= 1.5
                
                self._draw_afterburner(surface, self.pos + rear_vec * 40 + offset_l, offset, zoom, size=4)
                self._draw_afterburner(surface, self.pos + rear_vec * 40 + offset_r, offset, zoom, size=4)
        self.draw_ammo_bar(surface, screen_pos, zoom)
        self.draw_health_and_marker(surface, offset, zoom)
        self.draw_health_and_marker(surface, offset, zoom)

    def _draw_afterburner(self, surface, world_pos, offset, zoom, size):
        """绘制喷气火焰特效"""
        sp = to_screen(world_pos, offset, zoom)
        r = scale(random.randint(size, size+3), zoom)
        pygame.draw.circle(surface, (255, 100, 50), sp, r)
        pygame.draw.circle(surface, (255, 255, 200), sp, r * 0.5)


class AttackPlane(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = ATTACKER_STATS[2]
        self.hp = self.max_hp
        self.speed = ATTACKER_STATS[1]
        self.armor=5
        self.is_air = True
        self.is_mechanical = True
        self.is_fixed_wing = True
        self.faction = "USA" 
        if game.teams_config and team in game.teams_config:
            self.faction = game.teams_config[team].get('faction', 'USA')        
        self.radius = 25
        self.rect = pygame.Rect(pos.x-25, pos.y-25, 50, 50)
        
        self.state = "SPAWNING" 
        self.home_base = None
        self.find_home_base()
        
        if self.home_base:
            self.orbit_center = self.home_base.pos
            if not self.game.is_online or self.game.my_role == "HOST":
                self.pos = self.get_nearest_edge(self.home_base.pos)
        else:
            self.orbit_center = self.pos

        self.orbit_angle = 0
        self.bomb_target = None 
        
        self.has_bomb = True 
        self.reload_timer = 0

        self.collision=False         
        if self.faction == "CHINA":
            self.image = self._generate_jh7()
        elif self.faction == "USA":
            self.image = self._generate_fa18()
        elif self.faction == "RUSSIA":
            self.image = self._generate_su25()
        else:
            self.image = self._generate_jh7() 
    def find_home_base(self):
        min_dist = 99999
        for b in self.game.all_buildings:
            if b.team == self.team and getattr(b, 'b_type', '') == 'airfield' and b.alive:
                dist = self.pos.distance_to(b.pos)
                if dist < min_dist:
                    min_dist = dist
                    self.home_base = b
        if not self.home_base:
            self.orbit_center = self.pos
    def get_nearest_edge(self, target_pos):
        if self.game.current_map:
            w = self.game.current_map.width
            h = self.game.current_map.height
        else:
            w, h = WORLD_WIDTH, WORLD_HEIGHT 
            
        x, y = target_pos.x, target_pos.y
        
        d_left = x
        d_right = w - x
        d_top = y
        d_bottom = h - y
        
        m = min(d_left, d_right, d_top, d_bottom)
        
        if m == d_left: return vec(0, y)
        if m == d_right: return vec(w, y)
        if m == d_top: return vec(x, 0)
        return vec(x, h)


    def check_orbit_exit(self):
        target = self.target_entity
        
        if not target or not target.alive:
            target = self.find_nearest_enemy()
            
        if not target or target.team == self.team:
            return

        flight_dir = vec(1, 0).rotate(self.angle)
        
        to_target = (target.pos - self.pos).normalize()
        
        if flight_dir.dot(to_target) > 0.98:
            self.target_entity = target
            self.state = "ATTACKING"
    def move_to(self, target_pos):
        if self.has_bomb:
            self.bomb_target = vec(target_pos)
            self.state = "BOMBING_RUN"
            self.game.particles.add(FloatingText(self.pos, "BOMBING RUN!", RED))
        else:
            self.game.show_alert("NO AMMO!")
    def move_towards(self, target_pos):
        diff = target_pos - self.pos
        target_angle = math.degrees(math.atan2(diff.y, diff.x)) 
        
        delta = (target_angle - self.angle + 180) % 360 - 180
        turn_rate = 4
        
        if abs(delta) < turn_rate:
            self.angle = target_angle
        else:
            self.angle += turn_rate if delta > 0 else -turn_rate
            
        velocity = vec(self.speed, 0).rotate(self.angle)
        self.pos += velocity
    def set_target(self, entity):
        if isinstance(entity, Building) and entity.team == self.team:
            self.orbit_center = entity.pos
            self.state = "RETURNING"
            return

        if entity and entity.alive:
            self.move_to(entity.pos) 
    def update(self):
        if self.game.is_online and self.game.my_role == "CLIENT":
            self.update_rect(); return
        if self.game.frame_count % 60 == 0: 
            self.hp= min(self.hp+10,self.max_hp)      
        if self.state in ["SPAWNING", "RETURNING"]:
            dist = self.pos.distance_to(self.orbit_center)
            if dist < ORBIT_RADIUS + 10:
                self.state = "ORBITING"
                d = self.pos - self.orbit_center
                self.orbit_angle = math.degrees(math.atan2(d.y, d.x))
            else:
                self.move_towards(self.orbit_center)

        elif self.state == "ORBITING":
            self.orbit_angle += 0.5 
            offset = vec(ORBIT_RADIUS, 0).rotate(self.orbit_angle)
            self.pos = self.orbit_center + offset
            self.angle = self.orbit_angle + 90
            
            if not self.has_bomb and self.home_base and self.home_base.alive:
                if self.orbit_center.distance_to(self.home_base.pos) < 50:
                    self.reload_timer += 1
                    if self.reload_timer > BOMB_RELOAD_TIME: 
                        self.has_bomb = True
                        self.reload_timer = 0
                        if hasattr(self.game, 'net_events'):
                            self.game.net_events.append({
                                "type": "FX_TEXT", 
                                "x": int(self.pos.x), "y": int(self.pos.y),
                                "text": "RELOADED",
                                "color": "GREEN" 
                            })
                        self.game.particles.add(FloatingText(self.pos, "RELOADED", GREEN_HAT))
        elif self.state == "BOMBING_RUN":
            if not self.bomb_target:
                self.state = "RETURNING"; return
            
            dist = self.pos.distance_to(self.bomb_target)
            
            self.move_towards(self.bomb_target)
            
            if dist < 150:
                self.drop_bombs()
                self.state = "RETURNING"


        self.update_rect()

    def drop_bombs(self):
        if not self.has_bomb: return
        self.has_bomb = False
        
        flight_dir = vec(1, 0).rotate(-self.angle).normalize()
        

        offsets = [-50, 50] 
        
        for off in offsets:
            spread_vec = flight_dir * off + flight_dir.rotate(90) * random.randint(-20, 20)
            
            target = self.bomb_target + spread_vec
            
            p = Projectile(self.game, self.pos, None, self.team, BOMB_DAMAGE, "behemoth_bomb", is_aoe=True, aoe_radius=80)
            p.target_dest = target
            p.speed = 8
            
            p.vel = (target - self.pos).normalize() * p.speed
            
            self.game.projectiles.append(p)

    def _draw_gradient_body(self, surf, pts, color):
        """绘制带有简单光影立体感的机身"""
        pygame.draw.polygon(surf, color, pts)
        center_x = sum([p[0] for p in pts]) / len(pts)
        center_y = sum([p[1] for p in pts]) / len(pts)
        high_pts = []
        for p in pts:
            dx = center_x - p[0]
            dy = center_y - p[1]
            high_pts.append((p[0] + dx*0.4, p[1] + dy*0.6))
        
        if len(high_pts) > 2:
            highlight = (min(255, color[0]+40), min(255, color[1]+40), min(255, color[2]+40))
            s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            pygame.draw.polygon(s, (*highlight, 80), high_pts)
            surf.blit(s, (0,0))

    def _generate_jh7(self):
        s = 120 
        cx, cy = s//2, s//2
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        
        C_BODY = (220, 220, 230)
        C_DARK = (150, 150, 160) 
        C_GLASS = (30, 40, 50)   
        C_NOSE = (20, 20, 20)    
        C_ENGINE = (60, 60, 65)  
        
        body_pts = [
            (cx+55, cy),    
            (cx+30, cy-10), 
            (cx-30, cy-10), 
            (cx-50, cy-7),  
            (cx-50, cy+7),
            (cx-30, cy+10),
            (cx+30, cy+10)
        ]
        self._draw_gradient_body(surf, body_pts, C_BODY)
        
        pygame.draw.polygon(surf, C_NOSE, [(cx+55, cy), (cx+48, cy-4), (cx+48, cy+4)])

        pygame.draw.rect(surf, C_BODY, (cx+10, cy-14, 20, 6))
        pygame.draw.rect(surf, C_BODY, (cx+10, cy+8, 20, 6))
        pygame.draw.line(surf, C_NOSE, (cx+30, cy-14), (cx+30, cy-8), 3)
        pygame.draw.line(surf, C_NOSE, (cx+30, cy+8), (cx+30, cy+14), 3)

        wing_l = [(cx+15, cy-10), (cx-15, cy-50), (cx-28, cy-50), (cx-15, cy-10)]
        wing_r = [(cx+15, cy+10), (cx-15, cy+50), (cx-28, cy+50), (cx-15, cy+10)]
        
        pygame.draw.polygon(surf, C_BODY, wing_l)
        pygame.draw.polygon(surf, C_BODY, wing_r)
        
        pygame.draw.line(surf, C_DARK, (cx-5, cy-30), (cx-12, cy-30), 2)
        pygame.draw.line(surf, C_DARK, (cx-5, cy+30), (cx-12, cy+30), 2)
        
        for i in range(2):
            off = 20 + i*15
            pygame.draw.line(surf, (50,50,50), (cx, cy-off), (cx+5, cy-off), 2)
            pygame.draw.line(surf, (50,50,50), (cx, cy+off), (cx+5, cy+off), 2)

        stab_l = [(cx-35, cy-8), (cx-55, cy-25), (cx-48, cy-8)]
        stab_r = [(cx-35, cy+8), (cx-55, cy+25), (cx-48, cy+8)]
        pygame.draw.polygon(surf, C_BODY, stab_l)
        pygame.draw.polygon(surf, C_BODY, stab_r)
        
        pygame.draw.polygon(surf, C_DARK, [(cx-35, cy), (cx-55, cy), (cx-50, cy)], 3)
        
        pygame.draw.line(surf, C_DARK, (cx-40, cy-6), (cx-48, cy-6), 2)
        pygame.draw.line(surf, C_DARK, (cx-40, cy+6), (cx-48, cy+6), 2)

        pygame.draw.rect(surf, C_GLASS, (cx+20, cy-5, 18, 10), border_radius=4)
        pygame.draw.line(surf, C_BODY, (cx+29, cy-5), (cx+29, cy+5), 2) 

        pygame.draw.circle(surf, C_ENGINE, (cx-50, cy-5), 4)
        pygame.draw.circle(surf, C_ENGINE, (cx-50, cy+5), 4)

        return surf

    def _generate_fa18(self):
        s = 120
        cx, cy = s//2, s//2
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        
        C_BODY = (140, 145, 150) 
        C_DARK = (100, 105, 110)
        C_GLASS = (180, 140, 50) 
        C_NOZZLE = (40, 40, 45)
        
        body_pts = [
            (cx+50, cy),    
            (cx+25, cy-8),  
            (cx-10, cy-12), 
            (cx-45, cy-8),  
            (cx-45, cy+8),
            (cx-10, cy+12),
            (cx+25, cy+8)
        ]
        self._draw_gradient_body(surf, body_pts, C_BODY)
        
        pygame.draw.polygon(surf, C_BODY, [(cx+30, cy-6), (cx-5, cy-12), (cx+5, cy-20)])
        pygame.draw.polygon(surf, C_BODY, [(cx+30, cy+6), (cx-5, cy+12), (cx+5, cy+20)])

        wing_l = [(cx+5, cy-12), (cx-20, cy-45), (cx-35, cy-45), (cx-25, cy-12)]
        wing_r = [(cx+5, cy+12), (cx-20, cy+45), (cx-35, cy+45), (cx-25, cy+12)]
        pygame.draw.polygon(surf, C_BODY, wing_l)
        pygame.draw.polygon(surf, C_BODY, wing_r)
        
        pygame.draw.line(surf, (60,60,60), (cx-20, cy-45), (cx-20, cy-50), 2)
        pygame.draw.line(surf, (60,60,60), (cx-20, cy+45), (cx-20, cy+50), 2)

        stab_l = [(cx-30, cy-10), (cx-50, cy-28), (cx-45, cy-10)]
        stab_r = [(cx-30, cy+10), (cx-50, cy+28), (cx-45, cy+10)]
        pygame.draw.polygon(surf, C_BODY, stab_l)
        pygame.draw.polygon(surf, C_BODY, stab_r)
        
        v_l = [(cx-25, cy-10), (cx-40, cy-20), (cx-45, cy-10)]
        v_r = [(cx-25, cy+10), (cx-40, cy+20), (cx-45, cy+10)]
        pygame.draw.polygon(surf, C_DARK, v_l)
        pygame.draw.polygon(surf, C_DARK, v_r)

        pygame.draw.rect(surf, (50,50,55), (cx, cy-12, 10, 6))
        pygame.draw.rect(surf, (50,50,55), (cx, cy+6, 10, 6))

        pygame.draw.ellipse(surf, C_GLASS, (cx+20, cy-6, 16, 12))
        
        pygame.draw.circle(surf, C_NOZZLE, (cx-45, cy-5), 4)
        pygame.draw.circle(surf, C_NOZZLE, (cx-45, cy+5), 4)

        return surf

    def _generate_su25(self):
        s = 120
        cx, cy = s//2, s//2
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        
        C_BASE = (100, 120, 80) 
        C_CAMO = (140, 130, 90) 
        C_ENG  = (110, 120, 130)
        C_GLASS= (60, 80, 100)
        
        body_pts = [
            (cx+45, cy),    
            (cx+30, cy-6),
            (cx-40, cy-6),
            (cx-50, cy),    
            (cx-40, cy+6),
            (cx+30, cy+6)
        ]
        self._draw_gradient_body(surf, body_pts, C_BASE)
        pygame.draw.circle(surf, C_CAMO, (cx-10, cy), 12)
        pygame.draw.circle(surf, C_CAMO, (cx+20, cy), 8)

        eng_len = 40
        eng_w = 8
        eng_x = cx - 20
        
        pygame.draw.rect(surf, C_ENG, (eng_x, cy-14, eng_len, eng_w), border_radius=3)
        pygame.draw.circle(surf, (20,20,20), (eng_x+eng_len, cy-10), 3) 
        pygame.draw.rect(surf, C_ENG, (eng_x, cy+6, eng_len, eng_w), border_radius=3)
        pygame.draw.circle(surf, (20,20,20), (eng_x+eng_len, cy+10), 3) 

        wing_l = [(cx+10, cy-10), (cx, cy-50), (cx-15, cy-50), (cx-10, cy-10)]
        wing_r = [(cx+10, cy+10), (cx, cy+50), (cx-15, cy+50), (cx-10, cy+10)]
        pygame.draw.polygon(surf, C_BASE, wing_l)
        pygame.draw.polygon(surf, C_BASE, wing_r)
        
        for i in range(4):
            off = 12 + i*9
            pygame.draw.line(surf, (40,40,40), (cx+5, cy-off), (cx-5, cy-off), 2)
            pygame.draw.line(surf, (40,40,40), (cx+5, cy+off), (cx-5, cy+off), 2)
            if i % 2 == 0: 
                pygame.draw.ellipse(surf, (30,50,30), (cx-2, cy-off-2, 8, 4))
                pygame.draw.ellipse(surf, (30,50,30), (cx-2, cy+off-2, 8, 4))

        stab_l = [(cx-40, cy-3), (cx-50, cy-15), (cx-45, cy-3)]
        stab_r = [(cx-40, cy+3), (cx-50, cy+15), (cx-45, cy+3)]
        pygame.draw.polygon(surf, C_BASE, stab_l)
        pygame.draw.polygon(surf, C_BASE, stab_r)
        pygame.draw.line(surf, C_ENG, (cx-35, cy), (cx-50, cy), 4)

        pygame.draw.rect(surf, C_GLASS, (cx+25, cy-4, 8, 8))
        pygame.draw.line(surf, (200,200,200), (cx+25, cy-4), (cx+25, cy+4), 1) 

        return surf

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 200 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return              
        scaled_img = scale_img(self.image, zoom)
        
        rot_img = pygame.transform.rotate(scaled_img, -self.angle)
        rect = rot_img.get_rect(center=screen_pos)
        
        if self.speed > 0: 
            shadow_dist = 20 * zoom
            mask = pygame.mask.from_surface(rot_img)
            shadow_surf = mask.to_surface(setcolor=(0,0,0,80), unsetcolor=(0,0,0,0))
            surface.blit(shadow_surf, (rect.x + shadow_dist, rect.y + shadow_dist))
        
        surface.blit(rot_img, rect)
        
        if self.state in ["ORBITING", "BOMBING_RUN", "RETURNING"]:
            rear_vec = vec(-1, 0).rotate(self.angle)
            
            off_l = vec(0, -5).rotate(self.angle)
            off_r = vec(0, 5).rotate(self.angle)
            
            base_pos = self.pos + rear_vec * 40 
            
            if self.faction == "RUSSIA":
                off_l *= 2.0
                off_r *= 2.0
                base_pos = self.pos + rear_vec * 20 
            
            fp_l = base_pos + off_l
            fp_r = base_pos + off_r
            
            sp_l = to_screen(fp_l, offset, zoom)
            sp_r = to_screen(fp_r, offset, zoom)
            
            r = scale(random.randint(3, 5), zoom)
            pygame.draw.circle(surface, (255, 120, 50), sp_l, r)
            pygame.draw.circle(surface, (255, 120, 50), sp_r, r)
            pygame.draw.circle(surface, (255, 200, 100), sp_l, int(r*0.6))
            pygame.draw.circle(surface, (255, 200, 100), sp_r, int(r*0.6))

        self.draw_ammo_bar(surface, screen_pos, zoom)
        self.draw_health_and_marker(surface, offset, zoom)

    def draw_ammo_bar(self, surface, screen_pos, zoom):
        if self.has_bomb:
            bx = screen_pos[0]
            by = screen_pos[1] - scale(35, zoom)
            pygame.draw.circle(surface, (0, 255, 0), (int(bx), int(by)), int(scale(3, zoom)))
        elif self.reload_timer > 0:
            bar_w = scale(30, zoom)
            bx = screen_pos[0] - bar_w//2
            by = screen_pos[1] - scale(35, zoom)
            pct = self.reload_timer / BOMB_RELOAD_TIME
            pygame.draw.rect(surface, (0,0,0), (bx, by, bar_w, 4))
            pygame.draw.rect(surface, (255, 255, 0), (bx, by, bar_w*pct, 4))


class StealthHeli(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp =STEALHELI_STATS[2]
        self.hp = self.max_hp
        self.speed = STEALHELI_STATS[1]  
        self.armor=5
        self.radius = 20  
        self.is_air = True
        self.can_attack_air = True
        self.is_mechanical = True
        
        self.stealth_mode = True 
        self.is_stealth = True   
        self.rotor_angle = 0     
        
        self.cannon_range = STEALHELI_STATS[0]
        self.bomb_range = 50

        self.img_stealth = self.generate_heli_image(mode="stealth")
        self.img_attack = self.generate_heli_image(mode="attack")

    def generate_heli_image(self, mode):
        w, h = 140, 140
        cx, cy = w // 2, h // 2
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        
        C_BODY_DARK = (35, 40, 45)
        C_BODY_LIGHT = (50, 55, 60)
        C_COCKPIT = (15, 15, 20)
        C_GLASS = (100, 130, 150)
        C_WING = (30, 30, 30)
        
        if mode == "attack":
            pygame.draw.polygon(surf, C_WING, [
                (cx + 14, cy - 11), (cx - 7, cy - 35), (cx - 21, cy - 35), (cx - 7, cy - 11)
            ])
            pygame.draw.polygon(surf, C_WING, [
                (cx + 14, cy + 11), (cx - 7, cy + 35), (cx - 21, cy + 35), (cx - 7, cy + 11)
            ])
            pygame.draw.line(surf, (160, 50, 50), (cx - 7, cy - 35), (cx + 7, cy - 35), 3)
            pygame.draw.line(surf, (160, 50, 50), (cx - 7, cy + 35), (cx + 7, cy + 35), 3)

        fuselage_pts = [
            (cx + 68, cy),       
            (cx + 49, cy - 7),   
            (cx + 14, cy - 11),  
            (cx - 28, cy - 8),   
            (cx - 63, cy - 3),   
            (cx - 68, cy),       
            (cx - 63, cy + 3), 
            (cx - 28, cy + 8),
            (cx + 14, cy + 11),
            (cx + 49, cy + 7)    
        ]
        pygame.draw.polygon(surf, C_BODY_DARK, fuselage_pts)
        pygame.draw.line(surf, C_BODY_LIGHT, (cx + 68, cy), (cx - 56, cy), 1)

        tail_pts_l = [(cx - 49, cy - 4), (cx - 63, cy - 17), (cx - 56, cy - 3)]
        tail_pts_r = [(cx - 49, cy + 4), (cx - 63, cy + 17), (cx - 56, cy + 3)]
        pygame.draw.polygon(surf, C_BODY_LIGHT, tail_pts_l)
        pygame.draw.polygon(surf, C_BODY_LIGHT, tail_pts_r)

        cockpit_pts = [
            (cx + 56, cy), 
            (cx + 42, cy - 4), 
            (cx + 28, cy), 
            (cx + 42, cy + 4)
        ]
        pygame.draw.polygon(surf, C_COCKPIT, cockpit_pts)
        pygame.draw.line(surf, C_GLASS, (cx + 49, cy - 1), (cx + 40, cy - 1), 1)

        return surf

    def toggle_mode(self):
        self.stealth_mode = not self.stealth_mode
        self.is_stealth = self.stealth_mode
        
        msg = "STEALTH" if self.stealth_mode else "ASSAULT"
        color = (50, 255, 255) if self.stealth_mode else (255, 50, 50)
        self.game.particles.add(FloatingText(self.pos, msg, color))

    def update(self):
        if self.stealth_mode:
            self.attack_range = self.bomb_range 
        else:
            self.attack_range = self.cannon_range 
        
        super().update()
        
        spin_rate = 50 if not self.stealth_mode else 30
        self.rotor_angle = (self.rotor_angle + spin_rate) % 360

    def perform_attack(self, target):
        if self.attack_cooldown > 0: return

        if self.stealth_mode:
            self.drop_bomb(target)
        else:
            self.fire_cannon(target)

    def drop_bomb(self, target):
        p = Projectile(self.game, self.pos, target, self.team, 180,"heavy",breakshellvalue=self.breakarmorvalue)
        p.is_aoe = True
        p.aoe_radius = 100
        p.speed = 7
        self.game.projectiles.append(p)
        self.attack_cooldown = 70 

    def fire_cannon(self, target):
        p = Projectile(self.game, self.pos, target, self.team, 15, "bullet",breakshellvalue=self.breakarmorvalue)
        p.speed = 22
        self.game.projectiles.append(p)
        self.attack_cooldown = 5 

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 300 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return              
        base_img = self.img_stealth if self.stealth_mode else self.img_attack
        scaled_img = scale_img(base_img, zoom)
        rot_img = pygame.transform.rotate(scaled_img, self.angle) 
        
        img_rect = rot_img.get_rect(center=screen_pos)
        
            
        surface.blit(rot_img, img_rect)
        
        current_time = pygame.time.get_ticks()
        if (current_time % 1000) < 100:
            light_offset_l = vec(42, -10) 
            light_offset_r = vec(42, 10)
            
            offset_l_rot = light_offset_l.rotate(-self.angle)
            offset_r_rot = light_offset_r.rotate(-self.angle)
            
            offset_l_rot *= zoom
            offset_r_rot *= zoom
            
            light_pos_l = screen_pos + offset_l_rot
            light_pos_r = screen_pos + offset_r_rot
            
            glow_radius = int(6 * zoom) 
            pygame.draw.circle(surface, (255, 255, 255), (int(light_pos_l.x), int(light_pos_l.y)), glow_radius)
            pygame.draw.circle(surface, (255, 255, 255), (int(light_pos_r.x), int(light_pos_r.y)), glow_radius)
            
            core_radius = int(3 * zoom)
            pygame.draw.circle(surface, (255, 50, 50), (int(light_pos_l.x), int(light_pos_l.y)), core_radius) 
            pygame.draw.circle(surface, (50, 255, 50), (int(light_pos_r.x), int(light_pos_r.y)), core_radius) 

        rotor_radius = 60 * zoom 
        s_size = int(rotor_radius * 2.2)
        rotor_surf = pygame.Surface((s_size, s_size), pygame.SRCALPHA)
        rc = (s_size//2, s_size//2)
        blade_col = (10, 10, 10, 200) if not self.stealth_mode else (200, 255, 255, 50)
        
        num_blades = 5
        for i in range(num_blades):
            theta = math.radians(self.rotor_angle + i * (360/num_blades))
            end_x = rc[0] + math.cos(theta) * rotor_radius
            end_y = rc[1] + math.sin(theta) * rotor_radius
            pygame.draw.line(rotor_surf, blade_col, rc, (end_x, end_y), int(2*zoom))
            
        pygame.draw.circle(rotor_surf, blade_col, rc, int(4*zoom))
        rotor_rect = rotor_surf.get_rect(center=screen_pos)
        surface.blit(rotor_surf, rotor_rect)
        
        self.draw_health_and_marker(surface, offset, zoom)


class Mi24(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = HIND_STATS[2]
        self.hp = self.max_hp
        self.speed = HIND_STATS[1]
        self.attack_range = HIND_STATS[0]
        self.armor=15
        self.damage = 25 
        self.is_mechanical = True
        self.is_air = True
        self.can_attack_air = True
        self.radius = 35
        self.rect = pygame.Rect(pos.x-35, pos.y-35, 70, 70)
        
        self.is_crashing = False
        self.crash_timer = 0
        self.spin_angle = 0
        
        self.turret_angle = 0
        self.gun_cooldown = 5
        self.rocket_cooldown = 15
        
        self.turret_image = self.gen_turret_image()
        self.original_image = self.gen_body_image()


    def gen_body_image(self):
        w, h = 170, 160
        cx, cy = w // 2, h // 2
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        
        C_CAMO_BASE  = (160, 155, 120)  
        C_CAMO_DARK  = (70, 85, 60)     
        C_BELLY      = (100, 120, 130)  
        C_GLASS      = (40, 60, 80)     
        C_GLASS_HI   = (150, 180, 200)  
        C_METAL      = (80, 80, 85)     
        C_TIRE       = (20, 20, 20)     
        C_EXHAUST    = (40, 30, 25)     
        C_POD        = (90, 90, 95)     
        C_MISSILE    = (140, 60, 50)    
        
        c_team = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])

        pts_wing_l = [(cx-10, cy-15), (cx-20, cy-55), (cx-5, cy-55), (cx+15, cy-15)]
        pygame.draw.polygon(s, C_CAMO_BASE, pts_wing_l)
        pygame.draw.polygon(s, C_CAMO_DARK, [(cx-10, cy-15), (cx-15, cy-35), (cx, cy-35)], 0) 
        
        pts_wing_r = [(cx-10, cy+15), (cx-20, cy+55), (cx-5, cy+55), (cx+15, cy+15)]
        pygame.draw.polygon(s, C_CAMO_BASE, pts_wing_r)
        pygame.draw.polygon(s, C_CAMO_DARK, [(cx-10, cy+15), (cx-15, cy+35), (cx, cy+35)], 0) 

        for y_off in [-30, -45, 30, 45]:
            pygame.draw.line(s, C_METAL, (cx-15, cy+y_off), (cx+5, cy+y_off), 3)
        
        for y_off in [-30, 30]:
            pygame.draw.rect(s, C_POD, (cx-5, cy+y_off-5, 20, 10), border_radius=3)
            pygame.draw.circle(s, (20,20,20), (cx+15, cy+y_off), 4)
            pygame.draw.circle(s, (60,60,60), (cx+15, cy+y_off), 2)

        for y_off in [-55, 55]:
            pygame.draw.rect(s, C_METAL, (cx-20, cy+y_off-2, 25, 4))
            pygame.draw.rect(s, (180,180,180), (cx-15, cy+y_off-1, 22, 2))
            pygame.draw.circle(s, C_MISSILE, (cx+7, cy+y_off), 2)

        tail_rect = pygame.Rect(cx-75, cy-7, 60, 14)
        pygame.draw.rect(s, C_CAMO_BASE, tail_rect)
        pygame.draw.ellipse(s, C_CAMO_DARK, (cx-70, cy-7, 20, 8)) 
        
        pygame.draw.polygon(s, C_CAMO_BASE, [(cx-75, cy-5), (cx-90, cy-25), (cx-80, cy-5)])
        pygame.draw.circle(s, C_METAL, (cx-90, cy-25), 4)
        
        pygame.draw.ellipse(s, C_CAMO_BASE, (cx-35, cy-18, 80, 36))
        pygame.draw.arc(s, (50,50,50), (cx-35, cy-18, 80, 36), 3.5, 5.9, 2)

        pygame.draw.ellipse(s, C_CAMO_DARK, (cx-20, cy-16, 50, 14))
        pygame.draw.circle(s, C_TIRE, (cx+22, cy-9), 5) 
        pygame.draw.circle(s, C_EXHAUST, (cx-22, cy-10), 4) 
        
        pygame.draw.ellipse(s, C_CAMO_DARK, (cx-20, cy+2, 50, 14))
        pygame.draw.circle(s, C_TIRE, (cx+22, cy+9), 5) 
        pygame.draw.circle(s, C_EXHAUST, (cx-22, cy+10), 4) 
        
        smoke_surf = pygame.Surface((40, 40), pygame.SRCALPHA)
        pygame.draw.circle(smoke_surf, (0,0,0,40), (20,20), 15)
        s.blit(smoke_surf, (cx-50, cy-20))
        s.blit(smoke_surf, (cx-50, cy-5))

        pygame.draw.ellipse(s, C_GLASS, (cx+15, cy-8, 20, 16))
        pygame.draw.line(s, C_METAL, (cx+25, cy-8), (cx+25, cy+8), 1)
        pygame.draw.ellipse(s, C_GLASS_HI, (cx+18, cy-5, 6, 4))
        
        pygame.draw.ellipse(s, C_GLASS, (cx+32, cy-6, 16, 12))
        pygame.draw.ellipse(s, C_GLASS_HI, (cx+35, cy-4, 5, 3))

        pygame.draw.circle(s, (100, 100, 100), (cx-15, cy), 5) 
        pygame.draw.circle(s, (200, 50, 50), (cx-15, cy), 2)  

        pygame.draw.circle(s, C_METAL, (cx, cy), 7)
        pygame.draw.circle(s, (180, 180, 180), (cx, cy), 3) 
        for i in range(5):
            angle = i * (360/5)
            rad = math.radians(angle)
            ex = cx + math.cos(rad) * 10
            ey = cy + math.sin(rad) * 10
            pygame.draw.line(s, C_METAL, (cx, cy), (ex, ey), 2)

        pygame.draw.circle(s, c_team, (cx-50, cy), 4)
        if self.team == "red": 
            pygame.draw.line(s, (255,255,0), (cx-50, cy-2), (cx-50, cy+2), 1)
            pygame.draw.line(s, (255,255,0), (cx-52, cy), (cx-48, cy), 1)

        return s
    def gen_turret_image(self):
        
        w, h = 40, 20
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        
        C_GUN_BODY = (50, 50, 55) 
        C_BARREL = (20, 20, 20)   
        C_TIP = (10, 10, 10)      
        
        pygame.draw.ellipse(s, C_GUN_BODY, (0, 5, 12, 10))
        
        pygame.draw.rect(s, C_GUN_BODY, (8, 7, 10, 6))
        
        
        barrel_len = 18
        barrel_x = 18
        
        pygame.draw.rect(s, C_BARREL, (barrel_x, 6, barrel_len, 3))
        pygame.draw.rect(s, C_BARREL, (barrel_x, 11, barrel_len, 3))
        
        clamp_x = barrel_x + barrel_len - 2
        pygame.draw.line(s, (60,60,60), (clamp_x, 5), (clamp_x, 15), 2)
        
        pygame.draw.circle(s, C_TIP, (barrel_x + barrel_len, 7), 1)
        pygame.draw.circle(s, C_TIP, (barrel_x + barrel_len, 12), 1)

        return s

    def take_damage(self, amount, damage_type="normal",breakshellvalue=0):
        if self.is_crashing: return 
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.is_crashing = True
            self.crash_timer = 90
            self.speed = 1.5 

    def update(self):
        if self.is_crashing:
            self.crash_timer -= 1
            self.spin_angle += 15
            self.pos += vec(random.uniform(-1, 1), random.uniform(-1, 1))
            if self.crash_timer <= 0:
                self.die() 
                self.game.particles.add(FloatingText(self.pos, "CRASH!", WHITE))
            self.update_rect()
            return

        super().update()
        
        if self.gun_cooldown > 0: self.gun_cooldown -= 1
        if self.rocket_cooldown > 0: self.rocket_cooldown -= 1

        target = self.target_entity

        if not target or not target.alive:
            target = self.find_nearest_enemy()
            
        if target:
            dist = self.pos.distance_to(target.pos)
            
            dx, dy = target.pos.x - self.pos.x, target.pos.y - self.pos.y
            target_angle = math.degrees(math.atan2(-dy, dx))
            
            self.turret_angle = target_angle
            
            if dist < self.attack_range:
                if self.gun_cooldown <= 0:
                    self.fire_gun(target)
                
                angle_diff = (target_angle - self.angle + 180) % 360 - 180
                if abs(angle_diff) < 20 and self.rocket_cooldown <= 0:
                    self.fire_rockets(target)
    def die(self):
        for _ in range(3):
            spawn_pos = self.pos + vec(random.randint(-20, 20), random.randint(-20, 20))
            
            u_type = random.choice(["rifleman", "rocket"])
            if u_type == "rifleman":
                u = Rifleman(self.game, spawn_pos, self.team)
            else:
                u = RocketTrooper(self.game, spawn_pos, self.team)
                        
            self.game.all_units.append(u)
        super().die()
    def fire_gun(self, target):

        turret_base_offset = vec(45, 0).rotate(-self.angle) 
        
        muzzle_offset = vec(25, 0).rotate(-self.turret_angle) 
        
        spawn_pos = self.pos + turret_base_offset + muzzle_offset
        
        self.game.projectiles.append(
            Projectile(self.game, spawn_pos, target, self.team, 8,"bullet",breakshellvalue=self.breakarmorvalue) 
        )
        self.gun_cooldown = 5 
    def fire_rockets(self, target):
        off_l = vec(10, -20).rotate(-self.angle)
        off_r = vec(10, 20).rotate(-self.angle)
        
        start_l = self.pos + off_l
        start_r = self.pos + off_r
        
        base_dest = target.pos
        dest_l = base_dest + vec(random.randint(-25, 25), random.randint(-25, 25))
        dest_r = base_dest + vec(random.randint(-25, 25), random.randint(-25, 25))
        
        p1 = Projectile(self.game, start_l, None, self.team, 35,"rocket", is_aoe=True, aoe_radius=40,breakshellvalue=self.breakarmorvalue)
        p1.target_dest = dest_l  
        
        direction_l = (dest_l - start_l).normalize()
        p1.vel = direction_l * p1.speed 
        
        p2 = Projectile(self.game, start_r, None, self.team, 35, "rocket", is_aoe=True, aoe_radius=40,breakshellvalue=self.breakarmorvalue)
        p2.target_dest = dest_r
        
        direction_r = (dest_r - start_r).normalize()
        p2.vel = direction_r * p2.speed
        
        self.game.projectiles.append(p1)
        self.game.projectiles.append(p2)
        
        self.rocket_cooldown = 60

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 400 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return              
        draw_angle = self.spin_angle if self.is_crashing else self.angle
        s_body = scale_img(self.original_image, zoom)
        rot_body = pygame.transform.rotate(s_body, draw_angle)
        rect_body = rot_body.get_rect(center=screen_pos)
        
        if self.alive and not self.is_crashing:
            shadow_offset = vec(20, 20) * zoom
            shadow_rect = rect_body.copy()
            shadow_rect.center += shadow_offset
            
            mask = pygame.mask.from_surface(rot_body)
            shadow_surf = mask.to_surface(setcolor=(0,0,0,80), unsetcolor=(0,0,0,0))
            surface.blit(shadow_surf, shadow_rect)

        if self.alive and not self.is_crashing:
            turret_offset_vec = vec(45 * zoom, 0).rotate(-draw_angle) 
            turret_screen_pos = (screen_pos[0] + turret_offset_vec.x, screen_pos[1] + turret_offset_vec.y)
            
            s_tur = scale_img(self.turret_image, zoom)
            rot_tur = pygame.transform.rotate(s_tur, self.turret_angle)
            rect_tur = rot_tur.get_rect(center=turret_screen_pos)
            surface.blit(rot_tur, rect_tur)

        surface.blit(rot_body, rect_body)
        
        if self.alive or self.is_crashing:
            rotor_speed = 25 if self.alive else 5
            rotor_angle = (pygame.time.get_ticks() * rotor_speed * 0.05) % 360
            
            rx, ry = screen_pos
            blade_len = 75 * zoom
            num_blades = 5
            
            for i in range(num_blades):
                angle_deg = rotor_angle + i * (360/num_blades)
                rad = math.radians(angle_deg)
                end_x = rx + math.cos(rad) * blade_len
                end_y = ry - math.sin(rad) * blade_len 
                pygame.draw.line(surface, (20, 20, 20), (rx, ry), (end_x, end_y), int(4*zoom))
                tip_x = rx + math.cos(rad) * (blade_len - 5*zoom)
                tip_y = ry - math.sin(rad) * (blade_len - 5*zoom)
                pygame.draw.line(surface, (200, 200, 50), (tip_x, tip_y), (end_x, end_y), int(4*zoom))

        self.draw_health_and_marker(surface, offset, zoom)

