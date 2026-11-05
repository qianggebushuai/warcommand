import sys

# --- Windows DPI 感知（必须在 pygame.display.init / 任何窗口创建之前）---
# 未启用时系统返回"虚拟化分辨率"（物理 / 缩放系数，如 125% 下 1920x1080 -> 1536x864）：
# 全屏 surface 比物理屏幕小（右边/下面露出空白），窗口又被系统放大回去（窗口化看不出效果）。
if sys.platform == 'win32':
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()  # 旧系统兜底
    except Exception:
        pass

import pygame

# 逻辑分辨率 = 当前桌面（物理）分辨率：全屏 SCALED 时 1:1 铺满无黑边；
# 窗口模式由 SCALED 把该逻辑分辨率缩放进 80% 大小的窗口，UI 不受影响。
# 桌面信息不可用时（无头模式）回退 1920x1080。
pygame.display.init()
_desktop = pygame.display.Info()
SCREEN_WIDTH = _desktop.current_w if _desktop.current_w > 0 else 1920
SCREEN_HEIGHT = _desktop.current_h if _desktop.current_h > 0 else 1080
FPS = 60
# 世界层渲染分辨率比例：0.75=性能档（世界按 75% 渲染再放大回画布，UI 保持全分辨率）；
# 1.0=关闭。地形/单位/特效等填充型开销随面积平方下降，实体逻辑开销不受影响
WORLD_SCALE = 0.75
WORLD_WIDTH = 4800
WORLD_HEIGHT = 3200
# 单位空间网格边长（世界像素）：供分离力/碾压判定做邻域查询，替代全场景扫描
GRID_CELL = 96

# 颜色
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 50, 50)
BLUE = (50, 100, 255)
MARKER_BLUE = (0, 191, 255)
GREEN_HAT = (34, 139, 34)
YELLOW = (255, 215, 0)
GRAY = (100, 100, 100)
DARK_GRAY = (50, 50, 50)
GRASS_COLOR = (34, 100, 34)
GRASS_DETAIL = (40, 110, 40)
ORANGE = (255, 165, 0)
CYAN = (0, 255, 255)
UI_BG = (30, 30, 30, 200)
MENU_BG_COLOR = (20, 25, 20)
NEUTRAL_COLOR = (200, 200, 200)
PURPLE = (128, 0, 128)
# ... (保留数值配置) ..

CMD_EXP_RATE = 1.0

ENGINEER_SPEED = 2.5

DIFFICULTY_SETTINGS = {
    "EASY": 0.8,
    "NORMAL": 1.5,
    "HARD": 3.0
}

# 视野半径
VIEW_RADIUS = {"base": 500, "radar": 800, "unit": 250, "air": 400}

MAX_ENGINEERS = 2 # 工程师上限

# 激光舰
LASER_DMG_BASE = 0.5
LASER_DMG_MAX = 5
LASER_RAMP_UP = 120
LASER_LEVELS = 3

SHOCK_COOLDOWN = 600
SHOCK_RANGE = 250
SHOCK_FORCE = 15

# AC130 空中炮艇（units.json damage 分区同名键在 apply_unit_config 时覆盖，配置中心"伤害"页可改）
AC130_ORBIT_RADIUS = 400
AC130_DURATION = 900
AC130_ATTACK_RADIUS = 350       # 攻击半径（编辑器 AC130 特殊单位可改）；盘旋半径 = 2×攻击半径
AC130_HOWITZER_COOLDOWN = 240   # 榴弹炮发射间隔（帧）
DMG_AC130_HOWITZER = 200         # 榴弹炮单发伤害（大面积溅射）
AC130_HOWITZER_AOE = 110        # 榴弹炮溅射半径
BULLET_SPEED = 12
ROCKET_SPEED = 8
HARVEST_AMOUNT = 100  # 代码默认值：config/units.json stats.HARVESTER_STATS.mine 可覆盖（配置中心属性页"采矿"列）
# --- 红警式矿脉系统 ---
# 参数须与采集速率平衡：单车消耗 = HARVEST_AMOUNT/ORE_PATCH_MINE_FRAMES*60 ≈ 20/秒。
# 曾被改成 1000/3.0（消耗 20/s >> 再生 3/s）→ 矿脉约 1 分钟被采干，矿车全部
# 停在矿区等矿回血，表现为"第一次采矿后就停，动一下才继续"（2026-10-19 用户反馈）
ORE_PATCH_MAX_AMOUNT = 1000    # 单个矿脉满储量（spec 设计值）
ORE_PATCH_REGEN_PER_S = 2.0   # 每秒再生量（时间基准，防每帧双计）
ORE_PATCH_MINE_FRAMES = 300    # 满载一车所需帧数
MISSILE_DEFENSE_RANGE = 400

OIL_DERRICK_INCOME = 0.5
OIL_CAPTURE_TIME = 180
MERC_FACTORY_INTERVAL = 200

AI_WAVE_SIZE = 6
AI_BUILD_INTERVAL = 300
AI_INCOME_RATE = 1.5

BOMBARDMENT_INTERVAL = 1
BOMBARDMENT_DAMAGE = 100

REFUND_RATE = 0.5

TERMINATOR_HP_P2 = 400  # TerminatorIFV 阶段2血量阈值（行为参数，非初始血量；初始血量在 units.json TERMINATOR_STATS）

FIRE_ZONE_DURATION = 180

BOMB_RELOAD_TIME = 600 # 10秒补给

AMMO_CAPACITY = 30
AMMO_RELOAD_TIME = 300
ORBIT_RADIUS = 450

SCAVENGER_REWARD = 2000

# 2. EMP 发生器
EMP_COOLDOWN = 1800 # 30秒冷却
EMP_DURATION = 300  # 5秒瘫痪
EMP_RANGE = 1200    # 作用范围
# ... (其他配置) ...

# --- 电力系统 ---
INITIAL_POWER_CAP = 300
POWER_PLANT_CAP_BONUS = 300
# POWER_PLANT_HP / TECH_CENTER_HP 已迁移到 config/units.json buildings 分区（配置中心可编辑）

# --- 巨型电磁塔（TeslaTower）代码默认值：config/units.json buildings 分区可覆盖 ---
# 约定：新增单位/建筑的可调数值一律在此定义默认常量并在代码中引用，
# units.json 同名键会在 settings 末尾 apply_unit_config 时覆盖（配置中心可改）
TESLA_TOWER_HP = 900
TESLA_TOWER_CAPTURE_RADIUS = 130   # 占领触发半径
TESLA_TOWER_CAPTURE_TIME = 180     # 占领所需进度帧数
TESLA_TOWER_ATTACK_RANGE = 450     # 电击范围（中心距+目标半径判定）
TESLA_TOWER_ATTACK_INTERVAL = 120  # 放电间隔帧数
TESLA_TOWER_BASE_DAMAGE = 120      # 单轮总伤害（按目标数均分）
TESLA_TOWER_MAX_TARGETS = 6        # 单轮最多目标数
TESLA_TOWER_ZAP_DURATION = 12   # 闪电特效持续帧数
TESLA_TOWER_POWER_USAGE = 300   # 占领后的电网消耗

# --- AI 出兵规模（代码默认值）：config/units.json ai 分区可覆盖 ---
# 设计意图（经济换军力）：AI 不再无限爆兵吃光经济——基础部队额度固定，
# 矿车越多经济越强、可养部队越多，迫使 AI 把资金优先投入扩经济而非全砸军力
AI_UNIT_CAP_BASE = 16             # AI 基础战斗单位上限（不含矿车/工程师等辅助单位）
AI_UNIT_CAP_PER_HARVESTER = 8     # AI 每辆己方矿车增加的战斗单位上限
AI_HARVESTER_TARGET = 4           # AI 矿车目标数量：低于此数时优先补矿车（经济自平衡，
                                  # 绕过部队上限——矿车是收入来源不是战斗单位）

# --- 地图特殊单位（装甲列车/战列舰）代码默认值：config/units.json buildings 分区可覆盖 ---
# 约定同上：代码引用常量，units.json 同名键在 apply_unit_config 时覆盖（配置中心可改）
TRAIN_REGEN = 10              # 列车（车头/每节车厢）每个回血周期恢复的 HP
BATTLESHIP_REGEN = 15         # 战列舰每个回血周期恢复的 HP
SPECIAL_REGEN_INTERVAL = 60   # 回血周期（帧），60 帧 ≈ 1 秒
SPECIAL_RESPAWN_FRAMES = 3600 # 特殊单位死亡后的刷新等待帧数（默认 3600 帧 = 60 秒）

# --- 建筑血量（代码默认值）：config/units.json buildings 分区可覆盖 ---
# 约定同上：代码引用常量，units.json 同名键在 apply_unit_config 时覆盖（配置中心可改）
BASE_HP = 5000                # 主基地
MERCENARY_FACTORY_HP = 1500   # 佣兵工厂
FACTORY_HP = 800              # 战车工厂
BARRACKS_HP = 1000            # 兵营
RADAR_HP = 500                # 雷达站
MINING_RIG_HP = 600           # 采矿平台
AIRFIELD_HP = 700             # 机场
RESEARCH_CENTER_HP = 600      # 研究中心
SHROUD_GEN_HP = 1000          # 黑幕发生器
PROTOTYPE_GEN_HP = 2000       # 原型机发生器
IRON_CURTAIN_HP = 1000        # 铁幕装置（子建筑）
LIGHTHOUSE_HP = 1000          # 灯塔（中立）
BASTION_HP = 5000             # 堡垒（中立）

TEAM_COLORS = {
    "team_0": (0, 100, 255),   # 蓝色
    "team_1":(200, 50, 50),   # 红色
    "team_2":  (50, 200, 50),   # 绿色
    "team_3": (200, 200, 50),  # 黄色
    "team_4": (200, 0, 255),   # 紫色
    "neutral": (128, 128, 128),# 中立灰
    "enemy": (200, 50, 50),    # 红
    "player": (0, 100, 255)    # 蓝
}

# --- 单位数据（造价/属性/伤害/建造时间/护甲）已迁移到 config/units.json ---
# 由配置中心 python config_center.py 可视化增删改；此处加载注入模块命名空间，
# 对所有 from core.settings import * 的代码透明。
UNIT_ARMOR = {}  # 类名->护甲（units.json armor 分区缺省时兜底，apply_unit_config 会覆盖）
from core.unit_config import apply_unit_config as _apply_unit_config
_apply_unit_config(globals())
