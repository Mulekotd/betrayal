from __future__ import annotations

import math


class StatusEffects:
	def __init__(self) -> None:
		self.reset()

	def reset(self) -> None:
		self.burning_time_left = 0.0
		self.burning_dps = 0.0
		self.frozen_time_left = 0.0
		self.slow_time_left = 0.0
		self.slow_multiplier = 1.0
		self.thaw_slow_multiplier = 1.0
		self.thaw_slow_time_left = 0.0

	def is_burning(self) -> bool:
		return self.burning_time_left > 0.0

	def is_frozen(self) -> bool:
		return self.frozen_time_left > 0.0

	def is_slowed(self) -> bool:
		return self.slow_time_left > 0.0 and self.slow_multiplier < 1.0

	def burn_flash_visible(self, blink_rate: float = 10.0) -> bool:
		if not self.is_burning():
			return False

		return math.floor(self.burning_time_left * max(1.0, float(blink_rate))) % 2 == 0

	def speed_multiplier(self) -> float:
		if self.is_frozen():
			return 0.0

		return self.slow_multiplier

	def ignite(self, dps: float, duration: float = 3.0) -> None:
		self.burning_dps = max(0.0, float(dps))
		self.burning_time_left = max(0.0, float(duration))

	def freeze(
		self,
		duration: float = 3.0,
		thaw_slow_multiplier: float = 0.5,
		thaw_slow_duration: float = 3.0
	) -> None:
		self.frozen_time_left = max(0.0, float(duration))
		self.thaw_slow_multiplier = max(0.0, min(1.0, float(thaw_slow_multiplier)))
		self.thaw_slow_time_left = max(0.0, float(thaw_slow_duration))

	def slow(self, multiplier: float, duration: float) -> None:
		multiplier = max(0.0, min(1.0, float(multiplier)))
		duration = max(0.0, float(duration))
		if duration <= 0.0:
			return

		self.slow_multiplier = min(self.slow_multiplier, multiplier)
		self.slow_time_left = max(self.slow_time_left, duration)

	def update(self, dt: float) -> float:
		dt = max(0.0, float(dt))
		if dt <= 0.0:
			return 0.0

		burn_damage = 0.0
		if self.burning_time_left > 0.0:
			burn_tick = min(dt, self.burning_time_left)
			self.burning_time_left = max(0.0, self.burning_time_left - dt)
			burn_damage = self.burning_dps * burn_tick

			if self.burning_time_left <= 0.0:
				self.burning_dps = 0.0

		if self.frozen_time_left > 0.0:
			self.frozen_time_left = max(0.0, self.frozen_time_left - dt)
			if self.frozen_time_left <= 0.0 and self.thaw_slow_time_left > 0.0:
				self.slow(self.thaw_slow_multiplier, self.thaw_slow_time_left)
				self.thaw_slow_multiplier = 1.0
				self.thaw_slow_time_left = 0.0

		if self.slow_time_left > 0.0:
			self.slow_time_left = max(0.0, self.slow_time_left - dt)
			if self.slow_time_left <= 0.0:
				self.slow_multiplier = 1.0

		return burn_damage
