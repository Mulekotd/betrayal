from __future__ import annotations

from dataclasses import dataclass

from src.utils.types import ColorRGB, FontLike, SurfaceLike
from src.utils.window import get_screen


@dataclass(slots=True)
class DamageNumber:
	text: str
	x: float
	y: float
	velocity_y: float
	life: float
	max_life: float
	color: ColorRGB


class DamageNumbers:
	def __init__(self, font: FontLike) -> None:
		self.font = font
		self.items: list[DamageNumber] = []
		self._cache: dict[tuple[str, ColorRGB], tuple[SurfaceLike, SurfaceLike]] = {}

	def spawn(self, amount: int, x: float, y: float, color: ColorRGB) -> None:
		self.items.append(
			DamageNumber(
				text=str(amount),
				x=x,
				y=y,
				velocity_y=-135.0,
				life=0.30,
				max_life=0.30,
				color=color,
			)
		)

	def update(self, dt: float) -> None:
		if not self.items:
			return

		survivors: list[DamageNumber] = []
		for item in self.items:
			item.life -= dt
			if item.life <= 0.0:
				continue

			item.y += item.velocity_y * dt
			survivors.append(item)

		self.items = survivors

	def draw(self, camera_x: float, camera_y: float) -> None:
		if not self.items:
			return

		screen = get_screen()
		screen_width = screen.get_width()
		screen_height = screen.get_height()

		for item in self.items:
			surface, shadow = self._surfaces(item.text, item.color)
			alpha = max(0, min(255, int(255 * (item.life / item.max_life))))

			surface.set_alpha(alpha)
			shadow.set_alpha(alpha)

			draw_x = int(item.x - camera_x - surface.get_width() * 0.5)
			draw_y = int(item.y - camera_y)
			if (
				draw_x + surface.get_width() < 0
				or draw_x > screen_width
				or draw_y + surface.get_height() < 0
				or draw_y > screen_height
			):
				continue

			screen.blit(shadow, (draw_x + 1, draw_y + 1))
			screen.blit(surface, (draw_x, draw_y))

	def _surfaces(self, text: str, color: ColorRGB) -> tuple[SurfaceLike, SurfaceLike]:
		key = (text, color)
		cached = self._cache.get(key)
		if cached is not None:
			return cached

		surface = self.font.render(text, False, color)
		shadow = self.font.render(text, False, (0, 0, 0))
		cached = (surface, shadow)
		self._cache[key] = cached
		return cached
