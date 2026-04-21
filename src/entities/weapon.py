from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Arrow:
	x: float
	y: float
	vel_x: float
	vel_y: float
	angle_deg: float
	speed: float
	damage: int
	radius: float
	life_left: float

	def update(self, dt: float) -> None:
		self.x += self.vel_x * self.speed * dt
		self.y += self.vel_y * self.speed * dt
		self.life_left = max(0.0, self.life_left - dt)
