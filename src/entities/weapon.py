from __future__ import annotations

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
	armor_pierce: float = 0.0
	bonus_vs_defense: float = 0.0

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
		shape: str = "arc",
		on_hit: Callable[[object, int, "Slash"], None] | None = None,
		resolve_hit_damage: Callable[[object, int, "Slash"], int] | None = None,
		owner: object | None = None,
		owner_is_player: bool = False
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
		self.shape = shape
		self.on_hit = on_hit
		self.resolve_hit_damage = resolve_hit_damage
		self.owner = owner
		self.owner_is_player = bool(owner_is_player)
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
		strength_scale: float = 1.5,
		hits_per_attack: int = 1,
		hit_delay: float = 0.06,
		attack_speed_mult: float = 1.0,
		move_speed_mult: float = 1.0,
		shape: str = "arc"
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
			shape=shape
		)
		del self.on_hit
		del self.resolve_hit_damage

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
		self.move_speed_mult = max(0.1, move_speed_mult)
		self.shape = shape

	def get_cooldown(self, attack_speed: float) -> float:
		return max(0.05, self.cooldown / max(0.1, attack_speed))

	def get_attack_speed_multiplier(self) -> float:
		return self.attack_speed_mult

	def get_move_speed_multiplier(self) -> float:
		return self.move_speed_mult

	def get_defense_multiplier(self) -> float:
		return 1.0

	def get_health_regen_multiplier(self) -> float:
		return 1.0

	def compute_damage(self, strength: int) -> int:
		return max(1, int(round(self.base_damage + strength * self.strength_scale)))

	def resolve_hit_damage(self, target: object, player_strength: int, slash: Slash) -> int:
		_ = (target, player_strength)
		return max(1, int(slash.damage))

	def spawn_slashes(self, owner: object) -> list[Slash]:
		dir_x, dir_y = getattr(owner, "facing", (1.0, 0.0))
		length = math.hypot(dir_x, dir_y)

		if length <= 0.0001:
			dir_x, dir_y = 1.0, 0.0
		else:
			dir_x /= length
			dir_y /= length

		center = getattr(owner, "center", (0.0, 0.0))
		radius = float(getattr(owner, "radius", 0.0))
		if self.shape == "circle":
			origin_x = center[0]
			origin_y = center[1]
		else:
			origin_x = center[0] + dir_x * (radius + self.forward_offset)
			origin_y = center[1] + dir_y * (radius + self.forward_offset)

		strength = int(getattr(owner, "attributes", {}).get("strength", 1))
		damage = self.compute_damage(strength)
		on_hit = type(self).on_hit.__get__(self, type(self))
		resolve_hit_damage = type(self).resolve_hit_damage.__get__(self, type(self))

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
				shape=self.shape,
				on_hit=on_hit,
				resolve_hit_damage=resolve_hit_damage,
				owner=owner,
				owner_is_player=not hasattr(owner, "enemy_type")
			)
			for index in range(self.hits_per_attack)
		]

	def on_hit(self, target: object, player_strength: int, slash: Slash) -> None:
		_ = (target, player_strength, slash)


class FireSword(Sword):
	def __init__(self) -> None:
		super().__init__(
			name="fire",
			base_damage=24,
			cooldown=0.82,
			radius=86.0,
			duration=0.22,
			color=(255, 140, 80),
			strength_scale=2.3
		)

		self.burn_duration = 3.0
		self.burn_dps_ratio = 0.35
		self.knight_bonus_multiplier = 1.35
		self.regen_multiplier = 2.0

	def get_health_regen_multiplier(self) -> float:
		return self.regen_multiplier

	def resolve_hit_damage(self, target: object, player_strength: int, slash: Slash) -> int:
		_ = player_strength
		damage = max(1, int(slash.damage))

		if bool(getattr(target, "is_burning", lambda: False)()):
			burn_multiplier = 1.5 if str(getattr(target, "enemy_type", "")) == "boss" else 2.0
			damage = int(round(damage * burn_multiplier))

		if str(getattr(target, "enemy_type", "")) == "knight":
			damage = int(round(damage * self.knight_bonus_multiplier))

		return max(1, damage)

	def on_hit(self, target: object, player_strength: int, slash: Slash) -> None:
		_ = player_strength
		ignite = getattr(target, "ignite", None)
		if not callable(ignite):
			return

		burn_dps = max(1, int(round(slash.damage * self.burn_dps_ratio)))
		ignite(burn_dps, self.burn_duration)


class IceSword(Sword):
	def __init__(self) -> None:
		super().__init__(
			name="ice",
			base_damage=16,
			cooldown=0.86,
			radius=96.0,
			duration=0.24,
			color=(140, 200, 255),
			strength_scale=1.6
		)

		self.freeze_duration = 3.0
		self.thaw_slow_multiplier = 0.45
		self.thaw_slow_duration = 3.0
		self.defense_multiplier = 2.0

	def get_defense_multiplier(self) -> float:
		return self.defense_multiplier

	def resolve_hit_damage(self, target: object, player_strength: int, slash: Slash) -> int:
		_ = player_strength
		damage = max(1, int(slash.damage))

		if bool(getattr(target, "is_frozen", lambda: False)()):
			damage *= 2

		return max(1, damage)

	def on_hit(self, target: object, player_strength: int, slash: Slash) -> None:
		_ = (player_strength, slash)
		freeze = getattr(target, "freeze", None)
		if not callable(freeze):
			return

		freeze(
			duration=self.freeze_duration,
			thaw_slow_multiplier=self.thaw_slow_multiplier,
			thaw_slow_duration=self.thaw_slow_duration
		)


class WindSword(Sword):
	def __init__(self) -> None:
		super().__init__(
			name="wind",
			base_damage=3,
			cooldown=0.78,
			radius=122.0,
			duration=0.18,
			color=(170, 240, 210),
			strength_scale=0.45,
			hits_per_attack=3,
			hit_delay=0.05,
			attack_speed_mult=1.25,
			move_speed_mult=1.25,
			shape="circle"
		)
