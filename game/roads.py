# -*- coding: utf-8 -*-
"""道路背景层：编辑器两点定起点/终点与宽度，游戏端贴地层沿方向平铺沥青纹理。

- 纹理程序生成（固定随机种子 → 主/客机渲染一致，无需美术资源）
- 每条道路的旋转贴条只合成一次（缓存挂在道路 dict 上），每帧仅按缩放 blit
- 数据格式（内存）：{"start": vec, "end": vec, "width": int}
  （布局 JSON：{"start": [x, y], "end": [x, y], "width": 64}）
"""
import math
import random
import pygame

ROAD_TILE = 64                                   # 沥青纹理边长（世界像素）
ROAD_WIDTH_CHOICES = (32, 48, 64, 96, 128)       # 编辑器路宽档位

_tile_cache = None


def get_road_tile():
    """64x64 沥青纹理：深灰底 + 碎石噪点 + 细裂纹（进程级缓存）"""
    global _tile_cache
    if _tile_cache is not None:
        return _tile_cache
    rng = random.Random(42)
    tile = pygame.Surface((ROAD_TILE, ROAD_TILE), pygame.SRCALPHA)
    tile.fill((56, 56, 58, 255))
    for _ in range(240):                         # 碎石噪点
        x, y = rng.randrange(ROAD_TILE), rng.randrange(ROAD_TILE)
        g = rng.randint(38, 96)
        tile.set_at((x, y), (g, g, min(255, g + 3), 255))
    for _ in range(4):                           # 细裂纹
        x, y = rng.randrange(ROAD_TILE), rng.randrange(ROAD_TILE)
        for _ in range(10):
            x = max(0, min(ROAD_TILE - 1, x + rng.randint(-3, 3)))
            y = max(0, min(ROAD_TILE - 1, y + rng.randint(-3, 3)))
            tile.set_at((x, y), (42, 42, 44, 255))
    _tile_cache = tile
    return tile


def build_road_strip(road):
    """沿 start→end 平铺纹理 + 中央黄色虚线，返回（旋转后贴条, 世界坐标左上角）。
    结果缓存在道路 dict（几何/宽度没变就复用），旋转只做一次"""
    start, end = road["start"], road["end"]
    width = int(road.get("width", 64))
    key = (round(start.x), round(start.y), round(end.x), round(end.y), width)
    if road.get("_strip_key") == key:
        return road["_strip"], road["_strip_pos"]
    sx, sy, ex, ey = start.x, start.y, end.x, end.y
    length = max(1.0, math.hypot(ex - sx, ey - sy))
    ang = math.degrees(math.atan2(ey - sy, ex - sx))
    tiles = int(length / ROAD_TILE) + 2
    strip = pygame.Surface((tiles * ROAD_TILE, width), pygame.SRCALPHA)
    t = get_road_tile()
    for i in range(tiles):
        strip.blit(t, (i * ROAD_TILE, 0))
    # 路缘压边（与草地衔接）+ 中央黄色虚线（读出"路"的方向感）
    pygame.draw.rect(strip, (40, 40, 42, 255), (0, 0, strip.get_width(), 3))
    pygame.draw.rect(strip, (40, 40, 42, 255), (0, width - 3, strip.get_width(), 3))
    cy = width // 2
    for x in range(0, strip.get_width(), 48):
        pygame.draw.rect(strip, (198, 168, 44, 210), (x, cy - 2, 24, 4))
    strip = pygame.transform.rotate(strip, -ang)
    pos = ((sx + ex) / 2 - strip.get_width() / 2,
           (sy + ey) / 2 - strip.get_height() / 2)
    road["_strip"], road["_strip_pos"], road["_strip_key"] = strip, pos, key
    return strip, pos


def seg_dist(p, a, b):
    """点到线段的距离（编辑器右键删除命中判定）"""
    ax, ay, bx, by = a.x, a.y, b.x, b.y
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 <= 1e-6:
        return math.hypot(p.x - ax, p.y - ay)
    t = max(0.0, min(1.0, ((p.x - ax) * dx + (p.y - ay) * dy) / l2))
    return math.hypot(p.x - (ax + t * dx), p.y - (ay + t * dy))


def draw_roads_screen(surface, roads, camera_offset, zoom):
    """游戏/编辑器通用：按相机变换把道路贴条画到目标 surface（贴地层调用）。
    camera_offset/zoom 语义与 units 的 draw 一致（世界→屏幕 = (p-offset)*zoom）"""
    if not roads:
        return
    z = max(zoom, 0.01)
    vx0 = camera_offset.x - 200
    vy0 = camera_offset.y - 200
    vx1 = vx0 + surface.get_width() / z + 400
    vy1 = vy0 + surface.get_height() / z + 400
    for r in roads:
        if not isinstance(r, dict) or "start" not in r:
            continue    # 防御：装饰性道路数据（已烘进背景）不符合贴条契约，跳过
        sx, sy = r["start"].x, r["start"].y
        ex, ey = r["end"].x, r["end"].y
        # 视口裁剪（贴条外接矩形）
        if max(sx, ex) < vx0 or min(sx, ex) > vx1 or max(sy, ey) < vy0 or min(sy, ey) > vy1:
            continue
        strip, pos = build_road_strip(r)
        sw = int(strip.get_width() * z)
        sh = int(strip.get_height() * z)
        if sw <= 0 or sh <= 0:
            continue
        scaled = pygame.transform.scale(strip, (sw, sh))
        surface.blit(scaled, (int((pos[0] - camera_offset.x) * z),
                              int((pos[1] - camera_offset.y) * z)))
