# Tasks: 红警式采矿系统

- [x] T1 core/settings.py：新增 ORE_PATCH_MAX_AMOUNT / ORE_PATCH_REGEN_PER_S / ORE_PATCH_MINE_FRAMES 常量
- [x] T2 maps/map_data.py：GameMap 保存 seed + ore_patches 初始化 + generate_ore_patches()（确定性 RNG）+ update() 驱动再生
- [x] T3 maps/map_data.py：OrePatch 类（储量/再生/晶簇预生成/萎缩绘制/视口裁剪）
- [x] T4 units/vehicles.py：Harvester 状态机重写（找矿→移动→采集扣减→满载返家卸货）
- [x] T5 units/buildings.py + spawner_mixin.py + infantry.py：MiningRig.ensure_ore_field() 幂等矿脉 + 三处生成点接入
- [x] T6 level_mixin.py：update_loading 生成挂点（arena 守卫）+ 单机 seed 随机化 + start_rematch map_seed 修复
- [x] T7 world_mixin.py：主机 WAITING 分支保存 map_seed
- [x] T8 net_mixin.py：snapshot "ore" 储量同步 + sync_client_state 回写
- [x] T9 render_mixin.py：draw_world 矿脉绘制层（湖泊后、建筑前）
- [x] T10 验证：py_compile + mock 无头状态机测试（采集扣减/卸货收益/换目标/再生/seed 一致性）— 18/18 通过
