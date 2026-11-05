"""竞技场（争锋频道）无头回归测试。

覆盖：存档回环 / 组军造价约束 / 竞技场地图 / 回合状态机 /
      中立生成 / 整局模拟（押中、押错、平局）/ UI 绘制冒烟 / 退出落盘。

运行： SDL_VIDEODRIVER=dummy D:/python3.8/python.exe tools/test_arena.py
"""
import os
import sys

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import json
import random
import pygame

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")


# ---------- 1. 存档回环 ----------
print("== 1. save_data 回环 ==")
from core import save_data as sd

test_path = os.path.join(ROOT, 'config', '_test_save.json')
if os.path.exists(test_path):
    os.remove(test_path)
if os.path.exists(test_path + '.bak'):
    os.remove(test_path + '.bak')

d = sd.load_save_data(test_path)
check("默认存档 funds=100", d["funds"] == 100, f"got {d['funds']}")
d["funds"] = 233
d["stats"]["wins"] = 5
sd.write_save_data(d, test_path)
d2 = sd.load_save_data(test_path)
check("写入后读回", d2["funds"] == 233 and d2["stats"]["wins"] == 5)
# 再写一次使旧内容轮换出 .bak，然后写坏主文件
sd.write_save_data(d, test_path)
with open(test_path, 'w', encoding='utf-8') as f:
    f.write("{corrupted!!!")
d3 = sd.load_save_data(test_path)
check("主文件损坏回退 .bak", d3["funds"] == 233, f"got {d3['funds']}")
# 主+bak 都坏 → 默认
with open(test_path + '.bak', 'w', encoding='utf-8') as f:
    f.write("nope")
d4 = sd.load_save_data(test_path)
check("双损坏回默认", d4["funds"] == 100)
sd.set_funds(777, test_path)
check("set_funds 落盘", sd.get_funds(test_path) == 777)
os.remove(test_path)
if os.path.exists(test_path + '.bak'):
    os.remove(test_path + '.bak')

# ---------- 2. 组军造价约束 ----------
print("== 2. arena_compose_army ==")
from core.settings import *
import game.arena_mixin as am

pool_costs = dict(am.ARENA_ARMY_POOL)
check("组军池 19 种（17 单位+2 建筑，无固定翼）",
      len(pool_costs) == 19 and "fighterjet" not in pool_costs and
      {"bunker", "bastion"} <= set(pool_costs))
sea_costs = dict(am.ARENA_SEA_POOL)
check("海池 9 种（海军+空军，无地面/建筑）",
      len(sea_costs) == 9 and "mi24" in sea_costs and
      not {"rifleman", "m1a2", "type99", "mech",
           "bunker", "bastion"} & set(sea_costs))
for budget in (450, 900, 1500, 2600, 4000):
    comp, total = am.ArenaMixin.arena_compose_army(None, budget, am.ARENA_ARMY_POOL)
    ok_budget = all(c <= budget for _t, c, _n in comp)
    ok_cap = all(c <= max(int(budget * 0.45), 300) for _t, c, _n in comp)
    ok_group = all(n >= (1 if t in am.ARENA_BUILDING_SPAWNERS else 2)
                   for t, _c, n in comp)
    n_units = sum(n for _t, _c, n in comp)
    check(f"budget={budget} 合法", ok_budget and ok_cap and ok_group and total > 0,
          f"groups={len(comp)} units={n_units} total={total}")
scomp, stotal = am.ArenaMixin.arena_compose_army(None, 1500, am.ARENA_SEA_POOL)
check("海池组军合法", all(c <= 1500 for _t, c, _n in scomp) and stotal > 0,
      f"groups={len(scomp)} total={stotal}")

# ---------- 3. 启动游戏 + 进入竞技场 ----------
print("== 3. 启动与进入 ==")
from main import Game

real_save = os.path.join(ROOT, 'config', 'save.json')
backup = None
if os.path.exists(real_save):
    with open(real_save, 'r', encoding='utf-8') as f:
        backup = f.read()

g = Game()
sd.write_save_data({"funds": 500, "stats": {"rounds": 0, "wins": 0, "best_streak": 0}},
                   real_save)  # 预置已知军费

g.arena_enter()
check("arena_enter 后 arena_active", g.arena_active)
check("读取军费 500", g.arena_funds == 500, f"got {g.arena_funds}")
check("teams_config 双方", set(g.teams_config.keys()) == {"team_0", "team_1"})
check("状态 LOADING", g.state == "LOADING")
for _i in range(600):
    if g.state != "LOADING":
        break
    g.update_loading()
check("加载完进入 ARENA", g.state == "ARENA")
map_name = type(g.current_map).__name__
sea_mode = map_name == "ArenaSeaMap"
check("竞技场专属地图（随机陆/海）",
      map_name in ("ArenaColiseumMap", "ArenaSeaMap"), f"got {map_name}")
check("组军池与地图匹配",
      (g.arena_army_pool is am.ARENA_SEA_POOL) == sea_mode)
check("BET 阶段", g.arena_phase == "BET")
check("无基地（新规则）", not g.bases and
      not any(getattr(b, 'b_type', '') == 'base' for b in g.all_buildings))
n_red = sum(1 for u in g.all_units if u.team == "team_0")
n_blue = sum(1 for u in g.all_units if u.team == "team_1")
check("两军已生成", n_red >= 2 and n_blue >= 2, f"red={n_red} blue={n_blue}")
part = [u for u in g.all_units if u.team in ("team_0", "team_1")]
check("无固定翼参战", not any(getattr(u, 'is_fixed_wing', False) for u in part))
if sea_mode:
    check("海图全员海军/空军", all(u.is_naval or u.is_air for u in part))
else:
    check("陆图无海军", all(not u.is_naval for u in part))
check("半区散布（红左蓝右，不摆一列）",
      all(u.pos.x < 1200 for u in part if u.team == "team_0") and
      all(u.pos.x > 1200 for u in part if u.team == "team_1"))
check("成组编成（建筑1/单位>=2）",
      all(n >= (1 if t in am.ARENA_BUILDING_SPAWNERS else 2)
          for t, _c, n in g.arena_army_info["team_0"]["comp"]) and
      all(n >= (1 if t in am.ARENA_BUILDING_SPAWNERS else 2)
          for t, _c, n in g.arena_army_info["team_1"]["comp"]))
neutrals = [b for b in g.all_buildings if str(b.team).startswith("neutral")]
neu_units = [u for u in g.all_units if str(u.team).startswith("neutral")]
check("中立生成 3~5", 3 <= len(neutrals) + len(neu_units) <= 5,
      f"b={len(neutrals)} u={len(neu_units)}")
check("军费预算接近", abs(g.arena_army_info["team_0"]["cost"] -
                      g.arena_army_info["team_1"]["cost"]) <= 900 * 0.3 + 300,
      f"c0={g.arena_army_info['team_0']['cost']} c1={g.arena_army_info['team_1']['cost']}")

# ---------- 4. 各阶段绘制冒烟 ----------
print("== 4. 绘制冒烟 ==")
g.arena_draw()
check("BET 绘制", True)
check("UI rects 已建", {"left", "right", "skip", "exit"} <= set(g.arena_ui.keys()))
pygame.event.clear()

# ---------- 5. 押注 + 整局模拟（押错路径验证：押弱方） ----------
print("== 5. 押注与战斗模拟 ==")
weak = "team_0" if g.arena_army_info["team_0"]["cost"] < g.arena_army_info["team_1"]["cost"] \
       else "team_1"
g.arena_ratio = 0.5
g.arena_place_bet(weak)
check("押注扣款", g.arena_bet == 250 and g.arena_funds == 250,
      f"bet={g.arena_bet} funds={g.arena_funds}")
check("FIGHT 阶段", g.arena_phase == "FIGHT")

result = None
for i in range(6200):
    g.arena_update()
    if g.arena_phase == "RESULT":
        result = g.arena_result_winner
        break
check("战斗已出结果", result is not None,
      f"winner={result} frames={g.arena_fight_frames}")
if result:
    payout = 250 * 2 if result == weak else 0
    expected = 250 + payout + 50  # 押注后余额 + 返还 + 观战奖励50
    check("结算军费数学", g.arena_funds == expected, f"funds={g.arena_funds} expect={expected}")
sd_data = sd.load_save_data(real_save)
check("结算已落盘", sd_data["funds"] == g.arena_funds,
      f"disk={sd_data['funds']} mem={g.arena_funds}")
check("战绩 rounds+1", sd_data["stats"]["rounds"] >= 1)

# ---------- 6. 下一轮软清场 ----------
print("== 6. 下一轮 ==")
old_units = list(g.all_units)
g.arena_next_round()
check("回到 BET", g.arena_phase == "BET")
check("软清场且仍无基地", not g.bases and
      not any(getattr(b, 'b_type', '') == 'base' for b in g.all_buildings))
check("实体已刷新", len([b for b in g.all_buildings if str(b.team).startswith("neutral")]) +
      len([u for u in g.all_units if str(u.team).startswith("neutral")]) >= 3)
g.arena_draw()
check("第二轮 BET 绘制", True)
pygame.event.clear()

# ---------- 7. 平局退款 ----------
print("== 7. 平局退款 ==")
g.arena_place_bet("team_0")
funds_before = g.arena_funds
bet_before = g.arena_bet
g.arena_settle("DRAW")
check("平局退款", g.arena_funds == funds_before + bet_before + 50,
      f"funds={g.arena_funds}")
check("平局落盘", sd.load_save_data(real_save)["funds"] == g.arena_funds)

# ---------- 8. 押中翻倍 ----------
print("== 8. 押中翻倍 ==")
g.arena_place_bet("team_1")
funds_before = g.arena_funds
bet_before = g.arena_bet
g.arena_settle("team_1")
check("翻倍返还", g.arena_funds == funds_before + bet_before * 2 + 50,
      f"funds={g.arena_funds} +{bet_before*2}")
check("连胜累计 (第8节押中, 连胜>=1)", g.arena_streak >= 1, f"streak={g.arena_streak}")

# ---------- 9. 军费归零救济 ----------
print("== 9. 救济金 ==")
g.arena_funds = 0
g.arena_next_round()
check("救济金 100", g.arena_funds == 100, f"got {g.arena_funds}")
g.arena_funds = 50  # 观战奖励后最低结余 50，也应触发救济
g.arena_next_round()
check("救济阈值<100", g.arena_funds == 100, f"got {g.arena_funds}")

# ---------- 10. 退出落盘 ----------
print("== 10. 退出 ==")
g.arena_funds = 321
g.arena_exit()
check("回菜单", g.state == "MENU")
check("退出落盘 321", sd.get_funds(real_save) == 321, f"disk={sd.get_funds(real_save)}")
check("arena_active 复位", not g.arena_active and g.arena_phase == "IDLE")
check("reset_game 回普通地图", not getattr(g, 'arena_active', False))

# ---------- 11. 连续三轮整局模拟（含绘制冒烟） ----------
print("== 11. 连续三轮模拟 ==")
g.arena_enter()
for _i in range(600):
    if g.state != "LOADING":
        break
    g.update_loading()
check("重进竞技场", g.state == "ARENA" and g.arena_round == 1)
ok_rounds = True
prev_max_cost = 0
for r in range(3):
    if g.arena_phase != "BET":
        ok_rounds = False
        break
    g.arena_draw()  # BET 覆盖层
    g.arena_ratio = 0.25
    g.arena_place_bet(random.choice(["team_0", "team_1"]))
    c0 = g.arena_army_info["team_0"]["cost"]
    c1 = g.arena_army_info["team_1"]["cost"]
    check(f"第{r+1}轮预算达标",
          c0 > int(900 * 0.85) - 2 * min(c for _t, c in g.arena_army_pool) and
          c1 > int(900 * 0.85) - 2 * min(c for _t, c in g.arena_army_pool),
          f"r{r+1}: c0={c0} c1={c1}")
    check(f"第{r+1}轮总价值严格递增", max(c0, c1) > prev_max_cost,
          f"c0={c0} c1={c1} prev={prev_max_cost}")
    prev_max_cost = max(c0, c1)
    ended = False
    for i in range(6200):
        g.arena_update()
        if i % 1000 == 0:
            g.arena_draw()  # FIGHT 覆盖层
        if g.arena_phase == "RESULT":
            ended = True
            break
    if not ended:
        ok_rounds = False
        print(f"  第{r+1}轮未在时限内结束!")
        break
    g.arena_draw()  # RESULT 覆盖层
    check(f"第{r+1}轮出结果并落盘",
          sd.load_save_data(real_save)["funds"] == g.arena_funds,
          f"winner={g.arena_result_winner} funds={g.arena_funds} "
          f"frames={g.arena_fight_frames}")
    if r < 2:
        g.arena_next_round()
check("三轮全部完整进行", ok_rounds)
check("场次统计=3", sd.load_save_data(real_save)["stats"]["rounds"] >= 3)
g.arena_exit()

# ---------- 12. 菜单按钮中文渲染 ----------
print("== 12. 菜单绘制 ==")
g.state = "MENU"
g.draw_menu()
check("菜单绘制（竞技场按钮+军费显示）", True)
pygame.event.clear()

# ---------- 13. 海上竞技场专项（整局） ----------
print("== 13. 海上竞技场专项 ==")
from maps import ArenaSeaMap
g.arena_enter()
g.arena_map_class = ArenaSeaMap      # 覆盖随机选图，强制海图
g.arena_army_pool = am.ARENA_SEA_POOL
g.reset_game()                        # 用海图重建（init_level 随 reset_game 调用）
for _i in range(600):
    if g.state != "LOADING":
        break
    g.update_loading()
check("海图加载进入 ARENA",
      g.state == "ARENA" and type(g.current_map).__name__ == "ArenaSeaMap")
m = g.current_map
check("全域水域 lake", len(m.lakes) == 1 and
      m.lakes[0]['type'] == 'water' and
      m.lakes[0]['rect'].width == m.width and m.lakes[0]['rect'].height == m.height)
spart = [u for u in g.all_units if u.team in ("team_0", "team_1")]
check("海图全员海军/空军", all(u.is_naval or u.is_air for u in spart),
      f"n={len(spart)}")
check("舰船都在水中（不在岛上）",
      all(m.lakes[0]['rect'].collidepoint(int(u.pos.x), int(u.pos.y)) and
          not any(i.collidepoint(int(u.pos.x), int(u.pos.y))
                  for i in m.islands)
          for u in spart if u.is_naval))
check("海图中立全为舰船",
      all(u.is_naval for u in g.all_units
          if str(u.team).startswith("neutral") and not u.is_air))
check("海图无固定翼", not any(getattr(u, 'is_fixed_wing', False) for u in spart))
g.arena_draw()
pygame.event.clear()
g.arena_start_fight()
sea_ended = False
for i in range(6200):
    g.arena_update()
    if i % 1000 == 0:
        g.arena_draw()  # 毒圈/顶栏覆盖层冒烟
    if g.arena_phase == "RESULT":
        sea_ended = True
        break
check("海图整局结束", sea_ended,
      f"winner={g.arena_result_winner} frames={g.arena_fight_frames}")
g.arena_exit()

# ---------- 14. 迷雾竞技场专项（整局） ----------
print("== 14. 迷雾竞技场专项 ==")
from core.base_classes import vec
g.arena_enter("fog")
for _i in range(600):
    if g.state != "LOADING":
        break
    g.update_loading()
check("迷雾模式进入 DEPLOY",
      g.state == "ARENA" and g.arena_mode == "fog" and g.arena_phase == "DEPLOY")
n_t1 = sum(1 for u in g.all_units if u.team == "team_1") + \
       sum(1 for b in g.all_buildings if b.team == "team_1")
check("开战前看不到敌军（不落位）", n_t1 == 0 and len(g.arena_fog_snapshot) == 0)
check("敌军编成已秘密生成（预算花满）",
      len(g.arena_army_info["team_1"]["comp"]) >= 1 and
      g.arena_army_info["team_1"]["cost"] >
      int(900 * 0.9) - 2 * min(c for _t, c in g.arena_army_pool),
      f"cost={g.arena_army_info['team_1']['cost']}")

# 布防侧栏（经典 UI）：按池过滤 + 竞技场定价 + 点击选中
g.sidebar.update()
build_items = {i.payload: i for i in g.sidebar.all_items["BUILD"]}
unit_items = {i.payload: i for i in g.sidebar.all_items["UNIT"]}
pool_map = dict(g.arena_army_pool)
vis = {p for src in (build_items, unit_items)
       for p, i in src.items() if i.visible}
check("侧栏按池过滤（无固定翼/技能）", vis == set(pool_map),
      f"diff={vis ^ set(pool_map)}")
check("侧栏定价同步",
      all((build_items.get(p) or unit_items[p]).visible and
          (build_items.get(p) or unit_items[p]).cost == pool_map[p]
          for p in pool_map))
first = next(iter(pool_map))
src = build_items if first in build_items else unit_items
g.sidebar.execute_item(src[first])
check("侧栏点击选中", g.arena_fog_selected == first)
g.sidebar.execute_item(src[first])
check("侧栏再点取消", g.arena_fog_selected is None)

# 侧栏滚动交互（回归：竞技场输入循环未转发滚轮/滚动条拖拽导致滑不动）
# BUILD 标签池内只有 2 建筑不出滚动条，切 UNIT 标签（17 项）才有 max_scroll
g.sidebar.current_tab = "UNIT"
g.sidebar.update()
# dummy 驱动 set_pos 无效（SDL dummy 不支持 warp），直接劫持光标读取
_orig_gp = pygame.mouse.get_pos

def _cursor_at(p):
    pygame.mouse.get_pos = lambda: p

if g.sidebar.max_scroll > 0:
    try:
        # 滚轮在侧栏列表上 -> 列表滚动而非缩放镜头
        # （zoom 先置到竞技场下限，否则低于下限时 arena_clamp_camera 会拉回，
        #   干扰"缩放未发生"断言）
        g.zoom = max(SCREEN_WIDTH / g.current_map.width,
                     SCREEN_HEIGHT / g.current_map.height)
        g.sidebar.scroll_y = 0
        zoom_before = g.zoom
        _cursor_at((g.sidebar.items_area.centerx, g.sidebar.items_area.centery))
        pygame.event.post(pygame.event.Event(pygame.MOUSEWHEEL, y=-3))
        g.handle_arena_input()
        check("滚轮滚动侧栏列表",
              g.sidebar.scroll_y > 0 and g.zoom == zoom_before,
              f"scroll_y={g.sidebar.scroll_y} zoom={zoom_before}->{g.zoom}")
        # 滚轮在战场空白处 -> 缩放镜头
        _cursor_at((400, 400))
        zoom_before = g.zoom
        pygame.event.post(pygame.event.Event(pygame.MOUSEWHEEL, y=1))
        g.handle_arena_input()
        check("滚轮在战场缩放镜头", g.zoom != zoom_before,
              f"zoom={zoom_before}->{g.zoom}")
        # 滚动条拖拽：按下 -> 拖动跟随 -> 松开结束
        g.sidebar.update()
        thumb, track = g.sidebar.scrollbar_thumb, g.sidebar.scrollbar_track
        _cursor_at(tuple(thumb.center))
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                             pos=tuple(thumb.center), button=1))
        g.handle_arena_input()
        check("滚动条按下开始拖拽", g.sidebar.dragging_scrollbar)
        pre_drag = g.sidebar.scroll_y
        target = (track.centerx, track.bottom - 10)
        _cursor_at(target)
        pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION,
                                             pos=target, rel=(0, 40)))
        g.handle_arena_input()
        check("滚动条拖动跟随", g.sidebar.scroll_y > pre_drag,
              f"{pre_drag}->{g.sidebar.scroll_y}")
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP,
                                             pos=target, button=1))
        g.handle_arena_input()
        check("滚动条松开结束拖拽", not g.sidebar.dragging_scrollbar)
    finally:
        pygame.mouse.get_pos = _orig_gp
        g.sidebar.current_tab = "BUILD"  # 恢复默认标签
else:
    check("侧栏列表可滚动(max_scroll>0)", False, f"max_scroll={g.sidebar.max_scroll}")

# 右键删除已布防单位/建筑并退款（布防阶段反悔机制）
zone0 = g.current_map.spawn_zones["team_0"]
del_type = min(pool_map, key=pool_map.get)  # 最便宜兵种（必非建筑）
pre_f = g.arena_funds = 1000
g.arena_fog_selected = del_type
g.arena_fog_place_at(vec(zone0.centerx, zone0.centery))
check("布防待删除", len(g.arena_fog_placed) == 1 and
      g.arena_funds == pre_f - pool_map[del_type])
ent0, cost0, ut0 = g.arena_fog_placed[0]
check("右键删除单位退款",
      g.arena_fog_remove_at(vec(ent0.rect.centerx, ent0.rect.centery)) and
      g.arena_funds == pre_f and g.arena_fog_placed == [] and
      ent0 not in g.all_units and ent0 not in g.all_buildings and
      (ut0, cost0, 1) not in g.arena_army_info["team_0"]["comp"])
if "bastion" in pool_map:
    g.arena_funds = 5000
    pre_f = g.arena_funds
    g.arena_fog_selected = "bastion"
    g.arena_fog_place_at(vec(zone0.centerx, zone0.centery))
    bent = g.arena_fog_placed[-1][0]
    check("右键删除堡垒退款",
          g.arena_fog_remove_at(vec(bent.rect.centerx, bent.rect.centery)) and
          bent not in g.all_buildings and g.arena_funds == pre_f and
          len(g.arena_fog_placed) == 0)
else:
    check("右键删除堡垒退款（海图无堡垒）", "bastion" not in pool_map)

# 输入链路：右键已布防单位=删除退款；右键空白=取消选中
pre_chain = g.arena_funds
g.arena_fog_selected = del_type
g.arena_fog_place_at(vec(zone0.centerx, zone0.centery))
ent2 = g.arena_fog_placed[-1][0]
try:
    _cursor_at(((ent2.rect.centerx - g.camera_offset.x) * g.zoom,
                (ent2.rect.centery - g.camera_offset.y) * g.zoom))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                         pos=(0, 0), button=3))
    g.handle_arena_input()
    check("右键链路删除+退款",
          ent2 not in g.all_units and g.arena_fog_placed == [] and
          g.arena_funds == pre_chain)
    g.arena_fog_selected = del_type
    _cursor_at((300, 300))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                         pos=(300, 300), button=3))
    g.handle_arena_input()
    check("右键空白取消选中", g.arena_fog_selected is None)
finally:
    pygame.mouse.get_pos = _orig_gp

# 堡垒炮塔绘制不得污染旋转缓存（阴影 fill 原地改共享面 → 炮塔渐进变黑的回归）
# 断言与贴图内容无关：绘制前后同一缓存条目像素必须完全一致
if "bastion" in pool_map:
    from units.buildings import Bastion
    from core.base_classes import scale_img
    from core.utils import cached_rotate
    b = Bastion(g, vec(zone0.centerx, zone0.centery), "team_0")
    scaled = scale_img(b.image_turret, 1.0)
    rot_before = cached_rotate(scaled, 0)
    px = next((x, y) for y in range(rot_before.get_height())
              for x in range(rot_before.get_width())
              if rot_before.get_at((x, y))[3] > 0)
    before = rot_before.get_at(px)
    for _ in range(3):
        b.draw(g.screen, g.camera_offset, 1.0)
    rot_after = cached_rotate(scaled, 0)
    check("堡垒炮塔缓存未被阴影污染", rot_after.get_at(px) == before,
          f"before={before} after={rot_after.get_at(px)}")

# 布防：选池首兵种在己方半区中心落位，扣费立即生效
g.arena_funds = 1000
u0 = g.arena_army_pool[0][0]
price = dict(g.arena_army_pool)[u0]
g.arena_fog_selected = u0
zone0 = g.current_map.spawn_zones["team_0"]
pre = g.arena_funds
g.arena_fog_place_at(vec(zone0.centerx, zone0.centery))
check("布防落位+扣费",
      g.arena_funds == pre - price and g.arena_fog_spent == price and
      any(u.team == "team_0" for u in g.all_units))

# 情报：扣 100 军费
g.arena_fog_buy_intel()
check("购买情报", g.arena_fog_intel and g.arena_funds == pre - price - 100)
g.arena_draw()  # DEPLOY 覆盖层冒烟（商店/情报面板）
pygame.event.clear()

# 开战：敌军瞬间落位 + 快照记价
g.arena_start_fight()
t1_units = sum(1 for u in g.all_units if u.team == "team_1")
t1_builds = sum(1 for b in g.all_buildings if b.team == "team_1")
check("开战后敌军落位+快照", t1_units + t1_builds >= 2 and
      len(g.arena_fog_snapshot) == t1_units + t1_builds,
      f"u={t1_units} b={t1_builds}")
check("快照记价正确",
      all(c == dict(g.arena_army_pool)[e.u_type] for e, c in g.arena_fog_snapshot)
      if all(hasattr(e, 'u_type') for e, _c in g.arena_fog_snapshot) else True)

pre_fight = g.arena_funds
fog_ended = False
for i in range(6200):
    g.arena_update()
    if i % 1000 == 0:
        g.arena_draw()
    if g.arena_phase == "RESULT":
        fog_ended = True
        break
check("迷雾整局结束", fog_ended, f"winner={g.arena_result_winner}")
dead_cost = sum(_c for e, _c in g.arena_fog_snapshot if not e.alive)
kills = sum(1 for e, _c in g.arena_fog_snapshot if not e.alive)
expect = pre_fight + int(dead_cost * am.ARENA_FOG_KILL_RATE)
if g.arena_result_winner == "team_0":
    expect += am.ARENA_FOG_WIN_REWARD
elif g.arena_result_winner == "team_1":
    expect = max(0, expect - am.ARENA_FOG_LOSE_PENALTY)
check("迷雾结算数学（击杀+胜负）", g.arena_funds == expect,
      f"kills={kills} funds={g.arena_funds} expect={expect}")
g.arena_draw()  # RESULT 覆盖层冒烟
pygame.event.clear()
check("军费已落盘", sd.load_save_data()["funds"] == g.arena_funds)
g.arena_exit()
check("退出恢复 standard", g.arena_mode == "standard" and not g.arena_active)

# ---------- 汇总 ----------
print("\n==============================")
print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")

# 还原测试前的真实存档（不存在则删除，保持工作区干净）
if backup is not None:
    with open(real_save, 'w', encoding='utf-8') as f:
        f.write(backup)
elif os.path.exists(real_save):
    os.remove(real_save)
    if os.path.exists(real_save + '.bak'):
        os.remove(real_save + '.bak')

if FAIL:
    print("失败项:", FAIL)
    sys.exit(1)
print("ALL TESTS PASSED")
