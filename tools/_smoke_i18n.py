# -*- coding: utf-8 -*-
"""i18n 中英双语系统冒烟测试（无头）。

覆盖：
1. 文本表完整性：所有键 zh/en 两份齐全
2. tr() 双语言取值 + 格式化 + 缺键回退
3. tr_name/tr_desc/tr_tab/tr_mode 语言切换行为
4. 语言持久化：set_language 写盘 + 重新加载读取 + 还原
5. 侧栏 SidebarItem 显示名按语言翻译（原文保持英文键）
6. 全模块导入无 NameError/ImportError
"""
import os
import sys
import json
import importlib

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG_PATH = os.path.join(PROJ, 'config', 'lang.json')

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


# ---- 1. 文本表完整性 + 2. tr 行为 ----
from core import i18n

missing = [k for k, v in i18n.STRINGS.items()
           if not isinstance(v, dict) or "zh" not in v or "en" not in v
           or not v["zh"] or not v["en"]]
check("文本表 zh/en 两份齐全", not missing, f"缺失键: {missing[:5]}")

i18n.set_language("zh", save=False)
check("tr 中文默认", i18n.tr("menu.title") == "单人游戏", i18n.tr("menu.title"))
i18n.set_language("en", save=False)
check("tr 英文切换", i18n.tr("menu.title") == "SINGLE PLAYER", i18n.tr("menu.title"))
check("tr 格式化", i18n.tr("menu.funds", n=123) == "Funds: 123", i18n.tr("menu.funds", n=123))
check("tr 缺键回退", i18n.tr("no.such.key") == "no.such.key")
check("tr 坏参数不崩", i18n.tr("menu.funds", bad_kw=1) in ("Funds: {n}", "Funds: {n}"))

# ---- 3. 覆盖表 ----
i18n.set_language("zh", save=False)
check("tr_name 中文", i18n.tr_name("Factory") == "工厂", i18n.tr_name("Factory"))
check("tr_name 缺失回退", i18n.tr_name("M1A2") == "M1A2")
check("tr_desc 中文", i18n.tr_desc("Provides Power") == "提供电力")
i18n.set_language("en", save=False)
check("tr_name 英文回退原文", i18n.tr_name("Factory") == "Factory")
check("tr_tab 英文", i18n.tr_tab("BUILD") == ("BUILD", "Construct Buildings"))
i18n.set_language("zh", save=False)
check("tr_tab 中文", i18n.tr_tab("BUILD") == ("建造", "建造建筑"))
check("tr_mode 中文", i18n.tr_mode("bombard") == "轰炸")
i18n.set_language("en", save=False)
check("tr_mode 英文大写", i18n.tr_mode("bombard") == "BOMBARD")

# ---- 4. 持久化 ----
_bak = None
if os.path.exists(LANG_PATH):
    with open(LANG_PATH, 'r', encoding='utf-8') as f:
        _bak = f.read()
i18n.set_language("en", save=True)
check("set_language 写盘", os.path.exists(LANG_PATH)
      and json.load(open(LANG_PATH, encoding='utf-8')).get("language") == "en")
importlib.reload(i18n)
check("重载后读取持久化语言", i18n.get_language() == "en", i18n.get_language())
i18n.set_language("zh", save=True)
importlib.reload(i18n)
check("还原 zh 后重载生效", i18n.get_language() == "zh")
if _bak is not None:
    with open(LANG_PATH, 'w', encoding='utf-8') as f:
        f.write(_bak)
elif os.path.exists(LANG_PATH):
    os.remove(LANG_PATH)

# ---- 5. SidebarItem 显示名 ----
import pygame
pygame.init()
pygame.display.set_mode((320, 240))
from panels.ui_sidebar import SidebarItem
item = SidebarItem("Power", 300, "BUILD", "power_plant", "base", desc="Provides Power")
check("SidebarItem 存原文", item.name == "Power" and item.description == "Provides Power")
check("SidebarItem 显示经 tr_name", i18n.tr_name(item.name) == "电站")
check("SidebarItem 描述经 tr_desc", i18n.tr_desc(item.description) == "提供电力")

# ---- 6. 全模块导入 ----
try:
    import panels.basesetting  # noqa
    import panels.ui_login     # noqa
    import panels.ui_lobby     # noqa
    import panels.selfdefine   # noqa
    import panels.widgets      # noqa
    import panels.warstory     # noqa
    import panels.updatelog    # noqa
    check("panels 全模块导入", True)
except Exception as e:
    check("panels 全模块导入", False, repr(e))

try:
    import game.menu_mixin    # noqa
    import game.render_mixin  # noqa
    import game.arena_mixin   # noqa
    import game.level_mixin   # noqa
    import game.spawner_mixin # noqa
    check("game mixins 全模块导入", True)
except Exception as e:
    check("game mixins 全模块导入", False, repr(e))

# i18n 表 vs 侧栏条目核对：列出未翻译的条目名（仅提示，不算失败）
untranslated = [n for n in ("Power", "Factory", "Airfield", "Radar", "Shipyard",
                            "Barracks", "Battleship") if n not in i18n.ITEM_NAMES]
check("抽查侧栏覆盖表", not untranslated, untranslated)

print(f"\n结果: {PASS} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
