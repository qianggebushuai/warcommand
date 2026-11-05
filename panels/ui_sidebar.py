import pygame
import os
import sys
from core.settings import *
from core.base_classes import vec
from core.utils import resource_path, get_font
from core.i18n import tr, tr_name, tr_desc, tr_tab

# 侧边栏配置
SIDEBAR_WIDTH = 220
TAB_HEIGHT = 40
ITEM_HEIGHT = 60
ITEM_MARGIN = 5
SCROLLBAR_W = 10          # 建造列表滚动条宽度
# 布局：小地图内嵌在侧栏顶部（正方形，边长=侧栏宽），标签在其下，建造列表最下（带滚动条）
MINIMAP_AREA_H = SIDEBAR_WIDTH
ITEMS_TOP = MINIMAP_AREA_H + TAB_HEIGHT

class SidebarItem:
    def __init__(self, name, cost, action_type, payload, req_building=None, req_tech=None, req_faction=None, req_tech_center=False, desc="", req_list=None):
        self.name = name
        self.cost = cost
        self.action_type = action_type
        self.payload = payload
        self.req_building = req_building
        self.req_tech = req_tech
        self.req_faction = req_faction
        self.req_tech_center = req_tech_center  
        self.req_list = req_list      
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.visible = False

        self.build_progress = 0.0
        self.is_ready = False
        self.is_building = False    # 本项是否正在读条（每项独立冷却栏，可并行）
        self.build_timer = 0
        self.total_build_time = 300
        self.description = desc
        self.image = None 
        
        # 尝试加载图片
        try:
            # 使用 resource_path 确保打包后能找到
            path = resource_path(os.path.join("picture", f"icon_{payload}.png"))
            if os.path.exists(path):
                img = pygame.image.load(path).convert_alpha()
                self.image = pygame.transform.scale(img, (40, 40)) 
        except:
            pass

class Sidebar:
    def __init__(self, game):
        self.game = game
        # 侧栏在屏幕右侧（小地图上、建造列表下，合为一体）
        self.rect = pygame.Rect(SCREEN_WIDTH - SIDEBAR_WIDTH, 0, SIDEBAR_WIDTH, SCREEN_HEIGHT)
        self.bg_color = (30, 30, 35)
        self.tab_color = (50, 50, 60)
        self.active_tab_color = (80, 80, 100)
        self.image_cache = {}
        # 滚动条状态
        self.scroll_y = 0
        self.max_scroll = 0
        self.items_area = pygame.Rect(self.rect.x, ITEMS_TOP, SIDEBAR_WIDTH, SCREEN_HEIGHT - ITEMS_TOP)
        self.scrollbar_track = pygame.Rect(0, 0, 0, 0)
        self.scrollbar_thumb = pygame.Rect(0, 0, 0, 0)
        self.dragging_scrollbar = False
        self.drag_offset = 0
        self._content_h = 0        
        # 标签定义
        self.tab_config = [
            ("BUILD", "icon_tab_build.png", "Construct Buildings"),
            ("UNIT",  "icon_tab_unit.png",  "Train Units"),
            ("SUPP",  "icon_tab_supp.png",  "Support Powers"),
            ("ETC",   "icon_tab_etc.png",   "Special Options")
        ]
        self.tabs = [t[0] for t in self.tab_config]
        self.current_tab = "BUILD"
        
        self.tab_rects = []
        self.tab_images = []
        
        # 初始化标签（位于小地图下方；侧栏在右侧，x 需加上侧栏偏移）
        tab_w = SIDEBAR_WIDTH // 4
        for i, (name, fname, _) in enumerate(self.tab_config):
            self.tab_rects.append(pygame.Rect(self.rect.x + i * tab_w, MINIMAP_AREA_H, tab_w, TAB_HEIGHT))
            
            # 加载标签图标
            path = resource_path(os.path.join("picture", fname))
            img = None
            if os.path.exists(path):
                try:
                    loaded = pygame.image.load(path).convert_alpha()
                    img = pygame.transform.scale(loaded, (24, 24))
                except: pass
            self.tab_images.append(img)
        # 定义所有项目
        self.all_items = {
            "BUILD": [
                SidebarItem("Power", POWER_PLANT_COST, "BUILD", "power_plant", "base", desc="Provides Power"),
                SidebarItem("Factory", FACTORY_COST, "BUILD", "factory", "base", desc="Produces Vehicles"),
                SidebarItem("Airfield", AIRFIELD_COST, "BUILD", "airfield", "base", desc="Produces Aircraft"),
                SidebarItem("Radar", RADAR_COST, "BUILD", "radar", "base", desc="Unlocks Support & Minimap"),
                SidebarItem("Shipyard", SHIPYARDCOST, "BUILD", "shipyard", "base", desc="Produces Naval Units"),
                SidebarItem("Tech Lab", RESEARCH_COST, "BUILD", "research", "radar", desc="Unlocks Advanced Tech"),
                SidebarItem("Mining", MINING_COST, "BUILD", "mining", "base", desc="Generates Income"),
                SidebarItem("AA Gun", AA_TURRET_COST, "BUILD", "aa_turret", "research", desc="Anti-Air Defense"),
                SidebarItem("Laser", LASER_TURRET_COST, "BUILD", "laser_turret", "research", desc="Anti-Ground Laser"),
                SidebarItem("Missile Def", MISSILE_DEFENSE_COST, "BUILD", "missile_def", "research", desc="Intercepts Missiles"),
                SidebarItem("Bunker", BUNKER_COST, "BUILD", "bunker", "base", desc="commom defense"),
                SidebarItem("Barracks", BARRACKS_COST, "BUILD", "barracks", "base", desc="2nd Infantry Line"),
                SidebarItem("Fortress", 2500, "BUILD", "bastion", "bastion_none", desc="Heavy quad-turret defense"),
                SidebarItem("BlackShroud", BLACKSHRODCOST, "BUILD", "shroud_gen", "base",req_tech_center=True, desc="create a disturbing area"), 
                SidebarItem("Prototype", PROTOTYPECOST, "BUILD", "prototype_gen", "research", req_tech_center=True,desc="Base for Superweapons"),
                SidebarItem("Iron Curtain", IRONCURTAINCOST, "BUILD", "iron_curtain", "prototype_gen", desc="Invulnerability Shield"),
                SidebarItem("Nuke Silo", NUKESILOCOST, "BUILD", "nuke_silo", "prototype_gen", desc="Devastating Rocket"),               
                #PLA
                SidebarItem("CIWS", CIWS_COST, "BUILD", "ciws", "research", req_faction="CHINA", desc="short defense"),                   
                # 特殊
                SidebarItem("Tech Center", TECH_CENTER_COST, "BUILD", "tech_center", "research", desc="Unlocks Advanced Units"),
                SidebarItem("REBUILD BASE", 5000, "SPECIAL", "rebuild_base", None, desc="Construct a new MCV/Base") 
            ],
            "UNIT": [
                SidebarItem("Rifleman", RIFLEMAN_COST, "SPAWN", "rifleman", "base", desc="Basic Infantry"),
                SidebarItem("Rocket", ROCKET_COST, "SPAWN", "rocket", "base", desc="Anti-Vehicle/Air Infantry"),
                SidebarItem("Engineer", COMBAT_EN_COST, "SPAWN", "combat_engineer", "base", desc="Repair & Capture Buildings"),
                SidebarItem("Shotgunner", 150, "SPAWN", "shotgunner", "base", desc="Close Range AOE"),
                
                SidebarItem("Harvester", HARVESTER_COST, "SPAWN", "harvester", "factory", desc="Collects Ore"),
                SidebarItem("APC", APC_COST, "SPAWN", "apc", "factory", desc="Transport Infantry"),
                SidebarItem("Armored", ARMORED_COST, "SPAWN", "armored", "factory", desc="Light Vehicle"),
                SidebarItem("M1A2", M1A2_COST, "SPAWN", "m1a2", "factory", desc="Main Battle Tank"),
                SidebarItem("Sniper", SNIPER_COST, "SPAWN", "sniper", "factory", req_tech=True, desc="Long Range Anti-Infantry"),
                SidebarItem("Mech", MECH_COST, "SPAWN", "mech", "factory",  req_tech_center=True,desc="Heavy Walker"),
                SidebarItem("ShockwaveVehicle", SHOCKWAVE_COST, "SPAWN", "waver", "factory",desc="blow enemy away"),                
                
                SidebarItem("Heli", HELICOPTER_COST, "SPAWN", "helicopter", "airfield", desc="Attack Helicopter"),
                SidebarItem("Attacking Heli", WZ10_COST, "SPAWN", "wz10", "airfield", desc="Heavy heli"),
                SidebarItem("FighterJet", FIGHTER_COST, "SPAWN", "fighterjet", "airfield",req_tech_center=True, desc="jet used for template but heavy strike"),
                SidebarItem("AttackPlane", ATTACKER_COST, "SPAWN", "attackplane", "airfield",req_list=["radar"], desc="jet used for strike vichile"),
                SidebarItem("HeavyTransport", HEAVYTRANSPORT_COST, "SPAWN", "heavytransport", "airfield", desc="carry mechs and drop them"),
                SidebarItem("Airship", KIROV_COST, "SPAWN", "kirov", "airfield",req_tech_center=True, desc="Heavy Bomber Airship"),
                
                SidebarItem("MissileBoat", 600, "SPAWN", "missile_boat", "shipyard", desc="Naval Missile Platform"),
                SidebarItem("AAFrigate", AABOAT_COST, "SPAWN", "antiairfrigate", "shipyard", req_tech_center=True, desc="Naval Missile Platform"), 
                SidebarItem("LaserDestroyer", LASER_SHIP_COST, "SPAWN", "laserdestroyer", "shipyard",req_faction="RUSSIA", req_tech_center=True, desc="laser damage get higher by time"),   
                SidebarItem("MissileCruiser",  MissileCruiser_COST, "SPAWN", "missilecruiser", "shipyard", req_faction="USA",req_tech_center=True, desc="Naval Missile Platform"),  
                SidebarItem("MissileCruiser",  MissileCruiser_COST, "SPAWN", "missilecruiser", "shipyard", req_faction="CHINA",req_tech_center=True, desc="Naval Missile Platform"),                  
                # 特色兵种
                SidebarItem("Type 99", TYPE99_COST, "SPAWN", "type99", "factory", req_faction="CHINA", req_tech_center=True,desc="Heavy Tank"),
                SidebarItem("DroneCarrier", DRONECARRIER_COST, "SPAWN", "dronecarrier", "factory", req_faction="CHINA", desc="spawner"),
                SidebarItem("TankCarrier", TANKCARRIER_COST, "SPAWN", "tankcarrier", "factory", req_faction="CHINA", desc="carry tank"),                

                SidebarItem("HIMARS", HIMARS_COST, "SPAWN", "himars", "factory", req_faction="USA", req_tech_center=True,desc="Rocket Arty"),
                SidebarItem("StealthHeli", STEALHELI_COST, "SPAWN", "stealheli", "airfield", req_faction="USA", req_tech_center=True,desc="hightech heli"),

                SidebarItem("Hind", HIND_COST, "SPAWN", "mi24", "airfield", req_faction="RUSSIA",req_tech_center=True, desc="Gunship"),
                SidebarItem("TerminatorIFV", TERMINATOR_COST, "SPAWN", "bmpt", "factory", req_faction="RUSSIA",req_tech_center=True, desc="The descendnet of doom"),
            ],
            "SUPP": [
                SidebarItem("AC-130", AC130_COST, "SUPPORT", "ac130", "radar",desc="Aerial Gunship Support"),
                SidebarItem("Missile", MISSILE_COST, "SUPPORT", "missile", "radar", desc="Long Range Cruise Missile"),
                SidebarItem("Airdrop", AIRDROP_COST, "SUPPORT", "airdrop", "radar",  req_tech_center=True,desc="Paratrooper Reinforcements"),
                SidebarItem("Battleship", 1000, "SUPPORT", "battleship_call", desc="Control the Battleship"),
            ],
            "ETC": [] 
        }
        
        # 字体（get_font 走项目 simhei.ttf，含中文字形；部分机器 SysFont 枚举
        # 注册表会崩、Font(None) 无中文字形——中文一律走 get_font）
        self.font = get_font(16)
        self.title_font = get_font(12, bold=True)
        
        # 悬停状态
        self.hover_item = None
        self.hover_tab_idx = -1
    def get_icon(self, payload, faction):
        # 1. 确定图片名
        img_name = f"icon_{payload}"
        
        # 特殊单位换皮
        if payload == "m1a2":
            if faction == "CHINA": img_name = "icon_type99L"
            elif faction == "RUSSIA": img_name = "icon_t28"
        if payload == "apc":
            if faction == "CHINA": img_name = "PGZ-the burns"
            elif faction == "RUSSIA": img_name = "PGZ-the burns"
        elif payload == "fighterjet":
            if faction == "CHINA": img_name = "J35"
            elif faction == "USA": img_name = "F35"
            elif faction == "RUSSIA": img_name = "SU57"  
        elif payload == "attackplane":
            if faction == "CHINA": img_name = "JH9"
            elif faction == "USA": img_name = "FA18E"
            elif faction == "RUSSIA": img_name = "SU25M"              
        # 2. 查缓存
        if img_name in self.image_cache:
            return self.image_cache[img_name]
            
        # 3. 加载新图
        path = resource_path(f"picture/{img_name}.png")
        if os.path.exists(path):
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.scale(img, (40, 40))
            self.image_cache[img_name] = img
            return img
        
        return None # 没图

    def _is_fog_deploy(self):
        return (getattr(self.game, 'arena_active', False)
                and getattr(self.game, 'arena_mode', 'standard') == "fog"
                and getattr(self.game, 'arena_phase', '') == "DEPLOY")

    def _update_arena_fog(self):
        """迷雾竞技场布防侧栏：只显示当前组军池内的项。

        价格覆写为竞技场定价（海军/建筑自定价）；跳过基地/科技等需求
        检查（竞技场无基地），排版与滚动几何复用主逻辑。
        """
        pool = dict(getattr(self.game, 'arena_army_pool', {}))
        for items in self.all_items.values():
            for item in items:
                item.visible = item.payload in pool
                if item.visible:
                    item.cost = pool[item.payload]
                    item.is_ready = False
                    item.build_progress = 0.0
        current_list = self.all_items[self.current_tab]
        visible_count = 0
        for item in current_list:
            if item.visible:
                x = self.rect.x + ITEM_MARGIN
                y = ITEMS_TOP + ITEM_MARGIN + \
                    visible_count * (ITEM_HEIGHT + ITEM_MARGIN) - self.scroll_y
                w = SIDEBAR_WIDTH - ITEM_MARGIN * 2 - SCROLLBAR_W
                item.rect = pygame.Rect(x, y, w, ITEM_HEIGHT)
                visible_count += 1
        self.items_area = pygame.Rect(self.rect.x, ITEMS_TOP,
                                      SIDEBAR_WIDTH, SCREEN_HEIGHT - ITEMS_TOP)
        self._content_h = ITEM_MARGIN + visible_count * (ITEM_HEIGHT + ITEM_MARGIN)
        self.max_scroll = max(0, self._content_h - self.items_area.height)
        self.scroll_y = max(0, min(self.scroll_y, self.max_scroll))
        track_h = self.items_area.height - 4
        self.scrollbar_track = pygame.Rect(self.rect.right - SCROLLBAR_W - 1,
                                           ITEMS_TOP + 2, SCROLLBAR_W, track_h)
        if self.max_scroll > 0:
            thumb_h = max(30, int(track_h * self.items_area.height / self._content_h))
            thumb_y = self.scrollbar_track.y + \
                int((self.scroll_y / self.max_scroll) * (track_h - thumb_h))
            self.scrollbar_thumb = pygame.Rect(self.scrollbar_track.x + 1, thumb_y,
                                               SCROLLBAR_W - 2, thumb_h)
        else:
            self.scrollbar_thumb = pygame.Rect(0, 0, 0, 0)

    def update(self):
        # 迷雾竞技场布防：按 arena_army_pool 过滤显示，价格用竞技场定价
        if self._is_fog_deploy():
            self._update_arena_fog()
            return
        # 扫描建筑
        my_buildings = set()
        upgraded_buildings = set()
        has_base = False
        has_tech_center = False
        has_comm_station = False
                    
        my_team = self.game.my_team 
        if self.game.current_map:
            current_map_name = self.game.current_map.name
        else:
            current_map_name = ""

        for b in self.game.all_buildings:
            if b.alive and getattr(b, 'b_type', '') == "comm_station":
                if b.team == my_team:
                    has_comm_station = True
                    break
        
        # 2. [新增] 检查是否已经拥有战列舰
        has_battleship = False
        from units import Battleship # 确保类型检查
        for u in self.game.all_units:
            if u.alive and u.team == my_team and isinstance(u, Battleship):
                has_battleship = True
                break
        has_empty_prototype = False
        self.superweapon_status = {} 
        for b in self.game.all_buildings:
            if b.team == my_team and b.alive:
                b_type = getattr(b, 'b_type', '')
                my_buildings.add(b_type)
                if getattr(b, 'is_upgraded', False):
                    upgraded_buildings.add(b_type)
                
                if b_type == "base": has_base = True
                if b_type == "tech_center": has_tech_center = True
            if b.team == my_team and b.alive and getattr(b, 'b_type', '') == 'prototype_gen':
                my_buildings.add('prototype_gen')
                # 检查是否还没有挂载武器
                if not getattr(b, 'loaded_weapon', None):
                    has_empty_prototype = True        
                if b.loaded_weapon:
                    if b.is_ready:
                        prog = 1.0
                    else:
                        prog = b.charge_timer / b.charge_time_total if b.charge_time_total > 0 else 0
                    
                    current_max = self.superweapon_status.get(b.loaded_weapon, 0.0)
                    self.superweapon_status[b.loaded_weapon] = max(current_max, prog)
        for u in self.game.all_units:
            if u.team == my_team and u.__class__.__name__ == "MCV":
                has_base = True
                my_buildings.add("base")

        # 更新可见性
        # 1. 刷新【所有页】条目的 visible（此前只刷当前 tab，导致非激活页
        #    条目永远 False——自动游玩策略器停在建筑页时无法判断单位解锁状态）
        current_list = self.all_items[self.current_tab]
        all_flat_items = [it for items in self.all_items.values() for it in items]
        my_faction = self.game.my_faction # 获取我方阵营   
        ban_list = {
            "广播中心": ["shipyard", "missile_boat", "battleship_call"],
            "荒野游踪": ["shipyard", "missile_boat"]
        }
        
        forbidden = ban_list.get(current_map_name, []) 

        for item in all_flat_items:
            item.visible = False # 先重置
            if item.payload in forbidden:
                continue                
            # 战列舰
            if item.payload == "battleship_call":
                # [核心逻辑] 有通讯站 且 没有战列舰 -> 显示按钮
                item.visible = has_comm_station and (not has_battleship)
                if not item.visible: continue
            if item.payload == "m1a2":
                if my_faction == "CHINA": item.name = "TYPE99L"
                elif my_faction == "RUSSIA": item.name = "T-14D"
                else: item.name = "M1A2"
                item.image = self.get_icon("m1a2", my_faction)
            if item.payload == "apc":
                if my_faction == "CHINA": item.name = "PGZ-the burns"
                elif my_faction == "RUSSIA": item.name = "PGZ-the burns"
                else: item.name = "APC"
                item.image = self.get_icon("apc", my_faction)
            if item.payload == "fighterjet":
                if my_faction == "CHINA": item.name = "J35-A"
                elif my_faction == "RUSSIA": item.name = "SU59"
                else: item.name = "F35-E"
                item.image = self.get_icon("fighterjet", my_faction) 
            if item.payload == "attackplane":
                if my_faction == "CHINA": item.name = "JH9"
                elif my_faction == "RUSSIA": item.name = "SU25M"
                else: item.name = "FA18E"
                item.image = self.get_icon("attackplane", my_faction)  
            if item.payload in ["iron_curtain", "nuke_silo"]:
                # 必须有空闲的基座才能造
                item.visible = has_empty_prototype
                item.charge_progress = self.superweapon_status.get(item.payload, 0.0)
                continue              
            # 特殊: 重建基地
            if item.payload == "rebuild_base":
                if not has_base: item.visible = True
                continue
                
            # 常规: 检查建筑和科技
            if item.req_faction and self.game.my_faction != item.req_faction: continue
            if item.req_tech_center and not has_tech_center: continue
            
            meets_building = False
            if item.req_building:
                if item.req_building in my_buildings:
                    if not item.req_tech or (item.req_building in upgraded_buildings):
                        meets_building = True
            else:
                meets_building = True # 无需求
            
            # 5. 额外列表检查
            meets_list = True
            if item.req_list:
                for req in item.req_list:
                    if req not in my_buildings:
                        meets_list = False; break
            
            # 最终判定
            if meets_building and meets_list:
                item.visible = True

        # 2. 统一计算坐标 (排版：单列 + 滚动偏移；x 加侧栏偏移)
        visible_count = 0
        for item in current_list:
            if item.visible:
                x = self.rect.x + ITEM_MARGIN
                y = ITEMS_TOP + ITEM_MARGIN + visible_count * (ITEM_HEIGHT + ITEM_MARGIN) - self.scroll_y
                w = SIDEBAR_WIDTH - ITEM_MARGIN * 2 - SCROLLBAR_W
                h = ITEM_HEIGHT
                item.rect = pygame.Rect(x, y, w, h)
                visible_count += 1

        # 3. 列表区域 / 滚动范围 / 滚动条几何
        self.items_area = pygame.Rect(self.rect.x, ITEMS_TOP, SIDEBAR_WIDTH, SCREEN_HEIGHT - ITEMS_TOP)
        self._content_h = ITEM_MARGIN + visible_count * (ITEM_HEIGHT + ITEM_MARGIN)
        self.max_scroll = max(0, self._content_h - self.items_area.height)
        self.scroll_y = max(0, min(self.scroll_y, self.max_scroll))
        track_h = self.items_area.height - 4
        self.scrollbar_track = pygame.Rect(self.rect.right - SCROLLBAR_W - 1, ITEMS_TOP + 2, SCROLLBAR_W, track_h)
        if self.max_scroll > 0:
            thumb_h = max(30, int(track_h * self.items_area.height / self._content_h))
            thumb_y = self.scrollbar_track.y + int((self.scroll_y / self.max_scroll) * (track_h - thumb_h))
            self.scrollbar_thumb = pygame.Rect(self.scrollbar_track.x + 1, thumb_y, SCROLLBAR_W - 2, thumb_h)
        else:
            self.scrollbar_thumb = pygame.Rect(0, 0, 0, 0)

        # 各建造项独立读条：每项一个冷却栏，多个建筑可同时冷却（红警式并行队列）
        for items in self.all_items.values():
            for item in items:
                if getattr(item, 'is_building', False):
                    item.build_timer += 1
                    item.build_progress = item.build_timer / item.total_build_time

                    if item.build_timer >= item.total_build_time:
                        item.is_ready = True
                        item.build_progress = 1.0
                        item.is_building = False    # 完成，本项冷却结束（不影响其他项）
                        from core.base_classes import FloatingText
                        self.game.particles.add(FloatingText(self.game.player_base.pos, "READY", GREEN_HAT))
    def scroll(self, delta):
        """滚动建造列表（正=向下看）。"""
        self.scroll_y = max(0, min(self.scroll_y + delta, self.max_scroll))

    def begin_scrollbar_drag(self, m_pos):
        self.dragging_scrollbar = True
        self.drag_offset = m_pos[1] - self.scrollbar_thumb.y

    def update_scrollbar_drag(self, m_pos):
        if not self.dragging_scrollbar or self.max_scroll <= 0:
            return
        thumb_h = max(1, self.scrollbar_thumb.height)
        span = self.scrollbar_track.height - thumb_h
        if span <= 0:
            return
        ratio = (m_pos[1] - self.drag_offset - self.scrollbar_track.y) / span
        self.scroll_y = max(0, min(int(ratio * self.max_scroll), self.max_scroll))

    def end_scrollbar_drag(self):
        self.dragging_scrollbar = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            m_pos = pygame.mouse.get_pos()

            # 1. 检查是否在侧边栏区域内
            if not self.rect.collidepoint(m_pos):
                return False

            # 1.5 小地图内嵌在侧栏顶部：放行给 Minimap 自己处理
            if self.game.minimap.rect.collidepoint(m_pos):
                return False

            # 2. 获取当前列表 (提取公共变量)
            current_list = self.all_items[self.current_tab]

            # 1.7 滚动条拖动开始
            if event.button == 1 and self.max_scroll > 0 and self.scrollbar_thumb.collidepoint(m_pos):
                self.begin_scrollbar_drag(m_pos)
                return True

            # 3. 中键点击 (秒造读条)
            if event.button == 2:
                 for item in current_list:
                    if item.visible and self.items_area.collidepoint(m_pos) and item.rect.collidepoint(m_pos):
                        if item.payload in ["iron_curtain", "nuke_silo"]:
                            self.game.show_alert("CANNOT QUEUE PROTOTYPE") # 可选提示
                            return True
                        if item.action_type == "BUILD" and self.game.has_tech_center(self.game.my_team):
                            self.start_remote_build(item)
                        return True

            # 4. 左键点击
            if event.button == 1:
                # A. 标签切换
                for i, rect in enumerate(self.tab_rects):
                    if rect.collidepoint(m_pos):
                        self.current_tab = self.tabs[i]
                        self.scroll_y = 0  # 切标签回到顶部
                        return True

                # B. 物品点击（仅当点击落在列表可见区域内）
                for item in current_list:
                    # [必须加这行] 检查鼠标是否在按钮上！
                    if item.visible and self.items_area.collidepoint(m_pos) and item.rect.collidepoint(m_pos):

                        if item.is_ready:
                             # 冷却转完 → 秒造放置（点击地图立即落成，无工程师）
                             self.game.place_building_type = item.payload
                             self.game.is_instant_build = True
                        elif item.action_type == "BUILD" and getattr(item, 'is_building', False):
                             # 本项读条中再点 → 冷却继续走，同时进入工程师放置（并行建造）
                             self.game.place_building_type = item.payload
                             self.game.is_instant_build = False
                        else:
                             # 首次点击 → 开始读条（红警式冷却栏）
                             self.execute_item(item)

                        return True # 处理完毕，退出

            # 5. 右键点击建造项 → 取消该项冷却并返还建造费用
            if event.button == 3:
                for item in current_list:
                    if item.visible and self.items_area.collidepoint(m_pos) and item.rect.collidepoint(m_pos):
                        if item.action_type == "BUILD" and getattr(item, 'is_building', False):
                            self.game.team_resources[self.game.my_team] = \
                                self.game.team_resources.get(self.game.my_team, 0) + item.cost
                            item.is_building = False
                            item.build_timer = 0
                            item.build_progress = 0.0
                            item.is_ready = False
                            self.game.show_alert("BUILD CANCELLED")
                        return True

            return True # 既然点在侧边栏内，就拦截事件

        return False
    def start_remote_build(self, item):
        if self._is_fog_deploy():
            return  # 迷雾竞技场无生产队列，中键读条禁用
        if getattr(item, 'is_building', False):
            self.game.show_alert("ALREADY BUILDING")
            return

        if item.is_ready:
            self.game.show_alert("ALREADY READY")
            return
        cost = item.cost
        if self.game.team_resources[self.game.my_team] >= cost:
            self.game.team_resources[self.game.my_team] -= cost
            item.is_building = True
            item.build_timer = 0
            item.is_ready = False
            # 根据造价计算时间
            item.total_build_time = int(cost /50 ) * 60
        else:
            self.game.show_alert("INSUFFICIENT FUNDS")
    def execute_item(self, item):
        # 迷雾竞技场：点击 = 选中兵种，点击己方半区落位时才扣军费
        if self._is_fog_deploy():
            if item.payload in dict(getattr(self.game, 'arena_army_pool', {})):
                self.game.arena_fog_select(item.payload)
            return
        current_money = self.game.team_resources.get(self.game.my_team, 0)
        
        if current_money < item.cost:
            self.game.show_alert("INSUFFICIENT FUNDS")
            return

        # BUILD
        if item.action_type == "BUILD":
            
            # [特殊分支] 原型武器 (铁幕/核弹)
            if item.payload in ["iron_curtain", "nuke_silo"]:
                progress = getattr(item, 'charge_progress', 0.0)
                
                # [情况 1: 已就绪，准备释放]
                if progress >= 1.0:
                    # 找到那个就绪的建筑
                    target_gen = None
                    for b in self.game.all_buildings:
                        if b.team == self.game.my_team and getattr(b, 'loaded_weapon', '') == item.payload and getattr(b, 'is_ready', False):
                            target_gen = b
                            break
                    
                    if target_gen:
                        # 进入技能瞄准模式
                        self.game.place_building_type = f"skill_{item.payload}" 
                        from core.base_classes import FloatingText
                        self.game.particles.add(FloatingText(target_gen.pos, "SELECT TARGET", CYAN))
                    else:
                        self.game.show_alert("WEAPON NOT FOUND")
                   

                is_built_or_building = False
                for b in self.game.all_buildings:
                    if b.team == self.game.my_team and getattr(b, 'loaded_weapon', '') == item.payload:
                        is_built_or_building = True
                        break

                if progress == 0 and not is_built_or_building:
                    # 检查是否有空闲基座
                    has_empty_base = False
                    target_base = None
                    for b in self.game.all_buildings:
                        if b.team == self.game.my_team and getattr(b, 'b_type', '') == 'prototype_gen':
                            if not getattr(b, 'loaded_weapon', None):
                                has_empty_base = True
                                target_base = b
                                break
                    
                    if not has_empty_base:
                        self.game.show_alert("NEED EMPTY PROTOTYPE BASE")
                        return

                    # 联机模式必须发包
                    if self.game.is_online and self.game.my_role == "CLIENT":
                        self.game.net.send({
                            "type": "REQ_BUILD_PROTOTYPE",
                            "p_type": item.payload
                        })
                        # 本地扣钱 (视觉效果)
                        if self.game.my_team in self.game.team_resources:
                            self.game.team_resources[self.game.my_team] -= item.cost
                    else:
                        # Host/Single 逻辑: 直接执行
                        self.game.team_resources[self.game.my_team] -= item.cost
                        if target_base:
                            target_base.build_prototype(item.payload)
                            from core.base_classes import FloatingText
                            self.game.particles.add(FloatingText(target_base.pos, "Upgrading...", GREEN_HAT))
                    return # 结束

                # [情况 3: 充能中]
                else:
                    self.game.show_alert("CHARGING...")
                    return

            if item.payload != "power_plant":
                if self.game.current_voltage + POWER_COST > self.game.max_voltage:
                    self.game.show_alert("LOW POWER!")
                    return
            
            # 红警式冷却：首次点击扣钱开始读条，转完后可秒放（读条中再点=出工程师，
            # 见 handle_event 的分支）；每个建造项有独立冷却栏，可多项同时读条
            if getattr(item, 'is_building', False):
                self.game.show_alert("ALREADY BUILDING")
                return
            self.game.team_resources[self.game.my_team] -= item.cost
            item.is_building = True
            item.build_timer = 0
            item.is_ready = False
            item.total_build_time = int(item.cost / 50) * 60

        # SPAWN
        elif item.action_type == "SPAWN":
            success = self.auto_queue_unit(item.payload, item.cost)
            if not success: self.game.show_alert("PRODUCTION HALTED")

        # SUPPORT
        elif item.action_type == "SUPPORT":
            if item.payload == "battleship_call":
                print("[UI] Clicked Battleship Call")
                if self.game.is_online and self.game.my_role == "CLIENT":
                    self.game.net.send({"type": "REQ_SUPPORT", "s_type": "battleship_call", "x":0, "y":0})
                else:
                    self.game.handle_battleship_call(self.game.my_team)
                return 
            if item.payload == "ac130": self.game.call_airstrike_mode = True
            elif item.payload == "missile": self.game.call_missile_mode = True
            elif item.payload == "airdrop": self.game.call_airdrop_mode = True

        # SPECIAL
        elif item.action_type == "SPECIAL" and item.payload == "rebuild_base":
            self.rebuild_base(item.cost)

    def auto_queue_unit(self, u_type, cost):
        # 1. 映射表（步兵允许基地/兵营双线生产，其余单类型）
        target_b_types = []
        if u_type in ["rifleman", "rocket","shotgunner", "combat_engineer"]: target_b_types = ["base", "barracks"]
        elif u_type in ["apc", "armored", "m1a2", "sniper", "mech", "type99", "himars","dronecarrier","bmpt","waver","tankcarrier","harvester"]: target_b_types = ["factory"]
        elif u_type in ["helicopter", "wz10", "kirov", "mi24","stealheli","fighterjet","heavytransport","attackplane"]: target_b_types = ["airfield"]
        elif u_type in ["missile_boat","antiairfrigate","laserdestroyer","missilecruiser"]: target_b_types = ["shipyard"]

        my_team = self.game.my_team

        candidates = []
        for b in self.game.all_buildings:
            if b.team == my_team and b.alive and getattr(b, 'b_type', '') in target_b_types:
                candidates.append(b)
        
        if not candidates: return False

        # 2. 智能选择 (分级负载均衡)
        ref_pos = vec(SCREEN_WIDTH/2, SCREEN_HEIGHT/2)
        if self.game.player_base and self.game.player_base.alive:
            ref_pos = self.game.player_base.pos
        
        def get_queue_len(b):
            if self.game.is_online and self.game.my_role == "CLIENT":
                return getattr(b, 'synced_queue_len', 0)
            
            count = len(b.production_queue) if hasattr(b, 'production_queue') else 0
            if getattr(b, 'current_production', None):
                count += 1
            return count

        # [新增] 分级筛选逻辑
        idle_buildings = []   # 完全空闲 (queue=0)
        busy_buildings = []   # 有活干但没满 (queue < 5)
        
        for b in candidates:
            q_len = get_queue_len(b)
            if q_len == 0:
                idle_buildings.append(b)
            elif q_len < 5: 
                busy_buildings.append((b, q_len))
        
        best_building = None
        
        if idle_buildings:
            # 优先选最近的空闲工厂
            best_building = min(idle_buildings, key=lambda b: b.pos.distance_to(ref_pos))
        elif busy_buildings:
            # 其次选队列最短的，同样队列长度选最近的
            busy_buildings.sort(key=lambda x: (x[1], x[0].pos.distance_to(ref_pos)))
            best_building = busy_buildings[0][0]
        else:
            self.game.show_alert("QUEUE FULL")
            return False

        # 3. 执行
        if self.game.is_online and self.game.my_role == "CLIENT":
            self.game.net.send({
                "type": "REQ_SPAWN", 
                "u_type": u_type, 
                "b_uid": best_building.uid, 
                "x": int(best_building.pos.x), "y": int(best_building.pos.y)
            })
            if self.game.my_team in self.game.team_resources:
                self.game.team_resources[self.game.my_team] -= cost
            return True 
        else:
            # Host / Single
            if self.game.team_resources[self.game.my_team] >= cost:
                # 计算时间
                from core import settings # 确保能读取 BUILD_TIME_XXX
                
                # 尝试动态获取时间配置
                time_var_name = f"BUILD_TIME_{u_type.upper()}"
                time_cost = getattr(settings, time_var_name, BUILD_TIME_TANK) # 默认值
                
                if u_type == "rifleman": time_cost = BUILD_TIME_INFANTRY
                elif u_type == "rocket": time_cost = BUILD_TIME_INFANTRY*2
                elif u_type == "shotgunner": time_cost = BUILD_TIME_INFANTRY*3
                elif u_type == "kirov": time_cost = BUILD_TIME_AIRSHIP
                elif u_type in ["helicopter", "wz10", "mi24", "stealheli", "fighterjet", "heavytransport","attackplane"]: time_cost = BUILD_TIME_AIR

                if best_building.queue_unit(u_type, time_cost):
                    self.game.team_resources[self.game.my_team] -= cost
                    return True
                else:
                    self.game.show_alert("QUEUE FULL")
            else:
                self.game.show_alert("INSUFFICIENT FUNDS")
            return False
    def consume_ready(self, b_type):
        # 遍历当前所有按钮，找到对应的那个，重置状态
        for items in self.all_items.values():
            for item in items:
                if item.payload == b_type:
                    item.is_ready = False
                    item.build_progress = 0.0
                    item.build_timer = 0
                    return
    def rebuild_base(self, cost):
        my_team = self.game.my_team
        spawn_pos = self.game.my_start_pos
        
        current_money = self.game.team_resources.get(my_team, 0)
        
        if current_money < cost:
            self.game.show_alert("NEED MORE FUNDS")
            return

        if self.game.is_online and self.game.my_role == "CLIENT":
            self.game.net.send({"type": "REQ_REBUILD_BASE"})
        else:
            if hasattr(self.game, 'perform_rebuild_base'):
                self.game.perform_rebuild_base(cost, my_team, spawn_pos)
            else:
                print("Error: perform_rebuild_base not found")
    def draw(self, screen):
        fog_deploy = self._is_fog_deploy()
        if getattr(self.game, 'is_spectator', False) and not fog_deploy:
            return
        pygame.draw.rect(screen, self.bg_color, self.rect)
        pygame.draw.line(screen, (100, 100, 100), (self.rect.x, 0), (self.rect.x, SCREEN_HEIGHT), 2)
        
        # 标签
        m_pos = pygame.mouse.get_pos()
        self.hover_tab_idx = -1
        
        for i, rect in enumerate(self.tab_rects):
            color = self.active_tab_color if self.tabs[i] == self.current_tab else self.tab_color
            if rect.collidepoint(m_pos): 
                color = (color[0]+20, color[1]+20, color[2]+20)
                self.hover_tab_idx = i
                
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, (20, 20, 20), rect, 1)
            
            if i < len(self.tab_images) and self.tab_images[i]:
                screen.blit(self.tab_images[i], (rect.centerx - 12, rect.centery - 12))
            else:
                txt = self.title_font.render(self.tabs[i], True, WHITE)
                screen.blit(txt, txt.get_rect(center=rect.center))

        # 列表（裁剪到列表区域，滚动超出部分不可见）
        self.hover_item = None
        current_list = self.all_items[self.current_tab]
        current_money = self.game.arena_funds if fog_deploy else \
            self.game.team_resources.get(self.game.my_team, 0)
        screen.set_clip(self.items_area)
        for item in current_list:
            if item.visible:
                is_hover = item.rect.collidepoint(m_pos)
                if is_hover: self.hover_item = item
                
                # 按钮背景
                bg_c = (70, 70, 80) if is_hover else (50, 50, 60)
                if current_money < item.cost: # [修改]
                    bg_c = (60, 30, 30)
                
                pygame.draw.rect(screen, bg_c, item.rect, border_radius=5)
                pygame.draw.rect(screen, (100, 100, 100), item.rect, 1, border_radius=5)
                
                # 图标
                icon_pos = (item.rect.x + 5, item.rect.y + 10)
                if item.image:
                    screen.blit(item.image, icon_pos)
                else:
                    pygame.draw.rect(screen, (200, 200, 200), (icon_pos[0], icon_pos[1], 40, 40))
                text_x = item.rect.x + 55
                name_surf = self.font.render(tr_name(item.name), True, WHITE)
                cost_surf = self.font.render(f"${item.cost}", True, YELLOW)
                screen.blit(name_surf, (text_x, item.rect.y + 8))
                screen.blit(cost_surf, (text_x, item.rect.y + 30))

            # [新增] 绘制进度遮罩
            if item.build_progress > 0 and not item.is_ready:
                # 画一个扇形或者从下往上的遮罩
                h = int(item.rect.height * (1 - item.build_progress))
                mask_rect = pygame.Rect(item.rect.x, item.rect.y, item.rect.width, h)
                s = pygame.Surface((mask_rect.width, mask_rect.height), pygame.SRCALPHA)
                s.fill((0, 0, 0, 150))
                screen.blit(s, mask_rect)
            
            if item.is_ready:
                pygame.draw.circle(screen, RED, (item.rect.x + 10, item.rect.y + 10), 8)
                # 白芯 (增强对比)
                pygame.draw.circle(screen, WHITE, (item.rect.x + 10, item.rect.y + 10), 4)
                
                # 文字提示 (居中覆盖)
                txt = self.title_font.render(tr("common.ready"), True, GREEN_HAT)
                txt_rect = txt.get_rect(center=item.rect.center)
                screen.blit(txt, txt_rect)
        screen.set_clip(None)  # 解除列表区域裁剪

        # 滚动条（内容超长时显示）
        if self.max_scroll > 0:
            pygame.draw.rect(screen, (60, 60, 70), self.scrollbar_track, border_radius=4)
            thumb_c = (150, 150, 160) if not self.dragging_scrollbar else (200, 200, 220)
            pygame.draw.rect(screen, thumb_c, self.scrollbar_thumb, border_radius=4)

        # Tooltip
        if self.hover_item:
            self.draw_tooltip(screen, m_pos, tr_name(self.hover_item.name), tr_desc(self.hover_item.description))
        elif self.hover_tab_idx != -1:
            name, desc = tr_tab(self.tab_config[self.hover_tab_idx][0])
            self.draw_tooltip(screen, m_pos, name, desc)

        surface = self.game.screen
        active_sw = []
        my_team = self.game.my_team
        
        for b in self.game.all_buildings:
            if b.alive and getattr(b, 'b_type', '') == 'prototype_gen' and getattr(b, 'loaded_weapon', None):
                
                # 1. 确定名称和队伍颜色
                raw_name = tr_name("Iron Curtain" if b.loaded_weapon == "iron_curtain" else "Nuke Silo")
                b_team_color = TEAM_COLORS.get(b.team, (200, 200, 200))

                is_mine = (b.team == self.game.my_team)

                if not is_mine:
                    display_name = f"{tr('w.enemy_tag')} {raw_name}"
                else:
                    display_name = raw_name

                if getattr(b, 'is_ready', False):
                    # 就绪状态：敌我都显示 READY
                    time_str = tr("common.ready")
                    status_color = (0, 255, 0) if is_mine else (255, 50, 50)
                else:
                    # 我方显示具体时间
                    total = getattr(b, 'charge_time_total', 0)
                    if total <= 0: total = 1
                    current = getattr(b, 'charge_timer', 0)
                    remaining = max(0, total - current)
                    seconds = int(remaining / 60)
                    time_str = f"{seconds//60:02}:{seconds%60:02}"
                    status_color = (255, 200, 0) # 黄色


                # 3. 添加到列表
                active_sw.append((display_name, time_str, status_color, b_team_color))

        if active_sw:
            big_font= get_font(18,bold=True)        
            start_x = self.rect.right - 10 # 靠右对齐
            start_y = self.rect.bottom - 20
            
            for name, time_str,color, b_team_color in active_sw:
                t_surf = big_font.render(time_str, True, b_team_color)
                t_rect = t_surf.get_rect(bottomright=(start_x, start_y))
                surface.blit(t_surf, t_rect)
                
                n_surf = big_font.render(name, True,b_team_color)
                n_rect = n_surf.get_rect(bottomright=(t_rect.left - 10, start_y))
                surface.blit(n_surf, n_rect)
                
                # 向上偏移下一行
                start_y -= 25
    def draw_tooltip(self, screen, pos, title, text):
        if not text: return
        padding = 5
        font_h = self.font.get_height()
        w = max(self.font.size(title)[0], self.font.size(text)[0]) + padding * 2
        h = font_h * 2 + padding * 2
        x, y = pos[0] + 15, pos[1] + 15
        if x + w > SCREEN_WIDTH: x = pos[0] - w - 5
        if y + h > SCREEN_HEIGHT: y = pos[1] - h - 5
        
        bg_rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(screen, (20, 20, 25), bg_rect)
        pygame.draw.rect(screen, WHITE, bg_rect, 1)
        
        t_surf = self.font.render(title, True, YELLOW)
        d_surf = self.font.render(text, True, (200, 200, 200))
        screen.blit(t_surf, (x + padding, y + padding))
        screen.blit(d_surf, (x + padding, y + padding + font_h))
class Minimap:
    def __init__(self, game):
        self.game = game
        # 内嵌在右侧栏顶部：宽度=侧栏宽的正方形（小地图在上、建造列表在下）
        self.size = SIDEBAR_WIDTH
        self.rect = pygame.Rect(SCREEN_WIDTH - self.size, 0, self.size, self.size)
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.surface = pygame.Surface((self.size, self.size))
        
    def update(self):
        pass

    def draw(self, surface):
        self.surface.fill((0, 0, 0)) 
        
        map_w = WORLD_WIDTH
        map_h = WORLD_HEIGHT
        if self.game.current_map:
            map_w = self.game.current_map.width
            map_h = self.game.current_map.height
            bg_color = self.game.current_map.bg_color
            pygame.draw.rect(self.surface, (bg_color[0]//2, bg_color[1]//2, bg_color[2]//2), (0,0,self.size,self.size))
            
        self.scale_x = self.size / map_w
        self.scale_y = self.size / map_h
        
        def w2m(wx, wy):
            return int(wx * self.scale_x), int(wy * self.scale_y)

        enemy_shrouds = []
        my_team = self.game.my_team
        shroud_radius = 1500
        for b in self.game.all_buildings:
            if b.alive and b.team != my_team and getattr(b, 'b_type', '') == 'shroud_gen':
                enemy_shrouds.append(b.pos)

        for shroud_pos in enemy_shrouds:
            sx, sy = w2m(shroud_pos.x, shroud_pos.y)
            sr = int(shroud_radius * self.scale_x)
            
            s = pygame.Surface((sr*2, sr*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (20, 20, 20, 150), (sr, sr), sr) 
            self.surface.blit(s, (sx-sr, sy-sr))

        for b in self.game.all_buildings:
            if not b.alive: continue
            
            should_draw = True
            if b.team != my_team:
                for shroud_pos in enemy_shrouds:
                    if b.pos.distance_to(shroud_pos) < shroud_radius:
                        should_draw = False
                        break
            
            if should_draw:
                color = TEAM_COLORS.get(b.team, (128,128,128))
                bx, by = w2m(b.pos.x, b.pos.y)
                size = 4
                if b.b_type == 'base': size = 6
                pygame.draw.rect(self.surface, color, (bx-size//2, by-size//2, size, size))

        # --- 3.5 矿脉标记（金色=富矿，暗金=低矿，灰=枯竭待再生） ---
        if self.game.current_map is not None:
            for op in getattr(self.game.current_map, 'ore_patches', []):
                ox, oy = w2m(op.pos.x, op.pos.y)
                if op.amount > 100:
                    pygame.draw.rect(self.surface, (255, 200, 60), (ox-2, oy-2, 4, 4))
                elif op.amount > 0:
                    pygame.draw.rect(self.surface, (150, 120, 60), (ox-1, oy-1, 3, 3))
                else:
                    pygame.draw.rect(self.surface, (110, 110, 110), (ox-1, oy-1, 2, 2))

        # --- 4. 绘制单位 (核心逻辑) ---
        for u in self.game.all_units:
            if not u.alive: continue
            
            # 默认：我方可见，敌方需判断
            is_visible = True
            
            if u.team != my_team:
                # 1. 隐形单位检查
                if getattr(u, 'is_stealth', False):
                    is_visible = False
                
                # 2. 干扰器检查 (如果在任何一个干扰圈内，就不可见)
                if is_visible: # 如果还没被隐形逻辑剔除
                    for shroud_pos in enemy_shrouds:
                        if u.pos.distance_to(shroud_pos) < shroud_radius:
                            is_visible = False
                            break
            
            # 只有通过了所有检查才绘制
            if is_visible:
                color = TEAM_COLORS.get(u.team, (128,128,128))
                ux, uy = w2m(u.pos.x, u.pos.y)
                # 飞机画大一点
                r = 3 if u.is_air else 2
                pygame.draw.circle(self.surface, color, (ux, uy), r)


        # 4. 绘制视口框 (白色矩形；右侧被侧栏遮挡，可视宽度减去侧栏)
        vx = self.game.camera_offset.x
        vy = self.game.camera_offset.y
        vw = (SCREEN_WIDTH - SIDEBAR_WIDTH) / self.game.zoom
        vh = SCREEN_HEIGHT / self.game.zoom
        
        mvx = vx * self.scale_x
        mvy = vy * self.scale_y
        mvw = vw * self.scale_x
        mvh = vh * self.scale_y
        
        pygame.draw.rect(self.surface, (255, 255, 255), (mvx, mvy, mvw, mvh), 1)
        
        # 绘制边框
        pygame.draw.rect(self.surface, (200, 200, 200), (0, 0, self.size, self.size), 2)

        # Blit 到主屏幕
        surface.blit(self.surface, self.rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            # 检查是否点击了小地图区域
            if self.rect.collidepoint(event.pos):
                if event.button == 1 or event.button == 3: # 左键或右键
                    # 计算点击点在小地图内的相对坐标
                    mx = event.pos[0] - self.rect.x
                    my = event.pos[1] - self.rect.y
                    
                    # 转回世界坐标
                    wx = mx / self.scale_x
                    wy = my / self.scale_y
                    
                    # 移动摄像机
                    scr_center = vec(SCREEN_WIDTH/2, SCREEN_HEIGHT/2)
                    target = vec(wx, wy)
                    self.game.camera_offset = target - (scr_center / self.game.zoom)
                    self.game.clamp_camera()  # 点小地图边缘时镜头可能越界，钳回
                    
                    return True # 消耗事件
        return False