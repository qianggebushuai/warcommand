import os
import sys
import pygame


def resource_path(relative_path):
    """ 获取资源绝对路径（基准 = 项目根目录） """
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        # utils.py 位于 core/ 下，上一级即项目根
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def get_font(size, bold=False):
    font_path = resource_path(os.path.join("fonts", "simhei.ttf"))
    try:
        font = pygame.font.Font(font_path, size)
        if bold:
            font.set_bold(True)
        return font
    except Exception:
        return pygame.font.Font(None, size)


# --- 缩放缓存 ---
# 摄像机平移时 zoom 恒定，但每帧对每个单位重复执行 scale/smoothscale 开销很大（卡顿主因）。
# 按 (surface id, zoom, 是否平滑) 缓存结果；条目持有原 surface 引用并用 is 校验身份，
# 超过上限整体清空，避免瞬时 surface 长期滞留。
# zoom 量化到 0.01：缩放动画期间同区间内命中，避免逐帧 miss 抖动（1% 尺寸差不可见）。
_scale_cache = {}
_SCALE_CACHE_CAP = 600


def cached_scale_img(img, zoom, smooth=True):
    key = (id(img), round(zoom, 2), smooth)
    entry = _scale_cache.get(key)
    if entry is not None and entry[0] is img:
        return entry[1]
    # 降采样纹理（downscale_texture）保留逻辑尺寸：按逻辑尺寸算目标，显示大小不变
    logical = _logical_sizes.get(id(img))
    if logical is not None and logical[0] is img:
        w, h = logical[1]
    else:
        w, h = img.get_size()
    size = (int(w * zoom), int(h * zoom))
    scaled = pygame.transform.smoothscale(img, size) if smooth else pygame.transform.scale(img, size)
    # 满员时逐出最旧条目（比整体清空平稳，避免全量重算的周期性尖峰）
    if len(_scale_cache) >= _SCALE_CACHE_CAP:
        _scale_cache.pop(next(iter(_scale_cache)), None)
    _scale_cache[key] = (img, scaled)
    return scaled


# --- 旋转缓存 ---
# transform.rotate 每次都生成全新 surface，是单位数量增多后的最大每帧开销。
# 静止/匀速单位角度不变或变化缓慢，按 2° 量化缓存旋转结果（视觉偏差 <=1°）。
# 条目持有原 surface 引用并以 is 校验身份，超上限整体清空。
_rotate_cache = {}
_ROTATE_CACHE_CAP = 1600
_ROTATE_QUANTUM = 2


def cached_rotate(img, angle, quantum=_ROTATE_QUANTUM, smooth=False):
    # quantum/smooth 可按单位调优：大战舰用 1°+rotozoom 平滑转向，小单位默认 2° 省 CPU
    q = int(round(angle / quantum))
    key = (id(img), q, quantum, smooth)
    entry = _rotate_cache.get(key)
    if entry is not None and entry[0] is img:
        return entry[1]
    a = q * quantum
    rotated = pygame.transform.rotozoom(img, a, 1.0) if smooth else pygame.transform.rotate(img, a)
    # 满员时逐出最旧条目（比整体清空平稳）
    if len(_rotate_cache) >= _ROTATE_CACHE_CAP:
        _rotate_cache.pop(next(iter(_rotate_cache)), None)
    _rotate_cache[key] = (img, rotated)
    return rotated


# --- 单位纹理降采样 ---
# 单位 PNG 按此系数降清存储（显示尺寸不变，运行时放大绘制），降低内存与缩放开销。
# 0.75 = 轻微降清几乎无损；需要更省可调 0.5。
SPRITE_DOWNSCALE = 0.75

# id(surf) -> (surf, 逻辑尺寸)；与缓存同模式：持有引用防 id 复用，is 校验身份
_logical_sizes = {}


def downscale_texture(surf, factor=None):
    """降低纹理分辨率但记录逻辑尺寸，blit 显示大小不变。"""
    factor = SPRITE_DOWNSCALE if factor is None else factor
    w, h = surf.get_size()
    nw, nh = max(1, int(w * factor)), max(1, int(h * factor))
    if nw >= w and nh >= h:
        return surf
    small = pygame.transform.smoothscale(surf, (nw, nh))
    _logical_sizes[id(small)] = (small, (w, h))
    return small


def logical_size(img):
    """downscale_texture 降采样表面的逻辑（显示）尺寸；未降采样则返回原始尺寸。"""
    entry = _logical_sizes.get(id(img))
    if entry is not None and entry[0] is img:
        return entry[1]
    return img.get_size()


def set_logical_size(img, size):
    """显式登记逻辑尺寸（如染色合成图继承 base 的逻辑尺寸）。"""
    try:
        if size is not None and tuple(size) != tuple(img.get_size()):
            _logical_sizes[id(img)] = (img, tuple(size))
    except Exception:
        pass
