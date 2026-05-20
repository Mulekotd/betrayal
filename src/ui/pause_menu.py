from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.utils.window import blit_surface, create_surface, draw_rect, get_screen, set_mouse_visible


@dataclass
class PauseButton:
	label: str
	x: int
	y: int
	width: int
	height: int
	action: Callable[[], None]

	def contains(self, x: float, y: float) -> bool:
		return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height


class PauseMenu:
	def __init__(self, width: int, height: int, title_font, button_font) -> None:
		self.width = width
		self.height = height
		self.title_font = title_font
		self.button_font = button_font
		self.active = False
		self.hover_index: int | None = None
		self.buttons: list[PauseButton] = []
		self._overlay = create_surface(width, height, alpha=True)
		self._overlay.fill((0, 0, 0, 125))

	def set_actions(self, resume: Callable[[], None], options: Callable[[], None], quit_game: Callable[[], None]) -> None:
		labels = [("VOLTAR", resume), ("OPCOES", options), ("SAIR", quit_game)]
		button_w = 260
		button_h = 48
		gap = 14
		start_x = (self.width - button_w) // 2
		start_y = int(self.height * 0.42)
		self.buttons = [
			PauseButton(label, start_x, start_y + index * (button_h + gap), button_w, button_h, action)
			for index, (label, action) in enumerate(labels)
		]

	def open(self) -> None:
		self.active = True
		set_mouse_visible(True)

	def close(self) -> None:
		self.active = False
		set_mouse_visible(False)

	def toggle(self) -> None:
		if self.active:
			self.close()
		else:
			self.open()

	def update(self, input_manager) -> None:
		if not self.active or input_manager is None:
			return

		mouse = input_manager.mouse
		mx, my = mouse.get_position()

		self.hover_index = None
		for index, button in enumerate(self.buttons):
			if button.contains(mx, my):
				self.hover_index = index
				if mouse.button_down(mouse.LEFT):
					button.action()
				return

	def draw(self) -> None:
		if not self.active:
			return

		screen = get_screen()

		blit_surface(self._overlay, (0, 0), target=screen)

		title = self.title_font.render("PAUSADO", False, (245, 245, 235))
		screen.blit(title, ((self.width - title.get_width()) // 2, int(self.height * 0.25)))

		for index, button in enumerate(self.buttons):
			hover = index == self.hover_index
			fill = (44, 52, 62) if hover else (24, 30, 38)
			border = (245, 210, 120) if hover else (100, 112, 124)

			draw_rect(fill, (button.x, button.y, button.width, button.height), target=screen)
			draw_rect(border, (button.x, button.y, button.width, button.height), width=2, target=screen)

			text = self.button_font.render(button.label, False, (245, 245, 235))
			screen.blit(
				text,
				(
					button.x + (button.width - text.get_width()) // 2,
					button.y + (button.height - text.get_height()) // 2
				),
			)
