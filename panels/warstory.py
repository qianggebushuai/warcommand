import random

import pygame
from core.settings import *
from core.base_classes import vec
import os
import sys
from core.utils import resource_path, get_font
from core.i18n import tr


class CampaignMission:
    def __init__(self, mission_id, title, subtitle, description, map_name, difficulty, objectives):
        self.mission_id = mission_id
        self.title = title
        self.subtitle = subtitle
        self.description = description
        self.map_name = map_name
        self.difficulty = difficulty
        self.objectives = objectives
        self.unlocked = False
        self.completed = False
        self.stars = 0

class CampaignManager:
    def __init__(self, game):
        self.game = game
        self.current_campaign = None
        self.current_mission_index = 0
        self.missions = []
        self.campaign_state = "MISSION_SELECT"

        self.bg_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.bg_surface.fill((20, 15, 10))

        try:
            path = resource_path("fonts/simhei.ttf")
            self.font_title = pygame.font.Font(path, 72)
            self.font_subtitle = pygame.font.Font(path, 36)
            self.font_desc = pygame.font.Font(path, 22)
            self.font_btn = pygame.font.Font(path, 28)
            self.font_small = pygame.font.Font(path, 20)
            self.font_objective = pygame.font.Font(path, 18)
        except:
            self.font_title = get_font(72)
            self.font_subtitle = get_font(36)
            self.font_desc = get_font(22)
            self.font_btn = get_font(28)
            self.font_small = get_font(20)
            self.font_objective = get_font(18)

        self.btn_back = pygame.Rect(50, SCREEN_HEIGHT - 100, 200, 50)
        self.mission_buttons = []
        self.scroll_offset = 0
        self.max_scroll = 0

        self._setup_broadcast_storm_1()

    def _setup_broadcast_storm_1(self):
        self.current_campaign = {
            "id": "broadcast_storm_1",
            "title": "广播风云",
            "subtitle": "第一章：通讯枢纽"
        }

        self.missions = [
            CampaignMission(
                mission_id=1,
                title="战役介绍",
                subtitle="选择你的任务",
                description="泛亚联盟在火星建立的广播中心突然与地球失去联系。\n美国联合开采者正在对这一地区施加军事压力。\n作为泛亚联盟的指挥官，你必须突破敌人的防线，\n恢复与地球的通讯，并夺回广播中心的控制权。\n\n任务目标：\n- 摧毁敌方前沿基地（3个）\n- 最终摧毁敌方核心基地\n- 保护己方基地不被摧毁",
                map_name="广播中心",
                difficulty="NORMAL",
                objectives=[
                    {"text": "摧毁敌方前沿基地 Alpha", "completed": False},
                    {"text": "摧毁敌方前沿基地 Beta", "completed": False},
                    {"text": "摧毁敌方前沿基地 Gamma", "completed": False},
                    {"text": "摧毁敌方核心基地", "completed": False}
                ]
            ),
            CampaignMission(
                mission_id=2,
                title="第一关：前沿突破",
                subtitle="难度：普通",
                description="突破美军第一道防线！\n\n敌方在广播中心外围建立了三个前沿基地。\n它们负责保护核心基地的外围防线。\n消灭所有前沿基地的防御力量，\n为最终进攻做好准备。",
                map_name="广播中心",
                difficulty="NORMAL",
                objectives=[
                    {"text": "摧毁敌方前沿基地 Alpha", "completed": False, "base_type": "alpha"},
                    {"text": "摧毁敌方前沿基地 Beta", "completed": False, "base_type": "beta"},
                    {"text": "摧毁敌方前沿基地 Gamma", "completed": False, "base_type": "gamma"}
                ]
            ),
            CampaignMission(
                mission_id=3,
                title="第二关：核心决战",
                subtitle="难度：困难",
                description="决战时刻！\n\n清除所有前沿基地后，\n敌人的核心基地已经暴露。\n发起最后的进攻，摧毁敌方核心基地，\n夺回广播中心的控制权！",
                map_name="广播中心",
                difficulty="HARD",
                objectives=[
                    {"text": "摧毁敌方核心基地", "completed": False, "base_type": "core"}
                ]
            )
        ]

        self.missions[0].unlocked = True
        for i, m in enumerate(self.missions):
            self.mission_buttons.append(pygame.Rect(450, 150 + i * 120, 700, 100))

    def handle_input(self, events):
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()

        for event in events:
            if event.type == pygame.QUIT:
                self.game.running = False
                return

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if self.btn_back.collidepoint(mouse_pos):
                        self.game.state = "MENU"
                        return

                    for i, btn in enumerate(self.mission_buttons):
                        if i < len(self.missions):
                            mission = self.missions[i]
                            if btn.collidepoint(mouse_pos) and mission.unlocked:
                                self._start_mission(i)

                elif event.button == 4:
                    self.scroll_offset = max(0, self.scroll_offset - 30)
                elif event.button == 5:
                    content_height = len(self.missions) * 120 + 200
                    visible_height = SCREEN_HEIGHT - 200
                    self.max_scroll = max(0, content_height - visible_height)
                    self.scroll_offset = min(self.max_scroll, self.scroll_offset + 30)

    def _start_mission(self, index):
        self.current_mission_index = index
        mission = self.missions[index]

        for i, map_cls in enumerate(self.game.maps):
            if map_cls.name_static == mission.map_name or map_cls.name_cn_static == mission.map_name:
                self.game.map_id = i
                break

        self.game.reset_game()
        self.game.is_campaign = True
        self.game.campaign_mission = index
        self.game.campaign_objectives = [obj.copy() for obj in mission.objectives]

        self.game.state = "PLAYING"

    def update(self):
        if self.game.state != "WARSTORY":
            return

        if self.game.is_campaign and self.game.campaign_objectives:
            self._check_objectives()

    def _check_objectives(self):
        for obj in self.game.campaign_objectives:
            if obj.get("completed", False):
                continue

            base_type = obj.get("base_type")
            if base_type:
                for b in self.game.all_buildings:
                    if not b.alive:
                        continue
                    b_type = getattr(b, 'b_type', '')
                    b_category = getattr(b, 'category', '')

                    if base_type == "alpha" and b_type == "base" and b.team == "enemy":
                        if not hasattr(b, 'is_core_base'):
                            obj["completed"] = True
                            self.game.show_notification(f"目标完成：{obj['text']}")

                    elif base_type == "beta" and b_type == "base" and b.team == "enemy":
                        if hasattr(b, 'is_forward_base'):
                            obj["completed"] = True
                            self.game.show_notification(f"目标完成：{obj['text']}")

                    elif base_type == "gamma" and b_type == "base" and b.team == "enemy":
                        if hasattr(b, 'is_forward_base'):
                            obj["completed"] = True
                            self.game.show_notification(f"目标完成：{obj['text']}")

                    elif base_type == "core":
                        if b_type == "base" and b.team == "enemy" and getattr(b, 'is_core_base', False):
                            if not b.alive:
                                obj["completed"] = True
                                self.game.show_notification(f"目标完成：{obj['text']}")

    def draw(self, screen):
        self.bg_surface.fill((20, 15, 10))
        screen.blit(self.bg_surface, (0, 0))

        panel_width = 400
        panel = pygame.Surface((panel_width, SCREEN_HEIGHT), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 180))
        screen.blit(panel, (0, 0))

        title = self.font_title.render(self.current_campaign["title"], True, YELLOW)
        screen.blit(title, (40, 40))

        subtitle = self.font_subtitle.render(self.current_campaign["subtitle"], True, ORANGE)
        screen.blit(subtitle, (40, 110))

        desc_text = self.font_desc.render(tr("ws.select"), True, WHITE)
        screen.blit(desc_text, (40, 170))

        mouse_pos = pygame.mouse.get_pos()

        for i, btn in enumerate(self.mission_buttons):
            if i >= len(self.missions):
                continue

            mission = self.missions[i]
            adjusted_btn = pygame.Rect(btn.x, btn.y - self.scroll_offset, btn.width, btn.height)

            if not adjusted_btn.colliderect(pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)):
                continue

            hover = adjusted_btn.collidepoint(mouse_pos) and mission.unlocked

            bg_color = (60, 80, 60) if hover else (40, 50, 40)
            if not mission.unlocked:
                bg_color = (30, 30, 30)
            elif mission.completed:
                bg_color = (50, 70, 50)

            pygame.draw.rect(screen, bg_color, adjusted_btn, border_radius=8)

            border_color = YELLOW if hover else (80, 80, 80)
            if mission.completed:
                border_color = GREEN_HAT
            pygame.draw.rect(screen, border_color, adjusted_btn, 2, border_radius=8)

            title_s = self.font_btn.render(mission.title, True, WHITE if mission.unlocked else (100, 100, 100))
            screen.blit(title_s, (adjusted_btn.x + 20, adjusted_btn.y + 15))

            sub_s = self.font_small.render(mission.subtitle, True, ORANGE if mission.unlocked else (80, 80, 80))
            screen.blit(sub_s, (adjusted_btn.x + 20, adjusted_btn.y + 50))

            diff_color = { "EASY": GREEN_HAT, "NORMAL": YELLOW, "HARD": RED }.get(mission.difficulty, WHITE)
            diff_s = self.font_small.render(f"[{mission.difficulty}]", True, diff_color)
            screen.blit(diff_s, (adjusted_btn.right - 100, adjusted_btn.y + 50))

            if not mission.unlocked:
                lock_s = self.font_btn.render("🔒", True, (100, 100, 100))
                screen.blit(lock_s, (adjusted_btn.centerx - 20, adjusted_btn.centery - 15))
            elif mission.completed:
                stars = "⭐" * mission.stars if mission.stars > 0 else "✓"
                star_s = self.font_btn.render(stars, True, YELLOW)
                screen.blit(star_s, (adjusted_btn.centerx - 30, adjusted_btn.centery + 10))

        if self.game.is_campaign and self.game.campaign_objectives:
            self._draw_objectives(screen)

        hover_back = self.btn_back.collidepoint(mouse_pos)
        back_color = WHITE if hover_back else (150, 150, 150)
        back_s = self.font_btn.render(tr("ws.back"), True, back_color)
        screen.blit(back_s, (self.btn_back.x + 20, self.btn_back.y))

        pygame.display.flip()

    def _draw_objectives(self, screen):
        obj_y = 150
        obj_x = SCREEN_WIDTH - 350

        panel = pygame.Surface((320, 250), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 150))
        screen.blit(panel, (obj_x - 20, obj_y - 20))

        title_s = self.font_btn.render(tr("ws.objectives"), True, YELLOW)
        screen.blit(title_s, (obj_x, obj_y))

        obj_y += 45
        for obj in self.game.campaign_objectives:
            completed = obj.get("completed", False)
            color = GREEN_HAT if completed else WHITE
            prefix = "✓ " if completed else "○ "
            text = prefix + obj["text"]

            lines = self._wrap_text(text, self.font_objective, 280)
            for line in lines:
                s = self.font_objective.render(line, True, color)
                screen.blit(s, (obj_x, obj_y))
                obj_y += 22
            obj_y += 5

    def _wrap_text(self, text, font, max_width):
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + " " + word if current_line else word
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines if lines else [""]


class BreakthroughMode:
    def __init__(self, game):
        self.game = game
        self.phase = 1
        self.max_phases = 3
        self.bases_destroyed = 0
        self.required_bases = 3
        self.phase_transition_timer = 0
        self.phase_notification = ""
        self.notification_timer = 0

        self.enemy_spawn_bases = []
        self._setup_forward_bases()

    def _setup_forward_bases(self):
        if not hasattr(self.game, 'current_map'):
            return

        map_obj = self.game.current_map
        w, h = map_obj.width, map_obj.height

        forward_positions = [
            vec(w * 0.25, h * 0.25),
            vec(w * 0.75, h * 0.25),
            vec(w * 0.5, h * 0.5)
        ]

        for i, pos in enumerate(forward_positions):
            base_type = ["alpha", "beta", "gamma"][i]
            self.enemy_spawn_bases.append({
                "pos": pos,
                "type": base_type,
                "spawned": False,
                "spawn_timer": 1800 + i * 600
            })

        core_pos = vec(w * 0.5, h * 0.8)
        self.enemy_spawn_bases.append({
            "pos": core_pos,
            "type": "core",
            "spawned": False,
            "spawn_timer": 999999
        })

    def update(self):
        if self.game.state != "PLAYING":
            return

        if self.notification_timer > 0:
            self.notification_timer -= 1

        if self.phase_transition_timer > 0:
            self.phase_transition_timer -= 1
            if self.phase_transition_timer <= 0:
                self.phase += 1
                self._spawn_next_phase()

        self._check_base_destruction()
        self._spawn_enemy_units()

    def _check_base_destruction(self):
        for base_info in self.enemy_spawn_bases:
            if base_info["spawned"]:
                continue

            pos = base_info["pos"]
            for b in self.game.all_buildings:
                if not b.alive:
                    continue
                if b.pos.distance_to(pos) < 200:
                    if b.team == "neutral" or (b.team == "enemy" and getattr(b, 'b_type', '') == "base"):
                        base_info["spawned"] = True
                        b.is_forward_base = True if base_info["type"] != "core" else False
                        b.is_core_base = base_info["type"] == "core"
                        b.category = base_info["type"]

    def _spawn_enemy_units(self):
        for base_info in self.enemy_spawn_bases:
            if not base_info["spawned"]:
                continue

            base_info["spawn_timer"] -= 1

            if base_info["spawn_timer"] <= 0:
                self._spawn_units_at_base(base_info)
                spawn_interval = 900 if base_info["type"] == "core" else 1500
                base_info["spawn_timer"] = spawn_interval

    def _spawn_units_at_base(self, base_info):
        from units import Rifleman, RocketTrooper, Tank, ArmoredCar

        pos = base_info["pos"]
        team = "enemy"

        if base_info["type"] == "core":
            spawn_count = random.randint(4, 6)
            unit_types = [Rifleman, RocketTrooper, Tank, Tank, ArmoredCar]
        elif base_info["type"] == "gamma":
            spawn_count = random.randint(2, 3)
            unit_types = [Rifleman, RocketTrooper, ArmoredCar]
        else:
            spawn_count = random.randint(1, 2)
            unit_types = [Rifleman, RocketTrooper]

        for _ in range(spawn_count):
            offset = vec(random.randint(-100, 100), random.randint(-100, 100))
            spawn_pos = pos + offset
            u_type = random.choice(unit_types)
            unit = u_type(self.game, spawn_pos, team)
            self.game.all_units.append(unit)

    def _spawn_next_phase(self):
        if self.phase > self.max_phases:
            return

        self.phase_notification = f"阶段 {self.phase} 开始！"
        self.notification_timer = 180

        for i, base_info in enumerate(self.enemy_spawn_bases):
            if i == self.phase - 1:
                base_info["spawned"] = False
                base_info["spawn_timer"] = 0

    def check_victory(self):
        forward_bases = [b for b in self.enemy_spawn_bases if b["type"] != "core"]
        core_base = [b for b in self.enemy_spawn_bases if b["type"] == "core"][0]

        if all(b["spawned"] and not self._base_alive(b) for b in forward_bases):
            if core_base["spawned"] and not self._base_alive(core_base):
                return "VICTORY"

        return None

    def _base_alive(self, base_info):
        pos = base_info["pos"]
        for b in self.game.all_buildings:
            if b.alive and b.pos.distance_to(pos) < 200:
                if b.team == "enemy":
                    return True
        return False

    def draw_notification(self, screen):
        if self.notification_timer > 0 and self.phase_notification:
            alpha = min(255, self.notification_timer * 5)
            font = get_font(48)

            text_s = font.render(self.phase_notification, True, (255, 200, 0))
            text_rect = text_s.get_rect(center=(SCREEN_WIDTH // 2, 150))

            notification_surf = pygame.Surface((text_rect.width + 40, text_rect.height + 20), pygame.SRCALPHA)
            notification_surf.fill((0, 0, 0, alpha // 2))
            pygame.draw.rect(notification_surf, (200, 150, 0, alpha), notification_surf.get_rect(), 2)

            screen.blit(notification_surf, (text_rect.x - 20, text_rect.y - 10))
            screen.blit(text_s, text_rect)

    def draw_phase_info(self, screen):
        font = get_font(24)
        info = f"阶段: {self.phase}/{self.max_phases}"
        s = font.render(info, True, WHITE)
        screen.blit(s, (20, 20))


class WarStoryUI:
    def __init__(self, game):
        self.game = game
        self.campaign_manager = CampaignManager(game)
        self.breakthrough_mode = None

        self.bg_image = None
        try:
            path = resource_path("picture/warstorybg1.png")
            img = pygame.image.load(path).convert()
            self.bg_image = pygame.transform.scale(img, (SCREEN_WIDTH, SCREEN_HEIGHT))
        except:
            self.bg_image = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            self.bg_image.fill((30, 20, 10))

        self.panel_rect = pygame.Rect(0, 0, 400, SCREEN_HEIGHT)
        self.panel_surf = pygame.Surface((400, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.panel_surf.fill((0, 0, 0, 200))

        try:
            path = resource_path("fonts/simhei.ttf")
            self.font_title = pygame.font.Font(path, 60)
            self.font_desc = pygame.font.Font(path, 24)
            self.font_btn = pygame.font.Font(path, 30)
        except:
            self.font_title = get_font(60)
            self.font_desc = get_font(24)
            self.font_btn = get_font(30)

        self.btn_start = pygame.Rect(50, 500, 200, 50)
        self.btn_back = pygame.Rect(50, 600, 200, 50)

        self.story_title = "在更了在更了"
        self.story_desc = "在更了在更了"

    def handle_input(self, events=None):
        if events is None:
            events = pygame.event.get()

        if self.game.state == "WARSTORY":
            self.campaign_manager.handle_input(events)

        for event in events:
            if event.type == pygame.QUIT:
                self.game.running = False

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                m_pos = pygame.mouse.get_pos()

                if self.game.state == "WARSTORY":
                    if self.btn_start.collidepoint(m_pos) or self.btn_back.collidepoint(m_pos):
                        pass
                    else:
                        return

                if self.btn_start.collidepoint(m_pos):
                    print("Start Campaign Mission 1")
                    self.game.reset_game()
                    self.game.state = "WARSTORY"

                elif self.btn_back.collidepoint(m_pos):
                    self.game.state = "MENU"

    def update(self):
        if self.game.state == "WARSTORY":
            self.campaign_manager.update()

            if self.game.is_campaign:
                if self.breakthrough_mode is None:
                    self.breakthrough_mode = BreakthroughMode(self.game)

                self.breakthrough_mode.update()

                victory = self.breakthrough_mode.check_victory()
                if victory == "VICTORY":
                    self.game.show_victory_screen()
                elif victory == "DEFEAT":
                    self.game.show_defeat_screen()

    def draw(self, screen):
        if self.game.state == "WARSTORY":
            self.campaign_manager.draw(screen)

            if self.breakthrough_mode:
                self.breakthrough_mode.draw_phase_info(screen)
                self.breakthrough_mode.draw_notification(screen)
        else:
            if self.bg_image:
                screen.blit(self.bg_image, (0, 0))

            screen.blit(self.panel_surf, (0, 0))

            title_s = self.font_title.render(self.story_title, True, YELLOW)
            screen.blit(title_s, (40, 80))

            self.draw_multiline_text(screen, self.story_desc, self.font_desc, (40, 180), WHITE)

            self.draw_btn(screen, self.btn_start, "START MISSION")
            self.draw_btn(screen, self.btn_back, "BACK TO MENU")

        pygame.display.flip()

    def draw_btn(self, screen, rect, text):
        m_pos = pygame.mouse.get_pos()
        hover = rect.collidepoint(m_pos)

        color = WHITE if hover else (180, 180, 180)
        txt_s = self.font_btn.render(text, True, color)
        screen.blit(txt_s, (rect.x + 20, rect.y))

        if hover:
            pygame.draw.rect(screen, ORANGE, (rect.x, rect.y + 5, 5, 30))

    def draw_multiline_text(self, surface, text, font, pos, color):
        x, y = pos
        lines = text.split('\n')
        line_h = font.get_linesize()

        for line in lines:
            s = font.render(line, True, color)
            surface.blit(s, (x, y))
            y += line_h