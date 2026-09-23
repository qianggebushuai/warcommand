import os
import sys
import pygame


def resource_path(relative_path):
    """ 获取资源绝对路径（基准 = 项目根目录） """
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        # utils.py 位于 core/ 下，上一级即项目根
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def get_font(size, bold=False):
    font_path = resource_path(os.path.join("fonts", "simhei.ttf"))
    try:
        font = pygame.font.Font(font_path, size)
        if bold:
            font.set_bold(True)
        return font
    except Exception:
        return pygame.font.Font(None, size)
