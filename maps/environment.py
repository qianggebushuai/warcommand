import pygame
import random
import math
from core.settings import *
from core.base_classes import vec, to_screen, scale

class EnvironmentManager:
    def __init__(self, game):
        self.game = game
        self.active_weather = None # "storm", "sandstorm", etc.
        self.intensity = 0.0 # 0.0 ~ 1.0 (淡入淡出)
        self.target_intensity = 0.0
        
        # 暴风雨粒子
        self.rain_drops = [] 
        self.ripples = []   
        
        # 滤镜层
        self.filter_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        
        # 雷电
        self.lightning_timer = 0
        self.flash_alpha = 0

        # ---- 常驻战场氛围（不依赖天气开关）----
        self._build_ambient()

    # ================= 常驻氛围层 =================
    def _build_ambient(self):
        """云影（世界坐标漂移）+ 飞鸟群 + 远处炮火闪光 + 空气尘埃（屏幕空间）"""
        # 1. 云影：柔和暗斑，世界坐标缓慢漂移，营造时间流逝感
        def _cloud(w, h):
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            cx, cy = w // 2, h // 2
            # 多层同心椭圆递减 alpha，形成柔和边缘
            for i in range(6):
                k = 1.0 - i / 6.0
                rx, ry = int(w * 0.5 * k), int(h * 0.5 * k)
                a = int(16 + 8 * i / 6.0)
                pygame.draw.ellipse(surf, (10, 12, 16, a), (cx - rx, cy - ry, rx * 2, ry * 2))
            return surf

        self.ambient_clouds = []
        for _ in range(5):
            w = random.randint(640, 980)
            h = int(w * random.uniform(0.55, 0.7))
            surf = _cloud(w, h)
            self.ambient_clouds.append({
                'surf': surf, 'w': w, 'h': h,
                'x': random.uniform(0, max(1, SCREEN_WIDTH * 3)),
                'y': random.uniform(0, max(1, SCREEN_HEIGHT * 3)),
                'vx': random.uniform(0.12, 0.30),
                'vy': random.uniform(0.03, 0.10),
            })
        # 云的活动范围（地图尺寸，update 时若 game.current_map 可用则刷新）
        self.ambient_bounds = (SCREEN_WIDTH * 3, SCREEN_HEIGHT * 3)

        # 2. 飞鸟群：间隔刷一队从屏幕一侧飞过
        self.birds = []                # [{'x','y','phase','side'}]
        self.bird_timer = random.randint(400, 900)

        # 3. 空气尘埃：极淡漂浮微粒，增加空气流动感
        self.dust = [[random.uniform(0, SCREEN_WIDTH), random.uniform(0, SCREEN_HEIGHT),
                      random.uniform(-0.25, 0.25), random.uniform(-0.15, 0.15),
                      random.randint(25, 55)] for _ in range(16)]

    def _refresh_ambient_bounds(self):
        m = getattr(self.game, 'current_map', None)
        if m is not None and getattr(m, 'width', 0):
            self.ambient_bounds = (float(m.width), float(m.height))

    def _update_ambient(self):
        # 1. 云影漂移（世界坐标，出界回绕）
        bw, bh = self.ambient_bounds
        for c in self.ambient_clouds:
            c['x'] += c['vx']
            c['y'] += c['vy']
            if c['x'] > bw + c['w']:
                c['x'] = -c['w']
            if c['y'] > bh + c['h']:
                c['y'] = -c['h']

        # 2. 飞鸟群
        self.bird_timer -= 1
        if self.bird_timer <= 0 and not self.birds:
            side = random.choice([-1, 1])
            y0 = random.uniform(SCREEN_HEIGHT * 0.1, SCREEN_HEIGHT * 0.55)
            for i in range(random.randint(5, 8)):
                self.birds.append({
                    'x': (SCREEN_WIDTH + 60) if side > 0 else -60,
                    'y': y0, 'phase': random.uniform(0, 6.28),
                    'dx': -side * random.uniform(2.4, 3.4),
                    'dy': random.uniform(-0.25, 0.25),
                    'i': i,
                })
            self.bird_timer = random.randint(1300, 2600)
        for b in self.birds:
            b['x'] += b['dx']
            b['y'] += b['dy'] + math.sin(pygame.time.get_ticks() * 0.004 + b['phase']) * 0.3
        self.birds = [b for b in self.birds if -80 < b['x'] < SCREEN_WIDTH + 80]

        # 3. 尘埃漂移 + wrap
        for d in self.dust:
            d[0] += d[2]
            d[1] += d[3]
            if d[0] < 0: d[0] += SCREEN_WIDTH
            if d[0] > SCREEN_WIDTH: d[0] -= SCREEN_WIDTH
            if d[1] < 0: d[1] += SCREEN_HEIGHT
            if d[1] > SCREEN_HEIGHT: d[1] -= SCREEN_HEIGHT

    def _draw_ambient(self, screen):
        zoom = getattr(self.game, 'zoom', 1.0)
        offset = getattr(self.game, 'camera_offset', vec(0, 0))

        # 1. 云影（世界坐标 -> 屏幕，柔和暗斑压在地面上）
        for c in self.ambient_clouds:
            sx = (c['x'] - offset.x) * zoom
            sy = (c['y'] - offset.y) * zoom
            w = int(c['w'] * zoom)
            h = int(c['h'] * zoom)
            if w < 8 or sx + w < 0 or sy + h < 0 or sx > SCREEN_WIDTH or sy > SCREEN_HEIGHT:
                continue
            scaled = self._ambient_scaled(c, w, h)
            screen.blit(scaled, (sx, sy))

        # 2. 飞鸟（深色小 V，翅膀正弦摆动）
        tick = pygame.time.get_ticks()
        for b in self.birds:
            flap = math.sin(tick * 0.012 + b['phase'])
            ws = max(2, int(5 * min(1.2, zoom)))
            bx, by = int(b['x']), int(b['y'])
            wy = int(flap * 2.2)
            pygame.draw.line(screen, (35, 40, 50), (bx - ws, by - wy), (bx, by), 1)
            pygame.draw.line(screen, (35, 40, 50), (bx, by), (bx + ws, by - wy), 1)

        # 3. 尘埃微粒
        for d in self.dust:
            pygame.draw.circle(screen, (255, 255, 240, d[4]), (int(d[0]), int(d[1])), 1)

    def _ambient_scaled(self, c, w, h):
        """云影缩放缓存（按尺寸档位）"""
        key = (c['w'], c['h'], w)
        cache = getattr(self, '_ambient_scale_cache', None)
        if cache is None:
            cache = self._ambient_scale_cache = {}
        if key not in cache:
            cache[key] = pygame.transform.smoothscale(c['surf'], (w, h))
            if len(cache) > 24:
                cache.pop(next(iter(cache)))
        return cache[key]

    def set_weather(self, weather_type):
        if self.active_weather != weather_type:
            self.active_weather = weather_type
            if weather_type:
                self.target_intensity = 1.0
                print(f"[Env] Weather changing to {weather_type}")
            else:
                self.target_intensity = 0.0

    def update(self):
        # 常驻氛围层永远更新（不依赖天气开关）
        if not getattr(self, '_ambient_bounds_ready', False):
            self._refresh_ambient_bounds()
            self._ambient_bounds_ready = True
        self._update_ambient()

        fade_speed = 0.0001 
        
        if self.intensity < self.target_intensity:
            self.intensity += fade_speed
        elif self.intensity > self.target_intensity:
            self.intensity -= fade_speed
            
        if self.intensity <= 0 and self.target_intensity == 0:
            self.active_weather = None
            return

        if self.active_weather == "storm":
            self.update_storm()

    def update_storm(self):
        # 1. 生成雨滴
        count = int(10 * self.intensity) 
        for _ in range(count):
            x = random.randint(-200, SCREEN_WIDTH)
            y = random.randint(-100, 0)
            
            speed = random.randint(15, 25)
            length = random.randint(10, 20)
            
            target_y = random.randint(int(SCREEN_HEIGHT * 0.2), SCREEN_HEIGHT)
            
            self.rain_drops.append([x, y, speed, length, target_y])
            
        new_drops = []
        for r in self.rain_drops:
            # r = [x, y, speed, length, target_y]
            r[0] += 3 # 右
            r[1] += r[2] # 下
            
            if r[1] >= r[4]:
                wx = r[0] / self.game.zoom + self.game.camera_offset.x
                wy = r[1] / self.game.zoom + self.game.camera_offset.y
                
                in_water = False
                if hasattr(self.game, 'lakes'):
                    from maps.map_data import lake_contains, island_contains
                    for lake in self.game.lakes:
                        if isinstance(lake, dict) and lake.get('type') != 'water':
                            continue
                        if lake_contains(lake, wx, wy):
                            in_water = True
                            break
                    if in_water and hasattr(self.game.current_map, 'islands'):
                        for isle in self.game.current_map.islands:
                            if island_contains(isle, wx, wy):
                                in_water = False
                                break
                
                # 只有水里才生波纹
                if in_water and random.random() < 0.5 * self.intensity:
                    # 存世界坐标！以便随镜头缩放
                    self.ripples.append([wx, wy, 2, 150]) # x, y, r, alpha (World Coords)
            else:
                new_drops.append(r)
        self.rain_drops = new_drops
        
        # 更新波纹
        for rip in self.ripples:
            rip[2] += 0.5 # 世界半径变大
            rip[3] -= 5
        self.ripples = [r for r in self.ripples if r[3] > 0]
        # 4. 雷电逻辑
        if self.flash_alpha > 0:
            self.flash_alpha -= 10
        else:
            if random.random() < 0.005 * self.intensity: # 小概率打雷
                self.flash_alpha = 180

    def draw(self, screen):
        # 常驻氛围层最先画（云影压地面、鸟/炮火/尘埃叠加），天气层在其上
        self._draw_ambient(screen)
        if self.intensity <= 0: return
        zoom = self.game.zoom
        offset = self.game.camera_offset        
        if self.active_weather == "storm":
            # 1. 灰暗滤镜
            # 强度越高越黑 (0, 0, 50) 深蓝灰
            alpha = int(100 * self.intensity)
            self.filter_surf.fill((20, 30, 50, alpha))
            screen.blit(self.filter_surf, (0, 0))
            
            rain_color = (200, 200, 255, int(150 * self.intensity))
            for r in self.rain_drops:
                start = (r[0], r[1])
                # end = start - velocity * length_factor
                # 速度是 (3, speed)
                end = (r[0] - 3, r[1] - r[3]) # 拖尾在左上
                pygame.draw.line(screen, (200, 200, 255), start, end, 1)

            # 3. 绘制波纹 (世界坐标 -> 屏幕坐标)
            for rip in self.ripples:
                # 转换坐标
                sx = int((rip[0] - offset.x) * zoom)
                sy = int((rip[1] - offset.y) * zoom)
                sr = int(rip[2] * zoom)
                
                if sr > 0:
                    alpha = rip[3]
                    if alpha > 20:
                        c_val = min(255, alpha + 40)
                        color = (c_val, c_val, 255)
                        pygame.draw.circle(screen, color, (sx, sy), sr, 1)
            # 4. 雷电闪光 (全屏白)
            if self.flash_alpha > 0:
                s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                s.fill((255, 255, 255, int(self.flash_alpha)))
                screen.blit(s, (0,0), special_flags=pygame.BLEND_RGBA_ADD)


class WaterFX:
    """多边形水域的波纹与海浪动画层。

    数据源：game.lakes 中 from_terrain 且带 poly 的条目（编辑器画的水域）。
    贴地层渲染：draw_world 在背景之后、建筑之前调用 update_and_draw。
    """
    MAX_RIPPLES = 90   # 波纹粒子上限（性能保护）

    def __init__(self):
        self.ripples = []   # [x, y, r, alpha]（世界坐标）
        self.t = 0          # 帧计数（波浪相位/生成节流）

    @staticmethod
    def _waters(lakes):
        # 只有真水参与波纹/海浪：waves=False 的水域（编辑器关闭波纹）与
        # mountain/cliff 等阻挡型条目（同在 lakes 容器里）都不生成
        return [l for l in (lakes or [])
                if isinstance(l, dict) and l.get('from_terrain') and l.get('poly')
                and l.get('type', 'water') == 'water'
                and l.get('waves', True)]

    def update_and_draw(self, screen, camera_offset, zoom, lakes, islands=None):
        waters = self._waters(lakes)
        if not waters:
            self.ripples = []
            return
        self.t += 1
        vx, vy = camera_offset.x, camera_offset.y
        view = pygame.Rect(int(vx), int(vy), max(1, int(SCREEN_WIDTH / zoom)),
                           max(1, int(SCREEN_HEIGHT / zoom)))

        from maps.map_data import point_in_poly

        # 0. 陆地阻挡（岛屿 Rect / 地形 land dict）——波纹与海浪线都不得落在陆地上
        blockers = []
        for i in (islands or []):
            if isinstance(i, pygame.Rect):
                blockers.append((i, None))
            elif isinstance(i, dict) and i.get('poly') and isinstance(i.get('rect'), pygame.Rect):
                blockers.append((i['rect'], i['poly']))

        def _hit_land(blk, x, y):
            for rc, poly in blk:
                if rc.collidepoint(x, y) and (poly is None or point_in_poly(poly, x, y)):
                    return True
            return False

        # 1. 波纹生成：每 5 帧在视口内随机水域里找一点（bbox 随机采样 + 射线精测 + 避陆地）
        if self.t % 5 == 0 and len(self.ripples) < self.MAX_RIPPLES:
            w = random.choice(waters)
            r = w['rect']
            if r.colliderect(view):
                blk_w = [b for b in blockers if b[0].colliderect(r)]
                for _ in range(6):
                    px = random.uniform(r.x, r.right)
                    py = random.uniform(r.y, r.bottom)
                    if point_in_poly(w['poly'], px, py) and not _hit_land(blk_w, px, py):
                        self.ripples.append([px, py, 2.0, 110.0])
                        break

        # 2. 波纹扩散绘制（1px 亮圈，扩散+淡出）
        alive = []
        for rp in self.ripples:
            rp[2] += 0.35
            rp[3] -= 2.2
            if rp[3] <= 0:
                continue
            alive.append(rp)
            sx = (rp[0] - vx) * zoom
            sy = (rp[1] - vy) * zoom
            if -12 < sx < SCREEN_WIDTH + 12 and -12 < sy < SCREEN_HEIGHT + 12:
                pygame.draw.circle(screen, (222, 238, 248),
                                   (int(sx), int(sy)), max(1, int(rp[2] * zoom)), 1)
        self.ripples = alive[:self.MAX_RIPPLES]

        # 3. 海浪线：每条水域两条缓慢推移的正弦亮线，点采样裁剪进多边形内且避开陆地
        phase = self.t * 0.008
        for w in waters:
            r = w['rect']
            if not r.colliderect(view):
                continue
            pts = w['poly']
            blk_w = [b for b in blockers if b[0].colliderect(r)]
            # 采样间距 ~24px：足够细，小岛也能截断线段
            steps = max(26, min(160, int(r.w / 24)))
            amp = 5.0 + (r.h % 7)
            for k in range(2):
                base_y = r.y + ((self.t * 0.35 + k * r.h / 2.0) % r.h)
                seg = []
                # 视口范围（世界坐标，左右各留 8px 余量）——大水域只画屏内段
                vx_min, vx_max = vx - 8, vx + SCREEN_WIDTH / zoom + 8
                vy_min, vy_max = vy - 8, vy + SCREEN_HEIGHT / zoom + 8
                for i in range(steps + 1):
                    x = r.x + r.w * i / steps
                    y = base_y + math.sin(x * 0.01 + phase + k * 2.1) * amp
                    if not (vx_min <= x <= vx_max and vy_min <= y <= vy_max):
                        if len(seg) >= 2:
                            self._draw_wave(screen, seg, vx, vy, zoom)
                        seg = []
                        continue
                    if point_in_poly(pts, x, y) and not _hit_land(blk_w, x, y):
                        seg.append((x, y))
                    elif len(seg) >= 2:
                        self._draw_wave(screen, seg, vx, vy, zoom)
                        seg = []
                if len(seg) >= 2:
                    self._draw_wave(screen, seg, vx, vy, zoom)

    @staticmethod
    def _draw_wave(screen, seg, vx, vy, zoom):
        spts = [((x - vx) * zoom, (y - vy) * zoom) for x, y in seg]
        pygame.draw.lines(screen, (200, 224, 240), False, spts, 1)