import random
import math
import pygame
from settings import *
from base_classes import vec, FloatingText
from units import Engineer, CruiseMissile, AC130, Harvester, ParatrooperPlane, CombatEngineer, APC
SHIPYARD_COST=1000
class AICommander:
    def __init__(self, game, team="team_1"): 
        self.game = game
        self.team = team
        
        # --- 状态机 ---
        self.state = "DEVELOP"  # DEVELOP, EXPAND, ASSAULT, DEFEND
        self.state_timer = 0
        
        # --- 经济参数 ---
        self.min_cash_reserve = 1000   # 最小存款 (用于修建筑或急用)
        self.tech_budget_ratio = 0.4   # 40% 的钱存着升科技
        self.attack_budget_ratio = 0.3  # 30% 的钱用于进攻
        self.expansion_budget_ratio = 0.2  # 20% 的钱用于扩张
        self.defense_budget_ratio = 0.1  # 10% 的钱用于防御
        
        # --- 资源管理 ---
        self.resource_trend = 0  # 资源趋势，正数表示收入大于支出
        self.last_money = 0  # 上一帧的资金
        self.attack_force_size = 0  # 当前进攻部队规模
        self.max_attack_force_size = 15  # 最大进攻部队规模
        
        # --- 冷却 ---
        self.build_timer = 0
        self.support_cooldown = 0
        self.production_cooldown = 0
        self.upgrade_check_timer = 0
        self.scout_timer = 0
        self.attack_timer = 0  # 进攻冷却
        
        # --- 地图分析 ---
        self.map_center = vec(4000, 2400)
        self.my_base_pos = None
        self.enemy_base_pos = None
        self.analyzed = False 
        self.failed_build_attempts = 0
    # -------------------------------------------------------------------------
    # 资源管理 (Resource Manager)
    # -------------------------------------------------------------------------
    def get_money(self):
        return self.game.team_resources.get(self.team, 0)

    def spend_money(self, amount):
        if self.team in self.game.team_resources:
            self.game.team_resources[self.team] -= amount

    def can_afford(self, cost, reserve_buffer=False):
        current = self.get_money()
        threshold = cost + (self.min_cash_reserve if reserve_buffer else 0)
        return current >= threshold

    # -------------------------------------------------------------------------
    # 核心更新循环 (Main Loop)
    # -------------------------------------------------------------------------
    def update(self):
        # 存活检查
        my_bases = [b for b in self.game.all_buildings if b.team == self.team and getattr(b, 'b_type', '') == 'base' and b.alive]
        if not my_bases: return
        self.my_base_pos = my_bases[0].pos
        current_money = self.get_money()
        
        # 资源趋势分析
        self.resource_trend = current_money - self.last_money
        self.last_money = current_money
        
        # 2. 状态决策
        self.update_strategy_state()
        
        # 3. 执行模块
        self.ai_economy_management() # 建造/开矿
        self.ai_military_production() # 造兵/升级
        self.ai_tactical_command()    # 控兵/进攻
        self.ai_use_support()
        
        # 4. 进攻冷却更新
        if self.attack_timer > 0:
            self.attack_timer -= 1
    # -------------------------------------------------------------------------
    # 战略决策 (Strategy)
    # -------------------------------------------------------------------------
    def update_strategy_state(self):
        self.state_timer += 1
        
        # 统计兵力
        my_units = [u for u in self.game.all_units if u.team == self.team and not isinstance(u, (Engineer, Harvester))]
        enemy_units_near_base = self.scan_threats(self.my_base_pos, 800)
        
        # 状态切换逻辑
        if enemy_units_near_base:
            self.state = "DEFEND"
        elif len(my_units) >= AI_WAVE_SIZE:
            self.state = "ASSAULT"
        elif self.get_money() > 5000 and len(my_units) > 5:
            self.state = "EXPAND"
        else:
            self.state = "DEVELOP"

    def scan_threats(self, pos, radius):
        """扫描指定区域内的敌人数量"""
        count = 0
        for u in self.game.all_units:
            if u.alive and u.team != self.team and u.team != "neutral":
                if u.pos.distance_to(pos) < radius:
                    count += 1
        return count
    def is_building_in_progress(self, b_type):
        for u in self.game.all_units:
            if u.team == self.team and isinstance(u, Engineer) and u.alive:
                if getattr(u, 'target_type', '') == b_type:
                    return True
        return False
    # -------------------------------------------------------------------------
    # 经济与建造 (Economy & Build)
    # -------------------------------------------------------------------------
    def ai_economy_management(self):
        self.build_timer += 1
        if self.build_timer < 30: return
        self.build_timer = 0

        eng_count = 0
        for u in self.game.all_units:
            if u.team == self.team and isinstance(u, Engineer) and u.alive:
                eng_count += 1

        if eng_count >= 3: return
        current_money = self.get_money()

        if current_money < 500: return

        my_buildings = [
            getattr(b, 'b_type', '')
            for b in self.game.all_buildings
            if b.team == self.team and b.alive
        ]

        mining_count = my_buildings.count("mining")
        power_count = my_buildings.count("power_plant")
        factory_count = my_buildings.count("factory")
        airfield_count = my_buildings.count("airfield")
        radar_count = my_buildings.count("radar")
        research_count = my_buildings.count("research")
        tech_center_count = my_buildings.count("tech_center")
        aa_count = my_buildings.count("aa_turret")

        build_options = []

        if "power_plant" not in my_buildings and current_money >= POWER_PLANT_COST:
            build_options.append(("power_plant", POWER_PLANT_COST, 100))

        if "factory" not in my_buildings and current_money >= FACTORY_COST:
            build_options.append(("factory", FACTORY_COST, 90))

        if "airfield" not in my_buildings and current_money >= AIRFIELD_COST:
            build_options.append(("airfield", AIRFIELD_COST, 80))

        if factory_count < 3 and current_money >= FACTORY_COST:
            build_options.append(("factory", FACTORY_COST, 70))

        if airfield_count < 2 and current_money >= AIRFIELD_COST:
            build_options.append(("airfield", AIRFIELD_COST, 65))

        if mining_count < 15 and current_money >= MINING_COST:
            build_options.append(("mining", MINING_COST, 60))

        if power_count < factory_count + 2 and current_money >= POWER_PLANT_COST:
            build_options.append(("power_plant", POWER_PLANT_COST, 55))

        if radar_count < 2 and current_money >= RADAR_COST:
            build_options.append(("radar", RADAR_COST, 50))

        if research_count < 2 and current_money >= RESEARCH_COST:
            build_options.append(("research", RESEARCH_COST, 45))

        if tech_center_count < 2 and current_money >= TECH_CENTER_COST:
            build_options.append(("tech_center", TECH_CENTER_COST, 40))

        if mining_count > 3:
            if aa_count < mining_count // 2 and current_money >= AA_TURRET_COST:
                build_options.append(("aa_turret", AA_TURRET_COST, 35))

            if "shipyard" not in my_buildings and current_money >= SHIPYARD_COST:
                build_options.append(("shipyard", SHIPYARD_COST, 30))

        if "bunker" not in my_buildings and current_money >= BUNKER_COST:
            build_options.append(("bunker", BUNKER_COST, 25))

        if "nuke_silo" not in my_buildings and current_money >= NUKE_SILO_COST:
            build_options.append(("nuke_silo", NUKE_SILO_COST, 20))

        if "iron_curtain" not in my_buildings and current_money >= IRON_CURTAIN_COST:
            build_options.append(("iron_curtain", IRON_CURTAIN_COST, 15))

        if build_options:
            build_options.sort(key=lambda x: x[2], reverse=True)
            b_type, cost, priority = build_options[0]
            self.execute_build(b_type, cost)
    def execute_build(self, b_type, cost):
        if self.game.current_map:
            self.map_w = self.game.current_map.width
            self.map_h = self.game.current_map.height
        # 找基地作为圆心
        bases = [b for b in self.game.all_buildings if b.team == self.team and getattr(b, 'b_type', '') == "base" and b.alive]
        if not bases: return
        base = random.choice(bases)
        
        # 智能选址 (尝试多次，离基地远一点，防止拥挤)
        for _ in range(15):
            dist = random.randint(150, 450)
            angle = random.randint(0, 360)
            offset = vec(dist, 0).rotate(angle)
            build_pos = base.pos + offset
            
            if not (100 < build_pos.x < self.map_w-100 and 100 < build_pos.y < self.map_h-100):
                continue
            
            # 碰撞检查 (Rect)
            build_rect = pygame.Rect(build_pos.x - 50, build_pos.y - 50, 100, 100)
            on_island = False
            if hasattr(self.game.current_map, 'islands'):
                # 必须完全在岛上 (用 contains 或 collidelist)
                # 简单点：只要撞到了岛就算在岛上
                if build_rect.collidelist(self.game.current_map.islands) != -1:
                    on_island = True

            in_obstacle = False
            
            # 船厂逻辑
            if b_type == "shipyard":
                # 必须在水里 且 不能在岛上
                # (同 handle_build_click 的修复逻辑)
                in_water = False
                for lake in self.game.lakes:
                    if lake['rect'].colliderect(build_rect): in_water = True; break
                
                if not in_water or on_island: continue             
                
            else:
                
                if hasattr(self.game.current_map, 'islands'):
                    if not on_island: in_obstacle = True # 没在岛上就是水里
                else:
                    for lake in self.game.lakes:
                        if lake['rect'].colliderect(build_rect): in_obstacle = True; break
            
            if in_obstacle: continue            # 查湖泊
            
            # 查其他建筑
            for b in self.game.all_buildings:
                if b.rect.inflate(20, 20).colliderect(build_rect): in_obstacle = True; break
            if in_obstacle: continue
            
            # 找到了！
            self.spend_money(cost)
            spawn_pos = base.pos + vec(0, 50) # 工程师从基地出来
            eng = Engineer(self.game, spawn_pos, self.team, build_pos)
            eng.target_type = b_type
            self.game.all_units.append(eng)
            print(f"[AI {self.team}] Building {b_type}")
            return


    def ai_military_production(self):
        self.production_cooldown += 1
        if self.production_cooldown < 30: return
        self.production_cooldown = 0
        
        # 1. 尝试升级
        self.ai_attempt_upgrades()
        
        # 2. 造兵
        current_money = self.get_money()
        # 预留 1000 块不花，除非在被打
        if self.state != "DEFEND" and current_money < 1000: return

        buildings = [b for b in self.game.all_buildings if b.team == self.team and b.alive]
        has_tech = self.has_tech_center()
        
        # 分析当前部队组成
        unit_types = {}
        for u in self.game.all_units:
            if u.team == self.team and not isinstance(u, (Engineer, Harvester, CruiseMissile)):
                unit_type = getattr(u, 'unit_type', 'unknown')
                unit_types[unit_type] = unit_types.get(unit_type, 0) + 1
        
        # 根据状态调整造兵策略
        for b in buildings:
            b_type = getattr(b, 'b_type', '')
            
            if b_type == "factory":
                # 根据状态和资源调整兵种选择
                if self.state == "ASSAULT":
                    # 进攻状态，优先造坦克和装甲车
                    if has_tech and current_money > 1500:
                        choices = ["type99", "mech", "himars"]
                    else:
                        choices = ["m1a2", "armored"]
                elif self.state == "DEFEND":
                    # 防御状态，优先造反坦克和防空
                    choices = ["rocket", "armored"]
                elif self.state == "EXPAND":
                    # 扩张状态，优先造工程师和APC
                    choices = ["combat_engineer", "apc"]
                else: # DEVELOP
                    # 发展状态，平衡造兵
                    if has_tech and current_money > 1000:
                        choices = ["type99", "mech", "himars", "apc", "combat_engineer"]
                    else:
                        choices = ["m1a2", "armored", "combat_engineer"]
                
                # 小概率造个工程师去修
                if random.random() < 0.1 and "combat_engineer" not in choices:
                    choices.append("combat_engineer")
                
                u_type = random.choice(choices)
                self.try_queue_unit(b, u_type)
                
            elif b_type == "airfield":
                # 根据资源和状态调整空军选择
                if self.state == "ASSAULT":
                    # 进攻状态，优先造攻击直升机
                    if has_tech and current_money > 2000:
                        choices = ["wz10", "mi24"]
                    else:
                        choices = ["helicopter"]
                elif self.state == "DEFEND":
                    # 防御状态，优先造防空单位
                    choices = ["helicopter"]
                else:
                    # 其他状态，平衡造兵
                    if has_tech and current_money > 1500:
                        choices = ["wz10", "kirov", "mi24"]
                    else:
                        choices = ["helicopter"]
                
                self.try_queue_unit(b, random.choice(choices))
                
            elif b_type == "base":
                # 补充步兵 (主要是为了占领或者当炮灰)
                if self.state == "ASSAULT":
                    # 进攻状态，优先造火箭兵和狙击手
                    choices = ["rocket", "sniper"]
                elif self.state == "DEFEND":
                    # 防御状态，优先造步枪兵
                    choices = ["rifleman"]
                else:
                    # 其他状态，平衡造兵
                    choices = ["rifleman", "rocket", "sniper"]
                
                self.try_queue_unit(b, random.choice(choices))

    def try_queue_unit(self, building, u_type):
        cost = 500 # 默认
        if u_type == "m1a2": cost = M1A2_COST
        elif u_type == "type99": cost = 800
        elif u_type == "kirov": cost = KIROV_COST
        elif u_type == "rifleman": cost = RIFLEMAN_COST
        
        if self.can_afford(cost):
            # 获取建造时间
            time_cost = 300 # 默认
            if u_type in ["kirov", "type99"]: time_cost = 600
            
            if hasattr(building, 'queue_unit'):
                if building.queue_unit(u_type, time_cost):
                    self.spend_money(cost)

    def ai_attempt_upgrades(self):
        """如果钱多，升级工厂和机场"""
        if self.get_money() < 3000: return
        
        for b in self.game.all_buildings:
            if b.team == self.team and b.alive and not getattr(b, 'is_upgraded', False):
                b_type = getattr(b, 'b_type', '')
                cost = 0
                if b_type == "factory": cost = UPGRADE_FACTORY_COST
                elif b_type == "airfield": cost = UPGRADE_AIRFIELD_COST
                
                if cost > 0 and self.can_afford(cost):
                    self.spend_money(cost)
                    b.is_upgraded = True
                    return # 一帧只升一个

    # -------------------------------------------------------------------------
    # 战术指挥 (Tactics)
    # -------------------------------------------------------------------------
    def ai_tactical_command(self):
        combat_units = [u for u in self.game.all_units if u.team == self.team and not isinstance(u, (Engineer, Harvester, CruiseMissile))]
        if not combat_units: return

        self.attack_force_size = len(combat_units)

        enemy_buildings = [b for b in self.game.all_buildings if b.team != self.team and b.team != "neutral" and b.alive]
        enemy_units = [u for u in self.game.all_units if u.team != self.team and u.team != "neutral" and u.alive]

        target = self.select_target(enemy_buildings, enemy_units)
        if not target:
            target = self.my_base_pos

        target_pos = target.pos if hasattr(target, 'pos') else target

        assault_interval = 1800

        if self.attack_timer <= 0 and self.attack_force_size >= 5:
            assault_units = self.get_assault_units(combat_units)
            if len(assault_units) >= 5:
                for u in assault_units:
                    if u.ai_mode == "GUARD" or self.game.frame_count % 120 == 0:
                        offset = vec(random.randint(-100, 100), random.randint(-100, 100))
                        u.move_to(target_pos + offset)
                self.attack_timer = assault_interval

        elif self.state == "DEFEND":
            if self.my_base_pos:
                for u in combat_units:
                    if u.pos.distance_to(self.my_base_pos) > 500:
                        u.move_to(self.my_base_pos + vec(random.randint(-200, 200), random.randint(-200, 200)))

        elif self.state == "EXPAND":
            self.ai_special_ops()

    def ai_special_ops(self):
        # 寻找中立建筑 (油井/通讯站)
        neutrals = [b for b in self.game.all_buildings if b.team == "neutral" and hasattr(b, 'capture_progress')]
        my_engs = [u for u in self.game.all_units if u.team == self.team and isinstance(u, CombatEngineer) and u.ai_mode == "GUARD"]
        
        if neutrals and my_engs:
            for eng in my_engs:
                # 找最近的中立建筑
                target = min(neutrals, key=lambda b: eng.pos.distance_squared_to(b.pos))
                eng.set_target(target)

    # -------------------------------------------------------------------------
    # 支援技能 (Support)
    # -------------------------------------------------------------------------
    def ai_use_support(self):
        if self.support_cooldown > 0:
            self.support_cooldown -= 1
            return

        # 检查是否有雷达
        has_radar = False
        for b in self.game.all_buildings:
            if b.team == self.team and b.alive and getattr(b, 'b_type', '') == "radar":
                has_radar = True; break
        if not has_radar: return


        targets = [b for b in self.game.all_buildings if b.team != self.team and b.team != "neutral" and b.alive]
        if not targets: return
        
        target = random.choice(targets)
        
        if self.can_afford(MISSILE_COST):
            self.spend_money(MISSILE_COST)
            self.game.all_units.append(CruiseMissile(self.game, target.pos, self.team))
            self.game.show_alert("WARNING: MISSILE DETECTED!")
            self.support_cooldown = 1800
            
        elif self.can_afford(AC130_COST+10000):
            self.spend_money(AC130_COST)
            self.game.all_units.append(AC130(self.game, target.pos, self.team))
            self.game.show_alert("WARNING: AC-130 ABOVE!")
            self.support_cooldown = 3000

    def has_tech_center(self):
        for b in self.game.all_buildings:
            if b.team == self.team and b.alive and getattr(b, 'b_type', '') == "tech_center":
                return True
        return False
    
    def select_target(self, enemy_buildings, enemy_units):
        target_priorities = {
            'base': 10,
            'tech_center': 9,
            'research': 8,
            'mining': 7,
            'factory': 6,
            'airfield': 5,
            'radar': 4,
            'power_plant': 3,
            'aa_turret': 2,
            'laser_turret': 2,
            'bunker': 1
        }

        if enemy_buildings:
            sorted_buildings = sorted(enemy_buildings,
                                   key=lambda b: target_priorities.get(getattr(b, 'b_type', ''), 0),
                                   reverse=True)
            return sorted_buildings[0]

        elif enemy_units:
            return min(enemy_units, key=lambda u: u.pos.distance_to(self.my_base_pos))

        return self.my_base_pos
    
    def should_attack(self):
        """判断是否应该进攻"""
        # 进攻冷却中
        if self.attack_timer > 0:
            return False
        
        # 资源充足
        if self.get_money() < 1500:
            return False
        
        # 部队规模足够
        if self.attack_force_size < 5:
            return False
        
        # 资源趋势良好
        if self.resource_trend < 0:
            return False
        
        return True
    
    def get_assault_units(self, combat_units):
        """获取适合进攻的部队"""
        # 筛选出状态良好的单位
        assault_units = []
        for u in combat_units:
            # 只选择健康状态良好的单位
            if u.hp > u.max_hp * 0.5:
                assault_units.append(u)
        return assault_units
    
    def rally_units(self, combat_units):
        """集结部队"""
        if not self.my_base_pos: return
        
        # 集结点设置在基地前方
        rally_point = self.my_base_pos + vec(200, 0)
        
        for u in combat_units:
            if u.ai_mode == "GUARD" or u.pos.distance_to(rally_point) > 100:
                u.move_to(rally_point)