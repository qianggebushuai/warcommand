import pygame
import random
import math
import os
import sys
import json
from core.settings import *
from core.base_classes import *
from units import * # 确保引入了新单位
from core.utils import resource_path, get_font
try:
    from pygame.math import Vector2 as vec
except ImportError:
    pass

# =============================================================================
#  辅助工具类 (Utils)
# =============================================================================
class NoiseGenerator:
    """支持固定随机源的噪声生成器"""
    def __init__(self, seed, rng_instance):
        self.rng = rng_instance # 使用传入的随机实例
        # 保存当前的随机状态，以免影响其他
        # 但其实用独立的 rng 实例最安全
        
        # 生成几个频率的相位偏移
        self.offsets = [self.rng.random() * 100 for _ in range(5)]

    def get_value(self, angle):
        val = 0
        val += math.sin(angle * 3 + self.offsets[0]) * 0.5
        val += math.sin(angle * 7 + self.offsets[1]) * 0.25
        val += math.sin(angle * 15 + self.offsets[2]) * 0.1
        return 1.0 + val * 0.3
# =============================================================================
#  特效管理器 (Effects)
# =============================================================================
class WaveManager:
    """管理海岸线的海浪拍打效果"""
    def __init__(self):
        self.waves = [] # list of [x, y, radius, life, max_life]

    def add_wave(self, pos):
        self.waves.append([pos.x, pos.y, 10, 60, 60])

    def update(self):
        for w in self.waves:
            w[2] += 0.5 # 半径扩大
            w[3] -= 1   # 生命递减
        self.waves = [w for w in self.waves if w[3] > 0]

    def draw(self, surface, offset):
        for w in self.waves:
            x, y, r, life, max_life = w
            screen_x = x - offset.x
            screen_y = y - offset.y
            
            # 屏幕剔除
            if screen_x < -50 or screen_x > surface.get_width() + 50 or \
               screen_y < -50 or screen_y > surface.get_height() + 50: continue

            alpha = int((life / max_life) * 150)
            s = pygame.Surface((int(r*2), int(r*2)), pygame.SRCALPHA)
            pygame.draw.circle(s, (*Colors.OCEAN_FOAM, alpha), (int(r), int(r)), int(r), 2)
            surface.blit(s, (screen_x-r, screen_y-r))
class Colors:
    # --- 地面 ---
    MUD_BASE    = (30, 26, 22)      # 低谷：深色泥浆
    MUD_WET     = (20, 18, 16)      # 湿地/弹坑底
    
    # --- 山丘 (高地颜色渐变) ---
    HILL_L1     = (45, 40, 35)      # 山脚
    HILL_L2     = (60, 55, 50)      # 山腰
    HILL_TOP    = (75, 70, 65)      # 山顶 (干燥、石质)
    HILL_SHADOW = (15, 10, 5)       # 山体投影/断崖阴影
    
    # --- 细节 ---
    SCORCHED    = (10, 10, 10)      # 焦痕
    TRENCH_DIRT = (50, 45, 40)      # 战壕翻出的土
    TRENCH_FLOOR= (15, 12, 10)      # 战壕底
    WIRE_RUST   = (55, 30, 20)      # 铁丝网
    WATER_TOXIC = (25, 35, 25)      # 毒水
    EMBER       = (255, 80, 10)     # 火星

    SCORCHED    = (10, 10, 10)      # 焦黑
    EMBER_DARK  = (100, 20, 0)      # 暗红余烬
    EMBER_BRIGHT= (255, 100, 30)    # 明亮火光
    EMBER_GLOW  = (255, 180, 50)    # 核心高光

    OCEAN_DEEP    = (20, 40, 60)    # 深海
    OCEAN_MID     = (30, 60, 80)    # 浅海
    OCEAN_SHALLOW = (60, 100, 110)  # 岸边浅滩
    OCEAN_FOAM    = (200, 220, 230) # 浪花

    # --- 岛屿 (红色砂岩) ---
    SAND_WET      = (160, 140, 110) # 湿沙滩
    SAND_DRY      = (210, 190, 150) # 干沙滩
    CLIFF_BASE    = (100, 40, 30)   # 悬崖底部 (深红)
    CLIFF_FACE    = (160, 70, 50)   # 悬崖立面 (鲜红砂岩)
    CLIFF_TOP     = (180, 90, 60)   # 悬崖顶部边缘
    
    # --- 植被 (贫瘠高地) ---
    GRASS_BASE    = (80, 100, 60)   # 基础草地
    GRASS_DRY     = (120, 130, 80)  # 枯草
    ROCK_GREY     = (90, 90, 95)    # 礁石

    # --- 人工建筑 (德国海军风格) ---
    CONCRETE_DARK = (60, 60, 65)    # 防波堤/碉堡
    CONCRETE_LIGHT= (100, 100, 105) # 顶部
    RUST          = (80, 40, 20)    # 锈迹

# =============================================================================
#  地面矿脉 (Ore Patch) — 红警式真实矿藏
# =============================================================================
# ---------------------------------------------------------------------------
# 多边形地形辅助（布局 JSON "terrain" 键）：水域/陆地/斜坡多边形的判定与序列化
# ---------------------------------------------------------------------------
# 地形多边形类型 → 视觉烘焙颜色（RGBA，bg_surface 烘焙与编辑器叠加共用）
TERRAIN_POLY_COLORS = {
    "water": (50, 110, 185, 150),   # 水域：半透明蓝
    "land":  (196, 178, 118, 160),  # 陆地（水中岛/填陆）：沙色
    "slope": (255, 70, 50, 100),    # 斜坡（减速区）：红
    "cliff": (104, 94, 84, 235),    # 悬崖：深岩色近实心（仅空中单位可通行）
}


def point_in_poly(pts, x, y):
    """射线法：点是否在多边形内。pts 为 [(x, y), ...]（至少 3 顶点）。"""
    inside = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i][0], pts[i][1]
        x2, y2 = pts[(i + 1) % n][0], pts[(i + 1) % n][1]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                inside = not inside
    return inside


def poly_bbox(pts):
    """多边形包围盒（供粗测与运行时 Rect 判定容器复用）。"""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return pygame.Rect(int(min(xs)), int(min(ys)),
                       int(max(xs) - min(xs)) + 1, int(max(ys) - min(ys)) + 1)


def _shape_contains(shape, x, y):
    """统一包含测试：Rect 直接测；dict{rect, poly?} 先包围盒粗测再多边形精测。"""
    if isinstance(shape, dict):
        r = shape.get('rect')
        if r is None or not r.collidepoint(int(x), int(y)):
            return False
        poly = shape.get('poly')
        return point_in_poly(poly, x, y) if poly else True
    return shape.collidepoint(int(x), int(y))


def lake_contains(lake, x, y):
    """水域条目包含测试（兼容旧 Rect 列表 / dict{rect,...} / poly 条目）。"""
    return _shape_contains(lake, x, y)


def island_contains(isle, x, y):
    """岛屿条目包含测试（同上兼容）。"""
    return _shape_contains(isle, x, y)


def slope_contains(sl, x, y):
    """斜坡条目包含测试（同上兼容）。"""
    return _shape_contains(sl, x, y)


def water_color_at(lakes, x, y):
    """世界坐标 (x,y) 所处多边形水域的 RGB 颜色；不在任何 poly 水域返回 None。

    只认 from_terrain 的 water 条目（编辑器画的水域，带自定义 color 字段），
    官方矩形湖无 poly 不参与。浪花/波纹等特效用它取色，alpha 由特效自定
    （浪花 alpha 固定 1 不透明，不继承水域透明度）。
    """
    for lake in (lakes or []):
        if not isinstance(lake, dict):
            continue
        if lake.get('type') != 'water' or not lake.get('from_terrain'):
            continue
        if _shape_contains(lake, x, y):
            c = lake.get('color') or TERRAIN_POLY_COLORS.get('water')
            if c:
                return (int(c[0]), int(c[1]), int(c[2]))
    return None


class OrePatch:
    """地面真实矿脉：可被采矿车采集耗尽、随后缓慢再生；矿井架常驻，矿石堆随储量萎缩。"""
    BASE_SIZE = 120  # 预渲染底图边长（世界像素）

    def __init__(self, game, pos, amount=None, max_amount=None):
        self.game = game
        self.pos = vec(pos)
        self.max_amount = float(max_amount if max_amount is not None else ORE_PATCH_MAX_AMOUNT)
        self.amount = float(amount if amount is not None else self.max_amount)
        self.radius = 38
        self._last_tick = pygame.time.get_ticks()
        # 矿石堆布局：专属 RNG 预生成（不扰动全局随机状态），萎缩时同步缩放不跳变
        cr = random.Random(int(self.pos.x) * 31 + int(self.pos.y) * 7 + 13)
        self._crystals = []  # (堆内偏移, size, 顶点数, 旋转, 堆中心偏移)
        for side in (vec(-34, 4), vec(34, 4)):  # 左右两堆
            for _ in range(cr.randint(3, 4)):
                ang = cr.uniform(0, math.tau)
                dist = cr.uniform(0, 14)
                self._crystals.append((
                    vec(math.cos(ang) * dist, math.sin(ang) * dist * 0.55),
                    cr.uniform(7, 15),
                    cr.randint(3, 4),
                    cr.uniform(0, math.tau),
                    side,
                ))
        self._sparkle_t = cr.uniform(0, 100)
        self._base_surf = self._build_base(cr)
        self._scaled_cache = {}  # zoom 档位 → 缩放后的结构图（只读 blit，禁原地改）

    def _build_base(self, cr):
        """预渲染矿井结构：土坑 + 井口 + 木质井架 + 矿车轨道（不随储量变化）"""
        S = self.BASE_SIZE
        surf = pygame.Surface((S, S), pygame.SRCALPHA)
        cx, cy = S // 2, 72  # 坑中心（下移，给井架留立面高度）

        # 1) 多层土坑（边缘→内部渐深）
        for rx, ry, col in ((52, 30, (86, 68, 48)), (46, 26, (66, 52, 37)),
                            (38, 21, (50, 39, 28)), (30, 16, (38, 30, 22))):
            r = pygame.Rect(0, 0, rx * 2, ry * 2)
            r.center = (cx, cy)
            pygame.draw.ellipse(surf, col, r)

        # 2) 坑沿碎石
        for _ in range(16):
            a = cr.uniform(0, math.tau)
            d = cr.uniform(40, 52)
            x = cx + math.cos(a) * d
            y = cy + math.sin(a) * d * 0.55
            rad = cr.randint(2, 4)
            col = cr.choice([(96, 78, 56), (112, 92, 66), (74, 60, 44)])
            pygame.draw.circle(surf, col, (int(x), int(y)), rad)

        # 3) 矿车轨道（井口向前延伸）
        for ty in range(cy + 8, S - 4, 9):
            pygame.draw.rect(surf, (66, 46, 30), (cx - 11, ty, 22, 3))  # 枕木
        pygame.draw.line(surf, (120, 122, 128), (cx - 6, cy + 6), (cx - 6, S - 6), 2)
        pygame.draw.line(surf, (120, 122, 128), (cx + 6, cy + 6), (cx + 6, S - 6), 2)

        # 4) 井口（深黑方洞 + 木框）
        pit = pygame.Rect(0, 0, 30, 20)
        pit.center = (cx, cy - 4)
        pygame.draw.rect(surf, (14, 11, 9), pit)
        pygame.draw.rect(surf, (104, 70, 38), pit, 3)          # 木框
        pygame.draw.rect(surf, (70, 46, 25), pit.inflate(6, 6), 1)
        for px, py in (pit.topleft, pit.topright, pit.bottomleft, pit.bottomright):
            pygame.draw.circle(surf, (60, 40, 22), (px, py), 3)  # 角桩

        # 5) A 字形木质井架（跨在井口上方）
        top = (cx, cy - 66)
        leg_l = (cx - 24, cy + 8)
        leg_r = (cx + 24, cy + 8)
        pygame.draw.line(surf, (96, 64, 34), leg_l, top, 5)
        pygame.draw.line(surf, (86, 56, 30), leg_r, top, 5)
        pygame.draw.line(surf, (110, 76, 42), (cx - 12, cy - 26), (cx + 12, cy - 26), 3)  # 中横梁
        pygame.draw.line(surf, (110, 76, 42), (cx - 17, cy - 8), (cx + 17, cy - 8), 3)   # 下横梁
        # 斜撑
        pygame.draw.line(surf, (78, 52, 28), (cx - 8, cy - 4), top, 2)
        pygame.draw.line(surf, (78, 52, 28), (cx + 8, cy - 4), top, 2)
        # 顶部滑轮
        pygame.draw.circle(surf, (150, 152, 158), top, 5)
        pygame.draw.circle(surf, (60, 60, 64), top, 5, 1)
        pygame.draw.circle(surf, (40, 40, 44), top, 2)
        # 吊绳（滑轮 → 井口）
        pygame.draw.line(surf, (50, 38, 26), top, (cx, cy - 8), 1)

        # 6) 两侧木围栏短桩
        for sx in (-1, 1):
            bx = cx + sx * 44
            pygame.draw.line(surf, (100, 68, 36), (bx, cy - 6), (bx, cy + 14), 3)
            pygame.draw.line(surf, (88, 58, 30), (bx, cy - 2), (bx - sx * 14, cy - 2), 2)
        return surf

    @property
    def ratio(self):
        return max(0.0, min(1.0, self.amount / self.max_amount))

    # 储量数字标签的字体缓存（类级共享，get_font 无内部缓存不能每帧新建）
    _font_cache = {}

    def _draw_amount_label(self, surface, cx, cy, zoom):
        """矿井上方储量数字标签（金→橙→灰 随储量变色）"""
        size = int(scale(13, zoom))
        if size < 8:
            return
        font = self._font_cache.get(size)
        if font is None:
            font = get_font(size, bold=True)
            self._font_cache[size] = font
        amt = int(self.amount)
        text = f"{amt}"
        ratio = self.ratio
        if ratio > 0.5:
            col = (255, 205, 70)
        elif ratio > 0.1:
            col = (235, 150, 60)
        else:
            col = (165, 165, 165)
        label = font.render(text, True, col, (20, 16, 12))
        lw, lh = label.get_size()
        lx = int(cx - lw / 2)
        ly = int(cy - scale(80, zoom))
        surface.blit(label, (lx, ly))

    def update(self):
        """缓慢再生：按真实时间差计算，天然防同帧双计"""
        now = pygame.time.get_ticks()
        dt = (now - self._last_tick) / 1000.0
        self._last_tick = now
        if dt > 0 and self.amount < self.max_amount:
            self.amount = min(self.max_amount, self.amount + dt * ORE_PATCH_REGEN_PER_S)

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        _cm = 160 * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        cx, cy = screen_pos
        ratio = self.ratio

        # 1) 矿井结构层：zoom 档位缓存缩放（只读 blit）
        zk = round(zoom, 1)
        base = self._scaled_cache.get(zk)
        if base is None:
            t = max(4, int(scale(self.BASE_SIZE, zoom)))
            if t < self.BASE_SIZE:
                base = pygame.transform.smoothscale(self._base_surf, (t, t))
            else:
                base = pygame.transform.scale(self._base_surf, (t, t))
            self._scaled_cache[zk] = base
        surface.blit(base, (int(cx - base.get_width() / 2), int(cy - base.get_height() / 2)))

        # 2) 金色矿石堆（左右两堆，随储量萎缩；井架常驻）
        if ratio > 0.02:
            t_now = pygame.time.get_ticks() / 1000.0
            n_visible = max(1, int(len(self._crystals) * (0.35 + 0.65 * ratio)))
            for i, (off, size, sides, rot, clu) in enumerate(self._crystals[:n_visible]):
                s = scale(size * (0.25 + 0.75 * ratio), zoom)
                if s < 1:
                    continue
                px = cx + scale(clu.x + off.x, zoom)
                py = cy + scale(clu.y + off.y, zoom)
                pts = []
                for k in range(sides):
                    a = rot + math.tau * k / sides
                    rr = s if k % 2 == 0 else s * 0.45
                    pts.append((px + math.cos(a) * rr, py + math.sin(a) * rr * 0.75))
                shade = 1.0 - 0.25 * (i % 3) / 2.0
                col = (int(255 * shade), int(200 * shade), int(60 * shade))
                pygame.draw.polygon(surface, col, pts)
                pygame.draw.polygon(surface, (120, 90, 20), pts, 1)
            # 富矿：井口金边 + 滑轮处闪光
            if ratio > 0.3:
                gw = max(1, int(scale(2, zoom)))
                pit_rect = pygame.Rect(0, 0, max(3, int(scale(30, zoom))), max(2, int(scale(20, zoom))))
                pit_rect.center = (int(cx), int(cy - scale(8, zoom)))
                pygame.draw.rect(surface, (255, 210, 90), pit_rect, gw)
                tw = (math.sin(t_now * 3.0 + self._sparkle_t) + 1) / 2
                if tw > 0.7:
                    g = scale(5, zoom)
                    pygame.draw.circle(surface, (255, 255, 210),
                                       (int(cx), int(cy - scale(62, zoom))), max(1, int(g)))

        # 3) 储量数字标签（UI 标记）
        self._draw_amount_label(surface, cx, cy, zoom)


# =============================================================================
#  地图布局编辑器支持：可摆放建筑注册表 + 布局 JSON 存读
# =============================================================================
LAYOUT_BUILDING_TYPES = {
    # name: {cls, team: 构造是否需要 team 参数, attr: 需要序列化的附加参数属性}
    "OilDerrick":      {"cls": OilDerrick,      "team": False},
    "TeslaTower":      {"cls": TeslaTower,      "team": False},
    "Skyscraper":      {"cls": Skyscraper,      "team": False},
    "CivilianHouse":   {"cls": CivilianHouse,   "team": False},
    "EuropeanChurch":  {"cls": EuropeanChurch,  "team": False},
    "HalfTimberHouse": {"cls": HalfTimberHouse, "team": False},
    "ClockTower":      {"cls": ClockTower,      "team": False},
    "Windmill":        {"cls": Windmill,        "team": False},
    "CommStation":     {"cls": CommStation,     "team": False},
    "EMPGenerator":    {"cls": EMPGenerator,    "team": False},
    "AncientTemple":   {"cls": AncientTemple,   "team": False},
    "Lighthouse":      {"cls": Lighthouse,      "team": False},
    "Bastion":         {"cls": Bastion,         "team": False},
    "Bridge":          {"cls": Bridge,          "team": False, "attrs": ["orientation", "length"]},
    "FactoryBuilding": {"cls": FactoryBuilding, "team": True},
    "PowerPlant":      {"cls": PowerPlant,      "team": True},
    "RadarBuilding":   {"cls": RadarBuilding,   "team": True},
    "Airfield":        {"cls": Airfield,        "team": True},
    "ResearchCenter":  {"cls": ResearchCenter,  "team": True},
    "TechCenter":      {"cls": TechCenter,      "team": True},
    "AntiAirTurret":   {"cls": AntiAirTurret,   "team": True},
    "CoastalGun":      {"cls": CoastalGun,      "team": True},
}

def _map_layout_path(map_name):
    """布局 JSON 路径：config/map_layouts/<地图类名>.json
    冻结环境优先 exe 旁目录（与存档惯例一致，部署自定义布局无需重打包）"""
    if getattr(sys, 'frozen', False):
        p = os.path.join(os.path.dirname(sys.executable), "config", "map_layouts", f"{map_name}.json")
        if os.path.exists(p):
            return p
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "config", "map_layouts", f"{map_name}.json")


class GameMap:
    def __init__(self, game):
        self.dlc="无"
        self.game = game
        self.name = ""
        self.description = "No description available." 
        self.location="unknown"# [新增] 加载界面介绍
        self.width = WORLD_WIDTH
        self.height = WORLD_HEIGHT
        self.bg_color = (30, 34, 30)
        self.lakes = [] 
        self.neutral_buildings = []
        self.bases_config = []
        self.ore_patches = []  # 地面矿脉（红警式采集）
        self.bg_surface = None
        self.preview_image = None
        self.max_players = 2
        self.bg_surface = None # [新增] 用于缓存生成好的精细背景
        self.terrain_polys = []  # 地形多边形（编辑器 JSON 覆盖，见 apply_terrain_polys）
        # 特殊单位刷新点（列车/战列舰）：编辑器 JSON special_units 分区覆盖；
        # None=未定义（布局 JSON 无该分区）→ 运行时从硬编码 initial_units 推导默认 spec
        self.special_specs = None
        # 道路背景：编辑器 JSON roads 分区（起终点+宽度，贴地层纹理平铺绘制）
        self.roads = []

        self.music_config = {
            "intro": "intro.mp3",
            "loop": "battle_loop.mp3",
            "final1": "phase1_loop.mp3",             
            "final2": "phase2_loop.mp3",            
            "final3": "final_rush.mp3", 
            "end_win": "victory.mp3",
            "end_lose": "defeat.mp3"
        }
    def generate(self, seed=None, visual_only=False):
        if seed is not None:
            random.seed(seed)
            print(f"[Map] Generating map with seed: {seed}")
        
        self.seed = seed or 0
        self.lakes = []
        self.neutral_buildings = []
        self.bases_config = []
        self.ore_patches = []
        self.slopes = [] 
        self.bg_surface = pygame.Surface((self.width, self.height))
        self.bg_surface.fill(self.bg_color)        
        # [新增] 坡度列表        
        # 在子类调用完逻辑后，生成纹理
        # 注意：子类必须在 super().generate(seed) 后执行自己的逻辑，
        # 最后显式调用 self.generate_background_texture()
    def generate_ore_patches(self):
        """确定性生成地面矿脉：专用 RNG 仅依赖 seed/lakes/bases_config，
        与全局随机状态、visual_only 无关 → 主机/客户端几何完全一致。"""
        self.ore_patches = []
        rng = random.Random((getattr(self, 'seed', 0) or 0) * 100003 + 777)
        margin = 200
        blocked = []
        for lake in self.lakes:
            r = lake.get('rect')
            if r:
                blocked.append(r.inflate(120, 120))
        base_pts = [vec(p) for p in (self.bases_config or [])]

        def valid(x, y):
            if not (margin < x < self.width - margin and margin < y < self.height - margin):
                return False
            for br in blocked:
                if br.collidepoint(x, y):
                    return False
            for bp in base_pts:
                if bp.distance_to(vec(x, y)) < 300:
                    return False
            return True

        n_fields = max(3, int(self.width * self.height / 3500000))
        for _f in range(n_fields):
            center = None
            for _try in range(80):
                x = rng.randint(margin + 100, max(margin + 101, self.width - margin - 100))
                y = rng.randint(margin + 100, max(margin + 101, self.height - margin - 100))
                if valid(x, y):
                    center = vec(x, y)
                    break
            if center is None:
                continue
            for _i in range(rng.randint(3, 5)):
                for _try in range(40):
                    ang = rng.uniform(0, math.tau)
                    dist = rng.uniform(60, 160)
                    px = center.x + math.cos(ang) * dist
                    py = center.y + math.sin(ang) * dist * 0.8
                    if valid(px, py):
                        # 储量随机 2200~4000，钳制到可调的 ORE_PATCH_MAX_AMOUNT（用户调小 MAX 时取满仓）
                        amount = min(ORE_PATCH_MAX_AMOUNT, rng.randint(2200, 4000))
                        self.ore_patches.append(OrePatch(
                            self.game, vec(px, py), amount=amount))
                        break
        print(f"[Map] Ore patches generated: {len(self.ore_patches)}")
        return self.ore_patches
    def generate_background_texture(self):
        """由子类调用，或者在客户端加载时手动调用"""
        print(f"[Map] Baking texture for {self.name}")
        self.bg_surface = pygame.Surface((self.width, self.height))
        self.bg_surface.fill(self.bg_color)

    def draw_background(self, surface, camera_offset, zoom):
        if self.bg_surface:
            # 预缩放缓存：zoom 变化才重建整图缩放，平移时直接取子区域 blit，
            # 消除每帧全屏 transform.scale 的大头开销。
            # 缓存键必须用精确 zoom（不能 round 取档）：取档会让同一档内的缩放
            # 漂移时背景停留在进档时的旧缩放图，而单位/烘焙层用当前 zoom——
            # 缩放和平移时背景与实体错位（0.75 世界层引入后尤其明显）
            scaled = getattr(self, '_bg_cache_surf', None)
            if getattr(self, '_bg_cache_key', None) != zoom or scaled is None:
                sw = max(1, int(self.width * zoom))
                sh = max(1, int(self.height * zoom))
                # 整图缓存上限 90MB，超限（如 zoom>1.2）回退逐帧局部缩放
                if sw * sh * 4 <= 90 * 1024 * 1024:
                    scaled = pygame.transform.scale(self.bg_surface, (sw, sh))
                    self._bg_cache_key = zoom
                    self._bg_cache_surf = scaled
                else:
                    scaled = None
            if scaled is not None:
                sx = int(camera_offset.x * zoom)
                sy = int(camera_offset.y * zoom)
                vw, vh = surface.get_size()
                clip = pygame.Rect(sx, sy, vw, vh).clip(
                    pygame.Rect(0, 0, scaled.get_width(), scaled.get_height()))
                if clip.width > 0 and clip.height > 0:
                    surface.blit(scaled.subsurface(clip), (clip.x - sx, clip.y - sy))
                return

            # 回退路径：超大 zoom 时逐帧缩放可见区域
            # 1. 屏幕视口在世界坐标系中的矩形
            view_w = SCREEN_WIDTH / zoom
            view_h = SCREEN_HEIGHT / zoom
            view_rect = pygame.Rect(camera_offset.x, camera_offset.y, view_w, view_h)
            
            # 2. 地图总矩形
            map_rect = pygame.Rect(0, 0, self.width, self.height)
            
            # 3. 计算交集 (要绘制的源区域)
            source_rect = view_rect.clip(map_rect)
            
            if source_rect.width > 0 and source_rect.height > 0:
                # 4. 计算在屏幕上的目标位置
                # dest_x = (source_x - camera_x) * zoom
                dest_x = (source_rect.x - camera_offset.x) * zoom
                dest_y = (source_rect.y - camera_offset.y) * zoom
                
                # 5. 目标尺寸 (必须取整)
                # [修复] 移除 +2 的冗余，使用精确的 ceil 或 round，避免重叠
                dest_w = int(source_rect.width * zoom) + 1 # +1 防止浮点缝隙，+2太多了
                dest_h = int(source_rect.height * zoom) + 1
                
                # 6. 获取子表面并缩放
                sub = self.bg_surface.subsurface(source_rect)
                scaled = pygame.transform.scale(sub, (dest_w, dest_h))
                
                surface.blit(scaled, (int(dest_x), int(dest_y)))
        else:
            surface.fill(self.bg_color)
    def draw_overlay(self, surface, offset, zoom):
        if not hasattr(self, 'overlay_surface'): return
        view_rect = pygame.Rect(offset.x, offset.y, SCREEN_WIDTH/zoom, SCREEN_HEIGHT/zoom)
        safe_x = max(0, int(view_rect.x))
        safe_y = max(0, int(view_rect.y))
        safe_w = min(self.width - safe_x, int(view_rect.width) + 1)
        safe_h = min(self.height - safe_y, int(view_rect.height) + 1)
        
        if safe_w > 0 and safe_h > 0:
            sub = self.overlay_surface.subsurface((safe_x, safe_y, safe_w, safe_h))
            scaled = pygame.transform.scale(sub, (int(safe_w * zoom), int(safe_h * zoom)))
            screen_x = int((safe_x - offset.x) * zoom)
            screen_y = int((safe_y - offset.y) * zoom)
            surface.blit(scaled, (screen_x, screen_y))    
    def draw_downlay(self, surface, offset):
        pass

    # ---------- 地图布局编辑器：建筑实例化 / 导出 / 保存 / 应用 ----------
    def make_layout_building(self, cls_name, pos, extra=None, team="neutral"):
        """按注册表实例化一个可摆放建筑；失败返回 None"""
        meta = LAYOUT_BUILDING_TYPES.get(cls_name)
        if meta is None:
            return None
        args = []
        if meta.get("team"):
            args.append(team)
        if extra:
            args.extend(extra)
        try:
            return meta["cls"](self.game, vec(pos), *args)
        except Exception as e:
            print(f"[Layout] Failed to create {cls_name} at {pos}: {e}")
            return None

    def apply_terrain_polys(self, game):
        """把 self.terrain_polys 合并进运行时判定容器（幂等：先清旧 poly 条目再追加）。

        water → game.lakes；land → self.islands；slope → self.slopes。
        lakes 是 game 属性（多人 init_level 可能用网络快照覆盖 current_map.lakes），
        覆盖后需再调一次本方法恢复 poly 水域。
        """
        polys = getattr(self, 'terrain_polys', None)
        if not polys:
            return
        # 水域（game 属性）。以地图自身 lakes 为基准并让 game.lakes 指向它：
        # 主游戏构造期 init_level 会往 game.lakes 塞随机矩形湖，而 generate() 之后
        # current_map.lakes 才是画进背景的视觉湖——不对齐会出现"单位走进看得见的
        # 水却判旱地 / 站在旱地却溺水"的错位。synced 客户端路径同理（快照湖=权威）。
        official = getattr(self, 'lakes', None)
        if official is not None:
            lakes = official
            game.lakes = lakes
        else:
            lakes = getattr(game, 'lakes', None)
            if lakes is None:
                lakes = []
                game.lakes = lakes
        lakes[:] = [l for l in lakes
                    if not (isinstance(l, dict) and l.get('from_terrain'))]
        # 岛屿/斜坡（map 属性）
        self.islands = [i for i in getattr(self, 'islands', [])
                        if not (isinstance(i, dict) and i.get('from_terrain'))]
        self.slopes = [s for s in getattr(self, 'slopes', [])
                       if not (isinstance(s, dict) and s.get('from_terrain'))]
        for t in polys:
            entry = {'rect': t['rect'], 'poly': t['poly'], 'from_terrain': True}
            if t['type'] == 'water':
                entry.update({'type': 'water', 'parts': [],
                              'waves': t.get('waves', True)})
                lakes.append(entry)
            elif t['type'] == 'land':
                self.islands.append(entry)
            elif t['type'] == 'slope':
                self.slopes.append(entry)
            elif t['type'] == 'cliff':
                # 悬崖复用 lakes 容器（与地图生成的 'mountain' 阻挡条目同机制）：
                # check_move_validity 只挡地面单位（海军沿崖底水面通行、空中单位不走该判定）
                entry.update({'type': 'cliff'})
                lakes.append(entry)

    def bake_terrain_visual(self):
        """把地形多边形烘焙进背景图（条目可带自定义 color/alpha，无描边）。"""
        if self.bg_surface is None:
            return
        for t in getattr(self, 'terrain_polys', []):
            default = TERRAIN_POLY_COLORS.get(t['type'])
            if default is None:
                continue
            col = t.get('color') or list(default[:3])
            alpha = t.get('alpha', default[3] if len(default) > 3 else 150)
            color = (int(col[0]), int(col[1]), int(col[2]), int(alpha))
            pts = [(int(p[0]), int(p[1])) for p in t['poly']]
            # 只烘多边形外接区域大小的图层，避免整图大 Surface 的开销
            r = t['rect'].inflate(4, 4)
            r.clamp_ip(pygame.Rect(0, 0, self.width, self.height))
            layer = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            local = [(p[0] - r.x, p[1] - r.y) for p in pts]
            pygame.draw.polygon(layer, color, local)
            self.bg_surface.blit(layer, r.topleft)

    def export_layout(self):
        """把当前 neutral_buildings / bases_config 序列化为可保存的 dict"""
        neutrals = []
        for b in self.neutral_buildings:
            name = b.__class__.__name__
            meta = LAYOUT_BUILDING_TYPES.get(name)
            if meta is None:
                continue
            entry = {"cls": name, "x": int(b.pos.x), "y": int(b.pos.y)}
            attrs = meta.get("attrs") or ([meta["attr"]] if meta.get("attr") else [])
            if attrs:
                # 桥的 length 等数值属性按原类型存；orientation 等字符串转 str
                entry["extra"] = [getattr(b, a) if isinstance(getattr(b, a, None), (int, float))
                                  else str(getattr(b, a, "")) for a in attrs]
            neutrals.append(entry)
        return {
            "map": self.__class__.__name__,
            "bases": [{"x": int(vec(p).x), "y": int(vec(p).y)} for p in self.bases_config],
            "neutral": neutrals,
            # 布局矿脉：JSON 存在时替换随机矿脉（空列表 = 不放矿脉也生效）
            "ore": [{"x": int(p.pos.x), "y": int(p.pos.y), "amount": int(p.amount)}
                    for p in getattr(self, 'ore_patches', [])],
            # 地形多边形：水域/陆地/斜坡（空列表/缺键 = 维持地图原地形）
            "terrain": [{"type": t['type'], "points": [[int(p[0]), int(p[1])] for p in t['poly']],
                         "color": list(t.get('color') or TERRAIN_POLY_COLORS.get(t['type'], (50, 110, 185))[:3]),
                         "alpha": int(t.get('alpha', TERRAIN_POLY_COLORS.get(t['type'], (0, 0, 0, 150))[3])),
                         # 水域波纹开关（缺省 True；仅 water 类型写出有意义）
                         "waves": bool(t.get('waves', True))}
                        for t in getattr(self, 'terrain_polys', [])],
            # 特殊单位刷新点：列车/战列舰的 spawn/target（respawn_frames 等于默认值时省略）
            "special_units": self._export_special_units(),
            # 道路背景：起终点+宽度（贴地层纹理平铺；空列表 = 无道路）
            "roads": [{"start": [int(r["start"].x), int(r["start"].y)],
                       "end": [int(r["end"].x), int(r["end"].y)],
                       "width": int(r.get("width", 64))}
                      for r in getattr(self, 'roads', []) if isinstance(r, dict)],
        }

    def _export_special_units(self):
        """把 special_specs 序列化为布局 JSON 的 special_units 分区"""
        out = []
        for s in getattr(self, 'special_specs', None) or []:
            entry = {"type": s["type"],
                     "spawn": [int(vec(s["spawn"]).x), int(vec(s["spawn"]).y)]}
            if s.get("target") is not None:
                entry["target"] = [int(vec(s["target"]).x), int(vec(s["target"]).y)]
            rf = int(s.get("respawn_frames", SPECIAL_RESPAWN_FRAMES))
            if rf != SPECIAL_RESPAWN_FRAMES:
                entry["respawn_frames"] = rf
            if s["type"] == "AC130" and s.get("attack_radius"):
                entry["attack_radius"] = int(s["attack_radius"])
            out.append(entry)
        return out

    def save_layout(self, path=None):
        """保存当前布局到 JSON"""
        if path is None:
            path = _map_layout_path(self.__class__.__name__)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.export_layout(), f, ensure_ascii=False, indent=2)
        print(f"[Layout] Saved: {path}")
        return path

    def apply_layout_override(self):
        """若存在布局 JSON 则覆盖随机中立建筑与出生点（主/客户端都会调用，布局一致）"""
        path = _map_layout_path(self.__class__.__name__)
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[Layout] Failed to load {path}: {e}")
            return False
        self.neutral_buildings = []
        for e in data.get("neutral", []):
            b = self.make_layout_building(e.get("cls", ""), vec(e.get("x", 0), e.get("y", 0)), e.get("extra"))
            if b is not None:
                self.neutral_buildings.append(b)
        bases = data.get("bases", [])
        if bases:
            self.bases_config = [vec(b["x"], b["y"]) for b in bases]
        # 布局矿脉：JSON 带 "ore" 键即接管矿脉生成（含空列表=该图无矿），
        # 游戏端据此跳过 generate_ore_patches 的随机生成；旧布局文件无此键→维持随机
        self.layout_has_ore = "ore" in data
        ores = data.get("ore", [])
        self.ore_patches = [
            OrePatch(self.game, vec(o.get("x", 0), o.get("y", 0)),
                     amount=o.get("amount", ORE_PATCH_MAX_AMOUNT))
            for o in ores
        ]
        # 地形多边形：JSON 带 "terrain" 键即接管该图地形标注（水域/陆地/斜坡），
        # 旧布局文件无此键 → 维持地图原地形
        self.terrain_polys = []
        for t in data.get("terrain", []):
            pts = [(float(p[0]), float(p[1])) for p in t.get("points", [])]
            if len(pts) < 3:
                continue
            entry = {
                "type": t.get("type", "water"),
                "poly": pts,
                "rect": poly_bbox(pts),
            }
            # 自定义颜色/透明度（缺省用 TERRAIN_POLY_COLORS 的类型默认值）
            col = t.get("color")
            if isinstance(col, (list, tuple)) and len(col) == 3:
                entry["color"] = [int(c) for c in col]
            if isinstance(t.get("alpha"), (int, float)):
                entry["alpha"] = max(10, min(230, int(t["alpha"])))
            # 水域波纹开关（缺省 = 有波纹；编辑器可对单个水域关闭）
            if t.get("type") == "water":
                entry["waves"] = bool(t.get("waves", True))
            self.terrain_polys.append(entry)
        # 编辑器水域接管：JSON 画了水域时，地图自带的 'mountain' 阻挡条目若与
        # 编辑器水域相交（中心或任一角落在水域内）则移除——玩家重划的水域以
        # 编辑器为准，否则龙谷这类藏在河道里的装饰岩石/探进河道的谷壁矩形
        # 会挡死海军（山体是 rect-only 全阻挡，优先于一切水域判定）
        water_polys = [e["poly"] for e in self.terrain_polys if e["type"] == "water"]
        if water_polys:
            def _in_editor_water(r):
                probes = [r.center, r.topleft, r.topright, r.bottomleft, r.bottomright]
                return any(lake_contains({"rect": poly_bbox(p), "poly": p}, px, py)
                           for p in water_polys for px, py in probes)
            self.lakes = [l for l in self.lakes
                          if not (isinstance(l, dict) and l.get("type") == "mountain"
                                  and isinstance(l.get("rect"), pygame.Rect)
                                  # 地图边框条（整行/整列的防越界山体）不参与移除
                                  and l["rect"].w < self.width and l["rect"].h < self.height
                                  and _in_editor_water(l["rect"]))]
        # 特殊单位刷新点（列车/战列舰）：JSON 带 "special_units" 键即接管该图特殊单位
        # （含空列表=该图不放特殊单位），并同步替换 initial_units 供关卡加载生成实体；
        # 旧布局文件无此键 → 维持地图硬编码 initial_units（运行时自动推导默认 spec）
        self.special_specs = None
        if "special_units" in data:
            specs = []
            for s in data.get("special_units", []):
                t = str(s.get("type", ""))
                t = {"train": "Train", "battleship": "Battleship"}.get(t, t)
                if t not in ("Train", "Battleship", "AC130"):
                    continue
                specs.append({
                    "type": t,
                    "spawn": vec(s.get("spawn", [0, 0])),
                    "target": vec(s["target"]) if s.get("target") else None,
                    "respawn_frames": int(s.get("respawn_frames", SPECIAL_RESPAWN_FRAMES)),
                    "attack_radius": int(s["attack_radius"]) if s.get("attack_radius") else None,
                })
            self.special_specs = specs
            self.initial_units = [("train" if sp["type"] == "Train" else
                                   ("AC130" if sp["type"] == "AC130" else "Battleship"),
                                   vec(sp["spawn"])) for sp in specs]
        # 道路背景：起终点+宽度（空列表/缺键 = 无道路）；贴地层纹理平铺绘制
        self.roads = []
        for r in data.get("roads", []):
            try:
                s, e = r.get("start", [0, 0]), r.get("end", [0, 0])
                self.roads.append({
                    "start": vec(float(s[0]), float(s[1])),
                    "end": vec(float(e[0]), float(e[1])),
                    "width": max(16, min(256, int(r.get("width", 64)))),
                })
            except Exception:
                continue
        if self.terrain_polys:
            # 编辑器画了地形 → 官方 water 湖让位（数据+判定一起清，老湖的运行时
            # 椭圆绘制已从 render_mixin 移除）；mountain 边界山/竞技场全图水不受影响
            self.lakes = [l for l in getattr(self, 'lakes', [])
                          if not isinstance(l, dict) or l.get('type', 'water') != 'water']
            if self.game is not None:
                self.apply_terrain_polys(self.game)
            self.bake_terrain_visual()
        print(f"[Layout] Applied {path}: {len(self.neutral_buildings)} neutral, "
              f"{len(self.bases_config)} bases, {len(self.ore_patches)} ore, "
              f"{len(self.terrain_polys)} terrain")
        return True

    def update(self):
        # 矿脉缓慢再生（时间基准，双调用安全）
        for p in getattr(self, 'ore_patches', []):
            p.update()

    def update_effects(self, game):
        """每帧调用，用于生成地图特有的环境特效"""
        pass

class WildernessMap(GameMap):
    max_players = 4 # [新增] 类属性
    name_static = "荒野游踪"
    name_cn_static = "荒野游踪"
    def __init__(self, game):
        super().__init__(game)
        self.name = "荒野游踪"
        self.description = "  新联邦对泛亚联盟内油田展开了大规模突袭,企图削弱泛亚联盟对于红钴矿的运输与使用"
        self.location="山东 胜利油田"
        self.width = 4800
        self.height = 3200
        self.bg_color = (34, 45, 34) # 基础深绿
        img_path = resource_path("map/wild.png")
        
        if os.path.exists(img_path):
            try:
                raw_img = pygame.image.load(img_path).convert()
                # 缩放到标准尺寸 (比如 400x250)
                self.preview_image = raw_img  # 保原分辨率（loading 界面大图显示用；选图界面自行缩放）
            except:
                self.preview_image = None # 加载失败
        else:
            # 文件不存在，回退到自绘 (或者显示默认图)
            self.preview_image = pygame.Surface((400, 250))
            self.preview_image.fill((50, 50, 50))        


    def generate(self, seed=None, visual_only=False):
        super().generate(seed)
        self.generate_background_texture()        
        # 1. 固定湖泊配置
        fixed_lakes_config = [
            (800, 800, 300, 200), (2000, 1500, 400, 300), (3500, 600, 250, 250),
            (1200, 2400, 350, 200), (3200, 2200, 300, 300), (4000, 1200, 200, 400)
        ]
        for (cx, cy, w, h) in fixed_lakes_config:
            rect = pygame.Rect(cx - w//2, cy - h//2, w, h)
            self.lakes.append({'rect': rect, 'parts': [(cx, cy, w, h)]})

        mid_y = self.height // 2
        mid_x = self.width // 2
        self.bases_config = [
            vec(400, mid_y),             # P1 (左)
            vec(self.width-400, mid_y),  # P2 (右)
            vec(mid_x, 400),             # P3 (上)
            vec(mid_x, self.height-400)  # P4 (下)
        ]

        # 3. 中立建筑
        neutral_zones = [(1500, 500), (2500, 800), (3500, 1500), (1000, 2000), (2200, 2500), (3800, 2806)]
        for x, y in neutral_zones: self.neutral_buildings.append(OilDerrick(self.game, vec(x, y)))
        
        from core.base_classes import Skyscraper
        skys = [ (1500, 1000), (3300, 2200)]
        for x, y in skys: self.neutral_buildings.append(Skyscraper(self.game, vec(x, y)))

        if not visual_only:
            from units import FactoryBuilding, PowerPlant, RadarBuilding, Airfield, ResearchCenter
            from core.base_classes import Bridge, CivilianHouse
            factory_pos = [(1200, 1200), (3600, 1200), (1200, 2000), (3600, 2000)]
            for x, y in factory_pos:
                self.neutral_buildings.append(FactoryBuilding(self.game, vec(x, y), "neutral"))
            
            power_pos = [(800, 1600), (4000, 1600), (2400, 800), (2400, 2400)]
            for x, y in power_pos:
                self.neutral_buildings.append(PowerPlant(self.game, vec(x, y), "neutral"))
            
            radar_pos = [(1800, 600), (3000, 2600)]
            for x, y in radar_pos:
                self.neutral_buildings.append(RadarBuilding(self.game, vec(x, y), "neutral"))
            
            airfield_pos = [(4000, 400), (400, 2800)]
            for x, y in airfield_pos:
                self.neutral_buildings.append(Airfield(self.game, vec(x, y), "neutral"))
            
            research_pos = [(2400, 1600)]
            for x, y in research_pos:
                self.neutral_buildings.append(ResearchCenter(self.game, vec(x, y), "neutral"))
            
            house_pos = [(600, 600), (4200, 600), (600, 2600), (4200, 2600)]
            for x, y in house_pos:
                self.neutral_buildings.append(CivilianHouse(self.game, vec(x, y)))

        self.initial_units = []
        # 放在中间
        self.initial_units.append(("train", vec(TRAIN_TRACK_X, self.height//2)))

        self.slopes = [] # 坡度列表（官方红色斜坡区已移除，需要斜坡用布局编辑器的 slope 多边形画）



    def generate_background_texture(self):
        super().generate_background_texture()
        surf = self.bg_surface
        
        # 1. 绘制草地噪点 (模拟质感)
        for _ in range(10000):
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            color = (30, random.randint(40, 60), 30) # 随机深浅绿色
            pygame.draw.rect(surf, color, (x, y, 4, 4))
            
        # 2. 绘制深色植被斑块 (灌木丛)
        for _ in range(300):
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            pygame.draw.circle(surf, (20, 35, 20), (x, y), random.randint(20, 50))
            
        # 3. 绘制泥土小径 (装饰性)
        # 画几条淡淡的褐色痕迹
        for _ in range(20):
            start = (random.randint(0, self.width), random.randint(0, self.height))
            end = (start[0] + random.randint(-500, 500), start[1] + random.randint(-500, 500))
            pygame.draw.line(surf, (50, 45, 35), start, end, 30)
        # [新增] 绘制铁轨 (贯穿南北)
        track_x = TRAIN_TRACK_X
        # 路基
        pygame.draw.line(surf, (60, 50, 40), (track_x, 0), (track_x, self.height), 60)
        # 枕木
        for y in range(0, self.height, 20):
            pygame.draw.line(surf, (40, 30, 20), (track_x-25, y), (track_x+25, y), 6)
        # 钢轨
        pygame.draw.line(surf, (150, 150, 160), (track_x-15, 0), (track_x-15, self.height), 4)
        pygame.draw.line(surf, (150, 150, 160), (track_x+15, 0), (track_x+15, self.height), 4)

class StormCoastMap(GameMap):
    max_players = 4 # [新增] 类属性
    name_static = "风暴海岸"
    name_cn_static = "风暴海岸"
    def __init__(self, game):
        super().__init__(game)
        self.name = "风暴海岸"
        self.description = "  北约对于太空合作矿产的意外进行问责,企图封锁住泛亚联盟的航天设施,而泛亚联盟的警告让这场对峙的发生不可避免."
        self.location="菲律宾 沿岸"
        self.width = 6400 
        self.height = 4800
        self.coast_y = 2000
        self.bg_color = (210, 180, 140) # 沙滩色
        
        img_path = resource_path("map/coast.png")
        
        if os.path.exists(img_path):
            try:
                raw_img = pygame.image.load(img_path).convert()
                # 缩放到标准尺寸 (比如 400x250)
                self.preview_image = raw_img  # 保原分辨率（loading 界面大图显示用；选图界面自行缩放）
            except:
                self.preview_image = None # 加载失败
        else:
            # 文件不存在，回退到自绘 (或者显示默认图)
            self.preview_image = pygame.Surface((400, 250))
            self.preview_image.fill((50, 50, 50))   
        self.bg_color = (210, 190, 150) # 暖沙色
        self.coast_y = 2200 


    def generate(self, seed=None, visual_only=False):
        super().generate(seed)

        img_path = resource_path("bg/coast.png") # 确保路径正确
        if os.path.exists(img_path):
            try:
                raw_img = pygame.image.load(img_path).convert()
                self.bg_surface = pygame.transform.scale(raw_img, (self.width, self.height))
                print(f"[Map] Loaded background from {img_path}")
            except Exception as e:
                print(f"[Map] Error loading image: {e}")
                self.bg_surface = pygame.Surface((self.width, self.height))
                self.bg_surface.fill(self.bg_color)
        else:
            print(f"[Map] Image not found: {img_path}, using default color.")
            self.bg_surface = pygame.Surface((self.width, self.height))
            self.bg_surface.fill(self.bg_color)
        
        self.lakes = []
        self.neutral_buildings = []
        self.neutral_units = []
        
        sea_rect = pygame.Rect(0, self.coast_y, self.width, self.height - self.coast_y)
        self.lakes.append({'rect': sea_rect, 'parts': [], 'type': 'water'})

        # 2. 基地配置 (放在城市两侧的空地上)
        mid_y = 1200 # 城市后方
        self.bases_config = [
            vec(400, mid_y),             # P1 左
            vec(self.width-400, mid_y),  # P2 右
            vec(400, self.coast_y - 300),# P3 左岸
            vec(self.width-400, self.coast_y - 300) # P4 右岸
        ]

        # 3. 战列舰与通讯站 (固定位置)
        # 战列舰在深海，通讯站在最长的那条栈桥尽头
        self.battleship_pos = vec(self.width//2, 2800)
        self.comm_station_pos = vec(self.width//2, 2100) # 岸边
        self.initial_units = []
        self.initial_units.append(("Battleship",self.battleship_pos) ) 
        com = [ (2400, 2400)]
        for x, y in com: self.neutral_buildings.append(CommStation(self.game, vec(x, y)))      
        if not visual_only:
            from core.base_classes import Skyscraper, CivilianHouse
            from units import FactoryBuilding, PowerPlant, RadarBuilding, Airfield, AntiAirTurret, ResearchCenter
            
            house_y = 2000
            for x in range(600, 4400, 150): 
                if abs(x - self.width//2) < 250: continue
                offset = vec(random.randint(-20, 20), random.randint(-20, 20))
                self.neutral_buildings.append(CivilianHouse(self.game, vec(x, house_y) + offset))

            for row in range(2):
                base_y = 1600 - row * 200
                for x in range(600, 4400, 140):
                    if abs(x - self.width//2) < 250: continue
                    offset = vec(random.randint(-15, 15), random.randint(-15, 15))
                    self.neutral_buildings.append(CivilianHouse(self.game, vec(x, base_y) + offset))
            
            factory_pos = [(800, 2800), (5600, 2800), (3200, 3200)]
            for x, y in factory_pos:
                self.neutral_buildings.append(FactoryBuilding(self.game, vec(x, y), "neutral"))
            
            power_pos = [(1200, 3000), (5200, 3000)]
            for x, y in power_pos:
                self.neutral_buildings.append(PowerPlant(self.game, vec(x, y), "neutral"))
            
            radar_pos = [(2000, 2600), (4400, 2600)]
            for x, y in radar_pos:
                self.neutral_buildings.append(RadarBuilding(self.game, vec(x, y), "neutral"))
            
            for x, y in [(1600, 3200), (4800, 3200)]:
                self.neutral_buildings.append(Airfield(self.game, vec(x, y), "neutral"))
            
            for x, y in [(1000, 3400), (5400, 3400)]:
                self.neutral_buildings.append(AntiAirTurret(self.game, vec(x, y), "neutral"))
            
            self.neutral_buildings.append(ResearchCenter(self.game, vec(3200, 2800), "neutral"))
            
            for x, y in [(2800, 3400), (3600, 3400)]:
                self.neutral_buildings.append(Skyscraper(self.game, vec(x, y)))


class FrozenArchipelagoMap(GameMap):
    max_players = 4 # [新增] 类属性
    def __init__(self, game):
        super().__init__(game)
        self.name = "FROZEN ARCHIPELAGO"
        self.description = "Navigating the ice floes is treacherous. Control the EMP towers to freeze enemy mechanical units."
        self.width = 4000
        self.height = 4000
        self.bg_color = (220, 230, 255) # 亮白/浅蓝冰面
        
        self.preview_image = pygame.Surface((400, 400))
        self.preview_image.fill(self.bg_color)
        pygame.draw.line(self.preview_image, (100, 150, 255), (0, 0), (400, 400), 2) # 裂缝

    def generate(self, seed=None):
        super().generate(seed)
        
        mid_y = self.height // 2
        mid_x = self.width // 2
        self.bases_config = [
            vec(400, mid_y),             # P1 (左)
            vec(self.width-400, mid_y),  # P2 (右)
            vec(mid_x, 400),             # P3 (上)
            vec(mid_x, self.height-400)  # P4 (下)
        ]
        
        # 冰湖/冰窟窿 (不可通过区域)
        self.lakes = []
        for i in range(10):
            cx = random.randint(800, self.width-800)
            cy = random.randint(400, self.height-400)
            # 颜色深一点表示水
            rect = pygame.Rect(cx-100, cy-100, 200, 200)
            self.lakes.append({'rect': rect, 'parts': []})
            
        self.neutral_buildings.append(EMPGenerator(self.game, vec(self.width//2, 800)))
        self.neutral_buildings.append(EMPGenerator(self.game, vec(self.width//2, self.height-800)))

        self.generate_background_texture()

    def generate_background_texture(self):
        super().generate_background_texture()
        surf = self.bg_surface
        
        # 1. 冰面纹理 (轻微的蓝色噪点)
        for _ in range(10000):
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            color = (200, 220, random.randint(230, 255))
            pygame.draw.rect(surf, color, (x, y, 5, 5))
            
        # 2. 巨大的冰裂缝 (Jagged Lines)
        for _ in range(40):
            start_x = random.randint(0, self.width)
            start_y = random.randint(0, self.height)
            points = [(start_x, start_y)]
            curr_x, curr_y = start_x, start_y
            
            # 生成曲折线
            for _ in range(10):
                curr_x += random.randint(-100, 100)
                curr_y += random.randint(-100, 100)
                points.append((curr_x, curr_y))
            
            if len(points) > 1:
                pygame.draw.lines(surf, (150, 180, 220), False, points, 3)

        # 3. 绘制深色冰窟 (对应 self.lakes 的位置)
        # 我们需要在背景图上也把这些不可通过区域画出来，虽然 GameMap.lakes 负责逻辑，但视觉也得跟上
        for lake in self.lakes:
            rect = lake['rect']
            # 深蓝海水
            pygame.draw.rect(surf, (40, 60, 100), rect)
            # 边缘冰层
            pygame.draw.rect(surf, (180, 200, 230), rect, 10)
class DragonValleyMap(GameMap):
    max_players = 4 # [新增] 类属性
    name_static = "龙之谷"
    name_cn_static = "龙之谷"
    def __init__(self, game):
        super().__init__(game)
        self.name = "龙之谷"
        self.description = "  有则关于此地「人间仙境」的古老传说，叙述着一条黄龙协助一名君王将泛滥的洪水导入大海。但是，现时聚集于此乡野山谷的美国军队，打算在发射中心旁对火星矿场上爆发的意外事件讨要说法。此区域内的美国海军陆战队势必采取攻势，而中华人民共和国军队则是为了保卫祖传之地而战，这将会是一场艰苦的战役。"
        self.location="四川 岷山"
        self.width = 5600 # 很大的地图
        self.height = 4000
        self.bg_color = (60, 80, 60) # 深山绿
        
        img_path = resource_path("map/dragon.png")
        
        if os.path.exists(img_path):
            try:
                raw_img = pygame.image.load(img_path).convert()
                # 缩放到标准尺寸 (比如 400x250)
                self.preview_image = raw_img  # 保原分辨率（loading 界面大图显示用；选图界面自行缩放）
            except:
                self.preview_image = None # 加载失败
        else:
            # 文件不存在，回退到自绘 (或者显示默认图)
            self.preview_image = pygame.Surface((400, 250))
            self.preview_image.fill((50, 50, 50))   
        self.music_config.update({
            "intro": "map5_loop.mp3", 
            "loop": "map5_loop.mp3",
            "final1": "phase1_loop.mp3",             
            "final2": "phase2_loop.mp3",            
            "final3": "final_rush.mp3", 
            "end_win": "victory.mp3",
            "end_lose": "defeat.mp3"
        })
    def generate(self, seed=None, visual_only=False):
        super().generate(seed)
        img_path = resource_path("bg/dragonvalley.png") # 确保路径正确
        if os.path.exists(img_path):
            try:
                raw_img = pygame.image.load(img_path).convert()
                self.bg_surface = pygame.transform.scale(raw_img, (self.width, self.height))
                print(f"[Map] Loaded background from {img_path}")
            except Exception as e:
                print(f"[Map] Error loading image: {e}")
                self.bg_surface = pygame.Surface((self.width, self.height))
                self.bg_surface.fill(self.bg_color)
        else:
            print(f"[Map] Image not found: {img_path}, using default color.")
            self.bg_surface = pygame.Surface((self.width, self.height))
            self.bg_surface.fill(self.bg_color)        
        # 1. 蜿蜒的河流 (The "Dragon") - 设置为不可通过的水域
        # 使用正弦波模拟河流
        river_points = []
        steps = 80
        for i in range(steps):
            t = i / steps
            # S形曲线: x 从左到右，y 上下波动
            x = int(self.width * t)
            y = int(self.height/2 + math.sin(t * 6) * 800) 
            river_points.append((x, y))
            
            # 将河流每一段作为一个 "Lake" (阻挡物)
            # 宽度 250
            rect = pygame.Rect(x - 125, y - 125, 250, 250)
            self.lakes.append({'rect': rect, 'parts': [], 'type': 'water'})

        # 山脉阻挡已移除（原 5 簇×5 矩形会探进河道挡死海军）：
        # 河道通行/绕行封锁改由布局 JSON 的编辑器地形（水域/悬崖）自由规划

        mid_y = self.height // 2
        mid_x = self.width // 2
        self.bases_config = [
            vec(400, mid_y),             # P1 (左)
            vec(self.width-400, mid_y),  # P2 (右)
            vec(mid_x, 400),             # P3 (上)
            vec(mid_x, self.height-400)  # P4 (下)
        ]
        
        # 4. 古刹 (Temples) - 放置在狭窄路口或战略点
        temple_positions = [
            (2400, 2000), # 地图正中心，过河的关键点
            (1200, 1800), # 左侧隘口
            (4000, 2200)  # 右侧隘口
        ]
        for tx, ty in temple_positions:
            self.neutral_buildings.append(AncientTemple(self.game, vec(tx, ty)))

        if not visual_only:
            from units import FactoryBuilding, PowerPlant, RadarBuilding, Airfield, ResearchCenter, AntiAirTurret
            from core.base_classes import CivilianHouse
            
            factory_pos = [(1600, 1200), (4000, 1200), (2800, 2800)]
            for x, y in factory_pos:
                self.neutral_buildings.append(FactoryBuilding(self.game, vec(x, y), "neutral"))
            
            power_pos = [(1200, 1600), (4400, 1600), (2800, 800)]
            for x, y in power_pos:
                self.neutral_buildings.append(PowerPlant(self.game, vec(x, y), "neutral"))
            
            radar_pos = [(2000, 2000), (3600, 2000)]
            for x, y in radar_pos:
                self.neutral_buildings.append(RadarBuilding(self.game, vec(x, y), "neutral"))
            
            for x, y in [(800, 2400), (4800, 2400)]:
                self.neutral_buildings.append(Airfield(self.game, vec(x, y), "neutral"))
            
            for x, y in [(1400, 2800), (4200, 2800)]:
                self.neutral_buildings.append(AntiAirTurret(self.game, vec(x, y), "neutral"))
            
            self.neutral_buildings.append(ResearchCenter(self.game, vec(2800, 2000), "neutral"))
            
            for x, y in [(2000, 2800), (3600, 2800)]:
                self.neutral_buildings.append(CivilianHouse(self.game, vec(x, y)))
        for _ in range(8):
            rx, ry = random.randint(500, self.width-500), random.randint(500, self.height-500)
            # 简单避障
            test_rect = pygame.Rect(rx-50, ry-50, 100, 100)
            if test_rect.collidelist([l['rect'] for l in self.lakes]) == -1:
                self.neutral_buildings.append(OilDerrick(self.game, vec(rx, ry)))
        from core.base_classes import Bridge
        
        # 在地图中央加一座桥
        bridge_pos = vec(2800, 2000) 
        self.neutral_buildings.append(Bridge(self.game, vec(2800, 2000), "horizontal"))
        


class CrossfireMap(GameMap):
    max_players = 4 
    name_static = "围攻"
    name_cn_static = "围攻"
    def __init__(self, game):
        super().__init__(game)
        self.name = "围攻" 
        self.description = "  在动荡发生后,台湾省的不法势力企图再次发动独立运动,处于风口浪尖上的美国政府却未对此做出回应,而中国的人民与解放军战士们必定会为统一而战"
        self.location="澎湖列岛及周边"
        self.width = 12000
        self.height = 12000
          
        img_path = resource_path("map/island.png")
        
        if os.path.exists(img_path):
            try:
                raw_img = pygame.image.load(img_path).convert()

                self.preview_image = raw_img  # 保原分辨率（loading 界面大图显示用；选图界面自行缩放）
            except:
                self.preview_image = None # 加载失败
        else:
            # 文件不存在，回退到自绘 (或者显示默认图)
            self.preview_image = pygame.Surface((400, 250))
            self.preview_image.fill((50, 50, 50))   

        self.bg_color = Colors.OCEAN_DEEP
        

        # 动态特效
        self.wave_manager = WaveManager()
        self.shore_points = [] # 用于生成海浪的点
        self.rng = random.Random() 
        self.FIXED_SEED = 12345 # 设定一个固定的魔数

    def generate(self, seed=None, visual_only=False):
        final_seed = self.FIXED_SEED 
        self.rng.seed(final_seed)
        self.music_config.update({
            "intro": "taiwan_intro.mp3",
            "loop": "battle_loop.mp3", # 把 Intro 也设为 Loop，或者设为 None
            "final1": "taiwan_phase1.mp3",             
            "final2": "taiwan_phase2.mp3",            
            "final3": "taiwan_final_rush.mp3", # 决战
            "end_win": "taiwan_victory.mp3",
            "end_lose": "taiwan_victory.mp3"
        })       
        print(f"[Map] Generating Heligoland Bight (Fixed Seed: {final_seed})...")
        
        self.bg_surface = pygame.Surface((self.width, self.height))
        self.bg_surface.fill(self.bg_color)
        
        self.lakes = []     
        self.islands = []   
        self.neutral_buildings = []
        img_path = resource_path("bg/siege.png") # 确保路径正确
        if os.path.exists(img_path):
            try:
                raw_img = pygame.image.load(img_path).convert()
                self.bg_surface = pygame.transform.scale(raw_img, (self.width, self.height))
                print(f"[Map] Loaded background from {img_path}")
            except Exception as e:
                print(f"[Map] Error loading image: {e}")
                self.bg_surface = pygame.Surface((self.width, self.height))
                self.bg_surface.fill(self.bg_color)
        else:
            print(f"[Map] Image not found: {img_path}, using default color.")
            self.bg_surface = pygame.Surface((self.width, self.height))
            self.bg_surface.fill(self.bg_color)               
        # 1. 基础设定
        self.lakes.append({'rect': pygame.Rect(0, 0, self.width, self.height), 'type': 'water', 'parts': []})
        
        # 2. 生成岛屿群 (所有坐标和形状都由 self.rng 控制)
        
        center = vec(self.width//2 - 1000, self.height//2)
        
        # A. 主岛
        self._generate_cliff_island(center, 2500, roughness=200, shape_type="triangle")
        
        # B. 沙丘岛
        dune_pos = center + vec(3500, 500)
        self._generate_sand_island(dune_pos, 1500, 400)
        
        # C. 卫星岛 (坐标列表是固定的，形状也通过 rng 固定)
        reef_configs = [
            (-2800, -2200, 400), (-3800, -1200, 300), (-1500, -3200, 350),
            (-2500, 2500, 450),
            (3200, -1800, 400),  (4500, -1000, 300),
            (2800, 2800, 500),   (4200, 2200, 350),
            (800, 2500, 250),
            (5500, 500, 300),    (-4500, 0, 300),
            (0, -4200, 250),     (0, 4200, 250)
        ]

        for off_x, off_y, radius in reef_configs:
            pos = center + vec(off_x, off_y)
            self._generate_cliff_island(pos, radius, roughness=40, shape_type="circle")

        # D. 防波堤
        self._generate_breakwaters(center)

        # 3. 基地配置 (固定)
        self.bases_config = [
            (2202,3800), 
            (2500, 8484),   
            (9192,8198 ),    
            (9507, 4993)      
        ]
        self.battleship_pos = vec(4281, 8772)
        self.initial_units = []
        self.initial_units.append(("Battleship",self.battleship_pos) ) 
        com = [ (4281,8172)]
        for x, y in com: self.neutral_buildings.append(CommStation(self.game, vec(x, y))) 
        house=[(6000,6000),(6200,6200),(6000,6200),(6200,6000)   ]    
        lighthouse=[(3030,7280),(4200,4200),(6458,4400),(7200,7250),(6400,8400),(5750,8550)]   
        if not visual_only:
            self._place_fortifications(center) 
            self.neutral_buildings.append(OilDerrick(self.game, vec(3500, 2784)))
            self.neutral_buildings.append(OilDerrick(self.game, vec(1230, 4816)))

            self.neutral_buildings.append(OilDerrick(self.game, vec(480, 6000)))
            self.neutral_buildings.append(OilDerrick(self.game, vec(7800,8750)))
            self.neutral_buildings.append(OilDerrick(self.game, vec(9500, 5000)))
            self.neutral_buildings.append(OilDerrick(self.game, vec(8150, 4100)))
            for (x,y) in house:
                self.neutral_buildings.append(CivilianHouse(self.game, vec(x,y)))
            for (x,y) in lighthouse:
                self.neutral_buildings.append(Lighthouse(self.game, vec(x,y)))
            self.neutral_buildings.append(Bastion(self.game, vec(5200, 5200)))            
            self.neutral_buildings.append(Bastion(self.game, vec(6000, 7000)))        
        print("[Map] Generation Complete.")

    # -------------------------------------------------------------------------
    #  修改所有生成方法，将 random 替换为 self.rng
    # -------------------------------------------------------------------------
    def _point_in_poly(self, x, y, poly):
        """
        判断点 (x, y) 是否在多边形 poly 内部
        使用射线法 (Ray Casting Algorithm)
        """
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
    def _generate_cliff_island(self, center, avg_radius, roughness, shape_type="circle"):
        # 传入 self.rng
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
            
            if self.rng.random() < 0.2: # 使用 self.rng
                self.shore_points.append(vec(px, py))

        # 逻辑填充 (保持不变，计算几何不需要随机)
        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)
        
        grid_size = 200
        for x in range(int(min_x), int(max_x), grid_size):
            for y in range(int(min_y), int(max_y), grid_size):
                if self._point_in_poly(x+grid_size/2, y+grid_size/2, points):
                    r = pygame.Rect(x, y, grid_size, grid_size)
                    self.islands.append(r)
        
        if not hasattr(self, 'cliff_islands'): self.cliff_islands = []
        self.cliff_islands.append({'poly': points, 'center': center, 'radius': avg_radius})
        
        return points # 返回 poly 供后续使用

    def _generate_sand_island(self, center, width, height):
        rect = pygame.Rect(center.x - width/2, center.y - height/2, width, height)
        angle = self.rng.uniform(-0.5, 0.5) # 使用 self.rng
        
        points = []
        for i in range(40):
            a = (i/40) * 6.28
            # 使用 self.rng
            rx = width/2 * (1 + self.rng.uniform(-0.1, 0.1))
            ry = height/2 * (1 + self.rng.uniform(-0.1, 0.1))
            
            lx = math.cos(a) * rx
            ly = math.sin(a) * ry
            
            wx = lx * math.cos(angle) - ly * math.sin(angle) + center.x
            wy = lx * math.sin(angle) + ly * math.cos(angle) + center.y
            points.append((wx, wy))
            
            if self.rng.random() < 0.1: self.shore_points.append(vec(wx, wy))

        self.islands.append(rect)
        if not hasattr(self, 'sand_islands'): self.sand_islands = []
        self.sand_islands.append(points)

    def _generate_breakwaters(self, main_center):
        # 防波堤坐标是固定的，不需要随机，直接调用
        start = main_center + vec(-500, 2000)
        end = main_center + vec(1500, 2000)
        self._add_concrete_wall(start, end)
        
        start = main_center + vec(1500, 2000)
        end = main_center + vec(1500, 1200)
        self._add_concrete_wall(start, end)

    def _add_concrete_wall(self, start, end):
        # 逻辑生成，无随机性
        thickness = 150
        diff = end - start
        length = diff.length()
        steps = int(length / 100)
        for i in range(steps):
            pos = start.lerp(end, i/steps)
            r = pygame.Rect(pos.x - thickness/2, pos.y - thickness/2, thickness, thickness)
            self.islands.append(r)
        
        if not hasattr(self, 'walls'): self.walls = []
        self.walls.append({'start': start, 'end': end, 'width': thickness})

    # -------------------------------------------------------------------------
    #  纹理绘制 (也必须替换所有 random 为 self.rng)
    # -------------------------------------------------------------------------
    def generate_background_texture(self):
        surf = self.bg_surface
        w, h = self.width, self.height
        
        # 1. 海洋细节
        for _ in range(5000):
            x = self.rng.randint(0, w)
            y = self.rng.randint(0, h)
            rad = self.rng.randint(100, 300)
            color = (
                Colors.OCEAN_DEEP[0] + self.rng.randint(0, 10),
                Colors.OCEAN_DEEP[1] + self.rng.randint(0, 10),
                Colors.OCEAN_DEEP[2] + self.rng.randint(0, 10)
            )
            s = pygame.Surface((rad*2, rad*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*color, 20), (rad, rad), rad)
            surf.blit(s, (x-rad, y-rad))

        # 2. 悬崖岛绘制 (包含树木生成)
        if hasattr(self, 'cliff_islands'):
            for island in self.cliff_islands:
                poly = island['poly']
                center = island['center']
                radius = island['radius']
                
                # ... (多边形绘制代码保持不变，因为颜色是固定的) ...
                pygame.draw.polygon(surf, Colors.OCEAN_SHALLOW, poly, width=120)
                shadow_poly = [(p[0]+30, p[1]+30) for p in poly]
                pygame.draw.polygon(surf, (0,0,0), shadow_poly) 
                pygame.draw.polygon(surf, Colors.CLIFF_BASE, poly) 
                inner_poly = [center + (vec(p)-center)*0.95 for p in poly]
                pygame.draw.polygon(surf, Colors.CLIFF_FACE, inner_poly)
                top_poly = [center + (vec(p)-center)*0.9 for p in poly]
                pygame.draw.polygon(surf, Colors.GRASS_BASE, top_poly)
                
                # 植被生成 (使用 self.rng)
                min_x, max_x = min(p[0] for p in top_poly), max(p[0] for p in top_poly)
                min_y, max_y = min(p[1] for p in top_poly), max(p[1] for p in top_poly)
                num_trees = int(radius * 0.8) 
                
                for _ in range(num_trees):
                    tx = self.rng.randint(int(min_x), int(max_x))
                    ty = self.rng.randint(int(min_y), int(max_y))
                    if self._point_in_poly(tx, ty, top_poly):
                        self._draw_pine_tree(surf, tx, ty) # 这里内部也要改

                self._generate_wrecks_around_island(surf, center, radius + 150)

        # 3. 沙岛绘制
        if hasattr(self, 'sand_islands'):
            for poly in self.sand_islands:
                pygame.draw.polygon(surf, Colors.SAND_WET, poly)
                center = vec(sum(p[0] for p in poly)/len(poly), sum(p[1] for p in poly)/len(poly))
                inner_poly = [center + (vec(p)-center)*0.8 for p in poly]
                pygame.draw.polygon(surf, Colors.SAND_DRY, inner_poly)
                
                r_approx = max(p[0] for p in poly) - min(p[0] for p in poly)
                self._generate_wrecks_around_island(surf, center, r_approx/2 + 100)

        # 4. 防波堤
        if hasattr(self, 'walls'):
            for wall in self.walls:
                s, e, wid = wall['start'], wall['end'], wall['width']
                pygame.draw.line(surf, Colors.CONCRETE_DARK, s, e, wid)
                pygame.draw.line(surf, Colors.CONCRETE_LIGHT, s, e, int(wid*0.8))

    def _draw_pine_tree(self, surf, x, y):
        # 使用 self.rng
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

    def _generate_wrecks_around_island(self, surf, center, radius):
        count = self.rng.randint(5, 15)
        for _ in range(count):
            angle = self.rng.uniform(0, 6.28)
            dist = radius + self.rng.randint(0, 200)
            wx = center.x + math.cos(angle) * dist
            wy = center.y + math.sin(angle) * dist
            
            type_id = self.rng.randint(0, 2)
            
            if type_id == 0: 
                w, h = self.rng.randint(10, 30), self.rng.randint(4, 8)
                p1 = (wx, wy)
                p2 = (wx + w, wy + h)
                pygame.draw.line(surf, (80, 60, 40), p1, p2, 3)
            elif type_id == 1: 
                w, h = self.rng.randint(30, 60), self.rng.randint(15, 25)
                rect = pygame.Rect(wx, wy, w, h)
                pygame.draw.ellipse(surf, Colors.RUST, rect)
            elif type_id == 2:
                r = self.rng.randint(20, 50)
                s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
                pygame.draw.circle(s, (0, 0, 0, 100), (r, r), r)
                surf.blit(s, (wx-r, wy-r))
    def _place_fortifications(self, center):

        if not hasattr(self, 'cliff_islands') or not self.cliff_islands:
            return
            
        # 假设第一个生成的悬崖岛就是主岛
        poly = self.cliff_islands[0]['poly']
        
        try:            
            from units import AntiAirTurret,RadarBuilding,CoastalGun
            for i in range(0, len(poly), 15):
                pos = vec(poly[i])
                # 稍微往里缩一点，避免悬空
                dir_to_center = (center - pos).normalize()
                bunker_pos = pos + dir_to_center * 200
                self.neutral_buildings.append(CoastalGun(self.game, bunker_pos, "neutral"))
                
            # 中央雷达站
            self.neutral_buildings.append(RadarBuilding(self.game, center, "neutral"))
            
        except ImportError:
            pass

    def update(self):
        # 矿脉再生（覆写 update 未调 super，须显式补充——否则矿脉只减不增，
        # 矿区被采到残量后矿车全部停在矿区待命）
        for p in getattr(self, 'ore_patches', []):
            p.update()
        # 更新海浪
        self.wave_manager.update()

        # 随机在岸边生成新浪花
        if self.shore_points and random.random() < 0.2:
            pt = random.choice(self.shore_points)
            self.wave_manager.add_wave(pt)

    def draw_overlay(self, surface, offset):
        self.wave_manager.draw(surface, offset)
        
        pass
    def update_effects(self, game):
        # 如果进入决战 (FINAL3)
        if game.current_music_state in ["FINAL1","FINAL2","FINAL3"]:
            game.env_manager.set_weather("storm")
        else:
            game.env_manager.set_weather(None)
        if not hasattr(self, 'waves'):
            self.waves = []
            
        # --- A. 生成新波浪 ---
        
        if hasattr(self, 'shore_points') and self.shore_points:
            if random.random() < 0.7: # 调节生成频率
                pt = random.choice(self.shore_points)
                # 添加一个拍击浪: 半径小，消失快，白色
                self.waves.append([pt.x, pt.y, 5, random.randint(25, 85), 200, 0])

        if random.random() < 0.4:
            wx = random.randint(0, self.width)
            wy = random.randint(0, self.height)
            mr = random.randint(80, 160)   # 深海波最终半径
            # 出生点按"整个圆的范围"查岛：圆扩散后也不得碰到陆地
            test_rect = pygame.Rect(wx - mr, wy - mr, mr * 2, mr * 2)
            # islands 仅在海图中初始化，非海图按空列表处理
            # 布局编辑器会注入 dict 条目（地形 land 多边形），collidelist 只认 Rect，需过滤
            island_rects = [i for i in getattr(self, 'islands', []) if isinstance(i, pygame.Rect)]
            if test_rect.collidelist(island_rects) == -1:
                self.waves.append([wx, wy, 10, mr, 100, 1])

        for w in self.waves:
            w_type = w[5]
            
            if w_type == 0: # 浪花 (White Foam)
                w[2] += 0.5  # 半径扩大
                w[4] -= 4    # 透明度快速降低
                
            elif w_type == 1: # 深海波 (Deep Swell)
                if w[2] < w[3]:  # 长到最终半径即停（max_rad 出生时已保证不碰岛）
                    w[2] += 0.8
                w[4] -= 1    # 缓慢消失
                
        # 移除消失的波浪
        self.waves = [w for w in self.waves if w[4] > 0]
        # 绘制波浪

        offset = game.camera_offset
        zoom = game.zoom
        
        for w in self.waves:
            wx, wy, rad, max_rad, alpha, w_type = w
            
            # 计算屏幕坐标
            screen_x = int((wx - offset.x) * zoom)
            screen_y = int((wy - offset.y) * zoom)
            screen_r = int(rad * zoom)
            
            # 剔除含半径：圆心在屏外但圆面压屏的也要画；圆完全出屏的跳过
            if screen_x < -screen_r - 4 or screen_x > SCREEN_WIDTH + screen_r + 4 or \
               screen_y < -screen_r - 4 or screen_y > SCREEN_HEIGHT + screen_r + 4: continue
            
            if w_type == 0: 
                color = (255, 255, 255, int(alpha))
            else: 
                color = (100, 150, 200, int(alpha)) 
            
            s = pygame.Surface((screen_r*2, screen_r*2), pygame.SRCALPHA)
            
            if w_type == 0:
                pygame.draw.circle(s, color, (screen_r, screen_r), screen_r)
            else:
                width = max(15, int(2 * zoom))
                pygame.draw.circle(s, color, (screen_r, screen_r), screen_r, width)
                
            game.screen.blit(s, (screen_x - screen_r, screen_y - screen_r))
    def draw_effects(self, surface, offset):
        if not hasattr(self, 'waves'): return
        
        # 获取屏幕尺寸用于剔除
        screen_w, screen_h = surface.get_size()
        
        for w in self.waves:
            x, y, r, max_r, alpha, w_type = w
            
            # 屏幕坐标
            sx = x - offset.x
            sy = y - offset.y
            
            # 剔除 (Culling)
            if sx < -r or sx > screen_w + r or sy < -r or sy > screen_h + r:
                continue
                
            # 绘制逻辑
            if w_type == 0: # 浪花 (白色填充圆 + 描边)
                # 创建带 Alpha 的 Surface
                s = pygame.Surface((int(r*2), int(r*2)), pygame.SRCALPHA)
                # 填充淡白
                pygame.draw.circle(s, (255, 255, 255, int(alpha * 0.3)), (r, r), r)
                # 描边亮白
                pygame.draw.circle(s, (255, 255, 255, int(alpha)), (r, r), r, 2)
                surface.blit(s, (sx-r, sy-r))
                
            elif w_type == 1: # 深海波 (深蓝细圈)
                s = pygame.Surface((int(r*2), int(r*2)), pygame.SRCALPHA)
                # 颜色比深海背景稍亮一点
                color = (60, 80, 100, int(alpha * 0.5))
                pygame.draw.circle(s, color, (r, r), r, 3)
                surface.blit(s, (sx-r, sy-r))
class BroadcastCenterMap(GameMap):
    max_players = 4
    name_static = "广播中心"
    name_cn_static = "广播中心"
    def __init__(self, game):
        super().__init__(game)
        self.name = "广播中心"
        self.description = "  作为探测火星新发现的稀有能源矿的专用望远镜,泛亚联盟进行了严格的防守来防止恶意破坏的发生,而美国联合开采者与联盟基地在火星上的失联驱使着北约对于此地施压,而越南军队驻扎于此,坚信美国的侵略最终会变为第二次无功而返"
        self.location="越南 河内胡志明天文望远镜"
        self.width = 8000
        self.height = 4000
        self.bg_color = (30, 40, 30) # 深绿/丛林底色
        img_path = resource_path("map/broadcast.png")
        self.music_config.update({
            "intro": "vitnam_intro.mp3", 
            "loop": "battle_loop.mp3",# 把 Intro 也设为 Loop，或者设为 None
            "final1": "vitnam_phase1.mp3",             
            "final2": "vitnam_phase2.mp3",            
            "final3": "vitnam_final.mp3", # 决战
            "end_win": "vitnam_victory.mp3",
            "end_lose": "vitnam_victory.mp3"
        })             
        if os.path.exists(img_path):
            try:
                raw_img = pygame.image.load(img_path).convert()
                # 缩放到标准尺寸 (比如 400x250)
                self.preview_image = raw_img  # 保原分辨率（loading 界面大图显示用；选图界面自行缩放）
            except:
                self.preview_image = None # 加载失败
        else:
            # 文件不存在，回退到自绘 (或者显示默认图)
            self.preview_image = pygame.Surface((400, 250))
            self.preview_image.fill((50, 50, 50))   

    def generate(self, seed=None, visual_only=False):
        super().generate(seed)
        
        self.bg_surface = pygame.Surface((self.width, self.height))
        self.bg_surface.fill(self.bg_color)
        self.overlay_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)        
        w, h = self.width, self.height
        cx, cy = w//2, h//2
        
        self.lakes = []
        self.slopes = [] # [新增] 斜坡列表
        self.neutral_buildings = []
        self.neutral_units = [] # 记得初始化这个
        
        border = 600
        # [修改] 加上 'parts': []
        self.lakes.append({'rect': pygame.Rect(0, 0, w, border), 'type': 'mountain', 'parts': []})
        self.lakes.append({'rect': pygame.Rect(0, h-border, w, border), 'type': 'mountain', 'parts': []})
        self.lakes.append({'rect': pygame.Rect(0, 0, border, h), 'type': 'mountain', 'parts': []})
        self.lakes.append({'rect': pygame.Rect(w-border, 0, border, h), 'type': 'mountain', 'parts': []})
        
        # 2. 中央天眼 (斜坡)
        # 天眼是一个巨大的圆形区域，把它近似为一个矩形加到 slopes 里
        dish_radius = 800
        dish_rect = pygame.Rect(cx - dish_radius, cy - dish_radius, dish_radius*2, dish_radius*2)
        self.slopes.append(dish_rect)
        # 3. 基地配置 (四角)
        base_offset = 1500
        self.bases_config = [
            vec(base_offset, base_offset),       # 左上
            vec(w-base_offset, base_offset),     # 右上
            vec(base_offset, h-base_offset),     # 左下
            vec(w-base_offset, h-base_offset)    # 右下
        ]
        
        
        # 5. 中立建筑 (围绕天眼的维护站)
        if not visual_only:
            from units import PowerPlant, RadarBuilding
            from core.base_classes import  TechCenter
            # 在天眼四周放一些装饰性中立建筑 (不可占领，或者可摧毁)
            # 或者放一些可占领的 TechCenter
            
            # 天眼正下方 (6点钟)
            self.neutral_buildings.append(TechCenter(self.game, vec(cx, cy + dish_radius + 200), "neutral"))
            # 天眼正上方 (12点钟)
            self.neutral_buildings.append(RadarBuilding(self.game, vec(cx, cy - dish_radius - 200), "neutral"))

            self.neutral_buildings.append(PowerPlant(self.game, vec(cx-1000, cy +dish_radius/2), "neutral"))
            self.neutral_buildings.append(PowerPlant(self.game, vec(cx-1000, cy -dish_radius/2), "neutral"))
            self.neutral_buildings.append(Airfield(self.game, vec(cx-1400, cy -dish_radius/2), "neutral"))
            self.neutral_buildings.append(Airfield(self.game, vec(cx-1400, cy +dish_radius/2), "neutral"))

            self.neutral_buildings.append(FactoryBuilding(self.game, vec(cx+1000, cy +dish_radius/2), "neutral"))
            self.neutral_buildings.append(AntiAirTurret(self.game, vec(cx+1200, cy -dish_radius/2+400), "neutral"))
            self.neutral_buildings.append(AntiAirTurret(self.game, vec(cx+1200, cy -dish_radius/2+200), "neutral"))
        self.generate_background_texture()
    def update_effects(self, game):
        # 如果进入决战 (FINAL3)
        if game.current_music_state in ["FINAL1","FINAL2","FINAL3"]:
            game.env_manager.set_weather("storm")
        else:
            game.env_manager.set_weather(None)
    def generate_background_texture(self):
        surf = self.bg_surface
        over = self.overlay_surface 
        w, h = self.width, self.height
        cx, cy = w//2, h//2
        

        for _ in range(5000):
            x = random.randint(0, w)
            y = random.randint(0, h)

            if x < 800 or x > w-800 or y < 800 or y > h-800:
                color = (20, random.randint(30, 50), 20) # 深绿
                radius = random.randint(50, 150)
                pygame.draw.circle(surf, color, (x, y), radius)
        

        dish_radius = 800
        # 盘面 (网格状)
        pygame.draw.circle(surf, (200, 200, 210), (cx, cy), dish_radius)
        pygame.draw.circle(surf, (150, 150, 160), (cx, cy), dish_radius, 5) # 边缘
        
        # 绘制网格经纬线
        for i in range(0, 180, 15):
            # 经线 (直线)
            rad = math.radians(i)
            start = (cx + math.cos(rad)*dish_radius, cy + math.sin(rad)*dish_radius)
            end = (cx - math.cos(rad)*dish_radius, cy - math.sin(rad)*dish_radius)
            pygame.draw.line(surf, (180, 180, 190), start, end, 2)
            
        for r in range(100, dish_radius, 100):
            # 纬线 (同心圆)
            pygame.draw.circle(surf, (180, 180, 190), (cx, cy), r, 2)
            
        # 馈源舱 (Feed Cabin) - 悬浮在中间
        # 画三根巨大的支撑臂
        for i in range(3):
            angle = math.radians(i * 120 - 90)
            start = (cx + math.cos(angle) * dish_radius, cy + math.sin(angle) * dish_radius)
            pygame.draw.line(surf, (50, 50, 50), start, (cx, cy), 8)
            
        # 舱体
        pygame.draw.circle(surf, (255, 255, 255), (cx, cy), 80)
        pygame.draw.circle(surf, (50, 50, 50), (cx, cy), 80, 3)
        # 红点闪烁 (虽然是静态背景，但画个红点)
        pygame.draw.circle(surf, (200, 0, 0), (cx, cy), 20)

        # 3. [修改] 巨型电缆与支架
        # 电缆从天眼中心延伸到地图边缘的四个中点
        angles = [-90, 30, 150] # -90, 30, 150 度
        cable_len = 3000 # 足够长伸出地图
        
        for angle in angles:
            rad = math.radians(angle)
            end_x = cx + math.cos(rad) * cable_len
            end_y = cy + math.sin(rad) * cable_len
            
            # 画电缆 (画在 overlay 上！)
            # 加上阴影增加悬空感 (阴影画在地面 surf 上)
            shadow_off = 50
            pygame.draw.line(surf, (0, 0, 0, 100), (cx+shadow_off, cy+shadow_off), (end_x+shadow_off, end_y+shadow_off), 20)
            
            # 电缆本体
            pygame.draw.line(over, (20, 20, 20), (cx, cy), (end_x, end_y), 15) # 黑底
            pygame.draw.line(over, (100, 100, 100), (cx, cy), (end_x, end_y), 5) # 亮芯
            
            # 支架 (Pylons)
            vec_start = vec(cx, cy)
            vec_end = vec(end_x, end_y)
            dist = vec_start.distance_to(vec_end)
            steps = int(dist / 600) # 间距更大
            
            for i in range(1, steps):
                pos = vec_start.lerp(vec_end, i / steps)
                px, py = int(pos.x), int(pos.y)
                
                # 支架脚 (画在地面 surf 上，因为它插在地上)
                pygame.draw.line(surf, (60, 60, 60), (px-30, py+30), (px, py), 6)
                pygame.draw.line(surf, (60, 60, 60), (px+30, py+30), (px, py), 6)
                
                # 塔顶连接点 (画在电缆 over 上，盖住电缆)
                pygame.draw.circle(over, (80, 80, 80), (px, py), 10)
                pygame.draw.circle(over, (200, 0, 0), (px, py), 4) # 航灯

        # 4. 植被填充 (平原区域)
        for _ in range(2000):
            x = random.randint(800, w-800)
            y = random.randint(800, h-800)
            # 避开天眼
            if vec(x, y).distance_to(vec(cx, cy)) < dish_radius + 50: continue
            
            # 小树
            pygame.draw.circle(surf, (40, 80, 40), (x, y), random.randint(5, 10))

MAP_WIDTH = 4800
MAP_HEIGHT = 3200
class FireManager:
    def __init__(self):
        self.fire_points = []
        self.particles = []

    def add_fire_source(self, pos, intensity=1.0):
        self.fire_points.append({'pos': pos, 'intensity': intensity})

    def update(self):
        # 产生粒子
        for fp in self.fire_points:
            if random.random() < 0.3 * fp['intensity']:
                px = fp['pos'].x + random.randint(-10, 10)
                py = fp['pos'].y + random.randint(-5, 5)
                vx = random.uniform(-0.5, 0.5)
                vy = random.uniform(-2.0, -0.5)
                life = random.randint(30, 60)
                size = random.randint(3, 8)
                self.particles.append([px, py, vx, vy, life, life, size])
            # 烟雾
            if random.random() < 0.1 * fp['intensity']:
                px = fp['pos'].x + random.randint(-15, 15)
                py = fp['pos'].y - 10
                vx = random.uniform(-1.0, 1.0) + 2.0 
                vy = random.uniform(-1.0, -0.2)
                life = random.randint(100, 200)
                size = random.randint(10, 25)
                self.particles.append([px, py, vx, vy, life, life, size])

        # 更新粒子
        for p in self.particles:
            p[0] += p[2]; p[1] += p[3]; p[4] -= 1
        self.particles = [p for p in self.particles if p[4] > 0]

    def draw(self, surface, offset):
        for p in self.particles:
            x, y, vx, vy, life, max_life, size = p
            screen_x = x - offset[0]
            screen_y = y - offset[1]
            
            # 屏幕剔除
            if screen_x < -50 or screen_x > surface.get_width() + 50 or \
               screen_y < -50 or screen_y > surface.get_height() + 50: continue

            alpha = int((life / max_life) * 255)
            if size > 10: # 烟雾
                s = pygame.Surface((size*2, size*2), pygame.SRCALPHA)
                pygame.draw.circle(s, (50, 50, 50, alpha // 3), (size, size), size)
                surface.blit(s, (screen_x-size, screen_y-size))
            else: # 火焰
                progress = 1.0 - (life / max_life)
                c = (255, 255, 100) if progress < 0.3 else ((255, 100, 0) if progress < 0.7 else (100, 20, 0))
                pygame.draw.circle(surface, c, (screen_x, screen_y), size)

class VerdunMap(GameMap):
    max_players = 4
    
    def __init__(self, game):
        super().__init__(game)
        self.dlc="重返末日"
        self.name = "凡尔登高地2057"
        self.description = ""
        self.location=""
        self.width = MAP_WIDTH
        self.height = MAP_HEIGHT
        self.bg_color = Colors.MUD_BASE # 默认底色是低谷泥浆
        self.music_config.update({
            "intro": "verdun_intro.mp3", # 把 Intro 也设为 Loop，或者设为 None
            "final1": "verdun_loop1.mp3",             
            "final2": "verdun_loop2.mp3",            
            "final3": "verdun_final_rush.mp3", # 决战
            "end_win": "verdun_victory.mp3",
            "end_lose": "verdun_victory.mp3"
        })        
        self.fire_manager = FireManager()
        self.preview_image = pygame.Surface((400, 250))
        self.preview_image.fill(Colors.MUD_BASE)

    def generate(self, seed=None, visual_only=False): # [新增参数]
        if seed: random.seed(seed)
        print("[Map] Generating Verdun Heights...")
        
        self.bg_surface = pygame.Surface((self.width, self.height))
        self.bg_surface.fill(self.bg_color)
        
        # 1. 视觉层 (必须同步)
        self._generate_elevation_layer() 
        self._generate_texture_layer()
        self._generate_crater_layer()
        self._generate_burning_zones()
        self._generate_trench_layer()
        self._generate_nature_layer()
        self._generate_details_layer()
        for _ in range(12):
            rx = random.randint(200, self.width - 200)
            ry = random.randint(200, self.height - 200)
            self.neutral_buildings.append(CivilianHouse(self.game, vec(rx, ry)))       
        self.slopes = [] # 坡度列表（官方红色斜坡区已移除，需要斜坡用布局编辑器的 slope 多边形画）

        if not visual_only:
            self._setup_gameplay_objects()
        
        print("[Map] Generation Complete.")

    # -------------------------------------------------------------------------
    # Layer 1: 立体山丘 (Elevation)
    # -------------------------------------------------------------------------
    # Layer: 燃烧地面 (Burning Ground Zones)
    # -------------------------------------------------------------------------
    def _generate_burning_zones(self):
        """
        生成正在燃烧的地面区域：
        1. 绘制地裂/余烬纹理 (看起来像地表下有火)
        2. 添加动态火源
        """
        surf = self.bg_surface
        w, h = self.width, self.height
        
        # 定义燃烧区数量 (主要集中在低谷/中部)
        num_zones = 15
        
        for _ in range(num_zones):
            # 随机位置 (偏向地图中心区域)
            cx = random.randint(800, w - 800)
            cy = random.randint(600, h - 600)
            
            # 随机大小
            radius = random.randint(60, 150)
            
            # --- 步骤 A: 绘制余烬纹理 (Embers) ---
            # 创建一个临时层来画发光效果
            ember_surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
            
            # 1. 底层热浪 (半透明红晕)
            for r in range(radius, 0, -10):
                alpha = int(30 * (1 - r/radius))
                pygame.draw.circle(ember_surf, (*Colors.EMBER_DARK, alpha), (radius, radius), r)
            
            # 2. 焦土覆盖 (黑色斑块，留出缝隙)
            # 先填满黑色
            pygame.draw.circle(ember_surf, (10, 5, 5, 200), (radius, radius), radius)
            
            # 3. "烧穿"地表 (绘制明亮的裂缝)
            # 这种方法模拟地表裂开露出下面的火光
            for _ in range(10):
                # 随机生成裂缝线条
                lx = random.randint(10, radius*2-10)
                ly = random.randint(10, radius*2-10)
                length = random.randint(10, 40)
                angle = random.uniform(0, 6.28)
                
                ex = lx + math.cos(angle) * length
                ey = ly + math.sin(angle) * length
                
                # 裂缝核心 (亮)
                pygame.draw.line(ember_surf, Colors.EMBER_BRIGHT, (lx, ly), (ex, ey), 3)
                # 裂缝晕光 (半透明)
                # 注意：pygame line 不支持 alpha，这里用多个小圆模拟晕光或者简单忽略
                
            # 将余烬层混合到背景
            surf.blit(ember_surf, (cx - radius, cy - radius), special_flags=pygame.BLEND_PREMULTIPLIED)
            
            # --- 步骤 B: 注册动态火源 ---
            # 强度与半径相关
            intensity = radius / 50.0 
            self.fire_manager.add_fire_source(vec(cx, cy), intensity=intensity)
            
            # 偶尔在燃烧区旁边加几根烧断的黑木头
            if random.random() < 0.7:
                lx = cx + random.randint(-radius, radius)
                ly = cy + random.randint(-radius, radius)
                pygame.draw.line(surf, (0,0,0), (lx, ly), (lx+20, ly+5), 6)
    def _generate_elevation_layer(self):
        """
        在左上和右下生成层叠的山丘。
        通过绘制带阴影的不规则多边形来模拟高度差。
        """
        surf = self.bg_surface
        w, h = self.width, self.height
        
        # 定义山丘配置
        hills = [
            # 左上大山 (Hill Alpha)
            {'center': vec(0, 0), 'radius': 2200, 'levels': 5, 'spread': 0.7},
            # 右下大山 (Hill Bravo)
            {'center': vec(w, h), 'radius': 2000, 'levels': 5, 'spread': 0.7}
        ]
        
        # 颜色梯度
        level_colors = [Colors.HILL_L1, Colors.HILL_L2, Colors.HILL_TOP]
        
        for hill in hills:
            cx, cy = hill['center'].x, hill['center'].y
            max_r = hill['radius']
            levels = hill['levels']
            
            # 从底层往顶层画
            for i in range(levels):
                # 计算当前层半径 (越往上越小)
                # i=0 是最底层(最大), i=levels-1 是山顶(最小)
                progress = i / (levels - 1)
                curr_r = max_r * (1.0 - (progress * hill['spread']))
                
                # 颜色插值
                color_idx = min(len(level_colors)-1, int(progress * len(level_colors)))
                color = level_colors[color_idx]
                
                # 生成不规则形状的点
                points = self._generate_organic_poly(cx, cy, curr_r, noise=60)
                
                # 1. 绘制阴影 (Drop Shadow)
                # 向右下偏移 (15, 15)，产生立体悬崖感
                shadow_offset = 20
                shadow_pts = [(p[0] + shadow_offset, p[1] + shadow_offset) for p in points]
                pygame.draw.polygon(surf, Colors.HILL_SHADOW, shadow_pts)
                
                # 2. 绘制地面
                pygame.draw.polygon(surf, color, points)
                
                # 3. 边缘高光 (可选，增加轮廓)
                # pygame.draw.lines(surf, (color[0]+10, color[1]+10, color[2]+10), True, points, 3)

    def _generate_organic_poly(self, cx, cy, radius, num_points=40, noise=50):
        """生成一个有随机波动的多边形，模拟自然地形"""
        points = []
        for i in range(num_points):
            angle = (i / num_points) * 6.28
            # 半径抖动
            r_noise = random.randint(-noise, noise)
            r = max(10, radius + r_noise)
            
            px = cx + math.cos(angle) * r
            py = cy + math.sin(angle) * r
            
            # 边界夹断 (防止画出界太多，虽然pygame会自动处理)
            points.append((px, py))
        return points

    # -------------------------------------------------------------------------
    # Layer 2: 纹理与焦土
    # -------------------------------------------------------------------------
    def _generate_texture_layer(self):
        surf = self.bg_surface
        
        # 1. 全局噪点 (统一风格)
        for _ in range(4000):
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            w = random.randint(20, 60)
            h = random.randint(10, 30)
            
            # 半透明泥点
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            alpha = 20
            c = random.randint(0, 30)
            pygame.draw.ellipse(s, (c, c, c, alpha), (0,0,w,h))
            surf.blit(s, (x, y))

        # 2. 焦土带 (Scorched Earth)
        # 主要集中在两山之间的低谷 (No Man's Land)
        for _ in range(12):
            # 随机位置，偏向地图对角线中心
            cx = random.randint(1000, self.width-1000)
            cy = random.randint(1000, self.height-1000)
            r = random.randint(200, 500)
            
            # 绘制渐变黑圈
            temp = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            for i in range(r, 0, -20):
                alpha = int(15 * (1 - i/r))
                pygame.draw.circle(temp, (0,0,0, alpha), (r, r), i)
            surf.blit(temp, (cx-r, cy-r))
            
            # 添加动态火源
            if random.random() < 0.6:
                self.fire_manager.add_fire_source(vec(cx, cy), intensity=1.2)

    # -------------------------------------------------------------------------
    # Layer 3: 弹坑 (Craters)
    # -------------------------------------------------------------------------
    def _generate_crater_layer(self):
        surf = self.bg_surface
        # 弹坑现在应该在低谷密集，山顶稀疏
        
        for _ in range(30): # 弹幕群
            sx, sy = random.randint(200, self.width-200), random.randint(200, self.height-200)
            
            # 简单判断是否在山顶附近 (通过距离)
            dist_tl = vec(sx, sy).distance_to(vec(0,0))
            dist_br = vec(sx, sy).distance_to(vec(self.width, self.height))
            
            # 山顶弹坑少且小
            if dist_tl < 800 or dist_br < 800:
                count = 5
                base_r = 15
            else: # 谷底弹坑多且大
                count = 15
                base_r = 30
            
            angle = random.uniform(0, 6.28)
            length = random.randint(200, 500)
            
            for d in range(0, length, 40):
                px = sx + math.cos(angle) * d + random.randint(-15, 15)
                py = sy + math.sin(angle) * d + random.randint(-15, 15)
                r = base_r + random.randint(-5, 10)
                
                # 绘制有立体感的弹坑
                pygame.draw.circle(surf, (70, 60, 50), (px-2, py-2), r) # 高光边缘
                pygame.draw.circle(surf, Colors.MUD_WET, (px, py), r-4) # 坑底

    # -------------------------------------------------------------------------
    # Layer 4: 战壕 (Trenches)
    # -------------------------------------------------------------------------
    def _generate_trench_layer(self):
        """战壕现在依山而建，形成防线"""
        
        # 左上山丘防线 (保护 P1, P2)
        # 第一道防线 (山脚)
        self._draw_complex_trench(vec(200, 1800), vec(1800, 200))
        # 第二道防线 (山腰)
        self._draw_complex_trench(vec(100, 1000), vec(1000, 100))
        
        # 右下山丘防线 (保护 P3, P4)
        w, h = self.width, self.height
        # 第一道防线
        self._draw_complex_trench(vec(w-1800, h-200), vec(w-200, h-1800))
        # 第二道防线
        self._draw_complex_trench(vec(w-1000, h-100), vec(w-100, h-1000))
        
        # 中间连接壕
        self._draw_complex_trench(vec(1600, 2800), vec(2800, 1600))

    def _draw_complex_trench(self, start, end):
        surf = self.bg_surface
        diff = end - start
        length = diff.length()
        direction = diff.normalize()
        perp = vec(-direction.y, direction.x)
        
        segment_len = 50
        num = int(length / segment_len)
        
        points = [start]
        curr = start
        for i in range(num):
            adv = direction * segment_len
            off = perp * (30 if i%2==0 else -30)
            nxt = curr + adv + off
            points.append(nxt)
            curr = nxt
        points.append(end)
        
        if len(points) < 2: return
        
        # 护坡
        pygame.draw.lines(surf, Colors.TRENCH_DIRT, False, points, 45)
        # 沟底
        pygame.draw.lines(surf, Colors.TRENCH_FLOOR, False, points, 18)
        # 鸭板
        for i in range(len(points)-1):
            mid = (points[i] + points[i+1]) / 2
            pygame.draw.line(surf, (50, 40, 30), mid, mid + vec(0,3), 5)
        
        # 碉堡 (随机)
        for i in range(1, len(points)-1):
            if random.random() < 0.2:
                p = points[i]
                pygame.draw.circle(surf, (60, 55, 50), (int(p.x), int(p.y)), 22)
                pygame.draw.rect(surf, (10,10,10), (int(p.x)-6, int(p.y)-6, 12, 12))

    # -------------------------------------------------------------------------
    # Layer 5: 植被与细节
    # -------------------------------------------------------------------------
    def _generate_nature_layer(self):
        surf = self.bg_surface
        for _ in range(400):
            x, y = random.randint(0, self.width), random.randint(0, self.height)
            # 倒木
            if random.random() < 0.5:
                angle = random.uniform(0, 6.28)
                l = random.randint(30, 70)
                ex = x + math.cos(angle)*l
                ey = y + math.sin(angle)*l
                pygame.draw.line(surf, (15,15,15), (x,y), (ex,ey), 4)
            # 树桩
            else:
                pygame.draw.circle(surf, (10,10,10), (x,y), random.randint(3,6))
                
    def _generate_details_layer(self):
        surf = self.bg_surface
        # 铁丝网 (主要在战壕前)
        for _ in range(50):
            cx, cy = random.randint(0, self.width), random.randint(0, self.height)
            for _ in range(8):
                ox, oy = random.randint(-30,30), random.randint(-30,30)
                p1 = (cx+ox, cy+oy)
                p2 = (cx+ox+random.randint(-10,10), cy+oy+random.randint(-10,10))
                pygame.draw.line(surf, Colors.WIRE_RUST, p1, p2, 1)

    # -------------------------------------------------------------------------
    # 游戏对象
    # -------------------------------------------------------------------------
    def _setup_gameplay_objects(self):
        w, h = self.width, self.height
        
        # 基地放置在山顶平原
        self.bases_config = [
            vec(400, 400),       # P1 (Hill Top A)
            vec(1900, 2600),       # P2 (Hill Top A)
            vec(w-400, h-400),   # P3 (Hill Top B)
            vec(w-900, h-600)    # P4 (Hill Top B)
        ]
        
        # 资源点与中立建筑
        try:
            from core.base_classes import OilDerrick, Skyscraper
            # 低谷中央的堡垒
            self.neutral_buildings.append(Skyscraper(self.game, vec(w/2, h/2)))
            # 山腰的油井
            self.neutral_buildings.append(OilDerrick(self.game, vec(1400, h-1000)))
            self.neutral_buildings.append(OilDerrick(self.game, vec(w-1400, 1000)))
        except ImportError:
            pass

    def update(self):
        # 矿脉再生（覆写 update 未调 super，须显式补充——否则矿脉只减不增，
        # 矿区被采到残量后矿车全部停在矿区待命）
        for p in getattr(self, 'ore_patches', []):
            p.update()
        self.fire_manager.update()

    def draw_downlay(self, surface, offset):
        self.fire_manager.draw(surface, offset)
class PARISMAP(GameMap):
    max_players = 4
    name_static = "巴黎围城"
    name_cn_static = "巴黎围城"

    def __init__(self, game):
        super().__init__(game)
        self.name = "巴黎围城"
        self.description = "巴黎，这座光之之城，在末日中成为了最后的堡垒。埃菲尔铁塔在战火中矗立，塞纳河畔的战斗即将打响。"
        self.location = "法国 巴黎"
        self.width = 4800
        self.height = 3200
        self.bg_color = (180, 190, 185)
        self.music_config.update({
            "intro": "paris_intro.mp3",
            "loop": "battle_loop.mp3",
            "final1": "paris_phase1.mp3",
            "final2": "paris_phase2.mp3",
            "final3": "paris_final.mp3",
            "end_win": "paris_victory.mp3",
            "end_lose": "paris_defeat.mp3"
        })
        self.preview_image = pygame.Surface((400, 250))
        self.preview_image.fill((180, 190, 185))
        try:
            font = get_font(30)
            text = font.render("巴黎围城", True, (80, 80, 80))
            self.preview_image.blit(text, (150, 110))
        except:
            pass

    def generate(self, seed=None, visual_only=False):
        super().generate(seed)

        self.bg_surface = pygame.Surface((self.width, self.height))
        self.bg_surface.fill(self.bg_color)
        self.overlay_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

        w, h = self.width, self.height
        cx, cy = w // 2, h // 2

        self.lakes = []
        self.slopes = []
        self.neutral_buildings = []
        self.neutral_units = []

        self.sene = []
        self.roads = []
        self.buildings_dec = []

        border = 400
        self.lakes.append({'rect': pygame.Rect(0, 0, w, border), 'type': 'mountain', 'parts': []})
        self.lakes.append({'rect': pygame.Rect(0, h - border, w, border), 'type': 'mountain', 'parts': []})
        self.lakes.append({'rect': pygame.Rect(0, 0, border, h), 'type': 'mountain', 'parts': []})
        self.lakes.append({'rect': pygame.Rect(w - border, 0, border, h), 'type': 'mountain', 'parts': []})

        base_offset = 1200
        self.bases_config = [
            vec(base_offset, base_offset),
            vec(w - base_offset, base_offset),
            vec(base_offset, h - base_offset),
            vec(w - base_offset, h - base_offset)
        ]

        self._draw_seine()
        self._draw_roads()
        self._draw_eiffel_tower()
        self._draw_arc_de_triomphe()
        self._draw_louvre()
        self._draw_notre_dame()
        self._draw_champs_elysees()
        self._draw_grand_palais()
        self._draw_military_base()
        self._draw_residential_blocks()
        self._draw_parks()
        self._draw_city_buildings()

        if not visual_only:
            self._place_neutral_buildings()

        self.generate_background_texture()

    def _draw_seine(self):
        w, h = self.width, self.height
        self.sene_width = 180

        sene_points = [
            (w * 0.0, h * 0.3),
            (w * 0.15, h * 0.35),
            (w * 0.3, h * 0.4),
            (w * 0.5, h * 0.5),
            (w * 0.7, h * 0.55),
            (w * 0.85, h * 0.6),
            (w * 1.0, h * 0.65)
        ]

        sene_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(len(sene_points) - 1):
            x1, y1 = sene_points[i]
            x2, y2 = sene_points[i + 1]
            width = self.sene_width if i % 2 == 0 else self.sene_width - 30

            pygame.draw.line(sene_surf, (100, 130, 160), (x1, y1), (x2, y2), width)

            for j in range(5):
                offset = random.randint(-30, 30)
                wx = (x1 + x2) // 2 + offset
                wy = (y1 + y2) // 2 + offset
                pygame.draw.circle(sene_surf, (120, 150, 180), (wx, wy), random.randint(10, 25))

        self.bg_surface.blit(sene_surf, (0, 0))

        pygame.draw.rect(self.bg_surface, (80, 100, 80), (0, 0, w, h * 0.25))
        pygame.draw.rect(self.bg_surface, (80, 100, 80), (0, h * 0.75, w, h * 0.25))

    def _draw_roads(self):
        w, h = self.width, self.height

        main_roads = [
            ((0, h * 0.45), (w, h * 0.55)),
            ((w * 0.45, 0), (w * 0.55, h)),
            ((w * 0.2, h * 0.2), (w * 0.8, h * 0.8)),
            ((w * 0.1, h * 0.7), (w * 0.9, h * 0.3))
        ]

        road_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for start, end in main_roads:
            pygame.draw.line(road_surf, (90, 90, 95), start, end, 80)
            pygame.draw.line(road_surf, (110, 110, 115), start, end, 75)

            start_vec = vec(*start)
            end_vec = vec(*end)
            dist = start_vec.distance_to(end_vec)
            steps = int(dist / 100)
            for i in range(steps):
                pos = start_vec.lerp(end_vec, i / steps)
                x, y = int(pos.x), int(pos.y)
                pygame.draw.circle(road_surf, (255, 255, 255), (x, y), 2)

        secondary_roads = [
            ((w * 0.3, 0), (w * 0.3, h)),
            ((w * 0.7, 0), (w * 0.7, h)),
            ((0, h * 0.3), (w, h * 0.3)),
            ((0, h * 0.7), (w, h * 0.7))
        ]

        for start, end in secondary_roads:
            pygame.draw.line(road_surf, (80, 80, 85), start, end, 40)

        self.bg_surface.blit(road_surf, (0, 0))
        # 装饰性道路只烘进背景图，不进 self.roads —— 该字段的数据契约是
        # {"start": vec, "end": vec, "width": int}（可删除/可导出/可绘制贴条），
        # 塞元组会让 draw_roads_screen/delete_road_at/export_layout 全部崩掉
        self.roads = []

    def _draw_eiffel_tower(self):
        w, h = self.width, self.height
        self.eiffel_pos = vec(w * 0.5, h * 0.25)
        ex, ey = int(self.eiffel_pos.x), int(self.eiffel_pos.y)

        tower_surf = pygame.Surface((w, h), pygame.SRCALPHA)

        pygame.draw.polygon(tower_surf, (60, 65, 75), [
            (ex - 180, ey + 400),
            (ex + 180, ey + 400),
            (ex + 80, ey),
            (ex - 80, ey)
        ])

        pygame.draw.polygon(tower_surf, (70, 75, 90), [
            (ex - 80, ey),
            (ex + 80, ey),
            (ex + 40, ey - 150),
            (ex - 40, ey - 150)
        ])

        pygame.draw.polygon(tower_surf, (80, 85, 100), [
            (ex - 40, ey - 150),
            (ex + 40, ey - 150),
            (ex + 15, ey - 300),
            (ex - 15, ey - 300)
        ])

        pygame.draw.line(tower_surf, (90, 95, 110), (ex - 15, ey - 300), (ex, ey - 350), 8)
        pygame.draw.circle(tower_surf, (150, 50, 50), (ex, ey - 350), 15)

        for y in [ey + 100, ey + 200, ey + 320]:
            pygame.draw.line(tower_surf, (50, 55, 70), (ex - 120 + (y - ey) * 0.3, y), (ex + 120 - (y - ey) * 0.3, y), 3)
            pygame.draw.line(tower_surf, (50, 55, 70), (ex - 60 + (y - ey) * 0.15, y - 50), (ex + 60 - (y - ey) * 0.15, y - 50), 3)

        self.bg_surface.blit(tower_surf, (0, 0))

    def _draw_arc_de_triomphe(self):
        w, h = self.width, self.height
        self.arc_pos = vec(w * 0.5, h * 0.5)
        ax, ay = int(self.arc_pos.x), int(self.arc_pos.y)

        arc_surf = pygame.Surface((w, h), pygame.SRCALPHA)

        pygame.draw.rect(arc_surf, (180, 175, 165), (ax - 80, ay - 60, 160, 100))
        pygame.draw.rect(arc_surf, (160, 155, 145), (ax - 70, ay - 50, 140, 80))

        pygame.draw.arc(arc_surf, (180, 175, 165), (ax - 60, ay - 60, 120, 90), math.pi, 2 * math.pi, 20)

        for x_offset in [-60, 60]:
            pygame.draw.rect(arc_surf, (200, 195, 185), (ax + x_offset - 15, ay - 60, 30, 100))

        for i in range(4):
            pygame.draw.line(arc_surf, (140, 135, 125), (ax - 70 + i * 40, ay - 50), (ax - 70 + i * 40, ay + 30), 2)

        pygame.draw.rect(arc_surf, (200, 180, 50), (ax - 5, ay - 70, 10, 10))

        self.bg_surface.blit(arc_surf, (0, 0))

    def _draw_louvre(self):
        w, h = self.width, self.height
        self.louvre_pos = vec(w * 0.25, h * 0.65)
        lx, ly = int(self.louvre_pos.x), int(self.louvre_pos.y)

        louvre_surf = pygame.Surface((w, h), pygame.SRCALPHA)

        pygame.draw.rect(louvre_surf, (180, 170, 150), (lx - 200, ly - 80, 400, 160))

        pygame.draw.rect(louvre_surf, (165, 155, 135), (lx - 190, ly - 70, 380, 140))

        pyramid_points = [
            (lx, ly - 100),
            (lx - 70, ly - 30),
            (lx + 70, ly - 30)
        ]
        pygame.draw.polygon(louvre_surf, (200, 200, 180), pyramid_points)
        pygame.draw.polygon(louvre_surf, (180, 180, 160), pyramid_points, 3)

        for i in range(8):
            for j in range(4):
                px = lx - 160 + i * 45
                py = ly - 40 + j * 30
                pygame.draw.rect(louvre_surf, (150, 145, 130), (px, py, 35, 20), 1)

        self.bg_surface.blit(louvre_surf, (0, 0))

    def _draw_notre_dame(self):
        w, h = self.width, self.height
        self.notre_dame_pos = vec(w * 0.35, h * 0.42)
        nx, ny = int(self.notre_dame_pos.x), int(self.notre_dame_pos.y)

        nd_surf = pygame.Surface((w, h), pygame.SRCALPHA)

        pygame.draw.rect(nd_surf, (135, 135, 140), (nx - 120, ny - 60, 240, 120))

        pygame.draw.rect(nd_surf, (120, 120, 125), (nx - 100, ny - 50, 80, 110))
        pygame.draw.rect(nd_surf, (120, 120, 125), (nx + 20, ny - 50, 80, 110))

        pygame.draw.polygon(nd_surf, (100, 100, 105), [
            (nx - 100, ny - 50),
            (nx - 60, ny - 100),
            (nx - 20, ny - 50)
        ])

        pygame.draw.polygon(nd_surf, (100, 100, 105), [
            (nx + 20, ny - 50),
            (nx + 60, ny - 100),
            (nx + 100, ny - 50)
        ])

        pygame.draw.circle(nd_surf, (80, 80, 85), (nx, ny - 130), 25)
        pygame.draw.circle(nd_surf, (100, 100, 105), (nx, ny - 130), 20, 3)

        for x_offset in [-80, 0, 80]:
            pygame.draw.rect(nd_surf, (110, 110, 115), (nx + x_offset - 8, ny - 80, 16, 50))
            pygame.draw.circle(nd_surf, (90, 90, 95), (nx + x_offset, ny - 90), 10)

        self.bg_surface.blit(nd_surf, (0, 0))

    def _draw_champs_elysees(self):
        w, h = self.width, self.height
        ce_start = vec(w * 0.45, h * 0.42)
        ce_end = vec(w * 0.65, h * 0.58)

        ce_surf = pygame.Surface((w, h), pygame.SRCALPHA)

        pygame.draw.line(ce_surf, (100, 100, 105), (ce_start.x, ce_start.y), (ce_end.x, ce_end.y), 60)

        start_vec = vec(ce_start.x, ce_start.y)
        end_vec = vec(ce_end.x, ce_end.y)
        dist = start_vec.distance_to(end_vec)
        steps = int(dist / 80)

        trees_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(steps):
            pos = start_vec.lerp(end_vec, i / steps)
            x, y = int(pos.x), int(pos.y)

            pygame.draw.circle(trees_surf, (30, 80, 30), (x - 20, y - 30), 25)
            pygame.draw.circle(trees_surf, (40, 90, 40), (x + 20, y - 25), 20)
            pygame.draw.circle(trees_surf, (35, 85, 35), (x, y - 35), 22)

            pygame.draw.line(trees_surf, (60, 40, 20), (x, y), (x, y + 20), 4)

        self.bg_surface.blit(ce_surf, (0, 0))
        self.bg_surface.blit(trees_surf, (0, 0))

    def _draw_grand_palais(self):
        w, h = self.width, self.height
        gp_pos = vec(w * 0.7, h * 0.35)
        gx, gy = int(gp_pos.x), int(gp_pos.y)

        gp_surf = pygame.Surface((w, h), pygame.SRCALPHA)

        pygame.draw.rect(gp_surf, (180, 185, 200), (gx - 150, gy - 50, 300, 100))

        pygame.draw.rect(gp_surf, (200, 205, 220), (gx - 130, gy - 40, 260, 80))

        for i in range(12):
            x = gx - 120 + i * 22
            pygame.draw.arc(gp_surf, (160, 165, 180), (x - 10, gy - 40, 20, 50), 0, math.pi, 3)

        pygame.draw.rect(gp_surf, (170, 175, 190), (gx - 20, gy - 80, 40, 80))
        pygame.draw.circle(gp_surf, (150, 150, 170), (gx, gy - 90), 20)

        self.bg_surface.blit(gp_surf, (0, 0))

    def _draw_military_base(self):
        w, h = self.width, self.height
        mb_pos = vec(w * 0.15, h * 0.25)
        mbx, mby = int(mb_pos.x), int(mb_pos.y)

        mb_surf = pygame.Surface((w, h), pygame.SRCALPHA)

        pygame.draw.rect(mb_surf, (80, 80, 85), (mbx - 200, mby - 150, 400, 300))
        pygame.draw.rect(mb_surf, (60, 60, 65), (mbx - 180, mby - 130, 360, 260))

        for i in range(4):
            for j in range(3):
                bx = mbx - 150 + i * 100
                by = mby - 100 + j * 80
                pygame.draw.rect(mb_surf, (70, 70, 75), (bx, by, 60, 40))
                pygame.draw.rect(mb_surf, (50, 50, 55), (bx + 5, by + 5, 50, 30))

        pygame.draw.circle(mb_surf, (100, 100, 100), (mbx, mby), 50, 5)

        self.bg_surface.blit(mb_surf, (0, 0))

    def _draw_residential_blocks(self):
        w, h = self.width, self.height

        residential_areas = [
            (w * 0.15, h * 0.65),
            (w * 0.85, h * 0.25),
            (w * 0.2, h * 0.15),
            (w * 0.8, h * 0.75)
        ]

        for rx, ry in residential_areas:
            for i in range(4):
                for j in range(3):
                    bx = rx - 100 + i * 45 + random.randint(-8, 8)
                    by = ry - 60 + j * 35 + random.randint(-8, 8)

                    height = random.randint(30, 60)
                    color = (
                        random.randint(180, 220),
                        random.randint(170, 200),
                        random.randint(160, 190)
                    )

                    pygame.draw.rect(self.bg_surface, color, (bx, by, 35, height))

                    for wy in range(int(by + 4), int(by + height - 4), 10):
                        for wx in range(int(bx + 4), int(bx + 30), 12):
                            pygame.draw.rect(self.bg_surface, (150, 180, 200), (wx, wy, 6, 6), 1)

    def _draw_parks(self):
        w, h = self.width, self.height

        park_positions = [
            (w * 0.1, h * 0.5),
            (w * 0.9, h * 0.4),
            (w * 0.75, h * 0.75),
            (w * 0.25, h * 0.2)
        ]

        for px, py in park_positions:
            park_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(park_surf, (100, 130, 80), (px - 100, py - 70, 200, 140))
            pygame.draw.ellipse(park_surf, (110, 140, 90), (px - 80, py - 50, 160, 100))

            for _ in range(15):
                tx = px + random.randint(-80, 80)
                ty = py + random.randint(-50, 50)
                tree_size = random.randint(6, 15)
                pygame.draw.circle(park_surf, (40, 90, 40), (tx, ty), tree_size)
                pygame.draw.circle(park_surf, (50, 100, 50), (tx, ty), tree_size - 2)

            self.bg_surface.blit(park_surf, (0, 0))

    def _draw_city_buildings(self):
        w, h = self.width, self.height

        building_zones = [
            (w * 0.1, h * 0.3, w * 0.25, h * 0.4),
            (w * 0.7, h * 0.6, w * 0.9, h * 0.8),
            (w * 0.6, h * 0.1, w * 0.85, h * 0.25)
        ]

        for zone_x1, zone_y1, zone_x2, zone_y2 in building_zones:
            x1, y1 = zone_x1, zone_y1
            x2, y2 = zone_x2, zone_y2

            for _ in range(8):
                bx = random.randint(int(x1), int(x2))
                by = random.randint(int(y1), int(y2))
                bw = random.randint(40, 80)
                bh = random.randint(60, 120)

                base_color = (
                    random.randint(160, 200),
                    random.randint(150, 180),
                    random.randint(140, 170)
                )
                pygame.draw.rect(self.bg_surface, base_color, (bx, by, bw, bh))

                window_color = (180, 200, 220)
                for wy in range(by + 10, by + bh - 10, 15):
                    for wx in range(bx + 8, bx + bw - 8, 12):
                        lit = random.random() > 0.3
                        color = window_color if lit else (80, 80, 90)
                        pygame.draw.rect(self.bg_surface, color, (wx, wy, 6, 8))

    def _place_neutral_buildings(self):
        from units import FactoryBuilding, PowerPlant, RadarBuilding, Airfield
        from core.base_classes import CivilianHouse, Bridge

        w, h = self.width, self.height

        self.neutral_buildings.append(PowerPlant(self.game, vec(w * 0.12, h * 0.35), "neutral"))
        self.neutral_buildings.append(PowerPlant(self.game, vec(w * 0.88, h * 0.65), "neutral"))
        self.neutral_buildings.append(PowerPlant(self.game, vec(w * 0.35, h * 0.12), "neutral"))
        self.neutral_buildings.append(PowerPlant(self.game, vec(w * 0.65, h * 0.88), "neutral"))

        self.neutral_buildings.append(FactoryBuilding(self.game, vec(w * 0.2, h * 0.8), "neutral"))
        self.neutral_buildings.append(FactoryBuilding(self.game, vec(w * 0.8, h * 0.2), "neutral"))
        self.neutral_buildings.append(FactoryBuilding(self.game, vec(w * 0.15, h * 0.15), "neutral"))
        self.neutral_buildings.append(FactoryBuilding(self.game, vec(w * 0.85, h * 0.85), "neutral"))

        self.neutral_buildings.append(Airfield(self.game, vec(w * 0.08, h * 0.5), "neutral"))
        self.neutral_buildings.append(Airfield(self.game, vec(w * 0.92, h * 0.5), "neutral"))

        self.neutral_buildings.append(RadarBuilding(self.game, vec(w * 0.5, h * 0.08), "neutral"))
        self.neutral_buildings.append(RadarBuilding(self.game, vec(w * 0.5, h * 0.92), "neutral"))

        for i in range(5):
            hx = w * 0.05 + i * 100
            hy = h * 0.1 + random.randint(0, 200)
            self.neutral_buildings.append(CivilianHouse(self.game, vec(hx, hy)))

        sene_x = w * 0.5
        self.neutral_buildings.append(Bridge(self.game, vec(sene_x, h * 0.45), "neutral"))
        self.neutral_buildings.append(Bridge(self.game, vec(sene_x, h * 0.55), "neutral"))

    def generate_background_texture(self):
        pass

    def update_effects(self, game):
        pass
class BERINGMAP(GameMap):
    max_players = 4

    def __init__(self, game):
        super().__init__(game)
        self.name="白令海峡"
        self.dlc="重返末日"


class ArenaColiseumMap(GameMap):
    """铁血竞技场：争锋频道专属地图（不进普通地图轮换池）。

    小而紧凑（2400x1600），无基地——双方出兵锚点（bases_config 仅作锚点，
    不生成 BaseBuilding）左右对峙，中央开阔为斗兽场式竞技区。
    neutral_spots 是每轮随机生成中立建筑/单位的候选点位（竞技场回合逻辑使用）。
    """
    max_players = 2
    name_static = "铁血竞技场"
    name_cn_static = "铁血竞技场"

    def __init__(self, game):
        super().__init__(game)
        self.name = "铁血竞技场"
        self.description = "  荒漠深处的地下斗兽场。两支按价组建的军团在此生死相搏，胜者通吃，败者归零。"
        self.location = "未知 区域 07"
        self.width = 2400
        self.height = 1600
        self.bg_color = (62, 56, 46)  # 沙土竞技场地
        # 仅作双方出兵锚点（竞技场无基地）
        self.bases_config = [
            vec(300, self.height // 2),              # 红方 (左)
            vec(self.width - 300, self.height // 2), # 蓝方 (右)
        ]
        # 每轮中立建筑/单位的候选点位（避开双方基地半径 500px 的出生区）
        self.neutral_spots = [
            vec(1200, 300), vec(1200, 800), vec(1200, 1300),
            vec(950, 550), vec(1450, 550), vec(950, 1050), vec(1450, 1050),
            vec(780, 220), vec(1620, 220), vec(780, 1380), vec(1620, 1380),
        ]
        # 双方散布出兵半区（arena_start_round 组军随机落点，组心+组内偏移）
        self.spawn_zones = {
            "team_0": pygame.Rect(140, 160, 920, 1280),
            "team_1": pygame.Rect(1340, 160, 920, 1280),
        }
        # 程序化预览图
        self.preview_image = pygame.Surface((400, 250))
        self.preview_image.fill((62, 56, 46))
        pygame.draw.circle(self.preview_image, (80, 72, 58), (200, 125), 90, 3)
        pygame.draw.circle(self.preview_image, (80, 72, 58), (200, 125), 60, 2)
        pygame.draw.rect(self.preview_image, (160, 60, 50), (20, 110, 30, 30))
        pygame.draw.rect(self.preview_image, (60, 90, 170), (350, 110, 30, 30))

    def generate(self, seed=None, visual_only=False):
        super().generate(seed)  # 注意：父类会重置 bases_config，随后恢复
        self.lakes = []          # 竞技场无水域（无舰船）
        self.slopes = []
        self.neutral_buildings = []  # 中立单位/建筑由竞技场回合逻辑每轮随机生成
        self.bases_config = [
            vec(300, self.height // 2),              # 红方 (左)
            vec(self.width - 300, self.height // 2), # 蓝方 (右)
        ]
        self.generate_background_texture()

    def generate_background_texture(self):
        super().generate_background_texture()
        surf = self.bg_surface
        w, h = self.width, self.height
        cx, cy = w // 2, h // 2

        # 1. 沙地噪点质感
        for _ in range(6000):
            x = random.randint(0, w - 4)
            y = random.randint(0, h - 4)
            c = random.randint(-10, 10)
            pygame.draw.rect(surf, (62 + c, 56 + c, 46 + c), (x, y, 4, 4))

        # 2. 斗兽场同心环 (浅色刻线)
        for r in (150, 280, 410, 540):
            pygame.draw.circle(surf, (78, 70, 56), (cx, cy), r, 6)
            pygame.draw.circle(surf, (50, 45, 37), (cx, cy), r + 6, 2)

        # 3. 外圈竞技场围墙 (粗环 + 垛口)
        pygame.draw.circle(surf, (86, 78, 62), (cx, cy), 700, 26)
        pygame.draw.circle(surf, (46, 42, 34), (cx, cy), 714, 3)
        pygame.draw.circle(surf, (46, 42, 34), (cx, cy), 686, 3)
        import math as _m
        for i in range(36):
            a = i * 10
            px = cx + int(700 * _m.cos(_m.radians(a)))
            py = cy + int(700 * _m.sin(_m.radians(a)))
            pygame.draw.rect(surf, (92, 84, 66), (px - 9, py - 9, 18, 18))

        # 4. 中央徽记 (双环 + 交叉剑)
        pygame.draw.circle(surf, (120, 40, 30), (cx, cy), 100, 10)
        pygame.draw.circle(surf, (120, 40, 30), (cx, cy), 70, 4)
        for sa in (45, 135, 225, 315):
            dx = int(60 * _m.cos(_m.radians(sa)))
            dy = int(60 * _m.sin(_m.radians(sa)))
            pygame.draw.line(surf, (140, 130, 110), (cx - dx, cy - dy), (cx + dx, cy + dy), 8)

        # 5. 双方出兵区平台 (红左蓝右，无基地纯标记)
        for pos, color in ((self.bases_config[0], (150, 60, 50)),
                           (self.bases_config[1], (60, 90, 170))):
            bx, by = int(pos.x), int(pos.y)
            pygame.draw.rect(surf, (70, 64, 52), (bx - 140, by - 140, 280, 280), border_radius=20)
            pygame.draw.rect(surf, color, (bx - 140, by - 140, 280, 280), 5, border_radius=20)

        # 6. 通道辐条 (连接基地与中央区)
        for a in (0, 90, 180, 270):
            dx = int(560 * _m.cos(_m.radians(a)))
            dy = int(560 * _m.sin(_m.radians(a)))
            pygame.draw.line(surf, (74, 67, 54), (cx - dx, cy - dy), (cx + dx, cy + dy), 44)
            pygame.draw.line(surf, (66, 60, 48), (cx - dx, cy - dy), (cx + dx, cy + dy), 2)


class ArenaSeaMap(GameMap):
    """海上竞技场：争锋频道专属海战地图（不进普通地图轮换池）。

    全域水域 2400x1600，中央走廊分布少量礁石岛（纯掩体，不生成建筑）。
    只出海军与空军（ARENA_SEA_POOL）；海军 in_water 判定基于全域 water
    lake 与 islands（岛上即陆地），islands 严格限制在中央走廊内且不与
    spawn_zones 的组员偏移半径（90+75px）相交，防止舰船出生在岛上卡死。
    """
    max_players = 2
    name_static = "海上竞技场"
    name_cn_static = "海上竞技场"

    def __init__(self, game):
        super().__init__(game)
        self.name = "海上竞技场"
        self.description = "  怒海争锋。两支混编舰队在暗礁环绕的公海狭路相逢，浪涛之下只有胜者能返航。"
        self.location = "未知 公海 13"
        self.width = 2400
        self.height = 1600
        self.bg_color = (24, 62, 96)  # 深海蓝
        # 仅作双方出兵锚点（竞技场无基地，锚点落在水面）
        self.bases_config = [
            vec(300, self.height // 2),              # 红方 (左)
            vec(self.width - 300, self.height // 2), # 蓝方 (右)
        ]
        # 双方散布出兵半区（与斗兽场同布局，右缘/左缘留出岛距安全余量）
        self.spawn_zones = {
            "team_0": pygame.Rect(140, 160, 880, 1280),
            "team_1": pygame.Rect(1380, 160, 880, 1280),
        }
        # 中立舰船候选点位（水面，避开岛与出兵区）
        self.neutral_spots = [
            vec(1200, 160), vec(980, 480), vec(1420, 480),
            vec(980, 1120), vec(1420, 1120), vec(1200, 1440),
            vec(760, 800), vec(1640, 800),
        ]
        # 中立舰船工厂（arena_spawn_neutrals 按点位随机实例化，纯点缀不参战）
        self.neutral_makers = [
            (lambda g, p: MissileBoat(g, p, "neutral"), 3),
            (lambda g, p: AAFrigate(g, p, "neutral"), 2),
        ]
        # 程序化预览图
        self.preview_image = pygame.Surface((400, 250))
        self.preview_image.fill((24, 62, 96))
        pygame.draw.ellipse(self.preview_image, (88, 80, 66), (178, 98, 44, 36))
        pygame.draw.rect(self.preview_image, (160, 60, 50), (20, 110, 30, 30))
        pygame.draw.rect(self.preview_image, (60, 90, 170), (350, 110, 30, 30))

    def generate(self, seed=None, visual_only=False):
        super().generate(seed)  # 父类会重置 lakes/bases_config，随后恢复
        # 全域水域：is_naval 单位的 in_water 判定依据（type 必须为 'water'）
        self.lakes = [{'rect': pygame.Rect(0, 0, self.width, self.height),
                       'type': 'water', 'parts': []}]
        self.slopes = []
        self.neutral_buildings = []  # 中立舰船由竞技场回合逻辑每轮随机生成
        # 中央礁石岛：Rect 列表，"不在任何岛上"即视为水中
        self.islands = [
            pygame.Rect(1100, 300, 150, 130),
            pygame.Rect(1090, 730, 180, 150),
            pygame.Rect(1110, 1170, 140, 120),
        ]
        self.bases_config = [
            vec(300, self.height // 2),              # 红方 (左)
            vec(self.width - 300, self.height // 2), # 蓝方 (右)
        ]
        self.generate_background_texture()

    def generate_background_texture(self):
        super().generate_background_texture()
        surf = self.bg_surface
        w, h = self.width, self.height
        cx, cy = w // 2, h // 2

        # 1. 深海横向渐变（上深下浅分带）
        for band in range(8):
            c = 26 + band * 5
            pygame.draw.rect(surf, (max(0, c - 12), c + 22, c + 48),
                             (0, h * band // 8 - 1, w, h // 8 + 2))

        # 2. 波纹噪点（短亮横线模拟浪尖）
        for _ in range(5000):
            x = random.randint(0, w - 10)
            y = random.randint(0, h - 2)
            c = random.randint(-8, 14)
            pygame.draw.line(surf, (40 + c, 78 + c, 116 + c),
                             (x, y), (x + random.randint(3, 8), y), 1)

        # 3. 中央航道同心刻线（斗兽场式）
        for r in (200, 340, 480):
            pygame.draw.circle(surf, (34, 68, 102), (cx, cy), r, 4)

        # 4. 礁石岛（浅滩晕圈 + 岩体 + 噪点）
        for isl in self.islands:
            shallow = isl.inflate(56, 56)
            pygame.draw.ellipse(surf, (52, 100, 132), shallow)
            pygame.draw.rect(surf, (88, 80, 66), isl, border_radius=24)
            pygame.draw.rect(surf, (112, 102, 84), isl, 5, border_radius=24)
            for _ in range(30):
                px = random.randint(isl.left, max(isl.left, isl.right - 5))
                py = random.randint(isl.top, max(isl.top, isl.bottom - 5))
                pygame.draw.rect(surf, (70, 62, 50), (px, py, 5, 5))

        # 5. 双方出兵海域浮标圈（红左蓝右）
        for pos, color in ((self.bases_config[0], (150, 60, 50)),
                           (self.bases_config[1], (60, 90, 170))):
            bx, by = int(pos.x), int(pos.y)
            pygame.draw.circle(surf, (30, 60, 92), (bx, by), 150)
            pygame.draw.circle(surf, color, (bx, by), 150, 6)
            for a in range(0, 360, 30):
                px = bx + int(170 * math.cos(math.radians(a)))
                py = by + int(170 * math.sin(math.radians(a)))
                pygame.draw.circle(surf, color, (px, py), 7)


