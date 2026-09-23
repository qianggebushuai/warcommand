import pygame
import os
import sys
import math

# 初始化pygame
pygame.init()

# 确保sprite文件夹存在
sprite_dir = os.path.join(os.path.dirname(__file__), 'sprite')
if not os.path.exists(sprite_dir):
    os.makedirs(sprite_dir)

# 模拟必要的设置
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
TEAM_COLORS = {
    "team_0": (0, 100, 255),
    "team_1": (200, 50, 50),
    "team_2": (50, 200, 50),
    "team_3": (200, 200, 50),
    "team_4": (200, 0, 255),
    "neutral": (128, 128, 128),
    "enemy": (200, 50, 50),
    "player": (0, 100, 255)
}

# 生成ArmoredCar图片
def generate_armored_car():
    folder = os.path.join(sprite_dir, 'armored_car')
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    # 生成不同队伍的装甲车
    for team, color in TEAM_COLORS.items():
        if team in ["neutral", "enemy", "player"]:
            continue
        
        original_image = pygame.Surface((80, 80), pygame.SRCALPHA)
        C_TIRE = (15, 15, 20)
        C_BODY = (65, 75, 65)
        C_BODY_LIGHT = (85, 95, 85)
        C_DETAIL = (40, 50, 40)
        C_BARREL = (30, 30, 35)
        C_TEAM = color
        
        wheel_offsets = [(12, -12), (-12, -12), (12, 12), (-12, 12)]
        for dx, dy in wheel_offsets:
            wx, wy = 40 + dx - 5, 40 + dy - 3
            pygame.draw.rect(original_image, C_TIRE, (wx, wy, 10, 6), border_radius=2)
        
        pygame.draw.rect(original_image, C_BODY, (20, 30, 35, 20))
        nose_points = [(55, 30), (65, 40), (55, 50)]
        pygame.draw.polygon(original_image, C_BODY, nose_points)
        pygame.draw.rect(original_image, C_BODY_LIGHT, (22, 34, 30, 12))
        pygame.draw.rect(original_image, (20, 30, 40), (50, 35, 4, 10))
        pygame.draw.rect(original_image, C_TEAM, (22, 34, 4, 12))
        
        turret_x, turret_y = 38, 40
        pygame.draw.line(original_image, C_BARREL, (turret_x, turret_y), (turret_x + 22, turret_y), 3)
        pygame.draw.line(original_image, (10,10,10), (turret_x + 20, turret_y), (turret_x + 22, turret_y), 5)
        pygame.draw.circle(original_image, C_BODY_LIGHT, (turret_x, turret_y), 7)
        pygame.draw.circle(original_image, C_DETAIL, (turret_x, turret_y), 4)
        
        pygame.draw.circle(original_image, (200, 50, 50), (20, 33), 1)
        pygame.draw.circle(original_image, (200, 50, 50), (20, 47), 1)
        
        # 保存图片
        filename = os.path.join(folder, f'armored_car_{team}.png')
        pygame.image.save(original_image, filename)
        print(f"生成 {filename}")

# 生成APC图片
def generate_apc():
    folder = os.path.join(sprite_dir, 'apc')
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    # 生成不同队伍的APC
    for team, color in TEAM_COLORS.items():
        if team in ["neutral", "enemy", "player"]:
            continue
        
        # 常规APC (USA)
        w_raw, h_raw = 80, 50
        body_surf = pygame.Surface((w_raw, h_raw), pygame.SRCALPHA)
        color_body = color
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
        
        # 炮塔
        s = pygame.Surface((40, 40), pygame.SRCALPHA)
        cx, cy = 20, 20
        color_dark = (40, 45, 40)
        pygame.draw.rect(s, (20, 20, 20), (cx, cy-2, 18, 4))
        pygame.draw.circle(s, color_dark, (cx, cy), 9)
        pygame.draw.rect(s, (40, 50, 40), (cx-5, cy-8, 10, 6))
        
        # 保存图片
        filename = os.path.join(folder, f'apc_{team}.png')
        pygame.image.save(body_surf, filename)
        print(f"生成 {filename}")
        
        # 防空APC (CHINA/RUSSIA)
        w, h = 80, 56
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w//2, h//2
        
        C_BODY = (100, 110, 90)
        C_TRACK = (30, 30, 35)
        C_DETAIL = (60, 70, 60)
        
        pygame.draw.rect(s, C_TRACK, (5, 2, 70, 10))
        pygame.draw.rect(s, C_TRACK, (5, 44, 70, 10))
        for i in range(0, 70, 8):
            pygame.draw.line(s, (10,10,10), (5+i, 2), (5+i, 12), 1)
            pygame.draw.line(s, (10,10,10), (5+i, 44), (5+i, 54), 1)
        
        body_rect = pygame.Rect(5, 10, 70, 36)
        pygame.draw.rect(s, C_BODY, body_rect)
        pygame.draw.rect(s, C_DETAIL, body_rect, 1)
        pygame.draw.polygon(s, (120, 130, 110), [(60, 12), (75, 20), (75, 36), (60, 44)])
        pygame.draw.rect(s, (40,40,40), (8, 15, 10, 26))
        for i in range(4):
            pygame.draw.line(s, (60,60,60), (8, 18+i*6), (18, 18+i*6), 1)
        
        # 防空炮塔
        w_turret, h_turret = 70, 60
        turret_surf = pygame.Surface((w_turret, h_turret), pygame.SRCALPHA)
        cx, cy = w_turret // 2, h_turret // 2
        
        C_TURRET = (80, 90, 70)
        C_BARREL = (30, 30, 35)
        C_MISSILE = (160, 150, 130)
        C_RADAR = (100, 110, 120)
        C_SENSOR = (40, 40, 50)
        
        turret_w = 28
        turret_h = 24
        turret_rect = pygame.Rect(cx-turret_w//2, cy-turret_h//2, turret_w, turret_h)
        pygame.draw.rect(turret_surf, C_TURRET, turret_rect, border_radius=4)
        pygame.draw.rect(turret_surf, (60, 70, 50), turret_rect.inflate(-4, -4), 1)
        
        barrel_len = 35
        barrel_w = 4
        gun_y_top = cy - 10
        pygame.draw.rect(turret_surf, C_BARREL, (cx+5, gun_y_top, barrel_len, barrel_w))
        pygame.draw.rect(turret_surf, (50,50,50), (cx+5+barrel_len, gun_y_top-1, 6, 6))
        
        gun_y_bot = cy + 10 - barrel_w
        pygame.draw.rect(turret_surf, C_BARREL, (cx+5, gun_y_bot, barrel_len, barrel_w))
        pygame.draw.rect(turret_surf, (50,50,50), (cx+5+barrel_len, gun_y_bot-1, 6, 6))
        
        mis_len = 18
        mis_w = 4
        mis_y_top = cy - 20
        pygame.draw.rect(turret_surf, (50,60,50), (cx, mis_y_top, 10, 6))
        pygame.draw.rect(turret_surf, C_MISSILE, (cx-5, mis_y_top-2, mis_len, mis_w))
        pygame.draw.rect(turret_surf, C_MISSILE, (cx-5, mis_y_top+2, mis_len, mis_w))
        
        mis_y_bot = cy + 14
        pygame.draw.rect(turret_surf, (50,60,50), (cx, mis_y_bot, 10, 6))
        pygame.draw.rect(turret_surf, C_MISSILE, (cx-5, mis_y_bot+2, mis_len, mis_w))
        pygame.draw.rect(turret_surf, C_MISSILE, (cx-5, mis_y_bot+6, mis_len, mis_w))
        
        radar_w = 4
        radar_h = 18
        pygame.draw.rect(turret_surf, C_RADAR, (cx-20, cy-radar_h//2, radar_w, radar_h))
        pygame.draw.line(turret_surf, C_TURRET, (cx-14, cy), (cx-20, cy), 3)
        pygame.draw.circle(turret_surf, C_SENSOR, (cx+8, cy), 4)
        pygame.draw.circle(turret_surf, (100, 255, 255), (cx+9, cy-1), 2)
        
        # 保存防空APC图片
        filename = os.path.join(folder, f'apc_aa_{team}.png')
        pygame.image.save(s, filename)
        print(f"生成 {filename}")

# 生成Helicopter图片
def generate_helicopter():
    folder = os.path.join(sprite_dir, 'helicopter')
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    w, h = 80, 80
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, cy = w // 2, h // 2
    
    C_BODY_TOP = (220, 225, 230)
    C_BODY_BOT = (60, 65, 70)
    C_DETAIL = (100, 100, 105)
    C_CAMERA = (20, 20, 25)
    C_LENS = (0, 100, 50)
    C_SKIDS = (40, 40, 45)
    C_ROTOR = (30, 30, 30, 200)
    
    pygame.draw.line(surf, C_SKIDS, (cx-10, cy-12), (cx+15, cy-12), 3)
    pygame.draw.line(surf, C_SKIDS, (cx-5, cy-12), (cx, cy-5), 2)
    pygame.draw.line(surf, C_SKIDS, (cx+10, cy-12), (cx+10, cy-5), 2)
    pygame.draw.line(surf, C_SKIDS, (cx-10, cy+12), (cx+15, cy+12), 3)
    pygame.draw.line(surf, C_SKIDS, (cx-5, cy+12), (cx, cy+5), 2)
    pygame.draw.line(surf, C_SKIDS, (cx+10, cy+12), (cx+10, cy+5), 2)
    
    pygame.draw.rect(surf, C_BODY_TOP, (cx-35, cy-2, 40, 4))
    
    body_pts_top = [(cx+25, cy), (cx+15, cy-10), (cx-15, cy-10), (cx-25, cy)]
    pygame.draw.polygon(surf, C_BODY_TOP, body_pts_top)
    
    body_pts_bot = [(cx+25, cy), (cx+15, cy+8), (cx-15, cy+8), (cx-25, cy)]
    pygame.draw.polygon(surf, C_BODY_BOT, body_pts_bot)
    
    pygame.draw.rect(surf, C_DETAIL, (cx-5, cy-6, 10, 3))
    pygame.draw.rect(surf, C_DETAIL, (cx-5, cy+3, 10, 3))
    
    cam_x, cam_y = cx + 20, cy
    pygame.draw.circle(surf, C_BODY_BOT, (cam_x-2, cam_y), 5)
    pygame.draw.circle(surf, C_CAMERA, (cam_x+2, cam_y), 6)
    pygame.draw.circle(surf, C_LENS, (cam_x+4, cam_y), 2)
    
    tail_x = cx - 35
    pygame.draw.polygon(surf, C_BODY_BOT, [(tail_x, cy-2), (tail_x-5, cy-12), (tail_x+2, cy-2)])
    pygame.draw.polygon(surf, C_BODY_BOT, [(tail_x, cy+2), (tail_x-5, cy+12), (tail_x+2, cy+2)])
    
    tr_pos = (tail_x - 2, cy - 8)
    pygame.draw.circle(surf, (200, 200, 200, 100), tr_pos, 8)
    
    pygame.draw.circle(surf, (50, 50, 50), (cx, cy), 4)
    
    rotor_len = 35
    num_blades = 3
    for i in range(num_blades):
        ang = i * (360/num_blades)
        rad = math.radians(ang)
        ex = cx + math.cos(rad) * rotor_len
        ey = cy + math.sin(rad) * rotor_len
        pygame.draw.line(surf, C_ROTOR, (cx, cy), (ex, ey), 3)
        pygame.draw.circle(surf, (200, 200, 200, 150), (int(ex), int(ey)), 2)
    
    # 保存图片
    filename = os.path.join(folder, 'helicopter.png')
    pygame.image.save(surf, filename)
    print(f"生成 {filename}")

# 生成WZ10图片
def generate_wz10():
    folder = os.path.join(sprite_dir, 'wz10')
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    # 生成不同队伍的WZ10
    for team, color in TEAM_COLORS.items():
        if team in ["neutral", "enemy", "player"]:
            continue
        
        original_image = pygame.Surface((140, 140), pygame.SRCALPHA)
        
        C_BODY = (50, 60, 50)
        C_BODY_LIGHT = (70, 80, 70)
        C_GLASS = (20, 30, 40)
        C_WEAPON = (30, 30, 35)
        C_MISSILE = (60, 70, 60)
        C_ROTOR = (20, 20, 20)
        C_TEAM = color
        
        pygame.draw.rect(original_image, C_WEAPON, (60, 45, 20, 50))
        
        pygame.draw.rect(original_image, C_MISSILE, (65, 38, 15, 6))
        pygame.draw.circle(original_image, (40, 40, 40), (62, 41), 3)
        pygame.draw.rect(original_image, C_MISSILE, (65, 96, 15, 6))
        pygame.draw.circle(original_image, (40, 40, 40), (62, 99), 3)
        
        body_points = [(110, 72), (95, 60), (60, 55), (30, 65), (5, 65), (30, 75), (60, 85), (95, 80)]
        pygame.draw.polygon(original_image, C_BODY, body_points)
        pygame.draw.line(original_image, C_BODY_LIGHT, (110, 72), (30, 70), 2)
        
        pygame.draw.polygon(original_image, C_GLASS, [(105, 68), (95, 63), (95, 75), (105, 75)])
        pygame.draw.polygon(original_image, C_GLASS, [(92, 63), (80, 58), (80, 75), (92, 75)])
        
        pygame.draw.rect(original_image, C_BODY, (15, 60, 10, 20))
        pygame.draw.polygon(original_image, C_BODY_LIGHT, [(10, 70), (0, 60), (5, 80)])
        
        pygame.draw.rect(original_image, (40, 40, 45), (55, 60, 25, 8))
        pygame.draw.rect(original_image, (40, 40, 45), (55, 72, 25, 8))
        pygame.draw.circle(original_image, (10, 10, 10), (80, 64), 3)
        pygame.draw.circle(original_image, (10, 10, 10), (80, 76), 3)
        
        pygame.draw.rect(original_image, (20, 20, 20), (100, 70, 15, 2))
        pygame.draw.rect(original_image, C_TEAM, (35, 68, 10, 4))
        
        # 保存图片
        filename = os.path.join(folder, f'wz10_{team}.png')
        pygame.image.save(original_image, filename)
        print(f"生成 {filename}")

# 生成CruiseMissile图片
def generate_cruise_missile():
    folder = os.path.join(sprite_dir, 'cruise_missile')
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    original_image = pygame.Surface((80, 40), pygame.SRCALPHA)
    C_BODY = (200, 200, 210)
    C_BODY_DARK = (150, 150, 160)
    C_NOSE = (80, 80, 80)
    C_WING = (120, 120, 130)
    C_INTAKE = (40, 40, 40)
    C_STRIPE = (255, 50, 50)
    
    tail_x = 10
    pygame.draw.polygon(original_image, C_WING, [(tail_x, 20), (tail_x-8, 5), (tail_x+2, 5)])
    pygame.draw.polygon(original_image, C_WING, [(tail_x, 20), (tail_x-8, 35), (tail_x+2, 35)])
    
    body_rect = pygame.Rect(10, 15, 60, 10)
    pygame.draw.rect(original_image, C_BODY, body_rect)
    pygame.draw.rect(original_image, C_BODY_DARK, (10, 22, 60, 3))
    pygame.draw.ellipse(original_image, C_NOSE, (65, 15, 12, 10))
    
    wing_x = 40
    pygame.draw.polygon(original_image, C_WING, [(wing_x, 15), (wing_x-10, 2), (wing_x+5, 2), (wing_x+10, 15)])
    pygame.draw.polygon(original_image, C_WING, [(wing_x, 25), (wing_x-10, 38), (wing_x+5, 38), (wing_x+10, 25)])
    
    pygame.draw.rect(original_image, C_INTAKE, (25, 23, 10, 6))
    pygame.draw.rect(original_image, C_STRIPE, (58, 15, 3, 10))
    pygame.draw.line(original_image, (100, 100, 100), (35, 15), (35, 25), 1)
    pygame.draw.line(original_image, (100, 100, 100), (55, 15), (55, 25), 1)
    
    # 保存图片
    filename = os.path.join(folder, 'cruise_missile.png')
    pygame.image.save(original_image, filename)
    print(f"生成 {filename}")

# 生成ShipMissile图片
def generate_ship_missile():
    folder = os.path.join(sprite_dir, 'ship_missile')
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    w, h = 50, 24
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, cy = w//2, h//2
    
    C_BODY = (220, 225, 230)
    C_NOSE = (50, 50, 55)
    C_WING = (160, 165, 170)
    C_STRIPE = (200, 50, 50)
    C_INTAKE = (30, 30, 30)
    
    body_rect = pygame.Rect(5, 7, 40, 10)
    pygame.draw.rect(s, C_BODY, body_rect, border_radius=2)
    
    pygame.draw.circle(s, C_NOSE, (45, 12), 5)
    
    pygame.draw.polygon(s, C_WING, [(30, 7), (20, 0), (35, 0), (38, 7)])
    pygame.draw.polygon(s, C_WING, [(30, 17), (20, 24), (35, 24), (38, 17)])
    
    pygame.draw.polygon(s, C_WING, [(10, 7), (5, 2), (12, 2), (12, 7)])
    pygame.draw.polygon(s, C_WING, [(10, 17), (5, 22), (12, 22), (12, 17)])
    
    pygame.draw.rect(s, C_INTAKE, (25, 15, 8, 4))
    pygame.draw.rect(s, C_STRIPE, (38, 7, 2, 10))
    pygame.draw.line(s, (150,150,150), (20, 7), (20, 17), 1)
    
    # 保存图片
    filename = os.path.join(folder, 'ship_missile.png')
    pygame.image.save(s, filename)
    print(f"生成 {filename}")

# 生成Harvester图片
def generate_harvester():
    folder = os.path.join(sprite_dir, 'harvester')
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    # 生成不同队伍的采矿车
    for team, color in TEAM_COLORS.items():
        if team in ["neutral", "enemy", "player"]:
            continue
        
        surf_size = 60
        s = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        cx, cy = surf_size // 2, surf_size // 2
        
        C_BODY = (255, 200, 0)
        C_CABIN = (40, 40, 50)
        C_TREAD = (30, 30, 30)
        C_ORE = (0, 255, 255)
        C_DRILL = (150, 150, 150)
        
        body_len = 36
        body_wid = 24
        tread_w = 6
        
        pygame.draw.rect(s, C_TREAD, (cx - body_len/2, cy - body_wid/2 - tread_w/2, body_len, tread_w))
        pygame.draw.rect(s, C_TREAD, (cx - body_len/2, cy + body_wid/2 - tread_w/2, body_len, tread_w))
        
        for i in range(0, body_len, 4):
            x = cx - body_len/2 + i
            pygame.draw.line(s, (60,60,60), (x, cy - body_wid/2 - tread_w/2), (x, cy - body_wid/2 + tread_w/2), 1)
            pygame.draw.line(s, (60,60,60), (x, cy + body_wid/2 - tread_w/2), (x, cy + body_wid/2 + tread_w/2), 1)
        
        body_rect = pygame.Rect(cx - body_len/2, cy - body_wid/2, body_len, body_wid)
        pygame.draw.rect(s, C_BODY, body_rect, border_radius=3)
        
        pygame.draw.line(s, (0,0,0), (cx-body_len/4, cy-body_wid/2), (cx-body_len/4, cy+body_wid/2), 2)
        pygame.draw.line(s, (0,0,0), (cx+body_len/4, cy-body_wid/2), (cx+body_len/4, cy+body_wid/2), 2)
        
        cabin_rect = pygame.Rect(cx + body_len/4, cy - body_wid/2 + 2, 8, 10)
        pygame.draw.rect(s, C_CABIN, cabin_rect)
        pygame.draw.rect(s, (100, 200, 255), (cabin_rect.left+2, cabin_rect.top+2, 2, 6))
        
        ore_rect = pygame.Rect(cx - body_len/2 + 2, cy - body_wid/3, body_len*0.6, body_wid*0.6)
        pygame.draw.rect(s, (100, 100, 0), ore_rect)
        
        for _ in range(5):
            ox = cx - body_len/3 + (_ % 3) * 6
            oy = cy + (_ % 2) * 4 - 2
            pygame.draw.circle(s, C_ORE, (int(ox), int(oy)), 3)
            pygame.draw.circle(s, (255, 255, 255), (int(ox-1), int(oy-1)), 1)
        
        drill_len = 12
        drill_start = (cx + body_len/2, cy)
        drill_end = (cx + body_len/2 + drill_len, cy)
        
        pygame.draw.polygon(s, C_DRILL, [
            (drill_start[0], drill_start[1]-4),
            (drill_start[0], drill_start[1]+4),
            drill_end
        ])
        pygame.draw.line(s, (50,50,50), drill_start, drill_end, 1)
        
        # 保存图片
        filename = os.path.join(folder, f'harvester_{team}.png')
        pygame.image.save(s, filename)
        print(f"生成 {filename}")

# 生成AC130图片
def generate_ac130():
    folder = os.path.join(sprite_dir, 'ac130')
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    # 生成不同队伍的AC130
    for team, color in TEAM_COLORS.items():
        if team in ["neutral", "enemy", "player"]:
            continue
        
        original_image = pygame.Surface((200, 200), pygame.SRCALPHA)
        
        C_BODY_BASE = (90, 95, 100)
        C_BODY_SHADOW = (60, 65, 70)
        C_BODY_HILITE = (120, 125, 130)
        C_WING_SURF = (80, 85, 90)
        C_JET_INTAKE = (20, 20, 20)
        C_JET_METAL = color
        
        # 这里简化绘制，只绘制基本形状
        # 机身
        pygame.draw.rect(original_image, C_BODY_BASE, (50, 90, 100, 20))
        # 机翼
        pygame.draw.rect(original_image, C_WING_SURF, (20, 95, 40, 5))
        pygame.draw.rect(original_image, C_WING_SURF, (140, 95, 40, 5))
        # 尾翼
        pygame.draw.polygon(original_image, C_BODY_BASE, [(150, 80), (160, 90), (150, 100)])
        # 引擎
        pygame.draw.circle(original_image, C_JET_METAL, (80, 95), 10)
        pygame.draw.circle(original_image, C_JET_METAL, (120, 95), 10)
        pygame.draw.circle(original_image, C_JET_INTAKE, (80, 95), 5)
        pygame.draw.circle(original_image, C_JET_INTAKE, (120, 95), 5)
        
        # 保存图片
        filename = os.path.join(folder, f'ac130_{team}.png')
        pygame.image.save(original_image, filename)
        print(f"生成 {filename}")

# 主函数
if __name__ == "__main__":
    print("开始生成精灵图片...")
    generate_armored_car()
    generate_apc()
    generate_helicopter()
    generate_wz10()
    generate_cruise_missile()
    generate_ship_missile()
    generate_harvester()
    generate_ac130()
    print("精灵图片生成完成!")
    pygame.quit()
