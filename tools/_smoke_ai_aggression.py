# -*- coding: utf-8 -*-
"""AI 攻击性增强冒烟测试（无头 mock）。

覆盖：
1. 进攻触发：兵力达标 + 冷却归零 → 单位收到 move_to 指令
2. 进攻节奏：assault_interval=900（原 1800）更频繁
3. AI 互打：AI 甲的目标选择会命中 AI 乙的建筑（加权就近）
4. 骚扰小队：闲置单位会被派去袭击敌方矿车
5. 空投突袭：科技中心+机场+钱够 → 生成 ParatrooperPlane
6. 掉队追赶：离目标远且无指令的单位被重新下令
"""
import os
import sys

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()
pygame.display.set_mode((100, 100))

from core.base_classes import vec
from ai.ai_logic import AICommander
from units import Harvester, ParatrooperPlane

PASS = 0
FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {detail}")


class MockBuilding:
    def __init__(self, pos, team, b_type="base"):
        self.pos = pos
        self.team = team
        self.alive = True
        self.b_type = b_type
        self.hp = 1000
        self.max_hp = 1000


class MockUnit:
    def __init__(self, pos, team, is_harv=False):
        self.pos = pos
        self.team = team
        self.alive = True
        self.hp = 100
        self.max_hp = 100
        self.ai_mode = "GUARD"
        self.target_pos = None
        self.is_air = False
        self.can_deploy = False
        self.move_orders = []
        if is_harv:
            self.__class__.__name__ = "HarvesterFake"  # 类型识别走 isinstance(Harvester)

    def move_to(self, p):
        self.move_orders.append(vec(p.x, p.y))
        self.target_pos = vec(p.x, p.y)

    def set_target(self, entity):
        # _engage_orders 对实体目标改走 set_target（单位自行推进开火），
        # 测试桩同样记为一条命令供断言
        self.move_orders.append(entity)


def make_game():
    """最小 mock：两个 AI 队伍（team_1/team_2）+ 玩家 team_0。"""
    class G:
        frame_count = 0
        is_online = False
        my_team = "team_0"
        all_units = []
        all_buildings = []
        team_resources = {"team_0": 5000, "team_1": 5000, "team_2": 5000}
        def show_alert(self, *a, **k): pass
    return G()


# ---- 场景：三队各有基地；AI1 有 6 个战斗单位 ----
g = make_game()
g.all_buildings = [
    MockBuilding(vec(1000, 1000), "team_0"),
    MockBuilding(vec(7000, 1000), "team_1"),
    MockBuilding(vec(1500, 6500), "team_2"),
]
ai1 = AICommander(g, team="team_1")
ai2 = AICommander(g, team="team_2")

# AI1 造 6 个战斗单位（isinstance 过滤走 units.Harvester/Engineer 真类，
# mock 单位不是这些实例所以全算战斗单位）
my_units = []
for i in range(6):
    u = MockUnit(vec(6900 + i * 20, 1100), "team_1")
    g.all_units.append(u)
    my_units.append(u)

# ---- 1/2. 进攻触发与节奏 ----
ai1.update()
check("进攻触发：单位收到 move_to", any(len(u.move_orders) > 0 for u in my_units))
check("进攻间隔=900 帧", ai1.assault_interval == 900)
check("进攻冷却已装填", ai1.attack_timer > 0)

# ---- 3. AI 互打：ai2 的目标应是敌对建筑（含 AI1 基地）----
t2 = ai2.select_target(
    [b for b in g.all_buildings if b.team != "team_2" and b.team != "neutral" and b.alive],
    [])
check("AI2 目标为敌对建筑", t2 is not None and getattr(t2, 'team', '') in ("team_0", "team_1"),
      getattr(t2, 'team', None))
# 就近加权：AI2 基地在 (1500,6500)，最近的敌建筑是玩家 (1000,1000) 距离≈5590，
# AI1 基地 (7000,1000) 距离≈7088——两者同为 base 优先级，应选更近的玩家基地
check("就近加权生效（选近处基地）", getattr(t2, 'team', '') == "team_0")

# ---- 4. 骚扰小队 ----
# 给 AI2 一个矿车目标（敌矿车=team_1 的 Harvester 实例）+ 2 个闲置单位
enemy_base = g.all_buildings[1]  # AI1 基地
harv = Harvester(g, vec(6800, 1200), "team_1", enemy_base)
g.all_units.append(harv)
raiders = [MockUnit(vec(2000, 6000), "team_2"), MockUnit(vec(2050, 6050), "team_2")]
g.all_units.extend(raiders)
ai2.raid_cooldown = 0
ai2.update()
raided = any(u.move_orders for u in raiders)
check("骚扰小队出动袭击矿车", raided)

# ---- 5. 空投突袭 ----
# 科技中心+机场必须建在 AI2 自己名下（has_tech_center 查本队建筑）
g.all_buildings.append(MockBuilding(vec(1600, 6600), "team_2", b_type="tech_center"))
g.all_buildings.append(MockBuilding(vec(1700, 6700), "team_2", b_type="airfield"))
g.team_resources["team_2"] = 20000
ai2.drop_cooldown = 0
n_before = len(g.all_units)
ai2.update()
dropped = any(isinstance(u, ParatrooperPlane) and u.team == "team_2" for u in g.all_units)
check("空投伞兵生成", dropped)
check("空投扣费", g.team_resources["team_2"] < 20000)

# ---- 6. 掉队追赶 ----
g2 = make_game()
g2.all_buildings = [
    MockBuilding(vec(1000, 1000), "team_0"),
    MockBuilding(vec(7000, 1000), "team_1"),
]
ai_b = AICommander(g2, team="team_1")
straggler = MockUnit(vec(1500, 5500), "team_1")  # 离目标远、无指令
straggler.target_pos = None
g2.all_units.append(straggler)
ai_b.attack_timer = ai_b.assault_interval - ai_b.chase_interval  # 进入追赶窗口
g2.frame_count = 0
ai_b.chase_tick = 0
# 强制 frame_count % 300 == 0
ai_b.update()
check("掉队单位被重新下令", len(straggler.move_orders) > 0)

print(f"\n结果: {PASS} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
