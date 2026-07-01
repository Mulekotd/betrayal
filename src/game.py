from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from external.pplay.window import Window

from src.system.audio import Audio
from src.system.input import Input
from src.utils.services import GameServices
from src.utils.types import SurfaceLike
from src.utils.window import blit_surface, enable_custom_cursor, get_screen, is_mouse_visible, load_image


class SceneContract(Protocol):
	def handle_events(self, input_manager: Input | None) -> None: ...
	def update(self, dt: float, input_manager: Input | None) -> None: ...
	def render(self) -> None: ...


@dataclass(frozen=True)
class SoundConfig:
	key: str
	path: Path
	volume: float


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

		self.window: Window | None = None
		self.input: Input | None = None
		self.audio: Audio | None = None
		self.running = False
		self.current_scene: SceneContract | None = None
		self.services: GameServices | None = None
		self.cursor_surface: SurfaceLike | None = None
		self.cursor_hotspot = (0, 0)

	def initialize(self, native_width: int | None = None, native_height: int | None = None) -> None:
		self.window = Window(self.width, self.height)
		self.window.set_title(self.title)
		self.window.set_background_color(list(self.background_color))

		if native_width and native_height and (native_width != self.width or native_height != self.height):
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
			font_path=font_path,
		)
		self.audio = Audio()

		self._configure_window_assets(assets_dir)
		self._load_audio_assets(assets_dir / "sounds")

		self.input = Input()
		self.input.keyboard = self.window.keyboard
		self.input.mouse = self.window.mouse

	def set_scene(self, scene: SceneContract) -> None:
		self.current_scene = scene

	def stop(self) -> None:
		self.running = False

	def handle_events(self) -> None:
		if self.input is not None and self.current_scene is not None:
			self.current_scene.handle_events(self.input)

	def update(self, dt: float) -> None:
		if self.audio is not None:
			self.audio.pump()

		if self.current_scene is not None:
			self.current_scene.update(dt, self.input)

	def render(self) -> None:
		if self.window is None:
			return

		self.window.set_background_color(list(self.background_color))
		if self.current_scene is not None:
			self.current_scene.render()
		self._draw_cursor()
		self.window.update(self.fps)

	def _configure_window_assets(self, assets_dir: Path) -> None:
		if self.window is None:
			return

		icons_dir = assets_dir / "images"
		for icon_name in ("icon.ico", "favicon.ico"):
			icon_path = icons_dir / icon_name
			if icon_path.exists():
				self.window.set_icon(icon_path)
				break

		cursor_path = icons_dir / "cursor.png"
		self.cursor_surface = load_image(cursor_path, alpha=True) if cursor_path.exists() else None
		enable_custom_cursor(self.cursor_surface is not None)

	def _load_audio_assets(self, sounds_dir: Path) -> None:
		if self.audio is None:
			return

		sound_configs = (
			SoundConfig("theme", sounds_dir / "theme.ogg", 1.0),
			SoundConfig("fire_slash", sounds_dir / "fire_slash.ogg", 2.0),
			SoundConfig("ice_slash", sounds_dir / "ice_slash.ogg", 0.5),
			SoundConfig("wind_slash", sounds_dir / "wind_slash.ogg", 0.25),
		)

		for config in sound_configs:
			if not config.path.exists():
				continue

			# Centralizamos o carregamento para manter volumes e chaves consistentes.
			self.audio.load_sound(config.key, str(config.path), volume=config.volume)

	def _draw_cursor(self) -> None:
		if self.cursor_surface is None or self.input is None or not is_mouse_visible():
			return

		mouse_x, mouse_y = self.input.mouse.get_position()
		draw_x = int(mouse_x - self.cursor_hotspot[0])
		draw_y = int(mouse_y - self.cursor_hotspot[1])
		blit_surface(self.cursor_surface, (draw_x, draw_y), target=get_screen())

	async def loop(self) -> None:
		if self.window is None:
			self.initialize()

		self.running = True
		while self.running:
			if self.window is None:
				break

			delta_time = self.window.delta_time()
			self.handle_events()
			self.update(delta_time)
			self.render()
			await asyncio.sleep(0)
