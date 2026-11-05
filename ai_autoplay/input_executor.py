# -*- coding: utf-8 -*-
"""JSON 指令执行器：把协议指令转换成真实鼠标/键盘操作。

主后端（Windows）：ctypes SendInput —— 真实移动光标、按下按键，
pygame.mouse.get_pos()/get_pressed() 与事件流全部为真实状态，
拖拽框选等依赖 get_pressed() 的路径同样生效。
后备后端（非 Windows / SendInput 失败）：pygame.mouse.set_pos + event.post
（覆盖点击/按键，但拖拽时 get_pressed 不翻转）。

队列按帧节拍回放：click 自动拆 down→(12帧)→up；drag 拆 down→移动插值→up；
wait 用真实毫秒。每帧由 AutoPlayManager.update() 调 step()。
"""
import ctypes
import time

import pygame

from .protocol import MODIFIER_KEYS

# 平台虚拟键码（其余字符用 VkKeyScanW 动态解析）
_VK = {
    'esc': 0x1B, 'tab': 0x09, 'space': 0x20, 'enter': 0x0D, 'backspace': 0x08,
    'delete': 0x2E, 'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
    'shift': 0x10, 'ctrl': 0x11, 'alt': 0x12,
}
for _i in range(1, 13):
    _VK['f%d' % _i] = 0x6F + _i          # F1=0x70
for _c in 'abcdefghijklmnopqrstuvwxyz':
    _VK[_c] = ord(_c.upper())
for _d in '0123456789':
    _VK[_d] = ord(_d)

_MOUSEEVENTF = {'move': 0x0001, 'leftdown': 0x0002, 'leftup': 0x0004,
                'rightdown': 0x0008, 'rightup': 0x0010, 'absmove': 0x8001}

# 点击按下/抬起之间的帧间隔（保证游戏事件循环读到 down 与 up 两个事件）
DOWN_UP_FRAMES = 12
DRAG_STEP_FRAMES = 2


class InputExecutor:
    """动作队列 + 逐帧回放。动作是已规范的协议指令 dict（内部可再拆步）。"""

    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.queue = []              # 待回放的原子步骤
        self.desc_q = []             # 与 queue 同长度：每步的人话描述（HUD 显示）
        self.current_desc = ''       # 正在执行的步骤描述
        self.executed_log = []       # 最近执行的指令摘要（HUD/调试用）
        self._wait_until = 0.0       # wait 用的真实时间闸
        self._win = None             # SendInput 可用性（None=未探测）
        self._last_cursor = None     # OS 后备：本轮指令起始光标位置

    # ---------------- OS 注入 ----------------
    class _MI(ctypes.Structure):
        _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long),
                    ('mouseData', ctypes.c_ulong), ('dwFlags', ctypes.c_ulong),
                    ('time', ctypes.c_ulong),
                    ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]

    def _send(self, kind, x=0, y=0, vk=0):
        if self._win is None:
            self._detect_win()
        if not self._win:
            return False
        ctypes = self._ctypes
        flags = _MOUSEEVENTF[kind]
        if kind in ('move', 'absmove'):
            # 绝对坐标归一化到 0..65535（主屏）
            fx = int(x * 65535 / max(1, self.screen_w - 1))
            fy = int(y * 65535 / max(1, self.screen_h - 1))
            mi = self._MI(fx, fy, 0, flags, 0, None)
        else:
            mi = self._MI(0, 0, 0, flags, 0, None)
        arr = (self._MI * 1)(mi)
        ctypes.windll.user32.SendInput(1, arr, ctypes.sizeof(self._MI))
        return True

    def _send_key(self, vk, down):
        if self._win is None:
            self._detect_win()
        if self._win:
            import ctypes
            class _KBD(ctypes.Structure):
                _fields_ = [('wVk', ctypes.c_ushort), ('wScan', ctypes.c_ushort),
                            ('dwFlags', ctypes.c_ulong), ('time', ctypes.c_ulong),
                            ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]
            class _INP(ctypes.Structure):
                class _U(ctypes.Union):
                    _fields_ = [('ki', _KBD), ('pad', ctypes.c_ubyte * 32)]
                _anonymous_ = ('u',)
                _fields_ = [('type', ctypes.c_ulong), ('u', _U)]
            inp = _INP(type=1)
            inp.ki = _KBD(vk, 0, 0 if down else 2, 0, None)
            arr = (_INP * 1)(inp)
            ctypes.windll.user32.SendInput(1, arr, ctypes.sizeof(_INP))
            return True
        # pygame 后备
        code = pygame.key.key_code_from_vk(vk) if hasattr(pygame.key, 'key_code_from_vk') else None
        if code is not None:
            pygame.event.post(pygame.event.Event(
                pygame.KEYDOWN if down else pygame.KEYUP, key=code, unicode='', mod=0))
        return True

    def _detect_win(self):
        self._win = False
        try:
            import ctypes
            if hasattr(ctypes, 'windll') and ctypes.windll.user32:
                self._ctypes = ctypes
                # SendInput 绝对坐标按【主显示器全屏】归一化，不能用 pygame 窗口尺寸
                # （窗口化时两者不同，之前用窗口尺寸导致所有点击错位 → 表现为无操作）
                self.screen_w = ctypes.windll.user32.GetSystemMetrics(0)
                self.screen_h = ctypes.windll.user32.GetSystemMetrics(1)
                self._win = True
        except Exception:
            self._win = False

    def _vk_of(self, name):
        name = str(name).lower()
        if name in _VK:
            return _VK[name]
        try:
            import ctypes
            r = ctypes.windll.user32.VkKeyScanW(ord(name[0]))
            return (r & 0xFF) if r >= 0 else 0
        except Exception:
            return 0

    def _move(self, x, y):
        if self._win is None:
            self._detect_win()
        if self._win:
            return self._send('absmove', x, y)
        pygame.mouse.set_pos((x, y))
        return True

    def _button(self, button, down):
        if self._win is None:
            self._detect_win()
        if self._win:
            kind = ('left' if button == 1 else 'right') + ('down' if down else 'up')
            return self._send(kind)
        pygame.event.post(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN if down else pygame.MOUSEBUTTONUP,
            pos=pygame.mouse.get_pos(), button=button))
        return True

    def _wheel(self, delta):
        if self._win is None:
            self._detect_win()
        if self._win:
            import ctypes
            class _MI(ctypes.Structure):
                _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long),
                            ('mouseData', ctypes.c_ulong),
                            ('dwFlags', ctypes.c_ulong), ('time', ctypes.c_ulong),
                            ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]
            mi = _MI(0, 0, 120 * delta, 0x0800, 0, None)
            arr = (_MI * 1)(mi)
            ctypes.windll.user32.SendInput(1, arr, ctypes.sizeof(_MI))
            return True
        pygame.event.post(pygame.event.Event(pygame.MOUSEWHEEL, y=delta))
        return True

    # ---------------- 指令 → 原子步骤 ----------------
    @staticmethod
    def _describe(c):
        """协议指令 → 人话描述（HUD/日志显示）。"""
        t = c['type']
        if t == 'mouse_click':
            btn = {1: '左键', 2: '中键', 3: '右键'}.get(c.get('button', 1), '左键')
            return '点击(%d,%d)%s' % (c['x'], c['y'], btn)
        if t == 'mouse_move':
            return '移动(%d,%d)' % (c['x'], c['y'])
        if t == 'mouse_down':
            return '按下(%d,%d)' % (c['x'], c['y'])
        if t == 'mouse_up':
            return '抬起(%d,%d)' % (c['x'], c['y'])
        if t == 'mouse_drag':
            return '框选(%d,%d→%d,%d)' % (c['from'][0], c['from'][1],
                                          c['to'][0], c['to'][1])
        if t == 'wheel':
            return '滚轮(%+d)' % c.get('delta', 0)
        if t in ('key_down', 'key_up', 'key_tap'):
            return {'key_down': '按下键', 'key_up': '抬起键', 'key_tap': '敲击键'}[t] + \
                   '(%s)' % c.get('key', '')
        if t == 'hotkey':
            return '组合键(%s)' % '+'.join(c.get('keys', []))
        if t == 'wait':
            return '等待(%dms)' % c.get('ms', 0)
        return t

    def push_cycle(self, commands):
        """把一轮校验后的协议指令拆成原子步骤，追加到队列尾部。"""
        for c in commands:
            desc = self._describe(c)
            t = c['type']
            if t == 'mouse_move':
                self._emit(('move', c['x'], c['y']), desc)
            elif t == 'mouse_click':
                btn = c.get('button', 1)
                self._emit(('move', c['x'], c['y']), desc)
                self._emit(('down', btn), desc)
                self._emit(('pause_frames', DOWN_UP_FRAMES), desc)
                self._emit(('up', btn), desc)
                if c.get('double'):
                    self._emit(('pause_frames', DOWN_UP_FRAMES), desc)
                    self._emit(('down', btn), desc)
                    self._emit(('pause_frames', DOWN_UP_FRAMES), desc)
                    self._emit(('up', btn), desc)
            elif t == 'mouse_down':
                self._emit(('move', c['x'], c['y']), desc)
                self._emit(('down', c.get('button', 1)), desc)
            elif t == 'mouse_up':
                self._emit(('move', c['x'], c['y']), desc)
                self._emit(('up', c.get('button', 1)), desc)
            elif t == 'mouse_drag':
                (fx, fy), (tx, ty) = c['from'], c['to']
                btn = c.get('button', 1)
                self._emit(('move', fx, fy), desc)
                self._emit(('down', btn), desc)
                steps = 8
                for i in range(1, steps + 1):
                    self._emit(('pause_frames', DRAG_STEP_FRAMES), desc)
                    self._emit(('move',
                                int(fx + (tx - fx) * i / steps),
                                int(fy + (ty - fy) * i / steps)), desc)
                self._emit(('up', btn), desc)
            elif t == 'wheel':
                self._emit(('wheel', c['delta']), desc)
            elif t == 'key_down':
                self._emit(('keydown', self._vk_of(c['key'])), desc)
            elif t == 'key_up':
                self._emit(('keyup', self._vk_of(c['key'])), desc)
            elif t == 'key_tap':
                for _ in range(c.get('count', 1)):
                    self._emit(('keydown', self._vk_of(c['key'])), desc)
                    self._emit(('pause_frames', 3), desc)
                    self._emit(('keyup', self._vk_of(c['key'])), desc)
            elif t == 'hotkey':
                mods = [k for k in c['keys'] if k in MODIFIER_KEYS]
                mains = [k for k in c['keys'] if k not in MODIFIER_KEYS]
                for m in mods:
                    self._emit(('keydown', self._vk_of(m)), desc)
                for m in mains:
                    self._emit(('keydown', self._vk_of(m)), desc)
                    self._emit(('pause_frames', 3), desc)
                    self._emit(('keyup', self._vk_of(m)), desc)
                for m in reversed(mods):
                    self._emit(('keyup', self._vk_of(m)), desc)
            elif t == 'wait':
                self._emit(('pause_ms', c['ms']), desc)
            elif t == 'stop':
                self._emit(('stop',), desc)
            self.executed_log.append(desc)
            del self.executed_log[:-30]

    def _emit(self, step, desc):
        self.queue.append(step)
        self.desc_q.append(desc)

    def clear(self):
        self.queue = []
        self.desc_q = []

    # ---------------- 逐帧回放 ----------------
    def step(self):
        """每帧调用：执行到下一个时间闸为止的步骤。返回 True 表示还有步骤在排队。"""
        if not self.queue:
            self.current_desc = ''
            return False
        if time.time() < self._wait_until:
            return True
        while self.queue:
            s = self.queue[0]
            kind = s[0]
            if kind == 'pause_frames':
                # 递减中的步骤不弹队列，描述也不动（正在执行的描述保持）
                self.queue[0] = ('pause_frames', s[1] - 1)
                if not self.desc_q and self.queue:
                    self.desc_q.insert(0, self.current_desc)
                self.current_desc = self.desc_q[0] if self.desc_q else self.current_desc
                if s[1] - 1 <= 0:
                    self.queue.pop(0)
                    if self.desc_q:
                        self.desc_q.pop(0)
                return True
            if self.desc_q:
                self.current_desc = self.desc_q.pop(0)
            if kind == 'move':
                self._move(s[1], s[2])
            elif kind == 'down':
                self._button(s[1], True)
            elif kind == 'up':
                self._button(s[1], False)
            elif kind == 'keydown':
                self._send_key(s[1], True)
            elif kind == 'keyup':
                self._send_key(s[1], False)
            elif kind == 'wheel':
                self._wheel(s[1])
            elif kind == 'pause_ms':
                self._wait_until = time.time() + s[1] / 1000.0
                self.queue.pop(0)
                return True
            elif kind == 'stop':
                self.queue = []
                self.desc_q = []
                return 'stop'
            self.queue.pop(0)
        return False
