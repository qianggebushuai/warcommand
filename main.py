import pygame

from controllers.camera_mixin import CameraMixin
from controllers.input_mixin import InputMixin
from game.core_mixin import GameCoreMixin
from game.menu_mixin import MenuMixin
from game.level_mixin import LevelMixin
from game.spawner_mixin import SpawnerMixin
from game.world_mixin import WorldMixin
from game.render_mixin import RenderMixin
from game.net_mixin import NetMixin


class Game(GameCoreMixin, CameraMixin, InputMixin, MenuMixin, LevelMixin,
           SpawnerMixin, WorldMixin, RenderMixin, NetMixin):
    """主游戏类：由各职责 Mixin 组装而成（方法体与拆分前逐字一致）。"""


if __name__ == "__main__":
    game = Game()
    game.run()
