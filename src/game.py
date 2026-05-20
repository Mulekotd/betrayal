from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from external.pplay.window import Window

from src.system.audio import Audio
from src.system.input import Input
from src.utils.services import GameServices


class SceneContract(Protocol):
    def handle_events(self, input_manager: Input | None) -> None:
        ...

    def update(self, dt: float, input_manager: Input | None) -> None:
        ...

    def render(self, window: Any) -> None:
        ...


class Game:
    def __init__(
        self,
        width: int,
        height: int,
        title: str,
        fps: int,
        background_color: tuple[int, int, int] = (15, 20, 30),
    ) -> None:
        self.width = width
        self.height = height
        self.title = title
        self.fps = fps
        self.background_color = background_color

        self.window: Any | None = None

        self.input: Input | None = None
        self.audio: Audio | None = None
        self.running = False
        self.current_scene: SceneContract | None = None
        self.services: GameServices | None = None

    def initialize(self, native_width: int | None = None, native_height: int | None = None) -> None:
        self.window = Window(self.width, self.height)
        self.window.set_title(self.title)
        self.window.set_background_color(list(self.background_color))

        if native_width and native_height:
            import pygame
            pygame.display.set_mode(
                (native_width, native_height),
                pygame.DOUBLEBUF | pygame.HWSURFACE | pygame.RESIZABLE
            )
            self.window.real_screen = pygame.display.get_surface()

        assets_dir = Path(__file__).resolve().parent / "assets"
        images_dir = assets_dir / "images"
        fonts_dir = assets_dir / "fonts"
        font_path = fonts_dir / "Kenney Mini.ttf"
        if not font_path.exists():
            font_path = fonts_dir / "Monogram.ttf"

        self.services = GameServices(
            assets_dir=assets_dir,
            images_dir=images_dir,
            fonts_dir=fonts_dir,
            font_path=font_path,
        )

        self.audio = Audio()

        icon_path = assets_dir / "images" / "icon.ico"
        theme_path = assets_dir / "sounds" / "theme.ogg"

        if icon_path.exists():
            self.window.set_icon(icon_path)

        if theme_path.exists():
            theme_key = "theme"
            self.audio.load_sound(theme_key, str(theme_path))

            if theme_key in self.audio._sounds:
                self.audio.play_sound(theme_key, repeat=True)
            else:
                self.audio.load_music(str(theme_path), key=theme_key)
                self.audio.play_music(repeat=True)

        self.input = Input()
        window_cls: Any = Window

        self.input.keyboard = window_cls.get_keyboard()
        self.input.mouse = window_cls.get_mouse()

    def set_scene(self, scene: SceneContract) -> None:
        self.current_scene = scene

    def stop(self) -> None:
        self.running = False

    def handle_events(self) -> None:
        if self.input is None:
            return

        if self.current_scene is not None:
            self.current_scene.handle_events(self.input)

    def update(self, dt: float) -> None:
        if self.current_scene is not None:
            self.current_scene.update(dt, self.input)

    def render(self) -> None:
        if self.window is None:
            return

        self.window.set_background_color(list(self.background_color))

        if self.current_scene is not None:
            self.current_scene.render(self.window)

        self.window.update()

    def loop(self) -> None:
        if self.window is None:
            self.initialize()

        self.running = True

        while self.running:
            if self.window is None:
                break

            dt = self.window.delta_time()

            self.handle_events()
            self.update(dt)
            self.render()

            if self.fps > 0:
                self.window.delay(int(1000 / self.fps))
