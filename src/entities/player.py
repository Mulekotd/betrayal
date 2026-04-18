from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Iterable

import pygame

from external.pplay.sprite import Sprite
from external.pplay.window import Window

from src.system.input import Input
from src.entities.weapon import FireWeapon, IceWeapon, Weapon, WindWeapon


class Player:
	def __init__(
		self,
		assets_dir: str | Path,
		spawn_x: float,
		spawn_y: float,
		move_speed: float = 220.0,
		attack_speed: float = 1.2,
		strength: int = 6,
		max_health: int = 100,
		health_regen: float = 0.02,
		defense: int = 2,
	) -> None:
		self.assets_dir = Path(assets_dir)

		self.sprite = Sprite(str(self.assets_dir / "player.png"))
		self.sprite.set_position(spawn_x, spawn_y)

		self.weapon_sprites: dict[str, Sprite] = {
			"ice_sword": Sprite(str(self.assets_dir / "ice_sword.png")),
			"fire_sword": Sprite(str(self.assets_dir / "fire_sword.png")),
			"wind_sword": Sprite(str(self.assets_dir / "wind_sword.png")),
		}

		self.weapons: dict[str, Weapon] = {
			"ice_sword": IceWeapon(
				name="ice_sword",
				damage=12,
				attack_radius=80.0,
				slow_factor=0.55,
				slow_duration=1.2,
				freeze_hits=3,
				freeze_duration=1.5,
			),
			"fire_sword": FireWeapon(
				name="fire_sword",
				damage=10,
				attack_radius=80.0,
				burn_dps=6.0,
				burn_duration=2.5,
			),
			"wind_sword": WindWeapon(
				name="wind_sword",
				damage=9,
				attack_radius=110.0,
			),
		}

		self.weapon_name = random.choice(list(self.weapon_sprites.keys()))
		self.weapon_sprite = self.weapon_sprites[self.weapon_name]
		self.weapon = self.weapons[self.weapon_name]

		self.attributes = {
			"max_health": max_health,
			"health_regen": health_regen,
			"defense": defense,
			"strength": strength,
			"move_speed": move_speed,
			"attack_speed": attack_speed,
		}

		self.attribute_levels = {
			"max_health": 0,
			"health_regen": 0,
			"defense": 0,
			"strength": 0,
			"move_speed": 0,
			"attack_speed": 0,
		}

		self.max_attribute_level = 5

		self.max_health = self.attributes["max_health"]
		self.health = float(self.max_health)
		self.invuln_duration = 0.6
		self.invuln_left = 0.0
		self.blink_interval = 0.08
		self._blink_timer = 0.0
		self._blink_on = False

		self.base_radius = max(10.0, min(self.sprite.width, self.sprite.height) * 0.45)
		self.radius = self.base_radius
		self._flash_surface: pygame.Surface | None = None

		self.regen_timer = 0.0

		self.attack_timer = 0.0
		self.swing_timer = 0.0
		self.swing_duration = 0.32
		self.swing_arc = math.radians(120)
		self.swing_trail_steps = 4
		self.swing_trail_spacing = 0.08
		self.facing = (0.0, 1.0)
		self._pending_attack = False

		self.init_progression()

	@property
	def x(self) -> float:
		return self.sprite.x

	@property
	def y(self) -> float:
		return self.sprite.y

	@property
	def center(self) -> tuple[float, float]:
		return (
			self.sprite.x + self.sprite.width * 0.5,
			self.sprite.y + self.sprite.height * 0.5,
		)

	def update(self, input_manager: Input, dt: float, world_width: int, world_height: int) -> None:
		_ = (world_width, world_height)
		keyboard = input_manager.keyboard

		dx = 0.0
		dy = 0.0

		move_speed = self.attributes["move_speed"]

		if keyboard.key_pressed("A") or keyboard.key_pressed("LEFT"):
			dx -= move_speed * dt
		if keyboard.key_pressed("D") or keyboard.key_pressed("RIGHT"):
			dx += move_speed * dt
		if keyboard.key_pressed("W") or keyboard.key_pressed("UP"):
			dy -= move_speed * dt
		if keyboard.key_pressed("S") or keyboard.key_pressed("DOWN"):
			dy += move_speed * dt

		self.sprite.x += dx
		self.sprite.y += dy

		is_moving = (dx != 0.0 or dy != 0.0)

		if is_moving:
			length = math.hypot(dx, dy)
			if length > 0.0:
				self.facing = (dx / length, dy / length)

		if keyboard.key_pressed("1"):
			self.weapon_name = "ice_sword"
			self.weapon_sprite = self.weapon_sprites[self.weapon_name]
			self.weapon = self.weapons[self.weapon_name]
		if keyboard.key_pressed("2"):
			self.weapon_name = "fire_sword"
			self.weapon_sprite = self.weapon_sprites[self.weapon_name]
			self.weapon = self.weapons[self.weapon_name]
		if keyboard.key_pressed("3"):
			self.weapon_name = "wind_sword"
			self.weapon_sprite = self.weapon_sprites[self.weapon_name]
			self.weapon = self.weapons[self.weapon_name]

		self._update_attack(dt, is_moving)
		self._update_invulnerability(dt)
		self._update_regen(dt)

	def resolve_enemy_collisions(self, enemies: Iterable[object]) -> None:
		max_damage = 0
		collided = False

		player_center_x, player_center_y = self.center

		for enemy in enemies:
			enemy_center = getattr(enemy, "center", None)
			enemy_radius = getattr(enemy, "radius", None)
			enemy_damage = getattr(enemy, "damage", 0)

			if enemy_center is None or enemy_radius is None:
				continue

			dx = player_center_x - enemy_center[0]
			dy = player_center_y - enemy_center[1]

			dist_sq = dx * dx + dy * dy
			min_dist = self.radius + float(enemy_radius)

			if dist_sq >= min_dist * min_dist:
				continue

			collided = True
			if enemy_damage > max_damage:
				max_damage = enemy_damage

			if dist_sq <= 0.000001:
				dx, dy = 1.0, 0.0

		if collided and max_damage > 0:
			self.take_damage(max_damage)

	def take_damage(self, amount: int) -> bool:
		if self.invuln_left > 0.0:
			return False

		reduced = max(1, int(amount - self.attributes["defense"]))
		self.health = max(0.0, self.health - reduced)
		self.invuln_left = self.invuln_duration
		self._blink_timer = 0.0
		self._blink_on = True

		return True

	def try_attack(self, enemies: Iterable[object]) -> int:
		attack_center_x, attack_center_y = self.center
		radius_sq = self.weapon.attack_radius * self.weapon.attack_radius

		hits = 0

		damage = self._calculate_damage()

		for enemy in enemies:
			enemy_center = getattr(enemy, "center", None)

			if enemy_center is None:
				continue

			enemy_x, enemy_y = enemy_center
			dx = enemy_x - attack_center_x
			dy = enemy_y - attack_center_y

			if dx * dx + dy * dy <= radius_sq:
				apply_fn = getattr(self.weapon, "apply_with_damage", None)

				if callable(apply_fn):
					if apply_fn(enemy, damage=damage):
						hits += 1
				elif self.weapon.apply(enemy, damage=damage):
					hits += 1

		return hits

	def consume_attack(self) -> bool:
		if self._pending_attack:
			self._pending_attack = False
			return True
		return False

	def draw(self, camera_x: float = 0.0, camera_y: float = 0.0) -> None:
		self._draw_with_camera(self.sprite, camera_x, camera_y)
		self._draw_weapon(camera_x, camera_y)
		self._draw_health_bar(camera_x, camera_y)
		self._draw_damage_flash(camera_x, camera_y)

	def _draw_with_camera(self, sprite: Sprite, camera_x: float, camera_y: float) -> None:
		world_x = sprite.x
		world_y = sprite.y

		sprite.set_position(world_x - camera_x, world_y - camera_y)
		sprite.draw()
		sprite.set_position(world_x, world_y)

	def _draw_weapon(self, camera_x: float, camera_y: float) -> None:
		px, py = self.center
		fx, fy = self.facing
		base_angle = math.atan2(fy, fx)
		phase = 0.0

		if self.swing_duration > 0.0 and self.swing_timer > 0.0:
			phase = 1.0 - (self.swing_timer / self.swing_duration)

		ease = phase * phase * (3.0 - 2.0 * phase)
		swing = math.sin(ease * math.pi) * self.swing_arc
		angle = base_angle + swing
		self.weapon_sprite.set_rotation(math.degrees(angle))

		offset = max(self.sprite.width, self.sprite.height) * 0.55
		wx = px + math.cos(angle) * offset
		wy = py + math.sin(angle) * offset

		self.weapon_sprite.set_position(
			wx - (self.weapon_sprite.width * 0.5),
			wy - (self.weapon_sprite.height * 0.5),
		)

		screen = Window.get_screen()
		if screen is not None and self.swing_timer > 0.0:
			base_image = self.weapon_sprite.image
			for step in range(self.swing_trail_steps, 0, -1):
				trail_phase = max(0.0, phase - step * self.swing_trail_spacing)
				if trail_phase <= 0.0:
					continue
				ease_trail = trail_phase * trail_phase * (3.0 - 2.0 * trail_phase)
				trail_swing = math.sin(ease_trail * math.pi) * self.swing_arc
				trail_angle = base_angle + trail_swing
				trail_offset = max(self.sprite.width, self.sprite.height) * 0.55
				trail_x = px + math.cos(trail_angle) * trail_offset
				trail_y = py + math.sin(trail_angle) * trail_offset
				trail_surface = pygame.transform.rotate(base_image, math.degrees(trail_angle))
				trail_alpha = int(140 * (step / self.swing_trail_steps))
				trail_surface.set_alpha(trail_alpha)
				screen.blit(
					trail_surface,
					(
						trail_x - camera_x - trail_surface.get_width() * 0.5,
						trail_y - camera_y - trail_surface.get_height() * 0.5,
					),
				)

		self._draw_with_camera(self.weapon_sprite, camera_x, camera_y)

	def _draw_health_bar(self, camera_x: float, camera_y: float) -> None:
		screen = Window.get_screen()

		if screen is None:
			return

		bar_width = int(self.sprite.width)
		bar_height = 6
		bar_gap = 12
		bar_x = int(self.sprite.x - camera_x)
		bar_y = int(self.sprite.y - camera_y + self.sprite.height + bar_gap)

		pygame.draw.rect(screen, (200, 0, 0), (bar_x, bar_y, bar_width, bar_height))
		missing = int(bar_width * (1.0 - (self.health / self.max_health))) if self.max_health > 0 else bar_width

		if missing > 0:
			pygame.draw.rect(screen, (0, 0, 0), (bar_x + bar_width - missing, bar_y, missing, bar_height))

	def _draw_damage_flash(self, camera_x: float, camera_y: float) -> None:
		if self.invuln_left <= 0.0 or not self._blink_on:
			return

		screen = Window.get_screen()

		if screen is None:
			return

		width = int(self.sprite.width)
		height = int(self.sprite.height)

		if self._flash_surface is None or self._flash_surface.get_size() != (width, height):
			mask = pygame.mask.from_surface(self.sprite.image)
			self._flash_surface = mask.to_surface(
				setcolor=(255, 255, 255, 120),
				unsetcolor=(0, 0, 0, 0),
			)

		screen.blit(
			self._flash_surface,
			(int(self.sprite.x - camera_x), int(self.sprite.y - camera_y)),
		)

	def _update_attack(self, dt: float, is_moving: bool) -> None:
		attack_speed = max(0.1, self.attributes["attack_speed"])
		interval = 1.0 / attack_speed
		self.attack_timer = max(0.0, self.attack_timer - dt)

		if self.attack_timer <= 0.0 and is_moving:
			self.attack_timer = interval
			self.swing_timer = self.swing_duration
			self._pending_attack = True
		else:
			self._pending_attack = False

		if self.swing_timer > 0.0:
			self.swing_timer = max(0.0, self.swing_timer - dt)

	def _update_invulnerability(self, dt: float) -> None:
		if self.invuln_left <= 0.0:
			self._blink_on = False
			return

		self.invuln_left = max(0.0, self.invuln_left - dt)
		self._blink_timer += dt

		if self._blink_timer >= self.blink_interval:
			self._blink_timer = 0.0
			self._blink_on = not self._blink_on

	def _update_regen(self, dt: float) -> None:
		self.regen_timer += dt

		if self.regen_timer >= 1.0:
			self.regen_timer = 0.0
			heal = self.max_health * self.attributes["health_regen"]
			self.health = min(self.max_health, self.health + heal)

	def _calculate_damage(self) -> int:
		return max(1, int(self.weapon.damage + self.attributes["strength"]))

	def init_progression(self) -> None:
		self.level = 1
		self.xp = 0
		self.xp_to_next = 25

	def add_xp(self, amount: int) -> int:
		self.xp += amount
		levels_gained = 0

		while self.xp >= self.xp_to_next:
			self.xp -= self.xp_to_next
			self._level_up()
			levels_gained += 1

		return levels_gained

	def _level_up(self) -> None:
		self.level += 1
		self.xp_to_next = int(self.xp_to_next * 1.45)

	def upgrade_attribute(self, name: str) -> bool:
		if name not in self.attribute_levels:
			return False
		if self.attribute_levels[name] >= self.max_attribute_level:
			return False

		self.attribute_levels[name] += 1

		if name == "max_health":
			self.max_health = int(self.max_health * 1.15)
			self.health = min(self.max_health, self.health + self.max_health * 0.15)
		elif name == "health_regen":
			self.attributes[name] = min(0.15, self.attributes[name] + 0.01)
		elif name == "defense":
			self.attributes[name] += 2
		elif name == "strength":
			self.attributes[name] += 2
		elif name == "move_speed":
			self.attributes[name] += 20
		elif name == "attack_speed":
			self.attributes[name] += 0.2
		return True

	def distance_to(self, target_x: float, target_y: float) -> float:
		cx, cy = self.center
		dx = target_x - cx
		dy = target_y - cy

		return math.sqrt(dx * dx + dy * dy)
