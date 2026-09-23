import pygame
import random
import math
from settings import *
import uuid 
import time
import os
import sys
vec = pygame.math.Vector2

def to_screen(pos, offset, zoom):
    return (int((pos[0] - offset.x) * zoom), int((pos[1] - offset.y) * zoom))

def scale(value, zoom):
    return max(1, int(value * zoom))
def resource_path(relative_path):
    """ 获取资源绝对路径 """
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)
# main.py
def get_font(size, bold=False):
    font_path = resource_path(os.path.join("fonts", "simhei.ttf"))
    try:
        font = pygame.font.Font(font_path, size)
        if bold: font.set_bold(True)
        return font
    except:
        return pygame.font.Font(None, size)
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
        self.armor=0
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
        if hasattr(self.game, 'net_events'):
            dt = "normal"
            if getattr(self, 'is_mechanical', False): dt = "mech_death"
            if getattr(self, 'is_air', False): dt = "air_crash"
            
            # 发送
            self.game.net_events.append({
                "type": "EXPLOSION", 
                "x": int(self.pos.x), "y": int(self.pos.y), 
                "dt": dt
            })
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
                        break 
            
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


    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
        # --- 1. 尺寸与颜色配置 ---
        # 尺寸
        base_w = scale(50, zoom)     # 地基宽
        base_l = scale(80, zoom)     # 地基长
        base_h = scale(10, zoom)     # 地基厚度
        
        tower_h = scale(45, zoom)    # A型支架高度
        beam_len_front = scale(35, zoom) # 游梁前半截长度
        beam_len_back = scale(25, zoom)  # 游梁后半截长度
        
        # 颜色 (工业废土风)
        C_CONCRETE = (120, 120, 125)
        C_STEEL_DARK = (60, 60, 65)
        C_STEEL_LIGHT = (140, 140, 150)
        C_RUST = (100, 70, 60)       # 生锈细节
        C_SHADOW = (0, 0, 0, 80)
        
        # 队伍颜色处理
        # 假设 self.team 存在
        BLUE = (0, 150, 255)
        RED = (220, 60, 60)
        default_color = TEAM_COLORS.get("neutral", (100, 100, 100))
        team_color = default_color       
        team_color = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])


        # --- 2. 绘制阴影 (Shadow) ---
        # 一个长条形阴影
        shadow_offset = scale(10, zoom)
        shadow_rect = pygame.Rect(cx - base_w//2 + shadow_offset, 
                                cy - base_h//2 + shadow_offset, 
                                base_l, base_w) # 注意俯视时长宽视觉变换
        s_surf = pygame.Surface((scale(150, zoom), scale(150, zoom)), pygame.SRCALPHA)
        pygame.draw.ellipse(s_surf, C_SHADOW, (0, 0, base_l, base_w))
        surface.blit(s_surf, (cx - base_l//2 + shadow_offset, cy - base_w//4 + shadow_offset))


        # --- 3. 绘制地基 (Base Slab) ---
        # 画一个有厚度的长方体
        base_top_y = cy
        
        # 3.1 侧面 (厚度)
        rect_base_side = pygame.Rect(cx - base_l//2, base_top_y, base_l, base_h)
        pygame.draw.rect(surface, (80, 80, 85), rect_base_side)
        
        # 3.2 顶面 (Top)
        rect_base_top = pygame.Rect(cx - base_l//2, base_top_y - base_w//2, base_l, base_w)
        pygame.draw.rect(surface, C_CONCRETE, rect_base_top)
        pygame.draw.rect(surface, (60, 60, 60), rect_base_top, 2) # 边框
        
        # 3.3 地基上的油渍细节
        pygame.draw.ellipse(surface, (40, 40, 30), 
                        (cx + scale(20, zoom), base_top_y - scale(10, zoom), scale(15, zoom), scale(8, zoom)))


        # --- 4. A型支架 (The Tower) ---
        # 支撑摇臂的三角形结构
        pivot_x = cx 
        pivot_y = base_top_y - tower_h
        
        # 支架脚 (Spread out at base)
        feet_w = scale(20, zoom)
        foot_left = (cx - scale(10, zoom), base_top_y - scale(10, zoom)) # 稍微偏后
        foot_right = (cx + scale(10, zoom), base_top_y - scale(10, zoom))
        
        # 绘制三角形支架
        # 使用深色线条模拟钢架
        pygame.draw.line(surface, C_STEEL_DARK, foot_left, (pivot_x, pivot_y), int(scale(4, zoom)))
        pygame.draw.line(surface, C_STEEL_DARK, foot_right, (pivot_x, pivot_y), int(scale(4, zoom)))
        # 横向加固杆
        mid_y = (pivot_y + base_top_y) / 2
        pygame.draw.line(surface, C_STEEL_DARK, 
                        (foot_left[0]*0.5 + pivot_x*0.5, mid_y), 
                        (foot_right[0]*0.5 + pivot_x*0.5, mid_y), 2)


        # --- 5. 游梁动画 (The Walking Beam) ---
        # 计算摇摆角度
        # 使用正弦波代替原来的 pump_y += dir 逻辑，更加平滑且符合物理
        # 如果游戏逻辑必须依赖 self.pump_y，可以在这里更新它，但绘制用 math.sin 更好看
        
        # 模拟机械运动：周期约 2-3秒
        t = time.time() * 3 
        swing_angle = math.sin(t) * 0.25 # 摆动幅度弧度 (约15度)
        
        # 计算游梁两端的坐标
        # 前端 (Horse Head) - 向右
        head_x = pivot_x + math.cos(swing_angle) * beam_len_front
        head_y = pivot_y + math.sin(swing_angle) * beam_len_front
        
        # 后端 (Counterweight side) - 向左
        tail_x = pivot_x - math.cos(swing_angle) * beam_len_back
        tail_y = pivot_y - math.sin(swing_angle) * beam_len_back
        
        
        # --- 6. 绘制机械部件 ---
        
        # 6.1 抽油杆 (Polished Rod) - 垂直插入地下
        # 只有当头低下时才看起来连贯，这里做一个简单的垂直线
        # 抽油杆连接点在驴头下方
        rod_top = (head_x, head_y + scale(5, zoom)) # 驴头有个圆弧，杆子挂在下面
        rod_bottom = (head_x, base_top_y)
        pygame.draw.line(surface, (30, 30, 30), rod_top, rod_bottom, 2)
        
        # 6.2 驴头 (Horse Head) - 前端的圆弧状物体
        # 画一个扇形或半圆填充
        head_size = scale(12, zoom)
        # 用阵营颜色涂装驴头，方便识别
        pygame.draw.circle(surface, team_color, (int(head_x), int(head_y)), int(head_size))
        pygame.draw.circle(surface, (50, 50, 50), (int(head_x), int(head_y)), int(head_size), 2)
        
        # 6.3 游梁本体 (Beam) - 连接头尾的横梁
        pygame.draw.line(surface, C_STEEL_LIGHT, (tail_x, tail_y), (head_x, head_y), int(scale(8, zoom)))
        # 顶部的一层装饰线
        pygame.draw.line(surface, C_RUST, (tail_x, tail_y-2), (head_x, head_y-2), 2)

        # 6.4 尾部配重与连杆 (Rear Mechanism)
        # 尾部配重块
        pygame.draw.rect(surface, C_STEEL_DARK, (tail_x - scale(5, zoom), tail_y - scale(5, zoom), scale(10, zoom), scale(10, zoom)))
        
        # 连杆 (Pitman Arm) - 连接尾部到地面的曲柄
        # 曲柄位置 (模拟在地面转动)
        crank_center_x = pivot_x - scale(20, zoom)
        crank_center_y = base_top_y - scale(15, zoom)
        # 曲柄旋转
        crank_radius = scale(10, zoom)
        crank_angle = t + math.pi/2 # 相位差
        crank_pos_x = crank_center_x + math.cos(crank_angle) * crank_radius
        crank_pos_y = crank_center_y + math.sin(crank_angle) * crank_radius
        
        # 画连杆
        pygame.draw.line(surface, (80, 80, 80), (tail_x, tail_y), (crank_pos_x, crank_pos_y), 2)
        # 画曲柄轮
        pygame.draw.circle(surface, (50, 50, 50), (int(crank_center_x), int(crank_center_y)), int(scale(8, zoom)))
        # 旋转的销子
        pygame.draw.circle(surface, (200, 200, 200), (int(crank_pos_x), int(crank_pos_y)), 3)

        # 6.5 中央转轴 (Pivot Point)
        pygame.draw.circle(surface, C_STEEL_DARK, (int(pivot_x), int(pivot_y)), int(scale(5, zoom)))


        # --- 7. 占领进度条 (Capture Bar) ---
        if self.capture_progress > 0:
            bar_w = scale(50, zoom) # 加宽一点
            bar_h = scale(6, zoom)
            
            # 进度比
            pct = min(1.0, max(0.0, self.capture_progress / self.max_capture))
            
            bar_c=TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
            
            # 位置：在地基上方，稍微高一点
            bar_x = cx - bar_w // 2
            bar_y = base_top_y - tower_h - scale(25, zoom)
            
            # 背景框 (黑色半透明)
            s_bar = pygame.Surface((bar_w + 4, bar_h + 4))
            s_bar.fill((0,0,0))
            surface.blit(s_bar, (bar_x - 2, bar_y - 2))
            
            # 灰色底槽
            pygame.draw.rect(surface, (80, 80, 80), (bar_x, bar_y, bar_w, bar_h))
            # 彩色进度
            if pct > 0:
                pygame.draw.rect(surface, bar_c, (bar_x, bar_y, bar_w * pct, bar_h))
            
            # 外框装饰
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
                else:
                    self.capture_progress = 0
        else:
            self.capture_progress = max(0, self.capture_progress - 0.5)

    def draw(self, surface, offset, zoom):
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
class Projectile(pygame.sprite.Sprite):
    def __init__(self, game, pos, target, team, damage, d_type, is_aoe=False, aoe_radius=0, breakshellvalue=0):
        super().__init__()
        self.game = game
        self.pos = vec(pos)
        self.target = target  # [修改1] 保存目标引用
        self.team = team
        self.damage = damage
        self.breakshellvalue=breakshellvalue
        self.d_type = d_type
        self.alive = True
        self.is_aoe = is_aoe
        self.aoe_radius = aoe_radius
        self.target_dest = None
        self.target_dest = None # 初始        
        self.speed = ROCKET_SPEED if d_type == "rocket" else BULLET_SPEED
        if d_type == "ac130_vis": self.speed = 18 
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
        if self.d_type == "ac130_vis":
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
                    "dt": self.d_type # 传入伤害类型以便客户端区分特效
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
                Particle(self.game.particles, self.pos, ORANGE, 1, 15, 6)
            
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
    # draw 方法保持不变
    def draw(self, surface, offset, zoom):
        # ... (保持原样) ...
        if self.d_type == "ac130": return 
        screen_pos = to_screen(self.pos, offset, zoom)
        if not (-20 <= screen_pos[0] <= SCREEN_WIDTH+20 and -20 <= screen_pos[1] <= SCREEN_HEIGHT+20): return
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
                    
                    # 估算高度: 越高的 tier y 越小
                    tier_h = self.total_visual_height * (spot['tier'] / len(self.tiers))
                    offset_y = -tier_h
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

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        bx, by = screen_pos
        margin = 600 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return            
        # === 倒塌状态 ===
        if self.is_collapsed:
            # 绘制烧焦的废墟底座
            rubble_w = self.base_width * zoom * 1.2
            rubble_h = self.base_depth * zoom * 1.2
            rect = pygame.Rect(bx - rubble_w/2, by - rubble_h/2, rubble_w, rubble_h)
            
            # 焦黑的底色
            pygame.draw.rect(surface, (40, 35, 30), rect)
            # 依然冒烟 (可选)
            return

        # === 正常状态 (带战损) ===
        
        hp_pct = self.hp / self.max_hp
        
        # 阴影
        shadow_len = self.total_visual_height * zoom * 0.45
        base_w_px = self.base_width * zoom
        pygame.draw.rect(surface, (0, 0, 0), (bx - base_w_px*0.4, by, base_w_px, shadow_len))

        # 逐层绘制
        current_y = by + (self.base_depth * zoom) / 2
        total_height_offset = 0
        
        for i, tier in enumerate(self.tiers):
            w_ratio, d_ratio, h_offset = tier
            
            curr_w = self.base_width * w_ratio * zoom
            curr_d = self.base_depth * d_ratio * zoom
            curr_h_off = h_offset * zoom
            
            vis_top_cy = current_y - total_height_offset - curr_h_off
            total_height_offset += curr_h_off
            
            # A. 墙体 (South Face)
            wall_rect = pygame.Rect(bx - curr_w/2, vis_top_cy + curr_d/2, curr_w, curr_h_off)
            
            # 基础墙面
            pygame.draw.rect(surface, self.theme["wall"], wall_rect)
            pygame.draw.rect(surface, (20, 20, 20), wall_rect, 1)
            
            # 窗户 (如果受损严重，不画窗户或者画破损窗户)
            if 0 < i < len(self.tiers) - 1:
                # 简单的整面玻璃绘制
                glass_area = wall_rect.inflate(-10*zoom, -10*zoom)
                # 如果血量低，玻璃颜色变暗/变碎
                glass_color = self.theme["glass"]
                if hp_pct < 0.5:
                    glass_color = (50, 60, 70) # 破碎黯淡
                pygame.draw.rect(surface, glass_color, glass_area)
                
                # 绘制窗框网格
                for wy in range(int(glass_area.top), int(glass_area.bottom), int(10*zoom)):
                    pygame.draw.line(surface, (100,100,100), (glass_area.left, wy), (glass_area.right, wy), 1)

            # --- [新增] 绘制战损斑点 (Damage Decals) ---
            # 筛选出属于这一层且已激活的损伤点
            layer_spots = [s for s in self.damage_spots if s['tier'] == i and hp_pct < s['active_threshold']]
            
            for spot in layer_spots:
                # 计算斑点在墙面上的位置
                sx = wall_rect.left + wall_rect.width * spot['x_pct']
                sy = wall_rect.top + wall_rect.height * spot['y_pct']
                sr = spot['size'] * zoom * 0.8
                
                # 1. 焦黑坑洞 (Scorch Mark)
                pygame.draw.circle(surface, (20, 10, 5), (int(sx), int(sy)), int(sr))
                
                # 2. 内部火光 (Fire Glow) - 严重受损时
                if hp_pct < 0.3:
                    # 闪烁效果
                    if random.random() < 0.8: # 80%概率亮
                        glow_r = sr * 0.6
                        pygame.draw.circle(surface, (255, 100, 0), (int(sx), int(sy)), int(glow_r))
                        pygame.draw.circle(surface, (255, 255, 100), (int(sx), int(sy)), int(glow_r*0.5))

            # B. 顶面 (Roof)
            roof_rect = pygame.Rect(bx - curr_w/2, vis_top_cy - curr_d/2, curr_w, curr_d)
            pygame.draw.rect(surface, self.theme["roof"], roof_rect)
            pygame.draw.rect(surface, (150, 150, 150), roof_rect, 1)
            
            # C. 侧面阴影
            pygame.draw.line(surface, (30,30,30), wall_rect.topright, wall_rect.bottomright, int(4*zoom))

        # 3. 楼顶设施 (受损时歪斜或消失)
        # 这里保持简单，不画歪斜，只画颜色变化
        top_cy = current_y - total_height_offset
        ant_base = (bx, top_cy)
        ant_tip = (bx, top_cy - 40*zoom)
        
        # 天线
        pygame.draw.line(surface, (100, 100, 100), ant_base, ant_tip, 2)
        # 灯 (受损就不亮了)
        if hp_pct > 0.2 and (pygame.time.get_ticks() // 500) % 2 == 0:
            pygame.draw.circle(surface, (255, 0, 0), (int(ant_tip[0]), int(ant_tip[1])), int(3*zoom))

        # 4. 血条
        self.draw_health_and_marker(surface, offset, zoom, -total_height_offset - 20*zoom)
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
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
        # --- 1. 尺寸与配色 ---
        w = scale(110, zoom)       # 总宽度 (左右跨度)
        l = scale(100, zoom)       # 总长度 (进深)
        dock_width = scale(50, zoom) # 中间水域宽度
        platform_w = (w - dock_width) // 2 # 两侧平台宽度
        
        # 颜色
        default_color = TEAM_COLORS.get("neutral", (100, 100, 100))
        team_color = default_color       
        team_color = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        C_CONCRETE    = (110, 110, 115) # 混凝土
        C_CONCRETE_DK = (80, 80, 85)    # 侧面/阴影
        C_WATER_DOCK  = (30, 60, 90)    # 船坞内的深水
        C_CRANE       = (220, 180, 20)  # 起重机黄
        C_CRANE_DARK  = (160, 120, 10)  # 起重机暗部
        C_CONTROL     = (80, 90, 100)   # 控制室
        C_ACCENT      = team_color
        
        # --- 2. 绘制阴影 (Shadow) ---
        # 阴影主要投射在水面上或海底（如果是浅水）
        # 这里简单画一个整体轮廓阴影
        shadow_offset = scale(12, zoom)
        s_surf = pygame.Surface((w + shadow_offset, l + shadow_offset), pygame.SRCALPHA)
        
        # U型阴影
        # 左臂
        pygame.draw.rect(s_surf, (0,0,0,80), (shadow_offset, shadow_offset, platform_w, l))
        # 右臂
        pygame.draw.rect(s_surf, (0,0,0,80), (w - platform_w + shadow_offset, shadow_offset, platform_w, l))
        # 底部连接处 (Backstop)
        pygame.draw.rect(s_surf, (0,0,0,80), (shadow_offset, shadow_offset, w, scale(20, zoom)))
        
        surface.blit(s_surf, (cx - w//2, cy - l//2))

        # --- 3. 船坞结构 (The Dock) ---
        top_y = cy - l//2 # 建筑最上沿 (靠岸的一侧)
        
        # 3.1 船坞内的水域 (Water Basin)
        # 在绘制平台之前，先画中间的深色水域
        dock_rect = pygame.Rect(cx - dock_width//2, top_y + scale(20, zoom), dock_width, l - scale(20, zoom))
        pygame.draw.rect(surface, C_WATER_DOCK, dock_rect)
        
        # 水面波纹特效 (简单画几条线)
        t = time.time()
        for i in range(3):
            wave_y = dock_rect.top + ((t * 10 + i * 30) % dock_rect.height)
            width_var = math.sin(t + i) * 10
            pygame.draw.line(surface, (50, 80, 120), 
                            (dock_rect.left + 5, wave_y), 
                            (dock_rect.right - 5, wave_y), 1)

        # 3.2 混凝土平台 (Concrete Platforms)
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

        # 3.3 装饰细节 (Bollards & Stripes)
        # 黄黑警示线 (在水岸边缘)
        for i in range(0, int(l), int(scale(15, zoom))):
            # 左侧
            pygame.draw.rect(surface, (200, 180, 0), (left_rect.right - 4, top_y + i, 4, 8))
            # 右侧
            pygame.draw.rect(surface, (200, 180, 0), (right_rect.left, top_y + i, 4, 8))
            
        # 系缆桩 (小黑点)
        for i in range(0, int(l), int(scale(30, zoom))):
            pygame.draw.circle(surface, (20, 20, 20), (left_rect.right - scale(8, zoom), top_y + scale(20, zoom) + i), 2)
            pygame.draw.circle(surface, (20, 20, 20), (right_rect.left + scale(8, zoom), top_y + scale(20, zoom) + i), 2)


        # --- 4. 龙门吊 (Gantry Crane) ---
        # 横跨船坞的巨大吊车
        crane_y = cy # 位于中间位置
        crane_h = scale(12, zoom) # 梁的粗细
        crane_leg_h = scale(25, zoom) # 腿高 (高度差)
        
        # 4.1 吊车轨道 (Rails)
        pygame.draw.line(surface, (40, 40, 45), (left_rect.centerx, top_y), (left_rect.centerx, top_y + l), 2)
        pygame.draw.line(surface, (40, 40, 45), (right_rect.centerx, top_y), (right_rect.centerx, top_y + l), 2)
        
        # 4.2 吊车支腿 (Legs)
        leg_l_pos = (left_rect.centerx, crane_y)
        leg_r_pos = (right_rect.centerx, crane_y)
        
        # 左腿
        pygame.draw.rect(surface, C_CRANE_DARK, (leg_l_pos[0]-2, crane_y - crane_leg_h, 4, crane_leg_h))
        # 右腿
        pygame.draw.rect(surface, C_CRANE_DARK, (leg_r_pos[0]-2, crane_y - crane_leg_h, 4, crane_leg_h))
        
        # 4.3 吊车横梁 (Main Beam)
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
                
        # 4.4 驾驶室 (Cab) - 挂在横梁下
        cab_x = leg_l_pos[0] + scale(10, zoom)
        pygame.draw.rect(surface, C_CONTROL, (cab_x, beam_rect.bottom, scale(12, zoom), scale(10, zoom)))
        pygame.draw.rect(surface, (20, 20, 20), (cab_x+2, beam_rect.bottom+2, 8, 4)) # 窗户
        
        # 4.5 吊钩 (Hook)
        hook_x = cx
        pygame.draw.line(surface, (20, 20, 20), (hook_x, beam_rect.bottom), (hook_x, beam_rect.bottom + scale(15, zoom)), 1)
        pygame.draw.circle(surface, (30, 30, 30), (int(hook_x), int(beam_rect.bottom + scale(15, zoom))), 3)


        # --- 5. 附属设施 ---
        # 控制塔/办公室 (位于左后方)
        office_rect = pygame.Rect(left_rect.left + scale(5, zoom), top_y - scale(10, zoom), scale(30, zoom), scale(20, zoom))
        pygame.draw.rect(surface, C_CONTROL, office_rect)
        # 阵营色屋顶
        pygame.draw.rect(surface, C_ACCENT, (office_rect.left, office_rect.top, office_rect.width, 4))
        self.draw_health_and_marker(surface, offset, zoom, -60)       
class TechCenter(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "tech_center")
        self.hp = 1500 # 或 TECH_CENTER_HP
        self.max_hp = 1500
        self.radius = 60
        self.rect = pygame.Rect(pos.x - 60, pos.y - 60, 120, 120)
        self.power_usage = 150 

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
        # --- 1. 尺寸与配色 ---
        w = scale(110, zoom)       # 建筑宽度
        l = scale(90, zoom)        # 建筑进深
        pit_w = scale(60, zoom)    # 组装坑宽度
        pit_l = scale(70, zoom)    # 组装坑长度
        
        # 颜色 (高科技/赛博风)
        C_WALL        = (50, 55, 60)    # 建筑外墙
        C_ROOF        = (70, 75, 80)    # 屋顶
        C_PIT_FLOOR   = (20, 20, 25)    # 坑底深色
        C_GANTRY      = (100, 100, 110) # 龙门架
        C_GLOW        = (0, 200, 255)   # 科技蓝光
        C_LASER       = (150, 255, 255) # 扫描激光
        C_FAN         = (30, 30, 30)    # 风扇
        
        # 阵营色
        team_c = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        
        # 时间因子
        t = time.time()
        
        # --- 2. 绘制阴影 ---
        shadow_offset = scale(10, zoom)
        s_surf = pygame.Surface((w + shadow_offset, l + shadow_offset), pygame.SRCALPHA)
        pygame.draw.rect(s_surf, (0, 0, 0, 80), (shadow_offset, shadow_offset, w, l), border_radius=int(scale(8, zoom)))
        # 挖去中间的坑 (让阴影只在建筑周围)
        # 这一步比较麻烦，简单处理：直接画大阴影，反正坑底也是黑的
        surface.blit(s_surf, (cx - w//2, cy - l//2))

        # --- 3. 建筑主体 (Structure) ---
        base_rect = pygame.Rect(cx - w//2, cy - l//2, w, l)
        
        # 3.1 外墙底座
        pygame.draw.rect(surface, C_WALL, base_rect, border_radius=int(scale(5, zoom)))
        
        # 3.2 组装坑 (Assembly Pit)
        # 位于中央
        pit_rect = pygame.Rect(cx - pit_w//2, cy - pit_l//2, pit_w, pit_l)
        pygame.draw.rect(surface, C_PIT_FLOOR, pit_rect)
        # 坑壁内阴影
        pygame.draw.rect(surface, (10, 10, 10), pit_rect, 2)
        
        # 坑底网格线 (Grid)
        grid_spacing = scale(15, zoom)
        for i in range(1, 5):
            # 纵线
            lx = pit_rect.left + i * grid_spacing
            if lx < pit_rect.right:
                pygame.draw.line(surface, (30, 40, 50), (lx, pit_rect.top), (lx, pit_rect.bottom), 1)
            # 横线
            ly = pit_rect.top + i * grid_spacing
            if ly < pit_rect.bottom:
                pygame.draw.line(surface, (30, 40, 50), (pit_rect.left, ly), (pit_rect.right, ly), 1)

        # 3.3 屋顶平台 (左右两侧)
        # 左侧平台
        left_roof = pygame.Rect(base_rect.left, base_rect.top, (w - pit_w)//2, l)
        pygame.draw.rect(surface, C_ROOF, left_roof)
        pygame.draw.rect(surface, (90, 95, 100), left_roof, 1) # 边框
        
        # 右侧平台
        right_roof = pygame.Rect(pit_rect.right, base_rect.top, (w - pit_w)//2, l)
        pygame.draw.rect(surface, C_ROOF, right_roof)
        pygame.draw.rect(surface, (90, 95, 100), right_roof, 1)

        # --- 4. 动态细节 (Fans & Lights) ---
        
        # 4.1 旋转排气扇 (两侧屋顶)
        fan_r = scale(8, zoom)
        fan_positions = [
            (left_roof.centerx, left_roof.centery - scale(20, zoom)),
            (left_roof.centerx, left_roof.centery + scale(20, zoom)),
            (right_roof.centerx, right_roof.centery)
        ]
        
        for fx, fy in fan_positions:
            # 风扇口
            pygame.draw.circle(surface, (20, 20, 20), (int(fx), int(fy)), int(fan_r))
            pygame.draw.circle(surface, (60, 60, 60), (int(fx), int(fy)), int(fan_r), 1)
            # 旋转叶片
            angle_offset = t * 8
            for i in range(3):
                angle = angle_offset + i * (2 * math.pi / 3)
                ex = fx + math.cos(angle) * fan_r
                ey = fy + math.sin(angle) * fan_r
                pygame.draw.line(surface, (50, 50, 50), (fx, fy), (ex, ey), 2)

        # 4.2 阵营光条
        pygame.draw.rect(surface, team_c, (left_roof.right - 4, left_roof.top + 5, 2, l - 10))
        pygame.draw.rect(surface, team_c, (right_roof.left + 2, right_roof.top + 5, 2, l - 10))


        # --- 5. 移动龙门架/打印臂 (Scanning Gantry) ---
        # 在坑上方前后移动的机械臂
        
        # 移动逻辑: 正弦波往复运动
        slide_progress = (math.sin(t * 2) + 1) / 2 # 0 ~ 1
        gantry_y = pit_rect.top + slide_progress * (pit_l - scale(10, zoom))
        
        # 绘制龙门架横梁
        gantry_h = scale(8, zoom)
        gantry_rect = pygame.Rect(pit_rect.left - 2, gantry_y, pit_w + 4, gantry_h)
        
        # 激光扫描面 (在龙门架下方)
        # 用半透明 Surface 模拟光片
        beam_h = scale(20, zoom)
        s_beam = pygame.Surface((pit_w, beam_h), pygame.SRCALPHA)
        # 渐变光
        for i in range(int(beam_h)):
            alpha = int(100 * (1 - i/beam_h))
            pygame.draw.line(s_beam, (*C_GLOW, alpha), (0, i), (pit_w, i))
        
        # 绘制光束 (如果是向下扫描，需要 flip 或者直接画)
        surface.blit(s_beam, (pit_rect.left, gantry_rect.bottom))
        
        # 绘制龙门架实体
        pygame.draw.rect(surface, C_GANTRY, gantry_rect)
        # 龙门架上的灯
        pygame.draw.circle(surface, (0, 255, 0), (int(gantry_rect.left + 5), int(gantry_rect.centery)), 2)
        pygame.draw.circle(surface, (255, 0, 0), (int(gantry_rect.right - 5), int(gantry_rect.centery)), 2)
        # 发光核心 (打印头)
        head_x = gantry_rect.left + (math.sin(t * 5) + 1) / 2 * gantry_rect.width # 左右移动的打印头
        pygame.draw.circle(surface, C_LASER, (int(head_x), int(gantry_rect.centery)), 3)
        
        # --- 6. 制造火花特效 (Sparks) ---
        # 在扫描线附近随机产生
        if random.random() < 0.3:
            sx = random.randint(pit_rect.left, pit_rect.right)
            sy = int(gantry_rect.bottom + random.randint(0, 10))
            pygame.draw.circle(surface, (255, 255, 200), (sx, sy), 1)
            pygame.draw.line(surface, (255, 255, 255), (sx, sy), (sx+2, sy+2), 1)

        # --- 7. 进度条/血条 ---
        # 如果正在生产，可以在这里画生产进度
        # 假设 self.build_progress 存在
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

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 画一个科幻塔
        color = CYAN if self.cooldown <= 0 else GRAY
        pygame.draw.circle(surface, (30, 30, 30), screen_pos, scale(40, zoom))
        pygame.draw.circle(surface, color, screen_pos, scale(15, zoom))
        # 电弧
        if self.cooldown <= 0:
            pygame.draw.circle(surface, WHITE, screen_pos, scale(10 + math.sin(pygame.time.get_ticks()*0.01)*5, zoom), 2)
        
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
        
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        if self.is_collapsed:
            # 绘制废墟 (一堆碎石)
            for i in range(5):
                offset_x = random.randint(-40, 40)
                offset_y = random.randint(-40, 40)
                # 使用确定性随机(基于位置)防止抖动，或者简单画几个固定的块
                # 这里为了简单，画个大的废墟堆
                pygame.draw.circle(surface, (100, 90, 80), screen_pos, scale(60, zoom))
                pygame.draw.rect(surface, (80, 70, 60), (screen_pos[0]-scale(30, zoom), screen_pos[1], scale(60, zoom), scale(20, zoom)))
        else:        
            # --- 绘制中式古刹/宝塔 ---
            # 颜色
            roof_color = (180, 60, 40)  # 朱红/砖红
            wall_color = (160, 140, 100) # 土黄墙
            
            # 这是一个三层塔的俯视图
            layers = 3
            base_size = scale(100, zoom)
            
            for i in range(layers):
                s = base_size - i * scale(25, zoom)
                rect = pygame.Rect(0, 0, s, s)
                rect.center = screen_pos
                
                # 屋檐 (带翘角)
                pygame.draw.rect(surface, roof_color, rect)
                pygame.draw.rect(surface, (100, 30, 20), rect, 2) # 轮廓
                
                # 墙体 (比屋檐小一点)
                inner_s = s - scale(10, zoom)
                if inner_s > 0:
                    inner_rect = pygame.Rect(0, 0, inner_s, inner_s)
                    inner_rect.center = screen_pos
                    pygame.draw.rect(surface, wall_color, inner_rect)

            # 塔顶装饰
            pygame.draw.circle(surface, (255, 215, 0), screen_pos, scale(8, zoom)) # 金顶

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
def scale_img(image, zoom):
    w, h = image.get_size()
    return pygame.transform.scale(image, (int(w*zoom), int(h*zoom)))
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
                        break
            
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

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 800 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return            
        # 1. 底座
        scaled_base = scale_img(self.base_image, zoom)
        base_rect = scaled_base.get_rect(center=screen_pos)
        surface.blit(scaled_base, base_rect)
        
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
        
        rot_radar = pygame.transform.rotate(r_surf, angle)
        surface.blit(rot_radar, rot_radar.get_rect(center=(radar_cx, radar_cy)))
        
        # 2.2 龙门吊 (Gantry Crane) - 可以在轨道上移动
        # 轨道在左侧栈桥，y范围 160-480
        # 让它做往复运动
        crane_y_offset = 160 + abs(math.sin(pygame.time.get_ticks() * 0.0005)) * 250
        
        # 转换为屏幕偏移
        # 轨道x在 35-75 之间 (中心 55)
        # 相对于整体中心 (150, 250) -> x偏移 -95, y偏移 crane_y_offset - 250
        
        crane_sx = screen_pos[0] - scale(95, zoom)
        crane_sy = screen_pos[1] + scale(crane_y_offset - 250, zoom)
        
        # 画吊车 (俯视就是一个黄框)
        c_w = scale(40, zoom)
        c_h = scale(20, zoom)
        pygame.draw.rect(surface, (220, 180, 20), (crane_sx - c_w//2, crane_sy - c_h//2, c_w, c_h))
        pygame.draw.rect(surface, (0,0,0), (crane_sx - c_w//2, crane_sy - c_h//2, c_w, c_h), 1)
        
        # 3. 阵营标识 (Team Flag)
        # 插在主楼顶上
        team_color = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        # 主楼中心 (70, 70) -> 偏移 (-80, -180)
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
    def __init__(self, game, pos, orientation="horizontal"):
        # 桥梁通常算作中立，但不可被占领，只会被破坏
        super().__init__(game, pos, "neutral", "bridge")
        self.hp = 1500
        self.max_hp = 1500
        self.orientation = orientation
        
        # 尺寸
        if orientation == "horizontal":
            self.width, self.height = 600, 300
        else:
            self.width, self.height = 200, 300
            
        self.radius = max(self.width, self.height) // 2
        self.rect = pygame.Rect(pos.x - self.width//2, pos.y - self.height//2, self.width, self.height)
        
        # 状态
        self.is_broken = False
        self.regen_timer = 0
        self.regen_time_total = 1800 # 30秒 (60帧 * 30)

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

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        w = scale(self.width, zoom)
        h = scale(self.height, zoom)
        
        rect = pygame.Rect(screen_pos[0]-w//2, screen_pos[1]-h//2, w, h)
        
        if self.is_broken:
            # 断桥绘制
            pygame.draw.rect(surface, (50, 50, 60), rect) # 深色底表示水/废墟
            # 画两端断裂
            if self.orientation == "horizontal":
                pygame.draw.rect(surface, (100, 90, 80), (rect.x, rect.y, w//4, h))
                pygame.draw.rect(surface, (100, 90, 80), (rect.right-w//4, rect.y, w//4, h))
            else:
                pygame.draw.rect(surface, (100, 90, 80), (rect.x, rect.y, w, h//4))
                pygame.draw.rect(surface, (100, 90, 80), (rect.x, rect.bottom-h//4, w, h//4))
            
            # 倒计时文本
            time_left = int(self.regen_timer / 60)
            txt = self.game.ui_font.render(f"REPAIR: {time_left}s", True, WHITE)
            surface.blit(txt, txt.get_rect(center=screen_pos))
            
        else:
            # 正常桥梁
            color = (160, 150, 140) # 水泥灰
            pygame.draw.rect(surface, color, rect)
            pygame.draw.rect(surface, (80, 80, 80), rect, 2)
            
            # 桥面纹理
            if self.orientation == "horizontal":
                pygame.draw.line(surface, YELLOW, (rect.x, rect.centery), (rect.right, rect.centery), 2)
                for i in range(1, 4):
                    x = rect.x + i * (w // 4)
                    pygame.draw.line(surface, (100, 100, 100), (x, rect.y), (x, rect.bottom), 2)
            else:
                pygame.draw.line(surface, YELLOW, (rect.centerx, rect.y), (rect.centerx, rect.bottom), 2)
                
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

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
        # 尺寸
        r_cabin = scale(60, zoom)
        
        # 1. 悬索连接点 (Cables attachment)
        # 虽然具体的电缆由 CableSegment 画，但这里画出连接到舱体的部分
        # 假设 3 根电缆从 -90, 30, 150 度连过来
        angles = [-90, 30, 150]
        for ang in angles:
            rad = math.radians(ang)
            # 缆索头
            end_x = cx + math.cos(rad) * r_cabin
            end_y = cy + math.sin(rad) * r_cabin
            pygame.draw.line(surface, (50, 50, 50), (cx, cy), (end_x, end_y), int(scale(10, zoom)))
            pygame.draw.circle(surface, (80, 80, 90), (int(end_x), int(end_y)), int(scale(8, zoom)))

        # 2. 舱体外壳 (Main Body) - 三角形结构
        # 使用三个点构建一个倒三角形或者六边形
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
        
        # 4. 信号灯/能量光效
        # 模拟接收数据的闪烁
        t = pygame.time.get_ticks()
        alpha = 150 + int(math.sin(t * 0.01) * 100)
        
        # 红色警告灯 (顶部)
        pygame.draw.circle(surface, (200, 0, 0), (cx, cy - int(r_core//2)), int(scale(6, zoom)))
        
        # 蓝色能量环 (呼吸效果)
        s_glow = pygame.Surface((int(r_core*3), int(r_core*3)), pygame.SRCALPHA)
        pygame.draw.circle(s_glow, (0, 200, 255, 50), (int(r_core*1.5), int(r_core*1.5)), int(r_core))
        # 动态波纹
        wave_r = (t * 0.05) % r_core
        pygame.draw.circle(s_glow, (0, 255, 255, 100 - int(wave_r/r_core * 100)), 
                          (int(r_core*1.5), int(r_core*1.5)), int(wave_r), 2)
        
        surface.blit(s_glow, (cx - int(r_core*1.5), cy - int(r_core*1.5)))

        # 5. 血条
        self.draw_health_and_marker(surface, offset, zoom, -scale(80, zoom))

# ---------------------------------------------------------

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
        r = scale(self.radius, zoom)
        # 画一个黑洞
        pygame.draw.circle(surface, (0, 0, 0), screen_pos, r)
        pygame.draw.circle(surface, (50, 20, 0), screen_pos, r, 5) # 烧焦边缘