from __future__ import annotations

from pathlib import Path
from typing import Protocol

from external.pplay.window import Window

from src.system.audio import Audio
from src.system.input import Input
from src.utils.services import GameServices
from src.utils.window import blit_surface, enable_custom_cursor, get_screen, is_mouse_visible, load_image


class SceneContract(Protocol):
    def handle_events(self, input_manager: Input | None) -> None:
        ...

    def update(self, dt: float, input_manager: Input | None) -> None:
        ...

    def render(self) -> None:
        ...


class Game:
    def __init__(
        self,
        width: int,
        height: int,
        title: str,
        fps: int,
        background_color: tuple[int, int, int] = (15, 20, 30)
    ) -> None:
        self.width = width
        self.height = height
        self.title = title
        self.fps = fps
        self.background_color = background_color

        self.window: Window | None = None

        self.input: Input | None = None
        self.audio: Audio | None = None
        self.running = False
        self.current_scene: SceneContract | None = None
        self.services: GameServices | None = None
        self.cursor_surface = None
        self.cursor_hotspot = (0, 0)

    def initialize(self, native_width: int | None = None, native_height: int | None = None) -> None:
        self.window = Window(self.width, self.height)
        self.window.set_title(self.title)
        self.window.set_background_color(list(self.background_color))

        if native_width and native_height:
            self.window.set_native_size(native_width, native_height)

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
            font_path=font_path
        )

        self.audio = Audio()

        icon_path = assets_dir / "images" / "icon.ico"
        cursor_path = assets_dir / "images" / "cursor.png"
        theme_path = assets_dir / "sounds" / "theme.ogg"

        if icon_path.exists():
            self.window.set_icon(icon_path)

        self.cursor_surface = None

        if cursor_path.exists():
            self.cursor_surface = load_image(str(cursor_path), alpha=True)

        if self.cursor_surface is not None:
            self.cursor_hotspot = (0, 0)

        enable_custom_cursor(self.cursor_surface is not None)

        # Load theme and slash sound effects
        if theme_path.exists():
            theme_key = "theme"
            self.audio.load_sound(theme_key, str(theme_path), volume=1.0)

        sounds_dir = assets_dir / "sounds"
        slash_sounds = {
            "fire_slash": {
                "path": sounds_dir / "fire_slash.ogg",
                "volume": 2.0
            },
            "ice_slash": {
                "path": sounds_dir / "ice_slash.ogg",
                "volume": 0.5
            },
            "wind_slash": {
                "path": sounds_dir / "wind_slash.ogg",
                "volume": 0.25
            }
        }

        for sound_key, sound_config in slash_sounds.items():
            sound_path = sound_config["path"]
            sound_volume = float(sound_config["volume"])

            if sound_path.exists():
                self.audio.load_sound(sound_key, str(sound_path), volume=sound_volume)

        self.input = Input()
        self.input.keyboard = self.window.keyboard
        self.input.mouse = self.window.mouse

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
            self.current_scene.render()
        self._draw_cursor()

        self.window.update()

    def _draw_cursor(self) -> None:
        if self.cursor_surface is None or self.input is None or not is_mouse_visible():
            return

        mouse = self.input.mouse
        mouse_x, mouse_y = mouse.get_position()
        draw_x = int(mouse_x - self.cursor_hotspot[0])
        draw_y = int(mouse_y - self.cursor_hotspot[1])
        blit_surface(self.cursor_surface, (draw_x, draw_y), target=get_screen())

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
