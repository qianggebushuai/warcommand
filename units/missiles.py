import pygame
import random
import math
from core.settings import *
from core.base_classes import *
from .base import *

class CruiseMissile(Unit):
    def __init__(self, game, target_pos, team):
        spawn_pos = vec(target_pos) + vec(-1000, -1000)
        super().__init__(game, spawn_pos, team)
        self.target_dest = vec(target_pos)
        self.speed = 18 
        self.hp = 100
        self.max_hp = 100
        self.is_mechanical = True
        self.is_air = True
        self.radius = 25
        self.original_image = pygame.Surface((80, 40), pygame.SRCALPHA)       
        C_BODY       = (200, 200, 210)  
        C_BODY_DARK  = (150, 150, 160)  
        C_NOSE       = (80, 80, 80)    
        C_WING       = (120, 120, 130)  
        C_INTAKE     = (40, 40, 40)     
        C_STRIPE     = (255, 50, 50)    
        

        tail_x = 10

        pygame.draw.polygon(self.original_image, C_WING, [(tail_x, 20), (tail_x-8, 5), (tail_x+2, 5)])
        pygame.draw.polygon(self.original_image, C_WING, [(tail_x, 20), (tail_x-8, 35), (tail_x+2, 35)])
        
        body_rect = pygame.Rect(10, 15, 60, 10)
        pygame.draw.rect(self.original_image, C_BODY, body_rect)
        

        pygame.draw.rect(self.original_image, C_BODY_DARK, (10, 22, 60, 3))
        

        pygame.draw.ellipse(self.original_image, C_NOSE, (65, 15, 12, 10))
        
        wing_x = 40
        pygame.draw.polygon(self.original_image, C_WING, [(wing_x, 15), (wing_x-10, 2), (wing_x+5, 2), (wing_x+10, 15)])
        pygame.draw.polygon(self.original_image, C_WING, [(wing_x, 25), (wing_x-10, 38), (wing_x+5, 38), (wing_x+10, 25)])
        

        pygame.draw.rect(self.original_image, C_INTAKE, (25, 23, 10, 6))
        
        pygame.draw.rect(self.original_image, C_STRIPE, (58, 15, 3, 10))

        pygame.draw.line(self.original_image, (100, 100, 100), (35, 15), (35, 25), 1)
        pygame.draw.line(self.original_image, (100, 100, 100), (55, 15), (55, 25), 1)

    def update(self):
        self.game.particles.add(Particle(self.game.particles, self.pos, ORANGE, 1, 20, 4))
        self.game.particles.add(Particle(self.game.particles, self.pos, (100, 100, 100), 1, 40, 6))
        if not self.game.is_online or self.game.my_role == "HOST":
            vec_to_target = self.target_dest - self.pos
            dist = vec_to_target.length()
            if dist < 10:
                self.explode()
                return
            if dist < 300: self.speed = max(4, self.speed * 0.95) 
            direction = vec_to_target.normalize()
            self.pos += direction * self.speed
            self.angle = math.degrees(math.atan2(-direction.y, direction.x))
            self.update_rect()


    def explode(self):
        self.alive = False

        
        if not self.game.is_online or self.game.my_role == "HOST":
            if hasattr(self.game, 'net_events'):
                self.game.net_events.append({
                    "type": "EXPLOSION", 
                    "x": int(self.pos.x), 
                    "y": int(self.pos.y),
                    "dt": "missile" 
                })

        for _ in range(30): Particle(self.game.particles, self.pos, ORANGE, random.uniform(2, 6), 50, 8)
        for _ in range(20): Particle(self.game.particles, self.pos, RED, random.uniform(1, 4), 60, 10)
        for _ in range(10): Particle(self.game.particles, self.pos, WHITE, random.uniform(0.5, 2), 40, 15)
        targets = self.game.all_units + self.game.all_buildings
        for t in targets:
            if t.alive:
                if self.team == "neutral" or t.team != self.team:
                    if self.pos.distance_to(t.pos) <= 120:
                        t.take_damage(DMG_MISSILE, "heavy",breakshellvalue=0)
    def draw(self, surface, offset, zoom):
        scaled_img = scale_img(self.original_image, zoom)
        rotated_image = pygame.transform.rotate(scaled_img, self.angle)
        
        screen_pos = to_screen(self.pos, offset, zoom)
        rect = rotated_image.get_rect(center=screen_pos)
        
        shadow_offset = scale(15, zoom) 
        s_w = rect.width * 0.6
        s_h = rect.height * 0.6
        s_surf = pygame.Surface((s_w, s_h), pygame.SRCALPHA)
        pygame.draw.ellipse(s_surf, (0, 0, 0, 60), (0,0,s_w,s_h))
        surface.blit(s_surf, (screen_pos[0] - s_w//2 + shadow_offset, screen_pos[1] - s_h//2 + shadow_offset))
        
        surface.blit(rotated_image, rect.topleft)
        
        rad = math.radians(self.angle)
        tail_dist = scale(30, zoom)
        tail_x = screen_pos[0] - math.cos(rad) * tail_dist
        tail_y = screen_pos[1] + math.sin(rad) * tail_dist 
        for i in range(3):
            flame_len = random.randint(10, 25)
            flame_w = random.randint(3, 8)
            fx = tail_x - math.cos(rad) * scale(flame_len, zoom)
            fy = tail_y + math.sin(rad) * scale(flame_len, zoom)
            
            color = random.choice([(255, 200, 50), (255, 100, 0), (200, 200, 200)]) 
            pygame.draw.circle(surface, color, (int(fx), int(fy)), int(scale(flame_w, zoom)))


class ShipMissile(Unit):
    def __init__(self, game, target_pos, team, spawn_pos=None):
        if spawn_pos is None:
            spawn_pos = vec(target_pos) + vec(-1000, -1000)
            
        super().__init__(game, spawn_pos, team)
        
        self.target_dest = vec(target_pos)
        self.speed = 22 
        self.hp = 40    
        self.max_hp = 40
        self.is_mechanical = True
        self.is_air = True
        self.radius = 15 
        self.rect = pygame.Rect(10, 15, 30, 30)
        
        self.damage = 150 
        self.blast_range = 80
        
        self.wobble_timer = 0
        
        self.original_image = self.generate_image()

    def generate_image(self):
        w, h = 50, 24 
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w//2, h//2
        
        C_BODY   = (220, 225, 230) 
        C_NOSE   = (50, 50, 55)    
        C_WING   = (160, 165, 170) 
        C_STRIPE = (200, 50, 50)   
        C_INTAKE = (30, 30, 30)    
        

        body_rect = pygame.Rect(5, 7, 40, 10)
        pygame.draw.rect(s, C_BODY, body_rect, border_radius=2)
        
        pygame.draw.circle(s, C_NOSE, (45, 12), 5) 
        
        pygame.draw.polygon(s, C_WING, [(30, 7), (20, 0), (35, 0), (38, 7)]) 
        pygame.draw.polygon(s, C_WING, [(30, 17), (20, 24), (35, 24), (38, 17)]) 
        
        pygame.draw.polygon(s, C_WING, [(10, 7), (5, 2), (12, 2), (12, 7)]) 
        pygame.draw.polygon(s, C_WING, [(10, 17), (5, 22), (12, 22), (12, 17)]) 
        
        pygame.draw.rect(s, C_INTAKE, (25, 15, 8, 4))
        
        pygame.draw.rect(s, C_STRIPE, (38, 7, 2, 10))
        pygame.draw.line(s, (150,150,150), (20, 7), (20, 17), 1)

        return s

    def update(self):
        vec_to_target = self.target_dest - self.pos
        dist = vec_to_target.length()
        
        if dist < 10:
            self.explode()
            return
            
        base_dir = vec_to_target.normalize()
        
        if dist < 300:
            self.wobble_timer += 0.5
            perp_vec = vec(-base_dir.y, base_dir.x)
            wobble = perp_vec * math.sin(self.wobble_timer) * 0.5 
            final_dir = (base_dir + wobble).normalize()
        else:
            final_dir = base_dir
            
        self.pos += final_dir * self.speed
        
        self.angle = math.degrees(math.atan2(-final_dir.y, final_dir.x))
        
        self.update_rect()
        
        if self.game.frame_count % 2 == 0:
            self.game.particles.add(Particle(self.game.particles, self.pos, (200, 200, 200), 0.5, 15, 3))

    def explode(self):
        self.alive = False
        
        if not self.game.is_online or self.game.my_role == "HOST":
            if hasattr(self.game, 'net_events'):
                self.game.net_events.append({
                    "type": "EXPLOSION", 
                    "x": int(self.pos.x), 
                    "y": int(self.pos.y),
                    "dt": "rocket" 
                })

        for _ in range(15): Particle(self.game.particles, self.pos, ORANGE, random.uniform(2, 5), 30, 6)
        for _ in range(10): Particle(self.game.particles, self.pos, (50, 50, 50), random.uniform(1, 3), 40, 8)
        
        targets = self.game.all_units + self.game.all_buildings
        for t in targets:
            if t.alive:
                if self.team == "neutral" or t.team != self.team:
                    if self.pos.distance_to(t.pos) <= self.blast_range:
                        t.take_damage(self.damage, "heavy", breakshellvalue=5)

    def draw(self, surface, offset, zoom):
        scaled_img = scale_img(self.original_image, zoom)
        rotated_image = pygame.transform.rotate(scaled_img, self.angle)
        
        screen_pos = to_screen(self.pos, offset, zoom)
        rect = rotated_image.get_rect(center=screen_pos)
        
        shadow_offset = scale(8, zoom) 
        s_w = rect.width * 0.7
        s_h = rect.height * 0.7
        s_surf = pygame.Surface((s_w, s_h), pygame.SRCALPHA)
        pygame.draw.ellipse(s_surf, (0, 0, 0, 50), (0,0,s_w,s_h))
        surface.blit(s_surf, (screen_pos[0] - s_w//2 + shadow_offset, screen_pos[1] - s_h//2 + shadow_offset))
        
        surface.blit(rotated_image, rect.topleft)
        
        rad = math.radians(self.angle)
        tail_dist = scale(18, zoom) 
        back_x = -math.cos(rad)
        back_y = math.sin(rad) 
        
        tail_screen_x = screen_pos[0] + back_x * tail_dist
        tail_screen_y = screen_pos[1] + back_y * tail_dist
        
        flame_len = random.randint(8, 15)
        end_x = tail_screen_x + back_x * scale(flame_len, zoom)
        end_y = tail_screen_y + back_y * scale(flame_len, zoom)
        
        pygame.draw.line(surface, (255, 200, 50), (tail_screen_x, tail_screen_y), (end_x, end_y), int(scale(4, zoom)))
        pygame.draw.circle(surface, (255, 255, 200), (int(tail_screen_x), int(tail_screen_y)), int(scale(3, zoom)))


class MegaRocket(Unit):
    def __init__(self, game, pos, team, target_pos=None):
        super().__init__(game, pos, team)

        self.target_dest = vec(target_pos)
        self.speed = 3.5 
        self.radius = 20
        self.max_hp = 1000 
        self.hp = 1000
        self.armor=5
        self.is_air = True
        
        self.angle=0
        self.image = self.generate_missile_image()

        pygame.draw.circle(self.image, (255, 50, 50), (20, 20), 15)

    def update(self):
        vec_to_target = self.target_dest - self.pos
        dist = vec_to_target.length()
        
        if dist < 10:
            self.explode()
            return

        if dist > 0:
            direction = vec_to_target.normalize()
            self.pos += direction * self.speed
            
            self.angle = math.degrees(math.atan2(-direction.y, direction.x))
            
        for u in self.game.all_units:
            if u != self and u.team != self.team and self.pos.distance_to(u.pos) < 40:
                u.take_damage(500, "crush")

    def explode(self):
        self.alive = False
        targets = self.game.all_units + self.game.all_buildings
        for t in targets:
            if t.pos.distance_to(self.pos) < 300: 
                t.take_damage(2000, "behemoth_bomb") 
        for i in range(36):
            angle = i * 10
            speed = 6
            vel = vec(speed, 0).rotate(angle)
            Particle(self.game.particles, self.pos, WHITE, speed, 40, 10)
        for _ in range(40): Particle(self.game.particles, self.pos, ORANGE, random.uniform(1, 4), 60, 15)
        for _ in range(20): Particle(self.game.particles, self.pos, (50, 50, 50), random.uniform(2, 5), 80, 20)        
        if hasattr(self.game, 'net_events'):
            self.game.net_events.append({
                "type": "EXPLOSION", 
                "x": int(self.pos.x), "y": int(self.pos.y),
                "dt": "behemoth_bomb"
            })
    def generate_missile_image(self):
        w, h = 120, 40
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        
        C_BODY = (220, 220, 230)
        C_NOSE = (200, 50, 50)
        C_FIN  = (150, 150, 160)
        
        
        body_rect = pygame.Rect(10, 10, 80, 20)
        pygame.draw.rect(s, C_BODY, body_rect, border_radius=5)
        
        pygame.draw.polygon(s, C_NOSE, [(90, 10), (115, 20), (90, 30)])
        
        pygame.draw.polygon(s, C_FIN, [(20, 10), (5, 0), (30, 0), (35, 10)])
        pygame.draw.polygon(s, C_FIN, [(20, 30), (5, 40), (30, 40), (35, 30)])
        
        pygame.draw.circle(s, (200, 200, 0), (70, 20), 5)
        
        return s    
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled = scale_img(self.image, zoom)

        rotated = pygame.transform.rotate(scaled, self.angle) 
        
        rect = rotated.get_rect(center=screen_pos)
        surface.blit(rotated, rect)
        
        if self.speed > 0:
            rad = math.radians(self.angle)
            back_vec = vec(-math.cos(rad), math.sin(rad)) 
            
            tail_dist = 50 * zoom
            tail_pos = screen_pos + back_vec * tail_dist
            
            for i in range(3):
                r = int(random.randint(10, 20) * zoom)
                fx = tail_pos.x + back_vec.x * r * i
                fy = tail_pos.y + back_vec.y * r * i
                
                color = random.choice([(255, 100, 0), (255, 200, 50), (200, 200, 200)])
                pygame.draw.circle(surface, color, (int(fx), int(fy)), r)

