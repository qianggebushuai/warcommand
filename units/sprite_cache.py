"""单位 sprite 的 PNG 缓存层（base + team-color mask 双层架构）。

目录结构（所有队伍共用同一套立绘）：

    sprites/units/<类名>/base/<属性名>.png   # 基础立绘（车体/炮塔等部件分开保存）
    sprites/units/<类名>/mask/<属性名>.png   # 染色遮罩：白色=显示队伍色的区域，透明=不受影响

运行时流程（units/__init__.py 末尾 enable_sprite_cache）：
1. 实例化时按类名查 base/ 目录 PNG；
2. 命中 -> 临时屏蔽 pygame.draw.* 让 __init__ 空跑，然后把 base 按各部件 mask
   染上当前队伍颜色后注入实例（同 (部件, 遮罩, 队伍色) 全局共享一份合成结果）；
3. 未命中 -> 照常现场绘制，导出 base/ PNG，并把图中与当前队伍色相近的像素
   提取为 mask/ PNG（下次运行即命中）。

美术修改指引：
- 改外观：编辑 base/ 下的 PNG（所有队伍共用这一份）；
- 改队伍色区域：编辑 mask/ 下对应 PNG——白色（不透明）区域会染成队伍色，
  透明区域保持 base 原色；
- 删除 sprites/units/<类名>/ 目录或重跑 python tools/export_sprites.py 可从
  程序绘制重新生成。
"""
import os
import functools
import pygame
from core.utils import resource_path, downscale_texture
from core.settings import TEAM_COLORS

SPRITE_ROOT = ('sprites', 'units')

# 这些类已自行实现 PNG 加载（sprites/mbt、sprites/bmpt + 类级 _sprite_cache），不重复包装；
# Unit/Building/Entity 是不含 sprite 绘制的基类，同样跳过。
EXCLUDED = {'Unit', 'Building', 'Entity', 'M1A2', 'TerminatorIFV'}

_surface_cache = {}          # 类名 -> ({部件: base Surface}, {部件: mask Surface}) / None
_tint_cache = {}             # (id(base), id(mask), 队伍色RGB) -> 染色合成 Surface
_save_failed_warned = set()

# 屏蔽期间 pygame.draw.* 统一返回 None。
# 已确认全项目没有 "= pygame.draw.xxx(...)" 捕获返回值的用法。
_DRAW_NAMES = tuple(n for n in (
    'rect', 'circle', 'polygon', 'line', 'lines', 'aaline', 'aalines',
    'ellipse', 'arc', 'pie') if hasattr(pygame.draw, n))


class suppress_draws:
    """临时把 pygame.draw.* 换成空操作：跳过绘制但保留 Surface 尺寸与其余逻辑。"""

    def __enter__(self):
        self._saved = {n: getattr(pygame.draw, n) for n in _DRAW_NAMES}
        for n in _DRAW_NAMES:
            setattr(pygame.draw, n, (lambda *a, **k: None))
        return self

    def __exit__(self, *exc):
        for n, fn in self._saved.items():
            setattr(pygame.draw, n, fn)
        return False


def parts_dir(cls_name, team, faction):
    """旧版按队伍分目录的路径（仅作向后兼容回退）。"""
    return resource_path(os.path.join(*SPRITE_ROOT, cls_name, '%s__%s' % (team, faction)))


def base_dir(cls_name):
    return resource_path(os.path.join(*SPRITE_ROOT, cls_name, 'base'))


def mask_dir(cls_name):
    return resource_path(os.path.join(*SPRITE_ROOT, cls_name, 'mask'))


def resolve_faction(game, team):
    """与单位类内部逻辑保持一致：faction 来自 game.teams_config[team]['faction']。"""
    tc = getattr(game, 'teams_config', None)
    try:
        if tc and team in tc:
            return tc[team].get('faction', 'USA')
    except Exception:
        pass
    return 'USA'


def team_rgb(team):
    """取队伍色 RGB 三元组。"""
    c = TEAM_COLORS.get(team, TEAM_COLORS.get('neutral', (120, 120, 120)))
    return (int(c[0]), int(c[1]), int(c[2]))


def _load_dir_pngs(d):
    loaded = {}
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith('.png'):
                loaded[fn[:-4]] = downscale_texture(
                    pygame.image.load(os.path.join(d, fn)).convert_alpha())
    return loaded


def load_parts(cls_name, team='neutral', faction='USA'):
    """加载某类共用的全部部件：返回 ({attr: base}, {attr: mask}) 或 None。

    优先读 base/ + mask/ 新结构；base/ 不存在时回退旧 <team>__<faction>/ 目录
    （旧图为特定队伍已染色版本，直接使用、不再染色）。
    """
    if cls_name in _surface_cache:
        return _surface_cache[cls_name]
    bundle = None
    try:
        base = _load_dir_pngs(base_dir(cls_name))
        if base:
            masks = _load_dir_pngs(mask_dir(cls_name))
            bundle = (base, {k: v for k, v in masks.items() if k in base})
        else:
            # 旧结构回退（兼容手改过的旧目录）
            legacy = _load_dir_pngs(parts_dir(cls_name, team, faction))
            if legacy:
                bundle = (legacy, {})
    except Exception as e:
        print('[sprite_cache] 加载 %s 失败，回退现场绘制: %s' % (cls_name, e))
        bundle = None
    _surface_cache[cls_name] = bundle
    return bundle


def extract_parts(instance):
    """收集实例属性里所有 pygame.Surface（车体/炮塔等部件）。"""
    return {k: v for k, v in vars(instance).items() if isinstance(v, pygame.Surface)}


def _extract_mask(surf, rgb):
    """从已染色部件图中提取队伍色遮罩：接近 team_color 的像素 -> 白色（保留原 alpha），
    其余 -> 透明。无有效队伍色像素返回 None。"""
    try:
        m = surf.convert_alpha().copy()
        w, h = m.get_size()
        if w == 0 or h == 0:
            return None
        px = pygame.surfarray.pixels3d(m)
        pa = pygame.surfarray.pixels_alpha(m)
        tr, tg, tb = rgb
        count = 0
        for x in range(w):
            for y in range(h):
                a = pa[x, y]
                if a == 0:
                    continue
                d = abs(px[x, y, 0] - tr) + abs(px[x, y, 1] - tg) + abs(px[x, y, 2] - tb)
                if d <= 130:
                    px[x, y, 0] = px[x, y, 1] = px[x, y, 2] = 255
                    count += 1
                else:
                    px[x, y, 0] = px[x, y, 1] = px[x, y, 2] = 0
                    pa[x, y] = 0
        del px, pa
        return m if count > 20 else None
    except Exception:
        return None


def shrink_mask(m, px=3):
    """把遮罩的白色（不透明）区域边缘向内腐蚀——缩小队伍色区域，
    避免大面积染色块在缩放/旋转时显得错位。
    自适应：逐轮腐蚀（每轮 1px，最多 px 轮），任一轮面积损失超过 20% 即
    不应用该轮并停止——大色块正常收缩，细识别条完全不动（细条腐蚀后
    降采样会 alpha 稀释到不可见）。"""
    try:
        import numpy as np
        a = pygame.surfarray.array_alpha(m) > 0
        orig = int(a.sum())
        if orig == 0:
            return m
        for _ in range(px):
            er = a.copy()
            er[1:, :] &= a[:-1, :]
            er[:-1, :] &= a[1:, :]
            er[:, 1:] &= a[:, :-1]
            er[:, :-1] &= a[:, 1:]
            if int(er.sum()) < orig * 0.8:    # 细条/窄环到此为止
                break
            a = er
        if int(a.sum()) == orig:
            return m
        pa = pygame.surfarray.pixels_alpha(m)
        pa[:] = np.where(a, pa, 0)
        del pa
        return m
    except Exception as e:
        print('[sprite_cache] mask 收缩失败（保留原样）: %s' % e)
        return m


def save_parts(cls_name, team, faction, parts):
    """导出共用 base/ 立绘 + 按当前队伍色提取 mask/ 遮罩（team/faction 仅用于日志）。"""
    try:
        bd = base_dir(cls_name)
        md = mask_dir(cls_name)
        os.makedirs(bd, exist_ok=True)
        os.makedirs(md, exist_ok=True)
        rgb = team_rgb(team)
        for attr, surf in parts.items():
            pygame.image.save(surf, os.path.join(bd, '%s.png' % attr))
            if team == 'neutral':
                continue    # 中立实体不提取遮罩（见 make_cached_init：不做中立染色）
            mask = _extract_mask(surf, rgb)
            if mask is not None:
                pygame.image.save(shrink_mask(mask), os.path.join(md, '%s.png' % attr))
    except Exception as e:
        if cls_name not in _save_failed_warned:
            _save_failed_warned.add(cls_name)
            print('[sprite_cache] 导出 %s(%s/%s) 失败: %s' % (cls_name, team, faction, e))


def _tint_part(base, mask, rgb):
    """base + 白色遮罩 -> 队伍色合成图（全局缓存，同 (部件, 遮罩, 队伍色) 只合成一次）。"""
    key = (id(base), id(mask), rgb)
    if key in _tint_cache:
        return _tint_cache[key]
    try:
        if mask.get_size() != base.get_size():
            mask = pygame.transform.smoothscale(mask, base.get_size())
        layer = pygame.Surface(base.get_size(), pygame.SRCALPHA)
        layer.fill((rgb[0], rgb[1], rgb[2], 255))
        layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        out = base.copy()
        out.blit(layer, (0, 0))
        # 关键：合成结果继承 base 的逻辑（显示）尺寸，否则降采样图按像素尺寸
        # 显示会缩小 25% 且锚点错位
        from core.utils import logical_size, set_logical_size
        set_logical_size(out, logical_size(base))
    except Exception:
        return base
    _tint_cache[key] = out
    return out


def inject_parts(instance, parts):
    for attr, surf in parts.items():
        setattr(instance, attr, surf)


def make_cached_init(cls, orig_init):
    # 变体类（如民居/欧式建筑）：类属性 _variant_attr 指明变体号字段，
    # PNG 按变体分开存（<attr>_v<variant>.png），避免注入时所有变体塌缩成一张图
    vattr = getattr(cls, '_variant_attr', None)

    @functools.wraps(orig_init)
    def __init__(self, game, *args, **kwargs):
        # 约定：所有单位 __init__ 均为 (game, pos[, team, ...]) 形态。
        # 队伍必须是合法队伍名——不能盲取 args[1]：桥是 (game, pos, orientation, length)，
        # args[1]='horizontal' 会被误当队伍，导致中立灰染色仍然发生（桥墩被抹平的根因）
        team = kwargs.get('team')
        if team is None:
            for a in args:
                if isinstance(a, str) and (a in TEAM_COLORS or str(a).startswith('team_')):
                    team = a
                    break
        if team is None:
            team = 'neutral'
        faction = resolve_faction(game, team)
        bundle = load_parts(cls.__name__, team, faction)
        if bundle:
            base_parts, mask_parts = bundle
            with suppress_draws():
                orig_init(self, game, *args, **kwargs)
            if vattr:
                vid = getattr(self, vattr, None)
                if vid is not None:
                    vp, vm = {}, {}
                    # 只按真实属性名匹配：vars(self) 的属性名 + 变体键去掉 _v<vid> 后缀
                    # 的名字。直接遍历 bundle 键会把别的变体（image_vhorizontal_600）
                    # 当垃圾属性注入，self.image 留在 suppress_draws 下的空白画布上
                    attr_names = set(vars(self)) | {
                        k.rsplit('_v', 1)[0] for k in base_parts if '_v' in k}
                    for a in attr_names:
                        k = '%s_v%s' % (a, vid)
                        if k in base_parts:
                            vp[a] = base_parts[k]
                            if k in mask_parts:
                                vm[a] = mask_parts[k]
                        elif a in base_parts:
                            vp[a] = base_parts[a]      # 回退到无变体后缀的图
                            if a in mask_parts:
                                vm[a] = mask_parts[a]
                    base_parts, mask_parts = vp, vm
            if base_parts:
                rgb = team_rgb(team)
                # 中立实体不做队伍染色：中立色是固定灰，染色只会把立绘里的灰阶调色板
                #（混凝土/金属等）整片误染成同一块平板灰，毁掉细节对比（如桥墩帽消失）
                final = {a: (_tint_part(s, mask_parts[a], rgb)
                             if (a in mask_parts and team != 'neutral') else s)
                         for a, s in base_parts.items()}
                inject_parts(self, final)
            else:
                # 精确变体未命中（如桥的新长度，bundle 里全是别的变体）：
                # suppress_draws 下的画布是空白的，必须真实重画一遍并保存本变体，
                # 之后的实例即可直接命中
                orig_init(self, game, *args, **kwargs)
                new_parts = extract_parts(self)
                if new_parts and vattr:
                    vid = getattr(self, vattr, None)
                    if vid is not None:
                        new_parts = {'%s_v%s' % (a, vid): s for a, s in new_parts.items()}
                if new_parts:
                    save_parts(cls.__name__, team, faction, new_parts)
        else:
            orig_init(self, game, *args, **kwargs)
            new_parts = extract_parts(self)
            if new_parts and vattr:
                vid = getattr(self, vattr, None)
                if vid is not None:
                    new_parts = {'%s_v%s' % (a, vid): s for a, s in new_parts.items()}
            if new_parts:
                save_parts(cls.__name__, team, faction, new_parts)
    return __init__


def enable_sprite_cache(namespace):
    """包装 units 包里所有定义了自身 __init__ 的实体类。返回包装数量。"""
    from core.base_classes import Entity
    count = 0
    for name, obj in list(namespace.items()):
        if not isinstance(obj, type) or name in EXCLUDED:
            continue
        if not getattr(obj, '__module__', '').startswith('units.'):
            continue
        if not issubclass(obj, Entity):
            continue
        # 继承标记：父类已被包装则跳过（含无自定义 __init__ 的子类）
        # 注意用 __dict__ 检查，避免子类继承父类的标记而被误跳过
        if obj.__dict__.get('_sprite_png_wrapped', False):
            continue
        orig = obj.__init__
        # 只包装"自己定义了 __init__"的类（继承来的由父类包装负责）
        if getattr(orig, '__module__', '') != obj.__module__:
            continue
        obj.__init__ = make_cached_init(obj, orig)
        obj._sprite_png_wrapped = True
        count += 1
    return count


def enable_sprite_cache_for(classes):
    """显式包装类列表（用于 core.base_classes 等非 units.* 模块的建筑类）"""
    count = 0
    for cls in classes:
        if not isinstance(cls, type) or cls.__dict__.get('_sprite_png_wrapped', False):
            continue
        orig = cls.__init__
        # 只包装"自己定义了 __init__"的类
        if getattr(orig, '__module__', '') != cls.__module__:
            continue
        cls.__init__ = make_cached_init(cls, orig)
        cls._sprite_png_wrapped = True
        count += 1
    return count
