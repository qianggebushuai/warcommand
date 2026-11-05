import pygame
import random
import math
from core.settings import *
from core.base_classes import *
from .base import *

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
        rotated_image = cached_rotate(scaled_img, self.angle)
        rotated_shadow = cached_rotate(shadow_surf, self.angle)
        
        shadow_offset_vec = scale(5, zoom)
        shadow_rect = rotated_shadow.get_rect(center=(screen_pos[0] + shadow_offset_vec, screen_pos[1] + shadow_offset_vec))
        surface.blit(rotated_shadow, shadow_rect.topleft)
        
        rect = rotated_image.get_rect(center=screen_pos)
        surface.blit(rotated_image, rect.topleft)
        
        self.draw_health_and_marker(surface, offset, zoom)


class APC(Unit):
    # PNG 缓存按阵营分变体（USA 运兵车 / CHINA、RUSSIA 防空车贴图各不相同）
    _variant_attr = 'faction'

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
        
        if self.faction == "RUSSIA":
            C_BODY = (95, 100, 110)     # 俄系灰蓝涂装（区别于中系绿）
            C_TRACK = (35, 35, 40)
            C_DETAIL = (65, 70, 75)
            C_HIGHLIGHT = (115, 120, 130)
        else:
            C_BODY = (100, 110, 90)     # 中系绿涂装
            C_TRACK = (30, 30, 35)
            C_DETAIL = (60, 70, 60)
            C_HIGHLIGHT = (120, 130, 110)
        
        pygame.draw.rect(s, C_TRACK, (5, 2, 70, 10))  
        pygame.draw.rect(s, C_TRACK, (5, 44, 70, 10)) 
        for i in range(0, 70, 8): 
            pygame.draw.line(s, (10,10,10), (5+i, 2), (5+i, 12), 1)
            pygame.draw.line(s, (10,10,10), (5+i, 44), (5+i, 54), 1)

        body_rect = pygame.Rect(5, 10, 70, 36)
        pygame.draw.rect(s, C_BODY, body_rect)
        pygame.draw.rect(s, C_DETAIL, body_rect, 1)
        
        # 队伍色识别条：染色遮罩按此区域提取（否则阵营灰涂装无法按队伍染色）
        col = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        pygame.draw.rect(s, col, (12, 26, 44, 6))
        
        pygame.draw.polygon(s, C_HIGHLIGHT, [(60, 12), (75, 20), (75, 36), (60, 44)])
        
        pygame.draw.rect(s, (40,40,40), (8, 15, 10, 26))
        for i in range(4):
            pygame.draw.line(s, (60,60,60), (8, 18+i*6), (18, 18+i*6), 1)

        return s

    def generate_aa_turret_image(self):
        w, h = 70, 60
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        
        if self.faction == "RUSSIA":
            C_TURRET = (85, 90, 100)   # 俄系灰蓝（区别于中系绿）
            C_BARREL = (35, 35, 40)
        else:
            C_TURRET = (80, 90, 70)    # 中系绿
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
                # 先转炮后打：炮塔平滑转向敌人，对准（±8°）才允许开火
                diff = fire_target.pos - self.pos
                target_a = math.degrees(math.atan2(-diff.y, diff.x))
                if aim_turret(self, target_a, turn_rate=4, tolerance=8) \
                        and self.attack_cooldown <= 0:
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
        rot_body = cached_rotate(scaled_body, self.angle)
        body_rect = rot_body.get_rect(center=screen_pos)
        surface.blit(rot_body, body_rect)
        
        if self.faction in ["CHINA", "RUSSIA"]:
            t_off_x = 0 
        else:
            t_off_x = 15
            
        turret_offset = vec(t_off_x, 0).rotate(-self.angle)
        turret_screen_pos = to_screen(self.pos + turret_offset, offset, zoom)
        
        scaled_turret = scale_img(self.turret_image, zoom)
        rot_turret = cached_rotate(scaled_turret, self.turret_angle) 
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


class Harvester(Unit):
    def __init__(self, game, pos, team, home_building):
        super().__init__(game, pos, team)
        self.home_building = home_building
        self.speed = HARVESTER_STATS[1]
        self.hp = HARVESTER_STATS[2]
        self.max_hp = self.hp
        self.is_mechanical = True
        self.radius = 15
        self.rect = pygame.Rect(pos.x - 15, pos.y - 15, 30, 30)

        self.home_building = home_building
        self.state = "IDLE" 
        self.ore_patch = None      # 当前目标矿脉（OrePatch 实体）
        self.ore_cargo = 0.0       # 矿石货舱（满载 = HARVEST_AMOUNT；改名避开运输单位 cargo 列表）
        self.mine_timer = 0        # IDLE 找矿重试计时
    def _find_ore_patch(self):
        """搜索全图矿脉：优先储量最多者（同量取更近）；
        无富矿(≥20)时接受残矿(≥1)兜底——避免矿区被采到低残量时矿车
        因门槛排除所有矿而停在矿区待命（2026-10-18 用户反馈）"""
        best = None
        fallback = None
        for p in getattr(self.game.current_map, 'ore_patches', []):
            if p.amount >= 20:
                if best is None or p.amount > best.amount or \
                        (p.amount == best.amount and self.pos.distance_to(p.pos) < self.pos.distance_to(best.pos)):
                    best = p
            elif p.amount >= 1:
                if fallback is None or p.amount > fallback.amount or \
                        (p.amount == fallback.amount and self.pos.distance_to(p.pos) < self.pos.distance_to(fallback.pos)):
                    fallback = p
        return best if best is not None else fallback

    def _find_delivery_rig(self):
        """就近选同队存活矿场作交付点：工厂造的矿车不再回工厂卸货，
        统一送最近矿场（矿场=换矿点）；无矿场返回 None"""
        best = None
        best_d = None
        for b in self.game.all_buildings:
            if getattr(b, 'b_type', '') != 'mining' or not getattr(b, 'alive', False):
                continue
            if getattr(b, 'team', None) != self.team:   # getattr：兼容测试桩/无队实体
                continue
            d = self.pos.distance_to(b.pos)
            if best is None or d < best_d:
                best = b
                best_d = d
        return best

    def _update_mining_ai(self):
        # --- 红警式采集：找矿 → 移动 → 采集（真实扣减矿脉）→ 返家卸货 ---
        if self.state == "IDLE":
            self.mine_timer -= 1
            if self.mine_timer > 0:
                return
            self.mine_timer = 60  # 找不到矿每秒重试
            patch = self._find_ore_patch()
            if patch:
                self.ore_patch = patch
                self.state = "MOVING_TO_ORE"

        elif self.state == "MOVING_TO_ORE":
            patch = self.ore_patch
            if patch is None or patch.amount < 0.01:
                self.ore_patch = None
                self.state = "IDLE"
                self.mine_timer = 0
                return
            dist = self.pos.distance_to(patch.pos)
            stop = 1  # 开进矿井中央(距矿心 1px)才开始采矿（用户要求：贴到矿井上采）
            # 容差 1e-6 吸收浮点误差：float64 在 pos≈2000 处 ulp≈4.5e-13，
            # 精确落位/渐近逼近都可能停在 stop+ε（实测 1.000000000000043），
            # 严格 <= 会永久差"最后一丝"触发不了转换（2026-10-19 用户反馈真根因）
            if dist <= stop + 1e-6:
                self.state = "MINING"
            else:
                direction = (patch.pos - self.pos).normalize()
                remain = dist - stop
                if remain <= self.speed:
                    # 一步可达：直接精确落位到距矿心 stop 处。
                    # 渐近逼近在 dist≈stop 时步长(dist-stop)会小于 float64 在 pos≈2000
                    # 处的分辨率 ulp(≈4.5e-13)，加法被浮点吸收 → pos 冻结在 stop+ε
                    # （实测 dist 卡死在 1.000000000000043）→ dist<=stop 永假，
                    # 矿车停在矿井上永远进不了 MINING（2026-10-19 用户反馈真根因）
                    self.pos = patch.pos - direction * stop
                else:
                    self.pos += direction * self.speed
                self.angle = math.degrees(math.atan2(-direction.y, direction.x))

        elif self.state == "MINING":
            patch = self.ore_patch
            if patch is None or patch.amount < 0.01:
                # 矿采空：有货就回家，没货重新找
                self.state = "RETURNING" if self.ore_cargo > 0 else "IDLE"
                self.mine_timer = 0
                return
            space = HARVEST_AMOUNT - self.ore_cargo
            transfer = min(HARVEST_AMOUNT / ORE_PATCH_MINE_FRAMES, patch.amount, space)
            if transfer > 0:
                patch.amount -= transfer
                self.ore_cargo += transfer
            if self.ore_cargo >= HARVEST_AMOUNT - 0.01:
                self.ore_cargo = HARVEST_AMOUNT  # 钳位，消除浮点累积误差
                self.state = "RETURNING"

        elif self.state == "RETURNING":
            rig = self._find_delivery_rig()
            if rig is None:
                # 全图无同队矿场：不执行换矿（用户要求），货舱保留、原地待命；
                # 每帧重扫，矿场一建成立即恢复运送
                return
            target = rig.pos
            dist = self.pos.distance_to(target)
            if dist < 60:
                payout = int(round(self.ore_cargo))
                if payout > 0 and self.team in self.game.team_resources:
                    current = self.game.team_resources[self.team]
                    limit = getattr(self.game, 'max_cmd_exp', 50000)
                    self.game.team_resources[self.team] = min(current + payout, limit)
                    self.game.particles.add(FloatingText(self.pos, f"+{payout}", YELLOW))
                self.ore_cargo = 0.0
                self.ore_patch = None
                self.state = "IDLE"
                self.mine_timer = 0
            else:
                direction = (target - self.pos).normalize()
                self.pos += direction * min(self.speed, dist)
                self.angle = math.degrees(math.atan2(-direction.y, direction.x))

    def update(self):
        if self.target_pos and self.ai_mode == "MOVE":
            if self.state != "MANUAL":
                self.state = "MANUAL"
                self._manual_best = self.pos.distance_to(self.target_pos)
                self._manual_stuck = 0
        elif self.state == "MANUAL" and not self.target_pos:
            # 手动移动到位：复位指令状态并恢复自动采矿
            # （基类到达后不清 target_pos，不复位会永久卡在 MANUAL 在矿井旁发呆）
            self.state = "IDLE"
            self.target_pos = None
            self.ai_mode = "GUARD"
            self.ore_patch = None
            self.target_entity = None
            self.mine_timer = 0  # 立即找矿，不等节流

        # MANUAL 卡死检测：目标不可达（点在水对岸/建筑围死）时基类 A* 失败只能顶墙，
        # 距离永远不改善 → target_pos 永不清除 → 永久 MANUAL 罢工（2026-10-18 用户反馈）。
        # 距离 10 秒无改善且未到达 → 判定不可达，恢复自动采矿
        if self.state == "MANUAL" and self.target_pos:
            d = self.pos.distance_to(self.target_pos)
            if d < getattr(self, '_manual_best', 1e9) - 5:
                self._manual_best = d
                self._manual_stuck = 0
            else:
                self._manual_stuck = getattr(self, '_manual_stuck', 0) + 1
                if self._manual_stuck > 600 and d > 40:
                    self.state = "IDLE"
                    self.target_pos = None
                    self.ai_mode = "GUARD"
                    self.ore_patch = None
                    self.target_entity = None
                    self.mine_timer = 0

        if not self.home_building or not self.home_building.alive:
            found_new = False
            for b in self.game.all_buildings:
                if b.team == self.team and getattr(b, 'b_type', '') == 'mining' and b.alive:
                    self.home_building = b
                    if isinstance(b, MiningRig) and self not in b.harvesters:
                        b.harvesters.append(self)
                    found_new = True
                    break
            if not found_new:
                self.hp = 0
                return

        if not self.game.is_online or self.game.my_role == "HOST":
            if self.state != "MANUAL":
                self._update_mining_ai()

        if self.state == "MANUAL":
            super().update()
        else:
            self.update_rect()
    def is_position_valid(self, pos):
        if not self.game.current_map: return True
        # 延迟导入：maps.map_data 顶层 import units，避免循环
        from maps.map_data import lake_contains, island_contains
        in_water = False
        in_island = False

        if hasattr(self.game.current_map, 'lakes'):
            for lake in self.game.current_map.lakes:
                if lake['type'] == 'water' and lake_contains(lake, pos.x, pos.y):
                    in_water = True
                    break

        if hasattr(self.game.current_map, 'islands'):
            for isle in self.game.current_map.islands:
                if island_contains(isle, pos.x, pos.y):
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

        rot_surf = cached_rotate(s, self.angle)
        rect = rot_surf.get_rect(center=screen_pos)
        surface.blit(rot_surf, rect)
        
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
                img = downscale_texture(pygame.image.load(path).convert_alpha())
                M1A2._sprite_cache[key] = img
            except Exception as e:  
                print(f"Error loading {fname}, trying default...")
                try:
                    default_path = resource_path(os.path.join("sprites/mbt", f"{prefix}.png"))
                    img = downscale_texture(pygame.image.load(default_path).convert_alpha())
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
        
        rot_img = cached_rotate(scaled_img, self.angle) 

        new_rect = rot_img.get_rect(center=screen_pos)
        surface.blit(rot_img, new_rect.topleft)
        
        self.draw_health_and_marker(surface, offset, zoom)
    def perform_attack(self, target):
        if self.attack_cooldown <= 0:
            dmg = DMG_M1A2 * self.tech_bonus_dmg
            shell = Projectile(self.game, self.pos, target, self.team, dmg, "tank_shell", is_aoe=True, aoe_radius=30, breakshellvalue=self.breakarmorvalue, png_key="shell_m1a2")
            shell.target_dest = vec(target.pos)
            self.game.projectiles.append(shell)
            self.attack_cooldown = 120 


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
        
        rot_shadow = cached_rotate(shadow_surf, self.angle - 90)
        shadow_rect = rot_shadow.get_rect(center=(screen_pos[0]+shadow_dist, screen_pos[1]+shadow_dist))
        surface.blit(rot_shadow, shadow_rect)
        
        scaled_hull = scale_img(self.hull_image, zoom)
        rot_hull = cached_rotate(scaled_hull, self.angle - 90) 
        
        hull_rect = rot_hull.get_rect(center=screen_pos)
        surface.blit(rot_hull, hull_rect)
        
        scaled_turret = scale_img(self.turret_image, zoom)
        rot_turret = cached_rotate(scaled_turret, self.turret_angle)
        
        turret_rect = rot_turret.get_rect(center=screen_pos)
        surface.blit(rot_turret, turret_rect)
        
        self.draw_health_and_marker(surface, offset, zoom)
    def update(self):
        super().update()
        
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        if not self.game.is_online or self.game.my_role == "HOST":
            target = self.target_entity or self.find_nearest_enemy()
            
            if target and target.alive:
                # 先转炮后打：炮塔平滑转向敌人，对准（±8°）才允许开火
                diff = target.pos - self.pos
                target_a = math.degrees(math.atan2(-diff.y, diff.x))
                if aim_turret(self, target_a, turn_rate=4, tolerance=8) \
                        and self.pos.distance_to(target.pos) < self.attack_range \
                        and self.attack_cooldown <= 0:
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


class ShockwaveVehicle(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = SHOCKWAVE_STATS[2]
        self.hp = self.max_hp
        self.speed = SHOCKWAVE_STATS[1]
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
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        
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
        rotated_surf = cached_rotate(scaled_surf, self.angle)
        
        rect = rotated_surf.get_rect(center=screen_pos)
        surface.blit(rotated_surf, rect)
        
        if self.shock_cooldown > 0:
            bar_w = 40 * zoom
            bx = screen_pos[0] - bar_w / 2
            by = screen_pos[1] - 35 * zoom
            pygame.draw.rect(surface, (0,0,0), (bx, by, bar_w, 4))
            pygame.draw.rect(surface, C_GLOW_BLUE, (bx, by, bar_w * charge_pct, 4))
            
        self.draw_health_and_marker(surface, offset, zoom)


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
        rotated_surf = cached_rotate(scaled_surf, self.angle)
        
        rect = rotated_surf.get_rect(center=screen_pos)
        surface.blit(rotated_surf, rect)
        
        if self.shock_cooldown > 0:
            bar_w = 40 * zoom
            bx = screen_pos[0] - bar_w / 2
            by = screen_pos[1] - 35 * zoom
            pygame.draw.rect(surface, (0,0,0), (bx, by, bar_w, 4))
            pygame.draw.rect(surface, C_GLOW_BLUE, (bx, by, bar_w * charge_pct, 4))
            
        self.draw_health_and_marker(surface, offset, zoom)


class Type99(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = TYPE99_STATS[2]
        self.hp = self.max_hp
        self.speed = TYPE99_STATS[1]
        self.attack_range = TYPE99_STATS[0]
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
                # 先转炮后打：炮塔平滑转向敌人，对准（±8°）才允许开火
                diff = current_target.pos - self.pos
                target_angle = math.degrees(math.atan2(-diff.y, diff.x))
                aimed = aim_turret(self, target_angle, turn_rate=4, tolerance=8)

                if aimed and self.pos.distance_to(current_target.pos) < self.attack_range:
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
        
        p1 = Projectile(self.game, self.pos + offset_1, target, self.team, dmg_per_shot, "tank_shell", breakshellvalue=self.breakarmorvalue, png_key="shell_type99")
        p2 = Projectile(self.game, self.pos + offset_2, target, self.team, dmg_per_shot,"tank_shell", breakshellvalue=self.breakarmorvalue, png_key="shell_type99")
        
        self.game.projectiles.append(p1)
        self.game.projectiles.append(p2)
        
        self.attack_cooldown = 70

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        
        
        scaled_body = scale_img(self.body_image, zoom)
        rot_body = cached_rotate(scaled_body, self.angle)
        body_rect = rot_body.get_rect(center=screen_pos)
        surface.blit(rot_body, body_rect)
        
        turret_offset = vec(5, 0).rotate(-self.angle) 
        
        turret_pos = self.pos + turret_offset
        turret_screen_pos = to_screen(turret_pos, offset, zoom)
        
        scaled_turret = scale_img(self.turret_image, zoom)
        rot_turret = cached_rotate(scaled_turret, self.turret_angle) 
        turret_rect = rot_turret.get_rect(center=turret_screen_pos)
        surface.blit(rot_turret, turret_rect)
        
        self.draw_health_and_marker(surface, offset, zoom)


        screen_pos = to_screen(self.pos, offset, zoom)
        
        
        scaled_body = scale_img(self.body_image, zoom)
        rot_body = cached_rotate(scaled_body, self.angle)
        body_rect = rot_body.get_rect(center=screen_pos)
        surface.blit(rot_body, body_rect)
        
        turret_offset = vec(5, 0).rotate(-self.angle) 
        
        turret_pos = self.pos + turret_offset
        turret_screen_pos = to_screen(turret_pos, offset, zoom)
        
        scaled_turret = scale_img(self.turret_image, zoom)
        rot_turret = cached_rotate(scaled_turret, self.turret_angle) 
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

        rot_surf = cached_rotate(surf, self.angle)
        rect = rot_surf.get_rect(center=screen_pos)
        surface.blit(rot_surf, rect)
        
        self.draw_health_and_marker(surface, offset, zoom)


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
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        
        scaled_body = scale_img(self.body_image, zoom)
        rot_body = cached_rotate(scaled_body, self.angle)
        rect_body = rot_body.get_rect(center=screen_pos)
        surface.blit(rot_body, rect_body)
        
        if self.loaded_tank:
            scaled_tank = scale_img(self.tank_image, zoom)
            rot_tank = cached_rotate(scaled_tank, self.turret_angle)
            rect_tank = rot_tank.get_rect(center=screen_pos)
            
            surface.blit(rot_tank, rect_tank)
            
        if self.cargo:
            for i in range(len(self.cargo)):
                pygame.draw.circle(surface, (0, 255, 0), (screen_pos[0]-10+i*5, screen_pos[1]), 2)

        self.draw_health_and_marker(surface, offset, zoom)


        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled_body = scale_img(self.body_image, zoom)
        rot_body = cached_rotate(scaled_body, self.angle)
        rect_body = rot_body.get_rect(center=screen_pos)
        surface.blit(rot_body, rect_body)
        
        if self.loaded_tank:
            scaled_tank = scale_img(self.tank_image, zoom)
            rot_tank = cached_rotate(scaled_tank, self.turret_angle)
            rect_tank = rot_tank.get_rect(center=screen_pos)
            
            surface.blit(rot_tank, rect_tank)
            
        if self.cargo:
            for i in range(len(self.cargo)):
                pygame.draw.circle(surface, (0, 255, 0), (screen_pos[0]-10+i*5, screen_pos[1]), 2)

        self.draw_health_and_marker(surface, offset, zoom)


class HIMARS(Unit):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = HIMARS_STATS[2]
        self.hp = self.max_hp
        self.speed = HIMARS_STATS[1]
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
            
            proj = Projectile(self.game, spawn_pos, None, self.team, self.damage,"rocket", is_aoe=True, aoe_radius=40,breakshellvalue=self.breakarmorvalue, png_key="rocket_himars")
            
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
        rotated_chassis = cached_rotate(scaled_chassis, self.angle)
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

        # pod_surf 为每帧新建的临时 surface，不走缓存
        w, h = pod_surf.get_size()
        scaled_pod = pygame.transform.smoothscale(pod_surf, (int(w * zoom), int(h * zoom)))
        rotated_pod = cached_rotate(scaled_pod, self.angle)
        
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
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        
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
        rotated_img = cached_rotate(scaled_img, self.angle)
        
        rect = rotated_img.get_rect(center=screen_pos)
        surface.blit(rotated_img, rect)
        
        self.draw_health_and_marker(surface, offset, zoom)


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
        rotated_img = cached_rotate(scaled_img, self.angle)
        
        rect = rotated_img.get_rect(center=screen_pos)
        surface.blit(rotated_img, rect)
        
        self.draw_health_and_marker(surface, offset, zoom)


class TerminatorIFV(Unit):
    _sprite_cache = {}
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team)
        self.max_hp = TERMINATOR_STATS[2]
        self.hp = self.max_hp
        self.speed = TERMINATOR_STATS[1]
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
                TerminatorIFV._sprite_cache["body_p1"] = downscale_texture(pygame.image.load(resource_path("sprites/bmpt/terminator_body_p1.png")).convert_alpha())
                TerminatorIFV._sprite_cache["body_p2"] = downscale_texture(pygame.image.load(resource_path("sprites/bmpt/terminator_body_p2.png")).convert_alpha())
                TerminatorIFV._sprite_cache["turret"] = downscale_texture(pygame.image.load(resource_path("sprites/bmpt/terminator_turret.png")).convert_alpha())
                TerminatorIFV._sprite_cache["turret_broken"] = downscale_texture(pygame.image.load(resource_path("sprites/bmpt/terminator_turret_broken.png")).convert_alpha())
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
        rot_body = cached_rotate(s_body, self.angle)
        surface.blit(rot_body, rot_body.get_rect(center=screen_pos))
        
        img_turret = self.turret_img if self.phase == 1 else self.turret_img_broken
        angle = self.turret_angle 
        
        recoil_offset = vec(0, 0)
        if self.recoil_timer > 0:
            kick_back = 4 * zoom * (self.recoil_timer / 4) 
            recoil_offset = vec(-kick_back, 0).rotate(-angle)
            
        s_tur = scale_img(img_turret, zoom)
        rot_tur = cached_rotate(s_tur, angle)
        
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
        p = Projectile(self.game, self.pos, None, self.team, self.damage, "rocket", is_aoe=True, aoe_radius=self.blast_range,breakshellvalue=self.breakarmorvalue, png_key="rocket_drone")
        p.on_hit(None) 
        self.die()
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        
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

        rot_surf = cached_rotate(surf, self.angle)
        
        rect = rot_surf.get_rect(center=screen_pos)
        surface.blit(rot_surf, rect)


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

        rot_surf = cached_rotate(surf, self.angle)
        
        rect = rot_surf.get_rect(center=screen_pos)
        surface.blit(rot_surf, rect)


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
        # 特殊单位缓慢回血（坦克式周期回血）：每 SPECIAL_REGEN_INTERVAL 帧恢复 TRAIN_REGEN HP
        self.regen_timer = getattr(self, 'regen_timer', 0) + 1
        if self.regen_timer >= SPECIAL_REGEN_INTERVAL:
            self.regen_timer = 0
            if self.hp < self.max_hp:
                self.hp = min(self.max_hp, int(self.hp) + TRAIN_REGEN)
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
        
        # 有目标点即行驶（含中立）：刷新/开局的中立列车直接驶向目标点模拟进场，
        # 到站清目标点后原地待占领；开火仍限非中立（中立列车不主动攻击）
        if self.target_pos:
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
                    self.game.projectiles.append(Projectile(self.game, self.pos, enemy, self.team, 80,"tank_shell",breakshellvalue=self.breakarmorvalue, png_key="shell_train"))
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
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
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


        rotated_img = cached_rotate(img, angle)
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


        rotated_img = cached_rotate(img, angle)
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
        # 特殊单位缓慢回血（坦克式周期回血）：每 SPECIAL_REGEN_INTERVAL 帧恢复 TRAIN_REGEN HP
        self.regen_timer = getattr(self, 'regen_timer', 0) + 1
        if self.regen_timer >= SPECIAL_REGEN_INTERVAL:
            self.regen_timer = 0
            if self.hp < self.max_hp:
                self.hp = min(self.max_hp, int(self.hp) + TRAIN_REGEN)

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
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        
        scaled_img = scale_img(self.original_image, zoom)
        rotated_img = cached_rotate(scaled_img, self.angle)
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
        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled_img = scale_img(self.original_image, zoom)
        rotated_img = cached_rotate(scaled_img, self.angle)
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
