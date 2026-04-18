from __future__ import annotations

import math
import random
from pathlib import Path

from external.pplay.sprite import Sprite


class Enemy:
	def __init__(
		self,
		sprite_path: str | Path,
		base_health: int = 30,
		base_speed: float = 150.0,
		base_damage: int = 12,
		xp_value: int = 6,
	) -> None:
		self.sprite = Sprite(str(sprite_path))
		self.base_health = base_health
		self.base_speed = base_speed
		self.base_damage = base_damage
		self.xp_value = xp_value
		self.health = base_health
		self.speed = base_speed
		self.damage = base_damage
		self.base_radius = max(8.0, min(self.sprite.width, self.sprite.height) * 0.42)
		self.radius = self.base_radius
		self.sprite_scale = 1.0

		self.slow_factor = 1.0
		self.slow_timer = 0.0
		self.burn_dps = 0.0
		self.burn_timer = 0.0
		self.freeze_timer = 0.0
		self.ice_hits = 0

	def spawn(self, x: float, y: float, speed_multiplier: float = 1.0) -> None:
		self.sprite.set_position(x, y)
		self.health = self.base_health
		self.speed = self.base_speed * speed_multiplier
		self.damage = self.base_damage
		self.slow_factor = 1.0
		self.slow_timer = 0.0
		self.burn_dps = 0.0
		self.burn_timer = 0.0
		self.freeze_timer = 0.0
		self.ice_hits = 0
		self.set_scale(self.sprite_scale)

	def set_scale(self, scale: float) -> None:
		self.sprite_scale = max(0.1, scale)
		self.sprite.set_scale(self.sprite_scale)
		self.radius = self.base_radius * self.sprite_scale

	@property
	def center(self) -> tuple[float, float]:
		return (
			self.sprite.x + self.sprite.width * 0.5,
			self.sprite.y + self.sprite.height * 0.5,
		)

	def move_by(self, dx: float, dy: float) -> None:
		self.sprite.x += dx
		self.sprite.y += dy

	def update_towards(self, target_x: float, target_y: float, dt: float) -> None:
		self._update_statuses(dt)
		if self.freeze_timer > 0.0:
			return

		cx, cy = self.center
		dx = target_x - cx
		dy = target_y - cy
		dist_sq = dx * dx + dy * dy
		if dist_sq <= 0.000001:
			return

		inv_dist = 1.0 / math.sqrt(dist_sq)
		speed = self.speed * self.slow_factor
		self.sprite.x += dx * inv_dist * speed * dt
		self.sprite.y += dy * inv_dist * speed * dt

	def take_damage(self, amount: int) -> None:
		self.health -= amount

	def apply_burn(self, dps: float, duration: float) -> None:
		self.burn_dps = max(self.burn_dps, dps)
		self.burn_timer = max(self.burn_timer, duration)

	def apply_slow(self, slow_factor: float, duration: float) -> None:
		self.slow_factor = min(self.slow_factor, slow_factor)
		self.slow_timer = max(self.slow_timer, duration)

	def register_ice_hit(self, freeze_hits: int, freeze_duration: float) -> None:
		self.ice_hits += 1
		if self.ice_hits >= freeze_hits:
			self.ice_hits = 0
			self.freeze_timer = max(self.freeze_timer, freeze_duration)

	def _update_statuses(self, dt: float) -> None:
		if self.burn_timer > 0.0:
			self.burn_timer = max(0.0, self.burn_timer - dt)
			self.health -= self.burn_dps * dt
			if self.burn_timer <= 0.0:
				self.burn_dps = 0.0

		if self.slow_timer > 0.0:
			self.slow_timer = max(0.0, self.slow_timer - dt)
			if self.slow_timer <= 0.0:
				self.slow_factor = 1.0

		if self.freeze_timer > 0.0:
			self.freeze_timer = max(0.0, self.freeze_timer - dt)

	def is_dead(self) -> bool:
		return self.health <= 0

	def draw(self, camera_x: float = 0.0, camera_y: float = 0.0) -> None:
		world_x = self.sprite.x
		world_y = self.sprite.y
		self.sprite.set_position(world_x - camera_x, world_y - camera_y)
		self.sprite.draw()
		self.sprite.set_position(world_x, world_y)


class Slime(Enemy):
	def __init__(self, sprite_path: str | Path) -> None:
		super().__init__(
			sprite_path=sprite_path,
			base_health=25,
			base_speed=170.0,
			base_damage=5,
			xp_value=4,
		)


class Skeleton(Enemy):
	def __init__(self, sprite_path: str | Path) -> None:
		super().__init__(
			sprite_path=sprite_path,
			base_health=45,
			base_speed=165.0,
			base_damage=9,
			xp_value=7,
		)


class Knight(Enemy):
	def __init__(self, sprite_path: str | Path) -> None:
		super().__init__(
			sprite_path=sprite_path,
			base_health=90,
			base_speed=120.0,
			base_damage=16,
			xp_value=12,
		)


class EnemyCluster:
	"""Spatial hash grid to reduce neighbor checks for enemy separation."""

	def __init__(self, cell_size: float = 96.0) -> None:
		self.cell_size = max(32.0, cell_size)
		self._cells: dict[tuple[int, int], list[Enemy]] = {}

	def rebuild(self, enemies: list[Enemy]) -> None:
		self._cells.clear()
		for enemy in enemies:
			cell = self._cell_for(enemy)
			self._cells.setdefault(cell, []).append(enemy)

	def candidates_for(self, enemy: Enemy) -> list[Enemy]:
		base_cell = self._cell_for(enemy)
		neighbors: list[Enemy] = []
		for ox in (-1, 0, 1):
			for oy in (-1, 0, 1):
				cell = (base_cell[0] + ox, base_cell[1] + oy)
				neighbors.extend(self._cells.get(cell, []))
		return neighbors

	def _cell_for(self, enemy: Enemy) -> tuple[int, int]:
		x, y = enemy.center
		return (int(x // self.cell_size), int(y // self.cell_size))


class EnemyManager:
	def __init__(
		self,
		assets_dir: str | Path,
		world_width: int,
		world_height: int,
		base_spawn_rate: float = 0.12,
		spawn_growth: float = 0.06,
		max_spawn_rate: float = 2.0,
	) -> None:
		self.assets_dir = Path(assets_dir)
		self.world_width = world_width
		self.world_height = world_height
		self.enemy_sprite_path = self.assets_dir / "enemy.png"

		self.active: list[Enemy] = []
		self.pool: list[Enemy] = []

		self.cluster = EnemyCluster(cell_size=96.0)

		self.elapsed_time = 0.0
		self.spawn_budget = 0.0
		self.base_spawn_rate = base_spawn_rate
		self.spawn_growth = spawn_growth
		self.max_spawn_rate = max_spawn_rate
		self.sprite_scale = 1.0
		self.spawn_weights = [
			(Slime, 0.5),
			(Skeleton, 0.35),
			(Knight, 0.15),
		]

	def update(self, player: object, dt: float) -> int:
		self.elapsed_time += dt
		target_x, target_y = getattr(player, "center", (self.world_width * 0.5, self.world_height * 0.5))
		self._spawn_by_budget(dt, target_x=target_x, target_y=target_y)

		for enemy in self.active:
			enemy.update_towards(target_x, target_y, dt)

		self._resolve_enemy_collisions()
		return self._recycle_dead()

	def draw(self, camera_x: float = 0.0, camera_y: float = 0.0) -> None:
		for enemy in self.active:
			enemy.draw(camera_x=camera_x, camera_y=camera_y)

	def get_enemies(self) -> list[Enemy]:
		return self.active

	def set_scale(self, scale: float) -> None:
		self.sprite_scale = max(0.1, scale)
		for enemy in self.active:
			enemy.set_scale(self.sprite_scale)
		for enemy in self.pool:
			enemy.set_scale(self.sprite_scale)

	def _spawn_by_budget(self, dt: float, target_x: float, target_y: float) -> None:
		rate = self.current_spawn_rate()
		self.spawn_budget += rate * dt

		spawned_this_frame = 0
		max_spawns_per_frame = 3
		while self.spawn_budget >= 1.0 and spawned_this_frame < max_spawns_per_frame:
			self.spawn_budget -= 1.0
			self._spawn_enemy(target_x=target_x, target_y=target_y)
			spawned_this_frame += 1

	def current_spawn_rate(self) -> float:
		rate = self.base_spawn_rate * math.exp(self.spawn_growth * self.elapsed_time)
		return min(self.max_spawn_rate, rate)

	def _spawn_enemy(self, target_x: float, target_y: float) -> None:
		enemy = self.pool.pop() if self.pool else self._create_enemy()

		x, y = self._pick_spawn_position(enemy, target_x=target_x, target_y=target_y)
		speed_multiplier = min(2.5, 1.0 + self.elapsed_time * 0.01)
		enemy.spawn(x, y, speed_multiplier=speed_multiplier)
		enemy.set_scale(self.sprite_scale)

		self.active.append(enemy)

	def _create_enemy(self) -> Enemy:
		types, weights = zip(*self.spawn_weights)
		choice = random.choices(types, weights=weights, k=1)[0]
		return choice(self.enemy_sprite_path)

	def _pick_spawn_position(self, enemy: Enemy, target_x: float, target_y: float) -> tuple[float, float]:
		margin = max(enemy.sprite.width, enemy.sprite.height)
		half_view_w = self.world_width * 0.5
		half_view_h = self.world_height * 0.5
		side = random.choice(["top", "bottom", "left", "right"])

		if side == "top":
			return random.uniform(target_x - half_view_w, target_x + half_view_w), target_y - half_view_h - margin
		if side == "bottom":
			return random.uniform(target_x - half_view_w, target_x + half_view_w), target_y + half_view_h + margin
		if side == "left":
			return target_x - half_view_w - margin, random.uniform(target_y - half_view_h, target_y + half_view_h)

		return target_x + half_view_w + margin, random.uniform(target_y - half_view_h, target_y + half_view_h)

	def _resolve_enemy_collisions(self) -> None:
		if len(self.active) < 2:
			return

		self.cluster.rebuild(self.active)
		visited_pairs: set[tuple[int, int]] = set()

		for enemy in self.active:
			for other in self.cluster.candidates_for(enemy):
				if enemy is other:
					continue

				pair = (min(id(enemy), id(other)), max(id(enemy), id(other)))
				if pair in visited_pairs:
					continue
				visited_pairs.add(pair)
				self._separate_pair(enemy, other)

	def _separate_pair(self, enemy_a: Enemy, enemy_b: Enemy) -> None:
		ax, ay = enemy_a.center
		bx, by = enemy_b.center
		dx = bx - ax
		dy = by - ay
		min_dist = enemy_a.radius + enemy_b.radius + 2.0
		dist_sq = dx * dx + dy * dy

		if dist_sq <= 0.000001:
			angle = random.uniform(0, math.tau)
			dx = math.cos(angle)
			dy = math.sin(angle)
			dist_sq = dx * dx + dy * dy

		if dist_sq >= min_dist * min_dist:
			return

		dist = math.sqrt(dist_sq)
		overlap = min_dist - dist
		nx = dx / dist
		ny = dy / dist
		separation_x = nx * overlap * 0.5
		separation_y = ny * overlap * 0.5

		enemy_a.move_by(-separation_x, -separation_y)
		enemy_b.move_by(separation_x, separation_y)

	def _recycle_dead(self) -> int:
		if not self.active:
			return 0

		survivors: list[Enemy] = []
		xp_total = 0

		for enemy in self.active:
			if enemy.is_dead():
				xp_total += enemy.xp_value
				self.pool.append(enemy)
			else:
				survivors.append(enemy)

		self.active = survivors
		return xp_total
