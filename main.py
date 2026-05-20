import pygame
from src.game import Game
from src.scenes.menu_scene import MenuScene


def main() -> None:
    pygame.init()
    info = pygame.display.Info()
    screen_w = info.current_w
    screen_h = info.current_h

    game_w = 1280
    game_h = 720

    game = Game(width=game_w, height=game_h, title="Betrayal", fps=60)
    game.initialize(native_width=screen_w, native_height=screen_h)

    if game.services is None:
        raise RuntimeError("Game services not initialized.")

    game.set_scene(
        MenuScene(
            game=game,
            services=game.services,
            world_width=game.width,
            world_height=game.height,
        )
    )

    game.loop()


if __name__ == "__main__":
    main()
