# -*- coding: utf-8 -*-
"""直接执行器：高级动作 → 游戏内部 API 直接调用，不模拟键鼠。

比 SendInput 模拟可靠（无坐标映射/焦点/标签页问题），仅用于 decision=local
的本地策略（VLM 模式只能看屏幕，仍走键鼠模拟）。

动作协议（local_policy.decide 产出）：
    {'do': 'build',   'payload': 'power_plant'}            开始建造读条
    {'do': 'place',   'payload': 'power_plant', 'world': [x, y]}   就绪建筑放置
    {'do': 'produce', 'payload': 'rifleman'}               生产单位
    {'do': 'attack',  'world': [x, y]}                     我方战斗单位进攻该点
    {'do': 'camera',  'world': [x, y]}                     相机跳转
"""
import math
import random

import pygame

from core.settings import WORLD_WIDTH, WORLD_HEIGHT

from pygame.math import Vector2 as vec

DO_DESC = {'build': '开建', 'place': '放置', 'produce': '生产',
           'attack': '进攻', 'camera': '视角', 'support': '支援',
           'apc_transport': '运兵占领'}


class DirectExecutor:
    """把高级动作直接落到 game/sidebar 内部方法上。"""

    def __init__(self, game):
        self.game = game
        self.last_done = []          # 最近一轮成功动作描述（HUD）

    # ---------------- 动作查找 ----------------
    def _find_item(self, tab, payload):
        try:
            for it in self.game.sidebar.all_items.get(tab, []):
                if it.payload == payload:
                    return it
        except Exception:
            pass
        return None

    @staticmethod
    def _find_build_spot(game, base_pos):
        """基地周围找一个不与建筑重叠、且不在湖里的落点（随机起始角防死循环）。"""
        from maps.map_data import lake_contains
        bx, by = base_pos
        lakes = list(getattr(game, 'lakes', []) or [])
        start = random.randint(0, 45)
        for i in range(8):
            ang = start + i * 45
            for r in (160, 240, 330):                     # 三档半径，密了往外扩
                x = int(bx + math.cos(math.radians(ang)) * r)
                y = int(by + math.sin(math.radians(ang)) * r)
                if not (150 < x < WORLD_WIDTH - 150 and 150 < y < WORLD_HEIGHT - 150):
                    continue
                if any(lake_contains(lk, x, y) for lk in lakes):
                    continue                                  # 湖面放不下
                ok = True
                for b in game.all_buildings:
                    if getattr(b, 'alive', True) and \
                            math.hypot(b.pos.x - x, b.pos.y - y) < 100:
                        ok = False
                        break
                if ok:
                    return [x, y]
        return None

    # ---------------- 执行 ----------------
    def execute(self, actions):
        done = []
        for a in actions or []:
            try:
                desc = self._one(a)
                if desc:
                    done.append(desc)
            except Exception as e:
                print('[Direct] 动作失败 %s: %s' % (a, e))
        self.last_done = done
        return done

    def _one(self, a):
        g = self.game
        d = a.get('do')
        if d == 'build':
            item = self._find_item('BUILD', a['payload'])
            if item is None or getattr(item, 'is_building', False) \
                    or getattr(item, 'is_ready', False):
                return None
            self.game.sidebar.execute_item(item)
            return '开建' + a['payload']

        if d == 'place':
            payload = a.get('payload')
            if payload:
                item = self._find_item('BUILD', payload)
                if item is not None and getattr(item, 'is_ready', False):
                    items = [item]
                else:
                    # payload 错配/陈旧模型：目标建筑并未就绪 →
                    # 兜底改放"全部就绪建筑"，而不是作废这轮放置
                    items = [it for it in
                             (g.sidebar.all_items.get('BUILD', []) or [])
                             if getattr(it, 'is_ready', False)]
                    if not items:
                        return None
            else:
                # 动作没带 payload（学生只输出 DO_PLACE）→ 放置全部就绪建筑。
                # 低频建筑（机场/雷达/兵营）示范太少，学生学不出 P_ 特定
                # payload；分权：学生管"何时放"，执行器管"放什么/放哪里"。
                items = [it for it in (g.sidebar.all_items.get('BUILD', []) or [])
                         if getattr(it, 'is_ready', False)]
                if not items:
                    return None
            # 基地坐标：动作没带（神经策略只输出 payload）就从游戏里找
            base = a.get('base')
            if base is None:
                bp = next((b.pos for b in g.all_buildings
                           if b.team == g.my_team and getattr(b, 'alive', True)),
                          None)
                if bp is None:
                    return None                    # 基地全毁，无处可放
                base = (bp.x, bp.y)
            n_placed = 0
            first_desc = None
            for it in items:
                world = a.get('world') if len(items) == 1 else None
                if world:
                    # 动作自带坐标（神经策略学的）：预检不合法就换自己的搜索点——
                    # handle_build_click 遇重叠/湖面会静默取消，白跑一轮
                    from maps.map_data import lake_contains
                    bad = any(lake_contains(lk, world[0], world[1])
                              for lk in (getattr(g, 'lakes', None) or []))
                    bad = bad or any(
                        getattr(b, 'alive', True) and
                        math.hypot(b.pos.x - world[0], b.pos.y - world[1]) < 90
                        for b in g.all_buildings)
                    if bad:
                        world = None
                if not world:
                    world = self._find_build_spot(g, (base[0], base[1]))
                if not world:
                    continue
                g.place_building_type = it.payload
                g.is_instant_build = True
                g.handle_build_click(vec(*world))
                n_placed += 1
                if first_desc is None:
                    first_desc = '放置%s@(%d,%d)' % (it.payload, world[0], world[1])
            if not n_placed:
                return None
            return first_desc if n_placed == 1 else \
                '%s 等x%d' % (first_desc, n_placed)

        if d == 'produce':
            item = self._find_item('UNIT', a['payload'])
            if item is None or getattr(item, 'is_building', False):
                return None
            self.game.sidebar.execute_item(item)
            return '生产' + a['payload']

        if d == 'attack':
            wx, wy = a['world']
            n = 0
            # 攻击目标实体（set_target 追着打），而不是 move_to 到位置挤压
            tgt = None
            best = 1e18
            for e in list(g.all_units) + list(g.all_buildings):
                if not getattr(e, 'alive', True):
                    continue
                if e.team == g.my_team or getattr(e, 'team', '') == 'neutral':
                    continue
                d = (e.pos.x - wx) ** 2 + (e.pos.y - wy) ** 2
                if d < best:
                    best, tgt = d, e
            for u in list(g.all_units):
                if getattr(u, 'alive', True) and u.team == g.my_team:
                    cls = u.__class__.__name__.lower()
                    if any(k in cls for k in ('harvester', 'transport',
                                              'engineer', 'mcv')):
                        continue
                    if tgt is not None and hasattr(u, 'set_target'):
                        u.set_target(tgt)
                    else:
                        u.move_to(vec(wx, wy))
                    n += 1
            return '进攻%sx%d' % (tgt.__class__.__name__ if tgt else
                                 '(%d,%d)' % (wx, wy), n) if n else None

        if d == 'defend_base':
            # 驻防：霰弹/步枪步兵在基地周围环形布点，敌人靠近则迎击。
            # 与进攻波隔离——坦克/空军走 attack，驻防兵不参与长途奔袭。
            GUARD_KEYS = ('shotgun', 'rifleman')
            guards = [u for u in g.all_units
                      if getattr(u, 'alive', True) and u.team == g.my_team
                      and any(k in u.__class__.__name__.lower()
                              for k in GUARD_KEYS)]
            if not guards:
                return None
            base_pos = None
            if getattr(g, 'player_base', None) is not None and \
                    getattr(g.player_base, 'alive', False):
                base_pos = g.player_base.pos
            else:
                for b in g.all_buildings:
                    if getattr(b, 'alive', True) and b.team == g.my_team:
                        base_pos = b.pos
                        break
            if base_pos is None:
                return None
            # 敌人进基地 500px 圈 → 驻防兵迎击（set_target 追打）
            tgt, best = None, 1e18
            for e in g.all_units:
                if not getattr(e, 'alive', True) or e.team == g.my_team:
                    continue
                dd = (e.pos - base_pos).length()
                if dd < 500 and dd < best:
                    best, tgt = dd, e
            if tgt is not None:
                n = 0
                for u in guards:
                    if hasattr(u, 'set_target'):
                        u.set_target(tgt)
                        n += 1
                return '驻防迎击%s x%d' % (tgt.__class__.__name__, n)
            # 无敌情 → 环形驻点（8 个，半径 260），步兵分散站位
            import math as _m
            n = 0
            for i, u in enumerate(guards):
                ang = _m.radians(i * 45.0)
                spot = base_pos + vec(int(260 * _m.cos(ang)),
                                      int(260 * _m.sin(ang)))
                u.move_to(spot)
                n += 1
            return '驻防%d人环形布点' % n

        if d == 'air_raid':
            # 飞艇轰炸：kirovairship set_target 敌方防御建筑（激光塔/碉堡/
            # 防空炮等），飞艇血厚由其自动飞过去投弹
            wx, wy = a['world']
            tgt, best = None, 1e18
            for e in g.all_buildings:
                if not getattr(e, 'alive', True):
                    continue
                if e.team == g.my_team or getattr(e, 'team', '') == 'neutral':
                    continue
                dd = (e.pos.x - wx) ** 2 + (e.pos.y - wy) ** 2
                if dd < best:
                    best, tgt = dd, e
            if tgt is None:
                return None
            n = 0
            for u in g.all_units:
                if getattr(u, 'alive', True) and u.team == g.my_team \
                        and 'kirov' in u.__class__.__name__.lower() \
                        and hasattr(u, 'set_target'):
                    u.set_target(tgt)
                    n += 1
            return '飞艇轰炸%sx%d' % (tgt.__class__.__name__, n) if n else None

        if d == 'support':
            # 支援技能（AC130/导弹/空降）：需要雷达覆盖，内部自扣费
            wx, wy = a['world']
            s_type = a.get('s_type', 'ac130')
            mode = {'ac130': 'call_airstrike_mode',
                    'missile': 'call_missile_mode',
                    'airdrop': 'call_airdrop_mode'}.get(s_type)
            if mode is None:
                return None
            # 雷达前置检查（handle_support_click 无雷达只弹 alert）
            has_radar = any(getattr(b, 'alive', True) and b.team == g.my_team
                            and getattr(b, 'b_type', '') == 'radar'
                            for b in g.all_buildings)
            if not has_radar:
                return None
            setattr(g, mode, True)
            g.handle_support_click(vec(wx, wy))
            setattr(g, mode, False)
            return '支援%s@(%d,%d)' % (s_type, wx, wy)

        if d == 'apc_transport':
            # 占领调度（三段状态机，状态全在游戏对象上，无本地记忆）：
            #   空载 → 双向汇合工程师 → 满载开往中立可占领建筑 → 到站卸载占领
            my = g.my_team
            apcs = [u for u in g.all_units
                    if getattr(u, 'alive', True) and u.team == my
                    and hasattr(u, 'cargo') and hasattr(u, 'capacity')
                    and 'harvester' not in u.__class__.__name__.lower()]
            # 占领目标 = 全部敌对建筑（工程师 set_target 的 capture 对任何
            # 敌对建筑生效；不再占领中立油井——见用户要求"只占敌对建筑"）
            neutrals = [b for b in g.all_buildings
                        if getattr(b, 'alive', True)
                        and b.team != my and b.team != 'neutral']
            if not apcs or not neutrals:
                return None
            engineers = [u for u in g.all_units
                         if getattr(u, 'alive', True) and u.team == my
                         and 'engineer' in u.__class__.__name__.lower()]
            n_done = 0
            moving = 0
            for apc in apcs:
                tgt = min(neutrals, key=lambda b: apc.pos.distance_to(b.pos))
                if not apc.cargo:
                    # --- 空载：只捡"尚未派遣"的工程师。判定用工程师自身的
                    #     占领行动状态（set_target 后 target_building 非空），
                    #     而非位置——位置判定会把走向目标途中的工程师误判为
                    #     已部署，导致 APC 永不装人（死锁） ---
                    cand = [e for e in engineers
                            if getattr(e, 'target_building', None) is None
                            and getattr(e, 'action_type', '') != 'capture'
                            and getattr(getattr(e, 'target_building', None),
                                        'alive', False) is not True]
                    if cand:
                        eng = min(cand, key=lambda e: apc.pos.distance_to(e.pos))
                        if apc.pos.distance_to(eng.pos) > 90:
                            apc.move_to(eng.pos)            # APC 去接
                            eng.move_to(apc.pos)            # 工程师也靠过来
                            moving += 1
                            continue
                        # 已在工程师身边：就地装车（load_units 判定半径 100）。
                        # 绝不能先开往敌建筑——那会让 APC 越过 100px 后反复折返，
                        # 永远装不上人。
                        apc.load_units()
                        moving += 1
                    else:
                        # 无未派遣工程师 → 绝不开向敌区送人头：
                        # 靠得近就撤到 250px 待命，本来就远则原地不动
                        d = apc.pos.distance_to(tgt.pos)
                        if d < 250:
                            aim = apc.pos - tgt.pos
                            if aim.length() > 0:
                                apc.move_to(tgt.pos +
                                            aim * (250.0 / aim.length()))
                else:
                    # --- 装到人就走：开往目标建筑外缘，到站卸载并撤离 ---
                    # 停点按建筑外缘计算（大建筑 120px 可能落在墙里）；
                    # 抵达判定再放宽 30px：Unit.update 距目标 25px 内就清空
                    # target_pos，APC 实际会停在 drop_r+~25 处，判定太紧会
                    # 永远"未到站"而卡死。
                    _rect = getattr(tgt, 'rect', None)
                    _half = max(getattr(tgt, 'radius', 15),
                                max(_rect.width, _rect.height) * 0.5 if _rect else 0)
                    drop_r = _half + 60
                    d_now = apc.pos.distance_to(tgt.pos)
                    # 卡住检测：跨扫描轮位置几乎不变（水域挡路 / 建筑围死 /
                    # 停点落进别的建筑里）→ 不再死等到站，就地卸人。
                    # 工程师移动不判碰撞和水域，能自己走完剩下的路。
                    same_tgt = getattr(apc, '_cap_tgt', None) is tgt
                    last = getattr(apc, '_cap_last_pos', None)
                    stalled = getattr(apc, '_cap_stalled', 0) if same_tgt else 0
                    if last is not None and same_tgt and \
                            apc.pos.distance_to(last) < 30:
                        stalled += 1
                    else:
                        stalled = 0
                    apc._cap_tgt = tgt
                    apc._cap_stalled = stalled
                    apc._cap_last_pos = vec(apc.pos)
                    if d_now > drop_r + 30 and stalled < 2:
                        aim = tgt.pos - apc.pos
                        if aim.length() > 0:
                            stop = tgt.pos - aim * (drop_r / aim.length())
                            apc.move_to(stop)
                        moving += 1
                    else:
                        apc._cap_stalled = 0
                        apc._cap_last_pos = None
                        apc.unload_units()                  # 卸下占领
                        n_done += 1
                        # 工程师的占领是专门的牺牲式指令：set_target(建筑)
                        # → 自动走到 radius+20 → team 直改 = 秒占（比进度圈快且
                        # 可靠；move_to 站圈等 180 帧是给普通单位的进度式占领）
                        for u in g.all_units:
                            if getattr(u, 'alive', True) and u.team == my \
                                    and 'engineer' in u.__class__.__name__.lower() \
                                    and u.pos.distance_to(apc.pos) < 120:
                                try:
                                    u.set_target(tgt)       # 触发 capture 行动
                                except Exception:
                                    u.move_to(tgt.pos)      # 兜底走过去
                        # APC 暂留原地，下轮空载且无未部署工程师时自动撤离待命
            if n_done:
                return '卸载工程师x%d' % n_done
            if moving:
                return '运兵调度'
            return None

        if d == 'camera':
            sw, sh = pygame.display.get_surface().get_size()
            g.camera_offset = vec(
                max(0, min(WORLD_WIDTH - sw / g.zoom, a['world'][0] - sw / g.zoom / 2)),
                max(0, min(WORLD_HEIGHT - sh / g.zoom, a['world'][1] - sh / g.zoom / 2)))
            return '视角(%d,%d)' % (a['world'][0], a['world'][1])
        return None
