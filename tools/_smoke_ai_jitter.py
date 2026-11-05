# -*- coding: utf-8 -*-
"""冒烟：AI 绕基地抽动修复（2026-10-18 用户反馈）。

场景：
  A. DEFEND 下驻守圈(250px)内单位不被反复下令；圈外闲置单位最多召回 1 次（45 帧节流 + busy 跳过）
  B. 威胁 2~3 波动时 DEFEND 滞回不横跳；威胁 <=1 才退出
  C. 开火中(ATTACK)的单位不被 move_to 拉走
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from core.base_classes import vec
from ai.ai_logic import AICommander

PASS = 0
TOTAL = 0
def check(name, cond, detail=""):
    global PASS, TOTAL
    TOTAL += 1
    status = "PASS" if cond else "FAIL"
    print("[%s] %s %s" % (status, name, detail))
    if cond: PASS += 1
    return cond

class MockUnit:
    def __init__(self, pos, team="team_1", ai_mode="GUARD"):
        self.pos = vec(*pos)
        self.team = team
        self.alive = True
        self.ai_mode = ai_mode
        self.target_pos = None
        self.target_entity = None
        self.hp = 100
        self.max_hp = 100
        self.is_air = False
        self.unit_type = "rifleman"
        self.orders = []
    def move_to(self, tp):
        self.target_pos = vec(tp)
        self.orders.append(vec(tp))

class MockBase:
    def __init__(self, pos):
        self.pos = vec(*pos)
        self.team = "team_1"
        self.alive = True
        self.b_type = "base"

class MockGame:
    def __init__(self):
        self.all_units = []
        self.all_buildings = []
        self.team_resources = {"team_1": 5000}
        self.frame_count = 0
        self.current_map = None

# --- 场景 A：DEFEND 驻扎不再每帧跳目标 ---
g = MockGame()
g.all_buildings.append(MockBase((4000, 4000)))
cmd = AICommander(g, "team_1")
cmd.my_base_pos = vec(4000, 4000)
inner = MockUnit((4200, 4000))    # 离基地 200，驻守圈内
mid   = MockUnit((4400, 4000))    # 400，圈外闲置
far   = MockUnit((4600, 4000))    # 600，圈外闲置
g.all_units.extend([inner, mid, far])
for i in range(4):                 # 4 敌近基地 -> DEFEND
    g.all_units.append(MockUnit((4050 + i * 30, 4050), team="team_2"))

for _ in range(200):
    cmd.update_strategy_state()
    cmd.ai_tactical_command()

check("A1 state=DEFEND", cmd.state == "DEFEND", cmd.state)
check("A2 圈内单位 0 次下令", len(inner.orders) == 0, "orders=%d" % len(inner.orders))
check("A3 圈外单位最多 1 次召回", len(mid.orders) <= 1 and len(far.orders) <= 1,
      "mid=%d far=%d" % (len(mid.orders), len(far.orders)))

# --- 场景 B：威胁 2~3 波动时 DEFEND 滞回 ---
g2 = MockGame()
g2.all_buildings.append(MockBase((4000, 4000)))
cmd2 = AICommander(g2, "team_1")
cmd2.my_base_pos = vec(4000, 4000)
for i in range(3):                 # 3 兵 5000 钱 -> 非 ASSAULT/EXPAND
    g2.all_units.append(MockUnit((4000 + i * 50, 3800)))
pool = [MockUnit((4050 + i * 30, 4050), team="team_2") for i in range(4)]
g2.all_units.extend(pool[:3])
cmd2.update_strategy_state()
check("B1 3 敌进 DEFEND", cmd2.state == "DEFEND", cmd2.state)

switches = 0
prev = cmd2.state
for f in range(300):               # 威胁在 2/3 间每 30 帧交替
    if f % 30 == 0:
        want = 2 if (f // 30) % 2 == 0 else 3
        cur = [u for u in g2.all_units if u.team == "team_2"]
        if len(cur) > want:
            for u in cur[want:]:
                g2.all_units.remove(u)
        elif len(cur) < want:
            g2.all_units.append(pool[len(cur)])
    cmd2.update_strategy_state()
    if cmd2.state != prev:
        switches += 1
        prev = cmd2.state
check("B2 滞回带内不横跳", switches == 0, "switches=%d" % switches)

for u in [u for u in g2.all_units if u.team == "team_2"][1:]:  # 威胁降到 1
    g2.all_units.remove(u)
cmd2.update_strategy_state()
check("B3 威胁<=1 退出 DEFEND", cmd2.state != "DEFEND", cmd2.state)

# --- 场景 C：开火中的单位不被拉走 ---
g3 = MockGame()
g3.all_buildings.append(MockBase((4000, 4000)))
cmd3 = AICommander(g3, "team_1")
cmd3.my_base_pos = vec(4000, 4000)
fighter = MockUnit((4400, 4000), ai_mode="ATTACK")
g3.all_units.extend([fighter, MockUnit((4200, 4000))])
for i in range(4):
    g3.all_units.append(MockUnit((4050 + i * 30, 4050), team="team_2"))
cmd3.update_strategy_state()
check("C1 state=DEFEND", cmd3.state == "DEFEND", cmd3.state)
for _ in range(200):
    cmd3.ai_tactical_command()
check("C2 开火中单位 0 次下令", len(fighter.orders) == 0, "orders=%d" % len(fighter.orders))

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
