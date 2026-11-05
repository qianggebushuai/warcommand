"""单位数据配置加载器：数据唯一来源是 config/units.json。

JSON 分七个分区，键名与 core.settings 中的常量名完全一致：
  costs       造价（*_COST / *_COST 变体命名）
  stats       属性（键 -> {hp, speed, range, mine?}，加载时转为 [range, speed, hp] 位置列表；
              mine 为可选扩展字段=矿车满载采矿量，注入为 HARVEST_AMOUNT）
  damage      伤害（DMG_* 等）
  build_time  建造时间（BUILD_TIME*）
  buildings   建筑数值（POWER_PLANT_HP 等标量）
  ai          电脑AI 数值（AI_UNIT_CAP_* 等标量）
  armor       护甲表（键=实体类名，整体注入为 UNIT_ARMOR 字典供 Entity 查表）

core/settings.py 末尾调用 apply_unit_config(globals()) 把数据注入模块命名空间，
因此所有 `from core.settings import *` 的代码无需任何改动。
"""
import json
import os

# unit_config.py 位于 core/ 下，上一级即项目根（与 core/utils.resource_path 同基准）
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(_ROOT, 'config', 'units.json')

SECTIONS = ('costs', 'stats', 'damage', 'build_time', 'buildings', 'ai', 'armor')


class UnitConfigError(Exception):
    """单位配置缺失/损坏时抛出（带可操作的恢复指引）。"""


def load_config(path=CONFIG_PATH):
    """读取单位配置。文件缺失或 JSON 损坏时抛 UnitConfigError。"""
    if not os.path.exists(path):
        raise UnitConfigError(
            u'单位配置文件不存在：%s\n'
            u'请从 git 恢复该文件，或运行 python config_center.py 重建。' % path)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        raise UnitConfigError(
            u'单位配置文件损坏：%s\n%s\n可从同名 .bak 备份或 git 恢复。' % (path, e))
    if not isinstance(data, dict):
        raise UnitConfigError(u'单位配置文件格式错误（顶层必须是 JSON 对象）：%s' % path)
    return data


def save_config(data, path=CONFIG_PATH):
    """写回 JSON；写前把旧文件轮换为 .bak 备份，防止保存过程出错丢数据。"""
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                old = f.read()
            with open(path + '.bak', 'w', encoding='utf-8') as f:
                f.write(old)
        except Exception:
            pass  # 备份失败不阻塞保存
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def stats_to_list(d):
    """JSON 命名字段 {hp, speed, range} -> 游戏使用的位置列表 [range, speed, hp]。

    （游戏代码约定：STATS[0]=attack_range, [1]=speed, [2]=hp）
    """
    return [d['range'], d['speed'], d['hp']]


def apply_unit_config(ns, path=CONFIG_PATH):
    """把 JSON 数据注入命名空间（settings.py 传 globals()）。返回加载的数据。"""
    data = load_config(path)
    for section in SECTIONS:
        items = data.get(section)
        if not isinstance(items, dict):
            continue
        if section == 'armor':
            # 护甲表：键=实体类名。整体注入为字典（逐键注入会与同名类冲突）
            ns['UNIT_ARMOR'] = items
            continue
        for key, val in items.items():
            if section == 'stats':
                try:
                    ns[key] = stats_to_list(val)
                except (KeyError, TypeError):
                    raise UnitConfigError(
                        u'单位配置 stats.%s 缺少 hp/speed/range 字段：%s' % (key, path))
                # 扩展字段：mine = 矿车满载采矿量（HARVESTER_STATS.mine -> settings.HARVEST_AMOUNT）
                if isinstance(val, dict) and 'mine' in val:
                    ns['HARVEST_AMOUNT'] = val['mine']
            else:
                ns[key] = val
    return data
