from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import pygame

from external.pplay.window import Window

from src.system.audio import Audio
from src.system.input import Input
from src.system.services import GameServices


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
		self.audio = Audio()
		self.running = False
		self.current_scene: SceneContract | None = None
		self.services: GameServices | None = None

	def initialize(self) -> None:
		self.window = Window(self.width, self.height)
		self.window.set_title(self.title)
		self.window.set_background_color(list(self.background_color))

		assets_dir = Path(__file__).resolve().parent.parent / "assets"
		images_dir = assets_dir / "images"
		fonts_dir = assets_dir / "fonts"
		font_path = fonts_dir / "Monogram.ttf"

		self.services = GameServices(
			assets_dir=assets_dir,
			images_dir=images_dir,
			fonts_dir=fonts_dir,
			font_path=font_path,
		)

		icon_path = Path(__file__).resolve().parent.parent / "assets" / "images" / "icon.ico"

		if icon_path.exists():
			try:
				icon_surface = pygame.image.load(str(icon_path))
				pygame.display.set_icon(icon_surface)
			except pygame.error:
				pass

		self.input = Input()
		# Use the Keyboard/Mouse objects created by Window.
		window_cls: Any = Window
		
		self.input.keyboard = window_cls.get_keyboard()
		self.input.mouse = window_cls.get_mouse()

		pygame.mouse.set_visible(False)
		self.input.mouse.hide()

	def set_scene(self, scene: SceneContract) -> None:
		self.current_scene = scene

	def stop(self) -> None:
		self.running = False

	def handle_events(self) -> None:
		if self.input is None:
			return

		if self.input.keyboard.key_pressed("ESC"):
			self.stop()

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
