import pygame
import os
import random
import math
import heapq
from core.settings import *
from core.base_classes import *
from core.utils import cached_scale_img, cached_rotate, downscale_texture

vec = pygame.math.Vector2


try:
    from pygame.math import Vector2 as vec
except ImportError:
    pass


TRAIN_TRACK_X = 2400


def _query_neighbors(game, pos, query_radius):
    """用帧初重建的空间网格（game._unit_grid）取邻近单位；网格缺失时回退全表。"""
    grid = getattr(game, '_unit_grid', None)
    if not grid:
        return game.all_units
    x0 = int((pos.x - query_radius) // GRID_CELL)
    x1 = int((pos.x + query_radius) // GRID_CELL)
    y0 = int((pos.y - query_radius) // GRID_CELL)
    y1 = int((pos.y + query_radius) // GRID_CELL)
    out = []
    for gx in range(x0, x1 + 1):
        for gy in range(y0, y1 + 1):
            bucket = grid.get((gx, gy))
            if bucket:
                out.extend(bucket)
    return out


def scale_img(img, zoom):
    # 走共享缓存（见 core/utils.cached_scale_img），摄像机平移时免重复缩放
    return cached_scale_img(img, zoom, smooth=True)


def to_screen(pos, offset, zoom):
    return (pos - offset) * zoom



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
        # A* 重算间隔按 uid 错峰，避免同批单位同帧一起重算路径造成尖峰
        self.path_recalc_timer = hash(self.uid) % 60
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
        # 障碍预扩展并烙成 35px 栅格阻挡集：邻居可达性 O(1) 查询，
        # 替代"每邻居 × 每障碍 collidepoint + inflate 分配"（单次 A* 从几十 ms 降到 ~1ms）
        cell = 35
        blocked = set()
        for obs in self._get_obstacles():
            r = obs.inflate(20, 20)
            for gx in range(int(r.left // cell), int(r.right // cell) + 1):
                for gy in range(int(r.top // cell), int(r.bottom // cell) + 1):
                    blocked.add((gx, gy))
        open_heap = [(start.distance_to(goal), 0.0, start_tuple)]
        came_from = {}
        g_score = {start_tuple: 0.0}
        closed = set()
        max_iter = 1500
        iterations = 0
        gx_goal, gy_goal = goal_tuple
        current = start_tuple
        while open_heap and iterations < max_iter:
            iterations += 1
            _, g, current = heapq.heappop(open_heap)
            if current in closed:
                continue
            closed.add(current)
            cx, cy = current
            if (cx - gx_goal)**2 + (cy - gy_goal)**2 < 1600:
                return self._reconstruct_path(came_from, current)
            for dx in [-35, 0, 35]:
                for dy in [-35, 0, 35]:
                    if dx == 0 and dy == 0:
                        continue
                    neighbor = (cx + dx, cy + dy)
                    if neighbor in closed or neighbor in blocked:
                        continue
                    tentative_g = g + (35.0 if dx == 0 or dy == 0 else 49.497)
                    if tentative_g < g_score.get(neighbor, float('inf')):
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g
                        h = math.hypot(neighbor[0] - gx_goal, neighbor[1] - gy_goal)
                        heapq.heappush(open_heap, (tentative_g + h, tentative_g, neighbor))
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
        # 索敌半径固定用侦察圈：长射程单位（火炮/战列舰）在玩家手中要可控，
        # 不能因为在 attack_range 内有敌人就自动索敌开火——打不打、打谁由玩家下令
        # （右键指定目标时走 set_target，仍可打满射程+目标半径）
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
        # 延迟导入：maps.map_data 顶层 import units，避免循环
        from maps.map_data import lake_contains, island_contains, slope_contains
        on_bridge = False
        for b in self.game.all_buildings:
            if getattr(b, 'b_type', '') == 'bridge' and not getattr(b, 'is_broken', False):
                if b.rect.inflate(10, 10).collidepoint(int(test_pos.x), int(test_pos.y)):
                    on_bridge = True
                    break

        is_naval = getattr(self, 'is_naval', False)
        in_water = False

        if hasattr(self.game, 'lakes'):
            for lake in self.game.lakes:
                if lake_contains(lake, int(test_pos.x), int(test_pos.y)):
                    l_type = lake.get('type', 'water') if isinstance(lake, dict) else 'water'
                    if l_type == 'water':
                        in_water = True
                        break
                    elif l_type == 'mountain':
                        # 山体：全阻挡（地面与海军都不许，只有空中单位可过——
                        # 空中单位不调用本判定，直接位移）
                        return False
                    elif l_type == 'cliff':
                        # 悬崖只挡地面：崖是岸边岩壁，海军沿崖底水面通行
                        #（空中单位不走本判定）；海军压在悬崖上时靠下方水域放行
                        if not is_naval:
                            return False

        if in_water and hasattr(self.game.current_map, 'islands'):
            for isle in self.game.current_map.islands:
                if island_contains(isle, int(test_pos.x), int(test_pos.y)):
                    in_water = False
                    break

        hit_building = False
        if not isinstance(self, Harvester):
            for b in self.game.all_buildings:
                if b.alive:
                    # 海军从桥下通行：跨河桥不算建筑碰撞，否则船会被桥 Rect 卡死
                    if is_naval and getattr(b, 'b_type', '') == 'bridge':
                        continue
                    if b.rect.inflate(-10, -10).collidepoint(int(test_pos.x), int(test_pos.y)):
                        hit_building = True
                        break

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
                    # 每帧 A* 预算上限：大部队同时寻路时摊到多帧，消帧尖峰
                    if getattr(self.game, '_path_budget', 0) > 0:
                        self.game._path_budget -= 1
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
                # 自动索敌结果缓存 10 帧，降低全场景扫描频率（场景单位多时 O(n²) 大头）
                scan_t = getattr(self, '_target_scan_timer', 0)
                if scan_t > 0:
                    self._target_scan_timer = scan_t - 1
                    _t = getattr(self, '_cached_target', None)
                    target_unit = _t if (_t is not None and _t.alive) else None
                else:
                    target_unit = self.find_nearest_enemy()
                    self._cached_target = target_unit
                    self._target_scan_timer = 10

        current_speed = self.speed
        if not self.is_air:
            in_slope = False
            if hasattr(self.game, 'current_map') and self.game.current_map:
                if hasattr(self.game.current_map, 'slopes'):
                    from maps.map_data import slope_contains
                    point = (int(self.pos.x), int(self.pos.y))
                    for sl in self.game.current_map.slopes:
                        if slope_contains(sl, point[0], point[1]):
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

            # 射程按目标边缘计算：dist 量到的是目标中心，建筑类目标要加其半径——
            # 否则短射程单位永远够不着"最大射程"，只能挤到墙边贴脸
            if dist <= self.attack_range + getattr(target_unit, 'radius', 0):
                # 先转向后攻击：车体/朝向未对准敌人（±12°内）时不开火
                aim = math.degrees(math.atan2(-(target_unit.pos.y - self.pos.y),
                                              target_unit.pos.x - self.pos.x))
                a_diff = abs((aim - self.angle + 180) % 360 - 180)
                if a_diff <= 12:
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
        # 邻域查询（空间网格）替代全场景扫描：单位数量多时 O(n²) -> O(n·k)
        for u in _query_neighbors(self.game, self.pos, self.radius + 60):
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

            for victim in _query_neighbors(self.game, self.pos, self.radius + 40):
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
        # 浪花颜色跟随所处水域颜色（编辑器多边形水域的自定义色）；alpha 固定 1 不透明，不继承水域透明度
        from maps.map_data import water_color_at
        w_color = water_color_at(getattr(self.game, 'lakes', []), int(self.pos.x), int(self.pos.y))
        if w_color:
            color = w_color
        else:
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
        from maps.map_data import lake_contains, island_contains

        if hasattr(self.game, 'lakes'):
            for lake in self.game.lakes:
                # 只有真水会淹人：mountain/cliff 等阻挡型条目不算水
                if isinstance(lake, dict) and lake.get('type') not in (None, 'water'):
                    continue
                if lake_contains(lake, int(self.pos.x), int(self.pos.y)):
                    in_water = True
                    break
            if in_water and hasattr(self.game.current_map, 'islands'):
                for isle in self.game.current_map.islands:
                    if island_contains(isle, int(self.pos.x), int(self.pos.y)):
                        in_water = False
                        break
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

