# -*- coding: utf-8 -*-
"""单位数据配置中心（pygame 版）：可视化增删改 config/units.json。

运行：
    python config_center.py              编辑 config/units.json
    python config_center.py 其他.json     编辑指定配置文件

操作：
    - 点顶部标签切换分区（造价/属性/伤害/建造时间）
    - 点列表行选中 -> 下方输入框载入 -> 改数值 -> "应用修改"
    - "添加新条目"：键名框 + 数值框填好后点它
    - "删除选中"/"重新加载"/"退出"：需连点两次确认（有未保存修改时）
    - "保存"写回 JSON（自动留一份 .bak 备份）；保存后需重启游戏生效
"""
import os
import re
import sys

import pygame

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.unit_config import CONFIG_PATH, UnitConfigError, load_config, save_config
from core.utils import get_font

# (分区键, 标签名, 数值列名)
TABS = [
    ('costs', u'造价', (u'数值',)),
    ('stats', u'属性', (u'血量', u'速度', u'射程', u'采矿')),
    ('damage', u'伤害', (u'数值',)),
    ('build_time', u'建造时间(帧)', (u'数值',)),
    ('buildings', u'建筑数值', (u'数值',)),
    ('ai', u'电脑AI', (u'数值',)),
    ('armor', u'护甲', (u'数值',)),
]
TAB_KEYS = [t[0] for t in TABS]
VAL_COLS = dict((sec, cols) for sec, _, cols in TABS)
TAB_NAMES = dict((sec, name) for sec, name, _ in TABS)

# 布局
W, H = 1200, 720
TAB_Y, TAB_H = 16, 36
HEAD_Y = 66
LIST_TOP, LIST_BOTTOM = 96, 560
ROW_H = 30
FORM1_Y, FORM2_Y = 578, 630
BOX_H = 30
KEY_X, VAL_XS = 16, (400, 520, 640)

# 属性页 4 列（血量/速度/射程/采矿）：列表列距大，超出视口 → 下方横向滚动条
STATS_FIELDS = ('hp', 'speed', 'range', 'mine')
STATS_VAL_XS = (450, 700, 950, 1200)     # 列表+表头的列 x（随横向滚动平移）
STATS_VAL_W = 200
HSCROLL_MAX = STATS_VAL_XS[-1] + STATS_VAL_W + 40 - W   # 内容宽 - 视口宽 = 可滚动量

# 颜色
BG = (24, 26, 30)
PANEL = (34, 38, 44)
ROW_ALT = (40, 44, 52)
SEL = (58, 92, 146)
TXT = (230, 230, 230)
TXT_DIM = (150, 152, 158)
BTN = (60, 66, 76)
BTN_HOVER = (82, 90, 102)
DANGER = (150, 60, 60)
DANGER_HOVER = (190, 70, 70)
ERR = (235, 100, 100)
OK = (130, 220, 150)
LINE = (70, 74, 84)

_KEY_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def parse_num(raw):
    """字符串 -> int/float；非法返回 None。"""
    raw = raw.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        try:
            return float(raw)
        except ValueError:
            return None


class InputBox(object):
    def __init__(self, rect, font, tip=''):
        self.rect = rect
        self.font = font
        self.tip = tip
        self.text = ''
        self.active = False

    def set_text(self, t):
        self.text = t

    def handle_event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.active = self.rect.collidepoint(e.pos)
            return self.active
        if e.type == pygame.KEYDOWN and self.active:
            if e.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif e.key == pygame.K_TAB:
                self.active = False  # 简单失焦
            elif e.unicode and ord(e.unicode) >= 32:
                self.text += e.unicode
            return True
        return False

    def draw(self, surf):
        pygame.draw.rect(surf, (18, 20, 24), self.rect)
        color = (120, 190, 255) if self.active else (110, 114, 124)
        pygame.draw.rect(surf, color, self.rect, 2)
        if self.text:
            surf.blit(self.font.render(self.text, True, TXT),
                      (self.rect.x + 8, self.rect.y + (self.rect.h - self.font.get_height()) // 2))
        elif self.tip:
            surf.blit(self.font.render(self.tip, True, TXT_DIM),
                      (self.rect.x + 8, self.rect.y + (self.rect.h - self.font.get_height()) // 2))


class Button(object):
    def __init__(self, rect, text, callback, font, danger=False):
        self.rect = rect
        self.text = text
        self.callback = callback
        self.font = font
        self.danger = danger
        self.enabled = True

    def handle_event(self, e):
        if not self.enabled:
            return False
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 \
                and self.rect.collidepoint(e.pos):
            self.callback()
            return True
        return False

    def draw(self, surf, mouse_pos):
        base = DANGER if self.danger else BTN
        hover = DANGER_HOVER if self.danger else BTN_HOVER
        color = hover if self.rect.collidepoint(mouse_pos) else base
        pygame.draw.rect(surf, color, self.rect, border_radius=4)
        pygame.draw.rect(surf, LINE, self.rect, 1, border_radius=4)
        surf.blit(self.font.render(self.text, True, TXT),
                  (self.rect.centerx - self.font.size(self.text)[0] // 2,
                   self.rect.centery - self.font.get_height() // 2))


class ConfigCenterApp(object):
    def __init__(self, path=CONFIG_PATH):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption(u'单位数据配置中心')
        self.font = get_font(18)
        self.font_s = get_font(15)
        self.font_b = get_font(20, bold=True)
        self.path = path
        self.dirty = False
        self.status = u''
        self.status_err = False
        self.tab = 'costs'
        self.scroll = 0
        self.hscroll = 0            # 属性页列表横向滚动量
        self.hdrag = None           # 横向滚动条拖拽状态 (grab_x, base)
        self.tab_hscroll = 0        # 顶部标签条横向滚动量（标签多于一屏时）
        self.tab_drag = None
        self.selected = None
        self.confirm_armed = None  # 'delete' / 'reload' / 'quit'
        try:
            self.data = load_config(path)
            self.load_error = None
        except UnitConfigError as e:
            self.load_error = str(e)
            self.data = dict((sec, {}) for sec in TAB_KEYS)
        self._build_widgets()
        self.running = True

    # ---------- UI ----------
    def _build_widgets(self):
        self.tab_btns = []
        for i, (sec, name, _) in enumerate(TABS):
            r = pygame.Rect(16 + i * 190, TAB_Y, 180, TAB_H)
            self.tab_btns.append((sec, Button(r, name, lambda s=sec: self.on_tab(s), self.font)))
        # 标签条横向滚动：标签总宽超出视口时（右端被切）可横向滑动
        self.tab_base_xs = [r.rect.x for _, r in self.tab_btns]
        self.tab_hmax = max(0, self.tab_base_xs[-1] + 180 + 16 - W)

        self.key_box = InputBox(pygame.Rect(KEY_X, FORM1_Y, 300, BOX_H), self.font_s, u'新条目键名')
        self.val_boxes = []
        for i, x in enumerate(VAL_XS):
            self.val_boxes.append(InputBox(pygame.Rect(x, FORM1_Y, 110, BOX_H), self.font_s))
        # 补足到 4 个：属性页 4 列共用（_layout_form 摆位，非属性页藏到屏外）
        while len(self.val_boxes) < len(STATS_FIELDS):
            self.val_boxes.append(InputBox(pygame.Rect(-9999, FORM1_Y, STATS_VAL_W, BOX_H), self.font_s))

        bx = 770
        self.btn_apply = Button(pygame.Rect(bx, FORM1_Y, 120, BOX_H), u'应用修改', self.on_apply, self.font_s)
        self.btn_add = Button(pygame.Rect(bx + 130, FORM1_Y, 140, BOX_H), u'添加新条目', self.on_add, self.font_s)
        self.btn_del = Button(pygame.Rect(bx + 280, FORM1_Y, 120, BOX_H), u'删除选中', self.on_delete, self.font_s, danger=True)
        self.btn_save = Button(pygame.Rect(16, FORM2_Y, 130, BOX_H), u'保存', self.on_save, self.font)
        self.btn_reload = Button(pygame.Rect(156, FORM2_Y, 130, BOX_H), u'重新加载', self.on_reload, self.font)
        self.btn_quit = Button(pygame.Rect(296, FORM2_Y, 130, BOX_H), u'退出', self.request_quit, self.font)

        self.list_rect = pygame.Rect(0, LIST_TOP, W, LIST_BOTTOM - LIST_TOP)
        self._layout_form()

    def _sync_tab_rects(self):
        """按标签条横向滚动量平移各标签按钮的命中矩形"""
        for i, (_, btn) in enumerate(self.tab_btns):
            btn.rect.x = self.tab_base_xs[i] - self.tab_hscroll

    def _layout_form(self):
        """按页签重排表单：属性页 4 个数值框并挤紧宽度（按钮移到第二行），
        其余页保持原布局（多余数值框藏到屏外，避免吃掉点击）。"""
        if self.tab == 'stats':
            self.key_box.rect = pygame.Rect(16, FORM1_Y, 240, BOX_H)
            for b, x in zip(self.val_boxes, (270, 450, 630, 810)):
                b.rect = pygame.Rect(x, FORM1_Y, 150, BOX_H)
            self.btn_apply.rect = pygame.Rect(446, FORM2_Y, 130, BOX_H)
            self.btn_add.rect = pygame.Rect(586, FORM2_Y, 150, BOX_H)
            self.btn_del.rect = pygame.Rect(746, FORM2_Y, 130, BOX_H)
        else:
            self.key_box.rect = pygame.Rect(KEY_X, FORM1_Y, 300, BOX_H)
            self.val_boxes[0].rect = pygame.Rect(VAL_XS[0], FORM1_Y, 110, BOX_H)
            for b in self.val_boxes[1:]:
                b.rect = pygame.Rect(-9999, FORM1_Y, 110, BOX_H)
            self.btn_apply.rect = pygame.Rect(770, FORM1_Y, 120, BOX_H)
            self.btn_add.rect = pygame.Rect(900, FORM1_Y, 140, BOX_H)
            self.btn_del.rect = pygame.Rect(1050, FORM1_Y, 120, BOX_H)

    # ---------- 数据辅助 ----------
    def _rows(self, sec=None):
        return sorted(self.data.get(sec or self.tab, {}))

    def _set_status(self, msg, err=False):
        self.status = msg
        self.status_err = err

    def _disarm(self):
        self.confirm_armed = None

    # ---------- 操作 ----------
    def on_tab(self, sec):
        self.tab = sec
        self.scroll = 0
        self.hscroll = 0
        self.hdrag = None
        self.selected = None
        self._disarm()
        self._layout_form()
        self._clear_form()
        self._set_status(u'当前分区：%s（共 %d 项）' % (TAB_NAMES[sec], len(self.data.get(sec, {}))))

    def _clear_form(self):
        self.key_box.set_text('')
        for b in self.val_boxes:
            b.set_text('')

    def _fill_form(self, key):
        val = self.data[self.tab][key]
        self.key_box.set_text(key)
        if self.tab == 'stats':
            cur = tuple(val.get(f, '') for f in STATS_FIELDS)
        else:
            cur = (val,)
        for b, c in zip(self.val_boxes, cur):
            b.set_text(str(c))

    def on_list_click(self, pos):
        idx = (pos[1] - LIST_TOP + self.scroll) // ROW_H
        rows = self._rows()
        if 0 <= idx < len(rows):
            self.selected = rows[idx]
            self._disarm()
            self._fill_form(self.selected)
            self._set_status(u'已选中：%s' % self.selected)
        else:
            self.selected = None
            self._clear_form()

    def _collect_nums(self):
        """按当前分区取数值输入框内容 -> (数字列表, 采矿列是否有输入)；
        非法时置状态并返回 None。属性页留空的列 = 保留原值（新条目取 0）。"""
        if self.tab == 'stats':
            old = self.data['stats'].get(self.selected, {}) if self.selected else {}
            if not isinstance(old, dict):
                old = {}
            nums, mine_given = [], False
            for i, field in enumerate(STATS_FIELDS):
                t = self.val_boxes[i].text.strip()
                if t == '':
                    nums.append(old.get(field, 0) or 0)
                    continue
                n = parse_num(t)
                if n is None:
                    self._set_status(u'输入错误："%s" 不是有效数字' % t, err=True)
                    return None
                nums.append(n)
                if field == 'mine':
                    mine_given = True
            return nums, mine_given
        n = parse_num(self.val_boxes[0].text)
        if n is None:
            self._set_status(u'输入错误："%s" 不是有效数字' % self.val_boxes[0].text, err=True)
            return None
        return [n], False

    def _write_entry(self, key, nums, mine_given=False):
        if self.tab == 'stats':
            old = self.data[self.tab].get(key, {})
            if not isinstance(old, dict):
                old = {}
            d = {'hp': nums[0], 'speed': nums[1], 'range': nums[2]}
            # 只有本来就带 mine（矿车）或这次填了采矿值的条目才写 mine，
            # 避免给其他单位凭空加 "mine": 0
            if isinstance(old.get('mine'), (int, float)) or mine_given:
                d['mine'] = nums[3]
            self.data[self.tab][key] = d
        else:
            self.data[self.tab][key] = nums[0]

    def on_apply(self):
        if not self.selected:
            self._set_status(u'请先在列表中点选一行', err=True)
            return
        got = self._collect_nums()
        if got is None:
            return
        nums, mine_given = got
        self._write_entry(self.selected, nums, mine_given)
        self.dirty = True
        self._disarm()
        self._set_status(u'已修改 %s（记得点"保存"）' % self.selected)

    def on_add(self):
        key = self.key_box.text.strip()
        if not _KEY_RE.match(key):
            self._set_status(u'键名必须是字母/数字/下划线，且不以数字开头', err=True)
            return
        got = self._collect_nums()
        if got is None:
            return
        nums, mine_given = got
        overwritten = key in self.data.get(self.tab, {})
        self._write_entry(key, nums, mine_given)
        self.dirty = True
        self.selected = key
        self._disarm()
        self._set_status(u'%s %s（记得点"保存"）'
                         % (u'已覆盖' if overwritten else u'已添加', key))

    def on_delete(self):
        if not self.selected:
            self._set_status(u'请先在列表中点选一行', err=True)
            return
        if self.confirm_armed != 'delete':
            self.confirm_armed = 'delete'
            self._set_status(u'再次点击"删除选中"确认删除 %s' % self.selected, err=True)
            return
        del self.data[self.tab][self.selected]
        self.dirty = True
        self.selected = None
        self._disarm()
        self._clear_form()
        self._set_status(u'已删除（记得点"保存"；引用它的游戏代码重启后会报错）')

    def on_save(self):
        try:
            save_config(self.data, self.path)
        except Exception as e:
            self._set_status(u'保存失败：%s' % e, err=True)
            return
        self.dirty = False
        self._disarm()
        self._set_status(u'已保存到 %s（旧文件备份为 .bak）；重启游戏生效' % self.path)

    def on_reload(self):
        if self.dirty and self.confirm_armed != 'reload':
            self.confirm_armed = 'reload'
            self._set_status(u'有未保存修改：再次点击"重新加载"放弃修改并重读', err=True)
            return
        try:
            self.data = load_config(self.path)
        except UnitConfigError as e:
            self._set_status(u'加载失败：%s' % e, err=True)
            return
        self.dirty = False
        self.selected = None
        self._disarm()
        self._clear_form()
        self._set_status(u'已重新加载')

    def request_quit(self):
        if self.dirty and self.confirm_armed != 'quit':
            self.confirm_armed = 'quit'
            self._set_status(u'有未保存修改：再次点击"退出"放弃修改并退出', err=True)
            return
        self.running = False

    # ---------- 事件 ----------
    def handle_event(self, e):
        if e.type == pygame.QUIT:
            self.request_quit()  # 有未保存修改时走两步确认
            return
        if e.type == pygame.MOUSEWHEEL:
            mouse = pygame.mouse.get_pos()
            # 光标悬在顶部标签条上 → 横向滚动标签条
            if self.tab_hmax > 0 and mouse[1] <= TAB_Y + TAB_H + 16:
                self.tab_hscroll = max(0, min(self.tab_hmax,
                                              self.tab_hscroll + (e.x + e.y) * 60))
                self._sync_tab_rects()
                return
            max_scroll = max(0, len(self._rows()) * ROW_H - (LIST_BOTTOM - LIST_TOP))
            self.scroll = max(0, min(max_scroll, self.scroll - e.y * ROW_H * 3))
            # 属性页横向滚动（鼠标侧键 / 触控板水平分量，e.x>0 = 向右看）
            if self.tab == 'stats':
                self.hscroll = max(0, min(HSCROLL_MAX, self.hscroll + e.x * 60))
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.request_quit()
            return
        if e.type == pygame.MOUSEMOTION and e.buttons[0]:
            if self.tab_drag:
                grab_x, base = self.tab_drag
                self.tab_hscroll = max(0, min(self.tab_hmax, base + (e.pos[0] - grab_x)))
                self._sync_tab_rects()
                return
            if self.hdrag:
                grab_x, base = self.hdrag
                self.hscroll = max(0, min(HSCROLL_MAX, base + (e.pos[0] - grab_x)))
                return
        if e.type == pygame.MOUSEBUTTONUP:
            self.tab_drag = None
            self.hdrag = None
        for box in [self.key_box] + self.val_boxes:
            if box.handle_event(e):
                return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            # 标签条横向滚动条拖拽/跳转
            if self.tab_hmax > 0 and getattr(self, '_tab_thumb', None) \
                    and (self._tab_thumb.collidepoint(e.pos) or self._tab_track.collidepoint(e.pos)):
                self.tab_drag = (e.pos[0], self.tab_hscroll)
                if not self._tab_thumb.collidepoint(e.pos):
                    rel = (e.pos[0] - self._tab_track.x) / float(max(1, self._tab_track.w - self._tab_thumb.w))
                    self.tab_hscroll = max(0, min(self.tab_hmax, int(rel * self.tab_hmax)))
                    self._sync_tab_rects()
                return
            # 属性页列表横向滚动条拖拽/跳转
            if self.tab == 'stats' and getattr(self, '_hthumb', None) \
                    and self._hthumb.collidepoint(e.pos):
                self.hdrag = (e.pos[0], self.hscroll)
                return
            if self.tab == 'stats' and getattr(self, '_htrack', None) \
                    and self._htrack.collidepoint(e.pos):
                # 点轨道跳转（滑块中心对准点击处）
                self.hdrag = (e.pos[0], self.hscroll)
                rel = (e.pos[0] - self._htrack.x) / float(max(1, self._htrack.w - self._hthumb.w))
                self.hscroll = max(0, min(HSCROLL_MAX, int(rel * HSCROLL_MAX)))
                return
            if self.list_rect.collidepoint(e.pos):
                self.on_list_click(e.pos)
                return
            for _, btn in self.tab_btns:
                if btn.handle_event(e):
                    return
            for btn in (self.btn_apply, self.btn_add, self.btn_del,
                        self.btn_save, self.btn_reload, self.btn_quit):
                if btn.handle_event(e):
                    return

    # ---------- 绘制 ----------
    def draw(self):
        mouse = pygame.mouse.get_pos()
        scr = self.screen
        scr.fill(BG)

        # 标签（随标签条横向滚动平移）
        self._sync_tab_rects()
        for sec, btn in self.tab_btns:
            active = (sec == self.tab)
            r = btn.rect
            if r.right < 0 or r.x > W:
                continue
            pygame.draw.rect(scr, SEL if active else BTN, r, border_radius=4)
            pygame.draw.rect(scr, LINE, r, 1, border_radius=4)
            tw = btn.font.size(btn.text)[0]
            scr.blit(btn.font.render(btn.text, True, TXT),
                     (r.centerx - tw // 2, r.centery - btn.font.get_height() // 2))
            if active:
                pygame.draw.rect(scr, (130, 200, 255), (r.x, r.y, r.w, 3))

        # 标签条横向滚动条（标签多于一屏时出现）
        self._tab_track = self._tab_thumb = None
        if self.tab_hmax > 0:
            track = pygame.Rect(0, TAB_Y + TAB_H + 2, W, 8)
            pygame.draw.rect(scr, PANEL, track)
            tw = max(40, int(track.w * float(W) / (W + self.tab_hmax)))
            tx = track.x + int((track.w - tw) * self.tab_hscroll / float(self.tab_hmax))
            self._tab_track = track
            self._tab_thumb = pygame.Rect(tx, track.y, tw, track.h)
            pygame.draw.rect(scr, (90, 96, 110), self._tab_thumb, border_radius=3)

        # 表头（属性页随横向滚动平移）
        cols = VAL_COLS[self.tab]
        hs = self.hscroll if self.tab == 'stats' else 0
        scr.blit(self.font_s.render(u'键名', True, TXT_DIM), (KEY_X - hs, HEAD_Y))
        xs = STATS_VAL_XS if self.tab == 'stats' else VAL_XS
        for x, name in zip(xs, cols):
            scr.blit(self.font_s.render(name, True, TXT_DIM), (x - hs, HEAD_Y))
        pygame.draw.line(scr, LINE, (0, LIST_TOP - 4), (W, LIST_TOP - 4))

        # 列表
        rows = self._rows()
        clip = self.list_rect
        scr.set_clip(clip)
        for i, key in enumerate(rows):
            y = LIST_TOP + i * ROW_H - self.scroll
            if y + ROW_H < LIST_TOP or y > LIST_BOTTOM:
                continue
            if key == self.selected:
                pygame.draw.rect(scr, SEL, (0, y, W, ROW_H))
            elif i % 2 == 1:
                pygame.draw.rect(scr, ROW_ALT, (0, y, W, ROW_H))
            val = self.data[self.tab][key]
            scr.blit(self.font_s.render(key, True, TXT), (KEY_X - hs, y + 6))
            if self.tab == 'stats':
                for x, field in zip(STATS_VAL_XS, STATS_FIELDS):
                    scr.blit(self.font_s.render(str(val.get(field, '')), True, TXT), (x - hs, y + 6))
            else:
                scr.blit(self.font_s.render(str(val), True, TXT), (VAL_XS[0], y + 6))
        scr.set_clip(None)

        # 横向滚动条（属性页专属）
        self._htrack = self._hthumb = None
        if self.tab == 'stats' and HSCROLL_MAX > 0:
            track = pygame.Rect(16, LIST_BOTTOM - 14, W - 44, 10)
            pygame.draw.rect(scr, PANEL, track, border_radius=4)
            tw = max(40, int(track.w * float(W) / (W + HSCROLL_MAX)))
            tx = track.x + int((track.w - tw) * self.hscroll / float(HSCROLL_MAX))
            self._htrack = track
            self._hthumb = pygame.Rect(tx, track.y, tw, track.h)
            pygame.draw.rect(scr, (90, 96, 110), self._hthumb, border_radius=4)

        # 滚动指示条
        total_h = len(rows) * ROW_H
        view_h = LIST_BOTTOM - LIST_TOP
        if total_h > view_h:
            bar_h = max(30, int(view_h * view_h / float(total_h)))
            bar_y = LIST_TOP + int((view_h - bar_h) * self.scroll / float(total_h - view_h))
            pygame.draw.rect(scr, (90, 96, 110), (W - 8, bar_y, 6, bar_h), border_radius=3)

        # 表单区
        pygame.draw.line(scr, LINE, (0, FORM1_Y - 12), (W, FORM1_Y - 12))
        n_cols = len(STATS_FIELDS) if self.tab == 'stats' else 1
        self.key_box.draw(scr)
        for i, b in enumerate(self.val_boxes):
            if i < n_cols:
                b.draw(scr)
            else:
                pygame.draw.rect(scr, BG, b.rect)
        if self.tab == 'stats':
            # 属性页数值框列标题（采矿=矿车满载量，仅 HARVESTER 使用）
            for b, name in zip(self.val_boxes, VAL_COLS['stats']):
                scr.blit(self.font_s.render(name, True, TXT_DIM), (b.rect.x + 2, FORM1_Y - 24))
        if self.selected:
            lbl = self.font_s.render(u'编辑: %s' % self.selected, True, (130, 200, 255))
        else:
            lbl = self.font_s.render(u'未选中（键名框供"添加"用）', True, TXT_DIM)
        scr.blit(lbl, (KEY_X, FORM1_Y - 34))

        for btn in (self.btn_apply, self.btn_add, self.btn_del,
                    self.btn_save, self.btn_reload, self.btn_quit):
            btn.draw(scr, mouse)

        # 状态行（属性页按钮在第二行 446-876，状态挪到右侧避免重叠）
        color = ERR if self.status_err else (OK if self.status.startswith(u'已保存') else TXT_DIM)
        tip = u'有未保存修改  ' if self.dirty else u''
        scr.blit(self.font_s.render(tip + self.status, True, color),
                 (900 if self.tab == 'stats' else 440, FORM2_Y + 8))
        # 配置加载错误提示（如文件缺失）
        if self.load_error:
            scr.blit(self.font_s.render(u'配置加载失败，当前为空数据：%s' % self.load_error.splitlines()[0],
                                        True, ERR), (16, H - 30))

        pygame.display.flip()

    def run(self):
        clock = pygame.time.Clock()
        while self.running:
            for e in pygame.event.get():
                self.handle_event(e)
            self.draw()
            clock.tick(30)
        pygame.quit()


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else CONFIG_PATH
    ConfigCenterApp(path).run()


if __name__ == '__main__':
    main()
