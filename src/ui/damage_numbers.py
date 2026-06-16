from __future__ import annotations

from typing import Any

from src.utils.window import get_screen


class DamageNumbers:
	def __init__(self, font: Any) -> None:
		self.font = font
		self.items: list[dict[str, object]] = []
		self._cache: dict[tuple[str, tuple[int, int, int]], tuple[Any, Any]] = {}

	def spawn(self, amount: int, x: float, y: float, color: tuple[int, int, int]) -> None:
		self.items.append({
			"text": str(amount),
			"x": x,
			"y": y,
			"vy": -135.0,
			"life": 0.30,
			"max_life": 0.30,
			"color": color
		})

	def update(self, dt: float) -> None:
		if not self.items:
			return

		survivors: list[dict[str, object]] = []
		for item in self.items:
			item["life"] = float(item["life"]) - dt
			if float(item["life"]) <= 0.0:
				continue

			item["y"] = float(item["y"]) + float(item["vy"]) * dt
			survivors.append(item)

		self.items = survivors

	def draw(self, camera_x: float, camera_y: float) -> None:
		if not self.items:
			return

		screen = get_screen()
		screen_width = screen.get_width()
		screen_height = screen.get_height()

		for item in self.items:
			text = str(item["text"])
			color = item["color"]

			surf, shadow = self._surfaces(text, color)

			life = float(item["life"])
			max_life = float(item["max_life"])

			alpha = max(0, min(255, int(255 * (life / max_life))))
			surf.set_alpha(alpha)
			shadow.set_alpha(alpha)

			x = int(float(item["x"]) - camera_x - surf.get_width() * 0.5)
			y = int(float(item["y"]) - camera_y)
			if x + surf.get_width() < 0 or x > screen_width or y + surf.get_height() < 0 or y > screen_height:
				continue

			screen.blit(shadow, (x + 1, y + 1))
			screen.blit(surf, (x, y))

	def _surfaces(self, text: str, color: tuple[int, int, int]):
		key = (text, color)

		cached = self._cache.get(key)
		if cached is not None:
			return cached

		surf = self.font.render(text, False, color)
		shadow = self.font.render(text, False, (0, 0, 0))
		self._cache[key] = (surf, shadow)

		return surf, shadow
