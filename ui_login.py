import pygame
import pygame.scrap # 剪贴板模块
from settings import *
from db_manager import DBManager
import cv2 
import os
import sys
import random
# 如果你有 resource_path 函数，记得引入或定义
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
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
class BFInput:
    def __init__(self, x, y, w, h, text='', is_password=False):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.is_password = is_password
        self.active = False
        self.font = get_font(24)
        
        # 尝试初始化剪贴板 (防止报错)
        try:
            if not pygame.scrap.get_init():
                pygame.scrap.init()
        except:
            pass

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
            
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            
            # --- [新增] Ctrl+V 粘贴功能 ---
            elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
                try:
                    # 获取剪贴板内容 (字节bytes -> 解码为 string)
                    clipboard_content = pygame.scrap.get(pygame.SCRAP_TEXT)
                    if clipboard_content:
                        # 过滤掉换行符等非法字符
                        paste_text = clipboard_content.decode('utf-8').strip().replace('\0', '')
                        self.text += paste_text
                except Exception as e:
                    print(f"Paste error: {e}")
            # -----------------------------
            
            elif event.key == pygame.K_TAB:
                pass 
            else:
                # 普通输入
                if not (event.mod & pygame.KMOD_CTRL): # 防止把 Ctrl+C 等录入
                    self.text += event.unicode

    def draw(self, screen):
        # 战地风格：只画底边线
        color = (255, 100, 0) if self.active else (150, 150, 150)
        pygame.draw.line(screen, color, (self.rect.x, self.rect.bottom), (self.rect.right, self.rect.bottom), 2)
        
        display_text = "*" * len(self.text) if self.is_password else self.text
        
        # 简单的文字裁剪防止溢出框
        # (实际项目中可以使用 surface subsurface 裁剪)
        surf = self.font.render(display_text, True, WHITE)
        screen.blit(surf, (self.rect.x, self.rect.y + 5))

class LoginUI:
    def __init__(self, game):
        self.game = game
        self.db = DBManager()
        self.mode = "LOGIN"
        
        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2
        # --- [新增] 视频初始化 ---
        self.video_path = resource_path("log.mp4")
        self.cap = None
        self.video_surf = None
        
        try:
            if os.path.exists(self.video_path):
                self.cap = cv2.VideoCapture(self.video_path)
            else:
                print(f"Video not found: {self.video_path}")
        except Exception as e:
            print(f"Video Init Error: {e}")
            
        # 视频半透明度 (0-255)
        self.video_alpha = 150 
        # -----------------------

        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2        
        # [修改] 布局调整，增加 Server 输入框
        # 1. 服务器地址 (最上面)
        self.input_server = BFInput(cx - 150, cy - 140, 300, 40, text='127.0.0.1')
        
        # 2. 用户名
        self.input_user = BFInput(cx - 150, cy - 70, 300, 40)
        
        # 3. 密码
        self.input_pass = BFInput(cx - 150, cy, 300, 40, is_password=True)
        
        # 按钮下移
        self.btn_action = pygame.Rect(cx - 150, cy + 80, 300, 50)
        self.btn_switch = pygame.Rect(cx - 150, cy + 150, 300, 30)
        self.btn_guest = pygame.Rect(cx - 150, cy + 190, 300, 40)       
        self.status_msg = ""
        self.status_color = RED
        self.font_btn = get_font(30)
        self.font_small = get_font(16)
    def update_video(self):
        """ 读取下一帧视频并转换为 Pygame Surface """
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            
            if not ret:
                # 播放结束，重置到开头 (循环播放)
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
            
            if ret:
                # OpenCV 是 BGR，Pygame 需要 RGB
                # 还需要旋转/翻转，因为 cv2 的坐标系和 pygame surface 转换时可能会倒置
                # 通常：cv2 image (numpy array) -> transpose -> pygame surface
                
                # 1. 转换颜色空间
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # 2. 旋转修正 (cv2读出来是横着的还是竖着的取决于数据，通常直接转置即可)
                # pygame.image.frombuffer 需要 (width, height, 'RGB')
                # frame.shape 是 (h, w, 3)
                h, w = frame.shape[:2]
                
                # 创建 Surface
                self.video_surf = pygame.image.frombuffer(frame.tobytes(), (w, h), "RGB")
                
                # 3. 缩放以适应屏幕
                if w != SCREEN_WIDTH or h != SCREEN_HEIGHT:
                    self.video_surf = pygame.transform.scale(self.video_surf, (SCREEN_WIDTH, SCREEN_HEIGHT))
                
                # 4. 设置透明度
                self.video_surf.set_alpha(self.video_alpha)

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.game.running = False
                return True
            
            # 处理三个输入框
            self.input_server.handle_event(event)
            self.input_user.handle_event(event)
            self.input_pass.handle_event(event)
            
            # Tab 切换循环
            if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
                if self.input_server.active:
                    self.input_server.active = False; self.input_user.active = True
                elif self.input_user.active:
                    self.input_user.active = False; self.input_pass.active = True
                elif self.input_pass.active:
                    self.input_pass.active = False; self.input_server.active = True
                else:
                    self.input_server.active = True

            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.btn_action.collidepoint(event.pos):
                    self.do_action()
                elif self.btn_switch.collidepoint(event.pos):
                    self.mode = "REGISTER" if self.mode == "LOGIN" else "LOGIN"
                    self.status_msg = ""
                elif self.btn_guest.collidepoint(event.pos):
                    self.do_guest_login()

        return False
    def do_guest_login(self):
        # 1. 生成随机名字
        guest_id = str(random.randint(100000, 999999))
        guest_name = f"Guest{guest_id}"
        
        # 2. 模拟登录成功的数据结构
        # uid 使用负数或特殊前缀，避免与数据库冲突
        self.game.player_info = {
            "uid": f"guest_{guest_id}",
            "name": guest_name
        }
        
        print(f"[Login] Guest Login: {guest_name}")
        
        # 3. 关闭视频并跳转
        self.close()
        self.game.state = "LOGIN" 

    def do_action(self):
        # 1. 设置数据库地址
        server_str = self.input_server.text.strip()
        if server_str:
            self.db.set_host(server_str)
        
        user = self.input_user.text.strip()
        pwd = self.input_pass.text.strip()
        
        if not user or not pwd:
            self.status_msg = "Fields cannot be empty"
            self.status_color = RED
            return

        self.status_msg = "Connecting..." # UI反馈
        
        # 强制刷新一下界面显示"Connecting..."（可选，因为单线程会卡住）
        # pygame.display.flip() 
        
        if self.mode == "LOGIN":
            res = self.db.login_user(user, pwd)
            if res:
                self.game.player_info = res
                print(f"[Login] Welcome {res['name']}")
                
                # [新增] 登录成功，关闭视频
                self.close() 
                
                self.game.state = "LOGIN"
            else:
                self.status_msg = "Login Failed (Check Server/User/Pass)"
                self.status_color = RED
        else:
            res = self.db.register_user(user, pwd)
            if res == "Success":
                self.status_msg = "Registration Successful! Please Login."
                self.status_color = GREEN_HAT
                self.mode = "LOGIN"
            else:
                self.status_msg = f"Error: {res}"
                self.status_color = RED

    def draw(self):
        self.game.screen.fill((0, 0, 0))
        
        # 2. 更新并绘制视频
        self.update_video()
        if self.video_surf:
            self.game.screen.blit(self.video_surf, (0, 0))
        else:
            # 如果视频没加载成功，画个静态背景
            self.game.screen.fill((20, 25, 30))
        
        # 标题位置上移
        title = "WAR COMMANDER"
        t_surf = self.game.font_header.render(title, True, WHITE)
        self.game.screen.blit(t_surf, (SCREEN_WIDTH//2 - t_surf.get_width()//2, 10))

        title = "IDENTIFICATION" if self.mode == "LOGIN" else "ENLISTMENT"
        t_surf = self.game.font_header.render(title, True, WHITE)
        self.game.screen.blit(t_surf, (SCREEN_WIDTH//2 - t_surf.get_width()//2, 80))
        
        # 绘制输入框
        self.input_server.draw(self.game.screen)
        self.input_user.draw(self.game.screen)
        self.input_pass.draw(self.game.screen)
        
        # 绘制标签 (Labels)
        def draw_label(text, rect):
            surf = self.game.font.render(text, True, (150, 150, 150))
            self.game.screen.blit(surf, (rect.x, rect.y - 20))

        draw_label("SERVER ADDRESS (IP:PORT)", self.input_server.rect)
        draw_label("USERNAME", self.input_user.rect)
        draw_label("PASSWORD", self.input_pass.rect)
        
        # 按钮
        action_color = (255, 100, 0)
        pygame.draw.rect(self.game.screen, action_color, self.btn_action)
        btn_txt = "LOGIN" if self.mode == "LOGIN" else "REGISTER"
        b_surf = self.font_btn.render(btn_txt, True, BLACK)
        self.game.screen.blit(b_surf, b_surf.get_rect(center=self.btn_action.center))
        
        # 切换
        switch_txt = "Create Account" if self.mode == "LOGIN" else "Back to Login"
        s_surf = self.font_small.render(switch_txt, True, WHITE)
        self.game.screen.blit(s_surf, s_surf.get_rect(center=self.btn_switch.center))

        pygame.draw.rect(self.game.screen, (100, 100, 100), self.btn_guest)
        pygame.draw.rect(self.game.screen, WHITE, self.btn_guest, 2)
        
        g_surf = self.font_small.render("GUEST LOGIN", True, WHITE)
        self.game.screen.blit(g_surf, g_surf.get_rect(center=self.btn_guest.center))          
        # 状态信息
        if self.status_msg:
            msg_surf = self.font_small.render(self.status_msg, True, self.status_color)
            self.game.screen.blit(msg_surf, (SCREEN_WIDTH//2 - msg_surf.get_width()//2, self.btn_action.bottom + 20))
            
        pygame.display.flip()
    def close(self):
        """ [新增] 释放视频资源 """
        if self.cap:
            self.cap.release()
            self.cap = None