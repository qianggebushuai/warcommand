# -*- coding: utf-8 -*-
"""人工示范录制器（F8 开关）：玩家手动游玩，系统每 6 秒落盘一批示范样本。

捕获方式 = 包装游戏内部方法（零侵入，不改变原行为）：
    sidebar.execute_item     → 侧栏点击 → build/produce
    game.handle_build_click  → 建筑放置 → place（技能类 → support）
    game.handle_support_click→ 支援技能 → support（ac130/missile/airdrop）
    右键指挥（input_mixin 钩）→ 点敌 → attack / 点地 → move
    标签页切换/镜头移动      → update() 里对比状态变化 → tab/camera
每批样本 = 截图 + 态势(format_situation) + 本周期动作集合 + 相机状态，
与老师采集样本完全同格式（dataset/il/human/），可直接混入模仿学习训练：
    python tools/train_il.py --data dataset/il/human --init dataset/il
"""
import json
import os
import threading
import time

import pygame

from .il_dataset import ILCollector, format_situation

# place_building_type 里属于技能（支援）而非建筑的值
_SKILL_TYPES = ('skill_iron_curtain', 'skill_nuke', 'cruiser_missile')

# 标签页属性探测（不同版本 sidebar 页面字段名不同，逐个尝试）
_TAB_ATTRS = ('current_page', 'active_page', 'current_tab', 'cur_page', 'page')


class HumanDemoRecorder:
    """把玩家的手动操作翻译成标准动作协议并周期性落盘。"""

    def __init__(self, game, dump_interval=6.0):
        self.game = game
        self.dump_interval = float(dump_interval)
        self.recording = False
        self.acts = []                    # 本周期累积动作
        self._last_dump = 0.0
        self._last_cam = None
        self._last_tab = None
        self._lock = threading.Lock()
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'dataset', 'il', 'human')
        self.collector = ILCollector(base_dir=base)
        self.jsonl = self.collector.jsonl
        self._install_hooks()

    # ---------------- 钩子安装（包装原方法，行为不变） ----------------
    def _install_hooks(self):
        g = self.game
        # 1) 侧栏按钮点击（建造/生产）
        sb = getattr(g, 'sidebar', None)
        if sb is not None and hasattr(sb, 'execute_item'):
            orig_item = sb.execute_item

            def wrapped_item(item, _orig=orig_item):
                if self.recording and item is not None:
                    payload = getattr(item, 'payload', '')
                    is_b = getattr(item, 'is_building', False) or \
                        any(getattr(it, 'payload', '') == payload
                            for it in (sb.all_items or {}).get('BUILD', []))
                    self.acts.append({'do': 'build' if is_b else 'produce',
                                      'payload': payload})
                return _orig(item)

            sb.execute_item = wrapped_item
        # 2) 建筑/技能放置点击
        if hasattr(g, 'handle_build_click'):
            orig_bc = g.handle_build_click

            def wrapped_bc(pos, _orig=orig_bc):
                t = getattr(g, 'place_building_type', None)
                if self.recording and t and pos is not None:
                    w = [int(pos.x), int(pos.y)]
                    if t in _SKILL_TYPES:
                        self.acts.append({'do': 'support', 'payload': t,
                                          'world': w})
                    else:
                        self.acts.append({'do': 'place', 'payload': t,
                                          'world': w})
                return _orig(pos)

            g.handle_build_click = wrapped_bc
        # 3) 支援技能（AC130/巡航导弹/空投）
        if hasattr(g, 'handle_support_click'):
            orig_sc = g.handle_support_click

            def wrapped_sc(pos, _orig=orig_sc):
                if self.recording and pos is not None:
                    st = 'ac130'
                    if getattr(g, 'call_missile_mode', False):
                        st = 'missile'
                    elif getattr(g, 'call_airdrop_mode', False):
                        st = 'airdrop'
                    self.acts.append({'do': 'support', 'payload': st,
                                      'world': [int(pos.x), int(pos.y)]})
                return _orig(pos)

            g.handle_support_click = wrapped_sc

    # ---------------- 玩家操作入口 ----------------
    def on_right_click(self, world_pos, clicked_entity, my_team):
        """右键指挥单位（由 input_mixin 在单位指挥分派处调用）。
        点敌方实体 → attack；点空地 → move；点己方目标不记录。"""
        if not self.recording or world_pos is None:
            return
        w = [int(world_pos.x), int(world_pos.y)]
        team = getattr(clicked_entity, 'team', None)
        if clicked_entity is not None and team and team != my_team \
                and team != 'neutral':
            self.acts.append({'do': 'attack', 'world': w})
        elif clicked_entity is None:
            self.acts.append({'do': 'move', 'world': w})

    # ---------------- 开关 ----------------
    def toggle(self):
        self.recording = not self.recording
        if self.recording:
            self._last_dump = time.time()
            self._last_cam = None
            self._last_tab = self._cur_tab()
        print('[DemoRecorder] %s（每 %ds 落盘一批）' %
              ('开始录制' if self.recording else '停止', self.dump_interval))

    # ---------------- 每帧驱动 ----------------
    def update(self):
        g = self.game
        if not self.recording or g.state != 'PLAYING':
            return
        now = time.time()
        # 镜头移动 >120px → camera 动作（学习"玩家什么时候切视角"）
        cam_c = self._cam_center()
        if self._last_cam is not None and cam_c is not None:
            dx = cam_c[0] - self._last_cam[0]
            dy = cam_c[1] - self._last_cam[1]
            if dx * dx + dy * dy > 120 * 120:
                self.acts.append({'do': 'camera', 'world': [int(cam_c[0]),
                                                            int(cam_c[1])]})
                self._last_cam = cam_c
        elif cam_c is not None:
            self._last_cam = cam_c
        # 标签页切换 → tab 动作
        tab = self._cur_tab()
        if tab is not None and self._last_tab is not None and tab != self._last_tab:
            self.acts.append({'do': 'tab', 'payload': tab})
        self._last_tab = tab
        # 周期落盘
        if self.acts and now - self._last_dump >= self.dump_interval:
            self._dump()

    # ---------------- 内部 ----------------
    def _cam_center(self):
        try:
            sw, sh = pygame.display.get_surface().get_size()
            z = getattr(self.game, 'zoom', 1.0) or 1.0
            o = self.game.camera_offset
            return (o.x + sw / z / 2, o.y + sh / z / 2)
        except Exception:
            return None

    def _cur_tab(self):
        sb = getattr(self.game, 'sidebar', None)
        for a in _TAB_ATTRS:
            v = getattr(sb, a, None)
            if isinstance(v, str) and v:
                return v
        return None

    def _dump(self):
        try:
            surface = pygame.display.get_surface()
            png = None
            try:
                from . import vision as vision_mod
                png = vision_mod.capture_png_bytes(surface)
            except Exception:
                pass
            if png is None:
                return
            sit = format_situation(self.game)
            cam = None
            try:
                z = getattr(self.game, 'zoom', 1.0) or 1.0
                o = self.game.camera_offset
                sw, sh = pygame.display.get_surface().get_size()
                cam = {'ox': int(o.x), 'oy': int(o.y), 'zoom': round(float(z), 3),
                       'vw': sw, 'vh': sh}
            except Exception:
                pass
            with self._lock:
                acts = self.acts[:]
                self.acts = []
            if not acts:
                self._last_dump = time.time()
                return
            ok = self.collector.save(png, sit, acts, cam)
            n = self.collector._count()
            print('[DemoRecorder] 落盘%s（累计 %d 条，本批 %d 动作: %s）' %
                  ('成功' if ok else '跳过', n, len(acts),
                   '/'.join(sorted({a['do'] for a in acts}))))
        except Exception as e:
            print('[DemoRecorder] 落盘失败: %s' % e)
        finally:
            self._last_dump = time.time()
