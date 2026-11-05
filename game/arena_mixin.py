"""竞技场（争锋频道）玩法模块。

玩法循环（参考明日方舟争锋频道）：
  每轮系统按造价自动组建两支军团（team_0 红 / team_1 蓝，造价带随机偏斜），
  玩家押注认为获胜的一方并投入军费：押中投入翻倍，押错清零；
  战斗全程自动进行（arena_director 指挥双方推进），玩家观战；
  每轮结束可继续下一轮（再次押注）或退出（军费落盘保留）。

状态机（self.arena_phase）：
  IDLE  -> 未在竞技场
  BET   -> 展示双方阵容，玩家选阵营押注 / 跳过 / 退出
  FIGHT -> 自动战斗模拟（复用 update_game_world，屏蔽其全局胜负判定）
  RESULT-> 结算展示，下一轮 / 退出

组军与战场（每轮）：
  地图随机 50/50：铁血竞技场（ArenaColiseumMap，陆军池）或海上竞技场
  （ArenaSeaMap，海军+空军池，全域水域中央礁岛），池随图切换。
  组军按预算"成组"编成（每组同型 2~4 个单位，建筑 1 个/组，
  comp=[(类型,单价,数量)]），出兵时在己方半区（地图 spawn_zones）随机
  散布：组心随机 + 组间避让 + 组内成员绕组心随机偏移，呈"成建制小队"
  而非一条长列。固定翼已移出全部竞技场池；碉堡/堡垒等可攻击防御建筑
  也编入两军（不可移动、自身索敌开火、计入存活判定与毒圈伤害）。

迷雾竞技场（arena_mode="fog"，btn_fog 入口，DEPLOY 阶段）：
  开战前看不到敌军（秘密编成、开战瞬间才落位）。玩家自费布防：点选
  商店兵种（同组军池定价）点击己方半区落位，军费立即扣除且胜利也不
  退还；可花 100 军费购买情报查看敌军编成。电脑敌军按预算随机组军。
  结算：击杀敌军 = 造价 50% 军费；胜利 +200 / 失败 -150；平局无奖惩。
  每轮结束可下一轮或退出（军费落盘）。

胜负判定（与常规对局独立）：
  竞技场无基地；一方单位全部死亡即结束，同帧互灭为平局（退押注）；
  超过 90 秒未分胜负则按剩余单位总血量裁定。
  单位全局锁定：director 为无目标单位指派全图最近的敌方单位并持续追击
  （set_target ATTACK 模式，目标死亡自动解锁后重新锁定）。
  特殊单位自动化（arena_specials）：机器人生产车（无人机车）敌近自动
  部署量产自爆无人机、清场后收起转移；隐身直升机接敌切突击模式、
  脱战重新隐身。UI 覆盖层全部沉底（阵容/押注/结算面板），不遮挡战场。

军费存档：core/save_data.py -> config/save.json（每轮结算/押注/退出即落盘）。
"""
import math
import pygame
import random
from core.settings import *
from core.base_classes import *
from units import *
from maps import *
from core.save_data import load_save_data, write_save_data
from core.utils import cached_scale_img
from core.i18n import tr

# ---------------------------------------------------------------------------
# 配置表
# ---------------------------------------------------------------------------

# 组军池：(spawn_unit 类型名, 造价常量)。造价读 config/units.json 注入的常量。
# 固定翼（fighterjet）已移出竞技场。
ARENA_ARMY_POOL = [
    ("rifleman", RIFLEMAN_COST), ("shotgunner", SHOTGUNNER_COST),
    ("rocket", ROCKET_COST), ("sniper", SNIPER_COST),
    ("armored", ARMORED_COST), ("helicopter", HELICOPTER_COST),
    ("dronecarrier", DRONECARRIER_COST), ("apc", APC_COST),
    ("m1a2", M1A2_COST), ("stealheli", STEALHELI_COST),
    ("wz10", WZ10_COST), ("himars", HIMARS_COST),
    ("bmpt", TERMINATOR_COST),
    ("mi24", HIND_COST), ("type99", TYPE99_COST),
    ("mech", MECH_COST), ("kirov", KIROV_COST),
    # 建筑（陆图限定）：可攻击防御建筑也编入两军（组内 1 个/组，不可移动，
    # 由自身索敌开火；造价取竞技场内平衡价，非商店价）
    ("bunker", 700),      # 碉堡 hp=BUNKER_STATS 自动索敌
    ("bastion", 2500),    # 堡垒 四炮塔 hp5000（高预算轮次才解锁）
]

# 海上竞技场池：海军 + 空军（无地面/固定翼/建筑——地面单位在水上溺亡，
# 建筑无法落在水里）。海军造价在竞技场内自定（游戏中海军走造船体系，无
# 独立 COST 常量）；最低价 250 保证首轮最差预算 765 的 max_single（≈344）
# 也买得起，不会整轮只剩兜底编队。
ARENA_SEA_POOL = [
    ("missile_boat", 250),            # 导弹艇 hp600
    ("antiairfrigate", 500),          # 防空护卫舰（可对空）
    ("laserdestroyer", 750),          # 激光驱逐舰
    ("missilecruiser", 1000),         # 导弹巡洋舰
    ("helicopter", HELICOPTER_COST), ("stealheli", STEALHELI_COST),
    ("wz10", WZ10_COST), ("mi24", HIND_COST), ("kirov", KIROV_COST),
]

# 池内最低造价：推导"每轮总价值严格递增"的预算下界（组版：每组 2 个起）
ARENA_MIN_COST = min(c for _t, c in ARENA_ARMY_POOL)

# 建筑类型 -> 实例化工厂（建筑不走 spawn_unit，落位即定格）
ARENA_BUILDING_SPAWNERS = {
    "bunker": lambda g, p, t: Bunker(g, p, t),
    "bastion": lambda g, p, t: Bastion(g, p, t),
}

# ---- 迷雾竞技场 ----
ARENA_FOG_INTEL_COST = 100    # 情报费：一次性查看本轮敌军编成
ARENA_FOG_KILL_RATE = 1.2     # 击杀奖励 = 阵亡敌军造价的 100%（全额返还）
ARENA_FOG_WIN_REWARD = 500    # 胜利奖励
ARENA_FOG_LOSE_PENALTY = 150  # 失败罚金
ARENA_FOG_FADE_FRAMES = 100   # 开战后迷雾消散演出帧数


def _arena_build_fog_tex(w, h):
    """程序化云雾贴图（SRCALPHA）：多层半透明白团叠加，边缘渐隐。

    pygame.draw 不做混合（直接写像素），故每个雾团先画在独立小面上
    再 blit 回主贴图——重叠处 alpha 自然累积，形成云的浓淡层次。
    """
    tex = pygame.Surface((w, h), pygame.SRCALPHA)
    edge_fade = max(1.0, min(w, h) * 0.22)

    def _blot(cx, cy, r, color, alpha):
        fade = min(cx, w - cx, cy, h - cy) / edge_fade
        alpha = int(alpha * max(0.0, min(1.0, fade)))
        if alpha <= 0 or r <= 0:
            return
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*color, alpha), (r, r), r)
        tex.blit(s, (int(cx - r), int(cy - r)))

    # 大团打底：更淡更大，撑起整体体积感
    for _ in range(26):
        _blot(random.uniform(0, w), random.uniform(0, h),
              int(random.uniform(h * 0.16, h * 0.30)), (200, 210, 230), 7)
    # 主雾团：中小团密集叠加
    for _ in range(130):
        _blot(random.uniform(0, w), random.uniform(0, h),
              int(random.uniform(40, 150)), (212, 222, 238),
              random.uniform(9, 26))
    return tex

# 毒圈时间轴（帧）：20 秒开始缩圈，60 秒毒完全覆盖全图，每 0.5 秒结算一次毒伤
ARENA_ZONE_START = 1200
ARENA_ZONE_FULL = 3600
ARENA_ZONE_TICK = 30

ARENA_UNIT_NAMES = {
    "rifleman": "步枪兵", "shotgunner": "霰弹兵", "rocket": "火箭兵",
    "sniper": "狙击手", "armored": "装甲车", "helicopter": "直升机",
    "dronecarrier": "无人机车", "apc": "运兵车", "m1a2": "M1A2 坦克",
    "stealheli": "隐身直升机", "wz10": "武直-10", "himars": "海马斯",
    "fighterjet": "战斗机", "bmpt": "BMPT 终结者", "mi24": "雌鹿",
    "type99": "99A 主战", "mech": "重型机甲", "kirov": "基洛夫飞艇",
}

ARENA_TEAM_INFO = {
    "team_0": {"name": "红方军团", "color": (200, 60, 50), "panel_bg": (38, 26, 24)},
    "team_1": {"name": "蓝方军团", "color": (70, 120, 210), "panel_bg": (24, 30, 40)},
}

# 每轮中立生成池：(工厂, 权重)。点位来自 ArenaColiseumMap.neutral_spots。
def _mk_oil(g, p): return OilDerrick(g, p)
def _mk_house(g, p): return CivilianHouse(g, p)
def _mk_sky(g, p): return Skyscraper(g, p)
def _mk_temple(g, p): return AncientTemple(g, p)
def _mk_bunker(g, p): return Bunker(g, p, "neutral")
def _mk_scav(g, p): return ScavengerWalker(g, p)

ARENA_NEUTRAL_MAKERS = [
    (_mk_oil, 3), (_mk_house, 2), (_mk_sky, 1),
    (_mk_temple, 1), (_mk_bunker, 2), (_mk_scav, 2),
]
# 海图（ArenaSeaMap）自带 neutral_makers 中立舰船工厂，无需回退池


class ArenaMixin:
    # ==================== 入口 / 退出 ====================
    def arena_enter(self, mode="standard"):
        """从菜单进入竞技场（btn_easy=标准押注观战 / btn_fog=迷雾布防）。"""
        self.arena_mode = mode
        data = load_save_data()
        self.arena_funds = data["funds"]
        self.arena_streak = 0
        self.arena_round = 0
        self.arena_bet = 0
        self.arena_bet_team = None
        self.arena_last_cost_max = 0  # 上一轮双方实际总造价最大值（递增下界）
        self.arena_ratio = 0.5
        self.arena_phase = "IDLE"
        self.arena_active = True
        self.arena_army_info = {}
        self.arena_result_text = ""
        self.arena_result_win = None
        self.arena_result_winner = None
        self.arena_ui = {}
        self.arena_fog_intel = False
        self.arena_fog_selected = None
        self.arena_fog_spent = 0
        self.arena_fog_snapshot = []
        self.arena_fog_placed = []  # 本轮已布防 [(实体, 造价, 类型名)]，可右键退款删除
        self.is_online = False
        self.is_spectator = False
        self.my_role = "HOST"
        self.my_team = "team_0"
        self.paused = False
        self.bombardment_mode = False
        self.difficulty = "NORMAL"  # 竞技场无 AICommander，此值不生效
        from core.factions import get_random_faction
        self.my_faction, _ = get_random_faction()
        self.enemy_faction, _ = get_random_faction()
        self.teams_config = {
            "team_0": {"name": "红方军团", "faction": self.my_faction},
            "team_1": {"name": "蓝方军团", "faction": self.enemy_faction},
        }
        # 随机地图：陆上斗兽场（陆军池）/ 海上竞技场（海军+空军池）。
        # 池随图切换；spawn_zones（己方半区 Rect）由地图类提供。
        if random.random() < 0.5:
            self.arena_map_class = ArenaColiseumMap
            self.arena_army_pool = ARENA_ARMY_POOL
        else:
            self.arena_map_class = ArenaSeaMap
            self.arena_army_pool = ARENA_SEA_POOL
        self.reset_game()  # arena_active 时使用上面随机到的专属地图
        self.state = "LOADING"
        self.play_music(self.common_music["loading"])

    def arena_exit(self):
        """退出竞技场回菜单，军费与战绩落盘。"""
        self._arena_persist()
        self.arena_active = False
        self.arena_phase = "IDLE"
        self.arena_mode = "standard"
        self.arena_fog_selected = None
        self.arena_fog_snapshot = []
        self.arena_bet = 0
        self.arena_bet_team = None
        self.dragging = False
        self.selected_entity = None
        self.place_building_type = None
        self.state = "MENU"
        self.current_music_state = "FORCE_RESET"

    def _arena_persist(self):
        """把当前军费/战绩写回存档。"""
        data = load_save_data()
        data["funds"] = max(0, int(self.arena_funds))
        write_save_data(data)

    # ==================== 回合流程 ====================
    def arena_start_round(self):
        """开启新一轮：清场（首轮除外）-> 中立生成 -> 按造价组军 -> BET 阶段。

        竞技场无基地，地图 bases_config 仅作双方出兵锚点。
        """
        self.arena_round += 1
        if self.arena_round > 1:
            # 软清场：首轮实体由 reset_game/init_level 生成，之后每轮重建
            self.all_units = []
            self.all_buildings = []
            self.projectiles = []
            self.particles = pygame.sprite.Group()
            self.floating_texts = pygame.sprite.Group()

        # 每轮在地图合适点位随机生成中立建筑/单位
        self.arena_spawn_neutrals()

        self.arena_bet = 0
        self.arena_bet_team = None
        self.arena_fight_frames = 0
        if getattr(self, 'arena_mode', 'standard') == "fog":
            return self._arena_setup_fog_round()

        # 标准模式：按造价组建两军：预算随轮次线性增长（不封顶），且带严格
        # 递增下界——无论随机偏斜如何，本轮双方总造价必然高于上一轮
        base_budget = 900 + (self.arena_round - 1) * 350
        pool = self.arena_army_pool  # 陆战场/海战场在 arena_enter 时按地图定池
        min_cost = min(c for _t, c in pool)
        prev_max = getattr(self, 'arena_last_cost_max', 0)
        floor = (prev_max + 2 * min_cost) if prev_max > 0 else 0
        skew = random.uniform(-0.15, 0.15)
        budget0 = max(int(base_budget * (1 + skew)), floor)
        budget1 = max(int(base_budget * (1 - skew)), floor)
        comp0, cost0 = self.arena_compose_army(budget0, pool)
        comp1, cost1 = self.arena_compose_army(budget1, pool)
        self.arena_last_cost_max = max(cost0, cost1)
        self.arena_army_info = {
            "team_0": {"comp": comp0, "cost": cost0},
            "team_1": {"comp": comp1, "cost": cost1},
        }
        self._arena_spawn_comp("team_0", comp0)
        self._arena_spawn_comp("team_1", comp1)
        self.arena_phase = "BET"

    def _arena_spawn_comp(self, t, comp):
        """把编成 [(类型,单价,数量)] 随机散布部署到 t 方半区。

        每组占一块区域（组心随机+组间避让），组内成员围绕组心随机偏移，
        呈"成建制小队"而非一条长列；建筑类型直接落位（组心附近小偏移）。
        返回 [(实体, 造价)]（迷雾竞技场用造价做击杀奖励）。
        """
        zone = self.current_map.spawn_zones[t]
        used, ents = [], []
        for u_type, cost, count in comp:
            gc = self._arena_random_group_center(zone, used, count)
            used.append((gc, count))
            if u_type in ARENA_BUILDING_SPAWNERS:
                off = vec(1, 0).rotate(random.uniform(0, 360)) * \
                    random.uniform(0, 40)
                ent = ARENA_BUILDING_SPAWNERS[u_type](self, gc + off, t)
                self.all_buildings.append(ent)
                ents.append((ent, cost))
                continue
            for _i in range(count):
                off = vec(1, 0).rotate(random.uniform(0, 360)) * \
                    random.uniform(0, 75)
                origin = gc + off
                # spawn_unit 内部固定 +100y 兜底，这里预先补偿
                self.spawn_unit(u_type, vec(origin.x, origin.y - 100), t)
                ents.append((self.all_units[-1], cost))
        return ents

    def _arena_setup_fog_round(self):
        """迷雾竞技场回合准备：秘密生成敌军（蓝方）编成但不部署。

        玩家进入 DEPLOY 阶段自费布防；敌军编成在开战瞬间才落位，
        开战前完全看不到（花钱买情报可看编成清单）。
        """
        base_budget = 900 + (self.arena_round - 1) * 350
        pool = self.arena_army_pool
        min_cost = min(c for _t, c in pool)
        prev_max = getattr(self, 'arena_last_cost_max', 0)
        floor = (prev_max + 2 * min_cost) if prev_max > 0 else 0
        budget1 = max(int(base_budget * random.uniform(0.9, 1.2)), floor)
        comp1, cost1 = self.arena_compose_army(budget1, pool)
        self.arena_last_cost_max = max(prev_max, cost1)
        self.arena_army_info = {"team_0": {"comp": [], "cost": 0},
                                "team_1": {"comp": comp1, "cost": cost1}}
        self.arena_fog_intel = False
        self.arena_fog_spent = 0
        self.arena_fog_selected = None
        self.arena_fog_snapshot = []
        self.arena_fog_placed = []
        self.arena_phase = "DEPLOY"

    # ==================== 迷雾竞技场：布防 / 情报 ====================
    def arena_fog_select(self, u_type):
        """选中/取消商店中的兵种（选中后点击己方半区落位）。"""
        self.arena_fog_selected = None if self.arena_fog_selected == u_type \
            else u_type

    def arena_fog_place_at(self, world_pos):
        """在己方半区落位当前选中的兵种，立即扣军费（胜利也不退还）。"""
        u_type = self.arena_fog_selected
        if not u_type:
            return
        price = dict(self.arena_army_pool)[u_type]
        if self.arena_funds < price:
            self.show_alert(tr("ar.alert_deploy"))
            self.arena_fog_selected = None
            return
        zone = self.current_map.spawn_zones["team_0"]
        p = vec(max(zone.left + 50, min(world_pos.x, zone.right - 50)),
                max(zone.top + 50, min(world_pos.y, zone.bottom - 50)))
        self.arena_funds -= price
        self.arena_fog_spent += price
        if u_type in ARENA_BUILDING_SPAWNERS:
            ent = ARENA_BUILDING_SPAWNERS[u_type](self, p, "team_0")
            self.all_buildings.append(ent)
        else:
            self.spawn_unit(u_type, vec(p.x, p.y - 100), "team_0")
            ent = self.all_units[-1]  # spawn_unit 固定 append 一个实例
        self.arena_fog_placed.append((ent, price, u_type))
        info = self.arena_army_info["team_0"]
        info["comp"].append((u_type, price, 1))
        info["cost"] += price

    def arena_fog_remove_at(self, world_pos):
        """右键删除己方已布防的单位/建筑，退还军费（DEPLOY 布防阶段）。"""
        for ent, cost, u_type in reversed(self.arena_fog_placed):
            if not ent.alive:
                continue
            if ent.rect.collidepoint(int(world_pos.x), int(world_pos.y)):
                ent.alive = False
                if ent in self.all_units:
                    self.all_units.remove(ent)
                elif ent in self.all_buildings:
                    self.all_buildings.remove(ent)
                self.arena_funds += cost
                self.arena_fog_spent -= cost
                self.arena_fog_placed.remove((ent, cost, u_type))
                info = self.arena_army_info["team_0"]
                if (u_type, cost, 1) in info["comp"]:
                    info["comp"].remove((u_type, cost, 1))
                    info["cost"] -= cost
                return True
        return False

    def arena_fog_buy_intel(self):
        """花费军费购买敌军情报（本轮一次性，显示蓝方完整编成）。"""
        if self.arena_fog_intel:
            return
        if self.arena_funds < ARENA_FOG_INTEL_COST:
            self.show_alert(tr("ar.alert_intel"))
            return
        self.arena_funds -= ARENA_FOG_INTEL_COST
        self.arena_fog_intel = True
        self._arena_persist()

    def arena_spawn_neutrals(self):
        """在竞技场地图预留点位随机布置中立建筑/单位（每轮不同）。

        makers 取自当前地图的 neutral_makers 属性（陆图=建筑/拾荒者，
        海图=中立舰船），地图未提供时回退陆上池。
        """
        spots = list(getattr(self.current_map, 'neutral_spots', []))
        if not spots:
            return
        random.shuffle(spots)
        count = min(len(spots), random.randint(3, 5))
        makers_def = getattr(self.current_map, 'neutral_makers', None) \
            or ARENA_NEUTRAL_MAKERS
        makers = [m for m, _w in makers_def]
        weights = [w for _m, w in makers_def]
        for i in range(count):
            ent = random.choices(makers, weights=weights)[0](self, spots[i])
            if isinstance(ent, Building):
                self.all_buildings.append(ent)
            else:
                self.all_units.append(ent)

    def arena_compose_army(self, budget, pool):
        """按预算随机组建一支军团（成组模式）。

        返回 ([(类型, 单价, 数量)], 总造价)。每组为同类型单位 2~4 个
        （优先大组，呈"一个班"出现而不是散兵）；单件造价不超过预算 45%
        （防止一轮全是基洛夫）；总人数上限随预算放大，保证最坏情况
        （全买最低价单位）也能把预算花满。循环结束时剩余预算必低于
        2×池最低单价，因此 实际总造价 > 预算 - 2×min_cost ≥ 上一轮双方
        最高实际造价，即"每轮单位总价值严格递增"。
        """
        comp = []
        total = 0
        n_units = 0
        max_single = max(int(budget * 0.45), 300)
        min_cost = min(c for _t, c in pool)
        max_units = max(14, budget // min_cost)
        while total < budget and n_units < max_units:
            options = []
            for t, c in pool:
                if c > max_single:
                    continue
                # 建筑组内只有 1 个（不可移动，多建挤在一起）；单位 4>3>2 优先
                for n in ((1,) if t in ARENA_BUILDING_SPAWNERS else (4, 3, 2)):
                    if c * n <= budget - total and n_units + n <= max_units:
                        options.append((t, c, n))
                        break
            if not options:
                break
            t, c, n = random.choice(options)
            comp.append((t, c, n))
            total += c * n
            n_units += n
        if not comp:
            t, c = min(pool, key=lambda kv: kv[1])
            comp = [(t, c, 1 if t in ARENA_BUILDING_SPAWNERS else 2)]
            total = c * comp[0][2]
        return comp, total

    def _arena_random_group_center(self, zone, used, size):
        """在己方半区 Rect 内随机取一个组中心点，与已有组保持间距。

        used 为 [(中心, 数量)]；组间距按双方组员规模动态计算，
        尝试 40 次找不到就放宽到地图内任意点（几乎不会发生）。
        """
        for _try in range(40):
            p = vec(random.uniform(zone.left + 90, zone.right - 90),
                    random.uniform(zone.top + 90, zone.bottom - 90))
            ok = True
            for uc, un in used:
                if p.distance_to(uc) < (size + un) * 22 + 60:
                    ok = False
                    break
            if ok:
                return p
        return vec(random.uniform(zone.left + 90, zone.right - 90),
                   random.uniform(zone.top + 90, zone.bottom - 90))

    def arena_place_bet(self, team):
        """按当前比例押注所选阵营并开战。押注即扣款并落盘。"""
        stake = int(self.arena_funds * self.arena_ratio)
        if stake <= 0:
            self.show_alert(tr("ar.alert_bet"))
            return
        self.arena_funds -= stake
        self.arena_bet = stake
        self.arena_bet_team = team
        self._arena_persist()
        self.arena_start_fight()

    def arena_start_fight(self):
        """进入战斗阶段（押注/跳过后；迷雾模式在开战瞬间才部署敌军）。"""
        self.arena_fight_frames = 0
        self.arena_zone_progress = 0.0
        m = self.current_map
        # 安全区初始半径 = 地图对角线半径（毒从四角外向场心推进）
        self.arena_zone_max_r = (((m.width / 2.0) ** 2 + (m.height / 2.0) ** 2) ** 0.5
                                 if m else 1500.0)
        if getattr(self, 'arena_mode', 'standard') == "fog":
            # DEPLOY 阶段全程看不到敌军，开战瞬间才落位并记下造价
            self.arena_fog_snapshot = self._arena_spawn_comp(
                "team_1", self.arena_army_info["team_1"]["comp"])
        self.arena_phase = "FIGHT"
        self.selected_entity = None

    def arena_next_round(self):
        """结算后开下一轮；军费不足 100 时发放救济金让玩家能翻本。"""
        if self.arena_funds < 100:
            self.arena_funds = 100
            self.show_alert(tr("ar.alert_relief"))
        self.arena_start_round()

    # ==================== 战斗模拟 ====================
    def arena_update(self):
        """竞技场主循环（update() 的 ARENA 状态分支）。"""
        self.arena_clamp_camera()  # 初始定位等任何越界镜头在帧首拉回
        if self.arena_phase == "FIGHT":
            self.arena_fight_frames += 1
            # 复用通用世界模拟（其中已含每帧 _path_budget 重置）；
            # _arena_fighting 屏蔽其全局胜负判定，由 arena_check_result
            # 用竞技场自己的规则结算
            self._arena_fighting = True
            self.update_game_world()
            self._arena_fighting = False
            self.arena_director()
            self.arena_specials()
            self.arena_zone_update()
            result = self.arena_check_result()
            if result:
                self.arena_settle(result)
        else:
            # BET/RESULT 阶段：只跑特效与环境动画，单位保持静止（防止下注前开打）
            self.particles.update()
            self.floating_texts.update()
            if self.arena_phase == "DEPLOY":
                self.sidebar.update()  # 布防侧栏（经典 UI）可见性与滚动
            if self.current_map and hasattr(self.current_map, 'update'):
                self.current_map.update()
        if self.active_alert:
            self.active_alert[1] -= 1
            if self.active_alert[1] <= 0:
                self.active_alert = None

    def arena_director(self):
        """全局锁定：为没有目标的单位指派全图最近的敌方单位。

        set_target 进入 ATTACK 模式，单位会持续追击该目标直至其死亡
        （目标死亡时 Unit.update 自动清空 target_entity），下一个 director
        周期再重新锁定，即"锁定到死"。只锁参战单位，不锁中立目标/建筑
        （竞技场无基地）；若当前目标是中立敌对单位（如拾荒者）则强制改锁
        真正的敌军。对空无能的单位只指派地面目标（否则 set_target 内部
        会降级为 move_to 追击空中单位原地打转）；隐身单位在近距以外
        不会被锁定，保留隐兵突袭的博弈空间。
        """
        if self.frame_count % 30 != 0:
            return
        enemies_by_team = {"team_0": [], "team_1": []}
        for u in self.all_units:
            if u.alive and u.team in enemies_by_team:
                enemies_by_team[u.team].append(u)
        # 防御建筑（碉堡/堡垒）也作为锁定目标（它们不追击，靠自身索敌开火）
        for b in self.all_buildings:
            if getattr(b, 'alive', False) and b.team in enemies_by_team:
                enemies_by_team[b.team].append(b)
        for u in self.all_units:
            if not u.alive or u.team not in enemies_by_team:
                continue
            tgt = getattr(u, 'target_entity', None)
            if tgt is not None and tgt.alive and tgt.team in ("team_0", "team_1"):
                continue  # 已锁定敌方参战单位（锁定到死）
            enemies = enemies_by_team["team_1" if u.team == "team_0" else "team_0"]
            if not enemies:
                continue
            # 过滤：打不到的空中单位、80px 外的隐身单位不作锁定候选
            cands = [e for e in enemies
                     if not (e.is_air and not u.can_attack_air)
                     and not (getattr(e, 'is_stealth', False)
                              and u.pos.distance_to(e.pos) > 80)]
            if not cands:
                cands = [e for e in enemies
                         if not (e.is_air and not u.can_attack_air)]
            if not cands:
                continue
            nearest = min(cands, key=lambda e: u.pos.distance_to(e.pos))
            u.set_target(nearest)

    # ==================== 特殊单位自动化 ====================
    def arena_specials(self):
        """让带特殊机制的单位在自动战斗中真正用上特殊效果。

        DroneCarrier（机器人生产车/无人机车）：敌近自动部署量产自爆无人机，
        战区清空后收起转移（部署状态无法移动且持续自损，收放互带迟滞防抖）。
        StealthHeli（隐身直升机）：默认隐身（射程被压到贴身炸弹），
        接敌自动切换突击模式启用机炮，脱战后重新隐身。
        """
        for u in self.all_units:
            if not u.alive or u.team not in ("team_0", "team_1"):
                continue
            if isinstance(u, DroneCarrier):
                _e, d = self._arena_nearest_enemy_dist(u)
                if u.carrier_state == "MOBILE":
                    if d is not None and d <= 600:
                        u.toggle_mode()  # 展开：开始生产自爆无人机
                elif d is None or d > 900:
                    u.toggle_mode()  # 周边无敌人：收起转移
            elif isinstance(u, StealthHeli):
                _e, d = self._arena_nearest_enemy_dist(u)
                if u.stealth_mode:
                    if d is not None and d <= u.cannon_range * 1.2:
                        u.toggle_mode()  # 接敌：切突击模式启用机炮
                elif d is None or d > u.cannon_range * 1.8:
                    u.toggle_mode()  # 脱离：重新隐身

    def _arena_nearest_enemy_dist(self, u):
        """返回 (最近敌方参战单位, 距离)；无则 (None, None)。"""
        best, best_d = None, None
        for e in self.all_units:
            if not e.alive or e.team not in ("team_0", "team_1") or e.team == u.team:
                continue
            d = u.pos.distance_to(e.pos)
            if best_d is None or d < best_d:
                best, best_d = e, d
        return best, best_d

    # ==================== 毒圈 ====================
    def arena_zone_update(self):
        """毒圈：20 秒后安全区（圆）从全图向场心收缩，60 秒毒完全覆盖。

        毒区内参战单位按最大生命值百分比持续掉血——无视护甲/护盾直接扣
        hp（take_damage 会被护甲削减到保底 1，起不到终结作用），死亡走
        die() 正常出爆炸特效。覆盖越深毒伤越重（3%/秒 -> 6%/秒），保证
        僵局战斗必然被毒终结（先于 90 秒超时兜底）。中立单位不受毒。
        """
        t = self.arena_fight_frames
        if t < ARENA_ZONE_START:
            return
        self.arena_zone_progress = min(
            1.0, (t - ARENA_ZONE_START) / (ARENA_ZONE_FULL - ARENA_ZONE_START))
        if t % ARENA_ZONE_TICK:
            return
        m = self.current_map
        if not m:
            return
        center = vec(m.width / 2.0, m.height / 2.0)
        r_safe = self.arena_zone_max_r * (1.0 - self.arena_zone_progress)
        pct = 0.015 * (1.0 + self.arena_zone_progress)  # 3% -> 6% 每秒
        targets = list(self.all_units) + [
            b for b in self.all_buildings
            if getattr(b, 'alive', False) and b.team in ("team_0", "team_1")]
        for u in targets:
            if not u.alive or u.team not in ("team_0", "team_1"):
                continue
            if u.pos.distance_to(center) >= r_safe:
                u.hp -= max(1, int(u.max_hp * pct))
                if u.hp <= 0:
                    u.die()

    def arena_check_result(self):
        """竞技场胜负判定：一方单位全部死亡即结束。

        返回 'team_0' / 'team_1' / 'DRAW' / None(未结束)。
        开局 4 秒保护期不判定；90 秒未分胜负按剩余单位总血量裁定。
        """
        if self.arena_fight_frames < 240:
            return None
        alive = {"team_0": 0, "team_1": 0}
        for u in self.all_units:
            if u.alive and u.team in alive:
                alive[u.team] += 1
        for b in self.all_buildings:  # 防御建筑也算存活战力
            if getattr(b, 'alive', False) and b.team in alive:
                alive[b.team] += 1
        if alive["team_0"] == 0 and alive["team_1"] == 0:
            return "DRAW"
        if alive["team_1"] == 0:
            return "team_0"
        if alive["team_0"] == 0:
            return "team_1"
        if self.arena_fight_frames > 5400:  # 90 秒超时：按剩余总血量裁定
            hp = {"team_0": 0, "team_1": 0}
            for u in self.all_units:
                if u.alive and u.team in hp:
                    hp[u.team] += max(0, u.hp)
            for b in self.all_buildings:
                if getattr(b, 'alive', False) and b.team in hp:
                    hp[b.team] += max(0, b.hp)
            if hp["team_0"] == hp["team_1"]:
                return "DRAW"
            return "team_0" if hp["team_0"] > hp["team_1"] else "team_1"
        return None

    def arena_settle(self, winner):
        """结算：标准=押中翻倍/押错归零/平局退款；迷雾=击杀+胜负奖惩。"""
        if getattr(self, 'arena_mode', 'standard') == "fog":
            return self._arena_settle_fog(winner)
        self.arena_phase = "RESULT"
        self.arena_result_winner = winner
        win_name = tr("ar.team_red" if winner == "team_0" else "ar.team_blue") \
            if winner in ARENA_TEAM_INFO else tr("ar.none")
        if winner == "DRAW":
            self.arena_funds += self.arena_bet
            self.arena_result_text = tr("ar.result_draw")
            self.arena_result_detail = tr("ar.result_draw_d")
            self.arena_result_win = None
        elif self.arena_bet_team and winner == self.arena_bet_team:
            self.arena_funds += self.arena_bet * 2
            self.arena_result_text = tr("ar.result_win")
            self.arena_result_detail = tr("ar.result_win_d", name=win_name, n=self.arena_bet * 2)
            self.arena_result_win = True
            self.arena_streak += 1
        elif self.arena_bet_team:
            self.arena_result_text = tr("ar.result_lose")
            self.arena_result_detail = tr("ar.result_lose_d", name=win_name, n=self.arena_bet)
            self.arena_result_win = False
            self.arena_streak = 0
        else:
            self.arena_result_text = tr("ar.result_nobet")
            self.arena_result_detail = tr("ar.result_nobet_d", name=win_name)
            self.arena_result_win = None
        # 观战奖励：每看完一场战斗 +50 军费（无论押注结果）
        self.arena_funds += 50
        self.arena_result_detail += tr("ar.watch_bonus")
        self.arena_bet = 0
        self.arena_bet_team = None
        # 战绩落盘（军费/场次/胜场/最高连胜）
        data = load_save_data()
        data["funds"] = max(0, int(self.arena_funds))
        data["stats"]["rounds"] = data["stats"].get("rounds", 0) + 1
        if self.arena_result_win:
            data["stats"]["wins"] = data["stats"].get("wins", 0) + 1
        data["stats"]["best_streak"] = max(data["stats"].get("best_streak", 0),
                                           self.arena_streak)
        write_save_data(data)

    def _arena_settle_fog(self, winner):
        """迷雾竞技场结算：击杀奖励 + 胜负奖惩；布防花费不退还。"""
        self.arena_phase = "RESULT"
        self.arena_result_winner = winner
        dead = [(e, c) for e, c in self.arena_fog_snapshot
                if not getattr(e, 'alive', False)]
        kill_reward = int(sum(c for _e, c in dead) * ARENA_FOG_KILL_RATE)
        self.arena_funds += kill_reward
        parts = [tr("ar.fog_kills", n=len(dead), r=kill_reward)]
        if winner == "team_0":
            self.arena_funds += ARENA_FOG_WIN_REWARD
            self.arena_result_text = tr("ar.fog_hold")
            self.arena_result_win = True
            self.arena_streak += 1
            parts.append(tr("ar.fog_win", n=ARENA_FOG_WIN_REWARD))
        elif winner == "DRAW":
            self.arena_result_text = tr("ar.result_draw")
            self.arena_result_win = None
        else:
            self.arena_funds = max(0, self.arena_funds - ARENA_FOG_LOSE_PENALTY)
            self.arena_result_text = tr("ar.fog_lost")
            self.arena_result_win = False
            self.arena_streak = 0
            parts.append(tr("ar.fog_lose", n=ARENA_FOG_LOSE_PENALTY))
        self.arena_result_detail = tr("ar.sep").join(parts) + \
            tr("ar.fog_spent", n=self.arena_fog_spent)
        self.arena_bet = 0
        self.arena_bet_team = None
        data = load_save_data()
        data["funds"] = max(0, int(self.arena_funds))
        data["stats"]["rounds"] = data["stats"].get("rounds", 0) + 1
        if self.arena_result_win:
            data["stats"]["wins"] = data["stats"].get("wins", 0) + 1
        data["stats"]["best_streak"] = max(data["stats"].get("best_streak", 0),
                                           self.arena_streak)
        write_save_data(data)

    # ==================== 镜头钳制 ====================
    def arena_clamp_camera(self):
        """竞技场镜头硬钳制：完全限制在地图边界内，看不到地图外。

        通用 clamp_camera 带 SIDEBAR_WIDTH 口径和"视口大于地图时居中"回退
        （会露出地图外黑边），竞技场无侧栏，这里单独钳：
        缩放下限 = max(屏宽/图宽, 屏高/图高)，保证视口永远不大于地图；
        位置钳在 [0, 地图-视口]。WASD/拖拽/缩放/初始定位任何路径设置的
        越界镜头都会在帧内被拉回。
        """
        m = self.current_map
        if not m:
            return
        min_zoom = max(SCREEN_WIDTH / m.width, SCREEN_HEIGHT / m.height)
        if self.zoom < min_zoom:
            self.zoom = min_zoom
        vp_w = SCREEN_WIDTH / self.zoom
        vp_h = SCREEN_HEIGHT / self.zoom
        self.camera_offset.x = max(0.0, min(self.camera_offset.x, m.width - vp_w))
        self.camera_offset.y = max(0.0, min(self.camera_offset.y, m.height - vp_h))

    # ==================== 输入 ====================
    def handle_arena_input(self):
        """竞技场输入：镜头控制 + 下注/结算面板点击。"""
        self.arena_clamp_camera()
        self.update_camera_pan()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.apply_display_mode(not getattr(self, 'fullscreen', False))
                continue
            if event.type == pygame.MOUSEWHEEL:
                # DEPLOY 布防时滚轮在侧栏列表上=滚动建造列表（小地图区除外），
                # 其余情况与经典对战一致缩放镜头
                m_pos = pygame.mouse.get_pos()
                if self.arena_phase == "DEPLOY" \
                        and self.sidebar.rect.collidepoint(m_pos) \
                        and not self.minimap.rect.collidepoint(m_pos):
                    self.sidebar.scroll(-event.y * 45)
                else:
                    self.zoom_at(event.y > 0)
                continue
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 \
                    and self.arena_phase == "DEPLOY":
                m_pos = pygame.mouse.get_pos()
                if not self.sidebar.rect.collidepoint(m_pos) \
                        and self.arena_fog_remove_at(self.screen_to_world(m_pos)):
                    continue  # 右键点已布防单位/建筑 = 删除并退款
                self.arena_fog_selected = None  # 其余右键 = 取消当前选中兵种
                continue
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                m_pos = pygame.mouse.get_pos()
                ui = getattr(self, 'arena_ui', {})
                # 收起/展开键（全阶段通用，优先级最高）
                if ui.get("toggle") and ui["toggle"].collidepoint(m_pos):
                    self.arena_ui_collapsed = not getattr(self, 'arena_ui_collapsed', False)
                    continue
                if self.arena_phase == "DEPLOY":
                    # 布防侧栏（经典 UI）：点击侧栏区域一律交给侧栏处理
                    # （选兵/切标签/滚动/小地图区），不触发地图落位
                    if self.sidebar.rect.collidepoint(m_pos):
                        self.sidebar.handle_event(event)
                        continue
                    if ui.get("intel") and ui["intel"].collidepoint(m_pos):
                        self.arena_fog_buy_intel()
                    elif ui.get("start") and ui["start"].collidepoint(m_pos):
                        if not self.arena_army_info["team_0"]["comp"]:
                            self.show_alert(tr("ar.alert_deploy1"))
                        else:
                            self.arena_fog_selected = None
                            self.arena_start_fight()
                    elif ui.get("exit") and ui["exit"].collidepoint(m_pos):
                        self.arena_exit()
                    elif self.arena_fog_selected:
                        # 点战场空白处：在己方半区落位（自动钳入半区）
                        self.arena_fog_place_at(self.screen_to_world(m_pos))
                elif self.arena_phase == "BET":
                    if ui.get("left") and ui["left"].collidepoint(m_pos):
                        self.arena_place_bet("team_0")
                    elif ui.get("right") and ui["right"].collidepoint(m_pos):
                        self.arena_place_bet("team_1")
                    elif ui.get("r25") and ui["r25"].collidepoint(m_pos):
                        self.arena_ratio = 0.25
                    elif ui.get("r50") and ui["r50"].collidepoint(m_pos):
                        self.arena_ratio = 0.5
                    elif ui.get("r100") and ui["r100"].collidepoint(m_pos):
                        self.arena_ratio = 1.0
                    elif ui.get("skip") and ui["skip"].collidepoint(m_pos):
                        self.arena_start_fight()
                    elif ui.get("exit") and ui["exit"].collidepoint(m_pos):
                        self.arena_exit()
                elif self.arena_phase == "RESULT":
                    if ui.get("next") and ui["next"].collidepoint(m_pos):
                        self.arena_next_round()
                    elif ui.get("exit") and ui["exit"].collidepoint(m_pos):
                        self.arena_exit()
                else:
                    # FIGHT 阶段：左键拖拽平移镜头
                    self.dragging = True
                    self.last_mouse_pos = vec(m_pos)
            elif event.type == pygame.MOUSEMOTION:
                if self.arena_phase == "DEPLOY" and self.sidebar.dragging_scrollbar:
                    # 滚动条拖动跟随（滑出侧栏也持续，与经典对战一致）
                    self.sidebar.update_scrollbar_drag(pygame.mouse.get_pos())
                elif getattr(self, 'dragging', False) \
                        and self.arena_phase == "FIGHT":
                    self.handle_camera_drag(pygame.mouse.get_pos())
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.arena_phase == "DEPLOY":
                    self.sidebar.end_scrollbar_drag()  # 滚动条拖动结束
                self.dragging = False
        # 滚轮缩放/WASD/拖拽之后的统一边界修正
        self.arena_clamp_camera()

    # ==================== 绘制 ====================
    def arena_draw(self):
        """竞技场绘制：世界 + 覆盖层。"""
        if self.current_map:
            self.draw_world()
        else:
            self.screen.fill(BLACK)
        self.arena_draw_overlay()

    def _arena_btn(self, rect, text, hover_color=(90, 110, 140),
                   normal_color=(55, 65, 85), border=(160, 170, 190)):
        hover = rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(self.screen, hover_color if hover else normal_color,
                         rect, border_radius=6)
        pygame.draw.rect(self.screen, border, rect, 2, border_radius=6)
        surf = self.ui_font.render(text, True, WHITE)
        self.screen.blit(surf, surf.get_rect(center=rect.center))
        return hover

    # ==================== 迷雾特效 ====================
    def arena_draw_fog(self):
        """迷雾竞技场：敌区上空的战争迷雾（DEPLOY 常驻，开战后消散）。

        双层不同速横向滚动 + alpha 呼吸；跟随镜头平移与缩放；
        在 arena_draw_overlay 开头调用（世界之上、UI 之下）。
        """
        if getattr(self, 'arena_mode', 'standard') != "fog":
            return
        if self.arena_phase == "DEPLOY":
            alpha_scale = 1.0
        elif self.arena_phase == "FIGHT":
            alpha_scale = 1.0 - self.arena_fight_frames / ARENA_FOG_FADE_FRAMES
            if alpha_scale <= 0:
                return
        else:
            return
        zones = getattr(self.current_map, 'spawn_zones', None) \
            if self.current_map else None
        if not zones or "team_1" not in zones:
            return
        zone = zones["team_1"].inflate(320, 220)

        # 惰性生成两层雾贴图（地图切换导致尺寸变化时自动重建）
        if getattr(self, 'arena_fog_tex', None) is None \
                or self.arena_fog_tex.get_size() != (zone.w, zone.h):
            self.arena_fog_tex = _arena_build_fog_tex(zone.w, zone.h)
            self.arena_fog_tex2 = _arena_build_fog_tex(zone.w, zone.h)

        base_a = (175 + 28 * math.sin(self.frame_count * 0.02)) * alpha_scale
        tex1 = cached_scale_img(self.arena_fog_tex, self.zoom)
        tex2 = cached_scale_img(self.arena_fog_tex2, self.zoom)
        tw, th = tex1.get_size()
        sx = int((zone.x - self.camera_offset.x) * self.zoom)
        sy = int((zone.y - self.camera_offset.y) * self.zoom)
        clip = pygame.Rect(sx, sy, tw, th).clip(self.screen.get_rect())
        if clip.width <= 0 or clip.height <= 0:
            return
        off1 = int(self.frame_count * 0.35) % tw   # 前层滚得快
        off2 = int(self.frame_count * 0.18) % tw   # 后层滚得慢
        old_clip = self.screen.get_clip()
        self.screen.set_clip(clip)
        for tex, off, dy, mul in ((tex1, off1, 0, 1.0),
                                  (tex2, off2, int(-60 * self.zoom), 0.72)):
            a = int(base_a * mul)
            if a <= 0:
                continue
            tex.set_alpha(a)
            x = sx + off - tw   # 相邻两张即可无缝覆盖整个雾区
            while x < sx + tw:
                self.screen.blit(tex, (x, sy + dy))
                x += tw
        self.screen.set_clip(old_clip)

    def arena_draw_overlay(self):
        self.arena_draw_fog()  # 迷雾特效：世界之上、UI 之下
        scr_w, scr_h = SCREEN_WIDTH, SCREEN_HEIGHT
        ui = {}
        info0 = ARENA_TEAM_INFO["team_0"]
        info1 = ARENA_TEAM_INFO["team_1"]

        # --- 收起/展开键（右上角常驻）：BET/DEPLOY/FIGHT 阶段可收起信息 UI 看战场；
        #     RESULT 有必须操作的按钮（下一轮/退出），自动保持展开 ---
        collapsed = getattr(self, 'arena_ui_collapsed', False) \
            and self.arena_phase in ("BET", "DEPLOY", "FIGHT")
        toggle_rect = pygame.Rect(scr_w - 48, 9, 38, 38)

        if not collapsed:
            # --- 顶栏 ---
            pygame.draw.rect(self.screen, (16, 18, 22, 220), (0, 0, scr_w, 56))
            pygame.draw.line(self.screen, (90, 90, 100), (0, 56), (scr_w, 56), 2)
            funds_surf = self.ui_font.render(tr("ar.funds", n=self.arena_funds), True, (255, 210, 80))
            self.screen.blit(funds_surf, (20, 14))
            mode_title = tr("menu.fog_arena") \
                if getattr(self, 'arena_mode', 'standard') == "fog" else tr("ar.title_standard")
            title = self.ui_font.render(
                f"{mode_title}  {tr('ar.round', n=self.arena_round)}", True, WHITE)
            self.screen.blit(title, title.get_rect(center=(scr_w // 2, 28)))
            if self.arena_phase == "FIGHT" and self.arena_bet > 0:
                bt = ARENA_TEAM_INFO.get(self.arena_bet_team, {})
                bet_surf = self.ui_font.render(
                    tr("ar.bet_on", name=bt.get('name', ''), n=self.arena_bet), True,
                    bt.get('color', WHITE))
                self.screen.blit(bet_surf, bet_surf.get_rect(right=scr_w - 60, centery=28))
            streak_surf = self.info_font.render(tr("ar.streak", n=self.arena_streak), True, (180, 180, 180))
            self.screen.blit(streak_surf, (20, 38))

        # 收起/展开按钮（纯几何三角图标，不依赖字体字形）
        ui["toggle"] = toggle_rect
        hov = toggle_rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(self.screen, (70, 80, 95) if hov else (40, 46, 56),
                         toggle_rect, border_radius=8)
        pygame.draw.rect(self.screen, (140, 150, 165), toggle_rect, 2, border_radius=8)
        cx, cy = toggle_rect.centerx, toggle_rect.centery
        if collapsed:
            tri = [(cx - 8, cy - 4), (cx + 8, cy - 4), (cx, cy + 6)]   # ▼ = 点展开
        else:
            tri = [(cx - 8, cy + 4), (cx + 8, cy + 4), (cx, cy - 6)]   # ▲ = 点收起
        pygame.draw.polygon(self.screen, (230, 230, 235), tri)

        if self.arena_phase == "BET" and not collapsed:
            # --- 紧凑底栏：左右阵营条（不列单位明细）+ 中间操作列 ---
            bar_h = 180
            py = scr_h - bar_h - 6
            pw = int(scr_w * 0.30)
            ui["left"] = pygame.Rect(16, py, pw, bar_h)
            ui["right"] = pygame.Rect(scr_w - 16 - pw, py, pw, bar_h)
            self._arena_draw_army_panel(ui["left"], "team_0")
            self._arena_draw_army_panel(ui["right"], "team_1")

            # --- 中间列：押注比例 / 预估 / 跳过 / 退出 ---
            cx = scr_w // 2
            hint = self.font.render(tr("ar.bet_hint"),
                                    True, (200, 200, 200))
            self.screen.blit(hint, hint.get_rect(center=(cx, py + 12)))
            bw, bh, gap = 100, 36, 8
            total_w = bw * 3 + gap * 2
            bx = cx - total_w // 2
            by = py + 26
            for key, label, ratio in (("r25", "押 25%", 0.25), ("r50", "押 50%", 0.5),
                                      ("r100", "押 100%", 1.0)):
                r = pygame.Rect(bx, by, bw, bh)
                ui[key] = r
                selected = abs(self.arena_ratio - ratio) < 1e-6
                self._arena_btn(r, label,
                                hover_color=(120, 140, 90) if selected else (90, 110, 140),
                                normal_color=(60, 90, 50) if selected else (55, 65, 85),
                                border=(220, 220, 120) if selected else (160, 170, 190))
                bx += bw + gap
            # 预估押注额
            est = int(self.arena_funds * self.arena_ratio)
            est_surf = self.font.render(tr("ar.bet_invest", n=est), True, (255, 210, 80))
            self.screen.blit(est_surf, est_surf.get_rect(center=(cx, by + bh + 12)))

            # --- 跳过 / 退出 ---
            sw = 250
            ui["skip"] = pygame.Rect(cx - sw // 2, py + 88, sw, 34)
            self._arena_btn(ui["skip"], tr("ar.skip_bet"))
            ui["exit"] = pygame.Rect(cx - sw // 2, py + 128, sw, 34)
            self._arena_btn(ui["exit"], tr("ar.exit_save"),
                            hover_color=(150, 80, 60), normal_color=(100, 55, 45),
                            border=(220, 140, 110))

        elif self.arena_phase == "DEPLOY":
            # --- 敌军情报面板（右上，购买前显示 ???；避开右侧布防侧栏） ---
            # 收起态只保留操作按钮行，情报面板与提示一并隐藏
            if not collapsed:
                from panels.ui_sidebar import SIDEBAR_WIDTH
                panel = pygame.Rect(scr_w - SIDEBAR_WIDTH - 330, 66, 314, 118)
                s = pygame.Surface((panel.w, panel.h), pygame.SRCALPHA)
                s.fill((12, 14, 18, 210))
                self.screen.blit(s, panel.topleft)
                pygame.draw.rect(self.screen, (90, 90, 100), panel, 2)
                self.screen.blit(self.ui_font.render(tr("ar.intel"), True, WHITE),
                                 (panel.x + 12, panel.y + 8))
                enemy = self.arena_army_info.get("team_1", {"comp": [], "cost": 0})
                if self.arena_fog_intel:
                    lines = [f"{t} x{n}" for t, _c, n in enemy["comp"]] or [tr("ar.empty")]
                    for i, ln in enumerate(lines[:4]):
                        self.screen.blit(
                            self.font.render(ln, True, (200, 200, 200)),
                            (panel.x + 12, panel.y + 34 + i * 20))
                    tail = f"总造价: {enemy['cost']}"
                    self.screen.blit(
                        self.font.render(tail, True, (255, 210, 80)),
                        (panel.right - self.font.size(tail)[0] - 12,
                         panel.bottom - 24))
                else:
                    self.screen.blit(self.font.render(tr("ar.unknown"), True, (120, 120, 130)),
                                     (panel.x + 12, panel.y + 38))
                    self.screen.blit(
                        self.font.render(tr("ar.intel_hint"), True, (150, 150, 160)),
                        (panel.x + 12, panel.bottom - 24))

            # --- 操作行（布防用右侧经典侧栏选兵） ---
            ay = scr_h - 54
            if not collapsed:
                tip = self.font.render(
                    tr("ar.fog_deploy_tip"),
                    True, (180, 180, 190))
                self.screen.blit(tip, tip.get_rect(center=(scr_w // 2, ay - 22)))
            place_n = sum(n for _t, _c, n in self.arena_army_info["team_0"]["comp"])
            sel = self.arena_fog_selected
            sel_price = dict(self.arena_army_pool).get(sel, 0) if sel else 0
            stat = self.font.render(
                tr("ar.fog_stat", s=sel or tr("ar.none2"), p=sel_price,
                   d=place_n, n=self.arena_fog_spent),
                True, (255, 210, 80))
            self.screen.blit(stat, (20, ay + 4))
            ui["intel"] = pygame.Rect(scr_w // 2 - 390, ay, 240, 38)
            self._arena_btn(ui["intel"],
                            tr("ar.intel_bought") if self.arena_fog_intel
                            else tr("ar.buy_intel", n=ARENA_FOG_INTEL_COST))
            ui["start"] = pygame.Rect(scr_w // 2 - 95, ay, 190, 38)
            self._arena_btn(ui["start"], tr("ar.fight_btn"),
                            hover_color=(150, 90, 60), normal_color=(110, 60, 40),
                            border=(255, 160, 120))
            ui["exit"] = pygame.Rect(scr_w // 2 + 140, ay, 230, 38)
            self._arena_btn(ui["exit"], tr("ar.exit_save2"),
                            hover_color=(150, 80, 60), normal_color=(100, 55, 45),
                            border=(220, 140, 110))

            # --- 右侧经典布防侧栏（同经典对战 UI：小地图区+标签+列表） ---
            self.sidebar.draw(self.screen)

        elif self.arena_phase == "FIGHT":
            # --- 毒圈：半透明毒雾（安全区挖洞）+ 边界描边，画在 UI 之下 ---
            prog = getattr(self, 'arena_zone_progress', 0.0)
            m = self.current_map
            if prog > 0 and m:
                center = vec(m.width / 2.0, m.height / 2.0)
                sx = int((center.x - self.camera_offset.x) * self.zoom)
                sy = int((center.y - self.camera_offset.y) * self.zoom)
                rs = self.arena_zone_max_r * (1.0 - prog) * self.zoom
                zone = pygame.Surface((scr_w, scr_h), pygame.SRCALPHA)
                zone.fill((70, 190, 70, 95))
                # pygame.draw 不做混合：直接写 alpha=0 像素挖出安全区
                if rs > 1:
                    pygame.draw.circle(zone, (0, 0, 0, 0), (sx, sy), int(rs))
                self.screen.blit(zone, (0, 0))
                if rs > 4:
                    pygame.draw.circle(self.screen, (150, 255, 150),
                                       (sx, sy), int(rs), 3)

            if not collapsed:
                if prog <= 0:
                    remain = max(0, (ARENA_ZONE_START - self.arena_fight_frames) // 60)
                    tip = self.font.render(
                        tr("ar.fight_hint", s=remain),
                        True, (190, 190, 190))
                else:
                    tip = self.font.render(
                        tr("ar.zone_shrink", p=int(prog * 100)),
                        True, (150, 255, 150))
                self.screen.blit(tip, tip.get_rect(center=(scr_w // 2, scr_h - 30)))
                left = sum(1 for u in self.all_units if u.alive and u.team == "team_0")
                right = sum(1 for u in self.all_units if u.alive and u.team == "team_1")
                cnt = self.ui_font.render(tr("ar.vs", l=left, r=right), True, WHITE)
                self.screen.blit(cnt, cnt.get_rect(center=(scr_w // 2, 80)))

        elif self.arena_phase == "RESULT":
            # --- 结算面板（紧凑沉底居中，不遮挡战场） ---
            pw, ph = int(scr_w * 0.38), 200
            panel = pygame.Rect((scr_w - pw) // 2, scr_h - ph - 12, pw, ph)
            s = pygame.Surface((pw, ph), pygame.SRCALPHA)
            s.fill((12, 14, 18, 235))
            self.screen.blit(s, panel.topleft)
            color = (255, 210, 80) if self.arena_result_win else \
                    (150, 150, 160) if self.arena_result_win is None else (220, 90, 70)
            pygame.draw.rect(self.screen, color, panel, 3, border_radius=10)

            big = self.alert_font.render(self.arena_result_text, True, color)
            self.screen.blit(big, big.get_rect(center=(panel.centerx, panel.y + 38)))
            sub = self.ui_font.render(self.arena_result_detail, True, WHITE)
            self.screen.blit(sub, sub.get_rect(center=(panel.centerx, panel.y + 76)))
            cur = self.ui_font.render(tr("ar.cur_funds", n=self.arena_funds), True, (255, 210, 80))
            self.screen.blit(cur, cur.get_rect(center=(panel.centerx, panel.y + 104)))

            bw2 = pw // 2 - 30
            ui["next"] = pygame.Rect(panel.x + 20, panel.bottom - 54, bw2, 40)
            self._arena_btn(ui["next"], "下一轮（继续押注）")
            ui["exit"] = pygame.Rect(panel.right - 20 - bw2, panel.bottom - 54, bw2, 40)
            self._arena_btn(ui["exit"], tr("ar.exit_keep"),
                            hover_color=(150, 80, 60), normal_color=(100, 55, 45),
                            border=(220, 140, 110))
            if self.arena_funds < 100:
                tip = self.font.render(tr("ar.relief_tip"),
                                       True, (255, 150, 90))
                self.screen.blit(tip, tip.get_rect(center=(panel.centerx, panel.y + 130)))

        self.arena_ui = ui

        # --- 警报提示 ---
        if self.active_alert:
            txt, _t = self.active_alert
            surf = self.alert_font.render(txt, True, RED)
            rect = surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4))
            bg = rect.inflate(24, 12)
            pygame.draw.rect(self.screen, BLACK, bg)
            pygame.draw.rect(self.screen, RED, bg, 2)
            self.screen.blit(surf, rect)

    def _arena_draw_army_panel(self, rect, team):
        """绘制一方阵营条（下注阶段紧凑版：只显示队名/造价/评估，不列单位）。"""
        info = ARENA_TEAM_INFO[team]
        army = self.arena_army_info.get(team, {"comp": [], "cost": 0})
        faction = self.teams_config.get(team, {}).get("faction", "USA")
        hover = rect.collidepoint(pygame.mouse.get_pos())

        pygame.draw.rect(self.screen, info["panel_bg"], rect, border_radius=10)
        pygame.draw.rect(self.screen,
                         (255, 220, 120) if hover else info["color"],
                         rect, 3, border_radius=10)

        # 旗帜 + 队名，阵营名靠右
        icon = self.faction_icons.get(faction)
        tx = rect.x + 18
        ty = rect.y + 16
        if icon:
            self.screen.blit(icon, (tx, ty))
            tx += icon.get_width() + 12
        name = self.ui_font.render(
            tr("ar.team_red" if team == "team_0" else "ar.team_blue"), True, info["color"])
        self.screen.blit(name, (tx, ty - 2))
        fac = self.font.render(faction, True, (170, 170, 170))
        self.screen.blit(fac, fac.get_rect(right=rect.right - 16, centery=ty + 10))

        # 总造价 / 单位数 / 优势评估
        cost = army["cost"]
        other = "team_1" if team == "team_0" else "team_0"
        other_cost = self.arena_army_info.get(other, {}).get("cost", 0)
        if cost > other_cost * 1.05:
            tag, tc = tr("ar.advantage"), (255, 210, 80)
        elif cost < other_cost * 0.95:
            tag, tc = tr("ar.disadvantage"), (170, 170, 170)
        else:
            tag, tc = tr("ar.even"), WHITE
        line1 = self.ui_font.render(tr("ar.total_cost", n=cost), True, (255, 210, 80))
        self.screen.blit(line1, (rect.x + 18, rect.y + 58))
        n_units = sum(n for _t, _c, n in army["comp"])
        line2 = self.font.render(
            tr("ar.units_est", n=n_units, t=tag), True, tc)
        self.screen.blit(line2, (rect.x + 18, rect.y + 92))

        if hover:
            tip = self.font.render(tr("ar.bet_here"), True, (255, 220, 120))
            self.screen.blit(tip, (rect.right - tip.get_width() - 16,
                                   rect.bottom - 30))
