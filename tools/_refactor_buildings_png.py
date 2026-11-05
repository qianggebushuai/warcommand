# -*- coding: utf-8 -*-
"""一次性重构脚本：RadarBuilding/PowerPlant/Airfield/ResearchCenter/Bastion
   的 draw（PowerPlant/Airfield/ResearchCenter 为两遍重复绘制）-> _draw_static +
   generate_image + _image_anchor + 精简 draw（动态部分保留）。"""
import io
import os
import sys

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "units", "buildings.py")

raw = io.open(PATH, "rb").read().decode("utf-8")
has_bom = raw.startswith("﻿")
if has_bom:
    raw = raw[1:]
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n") if crlf else raw
lines = src.split("\n")


def find_line(pred, start=0):
    for i in range(start, len(lines)):
        if pred(lines[i]):
            return i
    raise AssertionError("anchor not found after line %d" % start)


def replace_draw(class_name, next_class_pred, methods_text, marker_check):
    i_class = find_line(lambda l: l.strip() == "class %s(Building):" % class_name)
    j = find_line(lambda l: l == "    def draw(self, surface, offset, zoom):", i_class)
    k = find_line(next_class_pred, j)
    old = "\n".join(lines[j:k])
    assert marker_check(old), "marker check failed for %s" % class_name
    new_lines = methods_text.strip("\n").split("\n")
    if next_class_pred is not _is_nested_class:
        new_lines = new_lines + ["", ""]
    lines[j:k] = new_lines
    print("replaced %s.draw: lines %d..%d -> %d lines" % (class_name, j + 1, k, len(new_lines)))


def _is_nested_class(l):
    return l.startswith("    class ")


def _is_top_class(l):
    return l.startswith("class ")


def insert_after_init(class_name, init_stmt, insert="        self.image = self.generate_image()"):
    i_class = find_line(lambda l: l.strip() == "class %s(Building):" % class_name)
    i = find_line(lambda l: l.strip() == init_stmt, i_class)
    lines.insert(i + 1, insert)
    print("inserted self.image into %s.__init__ after line %d" % (class_name, i + 1))


# ---------------- RadarBuilding ----------------
RADAR_NEW = '''    def _draw_static(self, surface, cx, cy, zoom):
        """静态外观：雷达车底盘（车轮/车体/驾驶舱/设备箱/支架），generate_image 与无图回退共用"""
        truck_len = scale(80, zoom)
        truck_wid = scale(35, zoom)

        C_CHASSIS = (55, 65, 50)
        C_CABIN = (70, 80, 65)
        C_TIRE = (20, 20, 20)
        C_SUPPORT = (30, 35, 30)
        C_BOX = (65, 75, 60)

        surf_size = int(truck_len * 1.5)
        surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        scx, scy = surf_size // 2, surf_size // 2

        wheel_r = scale(10, zoom)
        wheel_w = scale(6, zoom)
        axle_positions = [-0.35, -0.15, 0.15, 0.35]

        for pos_factor in axle_positions:
            wx = scx + truck_len * pos_factor
            pygame.draw.rect(surf, C_TIRE, (wx - wheel_r, scy - truck_wid//2 - wheel_w, wheel_r*2, wheel_w))
            pygame.draw.rect(surf, C_TIRE, (wx - wheel_r, scy + truck_wid//2, wheel_r*2, wheel_w))
            pygame.draw.circle(surf, (40,40,40), (int(wx), int(scy - truck_wid//2 - wheel_w//2)), int(scale(3, zoom)))
            pygame.draw.circle(surf, (40,40,40), (int(wx), int(scy + truck_wid//2 + wheel_w//2)), int(scale(3, zoom)))

        pygame.draw.line(surf, C_SUPPORT, (scx - truck_len*0.4, scy - truck_wid*0.4), (scx - truck_len*0.4, scy - truck_wid*0.8), 3)
        pygame.draw.circle(surf, C_SUPPORT, (int(scx - truck_len*0.4), int(scy - truck_wid*0.8)), int(scale(4, zoom)))
        pygame.draw.line(surf, C_SUPPORT, (scx - truck_len*0.4, scy + truck_wid*0.4), (scx - truck_len*0.4, scy + truck_wid*0.8), 3)
        pygame.draw.circle(surf, C_SUPPORT, (int(scx - truck_len*0.4), int(scy + truck_wid*0.8)), int(scale(4, zoom)))

        rect_body = pygame.Rect(scx - truck_len//2, scy - truck_wid//2, truck_len, truck_wid)
        pygame.draw.rect(surf, C_CHASSIS, rect_body)

        cab_len = truck_len * 0.2
        rect_cab = pygame.Rect(scx + truck_len//2 - cab_len, scy - truck_wid//2, cab_len, truck_wid)
        pygame.draw.rect(surf, C_CABIN, rect_cab)
        pygame.draw.rect(surf, (30, 40, 50), (rect_cab.right - scale(5, zoom), rect_cab.top + scale(3, zoom), scale(3, zoom), scale(10, zoom)))
        pygame.draw.rect(surf, (30, 40, 50), (rect_cab.right - scale(5, zoom), rect_cab.bottom - scale(13, zoom), scale(3, zoom), scale(10, zoom)))

        box_w = scale(5, zoom)
        for i in range(3):
            bx = scx - truck_len*0.3 + i * scale(15, zoom)
            pygame.draw.rect(surf, C_BOX, (bx, scy - truck_wid//2 - box_w, scale(12, zoom), box_w))
            pygame.draw.rect(surf, C_BOX, (bx, scy + truck_wid//2, scale(12, zoom), box_w))

        surface.blit(surf, (cx - scx, cy - scy))

    def generate_image(self):
        """静态外观基准图（zoom=1），锚点 (60, 60) = self.pos；PNG 缓存由 sprite_cache 自动导出/加载"""
        surf = pygame.Surface((120, 120), pygame.SRCALPHA)
        self._draw_static(surf, 60, 60, 1.0)
        return surf

    def _image_anchor(self):
        return 60, 60

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        margin = 300 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return

        radar_w = scale(60, zoom)

        C_CHASSIS = (55, 65, 50)
        C_RADAR_BACK = (60, 70, 55)
        C_SUPPORT = (30, 35, 30)
        C_BOX = (65, 75, 60)

        # --- 静态外观（PNG 命中时为图片 blit，未命中现场绘制） ---
        if not self._blit_cached_image(surface, cx, cy, zoom):
            self._draw_static(surface, cx, cy, zoom)

        # --- 动态部分：旋转雷达与扫描扇形（保留程序绘制） ---
        radar_surf_size = int(radar_w * 1.5)
        r_surf = pygame.Surface((radar_surf_size, radar_surf_size), pygame.SRCALPHA)
        rcx, rcy = radar_surf_size // 2, radar_surf_size // 2

        base_r = scale(18, zoom)
        pygame.draw.circle(r_surf, C_CHASSIS, (rcx, rcy), base_r)
        pygame.draw.circle(r_surf, (40, 50, 40), (rcx, rcy), base_r, 2)

        strut_len = scale(20, zoom)
        pygame.draw.line(r_surf, C_SUPPORT, (rcx, rcy), (rcx - strut_len, rcy), 4)
        pygame.draw.line(r_surf, C_SUPPORT, (rcx, rcy - scale(10, zoom)), (rcx - strut_len, rcy), 2)
        pygame.draw.line(r_surf, C_SUPPORT, (rcx, rcy + scale(10, zoom)), (rcx - strut_len, rcy), 2)

        pygame.draw.rect(r_surf, C_BOX, (rcx - scale(15, zoom), rcy - scale(15, zoom), scale(10, zoom), scale(30, zoom)))

        rect_face = pygame.Rect(rcx - scale(2, zoom), rcy - radar_w//2, scale(6, zoom), radar_w)
        pygame.draw.rect(r_surf, C_RADAR_BACK, rect_face)

        front_edge_x = rect_face.right
        pygame.draw.line(r_surf, (80, 90, 80), (front_edge_x, rect_face.top), (front_edge_x, rect_face.bottom), 2)

        pygame.draw.line(r_surf, C_SUPPORT, (rcx, rcy - radar_w//2), (rcx + scale(10, zoom), rcy - radar_w//2), 2)

        dish_pos = (rcx - scale(10, zoom), rcy + radar_w//2 + scale(5, zoom))
        pygame.draw.circle(r_surf, C_RADAR_BACK, dish_pos, scale(8, zoom))
        pygame.draw.circle(r_surf, (30, 40, 30), dish_pos, scale(6, zoom))
        pygame.draw.line(r_surf, C_SUPPORT, (rcx, rcy), dish_pos, 2)

        rotated_radar = cached_rotate(r_surf, -self.angle)
        radar_rect = rotated_radar.get_rect(center=screen_pos)

        shadow_surf = cached_rotate(r_surf, -self.angle)
        shadow_surf.fill((0, 0, 0, 60), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(shadow_surf, (radar_rect.x + scale(5, zoom), radar_rect.y + scale(5, zoom)))

        surface.blit(rotated_radar, radar_rect)

        if self.alive:
            scan_len = scale(200, zoom)
            scan_angle = math.radians(self.angle)
            p1 = screen_pos
            p2 = (cx + math.cos(scan_angle - 0.2) * scan_len, cy + math.sin(scan_angle - 0.2) * scan_len)
            p3 = (cx + math.cos(scan_angle + 0.2) * scan_len, cy + math.sin(scan_angle + 0.2) * scan_len)

            scan_s = pygame.Surface((scan_len*2, scan_len*2), pygame.SRCALPHA)
            local_c = (scan_len, scan_len)
            local_p2 = (scan_len + math.cos(-0.2)*scan_len, scan_len + math.sin(-0.2)*scan_len)
            local_p3 = (scan_len + math.cos(0.2)*scan_len, scan_len + math.sin(0.2)*scan_len)

            alpha = int(50 + 30 * math.sin(pygame.time.get_ticks() * 0.005))
            pygame.draw.polygon(scan_s, (0, 255, 0, alpha), [local_c, local_p2, local_p3])

            scan_rot = cached_rotate(scan_s, -self.angle)
            scan_rect = scan_rot.get_rect(center=screen_pos)
            surface.blit(scan_rot, scan_rect)

        self.draw_health_and_marker(surface, offset, zoom, -scale(60, zoom))'''

# ---------------- PowerPlant ----------------
POWER_NEW = '''    def _draw_static(self, surface, cx, cy, zoom):
        """静态外观：阴影/平台/冷却塔/反应堆主体，generate_image 与无图回退共用"""
        VIEW_ANGLE_FACTOR = 0.6

        tower_radius_base = scale(35, zoom)
        tower_radius_top = scale(25, zoom)
        tower_height_visual = scale(60, zoom) * VIEW_ANGLE_FACTOR

        reactor_radius = scale(18, zoom)

        C_SHADOW = (0, 0, 0, 80)
        C_CONCRETE_DARK = (100, 100, 110)
        C_CONCRETE_MID = (160, 160, 170)
        C_CONCRETE_LIGHT = (210, 210, 220)
        C_HOLE = (40, 40, 45)
        C_REACTOR = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        C_SYMBOL = (220, 200, 0)

        shadow_offset_x = scale(15, zoom)
        shadow_offset_y = scale(15, zoom)

        shadow_surf = pygame.Surface((scale(150, zoom), scale(150, zoom)), pygame.SRCALPHA)
        shadow_center = (scale(75, zoom), scale(75, zoom))

        pygame.draw.circle(shadow_surf, C_SHADOW, shadow_center, tower_radius_base)
        r_shadow_pos = (shadow_center[0] + scale(40, zoom), shadow_center[1] + scale(10, zoom))
        pygame.draw.circle(shadow_surf, C_SHADOW, r_shadow_pos, reactor_radius)

        surface.blit(shadow_surf, (cx - shadow_center[0] + shadow_offset_x, cy - shadow_center[1] + shadow_offset_y))

        base_rect = pygame.Rect(cx - tower_radius_base - scale(10, zoom),
                            cy - tower_radius_base - scale(10, zoom),
                            scale(100, zoom), scale(90, zoom))
        pygame.draw.rect(surface, (90, 90, 95), base_rect, border_radius=int(scale(5, zoom)))

        base_y = cy
        pygame.draw.circle(surface, C_CONCRETE_DARK, (cx, base_y), tower_radius_base)
        pygame.draw.circle(surface, (50,50,50), (cx, base_y), tower_radius_base, 1)

        top_y = cy - tower_height_visual

        points = [
            (cx - tower_radius_base, base_y),
            (cx - tower_radius_top, top_y),
            (cx + tower_radius_top, top_y),
            (cx + tower_radius_base, base_y)
        ]
        pygame.draw.polygon(surface, C_CONCRETE_MID, points)

        pygame.draw.circle(surface, C_CONCRETE_LIGHT, (cx, int(top_y)), tower_radius_top)
        pygame.draw.circle(surface, (100,100,100), (cx, int(top_y)), tower_radius_top, 1)

        hole_radius = tower_radius_top - scale(4, zoom)
        pygame.draw.circle(surface, C_HOLE, (cx, int(top_y)), hole_radius)

        pygame.draw.circle(surface, (20, 20, 25), (cx - scale(2, zoom), int(top_y) - scale(2, zoom)), hole_radius*0.9)

        rx = cx + scale(40, zoom)
        ry = cy + scale(10, zoom)
        r_top_y = ry - scale(15, zoom) * VIEW_ANGLE_FACTOR

        pygame.draw.circle(surface, C_CONCRETE_DARK, (rx, ry), reactor_radius)

        r_points = [
            (rx - reactor_radius, ry),
            (rx - reactor_radius, r_top_y),
            (rx + reactor_radius, r_top_y),
            (rx + reactor_radius, ry)
        ]
        pygame.draw.polygon(surface, C_CONCRETE_MID, r_points)

        pygame.draw.circle(surface, C_REACTOR, (rx, int(r_top_y)), reactor_radius)

        highlight_offset = scale(6, zoom)
        pygame.draw.circle(surface, (230, 230, 240), (rx - highlight_offset, int(r_top_y) - highlight_offset), reactor_radius * 0.4)

        icon_x, icon_y = rx, int(r_top_y)
        icon_r = scale(8, zoom)
        pygame.draw.circle(surface, C_SYMBOL, (icon_x, icon_y), icon_r)
        for i in range(3):
            angle_rad = math.radians(i * 120 - 30)
            end_x = icon_x + math.cos(angle_rad) * icon_r
            end_y = icon_y + math.sin(angle_rad) * icon_r
            pygame.draw.line(surface, (0,0,0), (icon_x, icon_y), (end_x, end_y), int(scale(3, zoom)))
        pygame.draw.circle(surface, (0,0,0), (icon_x, icon_y), int(scale(2, zoom)))

    def generate_image(self):
        """静态外观基准图（zoom=1），锚点 (60, 62) = self.pos；PNG 缓存由 sprite_cache 自动导出/加载"""
        surf = pygame.Surface((150, 152), pygame.SRCALPHA)
        self._draw_static(surf, 60, 62, 1.0)
        return surf

    def _image_anchor(self):
        return 60, 62

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

        # --- 动态部分：冷却塔蒸汽（保留程序绘制） ---
        top_y = cy - scale(60, zoom) * 0.6
        current_time = time.time()
        steam_base_y = top_y
        for i in range(3):
            offset_val = (current_time * 2 + i)
            steam_dy = (offset_val % 1.0) * scale(60, zoom)
            steam_alpha = 150 * (1 - (steam_dy / scale(60, zoom)))

            steam_dx = math.sin(current_time * 3 + i) * scale(5, zoom)

            steam_r = scale(10 + i*2, zoom)

            s_surf = pygame.Surface((steam_r*2, steam_r*2), pygame.SRCALPHA)
            pygame.draw.circle(s_surf, (255, 255, 255, int(steam_alpha)), (steam_r, steam_r), steam_r)

            dest_x = cx - steam_r + steam_dx
            dest_y = steam_base_y - steam_r - steam_dy
            surface.blit(s_surf, (dest_x, dest_y))

        self.draw_health_and_marker(surface, offset, zoom)'''

# ---------------- Airfield ----------------
AIRFIELD_NEW = '''    def _draw_static(self, surface, cx, cy, zoom):
        """静态外观：机场平台/跑道/机库/塔台主体（塔台饰条随 is_upgraded 变色，留在 draw）"""
        field_w = scale(140, zoom)
        field_h = scale(90, zoom)
        slab_h = scale(8, zoom)

        C_CONCRETE      = (100, 100, 105)
        C_CONCRETE_SIDE = (60, 60, 65)
        C_MARKING       = (220, 220, 220)
        C_MARKING_Y     = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        C_TOWER_BASE    = (120, 120, 125)
        C_GLASS         = (20, 40, 60)
        C_GLASS_HILITE  = (50, 80, 100)
        C_HANGAR        = (90, 95, 100)

        shadow_offset = scale(10, zoom)
        s_surf = pygame.Surface((field_w + shadow_offset, field_h + shadow_offset), pygame.SRCALPHA)
        pygame.draw.rect(s_surf, (0, 0, 0, 80), (shadow_offset, shadow_offset, field_w, field_h), border_radius=int(scale(5, zoom)))
        surface.blit(s_surf, (cx - field_w//2, cy - field_h//2))

        base_top_y = cy

        pygame.draw.rect(surface, C_CONCRETE_SIDE, (cx - field_w//2, base_top_y - field_h//2, field_w, field_h + slab_h))
        field_rect = pygame.Rect(cx - field_w//2, base_top_y - field_h//2, field_w, field_h)
        pygame.draw.rect(surface, C_CONCRETE, field_rect)
        pygame.draw.rect(surface, (80, 80, 80), field_rect, 2)

        runway_w = field_w * 0.8
        runway_h = field_h * 0.4
        runway_y = field_rect.bottom - runway_h - scale(10, zoom)

        pygame.draw.rect(surface, (80, 80, 85), (cx - runway_w//2, runway_y, runway_w, runway_h))

        dash_len = scale(15, zoom)
        gap_len = scale(10, zoom)
        start_x = cx - runway_w//2 + scale(10, zoom)
        mid_y = runway_y + runway_h//2
        for i in range(5):
            dx = start_x + i * (dash_len + gap_len)
            pygame.draw.line(surface, C_MARKING, (dx, mid_y), (dx + dash_len, mid_y), int(scale(3, zoom)))

        pygame.draw.line(surface, C_MARKING_Y, (cx - field_w//2 + scale(5, zoom), runway_y - scale(5, zoom)),
                        (cx + field_w//2 - scale(5, zoom), runway_y - scale(5, zoom)), 2)

        hangar_w = scale(40, zoom)
        hangar_l = scale(30, zoom)
        hangar_h = scale(20, zoom)

        hx = field_rect.left + scale(15, zoom)
        hy = field_rect.top + scale(15, zoom) + hangar_l

        pygame.draw.rect(surface, (70, 75, 80), (hx, hy - hangar_h, hangar_w, hangar_h))
        pygame.draw.rect(surface, (40, 40, 45), (hx + scale(5, zoom), hy - hangar_h + scale(5, zoom), hangar_w - scale(10, zoom), hangar_h))

        roof_rect = pygame.Rect(hx, hy - hangar_h - scale(10, zoom), hangar_w, scale(20, zoom))
        pygame.draw.arc(surface, C_HANGAR, roof_rect, 0, math.pi, scale(10, zoom))
        pygame.draw.line(surface, (60, 60, 65), (hx, hy - hangar_h), (hx + hangar_w, hy - hangar_h), 2)

        tx = field_rect.right - scale(30, zoom)
        ty_base = field_rect.top + scale(30, zoom)

        t_w = scale(20, zoom)
        t_h = scale(50, zoom)

        tower_rect = pygame.Rect(tx - t_w//2, ty_base - t_h, t_w, t_h)
        pygame.draw.rect(surface, C_TOWER_BASE, tower_rect)
        pygame.draw.rect(surface, (90, 90, 95), tower_rect, 2)

        deck_w = scale(32, zoom)
        deck_h = scale(18, zoom)
        deck_y = ty_base - t_h - deck_h

        deck_points = [
            (tx - deck_w//2 + scale(5, zoom), deck_y + deck_h),
            (tx + deck_w//2 - scale(5, zoom), deck_y + deck_h),
            (tx + deck_w//2, deck_y),
            (tx - deck_w//2, deck_y)
        ]
        pygame.draw.polygon(surface, C_GLASS, deck_points)
        pygame.draw.line(surface, C_GLASS_HILITE, (tx - deck_w//3, deck_y + deck_h*0.3), (tx + deck_w//3, deck_y + deck_h*0.8), 2)

        pygame.draw.rect(surface, C_TOWER_BASE, (tx - deck_w//2, deck_y - scale(4, zoom), deck_w, scale(4, zoom)))

        radar_y = deck_y - scale(4, zoom)

        pygame.draw.line(surface, (50, 50, 50), (tx, radar_y), (tx, radar_y - scale(6, zoom)), 2)

    def generate_image(self):
        """静态外观基准图（zoom=1），锚点 (70, 93) = self.pos；PNG 缓存由 sprite_cache 自动导出/加载"""
        surf = pygame.Surface((150, 150), pygame.SRCALPHA)
        self._draw_static(surf, 70, 93, 1.0)
        return surf

    def _image_anchor(self):
        return 70, 93

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

        # --- 动态部分：塔台饰条（随 is_upgraded 变色）/旋转雷达/闪烁灯（保留程序绘制） ---
        if self.is_upgraded:
            C_TOWER_TRIM = (255, 100, 50)
            C_RADAR = (255, 215, 0)
        else:
            C_TOWER_TRIM = (0, 100, 200)
            C_RADAR = (200, 200, 210)

        field_w = scale(140, zoom)
        field_h = scale(90, zoom)
        field_rect = pygame.Rect(cx - field_w//2, cy - field_h//2, field_w, field_h)

        tx = field_rect.right - scale(30, zoom)
        ty_base = field_rect.top + scale(30, zoom)
        t_h = scale(50, zoom)
        pygame.draw.line(surface, C_TOWER_TRIM, (tx, ty_base - t_h), (tx, ty_base), 2)

        deck_h = scale(18, zoom)
        deck_y = ty_base - t_h - deck_h
        radar_y = deck_y - scale(4, zoom)

        t = time.time()
        rot_speed = 8 if self.is_upgraded else 4
        angle = t * rot_speed

        radar_w = scale(14, zoom)
        dx = math.cos(angle) * radar_w
        dy = math.sin(angle) * scale(4, zoom)

        radar_center = (tx, radar_y - scale(6, zoom))
        p1 = (radar_center[0] - dx, radar_center[1] - dy)
        p2 = (radar_center[0] + dx, radar_center[1] + dy)

        pygame.draw.line(surface, C_RADAR, p1, p2, int(scale(4, zoom)))
        pygame.draw.circle(surface, (255, 255, 255), (int(radar_center[0]), int(radar_center[1])), scale(3, zoom))

        blink = int(time.time() * 2) % 2 == 0
        if blink or self.is_upgraded:
            light_color = (255, 50, 50)
            pygame.draw.circle(surface, light_color, (int(radar_center[0]), int(radar_center[1] - scale(5, zoom))), 2)

            runway_w = field_w * 0.8
            runway_h = field_h * 0.4
            runway_y = field_rect.bottom - runway_h - scale(10, zoom)
            corners = [
                (cx - runway_w//2, runway_y),
                (cx + runway_w//2, runway_y),
                (cx - runway_w//2, runway_y + runway_h),
                (cx + runway_w//2, runway_y + runway_h)
            ]
            for cp in corners:
                pygame.draw.circle(surface, (0, 255, 0), (int(cp[0]), int(cp[1])), 2)

        self.draw_health_and_marker(surface, offset, zoom, -scale(85, zoom))'''

# ---------------- ResearchCenter ----------------
RESEARCH_NEW = '''    def _draw_static(self, surface, cx, cy, zoom):
        """静态外观：阴影/基座/平台/壕沟/发电机/能量塔柱，generate_image 与无图回退共用"""
        w = scale(90, zoom)
        h_base = scale(20, zoom)
        core_h = scale(50, zoom)

        C_BASE_DARK   = (40, 40, 45)
        C_BASE_LIGHT  = (70, 75, 80)
        C_RING_METAL  = (150, 150, 160)

        shadow_offset = scale(10, zoom)
        s_surf = pygame.Surface((w + shadow_offset*2, w + shadow_offset*2), pygame.SRCALPHA)
        pygame.draw.rect(s_surf, (0, 0, 0, 80), (shadow_offset, shadow_offset, w, w), border_radius=int(scale(10, zoom)))
        surface.blit(s_surf, (cx - w//2, cy - w//2))

        base_top_y = cy + scale(10, zoom)

        pygame.draw.rect(surface, C_BASE_DARK, (cx - w//2, base_top_y - w//2, w, w))

        plat_w = w * 0.9
        plat_rect = pygame.Rect(cx - plat_w//2, base_top_y - plat_w//2 - h_base, plat_w, plat_w)

        pygame.draw.rect(surface, C_BASE_LIGHT, plat_rect)
        pygame.draw.rect(surface, (100, 105, 110), plat_rect, 2)

        trench_w = scale(6, zoom)
        pygame.draw.rect(surface, (20, 20, 25), (plat_rect.left, plat_rect.centery - trench_w//2, plat_rect.width, trench_w))
        pygame.draw.rect(surface, (20, 20, 25), (plat_rect.centerx - trench_w//2, plat_rect.top, trench_w, plat_rect.height))

        gen_w = scale(30, zoom)
        gen_h = scale(15, zoom)
        gen_y = plat_rect.centery

        gen_rect = pygame.Rect(cx - gen_w//2, gen_y - gen_h, gen_w, gen_h)
        pygame.draw.rect(surface, (50, 50, 55), gen_rect)
        pylon_offset = gen_w // 2 + scale(4, zoom)

        pylons = [
            (cx - pylon_offset, gen_y),
            (cx + pylon_offset, gen_y),
            (cx, gen_y - pylon_offset + scale(5, zoom)),
            (cx, gen_y + pylon_offset)
        ]

        for px, py in pylons:
            pygame.draw.circle(surface, C_BASE_DARK, (int(px), int(py)), int(scale(6, zoom)))
            pygame.draw.line(surface, C_RING_METAL, (px, py), (cx, gen_y - core_h//2), 2)

    def generate_image(self):
        """静态外观基准图（zoom=1），锚点 (45, 45) = self.pos；PNG 缓存由 sprite_cache 自动导出/加载"""
        surf = pygame.Surface((110, 110), pygame.SRCALPHA)
        self._draw_static(surf, 45, 45, 1.0)
        return surf

    def _image_anchor(self):
        return 45, 45

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        # 视口裁剪：镜头外直接跳过绘制
        _cm = max(500, getattr(self, 'radius', 20) * 3) * zoom
        if not (-_cm < screen_pos[0] < SCREEN_WIDTH + _cm and -_cm < screen_pos[1] < SCREEN_HEIGHT + _cm):
            return
        cx, cy = int(screen_pos[0]), int(screen_pos[1])

        w = scale(90, zoom)
        h_base = scale(20, zoom)

        C_ENERGY_CORE = (0, 180, 255)
        C_ENERGY_GLOW = (100, 220, 255)
        C_RING_METAL  = (150, 150, 160)

        team_color = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])

        t = time.time()

        # --- 静态外观（PNG 命中时为图片 blit，未命中现场绘制） ---
        if not self._blit_cached_image(surface, cx, cy, zoom):
            self._draw_static(surface, cx, cy, zoom)

        # --- 动态部分：能量流/脉冲核心/卫星/全息光束/数据流（保留程序绘制） ---
        base_top_y = cy + scale(10, zoom)
        plat_w = w * 0.9
        plat_rect = pygame.Rect(cx - plat_w//2, base_top_y - plat_w//2 - h_base, plat_w, plat_w)

        flow_offset = (t * 20) % plat_rect.width
        for i in range(-1, 2):
            pos_x = plat_rect.left + (flow_offset + i*30) % plat_rect.width
            pygame.draw.rect(surface, team_color, (pos_x, plat_rect.centery - 1, 4, 2))

            pos_y = plat_rect.top + (flow_offset + i*30) % plat_rect.height
            pygame.draw.rect(surface, team_color, (plat_rect.centerx - 1, pos_y, 2, 4))

        gen_y = plat_rect.centery
        core_center_y = gen_y - scale(25, zoom)

        pulse = (math.sin(t * 3) + 1) / 2
        core_r = scale(12 + 2 * pulse, zoom)

        glow_surf = pygame.Surface((core_r*4, core_r*4), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*C_ENERGY_CORE, 100), (core_r*2, core_r*2), core_r*1.5)
        pygame.draw.circle(glow_surf, (*C_ENERGY_GLOW, 150), (core_r*2, core_r*2), core_r)
        surface.blit(glow_surf, (cx - core_r*2, core_center_y - core_r*2))

        pygame.draw.circle(surface, (255, 255, 255), (cx, int(core_center_y)), int(core_r * 0.6))

        angle1 = t * 1.5
        rx1 = math.cos(angle1) * scale(25, zoom)
        ry1 = math.sin(angle1) * scale(8, zoom)

        sat_r = scale(3, zoom)
        pygame.draw.circle(surface, C_RING_METAL, (int(cx + rx1), int(core_center_y + ry1)), int(sat_r))
        pygame.draw.circle(surface, C_RING_METAL, (int(cx - rx1), int(core_center_y - ry1)), int(sat_r))

        beam_h = scale(80, zoom)
        beam_w = scale(10, zoom)

        beam_surf = pygame.Surface((beam_w, beam_h), pygame.SRCALPHA)

        for i in range(int(beam_h)):
            alpha = int(100 * (1 - i/beam_h))
            pygame.draw.line(beam_surf, (*team_color, alpha), (0, i), (beam_w, i))

        beam_surf = pygame.transform.flip(beam_surf, False, True)
        surface.blit(beam_surf, (cx - beam_w//2, core_center_y - beam_h))

        if int(t * 10) % 3 == 0:
            data_y = core_center_y - random.randint(10, max(10, int(scale(60, zoom))))
            data_x = cx + random.randint(-5, 5)
            pygame.draw.rect(surface, (200, 255, 255), (data_x, data_y, 2, 2))

        self.draw_health_and_marker(surface, offset, zoom, -scale(90, zoom))'''

# ---------------- Bastion ----------------
BASTION_NEW = '''    def _draw_static(self, surface, cx, cy, zoom):
        """底座静态外观：投影 + image_base 围墙/基座主体（generate_image 与无图回退共用）"""
        shadow_offset = 40 * zoom

        shadow_surf = pygame.Surface((int(420 * zoom), int(420 * zoom)), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surf, (0, 0, 0, 100), (0, 0, 420 * zoom, 420 * zoom), border_radius=int(10 * zoom))
        surface.blit(shadow_surf, (cx - 210 * zoom + shadow_offset, cy - 210 * zoom + shadow_offset + 15 * zoom))

        scaled_base = scale_img(self.image_base, zoom)
        rect_base = scaled_base.get_rect(center=(cx, cy))
        surface.blit(scaled_base, rect_base)

    def generate_image(self):
        """底座静态基准图（含投影，zoom=1），锚点 (300, 300) = self.pos；作为额外部件随 sprite_cache 导出/加载"""
        s = pygame.Surface((600, 600), pygame.SRCALPHA)
        self._draw_static(s, 300, 300, 1.0)
        return s

    def _image_anchor(self):
        return 300, 300

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 600 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return

        # --- 底座静态外观（含投影；PNG 命中时为图片 blit，未命中现场绘制） ---
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        if not self._blit_cached_image(surface, cx, cy, zoom):
            self._draw_static(surface, cx, cy, zoom)

        # --- 动态部分：四联炮塔（独立角度旋转，保留程序绘制） ---
        scaled_turret_img = scale_img(self.image_turret, zoom)

        for turret in self.turrets:
            t_offset = turret['offset'] * zoom
            t_screen_pos = (screen_pos[0] + t_offset.x, screen_pos[1] + t_offset.y)

            rot_turret = cached_rotate(scaled_turret_img, turret['angle'])
            rect_turret = rot_turret.get_rect(center=t_screen_pos)

            # 阴影必须用副本：cached_rotate 返回共享缓存面，原地 fill 会把
            # 缓存永久压暗（每帧再乘一次 alpha，炮塔渐进变黑消失）
            t_shadow_surf = rot_turret.copy()
            t_shadow_surf.fill((0,0,0,80), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(t_shadow_surf, (rect_turret.x + 5*zoom, rect_turret.y + 5*zoom))

            surface.blit(rot_turret, rect_turret)

        self.draw_health_and_marker(surface, offset, zoom, y_offset=-150*zoom)'''

replace_draw("RadarBuilding", _is_top_class, RADAR_NEW, lambda old: "cached_rotate(r_surf" in old)
replace_draw("PowerPlant", _is_top_class, POWER_NEW, lambda old: old.count("VIEW_ANGLE_FACTOR = 0.6") == 2)
replace_draw("Airfield", _is_top_class, AIRFIELD_NEW, lambda old: old.count("C_TOWER_TRIM = (255, 100, 50)") == 2)
replace_draw("ResearchCenter", _is_top_class, RESEARCH_NEW, lambda old: old.count("beam_h = scale(80, zoom)") == 2)
replace_draw("Bastion", _is_nested_class, BASTION_NEW,
             lambda old: "scaled_turret_img = scale_img(self.image_turret, zoom)" in old and "shadow_rect" in old)

insert_after_init("RadarBuilding", "self.angle = 0")
insert_after_init("PowerPlant", "self.power_usage = 0")
insert_after_init("Airfield", "self.is_upgraded = False")
insert_after_init("ResearchCenter", "self.rect = pygame.Rect(pos.x - 45, pos.y - 45, 90, 90)")
insert_after_init("Bastion", "self.image_turret = self.generate_turret_image()")

out = "\n".join(lines)
if crlf:
    out = out.replace("\n", "\r\n")
data = out.encode("utf-8")
if has_bom:
    data = b"\xef\xbb\xbf" + data
io.open(PATH, "wb").write(data)
print("written:", PATH, "total lines:", len(lines))
