# Spec: 红警式采矿系统（真实矿藏 + 采集消耗 + 缓慢再生）

## 目标
1. 矿藏作为真实实体存在于地面（金色晶簇矿坑），可见、可耗尽、缓慢再生。
2. 采矿车不再凭空产钱：寻找最近的有效矿脉 → 寻路前往 → 采集使矿脉储量下降（视觉萎缩）→ 满载返家卸货变钱。
3. 多人模式：矿脉几何由 seed 确定性生成（主机/客户端一致），储量由主机权威、每帧快照同步。
4. 采矿站建成时在其周围生成一小片配套矿脉（确定性偏移，双端一致）。

## 非目标
- 不改 AI 逻辑（AI 仍经 b_type=='base' 生产步兵，矿车由 MiningRig 自动产出）。
- 不做寻路 A* 接入（沿用 Harvester 现有直线移动风格）。
- 不改竞技场（arena_active 守卫跳过矿脉生成）。

## 常量（core/settings.py 新增）
```python
ORE_PATCH_MAX_AMOUNT   = 4000   # 单个矿脉满储量
ORE_PATCH_REGEN_PER_S  = 12.0   # 每秒再生量（时间基准，防双计）
ORE_PATCH_MINE_FRAMES  = 300    # 满载一车所需帧数（对齐原 mine_duration）
HARVEST_AMOUNT         = 100    # 已有：矿车货舱容量 = 单趟收益上限
```

## 变更清单（9 处）

### 1. maps/map_data.py — OrePatch 类 + 生成
- `GameMap.__init__` / `generate()` 增加 `self.ore_patches = []`、`self.seed = seed`（generate 内保存）。
- 新增 `GameMap.generate_ore_patches()`：
  - 专用 RNG `random.Random((self.seed or 0) * 100003 + 777)`，与全局 random 状态、visual_only 无关 → 双端几何一致。
  - 矿田数 = max(3, 面积/3,500,000)；每田 3-5 个 patch（半径 60-160 散布）。
  - 合法性：地图边距 ≥200、不在 lake['rect'] 外扩 60px 内、距 bases_config 各点 ≥300px。
  - 每个矿脉初始储量 `rng.randint(2200, ORE_PATCH_MAX_AMOUNT)`。
- 新增 `class OrePatch`：
  - 字段：pos、radius=38、amount、max_amount、`_crystals`（初始化时用 patch 专属 RNG 预生成 5-8 个晶簇 offset/size，萎缩时同步缩放不跳变）、`_last_tick`。
  - `update()`：时钟差值再生 `amount = min(max, amount + dt * ORE_PATCH_REGEN_PER_S)`（双调用/帧安全）。
  - `draw(surface, offset, zoom)`：视口裁剪（沿用 buildings 的 margin 模式）；深色土坑椭圆 + 金色晶簇多边形（数量/大小 ∝ amount/max_amount）；采空仅剩淡坑。
- `GameMap.update()`（现 pass）：调用各 patch.update()。

### 2. units/vehicles.py — Harvester 状态机重写（411-505 区段）
- 新字段：`cargo=0.0`（容量=HARVEST_AMOUNT）、`ore_patch=None`；移除 findrange/mine_duration 用法。
- IDLE：每 60 帧尝试找 `amount >= 20` 的最近 patch（搜索半径 800 起步，翻倍扩到全图）；找到 → MOVING_TO_ORE，找不到原地待命。
- MOVING_TO_ORE：目标 patch 采空 → 重新选；进入 `patch.radius+12` → MINING。
- MINING：每帧转移 `min(容量/ORE_PATCH_MINE_FRAMES, patch.amount, 剩余舱位)`；`patch.amount` 同步扣减；满载或(矿空且有货) → RETURNING；矿空无货 → IDLE。
- RETURNING：到家 60px → `team_resources += int(cargo)` + FloatingText "+N"（N=实际 cargo），cargo 清零 → IDLE。
- MANUAL / home_building 失效转投 / 客户端守卫逻辑全部保留不动。

### 3. units/buildings.py — MiningRig 配套矿脉
- 新增 `MiningRig.ensure_ore_field()`：幂等（`ore_field_ready` 旗标）；围绕 self.pos 固定 3 个偏移（120°间隔、半径 150）各建一个 patch（储量 = MAX*0.75），append 到 `current_map.ore_patches`（双端同序 → 索引同步安全）。
- 调用点（3 处，旗标防重复）：`SpawnerMixin.spawn_building_instantly`、`SpawnerMixin.spawn_building_by_data`（客户端）、`Engineer` 建造完成分支（units/infantry.py）。

### 4. game/level_mixin.py — 生成挂点 + seed 修复
- `update_loading()`：generate 之后（两分支汇合处）追加：
  ```python
  if not getattr(self, 'arena_active', False) and self.current_map:
      self.current_map.generate_ore_patches()
  ```
- 单机 seed 多样化：host/single 分支 generate 前若 `self.map_seed == 0` 则随机赋值一次。
- `start_rematch()`：`self.map_seed = seed`（修复重赛两侧种子不一致，连带修复湖泊）。

### 5. game/world_mixin.py — 主机首局 seed 修复
- WAITING 分支 `seed = random.randint(...)` 后补 `self.map_seed = seed`。

### 6. game/net_mixin.py — 储量同步
- `send_snapshot()`：snapshot 增加 `"ore": [[i, int(p.amount)], ...]`（来自 current_map.ore_patches）。
- `sync_client_state()`：收到后按索引回写 `patches[idx].amount`（长度守卫）。

### 7. game/render_mixin.py — 绘制层
- `draw_world()`：湖泊层之后、建筑之前遍历绘制 `current_map.ore_patches`。

### 8. core/settings.py — 常量（见上）。

## 兼容性
- HARVESTER_STATS（units.json 注入）不动；HARVEST_AMOUNT 语义改为"货舱容量"，数值不变。
- net_mixin 旧快照无 "ore" 键 → 客户端跳过，向后兼容。
- MiningRig/AI/竞技场均不受影响。

## 验证步骤
1. `python -m py_compile` 全部改动文件。
2. mock 无头测试（D:/python3.8/python.exe）：伪造 game/current_map/team_resources/particles，跑 2000 帧：
   - 矿车自动找 patch → 移动 → MINING 期间 patch.amount 单调下降、cargo 上升；
   - 满载返家 → team_resources 增量 == cargo 取整 → 循环重启；
   - patch 采空后矿车换目标；时间推进后 amount 再生；
   - generate_ore_patches 用相同 seed 跑两次 → 几何完全一致；不同 seed → 不同。
3. grep 确认 Harvester 旧随机选点/固定 +HARVEST_AMOUNT 逻辑无残留。
