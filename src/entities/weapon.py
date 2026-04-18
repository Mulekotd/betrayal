from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Weapon:
	name: str
	damage: int
	attack_radius: float

	def apply(self, enemy: object, damage: int | None = None) -> bool:
		damage_fn = getattr(enemy, "take_damage", None)

		if not callable(damage_fn):
			return False

		damage_fn(self.damage if damage is None else damage)

		return True


@dataclass
class FireWeapon(Weapon):
	burn_dps: float = 0.0
	burn_duration: float = 0.0

	def apply(self, enemy: object, damage: int | None = None) -> bool:
		return self.apply_with_damage(enemy, damage=damage)

	def apply_with_damage(self, enemy: object, damage: int | None = None) -> bool:
		if not super().apply(enemy, damage=damage):
			return False
		burn_fn = getattr(enemy, "apply_burn", None)
		if callable(burn_fn) and self.burn_duration > 0:
			burn_fn(self.burn_dps, self.burn_duration)
		return True


@dataclass
class IceWeapon(Weapon):
	slow_factor: float = 1.0
	slow_duration: float = 0.0
	freeze_hits: int = 0
	freeze_duration: float = 0.0

	def apply(self, enemy: object, damage: int | None = None) -> bool:
		return self.apply_with_damage(enemy, damage=damage)

	def apply_with_damage(self, enemy: object, damage: int | None = None) -> bool:
		if not super().apply(enemy, damage=damage):
			return False

		slow_fn = getattr(enemy, "apply_slow", None)

		if callable(slow_fn) and self.slow_duration > 0:
			slow_fn(self.slow_factor, self.slow_duration)

		freeze_fn = getattr(enemy, "register_ice_hit", None)

		if callable(freeze_fn) and self.freeze_hits > 0:
			freeze_fn(self.freeze_hits, self.freeze_duration)

		return True


@dataclass
class WindWeapon(Weapon):
	def apply(self, enemy: object, damage: int | None = None) -> bool:
		return self.apply_with_damage(enemy, damage=damage)

	def apply_with_damage(self, enemy: object, damage: int | None = None) -> bool:
		return super().apply(enemy, damage=damage)
