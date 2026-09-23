import pygame
import random
import math
from core.settings import *
from core.base_classes import *
from .base import *

class MercenaryFactory(Entity):
    def __init__(self, game, pos):
        super().__init__(game, pos, "neutral")
        self.hp = 1500
        self.max_hp = 1500
        self.radius = 60
        self.rect = pygame.Rect(pos.x - 60, pos.y - 60, 120, 120)
        self.armor=15
        self.is_mechanical = True
        self.spawn_timer = 0
        self.capture_progress = 0
        self.capturing_team = None
        self.max_capture = OIL_CAPTURE_TIME

    def update(self):
        if self.team != "neutral":
            self.spawn_timer += 1
            if self.spawn_timer > MERC_FACTORY_INTERVAL:
                self.spawn_timer = 0
                spawn_pos = self.pos + vec(0, 70)
                self.game.all_units.append(ArmoredCar(self.game, spawn_pos, self.team))
                self.game.particles.add(FloatingText(self.pos, "+TANK", YELLOW))

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
            else: self.capture_progress = 0
        else: self.capture_progress = max(0, self.capture_progress - 0.5)

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
        w = scale(90, zoom)        
        l = scale(110, zoom)       
        h_visual = scale(35, zoom) 
        
        C_CONCRETE_TOP  = (110, 110, 115) 
        C_CONCRETE_SIDE = (70, 70, 75)    
        C_CONCRETE_BASE = (90, 90, 95)    
        C_DOOR_DARK     = (40, 40, 45)    
        C_DOOR_SLAT     = (60, 60, 65)    
        C_HAZARD        = (220, 180, 20)  
        C_VENT          = (50, 50, 55)    
        C_SHADOW        = (0, 0, 0, 90)   
        
        BLUE = (0, 150, 255)
        RED = (220, 60, 60)
        NEUTRAL = (120, 120, 120)
        
        team_color =TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])

        shadow_offset = scale(12, zoom)
        s_surf = pygame.Surface((l + shadow_offset*2, w + shadow_offset*2), pygame.SRCALPHA)
        pygame.draw.rect(s_surf, C_SHADOW, (shadow_offset, shadow_offset, l, w), border_radius=int(scale(5, zoom)))
        surface.blit(s_surf, (cx - l//2, cy - w//2))


        base_rect = pygame.Rect(cx - l//2 - scale(5, zoom), cy - w//2 - scale(5, zoom), 
                                l + scale(10, zoom), w + scale(10, zoom))
        
        pygame.draw.rect(surface, C_CONCRETE_BASE, base_rect)
        pygame.draw.rect(surface, (130, 130, 135), base_rect, 2)
        
        door_w = scale(50, zoom)
        door_h = scale(20, zoom)
        door_x = cx - door_w // 2
        door_y = cy + w // 2 - door_h 
        
        pygame.draw.rect(surface, (30, 30, 30), (door_x, door_y + scale(5, zoom), door_w, scale(15, zoom)))
        for i in range(0, int(door_w), int(scale(10, zoom))):
            p1 = (door_x + i, door_y + scale(5, zoom))
            p2 = (door_x + i + scale(5, zoom), door_y + scale(20, zoom))
            if p2[0] < door_x + door_w:
                pygame.draw.polygon(surface, C_HAZARD, [
                    p1, (p1[0]+scale(3, zoom), p1[1]), 
                    (p2[0]+scale(3, zoom), p2[1]), p2
                ])

        
        roof_y_center = cy - h_visual // 2 
        roof_rect = pygame.Rect(cx - l//2, roof_y_center - w//2, l, w)
        
        front_wall_rect = pygame.Rect(roof_rect.left, roof_rect.bottom, roof_rect.width, h_visual)
        pygame.draw.rect(surface, C_CONCRETE_SIDE, front_wall_rect)
        
        gate_rect = pygame.Rect(door_x, roof_rect.bottom, door_w, h_visual - scale(2, zoom))
        pygame.draw.rect(surface, C_DOOR_DARK, gate_rect)
        for i in range(0, int(gate_rect.height), int(scale(4, zoom))):
            pygame.draw.line(surface, C_DOOR_SLAT, (gate_rect.left, gate_rect.top + i), (gate_rect.right, gate_rect.top + i), 1)
        pygame.draw.rect(surface, (50, 50, 50), gate_rect, 2)
        
        pygame.draw.rect(surface, C_CONCRETE_TOP, roof_rect)
        pygame.draw.rect(surface, (150, 150, 160), roof_rect, 1) 

        
        stripe_w = scale(15, zoom)
        pygame.draw.rect(surface, team_color, (cx - l//2 + scale(15, zoom), roof_rect.top, stripe_w, roof_rect.height))
        
        current_time = time.time()
        fan_positions = [
            (cx + scale(20, zoom), roof_rect.centery - scale(15, zoom)),
            (cx + scale(20, zoom), roof_rect.centery + scale(15, zoom))
        ]
        
        fan_radius = scale(10, zoom)
        for fx, fy in fan_positions:
            pygame.draw.circle(surface, C_VENT, (int(fx), int(fy)), int(fan_radius))
            pygame.draw.circle(surface, (80, 80, 85), (int(fx), int(fy)), int(fan_radius), 1)
            angle_offset = current_time * 5
            for i in range(3):
                angle = angle_offset + i * (2 * math.pi / 3)
                end_x = fx + math.cos(angle) * fan_radius * 0.8
                end_y = fy + math.sin(angle) * fan_radius * 0.8
                pygame.draw.line(surface, (20, 20, 20), (fx, fy), (end_x, end_y), 2)
        
        for i in range(3):
            lx = cx - scale(10, zoom) + i * scale(10, zoom)
            pygame.draw.line(surface, (90, 90, 95), (lx, roof_rect.top + scale(5, zoom)), (lx, roof_rect.bottom - scale(5, zoom)), 2)


        if self.capture_progress > 0:
            bar_w = scale(50, zoom)
            bar_h = scale(6, zoom)
            pct = min(1.0, self.capture_progress / self.max_capture)
            
            if self.capturing_team == "player": bar_c = BLUE
            elif self.capturing_team == "enemy": bar_c = RED
            else: bar_c = (200, 200, 0)
            
            bar_x = cx - bar_w // 2
            bar_y = roof_rect.top - scale(20, zoom)
            
            pygame.draw.rect(surface, (0, 0, 0), (bar_x-1, bar_y-1, bar_w+2, bar_h+2)) 
            pygame.draw.rect(surface, (255, 255, 255), (bar_x, bar_y, bar_w, bar_h))   
            pygame.draw.rect(surface, bar_c, (bar_x, bar_y, bar_w * pct, bar_h))       

        self.draw_health_and_marker(surface, offset, zoom)


class BaseBuilding(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "base")
        self.hp = 5000 
        self.max_hp = 5000
        self.radius = 70 
        self.armor=30
        self.rect = pygame.Rect(pos.x - 70, pos.y - 70, 140, 140)
    def update(self):
        return super().update()    
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        faction = "CHINA" 
        if self.team == "player": faction = self.game.my_faction
        elif self.team == "enemy": faction = self.game.enemy_faction
        
        base_color = (100, 100, 100)
        if faction == "CHINA": base_color = (150, 60, 60) 
        elif faction == "USA": base_color = (60, 80, 150) 
        elif faction == "RUSSIA": base_color = (80, 100, 60) 
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
        base_w = scale(120, zoom)    
        bunker_w = scale(70, zoom)   
        core_w = scale(35, zoom)     
        
        h_base = scale(15, zoom)     
        h_bunker = scale(30, zoom)   
        
        C_CONCRETE_TOP = (100, 100, 105)
        C_CONCRETE_SIDE = (60, 60, 65)
        C_METAL_DARK = (40, 40, 45)
        C_SHADOW = (0, 0, 0, 100)
        

        team_color = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        
        shadow_offset = scale(15, zoom)
        s_surf = pygame.Surface((base_w + shadow_offset, base_w + shadow_offset), pygame.SRCALPHA)
        shadow_rect = pygame.Rect(shadow_offset, shadow_offset, base_w, base_w)
        pygame.draw.rect(s_surf, C_SHADOW, shadow_rect, border_radius=int(scale(10, zoom)))
        surface.blit(s_surf, (cx - base_w//2, cy - base_w//2))

        
        base_rect_bottom = pygame.Rect(cx - base_w//2, cy - base_w//2, base_w, base_w)
        base_top_y = cy - h_base
        
        pygame.draw.rect(surface, C_CONCRETE_SIDE, (cx - base_w//2, base_top_y - base_w//2, base_w, base_w + h_base))
        
        base_rect_top = pygame.Rect(cx - base_w//2, base_top_y - base_w//2, base_w, base_w)
        pygame.draw.rect(surface, C_CONCRETE_TOP, base_rect_top)
        
        pygame.draw.rect(surface, C_METAL_DARK, base_rect_top, width=int(scale(6, zoom)))
        corner_offset = scale(8, zoom)
        rivet_r = scale(3, zoom)
        corners = [
            (base_rect_top.left + corner_offset, base_rect_top.top + corner_offset),
            (base_rect_top.right - corner_offset, base_rect_top.top + corner_offset),
            (base_rect_top.left + corner_offset, base_rect_top.bottom - corner_offset),
            (base_rect_top.right - corner_offset, base_rect_top.bottom - corner_offset)
        ]
        for cp in corners:
            pygame.draw.circle(surface, (150, 150, 150), (int(cp[0]), int(cp[1])), int(rivet_r))

        
        bunker_top_y = base_top_y - h_bunker
        
        bunker_rect_side = pygame.Rect(cx - bunker_w//2, bunker_top_y - bunker_w//2, bunker_w, bunker_w + h_bunker)
        pygame.draw.rect(surface, (50, 55, 60), bunker_rect_side) 
        
        bunker_rect_top = pygame.Rect(cx - bunker_w//2, bunker_top_y - bunker_w//2, bunker_w, bunker_w)
        pygame.draw.rect(surface, (120, 125, 130), bunker_rect_top) 
        
        stripe_w = scale(8, zoom)
        pygame.draw.rect(surface, team_color, (bunker_rect_top.left + stripe_w, bunker_rect_top.top, stripe_w, bunker_w))
        pygame.draw.rect(surface, team_color, (bunker_rect_top.right - stripe_w*2, bunker_rect_top.top, stripe_w, bunker_w))

        
        core_y = bunker_top_y
        
        pygame.draw.rect(surface, (20, 20, 20), (cx - core_w//2, core_y - core_w//2, core_w, core_w))
        
        pulse = (math.sin(time.time() * 5) + 1) / 2  
        
        r, g, b = team_color
        bright_color = (min(255, r + 100*pulse), min(255, g + 100*pulse), min(255, b + 100*pulse))
        
        inner_core_w = core_w - scale(8, zoom)
        pygame.draw.rect(surface, bright_color, (cx - inner_core_w//2, core_y - inner_core_w//2, inner_core_w, inner_core_w))
        
        glow_size = scale(50, zoom)
        glow_surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
        glow_alpha = 50 + int(50 * pulse) 
        pygame.draw.circle(glow_surf, (r, g, b, glow_alpha), (glow_size//2, glow_size//2), glow_size//2)
        surface.blit(glow_surf, (cx - glow_size//2, core_y - glow_size//2))

        ant_x = bunker_rect_top.left + scale(4, zoom)
        ant_y = bunker_rect_top.top + scale(4, zoom)
        ant_h = scale(25, zoom)
        pygame.draw.line(surface, (200, 200, 200), (ant_x, ant_y), (ant_x, ant_y - ant_h), 2)
        if int(time.time() * 2) % 2 == 0:
            pygame.draw.circle(surface, (255, 0, 0), (int(ant_x), int(ant_y - ant_h)), 2)

        self.draw_health_and_marker(surface, offset, zoom, -scale(80, zoom))

    def undeploy(self):
        if self.game.is_online and self.game.my_role == "CLIENT":
            return

        from units import MCV
        new_mcv = MCV(self.game, self.pos, self.team)
        new_mcv.hp = self.hp
        
        
        self.game.all_units.append(new_mcv)
        
        self.alive = False 
        self.production_queue = []
        self.current_production = None


class FactoryBuilding(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "factory")
        self.hp = 800
        self.max_hp = 800
        self.armor=15
        self.radius = 15
        self.rect = pygame.Rect(pos.x - 60, pos.y - 60, 120, 120)
    def update(self):
        return super().update()


    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        margin = 200 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return              
        w = scale(100, zoom)       
        l = scale(80, zoom)        
        h_visual = scale(30, zoom) 
        
        C_WALL_DARK   = (70, 70, 75)     
        C_WALL_LIGHT  = (100, 100, 105)  
        C_ROOF_SLOPE  = (80, 80, 85)     
        C_ROOF_GLASS  = (40, 50, 60)     
        C_CHIMNEY     = (60, 40, 30)     
        C_ACCENT      = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        
        shadow_offset = scale(10, zoom)
        s_surf = pygame.Surface((w + shadow_offset*2, l + shadow_offset*2 + scale(50, zoom)), pygame.SRCALPHA)
        
        pygame.draw.rect(s_surf, (0,0,0,80), (shadow_offset, shadow_offset + scale(20, zoom), w, l))
        
        chimney_x_rel = scale(15, zoom) 
        chimney_shadow_h = scale(80, zoom) 
        pygame.draw.rect(s_surf, (0,0,0,60), (chimney_x_rel, shadow_offset, scale(15, zoom), chimney_shadow_h))
        
        surface.blit(s_surf, (cx - w//2, cy - l//2))

        base_y = cy + l//2
        roof_y = base_y - h_visual 
        
        rect_main = pygame.Rect(cx - w//2, roof_y, w, l) 
        
        pygame.draw.rect(surface, C_WALL_DARK, (cx - w//2, base_y - scale(5, zoom), w, scale(10, zoom)))
        
        
        num_teeth = 4
        tooth_w = w / num_teeth
        
        start_x = cx - w//2
        
        for i in range(num_teeth):
            t_x1 = start_x + i * tooth_w
            t_x2 = start_x + (i + 1) * tooth_w
            
            slope_w = tooth_w * 0.7
            glass_w = tooth_w * 0.3
            
            slope_rect = pygame.Rect(t_x1, roof_y - l//2, slope_w, l) 
            pygame.draw.rect(surface, C_ROOF_SLOPE, slope_rect)
            pygame.draw.rect(surface, (90, 90, 95), slope_rect, 1) 
            
            glass_rect = pygame.Rect(t_x1 + slope_w, roof_y - l//2, glass_w, l)
            pygame.draw.rect(surface, C_ROOF_GLASS, glass_rect)
            
            pygame.draw.line(surface, (60, 70, 80), (glass_rect.left, glass_rect.top + l*0.3), (glass_rect.right, glass_rect.top + l*0.3), 1)
            pygame.draw.line(surface, (60, 70, 80), (glass_rect.left, glass_rect.top + l*0.7), (glass_rect.right, glass_rect.top + l*0.7), 1)

        chim_w = scale(16, zoom)
        chim_h = scale(60, zoom)
        chim_x = cx - w//2 + scale(15, zoom)
        chim_base_y = cy  
        chim_top_y = chim_base_y - chim_h
        
        pygame.draw.rect(surface, C_CHIMNEY, (chim_x - chim_w//2, chim_top_y, chim_w, chim_h))
        for i in range(0, int(chim_h), int(scale(8, zoom))):
            pygame.draw.line(surface, (50, 30, 20), (chim_x - chim_w//2, chim_top_y + i), (chim_x + chim_w//2, chim_top_y + i), 1)
        
        pygame.draw.rect(surface, (40, 20, 10), (chim_x - chim_w//2 - 2, chim_top_y, chim_w + 4, scale(6, zoom)))
        pygame.draw.rect(surface, (10, 10, 10), (chim_x - chim_w//2 + 2, chim_top_y + 1, chim_w - 4, scale(3, zoom)))
        
        current_time = time.time()
        for i in range(4):
            t_offset = i * 1.5 
            cycle = (current_time + t_offset) % 4
            
            dy = cycle * scale(30, zoom) 
            dx = math.sin(current_time * 2 + i) * scale(8, zoom) + (cycle * scale(10, zoom)) 
            
            radius = scale(6 + cycle * 3, zoom)
            alpha = max(0, 150 - cycle * 40)
            
            particle_pos = (int(chim_x + dx), int(chim_top_y - dy - scale(5, zoom)))
            s_smoke = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
            pygame.draw.circle(s_smoke, (30, 30, 30, int(alpha)), (radius, radius), radius)
            surface.blit(s_smoke, (particle_pos[0]-radius, particle_pos[1]-radius))


        door_w = scale(40, zoom)
        door_h = scale(15, zoom)
        door_rect = pygame.Rect(cx - door_w//2, base_y - door_h, door_w, door_h)
        
        pygame.draw.rect(surface, C_ACCENT, (door_rect.left - 2, door_rect.top - 2, door_rect.width + 4, door_rect.height + 4))
        pygame.draw.rect(surface, (30, 30, 35), door_rect)
        for i in range(0, int(door_h), int(scale(3, zoom))):
            pygame.draw.line(surface, (50, 50, 55), (door_rect.left, door_rect.top + i), (door_rect.right, door_rect.top + i), 1)



        self.draw_health_and_marker(surface, offset, zoom, -65)


class RadarBuilding(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "radar")
        self.hp = 500
        self.max_hp = 500
        self.armor=5
        self.radius = 40
        self.rect = pygame.Rect(pos.x - 40, pos.y - 40, 80, 80)
        self.angle = 0

    def update(self):
        self.angle += 1.5


    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        margin = 300 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return              
        truck_len = scale(80, zoom)
        truck_wid = scale(35, zoom)
        
        radar_w = scale(60, zoom) 
        radar_h = scale(10, zoom) 
        
        C_CHASSIS = (55, 65, 50)    
        C_CABIN = (70, 80, 65)      
        C_RADAR_FACE = (40, 50, 40) 
        C_RADAR_BACK = (60, 70, 55) 
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

        leg_len = scale(12, zoom)
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

        rotated_radar = pygame.transform.rotate(r_surf, -self.angle)
        radar_rect = rotated_radar.get_rect(center=screen_pos)
        
        shadow_surf = pygame.transform.rotate(r_surf, -self.angle)
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
            
            scan_rot = pygame.transform.rotate(scan_s, -self.angle)
            scan_rect = scan_rot.get_rect(center=screen_pos)
            surface.blit(scan_rot, scan_rect)

        self.draw_health_and_marker(surface, offset, zoom, -scale(60, zoom))


class PowerPlant(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team,"power_plant")
        self.b_type = "power_plant"
        self.hp = POWER_PLANT_HP
        self.max_hp = POWER_PLANT_HP
        self.armor=5
        self.radius = 35
        self.rect = pygame.Rect(pos.x - 35, pos.y - 35, 70, 70)
        self.power_usage = 0 
        
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
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

        self.draw_health_and_marker(surface, offset, zoom)


class MiningRig(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "mining")
        self.hp = 600
        self.max_hp = 600
        self.radius = 50
        self.armor=15
        self.rect = pygame.Rect(pos.x - 50, pos.y - 50, 100, 100)
        self.spawn_timer = 0
        self.harvester_count = 0
        self.max_harvesters = 2
        self.harvesters = [] 

    def update(self):

        self.harvesters = [h for h in self.harvesters if h.alive]

        if len(self.harvesters) < self.max_harvesters:
            self.spawn_timer += 1
            if self.spawn_timer > 600:
                self.spawn_timer = 0
                self.spawn_harvester()
        else:
            self.spawn_timer = 0 

    def spawn_harvester(self):
        spawn_pos = self.pos + vec(0, 50)
        harvester = Harvester(self.game, spawn_pos, self.team, self)
        self.game.all_units.append(harvester)
        self.harvesters.append(harvester) 
        self.game.particles.add(FloatingText(self.pos, "New Harvester", GREEN_HAT))

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = screen_pos
        
        w = scale(100, zoom)
        h = scale(80, zoom)
        
        C_CONCRETE = (100, 100, 105) 
        C_METAL    = (80, 75, 70)    
        C_RUST     = (120, 80, 60)   
        C_PIPE     = (60, 60, 65)    
        C_GLOW     = (255, 150, 50)  
        C_ROOF     = (50, 50, 55)    
        plat_w = w * 0.5
        plat_h = h * 0.6
        plat_rect = pygame.Rect(cx - w/2, cy - plat_h/2 + h*0.2, plat_w, plat_h)
        
        pygame.draw.rect(surface, C_CONCRETE, plat_rect)
        pygame.draw.rect(surface, (50,50,50), plat_rect, 2) 

        ramp_x = plat_rect.left
        ramp_y = plat_rect.bottom
        pygame.draw.polygon(surface, (80, 80, 85), [
            (ramp_x, ramp_y), 
            (ramp_x + plat_w, ramp_y), 
            (ramp_x + plat_w, ramp_y + scale(15, zoom)), 
            (ramp_x, ramp_y + scale(15, zoom))
        ])
        for i in range(3):
            ly = ramp_y + i * scale(5, zoom)
            pygame.draw.line(surface, (60,60,60), (ramp_x, ly), (ramp_x+plat_w, ly), 1)

        hopper_rect = pygame.Rect(plat_rect.centerx - scale(15, zoom), plat_rect.centery - scale(10, zoom), scale(30, zoom), scale(20, zoom))
        pygame.draw.rect(surface, (20, 20, 25), hopper_rect) 
        pygame.draw.rect(surface, (200, 180, 50), hopper_rect.inflate(-4, -4), 1) 

        tower_w = w * 0.4
        tower_h = h * 0.8
        tower_rect = pygame.Rect(cx + scale(5, zoom), cy - h/2, tower_w, tower_h)
        
        pygame.draw.rect(surface, C_METAL, tower_rect)
        pygame.draw.rect(surface, (40,40,40), tower_rect, 2)
        
        pygame.draw.rect(surface, C_RUST, (tower_rect.left, tower_rect.top + scale(20, zoom), tower_w, scale(10, zoom)))
        
        glow_alpha = int(150 + 100 * math.sin(pygame.time.get_ticks() * 0.005))
        glow_surf = pygame.Surface((int(tower_w*0.6), int(scale(15, zoom))), pygame.SRCALPHA)
        glow_surf.fill((*C_GLOW, glow_alpha))
        surface.blit(glow_surf, (tower_rect.centerx - tower_w*0.3, tower_rect.centery))
        
        for i in range(3):
            lx = tower_rect.centerx - tower_w*0.3 + i * scale(10, zoom)
            pygame.draw.line(surface, (30,30,30), (lx, tower_rect.centery), (lx, tower_rect.centery + scale(15, zoom)), 2)

        pipe_start = (plat_rect.right, plat_rect.centery)
        pipe_end = (tower_rect.left, tower_rect.centery)
        pygame.draw.line(surface, C_PIPE, pipe_start, pipe_end, int(scale(8, zoom)))
        pygame.draw.line(surface, (100,100,100), pipe_start, pipe_end, int(scale(2, zoom))) 

        chimney_w = scale(12, zoom)
        chimney_h = scale(25, zoom)
        chimney_rect = pygame.Rect(tower_rect.centerx - chimney_w/2, tower_rect.top - chimney_h, chimney_w, chimney_h)
        pygame.draw.rect(surface, (40, 40, 45), chimney_rect)
        pygame.draw.ellipse(surface, (20, 20, 20), (chimney_rect.left, chimney_rect.top-scale(3, zoom), chimney_w, scale(6, zoom))) 
        
        t = pygame.time.get_ticks()
        for i in range(3):
            offset_y = (t * 0.05 + i * 20) % 60
            alpha = max(0, 255 - offset_y * 4)
            smoke_r = scale(5 + offset_y * 0.2, zoom)
            
            offset_x = math.sin(offset_y * 0.1) * scale(10, zoom)
            
            s_smoke = pygame.Surface((int(smoke_r*2), int(smoke_r*2)), pygame.SRCALPHA)
            pygame.draw.circle(s_smoke, (100, 100, 100, int(alpha)), (int(smoke_r), int(smoke_r)), int(smoke_r))
            surface.blit(s_smoke, (chimney_rect.centerx + offset_x - smoke_r, chimney_rect.top - scale(offset_y, zoom) - smoke_r))

        lamp_color = (255, 50, 50) if (t // 500) % 2 == 0 else (100, 30, 30)
        pygame.draw.circle(surface, lamp_color, (tower_rect.right - scale(5, zoom), tower_rect.top + scale(5, zoom)), scale(3, zoom))

        self.draw_health_and_marker(surface, offset, zoom, y_offset=-scale(50, zoom))


class Airfield(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "airfield")
        self.hp = 700
        self.max_hp = 700
        self.armor=5
        self.radius = 60
        self.rect = pygame.Rect(pos.x - 60, pos.y - 60, 120, 120)
        self.is_upgraded = False
    def update(self):
        return super().update() 



    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
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
        C_RADAR         = (200, 200, 210)
        
        if self.is_upgraded:
            C_RADAR = (255, 215, 0) 
            C_TOWER_TRIM = (255, 100, 50) 
        else:
            C_TOWER_TRIM = (0, 100, 200) 
            
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
        pygame.draw.line(surface, C_TOWER_TRIM, (tx, ty_base - t_h), (tx, ty_base), 2)
        
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
            
            corners = [
                (cx - runway_w//2, runway_y),
                (cx + runway_w//2, runway_y),
                (cx - runway_w//2, runway_y + runway_h),
                (cx + runway_w//2, runway_y + runway_h)
            ]
            for cp in corners:
                pygame.draw.circle(surface, (0, 255, 0), (int(cp[0]), int(cp[1])), 2) 


        self.draw_health_and_marker(surface, offset, zoom, -scale(85, zoom))


class ResearchCenter(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "research")
        self.hp = 600
        self.max_hp = 600
        self.armor=5
        self.radius = 45
        self.rect = pygame.Rect(pos.x - 45, pos.y - 45, 90, 90)

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = int(screen_pos[0]), int(screen_pos[1])
        
        w = scale(90, zoom)       
        h_base = scale(20, zoom)  
        core_h = scale(50, zoom)  
        
        C_BASE_DARK   = (40, 40, 45)    
        C_BASE_LIGHT  = (70, 75, 80)    
        C_ENERGY_CORE = (0, 180, 255)   
        C_ENERGY_GLOW = (100, 220, 255) 
        C_RING_METAL  = (150, 150, 160) 
        C_HOLO_BEAM   = (0, 200, 255, 30) 
        
        team_color = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
        
        t = time.time()
        
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
        
        flow_offset = (t * 20) % plat_rect.width
        for i in range(-1, 2):
            pos_x = plat_rect.left + (flow_offset + i*30) % plat_rect.width
            pygame.draw.rect(surface, team_color, (pos_x, plat_rect.centery - 1, 4, 2))
            
            pos_y = plat_rect.top + (flow_offset + i*30) % plat_rect.height
            pygame.draw.rect(surface, team_color, (plat_rect.centerx - 1, pos_y, 2, 4))


        gen_w = scale(30, zoom)
        gen_h = scale(15, zoom)
        gen_y = plat_rect.centery
        
        gen_rect = pygame.Rect(cx - gen_w//2, gen_y - gen_h, gen_w, gen_h)
        pygame.draw.rect(surface, (50, 50, 55), gen_rect)
        pylon_h = scale(35, zoom)
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
        
        angle2 = t * 2.0 + 1.0
        rx2 = math.cos(angle2) * scale(20, zoom)
        ry2 = math.sin(angle2) * scale(20, zoom) 
        
        
        sat_r = scale(3, zoom)
        pygame.draw.circle(surface, C_RING_METAL, (int(cx + rx1), int(core_center_y + ry1)), int(sat_r))
        pygame.draw.circle(surface, C_RING_METAL, (int(cx - rx1), int(core_center_y - ry1)), int(sat_r))
        
        points = []
        for i in range(360):
            rad = math.radians(i)
            px = cx + math.cos(rad) * scale(22, zoom) * math.cos(t) 
            py = core_center_y + math.sin(rad) * scale(22, zoom)
            if i % 10 == 0: 
                pass


        beam_h = scale(80, zoom)
        beam_w = scale(10, zoom)
        
        beam_surf = pygame.Surface((beam_w, beam_h), pygame.SRCALPHA)
        
        for i in range(int(beam_h)):
            alpha = int(100 * (1 - i/beam_h)) 
            pygame.draw.line(beam_surf, (*team_color, alpha), (0, i), (beam_w, i))
            
        beam_surf = pygame.transform.flip(beam_surf, False, True)
        surface.blit(beam_surf, (cx - beam_w//2, core_center_y - beam_h))


        if int(t * 10) % 3 == 0:
            data_y = core_center_y - random.randint(10, int(scale(60, zoom)))
            data_x = cx + random.randint(-5, 5)
            pygame.draw.rect(surface, (200, 255, 255), (data_x, data_y, 2, 2))


        self.draw_health_and_marker(surface, offset, zoom, -scale(90, zoom))


class ShroudGen(Building):
    def __init__(self, game, pos, team):
        super().__init__(game, pos, team, "shroud_gen")
        self.hp = 1000
        self.max_hp = 1000
        self.radius = 40
        self.rect = pygame.Rect(pos.x-40, pos.y-40, 80, 80)
        self.power_usage = 300 
        
        self.image = self.generate_image()

    def generate_image(self):
        s = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(s, (20, 20, 20), (40, 40), 30)
        pygame.draw.circle(s, (50, 0, 50), (40, 40), 10) 
        for i in range(4):
            angle = i * 90
            end_x = 40 + math.cos(math.radians(angle)) * 35
            end_y = 40 + math.sin(math.radians(angle)) * 35
            pygame.draw.line(s, (100, 100, 100), (40, 40), (end_x, end_y), 3)
        return s

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        t = pygame.time.get_ticks()
        scale_p = 1.0 + math.sin(t * 0.005) * 0.1
        
        scaled_img = scale_img(self.image, zoom * scale_p)
        rect = scaled_img.get_rect(center=screen_pos)
        surface.blit(scaled_img, rect)
        
        self.draw_health_and_marker(surface, offset, zoom, -40)


class PrototypeGen(Building):
    def __init__(self, game, pos, team="neutral"):
        super().__init__(game, pos, team, "prototype_gen")
        self.b_type = "prototype_gen"
        self.hp = 2000
        self.max_hp = 2000
        self.armor=30
        self.radius = 70 
        self.rect = pygame.Rect(pos.x - 70, pos.y - 70, 140, 140)
        
        self.loaded_weapon = None 
        self.weapon_obj = None 
        
        self.image = self.generate_image()
        self.is_ready = False
        self.charge_timer = 0
        self.charge_time_total = 0 

    def update(self):
        super().update()
        
        if self.loaded_weapon and not self.is_ready:
            self.charge_timer += 1
            if self.charge_timer >= self.charge_time_total:
                self.is_ready = True
                self.charge_timer = self.charge_time_total
                self.game.particles.add(FloatingText(self.pos, "WEAPON READY", RED))

        if self.weapon_obj:
            self.weapon_obj.update()
            if not self.weapon_obj.alive:
                self.weapon_obj = None
                self.loaded_weapon = None
                self.is_ready = False 

    def build_prototype(self, p_type):
        if self.loaded_weapon: return 
        
        self.loaded_weapon = p_type
        self.is_ready = False
        self.charge_timer = 0
        
        if p_type == "iron_curtain":
            self.charge_time_total = 5400
            self.weapon_obj = IronCurtain(self.game, self.pos, self.team, self)
        elif p_type == "nuke_silo":
            self.charge_time_total = 3600 
            self.weapon_obj = NukeSilo(self.game, self.pos, self.team, self)
    def generate_image(self):
        w, h = 160, 160
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        
        C_BASE_DARK  = (40, 45, 50)
        C_BASE_LIGHT = (70, 75, 80)
        C_PLATFORM   = (30, 30, 35)
        C_ACCENT     = TEAM_COLORS.get(self.team, (0, 200, 255))
        C_DETAIL     = (100, 110, 120)
        
        base_w = 100
        base_h = 80
        base_rect = pygame.Rect(cx - base_w//2, cy - base_h//2 + 20, base_w, base_h)
        
        pygame.draw.rect(s, (0,0,0,80), base_rect.inflate(10, 10), border_radius=15)
        
        pygame.draw.rect(s, C_BASE_DARK, base_rect, border_radius=10)
        top_rect = base_rect.inflate(-10, -10)
        pygame.draw.rect(s, C_BASE_LIGHT, top_rect, border_radius=5)
        
        for i in range(3):
            lx = base_rect.left - 5
            ly = base_rect.top + 15 + i * 15
            pygame.draw.rect(s, (20,20,20), (lx, ly, 10, 8)) 
            
            rx = base_rect.right - 5
            ry = base_rect.top + 15 + i * 15
            pygame.draw.rect(s, (20,20,20), (rx, ry, 10, 8)) 

        plat_r = 35
        pygame.draw.circle(s, C_DETAIL, (cx, cy+10), plat_r)
        pygame.draw.circle(s, C_PLATFORM, (cx, cy+10), plat_r - 5)
        
        for i in range(3):
            angle = i * (360/3) - 90
            rad = math.radians(angle)
            ex = cx + math.cos(rad) * (plat_r + 5)
            ey = cy + 10 + math.sin(rad) * (plat_r + 5)
            pygame.draw.line(s, C_DETAIL, (cx, cy+10), (ex, ey), 4)
            pygame.draw.circle(s, (20,20,20), (int(ex), int(ey)), 4)

        pygame.draw.circle(s, (0, 100, 100), (cx, cy+10), 10)
        
        ant_base_x = cx + 40
        ant_base_y = cy - 30
        
        pygame.draw.rect(s, C_BASE_DARK, (ant_base_x-10, ant_base_y, 20, 20))
        
        pygame.draw.line(s, C_DETAIL, (ant_base_x, ant_base_y), (ant_base_x, ant_base_y - 50), 3)
        dish_pos = (ant_base_x, ant_base_y - 50)
        pygame.draw.arc(s, C_DETAIL, (dish_pos[0]-10, dish_pos[1]-10, 20, 20), 0.5, 2.6, 2)
        pygame.draw.line(s, C_DETAIL, dish_pos, (dish_pos[0]-8, dish_pos[1]-8), 1)
        
        pygame.draw.circle(s, (100, 0, 0), (ant_base_x, ant_base_y - 55), 2)

        pygame.draw.rect(s, C_ACCENT, (cx - 40, cy + 40, 80, 4))

        return s

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled = scale_img(self.image, zoom)
        rect = scaled.get_rect(center=screen_pos)
        surface.blit(scaled, rect)
        
        if not self.weapon_obj:
            alpha = int(100 + 50 * math.sin(pygame.time.get_ticks() * 0.005))
            glow_r = int(scale(10, zoom))
            glow_pos = (screen_pos[0], screen_pos[1] + 10*zoom)
            
            s = pygame.Surface((glow_r*2, glow_r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (0, 255, 255, alpha), (glow_r, glow_r), glow_r)
            surface.blit(s, (glow_pos[0]-glow_r, glow_pos[1]-glow_r), special_flags=pygame.BLEND_ADD)
            
        ant_pos = (screen_pos[0] + 40*zoom, screen_pos[1] - 55*zoom)
        if (pygame.time.get_ticks() // 500) % 2 == 0:
            pygame.draw.circle(surface, (255, 0, 0), ant_pos, int(3*zoom))

        if self.weapon_obj:
            
            self.weapon_obj.draw(surface, offset, zoom)
            
        self.draw_health_and_marker(surface, offset, zoom, y_offset=-60*zoom)


class IronCurtain(Building):
    def __init__(self, game, pos, team, parent):
        super().__init__(game, pos, team, "iron_curtain")
        self.parent = parent
        self.radius = 40
        self.hp = 1000 
        
        self.cooldown = 0
        self.max_cooldown = 0
        self.is_aiming = False
        
        self.image = self.generate_image()

    def generate_image(self):
        s = pygame.Surface((80, 80), pygame.SRCALPHA)
        cx, cy = 40, 40
        pygame.draw.circle(s, (100, 0, 0), (cx, cy), 25)
        pygame.draw.circle(s, (255, 50, 50), (cx, cy), 15) 
        pygame.draw.arc(s, (200, 200, 200), (cx-30, cy-30, 60, 60), 0, 3.14, 2)
        return s

    def toggle_mode(self):
        self.is_aiming = not self.is_aiming
        if self.is_aiming:
            self.game.particles.add(FloatingText(self.pos, "IRON CURTAIN READY", RED))
            if hasattr(self.game, 'net_events'):
                self.game.net_events.append({
                    "type": "FX_TEXT", 
                    "x": int(self.pos.x), "y": int(self.pos.y),
                    "text": "IRON CURTAIN READY",
                    "color": "RED" 
                })
            self.game.place_building_type = "skill_iron_curtain" 
        else:
            self.game.place_building_type = None

    def activate(self, target_pos):
        radius = 150
        amount = 1000 
        for u in self.game.all_units:
            if u.alive  and u.pos.distance_to(target_pos) < radius:
                if u.is_mechanical or u.is_air:
                    u.shield = amount
                    u.max_shield = amount
                    self.game.particles.add(FloatingText(u.pos, "+SHIELD", RED))
                    if hasattr(self.game, 'net_events'):
                        self.game.net_events.append({
                            "type": "FX_TEXT", 
                            "x": int(u.pos.x), "y": int(u.pos.y),
                            "text": "+SHIELD",
                            "color": "RED" 
                        })
                else:
                    p = Projectile(self.game, u.pos, None, "neutral", 300,"heavy_shell", is_aoe=True, aoe_radius=50,breakshellvalue=0)
                    p.on_hit(None)
        self.alive = False 
        self.is_aiming = False
        self.game.place_building_type = None
    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled = scale_img(self.image, zoom)
        rect = scaled.get_rect(center=screen_pos)
        surface.blit(scaled, rect)
        
        is_ready = False
        if self.parent:
            is_ready = getattr(self.parent, 'is_ready', False)
        else:
            pass

        if is_ready or self.is_aiming:
            import random
            
            if self.game.frame_count%15==0:
                num_bolts = random.randint(0, 4)
                radius = 35 * zoom 
                
                for _ in range(num_bolts):
                    angle = random.uniform(0, 6.28)
                    start_x = screen_pos[0] + math.cos(angle) * (radius * 0.3)
                    start_y = screen_pos[1] + math.sin(angle) * (radius * 0.3)
                    
                    points = [(start_x, start_y)]
                    segments = 3
                    curr_x, curr_y = start_x, start_y
                    
                    for i in range(segments):
                        dist = (radius * 0.7) / segments
                        curr_x += math.cos(angle) * dist + random.uniform(-5, 5)
                        curr_y += math.sin(angle) * dist + random.uniform(-5, 5)
                        points.append((curr_x, curr_y))
                    
                    if len(points) > 1:
                        pygame.draw.lines(surface, (255, 0, 0), False, points, 3)
                        pygame.draw.lines(surface, (255, 200, 200), False, points, 1)


class NukeSilo(Building):
    def __init__(self, game, pos, team, parent):
        super().__init__(game, pos, team, "nuke_silo")
        self.parent = parent
        self.is_aiming = False
        self.image = self.generate_image()



    def toggle_mode(self):
        self.is_aiming = not self.is_aiming
        if self.is_aiming:
            self.game.particles.add(FloatingText(self.pos, "ROCKET READY", ORANGE))
            if hasattr(self.game, 'net_events'):
                self.game.net_events.append({
                    "type": "FX_TEXT", 
                    "x": int(self.pos.x), "y": int(self.pos.y),
                    "text": "ROCKET READY",
                    "color": "ORANGE" 
                })
            self.game.place_building_type = "skill_nuke"
        else:
            self.game.place_building_type = None

    def activate(self, target_pos):
        missile = MegaRocket(self.game, self.pos, self.team,target_pos=target_pos)
        self.game.all_units.append(missile)

        self.alive = False
        self.is_aiming = False
        self.game.place_building_type = None
    def generate_image(self):
        w, h = 160, 100
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        
        C_BASE = (40, 40, 45)     
        C_ROCKET = (220, 220, 230)
        C_WARHEAD = (200, 50, 50) 
        C_DETAIL = (150, 150, 160)
        
        rect_base = pygame.Rect(10, 20, 140, 60)
        pygame.draw.rect(s, C_BASE, rect_base, border_radius=5)
        pygame.draw.line(s, (20,20,20), (20, 40), (140, 40), 4) 
        pygame.draw.line(s, (20,20,20), (20, 60), (140, 60), 4) 
        
        rocket_x = 30
        rocket_y = 35
        rocket_len = 100
        rocket_wid = 30
        
        r_rect = pygame.Rect(rocket_x, rocket_y, rocket_len, rocket_wid)
        pygame.draw.rect(s, C_ROCKET, r_rect, border_radius=5)
        
        head_pts = [
            (rocket_x + rocket_len, rocket_y),              
            (rocket_x + rocket_len, rocket_y + rocket_wid), 
            (rocket_x + rocket_len + 20, rocket_y + rocket_wid/2) 
        ]
        pygame.draw.polygon(s, C_WARHEAD, head_pts)
        
        pygame.draw.polygon(s, C_DETAIL, [(rocket_x+10, rocket_y), (rocket_x, rocket_y-10), (rocket_x+25, rocket_y)])
        pygame.draw.polygon(s, C_DETAIL, [(rocket_x+10, rocket_y+30), (rocket_x, rocket_y+40), (rocket_x+25, rocket_y+30)])
        
        pygame.draw.rect(s, (50,50,50), (rocket_x + 60, rocket_y, 5, 30))
        pygame.draw.rect(s, (200, 200, 0), (rocket_x + 40, rocket_y + 10, 10, 10)) 

        for i in range(3):
            x = rocket_x + 20 + i * 30
            pygame.draw.rect(s, (60,60,60), (x, 20, 8, 15))
            pygame.draw.rect(s, (60,60,60), (x, 65, 8, 15))

        return s

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        
        scaled = scale_img(self.image, zoom)
        rect = scaled.get_rect(center=screen_pos)
        surface.blit(scaled, rect)
        
        is_ready = False
        if self.parent:
            is_ready = getattr(self.parent, 'is_ready', False)
            
        if is_ready:
            import math
            alpha = int(100 + 100 * math.sin(pygame.time.get_ticks() * 0.01))
            
            warhead_offset = vec(50 * zoom, 0) 
            warhead_pos = (screen_pos[0] + warhead_offset.x, screen_pos[1] + warhead_offset.y)
            
            s = pygame.Surface((100, 100), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 50, 50, alpha), (50, 50), int(20*zoom))
            surface.blit(s, (warhead_pos[0]-50, warhead_pos[1]-50), special_flags=pygame.BLEND_ADD)


class Lighthouse(Building):
    def __init__(self, game, pos):
        super().__init__(game, pos, "neutral", "lighthouse")
        self.hp = 1000
        self.max_hp = 1000
        self.radius = 40
        self.rect = pygame.Rect(pos.x-40, pos.y-40, 80, 80)
        self.image = self.generate_image()

        self.is_collapsed = False
        self.garrison = []
        self.capacity = 4
        self.attack_cooldown = 0
        self.can_garrison = True 
    def update(self):
        super().update()
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        
        if self.garrison:
            self.team = self.garrison[0].team
            
            if not self.game.is_online or self.game.my_role == "HOST":
                if self.attack_cooldown <= 0:
                    target = self.find_nearest_enemy() 
                    if target and self.pos.distance_to(target.pos)<600:
                        self.fire_barrage(target) 
        if not self.is_collapsed and self.hp <= 0:
            self.start_collapse()
    def find_nearest_enemy(self):
        nearest = None
        min_dist = 99999
        enemies = [u for u in self.game.all_units if u.team != self.team ]
        for e in enemies:

            if getattr(e, 'is_stealth', False):
                if self.pos.distance_to(e.pos) > 50: 
                    continue  
            dist = self.pos.distance_to(e.pos)
            if dist < min_dist: min_dist = dist; nearest = e
        return nearest

    def fire_barrage(self, target):
        for _ in range(len(self.garrison)):
            offset = vec(random.randint(-20,20), random.randint(-20,20))
            p = Projectile(self.game, self.pos+offset, target, self.team, 15, "heavy")
            self.game.projectiles.append(p)
        
        self.attack_cooldown = 30 

    def enter_unit(self, unit):
        from units import Rifleman
        if not isinstance(unit, Rifleman):
            return False
        if len(self.garrison) < self.capacity :
            self.garrison.append(unit)
            self.game.all_units.remove(unit) 
            return True
        return False
    def start_collapse(self):
        self.is_collapsed = True
        self.hp = 0
        self.alive = False 
        if hasattr(self.game, 'particles'):
            for _ in range(5):
                Particle(self.game.particles, self.pos, (100, 90, 80), 1, 30, 10)
    def generate_image(self):
        w, h = 160, 160
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        
        C_CONCRETE = (90, 95, 100)
        C_DARK     = (60, 65, 70)
        C_LIGHT    = (120, 125, 130)
        C_METAL    = (50, 50, 55)
        C_GLASS    = (200, 255, 255) 
        C_WARNING  = (200, 180, 50)  
        
        base_r_out = 70
        pts_out = []
        for i in range(8):
            ang = math.radians(i * 45 + 22.5)
            pts_out.append((cx + math.cos(ang)*base_r_out, cy + math.sin(ang)*base_r_out))
        pygame.draw.polygon(s, C_DARK, pts_out)
        
        base_r_in = 55
        pts_in = []
        for i in range(8):
            ang = math.radians(i * 45 + 22.5)
            pts_in.append((cx + math.cos(ang)*base_r_in, cy + math.sin(ang)*base_r_in))
        pygame.draw.polygon(s, C_CONCRETE, pts_in)
        
        for i in range(8):
            pygame.draw.line(s, C_DARK, pts_out[i], pts_in[i], 2)
            
        for i in range(0, 8, 2): 
            p1 = pts_in[i]
            p2 = pts_in[(i+1)%8]
            mid = ((p1[0]+p2[0])/2, (p1[1]+p2[1])/2)
            pygame.draw.circle(s, (20,20,20), (int(mid[0]), int(mid[1])), 6)
            pygame.draw.rect(s, (40,40,40), (mid[0]-4, mid[1]-4, 8, 8))

        tower_r = 30
        pygame.draw.circle(s, C_DARK, (cx, cy), tower_r)
        pygame.draw.rect(s, C_METAL, (cx-8, cy+tower_r, 16, 10))

        plat_r = 35
        pygame.draw.circle(s, C_CONCRETE, (cx, cy), plat_r)
        pygame.draw.circle(s, C_METAL, (cx, cy), plat_r, 2)
        pygame.draw.circle(s, C_WARNING, (cx, cy), plat_r-4, 3)

        lantern_r = 20
        pygame.draw.circle(s, C_GLASS, (cx, cy), lantern_r)
        for i in range(4):
            ang = math.radians(i * 45)
            end_x = cx + math.cos(ang) * lantern_r
            end_y = cy + math.sin(ang) * lantern_r
            pygame.draw.line(s, C_METAL, (cx, cy), (end_x, end_y), 2)
            
        pygame.draw.circle(s, C_METAL, (cx, cy), 12)
        pygame.draw.circle(s, C_LIGHT, (cx, cy), 8) 

        return s

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        cx, cy = screen_pos
        margin = 400 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return           
        scaled_img = scale_img(self.image, zoom)
        rect = scaled_img.get_rect(center=screen_pos)
        
        shadow_r = scale(75, zoom)
        s_surf = pygame.Surface((shadow_r*2, shadow_r*2), pygame.SRCALPHA)
        pygame.draw.circle(s_surf, (0,0,0,80), (shadow_r, shadow_r), shadow_r)
        surface.blit(s_surf, (cx - shadow_r + 10*zoom, cy - shadow_r + 10*zoom))
        
        surface.blit(scaled_img, rect)

        angle = (pygame.time.get_ticks() * 0.05) % 360
        beam_len = scale(400, zoom)
        
        beam_surf = pygame.Surface((beam_len*2, beam_len*2), pygame.SRCALPHA)
        beam_cx, beam_cy = beam_len, beam_len
        
        beam_width_angle = 30 
        
        far_half_w = beam_len * math.tan(math.radians(beam_width_angle/2))
        
        poly_pts = [
            (beam_cx, beam_cy), 
            (beam_cx + beam_len, beam_cy - far_half_w),
            (beam_cx + beam_len, beam_cy + far_half_w)
        ]
        
        pygame.draw.polygon(beam_surf, (255, 255, 255, 40), poly_pts)
        far_half_w_outer = far_half_w * 1.5
        poly_outer = [
            (beam_cx, beam_cy), 
            (beam_cx + beam_len, beam_cy - far_half_w_outer),
            (beam_cx + beam_len, beam_cy + far_half_w_outer)
        ]
        pygame.draw.polygon(beam_surf, (200, 220, 255, 20), poly_outer)
        
        rot_beam = pygame.transform.rotate(beam_surf, -angle)
        beam_rect = rot_beam.get_rect(center=screen_pos)
        
        surface.blit(rot_beam, beam_rect, special_flags=pygame.BLEND_ADD)

        if not len(self.garrison)==0:
            team_c = TEAM_COLORS.get(self.team, TEAM_COLORS["neutral"])
            
            flag_x = cx + scale(40, zoom)
            flag_y = cy - scale(40, zoom)
            pole_h = scale(30, zoom)
            
            pygame.draw.line(surface, (20,20,20), (flag_x, flag_y), (flag_x, flag_y - pole_h), 2)
            
            flag_w = scale(20, zoom)
            flag_h = scale(14, zoom)
            
            rect_flag = (flag_x, flag_y - pole_h, flag_w, flag_h)
            pygame.draw.rect(surface, team_c, rect_flag)
            pygame.draw.rect(surface, (0,0,0), rect_flag, 1) 
            
            for i in range(len(self.garrison)):
                dot_x = flag_x - scale(5, zoom)
                dot_y = flag_y - pole_h + i * scale(4, zoom)
                pygame.draw.circle(surface, (255, 255, 255), (dot_x, dot_y), scale(2, zoom))

        self.draw_health_and_marker(surface, offset, zoom)


class Bastion(Building):
    def __init__(self, game, pos):
        super().__init__(game, pos, "neutral", "bastion")
        self.hp = 5000 
        self.max_hp = 5000
        self.radius = 240
        self.rect = pygame.Rect(pos.x - 240, pos.y - 240, 480, 480)
        
        self.turrets = [
            {'offset': vec(-150, -150), 'angle': 0, 'cooldown': 0, 'target': None}, 
            {'offset': vec(150, -150),  'angle': 0, 'cooldown': 0, 'target': None}, 
            {'offset': vec(-150, 150),  'angle': 0, 'cooldown': 0, 'target': None}, 
            {'offset': vec(150, 150),   'angle': 0, 'cooldown': 0, 'target': None}  
        ]
        self.attack_range = 600
        self.damage = 10
        self.fire_rate = 20
        
        self.image_base = self.generate_base_image()
        self.image_turret = self.generate_turret_image()

    def generate_base_image(self):
        w, h = 600, 600
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        
        C_BASE_DARK  = (50, 50, 55)   
        C_WALL       = (80, 85, 90)   
        C_ROOF       = (100, 105, 110)
        C_DETAIL     = (40, 40, 45)   
        C_ACCENT     = TEAM_COLORS.get(self.team, (200, 200, 200))
        
        base_w = 420
        base_rect = pygame.Rect(cx - base_w//2, cy - base_w//2, base_w, base_w)
        
        pygame.draw.rect(s, C_BASE_DARK, (base_rect.left, base_rect.bottom, base_w, 40))
        pygame.draw.rect(s, C_WALL, base_rect)
        pygame.draw.rect(s, C_DETAIL, base_rect, 6)
        
        for i in range(0, base_w, 30):
            pygame.draw.line(s, (90, 95, 100), (base_rect.left + i, base_rect.top), (base_rect.left + i, base_rect.bottom), 2)
            pygame.draw.line(s, (90, 95, 100), (base_rect.left, base_rect.top + i), (base_rect.right, base_rect.top + i), 2)

        mid_w = 270
        mid_rect = pygame.Rect(cx - mid_w//2, cy - mid_w//2, mid_w, mid_w)
        pygame.draw.rect(s, (60, 60, 65), (mid_rect.left, mid_rect.bottom, mid_w, 20)) 
        pygame.draw.rect(s, C_ROOF, mid_rect)
        
        pygame.draw.rect(s, C_ACCENT, (mid_rect.left, mid_rect.top + 20, mid_w, 15))
        pygame.draw.rect(s, C_ACCENT, (mid_rect.left, mid_rect.bottom - 35, mid_w, 15))

        top_w = 150
        pygame.draw.circle(s, C_WALL, (cx, cy), top_w//2)
        pygame.draw.circle(s, C_DETAIL, (cx, cy), top_w//2, 4)
        pygame.draw.rect(s, C_DETAIL, (cx-5, cy-40, 10, 80))
        pygame.draw.ellipse(s, C_ACCENT, (cx-30, cy-10, 60, 20), 4)

        return s

    def generate_turret_image(self):
        s = pygame.Surface((80, 80), pygame.SRCALPHA)
        cx, cy = 40, 40
        
        C_GUN_BODY = (90, 100, 90)
        C_BARREL   = (30, 30, 30)
        
        pygame.draw.circle(s, (60, 60, 65), (cx, cy), 30)
        pygame.draw.circle(s, (40, 40, 45), (cx, cy), 25, 2)
        
        pygame.draw.rect(s, C_GUN_BODY, (cx-20, cy-25, 40, 50), border_radius=5)
        
        pygame.draw.rect(s, C_BARREL, (cx+10, cy-12, 35, 8))
        pygame.draw.rect(s, C_BARREL, (cx+10, cy+4, 35, 8))
        
        return s

    def update(self):
        super().update()
        
        if self.team!="neutral":
            for i, turret in enumerate(self.turrets):
                if turret['cooldown'] > 0:
                    turret['cooldown'] -= 1

                turret_world_pos = self.pos + turret['offset']
                
                target = turret['target']
                
                if not target or not target.alive or turret_world_pos.distance_to(target.pos) > self.attack_range:
                    min_dist = self.attack_range
                    best_target = None
                    
                    for u in self.game.all_units:
                        if u.team != self.team and u.alive and not u.is_air:
                            d = turret_world_pos.distance_to(u.pos)
                            if d < min_dist:
                                min_dist = d
                                best_target = u
                    
                    turret['target'] = best_target
                
                if turret['target']:
                    diff = turret['target'].pos - turret_world_pos
                    target_angle = math.degrees(math.atan2(-diff.y, diff.x))
                    
                    turret['angle'] = target_angle
                    
                    if turret['cooldown'] <= 0:
                        self.fire_turret(i, turret['target'])

    def fire_turret(self, turret_idx, target):
        turret = self.turrets[turret_idx]
        turret_pos = self.pos + turret['offset']
        
        barrel_len = 35
        
        for off_y in [-8, 8]:
            muzzle_offset = vec(barrel_len, off_y).rotate(-turret['angle'])
            spawn_pos = turret_pos + muzzle_offset
            
            p = Projectile(self.game, spawn_pos, target, self.team, self.damage, "bullet")
            p.speed = 15
            self.game.projectiles.append(p)
            
        turret['cooldown'] = self.fire_rate

    def draw(self, surface, offset, zoom):
        screen_pos = to_screen(self.pos, offset, zoom)
        margin = 600 * zoom
        if not (-margin < screen_pos[0] < SCREEN_WIDTH + margin and 
                -margin < screen_pos[1] < SCREEN_HEIGHT + margin):
            return           
        base_w_zoom = 420 * zoom
        shadow_offset = 40 * zoom 
        
        shadow_rect = pygame.Rect(
            screen_pos[0] - base_w_zoom//2 + shadow_offset, 
            screen_pos[1] - base_w_zoom//2 + shadow_offset+15, 
            base_w_zoom, 
            base_w_zoom
        )
        
        shadow_surf = pygame.Surface((int(base_w_zoom), int(base_w_zoom)), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surf, (0, 0, 0, 100), (0, 0, base_w_zoom, base_w_zoom), border_radius=int(10*zoom))
        
        surface.blit(shadow_surf, shadow_rect)

        scaled_base = scale_img(self.image_base, zoom)
        rect_base = scaled_base.get_rect(center=screen_pos)
        surface.blit(scaled_base, rect_base)
        
        scaled_turret_img = scale_img(self.image_turret, zoom)
        
        for turret in self.turrets:
            t_offset = turret['offset'] * zoom
            t_screen_pos = (screen_pos[0] + t_offset.x, screen_pos[1] + t_offset.y)
            
            rot_turret = pygame.transform.rotate(scaled_turret_img, turret['angle'])
            rect_turret = rot_turret.get_rect(center=t_screen_pos)
            
            t_shadow_surf = pygame.transform.rotate(scaled_turret_img, turret['angle'])
            t_shadow_surf.fill((0,0,0,80), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(t_shadow_surf, (rect_turret.x + 5*zoom, rect_turret.y + 5*zoom))
            
            surface.blit(rot_turret, rect_turret)

        self.draw_health_and_marker(surface, offset, zoom, y_offset=-150*zoom)
    class Dock(Building):
        def __init__(self, game, pos, angle=0):
            super().__init__(game, pos, "neutral", "dock")
            self.hp = 1000
            if angle == 0 or angle == 180:
                self.rect = pygame.Rect(pos.x-100, pos.y-30, 200, 60)
            else:
                self.rect = pygame.Rect(pos.x-30, pos.y-100, 60, 200)
            
            self.angle = angle
            self.image = self.generate_image()

        def generate_image(self):
            s = pygame.Surface((200, 60), pygame.SRCALPHA)
            pygame.draw.rect(s, (100, 90, 80), (0, 0, 200, 60)) 
            for x in range(0, 200, 10):
                pygame.draw.line(s, (80, 70, 60), (x, 0), (x, 60), 1)
            for x in range(10, 190, 30):
                pygame.draw.circle(s, (20,20,20), (x, 0), 5)
                pygame.draw.circle(s, (20,20,20), (x, 60), 5)
            return s
        
        def draw(self, surface, offset, zoom):
            pass

