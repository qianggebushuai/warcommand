# -*- coding: utf-8 -*-
"""本地策略引擎：零 API 的高级动作生成器（config.json decision="local" 时启用）。

输出"高级动作"（build/place/produce/attack/camera），由 DirectExecutor 直接调用
游戏内部 API 执行（config "direct": true，默认），或退化为键鼠模拟协议指令。
不经过 UI 点击/标签页/坐标映射，执行可靠。

策略对应 strategy/playbook.md 的精简规则（每轮 ≤ 8 个动作）：
- 敌人逼近我方建筑 → 全体战斗单位进攻该敌人
- 建造按 BUILD_PRIORITY（电厂/矿场→工厂→兵营→防御）
- 就绪建筑 → 自动选基地旁空位放置
- 矿车/坦克/步兵按 UNIT_PRIORITY_PREFIX 生产
"""
import math
import random

from core.settings import WORLD_WIDTH, WORLD_HEIGHT
from . import vision as vision_mod

# 建造优先级（payload，对应 sidebar BUILD 页；经济→军事→科技→防御）
# 用户要求：激光塔作为防御主力，排在普通防空/碉堡之前
BUILD_PRIORITY = ['power_plant', 'mining', 'factory', 'airfield', 'barracks',
                  'radar', 'research', 'laser_turret', 'aa_turret', 'bunker',
                  'missile_def', 'tech_center', 'shipyard', 'bastion']
# 单位生产优先级（payload，按此顺序选第一个可生产的；矿车优先保证经济）
UNIT_PRIORITY = ['harvester', 'm1a2', 't14', 'type99', 'apc', 'armored',
                 'fighterjet', 'attackplane', 'helicopter', 'wz10',
                 'rifleman', 'rocket', 'combat_engineer', 'mech', 'waver',
                 'kirov']
HARVESTER_CAP = 4            # 矿车数量上限（够了就转产战斗单位）
HARVESTER_TANK_BALANCE = 3000  # 资金高于此线时矿车让位坦克（不再无脑补车抢工厂）
BUILD_RESERVE = 1200         # 开建前给生产留的最低资金（防止建造把坦克钱抽干）

THREAT_RANGE = 300          # 敌人距我建筑 300 内才回防（更远持续进攻）
MIN_INTERVAL = 6            # 同一 payload 两次开建的最小间隔轮数（防重复点击）
ATTACK_MIN_ARMY = 6         # 主动进攻所需最少战斗单位数
ATTACK_COOLDOWN = 4         # 两次进攻指令的间隔轮数（约 24 秒，持续锁定敌方建筑）
TANK_CAP = 8                # 坦克数量上限（够数转产空军/步兵）
AIR_CAP = 4                 # 各类战机数量上限
SUPPORT_COST_MARGIN = 1500  # 支援技能保留资金线
SUPPORT_COOLDOWN = 5        # 支援技能间隔轮数（约 30 秒）
APC_TARGET = 1              # 运输车目标数（占领分支）
ENGINEER_TARGET = 2         # 工程师目标数（装车用）
GUARD_INF_CAP = 6           # 驻防步兵上限（霰弹+步枪，专职守基地不参与进攻）
KIROV_CAP = 2               # 飞艇数量上限（专职轰炸敌方防御建筑）
# 全部建筑的存活数量上限（建够就让位下一项，防止无限添盖）；
# 防御塔允许多一些（激光塔是用户指定的防御主力）
BUILD_COUNT_CAPS = {'power_plant': 5, 'mining': 4, 'factory': 2,
                    'airfield': 1, 'barracks': 1, 'radar': 1, 'research': 1,
                    'laser_turret': 4, 'aa_turret': 3, 'bunker': 4,
                    'missile_def': 2, 'tech_center': 1, 'shipyard': 1,
                    'bastion': 2}


class LocalPolicy:
    """读取 game 状态生成分支战略动作。decide() 每个扫描周期调用一次。

    四通道并行（每轮全评估，上限 10 动作）：
      A 建造：经济→军事底座→科技/空军→防御（BUILD_PRIORITY 序列）
      B 生产：占领需求(APC/工程师) → 矿车 → 坦克 → 空军 → 步兵兜底
      C 军事：威胁近防(<300) / 占领调度 / 兵力≥6 持续锁定敌方建筑
      D 支援：资金富余+有雷达 → AC130 打敌方单位密集区
    """

    def __init__(self):
        self.dets_last = []          # 最近一轮检测框（HUD/调试展示用）
        self.last_reason = ''        # 最近一轮决策依据（HUD 显示）
        self.last_view = ''          # 最近一轮视野汇总（我/敌/中 × 类别计数）
        self._build_cd = {}          # payload → 剩余冷却轮数
        self._attack_cd = 0          # 主动进攻剩余冷却轮数
        self._support_cd = 0         # 支援技能剩余冷却轮数
        self._airraid_cd = 0         # 飞艇轰炸剩余冷却轮数

    # ---------------- 数据采集 ----------------
    def _entities(self, game):
        """地面真值实体（含敌我 team、屏幕/世界坐标）。"""
        try:
            return vision_mod.project_entities(game)
        except Exception:
            return []

    def _find_item(self, game, tab, payload):
        try:
            for it in game.sidebar.all_items.get(tab, []):
                if it.payload == payload:
                    return it
        except Exception:
            pass
        return None

    def _my_base(self, game):
        for b in game.all_buildings:
            if b.team == game.my_team and getattr(b, 'alive', True):
                return (int(b.pos.x), int(b.pos.y))
        return None

    @staticmethod
    def _view_summary(ents, my_team, limit=12):
        """视野汇总：'敌Bastion×1 敌M1A2×2 我PowerPlant×2 …'（供 HUD/日志）。"""
        c = {}
        for e in ents:
            team = e.get('team', 'unknown')
            if team == my_team:
                side = '我'
            elif team in ('neutral', 'unknown'):
                side = '中'
            else:
                side = '敌'
            key = side + str(e.get('class', '?'))
            c[key] = c.get(key, 0) + 1
        return ' '.join('%s×%d' % (k, v)
                        for k, v in sorted(c.items(),
                                           key=lambda kv: -kv[1])[:limit])

    def _find_build_spot(self, game, base_pos):
        """基地周围找一个不与建筑重叠、且不在湖里的落点（随机起始角防死循环）。"""
        from maps.map_data import lake_contains
        bx, by = base_pos
        lakes = list(getattr(game, 'lakes', []) or [])
        start = random.randint(0, 45)
        for i in range(8):
            ang = start + i * 45
            for r in (160, 240, 330, 420, 500):           # 五档半径，铺满秒建圈
                # 每档带 ±25px 随机微扰，密集区多试几个变体位置
                x = int(bx + math.cos(math.radians(ang)) * r +
                        random.randint(-25, 25))
                y = int(by + math.sin(math.radians(ang)) * r +
                        random.randint(-25, 25))
                if not (150 < x < WORLD_WIDTH - 150 and 150 < y < WORLD_HEIGHT - 150):
                    continue
                if any(lake_contains(lk, x, y) for lk in lakes):
                    continue                                  # 湖面放不下
                ok = True
                for b in game.all_buildings:
                    if getattr(b, 'alive', True) and \
                            math.hypot(b.pos.x - x, b.pos.y - y) < 90:
                        ok = False
                        break
                if ok:
                    return [x, y]
        return None

    # ---------------- 策略 ----------------
    def decide(self, game, dets=None):
        self.dets_last = dets or []
        acts = []
        reason = []
        my_team = getattr(game, 'my_team', 'team_0')

        money = 0
        try:
            money = game.team_resources.get(my_team, 0)
        except Exception:
            pass
        reason.append('资金%d' % int(money))

        # 读条冷却推进
        for k in list(self._build_cd):
            self._build_cd[k] -= 1
            if self._build_cd[k] <= 0:
                del self._build_cd[k]
        if self._attack_cd > 0:
            self._attack_cd -= 1
        if self._support_cd > 0:
            self._support_cd -= 1
        if self._airraid_cd > 0:
            self._airraid_cd -= 1

        # ---- C. 军事通道：近防 / 占领 / 持续进攻 ----
        ents = self._entities(game)
        self.last_view = self._view_summary(ents, my_team)
        base_pos = self._my_base(game)
        my_bld = [(int(b.pos.x), int(b.pos.y)) for b in game.all_buildings
                  if b.team == my_team and getattr(b, 'alive', True)]
        enemy_units = [e for e in ents
                       if e['team'] not in (my_team, 'neutral', 'unknown')]

        # 实时计数（单位分类）
        def ucount(*keys, exclude_harv=True):
            n = 0
            for u in game.all_units:
                if not getattr(u, 'alive', True) or u.team != my_team:
                    continue
                cls = u.__class__.__name__.lower()
                if exclude_harv and 'harvester' in cls:
                    continue
                if any(k in cls for k in keys):
                    n += 1
            return n

        # [修复] ucount 的 exclude_harv 会把矿车排除，矿车计数必须独立统计，
        # 否则永远=0 → 策略器以为没矿车，工厂被无限补车霸占（坦克永远排不上）
        n_harv = sum(1 for u in game.all_units
                     if getattr(u, 'alive', True) and u.team == my_team
                     and 'harvester' in u.__class__.__name__.lower())
        n_tank = ucount('m1a2', 't14', 'type99')
        n_air = ucount('fighter', 'attackplane', 'helicopter', 'wz10', 'kirov')
        n_inf = ucount('rifleman', 'rocket', 'shotgun', 'sniper')
        n_eng = ucount('engineer')
        n_apc = sum(1 for u in game.all_units
                    if getattr(u, 'alive', True) and u.team == my_team
                    and hasattr(u, 'cargo') and hasattr(u, 'capacity')
                    and 'harvester' not in u.__class__.__name__.lower())
        army = n_tank + n_air + n_inf + n_apc
        # 驻防步兵计数（霰弹+步枪，专职守基地；军事通道与生产通道共用）
        n_guard = ucount('shotgun', 'rifleman')

        # 占领目标 = 全部敌对建筑（用户要求：只占敌对，不打中立油井；
        # 工程师 set_target 对任何敌对建筑触发 capture 秒占）
        neutrals = [b for b in game.all_buildings
                    if getattr(b, 'alive', True)
                    and b.team != game.my_team and b.team != 'neutral']
        cap_done = False
        if neutrals and n_apc > 0:
            acts.append({'do': 'apc_transport'})
            reason.append('运兵占领敌建筑')
            cap_done = True

        threat = None
        best_d = 1e18
        for bx, by in my_bld:
            for e in enemy_units:
                d = (e['world_pos'][0] - bx) ** 2 + (e['world_pos'][1] - by) ** 2
                if d < best_d:
                    best_d, threat = d, e
        attacking = False
        if threat and best_d ** 0.5 < THREAT_RANGE:
            # 只有贴脸（<300）才回防；骚扰性远敌不理会，继续执行战略
            acts.append({'do': 'attack', 'world': list(threat['world_pos'])})
            reason.append('敌%s贴脸→回防' % threat['class'])
            attacking = True
        else:
            # 持续进攻：兵力足够就反复锁定最近的敌方建筑（不回防）
            enemy_bld = [e for e in ents
                         if e['team'] not in (my_team, 'neutral', 'unknown')
                         and e['class'].lower() not in ('m1a2', 'harvester',
                                                        'rifleman', 'apc')]
            if army >= ATTACK_MIN_ARMY and self._attack_cd <= 0 and enemy_bld:
                from_bx, from_by = base_pos or (WORLD_WIDTH / 2, WORLD_HEIGHT / 2)
                tgt = min(enemy_bld,
                          key=lambda e: (e['world_pos'][0] - from_bx) ** 2 +
                                        (e['world_pos'][1] - from_by) ** 2)
                acts.append({'do': 'attack', 'world': list(tgt['world_pos'])})
                self._attack_cd = ATTACK_COOLDOWN
                reason.append('兵力%d→锁定%s' % (army, tgt['class']))
                attacking = True

            # ---- C2. 驻防通道：霰弹/步枪步兵守基地（每次扫描持续调度） ----
            if n_guard > 0:
                acts.append({'do': 'defend_base'})
                reason.append('驻防%d人' % n_guard)

            # ---- C3. 飞艇轰炸：kirov 专职攻击敌方防御建筑 ----
            if ucount('kirov') > 0 and self._airraid_cd <= 0 and enemy_bld:
                DEF_KEYS = ('laser', 'bunker', 'bastion', 'antiair',
                            'turret', 'bombard', 'missile', 'aa')
                def_tgts = [e for e in enemy_bld
                            if any(k in e['class'].lower() for k in DEF_KEYS)]
                if def_tgts:
                    from_bx, from_by = base_pos or (WORLD_WIDTH / 2,
                                                    WORLD_HEIGHT / 2)
                    tgt = min(def_tgts,
                              key=lambda e: (e['world_pos'][0] - from_bx) ** 2 +
                                            (e['world_pos'][1] - from_by) ** 2)
                    acts.append({'do': 'air_raid', 'world': list(tgt['world_pos'])})
                    self._airraid_cd = ATTACK_COOLDOWN
                    reason.append('飞艇→炸%s' % tgt['class'])

        # ---- D. 支援通道：资金富余 + 有雷达 → AC130 打敌方单位密集区 ----
        if not attacking and self._support_cd <= 0 and \
                money >= SUPPORT_COST_MARGIN + 2000:
            has_radar = any(getattr(b, 'alive', True) and b.team == my_team
                            and getattr(b, 'b_type', '') == 'radar'
                            for b in game.all_buildings)
            if has_radar and len(enemy_units) >= 2:
                # 目标：敌方单位质心（以某敌单位为中心放置）
                cx = sum(e['world_pos'][0] for e in enemy_units) / len(enemy_units)
                cy = sum(e['world_pos'][1] for e in enemy_units) / len(enemy_units)
                center = min(enemy_units,
                             key=lambda e: (e['world_pos'][0] - cx) ** 2 +
                                           (e['world_pos'][1] - cy) ** 2)
                acts.append({'do': 'support', 's_type': 'ac130',
                             'world': list(center['world_pos'])})
                self._support_cd = SUPPORT_COOLDOWN
                reason.append('AC130支援@敌%s' % center['class'])
                money -= 2000

        # ---- 2. 建造（BUILD 页）----
        # 无基地（全毁）时不建任何东西——读了条也无处放置，会白白烧钱
        sidebar = getattr(game, 'sidebar', None)
        building_now = False
        if sidebar is not None and base_pos is not None:
            for payload in BUILD_PRIORITY:
                if len(acts) >= 8:
                    break
                item = self._find_item(game, 'BUILD', payload)
                if item is None or not getattr(item, 'visible', True):
                    continue
                if getattr(item, 'is_ready', False) and base_pos:
                    spot = self._find_build_spot(game, base_pos)
                    if spot:
                        # 就绪即放，一轮可放多个（不 break，后面的就绪项继续放）
                        acts.append({'do': 'place', 'payload': payload, 'world': spot})
                        reason.append('放置%s' % payload)
                    else:
                        # 找不到落点：绝不静默——提示出来，且下一轮该条目仍会
                        # 反复尝试（若持续失败，说明基地圈真的满了）
                        reason.append('%s无空位待放' % payload)
                    continue
                if getattr(item, 'is_building', False):
                    building_now = True                          # 有项在读条
                    continue
                # 全部建筑按存活数量封顶（建够就跳过，让位下一项）
                cap = BUILD_COUNT_CAPS.get(payload)
                if cap is not None:
                    n_def = sum(1 for b in game.all_buildings
                                if getattr(b, 'alive', True) and b.team == my_team
                                and (getattr(b, 'b_type', '')
                                     or b.__class__.__name__.lower()) == payload)
                    if n_def >= cap:
                        continue
                cost = getattr(item, 'cost', 0)
                if money >= cost + BUILD_RESERVE and payload not in self._build_cd:
                    acts.append({'do': 'build', 'payload': payload})
                    self._build_cd[payload] = MIN_INTERVAL
                    money -= cost
                    reason.append('开建%s' % payload)
                    break                                        # 一轮开一项
            if building_now:
                reason.append('读条中')

        # ---- B. 生产通道：分支优先级（占领 → 经济 → 装甲 → 空军 → 步兵兜底）----
        if sidebar is not None and money > 0:
            items = sidebar.all_items.get('UNIT') or []

            def pick(payload):
                return next((it for it in items
                             if it.payload == payload
                             and getattr(it, 'visible', True)
                             and not getattr(it, 'is_building', False)), None)

            prod = None
            # 分支2 占领扩张：有敌对建筑缺运输车/工程师 → 优先补。
            # 两个约束防"工厂被工程师霸占"：
            #   a) 敌人贴脸（attacking）时暂停占领生产，战时优先战斗单位
            #   b) 工程师按"车内外总数"封顶 ENGINEER_TARGET——load_units 装
            #      车时会把单位从 all_units 移除，只数自由工程师则永远不够
            #      → 无限补工程师，坦克永远排不上
            n_eng_total = n_eng
            for u in game.all_units:
                if getattr(u, 'alive', True) and u.team == my_team \
                        and hasattr(u, 'cargo') and hasattr(u, 'capacity') \
                        and 'harvester' not in u.__class__.__name__.lower():
                    n_eng_total += sum(1 for c in (u.cargo or [])
                                       if hasattr(c, 'pos'))
            if neutrals and not attacking:
                if n_apc < APC_TARGET and pick('apc'):
                    prod = ('apc', '占领→造APC')
                elif n_apc > 0 and n_eng_total < ENGINEER_TARGET \
                        and pick('combat_engineer'):
                    prod = ('combat_engineer', '占领→补工程师')
                if prod is not None:
                    it = pick(prod[0])
                    if it is not None and money < getattr(it, 'cost', 0):
                        prod = None        # 占领单位买不起 → 让位战斗单位
            # 分支1 经济：矿车仅在 0 辆或"坦克都产不起"时优先（否则坦克主力，不让补车抢工厂）
            tank_item = pick('m1a2') or pick('t14') or pick('type99')
            tank_cost = getattr(tank_item, 'cost', 2000) if tank_item else 2000
            if prod is None and n_harv < HARVESTER_CAP and pick('harvester') \
                    and (n_harv == 0 or money < tank_cost):
                prod = ('harvester', '经济→矿车')
            # 分支1 装甲突击：坦克主力（用户要求：造 tank 出动不回防）
            if prod is None and n_tank < TANK_CAP:
                for t in ('m1a2', 't14', 'type99'):
                    if pick(t):
                        prod = (t, '装甲→' + t)
                        break
            # 分支5 驻防步兵：霰弹兵+步枪兵专职守基地（不编入进攻波）
            if prod is None and n_guard < GUARD_INF_CAP:
                # 霰弹兵当肉盾前排，步枪兵输出，交替补
                t = 'shotgunner' if n_guard % 2 == 0 else 'rifleman'
                if pick(t):
                    prod = (t, '驻防→' + t)
                elif pick('rifleman'):
                    prod = ('rifleman', '驻防→rifleman')
                elif pick('shotgunner'):
                    prod = ('shotgunner', '驻防→shotgunner')
            # 分支4 空军：飞艇专职轰炸敌方防御建筑（优先于战机）
            if prod is None:
                has_af = any(getattr(b, 'alive', True) and b.team == my_team
                             and getattr(b, 'b_type', '') == 'airfield'
                             for b in game.all_buildings)
                n_kirov = ucount('kirov')
                if has_af and n_kirov < KIROV_CAP and pick('kirov'):
                    prod = ('kirov', '飞艇→攻防御塔')
                elif has_af and n_air < AIR_CAP:
                    for t in ('fighterjet', 'attackplane', 'helicopter',
                              'wz10', 'kirov'):
                        if pick(t):
                            prod = (t, '空军→' + t)
                            break
            if prod:
                item = pick(prod[0])
                cost = getattr(item, 'cost', 0) if item else 1e9
                if item is not None and money >= cost:
                    acts.append({'do': 'produce', 'payload': prod[0]})
                    reason.append('生产%s' % prod[0])
                    money -= cost
                elif item is not None:
                    reason.append('%s缺钱(需%d)' % (prod[0], cost))

        if not acts:
            reason.append('本轮无动作')
        self.last_reason = '；'.join(reason)
        return acts[:8]
