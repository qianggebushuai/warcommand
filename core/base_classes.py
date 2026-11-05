import pygame
import random
import math
from core.settings import *
from core.utils import resource_path, get_font, cached_scale_img, cached_rotate, logical_size
from core.sfx import SFXManager
import uuid
import time
import os
import sys
vec = pygame.math.Vector2

def to_screen(pos, offset, zoom):
    return (int((pos[0] - offset.x) * zoom), int((pos[1] - offset.y) * zoom))

def scale(value, zoom):
    return max(1, int(value * zoom))

def aim_turret(entity, target_angle, turn_rate=4.0, tolerance=8.0):
    """平滑把炮塔/朝向转向 target_angle（度，atan2(-dy,dx) 约定，与 rotate(-angle) 绘制一致）。
    返回 True 表示已对准（±tolerance 内）——此时才允许开火（先转炮后打）。
    优先转 turret_angle（炮塔独立瞄准的单位），否则转车体 angle。"""
    attr = 'turret_angle' if hasattr(entity, 'turret_angle') else 'angle'
    cur = float(getattr(entity, attr, 0.0))
    diff = (target_angle - cur + 180) % 360 - 180
    if abs(diff) > turn_rate:
        setattr(entity, attr, cur + (turn_rate if diff > 0 else -turn_rate))
    else:
        setattr(entity, attr, target_angle)
    return abs(diff) <= tolerance

class FloatingText(pygame.sprite.Sprite):
    def __init__(self, pos, text, color, duration=60):
        super().__init__()
        self.pos = vec(pos)
        self.text = text
        self.color = color
        self.timer = duration
        self.vel = vec(0, -0.5) 
        self.font = get_font(20,bold=True)

    def update(self):
        self.pos += self.vel
        self.timer -= 1
        if self.timer <= 0: self.kill()

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        surf = self.font.render(self.text, True, self.color)
        outline = self.font.render(self.text, True, BLACK)
        rect = surf.get_rect(center=screen_pos)
        surface.blit(outline, (rect.x+1, rect.y+1))
        surface.blit(surf, rect)
        screen_pos = to_screen(self.pos, offset, zoom)
        surf = self.font.render(self.text, True, self.color)
        outline = self.font.render(self.text, True, BLACK)
        rect = surf.get_rect(center=screen_pos)
        surface.blit(outline, (rect.x+1, rect.y+1))
        surface.blit(surf, rect)
class InterceptEffect(pygame.sprite.Sprite):
    def __init__(self, groups, start_pos, target_pos, color):
        super().__init__(groups)
        self.start_pos = vec(start_pos)
        self.target_pos = vec(target_pos)
        self.color = color
        self.life = 20 # 持续20帧
        self.max_life = 20

    def update(self):
        self.life -= 1
        if self.life <= 0: self.kill()

    def draw(self, surface, offset, zoom):
        s_start = to_screen(self.start_pos, offset, zoom)
        s_end = to_screen(self.target_pos, offset, zoom)
        # 画一条逐渐变细的激光
        width = scale(max(1, int(5 * (self.life / self.max_life))), zoom)
        pygame.draw.line(surface, self.color, s_start, s_end, width)
        # 击中点闪光
        pygame.draw.circle(surface, WHITE, s_end, scale(8 * (self.life/self.max_life), zoom))

class Particle(pygame.sprite.Sprite):
    def __init__(self, groups, pos, color, speed, life, size, decay=True):
        super().__init__(groups)
        self.pos = vec(pos)
        self.vel = vec(random.uniform(-1, 1), random.uniform(-1, 1)).normalize() * speed
        self.color = color
        self.life = life
        self.max_life = life
        self.size = size
        self.decay = decay
    def update(self):
        self.pos += self.vel
        self.life -= 1
        if self.life <= 0: self.kill()
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        if not (-50 <= screen_pos[0] <= SCREEN_WIDTH+50 and -50 <= screen_pos[1] <= SCREEN_HEIGHT+50): return
        if self.decay: current_size = max(0, int(self.size * (self.life / self.max_life)))
        else: current_size = self.size
        scaled_size = scale(current_size, zoom)
        if scaled_size > 0:
            pygame.draw.circle(surface, self.color, screen_pos, scaled_size)


def spawn_ac130_impact_fx(particles, pos, big):
    """AC130 落点爆炸特效（host/客户端共用）：机炮中等爆炸，榴弹（big）大范围爆炸。
    单机在 Projectile.on_hit 调用；联机客户端经 EXPLOSION 事件按 'ar' 还原。"""
    if big:
        # 中心闪光
        Particle(particles, pos, (255, 255, 220), 0, 8, 22)
        # 冲击波环
        for i in range(18):
            Particle(particles, pos, (255, 220, 150), 4, 25, 9)
        # 火球
        for _ in range(30):
            Particle(particles, pos, ORANGE, random.uniform(2, 5), 50, 13)
        # 浓烟
        for _ in range(18):
            Particle(particles, pos, (70, 70, 70), random.uniform(1, 3), 80, 17)
    else:
        for i in range(8):
            Particle(particles, pos, (255, 220, 150), 3, 18, 6)
        for _ in range(12):
            Particle(particles, pos, ORANGE, random.uniform(1.5, 3.5), 35, 8)
        for _ in range(8):
            Particle(particles, pos, (80, 80, 80), random.uniform(1, 2.5), 60, 10)


class Entity(pygame.sprite.Sprite):
    def __init__(self, game, pos, team):
        super().__init__()
        self.game = game
        self.uid = str(uuid.uuid4())[:8]
        self.pos = vec(pos)
        self.team = team
        self.alive = True
        self.hp = 100
        self.max_hp = 100
        self.radius = 15
        self.rect = pygame.Rect(pos.x - self.radius, pos.y - self.radius, self.radius*2, self.radius*2)
        self.is_mechanical = False
        self.is_air = False
        self.can_attack_air = False
        # 护甲从 config/units.json armor 分区按类名查表（配置中心可编辑），未配置默认 0
        self.armor = UNIT_ARMOR.get(type(self).__name__, 0)
        self.breakarmorvalue=0
        self.collision=True
        self.selected = False
        # [修复] 兼容元组
        if not isinstance(pos, pygame.math.Vector2):
            self.pos = vec(pos)
        else:
            self.pos = vec(pos) # 复制一份
    def update_rect(self):
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def take_damage(self, amount,damage_type="normal", breakshellvalue=0):
        if(breakshellvalue>=self.armor):
                self.hp -= amount
        else:
            if( amount-self.armor+breakshellvalue>1):
                self.hp -= amount-self.armor+breakshellvalue
            else:
                self.hp-=1            
        self.last_hit_timer = 60 
        if self.hp <= 0: self.die()

    def die(self):
        self.alive = False
        dt = "normal"
        if getattr(self, 'is_mechanical', False): dt = "mech_death"
        if getattr(self, 'is_air', False): dt = "air_crash"
        if hasattr(self.game, 'net_events'):
            # 发送
            self.game.net_events.append({
                "type": "EXPLOSION", 
                "x": int(self.pos.x), "y": int(self.pos.y), 
                "dt": dt
            })
        SFXManager.instance().play_explosion(dt, pos=self.pos)
        self.create_death_effect()

    def create_death_effect(self):
        count = 15 if self.is_mechanical else 10
        color = ORANGE if self.is_mechanical  else RED
        speed = 3 if self.is_mechanical else 1.5
        size = 5 if self.is_mechanical else 3
        for _ in range(count):
            Particle(self.game.particles, self.pos, color, random.uniform(0.5, speed), random.randint(20, 40), size)
        if self.is_mechanical:
            for _ in range(5): Particle(self.game.particles, self.pos, (50, 50, 50), 1, 60, 6)

    def draw_health_and_marker(self, surface, offset, zoom, y_offset=-25):
        screen_pos = to_screen(self.pos, offset, zoom)
        bar_w = scale(30, zoom)
        bar_h = scale(4, zoom)
        scaled_y_offset = scale(y_offset, zoom)
        
        # 1. 获取选中状态 (安全获取)
        is_selected = getattr(self, 'selected', False)
        
        # 2. 判断是否是己方单位 (用于标记颜色)
        is_mine = False
        if hasattr(self.game, 'my_team') and self.game.my_team:
            if self.team == self.game.my_team:
                is_mine = True
        elif hasattr(self.game, 'my_role'): 
            if self.game.is_online and self.game.my_role == "CLIENT":
                if self.team == "enemy": is_mine = True # 这里逻辑可能有点反常，根据你之前的代码保留
            else:
                if self.team == "player": is_mine = True
        else:
            if self.team == "player": is_mine = True

        # --- 绘制护盾特效 (Shield FX) ---
        # 护盾绘制在单位上方，血条下方
        shield_val = getattr(self, 'shield', 0)
        max_shield_val = getattr(self, 'max_shield', 1) # 防止除零
        
        if shield_val > 0:
            radius = getattr(self, 'radius', 20) * zoom
            
            # 动态参数
            import math
            t = pygame.time.get_ticks()
            
            # 1. 基础呼吸 Alpha
            base_alpha = 140 + 40 * math.sin(t * 0.005)
            
            # 2. 准备特效画布
            s_size = int(radius * 2.4)
            shield_surf = pygame.Surface((s_size, s_size), pygame.SRCALPHA)
            cx, cy = s_size // 2, s_size // 2
            
            # 颜色定义
            C_SHIELD_EDGE = (100, 255, 255) # 亮青
            C_SHIELD_FILL = (0, 100, 200)   # 深蓝
            C_SCANLINE    = (200, 255, 255) # 扫描线
            
            # A. 填充层
            fill_alpha = int(base_alpha * 0.3)
            pygame.draw.circle(shield_surf, (*C_SHIELD_FILL, fill_alpha), (cx, cy), radius)
            
            # B. 边缘发光层
            pygame.draw.circle(shield_surf, (*C_SHIELD_EDGE, int(base_alpha*0.5)), (cx, cy), radius, width=int(4*zoom))
            
            # C. 扫描线特效
            scan_y = cy + math.sin(t * 0.003) * radius
            scan_height = int(5 * zoom)
            dist_y = abs(scan_y - cy)
            if dist_y < radius:
                scan_w = 2 * math.sqrt(radius**2 - dist_y**2)
                scan_rect = pygame.Rect(cx - scan_w/2, scan_y, scan_w, scan_height)
                pygame.draw.rect(shield_surf, (*C_SCANLINE, 150), scan_rect)

            # E. 最终渲染
            dest_rect = shield_surf.get_rect(center=screen_pos)
            surface.blit(shield_surf, dest_rect)

        # --- 绘制血条与护盾条 (UI) ---
        # 显示条件：被选中 OR 受伤 OR 有护盾
        if is_selected or self.hp < self.max_hp or shield_val > 0:
            
            # 血条位置
            hp_bar_y = screen_pos[1] + scaled_y_offset
            
            # 1. 绘制血条
            hp_ratio = max(0, self.hp / self.max_hp)
            pygame.draw.rect(surface, RED, (screen_pos[0] - bar_w//2, hp_bar_y, bar_w, bar_h))
            pygame.draw.rect(surface, (0, 255, 0), (screen_pos[0] - bar_w//2, hp_bar_y, bar_w * hp_ratio, bar_h))
            pygame.draw.rect(surface, BLACK, (screen_pos[0] - bar_w//2, hp_bar_y, bar_w, bar_h), 1)
            
            # 2. 绘制护盾条 (在血条上方)
            if shield_val > 0:
                shield_bar_y = hp_bar_y - bar_h - 2 # 紧贴血条上方
                shield_ratio = max(0, shield_val / max_shield_val)
                
                # 背景 (深青色)
                pygame.draw.rect(surface, (0, 50, 100), (screen_pos[0] - bar_w//2, shield_bar_y, bar_w, bar_h))
                # 当前值 (亮青色)
                pygame.draw.rect(surface, (0, 255, 255), (screen_pos[0] - bar_w//2, shield_bar_y, bar_w * shield_ratio, bar_h))
                # 边框
                pygame.draw.rect(surface, BLACK, (screen_pos[0] - bar_w//2, shield_bar_y, bar_w, bar_h), 1)

        # --- 绘制阵营标记 (倒三角) ---
        if is_mine:
            # 标记位置：在所有条的最上方
            # 如果有护盾，要避开护盾条
            marker_y_base = screen_pos[1] + scaled_y_offset
            if shield_val > 0:
                marker_y_base -= (bar_h + 2)
            
            marker_y = marker_y_base - scale(8, zoom)
            s = scale(5, zoom)
            marker_color = MARKER_BLUE 
            
            points = [
                (screen_pos[0] - s, marker_y), 
                (screen_pos[0] + s, marker_y), 
                (screen_pos[0], marker_y + scale(8, zoom))
            ]
            pygame.draw.polygon(surface, marker_color, points)

    # ---------- PNG 化共享助手：静态外观图（generate_image 产物）缩放缓存 blit ----------
    def _image_anchor(self):
        """self.pos 在 self.image 中的像素锚点，默认图中心；子类可覆写。
        中心必须按逻辑尺寸取：sprite_cache 加载会 downscale_texture 降采样存储
        （显示尺寸回归原始大小），若按 raw 尺寸取中心，图心会偏向右下
        （logical/raw 差值）×zoom 处——大图建筑（如 320px 电磁塔）首当其冲"""
        img = getattr(self, 'image', None)
        if img is None:
            return 0, 0
        lw, lh = logical_size(img)   # 逻辑尺寸（未降采样基准，降采样图已注册）
        return lw // 2, lh // 2

    def _blit_cached_image(self, surface, cx, cy, zoom):
        """把 self.image 按 zoom 缩放缓存后 blit 到 (cx, cy) 锚点处。无图返回 False。
        image 缺失时惰性调 generate_image()，并首次落盘 PNG（已有 PNG 目录则不覆盖，用户手改的图优先）"""
        img = getattr(self, 'image', None)
        if img is None:
            gi = getattr(self, 'generate_image', None)
            if gi is None:
                return False
            try:
                img = self.image = gi()
            except Exception:
                return False
            try:
                import os as _os
                from units.sprite_cache import (extract_parts, save_parts,
                                                resolve_faction, parts_dir)
                team = getattr(self, 'team', 'neutral')
                faction = resolve_faction(getattr(self, 'game', None), team)
                d = parts_dir(self.__class__.__name__, team, faction)
                if not _os.path.isdir(d):
                    save_parts(self.__class__.__name__, team, faction, extract_parts(self))
            except Exception:
                pass
        key = int(round(zoom * 20))
        cache = getattr(self, '_img_scaled_cache', None)
        if cache is None or cache[0] != key:
            lw, lh = logical_size(img)  # 降采样 PNG 显示尺寸不变
            w = max(1, int(lw * zoom))
            h = max(1, int(lh * zoom))
            if (w, h) == img.get_size():
                cache = (key, img)  # 无需缩放：直接用原图，避免恒等重采样
            else:
                cache = (key, pygame.transform.smoothscale(img, (w, h)))
            self._img_scaled_cache = cache
        ox, oy = self._image_anchor()
        surface.blit(cache[1], (int(cx - ox * zoom), int(cy - oy * zoom)))
        return True

class Building(Entity):
    def __init__(self, game, pos, team, b_type):
        super().__init__(game, pos, team)
        self.b_type = b_type
        self.is_mechanical = True
        self.production_queue = [] 
        self.current_production = None 
        self.power_usage = POWER_COST
        self.target_entity = None
    def set_target(self, entity):
        # 只有防御塔才需要这个功能
        # 但为了通用性，基类实现也没坏处
        if entity and entity.alive:
            self.target_entity = entity
    def update(self):
        # [新增] 通用生产更新逻辑
        # 如果子类有特殊的 update，记得调用 super().update()
        
        if self.current_production:
            self.current_production['timer'] -= 1
            if self.current_production['timer'] <= 0:
                # 生产完成
                u_type = self.current_production['type']
                
                # 确定生成位置 (默认下方 50px)
                # 子类可以重写 spawn_unit_logic 来改变位置
                spawn_pos = self.pos + vec(0, 50)
                
                self.game.spawn_unit(u_type, spawn_pos, self.team)
                self.current_production = None
        desired_move = vec(0, 0)

        # === 通用: 应用朝向 ===
        final_pos = self.pos + desired_move
        can_move = True
        separation_force = vec(0, 0)
        neighbors = 0
        
        # 只检测附近的单位 (半径 30)
        # 为了性能，可以只检测同阵营的，或者所有阵营

        for u in self.game.all_units:
            if u != self and u.alive:
                
                # [核心修复] 层级检查
                # 如果我是空军，对方必须也是空军才碰撞
                # 如果我是陆军，对方必须也是陆军才碰撞
                # 简单说：层级必须相同 (is_air 属性一致)
                if self.is_air != u.is_air:
                    continue 
                
                # [额外] 排除海军与陆军的碰撞 (如果需要的话)
                # 比如船在水里，坦克在岸上，边缘重叠时不应该互推
                is_self_naval = getattr(self, 'is_naval', False)
                is_u_naval = getattr(u, 'is_naval', False)
                if is_self_naval != is_u_naval:
                    continue

                dist = self.pos.distance_to(u.pos)
                min_dist = self.radius + u.radius 
                
                if not self.is_air:# 如果重叠了
                    if dist < min_dist:
                            # 计算推力方向
                        if dist == 0: diff = vec(random.uniform(-1,1), random.uniform(-1,1))
                        else: diff = (self.pos - u.pos).normalize()
                        
                        # 力的大小与重叠深度成正比
                        push_strength = (min_dist - dist) * 0.1 
                        separation_force += diff * push_strength
                        neighbors += 1
            
        # 应用分离力
        if neighbors > 0:
            # 限制最大推力，防止弹飞
            if separation_force.length() > 2: separation_force.scale_to_length(2)
            
            # 将分离力叠加到最终位置
            final_pos += separation_force          
        # 自动从队列取下一个任务
        if not self.current_production and self.production_queue:
            next_task = self.production_queue.pop(0)
            self.current_production = {
                'type': next_task[0],
                'timer': next_task[1],
                'total_time': next_task[1]
            }
    def die(self):
        return super().die()
    # [新增] 通用加入队列方法
    def queue_unit(self, u_type, build_time):
        if len(self.production_queue) < 5:
            self.production_queue.append((u_type, build_time))
            return True
        return False
    def take_damage(self, amount, damage_type="normal", breakshellvalue=0):
        # 1. 计算有效护甲 (不能小于0)
        effective_armor = max(0, self.armor - breakshellvalue)
        
        # 2. 计算最终伤害
        if effective_armor == 0:
            # 破甲值 >= 护甲，完全穿透，全额伤害
            final_damage = amount
        else:
            # 护甲抵消伤害
            final_damage = amount - effective_armor
            
        # 3. 保底伤害 (至少扣1血)
        final_damage = max(1, final_damage)
        
        # 4. 扣血
        self.hp -= final_damage
        
        self.last_hit_timer = 60 
        if self.hp <= 0: self.die()

class OilDerrick(Entity):
    def __init__(self, game, pos):
        super().__init__(game, pos, "neutral") # 初始中立
        self.b_type = "oil_derrick"
        self.hp = 1000
        self.max_hp = 1000
        self.radius = 40
        self.rect = pygame.Rect(pos.x - 40, pos.y - 40, 80, 80)
        self.is_mechanical = True
        
        # 占领逻辑
        self.capture_progress = 0
        self.capturing_team = None
        self.max_capture = OIL_CAPTURE_TIME
        
        # 动画属性
        self.pump_y = 0
        self.pump_dir = 1

    def update(self):
        # 1. 资源产出 (Host 负责加钱)
        if not self.game.is_online or self.game.my_role == "HOST":
            
            # [修改] 使用 team_resources 字典
            # 只要当前归属的 team 在资源字典里 (排除 "neutral")
            if self.team in self.game.team_resources:
                self.game.team_resources[self.team] = min(
                    self.game.team_resources[self.team] + OIL_DERRICK_INCOME, 
                    self.game.max_cmd_exp
                )
        # 2. 占领逻辑 (权限控制：仅 Host 或 单机)
        if not self.game.is_online or self.game.my_role == "HOST":
            capturer = None
            min_dist = 60
            for u in self.game.all_units:
                if u.alive and not u.is_air:
                    dist = self.pos.distance_to(u.pos)
                    if dist < min_dist:
                        capturer = u
                        min_dist = dist   # 取最近的在圈单位（break 首个会被列表顺序坑：守点敌军挡住玩家的占领）
            
            if capturer:
                if capturer.team != self.team:
                    if self.capturing_team != capturer.team:
                        self.capturing_team = capturer.team
                        self.capture_progress = 0 
                    
                    self.capture_progress += 1
                    
                    if self.capture_progress >= self.max_capture:
                        self.team = capturer.team
                        self.capture_progress = 0
                        self.game.particles.add(FloatingText(self.pos, "CAPTURED!", TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])))
                        if hasattr(capturer, 'ai_mode') and capturer.ai_mode == "CAPTURE":
                            capturer.ai_mode = "GUARD"
                            capturer.target_pos = None
                else:
                    self.capture_progress = 0
            else:
                self.capture_progress = max(0, self.capture_progress - 0.5)


    def _draw_static(self, surface, cx, cy, zoom):
        """静态外观：阴影 / 地基 / 油渍 / A型支架（generate_image 与无图回退共用）"""
        base_w = scale(50, zoom)
        base_l = scale(80, zoom)
        base_h = scale(10, zoom)
        tower_h = scale(45, zoom)
        C_CONCRETE = (120, 120, 125)
        C_STEEL_DARK = (60, 60, 65)
        # 阴影
        shadow_offset = scale(10, zoom)
        s_surf = pygame.Surface((scale(150, zoom), scale(150, zoom)), pygame.SRCALPHA)
        pygame.draw.ellipse(s_surf, (0, 0, 0, 80), (0, 0, base_l, base_w))
        surface.blit(s_surf, (cx - base_l // 2 + shadow_offset, cy - base_w // 4 + shadow_offset))
        # 地基侧面 + 顶面
        pygame.draw.rect(surface, (80, 80, 85), pygame.Rect(cx - base_l // 2, cy, base_l, base_h))
        rect_top = pygame.Rect(cx - base_l // 2, cy - base_w // 2, base_l, base_w)
        pygame.draw.rect(surface, C_CONCRETE, rect_top)
        pygame.draw.rect(surface, (60, 60, 60), rect_top, 2)
        # 油渍
        pygame.draw.ellipse(surface, (40, 40, 30),
                            (cx + scale(20, zoom), cy - scale(10, zoom), scale(15, zoom), scale(8, zoom)))
        # A 型支架
        pivot = (cx, cy - tower_h)
        foot_l = (cx - scale(10, zoom), cy - scale(10, zoom))
        foot_r = (cx + scale(10, zoom), cy - scale(10, zoom))
        pygame.draw.line(surface, C_STEEL_DARK, foot_l, pivot, int(scale(4, zoom)))
        pygame.draw.line(surface, C_STEEL_DARK, foot_r, pivot, int(scale(4, zoom)))
        mid_y = (pivot[1] + cy) / 2
        pygame.draw.line(surface, C_STEEL_DARK,
                         (foot_l[0] * 0.5 + pivot[0] * 0.5, mid_y),
                         (foot_r[0] * 0.5 + pivot[0] * 0.5, mid_y), 2)

    def generate_image(self):
        """静态外观基准图（zoom=1），锚点 (52, 48) = self.pos；PNG 缓存由 sprite_cache 自动导出/加载"""
        surf = pygame.Surface((104, 100), pygame.SRCALPHA)
        self._draw_static(surf, 52, 48, 1.0)
        return surf

    def _image_anchor(self):
        return 52, 48

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        cx, cy = int(screen_pos[0]), int(screen_pos[1])

        # --- 静态外观（PNG 命中时为图片 blit，未命中现场绘制） ---
        if not self._blit_cached_image(surface, cx, cy, zoom):
            self._draw_static(surface, cx, cy, zoom)

        # --- 动态部分：游梁抽油机动画（驴头随队伍变色，保留程序绘制） ---
        base_top_y = cy
        tower_h = scale(45, zoom)
        beam_len_front = scale(35, zoom)
        beam_len_back = scale(25, zoom)
        C_STEEL_DARK = (60, 60, 65)
        C_STEEL_LIGHT = (140, 140, 150)
        C_RUST = (100, 70, 60)
        team_color = TEAM_COLORS.get(self.team, TEAM_COLORS.get("neutral", (100, 100, 100)))
        pivot_x, pivot_y = cx, base_top_y - tower_h

        t = time.time() * 3
        swing_angle = math.sin(t) * 0.25
        head_x = pivot_x + math.cos(swing_angle) * beam_len_front
        head_y = pivot_y + math.sin(swing_angle) * beam_len_front
        tail_x = pivot_x - math.cos(swing_angle) * beam_len_back
        tail_y = pivot_y - math.sin(swing_angle) * beam_len_back

        # 抽油杆
        pygame.draw.line(surface, (30, 30, 30), (head_x, head_y + scale(5, zoom)), (head_x, base_top_y), 2)
        # 驴头（队伍色涂装）
        head_size = scale(12, zoom)
        pygame.draw.circle(surface, team_color, (int(head_x), int(head_y)), int(head_size))
        pygame.draw.circle(surface, (50, 50, 50), (int(head_x), int(head_y)), int(head_size), 2)
        # 游梁本体
        pygame.draw.line(surface, C_STEEL_LIGHT, (tail_x, tail_y), (head_x, head_y), int(scale(8, zoom)))
        pygame.draw.line(surface, C_RUST, (tail_x, tail_y - 2), (head_x, head_y - 2), 2)
        # 尾部配重
        pygame.draw.rect(surface, C_STEEL_DARK, (tail_x - scale(5, zoom), tail_y - scale(5, zoom),
                                                 scale(10, zoom), scale(10, zoom)))
        # 曲柄连杆
        crank_center = (pivot_x - scale(20, zoom), base_top_y - scale(15, zoom))
        crank_angle = t + math.pi / 2
        crank_pos = (crank_center[0] + math.cos(crank_angle) * scale(10, zoom),
                     crank_center[1] + math.sin(crank_angle) * scale(10, zoom))
        pygame.draw.line(surface, (80, 80, 80), (tail_x, tail_y), crank_pos, 2)
        pygame.draw.circle(surface, (50, 50, 50), (int(crank_center[0]), int(crank_center[1])), int(scale(8, zoom)))
        pygame.draw.circle(surface, (200, 200, 200), (int(crank_pos[0]), int(crank_pos[1])), 3)
        # 中央转轴
        pygame.draw.circle(surface, C_STEEL_DARK, (int(pivot_x), int(pivot_y)), int(scale(5, zoom)))

        # --- 占领进度条 ---
        if self.capture_progress > 0:
            bar_w = scale(50, zoom)
            bar_h = scale(6, zoom)
            pct = min(1.0, max(0.0, self.capture_progress / self.max_capture))
            bar_c = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
            bar_x = cx - bar_w // 2
            bar_y = base_top_y - tower_h - scale(25, zoom)
            s_bar = pygame.Surface((bar_w + 4, bar_h + 4))
            s_bar.fill((0, 0, 0))
            surface.blit(s_bar, (bar_x - 2, bar_y - 2))
            pygame.draw.rect(surface, (80, 80, 80), (bar_x, bar_y, bar_w, bar_h))
            if pct > 0:
                pygame.draw.rect(surface, bar_c, (bar_x, bar_y, bar_w * pct, bar_h))
            pygame.draw.rect(surface, (200, 200, 200), (bar_x - 1, bar_y - 1, bar_w + 2, bar_h + 2), 1)
        self.draw_health_and_marker(surface, offset, zoom)
class MercenaryFactory(Entity):
    def __init__(self, game, pos):
        super().__init__(game, pos, "neutral")
        self.hp = 1500
        self.max_hp = 1500
        self.radius = 60
        self.rect = pygame.Rect(pos.x - 60, pos.y - 60, 120, 120)
        self.is_mechanical = True
        self.spawn_timer = 0
        
        # 占领逻辑
        self.capture_progress = 0
        self.capturing_team = None
        self.max_capture = OIL_CAPTURE_TIME

    def update(self):
        # 生产逻辑
        if self.team != "neutral":
            self.spawn_timer += 1
            if self.spawn_timer > MERC_FACTORY_INTERVAL:
                self.spawn_timer = 0
                # 生成装甲车
                # 避免循环引用，需要 import ArmoredCar (在 units.py 中已存在)
                # 由于这是 base_classes.py，无法直接创建 Unit，所以逻辑要移到 main.py 或者 units.py
                # 解决方案：将 MercenaryFactory 定义在 units.py 中
                pass 

        if not self.game.is_online or self.game.my_role == "HOST":        # 占领逻辑 (同油井)
            capturer = None
            min_dist = 100
            for u in self.game.all_units:
                if u.alive and not u.is_air:
                    dist = self.pos.distance_to(u.pos)
                    if dist < min_dist:
                        capturer = u
                        min_dist = dist   # 最近者占领（同油井：防列表顺序坑）
            
            if capturer:
                if capturer.team != self.team:
                    if self.capturing_team != capturer.team:
                        self.capturing_team = capturer.team
                        self.capture_progress = 0 
                    self.capture_progress += 1
                    if self.capture_progress >= self.max_capture:
                        self.team = capturer.team
                        self.game.particles.add(FloatingText(self.pos, "FACTORY CAPTURED!",TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"]) ))
                else:
                    self.capture_progress = 0
        else:
            self.capture_progress = max(0, self.capture_progress - 0.5)

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        w = scale(80, zoom)
        h = scale(60, zoom)
        
        default_color = TEAM_COLORS.get("neutral", (100, 100, 100))
        team_color = default_color       
        team_color = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        
        # 工厂主体
        pygame.draw.rect(surface, (80, 80, 80), (screen_pos[0]-w//2, screen_pos[1]-h//2, w, h))
        pygame.draw.rect(surface, BLACK, (screen_pos[0]-w//2, screen_pos[1]-h//2, w, h), 2)
        
        # 旗帜
        pygame.draw.rect(surface, team_color, (screen_pos[0]-w//4, screen_pos[1]-h//2-scale(10, zoom), w//2, scale(10, zoom)))
        
        # 齿轮装饰 (静态)
        pygame.draw.circle(surface, (50, 50, 50), screen_pos, scale(20, zoom), 4)

        if self.capture_progress > 0:
            bar_w = scale(40, zoom)
            bar_h = scale(5, zoom)
            pct = self.capture_progress / self.max_capture
            
            bar_color=TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
            
            pygame.draw.rect(surface, WHITE, (screen_pos[0]-bar_w//2, screen_pos[1]-h-scale(15, zoom), bar_w, bar_h))
            pygame.draw.rect(surface, bar_color, (screen_pos[0]-bar_w//2, screen_pos[1]-h-scale(15, zoom), bar_w*pct, bar_h))
        screen_pos = to_screen(self.pos, offset, zoom)
        w = scale(80, zoom)
        h = scale(60, zoom)
        
        default_color = TEAM_COLORS.get("neutral", (100, 100, 100))
        team_color = default_color       
        team_color = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        
        # 工厂主体
        pygame.draw.rect(surface, (80, 80, 80), (screen_pos[0]-w//2, screen_pos[1]-h//2, w, h))
        pygame.draw.rect(surface, BLACK, (screen_pos[0]-w//2, screen_pos[1]-h//2, w, h), 2)
        
        # 旗帜
        pygame.draw.rect(surface, team_color, (screen_pos[0]-w//4, screen_pos[1]-h//2-scale(10, zoom), w//2, scale(10, zoom)))
        
        # 齿轮装饰 (静态)
        pygame.draw.circle(surface, (50, 50, 50), screen_pos, scale(20, zoom), 4)

        if self.capture_progress > 0:
            bar_w = scale(40, zoom)
            bar_h = scale(5, zoom)
            pct = self.capture_progress / self.max_capture
            
            bar_color=TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
            
            pygame.draw.rect(surface, WHITE, (screen_pos[0]-bar_w//2, screen_pos[1]-h-scale(15, zoom), bar_w, bar_h))
            pygame.draw.rect(surface, bar_color, (screen_pos[0]-bar_w//2, screen_pos[1]-h-scale(15, zoom), bar_w*pct, bar_h))
_PROJ_IMG_CACHE = {}   # png_key -> surface / None（False=未探测）
_PROJ_DIR = 'sprites/projectiles'

def _get_proj_img(key):
    """加载弹射物立绘（模块级缓存）。缺失返回 None（draw 回退程序绘制圆球）。"""
    img = _PROJ_IMG_CACHE.get(key, False)
    if img is False:
        try:
            img = pygame.image.load(resource_path(_PROJ_DIR + '/' + key + '.png')).convert_alpha()
        except Exception:
            img = None
        _PROJ_IMG_CACHE[key] = img
    return img


class Projectile(pygame.sprite.Sprite):
    def __init__(self, game, pos, target, team, damage, d_type, is_aoe=False, aoe_radius=0, breakshellvalue=0, png_key=None):
        super().__init__()
        self.game = game
        self.pos = vec(pos)
        self.target = target  # [修改1] 保存目标引用
        self.team = team
        self.damage = damage
        self.breakshellvalue=breakshellvalue
        self.d_type = d_type
        # 立绘键：默认与 d_type 同名，发射单位可传 png_key 区分专属弹药
        self.png_key = png_key or d_type
        self.alive = True
        self.is_aoe = is_aoe
        self.aoe_radius = aoe_radius
        self.target_dest = None
        self.target_dest = None # 初始        
        self.speed = ROCKET_SPEED if d_type == "rocket" else BULLET_SPEED
        if d_type in ("ac130_vis", "ac130_howitzer_vis"): self.speed = 18 
        if d_type == "tank_shell": self.speed = 10 
        elif d_type == "heavy_shell": self.speed = 8 # 舰炮较慢
        self.vel = vec(0, 0)        
        if d_type == "laser" or d_type == "laser2":
            self.life_time = 5 
            self.target_dest = target.pos if target else pos 
        if self.d_type == "flame":
            self.life_time=30
            self.max_life = 30 
        else:
            self.life_time = 120
            
            # 计算初速度
            if target and hasattr(target, 'pos'):
                diff = target.pos - pos
                if diff.length_squared() > 0:
                    self.vel = diff.normalize() * self.speed
                else:
                    # 防止重叠导致的除零错误
                    self.vel = vec(1, 0).rotate(random.randint(0, 360)) * self.speed
            else:
                # 无目标时 (如 AC130 盲射)
                self.vel = vec(0, 0) # 保持默认或者赋予指定方向
        SFXManager.instance().play_weapon(d_type, team, getattr(self.game, 'my_team', None), pos=self.pos)

    def update(self):
        # 1. 激光逻辑 (不变)
        if self.d_type == "laser":
            self.life_time -= 1
            if self.life_time <= 0: self.alive = False
            return 
        if self.target_dest:
            dist = self.pos.distance_to(self.target_dest)
            # 如果距离小于速度，说明下一帧就会穿过地面 -> 爆炸
            if dist <= self.speed:
                self.pos = self.target_dest # 修正位置到地面
                self.on_hit(None) # 触发爆炸，没有直接命中的实体(靠AOE伤害)
                return
        if self.d_type == "flame":
            pass 
        if self.d_type == "fire_zone":
            self.life_time -= 1
            if self.life_time <= 0: self.alive = False
            
            if (not self.game.is_online or self.game.my_role == "HOST") and self.life_time % 10 == 0:
                targets = self.game.all_units + self.game.all_buildings
                for t in targets:
                    if t.team != self.team and t.alive:
                        if self.pos.distance_to(t.pos) < self.aoe_radius + t.radius:
                            t.take_damage(self.damage, "fire")
            
            return 
        if self.target and self.target.alive and self.d_type != "ac130_vis":
            direction = (self.target.pos - self.pos)
            if direction.length() > 0:
                self.vel = direction.normalize() * self.speed
            
            # 距离判定 (比 collidepoint 更稳定)
            # 如果距离小于速度，说明下一帧就会穿过去，直接判定命中
            dist = self.pos.distance_to(self.target.pos)
            hit_threshold = self.speed + getattr(self.target, 'radius', 20) 
            
            if dist <= hit_threshold:
                self.on_hit(self.target)
                return

        # 3. 移动
        self.pos += self.vel
        self.life_time -= 1

        # 4. AC130 视觉特效或其他无目标子弹的销毁逻辑
        if self.d_type in ("ac130_vis", "ac130_howitzer_vis"):
            # 榴弹拖尾：飞行途中持续冒烟（低速大弹，烟迹明显）
            if self.d_type == "ac130_howitzer_vis" and self.game.frame_count % 2 == 0:
                p = Particle(self.game.particles, self.pos, (120, 112, 100),
                             random.uniform(0.2, 0.6), 25, 4)
                p.vel = -(self.vel.normalize() * random.uniform(0.3, 0.8)) if self.vel.length_squared() > 0 else p.vel
                if self.game.frame_count % 6 == 0:
                    Particle(self.game.particles, self.pos, (255, 180, 90), 0.5, 10, 3)
            if self.target_dest and self.pos.distance_to(self.target_dest) <= self.speed:
                self.alive = False 
            elif self.life_time <= 0:
                self.alive = False
            return 

        if self.life_time <= 0:
            self.alive = False
            return
        if not (self.target and self.target.alive):
            hit_list = self.game.all_units + self.game.all_buildings
            for entity in hit_list:
                if entity.team != self.team and entity.alive :
                    # 距离判定优于 collidepoint
                    if self.pos.distance_to(entity.pos) < getattr(entity, 'radius', 30):
                        self.on_hit(entity)
                        return

    def on_hit(self, direct_hit_entity):

        
        # 发送网络爆炸事件
        # [修改] 仅 Host 或 单机 负责生成特效事件
        if not self.game.is_online or self.game.my_role == "HOST":
            if self.d_type != "laser" and hasattr(self.game, 'net_events'):
                self.game.net_events.append({
                    "type": "EXPLOSION", 
                    "x": int(self.pos.x), 
                    "y": int(self.pos.y),
                    "dt": self.d_type, # 传入伤害类型以便客户端区分特效
                    "ar": int(self.aoe_radius) # AOE 半径：AC130 机炮/榴弹区分爆炸规模
                })
        
        if self.is_aoe:
            if self.d_type == "flame":
                
                # 特效
                for _ in range(2): 
                    p = Particle(self.game.particles, self.pos, (255, 100, 0), 1, 15, 4)
                    
                if not hasattr(self, 'hit_list'): self.hit_list = []
                
                if direct_hit_entity and direct_hit_entity not in self.hit_list:
                    direct_hit_entity.take_damage(self.damage, "fire",self.breakshellvalue)
                    self.hit_list.append(direct_hit_entity)
                    
                return
            if self.d_type == "behemoth_bomb":
                for i in range(36):
                    angle = i * 10
                    speed = 6
                    vel = vec(speed, 0).rotate(angle)
                    Particle(self.game.particles, self.pos, WHITE, speed, 40, 10)
                for _ in range(40): Particle(self.game.particles, self.pos, ORANGE, random.uniform(1, 4), 60, 15)
                for _ in range(20): Particle(self.game.particles, self.pos, (50, 50, 50), random.uniform(2, 5), 80, 20)
            elif self.d_type=="rocket":
                for _ in range(15): Particle(self.game.particles, self.pos, ORANGE, random.uniform(2, 5), 30, 6)
                for _ in range(10): Particle(self.game.particles, self.pos, (50, 50, 50), random.uniform(1, 3), 40, 8)  
            elif self.d_type == "heavy_shell":
                # 冲击波环
                for i in range(12):
                    Particle(self.game.particles, self.pos, (200, 200, 255), 4, 30, 8) # 蓝白冲击波
                # 火球
                for _ in range(20): 
                    Particle(self.game.particles, self.pos, ORANGE, random.uniform(2, 5), 50, 12)
                # 烟雾
                for _ in range(15): 
                    Particle(self.game.particles, self.pos, (80, 80, 80), random.uniform(1, 3), 80, 15)
                # 如果需要强制设置 AOE 半径 (防止传入 0)
                if self.aoe_radius == 0: self.aoe_radius = 100

            elif self.d_type == "incendiary":
                if not self.game.is_online or self.game.my_role == "HOST":
                    fire = Projectile(self.game, self.pos, None, self.team, DMG_FIRE_ZONE, "fire_zone", is_aoe=True, aoe_radius=60,breakshellvalue=10000)
                    fire.life_time = 180 # 3秒
                    fire.vel = vec(0,0)
                    self.game.projectiles.append(fire)
            elif self.d_type != "ac130":
                for _ in range(8): Particle(self.game.particles, self.pos, ORANGE, 2, 20, 4)
            else:
                # AC130 机炮/榴弹落点：按 AOE 半径区分爆炸规模（榴弹 aoe=110 > 机炮 40）
                spawn_ac130_impact_fx(self.game.particles, self.pos, self.aoe_radius >= 80)
            
            targets = self.game.all_units + self.game.all_buildings
            for t in targets:
                if t.team != self.team and t.alive:
                    # [修复] 加上目标自身的半径，解决炸不到大建筑的问题
                    target_radius = getattr(t, 'radius', 10) 
                    if self.pos.distance_to(t.pos) <= self.aoe_radius + target_radius: 
                        if hasattr(t, 'take_damage'):
                            t.take_damage(self.damage, self.d_type,self.breakshellvalue)
        else:
            if direct_hit_entity and hasattr(direct_hit_entity, 'take_damage'): 
                direct_hit_entity.take_damage(self.damage, self.d_type,self.breakshellvalue)
            
            for _ in range(3): Particle(self.game.particles, self.pos, WHITE, 1, 15, 2)
        self.alive = False
    def _blit_proj_png(self, surface, zoom, screen_pos):
        """按速度方向旋转绘制立绘 PNG（弹头朝右为 0°）。成功返回 True，无图回退 False。
        PNG 为 2 倍世界尺寸，按 zoom*0.5 还原显示大小。"""
        img = _get_proj_img(self.png_key)
        if img is None:
            return False
        ang = 0.0
        if self.vel.length_squared() > 0:
            ang = math.degrees(math.atan2(-self.vel.y, self.vel.x))
        scaled = cached_scale_img(img, zoom * 0.5, smooth=True)
        if abs(ang) > 0.5:
            scaled = cached_rotate(scaled, ang, quantum=2)
        rect = scaled.get_rect(center=screen_pos)
        surface.blit(scaled, rect)
        return True

    def _draw_trail_fx(self, surface, zoom, screen_pos):
        """榴弹拖尾（纯绘制层，host/客户端均生效）：渐隐烟团 + 高热曳光线。
        客户端子弹 vel 恒为零，方向回退用 target_dest 推算。"""
        d = self.vel if self.vel.length_squared() > 1e-6 else (
            (self.target_dest - self.pos) if self.target_dest else vec(0, 0))
        if d.length_squared() <= 0:
            return
        dn = d.normalize()
        # 曳光线
        pygame.draw.line(surface, (255, 190, 110),
                         screen_pos - dn * scale(2, zoom),
                         screen_pos - dn * scale(10, zoom),
                         max(1, int(scale(2, zoom))))
        # 渐隐烟团（离弹体越远越大越淡）
        for i in range(1, 5):
            r = int(scale(3 + i * 2, zoom))
            if r <= 0:
                continue
            alpha = max(20, 130 - i * 28)
            p = screen_pos - dn * scale(8 + i * 7, zoom)
            s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (120, 112, 100, alpha), (r, r), r)
            surface.blit(s, (p.x - r, p.y - r))

    # draw 方法保持不变
    def draw(self, surface, offset, zoom):
        # ... (保持原样) ...
        if self.d_type == "ac130": return 
        screen_pos = to_screen(self.pos, offset, zoom)
        if not (-20 <= screen_pos[0] <= SCREEN_WIDTH+20 and -20 <= screen_pos[1] <= SCREEN_HEIGHT+20): return
        # 榴弹拖尾：在弹体 PNG 之下绘制烟团/曳光
        if self.d_type == "ac130_howitzer_vis":
            self._draw_trail_fx(surface, zoom, screen_pos)
        if self.d_type == "incendiary":
            # 核心
            pygame.draw.circle(surface, (255, 200, 50), screen_pos, scale(5, zoom))
            # 外焰
            pygame.draw.circle(surface, (255, 50, 0), screen_pos, scale(8, zoom), 2)
            # 拖尾
            if self.vel.length() > 0:
                tail_end = self.pos - self.vel.normalize() * 20
                tail_screen = to_screen(tail_end, offset, zoom)
                pygame.draw.line(surface, (200, 100, 0), screen_pos, tail_screen, scale(3, zoom))
            return        
        if self.d_type == "laser":
            if self.target_dest:
                end_screen = to_screen(self.target_dest, offset, zoom)
                width = scale(random.randint(2, 4), zoom)
                pygame.draw.line(surface, CYAN, screen_pos, end_screen, width)
                pygame.draw.circle(surface, WHITE, end_screen, scale(5, zoom))
            return
        if self.d_type == "laser2":
            level =int(self.breakshellvalue/1000)
            print(level)
            # 颜色：从蓝 -> 紫 -> 红
            colors = [(0, 200, 255), (100, 100, 255), (200, 0, 255), (255, 50, 50)]
            color = colors[min(level, 3)]
            
            # 粗细：越来越粗
            width = scale(2 + level *4 , zoom)
            
            end_pos = self.target.pos if self.target else self.target_dest
            start_scr = to_screen(self.pos, offset, zoom)
            end_scr = to_screen(end_pos, offset, zoom)
            
            # 核心光束
            pygame.draw.line(surface, color, start_scr, end_scr, width)
            # 白芯
            pygame.draw.line(surface, (255, 255, 255), start_scr, end_scr, max(1, width//2))
            
            
            return
        if self.d_type == "fire_zone":
            # 画一个半透明红圈
            s_rad = scale(self.aoe_radius, zoom)
            s = pygame.Surface((s_rad*2, s_rad*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 50, 0, 50), (s_rad, s_rad), s_rad)
            surface.blit(s, (screen_pos[0]-s_rad, screen_pos[1]-s_rad))
            
            # 随机冒火星
            if random.randint(0, 5) == 0:
                Particle(self.game.particles, self.pos + vec(random.randint(-30,30), random.randint(-30,30)), (255, 200, 0), 1, 30, 5)
            return
        if self.d_type == "flame":
            screen_pos = to_screen(self.pos, offset, zoom)
            
            current_life = getattr(self, 'life_time', 30)
            total_life = getattr(self, 'max_life', 30)
            
            life_pct = 1.0 - (current_life / total_life)
            
            current_radius = scale(4 + 11 * life_pct, zoom)
            
            # 3. 动态颜色 (黄 -> 橙 -> 红 -> 烟灰)
            if life_pct < 0.3:
                color = (255, 255, 100, 200) # 亮黄
            elif life_pct < 0.6:
                color = (255, 150, 0, 180)   # 橙
            elif life_pct < 0.8:
                color = (200, 50, 0, 150)    # 红
            else:
                color = (100, 100, 100, 100) # 灰烟
            

            if self.vel.length() > 0:
                vel_norm = self.vel.normalize()
                # 绘制 3-5 个重叠的圆，沿反方向排列
                num_segments = 4
                for i in range(num_segments):
                    # 越往后越小，越透明
                    seg_r = int(current_radius * (1 - i*0.15))
                    seg_pos = screen_pos - vel_norm * scale(i * 5, zoom)
                    
                    s = pygame.Surface((seg_r*2, seg_r*2), pygame.SRCALPHA)
                    pygame.draw.circle(s, color, (seg_r, seg_r), seg_r)
                    surface.blit(s, (seg_pos.x - seg_r, seg_pos.y - seg_r), special_flags=pygame.BLEND_ADD)
            else:
                # 静止时画圆
                s = pygame.Surface((int(current_radius*2), int(current_radius*2)), pygame.SRCALPHA)
                pygame.draw.circle(s, color, (int(current_radius), int(current_radius)), int(current_radius))
                surface.blit(s, (screen_pos[0]-current_radius, screen_pos[1]-current_radius), special_flags=pygame.BLEND_ADD)
            
            return
        if self.d_type == "heavy_shell":
            # 立绘 PNG 优先（随方向旋转），缺失回退程序绘制圆球
            if self._blit_proj_png(surface, zoom, screen_pos):
                return
            # 弹头
            pygame.draw.circle(surface, (20, 20, 20), screen_pos, scale(6, zoom))
            pygame.draw.circle(surface, (100, 100, 100), screen_pos, scale(4, zoom))
            # 简单的拖尾
            tail_len = scale(15, zoom)
            if self.vel.length() > 0:
                tail_end = self.pos - self.vel.normalize() * 15
                tail_screen = to_screen(tail_end, offset, zoom)
                pygame.draw.line(surface, (150, 150, 150), screen_pos, tail_screen, scale(4, zoom))
            return

        # 圆球家族统一走立绘 PNG（rocket/tank_shell/bullet/heavy/behemoth_bomb/ac130_vis 等），
        # 缺失对应 PNG 时回退下方彩色圆球
        if self._blit_proj_png(surface, zoom, screen_pos):
            return

        color = WHITE
        radius = 2
        if self.d_type == "heavy": color = YELLOW; radius = 3
        elif self.d_type == "rocket": color = ORANGE; radius = 5
        elif self.d_type == "ac130_vis": color = (255, 255, 0); radius = 4
        elif self.d_type == "tank_shell": color = (255, 200, 50); radius = 5

        pygame.draw.circle(surface, color, screen_pos, scale(radius, zoom))

class TargetMarker(pygame.sprite.Sprite):
    def __init__(self, game, pos, duration):
        super().__init__()
        self.game = game
        self.pos = vec(pos)
        self.timer = duration
        self.max_time = duration
        self.radius = 150 # 对应 AOE 范围

    def update(self):
        self.timer -= 1
        if self.timer <= 0: self.kill()

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        r = int(scale(self.radius, zoom))
        
        # 1. 倒计时圆环 (越来越小)
        progress = self.timer / self.max_time # 1.0 -> 0.0
        current_r = int(r * progress)
        
        pygame.draw.circle(surface, (255, 0, 0), screen_pos, max(1, current_r), 2)
        
        # 2. 目标点十字
        s = int(scale(10, zoom))
        pygame.draw.line(surface, RED, (screen_pos[0]-s, screen_pos[1]), (screen_pos[0]+s, screen_pos[1]), 2)
        pygame.draw.line(surface, RED, (screen_pos[0], screen_pos[1]-s), (screen_pos[0], screen_pos[1]+s), 2)
        
        # 3. 闪烁警告
        if self.timer % 30 < 15:
            t = self.game.ui_font.render("MISSILE INCOMING", True, RED)
            surface.blit(t, (screen_pos[0]+10, screen_pos[1]-20))
# 新增 FireZone 类
        screen_pos = to_screen(self.pos, offset, zoom)
        r = int(scale(self.radius, zoom))
        
        # 1. 倒计时圆环 (越来越小)
        progress = self.timer / self.max_time # 1.0 -> 0.0
        current_r = int(r * progress)
        
        pygame.draw.circle(surface, (255, 0, 0), screen_pos, max(1, current_r), 2)
        
        # 2. 目标点十字
        s = int(scale(10, zoom))
        pygame.draw.line(surface, RED, (screen_pos[0]-s, screen_pos[1]), (screen_pos[0]+s, screen_pos[1]), 2)
        pygame.draw.line(surface, RED, (screen_pos[0], screen_pos[1]-s), (screen_pos[0], screen_pos[1]+s), 2)
        
        # 3. 闪烁警告
        if self.timer % 30 < 15:
            t = self.game.ui_font.render("MISSILE INCOMING", True, RED)
            surface.blit(t, (screen_pos[0]+10, screen_pos[1]-20))
# 新增 FireZone 类
class FireZone(pygame.sprite.Sprite):
    def __init__(self, game, pos, team):
        super().__init__(game.particles) # 把它算作特效组，方便 update 和 draw
        self.game = game
        self.pos = vec(pos)
        self.team = team
        self.radius = 60
        self.life = FIRE_ZONE_DURATION # 180帧
        
    def update(self):
        self.life -= 1
        if self.life <= 0: self.kill()
        
        # 1. 造成伤害 (每 10 帧一次)
        if self.life % 10 == 0:
            targets = self.game.all_units + self.game.all_buildings
            for t in targets:
                if t.team != self.team and t.alive:
                    if self.pos.distance_to(t.pos) < self.radius + t.radius:
                        t.take_damage(DMG_FIRE_ZONE * 10, "fire",10000) # 伤害类型 fire
        
        # 2. 视觉特效 (冒火)
        if self.life % 5 == 0:
            offset = vec(random.randint(-self.radius, self.radius), random.randint(-self.radius, self.radius))
            # 只有在圆内才生成
            if offset.length() < self.radius:
                Particle(self.game.particles, self.pos + offset, (255, 100, 0), 0.5, 40, random.randint(5, 10))

    def draw(self, surface, offset, zoom):
        # 这是一个纯逻辑对象，不直接 draw (由 Particle 组管理)
        # 但如果要画个红圈示警：
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        s_rad = scale(self.radius, zoom)
        
        # 画一个半透明红圆
        s = pygame.Surface((s_rad*2, s_rad*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, 50, 0, 50), (s_rad, s_rad), s_rad)
        surface.blit(s, (screen_pos[0]-s_rad, screen_pos[1]-s_rad))
        # 这是一个纯逻辑对象，不直接 draw (由 Particle 组管理)
        # 但如果要画个红圈示警：
        screen_pos = to_screen(self.pos, offset, zoom)
        s_rad = scale(self.radius, zoom)
        
        # 画一个半透明红圆
        s = pygame.Surface((s_rad*2, s_rad*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, 50, 0, 50), (s_rad, s_rad), s_rad)
        surface.blit(s, (screen_pos[0]-s_rad, screen_pos[1]-s_rad))
class ConcreteRubble(Building):
    """大楼倒塌后生成的实体废墟块"""
    def __init__(self, game, pos):
        # 设为中立建筑，类型为 obstacle (障碍物)
        super().__init__(game, pos, "neutral", "obstacle")
        self.hp = 500 # 废墟也可以被摧毁
        self.max_hp = 500
        
        # 随机大小和形状
        self.size = random.randint(30, 50)
        self.radius = self.size * 0.8
        self.rect = pygame.Rect(pos.x - self.radius, pos.y - self.radius, self.radius*2, self.radius*2)
        
        # --- 生成随机外观 ---
        self.image = self._generate_image()
        
    def _generate_image(self):
        # 创建画布
        s = int(self.size * 2.5)
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        cx, cy = s // 2, s // 2
        
        # 1. 随机生成多边形 (模拟破碎的混凝土块)
        num_points = random.randint(5, 8)
        points = []
        for i in range(num_points):
            angle = (i / num_points) * 6.28
            # 半径随机扰动，制造不规则感
            r = self.size * random.uniform(0.7, 1.2)
            px = cx + math.cos(angle) * r
            py = cy + math.sin(angle) * r
            points.append((px, py))
            
        # 颜色：深灰/水泥灰
        color = random.choice([(80, 80, 85), (100, 95, 90), (70, 70, 70)])
        pygame.draw.polygon(surf, color, points)
        pygame.draw.polygon(surf, (40, 40, 40), points, 2) # 边框
        
        # 2. 表面细节 (裂缝)
        pygame.draw.line(surf, (20,20,20), points[0], points[2], 2)
        
        # 3. 裸露的钢筋 (Rebar) - 从废墟伸出的黑线
        for _ in range(3):
            start = (cx + random.randint(-10, 10), cy + random.randint(-10, 10))
            end = (start[0] + random.randint(-20, 20), start[1] + random.randint(-20, 20))
            pygame.draw.line(surf, (10, 10, 10), start, end, 2)
            
        return surf

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        
        # 简单的缩放绘制
        scaled_img = scale_img(self.image, zoom)
        rect = scaled_img.get_rect(center=screen_pos)
        surface.blit(scaled_img, rect)
        
        # 不需要血条，除非被攻击
        if self.hp < self.max_hp:
            self.draw_health_and_marker(surface, offset, zoom, -10)
        screen_pos = to_screen(self.pos, offset, zoom)
        
        # 简单的缩放绘制
        scaled_img = scale_img(self.image, zoom)
        rect = scaled_img.get_rect(center=screen_pos)
        surface.blit(scaled_img, rect)
        
        # 不需要血条，除非被攻击
        if self.hp < self.max_hp:
            self.draw_health_and_marker(surface, offset, zoom, -10)
class Skyscraper(Building):
    def __init__(self, game, pos):
        super().__init__(game, pos, "neutral", "skyscraper")
        self.b_type = "skyscraper"
        self.hp = 3000
        self.max_hp = 3000
        self.radius = 70
        self.rect = pygame.Rect(pos.x - 70, pos.y - 70, 140, 140)
        
        self.is_collapsed = False
        self.collapse_timer = 0
        
        # 颜色主题 (保持不变)
        themes = [
            {"roof": (110, 130, 150), "wall": (60, 70, 80), "glass": (100, 160, 220)}, 
            {"roof": (170, 160, 150), "wall": (110, 100, 90), "glass": (90, 110, 130)}, 
            {"roof": (210, 210, 210), "wall": (160, 160, 160), "glass": (60, 80, 100)}, 
        ]
        self.theme = random.choice(themes)
        
        # 建筑结构
        self.tiers = [
            (1.0, 1.0, 60),  
            (0.85, 0.85, 80), 
            (0.85, 0.85, 80), 
            (0.85, 0.85, 80), 
            (0.6, 0.6, 60),   
            (0.3, 0.3, 20)    
        ]
        self.total_visual_height = sum(t[2] for t in self.tiers)
        self.base_width = 140
        self.base_depth = 120
        
        # --- [新增] 战损数据 ---
        # 预先生成一些随机的裂缝和弹孔位置 (tier_index, local_x, local_y)
        # 这样每次绘制时位置固定，不会闪烁
        self.damage_spots = []
        for i in range(len(self.tiers)):
            # 每层预生成 3-5 个潜在损伤点
            for _ in range(random.randint(3, 5)):
                self.damage_spots.append({
                    'tier': i,
                    'x_pct': random.random(), # 0.0 ~ 1.0 (相对宽度)
                    'y_pct': random.random(), # 0.0 ~ 1.0 (相对高度)
                    'size': random.randint(10, 25),
                    'active_threshold': random.uniform(0.1, 0.9) # 当 HP% 低于此值时显示
                })

        # 静态外观基准图（PNG 缓存自动导出/加载；draw 优先 blit 此图）
        self.image = self.generate_image()

    def update(self):
        # 倒塌逻辑
        if not self.is_collapsed:
            if self.hp <= 0:
                self.start_collapse()
            
            # --- [新增] 燃烧特效 (Damage FX) ---
            # 如果血量低，持续产生烟雾和火焰粒子
            hp_pct = self.hp / self.max_hp
            if hp_pct < 0.7:
                # 随机选择一个已激活的损伤点生成粒子
                active_spots = [s for s in self.damage_spots if hp_pct < s['active_threshold']]
                
                if active_spots and random.random() < (1.0 - hp_pct) * 0.5: # 血越少概率越大
                    spot = random.choice(active_spots)
                    # 我们需要计算这个 spot 的大致世界坐标 (简化计算)
                    # 为了简单，直接在物体中心上方随机位置生成
                    # 更精确的做法是在 draw 里计算并返回坐标，或者在这里估算
                    
                    # 俯视外观：烟从屋顶面冒出（小负偏移），x 仍在屋顶范围内
                    offset_y = -random.randint(6, 26)
                    offset_x = (spot['x_pct'] - 0.5) * self.base_width
                    
                    particle_pos = self.pos + vec(offset_x, offset_y)
                    
                    if hasattr(self.game, 'particles'):
                        # 黑烟
                        Particle(self.game.particles, particle_pos, (50, 50, 50), 0.5, 60, random.randint(5, 10))
                        # 火焰 (严重受损时)
                        if hp_pct < 0.4 and random.random() < 0.3:
                            Particle(self.game.particles, particle_pos, (255, 100, 50), 0.8, 30, random.randint(3, 6))

        else:
            # 倒塌过程
            if self.collapse_timer > 0:
                self.collapse_timer -= 1
                if self.collapse_timer % 3 == 0:
                    offset = vec(random.randint(-60, 60), random.randint(-40, 40))
                    if hasattr(self.game, 'particles'):
                        Particle(self.game.particles, self.pos + offset, (100, 100, 100), 0.5, 90, random.randint(20, 50))

    def start_collapse(self):
        self.alive = False
        self.is_collapsed = True
        self.hp = 0
        self.collapse_timer = 90
        self.game.show_alert("BUILDING COLLAPSE!")
        
        # 爆炸特效
        if hasattr(self.game, 'particles'):
            for _ in range(30):
                Particle(self.game.particles, self.pos, (255, 100, 50), random.uniform(1, 3), 45, random.randint(10, 30))
                
        # 生成废墟 (复用之前的逻辑)
        num_rubble = random.randint(6, 8)
        spawn_radius = self.base_width * 0.6 
        for i in range(num_rubble):
            angle_deg = (i / num_rubble) * 360 + random.uniform(-15, 15)
            angle_rad = math.radians(angle_deg)
            dist = spawn_radius + random.uniform(0, 40)
            rx = self.pos.x + math.cos(angle_rad) * dist
            ry = self.pos.y + math.sin(angle_rad) * dist
            
            # 确保 ConcreteRubble 类已定义
            try:
                # from units import ConcreteRubble # 如果在同一文件则不需要
                rubble = ConcreteRubble(self.game, vec(rx, ry))
                if hasattr(self.game, 'neutral_buildings'):
                    self.game.neutral_buildings.append(rubble)
            except:
                pass # 忽略错误

        # 伤害判定 (略)

    # 天线在屋顶平面上的相对位置（俯视，占比坐标）
    ANT_X, ANT_Y = 0.90, 0.13

    def darken(self, color, factor=0.7):
        return (int(color[0] * factor), int(color[1] * factor), int(color[2] * factor))

    def _draw_static(self, surface, cx, cy, zoom):
        """静态外观（俯视微倾）：屋顶平面为主（停机坪/空调机组/水塔/屋顶间/天线座）
        + 南立面少量向下挤出 + 混凝土基座 + 地面阴影。
        （generate_image 与无图回退共用）战损斑点/天线警示灯为动态叠加，见 draw()"""
        bw = self.base_width * zoom      # 140
        bd = self.base_depth * zoom      # 120
        facade_h = scale(16, zoom)       # 南立面挤出高度
        roof = pygame.Rect(int(cx - bw / 2), int(cy - bd / 2), int(bw), int(bd))

        # --- 地面阴影（右下偏移，覆盖立面+基座投影）---
        off = scale(10, zoom)
        pygame.draw.rect(surface, (0, 0, 0), (roof.x + off, roof.y + scale(12, zoom),
                                              roof.w, roof.h + facade_h + scale(6, zoom)))

        # --- 混凝土基座 + 南立面（底部墙体挤出）---
        pygame.draw.rect(surface, (90, 90, 94),
                         (roof.x - scale(6, zoom), roof.bottom + facade_h - scale(2, zoom),
                          roof.w + scale(12, zoom), scale(8, zoom)))
        pygame.draw.rect(surface, (60, 60, 64),
                         (roof.x - scale(6, zoom), roof.bottom + facade_h - scale(2, zoom),
                          roof.w + scale(12, zoom), scale(8, zoom)), 1)
        pygame.draw.rect(surface, self.theme["wall"], (roof.x, roof.bottom, roof.w, facade_h))
        pygame.draw.rect(surface, (25, 25, 28), (roof.x, roof.bottom, roof.w, facade_h), 1)
        # 立面窗排 + 大门
        win_c = self.darken(self.theme["glass"], 0.7) if hasattr(self, 'theme') else (50, 60, 70)
        for wx in range(int(roof.x + scale(8, zoom)), int(roof.right - scale(10, zoom)), int(scale(16, zoom))):
            pygame.draw.rect(surface, win_c, (wx, roof.bottom + scale(4, zoom),
                                              scale(8, zoom), scale(7, zoom)))
        pygame.draw.rect(surface, (35, 35, 38), (cx - scale(8, zoom), roof.bottom,
                                                 scale(16, zoom), scale(11, zoom)))

        # --- 屋顶平面 ---
        pygame.draw.rect(surface, self.theme["roof"], roof)
        pygame.draw.rect(surface, self.darken(self.theme["roof"], 0.72), roof, scale(3, zoom))
        pygame.draw.rect(surface, (150, 150, 150), roof.inflate(-scale(6, zoom), -scale(6, zoom)), 1)

        # 屋顶间（楼梯间出口）
        box = pygame.Rect(int(cx - scale(24, zoom)), int(cy - scale(52, zoom)),
                          scale(24, zoom), scale(15, zoom))
        pygame.draw.rect(surface, self.theme["wall"], box)
        pygame.draw.rect(surface, (30, 30, 32), box, 1)
        pygame.draw.line(surface, (200, 200, 205), (box.x, box.y), (box.right, box.y), 1)

        # 停机坪（圆+黄圈+H 标线）
        hx, hy = int(cx - scale(35, zoom)), int(cy + scale(18, zoom))
        hr = scale(24, zoom)
        pygame.draw.circle(surface, (58, 64, 70), (hx, hy), hr)
        pygame.draw.circle(surface, (196, 168, 44), (hx, hy), hr, 2)
        bar_w = max(1, scale(3, zoom))
        pygame.draw.rect(surface, (196, 168, 44), (hx - bar_w // 2, hy - hr // 2, bar_w, hr))
        pygame.draw.rect(surface, (196, 168, 44), (hx - scale(7, zoom), hy - hr // 2,
                                                   scale(14, zoom), bar_w))
        pygame.draw.rect(surface, (196, 168, 44), (hx - scale(7, zoom), hy + hr // 2 - bar_w,
                                                   scale(14, zoom), bar_w))

        # 空调机组×2（灰色机箱+风扇圆）
        for ax, ay, aw, ah in ((scale(10, zoom), -scale(48, zoom), scale(26, zoom), scale(18, zoom)),
                               (scale(42, zoom), -scale(34, zoom), scale(20, zoom), scale(14, zoom))):
            u = pygame.Rect(int(cx + ax), int(cy + ay), int(aw), int(ah))
            pygame.draw.rect(surface, (150, 152, 156), u)
            pygame.draw.rect(surface, (70, 72, 76), u, 1)
            fr = max(1, scale(4, zoom))
            pygame.draw.circle(surface, (110, 112, 116), u.center, fr, 1)

        # 水塔（俯视圆罐+放射支撑）
        tx, ty, tr = int(cx + scale(48, zoom)), int(cy + scale(20, zoom)), scale(13, zoom)
        for a in range(0, 360, 45):
            ar = math.radians(a)
            pygame.draw.line(surface, (90, 94, 100), (tx, ty),
                             (tx + int(tr * math.cos(ar)), ty + int(tr * math.sin(ar))), 1)
        pygame.draw.circle(surface, (140, 146, 152), (tx, ty), tr)
        pygame.draw.circle(surface, (80, 84, 90), (tx, ty), tr, 2)
        pygame.draw.circle(surface, (165, 170, 176), (tx, ty), max(1, tr // 2))

        # 天线座（俯视小圆座，警示灯为动态）
        ant = (int(cx + (self.ANT_X - 0.5) * bw), int(cy + (self.ANT_Y - 0.5) * bd))
        pygame.draw.circle(surface, (70, 72, 76), ant, scale(4, zoom))
        pygame.draw.circle(surface, (130, 132, 136), ant, scale(2, zoom))

        # 屋顶行走步道（浅色连线：屋顶间→停机坪→立面门）
        pygame.draw.line(surface, (170, 172, 176), (box.centerx, box.bottom), (hx, hy - hr), 1)
        pygame.draw.line(surface, (170, 172, 176), (hx + hr, hy), (cx, roof.bottom), 1)

    def generate_image(self):
        """静态外观基准图（zoom=1），锚点 (86, 82) = self.pos（屋顶平面中心）；
        PNG 缓存由 sprite_cache 自动导出/加载"""
        surf = pygame.Surface((172, 180), pygame.SRCALPHA)
        self._draw_static(surf, 86, 82, 1.0)
        return surf

    def _image_anchor(self):
        return 86, 82

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        bx, by = screen_pos
        margin = 600 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return            
        # === 倒塌状态（动态，保留程序绘制） ===
        if self.is_collapsed:
            # 绘制烧焦的废墟底座
            rubble_w = self.base_width * zoom * 1.2
            rubble_h = self.base_depth * zoom * 1.2
            rect = pygame.Rect(bx - rubble_w/2, by - rubble_h/2, rubble_w, rubble_h)
            
            # 焦黑的底色
            pygame.draw.rect(surface, (40, 35, 30), rect)
            # 依然冒烟 (可选)
            return

        # === 正常状态：静态塔身（PNG 命中时为图片 blit，未命中现场绘制） ===
        hp_pct = self.hp / self.max_hp

        cx, cy = int(bx), int(by)
        if not self._blit_cached_image(surface, cx, cy, zoom):
            self._draw_static(surface, cx, cy, zoom)

        # --- 动态叠加：屋顶战损斑点（受损斑点 + 火光闪烁，保留程序绘制） ---
        roof = pygame.Rect(int(bx - self.base_width * zoom / 2), int(by - self.base_depth * zoom / 2),
                           int(self.base_width * zoom), int(self.base_depth * zoom))
        for spot in self.damage_spots:
            if hp_pct < spot['active_threshold']:
                sx = roof.left + roof.w * spot['x_pct']
                sy = roof.top + roof.h * spot['y_pct']
                sr = spot['size'] * zoom * 0.8
                pygame.draw.circle(surface, (20, 10, 5), (int(sx), int(sy)), int(sr))
                if hp_pct < 0.3 and random.random() < 0.8: # 火光闪烁
                    glow_r = sr * 0.6
                    pygame.draw.circle(surface, (255, 100, 0), (int(sx), int(sy)), int(glow_r))
                    pygame.draw.circle(surface, (255, 255, 100), (int(sx), int(sy)), int(glow_r*0.5))

        # --- 动态：天线警示灯闪烁 (受损就不亮了) ---
        if hp_pct > 0.2 and (pygame.time.get_ticks() // 500) % 2 == 0:
            ant_x = bx + (self.ANT_X - 0.5) * self.base_width * zoom
            ant_y = by + (self.ANT_Y - 0.5) * self.base_depth * zoom
            pygame.draw.circle(surface, (255, 0, 0), (int(ant_x), int(ant_y)), int(3*zoom))

        # 4. 血条
        self.draw_health_and_marker(surface, offset, zoom, -scale(74, zoom))
class Shipyard(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "shipyard")
        self.hp = 1500
        self.max_hp = 1500
        self.radius = 50
        self.rect = pygame.Rect(pos.x - 50, pos.y - 50, 100, 100)
        self.can_build_on_water = True # [特殊属性]
    def update(self):
        return super().update()        
    def _draw_static(self, surface, cx, cy, zoom):
        """静态外观：阴影 / 船坞平台·水域 / 龙门吊 / 控制室主体（generate_image 与无图回退共用）。
        水面波纹 / 队伍色屋顶条纹（team 可被网络同步改变）为动态，见 draw()"""
        w = scale(110, zoom)       # 总宽度 (左右跨度)
        l = scale(100, zoom)       # 总长度 (进深)
        dock_width = scale(50, zoom) # 中间水域宽度
        platform_w = (w - dock_width) // 2 # 两侧平台宽度

        C_CONCRETE    = (110, 110, 115) # 混凝土
        C_CONCRETE_DK = (80, 80, 85)    # 侧面/阴影
        C_WATER_DOCK  = (30, 60, 90)    # 船坞内的深水
        C_CRANE       = (220, 180, 20)  # 起重机黄
        C_CRANE_DARK  = (160, 120, 10)  # 起重机暗部
        C_CONTROL     = (80, 90, 100)   # 控制室

        # --- 绘制阴影 (U型) ---
        shadow_offset = scale(12, zoom)
        s_surf = pygame.Surface((w + shadow_offset, l + shadow_offset), pygame.SRCALPHA)
        pygame.draw.rect(s_surf, (0,0,0,80), (shadow_offset, shadow_offset, platform_w, l))
        pygame.draw.rect(s_surf, (0,0,0,80), (w - platform_w + shadow_offset, shadow_offset, platform_w, l))
        pygame.draw.rect(s_surf, (0,0,0,80), (shadow_offset, shadow_offset, w, scale(20, zoom)))
        surface.blit(s_surf, (cx - w//2, cy - l//2))

        top_y = cy - l//2 # 建筑最上沿 (靠岸的一侧)

        # 船坞内的水域 (Water Basin)
        dock_rect = pygame.Rect(cx - dock_width//2, top_y + scale(20, zoom), dock_width, l - scale(20, zoom))
        pygame.draw.rect(surface, C_WATER_DOCK, dock_rect)

        # 混凝土平台 (Concrete Platforms)
        # 后方连接平台 (Back)
        pygame.draw.rect(surface, C_CONCRETE, (cx - w//2, top_y, w, scale(25, zoom)))
        pygame.draw.line(surface, C_CONCRETE_DK, (cx - w//2, top_y + scale(25, zoom)), (cx + w//2, top_y + scale(25, zoom)), 2) # 边缘

        # 左侧臂 (Left Arm)
        left_rect = pygame.Rect(cx - w//2, top_y, platform_w, l)
        pygame.draw.rect(surface, C_CONCRETE, left_rect)
        pygame.draw.rect(surface, (130, 130, 135), left_rect, 1) # 高亮边缘
        # 侧壁厚度 (内侧，面向水)
        pygame.draw.rect(surface, C_CONCRETE_DK, (left_rect.right - 2, left_rect.top, 2, left_rect.height))

        # 右侧臂 (Right Arm)
        right_rect = pygame.Rect(cx + w//2 - platform_w, top_y, platform_w, l)
        pygame.draw.rect(surface, C_CONCRETE, right_rect)
        pygame.draw.rect(surface, (130, 130, 135), right_rect, 1)
        # 侧壁厚度 (内侧)
        pygame.draw.rect(surface, C_CONCRETE_DK, (right_rect.left, right_rect.top, 2, right_rect.height))

        # 装饰细节: 黄黑警示线 (在水岸边缘)
        for i in range(0, int(l), int(scale(15, zoom))):
            pygame.draw.rect(surface, (200, 180, 0), (left_rect.right - 4, top_y + i, 4, 8))
            pygame.draw.rect(surface, (200, 180, 0), (right_rect.left, top_y + i, 4, 8))
        # 系缆桩 (小黑点)
        for i in range(0, int(l), int(scale(30, zoom))):
            pygame.draw.circle(surface, (20, 20, 20), (left_rect.right - scale(8, zoom), top_y + scale(20, zoom) + i), 2)
            pygame.draw.circle(surface, (20, 20, 20), (right_rect.left + scale(8, zoom), top_y + scale(20, zoom) + i), 2)

        # --- 龙门吊 (Gantry Crane) ---
        crane_y = cy # 位于中间位置
        crane_h = scale(12, zoom) # 梁的粗细
        crane_leg_h = scale(25, zoom) # 腿高 (高度差)
        # 吊车轨道 (Rails)
        pygame.draw.line(surface, (40, 40, 45), (left_rect.centerx, top_y), (left_rect.centerx, top_y + l), 2)
        pygame.draw.line(surface, (40, 40, 45), (right_rect.centerx, top_y), (right_rect.centerx, top_y + l), 2)
        # 吊车支腿 (Legs)
        leg_l_pos = (left_rect.centerx, crane_y)
        leg_r_pos = (right_rect.centerx, crane_y)
        pygame.draw.rect(surface, C_CRANE_DARK, (leg_l_pos[0]-2, crane_y - crane_leg_h, 4, crane_leg_h))
        pygame.draw.rect(surface, C_CRANE_DARK, (leg_r_pos[0]-2, crane_y - crane_leg_h, 4, crane_leg_h))
        # 吊车横梁 (Main Beam)
        beam_rect = pygame.Rect(leg_l_pos[0] - scale(5, zoom), crane_y - crane_leg_h - crane_h,
                                leg_r_pos[0] - leg_l_pos[0] + scale(10, zoom), crane_h)
        pygame.draw.rect(surface, C_CRANE, beam_rect)
        pygame.draw.rect(surface, (50, 50, 50), beam_rect, 1) # 边框
        # 吊车上的斜纹警示
        for i in range(0, int(beam_rect.width), int(scale(10, zoom))):
            p1 = (beam_rect.left + i, beam_rect.bottom)
            p2 = (beam_rect.left + i + scale(5, zoom), beam_rect.top)
            if p2[0] < beam_rect.right:
                pygame.draw.line(surface, (0, 0, 0), p1, p2, 2)
        # 驾驶室 (Cab) - 挂在横梁下
        cab_x = leg_l_pos[0] + scale(10, zoom)
        pygame.draw.rect(surface, C_CONTROL, (cab_x, beam_rect.bottom, scale(12, zoom), scale(10, zoom)))
        pygame.draw.rect(surface, (20, 20, 20), (cab_x+2, beam_rect.bottom+2, 8, 4)) # 窗户
        # 吊钩 (Hook)
        hook_x = cx
        pygame.draw.line(surface, (20, 20, 20), (hook_x, beam_rect.bottom), (hook_x, beam_rect.bottom + scale(15, zoom)), 1)
        pygame.draw.circle(surface, (30, 30, 30), (int(hook_x), int(beam_rect.bottom + scale(15, zoom))), 3)

        # 附属设施: 控制塔/办公室主体 (队伍色屋顶条纹为动态，不画)
        office_rect = pygame.Rect(left_rect.left + scale(5, zoom), top_y - scale(10, zoom), scale(30, zoom), scale(20, zoom))
        pygame.draw.rect(surface, C_CONTROL, office_rect)

    def generate_image(self):
        """静态外观基准图（zoom=1），锚点 (56, 61) = self.pos；PNG 缓存由 sprite_cache 自动导出/加载"""
        surf = pygame.Surface((124, 124), pygame.SRCALPHA)
        self._draw_static(surf, 56, 61, 1.0)
        return surf

    def _image_anchor(self):
        return 56, 61

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        cx, cy = int(screen_pos[0]), int(screen_pos[1])

        if not self._blit_cached_image(surface, cx, cy, zoom):
            self._draw_static(surface, cx, cy, zoom)

        # --- 动态：水面波纹（保留程序绘制） ---
        w = scale(110, zoom)
        l = scale(100, zoom)
        dock_width = scale(50, zoom)
        top_y = cy - l//2
        dock_rect = pygame.Rect(cx - dock_width//2, top_y + scale(20, zoom), dock_width, l - scale(20, zoom))
        t = time.time()
        for i in range(3):
            wave_y = dock_rect.top + ((t * 10 + i * 30) % dock_rect.height)
            pygame.draw.line(surface, (50, 80, 120),
                            (dock_rect.left + 5, wave_y),
                            (dock_rect.right - 5, wave_y), 1)

        # --- 动态：队伍色屋顶条纹（team 可能被网络同步改变） ---
        team_color = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        office_x = cx - w//2 + scale(5, zoom)
        office_y = top_y - scale(10, zoom)
        pygame.draw.rect(surface, team_color, (office_x, office_y, scale(30, zoom), 4))

        self.draw_health_and_marker(surface, offset, zoom, -60)
class TechCenter(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "tech_center")
        self.hp = TECH_CENTER_HP
        self.max_hp = TECH_CENTER_HP
        self.radius = 60
        self.rect = pygame.Rect(pos.x - 60, pos.y - 60, 120, 120)
        self.power_usage = 150 

    def _draw_static(self, surface, cx, cy, zoom):
        """静态外观：阴影 / 外墙 / 组装坑（含网格）/ 左右屋顶平台（generate_image 与无图回退共用）。
        排气扇 / 阵营光条 / 扫描龙门架 / 火花为动态，见 draw()"""
        w = scale(110, zoom)       # 建筑宽度
        l = scale(90, zoom)        # 建筑进深
        pit_w = scale(60, zoom)    # 组装坑宽度
        pit_l = scale(70, zoom)    # 组装坑长度

        C_WALL        = (50, 55, 60)    # 建筑外墙
        C_ROOF        = (70, 75, 80)    # 屋顶
        C_PIT_FLOOR   = (20, 20, 25)    # 坑底深色

        # --- 绘制阴影 ---
        shadow_offset = scale(10, zoom)
        s_surf = pygame.Surface((w + shadow_offset, l + shadow_offset), pygame.SRCALPHA)
        pygame.draw.rect(s_surf, (0, 0, 0, 80), (shadow_offset, shadow_offset, w, l), border_radius=int(scale(8, zoom)))
        surface.blit(s_surf, (cx - w//2, cy - l//2))

        # --- 建筑主体 (Structure) ---
        base_rect = pygame.Rect(cx - w//2, cy - l//2, w, l)
        # 外墙底座
        pygame.draw.rect(surface, C_WALL, base_rect, border_radius=int(scale(5, zoom)))
        # 组装坑 (Assembly Pit) 位于中央
        pit_rect = pygame.Rect(cx - pit_w//2, cy - pit_l//2, pit_w, pit_l)
        pygame.draw.rect(surface, C_PIT_FLOOR, pit_rect)
        pygame.draw.rect(surface, (10, 10, 10), pit_rect, 2) # 坑壁内阴影
        # 坑底网格线 (Grid)
        grid_spacing = scale(15, zoom)
        for i in range(1, 5):
            lx = pit_rect.left + i * grid_spacing
            if lx < pit_rect.right:
                pygame.draw.line(surface, (30, 40, 50), (lx, pit_rect.top), (lx, pit_rect.bottom), 1)
            ly = pit_rect.top + i * grid_spacing
            if ly < pit_rect.bottom:
                pygame.draw.line(surface, (30, 40, 50), (pit_rect.left, ly), (pit_rect.right, ly), 1)

        # 屋顶平台 (左右两侧)
        left_roof = pygame.Rect(base_rect.left, base_rect.top, (w - pit_w)//2, l)
        pygame.draw.rect(surface, C_ROOF, left_roof)
        pygame.draw.rect(surface, (90, 95, 100), left_roof, 1) # 边框
        right_roof = pygame.Rect(pit_rect.right, base_rect.top, (w - pit_w)//2, l)
        pygame.draw.rect(surface, C_ROOF, right_roof)
        pygame.draw.rect(surface, (90, 95, 100), right_roof, 1)

    def generate_image(self):
        """静态外观基准图（zoom=1），锚点 (57, 47) = self.pos；PNG 缓存由 sprite_cache 自动导出/加载"""
        surf = pygame.Surface((124, 104), pygame.SRCALPHA)
        self._draw_static(surf, 57, 47, 1.0)
        return surf

    def _image_anchor(self):
        return 57, 47

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        cx, cy = int(screen_pos[0]), int(screen_pos[1])

        if not self._blit_cached_image(surface, cx, cy, zoom):
            self._draw_static(surface, cx, cy, zoom)

        # --- 动态细节（保留程序绘制） ---
        t = time.time()
        team_c = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])

        # 几何参数（与 _draw_static 一致）
        w = scale(110, zoom)
        l = scale(90, zoom)
        pit_w = scale(60, zoom)
        pit_l = scale(70, zoom)
        base_rect = pygame.Rect(cx - w//2, cy - l//2, w, l)
        pit_rect = pygame.Rect(cx - pit_w//2, cy - pit_l//2, pit_w, pit_l)
        left_roof = pygame.Rect(base_rect.left, base_rect.top, (w - pit_w)//2, l)
        right_roof = pygame.Rect(pit_rect.right, base_rect.top, (w - pit_w)//2, l)

        # 4.1 旋转排气扇 (两侧屋顶)
        fan_r = scale(8, zoom)
        fan_positions = [
            (left_roof.centerx, left_roof.centery - scale(20, zoom)),
            (left_roof.centerx, left_roof.centery + scale(20, zoom)),
            (right_roof.centerx, right_roof.centery)
        ]
        for fx, fy in fan_positions:
            pygame.draw.circle(surface, (20, 20, 20), (int(fx), int(fy)), int(fan_r))
            pygame.draw.circle(surface, (60, 60, 60), (int(fx), int(fy)), int(fan_r), 1)
            angle_offset = t * 8
            for i in range(3):
                angle = angle_offset + i * (2 * math.pi / 3)
                ex = fx + math.cos(angle) * fan_r
                ey = fy + math.sin(angle) * fan_r
                pygame.draw.line(surface, (50, 50, 50), (fx, fy), (ex, ey), 2)

        # 4.2 阵营光条
        pygame.draw.rect(surface, team_c, (left_roof.right - 4, left_roof.top + 5, 2, l - 10))
        pygame.draw.rect(surface, team_c, (right_roof.left + 2, right_roof.top + 5, 2, l - 10))

        # 5. 移动龙门架/打印臂 (Scanning Gantry)
        slide_progress = (math.sin(t * 2) + 1) / 2 # 0 ~ 1
        gantry_y = pit_rect.top + slide_progress * (pit_l - scale(10, zoom))
        gantry_h = scale(8, zoom)
        gantry_rect = pygame.Rect(pit_rect.left - 2, gantry_y, pit_w + 4, gantry_h)

        # 激光扫描面 (在龙门架下方，半透明渐变光片)
        C_GLOW = (0, 200, 255)
        beam_h = scale(20, zoom)
        s_beam = pygame.Surface((pit_w, beam_h), pygame.SRCALPHA)
        for i in range(int(beam_h)):
            alpha = int(100 * (1 - i/beam_h))
            pygame.draw.line(s_beam, (*C_GLOW, alpha), (0, i), (pit_w, i))
        surface.blit(s_beam, (pit_rect.left, gantry_rect.bottom))

        # 龙门架实体
        C_GANTRY = (100, 100, 110)
        pygame.draw.rect(surface, C_GANTRY, gantry_rect)
        pygame.draw.circle(surface, (0, 255, 0), (int(gantry_rect.left + 5), int(gantry_rect.centery)), 2)
        pygame.draw.circle(surface, (255, 0, 0), (int(gantry_rect.right - 5), int(gantry_rect.centery)), 2)
        # 发光核心 (打印头)
        C_LASER = (150, 255, 255)
        head_x = gantry_rect.left + (math.sin(t * 5) + 1) / 2 * gantry_rect.width
        pygame.draw.circle(surface, C_LASER, (int(head_x), int(gantry_rect.centery)), 3)

        # 6. 制造火花特效 (Sparks)
        if random.random() < 0.3:
            sx = random.randint(pit_rect.left, pit_rect.right)
            sy = int(gantry_rect.bottom + random.randint(0, 10))
            pygame.draw.circle(surface, (255, 255, 200), (sx, sy), 1)
            pygame.draw.line(surface, (255, 255, 255), (sx, sy), (sx+2, sy+2), 1)

        # 7. 进度条/血条
        if hasattr(self, 'build_progress') and self.build_progress > 0:
            bar_w = scale(40, zoom)
            bar_h = scale(4, zoom)
            bx = cx - bar_w//2
            by = base_rect.top - scale(15, zoom)
            pygame.draw.rect(surface, (0,0,0), (bx, by, bar_w, bar_h))
            pygame.draw.rect(surface, (0, 255, 0), (bx, by, bar_w * self.build_progress, bar_h))

        self.draw_health_and_marker(surface, offset, zoom, -scale(60, zoom))
class EMPGenerator(Entity):
    def __init__(self, game, pos):
        super().__init__(game, pos, "neutral")
        self.hp = 2000
        self.max_hp = 2000
        self.radius = 50
        self.rect = pygame.Rect(pos.x - 50, pos.y - 50, 100, 100)
        self.capture_progress = 0
        self.capturing_team = None
        self.max_capture = 300 # 占领时间较长
        self.cooldown = 0
        
    def update(self):
        if self.cooldown > 0: self.cooldown -= 1
        
        # 占领逻辑 (复制自 OilDerrick，简化)
        if not self.game.is_online or self.game.my_role == "HOST":
            # ... (这里省略重复的占领代码，请参考 OilDerrick) ...
            # 重点：当占领成功时，如果冷却完毕，触发 EMP
            pass
            
            # 简化的触发逻辑示例：
            if self.team != "neutral" and self.cooldown <= 0:
                self.trigger_emp()
                self.cooldown = EMP_COOLDOWN # 重置冷却，并归还中立？或者持续属于某方

    def trigger_emp(self):
        # 触发全图(或大范围) EMP
        self.game.particles.add(FloatingText(self.pos, "EMP DISCHARGE!", CYAN, 120))
        
        # 特效同步
        if not self.game.is_online or self.game.my_role == "HOST":
             if hasattr(self.game, 'net_events'):
                self.game.net_events.append({
                    "type": "EXPLOSION", "x": int(self.pos.x), "y": int(self.pos.y), "dt": "behemoth_bomb" # 借用大爆炸特效
                })

        # 逻辑：晕眩所有机械单位
        targets = self.game.all_units
        for u in targets:
            if u.is_mechanical and u.pos.distance_to(self.pos) < EMP_RANGE:
                # 给单位添加 stun 属性 (需要在 Unit.update 里支持)
                u.stun_timer = EMP_DURATION 
                self.game.particles.add(FloatingText(u.pos, "ZZZ...", CYAN))

    def _draw_static(self, surface, cx, cy, zoom):
        """静态外观：科幻塔基座圆盘（generate_image 与无图回退共用）。
        核心状态色圆 / 充能电弧为动态，见 draw()"""
        pygame.draw.circle(surface, (30, 30, 30), (cx, cy), scale(40, zoom))

    def generate_image(self):
        """静态外观基准图（zoom=1），锚点 (42, 42) = self.pos；PNG 缓存由 sprite_cache 自动导出/加载"""
        surf = pygame.Surface((84, 84), pygame.SRCALPHA)
        self._draw_static(surf, 42, 42, 1.0)
        return surf

    def _image_anchor(self):
        return 42, 42

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        cx, cy = int(screen_pos[0]), int(screen_pos[1])

        # --- 静态基座（PNG 命中时为图片 blit，未命中现场绘制） ---
        if not self._blit_cached_image(surface, cx, cy, zoom):
            self._draw_static(surface, cx, cy, zoom)

        # --- 动态：核心状态色 + 充能电弧（保留程序绘制） ---
        color = CYAN if self.cooldown <= 0 else GRAY
        pygame.draw.circle(surface, color, (cx, cy), scale(15, zoom))
        if self.cooldown <= 0:
            pygame.draw.circle(surface, WHITE, (cx, cy), scale(10 + math.sin(pygame.time.get_ticks()*0.01)*5, zoom), 2)

        self.draw_health_and_marker(surface, offset, zoom)
class AncientTemple(Building):
    def __init__(self, game, pos):
        super().__init__(game, pos, "neutral", "temple")
        self.hp = 400
        self.max_hp = 400
        self.radius = 60
        self.rect = pygame.Rect(pos.x - 60, pos.y - 60, 120, 120)
        
        # [新增] 倒塌状态
        self.is_collapsed = False
        self.collapse_timer = 0

    # [新增] 类似于 Skyscraper 的逻辑
    def update(self):
        if not self.is_collapsed:
            if self.hp <= 0:
                self.start_collapse()
        else:
            if self.collapse_timer > 0:
                self.collapse_timer -= 1
                # 灰尘特效
                if self.collapse_timer % 5 == 0:
                    Particle(self.game.particles, self.pos + vec(random.randint(-40,40), random.randint(-40,40)), (150,140,100), 1, 60, 20)

    def start_collapse(self):
        self.is_collapsed = True
        self.hp = 0
        self.alive = False # 逻辑死亡，允许单位通过(如果单位逻辑检查的是alive)
        self.collapse_timer = 120 
        
        self.game.show_alert("TEMPLE RUINED!")
        
        # 爆炸/崩塌特效
        for _ in range(20):
            Particle(self.game.particles, self.pos, (160, 140, 100), random.uniform(2,5), 60, 15)
        
    def _draw_static(self, surface, cx, cy, zoom):
        """静态外观：三层宝塔俯视（屋檐·墙体）+ 金顶（generate_image 与无图回退共用）。
        倒塌废墟为动态，见 draw()"""
        roof_color = (180, 60, 40)  # 朱红/砖红
        wall_color = (160, 140, 100) # 土黄墙

        # 这是一个三层塔的俯视图
        layers = 3
        base_size = scale(100, zoom)
        for i in range(layers):
            s = base_size - i * scale(25, zoom)
            rect = pygame.Rect(0, 0, s, s)
            rect.center = (cx, cy)

            # 屋檐 (带翘角)
            pygame.draw.rect(surface, roof_color, rect)
            pygame.draw.rect(surface, (100, 30, 20), rect, 2) # 轮廓

            # 墙体 (比屋檐小一点)
            inner_s = s - scale(10, zoom)
            if inner_s > 0:
                inner_rect = pygame.Rect(0, 0, inner_s, inner_s)
                inner_rect.center = (cx, cy)
                pygame.draw.rect(surface, wall_color, inner_rect)

        # 塔顶装饰
        pygame.draw.circle(surface, (255, 215, 0), (cx, cy), scale(8, zoom)) # 金顶

    def generate_image(self):
        """静态外观基准图（zoom=1），锚点 (52, 52) = self.pos；PNG 缓存由 sprite_cache 自动导出/加载"""
        surf = pygame.Surface((104, 104), pygame.SRCALPHA)
        self._draw_static(surf, 52, 52, 1.0)
        return surf

    def _image_anchor(self):
        return 52, 52

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        if self.is_collapsed:
            # 绘制废墟 (一堆碎石，动态，保留程序绘制)
            for i in range(5):
                offset_x = random.randint(-40, 40)
                offset_y = random.randint(-40, 40)
                # 使用确定性随机(基于位置)防止抖动，或者简单画几个固定的块
                # 这里为了简单，画个大的废墟堆
                pygame.draw.circle(surface, (100, 90, 80), screen_pos, scale(60, zoom))
                pygame.draw.rect(surface, (80, 70, 60), (screen_pos[0]-scale(30, zoom), screen_pos[1], scale(60, zoom), scale(20, zoom)))
        else:
            # --- 静态塔身（PNG 命中时为图片 blit，未命中现场绘制） ---
            if not self._blit_cached_image(surface, int(screen_pos[0]), int(screen_pos[1]), zoom):
                self._draw_static(surface, int(screen_pos[0]), int(screen_pos[1]), zoom)

            self.draw_health_and_marker(surface, offset, zoom, -60)
class ChineseHouseGenerator:
    def __init__(self):
        # 配色方案 (保持不变，或微调更鲜艳一点)
        self.palettes = [
            {'wall': (245, 245, 240), 'roof': (60, 65, 70), 'accent': (100, 80, 60)}, 
            {'wall': (200, 205, 210), 'roof': (50, 55, 60), 'accent': (140, 100, 80)},
            {'wall': (230, 220, 200), 'roof': (90, 80, 70), 'accent': (120, 90, 60)},
            {'wall': (150, 160, 170), 'roof': (40, 45, 50), 'accent': (80, 80, 90)},
            {'wall': (250, 250, 250), 'roof': (180, 180, 180), 'accent': (50, 50, 50)},
            {'wall': (80, 80, 85), 'roof': (30, 30, 35), 'accent': (200, 180, 150)}, 
            {'wall': (220, 210, 200), 'roof': (140, 80, 70), 'accent': (100, 60, 50)},
            {'wall': (230, 235, 230), 'roof': (60, 70, 60), 'accent': (100, 120, 80)},
            {'wall': (220, 220, 225), 'roof': (20, 20, 25), 'accent': (40, 40, 45)},
            {'wall': (240, 235, 220), 'roof': (70, 60, 50), 'accent': (180, 140, 60)}
        ]

    def darken(self, color, factor=0.7):
        return (int(color[0]*factor), int(color[1]*factor), int(color[2]*factor))

    def lighten(self, color, factor=1.2):
        return (min(255, int(color[0]*factor)), min(255, int(color[1]*factor)), min(255, int(color[2]*factor)))

    def draw_box_3d(self, surf, x, y, w, h, d, color_wall, color_roof, color_accent, has_eaves=True):
        x_shift = d * 0.5 
        y_shift = d * 0.4
        # Front Face (正面)
        fl_bot = (x, y)             # Front-Left-Bottom
        fr_bot = (x + w, y)         # Front-Right-Bottom
        fl_top = (x, y - h)         # Front-Left-Top
        fr_top = (x + w, y - h)     # Front-Right-Top
        
        bl_top = (x + x_shift, y - h - y_shift) # Back-Left-Top
        br_top = (x + w + x_shift, y - h - y_shift) # Back-Right-Top
        br_bot = (x + w + x_shift, y - y_shift)     # Back-Right-Bottom


        pygame.draw.ellipse(surf, (0,0,0, 120), (x-10, y-5, w+x_shift+20, 15))


        side_poly = [fr_bot, br_bot, br_top, fr_top]
        color_side = self.darken(color_wall, 0.45) 
        pygame.draw.polygon(surf, color_side, side_poly)
        
        front_rect = pygame.Rect(x, y - h, w, h)
        pygame.draw.rect(surf, color_wall, front_rect)        
        pygame.draw.rect(surf, self.darken(color_wall, 0.6), (x, y-5, w, 5))
        
        if has_eaves:
            eave_out = 8 
            roof_h = 20  
            
            # 屋顶基准面 (在墙顶上方)
            # Front Eave Line
            fe_l = (fl_top[0] - eave_out, fl_top[1])
            fe_r = (fr_top[0] + eave_out, fr_top[1])
            
            # Back Eave Line
            be_l = (bl_top[0] - eave_out, bl_top[1])
            be_r = (br_top[0] + eave_out, br_top[1])
            
            # Ridge Line (屋脊) - 居中且升高
            ridge_x_start = (fe_l[0] + fe_r[0]) / 2 + x_shift * 0.5 # 稍微向后偏一点
            ridge_y_start = fe_l[1] - roof_h - y_shift * 0.5
            
            # 屋脊长度 = 檐口长度 (如果是歇山顶则短一点，这里画悬山顶)
            ridge_start = (ridge_x_start, ridge_y_start)
            ridge_end   = (ridge_x_start + (be_r[0]-fe_r[0])*0.8, ridge_y_start - (y_shift)*0.8) # 稍微短一点增加透视感
            # 简化：屋脊平行于前后檐
            ridge_start = ((fl_top[0]+fr_top[0])/2, fl_top[1] - roof_h)
            ridge_end   = ((bl_top[0]+br_top[0])/2, bl_top[1] - roof_h)
            
            # 绘制屋顶侧面 (三角形) - 可见
            # [fe_r, ridge_start, ridge_end, be_r] ? 不对，这里侧面是一个斜坡
            
            # 右坡 (Right Slope) - 面向右上方，亮色
            # 连接: fr_top+eave -> ridge -> br_top+eave
            right_slope = [fe_r, ridge_start, ridge_end, be_r]
            pygame.draw.polygon(surf, self.darken(color_roof, 0.8), right_slope)
            
            # 前坡 (Front Slope) - 面向前方，本色
            front_slope = [fe_l, fe_r, ridge_start]
            pygame.draw.line(surf, self.lighten(color_roof), ridge_start, ridge_end, 3)
            
            # 前坡面 (梯形)
            poly_front_roof = [fe_l, fe_r, ridge_end, ridge_start]
            pygame.draw.polygon(surf, color_roof, poly_front_roof)
            
            # 侧檐口厚度
            pygame.draw.line(surf, (30,30,30), fe_r, (fe_r[0], fe_r[1]+3), 2)
            
            # 飞檐装饰
            pygame.draw.line(surf, color_accent, fe_l, ridge_start, 2)
            pygame.draw.line(surf, color_accent, fe_r, ridge_end, 2)

        else:
            # 平顶 (Flat Roof)
            # 顶面多边形: [fl_top, fr_top, br_top, bl_top]
            top_poly = [fl_top, fr_top, br_top, bl_top]
            pygame.draw.polygon(surf, color_roof, top_poly)
            # 女儿墙内侧阴影
            pygame.draw.rect(surf, self.darken(color_roof), (x+2, y-h-2, w-4, 2))

    def draw_window(self, surf, x, y, w, h, color):
        """画有深度的窗户"""
        # 窗框
        pygame.draw.rect(surf, color, (x, y, w, h), 1)
        # 玻璃
        pygame.draw.rect(surf, (40, 50, 60), (x+1, y+1, w-2, h-2))
        # 窗台 (深度)
        pygame.draw.line(surf, (200,200,200), (x, y+h), (x+w, y+h), 2)

    def generate(self, variant_id):
        # 画布尺寸翻倍：200x200
        W, H = 200, 200
        surf = pygame.Surface((W, H), pygame.SRCALPHA)
        
        vid = variant_id % 10
        palette = self.palettes[vid]
        
        cw, cr, ca = palette['wall'], palette['roof'], palette['accent']
        
        # 基准点 (底部中心)
        bx = W // 2 - 20 # 稍微偏左一点留出右侧投影空间
        by = H - 20
        
        # 尺寸放大 (Scale up)
        base_w = 80  # 原来是 40-50
        base_h = 70  # 高度
        base_d = 50  # 深度
        
        # === 户型生成 ===
        
        if vid == 0: # 独栋
            self.draw_box_3d(surf, bx-40, by, 80, 60, 40, cw, cr, ca, True)
            self.draw_window(surf, bx-25, by-40, 20, 20, ca)
            self.draw_window(surf, bx+5, by-40, 20, 20, ca)
            # 门
            pygame.draw.rect(surf, ca, (bx-10, by-25, 20, 25))

        elif vid == 1: # L型 (主楼+侧屋)
            # 主楼 (靠后)
            self.draw_box_3d(surf, bx-20, by, 60, 80, 40, cw, cr, ca, False)
            # 侧屋 (靠前)
            self.draw_box_3d(surf, bx-60, by, 40, 40, 40, cw, cr, ca, True)
            
        elif vid == 2: # 双拼
            w = 40
            self.draw_box_3d(surf, bx-w-5, by, w, 70, 40, cw, cr, ca, True)
            self.draw_box_3d(surf, bx+5, by, w, 70, 40, cw, cr, ca, True)

        elif vid == 3: # 叠拼 (二层悬挑)
            # 一层
            self.draw_box_3d(surf, bx-40, by, 80, 40, 50, self.darken(cw), cr, ca, False)
            # 二层 (退台)
            self.draw_box_3d(surf, bx-30, by-40, 60, 40, 40, cw, cr, ca, True)

        elif vid == 4: # 高层公寓
            self.draw_box_3d(surf, bx-30, by, 60, 100, 40, cw, cr, ca, False)
            # 竖条装饰
            pygame.draw.line(surf, ca, (bx, by-90), (bx, by-10), 2)

        elif vid == 5: # 围合院落
            # 后房
            self.draw_box_3d(surf, bx-40, by-20, 80, 50, 30, cw, cr, ca, True)
            # 围墙
            pygame.draw.rect(surf, self.darken(cw), (bx-50, by-30, 100, 30))
            pygame.draw.rect(surf, cr, (bx-52, by-32, 104, 4)) # 墙头
            # 大门
            pygame.draw.rect(surf, ca, (bx-10, by-28, 20, 28))

        elif vid == 6: # 现代悬挑
            # 核心
            self.draw_box_3d(surf, bx-20, by, 40, 80, 30, self.darken(cw), cr, ca, False)
            # 悬挑盒子
            self.draw_box_3d(surf, bx-40, by-50, 80, 30, 40, cw, cr, ca, False)

        elif vid == 7: # 亭子
            # 柱子
            pygame.draw.rect(surf, ca, (bx-30, by-60, 5, 60))
            pygame.draw.rect(surf, ca, (bx+25, by-60, 5, 60))
            # 基座
            self.draw_box_3d(surf, bx-35, by, 70, 10, 40, self.darken(cw), cr, ca, False)
            # 大屋顶
            pts = [(bx-45, by-60), (bx+45, by-60), (bx, by-90)]
            pygame.draw.polygon(surf, cr, pts)
            # 翘角
            pygame.draw.arc(surf, cr, (bx-50, by-70, 30, 20), 3.14, 4.71, 3)
            pygame.draw.arc(surf, cr, (bx+20, by-70, 30, 20), 0, 1.57, 3)

        elif vid == 8: # 联排
            for i in range(3):
                self.draw_box_3d(surf, bx-60 + i*40, by, 35, 60, 30, cw, cr, ca, True)

        elif vid == 9: # 豪宅
            self.draw_box_3d(surf, bx-60, by, 120, 50, 60, cw, cr, ca, False)
            # 落地窗
            pygame.draw.rect(surf, (50, 80, 100), (bx-50, by-40, 80, 30))

        return surf
class CivilianHouse(Building):
    # 变体类：sprite_cache 按变体号分开存取 PNG（image_v0.png...）
    _variant_attr = 'variant_id'
    _variant_count = 10

    def __init__(self, game, pos, variant_id=None):
        super().__init__(game, pos, "neutral", "house") 
        
        self.b_type = "house"
        self.hp = 1000
        self.max_hp = 1000
        self.radius = 30
        self.rect = pygame.Rect(pos.x - 30, pos.y - 30, 60, 60)
        
        # 1. 确定外观 ID
        if variant_id is not None:
            self.variant_id = variant_id
        else:
            self.variant_id = random.randint(0, 9)
            
        self.gen = ChineseHouseGenerator()
        self.image = self.gen.generate(self.variant_id)

        self.is_collapsed = False
        self.garrison = []
        self.capacity = 4
        self.attack_cooldown = 0
        self.can_garrison = True # 标记
    def update(self):
        super().update()
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        
        # 1. 驻军攻击逻辑
        if self.garrison:
            # 房子的队伍 = 第一个进驻者的队伍
            self.team = self.garrison[0].team
            
            if not self.game.is_online or self.game.my_role == "HOST":
                if self.attack_cooldown <= 0:
                    target = self.find_nearest_enemy() # 复用 Bunker 的索敌
                    if target and self.pos.distance_to(target.pos)<300:
                        self.fire_barrage(target) 
        if not self.is_collapsed and self.hp <= 0:
            self.start_collapse()
    def find_nearest_enemy(self):
        nearest = None
        min_dist = 99999
        enemies = [u for u in self.game.all_units if u.team != self.team and not u.is_air]
        for e in enemies:

            if getattr(e, 'is_stealth', False):
                # 还可以加距离判断：贴脸了还是能看见
                if self.pos.distance_to(e.pos) > 50: 
                    continue  
            dist = self.pos.distance_to(e.pos)
            if dist < min_dist: min_dist = dist; nearest = e
        return nearest

    def fire_barrage(self, target):
        # 发射子弹数 = 驻军数量
        for _ in range(len(self.garrison)):
            # 随机窗口开火
            offset = vec(random.randint(-20,20), random.randint(-20,20))
            p = Projectile(self.game, self.pos+offset, target, self.team, 15, "heavy") # 步枪伤害
            self.game.projectiles.append(p)
        
        self.attack_cooldown = 30 # 射速中等

    def enter_unit(self, unit):
        from units import Rifleman
        if not isinstance(unit, Rifleman):
            return False
        if len(self.garrison) < self.capacity :
            self.garrison.append(unit)
            self.game.all_units.remove(unit) # 从地图移除
            return True
        return False
    def start_collapse(self):
        self.is_collapsed = True
        self.hp = 0
        self.alive = False # 逻辑死亡
        # 播放倒塌特效 (假设 game.particles 存在)
        if hasattr(self.game, 'particles'):
            for _ in range(5):
                # 生成灰色尘土粒子
                # Particle(list, pos, color, speed, life, size)
                Particle(self.game.particles, self.pos, (100, 90, 80), 1, 30, 10)

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 200 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return            
        if self.is_collapsed:
            # 绘制废墟 (简单的瓦砾堆)
            w = scale(40, zoom)
            rect = pygame.Rect(0, 0, w, w)
            rect.center = screen_pos
            pygame.draw.rect(surface, (80, 75, 70), rect) # 废墟灰
            pygame.draw.line(surface, (50,50,50), rect.topleft, rect.bottomright, 2)
            pygame.draw.line(surface, (50,50,50), rect.topright, rect.bottomleft, 2)
        else:
            # 1. 绘制房子
            scaled_img = scale_img(self.image, zoom)
            rect = scaled_img.get_rect(center=screen_pos)
            surface.blit(scaled_img, rect)
            
            # 2. [新增] 绘制阵营旗帜 (如果有驻军)
            if self.garrison:
                # 获取当前控制者的颜色
                team_c = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
                
                # 旗杆位置 (屋顶右上角，稍微偏左)
                flag_base_x = screen_pos[0] + scale(15, zoom)
                flag_base_y = screen_pos[1] - scale(25, zoom)
                
                flag_h = scale(20, zoom)
                flag_w = scale(12, zoom)
                
                # 旗杆
                pygame.draw.line(surface, (50, 50, 50), (flag_base_x, flag_base_y), (flag_base_x, flag_base_y - flag_h), 2)
                
                # 旗面 (随风飘动效果 - 可选)
                pygame.draw.rect(surface, team_c, (flag_base_x, flag_base_y - flag_h, flag_w, flag_h//1.5))
                
                # 显示驻军数量 (小点)
                for i in range(len(self.garrison)):
                    dot_y = flag_base_y - flag_h + i * 3
                    pygame.draw.circle(surface, (255, 255, 255), (flag_base_x - 3, dot_y), 1)

            # 3. 血条
            self.draw_health_and_marker(surface, offset, zoom)

# =============================================================================
# 欧式建筑（中立装饰，逻辑与民居完全一致：可驻军/可摧毁/倒塌成废墟，
# 仅外观为欧式风格。外观由程序生成器绘制，种子=variant_id，主客机一致）
# =============================================================================
class _EuroGenBase:
    """欧式建筑外观生成器基类：固定随机种子 → 同 variant 永远同一张图"""
    SIZE = (60, 60)
    PALETTES = [{}]

    def darken(self, color, factor=0.7):
        return (int(color[0] * factor), int(color[1] * factor), int(color[2] * factor))

    def lighten(self, color, factor=1.2):
        return (min(255, int(color[0] * factor)), min(255, int(color[1] * factor)),
                min(255, int(color[2] * factor)))

    def generate(self, variant_id=0):
        rng = random.Random(777 + int(variant_id) * 31)
        w, h = self.SIZE
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (0, 0, 0, 90),
                            (int(w * 0.06), h - 11, int(w * 0.88), 11))   # 地面阴影
        self._paint(surf, rng, self.PALETTES[int(variant_id) % len(self.PALETTES)], rng)
        return surf

    def _paint(self, surf, rng, pal, rng2=None):
        raise NotImplementedError

    def _speckle(self, surf, rng, zone, base, n=None):
        """石墙做旧噪点（确定性）"""
        n = n or max(6, (zone.w * zone.h) // 90)
        for _ in range(n):
            x = rng.randrange(zone.x, max(zone.x + 1, zone.right))
            y = rng.randrange(zone.y, max(zone.y + 1, zone.bottom))
            f = rng.choice((0.88, 0.94, 1.05))
            surf.set_at((x, y), (min(255, int(base[0] * f)),
                                 min(255, int(base[1] * f)),
                                 min(255, int(base[2] * f))))


class ChurchGenerator(_EuroGenBase):
    """欧式教堂（俯视微倾）：拉丁十字坡顶平面+方塔同心方尖顶+平贴金十字+南面裙墙"""
    SIZE = (76, 96)
    PALETTES = [
        {'stone': (208, 203, 192), 'roof': (88, 104, 110), 'wood': (96, 64, 40)},
        {'stone': (196, 190, 178), 'roof': (74, 92, 98), 'wood': (88, 58, 36)},
        {'stone': (214, 208, 196), 'roof': (96, 112, 116), 'wood': (104, 70, 44)},
    ]

    def _paint(self, surf, rng, pal, rng2=None):
        stone, roof, wood = pal['stone'], pal['roof'], pal['wood']
        gold = (212, 175, 55)
        sd = self.darken(stone, 0.72)
        # --- 塔楼方顶（俯视同心方 = 尖顶）---
        pygame.draw.rect(surf, sd, (24, 4, 28, 28), border_radius=2)      # 塔檐
        pygame.draw.rect(surf, roof, (27, 7, 22, 22))                     # 坡面
        pygame.draw.rect(surf, self.lighten(roof, 1.1), (31, 11, 14, 14))
        pygame.draw.rect(surf, self.lighten(roof, 1.22), (35, 15, 6, 6))
        pygame.draw.line(surf, gold, (38, 23), (38, 31), 2)               # 平贴金十字
        pygame.draw.line(surf, gold, (34, 26), (42, 26), 2)
        # --- 侧廊（单坡窄顶）---
        for ax in (13, 56):
            pygame.draw.rect(surf, self.darken(roof, 0.66), (ax, 36, 7, 40))
        pygame.draw.line(surf, self.darken(roof, 0.5), (13, 36), (13, 76), 1)
        pygame.draw.line(surf, self.darken(roof, 0.5), (63, 36), (63, 76), 1)
        # --- 中殿（双坡顶，屋脊竖向）---
        pygame.draw.rect(surf, roof, (20, 28, 18, 50))                    # 西坡
        pygame.draw.rect(surf, self.darken(roof, 0.82), (38, 28, 18, 50))  # 东坡
        pygame.draw.line(surf, self.lighten(roof, 1.18), (37, 28), (37, 78), 2)  # 屋脊
        pygame.draw.line(surf, sd, (20, 28), (20, 78), 1)
        pygame.draw.line(surf, sd, (56, 28), (56, 78), 1)
        # 东西坡天窗
        for wy in (36, 52, 66):
            pygame.draw.rect(surf, self.lighten(roof, 1.25), (26, wy, 6, 5))
            pygame.draw.rect(surf, self.darken(roof, 0.7), (44, wy + 2, 6, 5))
        # --- 翼殿（横屋脊，盖在中殿上成十字）---
        pygame.draw.rect(surf, roof, (6, 44, 64, 9))                      # 北坡
        pygame.draw.rect(surf, self.darken(roof, 0.85), (6, 53, 64, 9))   # 南坡
        pygame.draw.line(surf, self.lighten(roof, 1.18), (6, 52), (70, 52), 2)
        pygame.draw.line(surf, sd, (6, 44), (70, 44), 1)
        pygame.draw.line(surf, sd, (6, 62), (70, 62), 1)
        # --- 南面裙墙（底部少量墙体挤出：木门+窗）---
        pygame.draw.rect(surf, self.darken(stone, 0.9), (22, 78, 32, 10))
        pygame.draw.rect(surf, sd, (22, 78, 32, 10), 1)
        pygame.draw.rect(surf, wood, (34, 80, 8, 7))                      # 木门
        pygame.draw.rect(surf, (46, 56, 72), (26, 81, 4, 5))              # 窗
        pygame.draw.rect(surf, (46, 56, 72), (46, 81, 4, 5))
        self._speckle(surf, rng, pygame.Rect(22, 78, 32, 10), self.darken(stone, 0.9))


class HalfTimberGenerator(_EuroGenBase):
    """欧式半木桁架屋（俯视微倾）：双坡顶两片+屋脊+老虎窗+烟囱+南墙木桁架挤出"""
    SIZE = (64, 64)
    PALETTES = [
        {'wall': (242, 234, 216), 'roof': (158, 76, 54), 'timber': (88, 58, 38)},
        {'wall': (236, 226, 204), 'roof': (140, 66, 50), 'timber': (80, 52, 34)},
        {'wall': (246, 238, 222), 'roof': (168, 86, 58), 'timber': (94, 62, 40)},
    ]

    def _paint(self, surf, rng, pal, rng2=None):
        wall, roof, timber = pal['wall'], pal['roof'], pal['timber']
        # --- 左侧披屋（低矮单坡顶）---
        pygame.draw.rect(surf, self.darken(roof, 0.7), (2, 22, 9, 24))
        pygame.draw.line(surf, self.darken(roof, 0.5), (2, 22), (2, 46), 1)
        # --- 主屋双坡顶（屋脊横向，俯视两片坡面）---
        pygame.draw.rect(surf, roof, (10, 8, 44, 18))                     # 北坡
        pygame.draw.rect(surf, self.darken(roof, 0.8), (10, 26, 44, 20))  # 南坡
        pygame.draw.line(surf, self.lighten(roof, 1.18), (10, 25), (54, 25), 2)  # 屋脊
        pygame.draw.rect(surf, self.darken(roof, 0.55), (9, 7, 46, 2))    # 檐口压边
        pygame.draw.rect(surf, self.darken(roof, 0.55), (9, 45, 46, 2))
        pygame.draw.line(surf, self.darken(roof, 0.55), (9, 7), (9, 47), 1)
        pygame.draw.line(surf, self.darken(roof, 0.55), (55, 7), (55, 47), 1)
        # 坡面瓦垄
        for wx in range(16, 52, 7):
            pygame.draw.line(surf, self.darken(roof, 0.9), (wx, 9), (wx, 24), 1)
            pygame.draw.line(surf, self.darken(roof, 0.88), (wx, 27), (wx, 44), 1)
        # 烟囱（北坡上）
        pygame.draw.rect(surf, (122, 117, 110), (42, 12, 9, 9))
        pygame.draw.rect(surf, (40, 36, 34), (45, 15, 3, 3))
        # 老虎窗×2（南坡上）
        for dx in (16, 30):
            pygame.draw.rect(surf, wall, (dx, 30, 8, 7))
            pygame.draw.polygon(surf, self.darken(roof, 0.9), [(dx - 1, 30), (dx + 9, 30), (dx + 4, 26)])
            pygame.draw.rect(surf, (48, 58, 72), (dx + 2, 32, 4, 3))
        # --- 南墙挤出（米白墙+木桁架+窗/门）---
        pygame.draw.rect(surf, wall, (10, 47, 44, 11))
        for bx in (13, 25, 37, 49):
            pygame.draw.rect(surf, timber, (bx, 47, 2, 11))
        pygame.draw.rect(surf, timber, (10, 47, 44, 2))
        pygame.draw.rect(surf, timber, (10, 56, 44, 2))
        pygame.draw.rect(surf, timber, (28, 49, 8, 9))                    # 木门
        pygame.draw.rect(surf, (48, 58, 72), (16, 50, 6, 5))              # 窗
        pygame.draw.line(surf, timber, (16, 52), (22, 52), 1)
        self._speckle(surf, rng, pygame.Rect(10, 47, 44, 11), wall)


class ClockTowerGenerator(_EuroGenBase):
    """欧式钟楼（俯视微倾）：石板格方顶+铜绿八角小顶+避雷针+南立面时钟/拱窗/木门+侧翼附楼顶"""
    SIZE = (56, 88)
    PALETTES = [
        {'stone': (178, 172, 164), 'spire': (74, 112, 96), 'gold': (190, 160, 60)},
        {'stone': (190, 184, 174), 'spire': (82, 122, 104), 'gold': (200, 170, 70)},
        {'stone': (168, 162, 156), 'spire': (66, 100, 88), 'gold': (182, 152, 58)},
    ]

    def _paint(self, surf, rng, pal, rng2=None):
        stone, spire, gold = pal['stone'], pal['spire'], pal['gold']
        sd = self.darken(stone, 0.72)

        def oct_pts(cx, cy, r):
            return [(cx + int(r * math.cos(math.radians(a))),
                     cy + int(r * math.sin(math.radians(a))))
                    for a in range(22, 360 + 22, 45)]

        # --- 塔顶：石板格方顶（俯视）---
        pygame.draw.rect(surf, sd, (12, 8, 32, 32), border_radius=2)      # 檐口
        pygame.draw.rect(surf, self.darken(stone, 0.84), (15, 11, 26, 26))
        for gy in range(15, 33, 5):
            pygame.draw.line(surf, self.darken(stone, 0.7), (16, gy), (40, gy), 1)
        for gx in range(19, 41, 5):
            pygame.draw.line(surf, self.darken(stone, 0.7), (gx, 12), (gx, 36), 1)
        # 铜绿八角小顶（俯视八边形嵌套）+ 避雷针
        pygame.draw.polygon(surf, spire, oct_pts(28, 24, 11))
        pygame.draw.polygon(surf, self.darken(spire, 0.8), oct_pts(28, 24, 11), 1)
        pygame.draw.polygon(surf, self.lighten(spire, 1.15), oct_pts(28, 24, 6))
        pygame.draw.circle(surf, gold, (28, 24), 2)                       # 顶饰
        pygame.draw.line(surf, (120, 124, 130), (28, 24), (28, 15), 1)    # 避雷针
        pygame.draw.circle(surf, (150, 154, 160), (28, 15), 1)
        # --- 塔身南立面（向下挤出：时钟+拱窗+木门）---
        pygame.draw.rect(surf, stone, (14, 40, 28, 28))
        pygame.draw.rect(surf, sd, (14, 40, 28, 28), 1)
        for yy in range(46, 66, 6):
            pygame.draw.line(surf, self.darken(stone, 0.9), (15, yy), (41, yy), 1)
        # 时钟面（指针角度来自 variant 种子）
        pygame.draw.circle(surf, gold, (28, 50), 6)
        pygame.draw.circle(surf, (242, 240, 232), (28, 50), 4)
        ha, ma = rng.randrange(360), rng.randrange(360)
        pygame.draw.line(surf, (40, 40, 42), (28, 50),
                         (28 + int(2 * math.cos(math.radians(ha))), 50 + int(2 * math.sin(math.radians(ha)))), 1)
        pygame.draw.line(surf, (40, 40, 42), (28, 50),
                         (28 + int(3 * math.cos(math.radians(ma))), 50 + int(3 * math.sin(math.radians(ma)))), 1)
        # 拱窗×2
        for wx in (18, 33):
            pygame.draw.rect(surf, (44, 42, 40), (wx, 58, 5, 6))
            pygame.draw.circle(surf, (44, 42, 40), (wx + 2, 58), 2,
                               draw_top_left=True, draw_top_right=True)
        # 木门
        pygame.draw.rect(surf, self.darken((96, 64, 40), 0.9), (23, 63, 10, 5))
        pygame.draw.circle(surf, self.darken((96, 64, 40), 0.9), (28, 63), 5,
                           draw_top_left=True, draw_top_right=True)
        # --- 侧翼附楼顶（双坡，屋脊竖向）---
        for ax, rx in ((2, 8), (42, 48)):
            pygame.draw.rect(surf, self.darken(stone, 0.88), (ax, 50, 12, 24))
            pygame.draw.line(surf, sd, (rx, 50), (rx, 74), 2)             # 屋脊
            pygame.draw.line(surf, sd, (ax, 50), (ax, 74), 1)
            pygame.draw.line(surf, sd, (ax + 11, 50), (ax + 11, 74), 1)
            pygame.draw.rect(surf, (48, 58, 72), (ax + 4, 60, 4, 5))      # 天窗
        self._speckle(surf, rng, pygame.Rect(14, 40, 28, 28), stone)


class WindmillGenerator(_EuroGenBase):
    """欧式风车（俯视微倾）：圆塔+红陶圆锥顶俯视同心圆+四向帆翼十字展开（角度随 variant）"""
    SIZE = (70, 84)
    PALETTES = [
        {'stone': (198, 190, 176), 'roof': (146, 70, 52), 'wood': (104, 72, 46)},
        {'stone': (188, 180, 166), 'roof': (134, 64, 48), 'wood': (96, 66, 42)},
        {'stone': (206, 198, 184), 'roof': (156, 78, 56), 'wood': (112, 78, 50)},
    ]

    def _paint(self, surf, rng, pal, rng2=None):
        stone, roof, wood = pal['stone'], pal['roof'], pal['wood']
        sd = self.darken(stone, 0.72)
        hub = (35, 40)
        # --- 四叶帆翼（十字展开，先画被塔顶压住中心）---
        base = math.radians(rng.randrange(0, 90))
        for i in range(4):
            ang = base + math.radians(90 * i)
            dx, dy = math.cos(ang), math.sin(ang)
            px, py = -dy, dx
            L, hw = 30, 6
            tip = (hub[0] + int(dx * L), hub[1] + int(dy * L))
            sail = [tip[0] + int(px * hw), tip[1] + int(py * hw)], \
                   [tip[0] - int(px * hw), tip[1] - int(py * hw)], \
                   [hub[0] - int(px * 3), hub[1] - int(py * 3)], \
                   [hub[0] + int(px * 3), hub[1] + int(py * 3)]
            pygame.draw.polygon(surf, (238, 232, 214), sail)
            pygame.draw.lines(surf, wood, False, sail, 1)
            pygame.draw.line(surf, wood, hub, tip, 1)                 # 帆臂
            for t in (0.4, 0.65, 0.9):                                # 帆格横撑
                mx, my = hub[0] + int(dx * L * t), hub[1] + int(dy * L * t)
                pygame.draw.line(surf, wood,
                                 (mx + int(px * hw * t), my + int(py * hw * t)),
                                 (mx - int(px * hw * t), my - int(py * hw * t)), 1)
        # --- 圆塔（俯视圆环，中心上移留出下缘塔身=倾斜感）---
        pygame.draw.circle(surf, sd, (35, 46), 24)                    # 塔檐
        pygame.draw.circle(surf, stone, (35, 44), 22)                 # 塔身环
        pygame.draw.circle(surf, self.darken(stone, 0.9), (35, 44), 22, 1)
        for a in range(210, 331, 24):                                 # 下缘石缝放射线
            ar = math.radians(a)
            pygame.draw.line(surf, self.darken(stone, 0.88),
                             (35 + int(17 * math.cos(ar)), 44 + int(17 * math.sin(ar))),
                             (35 + int(21 * math.cos(ar)), 44 + int(21 * math.sin(ar))), 1)
        # --- 红陶圆锥顶（俯视同心圆）---
        pygame.draw.circle(surf, roof, (35, 40), 18)
        pygame.draw.circle(surf, self.darken(roof, 0.8), (35, 40), 18, 1)
        pygame.draw.circle(surf, self.darken(roof, 0.85), (35, 40), 12)
        pygame.draw.circle(surf, self.darken(roof, 0.85), (35, 40), 12, 1)
        pygame.draw.circle(surf, self.lighten(roof, 1.15), (35, 40), 6)
        # 顶毂（帆翼轴心）
        pygame.draw.circle(surf, wood, hub, 4)
        pygame.draw.circle(surf, self.darken(wood, 0.7), hub, 4, 1)
        # --- 门廊（南缘小体量挤出）---
        pygame.draw.rect(surf, self.darken(stone, 0.9), (29, 64, 12, 10))
        pygame.draw.rect(surf, sd, (29, 64, 12, 10), 1)
        pygame.draw.rect(surf, wood, (32, 66, 6, 7))
        pygame.draw.circle(surf, wood, (35, 66), 3, draw_top_left=True, draw_top_right=True)
        self._speckle(surf, rng, pygame.Rect(29, 64, 12, 10), self.darken(stone, 0.9))


class EuropeanChurch(CivilianHouse):
    """欧式教堂（中立装饰建筑：可驻军/可摧毁，外观为石造教堂）"""
    _GEN = ChurchGenerator

    def __init__(self, game, pos, variant_id=None):
        super().__init__(game, pos, variant_id)
        self.gen = self._GEN()
        self.image = self.gen.generate(self.variant_id)


class HalfTimberHouse(CivilianHouse):
    """欧式半木桁架屋（中立装饰建筑，可驻军/可摧毁）"""
    _GEN = HalfTimberGenerator

    def __init__(self, game, pos, variant_id=None):
        super().__init__(game, pos, variant_id)
        self.gen = self._GEN()
        self.image = self.gen.generate(self.variant_id)


class ClockTower(CivilianHouse):
    """欧式钟楼（中立装饰建筑，可驻军/可摧毁）"""
    _GEN = ClockTowerGenerator

    def __init__(self, game, pos, variant_id=None):
        super().__init__(game, pos, variant_id)
        self.gen = self._GEN()
        self.image = self.gen.generate(self.variant_id)


class Windmill(CivilianHouse):
    """欧式风车（中立装饰建筑，可驻军/可摧毁）"""
    _GEN = WindmillGenerator

    def __init__(self, game, pos, variant_id=None):
        super().__init__(game, pos, variant_id)
        self.gen = self._GEN()
        self.image = self.gen.generate(self.variant_id)


def scale_img(image, zoom):
    # 走共享缓存（见 core/utils.cached_scale_img）
    return cached_scale_img(image, zoom, smooth=False)
class CommStation(Entity):
    def __init__(self, game, pos):
        super().__init__(game, pos, "neutral")
        self.b_type = "comm_station" 
        self.hp = 5000
        self.max_hp = 5000
        
        self.radius = 150
        self.rect = pygame.Rect(pos.x - 150, pos.y - 250, 300, 500)
        
        self.capture_progress = 0
        self.capturing_team = None
        self.max_capture = 300 
        self.linked_battleship = None 

        self.base_image = self.generate_base_image()
    def update(self):
        # 1. 占领逻辑 (Host Only)
        if not self.game.is_online or self.game.my_role == "HOST":
            capturer = None
            min_dist = 400
            for u in self.game.all_units:
                if u.alive and not u.is_air:
                    dist = self.pos.distance_to(u.pos)
                    if dist < min_dist:
                        capturer = u
                        min_dist = dist   # 最近者占领（防列表顺序坑：守点敌军排前会永久挡住玩家的占领）
            
            if capturer:
                if capturer.team != self.team:
                    if self.capturing_team != capturer.team:
                        self.capturing_team = capturer.team
                        self.capture_progress = 0
                    
                    self.capture_progress += 1
                    
                    if self.capture_progress >= self.max_capture:
                        old_team = self.team
                        self.team = capturer.team
                        self.capture_progress = 0

                        self.on_team_changed(old_team, self.team)
                        
                        self.game.particles.add(FloatingText(self.pos, "CAPTURED!", CYAN))
                else:
                    self.capture_progress = max(0, self.capture_progress - 1)
            else:
                self.capture_progress = max(0, self.capture_progress - 0.5)

    def on_team_changed(self, old_team, new_team):
        if self.linked_battleship and self.linked_battleship.alive:
            self.linked_battleship.team = "neutral"
            self.linked_battleship.target_entity = None
            self.linked_battleship.target_pos = None
            self.game.show_alert("BATTLESHIP CONTROL LOST!")

    def die(self):
        if self.linked_battleship and self.linked_battleship.alive:
            self.linked_battleship.team = "neutral"
            self.linked_battleship.ai_mode = "GUARD"
        super().die()
    def generate_base_image(self):
        w, h = 300, 500
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        
        # --- 调色板 ---
        C_WATER     = (30, 50, 70)     # 内部水域
        C_CONCRETE  = (100, 105, 110)  # 地面主色
        C_SEAM      = (80, 85, 90)     # 地面缝隙
        C_WALL      = (70, 75, 80)     # 建筑墙面
        C_ROOF_L    = (90, 95, 100)    # 亮屋顶
        C_ROOF_D    = (50, 55, 60)     # 暗屋顶/设备
        C_CAUTION   = (200, 180, 50)   # 警示黄
        C_RUST      = (120, 80, 60)    # 锈迹/集装箱
        C_BLUE_BOX  = (60, 80, 120)    # 蓝色集装箱
        
        # 1. 码头整体轮廓 (U型结构)
        # 左右两边的栈桥变窄，显得更长更精细
        pier_width = 50
        
        # 岸基 (Top 150px)
        pygame.draw.rect(surf, C_CONCRETE, (10, 10, 280, 150), border_radius=5)
        # 左栈桥
        pygame.draw.rect(surf, C_CONCRETE, (30, 150, pier_width, 340))
        # 右栈桥
        pygame.draw.rect(surf, C_CONCRETE, (220, 150, pier_width, 340))
        # 底部连接梁 (水下结构示意)
        pygame.draw.rect(surf, (50, 60, 70), (30, 450, 240, 20)) 

        # 2. 地面纹理 (Concrete Tiles)
        # 画网格线模拟地砖
        for x in range(10, 290, 20):
            pygame.draw.line(surf, C_SEAM, (x, 10), (x, 160), 1)
        for y in range(10, 160, 20):
            pygame.draw.line(surf, C_SEAM, (10, y), (290, y), 1)
        # 栈桥上的横纹
        for y in range(160, 490, 30):
            pygame.draw.line(surf, C_SEAM, (30, y), (30+pier_width, y), 1)
            pygame.draw.line(surf, C_SEAM, (220, y), (220+pier_width, y), 1)

        # 3. 泊位细节 (Inner Edges)
        # 黄色警示线
        pygame.draw.line(surf, C_CAUTION, (80, 160), (80, 490), 2) # 左内沿
        pygame.draw.line(surf, C_CAUTION, (220, 160), (220, 490), 2) # 右内沿
        
        # 防撞轮胎阵列 (密集的小黑圈)
        for y in range(170, 480, 15):
            pygame.draw.ellipse(surf, (10,10,10), (80-3, y, 6, 10))
            pygame.draw.ellipse(surf, (10,10,10), (220-3, y, 6, 10))

        # 4. 建筑群 (Building Complex) - 位于岸基
        
        # A. 主指挥所 (左上) - 不规则多边形
        b1_rect = pygame.Rect(20, 30, 100, 80)
        pygame.draw.rect(surf, C_WALL, b1_rect)
        pygame.draw.rect(surf, C_ROOF_L, b1_rect.inflate(-10, -10))
        # 屋顶细节: 两个空调风扇
        pygame.draw.circle(surf, C_ROOF_D, (40, 50), 10)
        pygame.draw.circle(surf, C_ROOF_D, (40, 80), 10)
        pygame.draw.line(surf, (30,30,30), (30, 50), (50, 50), 2) # 风扇叶示意
        
        # B. 雷达基座 (右上) - 圆形堡垒
        radar_base_center = (220, 70)
        pygame.draw.circle(surf, C_WALL, radar_base_center, 40)
        pygame.draw.circle(surf, C_ROOF_D, radar_base_center, 30)
        # 管道连接主楼和雷达座
        pygame.draw.line(surf, (150, 150, 160), (120, 70), (190, 70), 6) # 粗管
        pygame.draw.line(surf, (150, 150, 160), (120, 60), (190, 60), 3) # 细管

        # C. 发电机房 (中下)
        gen_rect = pygame.Rect(130, 100, 60, 40)
        pygame.draw.rect(surf, C_WALL, gen_rect)
        # 散热格栅
        for i in range(5):
            pygame.draw.line(surf, (20,20,20), (140 + i*10, 110), (140 + i*10, 130), 2)

        # 5. 工业杂物 (Clutter)
        
        # 龙门吊轨道 (Gantry Rails) - 铺设在左侧栈桥
        pygame.draw.line(surf, (40,40,40), (35, 160), (35, 480), 2)
        pygame.draw.line(surf, (40,40,40), (75, 160), (75, 480), 2)
        
        # 集装箱堆场 (右侧栈桥)
        # 随机堆放一些彩色小方块
        containers = [
            (230, 200, C_RUST), (230, 230, C_BLUE_BOX), 
            (245, 210, C_BLUE_BOX), (230, 300, C_RUST),
            (230, 350, C_RUST), (245, 350, C_BLUE_BOX)
        ]
        for cx, cy, col in containers:
            # 画一个带阴影的集装箱
            pygame.draw.rect(surf, (0,0,0,100), (cx+2, cy+2, 12, 25)) # 阴影
            pygame.draw.rect(surf, col, (cx, cy, 12, 25)) # 箱体
            pygame.draw.rect(surf, (200,200,200), (cx, cy, 12, 25), 1) # 边框

        h_center = (55, 420)
        pygame.draw.circle(surf, C_CONCRETE, h_center, 20)
        pygame.draw.circle(surf, C_CAUTION, h_center, 18, 2)
        # "H"
        pygame.draw.rect(surf, C_CAUTION, (48, 410, 4, 20))
        pygame.draw.rect(surf, C_CAUTION, (58, 410, 4, 20))
        pygame.draw.rect(surf, C_CAUTION, (48, 418, 14, 4))

        return surf

    def generate_image(self):
        """静态外观基准图（即 __init__ 生成的 base_image，300x500）；PNG 缓存由 sprite_cache 自动导出/加载"""
        return self.base_image

    def _image_anchor(self):
        return 150, 250

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 800 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return            
        # 1. 底座（PNG 命中时为图片 blit，未命中回退原 center blit）
        if getattr(self, 'image', None) is None:
            self.image = self.base_image
        if not self._blit_cached_image(surface, int(screen_pos[0]), int(screen_pos[1]), zoom):
            scaled_base = scale_img(self.base_image, zoom)
            base_rect = scaled_base.get_rect(center=screen_pos)
            surface.blit(scaled_base, base_rect)

        # 2. 动态：旋转雷达（保留程序绘制）
        radar_cx = screen_pos[0] + scale(70, zoom)
        radar_cy = screen_pos[1] - scale(180, zoom)

        angle = (pygame.time.get_ticks() * 0.1) % 360

        # 画一个旋转的十字或一字型天线
        r_len = scale(35, zoom)
        r_width = scale(6, zoom)

        # 创建雷达Surface
        r_surf = pygame.Surface((r_len * 2, r_len * 2), pygame.SRCALPHA)
        # 天线臂
        pygame.draw.rect(r_surf, (220, 220, 230), (0, r_len - r_width//2, r_len*2, r_width))
        # 天线锅 (两端的弧形)
        pygame.draw.arc(r_surf, (100, 100, 100), (0, r_len - 10, 20, 20), 1.5, 4.7, 3)
        pygame.draw.arc(r_surf, (100, 100, 100), (r_len*2 - 20, r_len - 10, 20, 20), 4.7, 1.5, 3)

        rot_radar = cached_rotate(r_surf, angle)
        surface.blit(rot_radar, rot_radar.get_rect(center=(radar_cx, radar_cy)))

        # 2.2 龙门吊 (Gantry Crane) - 在轨道上往复移动
        crane_y_offset = 160 + abs(math.sin(pygame.time.get_ticks() * 0.0005)) * 250
        crane_sx = screen_pos[0] - scale(95, zoom)
        crane_sy = screen_pos[1] + scale(crane_y_offset - 250, zoom)
        c_w = scale(40, zoom)
        c_h = scale(20, zoom)
        pygame.draw.rect(surface, (220, 180, 20), (crane_sx - c_w//2, crane_sy - c_h//2, c_w, c_h))
        pygame.draw.rect(surface, (0,0,0), (crane_sx - c_w//2, crane_sy - c_h//2, c_w, c_h), 1)

        # 3. 阵营标识 (Team Flag) - 队伍可被占领/网络同步改变，保留动态
        team_color = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        flag_x = screen_pos[0] - scale(80, zoom)
        flag_y = screen_pos[1] - scale(180, zoom)
        pygame.draw.line(surface, (20,20,20), (flag_x, flag_y), (flag_x, flag_y - scale(30,zoom)), 2)
        pygame.draw.rect(surface, team_color, (flag_x, flag_y - scale(30,zoom), scale(20,zoom), scale(12,zoom)))

        # 4. 占领条 (画在最上面)
        if self.capture_progress > 0:
            bar_w = scale(120, zoom)
            bar_h = scale(8, zoom)
            pct = self.capture_progress / self.max_capture
            c_color = TEAM_COLORS.get(self.capturing_team, WHITE)

            bx = screen_pos[0] - bar_w // 2
            by = screen_pos[1] - scale(260, zoom)

            pygame.draw.rect(surface, BLACK, (bx, by, bar_w, bar_h))
            pygame.draw.rect(surface, c_color, (bx, by, bar_w*pct, bar_h))
            pygame.draw.rect(surface, WHITE, (bx, by, bar_w, bar_h), 1)


        self.draw_health_and_marker(surface, offset, zoom)
class Bridge(Building):
    # PNG 缓存按 (方向_长度) 变体键分开存取（横竖桥与不同长度外观不同）
    _variant_attr = 'sprite_key'
    # 基准图画布四周外扩：桥墩帽长边外凸 3px、水面投影右下偏移(10,12)，
    # 精确画布会把外凸部分裁掉（桥墩"消失"的主因之一）
    IMG_PAD = 16

    def __init__(self, game, pos, orientation="horizontal", length=None):
        # 桥梁通常算作中立，但不可被占领，只会被破坏
        super().__init__(game, pos, "neutral", "bridge")
        self.hp = 1500
        self.max_hp = 1500
        self.orientation = orientation

        # 尺寸：length = 沿桥向跨度（编辑器可调，None = 旧默认 600/300）；
        # 碰撞箱 rect 随 width/height 同步缩放
        if length is None:
            length = 600 if orientation == "horizontal" else 300
        self.length = int(length)
        if orientation == "horizontal":
            self.width, self.height = self.length, 300
        else:
            self.width, self.height = 200, self.length
        self.sprite_key = "%s_%d" % (orientation, self.length)

        self.radius = max(self.width, self.height) // 2
        self.rect = pygame.Rect(pos.x - self.width//2, pos.y - self.height//2, self.width, self.height)
        
        # 状态
        self.is_broken = False
        self.regen_timer = 0
        self.regen_time_total = 1800 # 30秒 (60帧 * 30)
        # 静态外观基准图：__init__ 里就生成一份，sprite_cache 才能提取导出 PNG
        #（按 sprite_key 变体存 image_v<方向_长度>.png，之后同规格实例注入同一张）
        self.image = self.generate_image()

    def take_damage(self, amount, damage_type="normal",breakshellvalue=0):
        if self.is_broken: return
        self.hp -= amount
        if self.hp <= 0:
            self.break_bridge()

    def start_collapse(self):
        # 兼容 Building 类的接口
        self.break_bridge()

    def break_bridge(self):
        if self.is_broken: return
        self.is_broken = True
        self.hp = 0
        self.regen_timer = self.regen_time_total
        self.game.show_alert("BRIDGE DESTROYED!")
        
        # 特效
        if not self.game.is_online or self.game.my_role == "HOST":
            if hasattr(self.game, 'net_events'):
                self.game.net_events.append({
                    "type": "EXPLOSION", "x": int(self.pos.x), "y": int(self.pos.y), "dt": "rocket"
                })

    def update(self):
        if self.is_broken:
            self.regen_timer -= 1
            if self.regen_timer <= 0:
                self.restore_bridge()
    
    def restore_bridge(self):
        self.is_broken = False
        self.hp = self.max_hp
        self.game.particles.add(FloatingText(self.pos, "BRIDGE REPAIRED", CYAN))

    def _paint_deck(self, surface, zone, zoom):
        """桥面铺装：与道路同款沥青纹理 + 路缘压边 + 中央黄虚线（视觉上与 roads 衔接）。
        clip 到 zone 内铺贴，可同时用于完好桥面与断桥残段"""
        from game.roads import get_road_tile
        tile = get_road_tile()
        ts = max(2, scale(tile.get_width(), zoom))
        pygame.draw.rect(surface, (56, 56, 58), zone)           # 沥青底色兜底
        clip = surface.get_clip()
        surface.set_clip(zone)
        for yy in range(zone.top - ts, zone.bottom, ts):
            for xx in range(zone.left - ts, zone.right, ts):
                surface.blit(tile, (xx, yy))
        # 路缘压边（与道路一致）
        pygame.draw.rect(surface, (40, 40, 42), zone, max(1, scale(3, zoom)))
        # 中央黄虚线（行车方向：24px 段 / 48px 周期，与道路一致）
        dash = max(4, scale(24, zoom))
        gap = max(6, scale(24, zoom))
        lw = max(1, scale(4, zoom))
        lc = (198, 168, 44)
        if zone.w >= zone.h:
            y0 = zone.centery
            x = zone.left
            while x < zone.right:
                pygame.draw.rect(surface, lc, (x, y0 - lw // 2, dash, lw))
                x += dash + gap
        else:
            x0 = zone.centerx
            y = zone.top
            while y < zone.bottom:
                pygame.draw.rect(surface, lc, (x0 - lw // 2, y, lw, dash))
                y += dash + gap
        surface.set_clip(clip)

    def _draw_static(self, surface, cx, cy, zoom):
        """静态外观：混凝土桥体基座 + 沥青桥面（道路同款纹理/黄虚线，与 roads 衔接）
        + 钢护栏 + 桥台警示条 + 桥墩帽 + 水面投影。
        断桥状态与修复倒计时为动态，见 draw()"""
        w = scale(self.width, zoom)
        h = scale(self.height, zoom)
        rect = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
        horiz = self.orientation == "horizontal"

        # ---- 水面投影（右下偏移半透明，先铺在最底层）----
        sh = pygame.Surface((max(1, rect.w), max(1, rect.h)), pygame.SRCALPHA)
        sh.fill((15, 28, 45, 90))
        surface.blit(sh, (rect.x + scale(10, zoom), rect.y + scale(12, zoom)))

        # ---- 混凝土桥体基座 + 板缝 ----
        pygame.draw.rect(surface, (112, 110, 116), rect)
        pygame.draw.rect(surface, (86, 84, 92), rect, max(1, scale(3, zoom)))
        joint = scale(96, zoom)
        if joint >= 6:
            jc = (98, 96, 104)
            if horiz:
                for x in range(rect.x + joint, rect.right - 2, joint):
                    pygame.draw.line(surface, jc, (x, rect.y + 3), (x, rect.bottom - 3), 1)
            else:
                for y in range(rect.y + joint, rect.bottom - 2, joint):
                    pygame.draw.line(surface, jc, (rect.x + 3, y), (rect.right - 3, y), 1)

        # ---- 沥青桥面（跨全桥，宽 128 世界px ≈ 双车道+路肩）----
        dw = scale(128, zoom)
        if horiz:
            deck = pygame.Rect(rect.x, rect.centery - dw // 2, rect.w, dw)
        else:
            deck = pygame.Rect(rect.centerx - dw // 2, rect.y, dw, rect.h)
        self._paint_deck(surface, deck, zoom)

        # ---- 钢护栏（桥面两侧：亮轨 + 暗托 + 立柱）----
        rail_c, rail_d = (178, 182, 190), (96, 98, 106)
        post_gap = max(8, scale(48, zoom))
        if horiz:
            for ry in (deck.top + 2, deck.bottom - 5):
                pygame.draw.rect(surface, rail_d, (deck.x, ry + 3, deck.w, 2))
                pygame.draw.rect(surface, rail_c, (deck.x, ry, deck.w, 3))
                for x in range(deck.x + 4, deck.right - 3, post_gap):
                    pygame.draw.rect(surface, rail_c, (x, ry - 1, 2, 5))
        else:
            for rx in (deck.left + 2, deck.right - 5):
                pygame.draw.rect(surface, rail_d, (rx + 3, deck.y, 2, deck.h))
                pygame.draw.rect(surface, rail_c, (rx, deck.y, 3, deck.h))
                for y in range(deck.y + 4, deck.bottom - 3, post_gap):
                    pygame.draw.rect(surface, rail_c, (rx - 1, y, 5, 2))

        # ---- 桥台警示条（两端上桥处，斜纹黄黑）----
        band_w = max(3, scale(7, zoom))
        step = max(4, scale(10, zoom))
        if horiz:
            bands = (pygame.Rect(rect.x, deck.top, band_w, deck.h),
                     pygame.Rect(rect.right - band_w, deck.top, band_w, deck.h))
        else:
            bands = (pygame.Rect(deck.left, rect.y, deck.w, band_w),
                     pygame.Rect(deck.left, rect.bottom - band_w, deck.w, band_w))
        for b in bands:
            pygame.draw.rect(surface, (52, 50, 46), b)
            clip = surface.get_clip()
            surface.set_clip(b)
            if b.w >= b.h:
                yy = b.top - step
                while yy < b.bottom:
                    pygame.draw.rect(surface, (176, 150, 56), (b.x, yy, b.w, step // 2 + 1))
                    yy += step
            else:
                xx = b.left - step
                while xx < b.right:
                    pygame.draw.rect(surface, (176, 150, 56), (xx, b.y, step // 2 + 1, b.h))
                    xx += step
            surface.set_clip(clip)

        # ---- 桥墩帽（基座长边两侧外凸的混凝土墩头）----
        pier_l, pier_w2 = scale(18, zoom), scale(10, zoom)
        for t in (1 / 6, 1 / 2, 5 / 6):
            if horiz:
                px = rect.x + int(rect.w * t) - pier_l // 2
                for py in (rect.top - pier_w2 // 2 + 2, rect.bottom - pier_w2 // 2 - 2):
                    pygame.draw.rect(surface, (92, 90, 96), (px, py, pier_l, pier_w2), border_radius=2)
                    pygame.draw.rect(surface, (64, 62, 70), (px, py, pier_l, pier_w2), 1, border_radius=2)
            else:
                py = rect.y + int(rect.h * t) - pier_l // 2
                for px in (rect.left - pier_w2 // 2 + 2, rect.right - pier_w2 // 2 - 2):
                    pygame.draw.rect(surface, (92, 90, 96), (px, py, pier_w2, pier_l), border_radius=2)
                    pygame.draw.rect(surface, (64, 62, 70), (px, py, pier_w2, pier_l), 1, border_radius=2)

    def generate_image(self):
        """静态外观基准图（zoom=1），画布 = 桥体尺寸 + 四周 IMG_PAD 外扩，
        桥体居中（外凸桥墩帽/水面投影不被画布边缘裁掉）；锚点 = 图中心（对称外扩）；
        PNG 缓存由 sprite_cache 自动导出/加载"""
        pad = self.IMG_PAD
        cw, ch = self.width + 2 * pad, self.height + 2 * pad
        surf = pygame.Surface((cw, ch), pygame.SRCALPHA)
        self._draw_static(surf, cw // 2, ch // 2, 1.0)
        return surf

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        w = scale(self.width, zoom)
        h = scale(self.height, zoom)

        rect = pygame.Rect(screen_pos[0]-w//2, screen_pos[1]-h//2, w, h)

        if self.is_broken:
            # 断桥：两岸残段（沥青桥面+护栏残端）+ 锯齿断口 + 钢筋 + 落水残骸
            # （缺口直接露出真实水面/地形——原整块深蓝"桥下水"矩形看起来像阴影，已删）
            dw = scale(128, zoom)
            stub = (w // 3) if self.orientation == "horizontal" else (h // 3)
            if self.orientation == "horizontal":
                stubs = (pygame.Rect(rect.x, rect.centery - dw // 2, stub, dw),
                         pygame.Rect(rect.right - stub, rect.centery - dw // 2, stub, dw))
                break_xs = (stubs[0].right, stubs[1].left)
            else:
                stubs = (pygame.Rect(rect.centerx - dw // 2, rect.y, dw, stub),
                         pygame.Rect(rect.centerx - dw // 2, rect.bottom - stub, dw, stub))
                break_xs = (stubs[0].bottom, stubs[1].top)
            for st in stubs:
                self._paint_deck(surface, st, zoom)
                # 护栏残端（沿残段长度）
                rail_c = (150, 154, 162)
                if st.w >= st.h:
                    pygame.draw.rect(surface, rail_c, (st.x, st.top + 2, st.w, 2))
                    pygame.draw.rect(surface, rail_c, (st.x, st.bottom - 4, st.w, 2))
                else:
                    pygame.draw.rect(surface, rail_c, (st.left + 2, st.y, 2, st.h))
                    pygame.draw.rect(surface, rail_c, (st.right - 4, st.y, 2, st.h))
            # 锯齿断口 + 外露钢筋（指向缺口）
            jag_c, rebar_c = (34, 34, 38), (128, 96, 74)
            if self.orientation == "horizontal":
                for bx, sign in ((break_xs[0], 1), (break_xs[1], -1)):
                    seg = max(6, dw // 4)
                    for i, yy in enumerate(range(stubs[0].top, stubs[0].bottom, seg)):
                        notch = scale(10, zoom) if (i % 2 == 0) else scale(4, zoom)
                        pygame.draw.rect(surface, jag_c, (bx - sign * notch // 2 if sign > 0 else bx - notch // 2,
                                                          yy, notch, seg))
                    for i in range(3):
                        ry = stubs[0].top + dw // 4 * (i + 1)
                        ln = scale(26, zoom)
                        pygame.draw.line(surface, rebar_c, (bx, ry), (bx + sign * ln, ry + (i - 1) * 4), 2)
            else:
                for by, sign in ((break_xs[0], 1), (break_xs[1], -1)):
                    seg = max(6, dw // 4)
                    for i, xx in enumerate(range(stubs[0].left, stubs[0].right, seg)):
                        notch = scale(10, zoom) if (i % 2 == 0) else scale(4, zoom)
                        pygame.draw.rect(surface, jag_c, (xx, by - notch // 2 if sign > 0 else by - sign * notch // 2,
                                                          seg, notch))
                    for i in range(3):
                        rx = stubs[0].left + dw // 4 * (i + 1)
                        ln = scale(26, zoom)
                        pygame.draw.line(surface, rebar_c, (rx, by), (rx + (i - 1) * 4, by + sign * ln), 2)
            # 落水残骸（确定性偏移，避免逐帧闪烁）
            debris = ((-0.22, -0.18, 16, 10), (-0.12, 0.20, 10, 8), (0.10, -0.22, 12, 9),
                      (0.18, 0.14, 15, 8), (0.02, 0.03, 9, 7))
            for fx, fy, fw, fh in debris:
                d = pygame.Rect(int(rect.centerx + rect.w * fx - fw / 2),
                                int(rect.centery + rect.h * fy - fh / 2),
                                scale(fw, zoom), scale(fh, zoom))
                pygame.draw.rect(surface, (92, 90, 94), d, border_radius=2)
                pygame.draw.rect(surface, (60, 58, 66), d, 1, border_radius=2)

            # 倒计时文本
            time_left = int(self.regen_timer / 60)
            txt = self.game.ui_font.render(f"REPAIR: {time_left}s", True, WHITE)
            surface.blit(txt, txt.get_rect(center=screen_pos))

        else:
            # 完好桥梁：静态外观（PNG 命中时为图片 blit，未命中现场绘制）
            # 横/竖与不同长度尺寸不同：注入 PNG 的逻辑尺寸不符时按本实例重新生成
            #（画布 = 桥体 + IMG_PAD 外扩；用 logical_size 比较——注入图会被降采样存储）
            img = getattr(self, 'image', None)
            canvas = (self.width + 2 * self.IMG_PAD, self.height + 2 * self.IMG_PAD)
            if img is None or logical_size(img) != canvas:
                self.image = self.generate_image()
            cx, cy = int(screen_pos[0]), int(screen_pos[1])
            if not self._blit_cached_image(surface, cx, cy, zoom):
                self._draw_static(surface, cx, cy, zoom)

            self.draw_health_and_marker(surface, offset, zoom, -h//2)
class CableSegment(Entity):
    def __init__(self, game, pos, delay):
        super().__init__(game, pos, "neutral")
        self.b_type = "cable"
        self.radius = 20
        self.rect = pygame.Rect(pos.x-20, pos.y-20, 40, 40)
        self.alive = True
        self.explode_delay = delay # 延迟多少帧爆炸
        self.exploding = False

    def trigger_destruction(self):
        self.exploding = True

    def update(self):
        if self.exploding:
            self.explode_delay -= 1
            if self.explode_delay <= 0:
                self.explode()

    def explode(self):
        self.alive = False
        # 爆炸特效
        self.game.net_events.append({
            "type": "EXPLOSION", 
            "x": int(self.pos.x), "y": int(self.pos.y), 
            "dt": "behemoth_bomb" # 巨大的爆炸
        })
        # 伤害
        p = Projectile(self.game, self.pos, None, "neutral", 500, 10000,"behemoth_bomb", is_aoe=True, aoe_radius=150)
        p.on_hit(None)

    def draw(self, surface, offset, zoom):
        if not self.alive: return
        
        # 计算屏幕坐标
        start = to_screen(self.prev_pos, offset, zoom)
        end = to_screen(self.pos, offset, zoom)
        
        # 绘制电缆
        pygame.draw.line(surface, (20, 20, 20), start, end, int(scale(10, zoom)))
        pygame.draw.line(surface, (100, 100, 100), start, end, int(scale(4, zoom)))
        
        # 绘制支架/节点
        pygame.draw.circle(surface, (80, 80, 80), end, int(scale(8, zoom)))

class BroadcastDish(Building):
    def __init__(self, game, pos):
        super().__init__(game, pos, "neutral", "broadcast_dish")
        self.hp = 200 # Boss 级血量
        self.max_hp = 200
        self.radius = 200 # 很大
        self.rect = pygame.Rect(pos.x-200, pos.y-200, 400, 400)
        
        self.cables = [] # 存储所有的 CableSegment
        
        # 生成电缆段 (逻辑实体)
        # 3根，每根长 3000，每隔 200 像素放一个爆炸点
        angles = [-90, 30, 150]
        for ang in angles:
            rad = math.radians(ang)
            dir_vec = vec(math.cos(rad), math.sin(rad))
            for i in range(1, 15): # 15段
                dist = 200 + i * 200
                seg_pos = self.pos + dir_vec * dist
                # 延迟：越远越晚炸，每段延迟 10 帧
                delay = i * 10
                seg = CableSegment(game, seg_pos, delay)
                self.cables.append(seg)
                # 注意：这里我们不把 seg 加到 game.all_buildings 里，
                # 而是由 Dish 自己管理更新，或者加进去但不画
                game.all_buildings.append(seg) # 加进去为了能被 update

    def update(self):
        # 只需要处理死亡
        if self.hp <= 0:
            self.start_destruction()
        for seg in self.cables:
            seg.update()
    def start_destruction(self):
        if not self.alive: return
        self.alive = False
        
        # 1. 触发电缆连锁爆炸
        for seg in self.cables:
            seg.trigger_destruction()
            
        # 2. 自身大爆炸
        self.game.net_events.append({
            "type": "EXPLOSION", 
            "x": int(self.pos.x), "y": int(self.pos.y), 
            "dt": "behemoth_bomb" 
        })
        
        # 3. 生成大坑 (DeathZone)
        # 这是一个持续存在的区域，进入即死
        hole = DeathZone(self.game, self.pos, 300)
        self.game.all_buildings.append(hole) # 作为一个无敌的中立建筑存在

    def _draw_static(self, surface, cx, cy, zoom):
        """静态外观：悬索连接点 / 三角舱体 / 核心接收器（generate_image 与无图回退共用）。
        警示灯与能量光效为动态，见 draw()"""
        r_cabin = scale(60, zoom)

        # 1. 悬索连接点 (Cables attachment)
        # 虽然具体的电缆由 CableSegment 画，但这里画出连接到舱体的部分
        angles = [-90, 30, 150]
        for ang in angles:
            rad = math.radians(ang)
            end_x = cx + math.cos(rad) * r_cabin
            end_y = cy + math.sin(rad) * r_cabin
            pygame.draw.line(surface, (50, 50, 50), (cx, cy), (end_x, end_y), int(scale(10, zoom)))
            pygame.draw.circle(surface, (80, 80, 90), (int(end_x), int(end_y)), int(scale(8, zoom)))

        # 2. 舱体外壳 (Main Body) - 三角形结构
        pts = []
        for i in range(3):
            rad = math.radians(i * 120 - 90) # -90, 30, 150
            x = cx + math.cos(rad) * r_cabin
            y = cy + math.sin(rad) * r_cabin
            pts.append((x, y))
        pygame.draw.polygon(surface, (200, 200, 210), pts)
        pygame.draw.polygon(surface, (150, 150, 160), pts, int(scale(4, zoom))) # 边框

        # 3. 核心接收器 (Receiver Core) - 中央圆球
        r_core = scale(35, zoom)
        pygame.draw.circle(surface, (240, 240, 250), (cx, cy), int(r_core))
        pygame.draw.circle(surface, (100, 100, 110), (cx, cy), int(r_core), 2)

    def generate_image(self):
        """静态外观基准图（zoom=1），锚点 (70, 70) = self.pos；PNG 缓存由 sprite_cache 自动导出/加载"""
        surf = pygame.Surface((140, 140), pygame.SRCALPHA)
        self._draw_static(surf, 70, 70, 1.0)
        return surf

    def _image_anchor(self):
        return 70, 70

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        cx, cy = int(screen_pos[0]), int(screen_pos[1])

        if not self._blit_cached_image(surface, cx, cy, zoom):
            self._draw_static(surface, cx, cy, zoom)

        # --- 动态：信号灯/能量光效（保留程序绘制） ---
        r_core = scale(35, zoom)
        t = pygame.time.get_ticks()

        # 红色警告灯 (顶部)
        pygame.draw.circle(surface, (200, 0, 0), (cx, cy - int(r_core//2)), int(scale(6, zoom)))

        # 蓝色能量环 (呼吸效果 + 动态波纹)
        s_glow = pygame.Surface((int(r_core*3), int(r_core*3)), pygame.SRCALPHA)
        pygame.draw.circle(s_glow, (0, 200, 255, 50), (int(r_core*1.5), int(r_core*1.5)), int(r_core))
        wave_r = (t * 0.05) % r_core
        pygame.draw.circle(s_glow, (0, 255, 255, 100 - int(wave_r/r_core * 100)),
                          (int(r_core*1.5), int(r_core*1.5)), int(wave_r), 2)
        surface.blit(s_glow, (cx - int(r_core*1.5), cy - int(r_core*1.5)))

        # 5. 血条
        self.draw_health_and_marker(surface, offset, zoom, -scale(80, zoom))
class DeathZone(Building):
    def __init__(self, game, pos, radius):

        super().__init__(game, pos, "neutral", "death_zone")
        print(self.pos)
        self.radius = radius
        self.rect = pygame.Rect(pos.x-radius, pos.y-radius, radius*2, radius*2)
        self.hp = 999999 # 无敌
        
    def update(self):
        # 吞噬一切
        for u in self.game.all_units:
            if u.alive and self.pos.distance_to(u.pos) < self.radius:
                u.take_damage(99999, "void",0) # 秒杀
                # 特效：掉下去
                
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        r = scale(self.radius, zoom)
        # 画一个黑洞
        pygame.draw.circle(surface, (0, 0, 0), screen_pos, r)
        pygame.draw.circle(surface, (50, 20, 0), screen_pos, r, 5) # 烧焦边缘        screen_pos = to_screen(self.pos, offset, zoom)
        r = scale(self.radius, zoom)
        # 画一个黑洞
        pygame.draw.circle(surface, (0, 0, 0), screen_pos, r)
        pygame.draw.circle(surface, (50, 20, 0), screen_pos, r, 5) # 烧焦边缘