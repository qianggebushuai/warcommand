"""把 units 中所有单位类的 sprite 部件导出为 PNG（部件分开保存）。

用法（在项目根目录）:
    python tools/export_sprites.py

流程：无头模式（SDL dummy）下，对每个实体类 x 每个 team x 每个 faction
实例化一次；units/sprite_cache.py 的包装器发现没有 PNG 时会照常现场
绘制，并把实例上的 Surface 属性自动保存到:

    sprites/units/<类名>/<team>__<faction>/<属性名>.png

车体（original_image/body_image/hull_image...）与炮塔（turret_image）
等独立部件分开保存，draw() 时各自用不同角度旋转。
导出完成后，游戏即按路径加载这些 PNG，不再局内绘制。

faction 只随 teams_config 里的 team_N 变化；neutral 在运行时总是
解析为默认 USA，因此只需导出一份。
"""
import os
import sys
import inspect
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
pygame.init()
pygame.display.set_mode((1, 1))  # convert_alpha 需要一个 display（dummy 驱动即可）

from core.settings import TEAM_COLORS
from core.base_classes import Entity
import units
from units import sprite_cache
from units.sprite_cache import EXCLUDED, parts_dir

FACTIONS = ['USA', 'CHINA', 'RUSSIA']

# 与运行时 resolve_faction 行为一致：只有 team_N 会取到不同 faction
TEAM_FACTIONS = {t: FACTIONS for t in ('team_0', 'team_1', 'team_2', 'team_3', 'team_4')}
for t in TEAM_COLORS:
    TEAM_FACTIONS.setdefault(t, ['USA'])

# __init__ 额外参数的填充值（按参数名）
VEC_PARAMS = {'pos', 'target_pos', 'orbit_center', 'drop_pos', 'build_pos', 'spawn_pos'}
EXTRA_PARAMS = {'head': None, 'index': 0, 'home_building': None, 'parent': None}


class _Stub:
    def __getattr__(self, name):
        v = _Stub()
        self.__dict__[name] = v
        return v

    def __call__(self, *a, **k):
        return _Stub()

    def __getitem__(self, k):
        return _Stub()

    def __contains__(self, k):
        return False

    def get(self, k, d=None):
        return d

    def add(self, *a, **k):
        pass


class FakeGame(_Stub):
    """最小化 game 桩：只保证 __init__ 期间被访问的属性可用。"""

    def __init__(self, team, faction):
        self.teams_config = {team: {'name': 'P', 'faction': faction}}
        self.team_tech_levels = {}
        self.my_faction = faction
        self.enemy_faction = faction
        self.all_buildings = []
        self.all_units = []
        self.particles = _Stub()
        self.current_map = None  # AC130.calculate_spawn_pos 回退到 WORLD_WIDTH/HEIGHT


def build_init_args(cls, team, faction):
    sig = inspect.signature(cls.__init__)
    args = []
    for p in list(sig.parameters.values())[1:]:
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            break
        if p.name == 'game':
            args.append(FakeGame(team, faction))
        elif p.name == 'team':
            args.append(team)
        elif p.name in EXTRA_PARAMS:
            args.append(EXTRA_PARAMS[p.name])
        elif p.name in VEC_PARAMS:
            args.append(pygame.math.Vector2(0, 0))
        elif p.default is not inspect.Parameter.empty:
            break  # 剩余参数交给默认值
        else:
            args.append(pygame.math.Vector2(0, 0))  # 未知位置参数按向量兜底
    return args


# 死代码：ArtilleryCruiser.__init__ 调用了不存在的 self.gen_hull()/gen_turret()，
# 且其 draw() 为 pass（重构前的 units.py 即如此）。全项目没有任何地方生产它，
# 无法实例化导出，跳过。
DEAD_CLASSES = {'ArtilleryCruiser'}


def collect_classes():
    out = []
    for name, obj in vars(units).items():
        if not isinstance(obj, type) or name in EXCLUDED or name in DEAD_CLASSES:
            continue
        if not getattr(obj, '__module__', '').startswith('units.'):
            continue
        if not issubclass(obj, Entity):
            continue
        out.append(obj)
    # core.base_classes 白名单建筑（与 units.__init__ 的 _building_cache_whitelist 一致）
    for name in getattr(units, '_building_cache_whitelist', []):
        cls = getattr(units._bc, name, None)
        if isinstance(cls, type) and cls not in out:
            out.append(cls)
    return out


def variant_ids(cls):
    """变体类：返回变体号列表；普通类返回 [None]（单实例）
    - _variant_attr='faction'：按阵营字符串变体——构造时不追加参数，
      PNG 后缀自动取 self.faction（外层 team×faction 循环已覆盖所有阵营）
    - 其他 _variant_count：整数变体号，追加为位置参数"""
    if getattr(cls, '_variant_attr', None) == 'faction':
        return ['faction']
    n = getattr(cls, '_variant_count', 0)
    return list(range(n)) if n else [None]


def count_class_pngs(cls_name):
    d = resource_dir(cls_name)
    n = 0
    for root, _dirs, files in os.walk(d):
        n += sum(1 for f in files if f.lower().endswith('.png'))
    return n


def resource_dir(cls_name):
    return os.path.dirname(parts_dir(cls_name, 'x', 'y'))  # sprites/units/<类名>


def main():
    only = set(sys.argv[1:])  # 可选：只导出指定类名
    classes = collect_classes()
    if only:
        classes = [c for c in classes if c.__name__ in only]
    print('== 共 %d 个类待导出 ==' % len(classes))
    failures = []
    empty_classes = []
    for cls in classes:
        n_fail = 0
        # 强制现场重绘：删掉已有目录，否则加载命中旧 PNG 后原样再存，
        # 外观/mask 的修改（含收缩策略调整）永远不会重新起算
        import shutil
        cls_dir = resource_dir(cls.__name__)
        if os.path.isdir(cls_dir):
            shutil.rmtree(cls_dir)
        for team, factions in TEAM_FACTIONS.items():
            for faction in factions:
                for vid in variant_ids(cls):
                    label = '%s %s/%s%s' % (cls.__name__, team, faction,
                                            ' v%s' % vid if vid is not None else '')
                    try:
                        args = build_init_args(cls, team, faction)
                        if vid is not None and vid != 'faction':
                            args.append(vid)  # 变体类：追加 variant_id 位置参数（faction 变体不加）
                        inst = cls(*args)
                        n_parts = len(sprite_cache.extract_parts(inst))
                        if n_parts == 0 and not os.path.isdir(parts_dir(cls.__name__, team, faction)):
                            pass  # 该类无存储 sprite（程序化 draw），跳过
                    except Exception:
                        n_fail += 1
                        failures.append((label, traceback.format_exc(limit=4)))
        pngs = count_class_pngs(cls.__name__)
        if pngs == 0:
            empty_classes.append(cls.__name__)
        print('[%s] %-20s pngs=%-5d fail=%d' % (
            'FAIL' if n_fail else ('OK' if pngs else 'EMPTY'), cls.__name__, pngs, n_fail))

    total = 0
    base = os.path.dirname(resource_dir('x'))
    for _root, _dirs, files in os.walk(base):
        total += sum(1 for f in files if f.lower().endswith('.png'))

    print('\n== 汇总 ==')
    print('PNG 总数: %d  (目录: %s)' % (total, base))
    if empty_classes:
        print('无存储 sprite 的类（程序化 draw，无需导出）: %s' % ', '.join(empty_classes))
    if failures:
        print('\n== 失败详情 (%d) ==' % len(failures))
        for label, tb in failures[:40]:
            print('--- %s\n%s' % (label, tb))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
