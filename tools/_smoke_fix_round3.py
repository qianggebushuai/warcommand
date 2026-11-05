# -*- coding: utf-8 -*-
"""冒烟：矿车顶墙罢工修复 + AI 科技/高级建筑优先级（2026-10-18 用户反馈第三轮）。

场景：
  1. 矿车 MANUAL 指向不可达点（顶墙 pos 不动）→ 10 秒后判定卡死复位 IDLE 恢复采矿
  2. 矿车 MANUAL 正常到达 → 原复位链不受影响（回归）
  3. AI 建造顺序：research 提到 72 → 有 factory 后优先下科技中心订单（不再排 15 矿场之后）
  4. AI 高级建筑：nuke_silo(40)/iron_curtain(38) → 钱够时优先于 bunker(25)
"""
import os
import sys

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()
pygame.display.set_mode((100, 100))

from pygame.math import Vector2 as vec
from units.vehicles import Harvester
from maps.map_data import OrePatch
import ai.ai_logic as ai_mod
from ai.ai_logic import AICommander

PASS = 0
TOTAL = 0

def check(name, cond, detail=""):
    global PASS, TOTAL
    TOTAL += 1
    print("[%s] %s %s" % ("PASS" if cond else "FAIL", name, detail))
    if cond:
        PASS += 1

# ================= 场景 1/2：矿车 =================
class MockHome:
    pos = vec(2000, 2000)
    alive = True
    b_type = 'mining'
    team = 'team_0'   # 矿车交付改"最近同队矿场"后，MockHome 需带队伍才算有效换矿点

class MockParticles:
    def add(self, *a, **k):
        pass

class MockGame:
    my_team = 'team_0'
    my_role = 'HOST'
    is_online = False
    team_resources = {'team_0': 0}
    all_buildings = [MockHome()]
    all_units = []
    particles = MockParticles()
    current_map = None

g = MockGame()
g.current_map = type('M', (), {'ore_patches': []})()
home = MockHome()
h = Harvester(g, vec(1000, 1000), 'team_0', home)

# ---- 1. 顶墙罢工：目标不可达，pos 被墙挡住不动 ----
rich = OrePatch(g, vec(1400, 1000)); rich.amount = 4000
g.current_map.ore_patches = [rich]
h.pos = vec(1200, 1000)
h.target_pos = vec(3000, 3000)   # 玩家点到远处的不可达点
h.ai_mode = "MOVE"
h.state = "IDLE"
rescued = False
for i in range(601):
    h.update()
    h.pos = vec(1200, 1000)      # 模拟顶墙：位置不变
    if h.state != "MANUAL":
        rescued = True
        break
check("1a 顶墙 10 秒内复位", rescued, "state=%s stuck=%s" % (h.state, getattr(h, '_manual_stuck', None)))
check("1b 指令已清空", h.target_pos is None and h.ai_mode == "GUARD")
h.mine_timer = 0
h._update_mining_ai()
check("1c 复位后恢复采矿", h.state == "MOVING_TO_ORE" and h.ore_patch is rich, h.state)

# ---- 2. 正常到达回归：距离持续改善的 MANUAL 不误杀 ----
h2 = Harvester(g, vec(1000, 1000), 'team_0', home)
h2.pos = vec(1000, 1000)
h2.target_pos = vec(1100, 1000)  # 100px 正常可达
h2.ai_mode = "MOVE"
h2.state = "IDLE"
ok = True
for i in range(120):
    h2.update()
    # 模拟基类移动：每帧向目标走 3px（比卡死阈值 600 帧早到达）
    d = h2.pos.distance_to(h2.target_pos) if h2.target_pos else 0
    if h2.target_pos and d > 3:
        h2.pos += (h2.target_pos - h2.pos).normalize() * 3
    if h2.state == "IDLE":
        break
check("2a 正常移动到达即复位并恢复采矿", h2.state == "MOVING_TO_ORE" and h2.ai_mode == "GUARD",
      "state=%s ai_mode=%s" % (h2.state, h2.ai_mode))
h2.mine_timer = 0
h2._update_mining_ai()
check("2b 到达后恢复采矿", h2.state == "MOVING_TO_ORE", h2.state)

# ================= 场景 3/4：AI 建造优先级 =================
class MockBuilding:
    def __init__(self, pos, team, b_type="base"):
        self.pos = pos
        self.team = team
        self.alive = True
        self.b_type = b_type
        self.rect = pygame.Rect(int(pos.x) - 50, int(pos.y) - 50, 100, 100)

class FakeEng:
    """拦截真实 Engineer 构造（Unit.__init__ 依赖过多），只记录订单。"""
    last = None
    def __init__(self, game, pos, team, build_pos):
        self.build_pos = vec(build_pos)
        self.team = team
        self.target_type = None
        self.alive = True  # economy 统计在建工程师数时会访问
        FakeEng.last = self

ai_mod.Engineer = FakeEng

def make_ai_game(money):
    class G:
        frame_count = 0
        is_online = False
        my_team = "team_0"
        all_units = []
        all_buildings = []
        team_resources = {"team_1": money}
        current_map = None
        lakes = []
        def show_alert(self, *a, **k): pass
    return G()

# ---- 3. 发展路线概率化：research(85) 权重最高——60 次抽样中必出现且路线多样 ----
# （轮盘赌加权随机后不再确定性下单，改为统计断言）
g3 = make_ai_game(3000)
for i, t in enumerate(["base", "power_plant", "factory", "mining"]):
    g3.all_buildings.append(MockBuilding(vec(1000 + i * 200, 1000), "team_1", t))
ai3 = AICommander(g3, team="team_1")
ai3.my_base_pos = vec(1000, 1000)
orders3 = {}
for _ in range(60):
    g3.team_resources["team_1"] = 3000
    g3.all_units = []  # FakeEng 已顶替 Engineer 类：不清空会触发 eng_count>=3 限流
    ai3.build_timer = 30
    FakeEng.last = None
    ai3.ai_economy_management()
    if FakeEng.last is not None:
        t = FakeEng.last.target_type
        orders3[t] = orders3.get(t, 0) + 1
check("3a 高权重 research 必被抽中", orders3.get("research", 0) >= 1,
      "orders=%s" % orders3)
check("3b 发展路线多样（≥3 种不同建筑）", len(orders3) >= 3,
      "kinds=%d" % len(orders3))

# ---- 4. prototype_gen(68) 高权重：基建齐备（mining>=4 无 gen）钱 6000 → 抽样中必出现
# （核弹井/铁幕已改为 prototype_gen 挂载武器充能，不再作为独立建筑建造——
#   旧版直接建造会 TypeError 崩溃卡死工程师，2026-10 第三轮修复）
g4 = make_ai_game(6000)
types4 = ["base", "power_plant", "factory", "factory", "factory",
          "mining", "mining", "mining", "mining",
          "radar", "radar", "airfield", "airfield",
          "research", "research"]
for i, t in enumerate(types4):
    g4.all_buildings.append(MockBuilding(vec(1000 + i * 200, 1000), "team_1", t))
ai4 = AICommander(g4, team="team_1")
ai4.my_base_pos = vec(1000, 1000)
orders4 = {}
for _ in range(60):
    g4.team_resources["team_1"] = 6000
    g4.all_units = []  # 同 3：防 FakeEng 积累触发 eng_count 限流
    ai4.build_timer = 30
    FakeEng.last = None
    ai4.ai_economy_management()
    if FakeEng.last is not None:
        t = FakeEng.last.target_type
        orders4[t] = orders4.get(t, 0) + 1
check("4a 高权重 prototype_gen 必被抽中（挂载武器前置）",
      orders4.get("prototype_gen", 0) >= 1,
      "orders=%s" % orders4)
check("4b 高级建筑参与轮盘（非垫底饿死）",
      orders4.get("prototype_gen", 0) >= orders4.get("aa_turret", 0) - 10,
      "proto=%s aa=%s" % (orders4.get("prototype_gen", 0), orders4.get("aa_turret", 0)))

# ---- 5. 矿车贴矿采矿：停靠距离 ≤ 矿脉半径+10（原 +45 钻头悬空像没采）----
g5 = MockGame()
g5.current_map = type('M', (), {'ore_patches': []})()
patch5 = OrePatch(g5, vec(1400, 1000)); patch5.amount = 4000
g5.current_map.ore_patches = [patch5]
h5 = Harvester(g5, vec(900, 1000), 'team_0', MockHome())
mined_dist = None
for i in range(900):
    h5.update()
    if h5.state == "MINING":
        mined_dist = h5.pos.distance_to(patch5.pos)
        break
check("5a 自动流程转入 MINING", mined_dist is not None, "state=%s" % h5.state)
check("5b 停靠矿井中央（dist≤1+容差）",
      mined_dist is not None and mined_dist <= 2.0,
      "dist=%s" % (round(mined_dist, 2) if mined_dist else None))
for _ in range(10):  # MINING 次帧才开始 transfer
    h5.update()
check("5c 采到矿", h5.ore_cargo > 0 or h5.state == "RETURNING",
      "cargo=%.1f" % h5.ore_cargo)

# ---- 6. 残矿兜底：矿区被采到低残量(<20)时矿车仍能继续采，不再停摆 ----
g6 = MockGame()
g6.current_map = type('M', (), {'ore_patches': []})()
patch6 = OrePatch(g6, vec(1400, 1000)); patch6.amount = 15.0  # 低于富矿门槛 20
g6.current_map.ore_patches = [patch6]
h6 = Harvester(g6, vec(1100, 1000), 'team_0', MockHome())
saw_returning = False
for i in range(700):
    h6.update()
    if h6.state == "MINING" or h6.ore_cargo > 0:
        pass
    if h6.state == "RETURNING":
        saw_returning = True
        break
check("6a 残矿(15)被接受并采出货物", saw_returning and h6.ore_cargo > 0,
      "state=%s cargo=%.1f patch=%.2f" % (h6.state, h6.ore_cargo, patch6.amount))
check("6b 残矿被采空(amount<0.01)", patch6.amount < 0.01, "%.3f" % patch6.amount)
h6.pos = vec(MockHome.pos)  # 瞬移到家（dist<60 卸货）
for _ in range(5):
    h6.update()
h6.mine_timer = 0
h6._update_mining_ai()  # 卸完货再找矿：全图无矿 → 停 IDLE 不崩
check("6c 采空后无矿可找不崩（IDLE 待命）", h6.state == "IDLE" and h6.ore_patch is None, h6.state)

# ---- 7. 矿脉再生接通：OrePatch.update 生效 + 覆写 update 的地图补了再生 ----
patch7 = OrePatch(g6, vec(1500, 1000), amount=10, max_amount=4000)
patch7._last_tick -= 1000  # 模拟 1 秒前计时（update 按真实时间差再生）
patch7.update()
check("7a 矿脉按秒再生（10→明显回升）", patch7.amount > 10.5, "amount=%.2f (REGEN=%s/s)" % (
    patch7.amount, __import__('core.settings', fromlist=['ORE_PATCH_REGEN_PER_S']).ORE_PATCH_REGEN_PER_S))

import inspect
from maps.map_data import CrossfireMap, VerdunMap
src_cross = inspect.getsource(CrossfireMap.update)
src_verdun = inspect.getsource(VerdunMap.update)
check("7b CrossfireMap.update 含矿脉再生", "ore_patches" in src_cross)
check("7c VerdunMap.update 含矿脉再生", "ore_patches" in src_verdun)

# ---- 8. 经济参数平衡：矿车采集(20/s) vs 再生(12/s)+大储量缓冲 → 双车持续工作 ----
from core import settings as S
check("8a 参数恢复 spec 设计值", S.ORE_PATCH_MAX_AMOUNT == 4000 and S.ORE_PATCH_REGEN_PER_S == 12.0,
      "MAX=%s REGEN=%s" % (S.ORE_PATCH_MAX_AMOUNT, S.ORE_PATCH_REGEN_PER_S))

g8 = MockGame()
g8.current_map = type('M', (), {'ore_patches': []})()
patch8 = OrePatch(g8, vec(1400, 1000)); patch8.amount = S.ORE_PATCH_MAX_AMOUNT
g8.current_map.ore_patches = [patch8]

class NearHome:
    """矿场建在矿脉旁（真实 MiningRig 布局）"""
    pos = vec(1700, 1300)
    alive = True
    b_type = 'mining'

cars = [Harvester(g8, vec(1700, 1300), 'team_0', NearHome),
        Harvester(g8, vec(1730, 1330), 'team_0', NearHome)]
deliveries = [0, 0]
idle_frames = [0, 0]
prev_states = ["", ""]
FRAMES = 3600  # 60 秒游戏时间
for f in range(FRAMES):
    for i, c in enumerate(cars):
        c.update()
        if c.state == "IDLE":
            idle_frames[i] += 1
        if c.state == "RETURNING" and prev_states[i] != "RETURNING":
            deliveries[i] += 1  # 满舱出发一次
        prev_states[i] = c.state
check("8b 双车各完成 ≥2 趟运输", deliveries[0] >= 2 and deliveries[1] >= 2,
      "deliveries=%s" % deliveries)
check("8c 矿车闲置时间 <25%%", idle_frames[0] < FRAMES * 0.25 and idle_frames[1] < FRAMES * 0.25,
      "idle=%s/%d" % (idle_frames, FRAMES))
check("8d 矿脉未被采干", patch8.amount > 500, "amount=%.0f" % patch8.amount)

# ---- 9. 浮点渐近死区回归：stop=1 时逼近矿心的最后一步步长(dist-1)可小于
#         float64 在 pos≈2000 处的 ulp(≈4.5e-13)，pos 冻结在 stop+ε（实测
#         1.000000000000043）→ dist<=stop 永假 → 矿车停在矿井上永不转 MINING。
#         修复=判定加 1e-6 容差 + 一步可达时精确落位。用实测冻结轨迹做回归。
g9 = MockGame()
g9.current_map = type('M', (), {'ore_patches': []})()
patch9 = OrePatch(g9, vec(2100, 800)); patch9.amount = 3900
g9.current_map.ore_patches = [patch9]
h9 = Harvester(g9, vec(1811.4925864759535, 1099.0678537509662), 'team_0', MockHome())
h9.ore_patch = patch9
h9.state = "MOVING_TO_ORE"
entered = False
for _ in range(600):
    h9.update()
    if h9.state == "MINING":
        entered = True
        break
check("9a 冻结轨迹正常转入 MINING", entered, "state=%s dist=%r" % (
    h9.state, h9.pos.distance_to(patch9.pos) if not entered else None))
check("9b 容差后仍停在矿井中央", h9.pos.distance_to(patch9.pos) <= 1.5,
      "dist=%.6f" % h9.pos.distance_to(patch9.pos))

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
