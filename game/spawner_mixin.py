import pygame
import os
import random
import math
import json
import time
import sys
import fractions
import pygame.scrap
from core.settings import *
from core.base_classes import *
from units import *
from core.dic import *
from maps import *
from panels.widgets import ChatBox, BFButton, InputBox
from panels.ui_sidebar import Sidebar, Minimap
from panels.ui_login import LoginUI
from panels.ui_lobby import LobbyUI
from panels.basesetting import BaseSettingUI
from panels.selfdefine import SkirmishUI
from panels.updatelog import UpdateLogUI
from panels.warstory import WarStoryUI
from maps.environment import EnvironmentManager
from network import NetworkManager
from ai.ai_logic import AICommander
from core.factions import get_random_faction
from core.utils import resource_path, get_font
from core.i18n import tr

class SpawnerMixin:
    def spawn_unit(self, u_type, origin_pos, team):
        # 1. 寻找最佳生成点
        spawn_pos = vec(origin_pos)+(0,100)
        
        # 2. 寻找源头建筑
        source_building = None
        for b in self.all_buildings:
            if b.pos.distance_to(origin_pos) < 60: 
                source_building = b; break
        
        # 3. 智能选点
        if source_building:
            # 初始偏移距离 (从建筑半径开始)
            current_dist = source_building.radius + 40 
            max_dist = 500 # 防止死循环
            found = False
            
            # 尝试向外扩张
            while current_dist < max_dist and not found:
                # 尝试 8 个方向 (上下左右 + 斜向)
                angles = [90, 270, 0, 180, 45, 135, 225, 315]
                
                for angle in angles:
                    test_offset = vec(current_dist, 0).rotate(angle)
                    test_pos = source_building.pos + test_offset
                    
                    # 检查是否重叠
                    # 使用稍微大一点的 rect (比如 40x40) 模拟单位体积
                    test_rect = pygame.Rect(test_pos.x - 20, test_pos.y - 20, 40, 40)
                    collision_idx = test_rect.collidelist([b.rect for b in self.all_buildings])
                    if collision_idx != -1:
                        print(f"Collided with {self.all_buildings[collision_idx].b_type} at dist {current_dist}")                    
                    # 检查所有建筑 (包括源头，防止半径算小了卡在自己身上)
                    # 以及其他单位 (防止卡在别的坦克里)
                    collided = False
                    
                    # 查建筑
                    if test_rect.collidelist([b.rect for b in self.all_buildings]) != -1:
                        collided = True
                    
                    # 查单位 (可选，如果不想让单位叠在一起)
                    if not collided:
                        for u in self.all_units:
                            if u.alive and u.rect.colliderect(test_rect):
                                collided = True; break
                    
                    if not collided:
                        spawn_pos = test_pos
                        found = True
                        break # 找到方向了，跳出 angle 循环
                
                if found: break # 找到位置了，跳出 distance 循环
                
                # 没找到，扩大一圈继续找
                current_dist += 40 
            
            # 如果实在找不到 (被围死了)，只能强行生成在默认位置
            if not found:
                spawn_pos += vec(0, source_building.radius + 60)
                
        else:
            # 野外生成 (保持随机)
            spawn_pos += vec(random.randint(-20, 20), random.randint(-20, 20))
        if u_type == "rifleman": self.all_units.append(Rifleman(self, spawn_pos, team))
        elif u_type == "rocket": self.all_units.append(RocketTrooper(self, spawn_pos, team))
        elif u_type == "shotgunner": self.all_units.append(Shotgunner(self, spawn_pos, team))
        elif u_type == "armored": self.all_units.append(ArmoredCar(self, spawn_pos, team))
        elif u_type == "helicopter": self.all_units.append(Helicopter(self, spawn_pos, team))
        elif u_type == "wz10": self.all_units.append(WZ10(self, spawn_pos, team))
        elif u_type == "m1a2": self.all_units.append(M1A2(self, spawn_pos, team))
        elif u_type == "kirov":
            self.all_units.append(KirovAirship(self, spawn_pos, team))
            msg = "L30 REPORTING!" if team == self.my_team else "AIRSHIP DETECTED!"
            self.show_alert(msg)
        elif u_type == "sniper": self.all_units.append(Sniper(self, spawn_pos, team))
        elif u_type == "mech": self.all_units.append(HeavyMech(self, spawn_pos, team))
        elif u_type == "combat_engineer":
            from units import CombatEngineer
            self.all_units.append(CombatEngineer(self, spawn_pos, team))
        elif u_type == "missile_boat": 
            # 确保导入了 MissileBoat
            self.all_units.append(MissileBoat(self, spawn_pos, team))
        elif u_type == "apc":
            from units import APC
            self.all_units.append(APC(self, spawn_pos, team))
        elif u_type == "type99":
            from units import Type99
            self.all_units.append(Type99(self, spawn_pos, team))
        elif u_type == "himars":
            from units import HIMARS
            self.all_units.append(HIMARS(self, spawn_pos, team))
        elif u_type == "mi24":
            from units import Mi24
            self.all_units.append(Mi24(self, spawn_pos, team))
        elif u_type == "dronecarrier":
            from units import DroneCarrier
            self.all_units.append(DroneCarrier(self, spawn_pos, team))
        elif u_type == "stealheli":
            from units import StealthHeli
            self.all_units.append(StealthHeli(self, spawn_pos, team))
        elif u_type == "bmpt":
            from units import TerminatorIFV
            self.all_units.append(TerminatorIFV(self, spawn_pos, team))
        elif u_type == "waver":
            from units import ShockwaveVehicle
            self.all_units.append(ShockwaveVehicle(self, spawn_pos, team))
        elif u_type == "fighterjet":
            self.all_units.append(FighterJet(self, spawn_pos, team))
        elif u_type == "heavytransport":
            self.all_units.append(HeavyTransport(self, spawn_pos, team))
        elif u_type == "attackplane":
            self.all_units.append(AttackPlane(self, spawn_pos, team))
        elif u_type == "laserdestroyer":
            self.all_units.append(LaserDestroyer(self, spawn_pos, team))
        elif u_type == "antiairfrigate":
            self.all_units.append(AAFrigate(self, spawn_pos, team))
        elif u_type == "missilecruiser":
            self.all_units.append(MissileCruiser(self, spawn_pos, team))
        elif u_type == "megarocket":
            self.all_units.append(MegaRocket(self, spawn_pos, team))
        elif u_type == "tankcarrier":
            self.all_units.append(TankCarrier(self, spawn_pos, team))
            print("spawn")
        elif u_type == "harvester":
            # AI 补矿车走工厂排产（Building.update → spawn_unit）：home_building
            # 取就近源头建筑（排产的工厂）；家没了矿车会自寻 mining 建筑（见
            # Harvester.update 的兜底逻辑）
            self.all_units.append(Harvester(self, spawn_pos, team, source_building))


    def spawn_unit_by_name(self, class_name, pos, team, server_uid,target_pos):

        """
        根据类名字符串创建对应的单位实例，并强制覆盖为服务器指定的 UID。
        """
        new_u = None
        
        # --- 步兵 ---
        if class_name == "Rifleman":
            new_u = Rifleman(self, pos, team)
        elif class_name == "RocketTrooper":
            new_u = RocketTrooper(self, pos, team)
        elif class_name == "Engineer":
            # 工程师通常带有目标，这里仅做同步位置，目标可能需要额外处理或忽略
            # 为了防止报错，给个默认空目标位置
            new_u = Engineer(self, pos, team, pos) 
        elif class_name == "Shotgunner":
            new_u = Shotgunner(self, pos, team)
        # --- 地面载具 ---
        elif class_name == "ArmoredCar":
            new_u = ArmoredCar(self, pos, team)
        elif class_name == "M1A2":
            new_u = M1A2(self, pos, team)
        elif class_name == "Harvester":
            temp_base = self.player_base if self.player_base else self.all_buildings[0]
            new_u = Harvester(self, pos, team, temp_base)

        # --- 空中单位 ---
        elif class_name == "Helicopter":
            new_u = Helicopter(self, pos, team)
        elif class_name == "WZ10":
            new_u = WZ10(self, pos, team)
        elif class_name == "KirovAirship":
            new_u = KirovAirship(self, pos, team)

        elif class_name == "ArmoredTrain":
            from units import ArmoredTrain
            new_u = ArmoredTrain(self, pos)
        elif class_name == "TrainCarriage":
            from units import TrainCarriage
            new_u = TrainCarriage(self, pos, team, None, 0) 
        elif class_name == "Battleship":
            new_u = Battleship(self, pos, team)
        elif class_name == "ScavengerWalker":
            from units import ScavengerWalker
            new_u = ScavengerWalker(self, pos)        
        # --- 特殊单位 / 技能 ---
        elif class_name == "AC130":
            # AC130 需要 orbit_center，网络同步过来的是当前 pos
            # 我们可以把当前 pos 当作轨道中心（虽然会有误差，但在客户端仅作显示通常足够）
            new_u = AC130(self, pos, team)
        elif class_name == "CruiseMissile":
            new_u = CruiseMissile(self, pos, team)
        elif class_name == "ShipMissile":
            new_u = ShipMissile(self, pos, team)            
        elif class_name == "ParatrooperPlane":
            new_u = ParatrooperPlane(self, pos, team)
            new_u.pos = vec(pos) 
        elif class_name == "Sniper": new_u = Sniper(self, pos, team)
        elif class_name == "HeavyMech": new_u = HeavyMech(self, pos, team)
        elif class_name == "MissileBoat": new_u = MissileBoat(self, pos, team)
        elif class_name == "CombatEngineer":
            from units import CombatEngineer
            new_u = CombatEngineer(self, pos, team)
        elif class_name == "APC":
            from units import APC
            new_u = APC(self, pos, team)
        elif class_name == "Type99":
            from units import Type99
            new_u = Type99(self, pos, team)
        elif class_name == "HIMARS":
            from units import HIMARS
            new_u = HIMARS(self, pos, team)
        elif class_name == "Mi24":
            from units import Mi24
            new_u = Mi24(self, pos, team)
        elif class_name == "StealthHeli":
            from units import StealthHeli
            new_u = StealthHeli(self, pos, team)
        elif class_name == "DroneCarrier":
            from units import DroneCarrier
            new_u = DroneCarrier(self, pos, team)
        elif class_name == "SuicideDrone":
            from units import SuicideDrone
            new_u = SuicideDrone(self, pos, team)
        elif class_name == "TerminatorIFV":
            from units import TerminatorIFV
            new_u = TerminatorIFV(self, pos, team)
        elif class_name == "ShockwaveVehicle":
            from units import ShockwaveVehicle
            new_u = ShockwaveVehicle(self, pos, team)
        elif class_name == "FighterJet":
            new_u = FighterJet(self, pos, team)
        elif class_name == "HeavyTransport":
            new_u = HeavyTransport(self, pos, team)
        elif class_name == "AttackPlane":
            new_u = AttackPlane(self, pos, team)
        elif class_name == "AAFrigate":
            new_u = AAFrigate(self, pos, team)
        elif class_name == "LaserDestroyer":
            new_u = LaserDestroyer(self, pos, team)
        elif class_name == "MissileCruiser":
            new_u = MissileCruiser(self, pos, team)
        elif class_name == "MegaRocket":                 
            new_u = MegaRocket(self, pos, team, target_pos) 
        elif class_name == "TankCarrier":                 
            new_u = TankCarrier(self, pos, team) 
        elif class_name == "MCV":
            new_u = MCV(self, pos, team)
        if new_u:
            new_u.uid = server_uid  
            self.all_units.append(new_u)


    def spawn_building_instantly(self, b_type, pos, team):
        
        new_b = None
        if b_type == "factory": new_b = FactoryBuilding(self, pos, team)
        elif b_type == "radar": new_b = RadarBuilding(self, pos, team)
        elif b_type == "mining": new_b = MiningRig(self, pos, team)
        elif b_type == "airfield": new_b = Airfield(self, pos, team)
        elif b_type == "power_plant": new_b = PowerPlant(self, pos, team)
        elif b_type == "research": new_b = ResearchCenter(self, pos, team)
        elif b_type == "tech_center": new_b = TechCenter(self, pos, team)
        elif b_type == "aa_turret": new_b = AntiAirTurret(self, pos, team)
        elif b_type == "laser_turret": new_b = LaserTurret(self, pos, team)
        elif b_type == "missile_def": new_b = MissileDefenseSystem(self, pos, team)
        elif b_type == "bunker": new_b = Bunker(self, pos, team)
        elif b_type == "shroud_gen": new_b = ShroudGen(self, pos, team)
        elif b_type == "shipyard": new_b = Shipyard(self, pos, team)
        elif b_type == "prototype_gen": new_b = PrototypeGen(self, pos, team)
        elif b_type == "ciws": new_b = CIWS(self, pos, team)
        elif b_type == "barracks": new_b = Barracks(self, pos, team)
        if new_b:
            self.all_buildings.append(new_b)
            # 播放音效或特效
            from core.base_classes import FloatingText
            self.particles.add(FloatingText(pos, tr("w.constructed"), GREEN_HAT))


    def spawn_building_by_data(self, data):
        pos = vec(data['x'], data['y'])
        team = data['team']
        b_type = data['type'] # 建筑类型
        uid = data['uid']
        cls_name = data.get('cls', '')
        
        new_b = None
        # 根据 b_type 或 类名创建
        if b_type == "base": new_b = BaseBuilding(self, pos, team)
        elif b_type == "factory": new_b = FactoryBuilding(self, pos, team)
        elif b_type == "radar": new_b = RadarBuilding(self, pos, team)
        elif b_type == "mining": new_b = MiningRig(self, pos, team)
        elif b_type == "airfield": new_b = Airfield(self, pos, team)
        elif b_type == "research": new_b = ResearchCenter(self, pos, team)
        elif b_type == "missile_def": new_b = MissileDefenseSystem(self, pos, team)
        elif b_type == "aa_turret": new_b = AntiAirTurret(self, pos, team)
        elif b_type == "laser_turret": new_b = LaserTurret(self, pos, team)
        elif b_type == "bunker": new_b = Bunker(self, pos, team)        
        elif b_type == "house":
            from core.base_classes import CivilianHouse
            vid = data.get("vid", 0) # 获取 ID
            new_b = CivilianHouse(self, pos, variant_id=vid) 
        elif "OilDerrick" in cls_name: new_b = OilDerrick(self, pos)
        elif "MercenaryFactory" in cls_name: new_b = MercenaryFactory(self, pos)
        elif cls_name == "TeslaTower" or b_type == "tesla_tower": new_b = TeslaTower(self, pos)
        elif b_type == "power_plant":
            new_b = PowerPlant(self, pos, team)
        elif b_type == "shipyard":
            new_b = Shipyard(self, pos, team)
        elif b_type == "shroud_gen":
            new_b = ShroudGen(self, pos, team)
        elif  b_type== 'tech_center': 
            new_b = TechCenter(self, pos, team)
        elif cls_name == "CIWS" or b_type == "ciws":
            new_b = CIWS(self, pos,team)
        elif cls_name == "Barracks" or b_type == "barracks":
            new_b = Barracks(self, pos, team)
        if cls_name == "AncientTemple" or b_type == "temple":
            from core.base_classes import AncientTemple
            new_b = AncientTemple(self, pos)
        elif cls_name == "EMPGenerator":
            from core.base_classes import EMPGenerator
            new_b = EMPGenerator(self, pos)
        elif cls_name == "Lighthouse":
            
            new_b = Lighthouse(self, pos)
        # [修复] 确保 Skyscraper 也能被识别
        elif cls_name == "Skyscraper" or b_type == "skyscraper":
            from core.base_classes import Skyscraper
            new_b = Skyscraper(self, pos)
        elif cls_name == "CoastalGun" or b_type == "coastal_gun":
            new_b = CoastalGun(self, pos)
        elif cls_name == "Bastion" or b_type == "bastion":
            new_b = Bastion(self, pos)       
        elif cls_name == "PrototypeGen" or b_type == "prototype_gen":
            new_b = PrototypeGen(self, pos)    
        elif cls_name == "IronCurtain" or b_type == "iron_curtain":
            new_b = IronCurtain(self, pos)
        elif cls_name == "NukeSilo" or b_type == "nuke_silo":
            new_b = NukeSilo(self, pos)  
                                         
        elif cls_name == "CommStation" or b_type == "CommStation":
            from core.base_classes import CommStation
            new_b = CommStation(self, pos)
        extra = data.get('extra', {})
        
        if cls_name == "Bridge":
            from core.base_classes import Bridge
            orient = extra.get('orient', 'horizontal')
            length = extra.get('length')
            new_b = Bridge(self, pos, orient) if length is None else Bridge(self, pos, orient, length)
        if new_b:
            new_b.uid = uid # 覆盖ID
            new_b.hp = data['hp'] # 同步血量
            self.all_buildings.append(new_b)


    def upgrade_tech(self, tech_type):
        self.tech_levels[tech_type] += 1
        self.particles.add(FloatingText(self.player_base.pos, tr("w.upgraded", t=tech_type.upper()), YELLOW, 120))


    def spawn_engineer(self, target_pos, b_type):
        # 1. 确定出生点
        # 优先从基地出来，如果基地没了，就从初始点出来 (虽然没基地一般也造不了东西，但为了不崩)
        if self.player_base and self.player_base.alive:
            origin = self.player_base.pos
        else:
            origin = self.my_start_pos
            
        spawn_pos = origin + vec(0, 30)
        
        # 2. [修改] 传入正确的 team
        eng = Engineer(self, spawn_pos, self.my_team, target_pos)
        
        eng.target_type = b_type 
        self.all_units.append(eng)


    def issue_command(self, world_pos):
        target_entity = None
        
        my_team = self.my_team
        
        # 1. 搜索目标 (建筑)
        for b in self.all_buildings:
            # [修改] 只要不是我的队伍，且活着，就是潜在目标
            # 这包括 team="enemy" (对Client来说是Player) 和 team="neutral" (摩天大楼)
            if b.team != my_team and b.alive:
                if b.rect.collidepoint(world_pos):
                    target_entity = b
                    break
        
        # 2. 搜索目标 (单位)
        if not target_entity:
            for u in self.all_units:
                if u.team != my_team and u.rect.collidepoint(world_pos) and u.alive:
                    target_entity = u
                    break
        
        # 3. 执行指令
        if target_entity:
            # 如果选中了单位
            if self.selected_entity:
                # 检查防空
                if target_entity.is_air and not getattr(self.selected_entity, 'can_attack_air', False):
                    self.selected_entity.move_to(target_entity.pos)
                else:
                    if isinstance(u, CombatEngineer):
                        u.set_target(target_entity)
                    else:
                        self.selected_entity.set_target(target_entity)
        else:
            # 地面移动
            if self.selected_entity:
                self.selected_entity.move_to(world_pos)

