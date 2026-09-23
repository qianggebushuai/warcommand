# warcommand 模块化重构计划

## Context（背景）

项目是 pygame RTS 游戏，`main.py` 4746 行（含 4400+ 行的 Game 上帝类）、`units.py` 9078 行（63 个单位/建筑类），难以维护。用户要求把代码按职责拆分到不同文件夹：panel（UI 面板）、controller（输入/摄像机）、不同的 unit、输入处理、camera 移动逻辑、网络连接逻辑等。

**核心策略**：
- Game 类用 **Mixin 拆分**——方法体逐字节剪切到不同 Mixin 文件，`self.xxx` 属性访问完全不变，行为零改动；`main.py` 变成薄入口。
- 摄像机移动代码从 `handle_input`/`update` 中**抽成独立方法**放进 CameraMixin（这是唯一需要改调用点的部分）。
- `units.py` 拆成 **units/ 包**，按兵种分文件，`__init__.py` 聚合导出保持 `from units import *` 兼容。
- 现有单文件按职责归位到各包。

## 最终目录结构

```
warcommand/
├─ main.py                  # 薄入口：class Game(所有Mixin): pass + Game().run()
├─ core/                    # 基础层（不含游戏逻辑）
│  ├─ settings.py           # ← settings.py
│  ├─ base_classes.py       # ← base_classes.py
│  ├─ dic.py factions.py
│  └─ utils.py              # 唯一 resource_path/get_font（基准目录=项目根，保留 _MEIPASS 分支）
├─ units/
│  ├─ __init__.py           # 按依赖序聚合 from .base import * → from .defenses import *
│  ├─ base.py               # Unit 基类
│  ├─ infantry.py           # Rifleman RocketTrooper Shotgunner Sniper Engineer CombatEngineer HeavyMech ScavengerWalker
│  ├─ vehicles.py           # ArmoredCar APC Harvester M1A2 HeavyTransport ShockwaveVehicle Type99 DroneCarrier TankCarrier HIMARS MCV TerminatorIFV SuicideDrone ScoutDrone ArmoredTrain TrainCarriage
│  ├─ aircraft.py           # Helicopter WZ10 AC130 KirovAirship ParatrooperPlane FighterJet AttackPlane StealthHeli Mi24
│  ├─ missiles.py           # CruiseMissile ShipMissile MegaRocket
│  ├─ ships.py              # MissileBoat LaserDestroyer AAFrigate MissileCruiser ArtilleryCruiser Battleship
│  ├─ buildings.py          # MercenaryFactory BaseBuilding FactoryBuilding RadarBuilding PowerPlant MiningRig Airfield ResearchCenter ShroudGen PrototypeGen IronCurtain NukeSilo Lighthouse Bastion
│  └─ defenses.py           # MissileDefenseSystem AntiAirTurret LaserTurret Bunker CIWS CoastalGun
├─ panels/                  # UI 面板
│  ├─ widgets.py            # 从 main.py 移出 ChatBox / BFButton / InputBox
│  ├─ ui_sidebar.py ui_login.py ui_lobby.py basesetting.py selfdefine.py warstory.py
├─ controllers/             # 控制
│  ├─ camera_mixin.py       # CameraMixin：update_camera / zoom_at / screen_to_world
│  └─ input_mixin.py        # InputMixin：handle_input handle_box_selection handle_battleship_call handle_support_click handle_build_click select_entity
├─ game/                    # Game 主类剩余职责 Mixin
│  ├─ core_mixin.py         # GameCoreMixin：__init__ load_resources reset_lobby_data reset_game play_music check_music_state load_menu_backgrounds generate_background run my_money
│  ├─ menu_mixin.py         # MenuMixin：draw_login handle_login_input draw_menu handle_menu_click draw_tutorial draw_gameover
│  ├─ level_mixin.py        # LevelMixin：init_level apply_map_data start_rematch perform_rebuild_base draw_loading update_loading has_active_base has_tech_center
│  ├─ spawner_mixin.py      # SpawnerMixin：spawn_unit spawn_unit_by_name spawn_building_instantly spawn_building_by_data upgrade_tech spawn_engineer issue_command
│  ├─ world_mixin.py        # WorldMixin：update update_game_world（内嵌摄像机段→self.update_camera()）
│  ├─ render_mixin.py       # RenderMixin：draw draw_world draw_world_elements draw_ui draw_shroud draw_building_menu draw_button show_alert
│  └─ net_mixin.py          # NetMixin：sync_client_state handle_online_playing handle_setup_packet send_snapshot handle_lobby_network broadcast_lobby_state
├─ maps/                    # __init__.py 聚合；map_data.py(←maps.py) map_gen.py environment.py
├─ ai/                      # ai_logic.py（AICommander）
├─ network/                 # manager.py(←network.py, NetworkManager) db_manager.py
└─ tools/                   # generate_sprites.py updatelog.py（独立脚本）
```

注：`selfdefine.py` 是 SkirmishUI（依赖 ui_login.BFInput），归入 panels/ 而非 core/，避免循环依赖。

## 关键实现细节

1. **Mixin 机制**：所有 `self.` 属性仅由 GameCoreMixin 的 `__init__` 创建；方法体剪切时保持逐字节不变（除摄像机段）；`main.py` 中 `class Game(GameCoreMixin, CameraMixin, InputMixin, MenuMixin, LevelMixin, SpawnerMixin, WorldMixin, RenderMixin, NetMixin): pass`。
2. **摄像机抽取**（唯一逻辑改动点）：
   - `update_camera()`：键盘平移 + 鼠标边缘滚动 + clamp（从 `update` L2449 附近和 `handle_input` 中抽出）
   - `zoom_at()`：滚轮缩放（从 `handle_input` 抽出）
   - `screen_to_world()`（main.py L765）直接移入
   - 原调用点各替换为一行调用，`camera_offset`/`zoom` 数据仍存于 self。
3. **units/ 跨类引用规则**：子模块顶层零互引（只 import core.base_classes 的 Building/Entity/vec + core.settings）；跨类实例化/isinstance 一律在使用它的方法体内延迟导入，如 `ParatrooperPlane.spawn_paratrooper` 内 `from .infantry import Rifleman, RocketTrooper`；`BaseBuilding`→MCV、`MiningRig`→Harvester、`MercenaryFactory`→ArmoredCar、ships→M1A2/ShipMissile、`Unit.__init__` 的 isinstance 分组同理。同模块内引用（ArmoredTrain/TrainCarriage、DroneCarrier/ScoutDrone）无需导入。
4. **utils 去重**：`resource_path`/`get_font` 当前在 main.py、base_classes.py、units.py、basesetting.py、dic.py、warstory.py、selfdefine.py、ui_login.py、ui_lobby.py、ui_sidebar.py、maps.py 等处有 ~11 份重复定义；统一改为 `from core.utils import resource_path, get_font`。注意基准目录改为 utils.py 上两级（项目根），否则 fonts/images 加载失效。
5. **import 全局替换**：
   - `from settings import *` → `from core.settings import *`
   - `from base_classes import *` / `from base_classes import vec,...` → `from core.base_classes import ...`
   - `from network import NetworkManager` → `from network.manager import NetworkManager`
   - `from db_manager import` → `from network.db_manager import`
   - `from ai_logic import` → `from ai.ai_logic import`
   - `from ui_sidebar/login/lobby import` → `from panels.xxx import`
   - `from maps import *`、`from units import *`、`from dic import *` → 改为 `from maps import *`、`from units import *`、`from core.dic import *`（包聚合后形式不变或加前缀）
   - `from factions import` → `from core.factions import`
6. **依赖方向（已验证无循环）**：core.settings ← core.base_classes ← units ← (maps, ai) ← game/controllers mixins ← main；panels ← core + network。唯一隐患 selfdefine→ui_login 同包解决。
7. **PyInstaller**：多个 .spec 文件以 main.py 为入口，导入链自动跟踪，一般只需确认 datas 不变；最后启动一次打包验证（可选）。

## 实施顺序（每步 git commit，可回退）

1. **快照**：`git add -A && git commit`（确保当前状态可回退）。
2. **core/utils 统一**：建 core/ 包，迁移 settings/base_classes/dic/factions，新建 utils.py，替换 11 处重复 resource_path/get_font，全局替换 import。验证：`python -c "import main"`。
3. **main.py 内抽 CameraMixin**（先不挪文件）：抽 update_camera/zoom_at，验证游戏内摄像机功能。
4. **main.py Mixin 外拆**：ChatBox/BFButton/InputBox → panels/widgets.py；Game 方法按映射表剪切到 controllers/ 与 game/；main.py 变薄入口。验证：`python -c "import main"` + 启动游戏走 登录→菜单→单机遭遇战→联机大厅 流程。
5. **units.py 拆包**：按类清单分段剪切到 units/ 子模块，`__init__.py` 聚合。验证：`python -c "import units; print(units.Rifleman, units.Battleship, units.NukeSilo, units.Harvester)"` + 游戏内测试跨类生成单位（伞兵、雇佣兵工厂、矿车、列车）。
6. **其余归位**：panels（ui_*、basesetting、selfdefine、warstory）、network、maps、ai、tools 迁移 + 全局 import 替换。验证：`python -m py_compile` 所有 .py + `python -c "import main"` + 启动游戏。
7. **收尾**：确认 all.txt（非代码备份）不参与；spec 文件检查；最终完整启动测试。

## 风险与回退

- **风险**：通配导入遗漏导出名（拆分后用 `getattr(units, cls)` 逐一比对 63 个类名）；resource_path 基准漂移导致资源加载失败（统一走 core/utils 后 grep 确认无本地定义残留）；Mixin 剪切时手误改动逻辑（剪切不复制、剪切后原文件该方法必须消失）。
- **回退**：每步一个 git commit，失败 `git reset --hard` 回上一步；全程不改任何方法逻辑（除摄像机抽取）。

## 验证方式

1. 每步：`python -m py_compile <所有.py>`、`python -c "import main"`（验证导入链）。
2. 最终：启动 `python main.py`，人工走通 登录→主菜单→单机开局→建造/造兵→摄像机移动缩放→（可选）联机大厅。
3. `python -c "import units; [print(c) for c in ['Rifleman','Battleship','NukeSilo','Harvester','KirovAirship'] if not hasattr(units,c)]"` 确认聚合导出无遗漏。
