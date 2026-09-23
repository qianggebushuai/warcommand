import pygame
from settings import *  # 确保你的 settings.py 里定义了 SCREEN_WIDTH, SCREEN_HEIGHT, BLACK, WHITE, RED, YELLOW 等常量
import sys
import os

def resource_path(relative_path):
    """ 获取资源绝对路径 """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的临时目录
        base_path = sys._MEIPASS
    else:
        # 开发环境：使用 main.py 所在的文件夹，而不是 "."
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

def get_font(size, bold=False):
    # 路径根据你的实际情况改
    font_path = resource_path(os.path.join("fonts", "simhei.ttf"))
    try:
        font = pygame.font.Font(font_path, size)
        if bold: font.set_bold(True)
        return font
    except:
        return pygame.font.Font(None, size)

# ========== 新增：中文自动换行函数 ==========
def wrap_text(text, font, max_width):
    """
    将文本按指定宽度自动换行
    :param text: 要换行的文本
    :param font: 使用的字体对象
    :param max_width: 最大显示宽度
    :return: 换行后的字符串列表
    """
    lines = []
    raw_lines = text.split('\n')
    
    for raw_line in raw_lines:
        if not raw_line:  
            lines.append("")
            continue
            
        current_line = ""
        for char in raw_line:
            test_line = current_line + char
            text_width, _ = font.size(test_line)
            if text_width > max_width:
                lines.append(current_line)
                current_line = char
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)
    
    return lines

class UpdateLogUI:
    def __init__(self, game):
        self.game = game
        self.active = False
        
        self.btn_size = 40
        self.btn_pos = (50, 50) 
        self.btn_points = [
            (self.btn_pos[0], self.btn_pos[1] - self.btn_size//2), # 上
            (self.btn_pos[0] - self.btn_size//2, self.btn_pos[1] + self.btn_size//2), # 左下
            (self.btn_pos[0] + self.btn_size//2, self.btn_pos[1] + self.btn_size//2)  # 右下
        ]
        self.btn_rect = pygame.Rect(self.btn_pos[0]-20, self.btn_pos[1]-20, 40, 40)

        self.window_w, self.window_h = 600, 400
        self.window_rect = pygame.Rect(
            (SCREEN_WIDTH - self.window_w)//2,
            (SCREEN_HEIGHT - self.window_h)//2,
            self.window_w, self.window_h
        )
        self.close_btn_rect = pygame.Rect(self.window_rect.right - 30, self.window_rect.top + 5, 25, 25)
        
        # 3. 数据内容
        self.logs = [
            {
                "title": "0.6.3:空域",
                "desc": [
                    "为三个国家都添加了不同模型的固定翼",
                    "增添了地图背景",
                    "不想更了,最近去学blender了,之后会更一下地图破坏",
                ]
            },
            {
                "title": "0.7.0:黑幕时代",
                "desc": [
                    "添加了黑幕装置,通过全图的干扰让敌人陷入恐慌",
                    "单位图鉴现在可用了!可以在主界面查看单位的详细信息",
                    "对部分立绘进行了修补",
                    "优化了AI机制,现在AI更简单但是更有逻辑",
                    "优化了多人联机占线的问题",
                    "修复了字体读取的bug,看来后来要换新字体了o(╥﹏╥)o"
                ]
            },
            {
                "title": "0.7.1:填充计划1",
                "desc": [
                    "新增高科技制造,现在的高科技工厂不止用于解锁新单位,也能为玩家增加一个额外的建造栏",
                    "优化了点击逻辑",
                    "新增单位:太空运输飞船:可以运载地面的机械目标或者基地车跨过海洋,实施快速转移",
                    "添加了观战模式",
                    "新增地图:围攻 在祖国的海岸线上为维护统一而战"

                ]
            },
            {
                "title": "0.7.2:填充计划2",
                "desc": [
                    "新增岸防炮,将海军拖至岸边发动支援时需谨慎",
                    "添加,修改了部分立绘",
                    "修复了无法建造船厂的bug",
                    "修复了单位在水中窒息的bug",
                    "添加了调节音量快捷界面",
                    "战役在做了别催了(╥﹏╥)",
                    "现在运兵车添加了工程师维修功能",
                ]
            },
            {
                "title": "0.7.3:填充计划3",
                "desc": [
                    "添加新空中单位,攻击机",
                    "修复了部分死亡特效不显示的问题",
                    "平衡了部分单位(黑幕装置,mi24,wz-10,激光塔等)",
                    "新增了转向限制,掐住他滴头战术将在战场上起到重要作用",
                    "添加了景观类实体和可占领房屋",
                    "优化了多人游戏判定的问题",
                    "目前聊天框有阻塞问题,请加入方不要输入信息"

                    
                ]
            },
            {
                "title": "0.8.0:海军风暴I",
                "desc": [
                    "统一了单人界面风格并添加了自定义模式",
                    "添加了多个海军单位,巡空驱逐舰,导弹巡洋舰,聚能潜艇" ,
                    "修复了激光显示问题",
                    "修复了特效不同步问题",
                    "削弱了潜艇的聚能速度和射程,削弱了防空炮的范围,增加了主动防御阵列的冷却",
                    "优化了矿车的逻辑",
                    "增加了气候变化,在暴风雨中将战斗推向高潮"

                ]
            },
            {
                "title": "0.8.1:海军风暴II",
                "desc": [
                    "优化了护甲和绘制机制",
                    "在部分地图添加新区域:红钴富集地,用于更高效的开采矿物",
                    "添加新建筑:铁幕装置以及护盾机制"

                ]
            },
            {
                "title": "0.8.2:海军风暴III",
                "desc": [
                    "目前新项目 轰炸银河系（break the galaxy）正在开发中，请大家多多支持σ ﾟ∀ ﾟ) ﾟ∀ﾟ)σ，也希望大家继续支持作战指挥官：无限战争！",
                    "添加中国特色单位：龙式运载车，运载坦克进行火力支援;鱼雷艇，射出一段时间后自动调整位置的鱼雷，并向建筑投射自爆机器人；近防炮替代激光塔，对近距离空地目标进行毁灭性打击",
                    "添加新联邦单位：高爆多功能防空车替换运兵车,利用力场盾和集束防空弹痛击敌军",
                    "为美国添加新单位，航空母舰替换导弹驱逐舰",
                    "添加小地图机制"


                ]
            },
        ]
        
        self.current_idx = 0 # 
        
        # 4. 列表
        self.list_w = 200
        self.list_rect = pygame.Rect(self.window_rect.x, self.window_rect.y + 40, self.list_w, self.window_h - 40)
        
        # 5. 详情
        self.detail_rect = pygame.Rect(self.window_rect.x + self.list_w, self.window_rect.y + 40, 
                                       self.window_w - self.list_w, self.window_h - 40)
                                       
        self.scroll_y = 0
        self.content_height = 0 # 动态计算
        self.is_dragging_bar = False
        
        self.bar_bg_rect = pygame.Rect(self.detail_rect.right - 15, self.detail_rect.top, 15, self.detail_rect.height)
        self.thumb_rect = pygame.Rect(0, 0, 0, 0) 
        
        self.font_title = get_font(24, bold=True)
        self.font_item = get_font(20)
        self.font_desc = get_font(16) 

    def handle_event(self, event):
        # 修复：m_pos 只在需要时定义
        m_pos = pygame.mouse.get_pos() if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION) else None
        
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:            
            # 如果窗口打开
            if self.active:
                # 1. 关闭
                if self.close_btn_rect.collidepoint(m_pos):
                    self.active = False
                    return True # 拦截事件
                
                # 2. 列表点击
                if self.list_rect.collidepoint(m_pos):
                    item_h = 30
                    rel_y = m_pos[1] - self.list_rect.y
                    idx = rel_y // item_h
                    
                    if 0 <= idx < len(self.logs):
                        self.current_idx = idx
                    return True
                
                # 3. 滚动条点击
                if self.bar_bg_rect.collidepoint(m_pos):
                    self.is_dragging_bar = True
                    self.update_scroll_from_mouse(m_pos[1])
                    return True
                
                if self.window_rect.collidepoint(m_pos):
                    return True
            
            else:
                if self.btn_rect.collidepoint(m_pos):
                    self.active = True
                    return True

        elif event.type == pygame.MOUSEBUTTONUP:
            self.is_dragging_bar = False

        elif event.type == pygame.MOUSEMOTION:
            if self.is_dragging_bar and m_pos:
                self.update_scroll_from_mouse(m_pos[1])
                    
        return False

    def update_scroll_from_mouse(self, mouse_y):
        # 根据鼠标位置计算 scroll_y
        if self.content_height <= self.detail_rect.height:
            self.scroll_y = 0
            return

        # 可滚动区域高度
        track_h = self.bar_bg_rect.height - self.thumb_rect.height
        if track_h <= 0: return
        
        rel_y = mouse_y - self.bar_bg_rect.top - (self.thumb_rect.height / 2)
        ratio = rel_y / track_h
        
        max_scroll = self.content_height - self.detail_rect.height
        self.scroll_y = ratio * max_scroll
        self.clamp_scroll()

    def clamp_scroll(self):
        max_scroll = max(0, self.content_height - self.detail_rect.height)
        self.scroll_y = max(0, min(self.scroll_y, max_scroll))

    def draw(self, screen):
        m_pos = pygame.mouse.get_pos()
        
        # 1. 绘制主按钮 (三角形 + 感叹号)
        if not self.active:
            color = (255, 200, 0)
            if self.btn_rect.collidepoint(m_pos): color = (255, 255, 100)
            
            pygame.draw.polygon(screen, color, self.btn_points)
            pygame.draw.polygon(screen, BLACK, self.btn_points, 2)
            
            # 感叹号 (!)
            ex_x = self.btn_pos[0]
            ex_y = self.btn_pos[1] + 5
            pygame.draw.line(screen, BLACK, (ex_x, ex_y-8), (ex_x, ex_y+4), 3)
            pygame.draw.circle(screen, BLACK, (ex_x, ex_y+8), 2)
            return

        # 2. 绘制弹窗背景
        # 半透明遮罩
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0,0))
        
        # 窗口主体
        pygame.draw.rect(screen, (40, 45, 50), self.window_rect)
        pygame.draw.rect(screen, (200, 200, 200), self.window_rect, 2)
        
        # 标题栏
        pygame.draw.rect(screen, (30, 30, 35), (self.window_rect.x, self.window_rect.y, self.window_w, 40))
        title_surf = self.font_title.render("UPDATE LOG", True, WHITE)
        screen.blit(title_surf, (self.window_rect.x + 10, self.window_rect.y + 10))
        
        # 关闭按钮 (X)
        close_color = RED if self.close_btn_rect.collidepoint(m_pos) else (150, 50, 50)
        pygame.draw.rect(screen, close_color, self.close_btn_rect)
        pygame.draw.line(screen, WHITE, (self.close_btn_rect.left+5, self.close_btn_rect.top+5), 
                         (self.close_btn_rect.right-5, self.close_btn_rect.bottom-5), 2)
        pygame.draw.line(screen, WHITE, (self.close_btn_rect.left+5, self.close_btn_rect.bottom-5), 
                         (self.close_btn_rect.right-5, self.close_btn_rect.top+5), 2)

        # 3. 绘制列表 (左侧)
        pygame.draw.rect(screen, (50, 55, 60), self.list_rect)
        pygame.draw.line(screen, (100, 100, 100), (self.list_rect.right, self.list_rect.top), 
                         (self.list_rect.right, self.list_rect.bottom), 1)
        
        item_h = 30
        for i, log in enumerate(self.logs):
            item_y = self.list_rect.y + i * item_h
            item_rect = pygame.Rect(self.list_rect.x, item_y, self.list_w, item_h)
            
            # 选中高亮
            if i == self.current_idx:
                pygame.draw.rect(screen, (80, 100, 120), item_rect)
            elif item_rect.collidepoint(m_pos):
                pygame.draw.rect(screen, (60, 65, 70), item_rect)
            
            # 文字 (只显示标题的一部分)
            short_title = log['title'].split(':')[0] # 如 "v1.5"
            txt_surf = self.font_item.render(short_title, True, WHITE)
            screen.blit(txt_surf, (item_rect.x + 10, item_rect.y + 5))

        # 4. 绘制详情 (带滚动)
        if 0 <= self.current_idx < len(self.logs):
            log = self.logs[self.current_idx]
            
            # ========== 关键修改：处理中文换行 ==========
            # 计算详情区域可用宽度 (减去滚动条和边距)
            detail_available_width = self.detail_rect.width - 30  # 20px边距 + 10px预留
            
            # 绘制标题
            head_surf = self.font_title.render(log['title'], True, YELLOW)
            
            # 处理描述文本换行
            all_wrapped_lines = []
            line_h = self.font_desc.get_linesize()  # 获取字体行高（更准确）
            
            # 遍历所有描述行，进行换行处理
            for desc_line in log['desc']:
                wrapped_lines = wrap_text(desc_line, self.font_desc, detail_available_width)
                all_wrapped_lines.extend(wrapped_lines)
                all_wrapped_lines.append("")  # 段落之间加空行
            
            # 计算总内容高度
            self.content_height = 60 + len(all_wrapped_lines) * line_h  # 60px标题区域
            self.content_height = max(self.content_height, self.detail_rect.height)  # 至少填满窗口
            
            # 创建长画布
            content_surf = pygame.Surface((self.detail_rect.width - 20, self.content_height), pygame.SRCALPHA)
            
            # 绘制标题
            content_surf.blit(head_surf, (10, 10))
            
            # 绘制换行后的描述文本
            curr_y = 60  # 标题下方开始
            for line in all_wrapped_lines:
                if line.strip() == "":  # 空行
                    curr_y += line_h
                    continue
                line_surf = self.font_desc.render(line, True, (220, 220, 220))
                content_surf.blit(line_surf, (10, curr_y))
                curr_y += line_h
            
            # 裁剪并绘制到屏幕
            view_rect = pygame.Rect(0, int(self.scroll_y), 
                                    self.detail_rect.width - 20, self.detail_rect.height)
            
            # 确保不越界
            safe_y = min(view_rect.y, self.content_height - view_rect.height)
            safe_y = max(0, safe_y)
            
            sub = content_surf.subsurface((0, safe_y, view_rect.width, view_rect.height))
            screen.blit(sub, self.detail_rect.topleft)

            # 绘制滚动条
            if self.content_height > self.detail_rect.height:
                pygame.draw.rect(screen, (30, 30, 30), self.bar_bg_rect)
                
                # 计算滑块位置和大小
                ratio = self.detail_rect.height / self.content_height
                thumb_h = max(20, int(self.detail_rect.height * ratio))
                
                scroll_ratio = self.scroll_y / (self.content_height - self.detail_rect.height)
                thumb_y = self.bar_bg_rect.top + scroll_ratio * (self.bar_bg_rect.height - thumb_h)
                
                self.thumb_rect = pygame.Rect(self.bar_bg_rect.x, int(thumb_y), 15, thumb_h)
                
                c = (150, 150, 150) if self.is_dragging_bar else (100, 100, 100)
                if self.thumb_rect.collidepoint(pygame.mouse.get_pos()): c = (120, 120, 120)
                
                pygame.draw.rect(screen, c, self.thumb_rect, border_radius=5)

# 测试代码（如果需要单独测试）
if __name__ == "__main__":
    # 模拟 settings.py 中的常量
    SCREEN_WIDTH = 1280
    SCREEN_HEIGHT = 720
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    RED = (255, 0, 0)
    YELLOW = (255, 255, 0)
    
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    
    # 模拟 game 对象
    class MockGame:
        pass
    game = MockGame()
    
    update_log_ui = UpdateLogUI(game)
    
    running = True
    while running:
        screen.fill((30, 30, 30))
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            # 处理UI事件
            update_log_ui.handle_event(event)
        
        # 绘制UI
        update_log_ui.draw(screen)
        
        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()
    sys.exit()