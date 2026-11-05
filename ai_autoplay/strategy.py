# -*- coding: utf-8 -*-
"""策略文案库加载与 VLM prompt 组装。

上下文 = JSON 指令生成规则（protocol.py）+ UI 地标先验 + 策略文档
（strategy/*.md，可随时增删）+ 上轮指令执行回执（让模型知道上轮做了什么）。
"""
import os

from core.utils import resource_path
from . import protocol

_STRATEGY_DIR = None


def _strategy_dir():
    global _STRATEGY_DIR
    if _STRATEGY_DIR is None:
        _STRATEGY_DIR = resource_path(os.path.join('ai_autoplay', 'strategy'))
    return _STRATEGY_DIR


def load_strategy_docs():
    """读取 strategy/ 下全部 .md 文案（文件名即主题标签）。"""
    docs = {}
    d = _strategy_dir()
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith('.md'):
                try:
                    with open(os.path.join(d, fn), encoding='utf-8') as f:
                        docs[fn[:-3]] = f.read()
                except Exception:
                    pass
    return docs


def generation_rules_text():
    """把 protocol.py 的生成规则渲染成给模型的文字。"""
    return '%s\n可用指令类型：%s' % (
        protocol.__doc__.split('"""')[0].strip(),
        ', '.join(protocol.COMMAND_TYPES))


def build_messages(png_b64, screen_w, screen_h, last_feedback=None, extra_state=None):
    """组装 VLM chat messages。png_b64 为截图 base64（PNG）。"""
    lm = protocol.__doc__ or ''
    docs = load_strategy_docs()
    landmark_txt = '\n'.join(
        '- %s: (x=%d, y=%d, w=%d, h=%d)' % (k, v[0], v[1], v[2], v[3])
        for k, v in ui_landmark_rects(screen_w, screen_h).items())

    system = (
        '你是即时战略游戏《WarCommander》的自动游玩大脑。'
        '用户消息里附带当前游戏画面截图。你的任务是观察画面、结合策略知识库，'
        '输出这一轮要执行的操作指令。\n\n'
        '== JSON 指令生成规则 ==\n' + lm.strip() + '\n\n'
        '== 固定 UI 区域（屏幕像素）==\n' + landmark_txt + '\n\n'
        '== 策略知识库 ==\n'
    )
    for name, txt in docs.items():
        system += '\n### %s ###\n%s\n' % (name, txt)

    user_parts = ['当前截图如上。请输出本轮 JSON 指令数组。']
    if last_feedback:
        user_parts.append('上一轮指令执行情况：%s' % last_feedback)
    if extra_state:
        user_parts.append('补充状态：%s' % extra_state)

    return [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': [
            {'type': 'text', 'text': '\n'.join(user_parts)},
            {'type': 'image_url', 'image_url': {
                'url': 'data:image/png;base64,%s' % png_b64}},
        ]},
    ]


def ui_landmark_rects(screen_w, screen_h):
    from .vision import ui_landmarks
    return ui_landmarks(screen_w, screen_h)
