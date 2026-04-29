from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pygame

from external.pplay.gameimage import GameImage

from src.game import Game
from src.scenes.game_scene import GameScene
from src.utils.services import GameServices
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

		self._mx_norm = 0.0
		self._my_norm = 0.0

		logo_path = self.services.images_dir / "logo.png"
		target_logo_width = int(self.world_width * 0.38)
		
		self.logo = GameImage(str(logo_path))
		self.logo_scale = target_logo_width / max(1, int(self.logo.width))
		self.logo.scale_x = self.logo_scale
		self.logo.scale_y = self.logo_scale
		self.logo_surface, self.logo_glow_surface = self._build_logo_layers()

		self.menu_font = self.services.fonts.get(74)
		self.menu_color = (120, 210, 235)
		self.menu_hover_color = (170, 235, 255)
		self.menu_shadow_color = (20, 60, 76)
		self.menu_glow_color = (80, 180, 205)

		self.background_base_layer = self._build_background_surface()
		self.background_blur_layer = self._build_blurred_layer(self.background_base_layer, downscale=0.18, passes=2)
		self.background_depth_layer = self._build_depth_layer()
		self.ui_layer_surface = pygame.Surface((self.world_width, self.world_height), pygame.SRCALPHA).convert_alpha()

		padding = 64
		gap = 8

		start_x = padding
		start_y = int(self.world_height * 0.34)

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

		self._mx_norm = ((mx / max(1, self.world_width)) - 0.5) * 2.0
		self._my_norm = ((my / max(1, self.world_height)) - 0.5) * 2.0
		button_offset_x, button_offset_y = self._button_layer_offset()

		self._hover_index = None
		for index, button in enumerate(self.buttons):
			left = button.x + button_offset_x
			top = button.y + button_offset_y
			right = left + button.width
			bottom = top + button.height

			if left <= mx <= right and top <= my <= bottom:
				self._hover_index = index
				if mouse.button_down(mouse.LEFT):
					button.action()
				break

	def render(self, window: Any) -> None:
		_ = window
		screen = get_screen()
		screen.blit(self.background_base_layer, (0, 0))
		screen.blit(self.background_blur_layer, (0, 0))
		screen.blit(self.background_depth_layer, (0, 0))

		self.ui_layer_surface.fill((0, 0, 0, 0))
		self._draw_logo(self.ui_layer_surface)
		self._draw_buttons(self.ui_layer_surface)
		screen.blit(self.ui_layer_surface, (0, 0))

	def _build_background_surface(self) -> pygame.Surface:
		surface = pygame.Surface((self.world_width, self.world_height))

		top_color = (2, 8, 14)
		bottom_color = (52, 126, 140)

		for y in range(self.world_height):
			t = y / max(1, self.world_height - 1)

			color = (
				int(top_color[0] + (bottom_color[0] - top_color[0]) * t),
				int(top_color[1] + (bottom_color[1] - top_color[1]) * t),
				int(top_color[2] + (bottom_color[2] - top_color[2]) * t),
			)

			pygame.draw.line(surface, color, (0, y), (self.world_width, y))

		haze = pygame.Surface((self.world_width, self.world_height), pygame.SRCALPHA)
		glow_center = (int(self.world_width * 0.34), int(self.world_height * 0.80))
		max_radius = int(max(self.world_width, self.world_height) * 0.58)

		for radius in range(max_radius, 0, -8):
			t = radius / max(1, max_radius)

			alpha = int((1.0 - t) * (1.0 - t) * 100)
			if alpha <= 0:
				continue

			pygame.draw.circle(haze, (90, 205, 225, alpha), glow_center, radius)

		surface.blit(haze, (0, 0))

		top_shadow = pygame.Surface((self.world_width, self.world_height), pygame.SRCALPHA)
		shadow_height = int(self.world_height * 0.48)

		for y in range(shadow_height):
			t = y / max(1, shadow_height - 1)
			alpha = int((1.0 - t) * 105)
			pygame.draw.line(top_shadow, (0, 0, 0, alpha), (0, y), (self.world_width, y))

		surface.blit(top_shadow, (0, 0))
		return surface

	def _build_blurred_layer(self, source: pygame.Surface, downscale: float = 0.2, passes: int = 2) -> pygame.Surface:
		width, height = source.get_size()
		small_size = (
			max(1, int(width * downscale)),
			max(1, int(height * downscale)),
		)

		blurred = source.copy()
		for _ in range(max(1, passes)):
			blurred = pygame.transform.smoothscale(blurred, small_size)
			blurred = pygame.transform.smoothscale(blurred, (width, height))

		blurred = blurred.convert_alpha()
		blurred.set_alpha(132)

		return blurred

	def _build_depth_layer(self) -> pygame.Surface:
		overlay = pygame.Surface((self.world_width, self.world_height), pygame.SRCALPHA)
		horizon_height = int(self.world_height * 0.50)

		for y in range(horizon_height):
			t = y / max(1, horizon_height - 1)
			alpha = int((1.0 - t) * 112)

			pygame.draw.line(overlay, (0, 0, 0, alpha), (0, y), (self.world_width, y))

		return overlay

	def _build_logo_layers(self) -> tuple[pygame.Surface, pygame.Surface]:
		logo_w = max(1, int(self.logo.width * self.logo_scale))
		logo_h = max(1, int(self.logo.height * self.logo_scale))

		mask = pygame.mask.from_surface(self.logo.image)

		flat_logo = mask.to_surface(
			setcolor=(103, 210, 232, 255),
			unsetcolor=(0, 0, 0, 0),
		).convert_alpha()

		supersample = 3

		high_w = max(1, logo_w * supersample)
		high_h = max(1, logo_h * supersample)
		high_logo = pygame.transform.scale(flat_logo, (high_w, high_h))

		scaled_logo = pygame.transform.smoothscale(high_logo, (logo_w, logo_h)).convert_alpha()
		scaled_mask = pygame.mask.from_surface(scaled_logo)

		glow_surface = scaled_mask.to_surface(
			setcolor=(90, 210, 230, 90),
			unsetcolor=(0, 0, 0, 0),
		).convert_alpha()

		return scaled_logo, glow_surface

	def _draw_logo(self, target: pygame.Surface) -> None:
		logo_w = self.logo_surface.get_width()
		logo_h = self.logo_surface.get_height()
		logo_x = int(self.world_width * 0.50)
		logo_y = int(self.world_height * 0.35)

		logo_x = min(max(32, logo_x), self.world_width - logo_w - 32)
		logo_y = min(max(32, logo_y), self.world_height - logo_h - 32)
		logo_x += int(self._mx_norm * 10.0)
		logo_y += int(self._my_norm * 8.0)

		for ox, oy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2)):
			target.blit(self.logo_glow_surface, (logo_x + ox, logo_y + oy))

		target.blit(self.logo_surface, (logo_x, logo_y))

	def _draw_buttons(self, target: pygame.Surface) -> None:
		offset_x, offset_y = self._button_layer_offset()

		for index, button in enumerate(self.buttons):
			is_hover = index == self._hover_index
			draw_x = button.x + offset_x
			draw_y = button.y + offset_y

			color = self.menu_hover_color if is_hover else self.menu_color
			glow = self.menu_shadow_color
			glow_color = self.menu_glow_color

			glow_surface = self.menu_font.render(button.label, True, glow_color)
			for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
				target.blit(glow_surface, (draw_x + ox, draw_y + oy))

			shadow_surface = self.menu_font.render(button.label, True, glow)
			target.blit(shadow_surface, (draw_x + 2, draw_y + 2))

			text_surface = self.menu_font.render(button.label, True, color)
			target.blit(text_surface, (draw_x, draw_y))

	def _button_layer_offset(self) -> tuple[int, int]:
		return (int(self._mx_norm * 6.0), int(self._my_norm * 4.0))

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
