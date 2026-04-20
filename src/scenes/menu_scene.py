from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, cast

import pygame

from external.pplay.gameimage import GameImage

from src.engine.game import Game
from src.scenes.game_scene import GameScene
from src.system.services import GameServices
from src.utils.window import get_screen, get_window


@dataclass
class MenuButton:
	label: str
	x: int
	y: int
	width: int
	height: int
	action: Callable[[], None]

	def contains(self, mx: float, my: float) -> bool:
		return self.x <= mx <= self.x + self.width and self.y <= my <= self.y + self.height


class MenuScene:
	def __init__(self, game: Game, services: GameServices, world_width: int, world_height: int) -> None:
		self.game = game
		self.services = services
		self.world_width = world_width
		self.world_height = world_height

		logo_path = self.services.images_dir / "logo_lg.png"

		if not logo_path.exists():
			logo_path = self.services.images_dir / "logo.png"

		self.logo = GameImage(str(logo_path))
		self.logo_scale = 0.78
		self.logo.scale_x = self.logo_scale
		self.logo.scale_y = self.logo_scale

		self.menu_font = self.services.fonts.get(50)
		self.menu_color = (120, 210, 235)
		self.menu_hover_color = (170, 235, 255)
		self.menu_shadow_color = (45, 85, 105)

		padding = 32
		start_x = padding
		start_y = padding
		gap = 12

		labels = [
			("PLAY", self._start_game),
			("OPTIONS", self._placeholder),
			("QUIT", self._quit_game),
		]

		self.buttons = []
		cursor_y = start_y

		for label, action in labels:
			surface = self.menu_font.render(label, True, (255, 255, 255))

			self.buttons.append(
				MenuButton(
					label=label,
					x=start_x,
					y=cursor_y,
					width=surface.get_width(),
					height=surface.get_height(),
					action=action,
				)
			)

			cursor_y += surface.get_height() + gap

		self._hover_index: int | None = None

	def handle_events(self, input_manager) -> None:
		_ = input_manager

	def update(self, dt: float, input_manager) -> None:
		_ = dt
		mouse = input_manager.mouse if input_manager is not None else get_window().mouse
		mx, my = mouse.get_position()

		self._hover_index = None
		for index, button in enumerate(self.buttons):
			if button.contains(mx, my):
				self._hover_index = index
				if mouse.button_down(mouse.LEFT):
					button.action()
				break

	def render(self, window: Any) -> None:
		_ = window
		screen = get_screen()

		screen.fill((10, 16, 20))
		self._draw_background_haze()
		self._draw_logo()
		self._draw_buttons()

	def _draw_background_haze(self) -> None:
		screen = get_screen()

		haze = pygame.Surface((self.world_width, self.world_height), pygame.SRCALPHA)
		pygame.draw.circle(haze, (40, 90, 110, 120), (int(self.world_width * 0.35), int(self.world_height * 0.6)), int(self.world_width * 0.55))
		screen.blit(haze, (0, 0))

	def _draw_logo(self) -> None:
		logo_w = int(self.logo.width * self.logo_scale)
		logo_x = self.world_width - logo_w - 32
		logo_y = 32
		self.logo.set_position(logo_x, logo_y)
		self.logo.draw()

	def _draw_buttons(self) -> None:
		for index, button in enumerate(self.buttons):
			is_hover = index == self._hover_index
			screen = get_screen()

			color = self.menu_hover_color if is_hover else self.menu_color
			glow = self.menu_shadow_color

			shadow_surface = self.menu_font.render(button.label, True, glow)
			screen.blit(shadow_surface, (button.x + 2, button.y + 2))
			text_surface = self.menu_font.render(button.label, True, color)
			screen.blit(text_surface, (button.x, button.y))

	def _start_game(self) -> None:
		self.game.set_scene(
			GameScene(
				services=self.services,
				world_width=self.world_width,
				world_height=self.world_height,
			)
		)

	def _quit_game(self) -> None:
		get_window().close()

	def _placeholder(self) -> None:
		pass
