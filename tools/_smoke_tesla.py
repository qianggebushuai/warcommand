# -*- coding: utf-8 -*-
"""巨型电磁塔（TeslaTower）冒烟：立绘/注册/编辑器交互/占领/电力门控/电击拆分/绘制/布局往返/联机重建。"""
import os
import sys
import json

os.environ['SDL_VIDEODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from pygame.math import Vector2 as vec

PASS = TOTAL = 0
def check(name, cond, detail=""):
    global PASS, TOTAL
    TOTAL += 1
    if cond:
        PASS += 1
        print("PASS  " + name)
    else:
        print("FAIL  " + name + "  " + str(detail))

# 先建真窗口再 import 项目模块（SCREEN_WIDTH 陷阱）
pygame.init()
pygame.display.set_mode((1600, 900))

from map_layout_editor import MapLayoutEditor, EditorGame
from units.buildings import TeslaTower
from core.settings import TESLA_TOWER_HP, TESLA_TOWER_POWER_USAGE
from units.base import Unit

ed = MapLayoutEditor(0)
m = ed.map_obj
g = ed.game
# TeslaTower.update 需要的电网上下文（EditorGame 没有，手动补齐）
g.current_voltage = 0
g.max_voltage = 300
g.frame_count = 0
# 换成真 sprite Group 以便断言"已占领!"特效确实入列
g.particles = pygame.sprite.Group()

# JSON 备份/恢复：测试 save 不能污染真实布局文件（参考 _smoke_terrain 顶部做法）
from maps.map_data import _map_layout_path, LAYOUT_BUILDING_TYPES
_layout_path = _map_layout_path(m.__class__.__name__)
_json_backup = None
if os.path.exists(_layout_path):
    _json_backup = open(_layout_path, 'rb').read()

try:
    # 1. 立绘 PNG 存在且可 load（320×320、convert_alpha 友好）
    from core.utils import resource_path
    png_path = resource_path(os.path.join("picture", "tesla_tower.png"))
    img = None
    if os.path.exists(png_path):
        img = pygame.image.load(png_path).convert_alpha()
    check("1 picture/tesla_tower.png 存在且可 load 320x320",
          img is not None and img.get_size() == (320, 320),
          (os.path.exists(png_path), img.get_size() if img else None))

    # 2. 编辑器注册表 + 中立实例化
    check("2a LAYOUT_BUILDING_TYPES 已注册 TeslaTower(team=False)",
          "TeslaTower" in LAYOUT_BUILDING_TYPES
          and LAYOUT_BUILDING_TYPES["TeslaTower"]["team"] is False)
    t = m.make_layout_building("TeslaTower", vec(2000, 2000))
    check("2b make_layout_building 实例化 neutral/hp/radius/耗电",
          isinstance(t, TeslaTower) and t.team == "neutral" and t.hp == TESLA_TOWER_HP
          and t.radius == 75 and t.b_type == "tesla_tower" and t.power_usage == TESLA_TOWER_POWER_USAGE,
          (type(t).__name__, getattr(t, 'team', None)))

    # 3. 编辑器交互：面板数据源含按钮 → 放置 → 空手命中 → 删除
    panel_has = any(item == ("type", "TeslaTower") for item in ed.panel_items())
    check("3a 面板数据源含 TeslaTower 按钮", panel_has)
    # radius 提到 75 后固定点可能与既有建筑重叠被拒 → 依次试候选点取首个成功位
    spot = None
    for cand in ((1000, 1000), (300, 300), (4500, 300), (300, 3000), (4500, 3000), (2400, 1600)):
        ed.place_building("TeslaTower", vec(*cand))
        if any(isinstance(b, TeslaTower) for b in m.neutral_buildings):
            spot = cand
            break
    placed = [b for b in m.neutral_buildings if isinstance(b, TeslaTower)]
    check("3b 放置入库 neutral_buildings", len(placed) == 1 and spot is not None, (len(placed), spot))
    hit = ed.hit_building(vec(*spot)) if spot else None
    check("3c 空手可命中已放置电磁塔", isinstance(hit, TeslaTower))
    label = ed.delete_at(vec(*spot)) if spot else None
    check("3d 空手可删除已放置电磁塔",
          label == "TeslaTower" and not any(isinstance(b, TeslaTower) for b in m.neutral_buildings),
          (label,))

    # 4. generate_image：PNG 生成后优先引用该图
    gi = t.generate_image()
    check("4 generate_image 优先引用立绘 PNG(320x320)",
          isinstance(gi, pygame.Surface) and gi.get_size() == (320, 320),
          gi.get_size() if isinstance(gi, pygame.Surface) else type(gi))

    # 5. 占领：友方地面单位靠近跑帧 → team 翻转 + "已占领!"特效入列
    cap = m.make_layout_building("TeslaTower", vec(4000, 4000))
    class _Probe(Unit):
        def __init__(self, game, pos, team="team_0"):
            super().__init__(game, pos, team)
            self.speed = 0
    caper = _Probe(g, vec(4060, 4000))          # 距塔 60 < CAPTURE_RADIUS(130)
    g.all_units = [caper]
    for _ in range(TeslaTower.CAPTURE_TIME + 5):
        cap.update()
    check("5 占领后 team 翻转+特效文字入列",
          cap.team == "team_0" and cap.capture_progress == 0 and len(g.particles) >= 1,
          (cap.team, cap.capture_progress, len(g.particles)))

    # 6. 电力门控：电网超载（current > max）不电击、zaps 清空
    foe1 = _Probe(g, vec(4300, 4000), "team_1")  # 距塔 300 < 450，在攻击范围内
    g.all_units = [caper, foe1]
    hp0 = foe1.hp
    g.current_voltage = 400                      # > max(300) 超载
    cap.update()
    check("6 电网超载不电击", cap.powered is False and foe1.hp == hp0 and cap.zaps == [],
          (cap.powered, foe1.hp, hp0, cap.zaps))

    # 7. 电力充足：单目标受全额 120
    g.current_voltage = 0
    cap.update()
    check("7 电力充足单目标受全额伤害", foe1.hp == hp0 - TeslaTower.BASE_DAMAGE and len(cap.zaps) == 1,
          (foe1.hp, hp0, len(cap.zaps)))

    # 8. 多目标伤害拆分：3 个敌人各受 BASE_DAMAGE/3
    foes = [_Probe(g, vec(4200 + i * 30, 4100), "team_1") for i in range(3)]
    g.all_units = [caper] + foes
    hps0 = [f.hp for f in foes]
    cap.zaps = []
    cap.attack_timer = 0
    cap.update()
    split = [h0 - f.hp for h0, f in zip(hps0, foes)]
    per = TeslaTower.BASE_DAMAGE // 3
    check("8 三目标各受 BASE_DAMAGE/3", all(d == per for d in split) and len(cap.zaps) == 3, (per, split))

    # 9. 超 6 目标只打最近 6 个
    many = [_Probe(g, vec(4100 + (i % 6) * 40, 3900 - (i // 6) * 40), "team_1") for i in range(9)]
    g.all_units = [caper] + many
    n0 = [f.hp for f in many]
    cap.zaps = []
    cap.attack_timer = 0
    cap.update()
    hitn = sum(1 for f0, f in zip(n0, many) if f.hp < f0)
    check("9 九目标只电最近 MAX_TARGETS 个",
          hitn == TeslaTower.MAX_TARGETS and len(cap.zaps) == TeslaTower.MAX_TARGETS, (hitn, len(cap.zaps)))

    # 10. zaps 计时器随帧衰减至清空
    for _ in range(TeslaTower.ZAP_DURATION + 2):
        cap.update()
    check("10 zaps 计时衰减清空", cap.zaps == [], cap.zaps)

    # 11. 整帧绘制不崩（闪电特效 + 占领进度条 + 暗/亮态两种）
    try:
        cap.zaps = [(vec(4300, 4000), 12)]
        cap.capture_progress = 90
        cap.powered = True
        cap.draw(ed.win, vec(3500, 3600), 1.0)   # 平移镜头让塔落在视口内
        cap.powered = False
        cap.draw(ed.win, vec(3500, 3600), 1.0)
        ok11 = True
    except Exception as e:
        ok11 = False
        print("  draw err:", e)
    check("11 整帧绘制（闪电+进度条+暗/亮态）不崩", ok11)

    # 12. 布局导出→JSON→重载重建（save 走备份/finally 恢复，不污染真实布局）
    t2 = m.make_layout_building("TeslaTower", vec(1234, 567))
    m.neutral_buildings.append(t2)
    path = m.save_layout()
    data = json.load(open(path, encoding="utf-8"))
    tt = [e for e in data.get("neutral", []) if e.get("cls") == "TeslaTower"]
    check("12a 导出 JSON 含 cls=TeslaTower 且坐标正确",
          len(tt) >= 1 and tt[-1]["x"] == 1234 and tt[-1]["y"] == 567, tt)
    m2 = type(m)(None)
    m2.game = EditorGame(m2)
    m2.generate(seed=0)
    m2.apply_layout_override()
    rebuilt = [b for b in m2.neutral_buildings if isinstance(b, TeslaTower)]
    check("12b apply_layout_override 重载重建 TeslaTower", len(rebuilt) >= 1,
          len(rebuilt))

    # 13. 联机重建：spawn_building_by_data 按 cls_name 实例化
    from game.spawner_mixin import SpawnerMixin
    stub = type('S', (), {})()
    stub.all_buildings = []
    SpawnerMixin.spawn_building_by_data(stub, {"x": 500, "y": 600, "team": "team_0",
                                               "type": "tesla_tower", "uid": "u1",
                                               "cls": "TeslaTower", "hp": 777})
    nb = stub.all_buildings[0] if stub.all_buildings else None
    check("13 spawn_building_by_data 按 cls 重建",
          isinstance(nb, TeslaTower) and nb.uid == "u1" and nb.hp == 777
          and nb.team == "neutral", nb)

finally:
    # 恢复真实布局 JSON（测试 save 的内容不落盘）
    if _json_backup is not None:
        open(_layout_path, 'wb').write(_json_backup)
    elif os.path.exists(_layout_path):
        os.remove(_layout_path)

print("\n%d/%d passed" % (PASS, TOTAL))
sys.exit(0 if PASS == TOTAL else 1)
