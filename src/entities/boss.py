import math
from pathlib import Path
from typing import Callable

from src.entities.enemy import Enemy, EnemyAction
from src.entities.weapon import FireSword, IceSword, Slash, Sword, WindSword


class Boss(Enemy):
	def __init__(self, sprite_path: str | Path) -> None:
		super().__init__(
			sprite_path=sprite_path,
			frame_width=0,
			frame_height=0,
			frame_gap=0,
			actions=["ATTACK_1", "ATTACK_2", "ATTACK_3", "DEATH", "IDLE", "WALK", "HIT"],
			frame_rate=120,
			base_health=3000,
			base_speed=102.0,
			base_damage=118,
			xp_value=320,
			armor=0.24
		)

		self.base_scale = 2.6
		self.set_scale(0.75)
		self.contact_damage = False
		self.enemy_type = "boss"
		self.attributes = {
			"strength": 0,
			"attack_speed": 1.0
		}
		self.facing = (1.0, 0.0)
		self.attack_timer = 0.0
		self.attack_anim_time_left = 0.0
		self.current_attack_action = ""
		self.attack_range = 136.0
		self.attack_cycle = [
			("ATTACK_1", "wind", 1.25, 0.10),
			("ATTACK_2", "fire", 1.65, 0.16),
			("ATTACK_3", "ice", 2.05, 0.22)
		]
		self.next_attack_index = 0
		self.sword_base_damages = {
			"wind": 105,
			"fire": 235,
			"ice": 170
		}
		self.swords = self._build_swords()

	def _build_swords(self) -> dict[str, Sword]:
		wind = WindSword()
		wind.base_damage = self.sword_base_damages["wind"]
		wind.strength_scale = 0.0
		wind.radius = 132.0
		wind.duration = 0.22
		wind.attack_speed_mult = 1.0

		fire = FireSword()
		fire.base_damage = self.sword_base_damages["fire"]
		fire.strength_scale = 0.0
		fire.radius = 104.0
		fire.duration = 0.24
		fire.burn_dps_ratio = 0.40

		ice = IceSword()
		ice.base_damage = self.sword_base_damages["ice"]
		ice.strength_scale = 0.0
		ice.radius = 116.0
		ice.duration = 0.26
		ice.thaw_slow_multiplier = 0.35

		return {
			"wind": wind,
			"fire": fire,
			"ice": ice
		}

	def spawn(self, x: float, y: float, speed_multiplier: float = 1.0) -> None:
		super().spawn(x, y, speed_multiplier=speed_multiplier)
		self.attack_timer = 0.0
		self.attack_anim_time_left = 0.0
		self.current_attack_action = ""
		self.next_attack_index = 0
		self.facing = (1.0, 0.0)

	def set_damage_multiplier(self, multiplier: float) -> None:
		super().set_damage_multiplier(multiplier)

		for sword_key, sword in self.swords.items():
			base_damage = self.sword_base_damages[sword_key]
			sword.base_damage = max(1, int(round(base_damage * self.damage_multiplier)))

	def take_damage(self, amount: int) -> None:
		reduced = int(amount * (1.0 - self.armor))
		self.health -= max(1, reduced)

		if self.health <= 0:
			self.health = 0
			self.current_attack_action = ""
			self.attack_anim_time_left = 0.0
			self._set_state(EnemyAction.DEATH)

	def freeze(
		self,
		duration: float = 3.0,
		thaw_slow_multiplier: float = 0.5,
		thaw_slow_duration: float = 3.0
	) -> None:
		self.slow(thaw_slow_multiplier, max(duration, thaw_slow_duration))

	def update_towards(
		self,
		target_x: float,
		target_y: float,
		dt: float,
		player: object | None = None,
		spawn_slash: Callable[[Slash], None] | None = None,
		move_target_x: float | None = None,
		move_target_y: float | None = None
	) -> None:
		self._update_statuses(dt)

		if self.health <= 0:
			self._set_state(EnemyAction.DEATH)
			return

		if self.is_frozen():
			self._set_state(EnemyAction.IDLE)
			return

		self.animation.update(int(dt * 1000))
		self.attack_timer = max(0.0, self.attack_timer - dt * self.status_effects.speed_multiplier())
		self.attack_anim_time_left = max(0.0, self.attack_anim_time_left - dt)

		cx, cy = self.center
		dx = target_x - cx
		dy = target_y - cy
		dist_sq = dx * dx + dy * dy

		if dist_sq > 0.000001:
			dist = math.sqrt(dist_sq)
			self.facing = (dx / dist, dy / dist)
			self.facing_dir = -1 if dx < 0 else 1
		else:
			dist = 0.0

		if self.attack_anim_time_left > 0.0 and self.current_attack_action:
			self._set_state(self._action_for_name(self.current_attack_action))
			return

		player_radius = float(getattr(player, "radius", 12.0))
		effective_attack_distance = max(self.attack_range, self.radius + player_radius + 18.0)

		if dist <= effective_attack_distance:
			if self.attack_timer <= 0.0 and spawn_slash is not None:
				self._perform_attack(spawn_slash)
			else:
				self._set_state(EnemyAction.IDLE)
			return

		move_x = target_x if move_target_x is None else move_target_x
		move_y = target_y if move_target_y is None else move_target_y
		move_dx = move_x - cx
		move_dy = move_y - cy
		move_dist_sq = move_dx * move_dx + move_dy * move_dy

		if move_dist_sq <= 0.000001:
			self._set_state(EnemyAction.IDLE)
			return

		inv_dist = 1.0 / math.sqrt(move_dist_sq)
		speed = self.speed * self.status_effects.speed_multiplier()
		self.x += move_dx * inv_dist * speed * dt
		self.y += move_dy * inv_dist * speed * dt
		self._set_state(EnemyAction.WALK)

	def _perform_attack(self, spawn_slash: Callable[[Slash], None]) -> None:
		action_name, sword_key, cooldown, windup = self.attack_cycle[self.next_attack_index]
		sword = self.swords[sword_key]
		self.current_attack_action = action_name
		self.attack_timer = cooldown

		action_duration = max(
			windup + sword.duration + 0.18,
			self.animation.get_duration(action_name) / 1000.0
		)
		self.attack_anim_time_left = action_duration
		self._set_state(self._action_for_name(action_name))

		for slash in sword.spawn_slashes(self):
			slash.delay_left += windup
			spawn_slash(slash)

		self.next_attack_index = (self.next_attack_index + 1) % len(self.attack_cycle)
