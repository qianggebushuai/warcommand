import pygame
from core.settings import *
import os
import sys
from core.utils import resource_path, get_font
from core.i18n import tr, get_language_display, toggle_language

# 窗口尺寸预设（窗口模式可选；逻辑分辨率始终=桌面分辨率，SCALED 自动缩放）
WINDOW_SIZES = [
    (1920, 1080),
    (1600, 900),
    (1366, 768),
    (1280, 720),
]

# main.py
class BaseSettingUI:
    def __init__(self, game):
        self.game = game
        self.active = False

        # 弹窗尺寸
        self.w, self.h = 400, 430
        self.rect = pygame.Rect((SCREEN_WIDTH-self.w)//2, (SCREEN_HEIGHT-self.h)//2, self.w, self.h)

        # 入口按钮 (右上角齿轮)
        self.btn_open = pygame.Rect(SCREEN_WIDTH - 60, 20, 40, 40)

        # 音量滑块
        self.slider_vol = pygame.Rect(self.rect.x + 150, self.rect.y + 62, 210, 10)
        # 全屏复选框
        self.check_fullscreen = pygame.Rect(self.rect.x + 180, self.rect.y + 106, 20, 20)
        # 窗口尺寸按钮 (2x2)
        self.size_btns = []
        for i, (w, h) in enumerate(WINDOW_SIZES):
            bx = self.rect.x + 40 + (i % 2) * 170
            by = self.rect.y + 190 + (i // 2) * 46
            self.size_btns.append((pygame.Rect(bx, by, 150, 36), (w, h)))
        # 关闭按钮
        self.btn_close = pygame.Rect(self.rect.x + 150, self.rect.y + 360, 100, 40)
        # 语言切换按钮（中文/English 来回切，点击即时生效并持久化）
        self.btn_lang = pygame.Rect(self.rect.x + 160, self.rect.y + 318, 120, 32)

        self.dragging_vol = False

        # 弹窗半透明黑遮罩（缓存复用：旧版每帧新建全屏 SRCALPHA 面，
        # 是设置界面闪烁/卡顿来源之一）
        self._overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self._overlay.fill((0, 0, 0, 150))

        # 字体
        self.font = get_font(20)
        self.small_font = get_font(16)

        # 顶部横幅（工业金属风，程序化生成于 picture/；加载失败不影响面板）
        self.banner = None
        try:
            b = pygame.image.load(resource_path("picture/banner_settings.png")).convert_alpha()
            self.banner = pygame.transform.smoothscale(b, (self.w, 72))
        except Exception:
            self.banner = None

    def handle_event(self, event):
        if not self.active:
            if event.type == pygame.MOUSEBUTTONDOWN and self.btn_open.collidepoint(event.pos):
                self.active = True
                return True
            return False

        m_pos = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.btn_close.collidepoint(m_pos):
                self.active = False
                # 保存设置 (可选)

            # 音量滑块
            if self.slider_vol.inflate(0, 20).collidepoint(m_pos):
                self.dragging_vol = True
                self.update_volume(m_pos[0])

            # 全屏切换（toggle_fullscreen 在 SCALED 显示下不可靠，显式重建显示模式）
            if self.check_fullscreen.collidepoint(m_pos):
                self.game.apply_display_mode(not getattr(self.game, 'fullscreen', False))

            # 窗口尺寸选择（点击即切到窗口模式并应用该尺寸）
            for btn_rect, size in self.size_btns:
                if btn_rect.collidepoint(m_pos):
                    self.game.apply_display_mode(False, size=size)

            # 语言切换（即时生效：所有文本在 draw 时经 tr() 取当前语言）
            if self.btn_lang.collidepoint(m_pos):
                toggle_language()

        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging_vol = False

        elif event.type == pygame.MOUSEMOTION:
            if self.dragging_vol:
                self.update_volume(m_pos[0])

        return True # 激活时拦截所有事件

    def update_volume(self, mouse_x):
        # 映射 mouse_x 到 0.0 - 1.0
        ratio = (mouse_x - self.slider_vol.x) / self.slider_vol.width
        ratio = max(0.0, min(1.0, ratio))
        self.game.master_volume = ratio
        pygame.mixer.music.set_volume(ratio)

    def draw(self, screen):
        # 1. 绘制入口按钮 (齿轮)
        if not self.active:
            # 右上角齿轮入口（战地风，hover 高亮）
            hov = self.btn_open.collidepoint(pygame.mouse.get_pos())
            c = (70, 78, 90) if hov else (55, 58, 66)
            gc = (235, 235, 240) if hov else (170, 172, 178)
            pygame.draw.circle(screen, c, self.btn_open.center, 18)
            pygame.draw.circle(screen, gc, self.btn_open.center, 18, 2)
            # 齿牙（8 向短线）
            import math as _m
            cx, cy = self.btn_open.centerx, self.btn_open.centery
            for i in range(8):
                a = _m.radians(i * 45)
                pygame.draw.line(screen, gc,
                                 (cx + _m.cos(a) * 12, cy + _m.sin(a) * 12),
                                 (cx + _m.cos(a) * 17, cy + _m.sin(a) * 17), 2)
            pygame.draw.circle(screen, gc, self.btn_open.center, 6, 2)
            pygame.draw.circle(screen, gc, self.btn_open.center, 2)
            return

        # 2. 绘制弹窗背景（复用缓存遮罩，不再每帧新建）
        screen.blit(self._overlay, (0,0))

        pygame.draw.rect(screen, (40, 45, 50), self.rect, border_radius=10)
        pygame.draw.rect(screen, WHITE, self.rect, 2, border_radius=10)

        # 顶部横幅 + 标题
        if self.banner:
            screen.blit(self.banner, (self.rect.x, self.rect.y))
        t = self.font.render(tr("set.title"), True, WHITE)
        screen.blit(t, (self.rect.x + 20, self.rect.y + 20))

        # 音量
        v_label = self.font.render(tr("set.volume"), True, WHITE)
        screen.blit(v_label, (self.rect.x + 40, self.rect.y + 60))

        pygame.draw.rect(screen, (100, 100, 100), self.slider_vol)
        fill_w = self.game.master_volume * self.slider_vol.width
        pygame.draw.rect(screen, GREEN_HAT, (self.slider_vol.x, self.slider_vol.y, fill_w, 10))
        # 滑块头
        thumb_x = self.slider_vol.x + fill_w
        pygame.draw.circle(screen, WHITE, (int(thumb_x), self.slider_vol.centery), 8)

        # 全屏
        f_label = self.font.render(tr("set.fullscreen"), True, WHITE)
        screen.blit(f_label, (self.rect.x + 40, self.rect.y + 106))
        pygame.draw.rect(screen, BLACK, self.check_fullscreen)
        pygame.draw.rect(screen, WHITE, self.check_fullscreen, 2)
        # 检查是否全屏（用游戏记录的状态，SCALED 模式下 get_flags 不可靠）
        is_fs = getattr(self.game, 'fullscreen', False)
        if is_fs:
            pygame.draw.line(screen, GREEN_HAT, self.check_fullscreen.topleft, self.check_fullscreen.bottomright, 2)
            pygame.draw.line(screen, GREEN_HAT, self.check_fullscreen.topright, self.check_fullscreen.bottomleft, 2)

        # 窗口尺寸
        s_label = self.font.render(tr("set.window_size"), True, WHITE)
        screen.blit(s_label, (self.rect.x + 40, self.rect.y + 155))
        m_pos = pygame.mouse.get_pos()
        cur_size = tuple(getattr(self.game, 'window_size', (0, 0)))
        for btn_rect, size in self.size_btns:
            hovered = btn_rect.collidepoint(m_pos)
            selected = (not is_fs) and (cur_size == size)
            if selected:
                color = (60, 110, 60)
            elif hovered:
                color = (80, 85, 95)
            else:
                color = (55, 60, 70)
            pygame.draw.rect(screen, color, btn_rect, border_radius=6)
            pygame.draw.rect(screen, WHITE if selected else (120, 120, 130), btn_rect, 2, border_radius=6)
            txt = self.small_font.render("%dx%d" % size, True, WHITE)
            screen.blit(txt, txt.get_rect(center=btn_rect.center))

        # 当前模式
        if is_fs:
            mode_txt = tr("set.cur_full", w=SCREEN_WIDTH, h=SCREEN_HEIGHT)
        else:
            ws = getattr(self.game, 'window_size', (0, 0))
            mode_txt = tr("set.cur_window", w=ws[0], h=ws[1])
        mode_surf = self.small_font.render(mode_txt, True, (180, 220, 180))
        screen.blit(mode_surf, (self.rect.x + 40, self.rect.y + 292))

        # 语言切换行（按钮显示当前语言自身的名字：中文 / English）
        lang_label = self.font.render(tr("set.language"), True, WHITE)
        screen.blit(lang_label, (self.rect.x + 40, self.rect.y + 322))
        m_pos = pygame.mouse.get_pos()
        hovered = self.btn_lang.collidepoint(m_pos)
        btn_c = (80, 85, 95) if hovered else (55, 60, 70)
        pygame.draw.rect(screen, btn_c, self.btn_lang, border_radius=6)
        pygame.draw.rect(screen, (120, 120, 130), self.btn_lang, 2, border_radius=6)
        lang_txt = self.font.render(get_language_display(), True, WHITE)
        screen.blit(lang_txt, lang_txt.get_rect(center=self.btn_lang.center))

        # 关闭按钮
        btn_c = (80, 85, 95) if self.btn_close.collidepoint(m_pos) else (60, 65, 75)
        pygame.draw.rect(screen, btn_c, self.btn_close, border_radius=6)
        pygame.draw.rect(screen, WHITE, self.btn_close, 1, border_radius=6)
        c_txt = self.font.render(tr("common.close"), True, WHITE)
        screen.blit(c_txt, c_txt.get_rect(center=self.btn_close.center))
