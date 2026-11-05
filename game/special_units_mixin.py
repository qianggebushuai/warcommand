# -*- coding: utf-8 -*-
"""特殊单位刷新管理器（地图装甲列车 / 战列舰）

职责：
  1. 注册表：地图加载（init_level / apply_map_data）时按布局 JSON 的 special_units
     分区（map.special_specs）登记刷新 spec；JSON 无该分区时从地图硬编码
     initial_units 推导默认 spec（spawn=出生点，无目标点），保证 StormCoastMap
     等老地图的硬编码出生照常工作且可被刷新。
  2. 死亡定时刷新：扫描式检测（不入侵 die() 链）——每帧核对 spec 关联单位存活
     状态，死亡后等待 respawn_frames 帧在 spawn 点重建单位并下发向 target 移动
     的指令；列车重建走 ArmoredTrain 构造（spawn_carriages 自动挂 3 节车厢），
     沿固定铁轨（TRAIN_TRACK_X）行驶，move_to 取目标点 y 作为行进终点。
  3. 战列舰↔通讯站绑定：刷新（含首次注册补生成）出的战列舰自动绑定到
     linked_battleship 为空/已死的最近存活中立 CommStation（双向字段
     station.linked_battleship / battleship.linked_station），死亡时清空双向
     引用防悬空崩溃；绑定后玩家占领通讯站即可再次调用战列舰
     （handle_battleship_call），通讯站被夺/被毁时由 CommStation 现有逻辑
     将战列舰置回中立（CONTROL LOST）。

主更新链挂点：world_mixin.update_game_world（单机/主机/竞技场共用）每帧调用
SpecialUnitManager.update()；联机客户端不跑刷新逻辑（实体由网络同步）。
"""
from core.settings import SPECIAL_RESPAWN_FRAMES
from pygame.math import Vector2 as vec


class SpecialUnitManager:
    def __init__(self, game):
        self.game = game
        self.specs = []   # 运行时注册表：{type, spawn, target, respawn_frames, unit, dead_at}

    # ---------------- 注册 ----------------
    def register_from_map(self):
        """地图加载后调用：重建注册表并绑定/补生成初始单位（幂等，重开局会重跑）"""
        self.specs = []
        m = getattr(self.game, 'current_map', None)
        if m is None:
            return
        raw = getattr(m, 'special_specs', None)
        if raw is None:
            # 布局 JSON 无 special_units 分区 → 从地图硬编码 initial_units 推导默认 spec
            raw = []
            for u_type, pos in getattr(m, 'initial_units', []):
                t = {"train": "Train", "Train": "Train",
                     "Battleship": "Battleship"}.get(str(u_type))
                if t:
                    raw.append({"type": t, "spawn": vec(pos), "target": None,
                                "respawn_frames": SPECIAL_RESPAWN_FRAMES})
        for s in raw:
            t = str(s.get("type", ""))
            spec = {
                "type": t,
                "spawn": vec(s["spawn"]),
                "target": vec(s["target"]) if s.get("target") else None,
                "respawn_frames": int(s.get("respawn_frames", SPECIAL_RESPAWN_FRAMES)),
                "attack_radius": int(s["attack_radius"]) if s.get("attack_radius") else None,
                "unit": None,
                "dead_at": None,
                "last_team": None,
            }
            if spec["type"] not in ("Train", "Battleship", "AC130"):
                continue
            self.specs.append(spec)
            # 绑定关卡加载已生成的初始单位（按类名+距 spawn 600px 内就近匹配）
            u = self._find_live_unit(spec)
            if u is None:
                # spec 有但单位缺失（如布局 JSON 新增）→ 立即补生成
                u = self._spawn_unit(spec)
            self._attach(spec, u)
            if spec["type"] == "Battleship":
                self._bind_station(u)

    def _attach(self, spec, u):
        """spec 与单位实例互相挂引用；有目标点时下发移动指令"""
        spec["unit"] = u
        u.special_spec = spec
        t = spec.get("target")
        if t is not None:
            if spec["type"] == "Train":
                u.move_to(t)          # 列车沿铁轨走，目标点作为行进终点（取 y）
            elif spec["type"] != "AC130":
                u.target_pos = vec(t)  # 战列舰按常规移动机制驶向目标点
                u.ai_mode = "MOVE"
            # AC130：目标点即盘旋中心（构造时已用），无需移动指令

    def _find_live_unit(self, spec):
        """在现有单位中找未被其他 spec 认领的同类型存活单位（spawn 附近就近）"""
        from units import ArmoredTrain, Battleship, AC130
        if spec["type"] == "Train":
            want = ArmoredTrain
        elif spec["type"] == "AC130":
            want = AC130
        else:
            want = Battleship
        best = None
        best_d = 600
        anchor = spec["target"] if (spec["type"] == "AC130" and spec.get("target")) else spec["spawn"]
        for u in self.game.all_units:
            if not (isinstance(u, want) and u.alive):
                continue
            if any(s["unit"] is u for s in self.specs):
                continue
            d = u.pos.distance_to(anchor)
            if d < best_d:
                best = u
                best_d = d
        return best

    # ---------------- 每帧更新 ----------------
    def update(self):
        g = self.game
        if g.is_online and g.my_role != "HOST":
            return  # 客户端不跑刷新（实体由网络同步）
        frame = g.frame_count
        for spec in self.specs:
            u = spec["unit"]
            if u is not None and u.alive:
                # 反向引用维护：战列舰绑定的通讯站已毁 → 清引用防悬空
                if spec["type"] == "Battleship":
                    st = getattr(u, 'linked_station', None)
                    if st is not None and not st.alive:
                        u.linked_station = None
                continue
            if u is not None:
                # 扫描到死亡：记录死亡帧 + 记住生前队伍（列车重生还原队伍——
                # 构造默认中立，而 update 只在非中立时沿铁轨行驶，
                # 不还原会卡死在刷新点不动）
                spec["dead_at"] = frame
                spec["last_team"] = u.team
                spec["unit"] = None
                if spec["type"] == "Battleship":
                    st = getattr(u, 'linked_station', None)
                    if st is not None and getattr(st, 'linked_battleship', None) is u:
                        st.linked_battleship = None
                    u.linked_station = None
            if spec["dead_at"] is None:
                continue
            if frame - spec["dead_at"] >= spec["respawn_frames"]:
                spec["dead_at"] = None
                new_u = self._spawn_unit(spec)
                # 列车还原生前队伍：非中立才会沿铁轨向目标点行驶
                lt = spec.get("last_team")
                if spec["type"] == "Train" and lt and lt != "neutral":
                    new_u.change_team(lt)
                self._attach(spec, new_u)
                if spec["type"] == "Battleship":
                    self._bind_station(new_u)

    def _spawn_unit(self, spec):
        """在 spawn 点重建特殊单位并加入 all_units"""
        from units import ArmoredTrain, Battleship, AC130
        if spec["type"] == "Train":
            u = ArmoredTrain(self.game, spec["spawn"])   # 构造内 spawn_carriages 自动生成 3 节车厢
        elif spec["type"] == "AC130":
            # 编辑器放置的空中炮艇：中立单位，围绕目标点盘旋并随机炮击区域内目标（可被击落→定时重生）
            u = AC130(self.game, spec["target"] or spec["spawn"], "neutral",
                      attack_radius=spec.get("attack_radius"))
        else:
            u = Battleship(self.game, spec["spawn"])
        self.game.all_units.append(u)
        return u

    def _bind_station(self, bs):
        """战列舰绑定通讯站：linked_battleship 为空/已死的最近存活中立站（双向字段）"""
        from core.base_classes import CommStation
        if not bs.alive:
            return
        best = None
        best_d = None
        for b in self.game.all_buildings:
            if not isinstance(b, CommStation) or not b.alive:
                continue
            lb = getattr(b, 'linked_battleship', None)
            if lb is not None and getattr(lb, 'alive', False):
                continue
            d = b.pos.distance_to(bs.pos)
            if best is None or d < best_d:
                best = b
                best_d = d
        if best is not None:
            best.linked_battleship = bs
            bs.linked_station = best
