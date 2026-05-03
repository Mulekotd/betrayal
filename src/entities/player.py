import math
from pathlib import Path
from typing import Iterable

import pygame

from external.pplay.sprite import Sprite

from src.system.input import Input
from src.utils.window import get_screen, draw_rect, blit_surface
from src.utils.box import Rect


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
		defense: int = 2
	) -> None:
		self.assets_dir = Path(assets_dir)

		self.sprite = Sprite(str(self.assets_dir / "player.png"))
		self.sprite.set_position(spawn_x, spawn_y)

		self.attributes = {
			"max_health": max_health,
			"health_regen": health_regen,
			"defense": defense,
			"strength": strength,
			"move_speed": move_speed,
			"attack_speed": attack_speed
		}

		self.attribute_levels = {
			"max_health": 0,
			"health_regen": 0,
			"defense": 0,
			"strength": 0,
			"move_speed": 0,
			"attack_speed": 0
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
		self._flash_surface = None

		self.regen_timer = 0.0
		self.facing = (0.0, 1.0)

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
			self.sprite.y + self.sprite.height * 0.5
		)

	def is_dead(self) -> bool:
		return self.health <= 0.0

	def update(
		self,
		input_manager: Input,
		dt: float,
		world_width: int,
		world_height: int,
		world_bounds: Rect | None = None
	) -> None:
		if self.is_dead():
			self._blink_on = False
			self.invuln_left = 0.0
			return

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
		self._clamp_to_world(world_width, world_height, world_bounds)

		is_moving = (dx != 0.0 or dy != 0.0)

		if is_moving:
			length = math.hypot(dx, dy)
			if length > 0.0:
				self.facing = (dx / length, dy / length)

		self._update_invulnerability(dt)
		self._update_regen(dt)

	def _clamp_to_world(self, world_width: int, world_height: int, world_bounds: object | None = None) -> None:
		if world_bounds is None:
			min_x = 0.0
			max_x = float(world_width - self.sprite.width)
			min_y = 0.0
			max_y = float(world_height - self.sprite.height)
		else:
			min_x = float(world_bounds.left)
			max_x = float(world_bounds.right - self.sprite.width)
			min_y = float(world_bounds.top)
			max_y = float(world_bounds.bottom - self.sprite.height)

		if max_x < min_x:
			self.sprite.x = min_x
		else:
			self.sprite.x = max(min_x, min(self.sprite.x, max_x))

		if max_y < min_y:
			self.sprite.y = min_y
		else:
			self.sprite.y = max(min_y, min(self.sprite.y, max_y))

	def resolve_enemy_collisions(self, enemies: Iterable[object]) -> None:
		max_damage = 0
		collided = False

		player_center_x, player_center_y = self.center

		for enemy in enemies:
			enemy_center = getattr(enemy, "center", None)
			enemy_radius = getattr(enemy, "radius", None)
			enemy_damage = getattr(enemy, "damage", 0)
			contact_damage = bool(getattr(enemy, "contact_damage", True))

			if enemy_center is None or enemy_radius is None:
				continue

			enemy_dx = enemy_center[0] - player_center_x
			enemy_dy = enemy_center[1] - player_center_y

			dist_sq = enemy_dx * enemy_dx + enemy_dy * enemy_dy
			min_dist = self.radius + float(enemy_radius)

			if dist_sq >= min_dist * min_dist:
				continue

			collided = True
			if contact_damage and enemy_damage > max_damage:
				max_damage = enemy_damage

			if dist_sq <= 0.000001:
				enemy_dx, enemy_dy = 1.0, 0.0

			enemy_move = getattr(enemy, "move_by", None)
			if callable(enemy_move):
				dist = math.sqrt(max(dist_sq, 0.000001))
				overlap = max(0.0, min_dist - dist)
				if overlap > 0.0:
					nx = enemy_dx / dist
					ny = enemy_dy / dist
					enemy_move(nx * overlap, ny * overlap)

		if collided and max_damage > 0:
			self.take_damage(max_damage)

	def take_damage(self, amount: int) -> bool:
		if self.is_dead() or self.invuln_left > 0.0:
			return False

		reduced = max(1, int(amount - self.attributes["defense"]))
		self.health = max(0.0, self.health - reduced)
		self.invuln_left = self.invuln_duration
		self._blink_timer = 0.0
		self._blink_on = True

		return True

	def draw(self, camera_x: float = 0.0, camera_y: float = 0.0) -> None:
		self._draw_with_camera(self.sprite, camera_x, camera_y)
		self._draw_health_bar(camera_x, camera_y)
		self._draw_damage_flash(camera_x, camera_y)

	def _draw_with_camera(self, sprite: Sprite, camera_x: float, camera_y: float) -> None:
		screen = get_screen()

		frame_w = int(sprite.width)
		frame_h = int(sprite.height)
		frame_index = int(getattr(sprite, "frame_atual", 0))
		area = pygame.Rect(frame_index * frame_w, 0, frame_w, frame_h)

		frame_surface = sprite.image.subsurface(area).copy()
		frame_surface.set_alpha(getattr(sprite, "transparency", 255))

		rotation = getattr(sprite, "rotation", 0)
		if rotation != 0:
			frame_surface = pygame.transform.rotate(frame_surface, rotation)

		scale_x = getattr(sprite, "scale_x", 1.0)
		scale_y = getattr(sprite, "scale_y", 1.0)

		if scale_x != 1.0 or scale_y != 1.0:
			nw = max(1, int(frame_surface.get_width() * scale_x))
			nh = max(1, int(frame_surface.get_height() * scale_y))
			frame_surface = pygame.transform.scale(frame_surface, (nw, nh))

		blit_surface(frame_surface, (int(sprite.x - camera_x), int(sprite.y - camera_y)), target=screen)


	def _draw_health_bar(self, camera_x: float, camera_y: float) -> None:
		screen = get_screen()

		bar_width = int(self.sprite.width)
		bar_height = 6
		bar_gap = 12
		bar_x = int(self.sprite.x - camera_x)
		bar_y = int(self.sprite.y - camera_y + self.sprite.height + bar_gap)

		draw_rect((200, 0, 0), (bar_x, bar_y, bar_width, bar_height), target=screen)
		missing = int(bar_width * (1.0 - (self.health / self.max_health))) if self.max_health > 0 else bar_width

		if missing > 0:
			draw_rect((0, 0, 0), (bar_x + bar_width - missing, bar_y, missing, bar_height), target=screen)

	def _draw_damage_flash(self, camera_x: float, camera_y: float) -> None:
		if self.invuln_left <= 0.0 or not self._blink_on:
			return

		screen = get_screen()

		frame_w = int(self.sprite.width)
		frame_h = int(self.sprite.height)
		frame_index = int(getattr(self.sprite, "frame_atual", 0))
		area = pygame.Rect(frame_index * frame_w, 0, frame_w, frame_h)

		frame_surface = self.sprite.image.subsurface(area).copy()
		frame_surface.set_alpha(getattr(self.sprite, "transparency", 255))

		rotation = getattr(self.sprite, "rotation", 0)
		if rotation != 0:
			frame_surface = pygame.transform.rotate(frame_surface, rotation)

		scale_x = getattr(self.sprite, "scale_x", 1.0)
		scale_y = getattr(self.sprite, "scale_y", 1.0)

		if scale_x != 1.0 or scale_y != 1.0:
			nw = max(1, int(frame_surface.get_width() * scale_x))
			nh = max(1, int(frame_surface.get_height() * scale_y))
			frame_surface = pygame.transform.scale(frame_surface, (nw, nh))

		mask = pygame.mask.from_surface(frame_surface)
		alpha_val = 120
		mask_surf = mask.to_surface(setcolor=(255, 255, 255, alpha_val), unsetcolor=(0, 0, 0, 0))

		blit_surface(mask_surf, (int(self.sprite.x - camera_x), int(self.sprite.y - camera_y)), target=screen)

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
		if self.is_dead():
			return

		self.regen_timer += dt

		if self.regen_timer >= 1.0:
			self.regen_timer = 0.0
			heal = self.max_health * self.attributes["health_regen"]
			self.health = min(self.max_health, self.health + heal)

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
