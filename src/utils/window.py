import pygame

from external.pplay.window import Window


def get_screen() -> pygame.Surface:
    screen = Window.get_screen()

    if screen is None:
        raise RuntimeError("Window screen is not initialized.")

    return screen


def get_window() -> Window:
    window = Window.get_instance()

    if window is None:
        raise RuntimeError("Window instance is not initialized.")

    return window