import random
import math
import pygame
from core.settings import *
from core.base_classes import vec, FloatingText
from units import Engineer, CruiseMissile, AC130, Harvester, ParatrooperPlane, CombatEngineer, APC
SHIPYARD_COST=1000
# AI 与玩家同价：兵种实价映射（units.json costs 分区），try_queue_unit 扣款与
# 兵种池可负担过滤共用；矿车 HARVESTER_COST=800（原默认 500，用户要求提高矿车价格）
AI_UNIT_COSTS = {
    "m1a2": M1A2_COST, "type99": TYPE99_COST, "kirov": KIROV_COST,
    "rifleman": RIFLEMAN_COST, "armored": ARMORED_COST, "apc": APC_COST,
    "mech": MECH_COST, "himars": HIMARS_COST, "wz10": WZ10_COST,
    "mi24": HIND_COST, "helicopter": HELICOPTER_COST, "rocket": ROCKET_COST,
    "sniper": SNIPER_COST, "combat_engineer": COMBAT_EN_COST,
    "harvester": HARVESTER_COST,
}
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
        self.raid_cooldown = 600   # 骚扰小队冷却（帧）
        self.drop_cooldown = 1800  # 空投伞兵冷却（帧）
        self.defend_timer = 0      # 防守召回节流（帧）

        # --- 攻击性参数（用户要求加强 AI 攻击性） ---
        self.assault_interval = 900    # 主力进攻间隔：1800→900（30s→15s）
        self.min_assault_size = 4      # 发起进攻的最小部队规模
        self.chase_interval = 300      # 进攻途中掉队单位重新下令的间隔
        self.raid_size = 2             # 每波骚扰小队规模
        
        # --- 地图分析 ---
        self.map_center = vec(4000, 2400)
        self.my_base_pos = None
        self.enemy_base_pos = None
        self.analyzed = False
        self.failed_build_attempts = 0
        # 攒钱目标 (b_type, cost)：锁定的下一个建造目标，钱不够时军事生产/升级
        # 让路攒钱（否则资金被造兵花到预留线，科技中心/核弹井永远攒不齐）
        self.build_savings = None
        # 选址边界默认值（current_map 未就绪时的防御兜底）
        self.map_w = 8000
        self.map_h = 8000
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
        # 存活检查：有基地或基地车(MCV)任一存活即继续指挥
        my_bases = [b for b in self.game.all_buildings if b.team == self.team and getattr(b, 'b_type', '') == 'base' and b.alive]
        my_mcvs = [u for u in self.game.all_units if u.alive and u.team == self.team and getattr(u, 'can_deploy', False)]
        if not my_bases and not my_mcvs: return
        if my_bases: self.my_base_pos = my_bases[0].pos
        elif self.my_base_pos is None: self.my_base_pos = my_mcvs[0].pos
        current_money = self.get_money()
        
        # 资源趋势分析
        self.resource_trend = current_money - self.last_money
        self.last_money = current_money
        
        # 2. 状态决策
        self.update_strategy_state()
        
        # 3. 执行模块
        self.ai_economy_management() # 建造/开矿
        self.ai_prototype_charge()    # 原型机武器充能（核弹/铁幕）
        self.ai_military_production() # 造兵/升级
        self.ai_tactical_command()    # 控兵/进攻
        self.ai_use_support()
        self.ai_raid_logic()          # 骚扰小队（打敌方矿车/矿区）
        self.ai_airdrop()             # 空投伞兵突袭
        
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
        self.threats_near_base = enemy_units_near_base  # 供 tactical 拦截判定
        
        # 状态切换逻辑（攻击性增强：钱多兵少也强攻，不再傻发展）
        # 小股骚扰（<3 敌人近基地）不触发全军回防——那是"打到一半撤退"的元凶
        # DEFEND 滞回：进入需 3 威胁、退出需 <=1——威胁在 2~3 波动时状态若每帧横跳，
        # 部队会被"召回↔出击"来回拉扯（绕基地抽动的根源之一）
        if self.state == "DEFEND" and enemy_units_near_base >= 2:
            return  # 滞回带内维持 DEFEND
        if enemy_units_near_base >= 3:
            self.state = "DEFEND"
        elif len(my_units) >= AI_WAVE_SIZE or self.get_money() > 8000 and len(my_units) >= self.min_assault_size:
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
        aa_count = my_buildings.count("aa_turret")

        build_options = []

        # 建造愿望清单：只表达"想要什么"，买不买得起交给攒钱机制。
        # 旧版每项都带 current_money >= COST 门槛——但军事生产每周期把钱花到
        # 预留线，资金刚过线就被造兵吃掉 → 贵建筑(科技中心/核弹井/铁幕)的选项
        # 几乎永远不出现（实测中等收入下科技中心 4 分钟才落地，贫困 9:48）
        if "power_plant" not in my_buildings:
            build_options.append(("power_plant", POWER_PLANT_COST, 100))

        if "factory" not in my_buildings:
            build_options.append(("factory", FACTORY_COST, 90))

        if "airfield" not in my_buildings:
            build_options.append(("airfield", AIRFIELD_COST, 80))

        if factory_count < 3:
            build_options.append(("factory", FACTORY_COST, 70))

        if airfield_count < 2:
            build_options.append(("airfield", AIRFIELD_COST, 65))

        # 矿场上限 15→8：收入瓶颈是矿车数（AI_HARVESTER_TARGET=4）而非矿场数，
        # 15 座矿场 = 白烧 7500+ 建筑资金，挤压工厂/机场/科技中心
        if mining_count < 8:
            build_options.append(("mining", MINING_COST, 60))

        if power_count < factory_count + 2:
            build_options.append(("power_plant", POWER_PLANT_COST, 55))

        if radar_count < 2:
            build_options.append(("radar", RADAR_COST, 50))

        # research 原排 45（第 9 顺位）——要等 15 矿场+2 雷达全建完才轮到，
        # 科技中心迟迟不落地 → has_tech=False → factory 永远只出 m1a2/armored 基础兵。
        # 提到 85：power→factory→research→airfield，先解锁科技再铺机场
        if research_count < 2:
            build_options.append(("research", RESEARCH_COST, 85))

        # 旧版还会造第二种科技中心（TechCenter 2000/个，最多 2 座）——
        # 与 research 重复烧钱 4000+，是"AI 不造高级建筑"的钱坑，已删除

        if mining_count > 3:
            if aa_count < mining_count // 2:
                build_options.append(("aa_turret", AA_TURRET_COST, 35))

            if "shipyard" not in my_buildings:
                build_options.append(("shipyard", SHIPYARD_COST, 30))

        if "bunker" not in my_buildings:
            build_options.append(("bunker", BUNKER_COST, 25))

        # —— 高级武器（核弹井/铁幕）：不能当独立建筑造！ ——
        # 它们是 PrototypeGen(原型机发生器)的挂载武器 weapon_obj（构造还需要
        # parent 参数），旧版直接派工程师建会 TypeError 崩溃且工程师名额被卡死。
        # 正确链路与玩家侧栏一致：造 prototype_gen → build_prototype() 充能
        if mining_count >= 4:
            gen_count = my_buildings.count("prototype_gen")
            if gen_count < 1:
                build_options.append(("prototype_gen", PROTOTYPECOST, 68))

        # 在建类型去重：同一建筑已有工程师在浇就不再重复下单——
        # 旧版无此检查，AI 会一次派 3 个工程师同时造 3 座电厂/工厂，
        # 资金×3 消耗 + 工程师名额(3)被占满，表现就是"AI 不出工程师建造建筑"
        build_options = [o for o in build_options if not self.is_building_in_progress(o[0])]

        # —— 目标规划与攒钱：加权随机锁定一个目标，钱不够就转入攒钱模式 ——
        # 军事生产/升级看到 build_savings 会抬高预留线让路，攒够立即下单
        if self.build_savings:
            # 目标仍在愿望清单（未建成/类型未被占满）→ 继续攒
            if any(o[0] == self.build_savings[0] for o in build_options):
                b_type, cost = self.build_savings
                if self.get_money() >= cost:
                    self.execute_build(b_type, cost)
                    self.build_savings = None
                return                      # 攒钱期不换目标、不下新单
            self.build_savings = None       # 目标已无意义 → 重新规划

        if not build_options:
            return
        # 发展路线概率化（类似 LLM 采样）：轮盘赌加权随机，priority 越高越可能被选中
        # 但不固定——每局/每个 AI 的发展顺序都不同（有时提前造机场、有时先铺矿场）
        weights = [max(1, opt[2]) for opt in build_options]
        b_type, cost, priority = random.choices(build_options, weights=weights, k=1)[0]
        if self.get_money() >= cost:
            self.execute_build(b_type, cost)
        else:
            self.build_savings = (b_type, cost)

    def ai_prototype_charge(self):
        """原型机武器充能（与玩家侧栏 ui_sidebar 同款流程）。

        空闲基座 + 资金≥武器价+1000 预留时，交替充能核弹/铁幕；
        发射后 loaded_weapon 清空，下次循环自动续充。
        独立于 ai_economy_management：攒钱期提前 return 时充能不被跳过。
        """
        # 节流：与经济建造共用 30 帧节奏
        self.proto_timer = getattr(self, 'proto_timer', 0) + 1
        if self.proto_timer < 30: return
        self.proto_timer = 0

        gens = [b for b in self.game.all_buildings
                if b.team == self.team and b.alive
                and getattr(b, 'b_type', '') == 'prototype_gen'
                and not getattr(b, 'loaded_weapon', None)]
        if not gens: return

        p_type = "nuke_silo" if (self.game.frame_count // 3600) % 2 == 0 else "iron_curtain"
        w_cost = NUKESILOCOST if p_type == "nuke_silo" else IRONCURTAINCOST
        if self.get_money() >= w_cost + 1000:
            self.spend_money(w_cost)
            gens[0].build_prototype(p_type)

    def execute_build(self, b_type, cost):
        """AI 下单建造：选址规则与玩家 handle_build_click 完全一致。

        旧版用 Rect.collidelist 只认 Rect 岛屿，两类地图上 45 次选址全灭
        （AI 永远派不出工程师，诊断 tools/_diag_ai_build_realmap.py 复现 0/60）：
          1) apply_terrain_polys 会在无岛陆地图创建**空的 islands 属性** →
             hasattr 恒真 + on_island 恒假（荒野游踪/风暴海岸/龙之谷/广播中心全中招）
          2) 布局编辑器画的 land 多边形是 dict 岛屿，Rect 过滤后全部丢失
        改用玩家同款 lake_contains/island_contains（Rect/dict/poly 通吃），
        判定语义 = "在任一湖里且不在任何岛上才算水"。
        """
        if self.game.current_map:
            self.map_w = self.game.current_map.width
            self.map_h = self.game.current_map.height

        # 选址圆心：基地 → 基地车 → 最近己方建筑（否则后期永远无法扩建）
        bases = [b for b in self.game.all_buildings if b.team == self.team and getattr(b, 'b_type', '') == "base" and b.alive]
        if not bases:
            mcvs = [u for u in self.game.all_units if u.alive and u.team == self.team and getattr(u, 'can_deploy', False)]
            own = [b for b in self.game.all_buildings if b.team == self.team and b.alive]
            if mcvs: bases = mcvs
            elif own: bases = own
            else: return
        base = random.choice(bases)

        from maps.map_data import lake_contains, island_contains
        islands = getattr(self.game.current_map, 'islands', None) or []

        # 大建筑（原型机发生器 140x140/黑幕等）选址框放大防重叠
        big_footprint = b_type in ("prototype_gen", "shroud_gen")
        half = 70 if big_footprint else 50
        is_shipyard = (b_type == "shipyard")

        # 智能选址：45 次尝试、半径随失败次数外扩（150→~900）
        for attempt in range(45):
            dist = random.randint(150, min(900, 150 + attempt * 20))
            angle = random.randint(0, 360)
            offset = vec(dist, 0).rotate(angle)
            build_pos = base.pos + offset

            if not (100 < build_pos.x < self.map_w-100 and 100 < build_pos.y < self.map_h-100):
                continue

            # 水域判定（与玩家 handle_build_click 同款）：在湖里且不在岛上=水
            px, py = int(build_pos.x), int(build_pos.y)
            in_water = False
            for lake in self.game.lakes:
                if lake_contains(lake, px, py):
                    in_water = True
                    for isle in islands:
                        if island_contains(isle, px, py):
                            in_water = False
                            break
                    break

            if is_shipyard:
                if not in_water:        # 船厂必须下水（且不在岛上）
                    continue
            elif in_water:              # 其余建筑必须旱地
                continue

            # 碰撞检查（与玩家一致）：建筑外扩 20px + 地面单位占位
            build_rect = pygame.Rect(build_pos.x - half, build_pos.y - half, half * 2, half * 2)
            blocked = False
            for b in self.game.all_buildings:
                if b.alive and b.rect.inflate(20, 20).colliderect(build_rect):
                    blocked = True; break
            if not blocked:
                for u in self.game.all_units:
                    r = getattr(u, 'rect', None)
                    if u.alive and not getattr(u, 'is_air', False) and r is not None and r.colliderect(build_rect):
                        blocked = True; break
            if blocked: continue

            # 找到了！扣费并派工程师从基地出发浇筑
            self.spend_money(cost)
            spawn_pos = base.pos + vec(0, 50)  # 工程师从基地出来
            eng = Engineer(self.game, spawn_pos, self.team, build_pos)
            eng.target_type = b_type
            self.game.all_units.append(eng)
            print(f"[AI {self.team}] Building {b_type}")
            return


    def ai_military_production(self):
        self.production_cooldown += 1
        # 攒钱期（build_savings）军事降速三倍排兵：保留防守产出，
        # 同时给攒钱目标（科技中心/核弹井等）留出资金积累窗口
        saving = self.build_savings is not None
        if self.production_cooldown < (90 if saving else 30): return
        self.production_cooldown = 0

        # 1. 尝试升级
        self.ai_attempt_upgrades()

        # 2. 造兵
        current_money = self.get_money()
        # 预留线：DEFEND 800 / 其他 1000；攒钱期抬高到目标造价——
        # 造兵只花攒钱线以上的富余，否则贵建筑永远攒不齐（科技中心 4 分钟才落地）
        reserve = 800 if self.state == "DEFEND" else 1000
        if saving:
            reserve = max(reserve, self.build_savings[1])
        if current_money < reserve: return

        # 3. 部队上限（经济换军力）：战斗单位数达到 cap 就停止排兵，把资金
        # 留给造建筑/扩经济；矿车越多经济越强，可养部队越多（AI_UNIT_CAP_*）。
        # 放在资金检查之后、升级检查（ai_attempt_upgrades）已先行执行，不受影响。
        n_combat = 0
        n_harv = 0
        for u in self.game.all_units:
            if u.team != self.team or not getattr(u, 'alive', False):
                continue
            if isinstance(u, Harvester):
                n_harv += 1
            elif not isinstance(u, (Engineer, CruiseMissile)):
                n_combat += 1

        # 3.5 补矿车（经济自平衡）：矿车被打掉后运矿收入归零，资金永远攒不到
        # 建筑门槛，AI 会退化成"不出建筑只出步枪兵"。矿车少于目标数时优先补矿车
        # （矿车不是战斗单位，绕过部队上限）；矿车恢复→cap 回升→恢复造兵。
        # 【关键】统计存活+排队中（current_production/production_queue）的矿车
        # 总数——旧版只数存活：矿车损失后每 0.5s 排一辆直到出生，工厂队列(上限5)
        # 被矿车塞满 → 坦克进不了队列，还白烧钱（"矿车刷屏+不出坦克"根因）
        n_harv_queued = 0
        for b in self.game.all_buildings:
            if b.team != self.team or not getattr(b, 'alive', False):
                continue
            if getattr(b, 'b_type', '') != 'factory':
                continue
            cp = getattr(b, 'current_production', None)
            if cp and cp.get('type') == 'harvester':
                n_harv_queued += 1
            for t, _ in getattr(b, 'production_queue', []):
                if t == 'harvester':
                    n_harv_queued += 1
        if n_harv + n_harv_queued < AI_HARVESTER_TARGET:
            factories = [b for b in self.game.all_buildings
                         if b.team == self.team and b.alive
                         and getattr(b, 'b_type', '') == 'factory']
            if factories:
                self.try_queue_unit(random.choice(factories), "harvester")
                return

        cap = AI_UNIT_CAP_BASE + AI_UNIT_CAP_PER_HARVESTER * n_harv
        if n_combat >= cap: return

        buildings = [b for b in self.game.all_buildings if b.team == self.team and b.alive]
        has_tech = self.has_tech_center()
        
        # 分析当前部队组成
        unit_types = {}
        for u in self.game.all_units:
            if u.team == self.team and not isinstance(u, (Engineer, Harvester, CruiseMissile)):
                unit_type = getattr(u, 'unit_type', 'unknown')
                unit_types[unit_type] = unit_types.get(unit_type, 0) + 1
        
        # 根据状态调整造兵策略（每周期随机顺序：固定顺序时先建的工厂总是先
        # 扣款，后建的机场因资金被吃永远排不上队——用户反馈"高级兵种出得少"）
        for b in random.sample(buildings, len(buildings)):
            b_type = getattr(b, 'b_type', '')
            
            if b_type == "factory":
                # 根据状态和资源调整兵种选择（坦克双倍权重；选择后按实价过滤
                # 买得起的，全买不起才跳过本建筑——避免高级兵尝试白白浪费周期）
                if self.state == "ASSAULT":
                    # 进攻状态，优先重型坦克；m1a2 兜底——type99(1400)/mech(1600)
                    # 买不起时过滤后仍有坦克可出，避免工厂空转（用户反馈"不出坦克"）
                    if has_tech:
                        choices = ["type99", "type99", "mech", "himars", "m1a2"]
                    else:
                        choices = ["m1a2", "m1a2", "armored"]
                elif self.state == "DEFEND":
                    # 防御状态，反坦克+防空+主力坦克
                    choices = ["rocket", "armored", "m1a2"]
                elif self.state == "EXPAND":
                    # 扩张状态，优先造工程师和APC
                    choices = ["combat_engineer", "apc"]
                else: # DEVELOP
                    # 发展状态，坦克为主，科技后掺高级兵（m1a2 兜底同上）
                    if has_tech:
                        choices = ["type99", "type99", "mech", "himars", "apc", "m1a2"]
                    else:
                        choices = ["m1a2", "m1a2", "armored"]

                # 小概率造个工程师去修
                if random.random() < 0.1 and "combat_engineer" not in choices:
                    choices.append("combat_engineer")

                choices = [c for c in choices if self.can_afford(AI_UNIT_COSTS.get(c, 500))]
                if not choices: continue
                u_type = random.choice(choices)
                self.try_queue_unit(b, u_type)

            elif b_type == "airfield":
                # 根据资源和状态调整空军选择
                if self.state == "ASSAULT":
                    # 进攻状态，优先攻击直升机
                    if has_tech:
                        choices = ["wz10", "wz10", "mi24", "kirov"]
                    else:
                        choices = ["helicopter", "wz10"]
                elif self.state == "DEFEND":
                    # 防御状态，优先造防空单位
                    choices = ["helicopter", "wz10"]
                else:
                    # 其他状态，平衡造兵
                    if has_tech:
                        choices = ["wz10", "wz10", "kirov", "mi24"]
                    else:
                        choices = ["helicopter", "wz10"]

                choices = [c for c in choices if self.can_afford(AI_UNIT_COSTS.get(c, 500))]
                if not choices: continue
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
        # AI 与玩家同价：全部走 units.json costs（AI_UNIT_COSTS 模块常量，
        # 兵种筛选 ai_military_production 也用它做可负担过滤）
        cost = AI_UNIT_COSTS.get(u_type, 500)

        if self.can_afford(cost):
            # 建造时间与玩家下单路径（net_mixin REQ_TRAIN）使用同一份 BUILD_TIME_*
            # 映射，保证 AI 出兵速度对齐真人玩家（不再用旧的 300/600 硬编码帧）
            if u_type in ["armored", "m1a2", "mech", "type99", "himars"]:
                time_cost = BUILD_TIME_TANK
            elif u_type in ["helicopter", "wz10", "mi24", "stealheli", "heavytransport", "fighterjet", "attackplane"]:
                time_cost = BUILD_TIME_AIR
            elif u_type == "kirov":
                time_cost = BUILD_TIME_AIRSHIP
            elif u_type == "rifleman":
                time_cost = BUILD_TIME_INFANTRY
            elif u_type == "harvester":
                # 矿车专属时长（BUILD_TIME_HARVESTER=1600 帧 ≈ 27s，原 800）——
                # 用户要求降低矿车刷屏速度：更贵（800）+更慢+排队计数封顶
                time_cost = BUILD_TIME_HARVESTER
            elif u_type == "rocket":
                time_cost = BUILD_TIME_INFANTRY * 2
            elif "shotgunner" in u_type:
                time_cost = BUILD_TIME_INFANTRY * 3
            else:
                time_cost = BUILD_TIME_TANK  # 默认

            if hasattr(building, 'queue_unit'):
                if building.queue_unit(u_type, time_cost):
                    self.spend_money(cost)

    def ai_attempt_upgrades(self):
        """如果钱多，升级工厂和机场"""
        # 攒钱期不动升级的钱袋：门槛抬到 3000+目标缺口，避免升级吃掉积蓄
        remaining = self.build_savings[1] if self.build_savings else 0
        if self.get_money() - remaining < 3000: return
        
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
    def _engage_orders(self, units, target, scatter=100):
        """攻击性下令：目标是实体→set_target（单位自行推进到自身最大射程处开火，
        目标摧毁后自动索敌换下一个；不再冲到建筑中心挤在墙边）。目标只是坐标
        （如基地集结点）才用 move_to+散布。"""
        if hasattr(target, 'alive'):
            for u in units:
                u.set_target(target)
        else:
            for u in units:
                u.move_to(target + vec(random.randint(-scatter, scatter),
                                       random.randint(-scatter, scatter)))

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

        if self.attack_timer <= 0 and self.attack_force_size >= self.min_assault_size:
            assault_units = self.get_assault_units(combat_units)
            if len(assault_units) >= self.min_assault_size:
                ground = [u for u in assault_units if not getattr(u, 'is_air', False)]
                air_units = [u for u in assault_units if getattr(u, 'is_air', False)]
                # 空军直扑目标（不怕地面拦截，先行压制）
                self._engage_orders(air_units, target)
                # 地面部队：停在各自最大射程处开火，不贴脸
                self._engage_orders(ground, target)
                self.attack_timer = self.assault_interval

        elif self.state != "DEFEND" and self.attack_timer <= self.assault_interval - self.chase_interval:
            # 进攻途中掉队/卡住单位重新下令（防止单位发呆不再进攻）
            if self.game.frame_count % self.chase_interval == 0:
                for u in combat_units:
                    if u.hp > u.max_hp * 0.3 and u.pos.distance_to(target_pos) > 600:
                        if u.ai_mode == "GUARD" or not getattr(u, 'target_pos', None):
                            self._engage_orders([u], target, scatter=120)

        if self.state == "DEFEND":
            if self.my_base_pos:
                # 防守驻扎：45 帧节流 + 只召回"远处且闲置"的单位。
                # 旧版每帧给近基地单位下发新随机点——单位到达(25px)后 target_pos 清空、
                # 下一帧又被扔向新点，目标不停跳变 → 绕基地抽动（用户反馈）
                self.defend_timer -= 1
                if self.defend_timer <= 0:
                    self.defend_timer = 45
                    for u in combat_units:
                        dist_home = u.pos.distance_to(self.my_base_pos)
                        # 开火中(ATTACK)或赶路中有指令的单位不动；已在驻守圈(250px)内的闲置单位不再下令
                        busy = u.ai_mode == "ATTACK" or bool(getattr(u, 'target_pos', None))
                        if not busy and dist_home > 250:
                            u.move_to(self.my_base_pos + vec(random.randint(-200, 200), random.randint(-200, 200)))
        elif getattr(self, 'threats_near_base', 0) > 0:
            # 小股拦截：1-2 个敌人骚扰基地时派闲置单位去打（不惊动主力，不触发全军撤退）
            self._intercept_raiders(combat_units)

        if self.state == "EXPAND":
            self.ai_special_ops()

    def _intercept_raiders(self, combat_units):
        """小股敌人骚扰基地时派 2 个闲置单位拦截（每 180 帧节流）。"""
        if not hasattr(self, 'intercept_timer'):
            self.intercept_timer = 0
        self.intercept_timer -= 1
        if self.intercept_timer > 0: return
        self.intercept_timer = 180

        raiders = [u for u in self.game.all_units
                   if u.alive and u.team != self.team and u.team != "neutral"
                   and self.my_base_pos and u.pos.distance_to(self.my_base_pos) < 800]
        if not raiders: return
        idle = [u for u in combat_units
                if u.ai_mode == "GUARD" and not getattr(u, 'target_pos', None)
                and u.pos.distance_to(self.my_base_pos) < 1500]
        target = raiders[0]
        self._engage_orders(idle[:2], target, scatter=60)

    def ai_raid_logic(self):
        """骚扰小队：从闲置部队抽 2 个单位持续袭击敌方矿车/矿区（含其他 AI）。

        与主力进攻独立计时——大小队同时施压，让对手始终有侧翼威胁。
        """
        self.raid_cooldown -= 1
        if self.raid_cooldown > 0: return
        if self.state == "DEFEND": return  # 被打时部队留家防守

        idle = [u for u in self.game.all_units
                if u.alive and u.team == self.team
                and not isinstance(u, (Engineer, Harvester, CruiseMissile))
                and u.ai_mode == "GUARD" and u.hp > u.max_hp * 0.6]
        if len(idle) < self.raid_size:
            self.raid_cooldown = 300
            return

        # 袭扰目标优先级：敌方采矿车 > 敌方矿场 > 敌方电厂
        targets = [u for u in self.game.all_units if u.alive and u.team != self.team
                   and u.team != "neutral" and isinstance(u, Harvester)]
        if not targets:
            targets = [b for b in self.game.all_buildings if b.alive and b.team != self.team
                       and b.team != "neutral"
                       and getattr(b, 'b_type', '') in ("mining", "power_plant")]
        if not targets:
            self.raid_cooldown = 600
            return

        target = min(targets, key=lambda t: t.pos.distance_to(self.my_base_pos))
        self._engage_orders(idle[:self.raid_size], target, scatter=80)
        self.raid_cooldown = 900  # 15 秒一波

    def ai_airdrop(self):
        """空投伞兵：有科技中心+机场时定期往敌方经济区投兵（ParatrooperPlane 自带投放逻辑）。"""
        self.drop_cooldown -= 1
        if self.drop_cooldown > 0: return
        if not self.has_tech_center(): return
        if not self.can_afford(AIRDROP_COST, reserve_buffer=True): return

        targets = [b for b in self.game.all_buildings if b.alive and b.team != self.team
                   and b.team != "neutral"
                   and getattr(b, 'b_type', '') in ("mining", "power_plant", "factory", "base")]
        if not targets: return

        target = min(targets, key=lambda b: b.pos.distance_to(self.my_base_pos))
        self.spend_money(AIRDROP_COST)
        self.game.all_units.append(ParatrooperPlane(self.game, target.pos, self.team))
        self.drop_cooldown = 3600  # 60 秒一次

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

        # 就近打击（含其他 AI 的建筑）：距离近的目标威胁更大、性价比更高
        target = min(targets, key=lambda b: b.pos.distance_to(self.my_base_pos))
        
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
        # 科技中心实际 b_type="research"（ResearchCenter 类）；
        # 旧代码误查 "tech_center" 恒 False → AI 永远造不出高级兵/放不出空投
        for b in self.game.all_buildings:
            if b.team == self.team and b.alive and getattr(b, 'b_type', '') in ("research", "tech_center"):
                return True
        return False
    
    def select_target(self, enemy_buildings, enemy_units):
        target_priorities = {
            'base': 10,
            'research': 9,      # 科技中心（ResearchCenter）
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
            # 打分=价值优先 + 就近加成：各 AI 自然分散攻击不同目标，
            # 距离越近分越高，因此 AI 之间也会互相攻击而不是只盯着玩家
            origin = self.my_base_pos if self.my_base_pos else self.map_center
            def building_score(b):
                pri = target_priorities.get(getattr(b, 'b_type', ''), 0)
                dist = b.pos.distance_to(origin)
                return pri * 1000 - dist * 0.5
            return max(enemy_buildings, key=building_score)

        elif enemy_units:
            origin = self.my_base_pos if self.my_base_pos else self.map_center
            return min(enemy_units, key=lambda u: u.pos.distance_to(origin))

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