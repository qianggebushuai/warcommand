# -*- coding: utf-8 -*-
"""
地图布局编辑器（Map Layout Editor）
====================================
可视化配置开局：中立建筑位置 + 玩家出生点，背景即真实地图背景，
支持游戏同款缩放/平移观察，保存为 config/map_layouts/<地图类名>.json，
运行地图时由 GameMap.apply_layout_override()（level_mixin.update_loading 挂点）读取生成。

用法：
    python map_layout_editor.py [地图类名]
操作：
    左键   放置选中建筑 / 移动选中出生点
    右键   删除命中的中立建筑
    R      Bridge 选中时切换横竖方向
    滚轮   以鼠标为中心缩放    中键拖拽 / WASD  平移
    S 保存  L 丢弃修改并重载 JSON  ←/→ 或 F1-F9 切换地图  Tab 收起/展开面板  ESC 退出
"""
import os
import sys
import math
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame

from pygame.math import Vector2 as vec
from core.utils import get_font
from core.settings import SPECIAL_RESPAWN_FRAMES, AC130_ATTACK_RADIUS
from maps.map_data import LAYOUT_BUILDING_TYPES, _map_layout_path, TERRAIN_POLY_COLORS
from maps.map_data import (WildernessMap, StormCoastMap, FrozenArchipelagoMap,
                           DragonValleyMap, CrossfireMap, BroadcastCenterMap,
                           VerdunMap, PARISMAP, BERINGMAP)

MAP_CLASSES = [WildernessMap, StormCoastMap, FrozenArchipelagoMap, DragonValleyMap,
               CrossfireMap, BroadcastCenterMap, VerdunMap, PARISMAP, BERINGMAP]

PANEL_W = 250
PANEL_BG = (28, 30, 34)
PANEL_HI = (70, 74, 82)
ACCENT = (255, 200, 60)
TXT = (225, 225, 225)
TXT_DIM = (150, 152, 158)

# 建筑标记配色（按类型分组）
TYPE_COLORS = {
    "OilDerrick": (230, 170, 40), "Skyscraper": (120, 130, 145), "CivilianHouse": (150, 110, 80),
    "EuropeanChurch": (198, 192, 180), "HalfTimberHouse": (176, 140, 96),
    "ClockTower": (160, 158, 168), "Windmill": (188, 164, 128),
    "CommStation": (90, 140, 190), "EMPGenerator": (170, 90, 200), "AncientTemple": (190, 150, 90),
    "Lighthouse": (230, 230, 210), "Bastion": (180, 80, 70), "Bridge": (140, 120, 90),
    "FactoryBuilding": (110, 120, 130), "PowerPlant": (240, 190, 60), "RadarBuilding": (90, 170, 120),
    "Airfield": (100, 150, 210), "ResearchCenter": (200, 120, 160), "TechCenter": (220, 140, 60),
    "AntiAirTurret": (190, 90, 90), "CoastalGun": (160, 100, 100),
    "OrePatch": (240, 200, 60),
}
SPAWN_COLORS = [(90, 170, 250), (240, 110, 90), (120, 210, 130), (230, 200, 90)]
# 特殊单位标记配色：{类型: (刷新点色, 目标点色)}——列车橙/蓝，战列舰红/黄
SPECIAL_COLORS = {
    "Train": ((255, 150, 40), (80, 140, 250)),
    "Battleship": ((240, 80, 80), (250, 220, 70)),
    "AC130": ((120, 220, 120), (250, 150, 60)),
}


class MockParticles:
    def add(self, *a, **k):
        pass


class EditorGame:
    """编辑器用的轻量 game 替身：满足建筑构造期间的属性访问"""
    def __init__(self, map_obj):
        self.current_map = map_obj
        self.all_units = []
        self.all_buildings = []
        self.particles = MockParticles()
        self.my_faction = "CHINA"
        self.enemy_faction = "USA"
        self.my_team = "team_0"
        self.team_resources = {"team_0": 5000, "team_1": 5000}
        self.net_events = []
        self.is_online = False


class MapLayoutEditor:
    def __init__(self, start_map_index=0):
        pygame.init()
        pygame.display.set_caption("地图布局编辑器 - WarCommander")
        self.win = pygame.display.set_mode((1440, 900), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.font = get_font(15)
        self.font_s = get_font(12)
        self.font_b = get_font(17, bold=True)

        self.map_index = start_map_index
        self.zoom = 0.35
        self.offset = vec(0, 0)          # 视口左上角世界坐标
        self.selected_type = None        # 选中的建筑类名 / "spawn:k"
        self.bridge_orientation = "horizontal"
        self._size_cache = {}            # (cls_name, orientation) -> (w, h)
        self.panning = False
        self.dragging_ore = None         # 正在拖动移动的矿脉（OrePatch）
        self.terrain_mode = None         # 地形多边形绘制类型：None / "water" / "land" / "slope" / "cliff"
        self.terrain_drawing = []        # 绘制中的多边形顶点（世界坐标）
        self.terrain_color = None        # 当前绘制颜色（None=用类型默认色）
        self.terrain_alpha = 150         # 当前绘制透明度（10-230）
        self.selected_terrain = None     # 选中待编辑的已有多边形（索引）
        self._bg_clean = None            # 无地形多边形污染的干净背景快照（编辑器专用）
        self.save_msg = ""
        self.save_msg_t = 0
        self.dirty = False               # 有未保存修改
        self._last_cap = None
        self.drag_start = None
        self.panel_rect = None
        self.panel_scroll = 0            # 面板滚动偏移（内容超出屏幕时，滚轮滚动）
        self._panel_content_h = 0        # 面板内容总高（draw_panel 每帧回填，用于夹紧滚动）
        self.panel_collapsed = False     # Tab/拉手收起左侧面板（收起后整幅画布可编辑，不再被面板遮挡）
        self._toggle_rect = None         # 面板收起/展开拉手的屏幕区域（每帧绘制时更新）
        self.special_pending = None      # 特殊单位两步放置：已落下的刷新点 {type, spawn}
        self.selected_special = None     # 选中的特殊单位索引（AC130 用 +/- 调攻击半径）
        self.road_pending = None         # 道路两点绘制：已定下的起点 vec
        self.bridge_pending = None       # 桥梁两点放置：已定下的起点 vec（终点决定方向+长度）
        self.road_width = 64             # 新道路宽度（面板档位循环切换）
        self.load_map(self.map_index)

    # ---------------- 地图与数据 ----------------
    def _generate_map(self):
        """按各地图 generate 的实际签名传参（个别地图无 visual_only 参数）"""
        import inspect
        params = inspect.signature(self.map_obj.generate).parameters
        kwargs = {}
        if 'seed' in params:
            kwargs['seed'] = 0
        if 'visual_only' in params:
            kwargs['visual_only'] = False
        self.map_obj.generate(**kwargs)

    def load_map(self, index, keep_view=False):
        self.map_index = index % len(MAP_CLASSES)
        map_cls = MAP_CLASSES[self.map_index]
        print(f"[Editor] Loading {map_cls.__name__} ...")
        try:
            self.map_obj = map_cls(None)
        except Exception as ex:
            print(f"[Editor] {map_cls.__name__} load failed: {ex}")
            self.flash(f"{map_cls.__name__} 加载失败，已跳过")
            self.map_index = (self.map_index + 1) % len(MAP_CLASSES)
            if MAP_CLASSES[self.map_index] is map_cls:   # 全部失败，止损
                return
            return self.load_map(self.map_index, keep_view)
        self.game = EditorGame(self.map_obj)
        self.map_obj.game = self.game          # 让建筑构造时拿到 mock game
        self._generate_map()                   # 预载默认随机布局作为编辑起点
        # 干净背景快照（apply_layout_override 会把地形多边形烘进 bg_surface，
        # 编辑器叠加层自己矢量重画，避免烘焙层与实时绘制双重叠加）
        bs = self.map_obj.bg_surface
        self._bg_clean = bs.copy() if bs is not None else None
        self.map_obj.apply_layout_override()   # 已有 JSON 则覆盖
        self.terrain_mode = None               # 切图丢弃未完成的地形绘制
        self.terrain_drawing = []
        self.selected_terrain = None
        if not getattr(self.map_obj, 'layout_has_ore', False):
            # 旧布局 JSON 无矿脉键 → 预载随机矿脉供编辑；
            # 否则一保存就会写入空 "ore" 把该图矿脉清零
            self.map_obj.generate_ore_patches()
        if not self.map_obj.bases_config:
            self.map_obj.bases_config = [vec(self.map_obj.width * 0.2, self.map_obj.height * 0.5),
                                         vec(self.map_obj.width * 0.8, self.map_obj.height * 0.5)]
        # 特殊单位标记：JSON 无 special_units 分区时从地图硬编码 initial_units
        # 预载默认刷新点供编辑（保存后即以 JSON 为准）
        if getattr(self.map_obj, 'special_specs', None) is None:
            from core.settings import SPECIAL_RESPAWN_FRAMES
            specs = []
            for u_type, pos in getattr(self.map_obj, 'initial_units', []):
                t = {"train": "Train", "Train": "Train", "Battleship": "Battleship"}.get(str(u_type))
                if t:
                    specs.append({"type": t, "spawn": vec(pos), "target": None,
                                  "respawn_frames": SPECIAL_RESPAWN_FRAMES})
            self.map_obj.special_specs = specs
        self.special_pending = None           # 切图丢弃未完成的特殊单位两步放置
        self.selected_special = None          # 切图清空特殊单位选中
        self.road_pending = None              # 切图丢弃未完成的道路两点绘制
        self.bridge_pending = None            # 切图丢弃未完成的桥梁两点放置
        if not hasattr(self.map_obj, 'roads'):
            self.map_obj.roads = []           # 兜底（apply_layout_override 未跑时）
        if not keep_view:
            self.zoom = max(0.15, min(1.2, 900.0 / max(self.map_obj.width, self.map_obj.height)))
            self.offset = vec(0, 0)
        self.dirty = False                # 载入/切图 = 干净状态
        print(f"[Editor] {map_cls.__name__} ready: "
              f"{len(self.map_obj.neutral_buildings)} neutral, {len(self.map_obj.bases_config)} bases")

    def reload_json(self):
        """L 键：丢弃修改，重新生成并应用 JSON"""
        self.load_map(self.map_index, keep_view=True)
        self.flash("已重载（JSON 已应用）")

    def flash(self, msg):
        self.save_msg = msg
        self.save_msg_t = pygame.time.get_ticks()

    # ---------------- 坐标变换 ----------------
    def w2s(self, p):
        return (int((p.x - self.offset.x) * self.zoom), int((p.y - self.offset.y) * self.zoom))

    def s2w(self, p):
        return vec(p[0] / self.zoom + self.offset.x, p[1] / self.zoom + self.offset.y)

    def clamp_camera(self):
        m = self.map_obj
        view_w = self.win.get_width() / self.zoom
        view_h = self.win.get_height() / self.zoom
        self.offset.x = max(-300, min(m.width - view_w + 300, self.offset.x))
        self.offset.y = max(-300, min(m.height - view_h + 300, self.offset.y))

    # ---------------- 建筑操作 ----------------
    def probe_size(self, cls_name, orientation=None):
        """实例化探针建筑获取占地尺寸（缓存）"""
        key = (cls_name, orientation)
        if key in self._size_cache:
            return self._size_cache[key]
        if cls_name == "OrePatch":
            size = (76, 76)   # 矿脉显示直径（radius 38）
            self._size_cache[key] = size
            return size
        extra = [orientation] if (cls_name == "Bridge" and orientation) else None
        b = self.map_obj.make_layout_building(cls_name, vec(self.map_obj.width / 2, self.map_obj.height / 2), extra)
        if b is None:
            size = (80, 80)
        else:
            size = (max(20, b.rect.w), max(20, b.rect.h))
        self._size_cache[key] = size
        return size

    def place_building(self, cls_name, world_pos):
        if cls_name == "OrePatch":
            # 矿脉：满储量放置（走 JSON 布局链路，游戏端跳过随机矿脉生成）
            from maps.map_data import OrePatch
            self.map_obj.ore_patches.append(OrePatch(self.game, vec(world_pos)))
            self.dirty = True
            return
        if cls_name == "Bridge":
            # 桥梁：两点放置（起点→终点决定方向+长度，碰撞箱随之伸缩）
            self.place_bridge(world_pos)
            return
        b = self.map_obj.make_layout_building(cls_name, world_pos)
        if b is not None:
            self.map_obj.neutral_buildings.append(b)
            self.dirty = True

    def place_bridge(self, world_pos):
        """桥梁两点放置：第一次点击定起点，第二次点击定终点。
        方向取主轴（dx/dy 谁大），长度=主轴投影，横向固定 300/竖向固定 200；
        桥中心取两点中点（副轴吸附到起点坐标，保证桥面笔直）"""
        p = vec(int(world_pos.x), int(world_pos.y))
        if self.bridge_pending is None:
            self.bridge_pending = p
            self.flash("桥起点已定 — 再点一次放终点（右键取消）")
            return
        d = p - self.bridge_pending
        if max(abs(d.x), abs(d.y)) < 60:
            self.flash("太短（<60px），已丢弃；再点重新定起点")
            self.bridge_pending = None
            return
        s = self.bridge_pending
        if abs(d.x) >= abs(d.y):
            orientation, length = "horizontal", int(abs(d.x))
            center = vec((s.x + p.x) // 2, s.y)
        else:
            orientation, length = "vertical", int(abs(d.y))
            center = vec(s.x, (s.y + p.y) // 2)
        b = self.map_obj.make_layout_building("Bridge", center, [orientation, length])
        if b is not None:
            self.map_obj.neutral_buildings.append(b)
            self.dirty = True
        self.bridge_pending = None
        self.flash(f"已建桥 {orientation} 长{length}px — 右键点桥可删除")

    def place_special(self, world_pos):
        """特殊单位两步放置：第一次点击放刷新点，第二次点击放目标点"""
        t = self.selected_type.split(":", 1)[1]
        wp = vec(int(world_pos.x), int(world_pos.y))
        if self.special_pending is None or self.special_pending["type"] != t:
            self.special_pending = {"type": t, "spawn": wp}
            self.flash(f"{t} 刷新点已落 — 再点一次放目标点")
            return
        t = self.special_pending["type"]
        spec = {
            "type": t, "spawn": self.special_pending["spawn"],
            "target": wp, "respawn_frames": SPECIAL_RESPAWN_FRAMES}
        if t == "AC130":
            spec["attack_radius"] = AC130_ATTACK_RADIUS   # 默认攻击半径，选中后 +/- 调整
        self.map_obj.special_specs.append(spec)
        self.special_pending = None
        self.dirty = True
        self.flash(f"已添加特殊单位 {t}（右键点标记可删除）")

    def hit_special(self, world_pos):
        """命中检测：特殊单位标记（刷新点/目标点 <26px）→ 返回索引（供选中 AC130 调半径）"""
        for i, sp in reversed(list(enumerate(getattr(self.map_obj, 'special_specs', None) or []))):
            for key in ("target", "spawn"):
                p = sp.get(key)
                if p is not None and (vec(p) - world_pos).length() <= 26:
                    return i
        return None

    def adjust_ac130_radius(self, delta):
        """+/- 键：调整选中 AC130 的攻击半径（盘旋半径 = 攻击半径×2 联动）"""
        if self.selected_special is None:
            return False
        specs = getattr(self.map_obj, 'special_specs', None) or []
        if not (0 <= self.selected_special < len(specs)):
            return False
        sp = specs[self.selected_special]
        if sp.get("type") != "AC130":
            return False
        sp["attack_radius"] = max(100, min(2000, int(sp.get("attack_radius") or AC130_ATTACK_RADIUS) + delta))
        self.dirty = True
        self.flash(f"AC130 攻击半径 → {sp['attack_radius']}（盘旋半径 {sp['attack_radius'] * 2}）")
        return True

    def place_road(self, world_pos):
        """道路两点绘制：第一点=起点，第二点=终点成路（贴地层纹理平铺）"""
        p = vec(int(world_pos.x), int(world_pos.y))
        if self.road_pending is None:
            self.road_pending = p
            self.flash("道路起点已定 — 再点一次放终点（右键取消）")
            return
        dist = self.road_pending.distance_to(p)
        if dist < 24:
            self.flash("太短（<24px），已丢弃；再点重新定起点")
            self.road_pending = None
            return
        self.map_obj.roads.append({"start": self.road_pending, "end": p,
                                   "width": self.road_width})
        self.road_pending = None
        self.dirty = True
        self.flash(f"已铺道路（长{int(dist)}px 宽{self.road_width}）— 右键点路上可删除")

    def delete_road_at(self, world_pos):
        """右键删除道路：命中 = 距路中线 < 半宽+10px，删最近的一条"""
        roads = getattr(self.map_obj, 'roads', [])
        from game.roads import seg_dist
        best_i, best_d = None, 1e18
        for i, r in enumerate(roads):
            if not isinstance(r, dict):
                continue    # 防御：装饰性道路数据不可删
            d = seg_dist(world_pos, r["start"], r["end"]) - r.get("width", 64) / 2
            if d < best_d:
                best_i, best_d = i, d
        if best_i is not None and best_d < 10:
            roads.pop(best_i)
            self.dirty = True
            return True
        return False

    def hit_ore(self, world_pos):
        """命中检测：返回被点中的矿脉（半径略放大便于点选）"""
        for p in reversed(self.map_obj.ore_patches):
            if (p.pos - world_pos).length() <= p.radius + 8:
                return p
        return None

    def delete_at(self, world_pos):
        # 先查特殊单位标记（命中刷新点/目标点，半径放大便于点选）
        for i, sp in reversed(list(enumerate(getattr(self.map_obj, 'special_specs', None) or []))):
            for key in ("target", "spawn"):
                p = sp.get(key)
                if p is not None and (vec(p) - world_pos).length() <= 22:
                    self.map_obj.special_specs.remove(sp)
                    if self.selected_special == i:
                        self.selected_special = None
                    elif self.selected_special is not None and self.selected_special > i:
                        self.selected_special -= 1
                    self.dirty = True
                    return f"特殊单位:{sp['type']}"
        # 再查矿脉（命中半径略放大便于点选）
        for p in reversed(self.map_obj.ore_patches):
            if (p.pos - world_pos).length() <= p.radius + 8:
                self.map_obj.ore_patches.remove(p)
                self.dirty = True
                return "OrePatch"
        for b in reversed(self.map_obj.neutral_buildings):
            if b.rect.collidepoint(world_pos.x, world_pos.y):
                self.map_obj.neutral_buildings.remove(b)
                self.dirty = True
                return b.__class__.__name__
        return None

    def hit_building(self, world_pos):
        for b in reversed(self.map_obj.neutral_buildings):
            if b.rect.collidepoint(world_pos.x, world_pos.y):
                return b
        return None

    # ---------------- 绘制 ----------------
    def draw_background(self):
        m = self.map_obj
        W, H = self.win.get_size()
        self.win.fill((16, 18, 20))
        bg = self._bg_clean if self._bg_clean is not None else m.bg_surface
        if bg is None:
            return
        view_w = W / self.zoom
        view_h = H / self.zoom
        sx = max(0, int(self.offset.x))
        sy = max(0, int(self.offset.y))
        sw = int(min(view_w, bg.get_width() - sx))
        sh = int(min(view_h, bg.get_height() - sy))
        if sw <= 0 or sh <= 0:
            return
        sub = bg.subsurface((sx, sy, sw, sh))
        scaled = pygame.transform.scale(sub, (int(sw * self.zoom), int(sh * self.zoom)))
        self.win.blit(scaled, self.w2s(vec(sx, sy)))

    # ---------------- 地形多边形 ----------------
    TERRAIN_LABELS = {"water": "水域", "land": "陆地", "slope": "斜坡", "cliff": "悬崖"}
    TERRAIN_PRESETS = [
        ("湖蓝", (50, 110, 185)), ("深海", (25, 60, 120)), ("浅滩", (85, 165, 200)),
        ("墨绿", (40, 110, 90)), ("灰蓝", (95, 125, 155)), ("暗青", (30, 140, 140)),
        ("暗紫", (110, 85, 160)), ("浑水", (145, 125, 85)),
    ]
    TERRAIN_PRESETS_CLIFF = [
        ("深岩", (104, 94, 84)), ("花岗", (128, 122, 114)), ("铁灰", (90, 88, 92)),
        ("玄武", (66, 64, 68)), ("赭岩", (142, 110, 80)), ("黄土", (160, 140, 100)),
        ("青灰", (110, 120, 118)), ("红岩", (150, 82, 62)),
    ]

    def close_terrain_poly(self):
        """Enter：闭合绘制中的多边形（≥3 顶点生效）"""
        from maps.map_data import poly_bbox
        if len(self.terrain_drawing) < 3:
            self.flash("至少 3 个顶点才能闭合")
            return
        if not hasattr(self.map_obj, 'terrain_polys'):
            self.map_obj.terrain_polys = []
        pts = [(float(p[0]), float(p[1])) for p in self.terrain_drawing]
        self.map_obj.terrain_polys.append({
            "type": self.terrain_mode, "poly": pts, "rect": poly_bbox(pts),
            "color": list(self.terrain_color) if self.terrain_color else None,
            "alpha": int(self.terrain_alpha),
        })
        self.terrain_drawing = []
        self.dirty = True
        self.flash(f"已添加{self.TERRAIN_LABELS.get(self.terrain_mode, self.terrain_mode)}多边形")

    def cancel_terrain_drawing(self):
        self.terrain_drawing = []
        if self.terrain_mode:
            self.flash("已取消绘制（类型保持选中）")

    def hit_terrain_poly(self, world_pos, after=None):
        """命中检测：返回点中的地形多边形索引（从后往前=最上层优先）。
        after=已有选中索引且其也被点中时，返回它的下一个命中——用于同点
        循环选择重叠多边形（如整片水域上的岛屿：水域排在最后会一直压住岛屿）"""
        from maps.map_data import point_in_poly
        polys = getattr(self.map_obj, 'terrain_polys', [])
        hits = [i for i in range(len(polys) - 1, -1, -1)
                if point_in_poly(polys[i]["poly"], world_pos.x, world_pos.y)]
        if not hits:
            return -1
        if after is not None and after in hits:
            return hits[(hits.index(after) + 1) % len(hits)]
        return hits[0]

    def _selected_poly(self):
        """当前选中的多边形条目（索引失效返回 None）"""
        if self.selected_terrain is None:
            return None
        polys = getattr(self.map_obj, 'terrain_polys', [])
        if 0 <= self.selected_terrain < len(polys):
            return polys[self.selected_terrain]
        self.selected_terrain = None
        return None

    def select_terrain_at(self, world_pos):
        """空闲模式左键画布：命中多边形则选中并吸取其颜色/透明度，点空白取消选中。
        点击点仍在当前选中的多边形内时，循环切换到下一个重叠多边形
        （CrossfireMap 整片水域压住所有岛屿、DragonValley 河流压住河岸均靠此选择）"""
        from maps.map_data import point_in_poly
        cur = self._selected_poly()
        after = None
        if cur is not None and point_in_poly(cur["poly"], world_pos.x, world_pos.y):
            after = self.selected_terrain   # 同点再点 → 循环下一个重叠多边形
        idx = self.hit_terrain_poly(world_pos, after)
        self.selected_terrain = idx if idx >= 0 else None
        if idx >= 0:
            t = self.map_obj.terrain_polys[idx]
            self.terrain_color = list(t.get('color')) if t.get('color') else None
            self.terrain_alpha = int(t.get('alpha', self.terrain_alpha))
            self.flash(f"已选中{self.TERRAIN_LABELS.get(t['type'], t['type'])}多边形 #{idx}"
                       f"（共{len(self.map_obj.terrain_polys)}条）— 同点再点循环选择重叠多边形")

    def delete_terrain_poly(self, world_pos):
        from maps.map_data import point_in_poly
        idx = self.hit_terrain_poly(world_pos)
        # 已选中且点击点在其内 → 删选中的那个（可删被水域埋住的岛屿等多边形）
        cur = self._selected_poly()
        if cur is not None and point_in_poly(cur["poly"], world_pos.x, world_pos.y):
            idx = self.selected_terrain
        if idx < 0:
            return None
        t = self.map_obj.terrain_polys.pop(idx)
        # 选中索引同步修正
        if self.selected_terrain == idx:
            self.selected_terrain = None
        elif self.selected_terrain is not None and self.selected_terrain > idx:
            self.selected_terrain -= 1
        self.dirty = True
        return self.TERRAIN_LABELS.get(t["type"], t["type"])

    def draw_terrain_polys(self):
        """叠加渲染：已确认多边形（半透明填充，条目自定义色）+ 绘制中橡皮筋"""
        from maps.map_data import TERRAIN_POLY_COLORS
        m = self.map_obj
        # 已确认多边形：世界→屏幕坐标，bbox 小图层填充避免整屏 SRCALPHA
        for ti, t in enumerate(getattr(m, 'terrain_polys', [])):
            default = TERRAIN_POLY_COLORS.get(t["type"], (150, 150, 150, 150))
            col = t.get("color") or list(default[:3])
            alpha = t.get("alpha", default[3] if len(default) > 3 else 150)
            color = (*[int(c) for c in col], int(alpha))
            spts = [self.w2s(vec(p[0], p[1])) for p in t["poly"]]
            xs = [p[0] for p in spts]; ys = [p[1] for p in spts]
            bx, by = int(min(xs)), int(min(ys))
            bw, bh = int(max(xs)) - bx, int(max(ys)) - by
            if bw <= 0 or bh <= 0:
                continue
            # 与视口求交裁剪（整屏外直接跳过）
            W, H = self.win.get_size()
            if bx > W or by > H or bx + bw < 0 or by + bh < 0:
                continue
            layer = pygame.Surface((bw, bh), pygame.SRCALPHA)
            local = [(p[0] - bx, p[1] - by) for p in spts]
            pygame.draw.polygon(layer, color, local)
            self.win.blit(layer, (bx, by))
            # 选中高亮：白色描边框（编辑辅助，游戏内无此线）
            if ti == self.selected_terrain:
                pygame.draw.polygon(self.win, (255, 255, 255), spts, 2)
        # 绘制中：已落点连线 + 鼠标橡皮筋 + 顶点方块
        if self.terrain_mode and self.terrain_drawing:
            col = TERRAIN_POLY_COLORS.get(self.terrain_mode, (255, 255, 255, 180))
            spts = [self.w2s(p) for p in self.terrain_drawing]
            if len(spts) >= 2:
                pygame.draw.lines(self.win, col[:3], False, spts, 2)
            mx, my = pygame.mouse.get_pos()
            if not self.panel_rect or not self.panel_rect.collidepoint((mx, my)):
                pygame.draw.line(self.win, col[:3], spts[-1], (mx, my), 1)
            # 闭合预览线（首末点虚感：细线）
            if len(spts) >= 3:
                pygame.draw.line(self.win, (*col[:3], 120)[:3], spts[-1], spts[0], 1)
            for sp in spts:
                pygame.draw.rect(self.win, col[:3], (sp[0] - 3, sp[1] - 3, 6, 6))
                pygame.draw.rect(self.win, (255, 255, 255), (sp[0] - 3, sp[1] - 3, 6, 6), 1)

    def draw_buildings(self):
        # 立绘缩放缓存：uid -> (w, h, scaled_surface)（建筑构造自带 generate_image 立绘）
        if not hasattr(self, '_img_cache'):
            self._img_cache = {}
        # 矿脉（建筑下层）：游戏同款矿井立绘；zoom 太小时退化为金点
        for p in self.map_obj.ore_patches:
            if self.zoom >= 0.18:
                try:
                    p.draw(self.win, self.offset, self.zoom)
                except Exception:
                    self._draw_ore_fallback(p)
            else:
                self._draw_ore_fallback(p)
            if p is self.dragging_ore:
                sp = self.w2s(p.pos)
                pygame.draw.circle(self.win, ACCENT, sp, max(8, int((p.radius + 10) * self.zoom)), 2)
        self._draw_neutral_buildings()

    def _draw_ore_fallback(self, p):
        sp = self.w2s(p.pos)
        pygame.draw.circle(self.win, TYPE_COLORS["OrePatch"], sp, max(3, int(p.radius * self.zoom)))

    def _draw_neutral_buildings(self):
        for b in self.map_obj.neutral_buildings:
            sp = self.w2s(b.pos)
            w = max(6, int(b.rect.w * self.zoom))
            h = max(6, int(b.rect.h * self.zoom))
            r = pygame.Rect(0, 0, w, h)
            r.center = sp
            # 优先游戏同款 draw()（程序绘制外观），失败回退 image，再回退色块
            drawn = False
            try:
                b.draw(self.win, self.offset, self.zoom)
                drawn = True
            except Exception:
                pass
            if not drawn:
                img = getattr(b, 'image', None)
                if img is not None and img.get_width() > 1:
                    key = (b.uid, w, h)
                    cached = self._img_cache.get(key)
                    if cached is None:
                        cached = pygame.transform.scale(img, (w, h))
                        if len(self._img_cache) > 300:
                            self._img_cache.clear()
                        self._img_cache[key] = cached
                    self.win.blit(cached, r.topleft)
                    pygame.draw.rect(self.win, TYPE_COLORS.get(b.__class__.__name__, (200, 200, 200)), r, 1, border_radius=2)
                else:
                    color = TYPE_COLORS.get(b.__class__.__name__, (140, 140, 140))
                    pygame.draw.rect(self.win, color, r, border_radius=3)
                    pygame.draw.rect(self.win, (20, 20, 20), r, 1, border_radius=3)
            if self.zoom > 0.28 and w > 26:
                label = self.font_s.render(b.__class__.__name__[:9], True, (15, 15, 15))
                bg = pygame.Surface((label.get_width() + 4, label.get_height() + 2), pygame.SRCALPHA)
                bg.fill((255, 255, 255, 150))
                self.win.blit(bg, (sp[0] - label.get_width() // 2 - 2, r.bottom + 1))
                self.win.blit(label, (sp[0] - label.get_width() // 2, r.bottom + 2))
        # 悬浮高亮
        if self.panel_rect is None or not self.panel_rect.collidepoint(pygame.mouse.get_pos()):
            wp = self.s2w(pygame.mouse.get_pos())
            hb = self.hit_building(wp)
            if hb is not None:
                sp = self.w2s(hb.pos)
                w = max(6, int(hb.rect.w * self.zoom))
                h = max(6, int(hb.rect.h * self.zoom))
                r = pygame.Rect(0, 0, w + 6, h + 6)
                r.center = sp
                pygame.draw.rect(self.win, ACCENT, r, 2, border_radius=4)

    def draw_spawn_points(self):
        for i, p in enumerate(self.map_obj.bases_config):
            sp = self.w2s(vec(p))
            color = SPAWN_COLORS[i % len(SPAWN_COLORS)]
            s = max(10, int(22 * self.zoom))
            pygame.draw.line(self.win, (40, 40, 40), (sp[0], sp[1]), (sp[0], sp[1] - s * 2), max(2, s // 6))
            pygame.draw.polygon(self.win, color, [(sp[0], sp[1] - s * 2), (sp[0] + s, sp[1] - int(s * 1.6)), (sp[0], sp[1] - int(s * 1.2))])
            pygame.draw.circle(self.win, color, sp, max(3, s // 3))
            if self.zoom > 0.2:
                label = self.font_b.render(f"P{i + 1}", True, color)
                self.win.blit(label, (sp[0] + s // 2, sp[1] - s * 2 - label.get_height()))
            if self.selected_type == f"spawn:{i}":
                r = pygame.Rect(0, 0, s * 3, s * 3)
                r.center = sp
                pygame.draw.circle(self.win, ACCENT, sp, r.width // 2, 2)

    def draw_special_units(self):
        """特殊单位标记：刷新点大圆 + 目标点小圆 + 连线（列车橙/蓝，战列舰红/黄，AC130 绿/橙+攻击半径圈）"""
        for i, sp in enumerate(getattr(self.map_obj, 'special_specs', None) or []):
            spawn_col, tgt_col = SPECIAL_COLORS.get(sp["type"], ((200, 200, 200), (200, 200, 200)))
            sel = (self.selected_special == i)
            s_spawn = self.w2s(sp["spawn"])
            tgt = sp.get("target")
            if tgt is not None:
                s_tgt = self.w2s(tgt)
                pygame.draw.line(self.win, (120, 120, 120), s_spawn, s_tgt, 1)
                if sp["type"] == "AC130" and sp.get("attack_radius"):
                    # AC130 攻击半径圈（选中高亮加粗）
                    rr = max(8, int(sp["attack_radius"] * self.zoom))
                    col = (255, 220, 90) if sel else (250, 150, 60)
                    pygame.draw.circle(self.win, col, s_tgt, rr,
                                       2 if sel else 1)
                    pygame.draw.circle(self.win, col, s_tgt, max(3, int(rr * 0.5)), 1)
                r_t = max(4, int(10 * self.zoom))
                pygame.draw.circle(self.win, tgt_col, s_tgt, r_t)
                pygame.draw.circle(self.win, (20, 20, 20), s_tgt, r_t, 1)
            r_s = max(5, int(14 * self.zoom))
            if sel:
                pygame.draw.circle(self.win, (255, 220, 90), s_spawn, r_s, 2)
                pygame.draw.circle(self.win, (20, 20, 20), s_spawn, r_s, 1)
            else:
                pygame.draw.circle(self.win, spawn_col, s_spawn, r_s)
                pygame.draw.circle(self.win, (20, 20, 20), s_spawn, r_s, 1)
            if self.zoom > 0.2:
                label = {"Train": "列车", "Battleship": "战列舰", "AC130": "AC130"}.get(sp["type"], sp["type"])
                if sp["type"] == "AC130" and sp.get("attack_radius"):
                    label += f" 半径{sp['attack_radius']}"
                lab = self.font_s.render(label, True, (255, 220, 90) if sel else spawn_col)
                self.win.blit(lab, (s_spawn[0] + r_s + 2, s_spawn[1] - lab.get_height() // 2))
        # 两步放置中：已落的刷新点描边 + 到鼠标的引导线
        if self.special_pending is not None:
            spawn_col, _ = SPECIAL_COLORS.get(self.special_pending["type"], ((200, 200, 200), (200, 200, 200)))
            sp = self.w2s(self.special_pending["spawn"])
            r = max(5, int(14 * self.zoom))
            pygame.draw.circle(self.win, spawn_col, sp, r, 2)
            mx, my = pygame.mouse.get_pos()
            if self.panel_rect is None or not self.panel_rect.collidepoint((mx, my)):
                pygame.draw.line(self.win, spawn_col, sp, (mx, my), 1)

    def draw_ghost(self):
        if self.selected_type is None:
            return
        if self.panel_rect is not None and self.panel_rect.collidepoint(pygame.mouse.get_pos()):
            return
        if self.selected_type.startswith("spawn:") or self.selected_type.startswith("special:"):
            return  # 出生点/特殊单位用各自专用标记绘制，不走建筑 ghost
        wp = self.s2w(pygame.mouse.get_pos())
        if self.selected_type == "Bridge":
            # 桥梁两点放置：起点已定 → 橡皮筋 + 实时尺寸预览（主轴吸附）
            a_s = None
            if self.bridge_pending is not None:
                d = wp - self.bridge_pending
                if abs(d.x) >= abs(d.y):
                    orient, ln = "horizontal", int(abs(d.x))
                    c = vec((self.bridge_pending.x + wp.x) / 2, self.bridge_pending.y)
                else:
                    orient, ln = "vertical", int(abs(d.y))
                    c = vec(self.bridge_pending.x, (self.bridge_pending.y + wp.y) / 2)
                w, h = (max(60, ln), 300) if orient == "horizontal" else (200, max(60, ln))
                a_s = self.w2s(self.bridge_pending)
            else:
                w, h = self.probe_size("Bridge", self.bridge_orientation)
            wp = c if self.bridge_pending is not None else wp
            r = pygame.Rect(0, 0, max(6, int(w * self.zoom)), max(6, int(h * self.zoom)))
            r.center = (int(wp.x * self.zoom - self.offset.x * self.zoom),
                        int(wp.y * self.zoom - self.offset.y * self.zoom))
            ghost = pygame.Surface(r.size, pygame.SRCALPHA)
            ghost.fill((*TYPE_COLORS.get("Bridge", (200, 200, 200)), 110))
            self.win.blit(ghost, r.topleft)
            pygame.draw.rect(self.win, ACCENT, r, 1)
            if a_s is not None:
                # 起点圈 + 到鼠标的引导线（与道路两点绘制同款视觉）
                pygame.draw.line(self.win, ACCENT, a_s, r.center, 2)
                pygame.draw.circle(self.win, ACCENT, a_s, max(3, int(8 * self.zoom)), 1)
            return
        w, h = self.probe_size(self.selected_type, self.bridge_orientation)
        r = pygame.Rect(0, 0, max(6, int(w * self.zoom)), max(6, int(h * self.zoom)))
        r.center = (int(wp.x * self.zoom - self.offset.x * self.zoom), int(wp.y * self.zoom - self.offset.y * self.zoom))
        ghost = pygame.Surface(r.size, pygame.SRCALPHA)
        ghost.fill((*TYPE_COLORS.get(self.selected_type, (200, 200, 200)), 110))
        self.win.blit(ghost, r.topleft)
        pygame.draw.rect(self.win, ACCENT, r, 1)

    # ---------------- 面板 ----------------
    def panel_items(self):
        items = []
        n_spawn = len(self.map_obj.bases_config)
        items.append(("header", "出生点"))
        for i in range(n_spawn):
            items.append(("spawn", i))
        items.append(("mini", "[+]/[-] 增减出生点 (2-4)"))
        items.append(("header", "中立建筑"))
        for name in LAYOUT_BUILDING_TYPES:
            items.append(("type", name))
        items.append(("header", "矿脉"))
        items.append(("type", "OrePatch"))
        items.append(("header", "特殊单位"))
        items.append(("special", "Train"))
        items.append(("special", "Battleship"))
        items.append(("special", "AC130"))
        items.append(("header", "道路"))
        items.append(("road", None))
        items.append(("roadwidth", None))
        items.append(("header", "地形多边形"))
        for t in ("water", "land", "slope", "cliff"):
            items.append(("terrain", t))
        # 色预设按当前操作对象切换：选中多边形 > 绘制中类型 > 默认水（悬崖=岩色系）
        preset_type = "water"
        sel_poly0 = self._selected_poly()
        if sel_poly0 is not None:
            preset_type = sel_poly0.get('type', preset_type)
        elif self.terrain_mode:
            preset_type = self.terrain_mode
        presets = self.TERRAIN_PRESETS_CLIFF if preset_type == 'cliff' else self.TERRAIN_PRESETS
        items.append(("header", f"地形色预设（{self.TERRAIN_LABELS.get(preset_type, preset_type)}）"))
        for i in range(0, len(presets), 4):
            items.append(("tcolorrow", presets[i:i + 4]))
        items.append(("talpha", None))
        sel_poly = self._selected_poly()
        if sel_poly is not None and sel_poly.get('type') == 'water':
            items.append(("twaves", None))   # 选中水域时：波纹开关
        return items

    def draw_panel(self):
        W, H = self.win.get_size()
        pr = pygame.Rect(0, 0, PANEL_W, H)
        self.panel_rect = pr
        pygame.draw.rect(self.win, PANEL_BG, pr)
        pygame.draw.line(self.win, (60, 64, 70), (PANEL_W - 1, 0), (PANEL_W - 1, H), 2)
        title = self.font_b.render("地图布局编辑器", True, ACCENT)
        self.win.blit(title, (12, 8))

        mouse = pygame.mouse.get_pos()
        # 面板滚动：内容超出屏幕高度时按 panel_scroll 上移并裁剪到面板区域；
        # _panel_hits 每帧按滚动后的屏幕坐标重建 → 点击命中无需换算。
        # 内容从 y=40（标题下）开始铺，可视高度是 H-40 而非 H——差值会让最后
        # 一行永远差 40px 够不到（滚动条到不了底）
        max_scroll = max(0, self._panel_content_h - (H - 40))
        self.panel_scroll = max(0, min(self.panel_scroll, max_scroll))
        self.win.set_clip(pr)
        y = 40 - self.panel_scroll
        self._panel_hits = []
        for kind, val in self.panel_items():
            if kind == "header":
                self.win.blit(self.font.render(str(val), True, TXT_DIM), (12, y))
                y += 24
            elif kind == "mini":
                self.win.blit(self.font_s.render(str(val), True, TXT_DIM), (12, y))
                self._panel_hits.append(("mini:+", pygame.Rect(12, y, PANEL_W // 2 - 20, 20)))
                self._panel_hits.append(("mini:-", pygame.Rect(PANEL_W // 2 + 4, y, PANEL_W // 2 - 20, 20)))
                y += 24
            elif kind == "spawn":
                i = val
                r = pygame.Rect(12, y, PANEL_W - 24, 24)
                sel = (self.selected_type == f"spawn:{i}")
                pygame.draw.rect(self.win, ACCENT if sel else PANEL_HI, r, border_radius=4)
                col = SPAWN_COLORS[i % len(SPAWN_COLORS)]
                pygame.draw.circle(self.win, col, (r.x + 14, r.y + 12), 7)
                self.win.blit(self.font.render(f"出生点 P{i + 1}", True, (20, 20, 20) if sel else TXT), (r.x + 30, r.y + 4))
                self._panel_hits.append((f"spawn:{i}", r))
                y += 28
            elif kind == "type":
                name = val
                r = pygame.Rect(12, y, PANEL_W - 24, 22)
                sel = (self.selected_type == name)
                hot = r.collidepoint(mouse)
                if sel or hot:
                    pygame.draw.rect(self.win, PANEL_HI, r, border_radius=4)
                if sel:
                    pygame.draw.rect(self.win, ACCENT, r, 1, border_radius=4)
                pygame.draw.rect(self.win, TYPE_COLORS.get(name, (150, 150, 150)), (r.x + 4, r.y + 4, 14, 14), border_radius=2)
                self.win.blit(self.font_s.render(name, True, TXT), (r.x + 26, r.y + 4))
                self._panel_hits.append((f"type:{name}", r))
                y += 24
            elif kind == "special":
                t = val
                col = SPECIAL_COLORS.get(t, ((200, 200, 200), (200, 200, 200)))[0]
                r = pygame.Rect(12, y, PANEL_W - 24, 22)
                sel = (self.selected_type == f"special:{t}")
                hot = r.collidepoint(mouse)
                if sel or hot:
                    pygame.draw.rect(self.win, PANEL_HI, r, border_radius=4)
                if sel:
                    pygame.draw.rect(self.win, ACCENT, r, 1, border_radius=4)
                pygame.draw.rect(self.win, col, (r.x + 4, r.y + 4, 14, 14), border_radius=2)
                label = {"Train": "装甲列车 刷新/目标", "Battleship": "战列舰 刷新/目标",
                         "AC130": "AC130 炮艇 刷新/盘旋中心"}.get(t, f"{t} 刷新/目标")
                if sel:
                    label += "  ▍连点2次"
                self.win.blit(self.font_s.render(label, True, TXT), (r.x + 26, r.y + 4))
                self._panel_hits.append((f"special:{t}", r))
                y += 24
            elif kind == "road":
                r = pygame.Rect(12, y, PANEL_W - 24, 22)
                sel = (self.selected_type == "road")
                hot = r.collidepoint(mouse)
                if sel or hot:
                    pygame.draw.rect(self.win, PANEL_HI, r, border_radius=4)
                if sel:
                    pygame.draw.rect(self.win, ACCENT, r, 1, border_radius=4)
                pygame.draw.rect(self.win, (90, 90, 94), (r.x + 4, r.y + 4, 14, 14), border_radius=2)
                label = "道路 起点→终点"
                if sel:
                    label += "  ▍两点绘制" + ("（放置中）" if self.road_pending else "")
                self.win.blit(self.font_s.render(label, True, TXT), (r.x + 26, r.y + 4))
                self._panel_hits.append(("road:tool", r))
                y += 24
            elif kind == "roadwidth":
                r = pygame.Rect(12, y, PANEL_W - 24, 22)
                hot = r.collidepoint(mouse)
                if hot:
                    pygame.draw.rect(self.win, PANEL_HI, r, border_radius=4)
                self.win.blit(self.font_s.render(
                    f"路宽 {self.road_width}px  （点击切换档位）", True, TXT), (r.x + 8, r.y + 4))
                self._panel_hits.append(("roadwidth:cycle", r))
                y += 24
            elif kind == "terrain":
                t = val
                from maps.map_data import TERRAIN_POLY_COLORS
                col = TERRAIN_POLY_COLORS.get(t, (150, 150, 150, 255))[:3]
                r = pygame.Rect(12, y, PANEL_W - 24, 22)
                sel = (self.terrain_mode == t)
                hot = r.collidepoint(mouse)
                if sel or hot:
                    pygame.draw.rect(self.win, PANEL_HI, r, border_radius=4)
                if sel:
                    pygame.draw.rect(self.win, ACCENT, r, 1, border_radius=4)
                pygame.draw.rect(self.win, col, (r.x + 4, r.y + 4, 14, 14), border_radius=2)
                label = self.TERRAIN_LABELS.get(t, t)
                if sel:
                    label += "  ▍绘制中"
                self.win.blit(self.font_s.render(label, True, TXT), (r.x + 26, r.y + 4))
                self._panel_hits.append((f"terrain:{t}", r))
                y += 24
            elif kind == "tcolorrow":
                row = val
                cw = (PANEL_W - 24 - 3 * 4) // 4
                for j, (cname, cval) in enumerate(row):
                    r = pygame.Rect(12 + j * (cw + 4), y, cw, 20)
                    cur = (self.terrain_color == list(cval))
                    hot = r.collidepoint(mouse)
                    if cur:
                        pygame.draw.rect(self.win, ACCENT, r, 1, border_radius=3)
                    if hot and not cur:
                        pygame.draw.rect(self.win, PANEL_HI, r, border_radius=3)
                    pygame.draw.rect(self.win, cval, (r.x + 2, r.y + 2, r.w - 4, r.h - 4), border_radius=2)
                    if self.selected_terrain is not None:
                        polys = getattr(self.map_obj, 'terrain_polys', [])
                        if self.selected_terrain < len(polys):
                            sp = polys[self.selected_terrain]
                            if sp.get('color') == list(cval):
                                pygame.draw.rect(self.win, (255, 255, 255), r, 1, border_radius=3)
                    self._panel_hits.append((f"tcolor:{cval[0]},{cval[1]},{cval[2]}", r))
                y += 24
            elif kind == "talpha":
                r = pygame.Rect(12, y, PANEL_W - 24, 22)
                pygame.draw.rect(self.win, PANEL_BG, r, border_radius=4)
                self.win.blit(self.font_s.render(
                    f"透明度 {self.terrain_alpha}  [-] [+]（选中时直接修改它）",
                    True, TXT), (r.x + 6, r.y + 4))
                btn_w = 22
                for sym, dx in (("-", r.w - btn_w * 2 - 8), ("+", r.w - btn_w - 4)):
                    br = pygame.Rect(r.x + dx, r.y + 1, btn_w, 20)
                    hot = br.collidepoint(mouse)
                    pygame.draw.rect(self.win, PANEL_HI if hot else (60, 66, 74), br, border_radius=3)
                    self.win.blit(self.font_s.render(sym, True, TXT), (br.x + 8, br.y + 3))
                    self._panel_hits.append((f"talpha:{sym}", br))
                y += 26
            elif kind == "twaves":
                sp = self._selected_poly()
                on = sp.get('waves', True) if sp else True
                r = pygame.Rect(12, y, PANEL_W - 24, 22)
                hot = r.collidepoint(mouse)
                if hot:
                    pygame.draw.rect(self.win, PANEL_HI, r, border_radius=4)
                self.win.blit(self.font_s.render(
                    f"波纹: {'是' if on else '否'}  （点击切换）",
                    True, (140, 200, 235) if on else TXT_DIM), (r.x + 8, r.y + 4))
                self._panel_hits.append(("twaves:toggle", r))
                y += 24
        # 操作说明
        y += 10
        for line in ("左键 放置/移动  右键 删除", "拖动矿脉直接移动位置",
                     "特殊单位：连点2次=刷新点→目标点", "AC130：空手点标记选中,+/-调攻击半径",
                     "道路：两点成路 右键点路/Delete删除",
                     "桥：两点放置(起点→终点定长度)", "地形：左键加点 Enter闭合",
                     "Backspace撤销点 右键取消", "空手左键点多边形=选中",
                     "选中后改颜色/透明度", "Del/右键删除: 建筑>多边形",
                     "滚轮缩放 中键拖动/WASD", "S 保存  L 重载JSON",
                     "Tab 收起面板(挡住地形时)", "←/→ 切换地图  ESC 退出"):
            self.win.blit(self.font_s.render(line, True, TXT_DIM), (12, y))
            y += 18
        # 记录内容总高（下帧夹紧滚动用），解除裁剪后画滚动条（右缘轨道+位置滑块）
        self._panel_content_h = y + 4
        self.win.set_clip(None)
        if max_scroll > 0:
            track = pygame.Rect(PANEL_W - 8, 40, 5, H - 48)
            thumb_h = max(40, int(track.h * H / max(self._panel_content_h, 1)))
            thumb_y = track.y + int((track.h - thumb_h) * (self.panel_scroll / max_scroll))
            pygame.draw.rect(self.win, (70, 74, 80), track, border_radius=2)
            pygame.draw.rect(self.win, ACCENT, (track.x, thumb_y, track.w, thumb_h), border_radius=3)

    def draw_panel_toggle(self):
        """面板收起/展开拉手（面板右缘/屏幕左缘中部；几何三角不依赖字体字形）"""
        W, H = self.win.get_size()
        x = 0 if self.panel_collapsed else PANEL_W - 16
        r = pygame.Rect(x, H // 2 - 44, 16, 88)
        self._toggle_rect = r
        hot = r.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(self.win, PANEL_HI if hot else (48, 52, 58), r, border_radius=3)
        cy = H // 2
        if self.panel_collapsed:   # ▶ 展开方向
            tri = [(x + 4, cy - 6), (x + 4, cy + 6), (x + 11, cy)]
        else:                      # ◀ 收起方向
            tri = [(x + 12, cy - 6), (x + 12, cy + 6), (x + 5, cy)]
        pygame.draw.polygon(self.win, TXT, tri)

    def handle_panel_click(self, pos, button):
        if button != 1:
            return True
        for action, r in getattr(self, "_panel_hits", []):
            if r.collidepoint(pos):
                if action == "mini:+":
                    if len(self.map_obj.bases_config) < 4:
                        self.map_obj.bases_config.append(vec(self.map_obj.width / 2, self.map_obj.height / 2))
                        self.dirty = True
                elif action == "mini:-":
                    if len(self.map_obj.bases_config) > 2:
                        self.map_obj.bases_config.pop()
                        self.selected_type = None
                        self.dirty = True
                else:
                    kind, _, v = action.partition(":")
                    if kind == "type":
                        # 再点同类型=取消回空手（空手状态才能点选已有水域/多边形）
                        self.selected_type = None if self.selected_type == v else v
                        self.terrain_mode = None        # 互斥：退出地形绘制
                        self.terrain_drawing = []
                        if v == "Bridge":
                            self.bridge_pending = None  # 重新选中丢弃未完成的起点
                        self.flash("已空手 — 可左键点选水域/多边形" if self.selected_type is None
                                   else (f"放置：{v} — 两点放置，第一次点起点第二次点终点"
                                         if v == "Bridge" else f"放置：{v} — 再点一次取消"))
                    elif kind == "spawn":
                        key = f"spawn:{v}"              # 出生点
                        self.selected_type = None if self.selected_type == key else key
                        self.terrain_mode = None
                        self.terrain_drawing = []
                        self.flash("已空手 — 可左键点选水域/多边形" if self.selected_type is None
                                   else f"放置：出生点{v} — 再点一次取消")
                    elif kind == "special":
                        key = f"special:{v}"            # 特殊单位（列车/战列舰）
                        self.selected_type = None if self.selected_type == key else key
                        self.terrain_mode = None
                        self.terrain_drawing = []
                        self.special_pending = None
                        self.flash("已空手 — 可左键点选水域/多边形" if self.selected_type is None
                                   else f"特殊单位 {v}：第一次点击放刷新点，第二次点击放目标点")
                    elif kind == "road":
                        # 道路工具：两点绘制（起点→终点）
                        self.selected_type = None if self.selected_type == "road" else "road"
                        self.terrain_mode = None
                        self.terrain_drawing = []
                        self.special_pending = None
                        self.road_pending = None
                        self.flash("已空手 — 可左键点选水域/多边形" if self.selected_type is None
                                   else "道路：第一次点击定起点，第二次点击定终点（右键取消/删除）")
                    elif kind == "roadwidth":
                        from game.roads import ROAD_WIDTH_CHOICES
                        idx = ROAD_WIDTH_CHOICES.index(self.road_width) \
                            if self.road_width in ROAD_WIDTH_CHOICES else -1
                        self.road_width = ROAD_WIDTH_CHOICES[(idx + 1) % len(ROAD_WIDTH_CHOICES)]
                        self.flash(f"新道路宽度：{self.road_width}px")
                    elif kind == "terrain":
                        # 再点同类型=取消；切换类型清空未完成绘制
                        self.terrain_mode = None if self.terrain_mode == v else v
                        self.terrain_drawing = []
                        self.selected_terrain = None
                        if self.terrain_mode:
                            self.selected_type = None
                            # 新多边形默认色/透明度跟随类型（悬崖近实心 235 等）
                            self.terrain_color = None
                            self.terrain_alpha = TERRAIN_POLY_COLORS[v][3]
                            self.flash(f"地形绘制：{self.TERRAIN_LABELS.get(v, v)} — 左键加点，Enter 闭合")
                    elif kind == "tcolor":
                        self.terrain_color = [int(c) for c in v.split(",")]
                        tgt = self._selected_poly()
                        if tgt is not None:
                            tgt["color"] = list(self.terrain_color)
                            self.dirty = True
                            self.flash(f"已改选中多边形颜色")
                        else:
                            self.flash("新多边形将使用该颜色")
                    elif kind == "talpha":
                        delta = -15 if v == "-" else 15
                        # 上限 245：悬崖默认 235（旧上限 230 摸不到近实心档）
                        self.terrain_alpha = max(10, min(245, self.terrain_alpha + delta))
                        tgt = self._selected_poly()
                        if tgt is not None:
                            tgt["alpha"] = int(self.terrain_alpha)
                            self.dirty = True
                    elif kind == "twaves":
                        # 选中水域的波纹开关（默认开；关=不生成波纹/海浪）
                        tgt = self._selected_poly()
                        if tgt is not None:
                            tgt['waves'] = not tgt.get('waves', True)
                            self.dirty = True
                            self.flash(f"该水域波纹：{'开' if tgt['waves'] else '关'}")
                return True
        return False

    # ---------------- 主循环 ----------------
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60)
            W, H = self.win.get_size()
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    if self.terrain_drawing:
                        self.cancel_terrain_drawing()   # 绘制中先取消，再按才退出
                    elif self.selected_terrain is not None:
                        self.selected_terrain = None    # 选中态先取消，再按才退出
                    elif self.selected_type is not None:
                        self.selected_type = None       # 放置类型回空手，再按才退出
                        self.road_pending = None
                        self.bridge_pending = None
                        self.special_pending = None
                    else:
                        running = False
                elif e.type == pygame.VIDEORESIZE:
                    self.win = pygame.display.set_mode(e.size, pygame.RESIZABLE)
                elif e.type == pygame.MOUSEWHEEL:
                    mx, my = pygame.mouse.get_pos()
                    if self.panel_rect is None or not self.panel_rect.collidepoint((mx, my)):
                        before = self.s2w((mx, my))
                        self.zoom = max(0.15, min(2.0, self.zoom * (1.15 if e.y > 0 else 1 / 1.15)))
                        after = self.s2w((mx, my))
                        self.offset += before - after
                        self.clamp_camera()
                    else:
                        # 面板上滚轮 = 滚动面板列表（超出屏幕的内容），不缩放画布
                        self.panel_scroll = max(0, self.panel_scroll - e.y * 60)
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    if e.button == 2:
                        self.panning = True
                        self.drag_start = vec(e.pos) - self.offset * self.zoom
                    elif e.button == 1 and self._toggle_rect is not None and self._toggle_rect.collidepoint(e.pos):
                        self.panel_collapsed = not self.panel_collapsed   # 面板拉手（优先于面板/画布点击）
                    elif self.panel_rect is not None and self.panel_rect.collidepoint(e.pos):
                        self.handle_panel_click(e.pos, e.button)
                    elif e.button == 1:
                        wp = self.s2w(e.pos)
                        if self.terrain_mode:
                            # 地形绘制模式：左键=加顶点（点画布区域）
                            self.terrain_drawing.append(vec(int(wp.x), int(wp.y)))
                        elif self.selected_type and self.selected_type.startswith("special:"):
                            # 特殊单位：两步放置（刷新点→目标点）
                            self.place_special(wp)
                        elif self.selected_type == "road":
                            # 道路：两点绘制（起点→终点）
                            self.place_road(wp)
                        elif self.selected_type:
                            hit = self.hit_ore(wp)
                            if hit is not None:
                                # 拖动已有矿脉（优先于放置新矿脉）
                                self.dragging_ore = hit
                            elif self.selected_type and self.selected_type.startswith("spawn:"):
                                idx = int(self.selected_type.split(":")[1])
                                if idx < len(self.map_obj.bases_config):
                                    self.map_obj.bases_config[idx] = vec(int(wp.x), int(wp.y))
                                    self.dirty = True
                            else:
                                self.place_building(self.selected_type, vec(int(wp.x), int(wp.y)))
                        else:
                            # 空闲模式：点特殊单位标记=选中（AC130 可用 +/- 调攻击半径）；
                            # 点不到标记则走地形多边形选中/取消
                            hit = self.hit_special(wp)
                            if hit is not None:
                                if hit != self.selected_special:
                                    self.selected_special = hit
                                    self.flash("已选中特殊单位" + ("（AC130：按 +/- 调整攻击半径）"
                                                if (self.map_obj.special_specs or [])[hit].get("type") == "AC130" else ""))
                            else:
                                self.selected_special = None
                                self.select_terrain_at(wp)
                    elif e.button == 3:
                        if self.terrain_drawing:
                            self.cancel_terrain_drawing()
                        elif self.road_pending is not None:
                            self.road_pending = None          # 取消道路放置
                            self.flash("已取消道路放置")
                        elif self.bridge_pending is not None:
                            self.bridge_pending = None        # 取消桥梁放置
                            self.flash("已取消桥梁放置")
                        else:
                            wp = self.s2w(e.pos)
                            # 删除优先级：路（细长目标）→ 建筑（实体目标）→ 地形多边形。
                            # 点在水上建筑时必须能直接删建筑，而不是先删掉其下的水域
                            if self.delete_road_at(wp):
                                self.flash("已删除道路")
                            else:
                                deleted = self.delete_at(wp)
                                if deleted:
                                    self.flash(f"已删除 {deleted}")
                                else:
                                    deleted = self.delete_terrain_poly(wp)
                                    if deleted:
                                        self.flash(f"已删除{deleted}多边形")
                elif e.type == pygame.MOUSEBUTTONUP:
                    if e.button == 2:
                        self.panning = False
                    elif e.button == 1 and self.dragging_ore is not None:
                        self.dragging_ore = None
                elif e.type == pygame.MOUSEMOTION:
                    if self.panning and e.buttons[1]:
                        self.offset = (vec(e.pos) - self.drag_start) / self.zoom
                        self.clamp_camera()
                    elif self.dragging_ore is not None and e.buttons[0]:
                        # 矿脉跟随鼠标（吸附到 5px 格，存 JSON 整洁）
                        wp = self.s2w(e.pos)
                        self.dragging_ore.pos = vec(
                            int(wp.x // 5) * 5, int(wp.y // 5) * 5)
                        self.dirty = True
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_LEFT:
                        self.load_map(self.map_index - 1)      # 左右循环切换地图
                    elif e.key == pygame.K_RIGHT:
                        self.load_map(self.map_index + 1)
                    elif e.key == pygame.K_RETURN and self.terrain_mode:
                        self.close_terrain_poly()              # 闭合地形多边形
                    elif e.key == pygame.K_BACKSPACE and self.terrain_drawing:
                        self.terrain_drawing.pop()             # 撤销最后一个顶点
                    elif e.key == pygame.K_DELETE and not self.terrain_mode:
                        wp = self.s2w(pygame.mouse.get_pos())
                        if self.delete_road_at(wp):        # 鼠标下是路 → 优先删路
                            self.flash("已删除道路")
                        else:
                            deleted = self.delete_at(wp)   # 再删建筑（同右键优先级）
                            if deleted:
                                self.flash(f"已删除 {deleted}")
                            else:
                                deleted = self.delete_terrain_poly(wp)
                                if deleted:
                                    self.flash(f"已删除{deleted}多边形")
                    elif pygame.K_F1 <= e.key <= pygame.K_F9:
                        idx = e.key - pygame.K_F1
                        if idx < len(MAP_CLASSES):
                            self.load_map(idx)
                    elif e.key == pygame.K_s:
                        m = self.map_obj
                        path = m.save_layout()
                        self.dirty = False
                        self.flash(f"已保存 {len(m.neutral_buildings)} 建筑 {len(m.bases_config)} 出生点 → {os.path.basename(path)}")
                    elif e.key == pygame.K_l:
                        self.reload_json()
                    elif e.key == pygame.K_TAB:
                        self.panel_collapsed = not self.panel_collapsed   # 收起/展开面板
                    elif e.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                        self.adjust_ac130_radius(+50)          # 选中 AC130：攻击半径 +50
                    elif e.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        self.adjust_ac130_radius(-50)          # 选中 AC130：攻击半径 -50

            # 每帧平移（WASD；方向键已用于切换地图）
            keys = pygame.key.get_pressed()
            pan = 28 / self.zoom
            if keys[pygame.K_w]:
                self.offset.y -= pan
            if keys[pygame.K_a]:
                self.offset.x -= pan
            if keys[pygame.K_d]:
                self.offset.x += pan
            self.clamp_camera()

            # 标题栏：有未保存修改时提示
            cap = f"地图布局编辑器 - {self.map_obj.__class__.__name__}" + ("   * 未保存 (按 S) *" if self.dirty else "")
            if cap != self._last_cap:
                pygame.display.set_caption(cap)
                self._last_cap = cap

            self.panel_rect = None
            self.draw_background()
            self.draw_terrain_polys()
            # 道路背景层（贴地：地形之上、建筑/标记之下）
            if getattr(self.map_obj, 'roads', None):
                from game.roads import draw_roads_screen
                draw_roads_screen(self.win, self.map_obj.roads, self.offset, self.zoom)
            if self.road_pending is not None:
                # 两点绘制橡皮筋：起点圈 + 到鼠标的引导线（宽度示意圈）
                a = self.w2s(self.road_pending)
                mp = self.s2w(pygame.mouse.get_pos())
                b = self.w2s(mp)
                pygame.draw.line(self.win, (235, 205, 90), a, b, 2)
                rad = max(3, int(self.road_width * self.zoom / 2))
                pygame.draw.circle(self.win, (235, 205, 90), a, rad, 1)
                pygame.draw.circle(self.win, (235, 205, 90), b, rad, 1)
            self.draw_buildings()
            self.draw_spawn_points()
            self.draw_special_units()
            self.draw_ghost()
            if not self.panel_collapsed:
                self.draw_panel()
            self.draw_status()
            self.draw_panel_toggle()
            pygame.display.flip()
        pygame.quit()

    def draw_status(self):
        W, H = self.win.get_size()
        pw = 0 if self.panel_collapsed else PANEL_W
        bar = pygame.Rect(pw, H - 26, W - pw, 26)
        pygame.draw.rect(self.win, PANEL_BG, bar)
        m = self.map_obj
        cls_name = m.__class__.__name__
        cn = getattr(m, "name_cn_static", "") or getattr(m, "name_static", "")
        mx, my = pygame.mouse.get_pos()
        over_panel = self.panel_rect is not None and self.panel_rect.collidepoint((mx, my))
        wp = self.s2w((mx, my)) if not over_panel else None
        coord = f"({int(wp.x)}, {int(wp.y)})" if wp else "--"
        info = f"{cn} {cls_name}   缩放 {int(self.zoom * 100)}%   坐标 {coord}   中立建筑 {len(m.neutral_buildings)}   出生点 {len(m.bases_config)}   地形 {len(getattr(m, 'terrain_polys', []))}   特殊单位 {len(getattr(m, 'special_specs', None) or [])}   道路 {len(getattr(m, 'roads', []))}"
        if self.terrain_mode:
            label = self.TERRAIN_LABELS.get(self.terrain_mode, self.terrain_mode)
            n = len(self.terrain_drawing)
            info += f"   [{label}绘制中 顶点{n} Enter闭合 Backspace撤销 右键取消]"
        elif self.selected_terrain is not None:
            sp = self._selected_poly()
            if sp is not None:
                info += f"   [已选中{self.TERRAIN_LABELS.get(sp['type'], sp['type'])} Esc取消 面板可改颜色/透明度]"
        if self.selected_type == "Bridge":
            info += "   桥：两点放置" + ("（已定起点，再点终点；右键取消）" if self.bridge_pending is not None else "（点起点）")
        self.win.blit(self.font.render(info, True, TXT), (pw + 10, H - 22))
        if self.save_msg and pygame.time.get_ticks() - self.save_msg_t < 2500:
            msg = self.font.render(self.save_msg, True, (140, 240, 140))
            self.win.blit(msg, (W - msg.get_width() - 14, H - 22))
        elif self.dirty:
            warn = self.font.render("● 有未保存修改 — 按 S 保存", True, (250, 130, 100))
            self.win.blit(warn, (W - warn.get_width() - 14, H - 22))


if __name__ == "__main__":
    start = 0
    if len(sys.argv) > 1:
        for i, mc in enumerate(MAP_CLASSES):
            if mc.__name__ == sys.argv[1]:
                start = i
                break
        else:
            print(f"[Editor] Unknown map '{sys.argv[1]}', using first.")
    MapLayoutEditor(start).run()
