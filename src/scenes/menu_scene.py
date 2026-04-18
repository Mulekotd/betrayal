from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, cast

import pygame

from external.pplay.gameimage import GameImage
from external.pplay.window import Window

from src.engine.game import Game
from src.scenes.game_scene import GameScene


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
	def __init__(self, game: Game, world_width: int, world_height: int) -> None:
		self.game = game
		self.world_width = world_width
		self.world_height = world_height

		assets_dir = Path(__file__).resolve().parent.parent / "assets" / "images"
		self.logo = GameImage(str(assets_dir / "logo.png"))
		self.logo_scale = 0.5
		self.logo_padding = 24
		self.logo_button_gap = 28
		self.logo.scale_x = self.logo_scale
		self.logo.scale_y = self.logo_scale

		center_x = world_width // 2
		button_width = 260
		button_height = 56
		start_y = int(world_height * 0.48)
		gap = 18

		self.buttons = [
			MenuButton(
				label="START",
				x=center_x - button_width // 2,
				y=start_y,
				width=button_width,
				height=button_height,
				action=self._start_game,
			),
			MenuButton(
				label="OPTIONS",
				x=center_x - button_width // 2,
				y=start_y + button_height + gap,
				width=button_width,
				height=button_height,
				action=self._placeholder,
			),
			MenuButton(
				label="QUIT",
				x=center_x - button_width // 2,
				y=start_y + (button_height + gap) * 2,
				width=button_width,
				height=button_height,
				action=self._quit_game,
			),
		]

		self._hover_index: int | None = None

	def handle_events(self, input_manager) -> None:
		_ = input_manager

	def update(self, dt: float, input_manager) -> None:
		_ = dt
		mouse = input_manager.mouse if input_manager is not None else self._get_window().mouse
		mx, my = mouse.get_position()

		self._hover_index = None
		
		for index, button in enumerate(self.buttons):
			if button.contains(mx, my):
				self._hover_index = index

				if mouse.button_down(mouse.LEFT):
					button.action()
				break

	def render(self, window) -> None:
		screen = self._get_screen()
		screen.fill((20, 12, 14))
		self._draw_logo()
		self._draw_buttons(window)

	def _draw_logo(self) -> None:
		logo_w = int(self.logo.width * self.logo_scale)
		logo_h = int(self.logo.height * self.logo_scale)
		
		logo_x = (self.world_width - logo_w) // 2
		logo_y = max(self.logo_padding, self.buttons[0].y - logo_h - self.logo_button_gap)

		self.logo.set_position(logo_x, logo_y)
		self.logo.draw()

	def _draw_buttons(self, window) -> None:
		for index, button in enumerate(self.buttons):
			is_hover = index == self._hover_index
			
			fill_color = (66, 86, 168) if is_hover else (54, 72, 140)
			border_color = (220, 190, 110) if is_hover else (180, 150, 90)

			screen = self._get_screen()

			pygame.draw.rect(
				screen,
				fill_color,
				(button.x, button.y, button.width, button.height),
				border_radius=8,
			)

			pygame.draw.rect(
				screen,
				border_color,
				(button.x, button.y, button.width, button.height),
				2,
				border_radius=8,
			)

			window.draw_text(
				button.label,
				button.x + button.width // 2 - 36,
				button.y + 16,
				size=24,
				color=(255, 255, 255),
				font_name="Arial",
			)

	def _start_game(self) -> None:
		self.game.set_scene(GameScene(world_width=self.world_width, world_height=self.world_height))

	def _quit_game(self) -> None:
		self._get_window().close()

	def _placeholder(self) -> None:
		pass

	def _get_screen(self) -> pygame.Surface:
		screen = Window.get_screen()

		if screen is None:
			raise RuntimeError("Window screen is not initialized.")

		return screen

	def _get_window(self) -> Window:
		window = cast(Window, Window.get_instance())
		
		if window is None:
			raise RuntimeError("Window instance is not initialized.")

		return window
