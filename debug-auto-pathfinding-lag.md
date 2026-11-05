# Debug Session: auto-pathfinding-lag

## Status: [OPEN]

## Hypotheses

1. **A*算法每帧迭代次数过多**: max_iter=1500，每次迭代要做O(n)的min()查找，n是open_set大小
2. **障碍物碰撞检测开销大**: 每个邻居节点都要用`any(obs.inflate(20,20).collidepoint...)`遍历所有建筑
3. **路径重算频率过高**: 60帧(~1秒)就重算一次，多单位同时重算导致CPU峰值
4. **单位数量多导致重复计算**: 所有单位独立计算路径，没有共享计算结果

## Instrumentation Plan

- 在A*主循环添加迭代计数和耗时日志
- 在_recalc_path添加调用频率日志
- 在_get_obstacles添加返回障碍物数量日志

## Evidence Log

```
