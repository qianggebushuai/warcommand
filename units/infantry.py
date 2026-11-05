import pygame
import random
import math
from core.settings import *
from core.base_classes import *
from .base import *

class Rifleman(Unit):
    _sprite_cache = {}
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = RIFLEMAN_STATS[2]
        self.hp = self.max_hp
        self.speed = RIFLEMAN_STATS[1]
        self.attack_range = RIFLEMAN_STATS[0]
        self.radius = 12
        self.turn_speed = 20
        self.rect = pygame.Rect(pos.x - 12, pos.y - 12, 24, 24)
        self.can_attack_air = False 
        self.image = self.get_sprite()

    def get_sprite(self):
        if "rifleman" not in Rifleman._sprite_cache:
            path = resource_path("sprites/infantory/unit_rifleman.png")
            img = downscale_texture(pygame.image.load(path).convert_alpha())
            Rifleman._sprite_cache["rifleman"] = img        
        return Rifleman._sprite_cache["rifleman"]
    def fire_projectile(self, target):
        dmg = DMG_RIFLE * self.tech_bonus_dmg
        self.game.projectiles.append(Projectile(self.game, self.pos, target, self.team, dmg, "rifle", breakshellvalue=self.breakarmorvalue))
    def set_target(self, entity):
        if getattr(entity, 'can_garrison', False) and entity.team == "neutral": 
            self.target_entity = entity
            self.ai_mode = "MOVE" 
            return

        super().set_target(entity) 
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        if hasattr(self, 'deploy_timer') and self.deploy_timer > 0:
            total_time = 120 
            progress = (total_time - self.deploy_timer) / total_time 
            
            scale_factor = 0.5 + 0.5 * progress 
            
            height_offset = (1.0 - progress) * 100 
            base_w = 30
            base_h = 20
            para_w = scale(base_w * scale_factor, zoom)
            para_h = scale(base_h * scale_factor, zoom)
            para_x = screen_pos[0] - para_w // 2
            para_y = screen_pos[1] - scale(30 + height_offset, zoom) 
            pygame.draw.arc(surface, WHITE, (para_x, para_y, para_w, para_h), 0, 3.14, 2)
            pygame.draw.line(surface, WHITE, (para_x, para_y + para_h//2), screen_pos, 1)
            pygame.draw.line(surface, WHITE, (para_x + para_w, para_y + para_h//2), screen_pos, 1)
        scaled_img = scale_img(self.image, zoom)
        
        rotated_img = cached_rotate(scaled_img, self.angle)   
        rect = rotated_img.get_rect(center=screen_pos)        
        surface.blit(rotated_img, rect)
        team_color = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        pygame.draw.circle(surface, team_color, screen_pos, scale(4, zoom))

        self.draw_health_and_marker(surface, offset, zoom)


        screen_pos = to_screen(self.pos, offset, zoom)
        if hasattr(self, 'deploy_timer') and self.deploy_timer > 0:
            total_time = 120 
            progress = (total_time - self.deploy_timer) / total_time 
            
            scale_factor = 0.5 + 0.5 * progress 
            
            height_offset = (1.0 - progress) * 100 
            base_w = 30
            base_h = 20
            para_w = scale(base_w * scale_factor, zoom)
            para_h = scale(base_h * scale_factor, zoom)
            para_x = screen_pos[0] - para_w // 2
            para_y = screen_pos[1] - scale(30 + height_offset, zoom) 
            pygame.draw.arc(surface, WHITE, (para_x, para_y, para_w, para_h), 0, 3.14, 2)
            pygame.draw.line(surface, WHITE, (para_x, para_y + para_h//2), screen_pos, 1)
            pygame.draw.line(surface, WHITE, (para_x + para_w, para_y + para_h//2), screen_pos, 1)
        scaled_img = scale_img(self.image, zoom)
        
        rotated_img = cached_rotate(scaled_img, self.angle)   
        rect = rotated_img.get_rect(center=screen_pos)        
        surface.blit(rotated_img, rect)
        team_color = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        pygame.draw.circle(surface, team_color, screen_pos, scale(4, zoom))

        self.draw_health_and_marker(surface, offset, zoom)


class RocketTrooper(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = ROCKET_STATS[2]
        self.hp = self.max_hp

        self.speed = ROCKET_STATS[1]
        self.attack_range = ROCKET_STATS[0]
        self.radius = 13
        self.turn_speed = 20
        self.rect = pygame.Rect(pos.x - 13, pos.y - 13, 26, 26)
        self.can_attack_air = True 
        self.attack_cooldown = 90  
    def fire_projectile(self, target):
        vec_to_target = target.pos - self.pos
        scatter_angle = random.uniform(-15, 15)
        scattered_vec = vec_to_target.rotate(scatter_angle)
        new_dest = self.pos + scattered_vec
        dmg = DMG_ROCKET * self.tech_bonus_dmg
        rocket = Projectile(self.game, self.pos, None, self.team, dmg, "rocket", is_aoe=True, aoe_radius=50, breakshellvalue=self.breakarmorvalue, png_key="rocket_rpg")
        rocket.target_dest = new_dest 
        rocket.vel = scattered_vec.normalize() * ROCKET_SPEED
        self.game.projectiles.append(rocket)
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        if hasattr(self, 'deploy_timer') and self.deploy_timer > 0:
            total_time = 120 
            progress = (total_time - self.deploy_timer) / total_time 
            
            scale_factor = 0.5 + 0.5 * progress 
            
            height_offset = (1.0 - progress) * 100 

            base_w = 30
            base_h = 20
            
            para_w = scale(base_w * scale_factor, zoom)
            para_h = scale(base_h * scale_factor, zoom)
            
            para_x = screen_pos[0] - para_w // 2
            para_y = screen_pos[1] - scale(30 + height_offset, zoom) 

            pygame.draw.arc(surface, WHITE, (para_x, para_y, para_w, para_h), 0, 3.14, 2)
            pygame.draw.line(surface, WHITE, (para_x, para_y + para_h//2), screen_pos, 1)
            pygame.draw.line(surface, WHITE, (para_x + para_w, para_y + para_h//2), screen_pos, 1)
        s_rad = scale(12, zoom)
        uniform_color = (180, 160, 120) 
        pygame.draw.circle(surface, uniform_color, screen_pos, s_rad)
        accent =TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        pygame.draw.circle(surface, accent, screen_pos, scale(5, zoom))
        pygame.draw.circle(surface, (60, 50, 80), screen_pos, scale(9, zoom))
        side_offset = vec(0, 5).rotate(-self.angle)
        start_tube = self.pos - vec(5, 0).rotate(-self.angle) + side_offset
        end_tube = self.pos + vec(12, 0).rotate(-self.angle) + side_offset
        st_screen = to_screen(start_tube, offset, zoom)
        et_screen = to_screen(end_tube, offset, zoom)
        pygame.draw.line(surface, (20, 20, 20), st_screen, et_screen, scale(6, zoom))
        self.draw_health_and_marker(surface, offset, zoom)


        screen_pos = to_screen(self.pos, offset, zoom)
        if hasattr(self, 'deploy_timer') and self.deploy_timer > 0:
            total_time = 120 
            progress = (total_time - self.deploy_timer) / total_time 
            
            scale_factor = 0.5 + 0.5 * progress 
            
            height_offset = (1.0 - progress) * 100 

            base_w = 30
            base_h = 20
            
            para_w = scale(base_w * scale_factor, zoom)
            para_h = scale(base_h * scale_factor, zoom)
            
            para_x = screen_pos[0] - para_w // 2
            para_y = screen_pos[1] - scale(30 + height_offset, zoom) 

            pygame.draw.arc(surface, WHITE, (para_x, para_y, para_w, para_h), 0, 3.14, 2)
            pygame.draw.line(surface, WHITE, (para_x, para_y + para_h//2), screen_pos, 1)
            pygame.draw.line(surface, WHITE, (para_x + para_w, para_y + para_h//2), screen_pos, 1)
        s_rad = scale(12, zoom)
        uniform_color = (180, 160, 120) 
        pygame.draw.circle(surface, uniform_color, screen_pos, s_rad)
        accent =TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        pygame.draw.circle(surface, accent, screen_pos, scale(5, zoom))
        pygame.draw.circle(surface, (60, 50, 80), screen_pos, scale(9, zoom))
        side_offset = vec(0, 5).rotate(-self.angle)
        start_tube = self.pos - vec(5, 0).rotate(-self.angle) + side_offset
        end_tube = self.pos + vec(12, 0).rotate(-self.angle) + side_offset
        st_screen = to_screen(start_tube, offset, zoom)
        et_screen = to_screen(end_tube, offset, zoom)
        pygame.draw.line(surface, (20, 20, 20), st_screen, et_screen, scale(6, zoom))
        self.draw_health_and_marker(surface, offset, zoom)


class Shotgunner(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)

        self.max_hp = SHOTGUNNER_STATS[2]
        self.hp = self.max_hp
        
        self.speed = SHOTGUNNER_STATS[1]
        self.attack_range = SHOTGUNNER_STATS[0]
        self.damage = DMG_SHOTGUN
        self.shield=100
        self.breakarmorvalue=20

        self.radius = 12
        self.turn_speed = 20
        self.rect = pygame.Rect(pos.x - 12, pos.y - 12, 24, 24)
        
        self.can_attack_air = False

    def perform_attack(self, target):

        if self.attack_cooldown > 0: return

        base_vec = target.pos - self.pos
        
        pellet_count = 20
        spread_angle = 30 
        
        for _ in range(pellet_count):

            angle_offset = random.uniform(-spread_angle/2, spread_angle/2)
            
            fire_vec = base_vec.rotate(angle_offset)
            

            speed_mult = random.uniform(0.8, 1.2)
            
            dmg = self.damage * self.tech_bonus_dmg
            p = Projectile(self.game, self.pos, None, self.team, dmg, "rifle", breakshellvalue=self.breakarmorvalue)
            
            p.vel = fire_vec.normalize() * BULLET_SPEED * speed_mult
            
            p.life_time = 20 
            
            self.game.projectiles.append(p)

        self.attack_cooldown = 90

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        

        s_rad = scale(11, zoom)
        

        pygame.draw.circle(surface, (150, 140, 130), screen_pos, s_rad)
        

        accent = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        pygame.draw.circle(surface, accent, screen_pos, scale(6, zoom))
        
        gun_end = (screen_pos[0] + s_rad * 1.2 * math.cos(math.radians(-self.angle)),
                   screen_pos[1] + s_rad * 1.2 * math.sin(math.radians(-self.angle)))
        pygame.draw.line(surface, (20, 20, 20), screen_pos, gun_end, scale(5, zoom)) 
        
        self.draw_health_and_marker(surface, offset, zoom)


        screen_pos = to_screen(self.pos, offset, zoom)
        

        s_rad = scale(11, zoom)
        

        pygame.draw.circle(surface, (150, 140, 130), screen_pos, s_rad)
        

        accent = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        pygame.draw.circle(surface, accent, screen_pos, scale(6, zoom))
        
        gun_end = (screen_pos[0] + s_rad * 1.2 * math.cos(math.radians(-self.angle)),
                   screen_pos[1] + s_rad * 1.2 * math.sin(math.radians(-self.angle)))
        pygame.draw.line(surface, (20, 20, 20), screen_pos, gun_end, scale(5, zoom)) 
        
        self.draw_health_and_marker(surface, offset, zoom)


class Sniper(Unit):
    def __init__(self, game, pos, team):
        self.max_hp = SNIPER_STATS[2]
        self.hp = self.max_hp
        super().__init__(game, pos, team)
        
        self.speed = SNIPER_STATS[1]
        self.attack_range = SNIPER_STATS[0]
        self.damage = DMG_SNIPER
        self.view_radius = 500
        self.attack_speed = 3.0 
        self.radius = 10
        self.rect = pygame.Rect(pos.x - 10, pos.y - 10, 20, 20)

        self.original_image = pygame.Surface((30, 20), pygame.SRCALPHA)
        
        cloth_color = (60, 100, 60) 
        skin_color = (255, 200, 150)
        gun_color = (20, 20, 20)
        
        pygame.draw.ellipse(self.original_image, cloth_color, (5, 5, 15, 10))
        
        pygame.draw.circle(self.original_image, (50, 90, 50), (12, 10), 5)
        pygame.draw.line(self.original_image, (40,80,40), (12,10), (15, 5), 2)
        pygame.draw.line(self.original_image, (40,80,40), (12,10), (15, 15), 2)

        pygame.draw.line(self.original_image, gun_color, (8, 12), (28, 12), 2) 
        pygame.draw.rect(self.original_image, (40,30,20), (5, 11, 4, 3)) 
        pygame.draw.circle(self.original_image, (10,10,10), (20, 10), 2) 

    def perform_attack(self, target):
        if self.attack_cooldown <= 0:
            if hasattr(target, 'take_damage'):
                target.take_damage(self.damage, "sniper")
                self.game.command_lines.append([vec(self.pos), vec(target.pos), 5]) 
            self.attack_cooldown = self.attack_speed * 60

    def draw(self, surface, offset, zoom):
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


        scaled_img = scale_img(self.original_image, zoom)
        rotated_img = cached_rotate(scaled_img, self.angle)
        screen_pos = to_screen(self.pos, offset, zoom)
        new_rect = rotated_img.get_rect(center=screen_pos)
        surface.blit(rotated_img, new_rect.topleft)
        self.draw_health_and_marker(surface, offset, zoom)


class Engineer(Unit):
    def __init__(self, game, pos, team, build_pos):
        super().__init__(game, pos, team)
        self.speed = ENGINEER_SPEED
        self.build_pos = vec(build_pos)
        self.is_building = False
        self.build_timer = 0
        self.hp = 30
        self.max_hp = 30 
        self.radius = 10
        self.rect = pygame.Rect(pos.x - 10, pos.y - 10, 20, 20)
        self.build_time_total = BUILD_TIME * FPS
    def update(self):
        if not self.is_building:
            dist = self.pos.distance_to(self.build_pos)
            if dist < 5: 
                self.is_building = True
                
                base_time = BUILD_TIME * FPS 
                
                if hasattr(self, 'target_type') and self.target_type == 'bunker':
                    self.build_time_total = base_time //2
                else:
                    self.build_time_total = base_time
                    
            else:
                self.pos += (self.build_pos - self.pos).normalize() * self.speed
        else:
            self.build_timer += 1
            
            if self.build_timer >= self.build_time_total:
                new_b = None
                if hasattr(self, 'target_type'):
                    if self.target_type == 'radar': new_b = RadarBuilding(self.game, self.build_pos, self.team)
                    elif self.target_type == 'mining': new_b = MiningRig(self.game, self.build_pos, self.team)
                    elif self.target_type == 'airfield': new_b = Airfield(self.game, self.build_pos, self.team)
                    elif self.target_type == 'research': new_b = ResearchCenter(self.game, self.build_pos, self.team)
                    elif self.target_type == 'missile_def': new_b = MissileDefenseSystem(self.game, self.build_pos, self.team)
                    elif self.target_type == 'aa_turret': new_b = AntiAirTurret(self.game, self.build_pos, self.team)
                    elif self.target_type == 'power_plant': new_b =PowerPlant(self.game, self.build_pos, self.team)                    
                    elif self.target_type == 'laser_turret': new_b = LaserTurret(self.game, self.build_pos, self.team)
                    elif self.target_type == 'bunker': new_b = Bunker(self.game, self.build_pos, self.team)
                    elif self.target_type == 'barracks': new_b = Barracks(self.game, self.build_pos, self.team)
                    elif self.target_type == 'tech_center': 
                        from core.base_classes import TechCenter
                        new_b = TechCenter(self.game, self.build_pos, self.team)     
                    elif self.target_type == 'shroud_gen': 
                        new_b = ShroudGen(self.game, self.build_pos, self.team)     
                    elif self.target_type == 'prototype_gen': 
                        new_b = PrototypeGen(self.game, self.build_pos, self.team) 
                    # 注意：iron_curtain/nuke_silo 是 PrototypeGen 的挂载武器
                    # (weapon_obj)，构造需要 parent 且独立存在无法充能——
                    # 不能走工程师建造（否则 TypeError 卡死工程师），AI 侧
                    # 走 build_prototype() 流程，玩家走侧栏 ui_sidebar
                    elif self.target_type == 'ciws': 
                        new_b = CIWS(self.game, self.build_pos, self.team)                                                                                 
                    else: new_b = FactoryBuilding(self.game, self.build_pos, self.team)
                
                if new_b:
                    self.game.all_buildings.append(new_b)
                self.alive = False 
        self.update_rect()
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        scaled_rad = scale(10, zoom)
        pygame.draw.circle(surface, YELLOW, screen_pos, scaled_rad)
        if getattr(self, 'is_building', False) and getattr(self, 'build_time_total', 0) > 0:
            pct = self.build_timer / self.build_time_total
        if self.is_building:
            total = self.build_time_total if self.build_time_total > 0 else 1
            pct = self.build_timer / total
            bar_w = scale(40, zoom)
            bar_h = scale(5, zoom)
            bar_y = screen_pos[1] - scale(30, zoom)
            pygame.draw.rect(surface, WHITE, (screen_pos[0] - bar_w//2, bar_y, bar_w, bar_h), 1)
            pygame.draw.rect(surface, YELLOW, (screen_pos[0] - bar_w//2, bar_y, bar_w * pct, bar_h))
        self.draw_health_and_marker(surface, offset, zoom)


        screen_pos = to_screen(self.pos, offset, zoom)
        scaled_rad = scale(10, zoom)
        pygame.draw.circle(surface, YELLOW, screen_pos, scaled_rad)
        if getattr(self, 'is_building', False) and getattr(self, 'build_time_total', 0) > 0:
            pct = self.build_timer / self.build_time_total
        if self.is_building:
            total = self.build_time_total if self.build_time_total > 0 else 1
            pct = self.build_timer / total
            bar_w = scale(40, zoom)
            bar_h = scale(5, zoom)
            bar_y = screen_pos[1] - scale(30, zoom)
            pygame.draw.rect(surface, WHITE, (screen_pos[0] - bar_w//2, bar_y, bar_w, bar_h), 1)
            pygame.draw.rect(surface, YELLOW, (screen_pos[0] - bar_w//2, bar_y, bar_w * pct, bar_h))
        self.draw_health_and_marker(surface, offset, zoom)


class CombatEngineer(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = COMBAT_EN[0]
        self.hp = self.max_hp
        self.speed = COMBAT_EN[1]
        self.is_mechanical = False
        self.radius = 12
        self.rect = pygame.Rect(pos.x-12, pos.y-12, 24, 24)
        
        self.target_building = None
        self.action_type = None 
        self.repair_rate = 5 
        self.repair_cooldown = 0 
    def set_target(self, entity):
        if isinstance(entity, Building) and entity.alive:
            self.target_building = entity
            self.target_pos = None
            self.ai_mode = "MOVE" 
            
            if entity.team == self.team:
                self.action_type = "repair"
            else:
                self.action_type = "capture"
        else:
            super().set_target(entity)

    def update(self):
        if self.target_building:
            if not self.target_building.alive:
                self.target_building = None
                self.action_type = None
                self.ai_mode = "GUARD" 
            else:
                dist = self.pos.distance_to(self.target_building.pos)
                reach_dist = self.target_building.radius + 20 
                
                if dist < reach_dist:
                    self.perform_action()
                else:
                    self.pos += (self.target_building.pos - self.pos).normalize() * self.speed
                    self.update_rect()
                    return 

        super().update()

    def perform_action(self):
        if self.action_type == "repair":
            if self.target_building.hp < self.target_building.max_hp:
                if self.game.frame_count % 30 == 0:
                    FloatingText(self.target_building.pos, "+", GREEN_HAT)
                
                self.target_building.hp = min(self.target_building.hp + self.repair_rate, self.target_building.max_hp)
                
                
            else:
                self.target_building = None
                self.ai_mode = "GUARD"
                
        elif self.action_type == "capture":
            self.target_building.team = self.team
            self.target_building.hp = int(self.target_building.max_hp * 0.5) 
            self.game.particles.add(FloatingText(self.target_building.pos, "CAPTURED!", CYAN))
            self.die() 

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        color = (200, 200, 50) 
        pygame.draw.circle(surface, color, screen_pos, scale(10, zoom))
        accent = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        pygame.draw.circle(surface, accent, screen_pos, scale(5, zoom))
        end = (screen_pos[0]+scale(8,zoom), screen_pos[1]-scale(8,zoom))
        pygame.draw.line(surface, (50,50,50), screen_pos, end, 2)
        
        self.draw_health_and_marker(surface, offset, zoom)


        screen_pos = to_screen(self.pos, offset, zoom)
        color = (200, 200, 50) 
        pygame.draw.circle(surface, color, screen_pos, scale(10, zoom))
        accent = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        pygame.draw.circle(surface, accent, screen_pos, scale(5, zoom))
        end = (screen_pos[0]+scale(8,zoom), screen_pos[1]-scale(8,zoom))
        pygame.draw.line(surface, (50,50,50), screen_pos, end, 2)
        
        self.draw_health_and_marker(surface, offset, zoom)


class HeavyMech(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = MECH_STATS[2]
        self.hp = self.max_hp

        
        self.speed = MECH_STATS[1]
        self.attack_range = MECH_STATS[0]
        self.damage = DMG_MECH
        self.view_radius = 350
        self.attack_speed = 0.1 
        self.is_mechanical = True
        self.can_attack_air = True 
        self.radius = 24 
        self.turn_speed = 8
        self.rect = pygame.Rect(pos.x - 24, pos.y - 24, 48, 48)

        self.original_image = pygame.Surface((100, 100), pygame.SRCALPHA)
        
        C_METAL_DARK = (40, 45, 50)      
        C_ARMOR_BASE = (70, 80, 90)      
        C_ARMOR_HILITE = (100, 110, 120) 
        C_JOINT      = (30, 30, 35)      
        C_WEAPON     = (35, 35, 40)      
        C_VENT       = (20, 20, 20)      
        C_COCKPIT    = (255, 180, 50)    
        C_TEAM       = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        
        
        pygame.draw.polygon(self.original_image, C_METAL_DARK, [(45, 30), (35, 10), (55, 10), (60, 30)]) 
        pygame.draw.rect(self.original_image, C_ARMOR_BASE, (30, 8, 20, 12), border_radius=3) 
        pygame.draw.rect(self.original_image, C_METAL_DARK, (55, 8, 12, 10)) 
        pygame.draw.polygon(self.original_image, C_METAL_DARK, [(45, 70), (35, 90), (55, 90), (60, 70)])
        pygame.draw.rect(self.original_image, C_ARMOR_BASE, (30, 80, 20, 12), border_radius=3)
        pygame.draw.rect(self.original_image, C_METAL_DARK, (55, 82, 12, 10))
        
        pygame.draw.circle(self.original_image, C_JOINT, (50, 50), 12) 
        
        torso_pts = [(30, 35), (65, 25), (65, 75), (30, 65)]
        pygame.draw.polygon(self.original_image, C_ARMOR_BASE, torso_pts)
        
        pygame.draw.rect(self.original_image, C_VENT, (32, 40, 6, 20))
        pygame.draw.rect(self.original_image, C_ARMOR_HILITE, (45, 35, 15, 30))
        
        
        pygame.draw.circle(self.original_image, C_JOINT, (45, 25), 8) 
        pygame.draw.rect(self.original_image, C_WEAPON, (45, 14, 25, 10))
        pygame.draw.rect(self.original_image, (80, 80, 80), (70, 15, 15, 2))
        pygame.draw.rect(self.original_image, (80, 80, 80), (70, 18, 15, 2))
        pygame.draw.rect(self.original_image, (80, 80, 80), (70, 21, 15, 2))
        pygame.draw.rect(self.original_image, C_METAL_DARK, (35, 12, 10, 12))
        
        pygame.draw.circle(self.original_image, C_JOINT, (45, 75), 8)
        pygame.draw.rect(self.original_image, C_WEAPON, (40, 76, 25, 16))
        for mx in [0, 8]:
            for my in [0, 6]:
                pygame.draw.circle(self.original_image, (20, 10, 10), (55+mx, 80+my), 2)
                pygame.draw.circle(self.original_image, (150, 0, 0), (55+mx, 80+my), 1) 

        pygame.draw.circle(self.original_image, C_ARMOR_HILITE, (55, 50), 10) 
        pygame.draw.rect(self.original_image, C_COCKPIT, (58, 46, 6, 8))
        
        pygame.draw.rect(self.original_image, C_TEAM, (35, 28, 6, 6))
        pygame.draw.rect(self.original_image, C_TEAM, (35, 66, 6, 6))

    def perform_attack(self, target):
        if self.attack_cooldown <= 0:
            is_missile = (pygame.time.get_ticks() % 500) < 100 
            
            if is_missile:
                offset = vec(10, 20).rotate(self.angle)
                self.game.projectiles.append(
                    Projectile(self.game, self.pos + offset, target, self.team, self.damage*2,"rocket", breakshellvalue=self.breakarmorvalue, png_key="rocket_mech")
                )
                self.attack_cooldown = self.attack_speed * 220 
            else:
                offset = vec(15, -20).rotate(self.angle)
                self.game.projectiles.append(
                    Projectile(self.game, self.pos + offset, target, self.team, self.damage/2, "heavy", breakshellvalue=self.breakarmorvalue)
                )
                self.attack_cooldown = self.attack_speed * 20 

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 200 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return   
        scaled_img = scale_img(self.original_image, zoom)
        rotated_image = cached_rotate(scaled_img, self.angle)
        

        rect = rotated_image.get_rect(center=screen_pos)
        
        shadow_w = rect.width * 0.8
        shadow_h = rect.height * 0.8
        shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 70), (0, 0, shadow_w, shadow_h))
        
        shadow_dist = scale(12, zoom)
        shadow_rect = shadow_surf.get_rect(center=(screen_pos[0] + shadow_dist, screen_pos[1] + shadow_dist))
        surface.blit(shadow_surf, shadow_rect)
        
        surface.blit(rotated_image, rect.topleft)
        
        self.draw_health_and_marker(surface, offset, zoom)


class ScavengerWalker(Unit):
    def __init__(self, game, pos):
        super().__init__(game, pos, "neutral_hostile")
        self.max_hp = SCAVENGER_STATS[2]
        self.hp = self.max_hp
        self.speed = SCAVENGER_STATS[1]
        self.attack_range = SCAVENGER_STATS[0]
        self.radius = 30
        self.rect = pygame.Rect(pos.x-30, pos.y-30, 60, 60)
        self.is_mechanical = True
        self.wander_timer = 0
        self.wander_target = None
        
    def update(self):
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        
        target = None
        min_dist = 600
        for u in self.game.all_units:
            if u.team in ["player", "enemy"] and u.alive:
                d = self.pos.distance_to(u.pos)
                if d < min_dist:
                    min_dist = d
                    target = u
        
        if target:
            dist = self.pos.distance_to(target.pos)
            if dist <= self.attack_range:
                if self.attack_cooldown <= 0:
                    self.game.projectiles.append(Projectile(self.game, self.pos, target, self.team, DMG_SCAVENGER, 0,"laser"))
                    self.attack_cooldown = 40
            else:
                self.pos += (target.pos - self.pos).normalize() * self.speed
        else:
            self.wander_timer -= 1
            if self.wander_timer <= 0 or (self.wander_target and self.pos.distance_to(self.wander_target) < 10):
                angle = random.uniform(0, 360)
                dist = random.uniform(100, 300)
                self.wander_target = self.pos + vec(dist, 0).rotate(angle)
                self.wander_target.x = max(100, min(self.wander_target.x, WORLD_WIDTH-100))
                self.wander_target.y = max(100, min(self.wander_target.y, WORLD_HEIGHT-100))
                self.wander_timer = 180
            
            if self.wander_target:
                self.pos += (self.wander_target - self.pos).normalize() * (self.speed * 0.5)

        self.update_rect()

    def die(self):
        super().die()
        self.game.particles.add(FloatingText(self.pos, f"BOUNTY: {SCAVENGER_REWARD}", YELLOW, 120))
        player_units = [u for u in self.game.all_units if u.team == "player"]
        if player_units:
            d = min([u.pos.distance_to(self.pos) for u in player_units])
            if d < 600: self.game.cmd_exp += SCAVENGER_REWARD

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        w = scale(40, zoom)
        offset_val = math.sin(pygame.time.get_ticks() * 0.01) * scale(5, zoom)
        pygame.draw.line(surface, (50, 50, 50), screen_pos, (screen_pos[0]-scale(15,zoom), screen_pos[1]+scale(20,zoom)+offset_val), 3)
        pygame.draw.line(surface, (50, 50, 50), screen_pos, (screen_pos[0]+scale(15,zoom), screen_pos[1]+scale(20,zoom)-offset_val), 3)
        pygame.draw.circle(surface, (80, 40, 80), screen_pos, scale(15, zoom))
        pygame.draw.circle(surface, (150, 50, 150), screen_pos, scale(8, zoom)) 
        self.draw_health_and_marker(surface, offset, zoom)

        screen_pos = to_screen(self.pos, offset, zoom)
        w = scale(40, zoom)
        offset_val = math.sin(pygame.time.get_ticks() * 0.01) * scale(5, zoom)
        pygame.draw.line(surface, (50, 50, 50), screen_pos, (screen_pos[0]-scale(15,zoom), screen_pos[1]+scale(20,zoom)+offset_val), 3)
        pygame.draw.line(surface, (50, 50, 50), screen_pos, (screen_pos[0]+scale(15,zoom), screen_pos[1]+scale(20,zoom)-offset_val), 3)
        pygame.draw.circle(surface, (80, 40, 80), screen_pos, scale(15, zoom))
        pygame.draw.circle(surface, (150, 50, 150), screen_pos, scale(8, zoom)) 
        self.draw_health_and_marker(surface, offset, zoom)

