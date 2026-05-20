from external.pplay.window import Window

from src.game import Game
from src.scenes.menu_scene import MenuScene


def main() -> None:
    screen_w, screen_h = 1280, 720

    game = Game(width=screen_w, height=screen_h, title="Betrayal", fps=60)
    game.initialize(native_width=screen_w, native_height=screen_h)

    if game.services is None:
        raise RuntimeError("Game services not initialized.")

    game.set_scene(
        MenuScene(
            game=game,
            services=game.services,
            world_width=game.width,
            world_height=game.height
        )
    )

    game.loop()


if __name__ == "__main__":
    main()
