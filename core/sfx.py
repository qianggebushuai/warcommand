import os
import random
import time
import pygame
from core.utils import resource_path


class SFXManager:
    """全局音效管理器：单例，按事件键播放；缺失文件静默跳过。"""
    _instance = None

    LIBRARY = {
        # UI
        "select": ["sfx/ui/select1.wav", "sfx/ui/select2.wav"],
        "click": ["sfx/ui/click1.wav", "sfx/ui/click2.wav"],
        # 武器（键 = Projectile 的 d_type）
        "rifle": ["sfx/weapons/bullet1.ogg", "sfx/weapons/bullet2.ogg", "sfx/weapons/bullet3.ogg"],
        "bullet": ["sfx/weapons/bullet1.ogg", "sfx/weapons/bullet2.ogg", "sfx/weapons/bullet3.ogg"],
        "heavy": ["sfx/weapons/deep_heavy1.wav", "sfx/weapons/deep_heavy2.wav", "sfx/weapons/heavy1.ogg", "sfx/weapons/heavy2.ogg"],
        "heavy_shell": ["sfx/weapons/deep_heavy1.wav", "sfx/weapons/deep_heavy2.wav", "sfx/weapons/heavy1.ogg", "sfx/weapons/heavy2.ogg"],
        "tank_shell": ["sfx/weapons/deep_heavy1.wav", "sfx/weapons/deep_heavy2.wav", "sfx/weapons/heavy1.ogg", "sfx/weapons/heavy2.ogg"],
        "ac130": ["sfx/weapons/deep_heavy1.wav", "sfx/weapons/heavy1.ogg"],
        "rocket": ["sfx/weapons/rocket1.ogg", "sfx/weapons/rocket2.ogg"],
        "behemoth_bomb": ["sfx/weapons/rocket1.ogg"],
        "laser": ["sfx/weapons/laser1.ogg", "sfx/weapons/laser2.ogg"],
        "laser2": ["sfx/weapons/laser1.ogg", "sfx/weapons/laser2.ogg"],
        "flame": ["sfx/weapons/flame1.ogg"],
        "incendiary": ["sfx/weapons/flame1.ogg"],
        "fire_zone": ["sfx/weapons/flame1.ogg"],
        # 爆炸（键 = play_explosion 的死亡类型前缀 explo_）
        "explo_normal": ["sfx/explosions/deep_explo1.wav", "sfx/explosions/explo1.wav", "sfx/explosions/explo2.ogg", "sfx/explosions/explo3.ogg"],
        "explo_mech_death": ["sfx/explosions/explo_mech1.ogg", "sfx/explosions/explo_mech2.ogg"],
        "explo_air_crash": ["sfx/explosions/explo_air1.ogg", "sfx/explosions/explo_air2.ogg"],
    }

    # 移动音效：载具/飞机用循环音（专用通道），步兵用脚步一次性音
    MOVE_LOOPS = {
        "vehicle": "sfx/movement/engine_loop.ogg",
        "air": "sfx/movement/rotor_loop.mp3",
    }
    STEP_SOUNDS = ["sfx/movement/step1.ogg", "sfx/movement/step2.ogg", "sfx/movement/step3.ogg", "sfx/movement/step4.ogg"]

    MIN_INTERVAL = 0.04  # 同类音效最小间隔（秒），防止连发声爆音

    # 全局静音开关（True=所有音效不发声；挂机采集时建议开着）
    muted = True

    # 视野衰减：距相机中心 FULL_DIST 内全音量，向外线性衰减，CUTOFF_DIST 外不播放
    FULL_DIST = 800    # 世界单位
    CUTOFF_DIST = 2000
    listener = None    # 相机中心（世界坐标 vec），每帧由游戏主循环同步

    @classmethod
    def set_listener(cls, world_pos):
        cls.listener = world_pos

    def __init__(self):
        self.sounds = {}
        self._last_play = {}
        self._move_ch = {"vehicle": None, "air": None}
        self._step_timer = 0.0
        self.enabled = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.enabled = True
        except Exception:
            return
        for key, paths in self.LIBRARY.items():
            loaded = []
            for p in paths:
                full = resource_path(p)
                if os.path.isfile(full):
                    try:
                        loaded.append(pygame.mixer.Sound(full))
                    except Exception:
                        pass
            if loaded:
                self.sounds[key] = loaded
        for cat, p in self.MOVE_LOOPS.items():
            full = resource_path(p)
            if os.path.isfile(full):
                try:
                    self.sounds["move_" + cat] = pygame.mixer.Sound(full)
                except Exception:
                    pass
        steps = []
        for p in self.STEP_SOUNDS:
            full = resource_path(p)
            if os.path.isfile(full):
                try:
                    steps.append(pygame.mixer.Sound(full))
                except Exception:
                    pass
        if steps:
            self.sounds["step"] = steps

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def play(self, key, volume=1.0, pos=None):
        if not self.enabled or self.muted:
            return
        candidates = self.sounds.get(key)
        if not candidates:
            return
        # 视野衰减：按声源世界坐标与相机中心的距离调整音量，过远直接丢弃
        if pos is not None and SFXManager.listener is not None:
            try:
                d = pos.distance_to(SFXManager.listener)
            except Exception:
                d = None
            if d is not None:
                if d >= self.CUTOFF_DIST:
                    return
                if d > self.FULL_DIST:
                    volume *= 1.0 - (d - self.FULL_DIST) / (self.CUTOFF_DIST - self.FULL_DIST)
        now = time.time()
        if now - self._last_play.get(key, 0.0) < self.MIN_INTERVAL:
            return
        self._last_play[key] = now
        try:
            snd = random.choice(candidates)
            snd.set_volume(volume)
            snd.play()
        except Exception:
            pass

    def play_weapon(self, d_type, team=None, my_team=None, pos=None):
        """开火音：己方 0.5 音量，敌方再降 40%；按声源位置做视野衰减。"""
        volume = 0.5
        if my_team and team != my_team:
            volume *= 0.6
        self.play(d_type, volume, pos)

    def play_explosion(self, death_type="normal", pos=None):
        self.play("explo_" + death_type, 0.8, pos)

    def update_movement(self, counts, dt=1.0 / 60):
        """每帧调用。counts: {"infantry": n, "vehicle": n, "air": n}；
        载具/飞机按数量调循环音音量，步兵按节奏播脚步。传空即停。"""
        if not self.enabled or self.muted:
            return
        for cat in ("vehicle", "air"):
            n = counts.get(cat, 0)
            ch = self._move_ch.get(cat)
            if n <= 0:
                if ch and ch.get_busy():
                    ch.fadeout(300)
                self._move_ch[cat] = None
                continue
            snd = self.sounds.get("move_" + cat)
            if not snd:
                continue
            if ch is None or not ch.get_busy():
                try:
                    ch = snd.play(loops=-1, fade_ms=400)
                except Exception:
                    ch = None
                self._move_ch[cat] = ch
            if ch:
                ch.set_volume(min(0.55, 0.18 + n * 0.04))
        n_inf = counts.get("infantry", 0)
        if n_inf > 0 and self._step_timer <= 0 and self.sounds.get("step"):
            self._step_timer = 0.38
            self.play("step", min(0.45, 0.08 + n_inf * 0.03))
        self._step_timer -= dt

    def stop_all_loops(self):
        for cat, ch in self._move_ch.items():
            if ch and ch.get_busy():
                ch.stop()
            self._move_ch[cat] = None
