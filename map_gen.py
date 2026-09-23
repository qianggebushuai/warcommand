import pygame
import random
import math
import os

# 初始化 Pygame
pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)

# =============================================================================
#  配置与常量
# =============================================================================
MAP_WIDTH = 12000
MAP_HEIGHT = 12000

class Colors:
    OCEAN_DEEP    = (20, 40, 60)
    OCEAN_SHALLOW = (60, 100, 110)
    SAND_WET      = (160, 140, 110)
    SAND_DRY      = (210, 190, 150)
    CLIFF_BASE    = (100, 40, 30)
    CLIFF_FACE    = (160, 70, 50)
    GRASS_BASE    = (80, 100, 60)
    GRASS_DRY     = (120, 130, 80)
    CONCRETE_DARK = (60, 60, 65)
    CONCRETE_LIGHT= (100, 100, 105)
    RUST          = (80, 40, 20)

# =============================================================================
#  辅助类
# =============================================================================
class Vec2:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    def __add__(self, other):
        return Vec2(self.x + other.x, self.y + other.y)
    def __sub__(self, other):
        return Vec2(self.x - other.x, self.y - other.y)
    def __mul__(self, scalar):
        return Vec2(self.x * scalar, self.y * scalar)
    def length(self):
        return math.sqrt(self.x**2 + self.y**2)
    def lerp(self, other, t):
        return Vec2(self.x + (other.x - self.x)*t, self.y + (other.y - self.y)*t)

class NoiseGenerator:
    def __init__(self, seed, rng):
        self.rng = rng
        self.offsets = [self.rng.random() * 100 for _ in range(5)]

    def get_value(self, angle):
        val = 0
        val += math.sin(angle * 3 + self.offsets[0]) * 0.5
        val += math.sin(angle * 7 + self.offsets[1]) * 0.25
        val += math.sin(angle * 15 + self.offsets[2]) * 0.1
        return 1.0 + val * 0.3

# =============================================================================
#  地图生成器
# =============================================================================
class MapGenerator:
    def __init__(self):
        self.width = MAP_WIDTH
        self.height = MAP_HEIGHT
        self.bg_surface = pygame.Surface((self.width, self.height))
        self.rng = random.Random()
        self.rng.seed(12345) # 固定种子
        
        # 数据存储
        self.cliff_islands = []
        self.sand_islands = []
        self.walls = []
        self.shore_points = [] # 仅作逻辑保留

    def generate(self):
        print(f"Generating Heligoland Bight ({self.width}x{self.height})...")
        self.bg_surface.fill(Colors.OCEAN_DEEP)
        
        center = Vec2(self.width//2 - 1000, self.height//2)
        
        # 1. 生成数据
        # A. 主岛
        self._generate_cliff_island(center, 2500, roughness=200, shape_type="triangle")
        
        # B. 沙丘岛
        dune_pos = center + Vec2(3500, 500)
        self._generate_sand_island(dune_pos, 1500, 400)
        
        # C. 卫星岛
        reef_configs = [
            (-2800, -2200, 400), (-3800, -1200, 300), (-1500, -3200, 350),
            (-2500, 2500, 450), (-1200, 3500, 300),
            (3200, -1800, 400), (4500, -1000, 300),
            (2800, 2800, 500), (4200, 2200, 350),
            (800, 2500, 250),
            (5500, 500, 300), (-4500, 0, 300),
            (0, -4200, 250), (0, 4200, 250)
        ]
        for off_x, off_y, radius in reef_configs:
            pos = center + Vec2(off_x, off_y)
            self._generate_cliff_island(pos, radius, roughness=40, shape_type="circle")

        # D. 防波堤
        start = center + Vec2(-500, 2000)
        end = center + Vec2(1500, 2000)
        self.walls.append({'start': start, 'end': end, 'width': 150})
        
        start = center + Vec2(1500, 2000)
        end = center + Vec2(1500, 1200)
        self.walls.append({'start': start, 'end': end, 'width': 150})

        # 2. 绘制纹理
        self._draw_texture()
        
        print("Generation Done.")

    def _generate_cliff_island(self, center, avg_radius, roughness, shape_type):
        noise = NoiseGenerator(self.rng.randint(0, 9999), self.rng)
        points = []
        num_pts = 60
        
        for i in range(num_pts):
            angle = (i / num_pts) * 6.28
            n_val = noise.get_value(angle)
            r = avg_radius * n_val
            if shape_type == "triangle":
                r *= (1 + 0.3 * math.sin(angle * 3))
            
            px = center.x + math.cos(angle) * r
            py = center.y + math.sin(angle) * r
            points.append((px, py))
            
        self.cliff_islands.append({'poly': points, 'center': center, 'radius': avg_radius})

    def _generate_sand_island(self, center, width, height):
        angle = self.rng.uniform(-0.5, 0.5)
        points = []
        for i in range(40):
            a = (i/40) * 6.28
            rx = width/2 * (1 + self.rng.uniform(-0.1, 0.1))
            ry = height/2 * (1 + self.rng.uniform(-0.1, 0.1))
            lx = math.cos(a) * rx
            ly = math.sin(a) * ry
            wx = lx * math.cos(angle) - ly * math.sin(angle) + center.x
            wy = lx * math.sin(angle) + ly * math.cos(angle) + center.y
            points.append((wx, wy))
        self.sand_islands.append(points)

    def _draw_texture(self):
        surf = self.bg_surface
        
        # 1. 海洋细节
        print("Drawing Ocean Details...")
        for _ in range(5000):
            x = self.rng.randint(0, self.width)
            y = self.rng.randint(0, self.height)
            rad = self.rng.randint(100, 300)
            color = (
                Colors.OCEAN_DEEP[0] + self.rng.randint(0, 10),
                Colors.OCEAN_DEEP[1] + self.rng.randint(0, 10),
                Colors.OCEAN_DEEP[2] + self.rng.randint(0, 10)
            )
            s = pygame.Surface((rad*2, rad*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*color, 20), (rad, rad), rad)
            surf.blit(s, (x-rad, y-rad))

        # 2. 悬崖岛
        print("Drawing Cliff Islands...")
        for island in self.cliff_islands:
            poly = island['poly']
            center = island['center']
            radius = island['radius']
            
            # 浅滩
            pygame.draw.polygon(surf, Colors.OCEAN_SHALLOW, poly, width=120)
            
            # 阴影
            shadow_poly = [(p[0]+30, p[1]+30) for p in poly]
            pygame.draw.polygon(surf, (0,0,0), shadow_poly)
            
            # 底座
            pygame.draw.polygon(surf, Colors.CLIFF_BASE, poly)
            
            # 顶部平面
            inner_poly = [((p[0]-center.x)*0.95+center.x, (p[1]-center.y)*0.95+center.y) for p in poly]
            pygame.draw.polygon(surf, Colors.CLIFF_FACE, inner_poly)
            
            # 草地
            top_poly = [((p[0]-center.x)*0.9+center.x, (p[1]-center.y)*0.9+center.y) for p in poly]
            pygame.draw.polygon(surf, Colors.GRASS_BASE, top_poly)
            
            # 植被 (小树)
            min_x, max_x = min(p[0] for p in top_poly), max(p[0] for p in top_poly)
            min_y, max_y = min(p[1] for p in top_poly), max(p[1] for p in top_poly)
            num_trees = int(radius * 0.8)
            
            for _ in range(num_trees):
                tx = self.rng.randint(int(min_x), int(max_x))
                ty = self.rng.randint(int(min_y), int(max_y))
                if self._point_in_poly(tx, ty, top_poly):
                    self._draw_pine_tree(surf, tx, ty)
            
            # 残骸
            self._generate_wrecks(surf, center, radius + 150)

        # 3. 沙岛
        print("Drawing Sand Islands...")
        for poly in self.sand_islands:
            pygame.draw.polygon(surf, Colors.SAND_WET, poly)
            cx = sum(p[0] for p in poly)/len(poly)
            cy = sum(p[1] for p in poly)/len(poly)
            center = Vec2(cx, cy)
            
            inner_poly = [((p[0]-cx)*0.8+cx, (p[1]-cy)*0.8+cy) for p in poly]
            pygame.draw.polygon(surf, Colors.SAND_DRY, inner_poly)
            
            r_approx = max(p[0] for p in poly) - min(p[0] for p in poly)
            self._generate_wrecks(surf, center, r_approx/2 + 100)

        # 4. 防波堤
        print("Drawing Breakwaters...")
        for wall in self.walls:
            s = (wall['start'].x, wall['start'].y)
            e = (wall['end'].x, wall['end'].y)
            wid = wall['width']
            pygame.draw.line(surf, Colors.CONCRETE_DARK, s, e, wid)
            pygame.draw.line(surf, Colors.CONCRETE_LIGHT, s, e, int(wid*0.8))

    def _draw_pine_tree(self, surf, x, y):
        color = (
            self.rng.randint(20, 40),
            self.rng.randint(60, 90),
            self.rng.randint(20, 40)
        )
        r = self.rng.randint(8, 15)
        pygame.draw.circle(surf, (0,0,0,100), (x+5, y+5), r)
        pygame.draw.circle(surf, color, (x, y), r)
        c2 = (min(255, color[0]+20), min(255, color[1]+20), min(255, color[2]+20))
        pygame.draw.circle(surf, c2, (x, y-3), r-3)
        c3 = (min(255, color[0]+40), min(255, color[1]+40), min(255, color[2]+40))
        pygame.draw.circle(surf, c3, (x, y-5), r-6)

    def _generate_wrecks(self, surf, center, radius):
        count = self.rng.randint(5, 15)
        for _ in range(count):
            angle = self.rng.uniform(0, 6.28)
            dist = radius + self.rng.randint(0, 200)
            wx = center.x + math.cos(angle) * dist
            wy = center.y + math.sin(angle) * dist
            
            type_id = self.rng.randint(0, 2)
            if type_id == 0: 
                w, h = self.rng.randint(10, 30), self.rng.randint(4, 8)
                pygame.draw.line(surf, (80, 60, 40), (wx, wy), (wx+w, wy+h), 3)
            elif type_id == 1: 
                w, h = self.rng.randint(30, 60), self.rng.randint(15, 25)
                pygame.draw.ellipse(surf, Colors.RUST, (wx, wy, w, h))
            elif type_id == 2:
                r = self.rng.randint(20, 50)
                s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
                pygame.draw.circle(s, (0, 0, 0, 100), (r, r), r)
                surf.blit(s, (wx-r, wy-r))

    def _point_in_poly(self, x, y, poly):
        n = len(poly)
        inside = False
        p1x, p1y = poly[0]
        for i in range(n + 1):
            p2x, p2y = poly[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def save(self, filename="map_island.png"):
        print(f"Saving to {filename}...")
        pygame.image.save(self.bg_surface, filename)
        print("Done!")

if __name__ == "__main__":
    gen = MapGenerator()
    gen.generate()
    gen.save()
    pygame.quit()