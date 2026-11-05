# -*- coding: utf-8 -*-
"""合成训练数据：脱离游戏循环，用真实单位/建筑类渲染随机战场 → 自动标注。

不需要先打几局采集——直接调用游戏自身的实体类（M1A2/PowerPlant/…）在
随机背景上渲染随机阵容（阵营/缩放/血量/位置随机），画面与真实对局一致，
标注零成本（实体知道自己画在哪）。

产出与 DatasetRecorder 同格式（dataset/autoplay/{images,labels.jsonl}），
之后 `python tools/train_detector.py` 正常训练。

用法：
    python tools/synth_dataset.py               # 默认 400 帧
    python tools/synth_dataset.py --frames 600 --clear   # 清掉旧数据重来
"""
import argparse
import math
import os
import random
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
from pygame.math import Vector2 as vec

from core.settings import GRASS_COLOR, WORLD_WIDTH, WORLD_HEIGHT, SCREEN_WIDTH, SCREEN_HEIGHT
from ai_autoplay.vision import DatasetRecorder, ui_landmarks

# 参与合成的类（实例化失败自动跳过并汇总）
GROUND_CLASSES = ['M1A2', 'Type99', 'APC', 'Harvester', 'HeavyMech', 'TerminatorIFV',
                  'ArmoredCar', 'HIMARS', 'Rifleman', 'Shotgunner', 'Sniper',
                  'RocketTrooper', 'Engineer', 'CombatEngineer', 'ScoutDrone']
AIR_CLASSES = ['FighterJet', 'AttackPlane', 'Helicopter', 'KirovAirship', 'Mi24', 'WZ10']
BUILDING_CLASSES = ['PowerPlant', 'Barracks', 'FactoryBuilding', 'Bunker',
                    'AntiAirTurret', 'LaserTurret', 'MiningRig', 'RadarBuilding',
                    'Airfield', 'ResearchCenter', 'MissileDefenseSystem', 'Bastion']
TEAMS = ['team_0', 'team_1', 'team_2']
FACTIONS = ['USA', 'RUSSIA', 'CHINA']

SIDEBAR_W = ui_landmarks(SCREEN_WIDTH, SCREEN_HEIGHT)['minimap'][2]
VIEWPORT = pygame.Rect(0, 0, SCREEN_WIDTH - SIDEBAR_W, SCREEN_HEIGHT)


def make_game_stub():
    """实体 init/draw 需要的最小 game 替身。"""
    teams_config = {t: {'faction': random.choice(FACTIONS)} for t in TEAMS}
    return types.SimpleNamespace(
        teams_config=teams_config, all_units=[], all_buildings=[],
        particles=None, floating_texts=None, frame_count=0,
        my_team='team_0', is_online=False, state='PLAYING')


def make_background():
    """仿游戏地面：草底色 + 随机深浅地块 + 稀疏树。"""
    s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    s.fill(GRASS_COLOR)
    for _ in range(60):
        w, h = random.randint(40, 160), random.randint(40, 160)
        shade = random.randint(-14, 14)
        c = (max(0, min(255, GRASS_COLOR[0] + shade)),
             max(0, min(255, GRASS_COLOR[1] + shade)),
             max(0, min(255, GRASS_COLOR[2] + shade)))
        s.fill(c, (random.randint(-40, VIEWPORT.w), random.randint(-40, VIEWPORT.h), w, h))
    tree_path = os.path.join(ROOT, 'sprites', 'tree', 'tree.png')
    if os.path.exists(tree_path):
        try:
            tree = pygame.image.load(tree_path).convert_alpha()
            for _ in range(random.randint(3, 8)):
                z = random.uniform(0.6, 1.4)
                img = pygame.transform.smoothscale(
                    tree, (int(tree.get_width() * z), int(tree.get_height() * z)))
                s.blit(img, (random.randint(0, VIEWPORT.w - 80),
                             random.randint(0, VIEWPORT.h - 80)))
        except Exception:
            pass
    return s


def load_classes():
    """import 游戏实体类，返回 {name: class}（仅存在于对应模块的）。"""
    import units  # noqa: F401  触发 sprite_cache 等初始化
    from units import vehicles, aircraft, infantry, buildings, defenses
    wanted = set(GROUND_CLASSES + AIR_CLASSES + BUILDING_CLASSES)
    found = {}
    for mod in (vehicles, aircraft, infantry, buildings, defenses):
        for name in dir(mod):
            if name in wanted:
                found[name] = getattr(mod, name)
    return found


def build_frame(cls_map, rng):
    """渲染一帧：随机缩放/阵容/血量的实体群 + 随机水域 → (surface, labels)。"""
    stub = make_game_stub()
    zoom = rng.uniform(0.6, 1.3)
    cam = vec(rng.uniform(0, max(1, WORLD_WIDTH - VIEWPORT.w / zoom)),
              rng.uniform(0, max(1, WORLD_HEIGHT - VIEWPORT.h / zoom)))
    surface = make_background()

    # ---- 随机水域（世界坐标多边形，与游戏 terrain water 同款配色） ----
    from maps.map_data import point_in_poly, TERRAIN_POLY_COLORS
    lake_polys = []
    lake_labels = []
    for _ in range(rng.randint(0, 2)):
        cx = rng.uniform(300, WORLD_WIDTH - 300)
        cy = rng.uniform(300, WORLD_HEIGHT - 300)
        rx, ry = rng.uniform(180, 420), rng.uniform(140, 340)
        n_v = rng.randint(8, 12)
        poly = []
        for k in range(n_v):
            ang = k / float(n_v) * 2 * math.pi
            jr = rng.uniform(0.75, 1.2)
            poly.append((int(cx + math.cos(ang) * rx * jr),
                         int(cy + math.sin(ang) * ry * jr)))
        lake_polys.append(poly)
        # 屏幕 space 绘制（半透明蓝，叠在草地上）
        pts = [((px - cam[0]) * zoom, (py - cam[1]) * zoom) for px, py in poly]
        if all(-600 < p[0] < VIEWPORT.w + 600 and -600 < p[1] < VIEWPORT.h + 600
               for p in pts):
            water = pygame.Surface(VIEWPORT.size, pygame.SRCALPHA)
            pygame.draw.polygon(water, TERRAIN_POLY_COLORS['water'], pts)
            pygame.draw.polygon(water, (35, 85, 150, 200), pts, 3)
            surface.blit(water, (0, 0))
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            bx, by = int(max(0, min(xs))), int(max(0, min(ys)))
            bw = int(min(VIEWPORT.w - bx, max(xs) - bx))
            bh = int(min(VIEWPORT.h - by, max(ys) - by))
            if bw > 30 and bh > 30:
                lake_labels.append({
                    'class': 'Lake', 'team': 'neutral', 'hp_ratio': 1.0,
                    'x': bx, 'y': by, 'w': bw, 'h': bh,
                    'world_pos': [int(cx), int(cy)],
                })

    pool = (GROUND_CLASSES * 6 + AIR_CLASSES * 2 + BUILDING_CLASSES * 4)
    placed = []          # (screen_pos, half_px)
    labels = list(lake_labels)
    n_target = rng.randint(8, 16)
    for _ in range(n_target * 3):
        if len(placed) >= n_target:
            break
        name = rng.choice([n for n in pool if n in cls_map] or list(cls_map))
        cls = cls_map[name]
        team = rng.choice(TEAMS)
        pos = vec(rng.uniform(200, WORLD_WIDTH - 200), rng.uniform(200, WORLD_HEIGHT - 200))
        if any(point_in_poly(lp, pos.x, pos.y) for lp in lake_polys):
            continue                                       # 单位/建筑不下水
        sp = (pos - cam) * zoom
        if not VIEWPORT.collidepoint(sp):
            continue
        if any((sp - p).length() < (h + 40) for p, h in placed):   # 防重叠
            continue
        try:
            e = cls(stub, pos, team)
            if hasattr(e, 'max_hp') and e.max_hp:
                e.hp = e.max_hp * rng.uniform(0.35, 1.0)   # 触发血条绘制
            e.draw(surface, cam, zoom)
        except Exception as ex:
            print('  [skip] %s: %s' % (name, ex))
            cls_map.pop(name, None)                        # 坏类剔除，不再尝试
            continue
        rect = getattr(e, 'rect', None)
        vis = max(getattr(e, 'radius', 14) * 2,
                  rect.w if rect is not None else 0,
                  rect.h if rect is not None else 0, 24)
        half = vis * zoom / 2
        placed.append((vec(sp), half))
        # 类名带阵营后缀（与 vision.project_entities 一致）
        cls_name = name
        fac = str(getattr(e, 'faction', '') or '').upper()
        suffix = {'USA': 'usa', 'RUSSIA': 'rus', 'CHINA': 'chn'}.get(fac)
        if suffix:
            cls_name = '%s_%s' % (name, suffix)
        labels.append({
            'class': cls_name, 'team': team,
            'hp_ratio': round(float(getattr(e, 'hp', 100)) / max(1.0, float(getattr(e, 'max_hp', 100))), 2),
            'x': max(0, int(sp[0] - half) - 6), 'y': max(0, int(sp[1] - half) - 6),
            'w': min(VIEWPORT.w - max(0, int(sp[0] - half) - 6), int(half * 2) + 12),
            'h': min(VIEWPORT.h - max(0, int(sp[1] - half) - 6), int(half * 2) + 12),
            'world_pos': [int(pos.x), int(pos.y)],
        })
    return surface, labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frames', type=int, default=400)
    ap.add_argument('--clear', action='store_true', help='清空旧采集数据后重新生成')
    args = ap.parse_args()

    pygame.init()
    pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

    rec_dir = os.path.join(ROOT, 'dataset', 'autoplay')
    if args.clear and os.path.isdir(rec_dir):
        import shutil
        shutil.rmtree(rec_dir)
        print('[synth] 已清空旧数据 %s' % rec_dir)

    rec = DatasetRecorder(rec_dir)
    cls_map = load_classes()
    print('[synth] 可用类 %d/%d' % (len(cls_map), len(GROUND_CLASSES + AIR_CLASSES + BUILDING_CLASSES)))
    rng = random.Random(20261102)
    n_ok = 0
    for i in range(args.frames):
        surface, labels = build_frame(cls_map, rng)
        if not labels:
            continue
        import io
        buf = io.BytesIO()
        pygame.image.save(surface, buf, 'frame.png')
        rec.save(buf.getvalue(), labels, {'synth': True, 'frame': i})
        n_ok += 1
        if n_ok % 50 == 0:
            print('[synth] %d/%d 帧' % (n_ok, args.frames))
    print('[synth] 完成：%d 帧 → %s' % (n_ok, rec_dir))
    print('[synth] 下一步：python tools/train_detector.py')


if __name__ == '__main__':
    main()
