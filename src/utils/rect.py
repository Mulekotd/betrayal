from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Rect:
	left: float
	top: float
	width: float
	height: float

	@property
	def x(self) -> float:
		return self.left

	@x.setter
	def x(self, value: float) -> None:
		self.left = value

	@property
	def y(self) -> float:
		return self.top

	@y.setter
	def y(self, value: float) -> None:
		self.top = value

	@property
	def right(self) -> float:
		return self.left + self.width

	@property
	def bottom(self) -> float:
		return self.top + self.height

	@property
	def centerx(self) -> float:
		return self.left + self.width * 0.5

	@property
	def centery(self) -> float:
		return self.top + self.height * 0.5

	@property
	def center(self) -> tuple[float, float]:
		return (self.centerx, self.centery)

	def copy(self) -> Rect:
		return Rect(self.left, self.top, self.width, self.height)

	def inflate(self, delta_width: float, delta_height: float) -> Rect:
		new_width = self.width + delta_width
		new_height = self.height + delta_height
		new_left = self.left - delta_width * 0.5
		new_top = self.top - delta_height * 0.5
		return Rect(new_left, new_top, new_width, new_height)

	def colliderect(self, other: Rect) -> bool:
		return (
			self.left < other.right
			and self.right > other.left
			and self.top < other.bottom
			and self.bottom > other.top
		)

	def clamp_within(self, bounds: Rect) -> Rect:
		left = max(bounds.left, min(self.left, bounds.right - self.width))
		top = max(bounds.top, min(self.top, bounds.bottom - self.height))
		return Rect(left, top, self.width, self.height)