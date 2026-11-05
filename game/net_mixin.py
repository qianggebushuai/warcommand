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

class NetMixin:
    def sync_client_state(self, snapshot):
        # 1. 同步资源
        if 'res' in snapshot:
            self.team_resources = snapshot['res']

        # 1.5 [红警式矿脉] 同步矿脉储量（按索引回写，几何由 seed 确定性生成保持一致）
        if 'ore' in snapshot and self.current_map is not None:
            patches = getattr(self.current_map, 'ore_patches', None)
            if patches:
                for idx, amt in snapshot['ore']:
                    if 0 <= idx < len(patches):
                        patches[idx].amount = float(amt)

        # 2. 同步子弹
        self.projectiles = [] 
        if 'projs' in snapshot:
            for p_data in snapshot['projs']:
                # [关键] 读取 bsv
                bsv = p_data.get('bsv', 0)
                
                # 创建对象 (使用关键字参数防止错位)
                p = Projectile(
                    game=self, 
                    pos=vec(p_data['x'], p_data['y']), 
                    target=None, # Client 不保存 target 引用
                    team="neutral", 
                    damage=0, 
                    d_type=p_data['type'],
                    breakshellvalue=bsv # 传入等级
                )
                if 'lt' in p_data: p.life_time = p_data['lt']
                if 'ml' in p_data: p.max_life = p_data['ml']                
                if "tx" in p_data:
                    p.target_dest = vec(p_data["tx"], p_data["ty"])
                
                self.projectiles.append(p)
        # 3. 同步单位
        server_uids = set()
        
        # [第一步] 更新或生成存在的单位
        for data in snapshot['units']:
            uid = data['uid']
            server_uids.add(uid)
            
            found_unit = None
            for u in self.all_units:
                if u.uid == uid:
                    found_unit = u
                    break
            
            if found_unit:
                u = found_unit
                # 更新属性
                u.team = data['team']
                u.pos = vec(data['x'], data['y'])
                u.hp = data['hp']
                u.shield = data['sh']
                u.max_shield = data['msh']
                if 'angle' in data: u.angle = data['angle']
                if 'ta' in data: u.turret_angle = data['ta']
                u.update_rect()
                if "st" in data: 
                    u.state = data["st"]
                    u.deploy_timer = data.get("dt", 0)
                    u.pack_timer = data.get("pt", 0)
                if "bt" in data:
                    u.build_timer = data["bt"]
                    if "btt" in data: u.build_time_total = data["btt"]
                    u.is_building = (u.build_timer > 0)
                
                if u.__class__.__name__ == "DroneCarrier":
                    if 'st_c' in data: u.carrier_state = data['st_c']
                elif u.__class__.__name__ == "StealthHeli":
                    if 'st_h' in data:
                        u.stealth_mode = data['st_h']
                        u.is_stealth = u.stealth_mode
                elif u.__class__.__name__ == "APC":
                    if 'rep' in data: u.is_repairing = data['rep']
                elif u.__class__.__name__ == "TerminatorIFV":
                    if 'ph' in data: u.phase = data['ph']
                elif u.__class__.__name__ == "ShockwaveVehicle":
                    if 'sc' in data: u.shock_cooldown = data['sc']
                elif u.__class__.__name__ == "AC130":
                    if 'ox' in data: u.orbit_center = vec(data['ox'], data['oy'])
                    if 'oa' in data: u.orbit_angle = data['oa']
                    if 'ar' in data:
                        u.attack_radius = data['ar']
                        u.orbit_radius = u.attack_radius * 2
                    if 'st_a' in data: u.state = data['st_a']
                elif u.__class__.__name__ == "FighterJet":
                    if 'ammo' in data: 
                        u.ammo = data['ammo']
                    if 'st_f' in data: 
                        u.state = data['st_f']
                elif u.__class__.__name__ == "AttackPlane":
                    if 'bomb' in data: 
                        u.has_bomb = data['bomb']
                    if 'st_f' in data: 
                        u.state = data['st_f']
                elif u.__class__.__name__ == "LaserDestroyer":
                    if 'cl' in data: u.charge_level = data['cl']
                elif u.__class__.__name__ == "ShipMissile":
                    if 'wob' in data: u.wobble_timer=data['wob']
                elif u.__class__.__name__ == "MegaRocket":
                    if "tx" in data and "ty" in data:
                        u.target_dest = vec(data["tx"], data["ty"])  
                elif u.__class__.__name__ == "TankCarrier":
                    has_tank = data.get("lt", False)
                    
                    if has_tank:
                        if not u.loaded_tank:
                            u.loaded_tank = True 
                        if 'tta' in data:
                            u.turret_angle = data['tta']
                    else:
                        u.loaded_tank = None            
            else:
                self.spawn_unit_by_name(data['cls'], vec(data['x'], data['y']), data['team'], uid,target_pos=(1000,1000))

        for u in self.all_units[:]:
            if u.uid not in server_uids:
                self.all_units.remove(u)
        server_b_uids = set()
        if 'buildings' in snapshot:
            for b_data in snapshot['buildings']:
                uid = b_data['uid']
                server_b_uids.add(uid)
                
                found_b = None
                for b in self.all_buildings:
                    if b.uid == uid:
                        found_b = b
                        break
                
                # [优化] 如果没找到，先生成，然后统一走更新逻辑
                if not found_b:
                    found_b = self.spawn_building_by_data(b_data)
                
                if found_b:
                    found_b.hp = b_data['hp']
                    found_b.team = b_data['team'] 
                    found_b.progress = b_data.get('prog', 0.0)
                    if 'cap' in b_data: found_b.capture_progress = b_data['cap']
                    if 'ang' in b_data: found_b.angle = b_data['ang'] # 移动到这里通用
                    
                    found_b.synced_queue_len = b_data.get('q_len', 0)
                    found_b.is_upgraded = b_data.get('upg', False)

                    # 2. 倒塌状态
                    if b_data.get('collapsed', False) and not getattr(found_b, 'is_collapsed', False):
                        if hasattr(found_b, 'start_collapse'): found_b.start_collapse()

                    # 3. 特殊建筑逻辑
                    b_type = getattr(found_b, 'b_type', '')
                    
                    if b_type == 'bastion' and 't_angs' in b_data:
                        if hasattr(found_b, 'turrets'):
                            for i, angle in enumerate(b_data['t_angs']):
                                if i < len(found_b.turrets):
                                    found_b.turrets[i]['angle'] = angle
                                    
                    if b_type == "prototype_gen":
                        found_b.loaded_weapon = b_data.get("lw")
                        found_b.charge_timer = b_data.get("ct")
                        found_b.charge_time_total = b_data.get("ctt")
                        found_b.is_ready = b_data.get("rdy", False)
                        
                        # 同步武器对象 (同上文修正)
                        if found_b.loaded_weapon:
                            if not found_b.weapon_obj or found_b.weapon_obj.b_type != found_b.loaded_weapon:
                                if found_b.loaded_weapon == "iron_curtain":
                                    found_b.weapon_obj = IronCurtain(self, found_b.pos, found_b.team, found_b)
                                elif found_b.loaded_weapon == "nuke_silo":
                                    found_b.weapon_obj = NukeSilo(self, found_b.pos, found_b.team, found_b)
                        else:
                            found_b.weapon_obj = None

            for b in self.all_buildings[:]:
                if b.uid not in server_b_uids:
                    # [修复] 摩天大楼和寺庙废墟不移除
                    if hasattr(b, 'b_type') and b.b_type in ["skyscraper", "temple"]: continue
                    self.all_buildings.remove(b)
                if hasattr(b, 'b_type') and b.b_type == "laser_turret" and 't_uids' in b_data:
                    # 根据 UID 列表重建 targets 列表
                    b.targets = []
                    for tid in b_data['t_uids']:
                        for u in self.all_units:
                            if u.uid == tid: b.targets.append(u); break

        # 5. 同步特效
        if 'fx' in snapshot:
            for evt in snapshot['fx']:
                if evt['type'] == 'EXPLOSION':
                    pos = vec(evt['x'], evt['y'])
                    d_type = evt.get('dt', 'normal')

                    if d_type == "heavy_shell":
                        for i in range(12):
                            Particle(self.particles, pos, (200, 200, 255), 4, 30, 8) # 蓝白冲击波
                        # 火球
                        for _ in range(20): 
                            Particle(self.particles, pos, ORANGE, random.uniform(2, 5), 50, 12)
                        # 烟雾
                        for _ in range(15): 
                            Particle(self.particles, pos, (80, 80, 80), random.uniform(1, 3), 80, 15)                   
                    elif d_type == "ac130":
                        # AC130 机炮/榴弹落点：榴弹（AOE≥80）还原大范围爆炸
                        spawn_ac130_impact_fx(self.particles, pos, evt.get('ar', 40) >= 80)
                    elif d_type == "behemoth_bomb" or d_type == "missile":
                        for i in range(36):
                            angle = i * 10
                            speed = 6
                            vel = vec(speed, 0).rotate(angle)
                            Particle(self.particles, pos, WHITE, speed, 40, 10)
                        for _ in range(40): Particle(self.particles, pos, ORANGE, random.uniform(1, 4), 60, 15)
                        for _ in range(20): Particle(self.particles, pos, (50, 50, 50), random.uniform(2, 5), 80, 20)
                    elif d_type == "rocket" :
                        for _ in range(15): Particle(self.particles, pos, ORANGE, random.uniform(2, 5), 30, 6)
                        for _ in range(10): Particle(self.particles, pos, (50, 50, 50), random.uniform(1, 3), 40, 8)                        
                    elif d_type == "tank_shell" or d_type == "heavy":
                        for _ in range(8): Particle(self.particles, pos, ORANGE, 2, 20, 4)
                    elif d_type == "launch_smoke":
                        for _ in range(5):
                            Particle(self.particles, pos, (255, 200, 50), 2, 20, 8)
                        # 发射烟雾 
                        for _ in range(8):
                            p = Particle(self.particles, pos, (200, 200, 200, 150), 1, 60, 10)
                            p.vel = vec(random.uniform(-1,1), random.uniform(-1,1))
                    elif d_type == "mech_death" or d_type == "air_crash":
                        count = 15
                        color = ORANGE
                        speed = 3 
                        size = 5 
                        for _ in range(count):
                            Particle(self.particles, pos, color, random.uniform(0.5, speed), random.randint(20, 40), size)
                        for _ in range(5): Particle(self.particles,pos, (50, 50, 50), 1, 60, 6)
                    elif d_type == "normal":
                        count =  10
                        color = RED
                        speed = 1.5
                        size =  3
                        for _ in range(count):
                            Particle(self.particles, pos, color, random.uniform(0.5, speed), random.randint(20, 40), size)
                    else:
                        for _ in range(3): Particle(self.particles, pos, WHITE, 1, 15, 2)
                    
                    if d_type == "intercept":
                         Particle(self.particles, pos, CYAN, 0, 10, 10)
                if evt['type'] == 'FX_TARGET_LOCK':
                    pos = vec(evt['x'], evt['y'])
                    duration = evt.get('duration', 300)
                    from core.base_classes import TargetMarker
                    self.particles.add(TargetMarker(self, pos, duration))
                if evt['type'] == 'FX_SHOCKWAVE':
                    pos = vec(evt['x'], evt['y'])
                    base_angle = evt.get('angle', 0)
                    
                    for i in range(18): 
                        angle = base_angle - 90 + i * 10
                        vel = vec(5, 0).rotate(angle) # 注意这里是否需要负号，取决于 draw
                        Particle(self.particles, pos, (0, 255, 255), 5, 30, 5)
                if evt['type'] == 'FX_TEXT':
                    pos = vec(evt['x'], evt['y'])
                    text = evt['text']
                    
                    c_map = {"RED": RED, "CYAN": CYAN, "GREEN": GREEN_HAT, "YELLOW": YELLOW}
                    color = c_map.get(evt['color'], WHITE)
                    
                    self.particles.add(FloatingText(pos, text, color))
        # 6. 同步胜负状态
        if snapshot.get("game_over"):
            self.game_over = True
            self.winner = snapshot["winner"]
            self.state = "GAMEOVER"
            self.game_over_timer = 1800 
        #7. 同步音乐状态
        if "music_state" in snapshot:
            server_music_state = snapshot["music_state"]
            
            if not hasattr(self, 'current_music_state'):
                self.current_music_state = "MENU"
            
            if self.current_music_state != server_music_state:
                self.current_music_state = server_music_state
        if not self.has_received_first_snapshot and self.player_base:
            print("[Client] First Snapshot Received -> Init Camera")
            
            self.has_received_first_snapshot = True
            if self.state == "PLAYING" and not self.opening_animation_done:
                pass


    def handle_online_playing(self):
        current_time = pygame.time.get_ticks()
        if not self.net.connected: # 简化超时判断
            self.state = "LOGIN"; self.reset_lobby_data(); return

        msgs = self.net.get_messages()
        if msgs: self.last_packet_time = current_time
        
        if self.my_role == "HOST":

            for msg in msgs:
                sender_addr = msg.get('_sender')
                # 如果 sender_addr 为空或不在表中，默认是 Host 自己 (team_0)
                # 注意：如果 Host 是单机调试网络功能，可能 sender_addr 为 None
                team_id = self.client_id_to_team.get(sender_addr, "team_0")
                if msg['type'] == 'CHAT':
                    self.chat_box.add_message(msg['text'], msg.get('name', 'Unknown'))
                
                # 移动/攻击/特殊操作
                elif msg['type'] == 'REQ_MOVE':
                    uids = msg['uids']
                    
                    # [必须加上这行]
                    target = vec(msg['x'], msg['y'])
                    for u in self.all_units:
                        if u.uid in msg['uids']:
                            print(f" - Found unit {u.uid}, Team: {u.team}")
                            if u.team == team_id: 
                                u.move_to(target)
                            else:
                                print(f" - [Reject] Team mismatch! Unit: {u.team}, Client: {team_id}")
                elif msg['type'] == 'REQ_ATTACK':
                    target = None
                    for x in self.all_units + self.all_buildings:
                        if x.uid == msg['target_uid']: target = x; break
                    
                    if target:
                        # [必须修改] 把 all_buildings 也加进去
                        all_commandable = self.all_units + self.all_buildings
                        
                        for u in all_commandable:
                            if u.uid in msg['uids'] and u.team == team_id:
                                if hasattr(u, 'set_target'):
                                    u.set_target(target)
                elif msg['type'] == 'REQ_SPAWN':
                    cost_map = {
                        "rifleman": RIFLEMAN_COST, "rocket": ROCKET_COST, "shotgunner": SHOTGUNNER_COST,"sniper": SNIPER_COST,
                        "armored": ARMORED_COST, "m1a2": M1A2_COST, "mech": MECH_COST,
                        "helicopter": HELICOPTER_COST, "wz10": WZ10_COST, "kirov": KIROV_COST,
                        "missile_boat": 600, "combat_engineer": 150, "apc": APC_COST,
                        "type99": TYPE99_COST, "himars": HIMARS_COST, "mi24": HIND_COST,
                        "dronecarrier": DRONECARRIER_COST, "stealheli": STEALHELI_COST, "bmpt": TERMINATOR_COST,"waver":SHOCKWAVE_COST,"fighterjet":FIGHTER_COST,"heavytransport":HEAVYTRANSPORT_COST,
                        "attackplane":ATTACKER_COST,"antiairfrigate":AABOAT_COST,"laserdestroyer":LASER_SHIP_COST,"missilecruiser":MissileCruiser_COST,"tankcarrier":TANKCARRIER_COST,
                    }
                    cost = cost_map.get(msg['u_type'], 0)
                    
                    if self.team_resources[team_id] >= cost:
                        b_uid = msg.get('b_uid')
                        target_building = None
                        if b_uid:
                            for b in self.all_buildings:
                                if b.uid == b_uid: target_building = b; break
                        
                        if target_building and target_building.team == team_id and hasattr(target_building, 'queue_unit'):
                            time_cost = BUILD_TIME_INFANTRY
                            u_type = msg['u_type']
                            if u_type in ["armored", "m1a2", "mech", "type99", "himars"]: time_cost = BUILD_TIME_TANK
                            elif u_type in ["helicopter", "wz10", "mi24","stealheli","heavytransport","fighterjet","attackplane"]: time_cost = BUILD_TIME_AIR
                            elif u_type == "kirov": time_cost = BUILD_TIME_AIRSHIP
                            elif u_type == "rifleman": time_cost = BUILD_TIME_INFANTRY
                            elif u_type == "rocket": time_cost = BUILD_TIME_INFANTRY*2
                            elif "shotgunner" in u_type: time_cost =  BUILD_TIME_INFANTRY*3
                            elif u_type == "harvester": time_cost = BUILD_TIME_HARVESTER
                            else: time_cost = BUILD_TIME_TANK                           
                            if target_building.queue_unit(msg['u_type'], time_cost):
                                self.team_resources[team_id]  -= cost

                        else:
                            self.team_resources[team_id] -= cost
                            self.spawn_unit(msg['u_type'], vec(msg['x'], msg['y']),team_id)
                
                elif msg['type'] == 'REQ_BUILD':
                    b_type = msg['b_type']
                    cost_map = {
                        "factory": FACTORY_COST, "radar": RADAR_COST, "mining": MINING_COST, 
                        "airfield": AIRFIELD_COST, "research": RESEARCH_COST, 
                        "missile_def": MISSILE_DEFENSE_COST, "aa_turret": AA_TURRET_COST, 
                        "laser_turret": LASER_TURRET_COST, "power_plant": POWER_PLANT_COST,
                        "shipyard": SHIPYARDCOST, "tech_center": TECH_CENTER_COST,"bunker":BUNKER_COST,
                        "shroud_gen":BLACKSHRODCOST,"prototype_gen":PROTOTYPECOST,"ciws":CIWS_COST,
                        "barracks": BARRACKS_COST
                    }
                    cost = cost_map.get(msg['b_type'], 0)

                    if self.team_resources[team_id] >= cost:
                        self.team_resources[team_id] -= cost
                        
                        if msg['b_type'] == "shipyard":
                            from core.base_classes import Shipyard
                            self.all_buildings.append(Shipyard(self, vec(msg['x'], msg['y']), team_id))
                        else:
                            spawn_origin = vec(0, 0)
                            found_origin = False
                            
                            dependency_map = {
                                "laser_turret": "research", 
                                "aa_turret": "radar",          
                                "missile_def": "radar",
                                "shroud_gen": "research",
                                "ciws":"research"
                                
                            }
                            
                            required_origin_type = dependency_map.get(b_type, "base") # 默认为 base
                            
                            candidates = []
                            for b in self.all_buildings:
                                if b.team == team_id and b.alive and getattr(b, 'b_type', '') == required_origin_type:
                                    candidates.append(b)
                            
                            if candidates:
                                print(f"[Build] No candidate found for {required_origin_type}, fallback to base.")
                                target_pos = vec(msg['x'], msg['y'])
                                best_b = min(candidates, key=lambda b: b.pos.distance_to(target_pos))
                                spawn_origin = best_b.pos
                                found_origin = True
                            else:
                                print(f"[Build] No candidate found for {required_origin_type}, fallback to base.")
                            if not found_origin:
                                # 回退到找基地
                                if team_id in self.bases and self.bases[team_id].alive:
                                    spawn_origin = self.bases[team_id].pos
                                else:
                                    # 基地也没了? 随便找个活着的建筑
                                    any_b = next((b for b in self.all_buildings if b.team == team_id and b.alive), None)
                                    if any_b: spawn_origin = any_b.pos
                            
                            # 生成工程师
                            eng = Engineer(self, spawn_origin, team_id, vec(msg['x'], msg['y']))
                            eng.target_type = b_type
                            self.all_units.append(eng)
                elif msg['type'] == 'REQ_BUILD_INSTANT':
                    b_type = msg['b_type']
                    pos = vec(msg['x'], msg['y'])
                    
                    self.spawn_building_instantly(b_type, pos, team_id)               
                elif msg['type'] == 'REQ_BUILD_PROTOTYPE':
                    p_type = msg['p_type'] 
                    cost_map = {
                        "iron_curtain": 2500,
                        "nuke_silo": 3000
                    }
                    cost = cost_map.get(p_type, 99999)
                    
                    # 1. 检查资金
                    if self.team_resources[team_id] >= cost:
                        
                        # 2. 寻找一个属于该玩家且空闲的 PrototypeGen
                        target_gen = None
                        for b in self.all_buildings:
                            if b.team == team_id and getattr(b, 'b_type', '') == 'prototype_gen':
                                # 必须没有挂载武器
                                if not getattr(b, 'loaded_weapon', None):
                                    target_gen = b
                                    break
                        
                        if target_gen:
                            # 扣钱
                            self.team_resources[team_id] -= cost
                            target_gen.build_prototype(p_type)
                        else:
                            pass
                elif msg['type'] == 'REQ_UPGRADE':
                    tech = msg['tech']
                    cost = 0
                    if tech == "airfield_unlock": cost = UPGRADE_AIRFIELD_COST
                    elif tech == "factory_unlock": cost = UPGRADE_FACTORY_COST
                    if cost > 0 and self.team_resources[team_id] >= cost:
                        for b in self.all_buildings:
                            # 必须是该队伍的建筑
                            if b.uid == msg['uid'] and b.team == team_id: 
                                b.is_upgraded = True
                                self.team_resources[team_id] -= cost
                                break
                
                elif msg['type'] == 'REQ_SUPPORT':
                    s_type = msg['s_type']; pos = vec(msg['x'], msg['y'])
                    cost = 0
                    if s_type == "ac130": cost = AC130_COST
                    elif s_type == "missile": cost = MISSILE_COST
                    elif s_type == "airdrop": cost = AIRDROP_COST
                    if self.team_resources[team_id] >= cost:
                        self.team_resources[team_id] -= cost
                        if s_type == "ac130": self.all_units.append(AC130(self, pos, team_id))
                        elif s_type == "missile": self.all_units.append(CruiseMissile(self, pos, team_id))
                        elif s_type == "airdrop": self.all_units.append(ParatrooperPlane(self, pos, team_id))                    
                    if s_type == "battleship_call":
                        # 不需要扣钱，直接调用
                        self.handle_battleship_call(team_id)    
            
                elif msg['type'] == 'REQ_SELL':
                    for b in self.all_buildings:
                        if b.uid == msg['uid'] and b.team == team_id: # 只能卖自己的
                            b.alive = False
                            self.team_resources[team_id] += msg['refund']
                            break
                
                elif msg['type'] == 'REQ_DEPLOY':
                    for u in self.all_units:
                        if u.uid == msg['uid']:
                            if u.team == team_id:
                                if u.alive and isinstance(u, MCV):
                                    success = u.deploy()
                                    if success:
                                        print(f"[Host] Team {team_id} deployed MCV {u.uid}")
                                    else:
                                        pass
                            else:
                                print(f"[Host Warning] Team {team_id} tried to deploy {u.team}'s MCV!")
                            break                
                elif msg['type'] == 'REQ_UNDEPLOY':
                    for b in self.all_buildings:
                        # [修正] 增加队伍检查，防止收起别人的基地
                        if b.uid == msg['uid'] and b.team == team_id and b.alive: 
                            b.undeploy()
                            print(f"[Host] Team {team_id} undeployed Base {b.uid}")
                            break
                
                elif msg['type'] == 'REQ_APC_LOAD':
                    for u in self.all_units:
                        if u.uid == msg['uid'] and u.team == team_id and isinstance(u, APC): u.load_units(); break
                
                elif msg['type'] == 'REQ_APC_UNLOAD':
                    for u in self.all_units:
                        if u.uid == msg['uid'] and u.team == team_id and isinstance(u, APC): u.unload_units(); break  
                elif msg['type'] == 'REQ_TANKCARRIER_LOAD':
                    for u in self.all_units:
                        if u.uid == msg['uid'] and u.team == team_id and isinstance(u, TankCarrier): u.load_units(); break   
                elif msg['type'] == 'REQ_TANKCARRIER_UNLOAD':
                    for u in self.all_units:
                        if u.uid == msg['uid'] and u.team == team_id and isinstance(u,TankCarrier ): u.unload_units(); break       
                elif msg['type'] == 'REQ_HEAVYTRANSPORT_LOAD':
                    for u in self.all_units:
                        if u.uid == msg['uid'] and u.team == team_id and isinstance(u, HeavyTransport): u.load_units(); break
                
                elif msg['type'] == 'REQ_HEAVYTRANSPORT_UNLOAD':
                    for u in self.all_units:
                        if u.uid == msg['uid'] and u.team == team_id and isinstance(u,HeavyTransport): u.unload_units(); break                          
                elif msg['type'] == 'REQ_TOGGLE':
                    for u in self.all_units:
                        # 必须检查 UID 和 Team (防止控制别人的兵)
                        if u.uid == msg['uid'] and u.team == team_id:
                            if hasattr(u, 'toggle_mode'):
                                u.toggle_mode()
                            break            
                elif msg['type'] == 'REQ_SKILL': # 合并后的通用类型
                    uid = msg['uid']
                    target_pos = vec(msg['x'], msg['y'])
                    skill_type = msg.get('skill', None) 
                    
                    found = False
                    
                    for u in self.all_units:
                        if u.uid == uid and u.team == team_id and u.alive:
                            if u.__class__.__name__ == "MissileCruiser":
                                u.start_charge(target_pos)
                                found = True
                            break
                    
                    if not found:
                        for b in self.all_buildings:
                            if b.uid == uid and b.team == team_id and b.alive:
                                if getattr(b, 'b_type', '') == 'prototype_gen' and b.weapon_obj:
                                    current_weapon = b.loaded_weapon 

                                    if skill_type and current_weapon in skill_type:
                                        b.weapon_obj.activate(target_pos)
                                        found = True
                                break
                elif msg['type'] == 'REQ_REBUILD_BASE':
                    cost = 5000
                    if self.team_resources[team_id] >= cost:
                        self.team_resources[team_id] -= cost
                        
                        from core.base_classes import BaseBuilding
                        
                        spawn_pos = vec(WORLD_WIDTH // 2, WORLD_HEIGHT // 2)                        
                        
                        new_base = BaseBuilding(self, spawn_pos, team_id)
                        self.all_buildings.append(new_base)

                        if not hasattr(self, 'bases'): self.bases = {}
                        self.bases[team_id] = new_base
                        
                        print(f"[Host] Team {team_id} rebuilt base at {spawn_pos}")

            self.update_game_world()
            
            for tid in self.team_resources:
                if self.team_resources[tid] < self.max_cmd_exp:
                    self.team_resources[tid] += self.current_income_rate
            

            self.send_snapshot()

        elif self.my_role == "CLIENT":
            for msg in msgs:
                if msg['type'] == 'CHAT':
                    self.chat_box.add_message(msg['text'], msg.get('name', 'Unknown'))
                elif msg['type'] == 'SNAPSHOT':
                    self.sync_client_state(msg)
            self.update_game_world()            
            self.particles.update()
            self.floating_texts.update()
            
            # [修复 3] 客户端移除旧的胜负判定，完全依赖 Host 的 Snapshot
            if self.game_over:
                self.state = "GAMEOVER"


    def handle_setup_packet(self, msg):

        if 'lakes_data' in msg: self.synced_lakes = msg['lakes_data']
        random.seed(msg.get('seed', 0))
        self.map_seed = msg.get('seed', 0)
        self.map_id = msg.get('map_id', 0)
        
        # [修改] 接收多人信息
        self.my_team = msg.get('your_team') # 默认 team_1
        self.teams_config = msg.get('teams_config', {})
        if self.my_team is None:
            print("[Client] ERROR: Host did not assign a team!")
            self.my_team = "team_1" # 强行修补 (不推荐，但能救急)        
        # 从 config 中提取自己的 faction 用于 UI 显示
        if self.my_team in self.teams_config:
            self.my_faction = self.teams_config[self.my_team]['faction']
        print(f"[Client] My Team is: {self.my_team}")        
        # enemy_faction 不再单一，可以设为 None 或显示列表
        # self.enemy_faction = ... 
        
        self.reset_game()
        self.state = "LOADING"


    def send_snapshot(self):
        # 1. 建筑数据
        buildings_data = []
        for b in self.all_buildings:
            progress = 0.0
            
            # 计算生产进度 (工厂/机场)
            if hasattr(b, 'current_production') and b.current_production:
                total = b.current_production['total_time']
                current = b.current_production['timer']
                if total > 0: progress = (total - current) / total           
            # 计算建造进度 (工程师正在建造的地基? 不，这里通常是 Unit 的属性)
            # 如果有 spawn_timer (如油井生产资源，或者旧版逻辑)
            elif hasattr(b, 'spawn_timer') and hasattr(b, 'build_time_total') and b.build_time_total > 0:
                 progress = b.spawn_timer / b.build_time_total
            
            cap_prog = getattr(b, 'capture_progress', 0.0)
            
            # 额外数据 (桥梁方向+跨度)
            extra = {}
            if getattr(b, 'b_type', '') == 'bridge':
                extra['orient'] = getattr(b, 'orientation', 'horizontal')
                extra['length'] = getattr(b, 'length', None)
            q_len = len(b.production_queue) if hasattr(b, 'production_queue') else 0
            if getattr(b, 'current_production', None):
                q_len += 1
            b_data = {
                "uid": b.uid,
                "cls": b.__class__.__name__,
                "type": getattr(b, 'b_type', 'unknown'),
                "team": b.team,
                "x": int(b.pos.x), "y": int(b.pos.y),
                "hp": b.hp,
                "prog": progress,
                "cap": cap_prog,
                "extra": extra,
                "collapsed": getattr(b, 'is_collapsed', False),
                "upg": getattr(b, 'is_upgraded', False),
                "q_len": q_len,
    
            }
            b_type = getattr(b, 'b_type', '')
            

            if b_type in ["bunker", "aa_turret", "coastal_gun","ciws"]:
                b_data["ang"] = getattr(b, 'angle', 0) 
            if b_type in ["bastion"]:
                if hasattr(b, 'turrets'):
                    turret_angles = [t['angle'] for t in b.turrets]
                    b_data["t_angs"] = turret_angles                
            if b.b_type == "house":
                b_data["gc"] = len(b.garrison)     
            if b.b_type == "lighthouse":
                b_data["gc"] = len(b.garrison)  
            if b.b_type == "laser_turret":
                b_data["t_uids"] = [t.uid for t in b.targets]
            if b.b_type == "prototype_gen":
                b_data["lw"] = getattr(b, 'loaded_weapon', None)
                b_data["ct"] = getattr(b, 'charge_timer', 0)
                b_data["ctt"] = getattr(b, 'charge_time_total', 0)
                b_data["rdy"] = getattr(b, 'is_ready', False)
            if getattr(b, 'b_type', '') == "house":
                b_data["vid"] = getattr(b, 'variant_id', 0)

            buildings_data.append(b_data)        
        # 2. 单位数据
        units_data = []
        for u in self.all_units:
            u_data = {
                "uid": u.uid, "cls": u.__class__.__name__, "team": u.team, 
                "x": int(u.pos.x), "y": int(u.pos.y), "hp": u.hp, "angle": getattr(u, 'angle', 0),"ta": getattr(u, 'turret_angle', 0), "sh": getattr(u, 'shield', 0),
                "msh": getattr(u, 'max_shield', 0),
            }
            if u.__class__.__name__ == "Harvester":
                u_data["st"] = getattr(u, 'state', "IDLE")
            if u.__class__.__name__ == "DroneCarrier":
                u_data["st_c"] = getattr(u, 'carrier_state', "MOBILE")
            if u.__class__.__name__ == "APC":
                u_data["rep"] = getattr(u, 'is_repairing', False)            
            if u.__class__.__name__ == "StealthHeli":
                u_data["st_h"] = getattr(u, 'stealth_mode', True) 
            if u.__class__.__name__ == "ShockwaveVehicle":
                u_data["sc"] = getattr(u, 'shock_cooldown', 0)  
            if u.__class__.__name__ == "AC130":
                u_data["ox"] = int(u.orbit_center.x)
                u_data["oy"] = int(u.orbit_center.y)
                u_data["oa"] = u.orbit_angle
                u_data["ar"] = u.attack_radius  # 攻击半径（编辑器可配）
                u_data["st_a"] = u.state # 状态也同步
            if u.__class__.__name__ == "LaserDestroyer":
                u_data["cl"] = getattr(u, 'charge_level', 0)
            if u.__class__.__name__ == "FighterJet":
                u_data["bomb"] = getattr(u, 'has_bomb', False)  
                u_data["st_f"] = getattr(u, 'state', "ORBITING") 
            if u.__class__.__name__ == "AttackPlane":
                u_data["bomb"] = getattr(u, 'has_bomb', False)  
                u_data["st_f"] = getattr(u, 'state', "ORBITING")            
            if u.__class__.__name__ == "ShipMissile":
                u_data["wob"] = getattr(u, 'wobble_timer', 0)  
            if u.__class__.__name__ == "MegaRocket":
                # 获取目标点
                td = getattr(u, 'target_dest', None)
                if td:
                    # 拆解为基本类型 (int 或 float)
                    u_data["tx"] = int(td.x)
                    u_data["ty"] = int(td.y)
                else:
                    # 默认值
                    u_data["tx"] = 0
                    u_data["ty"] = 0 
            if u.__class__.__name__ == "TankCarrier":
                u_data["lt"] = bool(u.loaded_tank)
                if u.loaded_tank:
                    u_data["tta"] = getattr(u, 'turret_angle', 0)                       
            if isinstance(u, Engineer): 
                u_data["bt"] = u.build_timer
                u_data["btt"] = u.build_time_total
            
            if isinstance(u, HIMARS):
                u_data["st"] = u.state
                u_data["dt"] = u.deploy_timer
                u_data["pt"] = u.pack_timer
                
            units_data.append(u_data)

        # 3. 投射物数据
        projs_data = []
        for p in self.projectiles:
            p_data = {
                "x": int(p.pos.x), 
                "y": int(p.pos.y), 
                "type": p.d_type,
                "bsv": getattr(p, 'breakshellvalue', 0),
                "lt": getattr(p, 'life_time', 0),
                "ml": getattr(p, 'max_life', 0)
            }
            
            # [新增] 同步目标位置 (用于激光和导弹绘制)
            if p.target:
                p_data["tx"] = int(p.target.pos.x)
                p_data["ty"] = int(p.target.pos.y)
            elif p.target_dest:
                p_data["tx"] = int(p.target_dest.x)
                p_data["ty"] = int(p.target_dest.y)
                
            projs_data.append(p_data)

        # 4. 构建并发送
        # [红警式矿脉] 主机权威：同步各矿脉当前储量（按索引，双端几何一致）
        ore_data = []
        for i, p in enumerate(getattr(self.current_map, 'ore_patches', []) or []):
            ore_data.append([i, int(p.amount)])
            
        snapshot = {
            "type": "SNAPSHOT",
            "units": units_data,
            "buildings": buildings_data,
            "projs": projs_data,
            "fx": list(self.net_events), 
            "msgs": self.broadcast_msgs,
            
            # [修改] 直接发送完整的资源字典
            "res": self.team_resources, 
            
            "ore": ore_data,
            
            "game_over": self.game_over,
            "winner": self.winner,
            "music_state": getattr(self, 'current_music_state', 'MENU') 
        }
        self.net.send(snapshot)
        
        # 5. 清理一次性数据
        self.net_events = [] 
        self.broadcast_msgs = []


    def handle_lobby_network(self):
        msgs = self.net.get_messages()
        for msg in msgs:
            if msg['type'] == 'CHAT':
                self.chat_box.add_message(msg['text'], msg['team'])
            
            # Host 逻辑
            if self.my_role == "HOST":
                if msg['type'] == 'JOIN_REQUEST':
                    # 将玩家加入列表
                    new_player = {"id": msg['_sender'], "name": msg['name'], "ready": False}
                    self.lobby_players.append(new_player)
                    # 广播更新
                    self.broadcast_lobby_state()
                
                elif msg['type'] == 'LOBBY_READY':
                    # 更新玩家准备状态
                    for p in self.lobby_players:
                        if p['id'] == msg['_sender']:
                            p['ready'] = msg['status']
                            break
                    self.broadcast_lobby_state()

            # Client 逻辑
            elif self.my_role == "CLIENT":
                if msg['type'] == 'LOBBY_STATE':
                    self.lobby_players = msg['players']
                    self.map_id = msg['map_id']
                
                elif msg['type'] == 'LOBBY_START':
                    if 'config' in msg:
                        self.lobby_config = msg['config']
                        
                    self.state = "WAITING"


    def broadcast_lobby_state(self):
        host_info = {"id": "host", "name": self.player_info['name'], "ready": True}
        all_players = [host_info] + self.lobby_players
        
        self.net.send({
            "type": "LOBBY_STATE",
            "players": all_players,
            "map_id": self.map_id
        })

