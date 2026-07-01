import asyncio

import pygame

SCREEN_W, SCREEN_H = 1280, 720


def _is_web_runtime() -> bool:
    try:
        import platform

        return hasattr(platform, "window")
    except Exception:
        return False


def _preboot_web_display() -> None:
    if not _is_web_runtime():
        return

    try:
        surface = pygame.display.get_surface()
    except pygame.error:
        surface = None

    if surface is None:
        pygame.init()
        pygame.display.set_mode((SCREEN_W, SCREEN_H))


_preboot_web_display()

# Pygbag/SDL web needs the display opened before PPlay imports wrap pygame.
from src.game import Game
from src.scenes.menu_scene import MenuScene


def create_game() -> Game:
    screen_w, screen_h = SCREEN_W, SCREEN_H

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

    return game


game = create_game()


async def main() -> None:
    await game.loop()


asyncio.run(main())
