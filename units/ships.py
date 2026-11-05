import pygame
import random
import math
from core.settings import *
from core.base_classes import *
from .base import *

class MissileBoat(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.view_radius = 600        
        self.hp = 600
        self.max_hp = 600
        self.speed = 4.0
        self.attack_range = 250 
        self.damage = 80
        self.attack_speed = 2.0 
        self.view_radius = 500
        self.is_naval = True 
        self.is_mechanical = True
        self.can_attack_air = False
        self.radius = 25
        self.rect = pygame.Rect(pos.x - 25, pos.y - 25, 50, 50)


        self.original_image = pygame.Surface((100, 50), pygame.SRCALPHA)
        
        C_HULL_SIDE  = (60, 70, 80)     
        C_DECK       = (100, 110, 120)  
        C_SUPER      = (120, 130, 140)  
        C_WINDOW     = (20, 30, 40)     
        C_MISSILE    = (220, 220, 230)  
        C_RADAR      = (30, 30, 35)     
        C_HELIPAD    = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])    
        

        deck_points = [
            (95, 25),  
            (85, 10),  
            (10, 8),   
            (5, 15),   
            (5, 35),   
            (10, 42),  
            (85, 40)   
        ]
        pygame.draw.polygon(self.original_image, C_DECK, deck_points)
        
        side_points = [
            (95, 25), (85, 40), (10, 42), (5, 35), 
            (5, 38), (10, 45), (80, 43), (92, 28)  
        ]
        pygame.draw.polygon(self.original_image, C_HULL_SIDE, side_points)
        
        pygame.draw.rect(self.original_image, C_HELIPAD, (10, 12, 25, 26))
        pygame.draw.circle(self.original_image, (200, 200, 200), (22, 25), 10, 1)
        pygame.draw.line(self.original_image, (200, 200, 200), (22, 18), (22, 32), 2)
        pygame.draw.line(self.original_image, (200, 200, 200), (19, 25), (25, 25), 2)

        pygame.draw.rect(self.original_image, C_SUPER, (35, 12, 30, 26))
        pygame.draw.rect(self.original_image, (140, 150, 160), (45, 15, 15, 20))
        pygame.draw.rect(self.original_image, C_WINDOW, (55, 16, 3, 18))
        
        mast_x = 42
        pygame.draw.rect(self.original_image, (50, 50, 60), (mast_x, 15, 4, 20))
        pygame.draw.line(self.original_image, (50, 50, 60), (mast_x+2, 10), (mast_x+2, 40), 2)
        pygame.draw.circle(self.original_image, (200, 200, 200), (mast_x+2, 15), 3)

        pygame.draw.rect(self.original_image, (40, 40, 45), (38, 20, 6, 10))
        pygame.draw.ellipse(self.original_image, (10, 10, 10), (39, 22, 4, 6)) 

        
        gun_x, gun_y = 75, 25
        pygame.draw.circle(self.original_image, (110, 120, 130), (gun_x, gun_y), 6)
        pygame.draw.line(self.original_image, (30, 30, 35), (gun_x, gun_y), (gun_x+12, gun_y), 3)
        
        pygame.draw.rect(self.original_image, C_MISSILE, (50, 8, 12, 6))
        pygame.draw.line(self.original_image, (50, 50, 50), (50, 11), (62, 11), 1) 
        pygame.draw.rect(self.original_image, C_MISSILE, (50, 36, 12, 6))
        pygame.draw.line(self.original_image, (50, 50, 50), (50, 39), (62, 39), 1)
        
        pygame.draw.circle(self.original_image, (200, 200, 200), (32, 25), 4)
        pygame.draw.circle(self.original_image, (20, 20, 20), (32, 25), 1)

        accent = (0, 150, 255) if self.team == "player" else (220, 50, 50)
        pygame.draw.line(self.original_image, accent, (70, 15), (80, 20), 2)
        pygame.draw.line(self.original_image, accent, (70, 35), (80, 30), 2)
    def find_nearest_enemy(self):
        nearest = None
        min_dist = 700
        target_team = "player" if self.team == "enemy" else "enemy"
        
        valid_targets = []
        for u in self.game.all_units:
            if u.team == target_team and u.alive:
                if u.is_air and not self.can_attack_air: continue
                valid_targets.append(u)
        
        if self.team == "enemy" and self.ai_mode == "ATTACK" and not valid_targets:
            if self.game.player_base and self.game.player_base.alive: return self.game.player_base

        if not valid_targets:
            for b in self.game.all_buildings:
                if b.team == target_team and b.alive: valid_targets.append(b)
        if self.team == "player":
            for b in self.game.all_buildings:
                if b.team != self.team and b.alive:
                    d = self.pos.distance_to(b.pos)
                    if d < min_dist:
                        min_dist = d
                        nearest = b
        for e in valid_targets:
            dist = self.pos.distance_to(e.pos)
            if dist < min_dist: min_dist = dist; nearest = e
        return nearest        

    def perform_attack(self, target):
        if self.attack_cooldown <= 0:
            dmg = self.damage * self.tech_bonus_dmg
            offset_y = -5 if (pygame.time.get_ticks() // 1000) % 2 == 0 else 5
            launch_pos = self.pos + vec(10, offset_y).rotate(self.angle)
            
            proj = Projectile(self.game, launch_pos, target, self.team, dmg,"rocket", is_aoe=True, aoe_radius=60, breakshellvalue=self.breakarmorvalue)
            
            self.game.projectiles.append(proj)
            self.attack_cooldown = self.attack_speed * 60

    def draw(self, surface, offset, zoom):
        if self.target_pos and self.pos.distance_to(self.target_pos) > 5:
            wake_start = to_screen(self.pos - vec(20, 0).rotate(self.angle), offset, zoom)
            pass 

        scaled_img = scale_img(self.original_image, zoom)
        rotated_img = cached_rotate(scaled_img, self.angle) 
        
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        new_rect = rotated_img.get_rect(center=screen_pos)
        surface.blit(rotated_img, new_rect.topleft)
        
        self.draw_health_and_marker(surface, offset, zoom)


        if self.target_pos and self.pos.distance_to(self.target_pos) > 5:
            wake_start = to_screen(self.pos - vec(20, 0).rotate(self.angle), offset, zoom)
            pass 

        scaled_img = scale_img(self.original_image, zoom)
        rotated_img = cached_rotate(scaled_img, self.angle) 
        
        screen_pos = to_screen(self.pos, offset, zoom)
        new_rect = rotated_img.get_rect(center=screen_pos)
        surface.blit(rotated_img, new_rect.topleft)
        
        self.draw_health_and_marker(surface, offset, zoom)


class LaserDestroyer(Unit):
    _sprite_cache = {}
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = LASER_SHIP_STATS[2]
        self.hp = self.max_hp
        self.speed = LASER_SHIP_STATS[1]
        self.attack_range = LASER_SHIP_STATS[0]
        self.is_naval = True
        self.is_mechanical = True
        self.can_attack_air=False
        self.radius = 45
        self.rect = pygame.Rect(pos.x-45, pos.y-45, 90, 90)
        
        self.charge_level = 0
        self.charge_timer = 0
        self.last_target = None        
        self.image = self.get_sprite()
        self.offset_distance=-50
    def get_sprite(self):
        if "rifleman" not in LaserDestroyer._sprite_cache:
            path = resource_path("sprites/laserdestroyer/laserdestroyer.png")
            img = downscale_texture(pygame.image.load(path).convert_alpha())
            LaserDestroyer._sprite_cache["laserdestroyer"] = img        
        return LaserDestroyer._sprite_cache["laserdestroyer"]        
    def update(self):
        super().update() 
        if not self.game.is_online or self.game.my_role == "HOST":
            is_moving = (self.pos - getattr(self, 'prev_pos', self.pos)).length() > 0.1
            if is_moving:
                self.charge_level = 0
                self.charge_timer = 0
                return
            target = self.target_entity or self.find_nearest_enemy()
            if target != self.last_target:
                self.charge_level = 0
                self.charge_timer = 0
                self.last_target = target
            
            if target and target.alive:
                dist = self.pos.distance_to(target.pos)
                if dist < self.attack_range:
                    self.fire_laser(target)
                    
                    if self.charge_level < LASER_LEVELS:
                        self.charge_timer += 1
                        if self.charge_timer > LASER_RAMP_UP:
                            self.charge_level += 1
                            self.charge_timer = 0
                else:
                    self.charge_level = 0
            else:
                self.charge_level = 0
                self.charge_timer = 0

    def fire_laser(self, target):
        damage = LASER_DMG_BASE * (1 + self.charge_level)
        
        target.take_damage(damage, "energy")
        
        breakshell=(self.charge_level)*1000
        p = Projectile(self.game, self.pos, target, self.team, 0, "laser2", 
                       breakshellvalue=breakshell)
        self.game.projectiles.append(p)
        
        if self.charge_level >= LASER_LEVELS:
            self.fire_splash(target, damage)

    def fire_splash(self, target, damage):
        beam_dir = (target.pos - self.pos).normalize()
        splash_start = target.pos
        splash_end = splash_start + beam_dir * 300
        
        for u in self.game.all_units:
            if u != target and u.alive and u.team != self.team:
                dist = self.point_distance_line(u.pos, splash_start, splash_end)
                if dist < 200: 
                    u.take_damage(damage * 0.5, "energy")
                    
        p = Projectile(self.game, splash_start, None, self.team, 0, "laser2", breakshellvalue=3000)
        p.target_dest = splash_end
        self.game.projectiles.append(p)

    def point_distance_line(self, point, start, end):
        line_vec = end - start
        point_vec = point - start
        
        line_len = line_vec.length()
        
        if line_len == 0: 
            return point_vec.length() 
            

        
        line_unit = line_vec.normalize()
        proj = point_vec.dot(line_unit)
        
        if proj < 0:
            return point_vec.length() 
        if proj > line_len:
            return (point - end).length() 
            
        perpendicular_vec = point_vec - line_unit * proj
        return perpendicular_vec.length()
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        
        scaled_hull = scale_img(self.image, zoom)
        rot_hull = cached_rotate(scaled_hull, self.angle) 
        rot_hull = cached_rotate(scaled_hull, self.angle)
        
        rect = rot_hull.get_rect(center=screen_pos)
        surface.blit(rot_hull, rect)
        
        core_offset = vec(40 * zoom, 0).rotate(-self.angle) 
        
        core_pos = (screen_pos[0] + core_offset.x, screen_pos[1] + core_offset.y)
        
        charge_pct = self.charge_level / LASER_LEVELS
        
        if self.charge_level > 0 or self.charge_timer > 0:
            base_r = scale(9, zoom) 
            glow_r = scale(15 + 15 * charge_pct, zoom)
            
            colors = [
                (0, 200, 255),   
                (100, 100, 255), 
                (200, 0, 255),   
                (255, 50, 50)    
            ]
            
            idx = min(int(self.charge_level), 3)
            base_color = colors[idx]
            
            core_color = (
                min(255, base_color[0] + 100),
                min(255, base_color[1] + 100),
                min(255, base_color[2] + 100)
            )
            pygame.draw.circle(surface, core_color, (int(core_pos[0]), int(core_pos[1])), int(base_r))
            
            glow_surf = pygame.Surface((int(glow_r*2), int(glow_r*2)), pygame.SRCALPHA)
            
            alpha = int(100 + 100 * charge_pct)
            glow_rgba = (*base_color, alpha)
            
            pygame.draw.circle(glow_surf, glow_rgba, (int(glow_r), int(glow_r)), int(glow_r))
            surface.blit(glow_surf, (core_pos[0]-glow_r, core_pos[1]-glow_r), special_flags=pygame.BLEND_ADD)

        self.draw_health_and_marker(surface, offset, zoom)


        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled_hull = scale_img(self.image, zoom)
        rot_hull = cached_rotate(scaled_hull, self.angle) 
        rot_hull = cached_rotate(scaled_hull, self.angle)
        
        rect = rot_hull.get_rect(center=screen_pos)
        surface.blit(rot_hull, rect)
        
        core_offset = vec(40 * zoom, 0).rotate(-self.angle) 
        
        core_pos = (screen_pos[0] + core_offset.x, screen_pos[1] + core_offset.y)
        
        charge_pct = self.charge_level / LASER_LEVELS
        
        if self.charge_level > 0 or self.charge_timer > 0:
            base_r = scale(9, zoom) 
            glow_r = scale(15 + 15 * charge_pct, zoom)
            
            colors = [
                (0, 200, 255),   
                (100, 100, 255), 
                (200, 0, 255),   
                (255, 50, 50)    
            ]
            
            idx = min(int(self.charge_level), 3)
            base_color = colors[idx]
            
            core_color = (
                min(255, base_color[0] + 100),
                min(255, base_color[1] + 100),
                min(255, base_color[2] + 100)
            )
            pygame.draw.circle(surface, core_color, (int(core_pos[0]), int(core_pos[1])), int(base_r))
            
            glow_surf = pygame.Surface((int(glow_r*2), int(glow_r*2)), pygame.SRCALPHA)
            
            alpha = int(100 + 100 * charge_pct)
            glow_rgba = (*base_color, alpha)
            
            pygame.draw.circle(glow_surf, glow_rgba, (int(glow_r), int(glow_r)), int(glow_r))
            surface.blit(glow_surf, (core_pos[0]-glow_r, core_pos[1]-glow_r), special_flags=pygame.BLEND_ADD)

        self.draw_health_and_marker(surface, offset, zoom)


class AAFrigate(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = AABOAT_STATS[2]
        self.hp = self.max_hp
        self.speed = AABOAT_STATS[1]
        self.radius = 35
        self.rect = pygame.Rect(pos.x-70, pos.y-70, 140, 140)
        self.is_mechanical = True
        self.is_naval = True
        
        self.attack_range = AABOAT_STATS[0]
        self.damage = 18
        self.can_attack_air = True 
        
        self.turret_angle = 0
        
        self.hull_image = self.generate_hull_image()
        self.turret_image = self.generate_turret_image()
        self.offset_distance=-50
    def generate_hull_image(self):
        w, h = 240, 80
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        
        C_HULL_DARK  = (70, 80, 90)   
        C_HULL_LIGHT = (100, 110, 120)
        C_DECK       = (60, 65, 70)   
        C_DETAIL     = (40, 45, 50)   
        C_WINDOW     = (20, 30, 40)   
        C_PAD        = (50, 50, 55)   
        
        hull_pts = [
            (235, cy),      
            (190, cy-22),   
            (30, cy-22),    
            (10, cy-14),    
            (10, cy+14),    
            (30, cy+22),    
            (190, cy+22)    
        ]
        pygame.draw.polygon(s, C_HULL_DARK, hull_pts) 
        
        deck_pts = [(p[0]-2, p[1]*0.9 + cy*0.1) for p in hull_pts]
        pygame.draw.polygon(s, C_HULL_LIGHT, deck_pts)

        pygame.draw.rect(s, C_HULL_LIGHT, (130, cy-14, 30, 28))
        pygame.draw.rect(s, C_DETAIL, (130, cy-14, 30, 28), 1) 
        pygame.draw.rect(s, C_WINDOW, (150, cy-10, 6, 20))
        
        pygame.draw.rect(s, (80, 85, 90), (90, cy-10, 30, 20))
        pygame.draw.circle(s, (20,20,20), (105, cy), 6)
        
        pygame.draw.rect(s, C_HULL_LIGHT, (60, cy-12, 20, 24))

        vls_x = 170
        pygame.draw.rect(s, C_DECK, (vls_x-5, cy-10, 20, 20))
        for r in range(2):
            for c in range(4):
                pygame.draw.rect(s, (30,30,30), (vls_x + c*4, cy - 6 + r*8, 2, 2))
                
        pygame.draw.rect(s, (200, 100, 50), (100, cy-22, 10, 4))
        pygame.draw.rect(s, (200, 100, 50), (100, cy+18, 10, 4))
        
        pygame.draw.line(s, C_DETAIL, (140, cy), (120, cy), 2)
        pygame.draw.line(s, C_DETAIL, (130, cy-10), (130, cy+10), 2)

        pad_rect = pygame.Rect(15, cy-18, 40, 36)
        pygame.draw.rect(s, C_PAD, pad_rect)
        pygame.draw.line(s, (200,200,200), (25, cy-8), (25, cy+8), 3)
        pygame.draw.line(s, (200,200,200), (45, cy-8), (45, cy+8), 3)
        pygame.draw.line(s, (200,200,200), (25, cy), (45, cy), 3)
        
        pygame.draw.circle(s, C_DECK, (80, cy-20), 10)
        pygame.draw.circle(s, C_DECK, (80, cy+20), 10)

        return s
    def generate_turret_image(self):

        s = pygame.Surface((40, 40), pygame.SRCALPHA)
        cx, cy = 20, 20
        
        C_BOX = (70, 80, 70)
        C_TUBE = (30, 30, 35)
        
        pygame.draw.circle(s, (50, 55, 60), (cx, cy), 12)
        
        box_w, box_h = 24, 18
        pygame.draw.rect(s, C_BOX, (cx-8, cy-9, box_w, box_h), border_radius=3)
        
        for r in range(2):
            for c in range(3):
                px = cx + 8 + c * 2 
                py = cy - 5 + r * 8
                pygame.draw.circle(s, C_TUBE, (px, py), 3)
                pygame.draw.circle(s, (10,10,10), (px, py), 1)
        
        return s

    def set_target(self, entity):
        if entity and entity.alive and getattr(entity, 'is_air', False):
            super().set_target(entity)
        else:
            if entity:
                self.move_to(entity.pos)

    def update(self):
        super().update() 
        
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        
        if not self.game.is_online or self.game.my_role == "HOST":
            
            fire_target = None
            
            if self.target_entity and self.target_entity.alive:
                if getattr(self.target_entity, 'is_air', False):
                    fire_target = self.target_entity
            
            if not fire_target:
                fire_target = self.find_air_target()
            
            if fire_target:
                # 先转炮后打：防空炮塔平滑转向敌机，对准（±8°）才允许开火
                diff = fire_target.pos - self.pos
                target_a = math.degrees(math.atan2(-diff.y, diff.x))
                if aim_turret(self, target_a, turn_rate=4, tolerance=8) \
                        and self.pos.distance_to(fire_target.pos) < self.attack_range \
                        and self.attack_cooldown <= 0:
                    self.perform_attack(fire_target)

    def find_air_target(self):
        best = None
        min_dist = self.attack_range
        
        for u in self.game.all_units:
            if u.team != self.team and u.alive and getattr(u, 'is_air', False):
                d = self.pos.distance_to(u.pos)
                if d < min_dist:
                    min_dist = d
                    best = u
        return best

    def perform_attack(self, target):
        if self.attack_cooldown > 0: return
        if not getattr(target, 'is_air', False): return

        side_vec = vec(0, 1).rotate(-self.turret_angle) 
        
        offsets = [side_vec * 10, side_vec * -10]
        
        for off in offsets:
            spawn_pos = self.pos + off
            
            spread = vec(random.randint(-50, 50), random.randint(-50, 50))
            aim_point = target.pos + spread
            
            dmg = self.damage / 2
            
            p = Projectile(self.game, spawn_pos, None, self.team, dmg, "bullet", is_aoe=True, aoe_radius=40)
            p.target_dest = aim_point
            p.speed = 25
            p.vel = (aim_point - spawn_pos).normalize() * p.speed
            p.color = (255, 255, 100)
            
            self.game.projectiles.append(p)
            
        self.attack_cooldown = 18 

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        
        scaled_hull = scale_img(self.hull_image, zoom)
        rot_hull = cached_rotate(scaled_hull, self.angle) 
        rect_hull = rot_hull.get_rect(center=screen_pos)
        surface.blit(rot_hull, rect_hull)
        
        
        launcher_offsets = [
            vec(-40 * zoom, -20 * zoom), 
            vec(-40 * zoom,  20 * zoom)  
        ]
        
        scaled_launcher = scale_img(self.turret_image, zoom)
        rot_launcher = cached_rotate(scaled_launcher, self.turret_angle)
        
        for off_vec in launcher_offsets:
            
            current_offset = off_vec.rotate(-self.angle)
            
            launcher_pos = (screen_pos[0] + current_offset.x, screen_pos[1] + current_offset.y)
            rect = rot_launcher.get_rect(center=launcher_pos)
            surface.blit(rot_launcher, rect)
        
        self.draw_health_and_marker(surface, offset, zoom)


        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled_hull = scale_img(self.hull_image, zoom)
        rot_hull = cached_rotate(scaled_hull, self.angle) 
        rect_hull = rot_hull.get_rect(center=screen_pos)
        surface.blit(rot_hull, rect_hull)
        
        
        launcher_offsets = [
            vec(-40 * zoom, -20 * zoom), 
            vec(-40 * zoom,  20 * zoom)  
        ]
        
        scaled_launcher = scale_img(self.turret_image, zoom)
        rot_launcher = cached_rotate(scaled_launcher, self.turret_angle)
        
        for off_vec in launcher_offsets:
            
            current_offset = off_vec.rotate(-self.angle)
            
            launcher_pos = (screen_pos[0] + current_offset.x, screen_pos[1] + current_offset.y)
            rect = rot_launcher.get_rect(center=launcher_pos)
            surface.blit(rot_launcher, rect)
        
        self.draw_health_and_marker(surface, offset, zoom)


class MissileCruiser(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = MissileCruiser_STATS[2]
        self.hp = self.max_hp
        self.speed = MissileCruiser_STATS[1]
        self.is_mechanical = True
        self.radius = 60 
        self.rect = pygame.Rect(pos.x-60, pos.y-60, 120, 120)
        self.attack_range = MissileCruiser_STATS[0]
        
        self.skill_cooldown = 0
        self.skill_max_cooldown = 900 
        
        self.is_aiming = False 
        self.is_charging = False 
        self.charge_timer = 0
        self.charge_duration = 180 
        self.target_spot = None 
        
        self.is_firing_salvo = False 
        self.salvo_count = 0         
        self.salvo_timer = 0         
        self.salvo_total = 15        
        self.salvo_interval = 10     
        self.is_naval = True        
        self.hull_image = self.generate_image()
        self.offset_distance=-75
        self.trail_size=1.5
    def toggle_mode(self):
        if self.skill_cooldown > 0:
            self.game.show_alert("SKILL NOT READY")
            return
            
        if self.is_charging or self.is_firing_salvo:
            self.game.show_alert("BUSY...")
            return

        self.is_aiming = not self.is_aiming
        if self.is_aiming:
            self.game.particles.add(FloatingText(self.pos, "AIMING MODE", CYAN))
            self.game.place_building_type = "cruiser_missile" 
        else:
            self.game.place_building_type = None

    def start_charge(self, pos):
        print(f"[Host] Start Charge at {pos}")
        if self.pos.distance_to(pos) > self.attack_range: 
            self.game.show_alert("OUT OF RANGE")
            return

        self.is_aiming = False
        self.is_charging = True
        self.charge_timer = self.charge_duration
        self.target_spot = vec(pos)
        
        if hasattr(self.game, 'net_events'):
            self.game.net_events.append({
                "type": "FX_TARGET_LOCK",
                "x": int(pos.x), "y": int(pos.y),
                "duration": self.charge_duration + self.salvo_total * self.salvo_interval
            })
        self.game.particles.add(TargetMarker(self.game, pos, self.charge_duration))
        
        self.game.particles.add(FloatingText(self.pos, "CHARGING...", YELLOW))
        for _ in range(10):
            offset = vec(random.randint(-40, 40), random.randint(-10, 10))
            p = Particle(self.game.particles, self.pos + offset, (200, 200, 200, 100), 0.5, 60, 5)
            p.vel = vec(0, -1) 

    def update(self):
        super().update()

        is_moving = (self.pos - getattr(self, 'prev_pos', self.pos)).length() > 0.1
        self.prev_pos = vec(self.pos)
        
        if self.is_charging and is_moving:
            self.is_charging = False
            self.charge_timer = 0
            self.target_spot = None
            self.game.particles.add(FloatingText(self.pos, "CANCELLED", RED))

            return

        if self.is_charging:
            self.charge_timer -= 1
            
            if self.charge_timer % 10 == 0:
                pass

            if self.charge_timer <= 0:
                self.is_charging = False
                self.start_salvo()
                self.skill_cooldown = self.skill_max_cooldown

        if self.is_firing_salvo:
            self.salvo_timer -= 1
            if self.salvo_timer <= 0:
                self.fire_one_missile()
                self.salvo_count -= 1
                self.salvo_timer = self.salvo_interval
                
                if self.salvo_count <= 0:
                    self.is_firing_salvo = False 

        if self.skill_cooldown > 0: self.skill_cooldown -= 1
        


    def start_salvo(self):
        self.is_firing_salvo = True
        self.salvo_count = self.salvo_total
        self.salvo_timer = 0

    def fire_one_missile(self):
        if not self.target_spot: return
        
        if random.random() < 0.7: 
            launch_x = random.randint(60, 120) 
        else:
            launch_x = random.randint(-80, -50)
        
        launch_y = random.randint(-15, 15)
        
        launch_offset = vec(launch_x, launch_y).rotate(self.angle) 
        spawn_pos = self.pos + launch_offset
        
        spread = vec(random.randint(-80, 80), random.randint(-80, 80))
        target = self.target_spot + spread
        
        missile = ShipMissile(self.game, target, self.team)
        
        missile.angle = random.randint(0, 180) 
        
        self.game.all_units.append(missile)
        
        for _ in range(5):
            Particle(self.game.particles, spawn_pos, (255, 200, 50), 2, 20, 8)
        for _ in range(8):
            p = Particle(self.game.particles, spawn_pos, (200, 200, 200, 150), 1, 60, 10)
            p.vel = vec(random.uniform(-1,1), random.uniform(-1,1))
        if hasattr(self.game, 'net_events'):
            self.game.net_events.append({
                "type": "EXPLOSION", 
                "x": int(spawn_pos.x), "y": int(spawn_pos.y), 
                "dt": "launch_smoke" 
            })
    def generate_image(self):
        w, h = 240, 80
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        
        C_HULL_DARK  = (60, 70, 80)
        C_HULL_LIGHT = (90, 100, 110)
        C_DECK       = (50, 55, 60)
        C_VLS        = (30, 30, 35) 
        C_DETAIL     = (130, 140, 150)
        C_RADAR      = (70, 80, 90)
        
        hull_pts = [
            (235, cy),      
            (200, cy-25),   
            (20, cy-25),    
            (5, cy-15),     
            (5, cy+15),     
            (20, cy+25),    
            (200, cy+25)    
        ]
        pygame.draw.polygon(s, C_HULL_DARK, hull_pts)
        
        deck_pts = [(p[0]-2, p[1]*0.9 + cy*0.1) for p in hull_pts]
        pygame.draw.polygon(s, C_HULL_LIGHT, deck_pts)

        vls_front_x = 160
        pygame.draw.rect(s, C_DECK, (vls_front_x-5, cy-18, 45, 36)) 
        for r in range(4): 
            for c in range(8): 
                px = vls_front_x + c*5
                py = cy - 14 + r*8
                pygame.draw.rect(s, C_VLS, (px, py, 3, 6))

        bridge_rect = pygame.Rect(110, cy-20, 40, 40)
        pygame.draw.rect(s, C_HULL_LIGHT, bridge_rect)
        pygame.draw.rect(s, (40,45,50), bridge_rect, 1) 

        pygame.draw.polygon(s, C_RADAR, [(130, cy-22), (145, cy-22), (140, cy-15), (135, cy-15)])
        pygame.draw.polygon(s, C_RADAR, [(130, cy+22), (145, cy+22), (140, cy+15), (135, cy+15)])
        
        pygame.draw.rect(s, (70, 75, 80), (60, cy-15, 40, 30))
        pygame.draw.circle(s, (20,20,20), (80, cy), 8)

        vls_back_x = 30
        pygame.draw.rect(s, C_DECK, (vls_back_x, cy-14, 25, 28))
        for r in range(3):
            for c in range(4):
                px = vls_back_x + 2 + c*5
                py = cy - 10 + r*8
                pygame.draw.rect(s, C_VLS, (px, py, 3, 6))

        gun_x = 210
        pygame.draw.circle(s, (50,55,60), (gun_x, cy), 8) 
        pygame.draw.rect(s, (30,30,30), (gun_x, cy-2, 20, 4)) 

        pygame.draw.circle(s, C_DETAIL, (120, cy), 4) 

        return s
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        
        scaled = scale_img(self.hull_image, zoom)
        rotated = cached_rotate(scaled, self.angle)
        rect = rotated.get_rect(center=screen_pos)
        
        surface.blit(rotated, rect)
        if self.is_charging:
            pct = 1.0 - (self.charge_timer / self.charge_duration)
        self.draw_health_and_marker(surface, offset, zoom)


        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled = scale_img(self.hull_image, zoom)
        rotated = cached_rotate(scaled, self.angle)
        rect = rotated.get_rect(center=screen_pos)
        
        surface.blit(rotated, rect)
        if self.is_charging:
            pct = 1.0 - (self.charge_timer / self.charge_duration)
        self.draw_health_and_marker(surface, offset, zoom)


class ArtilleryCruiser(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = MissileCruiser_STATS[2]
        self.hp = self.max_hp
        self.speed = MissileCruiser_STATS[1]
        self.radius = 50
        self.is_naval = True
        self.can_attack_air = False
        
        self.attack_range = MissileCruiser_STATS[0]
        self.damage = 120
        self.turret_angle = 0
        
        self.drone_timer = 0
        self.max_drones = 2 
        self.my_drones = [] 

        self.hull_image = self.gen_hull()
        self.turret_image = self.gen_turret()

    def update(self):
        super().update()
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        
        if not self.game.is_online or self.game.my_role == "HOST":
            self.my_drones = [d for d in self.my_drones if d.alive]
            
            if len(self.my_drones) < self.max_drones:
                self.drone_timer += 1
                if self.drone_timer > 600: 
                    self.spawn_drone()
                    self.drone_timer = 0
            
            target = self.find_nearest_enemy()
            if target:
                pass

    def spawn_drone(self):
        from units import ScoutDrone
        drone = ScoutDrone(self.game, self.pos, self.team)
        drone.parent_ship = self 
        self.game.all_units.append(drone)
        self.my_drones.append(drone)

    def draw(self, surface, offset, zoom):
        pass


class Battleship(Unit):
    def __init__(self, game, pos, team="neutral"):
        super().__init__(game, pos, team)
        
        self.max_hp = 4000  
        self.hp = self.max_hp
        self.speed = 0.8         
        self.turn_speed = 0.12    
        self.attack_range = 1400  
        self.damage = 50         
        self.radius = 80  
        self.breakarmorvalue=500
        self.is_mechanical = True
        self.is_naval = True
        self.trail_size=4
        self.offset_distance=-550
        self.spread=20
        self.rect = pygame.Rect(pos.x - 600, pos.y - 100, 1200, 200)

        if not hasattr(self, 'angle'): self.angle = 0
        self.turret_angle = self.angle 
        
        self.hull_image = self.generate_hull_image()
        self.turret_image = self.generate_turret_image()
        
        self.turret_offsets = [
            (vec(380, 0), 1.0),   
            (vec(260, 0), 1.1),   
            (vec(-350, 0), 1.0)   
        ]
        
        self.barrel_spacing = 10 

    def generate_hull_image(self):
        w, h = 1200, 220
        cx, cy = w // 2, h // 2
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        
        C_HULL_DARK   = (45, 50, 60)     
        C_DECK_TEAK   = (130, 110, 90)   
        C_SUPER_LIGHT = (140, 145, 150)  
        C_SUPER_DARK  = (100, 105, 110)  
        C_BLACK       = (20, 20, 20)     
        C_TEAM        = TEAM_COLORS.get(self.team, (200, 200, 200))
        
        hull_pts = [
            (1180, cy),           
            (1050, cy - 40),      
            (800, cy - 85),       
            (300, cy - 85),       
            (100, cy - 60),       
            (20, cy - 30),        
            (20, cy + 30),        
            (100, cy + 60),
            (300, cy + 85),
            (800, cy + 85),
            (1050, cy + 40)
        ]
        pygame.draw.polygon(surf, C_HULL_DARK, hull_pts)
        
        deck_pts = [(p[0]-4 if p[0]<cx else p[0]-8, p[1]*0.92 + cy*0.08) for p in hull_pts]
        pygame.draw.polygon(surf, C_DECK_TEAK, deck_pts)
        
        for i in range(100, 1100, 15):
            pygame.draw.line(surf, (110, 90, 70), (i, cy-70), (i, cy+70), 1)

        pygame.draw.rect(surf, C_SUPER_DARK, (350, cy - 65, 450, 130), border_radius=15)
        pygame.draw.rect(surf, C_SUPER_LIGHT, (400, cy - 45, 350, 90), border_radius=10)
        
        pygame.draw.rect(surf, (160, 165, 170), (620, cy - 30, 60, 60))
        pygame.draw.rect(surf, (10, 10, 20), (660, cy - 20, 10, 40)) 
        
        pygame.draw.ellipse(surf, C_SUPER_DARK, (540, cy - 25, 30, 50))
        pygame.draw.ellipse(surf, C_BLACK, (550, cy - 18, 10, 36))
        pygame.draw.ellipse(surf, C_SUPER_DARK, (480, cy - 25, 30, 50))
        pygame.draw.ellipse(surf, C_BLACK, (490, cy - 18, 10, 36))
        
        pygame.draw.rect(surf, C_SUPER_DARK, (420, cy - 10, 20, 20))
        pygame.draw.line(surf, (50,50,50), (430, cy), (430, cy-60), 3) 

        for i in range(4):
            x = 450 + i * 50
            pygame.draw.circle(surf, C_SUPER_LIGHT, (x, cy - 70), 8)
            pygame.draw.line(surf, (80,80,80), (x, cy-70), (x, cy-85), 2)
            pygame.draw.circle(surf, C_SUPER_LIGHT, (x, cy + 70), 8)
            pygame.draw.line(surf, (80,80,80), (x, cy+70), (x, cy+85), 2)

        pygame.draw.rect(surf, (80, 80, 80), (100, cy - 25, 100, 50))
        pygame.draw.circle(surf, (200, 200, 200), (150, cy), 20, 2) 

        pygame.draw.line(surf, (30,30,30), (1150, cy), (1050, cy-15), 2)
        pygame.draw.line(surf, (30,30,30), (1150, cy), (1050, cy+15), 2)
        pygame.draw.line(surf, C_HULL_DARK, (950, cy-40), (950, cy+40), 2) 

        pygame.draw.rect(surf, C_TEAM, (40, cy - 20, 15, 40))

        return surf

    def generate_turret_image(self):
        surf = pygame.Surface((140, 70), pygame.SRCALPHA)
        cx, cy = 40, 35 
        
        C_BARREL  = (70, 75, 80)
        C_HOUSING = (130, 135, 140)
        C_BLAST   = BLUE
        
        b_len = 95
        b_w = 7
        offsets = [-10, 0, 10] 
        
        for y_off in offsets:
            pygame.draw.rect(surf, C_BARREL, (cx + 5, cy + y_off - b_w//2, b_len, b_w))
            pygame.draw.rect(surf, (10,10,10), (cx + 5 + b_len, cy + y_off - b_w//2 + 1, 2, b_w-2))

        pts = [
            (cx - 30, cy - 28), 
            (cx + 15, cy - 28), 
            (cx + 25, cy - 12), 
            (cx + 25, cy + 12), 
            (cx + 15, cy + 28), 
            (cx - 30, cy + 28)  
        ]
        pygame.draw.polygon(surf, C_HOUSING, pts)
        pygame.draw.polygon(surf, (80,85,90), pts, 2) 

        pygame.draw.rect(surf, (100, 100, 100), (cx - 20, cy - 32, 12, 4))
        pygame.draw.rect(surf, (100, 100, 100), (cx - 20, cy + 28, 12, 4))
        
        pygame.draw.rect(surf, (90, 95, 100), (cx - 15, cy - 10, 15, 20))

        return surf

    def update(self):
        # 特殊单位缓慢回血（坦克式周期回血）：每 SPECIAL_REGEN_INTERVAL 帧恢复 BATTLESHIP_REGEN HP
        self.regen_timer = getattr(self, 'regen_timer', 0) + 1
        if self.regen_timer >= SPECIAL_REGEN_INTERVAL:
            self.regen_timer = 0
            if self.hp < self.max_hp:
                self.hp = min(self.max_hp, int(self.hp) + BATTLESHIP_REGEN)

        self.can_attack_air = False
        if self.attack_cooldown > 0: self.attack_cooldown -= 1

        if not self.target_entity or not self.target_entity.alive:
            if self.team != "neutral":
                candidates = [u for u in self.game.all_units if u.team != self.team and u.alive and not u.is_air]
                candidates += [b for b in self.game.all_buildings if b.team != self.team and b.alive]

                if candidates:
                    nearest = min(candidates, key=lambda x: self.pos.distance_squared_to(x.pos))
                    if self.pos.distance_to(nearest.pos) <= 300:
                        self.target_entity = nearest

        is_stationary_attack = False
        if self.target_entity and self.target_entity.alive:
            dist = self.pos.distance_to(self.target_entity.pos)
            if dist <= self.attack_range:
                is_stationary_attack = True
                self.target_pos = None
                self.path_cache = []

        if not is_stationary_attack:
            if self.target_entity and self.target_entity.alive:
                dist = self.pos.distance_to(self.target_entity.pos)
                if dist > self.attack_range * 0.8:
                    self.target_pos = self.target_entity.pos
                else:
                    self.target_pos = None
            super().update()
        else:
            # 横船机动：射程内停船后，船身与目标方向保持垂直（侧舷对敌），
            # 不再把船头对准目标；炮塔独立瞄准，开火不受船体转向影响
            diff = self.target_entity.pos - self.pos
            target_angle = math.degrees(math.atan2(-diff.y, diff.x))
            # 直接比较 +90/-90 两个候选舷的转向距离，取更近者（单调收敛，
            # 避免目标恰在船头方位时按 d_to_t 符号选舷导致左右振荡）
            c1 = (target_angle + 90 - self.angle + 180) % 360 - 180
            c2 = (target_angle - 90 - self.angle + 180) % 360 - 180
            d = c1 if abs(c1) <= abs(c2) else c2
            if abs(d) > 0.5:
                step = min(self.turn_speed * 3, abs(d))  # 原地转舵比航行转向快
                self.angle += step if d > 0 else -step

            if not hasattr(self, 'prev_pos'):
                self.prev_pos = vec(self.pos)
            is_moving = (self.pos - self.prev_pos).length() > 0.1
            self.prev_pos = vec(self.pos)

            if is_moving and self.game.frame_count % 15 == 0:
                offsets = [vec(-25, 0), vec(35, 0)]
                for off in offsets:
                    rotated_off = off.rotate(-self.angle)
                    smoke_pos = self.pos + rotated_off
                    Particle(self.game.particles, smoke_pos, (200, 200, 200, 150), 0.5, 60, random.randint(15, 28))

        current_target = self.target_entity
        if current_target and current_target.alive:
            if self.pos.distance_to(current_target.pos) <= self.attack_range:
                diff = current_target.pos - self.pos
                target_turret_angle = math.degrees(math.atan2(-diff.y, diff.x))

                t_diff = (target_turret_angle - self.turret_angle + 180) % 360 - 180
                turret_turn_rate = 0.5

                if abs(t_diff) < turret_turn_rate:
                    self.turret_angle = target_turret_angle
                else:
                    self.turret_angle += turret_turn_rate if t_diff > 0 else -turret_turn_rate

                if abs(t_diff) < 5 and self.attack_cooldown <= 0:
                    self.perform_attack(current_target)


    def perform_attack(self, target):
        if self.attack_cooldown > 0: return
        for turret_offset_local, _ in self.turret_offsets:
            
            turret_center_world = self.pos + turret_offset_local.rotate(-self.angle)
            
            offsets_y = [-30, 0, 30]
            
            for off_y in offsets_y:
                muzzle_local = vec(105, off_y).rotate(-self.turret_angle)
                spawn_pos = turret_center_world + muzzle_local
                
                p = Projectile(self.game, spawn_pos, target, self.team, self.damage,
                            d_type="heavy_shell",
                            is_aoe=True,
                            aoe_radius=100,breakshellvalue=self.breakarmorvalue,
                            png_key="shell_battleship")
                p.speed = 35 
                p.is_aoe = True
                p.aoe_radius = 80
                
                spread = vec(random.uniform(-10, 10), random.uniform(-10, 10))
                self.game.projectiles.append(p)
            
        self.attack_cooldown = 440 

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        
        if self.speed > 0.05:
            rad = math.radians(self.angle)
            rear_dist = 500 * zoom
            rear_x = screen_pos.x - math.cos(rad) * rear_dist
            rear_y = screen_pos.y + math.sin(rad) * rear_dist

            wake_len = 300 * zoom
            wake_width = 80 * zoom

            p_rear = vec(rear_x, rear_y)
            p_l = p_rear + vec(-wake_len, -wake_width).rotate(-self.angle)
            p_r = p_rear + vec(-wake_len, wake_width).rotate(-self.angle)

            # 浪花（舰艏三角航迹）颜色跟随所处水域颜色；alpha 固定 1 不透明
            from maps.map_data import water_color_at
            wake_color = water_color_at(getattr(self.game, 'lakes', []), int(self.pos.x), int(self.pos.y)) or (200, 200, 255)
            pygame.draw.line(surface, wake_color, (rear_x, rear_y), p_l, int(10*zoom))
            pygame.draw.line(surface, wake_color, (rear_x, rear_y), p_r, int(10*zoom))

        # 大船体用 1° 量子 + rotozoom 平滑旋转：2° 台阶在大图上视觉卡顿明显
        scaled_hull = scale_img(self.hull_image, zoom)
        rot_hull = cached_rotate(scaled_hull, self.angle, quantum=1, smooth=True)
        hull_rect = rot_hull.get_rect(center=screen_pos)
        surface.blit(rot_hull, hull_rect)
        
        scaled_turret = scale_img(self.turret_image, zoom)
        rot_turret = cached_rotate(scaled_turret, self.turret_angle)
        
        for offset_vec, _ in self.turret_offsets:
            rotated_offset = offset_vec.rotate(-self.angle)
            turret_world_pos = self.pos + rotated_offset
            turret_screen_pos = to_screen(turret_world_pos, offset, zoom)
            
            t_rect = rot_turret.get_rect(center=turret_screen_pos)
            surface.blit(rot_turret, t_rect)

        self.draw_health_and_marker(surface, offset, zoom)

