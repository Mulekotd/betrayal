from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.game import Game
from src.system.input import Input
from src.utils.rect import Rect
from src.utils.services import GameServices
from src.utils.window import draw_circle, draw_line, draw_rect, get_screen, set_mouse_visible


@dataclass
class SettingsButton:
	label: str
	rect: Rect
	action: Callable[[], None]

	def contains(self, x: float, y: float) -> bool:
		return self.rect.left <= x <= self.rect.right and self.rect.top <= y <= self.rect.bottom


class SettingsScene:
	def __init__(
		self,
		game: Game,
		services: GameServices,
		world_width: int,
		world_height: int,
		on_back: Callable[[], None]
	) -> None:
		self.game = game
		self.services = services
		self.world_width = world_width
		self.world_height = world_height
		self.on_back = on_back

		self.title_font = self.services.fonts.title(58)
		self.label_font = self.services.fonts.mini(30)
		self.value_font = self.services.fonts.mini(24)
		self.button_font = self.services.fonts.mini(30)

		self.volume = self._current_volume()
		self.dragging_volume = False
		self.hover_back = False

		slider_w = min(520, int(self.world_width * 0.46))
		slider_x = (self.world_width - slider_w) // 2
		slider_y = int(self.world_height * 0.48)
		self.slider_rect = Rect(slider_x, slider_y, slider_w, 8)

		button_w = 220
		button_h = 48
		self.back_button = SettingsButton(
			"VOLTAR",
			Rect((self.world_width - button_w) // 2, int(self.world_height * 0.64), button_w, button_h),
			self._back,
		)

		set_mouse_visible(True)

	def handle_events(self, input_manager: Input | None) -> None:
		if input_manager is not None and input_manager.keyboard.key_down("ESC"):
			self._back()

	def update(self, dt: float, input_manager: Input | None) -> None:
		_ = dt
		if input_manager is None:
			return

		mouse = input_manager.mouse
		mx, my = mouse.get_position()
		self.hover_back = self.back_button.contains(mx, my)

		if mouse.button_down(mouse.LEFT):
			if self.hover_back:
				self.back_button.action()
				return

			if self._slider_hit_test(mx, my):
				self.dragging_volume = True
				self._set_volume_from_x(mx)

		if self.dragging_volume:
			if mouse.button_pressed(mouse.LEFT):
				self._set_volume_from_x(mx)
			else:
				self.dragging_volume = False

	def render(self) -> None:
		screen = get_screen()
		screen.fill((8, 12, 18))

		self._draw_background()
		self._draw_title()
		self._draw_volume_slider()
		self._draw_back_button()

	def _current_volume(self) -> int:
		if self.game.audio is None:
			return 50

		return self.game.audio.get_volume()

	def _back(self) -> None:
		self.dragging_volume = False
		self.on_back()

	def _set_volume_from_x(self, x: float) -> None:
		ratio = (x - self.slider_rect.left) / max(1.0, self.slider_rect.width)
		self.volume = max(0, min(100, int(round(ratio * 100))))

		if self.game.audio is not None:
			self.game.audio.set_volume(self.volume)

	def _slider_hit_test(self, x: float, y: float) -> bool:
		hit = self.slider_rect.inflate(28, 28)
		return hit.left <= x <= hit.right and hit.top <= y <= hit.bottom

	def _draw_background(self) -> None:
		screen = get_screen()

		top_color = (5, 13, 20)
		bottom_color = (28, 74, 82)

		for y in range(self.world_height):
			t = y / max(1, self.world_height - 1)

			color = (
				int(top_color[0] + (bottom_color[0] - top_color[0]) * t),
				int(top_color[1] + (bottom_color[1] - top_color[1]) * t),
				int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
			)

			draw_line(color, (0, y), (self.world_width, y), target=screen)

	def _draw_title(self) -> None:
		screen = get_screen()

		title = self.title_font.render("CONFIGURAÇÕES", False, (245, 245, 235))
		screen.blit(title, ((self.world_width - title.get_width()) // 2, int(self.world_height * 0.20)))

	def _draw_volume_slider(self) -> None:
		screen = get_screen()

		label = self.label_font.render("VOLUME", False, (245, 245, 235))
		value = self.value_font.render(f"{self.volume}%", False, (245, 210, 120))

		label_x = self.slider_rect.left
		label_y = self.slider_rect.top - label.get_height() - 18
		value_x = self.slider_rect.right - value.get_width()

		screen.blit(label, (int(label_x), int(label_y)))
		screen.blit(value, (int(value_x), int(label_y + 4)))

		draw_rect((18, 22, 28), self.slider_rect, target=screen)

		fill_w = int(self.slider_rect.width * (self.volume / 100.0))
		if fill_w > 0:
			draw_rect(
				(90, 205, 225),
				(self.slider_rect.left, self.slider_rect.top, fill_w, self.slider_rect.height),
				target=screen
			)

		draw_rect((100, 112, 124), self.slider_rect, width=2, target=screen)

		knob_x = int(self.slider_rect.left + fill_w)
		knob_y = int(self.slider_rect.top + self.slider_rect.height // 2)

		draw_circle((10, 14, 20), (knob_x, knob_y), 13, target=screen)
		draw_circle((245, 210, 120), (knob_x, knob_y), 10, target=screen)

	def _draw_back_button(self) -> None:
		screen = get_screen()

		rect = self.back_button.rect
		fill = (44, 52, 62) if self.hover_back else (24, 30, 38)
		border = (245, 210, 120) if self.hover_back else (100, 112, 124)

		draw_rect(fill, rect, target=screen)
		draw_rect(border, rect, width=2, target=screen)

		text = self.button_font.render(self.back_button.label, False, (245, 245, 235))
		screen.blit(
			text,
			(
				int(rect.left + (rect.width - text.get_width()) // 2),
				int(rect.top + (rect.height - text.get_height()) // 2)
			)
		)
