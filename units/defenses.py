import pygame
import random
import math
from core.settings import *
from core.base_classes import *
from .base import *

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
        self.image = self.generate_image()

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

    # ---- 静态外观（俯视）：圆形混凝土基座+拦截线圈环+电极螺栓 ----
    def generate_image(self):
        surf = pygame.Surface((64, 64), pygame.SRCALPHA)
        self._draw_static(surf, 32, 32, 1.0)
        return surf

    def _image_anchor(self):
        return 32, 32

    def _draw_static(self, surface, cx, cy, zoom):
        base_r = scale(24, zoom)
        C_BASE      = (60, 60, 65)
        C_BASE_TOP  = (90, 90, 95)
        team_c      = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        C_RING      = (180, 180, 190)
        # 阴影（保 alpha）
        s_surf = pygame.Surface((int(base_r * 2 + scale(10, zoom)),) * 2, pygame.SRCALPHA)
        so = scale(8, zoom)
        pygame.draw.circle(s_surf, (0, 0, 0, 80), (base_r + so // 2, base_r + so // 2), base_r)
        surface.blit(s_surf, (cx - base_r, cy - base_r))
        # 基座
        pygame.draw.circle(surface, C_BASE, (cx, cy), base_r)
        pygame.draw.circle(surface, C_BASE_TOP, (cx, cy), base_r - scale(4, zoom))
        pygame.draw.circle(surface, team_c, (cx, cy), base_r - scale(6, zoom), 2)
        # 拦截线圈（俯视为同心环）+ 中央发射孔
        pygame.draw.circle(surface, C_RING, (cx, cy), scale(14, zoom))
        pygame.draw.circle(surface, (70, 74, 80), (cx, cy), scale(14, zoom), 1)
        pygame.draw.circle(surface, team_c, (cx, cy), scale(9, zoom), 3)
        pygame.draw.circle(surface, (30, 30, 35), (cx, cy), scale(5, zoom))
        # 电极螺栓×8
        for i in range(8):
            ar = math.radians(45 * i)
            sr = scale(20, zoom) if i % 2 == 0 else scale(17, zoom)
            pygame.draw.circle(surface, (150, 152, 158),
                               (cx + int(sr * math.cos(ar)), cy + int(sr * math.sin(ar))),
                               max(1, int(scale(2, zoom))))

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        cx, cy = int(screen_pos[0]), int(screen_pos[1])

        team_c = (0, 150, 255) if self.team == "player" else (220, 60, 60)
        C_ELEC_CORE = (0, 200, 255)
        C_SPARK     = (220, 255, 255)
        top_r = scale(14, zoom)

        # 静态底座（PNG 优先）
        if not self._blit_cached_image(surface, cx, cy, zoom):
            self._draw_static(surface, cx, cy, zoom)

        # 动态：中央充能辉光脉冲
        pulse = (math.sin(time.time() * 15) + 1) / 2
        glow_r = scale(5 + 2 * pulse, zoom)
        g_surf = pygame.Surface((int(glow_r * 2), int(glow_r * 2)), pygame.SRCALPHA)
        pygame.draw.circle(g_surf, (0, 200, 255, 140), (int(glow_r), int(glow_r)), int(glow_r))
        surface.blit(g_surf, (cx - glow_r, cy - glow_r))

        # 动态：随机电火花（绕发射孔）
        if random.random() < 0.7:
            for _ in range(random.randint(1, 3)):
                angle = random.uniform(0, 6.28)
                dist = random.uniform(top_r, top_r * 2.5)
                start_p = (cx, cy)
                end_x = cx + math.cos(angle) * dist
                end_y = cy + math.sin(angle) * dist
                mid_x = (start_p[0] + end_x) / 2 + random.randint(-5, 5)
                mid_y = (start_p[1] + end_y) / 2 + random.randint(-5, 5)
                pygame.draw.line(surface, C_ELEC_CORE, start_p, (mid_x, mid_y), 2)
                pygame.draw.line(surface, C_ELEC_CORE, (mid_x, mid_y), (end_x, end_y), 2)
                pygame.draw.line(surface, C_SPARK, start_p, (mid_x, mid_y), 1)

        # 动态：旋转瞄准标线
        aim_vec = pygame.math.Vector2(top_r + scale(5, zoom), 0).rotate(self.angle)
        end_pos = (cx + aim_vec.x, cy + aim_vec.y)
        pygame.draw.line(surface, (50, 50, 50), (cx, cy), end_pos, 2)
        pygame.draw.circle(surface, team_c, (int(end_pos[0]), int(end_pos[1])), scale(3, zoom))

        if self.game.selected_entity == self:
            pygame.draw.circle(surface, (0, 191, 255), (cx, cy), scale(self.range, zoom), 1)
            s_range = pygame.Surface((scale(self.range*2, zoom), scale(self.range*2, zoom)), pygame.SRCALPHA)
            pygame.draw.circle(s_range, (0, 191, 255, 30), (scale(self.range, zoom), scale(self.range, zoom)), scale(self.range, zoom))
            surface.blit(s_range, (cx - scale(self.range, zoom), cy - scale(self.range, zoom)))

        self.draw_health_and_marker(surface, offset, zoom, -scale(42, zoom))


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
        self.breakarmorvalue=10
        self.image = self.generate_image()
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
                # 先转炮后打：炮塔平滑转向敌机，对准（±8°）才允许开火
                target_a = math.degrees(math.atan2(-vec_to.y, vec_to.x))
                if aim_turret(self, target_a, turn_rate=5, tolerance=8) \
                        and self.attack_cooldown <= 0:
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

    # ---- 静态外观（俯视微倾）：方形基座+南向挤出+中央旋转座环 ----
    def generate_image(self):
        surf = pygame.Surface((60, 68), pygame.SRCALPHA)
        self._draw_static(surf, 30, 34, 1.0)
        return surf

    def _image_anchor(self):
        return 30, 34

    def _draw_static(self, surface, cx, cy, zoom):
        base_w = scale(40, zoom)
        base_h = scale(12, zoom)
        C_BASE_SIDE = (50, 50, 55)
        C_BASE_TOP  = (90, 90, 95)
        # 阴影（保 alpha）
        shadow_offset = scale(8, zoom)
        s_surf = pygame.Surface((base_w * 2, base_w * 2), pygame.SRCALPHA)
        pygame.draw.rect(s_surf, (0, 0, 0, 80), (shadow_offset, shadow_offset, base_w, base_w), border_radius=int(scale(5, zoom)))
        surface.blit(s_surf, (cx - base_w // 2, cy - base_w // 2))
        # 侧立面（底部墙体向下挤出）
        pygame.draw.rect(surface, C_BASE_SIDE, (cx - base_w // 2, cy - base_w // 2, base_w, base_w + base_h), border_radius=3)
        # 顶面方座
        rect_base = pygame.Rect(cx - base_w // 2, cy - base_w // 2, base_w, base_w)
        pygame.draw.rect(surface, C_BASE_TOP, rect_base, border_radius=3)
        pygame.draw.rect(surface, (60, 60, 65), rect_base, 2, border_radius=3)
        # 中央旋转座
        pygame.draw.circle(surface, (40, 40, 40), (cx, cy), int(scale(14, zoom)))
        pygame.draw.circle(surface, (70, 70, 70), (cx, cy), int(scale(10, zoom)), 1)
        # 四角螺栓
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            pygame.draw.circle(surface, (110, 114, 120),
                               (int(cx + dx * scale(15, zoom)), int(cy + dy * scale(15, zoom))),
                               max(1, int(scale(2, zoom))))

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        cx, cy = int(screen_pos[0]), int(screen_pos[1])

        turret_w = scale(24, zoom)
        turret_l = scale(32, zoom)
        barrel_len = scale(30, zoom)
        barrel_w = scale(6, zoom)

        C_TURRET = (200, 200, 210)
        C_BARREL = (40, 40, 45)
        C_COIL   = (100, 100, 100)
        C_LENS   = (0, 255, 255)
        C_TEAM   = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])

        # 静态基座（PNG 优先）
        if not self._blit_cached_image(surface, cx, cy, zoom):
            self._draw_static(surface, cx, cy, zoom)

        # 动态：双管+炮塔体（随 angle 旋转，保留程序绘制）
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

        self.draw_health_and_marker(surface, offset, zoom, -scale(46, zoom))


class LaserTurret(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "laser_turret")
        self.hp = LASER_TURRET_STATS[2]
        self.max_hp = self.hp
        self.radius = 25
        self.rect = pygame.Rect(pos.x - 25, pos.y - 25, 50, 50)
        self.attack_range = LASER_TURRET_STATS[0]
        self.targets = []
        self.max_targets = 3
        self.image = self.generate_image()
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

    # ---- 静态外观（俯视）：方形基座+聚能环+发射核心 ----
    def generate_image(self):
        surf = pygame.Surface((48, 48), pygame.SRCALPHA)
        self._draw_static(surf, 24, 24, 1.0)
        return surf

    def _image_anchor(self):
        return 24, 24

    def _draw_static(self, surface, cx, cy, zoom):
        w = scale(40, zoom)
        # 阴影（保 alpha）
        s_surf = pygame.Surface((w + scale(8, zoom),) * 2, pygame.SRCALPHA)
        so = scale(6, zoom)
        pygame.draw.rect(s_surf, (0, 0, 0, 80), (so, so, w, w), border_radius=3)
        surface.blit(s_surf, (cx - w // 2, cy - w // 2))
        pygame.draw.rect(surface, (30, 30, 30), (cx - w // 2, cy - w // 2, w, w), border_radius=2)
        pygame.draw.rect(surface, (15, 15, 15), (cx - w // 2, cy - w // 2, w, w), 1, border_radius=2)
        # 聚能环（俯视）+ 中央发射核心
        pygame.draw.circle(surface, CYAN, (cx, cy), scale(18, zoom), 2)
        pygame.draw.circle(surface, (0, 200, 200), (cx, cy), scale(15, zoom))
        pygame.draw.circle(surface, (0, 120, 120), (cx, cy), scale(8, zoom))
        pygame.draw.circle(surface, (150, 255, 255), (cx, cy), scale(3, zoom))
        # 三向散热鳍
        for i in range(3):
            ar = math.radians(120 * i - 90)
            pygame.draw.line(surface, (0, 140, 140),
                             (cx + int(scale(10, zoom) * math.cos(ar)), cy + int(scale(10, zoom) * math.sin(ar))),
                             (cx + int(scale(17, zoom) * math.cos(ar)), cy + int(scale(17, zoom) * math.sin(ar))), 2)

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        # 静态底座（PNG 优先）
        if not self._blit_cached_image(surface, cx, cy, zoom):
            self._draw_static(surface, cx, cy, zoom)
        self.draw_health_and_marker(surface, offset, zoom, -30)


class Bunker(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "bunker")
        self.hp = BUNKER_STATS[2]
        self.max_hp = self.hp
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
        self.image = self.generate_image()
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
                    # 先转炮后打：碉堡枪口平滑转向敌人，对准（±10°）才允许开火
                    target_a = math.degrees(math.atan2(-vec_to.y, vec_to.x))
                    aimed = aim_turret(self, target_a, turn_rate=5, tolerance=10)
                else:
                    aimed = True
                if aimed and self.attack_cooldown <= 0:
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

    # ---- 静态外观（俯视）：六边形混凝土底座+沙袋+炮塔顶盖（俯视）----
    def generate_image(self):
        surf = pygame.Surface((84, 84), pygame.SRCALPHA)
        self._draw_static(surf, 42, 42, 1.0)
        return surf

    def _image_anchor(self):
        return 42, 42

    def _draw_static(self, surface, cx, cy, zoom):
        C_CONCRETE = (100, 105, 100)
        C_BORDER   = (50, 50, 50)
        C_ROOF     = (90, 100, 80)
        # 六边形底座
        pts = []
        radius = scale(32, zoom)
        for i in range(6):
            angle_rad = math.radians(60 * i)
            pts.append((cx + math.cos(angle_rad) * radius, cy + math.sin(angle_rad) * radius))
        pygame.draw.polygon(surface, C_CONCRETE, pts)
        pygame.draw.polygon(surface, C_BORDER, pts, 2)
        # 沙袋（六边中点）
        for i in range(6):
            angle_rad = math.radians(60 * i + 30)
            sx = cx + math.cos(angle_rad) * radius
            sy = cy + math.sin(angle_rad) * radius
            pygame.draw.circle(surface, (180, 160, 100), (int(sx), int(sy)), int(scale(8, zoom)))
            pygame.draw.circle(surface, (140, 120, 80), (int(sx), int(sy)), int(scale(8, zoom)), 1)
        # 炮塔顶盖（俯视圆顶，炮管/射孔为动态）
        turret_cy = cy - scale(5, zoom)
        turret_rad = scale(22, zoom)
        pygame.draw.circle(surface, C_ROOF, (cx, int(turret_cy)), int(turret_rad))
        pygame.draw.circle(surface, (60, 70, 50), (cx, int(turret_cy)), int(turret_rad), 2)
        pygame.draw.circle(surface, (100, 112, 90), (cx - int(turret_rad * 0.3), int(turret_cy - turret_rad * 0.3)), int(scale(4, zoom)))

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        cx, cy = int(screen_pos[0]), int(screen_pos[1])

        # 静态底座（PNG 优先）
        if not self._blit_cached_image(surface, cx, cy, zoom):
            self._draw_static(surface, cx, cy, zoom)

        # 动态：炮管+射孔（随 angle 旋转）
        aim_dir = pygame.math.Vector2(1, 0).rotate(-self.angle)
        turret_cy = cy - scale(5, zoom)
        turret_rad = scale(22, zoom)
        barrel_len = scale(20, zoom)
        barrel_w = scale(6, zoom)

        gun_start = pygame.math.Vector2(cx, turret_cy) + aim_dir * (turret_rad * 0.8)
        gun_end = gun_start + aim_dir * barrel_len
        pygame.draw.line(surface, (20, 20, 20), gun_start, gun_end, int(barrel_w))

        slit_center = pygame.math.Vector2(cx, turret_cy) + aim_dir * (turret_rad * 0.5)
        side_dir = pygame.math.Vector2(-aim_dir.y, aim_dir.x)
        slit_p1 = slit_center + side_dir * scale(8, zoom)
        slit_p2 = slit_center - side_dir * scale(8, zoom)
        pygame.draw.line(surface, (10, 10, 10), slit_p1, slit_p2, int(scale(3, zoom)))

        # 队伍旗帜（小杆+队色旗）
        team_c = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        flag_base = (cx, int(turret_cy))
        flag_top = (cx, int(turret_cy - scale(15, zoom)))
        pygame.draw.line(surface, (20, 20, 20), flag_base, flag_top, 2)
        pygame.draw.rect(surface, team_c, (flag_top[0], flag_top[1], scale(10, zoom), scale(6, zoom)))

        # 炮口焰
        if self.attack_cooldown > 2:
            flash_pos = gun_end + aim_dir * scale(5, zoom)
            flash_rad = scale(random.randint(4, 8), zoom)
            pygame.draw.circle(surface, (255, 200, 50), (int(flash_pos.x), int(flash_pos.y)), int(flash_rad))

        self.draw_health_and_marker(surface, offset, zoom, -scale(35, zoom))


class CIWS(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "ciws")
        self.hp = CIWS_STATS[2]
        self.max_hp = self.hp
        self.radius = 25
        self.rect = pygame.Rect(pos.x - 25, pos.y - 25, 50, 50)
        self.attack_range = CIWS_STATS[0]
        self.attack_cooldown = 0
        self.angle = 0
        self.target = None
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
                    # 先转炮后打：激光炮塔平滑转向敌人，对准（±8°）才允许开火
                    target_a = math.degrees(math.atan2(-vec_to.y, vec_to.x))
                    aimed = aim_turret(self, target_a, turn_rate=5, tolerance=8)

                    self.spin_up_timer = min(self.max_spin, self.spin_up_timer + 1)

                    progress = self.spin_up_timer / self.max_spin
                    current_cd = int(10 - 8 * progress)

                    if aimed and self.attack_cooldown <= 0:
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
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        
        scaled_base = scale_img(self.image, zoom)
        base_rect = scaled_base.get_rect(center=screen_pos)
        surface.blit(scaled_base, base_rect)
        
        self.turret_img = self.generate_turret_image()            
        scaled_turret = scale_img(self.turret_img, zoom)        
        angle = getattr(self, 'angle', 0)
        rot_turret = cached_rotate(scaled_turret, angle)
        turret_rect = rot_turret.get_rect(center=screen_pos)
        
        shadow_dist = 3 * zoom
        shadow_surf = rot_turret.copy()
        shadow_surf.fill((0,0,0,60), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(shadow_surf, (turret_rect.x + shadow_dist, turret_rect.y + shadow_dist))
        
        surface.blit(rot_turret, turret_rect)
        
        self.draw_health_and_marker(surface, offset, zoom)


        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled_base = scale_img(self.image, zoom)
        base_rect = scaled_base.get_rect(center=screen_pos)
        surface.blit(scaled_base, base_rect)
        
        self.turret_img = self.generate_turret_image()            
        scaled_turret = scale_img(self.turret_img, zoom)        
        angle = getattr(self, 'angle', 0)
        rot_turret = cached_rotate(scaled_turret, angle)
        turret_rect = rot_turret.get_rect(center=screen_pos)
        
        shadow_dist = 3 * zoom
        shadow_surf = rot_turret.copy()
        shadow_surf.fill((0,0,0,60), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(shadow_surf, (turret_rect.x + shadow_dist, turret_rect.y + shadow_dist))
        
        surface.blit(rot_turret, turret_rect)
        
        self.draw_health_and_marker(surface, offset, zoom)


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
                # 先转炮后打：炮塔平滑转向敌人，对准（±8°）才允许开火
                target_a = math.degrees(math.atan2(-diff.y, diff.x))
                if aim_turret(self, target_a, turn_rate=5, tolerance=8) \
                        and self.attack_cooldown <= 0:
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
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        
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

        # turret_surf 为每帧新建的临时合成 surface，不走缓存
        w, h = turret_surf.get_size()
        scaled_turret = pygame.transform.smoothscale(turret_surf, (int(w * zoom), int(h * zoom)))
        
        
        rot_turret = cached_rotate(scaled_turret, self.angle)
        

        offset_vec = vec(20*zoom, 0).rotate(-self.angle)
        draw_center = (screen_pos[0] + offset_vec.x, screen_pos[1] + offset_vec.y)
        
        turret_rect = rot_turret.get_rect(center=draw_center)
        surface.blit(rot_turret, turret_rect)
        
        self.draw_health_and_marker(surface, offset, zoom, -60)

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

        # turret_surf 为每帧新建的临时合成 surface，不走缓存
        w, h = turret_surf.get_size()
        scaled_turret = pygame.transform.smoothscale(turret_surf, (int(w * zoom), int(h * zoom)))
        
        
        rot_turret = cached_rotate(scaled_turret, self.angle)
        

        offset_vec = vec(20*zoom, 0).rotate(-self.angle)
        draw_center = (screen_pos[0] + offset_vec.x, screen_pos[1] + offset_vec.y)
        
        turret_rect = rot_turret.get_rect(center=draw_center)
        surface.blit(rot_turret, turret_rect)
        
        self.draw_health_and_marker(surface, offset, zoom, -60)

