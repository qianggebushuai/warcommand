# -*- coding: utf-8 -*-
"""AI 自动游玩 JSON 指令协议：指令分类、校验与生成规则。

指令由多模态模型根据截图 + 策略文案库生成，经 validate_commands() 校验后
由 ai_autoplay.input_executor 逐条转换成真实鼠标/键盘操作。

生成规则（同时写进 VLM 的 system prompt，见 strategy.py）：
1. 只输出一个 JSON 数组，不要任何解释文字或 markdown 代码块标记。
2. 每条指令是一个对象，type 必须来自 COMMAND_TYPES。
3. 坐标是屏幕像素（截图分辨率），y 向下，原点左上角。
4. 单轮最多 MAX_COMMANDS_PER_CYCLE 条；多余的会被丢弃。
5. 先观察（mouse_move）再操作；连续点击同一坐标不超过 3 次。
6. 需要等待动画/建造时输出 {"type":"wait","ms":...}（≤3000）。
7. 遇到无法处理的情况输出 [{"type":"wait","ms":1000}]，不要瞎点。
"""
import re

# 指令分类 ------------------------------------------------------------------
# 鼠标类：move/click/down/up/drag/wheel；键盘类：key_down/key_up/key_tap/hotkey；
# 流程类：wait/stop。
COMMAND_TYPES = (
    'mouse_move', 'mouse_click', 'mouse_down', 'mouse_up', 'mouse_drag',
    'wheel', 'key_down', 'key_up', 'key_tap', 'hotkey', 'wait', 'stop',
)

MAX_COMMANDS_PER_CYCLE = 24
MAX_WAIT_MS = 3000
CLICK_BUTTONS = (1, 2, 3)          # 1=左键(选择/建造) 3=右键(移动/攻击/取消)

# 允许的键名（executor 负责映射成平台虚拟键码）
KEY_NAMES = frozenset([
    'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
    'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
    'esc', 'tab', 'space', 'enter', 'backspace', 'delete',
    'up', 'down', 'left', 'right',
    'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
    'shift', 'ctrl', 'alt',
])
MODIFIER_KEYS = frozenset(['shift', 'ctrl', 'alt'])

_MOUSE_FIELDS = {'mouse_move': ('x', 'y'), 'mouse_click': ('x', 'y'),
                 'mouse_down': ('x', 'y'), 'mouse_up': ('x', 'y')}
_KEY_FIELDS = {'key_down': ('key',), 'key_up': ('key',), 'key_tap': ('key',)}


def _norm_key(k):
    return str(k).strip().lower()


def _validate_one(cmd, screen_w, screen_h):
    """校验单条指令：返回 (规范化 dict, None) 或 (None, 错误原因)。"""
    if not isinstance(cmd, dict):
        return None, 'not an object'
    t = cmd.get('type')
    if t not in COMMAND_TYPES:
        return None, 'unknown type %r' % (t,)
    out = {'type': t}
    if t in _MOUSE_FIELDS:
        try:
            x, y = int(cmd['x']), int(cmd['y'])
        except (KeyError, TypeError, ValueError):
            return None, 'missing/invalid x,y'
        if not (0 <= x < screen_w and 0 <= y < screen_h):
            return None, 'out of screen (%d,%d)' % (x, y)
        out['x'], out['y'] = x, y
        if t in ('mouse_click', 'mouse_down', 'mouse_up'):
            btn = int(cmd.get('button', 1))
            if btn not in CLICK_BUTTONS:
                return None, 'bad button %d' % btn
            out['button'] = btn
            if t == 'mouse_click':
                out['double'] = bool(cmd.get('double', False))
    elif t == 'mouse_drag':
        try:
            fx, fy = int(cmd['from'][0]), int(cmd['from'][1])
            tx, ty = int(cmd['to'][0]), int(cmd['to'][1])
        except (KeyError, TypeError, ValueError, IndexError):
            return None, 'drag needs from[x,y] and to[x,y]'
        for x, y in ((fx, fy), (tx, ty)):
            if not (0 <= x < screen_w and 0 <= y < screen_h):
                return None, 'drag point out of screen'
        out['from'] = [fx, fy]
        out['to'] = [tx, ty]
        out['button'] = int(cmd.get('button', 1)) if int(cmd.get('button', 1)) in CLICK_BUTTONS else 1
    elif t in _KEY_FIELDS:
        k = _norm_key(cmd.get('key', ''))
        if k not in KEY_NAMES:
            return None, 'bad key %r' % (cmd.get('key'),)
        out['key'] = k
        if t == 'key_tap':
            out['count'] = max(1, min(3, int(cmd.get('count', 1))))
    elif t == 'hotkey':
        keys = cmd.get('keys')
        if not isinstance(keys, list) or not 1 <= len(keys) <= 3:
            return None, 'hotkey needs keys[1..3]'
        norm = [_norm_key(k) for k in keys]
        if any(k not in KEY_NAMES for k in norm):
            return None, 'hotkey has bad key'
        out['keys'] = norm
    elif t == 'wheel':
        try:
            out['delta'] = 1 if int(cmd.get('delta', -1)) > 0 else -1
        except (TypeError, ValueError):
            return None, 'bad wheel delta'
    elif t == 'wait':
        try:
            out['ms'] = max(50, min(MAX_WAIT_MS, int(cmd.get('ms', 500))))
        except (TypeError, ValueError):
            return None, 'bad wait ms'
    elif t == 'stop':
        pass
    return out, None


def validate_commands(raw, screen_w, screen_h, log=None):
    """校验模型输出（可能是数组/含杂质的字符串）→ 规范指令列表。

    返回 (commands, errors)。errors 非空不代表整体失败，仅记录被丢弃的条目。
    """
    if isinstance(raw, (list, tuple)):
        return _validate_list(list(raw), screen_w, screen_h, log)  # 程序内直接传规范列表
    if not isinstance(raw, str):
        return [], ['model output is neither list nor string']
    import json
    # 扫描字符串中所有可解析的 JSON 数组（容忍模型包一层说明文字/杂质），
    # 逐个校验，取有效指令最多的一组。
    dec = json.JSONDecoder()
    candidates = []
    i = 0
    while i < len(raw):
        if raw[i] == '[':
            try:
                obj, end = dec.raw_decode(raw, i)
                if isinstance(obj, list):
                    candidates.append(obj)
                    i = end
                    continue
            except ValueError:
                pass
        i += 1
    if not candidates:
        return [], ['no JSON array found in model output']
    best, best_errs = [], []
    for cand in candidates:
        cmds, errs = _validate_list(cand, screen_w, screen_h, log)
        if len(cmds) > len(best):
            best, best_errs = cmds, errs
    return best, best_errs


def _validate_list(items, screen_w, screen_h, log=None):
    cmds, errors = [], []
    for c in items[:MAX_COMMANDS_PER_CYCLE * 2]:
        if len(cmds) >= MAX_COMMANDS_PER_CYCLE:
            errors.append('cycle limit reached, dropped rest')
            break
        fixed, err = _validate_one(c, screen_w, screen_h)
        if fixed:
            cmds.append(fixed)
        else:
            errors.append(err)
            if log is not None:
                log(err)
    return cmds, errors
