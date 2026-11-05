import pygame
import hashlib
from core.settings import *
from core.utils import resource_path, get_font
from core.i18n import tr

class ChatBox:
    def __init__(self, game):
        self.game = game
        self.active = False
        self.text = ""
        self.messages = [] 
        self.font = get_font(14) # 使用支持中文的字体
        # 对话面板放左上角（避开右侧栏）
        self.input_rect = pygame.Rect(20, 50, 300, 30)
        self.history_rect = pygame.Rect(20, 90, 300, 200)
        


    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if self.active:
                if event.key == pygame.K_RETURN:
                    if self.text.strip():
                        self.send_chat()
                        self.text = ""
                    self.active = False 
                    pygame.key.stop_text_input()
                    
                elif event.key == pygame.K_BACKSPACE:
                    self.text = self.text[:-1]
                    
                elif event.key == pygame.K_ESCAPE:
                    self.active = False
                    pygame.key.stop_text_input()
            else:
                # 激活聊天框
                if event.key == pygame.K_t: 
                    self.active = True
                    pygame.key.start_text_input()
        if event.type == pygame.TEXTINPUT and self.active:
            self.text += event.text
    def add_message(self, text, sender_name, is_self=False):
        # [修改] 颜色逻辑
        if is_self:
            name_color = (0, 255, 255) # 自己是青色
        elif sender_name == "System":
            name_color = YELLOW
        else:
            # 根据名字生成随机颜色 (确定性随机)
            import hashlib
            h = int(hashlib.md5(sender_name.encode()).hexdigest(), 16)
            r = (h & 0xFF)
            g = (h >> 8) & 0xFF
            b = (h >> 16) & 0xFF
            # 避免太黑
            name_color = (max(100, r), max(100, g), max(100, b))
        
        # 消息内容颜色
        msg_color = WHITE
        
        # 存储结构变一下，或者直接拼成字符串
        # 格式: "[Name]: Text"
        display_text = f"[{sender_name}]: {text}"
        self.messages.append({"text": display_text, "color": name_color}) # 整条消息用名字颜色，或者分开画

    def send_chat(self):
        my_name = self.game.player_info['name']
        self.add_message(self.text, my_name, is_self=True)
        
        if self.game.is_online:
            self.game.net.send({
                "type": "CHAT", 
                "text": self.text, 
                "name": my_name
            })

    def draw(self, screen):
        s = pygame.Surface((300, 200), pygame.SRCALPHA)
        s.fill((0, 0, 0, 100))
        screen.blit(s, (self.history_rect.x, self.history_rect.y))
        
        y = self.history_rect.bottom - 25
        for msg in reversed(self.messages):
            # 简单的自动换行略过，假设消息不长
            txt_surf = self.font.render(msg['text'], True, msg['color'])
            screen.blit(txt_surf, (self.history_rect.x + 5, y))
            y -= 25
            if y < self.history_rect.top: break

        # 2. 绘制输入框 (激活时)
        if self.active:
            pygame.draw.rect(screen, (50, 50, 50), self.input_rect)
            pygame.draw.rect(screen, WHITE, self.input_rect, 2)
            
            # 绘制输入内容 (加光标)
            txt_surf = self.font.render(self.text + "|", True, WHITE)
            screen.blit(txt_surf, (self.input_rect.x + 5, self.input_rect.y + 5))


class BFButton:
    def __init__(self, x, y, text, font, action_code):
        self.x = x
        self.y = y
        self.text = text
        self.font = font
        self.action_code = action_code # 用于标识点击了哪个按钮
        # 预渲染文字
        self.surf_normal = font.render(text, True, (180, 180, 180)) # 灰色未选中
        self.surf_hover = font.render(text, True, (255, 255, 255))  # 白色选中
        self.rect = self.surf_normal.get_rect(topleft=(x, y))
        self.is_hovered = False

    def check_hover(self, mouse_pos):
        self.is_hovered = self.rect.collidepoint(mouse_pos)
        return self.is_hovered

    def draw(self, screen):
        if self.is_hovered:
            screen.blit(self.surf_hover, (self.x, self.y))
            pygame.draw.rect(screen, (255, 100, 0), (self.x - 10, self.y + 5, 4, self.rect.height - 10))
        else:
            screen.blit(self.surf_normal, (self.x, self.y))


class InputBox:
    def __init__(self, x, y, w, h, text=''):
        self.rect = pygame.Rect(x, y, w, h)
        self.color_inactive = (100, 100, 100)
        self.color_active = (255, 255, 255) # 激活时变白
        self.color = self.color_inactive
        self.text = text
        self.font = get_font(24)
        self.txt_surface = self.font.render(text, True, self.color)
        self.active = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            # 点击切换激活状态
            if self.rect.collidepoint(event.pos):
                print("[Debug] InputBox ACTIVATED!")
                self.active = not self.active
            else:
                self.active = False
            self.color = self.color_active if self.active else self.color_inactive
            
        if event.type == pygame.KEYDOWN:
            if self.active:
                if event.key == pygame.K_RETURN:
                    pass # 回车不做处理，由外部逻辑决定
                
                elif event.key == pygame.K_BACKSPACE:
                    self.text = self.text[:-1]
                elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
                    try:
                        # Pygame 2.2+ 用法
                        clipboard_content = pygame.scrap.get(pygame.SCRAP_TEXT)
                        
                        if clipboard_content:
                            # 2.2+ 可能返回 bytes 或 str，需要判断
                            if isinstance(clipboard_content, bytes):
                                paste_text = clipboard_content.decode('utf-8')
                            else:
                                paste_text = str(clipboard_content)
                                
                            paste_text = paste_text.strip().replace('\0', '')
                            if paste_text.isascii(): # 过滤
                                self.text += paste_text
                    except Exception as e:
                        print(f"Paste error: {e}")
                
                else:
                    # 普通打字
                    self.text += event.unicode
                
                # 更新渲染文字
                self.txt_surface = self.font.render(self.text, True, self.color)

    def draw(self, screen):
        # 战地风格：只画底边线
        pygame.draw.line(screen, self.color, (self.rect.x, self.rect.bottom), (self.rect.right, self.rect.bottom), 2)
        screen.blit(self.txt_surface, (self.rect.x + 5, self.rect.y + 5))
        
        # 标签提示
        label = get_font(24).render(tr("login.server"), True, (150, 150, 150))
        screen.blit(label, (self.rect.x, self.rect.y - 20))

