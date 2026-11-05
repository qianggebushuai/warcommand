# -*- coding: utf-8 -*-
"""多边形地形编辑器 + 游戏端应用 冒烟。"""
import os
import sys
import json

os.environ['SDL_VIDEODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from pygame.math import Vector2 as vec

PASS = TOTAL = 0
def check(name, cond, detail=""):
    global PASS, TOTAL
    TOTAL += 1
    if cond:
        PASS += 1
        print("PASS  " + name)
    else:
        print("FAIL  " + name + "  " + str(detail))

# SCREEN_WIDTH import 陷阱：先建真窗口再 import 项目模块
pygame.init()
pygame.display.set_mode((1600, 900))

from map_layout_editor import MapLayoutEditor, EditorGame
from maps.map_data import (point_in_poly, poly_bbox, lake_contains,
                           island_contains, slope_contains)
from units.base import Unit

# ---- 固定测试多边形 ----
WATER = [(1000, 1000), (1400, 1000), (1400, 1300), (1000, 1300)]   # 水域矩形
ISLE  = [(1100, 1050), (1300, 1050), (1300, 1250), (1100, 1250)]   # 水中岛
SLOPE = [(2000, 2000), (2200, 2000), (2100, 2200)]                 # 斜坡三角

ed = MapLayoutEditor(0)
m = ed.map_obj
check("1 编辑器启动且干净背景快照存在", ed._bg_clean is not None)

# JSON 备份/恢复：测试 save 不能污染真实布局文件
from maps.map_data import _map_layout_path
_layout_path = _map_layout_path(m.__class__.__name__)
_json_backup = None
if os.path.exists(_layout_path):
    _json_backup = open(_layout_path, 'rb').read()

# 起点清零：JSON 预载的 terrain 与注入条目一并清掉（计数断言从 0 起）
m.terrain_polys = []
ed.game.lakes = []
if hasattr(m, 'islands'):
    m.islands = [i for i in m.islands if not (isinstance(i, dict) and i.get('from_terrain'))]
if hasattr(m, 'slopes'):
    m.slopes = [s for s in m.slopes if not (isinstance(s, dict) and s.get('from_terrain'))]

# 2. 射线法：内/外判定 + 包围盒
check("2 point_in_poly 内部", point_in_poly(WATER, 1200, 1150) is True)
check("3 point_in_poly 外部", point_in_poly(WATER, 1500, 1150) is False)
bb = poly_bbox(WATER)
check("4 poly_bbox 正确", bb.topleft == (1000, 1000) and bb.width in (400, 401)
      and bb.height in (300, 301), bb)

# 5-7. 编辑器交互：加点→闭合（Enter 语义）
ed.terrain_mode = "water"
ed.terrain_drawing = [vec(1000, 1000)]          # 只有 1 点
ed.close_terrain_poly()
check("5 不足3点拒闭合", len(m.terrain_polys) == 0)
ed.terrain_drawing = [vec(*p) for p in WATER]   # 4 顶点
ed.dirty = False
ed.close_terrain_poly()
check("6 Enter 闭合入列", len(m.terrain_polys) == 1
      and m.terrain_polys[0]["type"] == "water" and ed.dirty)
ed.terrain_mode = "land"
ed.terrain_drawing = [vec(*p) for p in ISLE]
ed.close_terrain_poly()
ed.terrain_mode = "slope"
ed.terrain_drawing = [vec(*p) for p in SLOPE]
ed.close_terrain_poly()
check("7 land/slope 各闭合一个", len(m.terrain_polys) == 3
      and [t["type"] for t in m.terrain_polys] == ["water", "land", "slope"])

# 8. 游戏端应用：water→game.lakes / land→islands / slope→slopes
ed.game.lakes = []
m.apply_terrain_polys(ed.game)
n_lakes = len([l for l in ed.game.lakes if isinstance(l, dict) and l.get('from_terrain')])
n_isles = len([i for i in m.islands if isinstance(i, dict) and i.get('from_terrain')])
n_slops = len([s for s in m.slopes if isinstance(s, dict) and s.get('from_terrain')])
check("8 三容器注入", n_lakes == 1 and n_isles == 1 and n_slops == 1,
      (n_lakes, n_isles, n_slops))

# 9. 幂等：二次应用 poly 条目不翻倍（game.lakes 已被对齐为官方湖+poly，总长含官方湖）
m.apply_terrain_polys(ed.game)
n_lakes2 = len([l for l in ed.game.lakes if isinstance(l, dict) and l.get('from_terrain')])
check("9 二次应用幂等", n_lakes2 == 1 and ed.game.lakes is m.lakes,
      (n_lakes2, len(ed.game.lakes)))

# 10-12. 三级判定函数：bbox 粗测 + 射线精测
w = ed.game.lakes[-1]
check("10 lake_contains 水内/水外", lake_contains(w, 1200, 1150)
      and not lake_contains(w, 1500, 1150) and not lake_contains(w, 999, 1150))
isle = m.islands[-1]
check("11 island_contains 岛内/岛外", island_contains(isle, 1200, 1100)
      and not island_contains(isle, 1050, 1020)
      and not island_contains(isle, 3000, 3000))
sl = m.slopes[-1]
check("12 slope_contains 坡内/坡外", slope_contains(sl, 2100, 2050)
      and not slope_contains(sl, 2300, 2100) and not slope_contains(sl, 1500, 1500))

# 13. 真实 Unit 走新消费点：水上不可通行、岛上可通行
class _Probe(Unit):
    def __init__(self, game, pos):
        super().__init__(game, pos, "team_0")
        self.speed = 100

probe = _Probe(ed.game, vec(300, 300))
ed.game.all_buildings = []
ed.game.current_map = m
on_water = probe.check_move_validity(vec(1050, 1020))       # 水域且非岛
check("13a 水上 can_pass=False", on_water is False)
on_isle = probe.check_move_validity(vec(1200, 1100))        # 岛上（水中陆地）
check("13b 岛上 can_pass=True", on_isle is True)
on_land = probe.check_move_validity(vec(3000, 3000))        # 普通地面
check("13c 普通地面 can_pass=True", on_land is True)

# 14. _check_drowning 走新消费点：水面进入溺水计时/岛上不计时
probe.pos = vec(1050, 1020)
probe._check_drowning()
check("14a 水面触发溺水计时", getattr(probe, 'drown_timer', 0) > 0)
probe2 = _Probe(ed.game, vec(1200, 1100))
probe2._check_drowning()
check("14b 岛上不溺水", getattr(probe2, 'drown_timer', 0) == 0)

# 15. 编辑器命中/删除多边形
idx = ed.hit_terrain_poly(vec(1200, 1100))
check("15a hit_terrain_poly 命中", idx >= 0 and m.terrain_polys[idx]["type"] == "land")
label = ed.delete_terrain_poly(vec(1200, 1100))
after = ed.hit_terrain_poly(vec(1200, 1100))
# 岛在水域中心：删岛后同点应命中 water 层（从后往前命中优先级正确）
check("15b delete_terrain_poly 删除岛", label == "陆地"
      and len(m.terrain_polys) == 2
      and after >= 0 and m.terrain_polys[after]["type"] == "water")

# 16. 保存→JSON terrain 键（含 color/alpha）→新地图对象读回一致
# 给已有 poly 涂自定义色验证往返
m.terrain_polys[0]["color"] = [25, 60, 120]
m.terrain_polys[0]["alpha"] = 90
path = m.save_layout()
data = json.load(open(path, encoding="utf-8"))
terr = data.get("terrain", [])
check("16a JSON 含 terrain+color/alpha", len(terr) == 2
      and [t["type"] for t in terr] == ["water", "slope"]
      and terr[0]["color"] == [25, 60, 120] and terr[0]["alpha"] == 90, terr)
m2 = type(m)(None)
m2.game = EditorGame(m2)
m2.generate(seed=0)
n_official_before = len(m2.lakes)
m2.apply_layout_override()
n_official_after = len([l for l in m2.lakes
                        if not (isinstance(l, dict) and l.get('from_terrain'))])
check("16b 读回 terrain+color/alpha 且官方 water 让位",
      len(m2.terrain_polys) == 2
      and m2.terrain_polys[0]["poly"] == [(float(p[0]), float(p[1])) for p in WATER]
      and m2.terrain_polys[0].get("color") == [25, 60, 120]
      and m2.terrain_polys[0].get("alpha") == 90
      and m2.terrain_polys[1]["type"] == "slope"
      and n_official_after == 0,
      (n_official_before, n_official_after, [t.get('color') for t in m2.terrain_polys]))

# 17. 烘焙不崩
try:
    m2.bake_terrain_visual()
    ok17 = True
except Exception as e:
    ok17 = False
    print("  bake err:", e)
check("17 bake_terrain_visual", ok17)

# 18. 整帧绘制（已确认多边形 + 绘制中橡皮筋）不崩
ed.terrain_mode = "water"
ed.terrain_drawing = [vec(500, 500), vec(700, 500), vec(600, 650)]
try:
    ed.draw_background()
    ed.draw_terrain_polys()
    ed.draw_buildings()
    ed.draw_spawn_points()
    ed.draw_panel()
    ed.draw_status()
    ok18 = True
except Exception as e:
    ok18 = False
    print("  draw err:", e)
check("18 整帧绘制含地形叠加", ok18)

# 19. 取消绘制（右键/Esc 语义）
ed.cancel_terrain_drawing()
check("19 取消绘制清空顶点", ed.terrain_drawing == [] and ed.terrain_mode == "water")

# 20. 模拟 level_mixin synced_lakes 覆盖后幂等恢复
# （复刻 synced 分支：current_map.lakes = self.lakes 同引用后才调 apply）
snapshot = [{'rect': pygame.Rect(50, 50, 100, 100), 'parts': [], 'type': 'water'}]
ed.game.lakes = snapshot
m.lakes = snapshot
m.apply_terrain_polys(ed.game)
restored = [l for l in ed.game.lakes if isinstance(l, dict) and l.get('from_terrain')]
check("20 synced 覆盖后恢复 poly 水域", len(restored) == 1
      and point_in_poly(restored[0]['poly'], 1200, 1150)
      and len(ed.game.lakes) == 2 and ed.game.lakes is m.lakes,
      [l.get('from_terrain') for l in ed.game.lakes])

# 21. WaterFX：波纹生成 + 海浪/整帧绘制不崩
from maps.environment import WaterFX
fx = WaterFX()
fx.update_and_draw(ed.win, vec(1000, 900), 1.0, ed.game.lakes)
for _ in range(200):                       # 推进 200 帧触发波纹生成/扩散
    fx.update_and_draw(ed.win, vec(1000, 900), 1.0, ed.game.lakes)
check("21 WaterFX 波纹+海浪运行", len(fx.ripples) > 0, len(fx.ripples))
# 无 poly 水域时清空且不崩
fx.update_and_draw(ed.win, vec(0, 0), 1.0, [{'rect': pygame.Rect(0, 0, 10, 10)}])
check("21b 无 poly 水域不崩且清空", fx.ripples == [])

# 22. 编辑器整帧绘制（含新面板行与选中态）
ed.selected_terrain = 0
try:
    ed.draw_background()
    ed.draw_terrain_polys()
    ed.draw_buildings()
    ed.draw_spawn_points()
    ed.draw_panel()
    ed.draw_status()
    ok22 = True
except Exception as e:
    ok22 = False
    print("  draw err:", e)
check("22 编辑器整帧绘制含颜色面板+选中态", ok22)

# 23. 海浪线/波纹避开岛屿（WaterFX islands 剔除）
import random
import maps.environment as _env
fx2 = WaterFX()
water = {'from_terrain': True, 'type': 'water', 'poly': [(0, 0), (400, 0), (400, 120), (0, 120)],
         'rect': pygame.Rect(0, 0, 401, 121), 'color': [40, 90, 160], 'alpha': 120}
isle = pygame.Rect(150, 0, 100, 120)          # 水域中央的岛
recorded = []
_orig_lines = pygame.draw.lines
pygame.draw.lines = lambda s, c, cl, pts, w=1: recorded.append(list(pts))
try:
    random.seed(7)
    for _ in range(120):                       # 跑够波浪推移一整轮
        fx2.update_and_draw(ed.win, vec(0, 0), 1.0, [water], islands=[isle])
finally:
    pygame.draw.lines = _orig_lines
bad_pts = [p for seg in recorded for p in seg if isle.collidepoint(int(p[0]), int(p[1]))]
check("23a 海浪线不落岛上", len(recorded) > 0 and not bad_pts,
      (len(recorded), len(bad_pts), bad_pts[:3]))
bad_rip = [rp for rp in fx2.ripples if isle.collidepoint(int(rp[0]), int(rp[1]))]
check("23b 波纹不落岛上", fx2.ripples and not bad_rip,
      (len(fx2.ripples), len(bad_rip)))

# 24. CrossfireMap 深海波出生+生长不碰岛
m2 = None
try:
    from maps.map_data import CrossfireMap
    m2 = CrossfireMap(type('G', (), {})())
    m2.generate(12345)
    random.seed(3)
    m2.waves = []
    for _ in range(3000):
        m2.update_effects(type('G', (), {'current_music_state': None, 'camera_offset': vec(0, 0),
                                         'zoom': 1.0, 'screen': ed.win,
                                         'env_manager': type('E', (), {'set_weather': lambda s, w: None})()})())
    irl = [i for i in getattr(m2, 'islands', []) if isinstance(i, pygame.Rect)]
    deep = [w for w in m2.waves if w[5] == 1]
    bad = [w for w in deep
           if any(i.collidelist([pygame.Rect(int(w[0]-w[2]), int(w[1]-w[2]), int(w[2]*2), int(w[2]*2))]) != -1
                  for i in irl)]
    check("24 深海波圆全程不碰岛", deep and not bad, (len(deep), len(bad)))
except Exception as e:
    check("24 深海波圆全程不碰岛", False, e)

# 25. WaterFX 波浪线视口剔除：宽 4000 水域只画屏内段
try:
    fx3 = WaterFX()
    water3 = {'from_terrain': True, 'type': 'water', 'poly': [(0, 0), (4000, 0), (4000, 120), (0, 120)],
              'rect': pygame.Rect(0, 0, 4001, 121), 'color': [40, 90, 160], 'alpha': 120}
    rec3 = []
    pygame.draw.lines = lambda s, c, cl, pts, w=1: rec3.append(list(pts))
    try:
        random.seed(11)
        for _ in range(90):
            fx3.update_and_draw(ed.win, vec(0, 0), 1.0, [water3], islands=[])
    finally:
        pygame.draw.lines = _orig_lines
    xs = [p[0] for seg in rec3 for p in seg]
    check("25 波浪线只画屏内(x<=1608)",
          rec3 and xs and max(xs) <= 1608 and max(xs) >= 1500, (len(rec3), max(xs) if xs else -1))
except Exception as e:
    check("25 波浪线只画屏内(x<=1608)", False, e)

# 26. 灯塔绘制不再创建大光束面
try:
    from units.buildings import Lighthouse

    class LHGame:
        particles = pygame.sprite.Group()
        all_units = []
        all_buildings = []
        projectiles = []
        team_resources = {"neutral": 0}
        frame_count = 0
        is_online = False
        max_cmd_exp = 0

        class _M:
            width = 8000
            height = 8000
            lakes = []
        current_map = _M()

    made = []
    _orig_surface3 = pygame.Surface

    def _spy3(size, *a, **k):
        made.append(size)
        return _orig_surface3(size, *a, **k)

    lh = Lighthouse(LHGame(), vec(2000, 2000))
    pygame.Surface = _spy3
    try:
        lh.draw(ed.win, vec(0, 0), 1.0)
    finally:
        pygame.Surface = _orig_surface3
    big = [s for s in made if len(s) >= 2 and s[0] >= 700]
    check("26 灯塔绘制无大光束面(<=700px)", not big, made[:5])
except Exception as e:
    check("26 灯塔绘制无大光束面(<=700px)", False, e)

# 27. 深海波视口剔除：圆心出屏但圆面压屏的画，完全出屏的不画
try:
    from maps.map_data import CrossfireMap
    m3 = CrossfireMap(type('G', (), {})())
    m3.generate(12345)
    m3.shore_points = []
    m3.waves = [[-2000, -2000, 160, 160, 100, 1],   # 完全出屏
                [-300, 500, 320, 320, 100, 1]]      # 圆心出屏但压屏边
    made3 = []
    _orig_surface4 = pygame.Surface

    def _spy4(size, *a, **k):
        made3.append(size)
        return _orig_surface4(size, *a, **k)

    _orig_random = random.random
    random.random = lambda: 0.99     # 禁用新波生成
    pygame.Surface = _spy4
    gmock = type('G', (), {'current_music_state': None, 'camera_offset': vec(0, 0), 'zoom': 1.0,
                           'screen': ed.win,
                           'env_manager': type('E', (), {'set_weather': lambda s, w: None})()})()
    try:
        m3.update_effects(gmock)
    finally:
        pygame.Surface = _orig_surface4
        random.random = _orig_random
    check("27 深海波视口剔除(出屏不画/压屏画)", len(made3) == 1, made3[:4])
except Exception as e:
    check("27 深海波视口剔除(出屏不画/压屏画)", False, e)

# 28. 背景缓存精确 zoom 对齐：同取整档内缩放不串档（0.65→0.74 都曾属 0.7 档）
try:
    import types
    from types import SimpleNamespace
    from maps.map_data import GameMap
    from core.base_classes import vec as _vec
    bg = pygame.Surface((2000, 2000))
    bg.fill((80, 80, 80))
    pygame.draw.rect(bg, (255, 0, 0), (500, 500, 100, 100))  # 世界坐标标记块
    stub = SimpleNamespace(bg_surface=bg, width=2000, height=2000)
    probe = pygame.Surface((1600, 900))
    GameMap.draw_background(stub, probe, _vec(0, 0), 0.65)   # 进档
    GameMap.draw_background(stub, probe, _vec(0, 0), 0.74)   # 同档漂移（旧码会复用 0.65 旧图）
    got = probe.get_at((407, 407))[:3]                       # 0.74 时标记中心应在此
    stale = probe.get_at((357, 357))[:3]                     # 0.65 旧图标记中心（错位位置）
    check("28 背景缩放精确对齐(不串档)", got == (255, 0, 0) and stale != (255, 0, 0),
          (got, stale, getattr(stub, '_bg_cache_key', None)))
except Exception as e:
    check("28 背景缩放精确对齐(不串档)", False, e)

# 29. 重叠多边形同点循环选择：水域(大,后画=最上层)压住陆地(小)，同点连点轮换
try:
    ed2 = MapLayoutEditor(0)
    m4 = ed2.map_obj
    m4.terrain_polys = [
        {"type": "water", "poly": [(0, 0), (1000, 0), (1000, 600), (0, 600)],
         "rect": pygame.Rect(0, 0, 1001, 601), "color": [30, 80, 140], "alpha": 120},
        {"type": "land", "poly": [(400, 200), (600, 200), (600, 400), (400, 400)],
         "rect": pygame.Rect(400, 200, 201, 201), "color": [200, 180, 120], "alpha": 150},
    ]
    p_in = vec(500, 300)     # 水域与陆地都包含
    p_out = vec(100, 100)    # 仅水域包含
    ed2.selected_terrain = None
    ed2.select_terrain_at(p_in)      # 最上层=land(1)
    r1 = ed2.selected_terrain
    ed2.select_terrain_at(p_in)      # 循环→water(0)
    r2 = ed2.selected_terrain
    ed2.select_terrain_at(p_in)      # 循环→land(1)
    r3 = ed2.selected_terrain
    ed2.selected_terrain = None
    ed2.select_terrain_at(p_out)     # 仅水域 → 直接 water(0)
    r4 = ed2.selected_terrain
    # 循环选中 land 后删除：应删 land(1) 而非最上层 water
    ed2.selected_terrain = 1
    ed2.delete_terrain_at = None
    label = ed2.delete_terrain_poly(p_in)
    rest = [t["type"] for t in m4.terrain_polys]
    check("29 重叠多边形同点循环选择+删选中项",
          (r1, r2, r3, r4) == (1, 0, 1, 0) and rest == ["water"], (r1, r2, r3, r4, label, rest))
except Exception as e:
    check("29 重叠多边形同点循环选择+删选中项", False, e)

# 30. 悬崖多边形：编辑器绘制→注入 lakes→地面单位阻挡→非水不溺水→JSON 回环
try:
    CLIFF = [(4000, 4000), (4500, 4000), (4500, 4300), (4000, 4300)]
    m.terrain_polys.append({"type": "cliff", "poly": CLIFF, "rect": poly_bbox(CLIFF)})
    m.apply_terrain_polys(ed.game)
    cliff_entry = [l for l in ed.game.lakes
                   if isinstance(l, dict) and l.get('type') == 'cliff']
    check("30a 悬崖注入 lakes 容器", len(cliff_entry) == 1
          and point_in_poly(cliff_entry[0]['poly'], 4200, 4150))
    ed.game.all_buildings = []
    ed.game.current_map = m
    p3 = _Probe(ed.game, vec(4200, 4150))
    check("30b 悬崖上地面单位 can_pass=False",
          p3.check_move_validity(vec(4300, 4200)) is False)
    check("30c 悬崖外地面正常通行",
          p3.check_move_validity(vec(3000, 3000)) is True)
    p3.pos = vec(4200, 4150)
    p3._check_drowning()
    check("30d 悬崖不算水（不溺水）", getattr(p3, 'drown_timer', 0) == 0)
    path = m.save_layout()
    data = json.load(open(path, encoding="utf-8"))
    check("30e JSON 含 cliff", any(t.get("type") == "cliff" for t in data.get("terrain", [])))
    m5 = type(m)(None)
    m5.game = EditorGame(m5)
    m5.generate(seed=0)
    m5.apply_layout_override()
    m5.apply_terrain_polys(m5.game)
    p4 = _Probe(m5.game, vec(4200, 4150))
    m5.game.all_buildings = []
    m5.game.current_map = m5
    check("30f 新地图读回 cliff 且地面单位被挡",
          any(t["type"] == "cliff" for t in m5.terrain_polys)
          and any(isinstance(l, dict) and l.get('type') == 'cliff' for l in m5.lakes)
          and p4.check_move_validity(vec(4300, 4200)) is False)
except Exception as e:
    check("30 悬崖链路", False, e)

# 30g/30h. 悬崖只挡地面：海军压悬崖+水域可通行，地面仍被挡
try:
    RIVER = [(3900, 4050), (4600, 4050), (4600, 4250), (3900, 4250)]
    m.terrain_polys.append({"type": "water", "poly": RIVER, "rect": poly_bbox(RIVER)})
    m.apply_terrain_polys(ed.game)
    ed.game.all_buildings = []
    ed.game.current_map = m
    pn = _Probe(ed.game, vec(4200, 4150))    # 悬崖内部（下有水域）
    pn.is_naval = True
    check("30g 海军压悬崖+水域可通行（崖底航行）",
          pn.check_move_validity(vec(4300, 4200)) is True)
    pg = _Probe(ed.game, vec(4200, 4150))
    check("30h 地面单位进悬崖仍被挡",
          pg.check_move_validity(vec(4300, 4200)) is False)
    pn2 = _Probe(ed.game, vec(3950, 4150))   # 悬崖外水域（崖西侧）
    pn2.is_naval = True
    check("30i 海军普通水面通行不受影响",
          pn2.check_move_validity(vec(3950, 4150)) is True)
except Exception as e:
    check("30g-i 海军悬崖通行", False, e)

# 31. 悬崖不生波纹（WaterFX._waters 只收真水）
try:
    from maps.environment import WaterFX
    cliff_l = {'rect': poly_bbox(CLIFF), 'poly': CLIFF, 'type': 'cliff', 'from_terrain': True}
    water_l = {'rect': poly_bbox([(0, 0), (100, 0), (100, 100), (0, 100)]),
               'poly': [(0, 0), (100, 0), (100, 100), (0, 100)],
               'type': 'water', 'from_terrain': True}
    no_wave = {'rect': poly_bbox([(0, 0), (50, 0), (50, 50)]), 'poly': [(0, 0), (50, 0), (50, 50)],
               'type': 'water', 'from_terrain': True, 'waves': False}
    ws = WaterFX._waters([cliff_l, water_l, no_wave])
    check("31 波纹层过滤：悬崖/关波纹不参与，真水参与",
          len(ws) == 1 and ws[0] is water_l)
except Exception as e:
    check("31 波纹层过滤", False, e)

print("\n%d/%d passed" % (PASS, TOTAL))

# 恢复真实布局 JSON（测试 save 的内容不落盘）
if _json_backup is not None:
    open(_layout_path, 'wb').write(_json_backup)
elif os.path.exists(_layout_path):
    os.remove(_layout_path)

sys.exit(0 if PASS == TOTAL else 1)
