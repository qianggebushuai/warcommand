import pygame
import random
import math
from settings import *
from base_classes import *
import uuid 
import time
import sys
import os

def scale_img(img, zoom):
    w, h = img.get_size()
    return pygame.transform.smoothscale(img, (int(w * zoom), int(h * zoom)))

def to_screen(pos, offset, zoom):
    return (pos - offset) * zoom

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def get_font(size, bold=False):
    font_path = resource_path(os.path.join("fonts", "simhei.ttf"))
    try:
        font = pygame.font.Font(font_path, size)
        if bold: font.set_bold(True)
        return font
    except:
        return pygame.font.Font(None, size)

vec = pygame.math.Vector2
try:
    from pygame.math import Vector2 as vec
except ImportError:
    pass


class Unit(Entity):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.last_hit_timer = 0
        self.speed = 0
        self.target_pos = None
        self.target_entity = None
        self.attack_cooldown = 0
        self.attack_range = 0
        self.angle = 0
        self.target_angle = 0
        self.turn_speed = 5
        self.move_threshold = 10
        self.can_attack_air=False
        self.is_air=False

        self.ai_mode = "GUARD"
        self.unbalanced = False
        self.weight=1
        self.armor=0
        self.breakarmorvalue=0
        self.shield = 0
        self.max_shield = 1000
        self.detectrange=300
        self.is_fixed_wing=False
        self.is_naval=False
        self.tech_bonus_dmg = 1.0

        self.offset_distance=15
        self.trail_size=1.0
        self.spread=8
        self.path_cache = []
        self.path_index = 0
        self.path_recalc_timer = 0
        self.stuck_counter = 0
        self.last_pos = None
        my_tech_tree = getattr(game, 'team_tech_levels', {}).get(team, {})
        
        tech_type = None
        if isinstance(self, (Rifleman, RocketTrooper)): tech_type = "infantry"
        elif isinstance(self, (ArmoredCar, Harvester)): tech_type = "armor"
        elif isinstance(self, (Helicopter, WZ10, AC130)): tech_type = "air"
        if tech_type:
            level = my_tech_tree.get(tech_type, 0)
            if level > 0:
                bonus = 1 + (level * 0.2)
                self.max_hp = int(self.max_hp * bonus)
                self.hp = self.max_hp
                self.tech_bonus_dmg = bonus
    def take_damage(self, amount, damage_type="normal", breakshellvalue=0):
        if self.shield > 0:
            if self.shield >= amount:
                self.shield -= amount
                if hasattr(self.game, 'particles'):
                    Particle(self.game.particles, self.pos, (100, 200, 255), 1, 20, 5)
                return 
            else:
                amount -= self.shield
                self.shield = 0
                if hasattr(self.game, 'particles'):
                    for _ in range(5):
                        Particle(self.game.particles, self.pos, (0, 255, 255), 2, 30, 8)

        super().take_damage(amount, damage_type, breakshellvalue)    
    def set_target(self, entity):
        if not entity or not entity.alive:
            return

        if getattr(entity, 'is_air', False):
            if not self.can_attack_air:
                self.move_to(entity.pos) 
                return

        self.target_entity = entity
        self.target_pos = None
        self.ai_mode = "ATTACK"

    def move_to(self, target_pos):
        target_pos = vec(target_pos)
        if self.target_pos is None or self.target_pos.distance_to(target_pos) > 50:
            self.path_cache = []
            self.path_index = 0
        self.target_pos = target_pos
        self.target_entity = None
        self.ai_mode = "MOVE"

    def _recalc_path(self):
        if self.target_pos is None or self.is_air:
            self.path_cache = []
            return
        start = vec(int(self.pos.x), int(self.pos.y))
        goal = vec(int(self.target_pos.x), int(self.target_pos.y))
        if start.distance_to(goal) < 30:
            self.path_cache = []
            return
        if self.path_recalc_timer > 0:
            self.path_recalc_timer -= 1
            return
        self.path_cache = self._a_star_path(start, goal)
        self.path_index = 0
        self.path_recalc_timer = 10

    def _a_star_path(self, start, goal):
        if self.is_naval:
            return self._simple_path(start, goal)
        start_tuple = (int(start.x), int(start.y))
        goal_tuple = (int(goal.x), int(goal.y))
        open_set = {start_tuple: 0.0}
        came_from = {}
        g_score = {start_tuple: 0.0}
        f_score = {start_tuple: start.distance_to(goal)}
        obstacles = self._get_obstacles()
        max_iter = 1500
        iterations = 0
        while open_set and iterations < max_iter:
            iterations += 1
            current = min(open_set, key=lambda p: f_score.get(p, float('inf')))
            if (current[0] - goal_tuple[0])**2 + (current[1] - goal_tuple[1])**2 < 1600:
                return self._reconstruct_path(came_from, current)
            del open_set[current]
            for dx in [-35, 0, 35]:
                for dy in [-35, 0, 35]:
                    if dx == 0 and dy == 0:
                        continue
                    neighbor = (current[0] + dx, current[1] + dy)
                    if any(obs.inflate(20, 20).collidepoint(neighbor[0], neighbor[1]) for obs in obstacles):
                        continue
                    tentative_g = g_score[current] + math.sqrt(dx*dx + dy*dy)
                    if neighbor not in g_score or tentative_g < g_score[neighbor]:
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g
                        f_score[neighbor] = tentative_g + math.sqrt((neighbor[0]-goal_tuple[0])**2 + (neighbor[1]-goal_tuple[1])**2)
                        if neighbor not in open_set:
                            open_set[neighbor] = f_score[neighbor]
        return self._reconstruct_path(came_from, current) if current in came_from else [vec(goal_tuple[0], goal_tuple[1])]

    def _reconstruct_path(self, came_from, current):
        path = [vec(current[0], current[1])]
        while current in came_from:
            current = came_from[current]
            path.append(vec(current[0], current[1]))
        path.reverse()
        return path[1:] if len(path) > 1 else []

    def _get_obstacles(self):
        obstacles = []
        for b in self.game.all_buildings:
            if not b.alive:
                continue
            b_type = getattr(b, 'b_type', '')
            if b_type in ('bridge', 'cliff', 'rock', 'tree'):
                continue
            obstacles.append(b.rect)
        return obstacles

    def _simple_path(self, start, goal):
        return [goal]

    def _get_waypoint(self):
        if not self.path_cache or self.path_index >= len(self.path_cache):
            return self.target_pos
        return self.path_cache[self.path_index]

    def _advance_path(self):
        if not self.path_cache or self.path_index >= len(self.path_cache):
            return
        wp = self.path_cache[self.path_index]
        if self.pos.distance_to(wp) < 40:
            self.path_index += 1

    def find_nearest_enemy(self):
        nearest = None
        min_dist = self.detectrange 
        
        all_targets = self.game.all_units + self.game.all_buildings
        
        for t in all_targets:
            if not t.alive: continue
            
            if t.team == self.team: continue
            if getattr(t, 'is_stealth', False):
                if self.pos.distance_to(t.pos) > 50: 
                    continue             
            if t.team == "neutral":
                continue
            
            if t.is_air and not self.can_attack_air: continue
            
            dist = self.pos.distance_to(t.pos)
            if dist < min_dist:
                min_dist = dist
                nearest = t
        return nearest
    def check_move_validity(self, test_pos):
        """
        检查目标位置 test_pos 是否可行走。
        返回: True (可行), False (阻挡)
        """
        on_bridge = False
        for b in self.game.all_buildings:
            if getattr(b, 'b_type', '') == 'bridge' and not getattr(b, 'is_broken', False):
                if b.rect.inflate(10, 10).collidepoint(int(test_pos.x), int(test_pos.y)):
                    on_bridge = True
                    break
        
        in_water = False
        
        if hasattr(self.game, 'lakes'):
            point_rect = pygame.Rect(int(test_pos.x), int(test_pos.y), 1, 1)
            
            for lake in self.game.lakes:
                l_rect = lake['rect'] if isinstance(lake, dict) else lake
                l_type = lake.get('type', 'water') if isinstance(lake, dict) else 'water'
                
                if l_rect.collidepoint(int(test_pos.x), int(test_pos.y)):
                    if l_type == 'water':
                        in_water = True
                        break 
                    elif l_type == 'mountain':
                        return False 
        
        if in_water and hasattr(self.game.current_map, 'islands'):
            point_rect = pygame.Rect(int(test_pos.x), int(test_pos.y), 1, 1)
            if point_rect.collidelist(self.game.current_map.islands) != -1:
                in_water = False

        hit_building = False
        if not isinstance(self, Harvester): 
            for b in self.game.all_buildings:
                if b.alive:
                    if b.rect.inflate(-10, -10).collidepoint(int(test_pos.x), int(test_pos.y)):
                        hit_building = True
                        break

        is_naval = getattr(self, 'is_naval', False)
        
        if is_naval:
            if not in_water: return False
            if hit_building: return False
            return True
        else:
            if on_bridge: return True 
            if in_water: return False 
            if hit_building: return False 
            return True
    def update(self):
        if hasattr(self, 'stun_timer') and self.stun_timer > 0:
            self.stun_timer -= 1; self.update_rect(); return
        if hasattr(self, 'deploy_timer') and self.deploy_timer > 0:
            self.deploy_timer -= 1; self.update_rect(); return

        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        if self.last_hit_timer > 0: self.last_hit_timer -= 1

        if getattr(self, 'unbalanced', False):
            self.unbalanced_timer -= 1
            if hasattr(self, 'drift_vel'):
                self.pos += self.drift_vel
                self.drift_vel *= 0.9

            for b in self.game.all_buildings:
                if b.alive and b.rect.inflate(-5, -5).collidepoint(int(self.pos.x), int(self.pos.y)):
                    self.take_damage(5, "crush")
                    Particle(self.game.particles, self.pos, (200, 100, 0), 1, 20, 5)
                    break

            self._check_drowning()

            if self.unbalanced_timer <= 0:
                self.unbalanced = False
                self.drift_vel = vec(0,0)

            self.update_rect()
            return

        if self.game.is_online and self.game.my_role == "CLIENT":
            self._update_trails()
            self.update_rect(); return

        if not self.is_air:
            if self.last_pos is None:
                self.last_pos = vec(self.pos)
            else:
                dist_moved = self.pos.distance_to(self.last_pos)
                if dist_moved < 1:
                    self.stuck_counter += 1
                    if self.stuck_counter > 30:
                        self.path_cache = []
                        self.stuck_counter = 0
                else:
                    self.stuck_counter = 0
                self.last_pos = vec(self.pos)

        self.path_recalc_timer += 1
        if self.path_recalc_timer > 60:
            self.path_recalc_timer = 0
            if self.target_pos and not self.is_air:
                if not self.path_cache or self.pos.distance_to(self.target_pos) > 100:
                    self._recalc_path()

        if self.path_cache and not self.is_air:
            self._advance_path()

        target_unit = None
        move_dest = None

        has_order = (self.target_entity is not None) or (self.target_pos is not None)
        if has_order:
            if self.target_entity:
                if not self.target_entity.alive: self.target_entity = None
                else: target_unit = self.target_entity
            elif self.target_pos:
                if self.path_cache and not self.is_air:
                    move_dest = self._get_waypoint()
                else:
                    move_dest = self.target_pos
        else:
            if not isinstance(self, (Harvester, CruiseMissile, Engineer)):
                target_unit = self.find_nearest_enemy()

        current_speed = self.speed
        if not self.is_air:
            in_slope = False
            if hasattr(self.game, 'current_map') and self.game.current_map:
                if hasattr(self.game.current_map, 'slopes'):
                    point = (int(self.pos.x), int(self.pos.y))
                    for rect in self.game.current_map.slopes:
                        if rect.collidepoint(point):
                            in_slope = True; break
            if in_slope: current_speed *= 0.8
        desired_move = vec(0, 0)
        face_vec = None

        if target_unit:
            dist = self.pos.distance_to(target_unit.pos)
            if getattr(target_unit, 'can_garrison', False):
                if dist < 100:
                    if target_unit.enter_unit(self):
                        return

            if dist <= self.attack_range:
                self.perform_attack(target_unit)
                face_vec = target_unit.pos - self.pos
            else:
                desired_move = (target_unit.pos - self.pos).normalize() * current_speed
                face_vec = desired_move
        elif move_dest:
            if self.pos.distance_to(move_dest) < 25:
                if self.path_cache and self.path_index < len(self.path_cache):
                    self.path_index += 1
                    if self.path_index >= len(self.path_cache):
                        self.target_pos = None
                        self.path_cache = []
                else:
                    self.target_pos = None
            else:
                desired_move = (move_dest - self.pos).normalize() * current_speed
                face_vec = desired_move


        actual_move = vec(0, 0)

        if desired_move.length() > 0:
            self.target_angle = math.degrees(math.atan2(-desired_move.y, desired_move.x))

            diff = (self.target_angle - self.angle + 180) % 360 - 180
            turn_spd = getattr(self, 'turn_speed', 10)

            if abs(diff) < turn_spd:
                self.angle = self.target_angle
            else:
                self.angle += turn_spd if diff > 0 else -turn_spd

            move_thresh = getattr(self, 'move_threshold', 20)
            if self.is_air or abs(diff) < move_thresh:
                actual_move = desired_move
            else:
                pass
        
        separation_force = vec(0, 0)
        neighbors = 0
        for u in self.game.all_units:
            if u != self and u.alive:
                if self.is_air != u.is_air: continue 
                if not self.collision or not u.collision:
                    continue                
                is_self_naval = getattr(self, 'is_naval', False)
                is_u_naval = getattr(u, 'is_naval', False)
                if is_self_naval != is_u_naval: continue

                dist = self.pos.distance_to(u.pos)
                min_dist = self.radius + u.radius
                if dist < min_dist:
                    push = (self.pos - u.pos).normalize() if dist > 0 else vec(1,0)
                    separation_force += push * ((min_dist - dist) * 0.1)
                    neighbors += 1
        
        if neighbors > 0:
            if separation_force.length() > 2: separation_force.scale_to_length(2)
            actual_move += separation_force 

        final_pos = self.pos + actual_move
        
        if self.is_air:
            self.pos = final_pos
        else:
            if actual_move.length() > 0:
                if self.check_move_validity(final_pos):
                    self.pos = final_pos
                else:
                    test_x = self.pos + vec(actual_move.x, 0)
                    if self.check_move_validity(test_x):
                        self.pos = test_x
                    else:
                        test_y = self.pos + vec(0, actual_move.y)
                        if self.check_move_validity(test_y):
                            self.pos = test_y
                        else:
                            pass
        if self.target_pos:
            dist = self.pos.distance_to(self.target_pos)
            if dist < 25: 
                self.target_pos = None

        if desired_move.length() == 0 and face_vec:
             target_a = math.degrees(math.atan2(-face_vec.y, face_vec.x))
             diff = (target_a - self.angle + 180) % 360 - 180
             turn_spd = getattr(self, 'turn_speed', 10)
             if abs(diff) < turn_spd: self.angle = target_a
             else: self.angle += turn_spd if diff > 0 else -turn_spd
        
        self.update_rect()
        
        if not self.is_air and not getattr(self, 'is_naval', False):
            self._check_drowning()

        can_crush = self.is_mechanical and not self.is_air and not getattr(self, 'is_naval', False)
        
        if can_crush and (not self.game.is_online or self.game.my_role == "HOST"):
            
            crush_rect = self.rect.inflate(-10, -10) 
            
            for victim in self.game.all_units:
                if victim != self and victim.alive:
                    is_enemy = (victim.team != self.team)
                    is_infantry = (not victim.is_mechanical and not victim.is_air)
                    
                    if is_enemy and is_infantry:
                        if crush_rect.colliderect(victim.rect):
                            victim.take_damage(9999, "crush")
                            
                            if hasattr(self.game, 'net_events'):
                                self.game.net_events.append({
                                    "type": "EXPLOSION", 
                                    "x": int(victim.pos.x), "y": int(victim.pos.y), 
                                    "dt": "blood"
                                })
        is_moving = (self.pos - getattr(self, 'prev_pos', self.pos)).length() > 0.01
        self.prev_pos = vec(self.pos) 
        if self.is_mechanical and not self.is_air and not getattr(self, 'is_naval', False) and is_moving and isinstance(self, (M1A2, Type99, TerminatorIFV,APC,TankCarrier)) :
            if self.game.frame_count % 5 == 0: 
                self.create_dust_trail()

        if is_moving and self.is_naval==True:
            if self.game.frame_count % 5 == 0: 
                self.create_water_trail(self.offset_distance,self.trail_size,self.spread)
        if self.shield>0 and self.game.frame_count%60==0:
            self.shield-=min(self.shield,20)


    def _update_trails(self):
        
        current_pos = vec(self.pos)
        prev = getattr(self, 'prev_pos', current_pos)
        
        if (current_pos - prev).length() > 0.2:
            is_moving = True
        else:
            is_moving = False
            
        self.prev_pos = current_pos 
        
        if is_moving:
            is_tank = isinstance(self, (M1A2, Type99, TerminatorIFV,APC,TankCarrier))
            if self.is_mechanical and not self.is_air and not getattr(self, 'is_naval', False) and is_tank:
                if self.game.frame_count % 5 == 0:
                    self.create_dust_trail()

            if getattr(self, 'is_naval', False):
                if self.game.frame_count % 5 == 0:
                    self.create_water_trail(self.offset_distance,self.trail_size,self.spread)      
    def create_dust_trail(self):
        map_name = getattr(self.game.current_map, 'name', '')
        color = (150, 140, 100) 
        
        if map_name == "VERDUN HEIGHTS":
            color = (50, 45, 40) 
        elif map_name == "FROZEN ARCHIPELAGO":
            color = (220, 230, 255) 
        elif map_name == "风暴海岸":
            color = (200, 190, 150) 
            
        rear_vec = vec(-15, 0).rotate(self.angle) 
        offset_l = rear_vec + vec(0, -8).rotate(self.angle)
        offset_r = rear_vec + vec(0, 8).rotate(self.angle)
        
        for pos in [self.pos + offset_l, self.pos + offset_r]:
            p_pos = pos + vec(random.randint(-2,2), random.randint(-2,2))
            Particle(self.game.particles, p_pos, color, 0.5, 40, random.randint(3, 6))    
    def create_water_trail(self, offset_distance=-15, trail_size=1.0, spread=8):
        color = (0, 60, 150)
        map_name = getattr(self.game.current_map, 'name', '')
        if map_name=="龙之谷":
            color=(0,100,255)           
        rear_vec = vec(offset_distance, 0).rotate(-self.angle)
        
        offset_l = rear_vec + vec(0, -spread).rotate(-self.angle)
        offset_r = rear_vec + vec(0, spread).rotate(-self.angle)
        
        base_min_size = 5
        base_max_size = 10
        base_duration = 60
        
        particle_min = int(base_min_size * trail_size)
        particle_max = int(base_max_size * trail_size)
        duration = int(base_duration * trail_size)
        
        scatter = int(3 * trail_size)
        
        for pos in [self.pos + offset_l, self.pos + offset_r]:
            p_pos = pos + vec(random.randint(-scatter, scatter), 
                            random.randint(-scatter, scatter))
            Particle(
                self.game.particles, 
                p_pos, 
                color, 
                0.5,  
                duration, 
                random.randint(particle_min, particle_max)
            )

    def _check_drowning(self):
        in_water = False
        pt = pygame.Rect(int(self.pos.x), int(self.pos.y), 1, 1)
        
        if hasattr(self.game, 'lakes'):
            lake_rects = [l['rect'] if isinstance(l, dict) else l for l in self.game.lakes]
            if pt.collidelist(lake_rects) != -1: 
                in_water = True
                
                if hasattr(self.game.current_map, 'islands'):
                    if pt.collidelist(self.game.current_map.islands) != -1:
                        in_water = False 
        if in_water:
            for b in self.game.all_buildings:
                if getattr(b, 'b_type', '') == 'bridge' and not getattr(b, 'is_broken', False):
                    if b.rect.inflate(10, 10).collidepoint(int(self.pos.x), int(self.pos.y)):
                        in_water = False; break

        if in_water:
            if not hasattr(self, 'drown_timer'): self.drown_timer = 0
            self.drown_timer += 1
            if self.drown_timer > 120:
                if self.game.frame_count % 30 == 0:
                    self.take_damage(20, "drown")
                    Particle(self.game.particles, self.pos, (200, 200, 255), 1, 30, 5)
        else:
            self.drown_timer = 0
    def perform_attack(self, target):
        if self.attack_cooldown <= 0:
            self.fire_projectile(target)
            self.attack_cooldown = 60 

    def fire_projectile(self, target): pass 

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
            img = pygame.image.load(path).convert_alpha()
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
        
        rotated_img = pygame.transform.rotate(scaled_img, self.angle)   
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
        rocket = Projectile(self.game, self.pos, None, self.team, dmg, "rocket", is_aoe=True, aoe_radius=50, breakshellvalue=self.breakarmorvalue)
        rocket.target_dest = new_dest 
        rocket.vel = scattered_vec.normalize() * ROCKET_SPEED
        self.game.projectiles.append(rocket)
    def draw(self, surface, offset, zoom):
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
        

        s_rad = scale(11, zoom)
        

        pygame.draw.circle(surface, (150, 140, 130), screen_pos, s_rad)
        

        accent = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        pygame.draw.circle(surface, accent, screen_pos, scale(6, zoom))
        
        gun_end = (screen_pos[0] + s_rad * 1.2 * math.cos(math.radians(-self.angle)),
                   screen_pos[1] + s_rad * 1.2 * math.sin(math.radians(-self.angle)))
        pygame.draw.line(surface, (20, 20, 20), screen_pos, gun_end, scale(5, zoom)) 
        
        self.draw_health_and_marker(surface, offset, zoom)

class ArmoredCar(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp =ARMORED_STATS[2]
        self.hp = self.max_hp

        self.speed = ARMORED_STATS[1]
        self.attack_range = ARMORED_STATS[0]
        self.is_mechanical = True
        self.can_attack_air = True
        self.radius = 12
        self.turn_speed = 12
        self.original_image = pygame.Surface((80, 80), pygame.SRCALPHA)
        C_TIRE       = (15, 15, 20)  
        C_BODY       = (65, 75, 65)      
        C_BODY_LIGHT = (85, 95, 85)   
        C_DETAIL     = (40, 50, 40)      
        C_BARREL     = (30, 30, 35)     
        C_TEAM       = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        wheel_offsets = [
            (12, -12), (-12, -12), 
            (12, 12),  (-12, 12)   
        ]
        
        for dx, dy in wheel_offsets:

            wx, wy = 40 + dx - 5, 40 + dy - 3
            pygame.draw.rect(self.original_image, C_TIRE, (wx, wy, 10, 6), border_radius=2)

        pygame.draw.rect(self.original_image, C_BODY, (20, 30, 35, 20))
        
        nose_points = [(55, 30), (65, 40), (55, 50)]
        pygame.draw.polygon(self.original_image, C_BODY, nose_points)
        
        pygame.draw.rect(self.original_image, C_BODY_LIGHT, (22, 34, 30, 12))
        
        pygame.draw.rect(self.original_image, (20, 30, 40), (50, 35, 4, 10))
        
        pygame.draw.rect(self.original_image, C_TEAM, (22, 34, 4, 12))

        turret_x, turret_y = 38, 40
        
        pygame.draw.line(self.original_image, C_BARREL, (turret_x, turret_y), (turret_x + 22, turret_y), 3)
        pygame.draw.line(self.original_image, (10,10,10), (turret_x + 20, turret_y), (turret_x + 22, turret_y), 5)
        
        pygame.draw.circle(self.original_image, C_BODY_LIGHT, (turret_x, turret_y), 7)
        pygame.draw.circle(self.original_image, C_DETAIL, (turret_x, turret_y), 4)

        pygame.draw.circle(self.original_image, (200, 50, 50), (20, 33), 1)
        pygame.draw.circle(self.original_image, (200, 50, 50), (20, 47), 1)

    def take_damage(self, amount, damage_type="normal",breakshellvalue=0):
        if damage_type == "rifle": amount *= 0.5
        super().take_damage(amount, damage_type,breakshellvalue)
    def perform_attack(self, target):
        if self.attack_cooldown <= 0:
            base_vec = (target.pos - self.pos).normalize()
            offset_angle = random.uniform(-10, 10)
            fire_vec = base_vec.rotate(offset_angle)
            dmg = DMG_ARMORED * self.tech_bonus_dmg
            proj = Projectile(self.game, self.pos, None, self.team, dmg,"heavy", breakshellvalue=self.breakarmorvalue)
            proj.vel = fire_vec * BULLET_SPEED
            self.game.projectiles.append(proj)
            self.attack_cooldown = 5
    def draw(self, surface, offset, zoom):

        screen_pos = to_screen(self.pos, offset, zoom)        
        scaled_img = scale_img(self.original_image, zoom)
        
        shadow_surf = scaled_img.copy()
        shadow_surf.fill((0, 0, 0, 80), special_flags=pygame.BLEND_RGBA_MULT)
        
        margin = 200 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return   
        rotated_image = pygame.transform.rotate(scaled_img, self.angle)
        rotated_shadow = pygame.transform.rotate(shadow_surf, self.angle)
        
        shadow_offset_vec = scale(5, zoom)
        shadow_rect = rotated_shadow.get_rect(center=(screen_pos[0] + shadow_offset_vec, screen_pos[1] + shadow_offset_vec))
        surface.blit(rotated_shadow, shadow_rect.topleft)
        
        rect = rotated_image.get_rect(center=screen_pos)
        surface.blit(rotated_image, rect.topleft)
        
        self.draw_health_and_marker(surface, offset, zoom)


class APC(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        
        self.faction = "USA"
        if game.teams_config and team in game.teams_config:
            self.faction = game.teams_config[team].get('faction', 'USA')
            
        self.max_hp = APC_STATS[2]
        self.hp = self.max_hp
        self.speed = APC_STATS[1]
        self.is_mechanical = True
        self.radius = 25
        self.rect = pygame.Rect(pos.x-25, pos.y-25, 50, 50)
        self.accuracy_error=18      
        self.cargo = [] 
        self.capacity = 8
        self.attack_range = 500
        self.damage = 10 
        self.turret_angle = 0
        self.armor=5
        if self.faction in ["CHINA", "RUSSIA"]:
            self.can_attack_air = True
            self.damage = 10 
            self.fire_rate = 5 
            self.attack_range = 300
            self.speed=APC_STATS[1]*0.7
            self.body_image = self.generate_aa_body_image()
            self.turret_image = self.generate_aa_turret_image()
        else:
            self.can_attack_air = False
            self.fire_rate = 10
            self.body_image = self.generate_body_image()
            self.turret_image = self.generate_turret_image()

    def generate_body_image(self):
        w_raw, h_raw = 80, 50
        body_surf = pygame.Surface((w_raw, h_raw), pygame.SRCALPHA)
        color_body = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        color_dark = (40, 45, 40)
        color_detail = (30, 30, 30)
        color_tire = (20, 20, 20)
        
        wheel_positions = [15, 40, 65] 
        for x in wheel_positions:
            pygame.draw.rect(body_surf, color_tire, (x-6, 2, 12, 8), border_radius=2)
            pygame.draw.rect(body_surf, color_tire, (x-6, h_raw-10, 12, 8), border_radius=2)

        body_points = [(5, 10), (75, 12), (75, 38), (5, 40)]
        pygame.draw.polygon(body_surf, color_body, body_points)
        pygame.draw.polygon(body_surf, color_detail, body_points, 1)
        
        pygame.draw.rect(body_surf, color_dark, (15, 8, 50, 4))
        pygame.draw.rect(body_surf, color_dark, (15, 38, 50, 4))
        
        r = min(255, color_body[0] + 20)
        g = min(255, color_body[1] + 20)
        b = min(255, color_body[2] + 20)
        highlight_color = (r, g, b)
        pygame.draw.polygon(body_surf, highlight_color, [(60, 15), (78, 20), (78, 30), (60, 35)])

        pygame.draw.line(body_surf, color_detail, (5, 15), (5, 35), 2)
        pygame.draw.rect(body_surf, (50, 55, 50), (20, 18, 12, 14), 1)
        
        return body_surf

    def generate_turret_image(self):
        s = pygame.Surface((40, 40), pygame.SRCALPHA)
        cx, cy = 20, 20
        color_dark = (40, 45, 40)
        pygame.draw.rect(s, (20, 20, 20), (cx, cy-2, 18, 4)) 
        pygame.draw.circle(s, color_dark, (cx, cy), 9)
        pygame.draw.rect(s, (40, 50, 40), (cx-5, cy-8, 10, 6))
        return s

    def generate_aa_body_image(self):
        w, h = 80, 56 
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w//2, h//2
        
        C_BODY = (100, 110, 90) 
        C_TRACK = (30, 30, 35)
        C_DETAIL = (60, 70, 60)
        
        pygame.draw.rect(s, C_TRACK, (5, 2, 70, 10))  
        pygame.draw.rect(s, C_TRACK, (5, 44, 70, 10)) 
        for i in range(0, 70, 8): 
            pygame.draw.line(s, (10,10,10), (5+i, 2), (5+i, 12), 1)
            pygame.draw.line(s, (10,10,10), (5+i, 44), (5+i, 54), 1)

        body_rect = pygame.Rect(5, 10, 70, 36)
        pygame.draw.rect(s, C_BODY, body_rect)
        pygame.draw.rect(s, C_DETAIL, body_rect, 1)
        
        pygame.draw.polygon(s, (120, 130, 110), [(60, 12), (75, 20), (75, 36), (60, 44)])
        
        pygame.draw.rect(s, (40,40,40), (8, 15, 10, 26))
        for i in range(4):
            pygame.draw.line(s, (60,60,60), (8, 18+i*6), (18, 18+i*6), 1)

        return s

    def generate_aa_turret_image(self):
        w, h = 70, 60
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        
        C_TURRET = (80, 90, 70)   
        C_BARREL = (30, 30, 35)   
        C_MISSILE = (160, 150, 130)
        C_RADAR = (100, 110, 120) 
        C_SENSOR = (40, 40, 50)   
        
        turret_w = 28
        turret_h = 24
        turret_rect = pygame.Rect(cx-turret_w//2, cy-turret_h//2, turret_w, turret_h)
        pygame.draw.rect(s, C_TURRET, turret_rect, border_radius=4)
        pygame.draw.rect(s, (60, 70, 50), turret_rect.inflate(-4, -4), 1) 
        
        barrel_len = 35
        barrel_w = 4
        
        gun_y_top = cy - 10
        pygame.draw.rect(s, C_BARREL, (cx+5, gun_y_top, barrel_len, barrel_w))
        pygame.draw.rect(s, (50,50,50), (cx+5+barrel_len, gun_y_top-1, 6, 6)) 
        

        gun_y_bot = cy + 10 - barrel_w
        pygame.draw.rect(s, C_BARREL, (cx+5, gun_y_bot, barrel_len, barrel_w))
        pygame.draw.rect(s, (50,50,50), (cx+5+barrel_len, gun_y_bot-1, 6, 6))
        
        mis_len = 18
        mis_w = 4
        
        mis_y_top = cy - 20
        pygame.draw.rect(s, (50,60,50), (cx, mis_y_top, 10, 6)) 
        pygame.draw.rect(s, C_MISSILE, (cx-5, mis_y_top-2, mis_len, mis_w)) 
        pygame.draw.rect(s, C_MISSILE, (cx-5, mis_y_top+2, mis_len, mis_w)) 
        
        mis_y_bot = cy + 14
        pygame.draw.rect(s, (50,60,50), (cx, mis_y_bot, 10, 6)) 
        pygame.draw.rect(s, C_MISSILE, (cx-5, mis_y_bot+2, mis_len, mis_w)) 
        pygame.draw.rect(s, C_MISSILE, (cx-5, mis_y_bot+6, mis_len, mis_w)) 

        radar_w = 4
        radar_h = 18 
        pygame.draw.rect(s, C_RADAR, (cx-20, cy-radar_h//2, radar_w, radar_h))
        pygame.draw.line(s, C_TURRET, (cx-14, cy), (cx-20, cy), 3)
        
        pygame.draw.circle(s, C_SENSOR, (cx+8, cy), 4)
        pygame.draw.circle(s, (100, 255, 255), (cx+9, cy-1), 2) 

        return s

    def update(self):
        super().update()
        
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        
        if not self.game.is_online or self.game.my_role == "HOST":
            has_eng = False
            for u in self.cargo:
                if u.__class__.__name__ == "CombatEngineer": 
                    has_eng = True; break
            
            self.is_repairing = has_eng 
            
            if has_eng and self.game.frame_count % 60 == 0:
                repair_range = 100
                repair_amount = 15
                for u in self.game.all_units:
                    if u.alive and u.team == self.team and u != self:
                        if self.pos.distance_to(u.pos) < repair_range:
                            if u.hp < u.max_hp:
                                u.hp = min(u.hp + repair_amount, u.max_hp)

            fire_target = None
            
            if self.target_entity and self.target_entity.alive:
                dist = self.pos.distance_to(self.target_entity.pos)
                if dist <= self.attack_range:
                    if self.faction in ["CHINA", "RUSSIA"]:
                        fire_target = self.target_entity
                    else:
                        if not getattr(self.target_entity, 'is_air', False):
                            fire_target = self.target_entity
            
            if not fire_target:
                best = None
                min_dist = self.attack_range
                
                can_aa = (self.faction in ["CHINA", "RUSSIA"])
                
                for u in self.game.all_units:
                    if u.team != self.team and u.alive:
                        d = self.pos.distance_to(u.pos)
                        if d < min_dist:
                            is_air = getattr(u, 'is_air', False)
                            if (is_air and can_aa) or (not is_air):
                                if can_aa and is_air: d -= 100 
                                
                                if d < min_dist:
                                    min_dist = d
                                    best = u
                
                fire_target = best
            
            if fire_target:
                diff = fire_target.pos - self.pos
                self.turret_angle = math.degrees(math.atan2(-diff.y, diff.x))
                
                if self.attack_cooldown <= 0:
                    self.perform_attack(fire_target)
            else:
                pass

    def perform_attack(self, target):
        if self.attack_cooldown > 0: return
        muzzle_offset = vec(25, 0).rotate(-self.turret_angle) 
        fire_pos = self.pos + muzzle_offset
        
        if self.faction in ["CHINA", "RUSSIA"]:

            for _ in range(2):
                angle_offset = random.uniform(-self.accuracy_error, self.accuracy_error)
                spread = vec(random.randint(-15, 15), random.randint(-15, 15))

                target_dest = target.pos + spread
                
                p = Projectile(self.game, fire_pos, None, self.team, self.damage, "bullet", is_aoe=True, aoe_radius=10)
                p.speed = 18
                p.vel = ((target_dest - fire_pos).rotate(angle_offset)).normalize() * p.speed
                
                p.pos += vec(random.randint(-15,15), random.randint(-15,15))
                p.life_time=40
                self.game.projectiles.append(p)
                
            self.attack_cooldown = 15
            
        else:
            p = Projectile(self.game, fire_pos, target, self.team, self.damage*2, "heavy", breakshellvalue=self.breakarmorvalue)
            self.game.projectiles.append(p)
            self.attack_cooldown = 10

    def load_units(self):
        if len(self.cargo) >= self.capacity: 
            self.game.particles.add(FloatingText(self.pos, "FULL!", RED))
            return

        valid_types = (Rifleman, RocketTrooper, CombatEngineer, Sniper, Shotgunner)
        
        for u in self.game.all_units[:]: 
            if u.team == self.team and isinstance(u, valid_types) and u != self:
                if self.pos.distance_to(u.pos) < 100: 
                    self.cargo.append(u)
                    self.game.all_units.remove(u) 
                    if len(self.cargo) >= self.capacity: break
        
        if self.cargo:
            self.game.particles.add(FloatingText(self.pos, "LOADED", GREEN_HAT))

    def unload_units(self):
        if not self.cargo: return
        for u in self.cargo:
            offset = vec(random.randint(-40, 40), random.randint(-40, 40))
            u.pos = self.pos + offset
            u.target_pos = None
            u.target_entity = None
            self.game.all_units.append(u)
        self.cargo = []
        self.game.particles.add(FloatingText(self.pos, "UNLOADED", GREEN_HAT))

    def die(self):
        super().die()
        self.cargo = [] 

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 200 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return           
        
        scaled_body = scale_img(self.body_image, zoom)
        rot_body = pygame.transform.rotate(scaled_body, self.angle)
        body_rect = rot_body.get_rect(center=screen_pos)
        surface.blit(rot_body, body_rect)
        
        if self.faction in ["CHINA", "RUSSIA"]:
            t_off_x = 0 
        else:
            t_off_x = 15
            
        turret_offset = vec(t_off_x, 0).rotate(-self.angle)
        turret_screen_pos = to_screen(self.pos + turret_offset, offset, zoom)
        
        scaled_turret = scale_img(self.turret_image, zoom)
        rot_turret = pygame.transform.rotate(scaled_turret, self.turret_angle) 
        turret_rect = rot_turret.get_rect(center=turret_screen_pos)
        surface.blit(rot_turret, turret_rect)

        if getattr(self, 'is_repairing', False):
            r = scale(100, zoom)
            s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (0, 200, 255, 30), (r, r), r)
            pygame.draw.circle(s, (0, 200, 255, 80), (r, r), r, 2)
            t = (pygame.time.get_ticks() // 50) % 20
            wave_r = int(r * (t / 20.0))
            pygame.draw.circle(s, (0, 255, 255, 100), (r, r), wave_r, 1)
            surface.blit(s, (screen_pos[0]-r, screen_pos[1]-r))       
            
        self.draw_health_and_marker(surface, offset, zoom)
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
class Harvester(Unit):
    def __init__(self, game, pos, team, home_building):
        super().__init__(game, pos, team)
        self.home_building = home_building
        self.speed = HARVESTER_STATS[1]
        self.hp = HARVESTER_STATS[2]
        self.armor=15
        self.max_hp = self.hp
        self.is_mechanical = True
        self.radius = 15
        self.rect = pygame.Rect(pos.x - 15, pos.y - 15, 30, 30)

        self.home_building = home_building
        self.state = "IDLE" 
        self.mine_target = None
        self.mine_timer = 0
        self.mine_duration = 300 
        self.findrange=0
    def update(self):
        if self.target_pos and self.ai_mode == "MOVE":
            self.state = "MANUAL"
        elif self.state == "MANUAL" and not self.target_pos:
            self.state = "IDLE"
            self.mine_target = None
            self.target_entity = None 

        if not self.home_building or not self.home_building.alive:
            found_new = False
            for b in self.game.all_buildings:
                if b.team == self.team and getattr(b, 'b_type', '') == 'mining' and b.alive:
                    self.home_building = b
                    if isinstance(b, MiningRig): b.harvesters.append(self)
                    found_new = True
                    break
            if not found_new:
                self.hp = 0
                return

        if not self.game.is_online or self.game.my_role == "HOST":
            if self.state != "MANUAL":
                
                if self.state == "IDLE":
                    if self.mine_target is None:
                        min_dist = 100 + 5 * self.findrange
                        max_dist = 200 + 10 * self.findrange
                        angle = random.randint(0, 360)
                        offset = vec(random.randint(min_dist, max_dist), 0).rotate(angle)
                        self.mine_target = self.home_building.pos + offset
                        
                        self.mine_target.x = max(0, min(self.game.current_map.width, self.mine_target.x))
                        self.mine_target.y = max(0, min(self.game.current_map.height, self.mine_target.y))
                        
                        self.state = "MOVING_TO_ORE"

                elif self.state == "MOVING_TO_ORE":
                    target = self.mine_target
                    dist = self.pos.distance_to(target)
                    
                    if dist < self.speed: 
                        self.pos = vec(target)
                        self.state = "MINING"
                        self.mine_timer = self.mine_duration
                    else:
                        direction = (target - self.pos).normalize()
                        self.pos += direction * self.speed
                        self.angle = math.degrees(math.atan2(-direction.y, direction.x))
                elif self.state == "MINING":
                    self.mine_timer -= 1
                    if self.mine_timer <= 0: 
                        self.state = "RETURNING"

                elif self.state == "RETURNING":
                    target = self.home_building.pos
                    dist = self.pos.distance_to(target)
                    
                    if dist < 60: 
                        
                        self.findrange += 1
                        if self.team in self.game.team_resources:
                            current = self.game.team_resources[self.team]
                            limit = getattr(self.game, 'max_cmd_exp', 50000)
                            self.game.team_resources[self.team] = min(current + HARVEST_AMOUNT, limit)
                            self.game.particles.add(FloatingText(self.pos, f"+{HARVEST_AMOUNT}", YELLOW))
                        
                        self.state = "IDLE"
                        self.mine_target = None
                    else:
                        direction = (target - self.pos).normalize()
                        self.pos += direction * self.speed
                        self.angle = math.degrees(math.atan2(-direction.y, direction.x))

        if self.state == "MANUAL":
            super().update()
        else:
            self.update_rect()
    def is_position_valid(self, pos):
        if not self.game.current_map: return True
        in_water = False
        in_island = False
        
        if hasattr(self.game.current_map, 'lakes'):
            for lake in self.game.current_map.lakes:
                if lake['type'] == 'water' and lake['rect'].collidepoint(pos.x, pos.y):
                    in_water = True
                    break
        
        if hasattr(self.game.current_map, 'islands'):
            for isle_rect in self.game.current_map.islands:
                if isle_rect.collidepoint(pos.x, pos.y):
                    in_island = True
                    break
        
        if in_water and not in_island:
            return False
            
        return True
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        w = scale(36, zoom)
        h = scale(24, zoom)
        margin = 200 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return           
        C_BODY   = (255, 200, 0)  
        C_CABIN  = (40, 40, 50)    
        C_TREAD  = (30, 30, 30)    
        C_ORE    = (0, 255, 255)   
        C_DRILL  = (150, 150, 150) 
        surf_size = int(scale(60, zoom)) 
        s = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        cx, cy = surf_size // 2, surf_size // 2
        
        body_len = w
        body_wid = h
        
        tread_w = scale(6, zoom)
        pygame.draw.rect(s, C_TREAD, (cx - body_len/2, cy - body_wid/2 - tread_w/2, body_len, tread_w))
        pygame.draw.rect(s, C_TREAD, (cx - body_len/2, cy + body_wid/2 - tread_w/2, body_len, tread_w))
        for i in range(0, int(body_len), int(scale(4, zoom))):
            x = cx - body_len/2 + i
            pygame.draw.line(s, (60,60,60), (x, cy - body_wid/2 - tread_w/2), (x, cy - body_wid/2 + tread_w/2), 1)
            pygame.draw.line(s, (60,60,60), (x, cy + body_wid/2 - tread_w/2), (x, cy + body_wid/2 + tread_w/2), 1)

        body_rect = pygame.Rect(cx - body_len/2, cy - body_wid/2, body_len, body_wid)
        pygame.draw.rect(s, C_BODY, body_rect, border_radius=int(scale(3, zoom)))
        
        pygame.draw.line(s, (0,0,0), (cx-body_len/4, cy-body_wid/2), (cx-body_len/4, cy+body_wid/2), 2)
        pygame.draw.line(s, (0,0,0), (cx+body_len/4, cy-body_wid/2), (cx+body_len/4, cy+body_wid/2), 2)

        cabin_rect = pygame.Rect(cx + body_len/4, cy - body_wid/2 + 2, scale(8, zoom), scale(10, zoom))
        pygame.draw.rect(s, C_CABIN, cabin_rect)
        pygame.draw.rect(s, (100, 200, 255), (cabin_rect.left+2, cabin_rect.top+2, 2, 6))

        if self.state == "RETURNING":
            ore_rect = pygame.Rect(cx - body_len/2 + 2, cy - body_wid/3, body_len*0.6, body_wid*0.6)
            pygame.draw.rect(s, (100, 100, 0), ore_rect) 
            for _ in range(5): 
                ox = cx - body_len/3 + (_ % 3) * 6
                oy = cy + (_ % 2) * 4 - 2
                pygame.draw.circle(s, C_ORE, (int(ox), int(oy)), int(scale(3, zoom)))
                pygame.draw.circle(s, (255, 255, 255), (int(ox-1), int(oy-1)), int(scale(1, zoom))) 
        else:
            pygame.draw.rect(s, (80, 80, 80), (cx - body_len/2 + 4, cy - body_wid/3, body_len*0.5, body_wid*0.6))

        drill_len = scale(12, zoom)
        drill_start = (cx + body_len/2, cy)
        drill_end = (cx + body_len/2 + drill_len, cy)
        
        if self.state == "MINING":
            drill_offset = math.sin(pygame.time.get_ticks() * 0.02) * scale(4, zoom) 
            drill_end = (drill_end[0] + drill_offset, drill_end[1])
            if random.random() < 0.3:
                pygame.draw.circle(s, (255, 255, 0), (int(drill_end[0]), int(drill_end[1])), int(scale(4, zoom)))
        pygame.draw.polygon(s, C_DRILL, [
            (drill_start[0], drill_start[1]-4),
            (drill_start[0], drill_start[1]+4),
            drill_end
        ])
        pygame.draw.line(s, (50,50,50), drill_start, drill_end, 1)

        rot_surf = pygame.transform.rotate(s, self.angle)
        rect = rot_surf.get_rect(center=screen_pos)
        surface.blit(rot_surf, rect)
        
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

class M1A2(Unit):
    _sprite_cache = {}
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        
        self.faction = "USA" 
        if game.teams_config and team in game.teams_config:
            self.faction = game.teams_config[team].get('faction', 'USA')
          
        base_stats = M1A2_STATS
        self.attack_range = base_stats[0]          
        if self.faction == "USA": 
            self.max_hp = base_stats[2] 
            self.speed = base_stats[1]
            self.model_name = "M1A2 Abrams"
        elif self.faction == "RUSSIA": 
            self.max_hp = base_stats[2]*1.2
            self.speed = base_stats[1]*0.8
            self.attack_range = base_stats[0]*1.5            
            self.model_name = "T-14D"
        elif self.faction == "CHINA": 
            self.max_hp = base_stats[2]*0.9
            self.speed = base_stats[1]*1.3 
            self.model_name = "Type 99L"

        self.hp = self.max_hp
        self.armor=15
        self.is_mechanical = True
        self.can_attack_air = False
        self.radius = 28
        self.rect = pygame.Rect(pos.x - 28, pos.y - 28, 56, 56)
        self.load_sprites()

    def load_sprites(self):
        if self.faction == "USA":
            prefix = "unit_m1a2_usa"
        elif self.faction == "RUSSIA":
            prefix = "unit_t14_rus"
        elif self.faction == "CHINA":
            prefix = "unit_type99_chn"
        else:
            prefix = "unit_m1a2_usa"
            
        
        suffix = "grey" 
        if self.team == "player" or self.team == "team_0":
            suffix = "blue"  
        elif self.team == "enemy" or self.team == "team_1":
            suffix = "red"   
        elif self.team == "team_2":
            suffix = "green"
        elif self.team == "team_3":
            suffix = "yellow"   

        fname = f"{prefix}_{suffix}.png" 
        key = fname 
        
        if key not in M1A2._sprite_cache:
            try:
                path = resource_path(os.path.join("sprites/mbt", fname))
                img = pygame.image.load(path).convert_alpha()
                M1A2._sprite_cache[key] = img
            except Exception as e:  
                print(f"Error loading {fname}, trying default...")
                try:
                    default_path = resource_path(os.path.join("sprites/mbt", f"{prefix}.png"))
                    img = pygame.image.load(default_path).convert_alpha()
                    M1A2._sprite_cache[key] = img
                except:
                    s = pygame.Surface((40,40), pygame.SRCALPHA)
                    pygame.draw.rect(s, (255,0,0), (0,0,40,40))
                    M1A2._sprite_cache[key] = s
                
        self.original_image = M1A2._sprite_cache[key]

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 200 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return   
            
        scaled_img = scale_img(self.original_image, zoom)
        
        rot_img = pygame.transform.rotate(scaled_img, self.angle) 

        new_rect = rot_img.get_rect(center=screen_pos)
        surface.blit(rot_img, new_rect.topleft)
        
        self.draw_health_and_marker(surface, offset, zoom)
    def perform_attack(self, target):
        if self.attack_cooldown <= 0:
            dmg = DMG_M1A2 * self.tech_bonus_dmg
            shell = Projectile(self.game, self.pos, target, self.team, dmg, "tank_shell", is_aoe=True, aoe_radius=30, breakshellvalue=self.breakarmorvalue)
            shell.target_dest = vec(target.pos)
            self.game.projectiles.append(shell)
            self.attack_cooldown = 120 


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
                    elif self.target_type == 'tech_center': 
                        from base_classes import TechCenter
                        new_b = TechCenter(self.game, self.build_pos, self.team)     
                    elif self.target_type == 'shroud_gen': 
                        new_b = ShroudGen(self.game, self.build_pos, self.team)     
                    elif self.target_type == 'prototype_gen': 
                        new_b = PrototypeGen(self.game, self.build_pos, self.team) 
                    elif self.target_type == 'iron_curtain': 
                        new_b = IronCurtain(self.game, self.build_pos, self.team) 
                    elif self.target_type == 'nuke_silo': 
                        new_b = NukeSilo(self.game, self.build_pos, self.team) 
                    elif self.target_type == 'ciws': 
                        new_b = CIWS(self.game, self.build_pos, self.team)                                                                                 
                    else: new_b = FactoryBuilding(self.game, self.build_pos, self.team)
                
                if new_b: self.game.all_buildings.append(new_b)
                self.alive = False 
        self.update_rect()
    def draw(self, surface, offset, zoom):
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
        color = (200, 200, 50) 
        pygame.draw.circle(surface, color, screen_pos, scale(10, zoom))
        accent = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        pygame.draw.circle(surface, accent, screen_pos, scale(5, zoom))
        end = (screen_pos[0]+scale(8,zoom), screen_pos[1]-scale(8,zoom))
        pygame.draw.line(surface, (50,50,50), screen_pos, end, 2)
        
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

class HeavyTransport(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = HEAVYTRANSPORT_STATS[2]
        self.hp = self.max_hp
        self.speed = HEAVYTRANSPORT_STATS[1]
        self.is_air = True
        self.is_mechanical = True
        self.radius = 40
        self.rect = pygame.Rect(pos.x-40, pos.y-40, 80, 80)
        self.attack_range=HEAVYTRANSPORT_STATS[0]       
        self.cargo = []
        self.capacity = 6
        
        self.attack_range = 400
        self.damage = 30 
        self.armor=15

        self.turret_angle = 0
        self.hull_image = self.generate_hull_image()
        self.turret_image = self.generate_turret_image()
    def generate_hull_image(self):

        w, h = 110, 150
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        w, h = 110, 150 
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w//2, h//2
        
        C_HULL_BASE = (80, 90, 100)     
        C_HULL_DARK = (50, 60, 70)      
        C_HULL_LIGHT = (130, 140, 150)  
        C_INTAKE = (30, 30, 35)         
        C_ENGINE = (60, 180, 255)       
        C_WARNING = (200, 180, 50)      
        
        body_pts = [
            (35, 10), (75, 10),   
            (95, 30), (95, 120),  
            (75, 145), (35, 145), 
            (15, 120), (15, 30)   
        ]
        pygame.draw.polygon(surf, C_HULL_BASE, body_pts)
        
        spine_rect = pygame.Rect(40, 15, 30, 125)
        pygame.draw.rect(surf, C_HULL_LIGHT, spine_rect)
        for i in range(10):
            y = 25 + i * 12
            pygame.draw.line(surf, C_HULL_DARK, (40, y), (70, y), 1)

        engines = [
            (5, 25, 20, 30),   
            (85, 25, 20, 30),  
            (5, 105, 20, 30),  
            (85, 105, 20, 30)  
        ]
        
        for ex, ey, ew, eh in engines:
            pygame.draw.rect(surf, C_HULL_DARK, (ex, ey, ew, eh), border_radius=4)
            for j in range(4):
                ly = ey + 5 + j * 6
                pygame.draw.line(surf, (20,20,20), (ex+4, ly), (ex+ew-4, ly), 2)
            pygame.draw.circle(surf, C_ENGINE, (ex+ew//2, ey+eh//2), 4)

        cockpit_pts = [(45, 5), (65, 5), (60, 15), (50, 15)]
        pygame.draw.polygon(surf, (20, 40, 50), cockpit_pts) 
        pygame.draw.line(surf, C_HULL_LIGHT, (45, 5), (50, 15), 1) 

        pygame.draw.polygon(surf, C_HULL_BASE, [(15, 60), (0, 70), (0, 90), (15, 80)])
        pygame.draw.polygon(surf, C_HULL_BASE, [(95, 60), (110, 70), (110, 90), (95, 80)])
        pygame.draw.circle(surf, (255, 0, 0), (2, 80), 2)   
        pygame.draw.circle(surf, (0, 255, 0), (108, 80), 2) 

        strip_y = 135
        pygame.draw.rect(surf, C_WARNING, (35, strip_y, 40, 6))
        for k in range(5):
            sx = 35 + k * 8
            pygame.draw.line(surf, (0,0,0), (sx, strip_y), (sx+4, strip_y+6), 2)
            
        pygame.draw.rect(surf, (20,20,20), (45, 100, 20, 10))
        pygame.draw.line(surf, (60,60,60), (45, 105), (65, 105), 1)

        return surf
    def generate_turret_image(self):

        s = pygame.Surface((60, 40), pygame.SRCALPHA) 
        cx, cy = 20, 20
        
        pygame.draw.line(s, (20, 20, 20), (cx, cy), (cx+30, cy), 5)
        pygame.draw.circle(s, (60, 60, 65), (cx, cy), 10)
        pygame.draw.circle(s, (30, 30, 30), (cx, cy), 10, 2)
        
        return s

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 200 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return        
        shadow_dist = scale(50, zoom)
        shadow_w = scale(90, zoom)
        shadow_h = scale(140, zoom)
        shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0,0,0,80), (0,0,shadow_w, shadow_h))
        
        rot_shadow = pygame.transform.rotate(shadow_surf, self.angle - 90)
        shadow_rect = rot_shadow.get_rect(center=(screen_pos[0]+shadow_dist, screen_pos[1]+shadow_dist))
        surface.blit(rot_shadow, shadow_rect)
        
        scaled_hull = scale_img(self.hull_image, zoom)
        rot_hull = pygame.transform.rotate(scaled_hull, self.angle - 90) 
        
        hull_rect = rot_hull.get_rect(center=screen_pos)
        surface.blit(rot_hull, hull_rect)
        
        scaled_turret = scale_img(self.turret_image, zoom)
        rot_turret = pygame.transform.rotate(scaled_turret, self.turret_angle)
        
        turret_rect = rot_turret.get_rect(center=screen_pos)
        surface.blit(rot_turret, turret_rect)
        
        self.draw_health_and_marker(surface, offset, zoom)
    def update(self):
        super().update()
        
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        if not self.game.is_online or self.game.my_role == "HOST":
            target = self.target_entity or self.find_nearest_enemy()
            
            if target and target.alive:
                diff = target.pos - self.pos
                self.turret_angle = math.degrees(math.atan2(-diff.y, diff.x))
                if self.pos.distance_to(target.pos) < self.attack_range:
                    if self.attack_cooldown <= 0:
                        self.perform_attack(target)
            else:
                self.turret_angle = self.angle

    def perform_attack(self, target):
        if self.attack_cooldown > 0: return

        barrel_vec = vec(30, 0).rotate(-self.turret_angle) 
        fire_pos = self.pos + barrel_vec

        p = Projectile(self.game, fire_pos, target, self.team, self.damage, "heavy")
        self.game.projectiles.append(p)
        
        self.attack_cooldown = 30
    def load_units(self):
        current_load = sum([c['size'] for c in self.cargo])
        if current_load >= self.capacity:
            self.game.particles.add(FloatingText(self.pos, "FULL!", RED))
            return

        
        for u in self.game.all_units[:]:
            if u == self: continue
            if u.team != self.team: continue
            if not u.alive: continue
            if u.is_air: continue 
            
            if self.pos.distance_to(u.pos) < 100:
                size = 1
                if isinstance(u, (M1A2, Type99, TerminatorIFV, ShockwaveVehicle)): size = 2
                if isinstance(u, MCV): size = 4
                
                if current_load + size <= self.capacity:
                    self.cargo.append({'unit': u, 'size': size})
                    self.game.all_units.remove(u)
                    current_load += size
                    
                    self.game.particles.add(FloatingText(self.pos, "LOADED", GREEN_HAT))
                    
                    if current_load >= self.capacity: break

    def unload_units(self):
        if not self.cargo: return
        
        for item in self.cargo:
            u = item['unit']
            
            offset = vec(random.randint(-60, 60), random.randint(-60, 60))
            u.pos = self.pos + offset
            
            u.target_pos = None
            u.target_entity = None
            u.ai_mode = "GUARD"
            
            self.game.all_units.append(u)
        
        self.cargo = []
        self.game.particles.add(FloatingText(self.pos, "UNLOADED", GREEN_HAT))
    def die(self):
        super().die()
        self.cargo = []

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
        rotated_img = pygame.transform.rotate(scaled_img, self.angle)
        screen_pos = to_screen(self.pos, offset, zoom)
        new_rect = rotated_img.get_rect(center=screen_pos)
        surface.blit(rotated_img, new_rect.topleft)
        self.draw_health_and_marker(surface, offset, zoom)
class HeavyMech(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = MECH_STATS[2]
        self.hp = self.max_hp

        
        self.speed = MECH_STATS[1]
        self.attack_range = MECH_STATS[0]
        self.damage = DMG_MECH
        self.armor=30
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
                    Projectile(self.game, self.pos + offset, target, self.team, self.damage*2,"rocket", breakshellvalue=self.breakarmorvalue)
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
        rotated_image = pygame.transform.rotate(scaled_img, self.angle)
        

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
    
class MercenaryFactory(Entity):
    def __init__(self, game, pos):
        super().__init__(game, pos, "neutral")
        self.hp = 1500
        self.max_hp = 1500
        self.radius = 60
        self.rect = pygame.Rect(pos.x - 60, pos.y - 60, 120, 120)
        self.armor=15
        self.is_mechanical = True
        self.spawn_timer = 0
        self.capture_progress = 0
        self.capturing_team = None
        self.max_capture = OIL_CAPTURE_TIME

    def update(self):
        if self.team != "neutral":
            self.spawn_timer += 1
            if self.spawn_timer > MERC_FACTORY_INTERVAL:
                self.spawn_timer = 0
                spawn_pos = self.pos + vec(0, 70)
                self.game.all_units.append(ArmoredCar(self.game, spawn_pos, self.team))
                self.game.particles.add(FloatingText(self.pos, "+TANK", YELLOW))

        capturer = None
        min_dist = 100
        for u in self.game.all_units:
            if u.alive and not u.is_air:
                dist = self.pos.distance_to(u.pos)
                if dist < min_dist:
                    capturer = u
                    break
        if capturer:
            if capturer.team != self.team:
                if self.capturing_team != capturer.team:
                    self.capturing_team = capturer.team
                    self.capture_progress = 0 
                self.capture_progress += 1
                if self.capture_progress >= self.max_capture:
                    self.team = capturer.team
                    self.game.particles.add(FloatingText(self.pos, "FACTORY CAPTURED!",TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"]) ))
            else: self.capture_progress = 0
        else: self.capture_progress = max(0, self.capture_progress - 0.5)

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
        w = scale(90, zoom)        
        l = scale(110, zoom)       
        h_visual = scale(35, zoom) 
        
        C_CONCRETE_TOP  = (110, 110, 115) 
        C_CONCRETE_SIDE = (70, 70, 75)    
        C_CONCRETE_BASE = (90, 90, 95)    
        C_DOOR_DARK     = (40, 40, 45)    
        C_DOOR_SLAT     = (60, 60, 65)    
        C_HAZARD        = (220, 180, 20)  
        C_VENT          = (50, 50, 55)    
        C_SHADOW        = (0, 0, 0, 90)   
        
        BLUE = (0, 150, 255)
        RED = (220, 60, 60)
        NEUTRAL = (120, 120, 120)
        
        team_color =TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])

        shadow_offset = scale(12, zoom)
        s_surf = pygame.Surface((l + shadow_offset*2, w + shadow_offset*2), pygame.SRCALPHA)
        pygame.draw.rect(s_surf, C_SHADOW, (shadow_offset, shadow_offset, l, w), border_radius=int(scale(5, zoom)))
        surface.blit(s_surf, (cx - l//2, cy - w//2))


        base_rect = pygame.Rect(cx - l//2 - scale(5, zoom), cy - w//2 - scale(5, zoom), 
                                l + scale(10, zoom), w + scale(10, zoom))
        
        pygame.draw.rect(surface, C_CONCRETE_BASE, base_rect)
        pygame.draw.rect(surface, (130, 130, 135), base_rect, 2)
        
        door_w = scale(50, zoom)
        door_h = scale(20, zoom)
        door_x = cx - door_w // 2
        door_y = cy + w // 2 - door_h 
        
        pygame.draw.rect(surface, (30, 30, 30), (door_x, door_y + scale(5, zoom), door_w, scale(15, zoom)))
        for i in range(0, int(door_w), int(scale(10, zoom))):
            p1 = (door_x + i, door_y + scale(5, zoom))
            p2 = (door_x + i + scale(5, zoom), door_y + scale(20, zoom))
            if p2[0] < door_x + door_w:
                pygame.draw.polygon(surface, C_HAZARD, [
                    p1, (p1[0]+scale(3, zoom), p1[1]), 
                    (p2[0]+scale(3, zoom), p2[1]), p2
                ])

        
        roof_y_center = cy - h_visual // 2 
        roof_rect = pygame.Rect(cx - l//2, roof_y_center - w//2, l, w)
        
        front_wall_rect = pygame.Rect(roof_rect.left, roof_rect.bottom, roof_rect.width, h_visual)
        pygame.draw.rect(surface, C_CONCRETE_SIDE, front_wall_rect)
        
        gate_rect = pygame.Rect(door_x, roof_rect.bottom, door_w, h_visual - scale(2, zoom))
        pygame.draw.rect(surface, C_DOOR_DARK, gate_rect)
        for i in range(0, int(gate_rect.height), int(scale(4, zoom))):
            pygame.draw.line(surface, C_DOOR_SLAT, (gate_rect.left, gate_rect.top + i), (gate_rect.right, gate_rect.top + i), 1)
        pygame.draw.rect(surface, (50, 50, 50), gate_rect, 2)
        
        pygame.draw.rect(surface, C_CONCRETE_TOP, roof_rect)
        pygame.draw.rect(surface, (150, 150, 160), roof_rect, 1) 

        
        stripe_w = scale(15, zoom)
        pygame.draw.rect(surface, team_color, (cx - l//2 + scale(15, zoom), roof_rect.top, stripe_w, roof_rect.height))
        
        current_time = time.time()
        fan_positions = [
            (cx + scale(20, zoom), roof_rect.centery - scale(15, zoom)),
            (cx + scale(20, zoom), roof_rect.centery + scale(15, zoom))
        ]
        
        fan_radius = scale(10, zoom)
        for fx, fy in fan_positions:
            pygame.draw.circle(surface, C_VENT, (int(fx), int(fy)), int(fan_radius))
            pygame.draw.circle(surface, (80, 80, 85), (int(fx), int(fy)), int(fan_radius), 1)
            angle_offset = current_time * 5
            for i in range(3):
                angle = angle_offset + i * (2 * math.pi / 3)
                end_x = fx + math.cos(angle) * fan_radius * 0.8
                end_y = fy + math.sin(angle) * fan_radius * 0.8
                pygame.draw.line(surface, (20, 20, 20), (fx, fy), (end_x, end_y), 2)
        
        for i in range(3):
            lx = cx - scale(10, zoom) + i * scale(10, zoom)
            pygame.draw.line(surface, (90, 90, 95), (lx, roof_rect.top + scale(5, zoom)), (lx, roof_rect.bottom - scale(5, zoom)), 2)


        if self.capture_progress > 0:
            bar_w = scale(50, zoom)
            bar_h = scale(6, zoom)
            pct = min(1.0, self.capture_progress / self.max_capture)
            
            if self.capturing_team == "player": bar_c = BLUE
            elif self.capturing_team == "enemy": bar_c = RED
            else: bar_c = (200, 200, 0)
            
            bar_x = cx - bar_w // 2
            bar_y = roof_rect.top - scale(20, zoom)
            
            pygame.draw.rect(surface, (0, 0, 0), (bar_x-1, bar_y-1, bar_w+2, bar_h+2)) 
            pygame.draw.rect(surface, (255, 255, 255), (bar_x, bar_y, bar_w, bar_h))   
            pygame.draw.rect(surface, bar_c, (bar_x, bar_y, bar_w * pct, bar_h))       

        self.draw_health_and_marker(surface, offset, zoom)



class BaseBuilding(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "base")
        self.hp = 5000 
        self.max_hp = 5000
        self.radius = 70 
        self.armor=30
        self.rect = pygame.Rect(pos.x - 70, pos.y - 70, 140, 140)
    def update(self):
        return super().update()    
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        faction = "CHINA" 
        if self.team == "player": faction = self.game.my_faction
        elif self.team == "enemy": faction = self.game.enemy_faction
        
        base_color = (100, 100, 100)
        if faction == "CHINA": base_color = (150, 60, 60) 
        elif faction == "USA": base_color = (60, 80, 150) 
        elif faction == "RUSSIA": base_color = (80, 100, 60) 
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
        base_w = scale(120, zoom)    
        bunker_w = scale(70, zoom)   
        core_w = scale(35, zoom)     
        
        h_base = scale(15, zoom)     
        h_bunker = scale(30, zoom)   
        
        C_CONCRETE_TOP = (100, 100, 105)
        C_CONCRETE_SIDE = (60, 60, 65)
        C_METAL_DARK = (40, 40, 45)
        C_SHADOW = (0, 0, 0, 100)
        

        team_color = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        
        shadow_offset = scale(15, zoom)
        s_surf = pygame.Surface((base_w + shadow_offset, base_w + shadow_offset), pygame.SRCALPHA)
        shadow_rect = pygame.Rect(shadow_offset, shadow_offset, base_w, base_w)
        pygame.draw.rect(s_surf, C_SHADOW, shadow_rect, border_radius=int(scale(10, zoom)))
        surface.blit(s_surf, (cx - base_w//2, cy - base_w//2))

        
        base_rect_bottom = pygame.Rect(cx - base_w//2, cy - base_w//2, base_w, base_w)
        base_top_y = cy - h_base
        
        pygame.draw.rect(surface, C_CONCRETE_SIDE, (cx - base_w//2, base_top_y - base_w//2, base_w, base_w + h_base))
        
        base_rect_top = pygame.Rect(cx - base_w//2, base_top_y - base_w//2, base_w, base_w)
        pygame.draw.rect(surface, C_CONCRETE_TOP, base_rect_top)
        
        pygame.draw.rect(surface, C_METAL_DARK, base_rect_top, width=int(scale(6, zoom)))
        corner_offset = scale(8, zoom)
        rivet_r = scale(3, zoom)
        corners = [
            (base_rect_top.left + corner_offset, base_rect_top.top + corner_offset),
            (base_rect_top.right - corner_offset, base_rect_top.top + corner_offset),
            (base_rect_top.left + corner_offset, base_rect_top.bottom - corner_offset),
            (base_rect_top.right - corner_offset, base_rect_top.bottom - corner_offset)
        ]
        for cp in corners:
            pygame.draw.circle(surface, (150, 150, 150), (int(cp[0]), int(cp[1])), int(rivet_r))

        
        bunker_top_y = base_top_y - h_bunker
        
        bunker_rect_side = pygame.Rect(cx - bunker_w//2, bunker_top_y - bunker_w//2, bunker_w, bunker_w + h_bunker)
        pygame.draw.rect(surface, (50, 55, 60), bunker_rect_side) 
        
        bunker_rect_top = pygame.Rect(cx - bunker_w//2, bunker_top_y - bunker_w//2, bunker_w, bunker_w)
        pygame.draw.rect(surface, (120, 125, 130), bunker_rect_top) 
        
        stripe_w = scale(8, zoom)
        pygame.draw.rect(surface, team_color, (bunker_rect_top.left + stripe_w, bunker_rect_top.top, stripe_w, bunker_w))
        pygame.draw.rect(surface, team_color, (bunker_rect_top.right - stripe_w*2, bunker_rect_top.top, stripe_w, bunker_w))

        
        core_y = bunker_top_y
        
        pygame.draw.rect(surface, (20, 20, 20), (cx - core_w//2, core_y - core_w//2, core_w, core_w))
        
        pulse = (math.sin(time.time() * 5) + 1) / 2  
        
        r, g, b = team_color
        bright_color = (min(255, r + 100*pulse), min(255, g + 100*pulse), min(255, b + 100*pulse))
        
        inner_core_w = core_w - scale(8, zoom)
        pygame.draw.rect(surface, bright_color, (cx - inner_core_w//2, core_y - inner_core_w//2, inner_core_w, inner_core_w))
        
        glow_size = scale(50, zoom)
        glow_surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
        glow_alpha = 50 + int(50 * pulse) 
        pygame.draw.circle(glow_surf, (r, g, b, glow_alpha), (glow_size//2, glow_size//2), glow_size//2)
        surface.blit(glow_surf, (cx - glow_size//2, core_y - glow_size//2))

        ant_x = bunker_rect_top.left + scale(4, zoom)
        ant_y = bunker_rect_top.top + scale(4, zoom)
        ant_h = scale(25, zoom)
        pygame.draw.line(surface, (200, 200, 200), (ant_x, ant_y), (ant_x, ant_y - ant_h), 2)
        if int(time.time() * 2) % 2 == 0:
            pygame.draw.circle(surface, (255, 0, 0), (int(ant_x), int(ant_y - ant_h)), 2)

        self.draw_health_and_marker(surface, offset, zoom, -scale(80, zoom))

    def undeploy(self):
        if self.game.is_online and self.game.my_role == "CLIENT":
            return

        from units import MCV
        new_mcv = MCV(self.game, self.pos, self.team)
        new_mcv.hp = self.hp
        
        
        self.game.all_units.append(new_mcv)
        
        self.alive = False 
        self.production_queue = []
        self.current_production = None
class FactoryBuilding(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "factory")
        self.hp = 800
        self.max_hp = 800
        self.armor=15
        self.radius = 15
        self.rect = pygame.Rect(pos.x - 60, pos.y - 60, 120, 120)
    def update(self):
        return super().update()


    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        margin = 200 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return              
        w = scale(100, zoom)       
        l = scale(80, zoom)        
        h_visual = scale(30, zoom) 
        
        C_WALL_DARK   = (70, 70, 75)     
        C_WALL_LIGHT  = (100, 100, 105)  
        C_ROOF_SLOPE  = (80, 80, 85)     
        C_ROOF_GLASS  = (40, 50, 60)     
        C_CHIMNEY     = (60, 40, 30)     
        C_ACCENT      = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        
        shadow_offset = scale(10, zoom)
        s_surf = pygame.Surface((w + shadow_offset*2, l + shadow_offset*2 + scale(50, zoom)), pygame.SRCALPHA)
        
        pygame.draw.rect(s_surf, (0,0,0,80), (shadow_offset, shadow_offset + scale(20, zoom), w, l))
        
        chimney_x_rel = scale(15, zoom) 
        chimney_shadow_h = scale(80, zoom) 
        pygame.draw.rect(s_surf, (0,0,0,60), (chimney_x_rel, shadow_offset, scale(15, zoom), chimney_shadow_h))
        
        surface.blit(s_surf, (cx - w//2, cy - l//2))

        base_y = cy + l//2
        roof_y = base_y - h_visual 
        
        rect_main = pygame.Rect(cx - w//2, roof_y, w, l) 
        
        pygame.draw.rect(surface, C_WALL_DARK, (cx - w//2, base_y - scale(5, zoom), w, scale(10, zoom)))
        
        
        num_teeth = 4
        tooth_w = w / num_teeth
        
        start_x = cx - w//2
        
        for i in range(num_teeth):
            t_x1 = start_x + i * tooth_w
            t_x2 = start_x + (i + 1) * tooth_w
            
            slope_w = tooth_w * 0.7
            glass_w = tooth_w * 0.3
            
            slope_rect = pygame.Rect(t_x1, roof_y - l//2, slope_w, l) 
            pygame.draw.rect(surface, C_ROOF_SLOPE, slope_rect)
            pygame.draw.rect(surface, (90, 90, 95), slope_rect, 1) 
            
            glass_rect = pygame.Rect(t_x1 + slope_w, roof_y - l//2, glass_w, l)
            pygame.draw.rect(surface, C_ROOF_GLASS, glass_rect)
            
            pygame.draw.line(surface, (60, 70, 80), (glass_rect.left, glass_rect.top + l*0.3), (glass_rect.right, glass_rect.top + l*0.3), 1)
            pygame.draw.line(surface, (60, 70, 80), (glass_rect.left, glass_rect.top + l*0.7), (glass_rect.right, glass_rect.top + l*0.7), 1)

        chim_w = scale(16, zoom)
        chim_h = scale(60, zoom)
        chim_x = cx - w//2 + scale(15, zoom)
        chim_base_y = cy  
        chim_top_y = chim_base_y - chim_h
        
        pygame.draw.rect(surface, C_CHIMNEY, (chim_x - chim_w//2, chim_top_y, chim_w, chim_h))
        for i in range(0, int(chim_h), int(scale(8, zoom))):
            pygame.draw.line(surface, (50, 30, 20), (chim_x - chim_w//2, chim_top_y + i), (chim_x + chim_w//2, chim_top_y + i), 1)
        
        pygame.draw.rect(surface, (40, 20, 10), (chim_x - chim_w//2 - 2, chim_top_y, chim_w + 4, scale(6, zoom)))
        pygame.draw.rect(surface, (10, 10, 10), (chim_x - chim_w//2 + 2, chim_top_y + 1, chim_w - 4, scale(3, zoom)))
        
        current_time = time.time()
        for i in range(4):
            t_offset = i * 1.5 
            cycle = (current_time + t_offset) % 4
            
            dy = cycle * scale(30, zoom) 
            dx = math.sin(current_time * 2 + i) * scale(8, zoom) + (cycle * scale(10, zoom)) 
            
            radius = scale(6 + cycle * 3, zoom)
            alpha = max(0, 150 - cycle * 40)
            
            particle_pos = (int(chim_x + dx), int(chim_top_y - dy - scale(5, zoom)))
            s_smoke = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
            pygame.draw.circle(s_smoke, (30, 30, 30, int(alpha)), (radius, radius), radius)
            surface.blit(s_smoke, (particle_pos[0]-radius, particle_pos[1]-radius))


        door_w = scale(40, zoom)
        door_h = scale(15, zoom)
        door_rect = pygame.Rect(cx - door_w//2, base_y - door_h, door_w, door_h)
        
        pygame.draw.rect(surface, C_ACCENT, (door_rect.left - 2, door_rect.top - 2, door_rect.width + 4, door_rect.height + 4))
        pygame.draw.rect(surface, (30, 30, 35), door_rect)
        for i in range(0, int(door_h), int(scale(3, zoom))):
            pygame.draw.line(surface, (50, 50, 55), (door_rect.left, door_rect.top + i), (door_rect.right, door_rect.top + i), 1)



        self.draw_health_and_marker(surface, offset, zoom, -65)
class RadarBuilding(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "radar")
        self.hp = 500
        self.max_hp = 500
        self.armor=5
        self.radius = 40
        self.rect = pygame.Rect(pos.x - 40, pos.y - 40, 80, 80)
        self.angle = 0

    def update(self):
        self.angle += 1.5


    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        margin = 300 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return              
        truck_len = scale(80, zoom)
        truck_wid = scale(35, zoom)
        
        radar_w = scale(60, zoom) 
        radar_h = scale(10, zoom) 
        
        C_CHASSIS = (55, 65, 50)    
        C_CABIN = (70, 80, 65)      
        C_RADAR_FACE = (40, 50, 40) 
        C_RADAR_BACK = (60, 70, 55) 
        C_TIRE = (20, 20, 20)
        C_SUPPORT = (30, 35, 30)    
        C_BOX = (65, 75, 60)        
        
        surf_size = int(truck_len * 1.5)
        surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        scx, scy = surf_size // 2, surf_size // 2
        
        wheel_r = scale(10, zoom)
        wheel_w = scale(6, zoom)
        axle_positions = [-0.35, -0.15, 0.15, 0.35] 
        
        for pos_factor in axle_positions:
            wx = scx + truck_len * pos_factor
            pygame.draw.rect(surf, C_TIRE, (wx - wheel_r, scy - truck_wid//2 - wheel_w, wheel_r*2, wheel_w))
            pygame.draw.rect(surf, C_TIRE, (wx - wheel_r, scy + truck_wid//2, wheel_r*2, wheel_w))
            pygame.draw.circle(surf, (40,40,40), (int(wx), int(scy - truck_wid//2 - wheel_w//2)), int(scale(3, zoom)))
            pygame.draw.circle(surf, (40,40,40), (int(wx), int(scy + truck_wid//2 + wheel_w//2)), int(scale(3, zoom)))

        leg_len = scale(12, zoom)
        pygame.draw.line(surf, C_SUPPORT, (scx - truck_len*0.4, scy - truck_wid*0.4), (scx - truck_len*0.4, scy - truck_wid*0.8), 3)
        pygame.draw.circle(surf, C_SUPPORT, (int(scx - truck_len*0.4), int(scy - truck_wid*0.8)), int(scale(4, zoom))) 
        pygame.draw.line(surf, C_SUPPORT, (scx - truck_len*0.4, scy + truck_wid*0.4), (scx - truck_len*0.4, scy + truck_wid*0.8), 3)
        pygame.draw.circle(surf, C_SUPPORT, (int(scx - truck_len*0.4), int(scy + truck_wid*0.8)), int(scale(4, zoom)))
        
        rect_body = pygame.Rect(scx - truck_len//2, scy - truck_wid//2, truck_len, truck_wid)
        pygame.draw.rect(surf, C_CHASSIS, rect_body)
        
        cab_len = truck_len * 0.2
        rect_cab = pygame.Rect(scx + truck_len//2 - cab_len, scy - truck_wid//2, cab_len, truck_wid)
        pygame.draw.rect(surf, C_CABIN, rect_cab)
        pygame.draw.rect(surf, (30, 40, 50), (rect_cab.right - scale(5, zoom), rect_cab.top + scale(3, zoom), scale(3, zoom), scale(10, zoom)))
        pygame.draw.rect(surf, (30, 40, 50), (rect_cab.right - scale(5, zoom), rect_cab.bottom - scale(13, zoom), scale(3, zoom), scale(10, zoom)))

        box_w = scale(5, zoom)
        for i in range(3):
            bx = scx - truck_len*0.3 + i * scale(15, zoom)
            pygame.draw.rect(surf, C_BOX, (bx, scy - truck_wid//2 - box_w, scale(12, zoom), box_w))
            pygame.draw.rect(surf, C_BOX, (bx, scy + truck_wid//2, scale(12, zoom), box_w))


        
        
        surface.blit(surf, (cx - scx, cy - scy)) 
        
        
        radar_surf_size = int(radar_w * 1.5)
        r_surf = pygame.Surface((radar_surf_size, radar_surf_size), pygame.SRCALPHA)
        rcx, rcy = radar_surf_size // 2, radar_surf_size // 2
        
        base_r = scale(18, zoom)
        pygame.draw.circle(r_surf, C_CHASSIS, (rcx, rcy), base_r)
        pygame.draw.circle(r_surf, (40, 50, 40), (rcx, rcy), base_r, 2) 
        
        
        strut_len = scale(20, zoom)
        pygame.draw.line(r_surf, C_SUPPORT, (rcx, rcy), (rcx - strut_len, rcy), 4)
        pygame.draw.line(r_surf, C_SUPPORT, (rcx, rcy - scale(10, zoom)), (rcx - strut_len, rcy), 2)
        pygame.draw.line(r_surf, C_SUPPORT, (rcx, rcy + scale(10, zoom)), (rcx - strut_len, rcy), 2)
        
        pygame.draw.rect(r_surf, C_BOX, (rcx - scale(15, zoom), rcy - scale(15, zoom), scale(10, zoom), scale(30, zoom)))
        
        rect_face = pygame.Rect(rcx - scale(2, zoom), rcy - radar_w//2, scale(6, zoom), radar_w)
        pygame.draw.rect(r_surf, C_RADAR_BACK, rect_face) 
        
        front_edge_x = rect_face.right
        pygame.draw.line(r_surf, (80, 90, 80), (front_edge_x, rect_face.top), (front_edge_x, rect_face.bottom), 2) 
        
        pygame.draw.line(r_surf, C_SUPPORT, (rcx, rcy - radar_w//2), (rcx + scale(10, zoom), rcy - radar_w//2), 2)
        
        dish_pos = (rcx - scale(10, zoom), rcy + radar_w//2 + scale(5, zoom))
        pygame.draw.circle(r_surf, C_RADAR_BACK, dish_pos, scale(8, zoom)) 
        pygame.draw.circle(r_surf, (30, 40, 30), dish_pos, scale(6, zoom)) 
        pygame.draw.line(r_surf, C_SUPPORT, (rcx, rcy), dish_pos, 2) 

        rotated_radar = pygame.transform.rotate(r_surf, -self.angle)
        radar_rect = rotated_radar.get_rect(center=screen_pos)
        
        shadow_surf = pygame.transform.rotate(r_surf, -self.angle)
        shadow_surf.fill((0, 0, 0, 60), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(shadow_surf, (radar_rect.x + scale(5, zoom), radar_rect.y + scale(5, zoom)))
        
        surface.blit(rotated_radar, radar_rect)

        if self.alive:
            scan_len = scale(200, zoom)
            scan_angle = math.radians(self.angle)
            p1 = screen_pos
            p2 = (cx + math.cos(scan_angle - 0.2) * scan_len, cy + math.sin(scan_angle - 0.2) * scan_len)
            p3 = (cx + math.cos(scan_angle + 0.2) * scan_len, cy + math.sin(scan_angle + 0.2) * scan_len)
            
            scan_s = pygame.Surface((scan_len*2, scan_len*2), pygame.SRCALPHA)
            local_c = (scan_len, scan_len)
            local_p2 = (scan_len + math.cos(-0.2)*scan_len, scan_len + math.sin(-0.2)*scan_len)
            local_p3 = (scan_len + math.cos(0.2)*scan_len, scan_len + math.sin(0.2)*scan_len)
            
            alpha = int(50 + 30 * math.sin(pygame.time.get_ticks() * 0.005))
            pygame.draw.polygon(scan_s, (0, 255, 0, alpha), [local_c, local_p2, local_p3])
            
            scan_rot = pygame.transform.rotate(scan_s, -self.angle)
            scan_rect = scan_rot.get_rect(center=screen_pos)
            surface.blit(scan_rot, scan_rect)

        self.draw_health_and_marker(surface, offset, zoom, -scale(60, zoom))
class PowerPlant(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team,"power_plant")
        self.b_type = "power_plant"
        self.hp = POWER_PLANT_HP
        self.max_hp = POWER_PLANT_HP
        self.armor=5
        self.radius = 35
        self.rect = pygame.Rect(pos.x - 35, pos.y - 35, 70, 70)
        self.power_usage = 0 
        
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
        VIEW_ANGLE_FACTOR = 0.6 
        
        tower_radius_base = scale(35, zoom)  
        tower_radius_top = scale(25, zoom)   
        tower_height_visual = scale(60, zoom) * VIEW_ANGLE_FACTOR 
        
        reactor_radius = scale(18, zoom)
        
        C_SHADOW = (0, 0, 0, 80)        
        C_CONCRETE_DARK = (100, 100, 110) 
        C_CONCRETE_MID = (160, 160, 170)  
        C_CONCRETE_LIGHT = (210, 210, 220)
        C_HOLE = (40, 40, 45)           
        C_REACTOR = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])     
        C_SYMBOL = (220, 200, 0)        
        
        shadow_offset_x = scale(15, zoom)
        shadow_offset_y = scale(15, zoom)
        
        shadow_surf = pygame.Surface((scale(150, zoom), scale(150, zoom)), pygame.SRCALPHA)
        shadow_center = (scale(75, zoom), scale(75, zoom))
        
        pygame.draw.circle(shadow_surf, C_SHADOW, shadow_center, tower_radius_base)
        r_shadow_pos = (shadow_center[0] + scale(40, zoom), shadow_center[1] + scale(10, zoom))
        pygame.draw.circle(shadow_surf, C_SHADOW, r_shadow_pos, reactor_radius)
        
        surface.blit(shadow_surf, (cx - shadow_center[0] + shadow_offset_x, cy - shadow_center[1] + shadow_offset_y))

        base_rect = pygame.Rect(cx - tower_radius_base - scale(10, zoom), 
                            cy - tower_radius_base - scale(10, zoom),
                            scale(100, zoom), scale(90, zoom))
        pygame.draw.rect(surface, (90, 90, 95), base_rect, border_radius=int(scale(5, zoom)))

        
        base_y = cy
        pygame.draw.circle(surface, C_CONCRETE_DARK, (cx, base_y), tower_radius_base)
        pygame.draw.circle(surface, (50,50,50), (cx, base_y), tower_radius_base, 1) 
        
        top_y = cy - tower_height_visual
        
        points = [
            (cx - tower_radius_base, base_y), 
            (cx - tower_radius_top, top_y),   
            (cx + tower_radius_top, top_y),   
            (cx + tower_radius_base, base_y)  
        ]
        pygame.draw.polygon(surface, C_CONCRETE_MID, points)
        
        pygame.draw.circle(surface, C_CONCRETE_LIGHT, (cx, int(top_y)), tower_radius_top)
        pygame.draw.circle(surface, (100,100,100), (cx, int(top_y)), tower_radius_top, 1)
        
        hole_radius = tower_radius_top - scale(4, zoom)
        pygame.draw.circle(surface, C_HOLE, (cx, int(top_y)), hole_radius)
        
        pygame.draw.circle(surface, (20, 20, 25), (cx - scale(2, zoom), int(top_y) - scale(2, zoom)), hole_radius*0.9)


        rx = cx + scale(40, zoom)
        ry = cy + scale(10, zoom)
        r_top_y = ry - scale(15, zoom) * VIEW_ANGLE_FACTOR 
        
        pygame.draw.circle(surface, C_CONCRETE_DARK, (rx, ry), reactor_radius)
        
        r_points = [
            (rx - reactor_radius, ry),
            (rx - reactor_radius, r_top_y),
            (rx + reactor_radius, r_top_y),
            (rx + reactor_radius, ry)
        ]
        pygame.draw.polygon(surface, C_CONCRETE_MID, r_points)
        
        pygame.draw.circle(surface, C_REACTOR, (rx, int(r_top_y)), reactor_radius)
        
        highlight_offset = scale(6, zoom)
        pygame.draw.circle(surface, (230, 230, 240), (rx - highlight_offset, int(r_top_y) - highlight_offset), reactor_radius * 0.4)
        
        icon_x, icon_y = rx, int(r_top_y)
        icon_r = scale(8, zoom)
        pygame.draw.circle(surface, C_SYMBOL, (icon_x, icon_y), icon_r)
        for i in range(3):
            angle_rad = math.radians(i * 120 - 30)
            end_x = icon_x + math.cos(angle_rad) * icon_r
            end_y = icon_y + math.sin(angle_rad) * icon_r
            pygame.draw.line(surface, (0,0,0), (icon_x, icon_y), (end_x, end_y), int(scale(3, zoom)))
        pygame.draw.circle(surface, (0,0,0), (icon_x, icon_y), int(scale(2, zoom)))


        current_time = time.time()
        steam_base_y = top_y
        for i in range(3):
            offset_val = (current_time * 2 + i) 
            steam_dy = (offset_val % 1.0) * scale(60, zoom) 
            steam_alpha = 150 * (1 - (steam_dy / scale(60, zoom))) 
            
            steam_dx = math.sin(current_time * 3 + i) * scale(5, zoom)
            
            steam_r = scale(10 + i*2, zoom) 
            
            s_surf = pygame.Surface((steam_r*2, steam_r*2), pygame.SRCALPHA)
            pygame.draw.circle(s_surf, (255, 255, 255, int(steam_alpha)), (steam_r, steam_r), steam_r)
            
            dest_x = cx - steam_r + steam_dx
            dest_y = steam_base_y - steam_r - steam_dy
            surface.blit(s_surf, (dest_x, dest_y))

        self.draw_health_and_marker(surface, offset, zoom)
class MiningRig(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "mining")
        self.hp = 600
        self.max_hp = 600
        self.radius = 50
        self.armor=15
        self.rect = pygame.Rect(pos.x - 50, pos.y - 50, 100, 100)
        self.spawn_timer = 0
        self.harvester_count = 0
        self.max_harvesters = 2
        self.harvesters = [] 

    def update(self):

        self.harvesters = [h for h in self.harvesters if h.alive]

        if len(self.harvesters) < self.max_harvesters:
            self.spawn_timer += 1
            if self.spawn_timer > 600:
                self.spawn_timer = 0
                self.spawn_harvester()
        else:
            self.spawn_timer = 0 

    def spawn_harvester(self):
        spawn_pos = self.pos + vec(0, 50)
        harvester = Harvester(self.game, spawn_pos, self.team, self)
        self.game.all_units.append(harvester)
        self.harvesters.append(harvester) 
        self.game.particles.add(FloatingText(self.pos, "New Harvester", GREEN_HAT))

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = screen_pos
        
        w = scale(100, zoom)
        h = scale(80, zoom)
        
        C_CONCRETE = (100, 100, 105) 
        C_METAL    = (80, 75, 70)    
        C_RUST     = (120, 80, 60)   
        C_PIPE     = (60, 60, 65)    
        C_GLOW     = (255, 150, 50)  
        C_ROOF     = (50, 50, 55)    
        plat_w = w * 0.5
        plat_h = h * 0.6
        plat_rect = pygame.Rect(cx - w/2, cy - plat_h/2 + h*0.2, plat_w, plat_h)
        
        pygame.draw.rect(surface, C_CONCRETE, plat_rect)
        pygame.draw.rect(surface, (50,50,50), plat_rect, 2) 

        ramp_x = plat_rect.left
        ramp_y = plat_rect.bottom
        pygame.draw.polygon(surface, (80, 80, 85), [
            (ramp_x, ramp_y), 
            (ramp_x + plat_w, ramp_y), 
            (ramp_x + plat_w, ramp_y + scale(15, zoom)), 
            (ramp_x, ramp_y + scale(15, zoom))
        ])
        for i in range(3):
            ly = ramp_y + i * scale(5, zoom)
            pygame.draw.line(surface, (60,60,60), (ramp_x, ly), (ramp_x+plat_w, ly), 1)

        hopper_rect = pygame.Rect(plat_rect.centerx - scale(15, zoom), plat_rect.centery - scale(10, zoom), scale(30, zoom), scale(20, zoom))
        pygame.draw.rect(surface, (20, 20, 25), hopper_rect) 
        pygame.draw.rect(surface, (200, 180, 50), hopper_rect.inflate(-4, -4), 1) 

        tower_w = w * 0.4
        tower_h = h * 0.8
        tower_rect = pygame.Rect(cx + scale(5, zoom), cy - h/2, tower_w, tower_h)
        
        pygame.draw.rect(surface, C_METAL, tower_rect)
        pygame.draw.rect(surface, (40,40,40), tower_rect, 2)
        
        pygame.draw.rect(surface, C_RUST, (tower_rect.left, tower_rect.top + scale(20, zoom), tower_w, scale(10, zoom)))
        
        glow_alpha = int(150 + 100 * math.sin(pygame.time.get_ticks() * 0.005))
        glow_surf = pygame.Surface((int(tower_w*0.6), int(scale(15, zoom))), pygame.SRCALPHA)
        glow_surf.fill((*C_GLOW, glow_alpha))
        surface.blit(glow_surf, (tower_rect.centerx - tower_w*0.3, tower_rect.centery))
        
        for i in range(3):
            lx = tower_rect.centerx - tower_w*0.3 + i * scale(10, zoom)
            pygame.draw.line(surface, (30,30,30), (lx, tower_rect.centery), (lx, tower_rect.centery + scale(15, zoom)), 2)

        pipe_start = (plat_rect.right, plat_rect.centery)
        pipe_end = (tower_rect.left, tower_rect.centery)
        pygame.draw.line(surface, C_PIPE, pipe_start, pipe_end, int(scale(8, zoom)))
        pygame.draw.line(surface, (100,100,100), pipe_start, pipe_end, int(scale(2, zoom))) 

        chimney_w = scale(12, zoom)
        chimney_h = scale(25, zoom)
        chimney_rect = pygame.Rect(tower_rect.centerx - chimney_w/2, tower_rect.top - chimney_h, chimney_w, chimney_h)
        pygame.draw.rect(surface, (40, 40, 45), chimney_rect)
        pygame.draw.ellipse(surface, (20, 20, 20), (chimney_rect.left, chimney_rect.top-scale(3, zoom), chimney_w, scale(6, zoom))) 
        
        t = pygame.time.get_ticks()
        for i in range(3):
            offset_y = (t * 0.05 + i * 20) % 60
            alpha = max(0, 255 - offset_y * 4)
            smoke_r = scale(5 + offset_y * 0.2, zoom)
            
            offset_x = math.sin(offset_y * 0.1) * scale(10, zoom)
            
            s_smoke = pygame.Surface((int(smoke_r*2), int(smoke_r*2)), pygame.SRCALPHA)
            pygame.draw.circle(s_smoke, (100, 100, 100, int(alpha)), (int(smoke_r), int(smoke_r)), int(smoke_r))
            surface.blit(s_smoke, (chimney_rect.centerx + offset_x - smoke_r, chimney_rect.top - scale(offset_y, zoom) - smoke_r))

        lamp_color = (255, 50, 50) if (t // 500) % 2 == 0 else (100, 30, 30)
        pygame.draw.circle(surface, lamp_color, (tower_rect.right - scale(5, zoom), tower_rect.top + scale(5, zoom)), scale(3, zoom))

        self.draw_health_and_marker(surface, offset, zoom, y_offset=-scale(50, zoom))
class Airfield(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "airfield")
        self.hp = 700
        self.max_hp = 700
        self.armor=5
        self.radius = 60
        self.rect = pygame.Rect(pos.x - 60, pos.y - 60, 120, 120)
        self.is_upgraded = False
    def update(self):
        return super().update() 



    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
        field_w = scale(140, zoom)
        field_h = scale(90, zoom)
        slab_h = scale(8, zoom) 
        
        C_CONCRETE      = (100, 100, 105)
        C_CONCRETE_SIDE = (60, 60, 65)
        C_MARKING       = (220, 220, 220) 
        C_MARKING_Y     = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])  
        C_TOWER_BASE    = (120, 120, 125)
        C_GLASS         = (20, 40, 60)    
        C_GLASS_HILITE  = (50, 80, 100)   
        C_HANGAR        = (90, 95, 100)
        C_RADAR         = (200, 200, 210)
        
        if self.is_upgraded:
            C_RADAR = (255, 215, 0) 
            C_TOWER_TRIM = (255, 100, 50) 
        else:
            C_TOWER_TRIM = (0, 100, 200) 
            
        shadow_offset = scale(10, zoom)
        s_surf = pygame.Surface((field_w + shadow_offset, field_h + shadow_offset), pygame.SRCALPHA)
        pygame.draw.rect(s_surf, (0, 0, 0, 80), (shadow_offset, shadow_offset, field_w, field_h), border_radius=int(scale(5, zoom)))
        surface.blit(s_surf, (cx - field_w//2, cy - field_h//2))

        base_top_y = cy
        
        pygame.draw.rect(surface, C_CONCRETE_SIDE, (cx - field_w//2, base_top_y - field_h//2, field_w, field_h + slab_h))
        field_rect = pygame.Rect(cx - field_w//2, base_top_y - field_h//2, field_w, field_h)
        pygame.draw.rect(surface, C_CONCRETE, field_rect)
        pygame.draw.rect(surface, (80, 80, 80), field_rect, 2)
        
        
        runway_w = field_w * 0.8
        runway_h = field_h * 0.4
        runway_y = field_rect.bottom - runway_h - scale(10, zoom)
        
        pygame.draw.rect(surface, (80, 80, 85), (cx - runway_w//2, runway_y, runway_w, runway_h))
        
        dash_len = scale(15, zoom)
        gap_len = scale(10, zoom)
        start_x = cx - runway_w//2 + scale(10, zoom)
        mid_y = runway_y + runway_h//2
        for i in range(5):
            dx = start_x + i * (dash_len + gap_len)
            pygame.draw.line(surface, C_MARKING, (dx, mid_y), (dx + dash_len, mid_y), int(scale(3, zoom)))
            
        pygame.draw.line(surface, C_MARKING_Y, (cx - field_w//2 + scale(5, zoom), runway_y - scale(5, zoom)), 
                        (cx + field_w//2 - scale(5, zoom), runway_y - scale(5, zoom)), 2)


        hangar_w = scale(40, zoom)
        hangar_l = scale(30, zoom) 
        hangar_h = scale(20, zoom)
        
        hx = field_rect.left + scale(15, zoom)
        hy = field_rect.top + scale(15, zoom) + hangar_l 
        
        pygame.draw.rect(surface, (70, 75, 80), (hx, hy - hangar_h, hangar_w, hangar_h))
        pygame.draw.rect(surface, (40, 40, 45), (hx + scale(5, zoom), hy - hangar_h + scale(5, zoom), hangar_w - scale(10, zoom), hangar_h))
        
        roof_rect = pygame.Rect(hx, hy - hangar_h - scale(10, zoom), hangar_w, scale(20, zoom))
        pygame.draw.arc(surface, C_HANGAR, roof_rect, 0, math.pi, scale(10, zoom)) 
        pygame.draw.line(surface, (60, 60, 65), (hx, hy - hangar_h), (hx + hangar_w, hy - hangar_h), 2)


        tx = field_rect.right - scale(30, zoom)
        ty_base = field_rect.top + scale(30, zoom)
        
        t_w = scale(20, zoom)
        t_h = scale(50, zoom) 
        
        tower_rect = pygame.Rect(tx - t_w//2, ty_base - t_h, t_w, t_h)
        pygame.draw.rect(surface, C_TOWER_BASE, tower_rect)
        pygame.draw.rect(surface, (90, 90, 95), tower_rect, 2)
        pygame.draw.line(surface, C_TOWER_TRIM, (tx, ty_base - t_h), (tx, ty_base), 2)
        
        deck_w = scale(32, zoom)
        deck_h = scale(18, zoom)
        deck_y = ty_base - t_h - deck_h
        
        deck_points = [
            (tx - deck_w//2 + scale(5, zoom), deck_y + deck_h), 
            (tx + deck_w//2 - scale(5, zoom), deck_y + deck_h), 
            (tx + deck_w//2, deck_y),                           
            (tx - deck_w//2, deck_y)                            
        ]
        pygame.draw.polygon(surface, C_GLASS, deck_points)
        pygame.draw.line(surface, C_GLASS_HILITE, (tx - deck_w//3, deck_y + deck_h*0.3), (tx + deck_w//3, deck_y + deck_h*0.8), 2)
        
        pygame.draw.rect(surface, C_TOWER_BASE, (tx - deck_w//2, deck_y - scale(4, zoom), deck_w, scale(4, zoom)))


        radar_y = deck_y - scale(4, zoom)
        
        pygame.draw.line(surface, (50, 50, 50), (tx, radar_y), (tx, radar_y - scale(6, zoom)), 2)
        
        t = time.time()
        rot_speed = 8 if self.is_upgraded else 4 
        angle = t * rot_speed
        
        radar_w = scale(14, zoom)
        dx = math.cos(angle) * radar_w
        dy = math.sin(angle) * scale(4, zoom) 
        
        radar_center = (tx, radar_y - scale(6, zoom))
        p1 = (radar_center[0] - dx, radar_center[1] - dy)
        p2 = (radar_center[0] + dx, radar_center[1] + dy)
        
        pygame.draw.line(surface, C_RADAR, p1, p2, int(scale(4, zoom)))
        pygame.draw.circle(surface, (255, 255, 255), (int(radar_center[0]), int(radar_center[1])), scale(3, zoom))


        blink = int(time.time() * 2) % 2 == 0
        if blink or self.is_upgraded: 
            light_color = (255, 50, 50) 
            pygame.draw.circle(surface, light_color, (int(radar_center[0]), int(radar_center[1] - scale(5, zoom))), 2)
            
            corners = [
                (cx - runway_w//2, runway_y),
                (cx + runway_w//2, runway_y),
                (cx - runway_w//2, runway_y + runway_h),
                (cx + runway_w//2, runway_y + runway_h)
            ]
            for cp in corners:
                pygame.draw.circle(surface, (0, 255, 0), (int(cp[0]), int(cp[1])), 2) 


        self.draw_health_and_marker(surface, offset, zoom, -scale(85, zoom))

class ResearchCenter(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "research")
        self.hp = 600
        self.max_hp = 600
        self.armor=5
        self.radius = 45
        self.rect = pygame.Rect(pos.x - 45, pos.y - 45, 90, 90)

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
        w = scale(90, zoom)       
        h_base = scale(20, zoom)  
        core_h = scale(50, zoom)  
        
        C_BASE_DARK   = (40, 40, 45)    
        C_BASE_LIGHT  = (70, 75, 80)    
        C_ENERGY_CORE = (0, 180, 255)   
        C_ENERGY_GLOW = (100, 220, 255) 
        C_RING_METAL  = (150, 150, 160) 
        C_HOLO_BEAM   = (0, 200, 255, 30) 
        
        team_color = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        
        t = time.time()
        
        shadow_offset = scale(10, zoom)
        s_surf = pygame.Surface((w + shadow_offset*2, w + shadow_offset*2), pygame.SRCALPHA)
        pygame.draw.rect(s_surf, (0, 0, 0, 80), (shadow_offset, shadow_offset, w, w), border_radius=int(scale(10, zoom)))
        surface.blit(s_surf, (cx - w//2, cy - w//2))


        base_top_y = cy + scale(10, zoom) 
        
        pygame.draw.rect(surface, C_BASE_DARK, (cx - w//2, base_top_y - w//2, w, w))
        
        plat_w = w * 0.9
        plat_rect = pygame.Rect(cx - plat_w//2, base_top_y - plat_w//2 - h_base, plat_w, plat_w)
        
        pygame.draw.rect(surface, C_BASE_LIGHT, plat_rect)
        pygame.draw.rect(surface, (100, 105, 110), plat_rect, 2)
        
        trench_w = scale(6, zoom)
        pygame.draw.rect(surface, (20, 20, 25), (plat_rect.left, plat_rect.centery - trench_w//2, plat_rect.width, trench_w))
        pygame.draw.rect(surface, (20, 20, 25), (plat_rect.centerx - trench_w//2, plat_rect.top, trench_w, plat_rect.height))
        
        flow_offset = (t * 20) % plat_rect.width
        for i in range(-1, 2):
            pos_x = plat_rect.left + (flow_offset + i*30) % plat_rect.width
            pygame.draw.rect(surface, team_color, (pos_x, plat_rect.centery - 1, 4, 2))
            
            pos_y = plat_rect.top + (flow_offset + i*30) % plat_rect.height
            pygame.draw.rect(surface, team_color, (plat_rect.centerx - 1, pos_y, 2, 4))


        gen_w = scale(30, zoom)
        gen_h = scale(15, zoom)
        gen_y = plat_rect.centery
        
        gen_rect = pygame.Rect(cx - gen_w//2, gen_y - gen_h, gen_w, gen_h)
        pygame.draw.rect(surface, (50, 50, 55), gen_rect)
        pylon_h = scale(35, zoom)
        pylon_offset = gen_w // 2 + scale(4, zoom)
        
        pylons = [
            (cx - pylon_offset, gen_y), 
            (cx + pylon_offset, gen_y), 
            (cx, gen_y - pylon_offset + scale(5, zoom)), 
            (cx, gen_y + pylon_offset)  
        ]
        
        for px, py in pylons:
            pygame.draw.circle(surface, C_BASE_DARK, (int(px), int(py)), int(scale(6, zoom)))
            pygame.draw.line(surface, C_RING_METAL, (px, py), (cx, gen_y - core_h//2), 2)


        core_center_y = gen_y - scale(25, zoom) 
        
        pulse = (math.sin(t * 3) + 1) / 2 
        core_r = scale(12 + 2 * pulse, zoom)
        
        glow_surf = pygame.Surface((core_r*4, core_r*4), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*C_ENERGY_CORE, 100), (core_r*2, core_r*2), core_r*1.5)
        pygame.draw.circle(glow_surf, (*C_ENERGY_GLOW, 150), (core_r*2, core_r*2), core_r)
        surface.blit(glow_surf, (cx - core_r*2, core_center_y - core_r*2))
        
        pygame.draw.circle(surface, (255, 255, 255), (cx, int(core_center_y)), int(core_r * 0.6))
        
        
        
        angle1 = t * 1.5
        rx1 = math.cos(angle1) * scale(25, zoom)
        ry1 = math.sin(angle1) * scale(8, zoom) 
        
        angle2 = t * 2.0 + 1.0
        rx2 = math.cos(angle2) * scale(20, zoom)
        ry2 = math.sin(angle2) * scale(20, zoom) 
        
        
        sat_r = scale(3, zoom)
        pygame.draw.circle(surface, C_RING_METAL, (int(cx + rx1), int(core_center_y + ry1)), int(sat_r))
        pygame.draw.circle(surface, C_RING_METAL, (int(cx - rx1), int(core_center_y - ry1)), int(sat_r))
        
        points = []
        for i in range(360):
            rad = math.radians(i)
            px = cx + math.cos(rad) * scale(22, zoom) * math.cos(t) 
            py = core_center_y + math.sin(rad) * scale(22, zoom)
            if i % 10 == 0: 
                pass


        beam_h = scale(80, zoom)
        beam_w = scale(10, zoom)
        
        beam_surf = pygame.Surface((beam_w, beam_h), pygame.SRCALPHA)
        
        for i in range(int(beam_h)):
            alpha = int(100 * (1 - i/beam_h)) 
            pygame.draw.line(beam_surf, (*team_color, alpha), (0, i), (beam_w, i))
            
        beam_surf = pygame.transform.flip(beam_surf, False, True)
        surface.blit(beam_surf, (cx - beam_w//2, core_center_y - beam_h))


        if int(t * 10) % 3 == 0:
            data_y = core_center_y - random.randint(10, int(scale(60, zoom)))
            data_x = cx + random.randint(-5, 5)
            pygame.draw.rect(surface, (200, 255, 255), (data_x, data_y, 2, 2))


        self.draw_health_and_marker(surface, offset, zoom, -scale(90, zoom))
class MissileDefenseSystem(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "missile_def")
        self.hp = 500
        self.max_hp = 500
        self.radius = 30
        self.rect = pygame.Rect(pos.x - 30, pos.y - 30, 60, 60)
        self.range = MISSILE_DEFENSE_RANGE
        self.angle = 0
        self.attack_cooldown=0
    def update(self):
        if self.attack_cooldown > 0: self.attack_cooldown -= 1        
        for u in self.game.all_units:
            is_missile = hasattr(u, 'explode') and u.is_air and u.team != self.team
            if is_missile and u.alive:
                dist = self.pos.distance_to(u.pos)
                if dist <= self.range  and self.attack_cooldown <= 0:
                    u.alive = False 
                    self.game.particles.add(FloatingText(u.pos, "INTERCEPTED", MARKER_BLUE))
                    
                    self.game.particles.add(InterceptEffect(self.game.particles, self.pos, u.pos, CYAN))
                    
                    self.game.particles.add(Particle(self.game.particles, u.pos, ORANGE, 0, 10, 20)) 
                    self.attack_cooldown=20
                    break 

        self.angle += 5 

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
        base_w = scale(40, zoom)
        total_h = scale(55, zoom)
        coil_w = scale(18, zoom)
        top_r = scale(14, zoom)
        
        C_BASE      = (60, 60, 65)
        C_BASE_TOP  = (90, 90, 95)
        C_COIL_DARK = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])      
        C_COIL_RING = (180, 180, 190)   
        C_ELEC_CORE = (0, 200, 255)     
        C_SPARK     = (220, 255, 255)   
        
        t = time.time()
        
        shadow_offset = scale(8, zoom)
        s_surf = pygame.Surface((base_w + shadow_offset, base_w + shadow_offset), pygame.SRCALPHA)
        pygame.draw.circle(s_surf, (0, 0, 0, 80), (base_w//2 + shadow_offset//2, base_w//2 + shadow_offset//2), base_w//2)
        surface.blit(s_surf, (cx - base_w//2, cy - base_w//2))

        base_y = cy + scale(10, zoom)
        pygame.draw.circle(surface, C_BASE, (cx, base_y), base_w//2)
        pygame.draw.circle(surface, C_BASE_TOP, (cx, base_y), base_w//2 - scale(4, zoom))
        team_c = (0, 150, 255) if self.team == "player" else (220, 60, 60)
        pygame.draw.circle(surface, team_c, (cx, base_y), base_w//2 - scale(2, zoom), 2)

        stack_y_start = base_y - scale(5, zoom)
        stack_height = scale(35, zoom)
        num_rings = 4
        
        pulse = (math.sin(t * 15) + 1) / 2  
        glow_w = int(coil_w * (0.6 + 0.2 * pulse))
        glow_rect = pygame.Rect(cx - glow_w//2, stack_y_start - stack_height, glow_w, stack_height)
        pygame.draw.rect(surface, C_ELEC_CORE, glow_rect)
        
        for i in range(num_rings):
            ring_y = stack_y_start - (i / (num_rings-1)) * stack_height
            rect_ring = pygame.Rect(cx - coil_w//2, ring_y - scale(3, zoom), coil_w, scale(6, zoom))
            pygame.draw.ellipse(surface, C_COIL_RING, rect_ring)
            pygame.draw.ellipse(surface, C_COIL_DARK, rect_ring, 1)

        top_y = stack_y_start - stack_height - scale(5, zoom)
        
        pygame.draw.circle(surface, (200, 200, 210), (cx, int(top_y)), top_r)
        pygame.draw.circle(surface, (255, 255, 255), (cx - top_r//3, int(top_y - top_r//3)), scale(4, zoom))
        
        if random.random() < 0.7: 
            for _ in range(random.randint(1, 3)):
                angle = random.uniform(0, 6.28)
                dist = random.uniform(top_r, top_r * 2.5)
                
                start_p = (cx, top_y)
                end_x = cx + math.cos(angle) * dist
                end_y = top_y + math.sin(angle) * dist
                
                mid_x = (start_p[0] + end_x) / 2 + random.randint(-5, 5)
                mid_y = (start_p[1] + end_y) / 2 + random.randint(-5, 5)
                
                pygame.draw.line(surface, C_ELEC_CORE, start_p, (mid_x, mid_y), 2)
                pygame.draw.line(surface, C_ELEC_CORE, (mid_x, mid_y), (end_x, end_y), 2)
                pygame.draw.line(surface, C_SPARK, start_p, (mid_x, mid_y), 1)

        aim_vec = pygame.math.Vector2(top_r + scale(5, zoom), 0).rotate(self.angle) 
        end_pos = (cx + aim_vec.x, cy - total_h + aim_vec.y + scale(10, zoom)) 
        
        pygame.draw.line(surface, (50, 50, 50), (cx, int(top_y)), end_pos, 2)
        pygame.draw.circle(surface, team_c, (int(end_pos[0]), int(end_pos[1])), scale(3, zoom))

        if self.game.selected_entity == self:
            pygame.draw.circle(surface, (0, 191, 255), (cx, cy), scale(self.range, zoom), 1)
            s_range = pygame.Surface((scale(self.range*2, zoom), scale(self.range*2, zoom)), pygame.SRCALPHA)
            pygame.draw.circle(s_range, (0, 191, 255, 30), (scale(self.range, zoom), scale(self.range, zoom)), scale(self.range, zoom))
            surface.blit(s_range, (cx - scale(self.range, zoom), cy - scale(self.range, zoom)))

        self.draw_health_and_marker(surface, offset, zoom, -scale(65, zoom))

class AntiAirTurret(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "aa_turret")
        self.hp = AA_TURRET_STATS[2]
        self.max_hp = self.hp
        self.radius = 25
        self.rect = pygame.Rect(pos.x - 25, pos.y - 25, 50, 50)
        self.attack_range = AA_TURRET_STATS[0]
        self.attack_cooldown = 0
        self.angle = 0
        self.target = None
        self.armor=5
        self.breakarmorvalue=10
    def update(self):
        if self.game.current_voltage > self.game.max_voltage:
            self.target_entity = None
            return 
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        if not self.target or not self.target.alive or not self.target.is_air:
            self.target = self.find_nearest_enemy()
        
        if self.target:
            dist = self.pos.distance_to(self.target.pos)
            if dist <= self.attack_range:
                vec_to = self.target.pos - self.pos
                self.angle = math.degrees(math.atan2(-vec_to.y, vec_to.x))
                if self.attack_cooldown <= 0:
                    self.fire()
                    self.attack_cooldown = 20 
            else:
                self.target = None 


    def find_nearest_enemy(self):
        nearest = None
        min_dist = 99999
        enemies = [u for u in self.game.all_units if u.team != self.team and u.is_air]
        for e in enemies:

            if getattr(e, 'is_stealth', False):
                if self.pos.distance_to(e.pos) > 50: 
                    continue  
            dist = self.pos.distance_to(e.pos)
            if dist < min_dist: min_dist = dist; nearest = e
        return nearest

    def fire(self):
        proj = Projectile(self.game, self.pos, self.target, self.team, DMG_AA,"heavy", breakshellvalue=self.breakarmorvalue)
        proj.speed = 15 
        self.game.projectiles.append(proj)

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
        base_w = scale(40, zoom)    
        base_h = scale(12, zoom)    
        
        turret_w = scale(24, zoom)  
        turret_l = scale(32, zoom)  
        
        barrel_len = scale(30, zoom)
        barrel_w = scale(6, zoom)   
        
        C_BASE_SIDE = (50, 50, 55)
        C_BASE_TOP  = (90, 90, 95)
        C_TURRET    = (200, 200, 210) 
        C_BARREL    = (40, 40, 45)    
        C_COIL      = (100, 100, 100) 
        C_LENS      = (0, 255, 255)   
        C_TEAM      =TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        
        shadow_offset = scale(8, zoom)
        s_surf = pygame.Surface((base_w*2, base_w*2), pygame.SRCALPHA)
        pygame.draw.rect(s_surf, (0,0,0,80), (shadow_offset, shadow_offset, base_w, base_w), border_radius=int(scale(5, zoom)))
        surface.blit(s_surf, (cx - base_w//2, cy - base_w//2))


        base_top_y = cy
        
        pygame.draw.rect(surface, C_BASE_SIDE, (cx - base_w//2, base_top_y - base_w//2, base_w, base_w + base_h))
        
        rect_base = pygame.Rect(cx - base_w//2, base_top_y - base_w//2, base_w, base_w)
        pygame.draw.rect(surface, C_BASE_TOP, rect_base)
        pygame.draw.rect(surface, (60, 60, 65), rect_base, 2)
        
        pygame.draw.circle(surface, (40, 40, 40), (cx, int(base_top_y)), int(scale(14, zoom)))
        pygame.draw.circle(surface, (70, 70, 70), (cx, int(base_top_y)), int(scale(10, zoom)), 1)


        
        
        aim_dir = pygame.math.Vector2(1, 0).rotate(-self.angle) 
        side_dir = pygame.math.Vector2(0, 1).rotate(-self.angle)
        
        barrel_offset_side = scale(10, zoom) 
        barrel_offset_back = scale(5, zoom)  
        
        for side in [-1, 1]: 
            start_pos = pygame.math.Vector2(cx, cy) + side_dir * (side * barrel_offset_side) - aim_dir * barrel_offset_back
            
            p1 = start_pos + side_dir * (barrel_w/2)
            p2 = start_pos - side_dir * (barrel_w/2)
            p3 = p2 + aim_dir * barrel_len
            p4 = p1 + aim_dir * barrel_len
            
            pygame.draw.polygon(surface, C_BARREL, [p1, p2, p3, p4])
            
            for i in range(3):
                dist = 0.3 + i * 0.2
                c_p1 = p1 + aim_dir * (barrel_len * dist)
                c_p2 = p2 + aim_dir * (barrel_len * dist)
                pygame.draw.line(surface, C_COIL, c_p1, c_p2, 1)
                
            lens_center = (p3 + p4) / 2
            lens_radius = scale(4, zoom)
            
            pulse = (math.sin(time.time() * 10) + 1) / 2
            glow_color = (
                max(0, min(255, C_LENS[0] + 50*pulse)),
                max(0, min(255, C_LENS[1] + 50*pulse)),
                max(0, min(255, C_LENS[2] + 50*pulse))
            )
            pygame.draw.circle(surface, glow_color, (int(lens_center.x), int(lens_center.y)), int(lens_radius))


        
        t_front_w = turret_w
        t_back_w = turret_w * 0.8
        t_len_f = turret_l * 0.4
        t_len_b = turret_l * 0.6
        
        points_local = [
            (t_len_f, -t_front_w/2),  
            (t_len_f, t_front_w/2),   
            (-t_len_b, t_back_w/2),   
            (-t_len_b, -t_back_w/2)   
        ]
        
        points_screen = []
        for px, py in points_local:
            rot_vec = pygame.math.Vector2(px, py).rotate(-self.angle)
            screen_pt = (cx + rot_vec.x, cy + rot_vec.y)
            points_screen.append(screen_pt)
            
        pygame.draw.polygon(surface, C_TURRET, points_screen)
        pygame.draw.polygon(surface, (150, 150, 160), points_screen, 1) 
        
        batt_center = pygame.math.Vector2(-scale(8, zoom), 0).rotate(-self.angle)
        batt_pos = (cx + batt_center.x, cy + batt_center.y)
        pygame.draw.circle(surface, C_TEAM, (int(batt_pos[0]), int(batt_pos[1])), int(scale(5, zoom)))
        
        sensor_center = pygame.math.Vector2(scale(6, zoom), 0).rotate(-self.angle)
        sensor_pos = (cx + sensor_center.x, cy + sensor_center.y)
        pygame.draw.circle(surface, (50, 50, 50), (int(sensor_pos[0]), int(sensor_pos[1])), int(scale(3, zoom)))
        pygame.draw.circle(surface, (255, 0, 0), (int(sensor_pos[0]), int(sensor_pos[1])), int(scale(1, zoom))) 

        
        self.draw_health_and_marker(surface, offset, zoom, -scale(40, zoom))
class LaserTurret(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "laser_turret")
        self.hp = LASER_TURRET_STATS[2]
        self.max_hp = self.hp
        self.armor=15
        self.radius = 25
        self.rect = pygame.Rect(pos.x - 25, pos.y - 25, 50, 50)
        self.attack_range = LASER_TURRET_STATS[0]
        self.targets = []
        self.max_targets = 3        
    def update(self):
        super().update()
        
        if self.game.current_voltage > self.game.max_voltage:
            self.targets = []
            return 

        if not self.game.is_online or self.game.my_role == "HOST":
            
            self.targets = [t for t in self.targets if 
                            t.alive and 
                            t.team != self.team and 
                            t.team != "neutral" and 
                            self.pos.distance_to(t.pos) <= self.attack_range]
            
            if len(self.targets) < self.max_targets:
                new_targets = self.find_multiple_enemies(self.max_targets - len(self.targets))
                for t in new_targets:
                    if t not in self.targets:
                        self.targets.append(t)
            for t in self.targets:
                t.take_damage(DMG_LASER, "energy", 1000)            
        for t in self.targets:
            p = Projectile(self.game, self.pos, t, self.team, 0, "laser", breakshellvalue=1000)
            p.life_time = 15
            self.game.projectiles.append(p)

    def find_multiple_enemies(self, count_needed):
        candidates = []
        for u in self.game.all_units:
            if u.alive and u.team != self.team and u.team != "neutral" and not u.is_air:
                if getattr(u, 'is_stealth', False): 
                    if self.pos.distance_to(u.pos) > 50: continue
                
                dist = self.pos.distance_to(u.pos)
                if dist <= self.attack_range:
                    candidates.append((dist, u))
        
        candidates.sort(key=lambda x: x[0])
        
        return [c[1] for c in candidates[:count_needed]]

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        w = scale(40, zoom)
        pygame.draw.rect(surface, (30, 30, 30), (screen_pos[0]-w//2, screen_pos[1]-w//2, w, w))
        pygame.draw.circle(surface, (0, 200, 200), screen_pos, scale(15, zoom))
        pygame.draw.circle(surface, CYAN, screen_pos, scale(18, zoom), 2)
        self.draw_health_and_marker(surface, offset, zoom, -30)
class ShroudGen(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "shroud_gen")
        self.hp = 1000
        self.max_hp = 1000
        self.radius = 40
        self.rect = pygame.Rect(pos.x-40, pos.y-40, 80, 80)
        self.power_usage = 300 
        
        self.image = self.generate_image()

    def generate_image(self):
        s = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(s, (20, 20, 20), (40, 40), 30)
        pygame.draw.circle(s, (50, 0, 50), (40, 40), 10) 
        for i in range(4):
            angle = i * 90
            end_x = 40 + math.cos(math.radians(angle)) * 35
            end_y = 40 + math.sin(math.radians(angle)) * 35
            pygame.draw.line(s, (100, 100, 100), (40, 40), (end_x, end_y), 3)
        return s

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        t = pygame.time.get_ticks()
        scale_p = 1.0 + math.sin(t * 0.005) * 0.1
        
        scaled_img = scale_img(self.image, zoom * scale_p)
        rect = scaled_img.get_rect(center=screen_pos)
        surface.blit(scaled_img, rect)
        
        self.draw_health_and_marker(surface, offset, zoom, -40)
class PrototypeGen(Building):
    def __init__(self, game, pos, team="neutral"):
        super().__init__(game, pos, team, "prototype_gen")
        self.b_type = "prototype_gen"
        self.hp = 2000
        self.max_hp = 2000
        self.armor=30
        self.radius = 70 
        self.rect = pygame.Rect(pos.x - 70, pos.y - 70, 140, 140)
        
        self.loaded_weapon = None 
        self.weapon_obj = None 
        
        self.image = self.generate_image()
        self.is_ready = False
        self.charge_timer = 0
        self.charge_time_total = 0 

    def update(self):
        super().update()
        
        if self.loaded_weapon and not self.is_ready:
            self.charge_timer += 1
            if self.charge_timer >= self.charge_time_total:
                self.is_ready = True
                self.charge_timer = self.charge_time_total
                self.game.particles.add(FloatingText(self.pos, "WEAPON READY", RED))

        if self.weapon_obj:
            self.weapon_obj.update()
            if not self.weapon_obj.alive:
                self.weapon_obj = None
                self.loaded_weapon = None
                self.is_ready = False 

    def build_prototype(self, p_type):
        if self.loaded_weapon: return 
        
        self.loaded_weapon = p_type
        self.is_ready = False
        self.charge_timer = 0
        
        if p_type == "iron_curtain":
            self.charge_time_total = 5400
            self.weapon_obj = IronCurtain(self.game, self.pos, self.team, self)
        elif p_type == "nuke_silo":
            self.charge_time_total = 3600 
            self.weapon_obj = NukeSilo(self.game, self.pos, self.team, self)
    def generate_image(self):
        w, h = 160, 160
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        
        C_BASE_DARK  = (40, 45, 50)
        C_BASE_LIGHT = (70, 75, 80)
        C_PLATFORM   = (30, 30, 35)
        C_ACCENT     = TEAM_COLORS.get(self.team, (0, 200, 255))
        C_DETAIL     = (100, 110, 120)
        
        base_w = 100
        base_h = 80
        base_rect = pygame.Rect(cx - base_w//2, cy - base_h//2 + 20, base_w, base_h)
        
        pygame.draw.rect(s, (0,0,0,80), base_rect.inflate(10, 10), border_radius=15)
        
        pygame.draw.rect(s, C_BASE_DARK, base_rect, border_radius=10)
        top_rect = base_rect.inflate(-10, -10)
        pygame.draw.rect(s, C_BASE_LIGHT, top_rect, border_radius=5)
        
        for i in range(3):
            lx = base_rect.left - 5
            ly = base_rect.top + 15 + i * 15
            pygame.draw.rect(s, (20,20,20), (lx, ly, 10, 8)) 
            
            rx = base_rect.right - 5
            ry = base_rect.top + 15 + i * 15
            pygame.draw.rect(s, (20,20,20), (rx, ry, 10, 8)) 

        plat_r = 35
        pygame.draw.circle(s, C_DETAIL, (cx, cy+10), plat_r)
        pygame.draw.circle(s, C_PLATFORM, (cx, cy+10), plat_r - 5)
        
        for i in range(3):
            angle = i * (360/3) - 90
            rad = math.radians(angle)
            ex = cx + math.cos(rad) * (plat_r + 5)
            ey = cy + 10 + math.sin(rad) * (plat_r + 5)
            pygame.draw.line(s, C_DETAIL, (cx, cy+10), (ex, ey), 4)
            pygame.draw.circle(s, (20,20,20), (int(ex), int(ey)), 4)

        pygame.draw.circle(s, (0, 100, 100), (cx, cy+10), 10)
        
        ant_base_x = cx + 40
        ant_base_y = cy - 30
        
        pygame.draw.rect(s, C_BASE_DARK, (ant_base_x-10, ant_base_y, 20, 20))
        
        pygame.draw.line(s, C_DETAIL, (ant_base_x, ant_base_y), (ant_base_x, ant_base_y - 50), 3)
        dish_pos = (ant_base_x, ant_base_y - 50)
        pygame.draw.arc(s, C_DETAIL, (dish_pos[0]-10, dish_pos[1]-10, 20, 20), 0.5, 2.6, 2)
        pygame.draw.line(s, C_DETAIL, dish_pos, (dish_pos[0]-8, dish_pos[1]-8), 1)
        
        pygame.draw.circle(s, (100, 0, 0), (ant_base_x, ant_base_y - 55), 2)

        pygame.draw.rect(s, C_ACCENT, (cx - 40, cy + 40, 80, 4))

        return s

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled = scale_img(self.image, zoom)
        rect = scaled.get_rect(center=screen_pos)
        surface.blit(scaled, rect)
        
        if not self.weapon_obj:
            alpha = int(100 + 50 * math.sin(pygame.time.get_ticks() * 0.005))
            glow_r = int(scale(10, zoom))
            glow_pos = (screen_pos[0], screen_pos[1] + 10*zoom)
            
            s = pygame.Surface((glow_r*2, glow_r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (0, 255, 255, alpha), (glow_r, glow_r), glow_r)
            surface.blit(s, (glow_pos[0]-glow_r, glow_pos[1]-glow_r), special_flags=pygame.BLEND_ADD)
            
        ant_pos = (screen_pos[0] + 40*zoom, screen_pos[1] - 55*zoom)
        if (pygame.time.get_ticks() // 500) % 2 == 0:
            pygame.draw.circle(surface, (255, 0, 0), ant_pos, int(3*zoom))

        if self.weapon_obj:
            
            self.weapon_obj.draw(surface, offset, zoom)
            
        self.draw_health_and_marker(surface, offset, zoom, y_offset=-60*zoom)

class IronCurtain(Building):
    def __init__(self, game, pos, team, parent):
        super().__init__(game, pos, team, "iron_curtain")
        self.parent = parent
        self.radius = 40
        self.hp = 1000 
        
        self.cooldown = 0
        self.max_cooldown = 0
        self.is_aiming = False
        
        self.image = self.generate_image()

    def generate_image(self):
        s = pygame.Surface((80, 80), pygame.SRCALPHA)
        cx, cy = 40, 40
        pygame.draw.circle(s, (100, 0, 0), (cx, cy), 25)
        pygame.draw.circle(s, (255, 50, 50), (cx, cy), 15) 
        pygame.draw.arc(s, (200, 200, 200), (cx-30, cy-30, 60, 60), 0, 3.14, 2)
        return s

    def toggle_mode(self):
        self.is_aiming = not self.is_aiming
        if self.is_aiming:
            self.game.particles.add(FloatingText(self.pos, "IRON CURTAIN READY", RED))
            if hasattr(self.game, 'net_events'):
                self.game.net_events.append({
                    "type": "FX_TEXT", 
                    "x": int(self.pos.x), "y": int(self.pos.y),
                    "text": "IRON CURTAIN READY",
                    "color": "RED" 
                })
            self.game.place_building_type = "skill_iron_curtain" 
        else:
            self.game.place_building_type = None

    def activate(self, target_pos):
        radius = 150
        amount = 1000 
        for u in self.game.all_units:
            if u.alive  and u.pos.distance_to(target_pos) < radius:
                if u.is_mechanical or u.is_air:
                    u.shield = amount
                    u.max_shield = amount
                    self.game.particles.add(FloatingText(u.pos, "+SHIELD", RED))
                    if hasattr(self.game, 'net_events'):
                        self.game.net_events.append({
                            "type": "FX_TEXT", 
                            "x": int(u.pos.x), "y": int(u.pos.y),
                            "text": "+SHIELD",
                            "color": "RED" 
                        })
                else:
                    p = Projectile(self.game, u.pos, None, "neutral", 300,"heavy_shell", is_aoe=True, aoe_radius=50,breakshellvalue=0)
                    p.on_hit(None)
        self.alive = False 
        self.is_aiming = False
        self.game.place_building_type = None
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled = scale_img(self.image, zoom)
        rect = scaled.get_rect(center=screen_pos)
        surface.blit(scaled, rect)
        
        is_ready = False
        if self.parent:
            is_ready = getattr(self.parent, 'is_ready', False)
        else:
            pass

        if is_ready or self.is_aiming:
            import random
            
            if self.game.frame_count%15==0:
                num_bolts = random.randint(0, 4)
                radius = 35 * zoom 
                
                for _ in range(num_bolts):
                    angle = random.uniform(0, 6.28)
                    start_x = screen_pos[0] + math.cos(angle) * (radius * 0.3)
                    start_y = screen_pos[1] + math.sin(angle) * (radius * 0.3)
                    
                    points = [(start_x, start_y)]
                    segments = 3
                    curr_x, curr_y = start_x, start_y
                    
                    for i in range(segments):
                        dist = (radius * 0.7) / segments
                        curr_x += math.cos(angle) * dist + random.uniform(-5, 5)
                        curr_y += math.sin(angle) * dist + random.uniform(-5, 5)
                        points.append((curr_x, curr_y))
                    
                    if len(points) > 1:
                        pygame.draw.lines(surface, (255, 0, 0), False, points, 3)
                        pygame.draw.lines(surface, (255, 200, 200), False, points, 1)
class NukeSilo(Building):
    def __init__(self, game, pos, team, parent):
        super().__init__(game, pos, team, "nuke_silo")
        self.parent = parent
        self.is_aiming = False
        self.image = self.generate_image()



    def toggle_mode(self):
        self.is_aiming = not self.is_aiming
        if self.is_aiming:
            self.game.particles.add(FloatingText(self.pos, "ROCKET READY", ORANGE))
            if hasattr(self.game, 'net_events'):
                self.game.net_events.append({
                    "type": "FX_TEXT", 
                    "x": int(self.pos.x), "y": int(self.pos.y),
                    "text": "ROCKET READY",
                    "color": "ORANGE" 
                })
            self.game.place_building_type = "skill_nuke"
        else:
            self.game.place_building_type = None

    def activate(self, target_pos):
        missile = MegaRocket(self.game, self.pos, self.team,target_pos=target_pos)
        self.game.all_units.append(missile)

        self.alive = False
        self.is_aiming = False
        self.game.place_building_type = None
    def generate_image(self):
        w, h = 160, 100
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        
        C_BASE = (40, 40, 45)     
        C_ROCKET = (220, 220, 230)
        C_WARHEAD = (200, 50, 50) 
        C_DETAIL = (150, 150, 160)
        
        rect_base = pygame.Rect(10, 20, 140, 60)
        pygame.draw.rect(s, C_BASE, rect_base, border_radius=5)
        pygame.draw.line(s, (20,20,20), (20, 40), (140, 40), 4) 
        pygame.draw.line(s, (20,20,20), (20, 60), (140, 60), 4) 
        
        rocket_x = 30
        rocket_y = 35
        rocket_len = 100
        rocket_wid = 30
        
        r_rect = pygame.Rect(rocket_x, rocket_y, rocket_len, rocket_wid)
        pygame.draw.rect(s, C_ROCKET, r_rect, border_radius=5)
        
        head_pts = [
            (rocket_x + rocket_len, rocket_y),              
            (rocket_x + rocket_len, rocket_y + rocket_wid), 
            (rocket_x + rocket_len + 20, rocket_y + rocket_wid/2) 
        ]
        pygame.draw.polygon(s, C_WARHEAD, head_pts)
        
        pygame.draw.polygon(s, C_DETAIL, [(rocket_x+10, rocket_y), (rocket_x, rocket_y-10), (rocket_x+25, rocket_y)])
        pygame.draw.polygon(s, C_DETAIL, [(rocket_x+10, rocket_y+30), (rocket_x, rocket_y+40), (rocket_x+25, rocket_y+30)])
        
        pygame.draw.rect(s, (50,50,50), (rocket_x + 60, rocket_y, 5, 30))
        pygame.draw.rect(s, (200, 200, 0), (rocket_x + 40, rocket_y + 10, 10, 10)) 

        for i in range(3):
            x = rocket_x + 20 + i * 30
            pygame.draw.rect(s, (60,60,60), (x, 20, 8, 15))
            pygame.draw.rect(s, (60,60,60), (x, 65, 8, 15))

        return s

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled = scale_img(self.image, zoom)
        rect = scaled.get_rect(center=screen_pos)
        surface.blit(scaled, rect)
        
        is_ready = False
        if self.parent:
            is_ready = getattr(self.parent, 'is_ready', False)
            
        if is_ready:
            import math
            alpha = int(100 + 100 * math.sin(pygame.time.get_ticks() * 0.01))
            
            warhead_offset = vec(50 * zoom, 0) 
            warhead_pos = (screen_pos[0] + warhead_offset.x, screen_pos[1] + warhead_offset.y)
            
            s = pygame.Surface((100, 100), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 50, 50, alpha), (50, 50), int(20*zoom))
            surface.blit(s, (warhead_pos[0]-50, warhead_pos[1]-50), special_flags=pygame.BLEND_ADD)
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
class Bunker(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "bunker")
        self.hp = BUNKER_STATS[2]
        self.max_hp = self.hp
        self.armor=15
        self.radius = 35
        self.rect = pygame.Rect(pos.x - 35, pos.y - 35, 70, 70)
        self.power_usage = 0
        
        self.attack_range = BUNKER_STATS[0]
        self.damage = 15 
        self.attack_cooldown = 0
        self.accuracy_error = 15 
        self.angle = 0 
        self.target = None
        self.target_entity = None
    def set_target(self, entity):
        if entity and entity.alive:
            self.target_entity = entity
    def update(self):        
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        
        if not self.game.is_online or self.game.my_role == "HOST":
            if self.target_entity==None:
                self.target_entity=self.find_nearest_enemy()
            if self.target_entity:
                lost_target = False
                if not self.target_entity.alive: lost_target = True
                elif self.pos.distance_to(self.target_entity.pos) > self.attack_range: lost_target = True
                elif self.target_entity.team == self.team or self.target_entity.team == "neutral": lost_target = True
                elif getattr(self.target_entity, 'is_stealth', False) and self.pos.distance_to(self.target_entity.pos) > 50: lost_target = True
                
                if lost_target:
                    self.target_entity = None
            
            
            if self.target_entity:
                if hasattr(self, 'angle'):
                    vec_to = self.target_entity.pos - self.pos
                    self.angle = math.degrees(math.atan2(-vec_to.y, vec_to.x))
                if self.attack_cooldown <= 0:
                    self.fire(self.target_entity)

    def find_nearest_enemy(self):
        nearest = None
        min_dist = BUNKER_STATS[0] 
        
        for u in self.game.all_units+ self.game.all_buildings:
            if u.alive and u.team != self.team  and not u.is_air:
                if getattr(u, 'is_stealth', False): 
                    if self.pos.distance_to(u.pos) > 50: continue 
                
                dist = self.pos.distance_to(u.pos)
                if dist < min_dist:
                    min_dist = dist
                    nearest = u
        return nearest

    def fire(self, target):
        base_vec = target.pos - self.pos
        angle_offset = random.uniform(-self.accuracy_error, self.accuracy_error)
        fire_vec = base_vec.rotate(angle_offset)
        
        p = Projectile(self.game, self.pos, None, self.team, self.damage, "heavy", breakshellvalue=self.breakarmorvalue)
        p.vel = fire_vec.normalize() * BULLET_SPEED
        p.life_time = 40 
        self.game.projectiles.append(p)
        self.attack_cooldown=3
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
        pts = []
        radius = scale(32, zoom)
        for i in range(6):
            angle_rad = math.radians(60 * i)
            px = cx + math.cos(angle_rad) * radius
            py = cy + math.sin(angle_rad) * radius
            pts.append((px, py))
        
        C_CONCRETE = (100, 105, 100)
        C_BORDER   = (50, 50, 50)
        pygame.draw.polygon(surface, C_CONCRETE, pts)
        pygame.draw.polygon(surface, C_BORDER, pts, 2)
        
        for i in range(6):
            angle_rad = math.radians(60 * i + 30)
            sx = cx + math.cos(angle_rad) * radius
            sy = cy + math.sin(angle_rad) * radius
            pygame.draw.circle(surface, (180, 160, 100), (int(sx), int(sy)), int(scale(8, zoom)))
            pygame.draw.circle(surface, (140, 120, 80), (int(sx), int(sy)), int(scale(8, zoom)), 1)

        
        aim_dir = pygame.math.Vector2(1, 0).rotate(-self.angle)
        
        turret_cy = cy - scale(5, zoom)
        turret_rad = scale(22, zoom)
        
        barrel_len = scale(20, zoom)
        barrel_w = scale(6, zoom)
        
        gun_start = pygame.math.Vector2(cx, turret_cy) + aim_dir * (turret_rad * 0.8)
        gun_end = gun_start + aim_dir * barrel_len
        
        pygame.draw.line(surface, (20, 20, 20), gun_start, gun_end, int(barrel_w))
        

        
        C_ROOF = (90, 100, 80) 
        pygame.draw.circle(surface, C_ROOF, (cx, int(turret_cy)), int(turret_rad))
        pygame.draw.circle(surface, (60, 70, 50), (cx, int(turret_cy)), int(turret_rad), 2) 
        
        slit_center = pygame.math.Vector2(cx, turret_cy) + aim_dir * (turret_rad * 0.5)
        side_dir = pygame.math.Vector2(-aim_dir.y, aim_dir.x)
        
        slit_p1 = slit_center + side_dir * scale(8, zoom)
        slit_p2 = slit_center - side_dir * scale(8, zoom)
        pygame.draw.line(surface, (10, 10, 10), slit_p1, slit_p2, int(scale(3, zoom)))
        
        team_c = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        flag_base = (cx, int(turret_cy))
        flag_top = (cx, int(turret_cy - scale(15, zoom)))
        
        pygame.draw.line(surface, (20,20,20), flag_base, flag_top, 2)
        pygame.draw.rect(surface, team_c, (flag_top[0], flag_top[1], scale(10, zoom), scale(6, zoom)))

        if self.attack_cooldown > 2:
            flash_pos = gun_end + aim_dir * scale(5, zoom)
            flash_rad = scale(random.randint(4, 8), zoom)
            pygame.draw.circle(surface, (255, 200, 50), (int(flash_pos.x), int(flash_pos.y)), int(flash_rad))

        self.draw_health_and_marker(surface, offset, zoom, -scale(35, zoom))
class ShockwaveVehicle(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = SHOCKWAVE_STATS[2]
        self.hp = self.max_hp
        self.speed = SHOCKWAVE_STATS[1]
        self.armor=15
        self.radius = 25
        self.rect = pygame.Rect(pos.x-25, pos.y-25, 50, 50)
        self.is_mechanical = True
        self.detectrange=0        
        self.shock_cooldown = 0
        self.shock_max_cooldown = SHOCK_COOLDOWN

        self.weight = 5.0 

    def toggle_mode(self):
        self.activate_shockwave()
    def activate_shockwave(self):
        if self.shock_cooldown > 0: 
            self.game.show_alert("SHOCKWAVE CHARGING...")
            return

        self.shock_cooldown = self.shock_max_cooldown
        
        forward_vec = vec(1, 0).rotate(-self.angle) 
        
        if not self.game.is_online or self.game.my_role == "HOST":
            self.game.net_events.append({
                "type": "FX_SHOCKWAVE",
                "x": int(self.pos.x), "y": int(self.pos.y),
                "radius": SHOCK_RANGE,
                "angle": self.angle 
            })
            
            for u in self.game.all_units:
                if u != self and u.alive:
                    dist = self.pos.distance_to(u.pos)
                    if dist < SHOCK_RANGE:
                        dir_to_target = (u.pos - self.pos).normalize()
                        
                        if forward_vec.dot(dir_to_target) > 0:
                            
                            if u.__class__.__name__ == "CruiseMissile" or u.__class__.__name__ == "ShipMissile":
                                self.apply_push(u, force_mult=2.0) 
                                u.team = self.team 
                                u.angle = (u.angle + 180) % 360 
                                u.target_entity = None 
                                u.target_pos = u.pos + dir_to_target * 2000
                                
                            elif not u.is_air:
                                self.apply_push(u)

            for p in self.game.projectiles:
                if p.alive:
                    dist = self.pos.distance_to(p.pos)
                    if dist < SHOCK_RANGE:
                        dir_to_target = (p.pos - self.pos).normalize()
                        
                        if forward_vec.dot(dir_to_target) > 0:
                            self.reflect_projectile(p, dir_to_target)
        if not self.game.is_online or self.game.my_role == "HOST":
            self.game.net_events.append({
                "type": "FX_SHOCKWAVE",
                "x": int(self.pos.x), "y": int(self.pos.y),
                "radius": SHOCK_RANGE,
                "angle": self.angle 
            })
    def apply_push(self, target, force_mult=1.0):
        push_dir = (target.pos - self.pos).normalize()
        
        weight = getattr(target, 'weight', 1.0)
        if isinstance(target, (TerminatorIFV, M1A2, Type99)): weight = 5.0
        
        dist = self.pos.distance_to(target.pos)
        dist_factor = 1.0 - (dist / SHOCK_RANGE)
        
        force = 10 * SHOCK_FORCE * dist_factor * force_mult / weight
        
        target.unbalanced = True
        target.unbalanced_timer = int(60 * dist_factor)
        target.drift_vel = push_dir * force
        target.pusher_team = self.team

    def reflect_projectile(self, p, push_dir):
        
        p.team = self.team
        
        
        if p.vel.length() > 0:
            p.vel = -p.vel 
        
        p.vel += push_dir * 5 
        
        p.target = None
        p.target_dest = None
        
        p.life_time += 60
        
        p.d_type = "deflected" 

    def update(self):
        super().update()
        if self.shock_cooldown > 0: self.shock_cooldown -= 1
        print(f"Angle: {self.angle}")
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        w, h = 90, 60 
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        
        C_TRACK = (40, 40, 45)      
        C_ARMOR_MAIN = (130, 135, 140) 
        C_ARMOR_DARK = (90, 95, 100)   
        C_ARMOR_LIGHT = (160, 165, 170)
        C_GUN_BARREL = (60, 65, 70)    
        C_GLOW_BLUE = (0, 220, 255)    
        C_GLOW_CORE = (200, 240, 255)  
        
        track_w = 12
        pygame.draw.rect(surf, C_TRACK, (0, 0, w, track_w))
        pygame.draw.rect(surf, C_ARMOR_DARK, (5, 0, w-10, track_w-2)) 
        pygame.draw.rect(surf, C_TRACK, (0, h-track_w, w, track_w))
        pygame.draw.rect(surf, C_ARMOR_DARK, (5, h-track_w+2, w-10, track_w-2))
        
        for i in range(3):
            lx = 20 + i * 20
            pygame.draw.rect(surf, C_GLOW_BLUE, (lx, 2, 10, 3))
            pygame.draw.rect(surf, C_GLOW_BLUE, (lx, h-5, 10, 3))

        body_rect = pygame.Rect(5, track_w-2, w-10, h - 2*track_w + 4)
        pygame.draw.rect(surf, C_ARMOR_MAIN, body_rect)
        pygame.draw.polygon(surf, C_ARMOR_LIGHT, [
            (w-5, track_w), (w, cy), (w-5, h-track_w), (w-20, h-track_w), (w-20, track_w)
        ])
        for i in range(4):
            x = 10 + i*4
            pygame.draw.line(surf, C_ARMOR_DARK, (x, cy-10), (x, cy+10), 2)

        turret_pts = [
            (cx+15, cy-12), (cx-20, cy-15), 
            (cx-30, cy-8), (cx-30, cy+8),   
            (cx-20, cy+15), (cx+15, cy+12), 
            (cx+25, cy)                     
        ]
        pygame.draw.polygon(surf, C_ARMOR_MAIN, turret_pts)
        pygame.draw.polygon(surf, C_ARMOR_DARK, turret_pts, 2) 
        
        pygame.draw.rect(surf, C_GLOW_BLUE, (cx-10, cy-10, 6, 4))
        pygame.draw.rect(surf, C_GLOW_BLUE, (cx-10, cy+6, 6, 4))

        rail_len = 50
        rail_base_w = 10
        rail_tip_w = 8
        
        start_x = cx + 10
        end_x = start_x + rail_len
        
        pygame.draw.polygon(surf, C_GUN_BARREL, [
            (start_x, cy-rail_base_w), (end_x, cy-rail_tip_w),
            (end_x, cy-2), (start_x, cy-3)
        ])
        pygame.draw.polygon(surf, C_GUN_BARREL, [
            (start_x, cy+rail_base_w), (end_x, cy+rail_tip_w),
            (end_x, cy+2), (start_x, cy+3)
        ])
        
        for i in range(3):
            rx = start_x + 10 + i * 12
            pygame.draw.rect(surf, C_ARMOR_LIGHT, (rx, cy-rail_base_w+1, 6, 2*rail_base_w-2))

        if self.shock_cooldown > 0:
            charge_pct = 1.0 - (self.shock_cooldown / self.shock_max_cooldown)
        else:
            charge_pct = 1.0 
            
        if charge_pct > 0.1:
            glow_len = rail_len * charge_pct
            glow_rect = (start_x, cy-2, glow_len, 4)
            
            pygame.draw.rect(surf, C_GLOW_CORE, glow_rect)
            pygame.draw.line(surf, C_GLOW_BLUE, (start_x, cy-3), (start_x+glow_len, cy-3), 1)
            pygame.draw.line(surf, C_GLOW_BLUE, (start_x, cy+3), (start_x+glow_len, cy+3), 1)
            
            if charge_pct > 0.8:
                r = 4 + random.randint(0, 2)
                pygame.draw.circle(surf, C_GLOW_BLUE, (end_x, cy), r)
                pygame.draw.circle(surf, C_GLOW_CORE, (end_x, cy), r-2)
                
                if random.random() < 0.3:
                    arc_end = (end_x + random.randint(5, 15), cy + random.randint(-10, 10))
                    pygame.draw.line(surf, C_GLOW_BLUE, (end_x, cy), arc_end, 1)

        if self.shock_cooldown > self.shock_max_cooldown - 5: 
            muzzle_x = end_x
            pygame.draw.line(surf, C_GLOW_CORE, (muzzle_x, cy), (muzzle_x+40, cy), 6)
            pygame.draw.circle(surf, C_GLOW_BLUE, (muzzle_x, cy), 15)
            for _ in range(3):
                lx = muzzle_x + random.randint(0, 20)
                ly = cy + random.randint(-15, 15)
                pygame.draw.line(surf, C_GLOW_BLUE, (muzzle_x, cy), (lx, ly), 2)

        scaled_surf = pygame.transform.smoothscale(surf, (int(w * zoom), int(h * zoom)))
        rotated_surf = pygame.transform.rotate(scaled_surf, self.angle)
        
        rect = rotated_surf.get_rect(center=screen_pos)
        surface.blit(rotated_surf, rect)
        
        if self.shock_cooldown > 0:
            bar_w = 40 * zoom
            bx = screen_pos[0] - bar_w / 2
            by = screen_pos[1] - 35 * zoom
            pygame.draw.rect(surface, (0,0,0), (bx, by, bar_w, 4))
            pygame.draw.rect(surface, C_GLOW_BLUE, (bx, by, bar_w * charge_pct, 4))
            
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

class MissileBoat(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.view_radius = 600        
        self.hp = 600
        self.max_hp = 600
        self.armor=5
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
        rotated_img = pygame.transform.rotate(scaled_img, self.angle) 
        
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
        self.armor=15
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
            img = pygame.image.load(path).convert_alpha()
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
        
        scaled_hull = scale_img(self.image, zoom)
        rot_hull = pygame.transform.rotate(scaled_hull, self.angle) 
        rot_hull = pygame.transform.rotate(scaled_hull, self.angle)
        
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
        self.armor=15
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
                diff = fire_target.pos - self.pos
                self.turret_angle = math.degrees(math.atan2(-diff.y, diff.x))
                
                dist = self.pos.distance_to(fire_target.pos)
                if dist < self.attack_range:
                    if self.attack_cooldown <= 0:
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
        
        scaled_hull = scale_img(self.hull_image, zoom)
        rot_hull = pygame.transform.rotate(scaled_hull, self.angle) 
        rect_hull = rot_hull.get_rect(center=screen_pos)
        surface.blit(rot_hull, rect_hull)
        
        
        launcher_offsets = [
            vec(-40 * zoom, -20 * zoom), 
            vec(-40 * zoom,  20 * zoom)  
        ]
        
        scaled_launcher = scale_img(self.turret_image, zoom)
        rot_launcher = pygame.transform.rotate(scaled_launcher, self.turret_angle)
        
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
        self.armor=15
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
        
        scaled = scale_img(self.hull_image, zoom)
        rotated = pygame.transform.rotate(scaled, self.angle)
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

class ScoutDrone(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = 50
        self.speed = 5.0
        self.is_air = True
        self.parent_ship = None
        
    def update(self):
        if self.parent_ship and self.parent_ship.alive:
            pass
        else:
            self.hp = 0
            
        super().update()


class Type99(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = TYPE99_STATS[2]
        self.hp = self.max_hp
        self.speed = TYPE99_STATS[1]
        self.attack_range = TYPE99_STATS[0]
        self.armor=15
        self.damage = 90
        self.radius = 28
        self.rect = pygame.Rect(pos.x-28, pos.y-28, 56, 56)
        self.is_mechanical = True
        
        self.turret_angle = 0
        
        self.body_image = self.generate_body_image()
        self.turret_image = self.generate_turret_image()

    def generate_body_image(self):
        surf = pygame.Surface((90, 70), pygame.SRCALPHA)
        
        C_BASE_GREEN = (80, 100, 70)
        C_CAMO_DARK  = (50, 60, 50)
        C_TRACKS     = (30, 30, 30)
        C_DETAIL     = (40, 45, 40)
        C_CAMO_LIGHT = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"]) 

        pygame.draw.rect(surf, C_TRACKS, (10, 5, 60, 12))
        pygame.draw.rect(surf, C_TRACKS, (10, 53, 60, 12))
        for i in range(12, 70, 6):
            pygame.draw.line(surf, (50,50,50), (i, 5), (i, 17), 1)
            pygame.draw.line(surf, (50,50,50), (i, 53), (i, 65), 1)

        pygame.draw.rect(surf, C_BASE_GREEN, (10, 12, 62, 46))
        pygame.draw.rect(surf, C_CAMO_DARK, (12, 12, 58, 4))
        pygame.draw.rect(surf, C_CAMO_DARK, (12, 54, 58, 4))
        pygame.draw.polygon(surf, C_CAMO_LIGHT, [(72, 12), (78, 35), (72, 58)])
        pygame.draw.rect(surf, C_DETAIL, (10, 25, 8, 20))
        for i in range(3):
            pygame.draw.line(surf, (20,20,20), (12, 28+i*6), (16, 28+i*6), 1)
            
        for _ in range(5):
            rx = random.randint(20, 60)
            ry = random.randint(15, 55)
            c = random.choice([C_CAMO_LIGHT, C_CAMO_DARK])
            pygame.draw.rect(surf, c, (rx, ry, 6, 6))
            
        return surf

    def generate_turret_image(self):
        
        surf = pygame.Surface((90, 70), pygame.SRCALPHA)
        
        C_BASE_GREEN = (80, 100, 70)
        C_CAMO_DARK  = (50, 60, 50)
        C_BARREL     = (60, 65, 60)
        C_DETAIL     = (40, 45, 40)
        C_ERA        = (90, 110, 80)
        
        
        barrel_len = 45
        pygame.draw.rect(surf, C_BARREL, (50, 26, barrel_len, 5))
        pygame.draw.rect(surf, C_DETAIL, (55, 26, 8, 5))
        pygame.draw.rect(surf, C_BARREL, (50, 39, barrel_len, 5))
        pygame.draw.rect(surf, C_DETAIL, (55, 39, 8, 5))
        
        turret_pts = [
            (30, 20), (60, 25), (65, 35), (60, 45), (30, 50)
        ]
        pygame.draw.polygon(surf, C_BASE_GREEN, turret_pts)
        
        pygame.draw.polygon(surf, C_ERA, [(45, 22), (60, 25), (62, 33), (48, 30)])
        pygame.draw.line(surf, C_DETAIL, (45, 22), (62, 33), 1)
        pygame.draw.polygon(surf, C_ERA, [(45, 48), (60, 45), (62, 37), (48, 40)])
        pygame.draw.line(surf, C_DETAIL, (45, 48), (62, 37), 1)
        
        pygame.draw.circle(surf, C_CAMO_DARK, (45, 30), 5)
        pygame.draw.circle(surf, C_CAMO_DARK, (45, 40), 4)
        
        pygame.draw.rect(surf, (40, 50, 40), (32, 18, 8, 8))
        pygame.draw.circle(surf, (100, 0, 50), (36, 22), 2)
        
        return surf

    def update(self):
        super().update() 
        
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        
        if not self.game.is_online or self.game.my_role == "HOST":
            
            current_target = None
            
            if self.target_entity and self.target_entity.alive:
                if self.pos.distance_to(self.target_entity.pos) < self.attack_range:
                    current_target = self.target_entity
                else:
                    current_target = self.target_entity
            
            else:
                self.target_entity = None 
                current_target = self.find_nearest_enemy()
            
            if current_target:
                diff = current_target.pos - self.pos
                target_angle = math.degrees(math.atan2(-diff.y, diff.x))
                self.turret_angle = target_angle
                
                if self.pos.distance_to(current_target.pos) < self.attack_range:
                    if self.attack_cooldown <= 0:
                        self.perform_attack(current_target)
            else:
                pass

    def perform_attack(self, target):
        
        if self.attack_cooldown > 0:
            return 

        offset_1 = vec(40, -9).rotate(-self.turret_angle)
        offset_2 = vec(40, 4).rotate(-self.turret_angle)
        
        dmg_per_shot = self.damage 
        
        p1 = Projectile(self.game, self.pos + offset_1, target, self.team, dmg_per_shot, "tank_shell", breakshellvalue=self.breakarmorvalue)
        p2 = Projectile(self.game, self.pos + offset_2, target, self.team, dmg_per_shot,"tank_shell", breakshellvalue=self.breakarmorvalue)
        
        self.game.projectiles.append(p1)
        self.game.projectiles.append(p2)
        
        self.attack_cooldown = 70

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        
        scaled_body = scale_img(self.body_image, zoom)
        rot_body = pygame.transform.rotate(scaled_body, self.angle)
        body_rect = rot_body.get_rect(center=screen_pos)
        surface.blit(rot_body, body_rect)
        
        turret_offset = vec(5, 0).rotate(-self.angle) 
        
        turret_pos = self.pos + turret_offset
        turret_screen_pos = to_screen(turret_pos, offset, zoom)
        
        scaled_turret = scale_img(self.turret_image, zoom)
        rot_turret = pygame.transform.rotate(scaled_turret, self.turret_angle) 
        turret_rect = rot_turret.get_rect(center=turret_screen_pos)
        surface.blit(rot_turret, turret_rect)
        
        self.draw_health_and_marker(surface, offset, zoom)

class DroneCarrier(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.detectrange=0
        self.max_hp = DRONECARRIER_STATS[2]
        self.hp = self.max_hp
        self.speed = DRONECARRIER_STATS[1]
        self.is_mechanical = True
        self.radius = 25

        self.rect = pygame.Rect(pos.x-25, pos.y-25, 50, 50)
        
        self.carrier_state = "MOBILE" 
        self.spawn_timer = 0
        self.spawn_interval = 300 
        self.self_dmg_rate = 5    
        self.door_open_factor = 0.0        
    def toggle_mode(self):
        if self.carrier_state == "MOBILE":
            self.carrier_state = "DEPLOYED"
            self.speed = 0 
            self.angle = (self.angle + 180) % 360 
            self.game.particles.add(FloatingText(self.pos, "DEPLOYING...", YELLOW))
        else:
            self.carrier_state = "MOBILE"
            self.speed = 2.0
            self.angle = (self.angle + 180) % 360

            self.game.particles.add(FloatingText(self.pos, "MOBILE MODE", GREEN_HAT))

    def update(self):
        if self.carrier_state == "MOBILE":
            self.min_dist=0
            super().update()
        else:
            self.update_rect() 
            
            if self.game.frame_count % 30 == 0:
                self.hp -= 5
                if self.hp <= 0: self.die()
            
            self.spawn_timer += 1
            if self.spawn_timer >= self.spawn_interval:
                self.spawn_timer = 0
                self.spawn_drone()

    def spawn_drone(self):
        offset = vec(random.randint(-30, 30), random.randint(-30, 30))
        drone = SuicideDrone(self.game, self.pos + offset, self.team)
        self.game.all_units.append(drone)
        self.game.particles.add(FloatingText(self.pos, "+DRONE", CYAN))

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 200 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return              
        width = 30 * zoom  
        length = 50 * zoom 
        
        C_BODY = (60, 65, 70)       
        C_ROOF = (80, 85, 90)       
        C_WINDSHIELD = (40, 50, 60) 
        C_TIRE = (20, 20, 20)
        C_DOOR_INNER = (15, 15, 15) 
        C_DOOR_PLATE = (70, 75, 80) 
        C_TEAM = TEAM_COLORS.get(self.team, (200, 200, 200))
        
        target_open = 1.0 if self.carrier_state == "DEPLOYED" else 0.0
        
        if not hasattr(self, 'door_open_factor'): 
            self.door_open_factor = 0.0
        
        if self.door_open_factor < target_open: 
            self.door_open_factor += 0.05
        elif self.door_open_factor > target_open: 
            self.door_open_factor -= 0.05
        self.door_open_factor = max(0.0, min(1.0, self.door_open_factor))

        surf_size = int(length * 1.8) 
        surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        cx, cy = surf_size // 2, surf_size // 2
        
        rect_body = pygame.Rect(cx - length/2, cy - width/2, length, width)
        
        wheel_offset_x = length * 0.35
        wheel_dims = (length * 0.25, width * 0.2)
        pygame.draw.rect(surf, C_TIRE, (cx - wheel_offset_x, cy - width/2 - 2*zoom, wheel_dims[0], width + 4*zoom))
        pygame.draw.rect(surf, C_TIRE, (cx + wheel_offset_x - wheel_dims[0], cy - width/2 - 2*zoom, wheel_dims[0], width + 4*zoom))
        
        pygame.draw.rect(surf, C_BODY, rect_body, border_radius=int(4*zoom))
        rect_roof = rect_body.inflate(-length*0.2, -width*0.2)
        pygame.draw.rect(surf, C_ROOF, rect_roof, border_radius=int(2*zoom))
        
        pygame.draw.rect(surf, C_WINDSHIELD, (cx + length*0.35, cy - width*0.3, length*0.1, width*0.6))
        
        pygame.draw.rect(surf, C_TEAM, (cx - length*0.2, cy - width*0.4, length*0.4, width*0.8), 1)

        tail_x = cx - length/2 
        
        if self.door_open_factor > 0.1:
            pygame.draw.rect(surf, C_DOOR_INNER, (tail_x + 2*zoom, cy - width*0.35, length*0.15, width*0.7))
            
            if self.carrier_state == "DEPLOYED":
                t = pygame.time.get_ticks() 
                if (t // 500) % 2 == 0: 
                    pygame.draw.rect(surf, (255, 200, 50), (tail_x + 2*zoom, cy - width*0.2, 4*zoom, width*0.4))

        door_len = width / 2 
        door_thick = 3 * zoom
        
        swing_angle = 135 * self.door_open_factor
        
        pivot_top = vec(tail_x, cy - width/2 + 1*zoom)
        pivot_bot = vec(tail_x, cy + width/2 - 1*zoom)
        
        vec_door_top = vec(0, door_len).rotate(-swing_angle)
        end_top = pivot_top + vec_door_top
        
        pygame.draw.line(surf, C_DOOR_PLATE, pivot_top, end_top, int(door_thick))
        
        vec_door_bot = vec(0, -door_len).rotate(swing_angle)
        end_bot = pivot_bot + vec_door_bot
        
        pygame.draw.line(surf, C_DOOR_PLATE, pivot_bot, end_bot, int(door_thick))

        rot_surf = pygame.transform.rotate(surf, self.angle)
        rect = rot_surf.get_rect(center=screen_pos)
        surface.blit(rot_surf, rect)
        
        self.draw_health_and_marker(surface, offset, zoom)

class SuicideDrone(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.is_mechanical=True
        self.max_hp = 50 
        self.hp = 50
        self.speed = 3.5 
        self.radius = 8
        self.turn_speed = 30
        self.rect = pygame.Rect(pos.x-8, pos.y-8, 16, 16)
        self.blast_range = 60
        self.damage = 300 

    def update(self):
        if not self.target_entity or not self.target_entity.alive:
            self.target_entity = self.find_nearest_enemy()
        
        if self.target_entity and self.target_entity.team!="neutral":
            dist = self.pos.distance_to(self.target_entity.pos)
            if dist < 20: 
                self.explode()
            else:
                self.move_to(self.target_entity.pos)
                super().update() 
        else:
            super().update() 

    def explode(self):
        p = Projectile(self.game, self.pos, None, self.team, self.damage, "rocket", is_aoe=True, aoe_radius=self.blast_range,breakshellvalue=self.breakarmorvalue)
        p.on_hit(None) 
        self.die()
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        size_base = 24 
        scaled_size = int(size_base * zoom)
        
        surf = pygame.Surface((scaled_size, scaled_size), pygame.SRCALPHA)
        cx, cy = scaled_size // 2, scaled_size // 2
        
        C_METAL = (150, 155, 160) 
        C_DARK  = (50, 50, 60)    
        C_TEAM  = TEAM_COLORS.get(self.team, (200, 200, 200))
        t = pygame.time.get_ticks()
        pulse = (math.sin(t * 0.03) + 1) / 2 
        
        C_BOMB_CORE = (255, 50 + int(100 * pulse), 50 + int(100 * pulse)) 
        C_BOMB_OUTER = (180, 0, 0)
        run_cycle = 0
        if self.target_entity:
            run_cycle = math.sin(t * 0.05) * (4 * zoom) 
        
        pygame.draw.circle(surf, C_DARK, (cx - 2*zoom + run_cycle, cy + 4*zoom), 2.5*zoom)
        pygame.draw.circle(surf, C_DARK, (cx - 2*zoom - run_cycle, cy - 4*zoom), 2.5*zoom)
        
        pygame.draw.circle(surf, C_METAL, (cx, cy), 5*zoom)
        pygame.draw.circle(surf, C_TEAM, (cx - 2*zoom, cy), 3*zoom)
        
        bomb_pos = (cx + 3*zoom, cy)
        bomb_radius = 4 * zoom
        
        pygame.draw.circle(surf, C_BOMB_OUTER, bomb_pos, bomb_radius)
        pygame.draw.circle(surf, C_BOMB_CORE, bomb_pos, bomb_radius * 0.6)
        
        if pulse > 0.5:
            glow_surf = pygame.Surface((scaled_size, scaled_size), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (255, 0, 0, 60), bomb_pos, bomb_radius * 1.5)
            surf.blit(glow_surf, (0,0), special_flags=pygame.BLEND_RGBA_ADD)

        rot_surf = pygame.transform.rotate(surf, self.angle)
        
        rect = rot_surf.get_rect(center=screen_pos)
        surface.blit(rot_surf, rect)

class TankCarrier(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        
        self.max_hp = TANKCARRIER_STATS[2]
        self.hp = self.max_hp
        self.speed = TANKCARRIER_STATS[1]
        self.radius = 35
        self.rect = pygame.Rect(pos.x-35, pos.y-35, 70, 70)
        self.is_mechanical = True
        
        self.cargo = []
        self.capacity_infantry = 5
        self.capacity_tank = 1
        self.loaded_tank = None 
        
        self.flame_range = 200
        self.flame_damage = 3
        self.flame_cooldown = 0
        self.attack_range=100
        self.armor=15
        self.tank_range = 0
        self.tank_damage = 0
        self.tank_cooldown = 0
        self.turret_angle = 0
        
        self.body_image = self.generate_body_image()
        self.tank_image = self.generate_tank_image() 


    def generate_body_image(self):
        w, h = 110, 60
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w//2, h//2
        
        C_BODY   = (90, 95, 100)    
        C_DECK   = (60, 60, 65)     
        C_TREAD  = (35, 35, 40)     
        C_MECH   = (50, 50, 55)     
        C_FLAME  = (40, 45, 50)     
        C_TANK   = (180, 50, 50)    
        C_GLASS  = (20, 40, 50)     
        
        track_h = 14
        pygame.draw.rect(s, C_TREAD, (0, 0, w, track_h))
        for i in range(0, w, 6): 
            pygame.draw.line(s, (20,20,20), (i, 0), (i, track_h), 1)
        pygame.draw.rect(s, C_TREAD, (0, h-track_h, w, track_h))
        for i in range(0, w, 6):
            pygame.draw.line(s, (20,20,20), (i, h-track_h), (i, h), 1)

        body_rect = pygame.Rect(5, 10, w-5, h-20)
        pygame.draw.rect(s, C_BODY, body_rect)
        pygame.draw.rect(s, (70,75,80), body_rect, 1) 

        deck_x = 10
        deck_w = 70
        deck_rect = pygame.Rect(deck_x, 15, deck_w, h-30)
        pygame.draw.rect(s, C_DECK, deck_rect)
        
        for i in range(deck_x, deck_x+deck_w, 8):
            pygame.draw.line(s, (50,50,55), (i, 15), (i, h-15), 1)
        for i in range(15, h-15, 8):
            pygame.draw.line(s, (50,50,55), (deck_x, i), (deck_x+deck_w, i), 1)
            
        pygame.draw.rect(s, C_MECH, (deck_x+5, 12, deck_w-10, 4)) 
        pygame.draw.rect(s, C_MECH, (deck_x+5, h-16, deck_w-10, 4)) 
        
        for cx_pos in [deck_x+15, deck_x+45]:
            pygame.draw.rect(s, (200, 180, 50), (cx_pos, 16, 6, 3)) 
            pygame.draw.rect(s, (200, 180, 50), (cx_pos, h-19, 6, 3))

        pygame.draw.polygon(s, C_MECH, [(5, 15), (0, 10), (0, h-10), (5, h-15)])

        cab_x = deck_x + deck_w + 2
        cab_w = 18
        cab_rect = pygame.Rect(cab_x, 12, cab_w, h-24)
        pygame.draw.rect(s, C_BODY, cab_rect)
        
        pygame.draw.rect(s, C_GLASS, (cab_x+10, 15, 6, 10)) 
        pygame.draw.rect(s, C_GLASS, (cab_x+10, h-25, 6, 10)) 
        pygame.draw.rect(s, C_GLASS, (cab_x+2, 15, 6, 8))
        pygame.draw.rect(s, C_GLASS, (cab_x+2, h-23, 6, 8))
        pygame.draw.line(s, (100, 200, 255), (cab_x+12, 16), (cab_x+12, 24), 1)

        flame_base_x = cab_x + cab_w
        
        pygame.draw.rect(s, C_TANK, (cab_x, 10, 12, 4)) 
        pygame.draw.rect(s, C_TANK, (cab_x, h-14, 12, 4)) 
        
        pygame.draw.rect(s, C_FLAME, (flame_base_x, 15, 8, 30))
        
        nozzle_len = 12
        pygame.draw.rect(s, (30,30,30), (flame_base_x+8, 18, nozzle_len, 6))
        pygame.draw.rect(s, (80,80,80), (flame_base_x+8, 18, 4, 6)) 
        pygame.draw.circle(s, (20,20,20), (flame_base_x+8+nozzle_len, 21), 2) 
        pygame.draw.circle(s, (255, 150, 0), (flame_base_x+8+nozzle_len, 23), 1)
        
        pygame.draw.rect(s, (30,30,30), (flame_base_x+8, 36, nozzle_len, 6))
        pygame.draw.rect(s, (80,80,80), (flame_base_x+8, 36, 4, 6))
        pygame.draw.circle(s, (20,20,20), (flame_base_x+8+nozzle_len, 39), 2)
        pygame.draw.circle(s, (255, 150, 0), (flame_base_x+8+nozzle_len, 37), 1)

        return s
    def generate_tank_image(self):
        s = pygame.Surface((70, 50), pygame.SRCALPHA)
        cx, cy = 35, 25
        c_team = TEAM_COLORS.get(self.team, (200, 200, 200))
        
        
        C_BASE  = (100, 120, 80)
        C_DARK  = (50, 70, 40)
        C_SAND  = (160, 150, 110)
        
        pygame.draw.rect(s, (40, 40, 45), (cx-32, cy-21, 64, 9))
        pygame.draw.rect(s, (40, 40, 45), (cx-32, cy+12, 64, 9))
        pygame.draw.line(s, C_DARK, (cx-32, cy-12), (cx+32, cy-12), 2)
        pygame.draw.line(s, C_DARK, (cx-32, cy+12), (cx+32, cy+12), 2)
        pygame.draw.rect(s, C_BASE, (cx-30, cy-12, 60, 24))
        
        turret_pts = [
            (cx+20, cy), (cx+5, cy-12), (cx-15, cy-14),
            (cx-20, cy), (cx-15, cy+14), (cx+5, cy+12)
        ]
        pygame.draw.polygon(s, C_BASE, turret_pts)
        pygame.draw.line(s, C_SAND, (cx+5, cy-12), (cx+20, cy), 2)
        pygame.draw.line(s, C_SAND, (cx+5, cy+12), (cx+20, cy), 2)
        
        pygame.draw.rect(s, (30, 30, 30), (cx-12, cy-10, 6, 6))
        
        pygame.draw.line(s, (50, 50, 50), (cx+20, cy), (cx+58, cy), 3)
        
        return s

    def load_units(self):
        infantry_full = len(self.cargo) >= self.capacity_infantry
        if self.loaded_tank or (infantry_full):
            
            if self.loaded_tank and infantry_full:
                self.game.particles.add(FloatingText(self.pos, "FULL!", RED))
                return

        loaded_count = 0
        
        for u in self.game.all_units[:]:
            if u == self: continue
            if u.team != self.team: continue
            if not u.alive: continue
            if u.is_air: continue 
            
            if self.pos.distance_to(u.pos) < 100:
                
                if u.is_mechanical and isinstance(u,M1A2):
                    if not self.loaded_tank:
                        self.loaded_tank = u
                        self.tank_range = getattr(u, 'attack_range', 500)
                        self.tank_damage = getattr(u, 'damage', 160)
                        
                        self.game.all_units.remove(u)
                        loaded_count += 1
                        self.game.particles.add(FloatingText(self.pos, "TANK LOADED", GREEN_HAT))
                        continue 

                else:
                    if len(self.cargo) < self.capacity_infantry:
                        self.cargo.append(u)
                        self.game.all_units.remove(u)
                        loaded_count += 1
        
        if loaded_count > 0:
            self.game.particles.add(FloatingText(self.pos, f"LOADED {loaded_count}", GREEN_HAT))

    def unload_units(self):
        spawn_offset = vec(-60, 0).rotate(self.angle) 
        
        if self.loaded_tank:
            u = self.loaded_tank
            u.pos = self.pos + spawn_offset
            self.game.all_units.append(u)
            self.loaded_tank = None
            
        for u in self.cargo:
            u.pos = self.pos + spawn_offset + vec(random.randint(-10,10), random.randint(-10,10))
            self.game.all_units.append(u)
        self.cargo = []

    def update(self):
        super().update()
        
        if self.flame_cooldown > 0: self.flame_cooldown -= 1
        if self.tank_cooldown > 0: self.tank_cooldown -= 1
        if not self.game.is_online or self.game.my_role == "HOST":        
            target = self.target_entity or self.find_nearest_enemy()
            
            if target and target.alive:
                dist = self.pos.distance_to(target.pos)
                
                if self.loaded_tank:
                    dx, dy = target.pos.x - self.pos.x, target.pos.y - self.pos.y
                    self.turret_angle = math.degrees(math.atan2(-dy, dx))
                    
                    if dist < self.tank_range and self.tank_cooldown <= 0:
                        muzzle_off = vec(40, 0).rotate(-self.turret_angle) 
                        p = Projectile(self.game, self.pos + muzzle_off, target, self.team, self.tank_damage, "tank_shell")
                        self.game.projectiles.append(p)
                        self.tank_cooldown = 60 
                
                if dist < self.flame_range and self.flame_cooldown <= 0:
                    for _ in range(3):
                        angle_offset = random.randint(-15, 15)
                        flame_dir = vec(1, 0).rotate(-self.angle + angle_offset)
                        p = Projectile(self.game, self.pos + flame_dir*20, None, self.team, self.flame_damage, "flame",breakshellvalue=1000)
                        p.vel = flame_dir * 12
                        p.is_aoe = True
                        p.aoe_radius = 40
                        p.breakshellvalue=10000
                        self.game.projectiles.append(p)
                    self.flame_cooldown = 4 

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled_body = scale_img(self.body_image, zoom)
        rot_body = pygame.transform.rotate(scaled_body, self.angle)
        rect_body = rot_body.get_rect(center=screen_pos)
        surface.blit(rot_body, rect_body)
        
        if self.loaded_tank:
            scaled_tank = scale_img(self.tank_image, zoom)
            rot_tank = pygame.transform.rotate(scaled_tank, self.turret_angle)
            rect_tank = rot_tank.get_rect(center=screen_pos)
            
            surface.blit(rot_tank, rect_tank)
            
        if self.cargo:
            for i in range(len(self.cargo)):
                pygame.draw.circle(surface, (0, 255, 0), (screen_pos[0]-10+i*5, screen_pos[1]), 2)

        self.draw_health_and_marker(surface, offset, zoom)
class CIWS(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "ciws")
        self.hp = CIWS_STATS[2]
        self.max_hp = self.hp
        self.radius = 25
        self.rect = pygame.Rect(pos.x - 25, pos.y - 25, 50, 50)
        self.armor=15
        self.attack_range = CIWS_STATS[0]
        self.attack_cooldown = 0
        self.angle = 0
        self.target = None
        self.armor = 5
        self.breakarmorvalue = 10
        
        self.spin_up_timer = 0
        self.max_spin = 180 
        
        self.image = self.generate_image()
        self.turret_img = self.generate_turret_image()

    def update(self):
        if self.game.current_voltage > self.game.max_voltage:
            self.target = None
            self.spin_up_timer = max(0, self.spin_up_timer - 2)
            return 
            
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        if not self.game.is_online or self.game.my_role == "HOST":        
            if not self.target or not self.target.alive:
                self.target = self.find_target() 
            
            if self.target:
                dist = self.pos.distance_to(self.target.pos)
                if dist <= self.attack_range:

                    vec_to = self.target.pos - self.pos
                    self.angle = math.degrees(math.atan2(-vec_to.y, vec_to.x))
                    
                    self.spin_up_timer = min(self.max_spin, self.spin_up_timer + 1)
                    
                    progress = self.spin_up_timer / self.max_spin
                    current_cd = int(10 - 8 * progress)
                    
                    if self.attack_cooldown <= 0:
                        self.fire(progress) 
                        self.attack_cooldown = current_cd
                else:
                    self.target = None
                    self.spin_up_timer = max(0, self.spin_up_timer - 1)
            else:
                self.spin_up_timer = max(0, self.spin_up_timer - 1)

    def find_target(self):
        nearest = None
        min_dist = 99999
        enemies = [u for u in self.game.all_units if u.team != self.team]
        for e in enemies:
            
            if getattr(e, 'is_stealth', False):
                if self.pos.distance_to(e.pos) > 100: continue 
            
            dist = self.pos.distance_to(e.pos)
            if dist < min_dist and dist <= self.attack_range:
                min_dist = dist
                nearest = e
        return nearest

    def fire(self, progress):

        spread_angle = 40 * (1.0 - progress) + 5

        offset_angle = random.uniform(-spread_angle/2, spread_angle/2)
        
        
        real_target_pos = self.target.pos
        vec_to = real_target_pos - self.pos
        perp_vec = vec(-vec_to.y, vec_to.x).normalize()
        
        dist = vec_to.length()
        miss_distance = dist * math.tan(math.radians(offset_angle))
        
        fake_target_pos = real_target_pos + perp_vec * miss_distance
        
        dmg = 8 
        p = Projectile(self.game, self.pos, None, self.team, dmg, "bullet", breakshellvalue=self.breakarmorvalue)
        p.target_dest = fake_target_pos
        p.speed = 20
        
        p.vel = (fake_target_pos - self.pos).normalize() * p.speed
        
        if progress > 0.8:
            p.color = (255, 255, 200)
        else:
            p.color = (255, 200, 50)
            
        self.game.projectiles.append(p)
    def generate_image(self):
        w, h = 60, 60
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        
        C_BASE = (70, 75, 80)     
        C_TURRET = (200, 200, 210)
        C_GUN = (30, 30, 35)      
        C_RADAR = (150, 160, 170) 
        C_WARN = (200, 180, 50)   
        
        base_rect = pygame.Rect(cx-20, cy-20, 40, 40)
        pygame.draw.rect(s, C_BASE, base_rect, border_radius=8)
        pygame.draw.rect(s, (40,40,45), base_rect, 2) 
        
        pygame.draw.line(s, C_WARN, (cx-15, cy-20), (cx-5, cy-20), 3)
        pygame.draw.line(s, C_WARN, (cx+5, cy-20), (cx+15, cy-20), 3)
        pygame.draw.line(s, C_WARN, (cx-15, cy+20), (cx-5, cy+20), 3)
        pygame.draw.line(s, C_WARN, (cx+5, cy+20), (cx+15, cy+20), 3)

        return s

    def generate_turret_image(self):
        s = pygame.Surface((50, 50), pygame.SRCALPHA)
        cx, cy = 25, 25
        
        C_TURRET = (220, 220, 230) 
        C_GUN = (20, 20, 20)
        C_RADAR = (180, 190, 200)
        
        
        barrel_len = 22
        barrel_w = 6
        pygame.draw.rect(s, C_GUN, (cx+5, cy-barrel_w//2, barrel_len, barrel_w))
        pygame.draw.rect(s, (60,60,60), (cx+5+barrel_len-4, cy-barrel_w//2-1, 4, barrel_w+2))
        
        pygame.draw.circle(s, C_TURRET, (cx, cy), 12)
        pygame.draw.circle(s, (150,150,160), (cx, cy), 12, 1) 
        
        pygame.draw.circle(s, C_RADAR, (cx-2, cy), 8)
        pygame.draw.circle(s, (255,255,255), (cx-4, cy-2), 3) 
        
        pygame.draw.rect(s, (180, 180, 190), (cx-10, cy+8, 12, 8), border_radius=2)

        return s

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled_base = scale_img(self.image, zoom)
        base_rect = scaled_base.get_rect(center=screen_pos)
        surface.blit(scaled_base, base_rect)
        
        self.turret_img = self.generate_turret_image()            
        scaled_turret = scale_img(self.turret_img, zoom)        
        angle = getattr(self, 'angle', 0)
        rot_turret = pygame.transform.rotate(scaled_turret, angle)
        turret_rect = rot_turret.get_rect(center=screen_pos)
        
        shadow_dist = 3 * zoom
        shadow_surf = rot_turret.copy()
        shadow_surf.fill((0,0,0,60), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(shadow_surf, (turret_rect.x + shadow_dist, turret_rect.y + shadow_dist))
        
        surface.blit(rot_turret, turret_rect)
        
        self.draw_health_and_marker(surface, offset, zoom)
class HIMARS(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = HIMARS_STATS[2]
        self.hp = self.max_hp
        self.speed = HIMARS_STATS[1]
        self.armor=5
        self.attack_range = HIMARS_STATS[0]
        self.damage = 40 
        self.radius = 25
        self.rect = pygame.Rect(pos.x-25, pos.y-25, 50, 50)
        self.is_mechanical = True
        
        self.state = "IDLE" 
        self.deploy_timer = 0
        self.pack_timer = 0
        self.deploy_time_total = 120 
        self.attack_cooldown = 0
        
        self.original_image = pygame.Surface((80, 40), pygame.SRCALPHA)
        
        C_TIRE       = (20, 20, 25)
        C_CHASSIS    = (60, 55, 50)     
        C_BODY       = (180, 170, 140)  
        C_BOX        = (160, 150, 120)  
        C_GLASS      = (30, 40, 50)     
        C_DETAIL     = (100, 90, 80)    
        C_TEAM       = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        
        
        for tx in [60, 30, 15]:
            pygame.draw.rect(self.original_image, C_TIRE, (tx, 5, 10, 6), border_radius=2)
            pygame.draw.rect(self.original_image, C_TIRE, (tx, 29, 10, 6), border_radius=2)
            
        pygame.draw.rect(self.original_image, C_CHASSIS, (10, 12, 65, 16))
        
        cab_rect = pygame.Rect(50, 8, 25, 24)
        pygame.draw.rect(self.original_image, C_BODY, cab_rect)
        pygame.draw.rect(self.original_image, C_GLASS, (68, 10, 5, 20)) 
        pygame.draw.rect(self.original_image, C_GLASS, (60, 8, 8, 3))   
        pygame.draw.rect(self.original_image, C_GLASS, (60, 29, 8, 3))  
        pygame.draw.circle(self.original_image, C_DETAIL, (62, 20), 5)
        
        pygame.draw.rect(self.original_image, C_BODY, (10, 10, 35, 20))
        pygame.draw.circle(self.original_image, C_DETAIL, (28, 20), 12) 
        
        pygame.draw.rect(self.original_image, C_DETAIL, (20, 5, 6, 4))
        pygame.draw.rect(self.original_image, C_DETAIL, (20, 31, 6, 4))
        
        pygame.draw.rect(self.original_image, C_TEAM, (55, 15, 4, 10))
    def update(self):
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        
        
        if self.state == "IDLE" or self.state == "MOVING":
            should_check_attack = (not self.game.is_online or self.game.my_role == "HOST")
            
            if should_check_attack:
                enemy = None
                if self.target_entity and self.target_entity.alive:
                    enemy = self.target_entity
                elif not self.target_pos: 
                    enemy = self.find_nearest_enemy()
                
                if enemy:
                    dist = self.pos.distance_to(enemy.pos)
                    if dist <= self.attack_range:
                        self.target_pos = None 
                        self.state = "DEPLOYING"
                        self.deploy_timer = self.deploy_time_total
                        self.game.particles.add(FloatingText(self.pos, "DEPLOYING...", YELLOW))
                        return 
            
            if self.target_pos:
                self.state = "MOVING"
                super().update() 
            else:
                self.state = "IDLE"
                self.update_rect()

        elif self.state == "DEPLOYING":
            self.deploy_timer -= 1
            if self.deploy_timer <= 0:
                self.state = "ATTACKING"
            self.update_rect()
        
        elif self.state == "ATTACKING":
            if not self.game.is_online or self.game.my_role == "HOST":
                if self.attack_cooldown <= 0:
                    enemy = self.target_entity if (self.target_entity and self.target_entity.alive) else self.find_nearest_enemy()
                    
                    if enemy and self.pos.distance_to(enemy.pos) <= self.attack_range + 100:
                        self.fire_cluster_rocket(enemy.pos)
                        self.attack_cooldown = 300 
                    else:
                        self.state = "PACKING"
                        self.pack_timer = 60 
            
            self.update_rect()
        
        elif self.state == "PACKING":
            self.pack_timer -= 1
            if self.pack_timer <= 0:
                self.state = "IDLE"
            self.update_rect()

    def fire_cluster_rocket(self, target_pos):
        for _ in range(15): 
            offset = vec(random.randint(-80, 80), random.randint(-80, 80))
            impact_pos = vec(target_pos) + offset
            
            spawn_pos = impact_pos + vec(0, -800)
            
            proj = Projectile(self.game, spawn_pos, None, self.team, self.damage,"rocket", is_aoe=True, aoe_radius=40,breakshellvalue=self.breakarmorvalue)
            
            proj.target_dest = impact_pos
            proj.vel = vec(0, 15) 
            
            self.game.projectiles.append(proj)

        if hasattr(self.game, 'net_events'):
            self.game.net_events.append({
                "type": "EXPLOSION", 
                "x": int(self.pos.x), "y": int(self.pos.y), 
                "dt": "launch_smoke" 
            })

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 200 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return              
        scaled_chassis = scale_img(self.original_image, zoom)
        rotated_chassis = pygame.transform.rotate(scaled_chassis, self.angle)
        chassis_rect = rotated_chassis.get_rect(center=screen_pos)
        
        s_w = chassis_rect.width * 0.8
        s_h = chassis_rect.height * 0.8
        s_surf = pygame.Surface((s_w, s_h), pygame.SRCALPHA)
        pygame.draw.ellipse(s_surf, (0, 0, 0, 70), (0, 0, s_w, s_h))
        surface.blit(s_surf, (screen_pos[0]-s_w//2 + scale(5, zoom), screen_pos[1]-s_h//2 + scale(5, zoom)))
        
        surface.blit(rotated_chassis, chassis_rect.topleft)
        
        lift_progress = 0.0
        if self.state == "DEPLOYING":
            lift_progress = 1.0 - (self.deploy_timer / self.deploy_time_total)
        elif self.state == "ATTACKING":
            lift_progress = 1.0
        elif self.state == "PACKING":
            lift_progress = self.pack_timer / 60
            
        pod_l = 35
        pod_w = 16
        
        visual_len = pod_l * (1.0 - lift_progress * 0.3) 
        
        pod_surf = pygame.Surface((pod_l, pod_w), pygame.SRCALPHA)
        
        box_color = (140, 130, 100) 
        pygame.draw.rect(pod_surf, box_color, (0, 0, visual_len, pod_w), border_radius=2)
        pygame.draw.rect(pod_surf, (100, 90, 70), (visual_len/3, 0, 2, pod_w))
        pygame.draw.rect(pod_surf, (100, 90, 70), (visual_len*2/3, 0, 2, pod_w))
        
        if lift_progress > 0.1:
            tube_r = 2
            cols = 3
            rows = 2
            start_x = 2 
            for r in range(rows):
                for c in range(cols):
                    cx = start_x + c * 5
                    cy = 4 + r * 8
                    if cx < visual_len:
                        pygame.draw.circle(pod_surf, (20, 20, 20), (int(cx), int(cy)), tube_r)
                        if self.attack_cooldown <= 0: 
                            pygame.draw.circle(pod_surf, (100, 50, 50), (int(cx), int(cy)), 1)

        scaled_pod = scale_img(pod_surf, zoom)
        rotated_pod = pygame.transform.rotate(scaled_pod, self.angle)
        
        offset_dist = scale(12, zoom) 
        rad = math.radians(self.angle)
        pod_center_x = screen_pos[0] - math.cos(rad) * offset_dist
        pod_center_y = screen_pos[1] + math.sin(rad) * offset_dist 
        
        pod_rect = rotated_pod.get_rect(center=(pod_center_x, pod_center_y))
        surface.blit(rotated_pod, pod_rect.topleft)
        
        if lift_progress > 0:
            leg_len = scale(10 * lift_progress, zoom)
            
            side_x = math.cos(rad + 1.57) * scale(15, zoom)
            side_y = -math.sin(rad + 1.57) * scale(15, zoom)
            
            leg_l_start = (pod_center_x + side_x, pod_center_y + side_y)
            leg_l_end = (leg_l_start[0] + side_x/15 * leg_len, leg_l_start[1] + side_y/15 * leg_len)
            pygame.draw.line(surface, (40, 40, 40), leg_l_start, leg_l_end, 2)
            pygame.draw.circle(surface, (20, 20, 20), (int(leg_l_end[0]), int(leg_l_end[1])), 3) 
            
            leg_r_start = (pod_center_x - side_x, pod_center_y - side_y)
            leg_r_end = (leg_r_start[0] - side_x/15 * leg_len, leg_r_start[1] - side_y/15 * leg_len)
            pygame.draw.line(surface, (40, 40, 40), leg_r_start, leg_r_end, 2)
            pygame.draw.circle(surface, (20, 20, 20), (int(leg_r_end[0]), int(leg_r_end[1])), 3) 

        if self.state == "DEPLOYING":
            bar_w = scale(40, zoom)
            bar_x = screen_pos[0] - bar_w//2
            bar_y = screen_pos[1] - scale(40, zoom)
            pygame.draw.rect(surface, (0, 0, 0), (bar_x, bar_y, bar_w, 4))
            pygame.draw.rect(surface, (255, 200, 0), (bar_x, bar_y, bar_w * lift_progress, 4))
            
        self.draw_health_and_marker(surface, offset, zoom)

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
class TerminatorIFV(Unit):
    _sprite_cache = {}
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = TERMINATOR_STATS[2]
        self.hp = self.max_hp
        self.speed = TERMINATOR_STATS[1]
        self.armor=15
        self.attack_range = TERMINATOR_STATS[0]
        self.radius = 22
        self.turn_speed = 9
        self.rect = pygame.Rect(pos.x-22, pos.y-22, 44, 44)
        self.is_mechanical = True
        
        self.phase = 1 
        self.phase_hp_threshold = TERMINATOR_HP_P2 
        self.breakarmorvalue=15
        self.turret_angle = 0
        self.gun_cooldown = 0
        self.missile_cooldown = 0
        self.missile_interval = 120 
        self.recoil_timer = 0    
        self.fire_barrel_idx = 0        
        self.load_sprites()

    def load_sprites(self):
        if "body_p1" not in TerminatorIFV._sprite_cache:
            try:
                TerminatorIFV._sprite_cache["body_p1"] = pygame.image.load(resource_path("sprites/bmpt/terminator_body_p1.png")).convert_alpha()
                TerminatorIFV._sprite_cache["body_p2"] = pygame.image.load(resource_path("sprites/bmpt/terminator_body_p2.png")).convert_alpha()
                TerminatorIFV._sprite_cache["turret"] = pygame.image.load(resource_path("sprites/bmpt/terminator_turret.png")).convert_alpha()
                TerminatorIFV._sprite_cache["turret_broken"] = pygame.image.load(resource_path("sprites/bmpt/terminator_turret_broken.png")).convert_alpha()
            except Exception as e:
                print(f"Error loading sprites: {e}")
                fallback = pygame.Surface((40,40), pygame.SRCALPHA)
                pygame.draw.rect(fallback, (255,0,0), (0,0,40,40))
                for k in ["body_p1", "body_p2", "turret", "turret_broken"]:
                    TerminatorIFV._sprite_cache[k] = fallback

        self.body_img_p1 = TerminatorIFV._sprite_cache["body_p1"]
        self.body_img_p2 = TerminatorIFV._sprite_cache["body_p2"]
        self.turret_img = TerminatorIFV._sprite_cache["turret"]
        self.turret_img_broken = TerminatorIFV._sprite_cache["turret_broken"]
    def take_damage(self, amount, damage_type="normal",breakshellvalue=0):
        super().take_damage(amount, damage_type,breakshellvalue)
        
        if self.phase == 1 and self.hp <= self.phase_hp_threshold:
            self.enter_phase_2()


    def enter_phase_2(self):
        self.phase = 2
        self.speed = 0 
        self.attack_range = 400 
        self.ai_mode = "GUARD" 
        self.game.particles.add(FloatingText(self.pos, "SYSTEM CRITICAL! BUNKER MODE!", RED))
        
        for _ in range(10):
            Particle(self.game.particles, self.pos, (50,50,50), 2, 40, 5)

    def update(self):
        super().update() 
        
        if self.recoil_timer > 0: self.recoil_timer -= 1 
        if self.gun_cooldown > 0: self.gun_cooldown -= 1
        if self.missile_cooldown > 0: self.missile_cooldown -= 1
        
        if self.phase == 2 and self.game.frame_count % 10 == 0:
            Particle(self.game.particles, self.pos + vec(random.randint(-10,10), -10), (100, 100, 100), 1, 60, 5)

        if not self.game.is_online or self.game.my_role == "HOST":
            target = self.target_entity or self.find_nearest_enemy()
            
            if target and target.alive:
                dist = self.pos.distance_to(target.pos)
                
                
                if dist < self.attack_range: 
                    dx, dy = target.pos.x - self.pos.x, target.pos.y - self.pos.y
                    self.turret_angle = math.degrees(math.atan2(-dy, dx))
                    
                    if self.gun_cooldown <= 0:
                        if self.phase == 1:
                            self.fire_barrel_idx = 0 if self.game.frame_count % 10 < 5 else 1
                            off_y = -6 if self.fire_barrel_idx == 0 else 6
                            fire_delay = 5
                        else:
                            self.fire_barrel_idx = 1 
                            off_y = 6 
                            fire_delay = 3
                            
                        self.recoil_timer = 4 
                        
                        offset = vec(20, off_y).rotate(-self.turret_angle)
                        p = Projectile(self.game, self.pos+offset, target, self.team, DMG_TERMINATOR_GUN, "bullet",breakshellvalue=self.breakarmorvalue)
                        self.game.projectiles.append(p)
                        self.gun_cooldown = fire_delay
                    

                    if self.phase == 1 and self.missile_cooldown <= 0:
                        self.fire_incendiary(target)
                        self.missile_cooldown = self.missile_interval
                    if self.hp <= 0:
                        self.explode()
    def fire_incendiary(self, target):
        p = Projectile(self.game, self.pos, target, self.team, DMG_TERMINATOR_BURN,"incendiary",breakshellvalue=self.breakarmorvalue)
        p.d_type = "incendiary" 
        p.is_aoe = True
        p.aoe_radius = 60
        self.game.projectiles.append(p)

    def explode(self):
        p = Projectile(self.game, self.pos, None, self.team, 400,"behemoth_bomb", is_aoe=True, aoe_radius=200,breakshellvalue=self.breakarmorvalue)
        p.on_hit(None)
        self.die()
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 200 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return              
        
        img_body = self.body_img_p1 if self.phase == 1 else self.body_img_p2
        s_body = scale_img(img_body, zoom)
        rot_body = pygame.transform.rotate(s_body, self.angle)
        surface.blit(rot_body, rot_body.get_rect(center=screen_pos))
        
        img_turret = self.turret_img if self.phase == 1 else self.turret_img_broken
        angle = self.turret_angle 
        
        recoil_offset = vec(0, 0)
        if self.recoil_timer > 0:
            kick_back = 4 * zoom * (self.recoil_timer / 4) 
            recoil_offset = vec(-kick_back, 0).rotate(-angle)
            
        s_tur = scale_img(img_turret, zoom)
        rot_tur = pygame.transform.rotate(s_tur, angle)
        
        turret_rect = rot_tur.get_rect(center=screen_pos)
        
        if self.phase == 2:
            fixed_offset = vec(-5 * zoom, 0).rotate(-self.angle)
            turret_rect.centerx += fixed_offset.x
            turret_rect.centery += fixed_offset.y
            
        turret_rect.centerx += recoil_offset.x
        turret_rect.centery += recoil_offset.y
            
        surface.blit(rot_tur, turret_rect)
        
        if self.recoil_timer > 2:
            barrel_y = -6 if self.fire_barrel_idx == 0 else 6
            muzzle_local = vec(35, barrel_y).rotate(-angle) 
            muzzle_vec = muzzle_local * zoom
            flash_pos = (turret_rect.centerx + muzzle_vec.x, turret_rect.centery + muzzle_vec.y)
            flash_size = random.randint(8, 12) * zoom
            pygame.draw.circle(surface, (255, 150, 0), (int(flash_pos[0]), int(flash_pos[1])), int(flash_size))
            pygame.draw.circle(surface, (255, 255, 100), (int(flash_pos[0]), int(flash_pos[1])), int(flash_size * 0.6))
        
        self.draw_health_and_marker(surface, offset, zoom)


class MCV(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = 5000 
        self.hp = self.max_hp
        self.speed = 1.5 
        self.is_mechanical = True
        self.radius = 60
        self.rect = pygame.Rect(pos.x-60, pos.y-60, 120, 120)
        self.can_deploy = True

    def deploy(self):
        if self.game.is_online and self.game.my_role == "CLIENT":
            return
        test_rect = self.rect.inflate(20, 20)
        valid = True
        if test_rect.collidelist([b.rect for b in self.game.all_buildings]) != -1: valid = False
        
        if valid:
            new_base = BaseBuilding(self.game, self.pos, self.team)
            self.game.all_buildings.append(new_base)
            
            if not hasattr(self.game, 'bases'): self.game.bases = {}
            self.game.bases[self.team] = new_base
            
            if hasattr(self.game, 'my_team') and self.team == self.game.my_team:
                self.game.player_base = new_base
            
            self.die() 
            return True
        else:
            self.game.show_alert("CANNOT DEPLOY HERE")
            return False


    def draw(self, surface, offset, zoom):
        if not self.alive: return
        screen_pos = to_screen(self.pos, offset, zoom)
        
        w_raw, h_raw = 100, 80
        self.original_image = pygame.Surface((w_raw, h_raw), pygame.SRCALPHA)
        
        color_body = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        
        color_dark = (50, 50, 60)
        color_tread = (30, 30, 35)
        color_detail = (200, 200, 200) 
        
        pygame.draw.rect(self.original_image, color_tread, (5, 5, 90, 15), border_radius=5)
        pygame.draw.rect(self.original_image, color_tread, (5, 60, 90, 15), border_radius=5)
        for i in range(8):
            x = 10 + i * 11
            pygame.draw.line(self.original_image, (60,60,65), (x, 5), (x, 20), 2)
            pygame.draw.line(self.original_image, (60,60,65), (x, 60), (x, 75), 2)

        pygame.draw.rect(self.original_image, color_dark, (10, 20, 80, 40))

        head_points = [(70, 25), (95, 30), (95, 50), (70, 55)]
        pygame.draw.polygon(self.original_image, color_body, head_points)
        pygame.draw.rect(self.original_image, (50, 200, 255), (85, 32, 5, 16))

        pygame.draw.rect(self.original_image, color_body, (10, 22, 60, 36))
        pygame.draw.rect(self.original_image, (255, 255, 255), (10, 22, 60, 36), 2) 
        
        pygame.draw.line(self.original_image, color_dark, (15, 25), (65, 55), 3)
        pygame.draw.line(self.original_image, color_dark, (15, 55), (65, 25), 3)
        
        pygame.draw.rect(self.original_image, color_detail, (20, 35, 20, 10))
        
        if (pygame.time.get_ticks() // 500) % 2 == 0:
            pygame.draw.circle(self.original_image, (255, 100, 0), (50, 40), 4)

        scaled_img = scale_img(self.original_image, zoom)
        rotated_img = pygame.transform.rotate(scaled_img, self.angle)
        
        rect = rotated_img.get_rect(center=screen_pos)
        surface.blit(rotated_img, rect)
        
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
        w = scale(40, zoom)
        offset_val = math.sin(pygame.time.get_ticks() * 0.01) * scale(5, zoom)
        pygame.draw.line(surface, (50, 50, 50), screen_pos, (screen_pos[0]-scale(15,zoom), screen_pos[1]+scale(20,zoom)+offset_val), 3)
        pygame.draw.line(surface, (50, 50, 50), screen_pos, (screen_pos[0]+scale(15,zoom), screen_pos[1]+scale(20,zoom)-offset_val), 3)
        pygame.draw.circle(surface, (80, 40, 80), screen_pos, scale(15, zoom))
        pygame.draw.circle(surface, (150, 50, 150), screen_pos, scale(8, zoom)) 
        self.draw_health_and_marker(surface, offset, zoom)

class Lighthouse(Building):
    def __init__(self, game, pos):
        super().__init__(game, pos, "neutral", "lighthouse")
        self.hp = 1000
        self.max_hp = 1000
        self.radius = 40
        self.rect = pygame.Rect(pos.x-40, pos.y-40, 80, 80)
        self.image = self.generate_image()

        self.is_collapsed = False
        self.garrison = []
        self.capacity = 4
        self.attack_cooldown = 0
        self.can_garrison = True 
    def update(self):
        super().update()
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        
        if self.garrison:
            self.team = self.garrison[0].team
            
            if not self.game.is_online or self.game.my_role == "HOST":
                if self.attack_cooldown <= 0:
                    target = self.find_nearest_enemy() 
                    if target and self.pos.distance_to(target.pos)<600:
                        self.fire_barrage(target) 
        if not self.is_collapsed and self.hp <= 0:
            self.start_collapse()
    def find_nearest_enemy(self):
        nearest = None
        min_dist = 99999
        enemies = [u for u in self.game.all_units if u.team != self.team ]
        for e in enemies:

            if getattr(e, 'is_stealth', False):
                if self.pos.distance_to(e.pos) > 50: 
                    continue  
            dist = self.pos.distance_to(e.pos)
            if dist < min_dist: min_dist = dist; nearest = e
        return nearest

    def fire_barrage(self, target):
        for _ in range(len(self.garrison)):
            offset = vec(random.randint(-20,20), random.randint(-20,20))
            p = Projectile(self.game, self.pos+offset, target, self.team, 15, "heavy")
            self.game.projectiles.append(p)
        
        self.attack_cooldown = 30 

    def enter_unit(self, unit):
        from units import Rifleman
        if not isinstance(unit, Rifleman):
            return False
        if len(self.garrison) < self.capacity :
            self.garrison.append(unit)
            self.game.all_units.remove(unit) 
            return True
        return False
    def start_collapse(self):
        self.is_collapsed = True
        self.hp = 0
        self.alive = False 
        if hasattr(self.game, 'particles'):
            for _ in range(5):
                Particle(self.game.particles, self.pos, (100, 90, 80), 1, 30, 10)
    def generate_image(self):
        w, h = 160, 160
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        
        C_CONCRETE = (90, 95, 100)
        C_DARK     = (60, 65, 70)
        C_LIGHT    = (120, 125, 130)
        C_METAL    = (50, 50, 55)
        C_GLASS    = (200, 255, 255) 
        C_WARNING  = (200, 180, 50)  
        
        base_r_out = 70
        pts_out = []
        for i in range(8):
            ang = math.radians(i * 45 + 22.5)
            pts_out.append((cx + math.cos(ang)*base_r_out, cy + math.sin(ang)*base_r_out))
        pygame.draw.polygon(s, C_DARK, pts_out)
        
        base_r_in = 55
        pts_in = []
        for i in range(8):
            ang = math.radians(i * 45 + 22.5)
            pts_in.append((cx + math.cos(ang)*base_r_in, cy + math.sin(ang)*base_r_in))
        pygame.draw.polygon(s, C_CONCRETE, pts_in)
        
        for i in range(8):
            pygame.draw.line(s, C_DARK, pts_out[i], pts_in[i], 2)
            
        for i in range(0, 8, 2): 
            p1 = pts_in[i]
            p2 = pts_in[(i+1)%8]
            mid = ((p1[0]+p2[0])/2, (p1[1]+p2[1])/2)
            pygame.draw.circle(s, (20,20,20), (int(mid[0]), int(mid[1])), 6)
            pygame.draw.rect(s, (40,40,40), (mid[0]-4, mid[1]-4, 8, 8))

        tower_r = 30
        pygame.draw.circle(s, C_DARK, (cx, cy), tower_r)
        pygame.draw.rect(s, C_METAL, (cx-8, cy+tower_r, 16, 10))

        plat_r = 35
        pygame.draw.circle(s, C_CONCRETE, (cx, cy), plat_r)
        pygame.draw.circle(s, C_METAL, (cx, cy), plat_r, 2)
        pygame.draw.circle(s, C_WARNING, (cx, cy), plat_r-4, 3)

        lantern_r = 20
        pygame.draw.circle(s, C_GLASS, (cx, cy), lantern_r)
        for i in range(4):
            ang = math.radians(i * 45)
            end_x = cx + math.cos(ang) * lantern_r
            end_y = cy + math.sin(ang) * lantern_r
            pygame.draw.line(s, C_METAL, (cx, cy), (end_x, end_y), 2)
            
        pygame.draw.circle(s, C_METAL, (cx, cy), 12)
        pygame.draw.circle(s, C_LIGHT, (cx, cy), 8) 

        return s

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = screen_pos
        margin = 400 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return           
        scaled_img = scale_img(self.image, zoom)
        rect = scaled_img.get_rect(center=screen_pos)
        
        shadow_r = scale(75, zoom)
        s_surf = pygame.Surface((shadow_r*2, shadow_r*2), pygame.SRCALPHA)
        pygame.draw.circle(s_surf, (0,0,0,80), (shadow_r, shadow_r), shadow_r)
        surface.blit(s_surf, (cx - shadow_r + 10*zoom, cy - shadow_r + 10*zoom))
        
        surface.blit(scaled_img, rect)

        angle = (pygame.time.get_ticks() * 0.05) % 360
        beam_len = scale(400, zoom)
        
        beam_surf = pygame.Surface((beam_len*2, beam_len*2), pygame.SRCALPHA)
        beam_cx, beam_cy = beam_len, beam_len
        
        beam_width_angle = 30 
        
        far_half_w = beam_len * math.tan(math.radians(beam_width_angle/2))
        
        poly_pts = [
            (beam_cx, beam_cy), 
            (beam_cx + beam_len, beam_cy - far_half_w),
            (beam_cx + beam_len, beam_cy + far_half_w)
        ]
        
        pygame.draw.polygon(beam_surf, (255, 255, 255, 40), poly_pts)
        far_half_w_outer = far_half_w * 1.5
        poly_outer = [
            (beam_cx, beam_cy), 
            (beam_cx + beam_len, beam_cy - far_half_w_outer),
            (beam_cx + beam_len, beam_cy + far_half_w_outer)
        ]
        pygame.draw.polygon(beam_surf, (200, 220, 255, 20), poly_outer)
        
        rot_beam = pygame.transform.rotate(beam_surf, -angle)
        beam_rect = rot_beam.get_rect(center=screen_pos)
        
        surface.blit(rot_beam, beam_rect, special_flags=pygame.BLEND_ADD)

        if not len(self.garrison)==0:
            team_c = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
            
            flag_x = cx + scale(40, zoom)
            flag_y = cy - scale(40, zoom)
            pole_h = scale(30, zoom)
            
            pygame.draw.line(surface, (20,20,20), (flag_x, flag_y), (flag_x, flag_y - pole_h), 2)
            
            flag_w = scale(20, zoom)
            flag_h = scale(14, zoom)
            
            rect_flag = (flag_x, flag_y - pole_h, flag_w, flag_h)
            pygame.draw.rect(surface, team_c, rect_flag)
            pygame.draw.rect(surface, (0,0,0), rect_flag, 1) 
            
            for i in range(len(self.garrison)):
                dot_x = flag_x - scale(5, zoom)
                dot_y = flag_y - pole_h + i * scale(4, zoom)
                pygame.draw.circle(surface, (255, 255, 255), (dot_x, dot_y), scale(2, zoom))

        self.draw_health_and_marker(surface, offset, zoom)

class Bastion(Building):
    def __init__(self, game, pos):
        super().__init__(game, pos, "neutral", "bastion")
        self.hp = 5000 
        self.max_hp = 5000
        self.radius = 240
        self.rect = pygame.Rect(pos.x - 240, pos.y - 240, 480, 480)
        
        self.turrets = [
            {'offset': vec(-150, -150), 'angle': 0, 'cooldown': 0, 'target': None}, 
            {'offset': vec(150, -150),  'angle': 0, 'cooldown': 0, 'target': None}, 
            {'offset': vec(-150, 150),  'angle': 0, 'cooldown': 0, 'target': None}, 
            {'offset': vec(150, 150),   'angle': 0, 'cooldown': 0, 'target': None}  
        ]
        self.attack_range = 600
        self.damage = 10
        self.fire_rate = 20
        
        self.image_base = self.generate_base_image()
        self.image_turret = self.generate_turret_image()

    def generate_base_image(self):
        w, h = 600, 600
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        
        C_BASE_DARK  = (50, 50, 55)   
        C_WALL       = (80, 85, 90)   
        C_ROOF       = (100, 105, 110)
        C_DETAIL     = (40, 40, 45)   
        C_ACCENT     = TEAM_COLORS.get(self.team, (200, 200, 200))
        
        base_w = 420
        base_rect = pygame.Rect(cx - base_w//2, cy - base_w//2, base_w, base_w)
        
        pygame.draw.rect(s, C_BASE_DARK, (base_rect.left, base_rect.bottom, base_w, 40))
        pygame.draw.rect(s, C_WALL, base_rect)
        pygame.draw.rect(s, C_DETAIL, base_rect, 6)
        
        for i in range(0, base_w, 30):
            pygame.draw.line(s, (90, 95, 100), (base_rect.left + i, base_rect.top), (base_rect.left + i, base_rect.bottom), 2)
            pygame.draw.line(s, (90, 95, 100), (base_rect.left, base_rect.top + i), (base_rect.right, base_rect.top + i), 2)

        mid_w = 270
        mid_rect = pygame.Rect(cx - mid_w//2, cy - mid_w//2, mid_w, mid_w)
        pygame.draw.rect(s, (60, 60, 65), (mid_rect.left, mid_rect.bottom, mid_w, 20)) 
        pygame.draw.rect(s, C_ROOF, mid_rect)
        
        pygame.draw.rect(s, C_ACCENT, (mid_rect.left, mid_rect.top + 20, mid_w, 15))
        pygame.draw.rect(s, C_ACCENT, (mid_rect.left, mid_rect.bottom - 35, mid_w, 15))

        top_w = 150
        pygame.draw.circle(s, C_WALL, (cx, cy), top_w//2)
        pygame.draw.circle(s, C_DETAIL, (cx, cy), top_w//2, 4)
        pygame.draw.rect(s, C_DETAIL, (cx-5, cy-40, 10, 80))
        pygame.draw.ellipse(s, C_ACCENT, (cx-30, cy-10, 60, 20), 4)

        return s

    def generate_turret_image(self):
        s = pygame.Surface((80, 80), pygame.SRCALPHA)
        cx, cy = 40, 40
        
        C_GUN_BODY = (90, 100, 90)
        C_BARREL   = (30, 30, 30)
        
        pygame.draw.circle(s, (60, 60, 65), (cx, cy), 30)
        pygame.draw.circle(s, (40, 40, 45), (cx, cy), 25, 2)
        
        pygame.draw.rect(s, C_GUN_BODY, (cx-20, cy-25, 40, 50), border_radius=5)
        
        pygame.draw.rect(s, C_BARREL, (cx+10, cy-12, 35, 8))
        pygame.draw.rect(s, C_BARREL, (cx+10, cy+4, 35, 8))
        
        return s

    def update(self):
        super().update()
        
        if self.team!="neutral":
            for i, turret in enumerate(self.turrets):
                if turret['cooldown'] > 0:
                    turret['cooldown'] -= 1

                turret_world_pos = self.pos + turret['offset']
                
                target = turret['target']
                
                if not target or not target.alive or turret_world_pos.distance_to(target.pos) > self.attack_range:
                    min_dist = self.attack_range
                    best_target = None
                    
                    for u in self.game.all_units:
                        if u.team != self.team and u.alive and not u.is_air:
                            d = turret_world_pos.distance_to(u.pos)
                            if d < min_dist:
                                min_dist = d
                                best_target = u
                    
                    turret['target'] = best_target
                
                if turret['target']:
                    diff = turret['target'].pos - turret_world_pos
                    target_angle = math.degrees(math.atan2(-diff.y, diff.x))
                    
                    turret['angle'] = target_angle
                    
                    if turret['cooldown'] <= 0:
                        self.fire_turret(i, turret['target'])

    def fire_turret(self, turret_idx, target):
        turret = self.turrets[turret_idx]
        turret_pos = self.pos + turret['offset']
        
        barrel_len = 35
        
        for off_y in [-8, 8]:
            muzzle_offset = vec(barrel_len, off_y).rotate(-turret['angle'])
            spawn_pos = turret_pos + muzzle_offset
            
            p = Projectile(self.game, spawn_pos, target, self.team, self.damage, "bullet")
            p.speed = 15
            self.game.projectiles.append(p)
            
        turret['cooldown'] = self.fire_rate

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 600 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return           
        base_w_zoom = 420 * zoom
        shadow_offset = 40 * zoom 
        
        shadow_rect = pygame.Rect(
            screen_pos[0] - base_w_zoom//2 + shadow_offset, 
            screen_pos[1] - base_w_zoom//2 + shadow_offset+15, 
            base_w_zoom, 
            base_w_zoom
        )
        
        shadow_surf = pygame.Surface((int(base_w_zoom), int(base_w_zoom)), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surf, (0, 0, 0, 100), (0, 0, base_w_zoom, base_w_zoom), border_radius=int(10*zoom))
        
        surface.blit(shadow_surf, shadow_rect)

        scaled_base = scale_img(self.image_base, zoom)
        rect_base = scaled_base.get_rect(center=screen_pos)
        surface.blit(scaled_base, rect_base)
        
        scaled_turret_img = scale_img(self.image_turret, zoom)
        
        for turret in self.turrets:
            t_offset = turret['offset'] * zoom
            t_screen_pos = (screen_pos[0] + t_offset.x, screen_pos[1] + t_offset.y)
            
            rot_turret = pygame.transform.rotate(scaled_turret_img, turret['angle'])
            rect_turret = rot_turret.get_rect(center=t_screen_pos)
            
            t_shadow_surf = pygame.transform.rotate(scaled_turret_img, turret['angle'])
            t_shadow_surf.fill((0,0,0,80), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(t_shadow_surf, (rect_turret.x + 5*zoom, rect_turret.y + 5*zoom))
            
            surface.blit(rot_turret, rect_turret)

        self.draw_health_and_marker(surface, offset, zoom, y_offset=-150*zoom)
    class Dock(Building):
        def __init__(self, game, pos, angle=0):
            super().__init__(game, pos, "neutral", "dock")
            self.hp = 1000
            if angle == 0 or angle == 180:
                self.rect = pygame.Rect(pos.x-100, pos.y-30, 200, 60)
            else:
                self.rect = pygame.Rect(pos.x-30, pos.y-100, 60, 200)
            
            self.angle = angle
            self.image = self.generate_image()

        def generate_image(self):
            s = pygame.Surface((200, 60), pygame.SRCALPHA)
            pygame.draw.rect(s, (100, 90, 80), (0, 0, 200, 60)) 
            for x in range(0, 200, 10):
                pygame.draw.line(s, (80, 70, 60), (x, 0), (x, 60), 1)
            for x in range(10, 190, 30):
                pygame.draw.circle(s, (20,20,20), (x, 0), 5)
                pygame.draw.circle(s, (20,20,20), (x, 60), 5)
            return s
        
        def draw(self, surface, offset, zoom):
            pass

class CoastalGun(Building):
    def __init__(self, game, pos, team="neutral"):
        super().__init__(game, pos, team, "coastal_gun")
        self.hp = 3000
        self.max_hp = 3000
        self.radius = 60 
        self.rect = pygame.Rect(pos.x-60, pos.y-60, 120, 120)
        
        self.attack_range = 1200
        self.damage = 500
        self.attack_cooldown = 0
        self.angle = 0
        self.target_entity = None 

        self.base_image = self.generate_base_image()

    def generate_base_image(self):
        s = pygame.Surface((120, 120), pygame.SRCALPHA)
        cx, cy = 60, 60
        
        pygame.draw.circle(s, (80, 85, 90), (cx, cy), 55)
        pygame.draw.circle(s, (50, 55, 60), (cx, cy), 55, 4)
        
        pygame.draw.circle(s, (30, 30, 35), (cx, cy), 40, 8)
        
        pygame.draw.rect(s, (20,20,20), (cx-10, cy-50, 20, 20))
        
        return s

    def update(self):
        super().update()
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        
        if not self.game.is_online or self.game.my_role == "HOST":
            
            if self.target_entity:
                if not self.target_entity.alive or \
                   self.pos.distance_to(self.target_entity.pos) > self.attack_range or \
                   self.target_entity.team == self.team:
                    self.target_entity = None
            
            if not self.target_entity:
                self.target_entity = self.find_nearest_enemy()
            
            if self.target_entity:
                diff = self.target_entity.pos - self.pos
                self.angle = math.degrees(math.atan2(-diff.y, diff.x))
                
                if self.attack_cooldown <= 0 :
                    self.fire(self.target_entity)

    def find_nearest_enemy(self):
        nearest = None
        min_dist = self.attack_range
        
        for u in self.game.all_units:
            if u.alive and u.team != self.team and u.team != "neutral":
                if not getattr(u, 'is_naval', False): continue
                
                dist = self.pos.distance_to(u.pos)
                if dist < min_dist:
                    min_dist = dist
                    nearest = u
        return nearest

    def fire(self, target):
        barrel_len = 70
        offset = vec(barrel_len, 0).rotate(-self.angle)
        fire_pos = self.pos + offset
        
        dest = vec(target.pos)
        
        p = Projectile(self.game, fire_pos, None, self.team, self.damage, "heavy_shell", is_aoe=True, aoe_radius=100)
        
        p.speed = 12
        p.target_dest = dest 
        
        direction = (dest - fire_pos).normalize()
        p.vel = direction * p.speed
        
        dist = fire_pos.distance_to(dest)
        p.life_time = int(dist / p.speed) + 5 
        
        self.game.projectiles.append(p)
        self.attack_cooldown = 180

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled_base = scale_img(self.base_image, zoom)
        base_rect = scaled_base.get_rect(center=screen_pos)
        surface.blit(scaled_base, base_rect)
        
        t_w, t_h = 100, 60
        turret_surf = pygame.Surface((t_w, t_h), pygame.SRCALPHA)
        tcx, tcy = 30, 30 
        
        C_GUN = (60, 70, 60)
        C_BARREL = (40, 40, 45)
        
        pygame.draw.rect(turret_surf, C_BARREL, (tcx, tcy-6, 70, 12))
        pygame.draw.rect(turret_surf, (20,20,20), (tcx+65, tcy-8, 10, 16))
        
        pygame.draw.circle(turret_surf, C_GUN, (tcx, tcy), 25)
        pygame.draw.rect(turret_surf, C_GUN, (tcx-20, tcy-25, 40, 50))
        
        team_c = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        pygame.draw.rect(turret_surf, team_c, (tcx-10, tcy-10, 20, 20))

        scaled_turret = scale_img(turret_surf, zoom)
        
        
        rot_turret = pygame.transform.rotate(scaled_turret, self.angle)
        

        offset_vec = vec(20*zoom, 0).rotate(-self.angle)
        draw_center = (screen_pos[0] + offset_vec.x, screen_pos[1] + offset_vec.y)
        
        turret_rect = rot_turret.get_rect(center=draw_center)
        surface.blit(rot_turret, turret_rect)
        
        self.draw_health_and_marker(surface, offset, zoom, -60)

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
        self.armor=30
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
                            aoe_radius=100,breakshellvalue=self.breakarmorvalue) 
                p.speed = 35 
                p.is_aoe = True
                p.aoe_radius = 80
                
                spread = vec(random.uniform(-10, 10), random.uniform(-10, 10))
                self.game.projectiles.append(p)
            
        self.attack_cooldown = 440 

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
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
            
            pygame.draw.line(surface, (200, 200, 255, 100), (rear_x, rear_y), p_l, int(10*zoom))
            pygame.draw.line(surface, (200, 200, 255, 100), (rear_x, rear_y), p_r, int(10*zoom))

        scaled_hull = scale_img(self.hull_image, zoom)
        rot_hull = pygame.transform.rotate(scaled_hull, self.angle)
        hull_rect = rot_hull.get_rect(center=screen_pos)
        surface.blit(rot_hull, hull_rect)
        
        scaled_turret = scale_img(self.turret_image, zoom)
        rot_turret = pygame.transform.rotate(scaled_turret, self.turret_angle)
        
        for offset_vec, _ in self.turret_offsets:
            rotated_offset = offset_vec.rotate(-self.angle)
            turret_world_pos = self.pos + rotated_offset
            turret_screen_pos = to_screen(turret_world_pos, offset, zoom)
            
            t_rect = rot_turret.get_rect(center=turret_screen_pos)
            surface.blit(rot_turret, t_rect)

        self.draw_health_and_marker(surface, offset, zoom)

TRAIN_TRACK_X = 2400

class ArmoredTrain(Unit):
    def __init__(self, game, pos):
        super().__init__(game, pos, "neutral") 
        self.max_hp = 5000
        self.hp = self.max_hp
        self.speed = 3.0 
        self.radius = 40
        self.rect = pygame.Rect(pos.x-40, pos.y-40, 80, 80)
        self.is_mechanical = True
        
        self.capture_progress = 0
        self.capturing_team = None
        self.max_capture = 300 
        
        self.carriages = []
        self.spawn_carriages()
        
        self.target_pos = None 

    def spawn_carriages(self):
        for i in range(1, 4):
            offset_y = i * 90 
            c_pos = self.pos + vec(0, offset_y) 
            carriage = TrainCarriage(self.game, c_pos, self.team, self, i)
            self.game.all_units.append(carriage)
            self.carriages.append(carriage)

    def update(self):
        if not self.game.is_online or self.game.my_role == "HOST":
            capturer = None
            min_dist = 80
            for u in self.game.all_units:
                if u.alive and not u.is_air and u != self and not isinstance(u, TrainCarriage):
                    dist = self.pos.distance_to(u.pos)
                    if dist < min_dist:
                        capturer = u
                        break
            
            if capturer:
                if capturer.team != self.team:
                    if self.capturing_team != capturer.team:
                        self.capturing_team = capturer.team
                        self.capture_progress = 0 
                    self.capture_progress += 1
                    if self.capture_progress >= self.max_capture:
                        self.change_team(capturer.team)
                else: self.capture_progress = 0
            else: self.capture_progress = max(0, self.capture_progress - 0.5)
        self.move_dir = 0 
        
        if self.target_pos and self.team != "neutral":
            dest_y = self.target_pos.y
            current_y = self.pos.y
            
            if abs(dest_y - current_y) > 5:
                direction = 1 if dest_y > current_y else -1
                self.pos.y += direction * self.speed
                self.pos.x = TRAIN_TRACK_X
                self.move_dir = direction
                self.angle = -90 
            else:
                self.target_pos = None
        
        self.update_rect()
        
        if self.team != "neutral":
            if self.attack_cooldown > 0: self.attack_cooldown -= 1 
            
            enemy = self.find_nearest_enemy()
            if enemy and self.pos.distance_to(enemy.pos) < 600:
                if self.attack_cooldown <= 0:
                    self.game.projectiles.append(Projectile(self.game, self.pos, enemy, self.team, 80,"tank_shell",breakshellvalue=self.breakarmorvalue))
                    self.attack_cooldown = 60

    def change_team(self, new_team):
        self.team = new_team
        self.capture_progress = 0
        self.game.particles.add(FloatingText(self.pos, "TRAIN CAPTURED!", GREEN_HAT))
        for c in self.carriages:
            c.team = new_team

    def die(self):
        super().die()
        self.game.projectiles.append(Projectile(self.game, self.pos, None, self.team, 500,"behemoth_bomb", True, 200,breakshellvalue=self.breakarmorvalue))
        for c in self.carriages:
            if c.alive: c.die()
    def move_to(self, target_pos):
        ty = max(100, min(target_pos.y, WORLD_HEIGHT - 100))
        
        self.target_pos = vec(TRAIN_TRACK_X, ty)
        
        self.target_entity = None
        self.ai_mode = "MOVE"
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
        w = scale(48, zoom)       
        l = scale(120, zoom)      
        
        C_ARMOR_DARK  = (50, 50, 55)
        C_ARMOR_LIGHT = (80, 85, 90)     
        C_RIVET       = (30, 30, 35)
        C_CATCHER     = (40, 40, 45)
        C_STRIPE      = (240, 200, 20)   
        C_WINDOW      = (20, 30, 40)
        C_TEAM        = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        C_DETAIL      = (35, 35, 40)     
        
        direction = getattr(self, 'move_dir', -1)
        if direction == 0: direction = -1
        angle = 0 if direction == -1 else 180
        
        surf_w = int(w * 1.6) 
        surf_h = int(l * 1.3)
        img = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)
        icx, icy = surf_w // 2, surf_h // 2
        
        pygame.draw.rect(img, (0,0,0,90), (icx - w//2 + 6, icy - l//2 + 6, w, l), border_radius=6)
        
        skirt_w = w + scale(10, zoom)
        skirt_len = l - scale(25, zoom)
        skirt_rect = pygame.Rect(icx - skirt_w//2, icy - l//2 + scale(15, zoom), skirt_w, skirt_len)
        pygame.draw.rect(img, C_ARMOR_DARK, skirt_rect, border_radius=4)
        
        for i in range(0, int(skirt_len), int(scale(15, zoom))):
            py = skirt_rect.top + i
            pygame.draw.line(img, (30,30,30), (skirt_rect.left, py), (skirt_rect.left+4, py), 2)
            pygame.draw.line(img, (30,30,30), (skirt_rect.right-4, py), (skirt_rect.right, py), 2)

        
        eng_w = w - scale(8, zoom)
        eng_l = l * 0.55
        eng_y = icy - l//2 + scale(25, zoom) + eng_l//2
        eng_rect = pygame.Rect(icx - eng_w//2, eng_y - eng_l//2, eng_w, eng_l)
        pygame.draw.rect(img, C_ARMOR_LIGHT, eng_rect)
        
        fan_r = scale(10, zoom)
        pygame.draw.circle(img, C_DETAIL, (icx, int(eng_y - scale(15, zoom))), int(fan_r))
        pygame.draw.circle(img, (20,20,20), (icx, int(eng_y - scale(15, zoom))), int(fan_r)-2, 1)
        pygame.draw.line(img, (20,20,20), (icx-fan_r+2, eng_y-scale(15, zoom)), (icx+fan_r-2, eng_y-scale(15, zoom)), 2)
        pygame.draw.line(img, (20,20,20), (icx, eng_y-scale(15, zoom)-fan_r+2), (icx, eng_y-scale(15, zoom)+fan_r-2), 2)

        for i in range(4):
            vy = eng_y + scale(10, zoom) + i*scale(5, zoom)
            pygame.draw.line(img, C_DETAIL, (eng_rect.left+4, vy), (eng_rect.right-4, vy), 2)

        cab_w = w
        cab_l = l * 0.25
        cab_y = icy + l//2 - scale(20, zoom) - cab_l//2
        cab_rect = pygame.Rect(icx - cab_w//2, cab_y - cab_l//2, cab_w, cab_l)
        pygame.draw.rect(img, C_ARMOR_DARK, cab_rect) 
        top_rect = pygame.Rect(icx - cab_w//2 + 2, cab_y - cab_l//2 + 2, cab_w - 4, cab_l - 4)
        pygame.draw.rect(img, C_ARMOR_LIGHT, top_rect)
        
        win_y = top_rect.top + scale(5, zoom)
        pygame.draw.rect(img, C_WINDOW, (icx - scale(12, zoom), win_y, scale(8, zoom), scale(4, zoom)))
        pygame.draw.rect(img, C_WINDOW, (icx + scale(4, zoom), win_y, scale(8, zoom), scale(4, zoom)))
        
        link_rect = pygame.Rect(icx - eng_w//2, eng_rect.bottom, eng_w, cab_rect.top - eng_rect.bottom)
        pygame.draw.rect(img, C_DETAIL, link_rect)

        catch_y = icy - l//2 + scale(15, zoom)
        catch_h = scale(25, zoom) 
        catch_w = skirt_w + scale(4, zoom) 
        
        points = [
            (icx - catch_w//2, catch_y),      
            (icx + catch_w//2, catch_y),      
            (icx, catch_y - catch_h)          
        ]
        pygame.draw.polygon(img, C_CATCHER, points)
        pygame.draw.polygon(img, (80,80,80), points, 2) 
        
        for i in range(1, 4):
            offset_x = i * (catch_w // 8)
            pygame.draw.line(img, C_STRIPE, (icx - offset_x, catch_y), (icx, catch_y - catch_h), 2)
            pygame.draw.line(img, C_STRIPE, (icx + offset_x, catch_y), (icx, catch_y - catch_h), 2)

        turret_r = scale(10, zoom)
        pygame.draw.circle(img, (50, 50, 50), (icx, int(cab_y)), int(turret_r))
        pygame.draw.circle(img, (30, 30, 30), (icx, int(cab_y)), int(turret_r)-2, 1)
        pygame.draw.rect(img, (20,20,20), (icx-3, cab_y-scale(18, zoom), 2, scale(18, zoom)))
        pygame.draw.rect(img, (20,20,20), (icx+1, cab_y-scale(18, zoom), 2, scale(18, zoom)))
        
        pygame.draw.rect(img, C_TEAM, (icx - scale(8, zoom), eng_rect.top + scale(5, zoom), scale(16, zoom), scale(6, zoom)))
        
        light_y = catch_y + scale(2, zoom)
        pygame.draw.circle(img, (255, 255, 200), (icx - w//2 + 2, light_y), 4)
        pygame.draw.circle(img, (255, 255, 200), (icx + w//2 - 2, light_y), 4)
        pygame.draw.rect(img, (255, 255, 220), (icx - 3, light_y - 2, 6, 4))


        rotated_img = pygame.transform.rotate(img, angle)
        new_rect = rotated_img.get_rect(center=screen_pos)
        surface.blit(rotated_img, new_rect.topleft)
        
        offset_y = -(l//2 - scale(30, zoom)) * direction 
        stack_pos = (cx, cy + offset_y)
        
        if self.alive:
            t = time.time()
            for i in range(2):
                dx = math.sin(t * 4 + i*2) * scale(8, zoom)
                dy = -(t * 3 + i) % 1.0 * scale(40, zoom)
                radius = scale(8 + abs(dy)/2, zoom) 
                alpha = max(0, 120 - abs(dy)*2.5) 
                
                s_smoke = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
                pygame.draw.circle(s_smoke, (40, 40, 40, int(alpha)), (radius, radius), radius)
                surface.blit(s_smoke, (stack_pos[0] + dx - radius, stack_pos[1] + dy - radius))
        if self.capture_progress > 0:
            bar_w = scale(60, zoom)
            pct = self.capture_progress / self.max_capture
            pygame.draw.rect(surface, WHITE, (screen_pos[0]-bar_w//2, screen_pos[1]-10, bar_w, 6))
            pygame.draw.rect(surface, YELLOW, (screen_pos[0]-bar_w//2, screen_pos[1]-10, bar_w*pct, 6))
        self.draw_health_and_marker(surface, offset, zoom)

class TrainCarriage(Unit):
    def __init__(self, game, pos, team, head, index):
        super().__init__(game, pos, team)
        self.head = head
        self.index = index
        self.max_hp = 2000
        self.hp = self.max_hp

        self.rect = pygame.Rect(pos.x-30, pos.y-30, 60, 60)
        self.is_mechanical = True
        self.can_attack_air = True 
        self.radius = 20
        self.original_image = pygame.Surface((60, 100), pygame.SRCALPHA)
        
        C_BODY       = (60, 65, 70)      
        C_BODY_LIGHT = (80, 85, 90)      
        C_DETAIL     = (40, 40, 45)      
        C_COUPLER    = (30, 30, 30)      
        C_TEAM       = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        
        
        pygame.draw.rect(self.original_image, C_COUPLER, (25, 0, 10, 8))
        pygame.draw.circle(self.original_image, (20,20,20), (30, 4), 2)
        pygame.draw.rect(self.original_image, C_COUPLER, (25, 92, 10, 8))
        pygame.draw.circle(self.original_image, (20,20,20), (30, 96), 2)

        pygame.draw.rect(self.original_image, (40,45,50), (2, 10, 56, 80), border_radius=4)
        
        pygame.draw.rect(self.original_image, C_BODY, (6, 10, 48, 80))
        
        segment_h = 20
        for i in range(4):
            y = 10 + i * segment_h
            pygame.draw.rect(self.original_image, C_BODY_LIGHT, (8, y+2, 44, segment_h-4))
            pygame.draw.circle(self.original_image, C_DETAIL, (10, y+4), 1)
            pygame.draw.circle(self.original_image, C_DETAIL, (50, y+4), 1)
            pygame.draw.circle(self.original_image, C_DETAIL, (10, y+segment_h-4), 1)
            pygame.draw.circle(self.original_image, C_DETAIL, (50, y+segment_h-4), 1)

        for i in range(3):
            y = 20 + i * 25
            pygame.draw.rect(self.original_image, (20,20,20), (2, y, 4, 10))
            pygame.draw.rect(self.original_image, (20,20,20), (54, y, 4, 10))

        pygame.draw.rect(self.original_image, C_TEAM, (15, 45, 30, 10))

    def update(self):

        if self.game.is_online and self.game.my_role == "CLIENT":
            self.update_rect(); return

        if self.head and self.head.alive:
            spacing = 95
            
            
            target_y = self.head.pos.y + (self.index * spacing)
            
            self.pos.x = TRAIN_TRACK_X
            self.pos.y = target_y
            
            self.team = self.head.team
        else:
            self.hp = 0; self.alive = False

        self.update_rect()
        self.update_rect()
        
        if self.team != "neutral":
            if self.attack_cooldown > 0: self.attack_cooldown -= 1 
            
            target = self.find_nearest_enemy()
            if target and self.pos.distance_to(target.pos) < 500:
                if self.attack_cooldown <= 0:
                    if self.index % 2 == 0: 
                        self.game.projectiles.append(Projectile(self.game, self.pos, target, self.team, 60,"rocket",breakshellvalue=self.breakarmorvalue))
                        self.attack_cooldown = 120
                    else: 
                        self.game.projectiles.append(Projectile(self.game, self.pos, target, self.team, 20, "heavy",breakshellvalue=self.breakarmorvalue))
                        self.attack_cooldown = 20

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled_img = scale_img(self.original_image, zoom)
        rotated_img = pygame.transform.rotate(scaled_img, self.angle)
        rect = rotated_img.get_rect(center=screen_pos)
        
        s_w = rect.width
        s_h = rect.height
        s_surf = pygame.Surface((s_w, s_h), pygame.SRCALPHA)
        pygame.draw.rect(s_surf, (0,0,0,60), (0,0,s_w,s_h)) 
        surface.blit(s_surf, (rect.x + scale(5, zoom), rect.y + scale(5, zoom)))
        
        surface.blit(rotated_img, rect.topleft)
        
        turret_angle = getattr(self, 'turret_angle', self.angle) 
        
        turret_r = scale(14, zoom)
        barrel_len = scale(25, zoom)
        barrel_w = scale(6, zoom)
        
        rad = math.radians(turret_angle) 
        barrel_end_x = screen_pos[0] + math.cos(rad) * barrel_len
        barrel_end_y = screen_pos[1] - math.sin(rad) * barrel_len 
        
        pygame.draw.line(surface, (30, 30, 35), screen_pos, (barrel_end_x, barrel_end_y), int(barrel_w))
        muzzle_x = screen_pos[0] + math.cos(rad) * (barrel_len - 2)
        muzzle_y = screen_pos[1] - math.sin(rad) * (barrel_len - 2)
        pygame.draw.circle(surface, (20, 20, 20), (int(muzzle_x), int(muzzle_y)), int(barrel_w))

        pygame.draw.circle(surface, (90, 95, 100), screen_pos, turret_r)
        pygame.draw.circle(surface, (50, 55, 60), screen_pos, turret_r, 2) 
        
        pygame.draw.circle(surface, (70, 75, 80), screen_pos, int(turret_r * 0.6))
        team_color =  TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        pygame.draw.circle(surface, team_color, screen_pos, int(scale(4, zoom)))

        self.draw_health_and_marker(surface, offset, zoom)