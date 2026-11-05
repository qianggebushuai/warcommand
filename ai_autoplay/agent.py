# -*- coding: utf-8 -*-
"""AI 自动游玩总控（AutoPlayManager）。

循环（玩家按 F10 开启后）：
    每隔 scan_interval 秒：
        1. 截图当前画面（vision.capture_png_bytes）
        2. （record=True 时）连同地面真值标注落盘，供多模态模型微调
        3. 后台线程调用 VLM（OpenAI 兼容 /chat/completions，图像+策略上下文）
        4. 模型输出 JSON 指令数组 → protocol.validate_commands() 校验
        5. InputExecutor 逐帧回放 → 真实鼠标/键盘操作游戏
同时每帧 step 执行队列 + 绘制 HUD。游戏内按 F10 开关（controllers/input_mixin）。
"""
import base64
import json
import os
import queue
import threading
import time

import pygame

from core.utils import resource_path
from .input_executor import InputExecutor
executor_desc = InputExecutor._describe      # 类内 staticmethod，经类访问即普通函数
from .protocol import validate_commands
from . import strategy as strategy_mod
from . import vision as vision_mod

CONFIG_PATH = resource_path(os.path.join('ai_autoplay', 'config.json'))

DEFAULT_CONFIG = {
    "api_base": "https://api.openai.com/v1",     # OpenAI 兼容端点
    "model": "gpt-4o",                            # 多模态模型名（可换成微调模型）
    "decision": "vlm",                            # vlm=远程/本地API推理 | local=零API本地策略引擎
    "direct": True,                               # local 模式直接调用游戏 API（不走键鼠模拟）
    "scan_interval": 6.0,                         # 扫描周期（秒）
    "record_dataset": False,                      # 采集训练数据（截图+自动标注）
    "max_queue_cycles": 2,                        # 待执行指令最多积压几轮
    "camera_tour": True,                          # 镜头自动巡视己方/敌方领地
    "camera_tour_interval": 5.0,                  # 巡视切换间隔秒
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


class AutoPlayManager:
    def __init__(self, game):
        self.game = game
        self.enabled = False
        self.cfg = load_config()
        self.executor = InputExecutor(*pygame.display.get_surface().get_size())
        self.recorder = None
        if self.cfg.get('record_dataset'):
            self.recorder = vision_mod.DatasetRecorder()
        self.detector = vision_mod.load_detector()   # 路线 C（可选，通常 None）
        self.policy = None                           # decision=local 时的本地策略引擎
        self.direct = None                           # local+direct 时的游戏 API 直接执行器
        self.neural = None                           # decision=neural 时的模仿学习策略
        self.il_collector = None                     # 老师数据采集器（il_collect）
        self._decision = str(self.cfg.get('decision', 'vlm')).lower()
        if self._decision == 'local':
            try:
                from .local_policy import LocalPolicy
                self.policy = LocalPolicy()
                if self.cfg.get('direct', True):
                    from .direct_executor import DirectExecutor
                    self.direct = DirectExecutor(game)
                    print('[AutoPlay] 直接执行模式：动作走游戏内部 API（不模拟键鼠）')
                else:
                    print('[AutoPlay] 键鼠模拟模式：动作经 SendInput/pygame 事件注入')
                if self.cfg.get('il_collect'):
                    try:
                        from .il_dataset import ILCollector
                        self.il_collector = ILCollector()
                        print('[AutoPlay] 模仿学习采集开启：%s' %
                              self.il_collector.jsonl)
                    except Exception as e:
                        print('[AutoPlay] IL 采集器初始化失败: %s' % e)
            except Exception as e:
                print('[AutoPlay] 本地策略引擎加载失败，回退 VLM: %s' % e)
        elif self._decision == 'neural':
            try:
                from .neural_policy import NeuralPolicy
                self.neural = NeuralPolicy()
                from .direct_executor import DirectExecutor
                self.direct = DirectExecutor(game)
                print('[AutoPlay] 神经策略模式：ILNet 看图决策 + 直接执行')
            except Exception as e:
                print('[AutoPlay] ILNet 加载失败（先跑 tools/train_il.py），回退 VLM: %s' % e)
        self.status = "关闭"
        self.hud_visible = True                     # F9 切换 HUD 面板显隐（红点常显）
        self.last_feedback = None
        self._last_scan = 0.0
        self._inflight = False
        self._result_q = queue.Queue()
        self._img_q = queue.Queue(maxsize=4)
        self._threads = []
        # 人工示范录制器（F8 开关）：玩家手动操作 → 标准动作协议样本
        self.demo = None
        try:
            from .human_demo import HumanDemoRecorder
            self.demo = HumanDemoRecorder(game)
        except Exception as e:
            print('[DemoRecorder] 初始化失败: %s' % e)
        # 镜头巡视状态
        self._tour_idx = 0
        self._tour_last = 0.0
        self._tour_hold_until = 0.0
        self._tour_last_set = None

    # ---------------- 开关 ----------------
    def toggle(self):
        self.enabled = not self.enabled
        if not self.enabled:
            self.executor.clear()
            self.status = "关闭"
        else:
            self._last_scan = 0.0        # 开启后立即扫描
            self.status = "已开启"
        print('[AutoPlay] %s' % self.status)

    # ---------------- 主循环挂钩 ----------------
    def update(self):
        """每帧调用（world_mixin.update 顶部）。"""
        # 键鼠模拟模式：执行队列逐帧回放（direct 模式无队列，跳过）
        if self.direct is None and (self.enabled or self.executor.queue):
            step = self.executor.step()
            if step == 'stop':
                self.enabled = False
                self.status = "模型请求停止"
                return

        if not self.enabled or self.game.state != "PLAYING":
            if self.enabled:
                self.status = "等待对局（%s）" % self.game.state
            return

        # 人工示范录制中（F8）：AI 全程让位——镜头不巡视、决策不出手，
        # 玩家独自操作，系统只旁观记录
        demo_rec = self.demo is not None and self.demo.recording

        # 镜头自动巡视（direct/local 模式；用户手动移镜时让路）
        if self.direct is not None and self.cfg.get('camera_tour', True) \
                and not demo_rec:
            self._update_camera_tour()

        # 人工示范录制：每帧驱动（录制中每 6 秒落盘一批）
        if self.demo is not None:
            self.demo.update()
        if demo_rec:
            return

        # 处理上一轮模型回复
        try:
            raw, png_bytes = self._result_q.get_nowait()
            self._inflight = False
            self._handle_reply(raw, png_bytes)
        except queue.Empty:
            pass

        # 定时扫描
        now = time.time()
        if not self._inflight and now - self._last_scan >= float(self.cfg.get('scan_interval', 6.0)):
            self._scan()
            self._last_scan = now

    # ---------------- 扫描 → 模型 ----------------
    # ---------------- 镜头自动巡视 ----------------
    def _update_camera_tour(self):
        """在己方基地 / 中立建筑 / 敌方领地之间轮转镜头；玩家手动移镜让路 8 秒。"""
        from pygame.math import Vector2 as vec
        g = self.game
        now = time.time()
        # 玩家手动移镜检测：当前 offset 与我们上次设置差 >100px → 视为手动。
        # 触发让路时必须把基线同步到玩家镜头——否则让路期间基线陈旧，
        # 每帧都重新触发让路，导致永不恢复轮转（死循环）。
        if self._tour_last_set is not None:
            drift = (g.camera_offset - self._tour_last_set).length()
            if drift > 100:
                self._tour_hold_until = now + 8.0
                self._tour_last_set = vec(g.camera_offset)
        if now < self._tour_hold_until:
            return
        if now - self._tour_last < float(self.cfg.get('camera_tour_interval', 5.0)):
            return

        my = g.my_team
        base = next((b for b in g.all_buildings
                     if b.team == my and getattr(b, 'alive', True)), None)
        neutrals = [b for b in g.all_buildings
                    if getattr(b, 'alive', True) and b.team == 'neutral']
        enemies = [b for b in g.all_buildings
                   if getattr(b, 'alive', True)
                   and b.team not in (my, 'neutral')]
        pts = []
        if base is not None:
            pts.append((base.pos, '己方基地'))
        pts += [(b.pos, '中立%s' % b.__class__.__name__) for b in neutrals]
        pts += [(b.pos, '敌方%s' % b.__class__.__name__) for b in enemies]
        if not pts:
            return
        pos, label = pts[self._tour_idx % len(pts)]
        self._tour_idx += 1
        sw, sh = pygame.display.get_surface().get_size()
        from core.settings import WORLD_WIDTH, WORLD_HEIGHT
        g.camera_offset = vec(
            max(0, min(WORLD_WIDTH - sw / g.zoom, pos.x - sw / g.zoom / 2)),
            max(0, min(WORLD_HEIGHT - sh / g.zoom, pos.y - sh / g.zoom / 2)))
        self._tour_last_set = vec(g.camera_offset)
        self._tour_last = now

    def _scan(self):
        try:
            surface = pygame.display.get_surface()
            png_bytes = vision_mod.capture_png_bytes(surface)
        except Exception as e:
            self.status = "截图失败: %s" % e
            return

        # 训练数据采集：截图 + 地面真值自动标注
        meta = None
        if self.recorder is not None:
            try:
                labels = vision_mod.project_entities(self.game)
                n = self.recorder.save(png_bytes, labels, {
                    'frame': self.game.frame_count, 'state': self.game.state})
                meta = '已采集 %d 帧训练数据' % n
            except Exception:
                pass

        # 神经策略引擎（decision=neural）：ILNet 看图+态势直接生成动作
        if self.neural is not None:
            self.status = "ILNet 推理中…"
            try:
                acts = self.neural.decide(self.game, png_bytes)
                reason = getattr(self.neural, 'last_reason', '')
                done = self.direct.execute(acts) if self.direct is not None else []
                print('[AutoPlay] 决策: %s' % reason)
                print('[AutoPlay] 执行: %s' % (done or '无动作'))
                self.status = ('执行 %d 项: %s' % (len(done), done[0])) if done \
                    else 'ILNet 本轮无动作'
            except Exception as e:
                self.status = "ILNet 推理失败: %s" % e
            return

        # 本地策略引擎（decision=local）：零 API，同步生成指令，不进线程
        if self.policy is not None:
            self.status = "本地推理中…"
            try:
                dets = None
                if self.detector is not None:          # 检测器结果作为视觉校验
                    try:
                        dets = self.detector.detect(png_bytes)[:30]
                    except Exception:
                        dets = None
                raw = self.policy.decide(self.game, dets)
                # 模仿学习采集：老师（规则策略）的 (截图, 态势, 动作) 三元组
                if self.il_collector is not None and raw:
                    try:
                        from .il_dataset import format_situation
                        g = self.game
                        off = getattr(g, 'camera_offset', None)
                        sw, sh = pygame.display.get_surface().get_size()
                        self.il_collector.save(
                            png_bytes,
                            format_situation(g, dets), raw,
                            cam={'ox': int(off.x), 'oy': int(off.y),
                                 'zoom': round(float(getattr(g, 'zoom', 1.0)), 3),
                                 'vw': sw, 'vh': sh} if off is not None else None)
                        if self.il_collector._n % 10 == 0:
                            print('[AutoPlay][IL采集] 已存 %d 条样本 → %s'
                                  % (self.il_collector._n,
                                     self.il_collector.jsonl))
                    except Exception:
                        pass
                view = getattr(self.policy, 'last_view', '')
                if view:
                    print('[AutoPlay] 视野: %s' % view)
                if dets:
                    print('[AutoPlay] 检测 %d 个目标: %s' % (
                        len(dets), ', '.join('%s(%.2f)' % (d['class'], d['conf'])
                                             for d in dets[:8])))
                reason = getattr(self.policy, 'last_reason', '')
                # 直接执行模式：动作即刻经游戏 API 生效，不排队
                if self.direct is not None:
                    done = self.direct.execute(raw)
                    print('[AutoPlay] 决策: %s' % reason)
                    print('[AutoPlay] 执行: %s' % (done or '无动作'))
                    self.status = ('执行 %d 项: %s' % (len(done), done[0])) if done \
                        else '本轮无动作'
                else:
                    print('[AutoPlay] 决策: %s → %s' % (
                        reason or '无依据',
                        [executor_desc(c) for c in raw] or '无动作'))
                    self._handle_reply(raw, None)
            except Exception as e:
                self.status = "本地推理失败: %s" % e
            return

        b64 = base64.b64encode(png_bytes).decode('ascii')
        # 检测器路线 C：本地检测出 UI/单位框，转成文字先验一起给 LLM
        extra = meta
        if self.detector is not None:
            try:
                dets = self.detector.detect(png_bytes)[:30]
                extra = '%s\n画面检测结果: %s' % (meta or '', json.dumps(dets, ensure_ascii=False))
            except Exception:
                pass

        # 简易状态回执：资金/人口类信息若可读则带上
        feedback = self.last_feedback
        self.status = "扫描中…"
        self._inflight = True
        t = threading.Thread(target=self._request, args=(b64, feedback, extra), daemon=True)
        self._threads = [th for th in self._threads if th.is_alive()][-3:]
        self._threads.append(t)
        t.start()

    def _request(self, b64, feedback, extra):
        """后台线程：调用 OpenAI 兼容 VLM。结果（原始文本, 截图）进结果队列。"""
        png_stub = None
        try:
            messages = strategy_mod.build_messages(
                b64, *pygame.display.get_surface().get_size(),
                last_feedback=feedback, extra_state=extra)
            cfg = load_config()
            api_key = os.environ.get('AUTOPLAY_API_KEY') or cfg.get('api_key', '')
            body = json.dumps({
                'model': cfg.get('model', 'gpt-4o'),
                'messages': messages,
                'temperature': 0.2,
                'max_tokens': 1000,
            }).encode('utf-8')
            from urllib import request as urlreq
            req = urlreq.Request(
                cfg.get('api_base', 'https://api.openai.com/v1').rstrip('/') + '/chat/completions',
                data=body,
                headers={'Content-Type': 'application/json',
                         'Authorization': 'Bearer %s' % api_key})
            with urlreq.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            text = data['choices'][0]['message']['content']
            self._result_q.put((text, png_stub))
        except Exception as e:
            self._result_q.put(('__error__%s' % e, png_stub))

    def _handle_reply(self, raw, _png):
        # raw 可以是 VLM 文本（str）或本地策略生成的指令列表（list）
        if isinstance(raw, str) and raw.startswith('__error__'):
            self.status = "模型调用失败: %s" % raw[9:80]
            self.last_feedback = '上一轮调用失败'
            return
        w, h = pygame.display.get_surface().get_size()
        cmds, errors = validate_commands(raw, w, h)
        if errors:
            print('[AutoPlay] 丢弃指令: %s' % errors[:3])
        if not cmds:
            self.status = "模型未产出有效指令"
            self.last_feedback = '上一轮无有效指令'
            return
        print('[AutoPlay] 本轮 %d 条指令: %s' % (
            len(cmds), ' | '.join(executor_desc(c) for c in cmds[:8])))
        # 防积压：待执行步骤过多时丢旧轮
        if len(self.executor.queue) > 60:
            self.executor.clear()
        self.executor.push_cycle(cmds)
        self.status = "执行中 %d 步" % len(self.executor.queue)
        self.last_feedback = '上轮执行: %s' % ', '.join(
            '%s(%s)' % (c['type'], c.get('x', c.get('key', ''))) for c in cmds[:6])

    # ---------------- HUD ----------------
    def draw_hud(self, surface):
        # 录屏风格状态红点：常显（不受 F9 面板开关影响）——
        # AI 开启时红色闪烁，关闭时灰色常亮，一眼可辨
        now = time.time()
        if self.enabled:
            lit = (now % 1.0) < 0.6                 # 0.6s 亮 / 0.4s 灭
            dot_col = (255, 60, 60) if lit else (90, 30, 30)
        else:
            dot_col = (110, 110, 110)
        cx, cy = surface.get_width() - 18, 16
        pygame.draw.circle(surface, (25, 25, 25), (cx, cy), 9)
        pygame.draw.circle(surface, dot_col, (cx, cy), 7)
        if not self.hud_visible:
            return
        if not self.enabled:
            return
        from core.utils import get_font          # simhei.ttf：支持中文
        font = get_font(19)
        small = get_font(16)
        col = (120, 230, 140) if self.executor.queue else (140, 200, 240)
        # 行1：状态
        txt = font.render(
            '[AUTOPLAY %s | %s | F10 关闭]' % (self.status, time.strftime('%H:%M:%S')),
            True, col, (20, 20, 20))
        surface.blit(txt, (8, 8))
        # 行2：正在执行的动作
        if self.direct is not None:                       # 直接执行模式
            if self.direct.last_done:
                t2 = small.render('执行: %s' % ' | '.join(self.direct.last_done[:4]),
                                  True, (255, 220, 120), (20, 20, 20))
                surface.blit(t2, (8, 30))
        elif self.executor.queue:
            act = '执行: %s | 队列 %d 步' % (
                self.executor.current_desc or '…', len(self.executor.queue))
            t2 = small.render(act, True, (255, 220, 120), (20, 20, 20))
            surface.blit(t2, (8, 30))
        # 行3：策略依据/最近反馈
        reason = ''
        if self.policy is not None:
            reason = getattr(self.policy, 'last_reason', '')
        elif self.last_feedback:
            reason = self.last_feedback
        if reason:
            t3 = small.render(('策略: %s' % reason)[:110], True,
                              (170, 210, 255), (20, 20, 20))
            surface.blit(t3, (8, 52))
        # 行4：视野汇总（看到了哪些单位/建筑）
        view = getattr(self.policy, 'last_view', '') if self.policy is not None else ''
        if view:
            t35 = small.render(('视野: %s' % view)[:110], True,
                               (255, 170, 170), (20, 20, 20))
            surface.blit(t35, (8, 74))
        # 行5：最近执行历史（最多 3 条）
        hist = self.executor.executed_log[-3:]
        if hist:
            t4 = small.render(('最近: %s' % ' → '.join(hist))[:110], True,
                              (200, 200, 200), (20, 20, 20))
            surface.blit(t4, (8, 96))
