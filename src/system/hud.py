from __future__ import annotations

import pygame

from src.system.services import FontLibrary
from src.utils.window import get_screen

class HUD:
	def __init__(self, viewport_width: int, viewport_height: int, fonts: FontLibrary, padding: int = 0) -> None:
		self.viewport_width = viewport_width
		self.viewport_height = viewport_height
		self.padding = max(0, int(padding))
		self.font_small = fonts.get(22)

	def draw(self, player: object, total_kills: int) -> None:
		self._draw_xp_bar(player)
		self._draw_kills_counter(total_kills)

	def _draw_xp_bar(self, player: object) -> None:
		screen = get_screen()

		bar_margin = self.padding
		bar_height = 22
		bar_width = max(0, self.viewport_width - (bar_margin * 2))
		bar_x = bar_margin
		bar_y = bar_margin

		pygame.draw.rect(screen, (16, 18, 22), (bar_x, bar_y, bar_width, bar_height))

		xp_value = int(getattr(player, "xp", 0))
		xp_to_next = max(1, int(getattr(player, "xp_to_next", 1)))
		fill_ratio = min(1.0, max(0.0, xp_value / xp_to_next))
		fill_width = int(bar_width * fill_ratio)

		if fill_width > 0:
			pygame.draw.rect(screen, (30, 120, 255), (bar_x, bar_y, fill_width, bar_height))

		level = int(getattr(player, "level", 1))
		label = f"LV {level}"
		label_surface = self.font_small.render(label, True, (255, 255, 255))
		label_x = bar_x + bar_width - label_surface.get_width() - 8
		label_y = bar_y + (bar_height - label_surface.get_height()) // 2
		screen.blit(label_surface, (label_x, label_y))

	def _draw_kills_counter(self, total_kills: int) -> None:
		screen = get_screen()

		bar_margin = self.padding
		bar_height = 22

		label = f"Kills: {total_kills}"
		label_surface = self.font_small.render(label, True, (255, 255, 255))
		label_x = bar_margin
		label_y = bar_margin + bar_height + 6

		screen.blit(label_surface, (label_x, label_y))
