from dataclasses import dataclass
import math
from typing import Callable


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


class Slash:
	def __init__(
		self,
		x: float,
		y: float,
		dir_x: float,
		dir_y: float,
		arc_deg: float,
		radius: float,
		damage: int,
		duration: float,
		color: tuple[int, int, int],
		line_width: int = 6,
		delay: float = 0.0,
		on_hit: Callable[[object, int, "Slash"], None] | None = None,
	) -> None:
		self.x = x
		self.y = y
		self.dir_x = dir_x
		self.dir_y = dir_y
		self.arc_deg = arc_deg
		self.radius = radius
		self.damage = damage
		self.duration = duration
		self.color = color
		self.line_width = max(1, int(line_width))
		self.on_hit = on_hit
		self.life_left = max(0.0, duration)
		self.delay_left = max(0.0, delay)
		self.hit_ids: set[int] = set()

	def update(self, dt: float) -> None:
		if self.delay_left > 0.0:
			self.delay_left = max(0.0, self.delay_left - dt)
			return

		self.life_left = max(0.0, self.life_left - dt)

	def is_alive(self) -> bool:
		return self.life_left > 0.0 or self.delay_left > 0.0

	def is_active(self) -> bool:
		return self.delay_left <= 0.0 and self.life_left > 0.0

	def alpha(self) -> int:
		if self.duration <= 0.0 or not self.is_active():
			return 0

		ratio = max(0.0, min(1.0, self.life_left / self.duration))
		return int(220 * ratio)


class Sword(Slash):
	def __init__(
		self,
		name: str,
		base_damage: int,
		cooldown: float,
		radius: float,
		duration: float,
		color: tuple[int, int, int],
		arc_deg: float = 135.0,
		forward_offset: float = 18.0,
		line_width: int = 6,
		strength_scale: float = 1.7,
		hits_per_attack: int = 1,
		hit_delay: float = 0.06,
		attack_speed_mult: float = 1.0,
	) -> None:
		super().__init__(
			x=0.0,
			y=0.0,
			dir_x=1.0,
			dir_y=0.0,
			arc_deg=arc_deg,
			radius=radius,
			damage=base_damage,
			duration=0.0,
			color=color,
			line_width=line_width,
		)

		self.name = name
		self.base_damage = base_damage
		self.cooldown = cooldown
		self.radius = radius
		self.duration = duration
		self.color = color
		self.arc_deg = arc_deg
		self.forward_offset = forward_offset
		self.line_width = line_width
		self.strength_scale = strength_scale
		self.hits_per_attack = max(1, hits_per_attack)
		self.hit_delay = max(0.0, hit_delay)
		self.attack_speed_mult = max(0.1, attack_speed_mult)

	def get_cooldown(self, attack_speed: float) -> float:
		attack_speed = max(0.1, attack_speed)
		return max(0.05, self.cooldown / attack_speed / self.attack_speed_mult)

	def compute_damage(self, strength: int) -> int:
		return max(1, int(self.base_damage + strength * self.strength_scale))

	def spawn_slashes(self, player: object) -> list[Slash]:
		dir_x, dir_y = getattr(player, "facing", (1.0, 0.0))
		length = math.hypot(dir_x, dir_y)
		if length <= 0.0001:
			dir_x, dir_y = 1.0, 0.0
		else:
			dir_x /= length
			dir_y /= length

		center = getattr(player, "center", (0.0, 0.0))
		radius = float(getattr(player, "radius", 0.0))
		origin_x = center[0] + dir_x * (radius + self.forward_offset)
		origin_y = center[1] + dir_y * (radius + self.forward_offset)

		strength = int(getattr(player, "attributes", {}).get("strength", 1))
		damage = self.compute_damage(strength)

		return [
			Slash(
				x=origin_x,
				y=origin_y,
				dir_x=dir_x,
				dir_y=dir_y,
				arc_deg=self.arc_deg,
				radius=self.radius,
				damage=damage,
				duration=self.duration,
				color=self.color,
				line_width=self.line_width,
				delay=index * self.hit_delay,
				on_hit=self.on_hit,
			)
			for index in range(self.hits_per_attack)
		]

	def on_hit(self, enemy: object, player_strength: int, slash: Slash) -> None:
		_ = (enemy, player_strength, slash)


class FireSword(Sword):
	def __init__(self) -> None:
		super().__init__(
			name="fire",
			base_damage=19,
			cooldown=0.72,
			radius=82.0,
			duration=0.22,
			color=(255, 140, 80),
			attack_speed_mult=1.05,
		)

		self.burn_duration = 2.4
		self.burn_damage_ratio = 0.22
		self.burn_strength_scale = 0.30

	def on_hit(self, enemy: object, player_strength: int, slash: Slash) -> None:
		apply_burn = getattr(enemy, "apply_burn", None)
		if not callable(apply_burn):
			return

		dps = int((slash.damage * self.burn_damage_ratio) + (player_strength * self.burn_strength_scale))
		apply_burn(max(1, dps), self.burn_duration)


class IceSword(Sword):
	def __init__(self) -> None:
		super().__init__(
			name="ice",
			base_damage=20,
			cooldown=0.78,
			radius=96.0,
			duration=0.24,
			color=(140, 200, 255),
			attack_speed_mult=1.0,
		)

		self.slow_factor = 0.62
		self.slow_duration = 1.6
		self.combo_window = 1.35
		self.combo_bonus_step = 4
		self.combo_bonus_cap = 16
		self.combo_strength_scale = 0.25
		self.freeze_hits = 5
		self.freeze_duration = 1.2

	def on_hit(self, enemy: object, player_strength: int, slash: Slash) -> None:
		combo_stacks = int(getattr(enemy, "ice_hits", 0))

		apply_slow = getattr(enemy, "apply_slow", None)
		if callable(apply_slow):
			apply_slow(self.slow_factor, self.slow_duration)

		if combo_stacks > 0:
			extra_damage = min(
				self.combo_bonus_cap,
				int(combo_stacks * self.combo_bonus_step + player_strength * self.combo_strength_scale)
			)
			take_damage = getattr(enemy, "take_damage", None)
			if callable(take_damage):
				take_damage(max(1, extra_damage))

		register_hit = getattr(enemy, "register_ice_hit", None)
		if callable(register_hit):
			register_hit(self.freeze_hits, self.freeze_duration, self.combo_window)


class WindSword(Sword):
	def __init__(self) -> None:
		super().__init__(
			name="wind",
			base_damage=7,
			cooldown=0.64,
			radius=120.0,
			duration=0.18,
			color=(170, 240, 210),
			strength_scale=1.25,
			hits_per_attack=2,
			hit_delay=0.07,
			attack_speed_mult=1.15,
		)
