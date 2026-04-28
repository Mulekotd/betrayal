from __future__ import annotations


class Camera:
	def __init__(self, viewport_width: int, viewport_height: int) -> None:
		self.viewport_width = viewport_width
		self.viewport_height = viewport_height
		self.x = 0.0
		self.y = 0.0

	def follow(self, target_x: float, target_y: float) -> None:
		self.x = target_x - self.viewport_width * 0.5
		self.y = target_y - self.viewport_height * 0.5

	def world_to_screen(self, world_x: float, world_y: float) -> tuple[float, float]:
		return world_x - self.x, world_y - self.y
