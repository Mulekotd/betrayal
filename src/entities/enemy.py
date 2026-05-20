import math
import random
from enum import Enum
from pathlib import Path
from typing import Callable

from src.engine.animation import Animation
from src.engine.state_machine import StateMachine
from src.entities.weapon import Arrow
from src.utils.window import get_screen, scale_surface, blit_surface, create_mask_surface
from src.utils.rect import Rect


class EnemyAction(Enum):
	IDLE     = "IDLE"
	WALK     = "WALK"
	ATTACK_1 = "ATTACK_1"
	ATTACK_2 = "ATTACK_2"
	ATTACK_3 = "ATTACK_3"
	GUARD    = "GUARD"
	HIT      = "HIT"


class Enemy:
	def __init__(
		self,
		sprite_path: str | Path,
		frame_width: int,
		frame_height: int,
		frame_gap: int,
		actions: list[str],
		frame_rate: int = 120,
		base_health: int = 30,
		base_speed: float = 150.0,
		base_damage: int = 12,
		xp_value: int = 6,
		armor: float = 0.0
	) -> None:
		self.animation = Animation(
			sprite_path = sprite_path,
			width = frame_width,
			height = frame_height,
			gap = frame_gap,
			actions = actions,
			frame_rate = frame_rate
		)

		self.x = 0.0
		self.y = 0.0

		self.frame_width = self.animation.frame_width or frame_width
		self.frame_height = self.animation.frame_height or frame_height

		self.base_health = base_health
		self.base_speed = base_speed
		self.base_damage = base_damage
		self.base_armor = max(0.0, min(armor, 0.9))

		self.xp_value = xp_value
		self.health = base_health
		self.speed = base_speed
		self.damage = base_damage
		self.armor = self.base_armor

		self.base_radius = max(8.0, min(self.frame_width, self.frame_height) * 0.42)
		self.radius = self.base_radius
		self.base_scale = 1.0
		self.scale_multiplier = 1.0
		self.sprite_scale = self.base_scale * self.scale_multiplier
		self.state_machine = StateMachine(list(EnemyAction), EnemyAction.IDLE)

		self.slow_factor = 1.0
		self.slow_timer = 0.0
		self.burn_dps = 0.0
		self.burn_timer = 0.0
		self.freeze_timer = 0.0
		self.ice_hits = 0

		self.hit_anim_time_left = 0.0

		self.idle_action = "IDLE" if "IDLE" in actions else (actions[0] if actions else "")
		self.walk_action = "WALK" if "WALK" in actions else self.idle_action
		self.facing_dir = 1
		self.contact_damage = True
		self._draw_cache: dict[tuple[str, int, bool, int, int], object] = {}
		self._hit_mask_cache: dict[tuple[str, int, bool, int, int], object] = {}
		self._freeze_mask_cache: dict[tuple[str, int, bool, int, int], object] = {}
		self._sync_state_animation()

	def spawn(self, x: float, y: float, speed_multiplier: float = 1.0) -> None:
		self.x = x
		self.y = y
		self.health = self.base_health
		self.speed = self.base_speed * speed_multiplier
		self.damage = self.base_damage
		self.armor = self.base_armor
		self.slow_factor = 1.0
		self.slow_timer = 0.0
		self.burn_dps = 0.0
		self.burn_timer = 0.0
		self.freeze_timer = 0.0
		self.ice_hits = 0
		self.hit_anim_time_left = 0.0
		self.set_scale(self.scale_multiplier)
		self._set_state(EnemyAction.IDLE)

	def set_scale(self, scale: float) -> None:
		self.scale_multiplier = max(0.1, scale)
		self.sprite_scale = max(0.1, self.base_scale * self.scale_multiplier)
		self.radius = self.base_radius * self.sprite_scale

	@property
	def width(self) -> float:
		return self.frame_width * self.sprite_scale

	@property
	def height(self) -> float:
		return self.frame_height * self.sprite_scale

	@property
	def center(self) -> tuple[float, float]:
		return (
			self.x + self.width * 0.5,
			self.y + self.height * 0.5
		)

	def move_by(self, dx: float, dy: float) -> None:
		self.x += dx
		self.y += dy

	def update_towards(
		self,
		target_x: float,
		target_y: float,
		dt: float,
		move_target_x: float | None = None,
		move_target_y: float | None = None
	) -> None:
		self._update_statuses(dt)
		self.animation.update(int(dt * 1000))

		if self.health <= 0:
			return

		if self.freeze_timer > 0.0:
			self._set_state(EnemyAction.IDLE)
			return

		if self.hit_anim_time_left > 0.0:
			self._set_state(EnemyAction.HIT)
			return

		cx, cy = self.center
		dx = target_x - cx
		self.facing_dir = -1 if dx < 0 else 1

		move_x = target_x if move_target_x is None else move_target_x
		move_y = target_y if move_target_y is None else move_target_y

		move_dx = move_x - cx
		move_dy = move_y - cy

		move_dist_sq = move_dx * move_dx + move_dy * move_dy
		if move_dist_sq <= 0.000001:
			self._set_state(EnemyAction.IDLE)
			return

		inv_dist = 1.0 / math.sqrt(move_dist_sq)
		speed = self.speed * self.slow_factor

		self.x += move_dx * inv_dist * speed * dt
		self.y += move_dy * inv_dist * speed * dt

		self._set_state(EnemyAction.WALK)

	def _sync_state_animation(self) -> None:
		self.animation.play(self.state_machine.state.value)

	def _action_for_name(self, action: str) -> EnemyAction:
		try:
			return EnemyAction(action)
		except ValueError:
			return EnemyAction.IDLE

	def _set_state(self, state: EnemyAction) -> None:
		if self.state_machine.state != state:
			self.state_machine.set(state)

		self._sync_state_animation()

	def take_damage(self, amount: int) -> None:
		reduced = int(amount * (1.0 - self.armor))
		self.health -= max(1, reduced)
		self._trigger_hit_animation()

	def _trigger_hit_animation(self) -> None:
		hit_frames = self.animation.frames.get("HIT", [])
		if hit_frames:
			hit_duration = max(0.08, self.animation.get_duration("HIT") / 1000.0)
			self.hit_anim_time_left = hit_duration
			self._set_state(EnemyAction.HIT)

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

		if self.hit_anim_time_left > 0.0:
			self.hit_anim_time_left = max(0.0, self.hit_anim_time_left - dt)

	def is_dead(self) -> bool:
		return self.health <= 0

	def draw(self, camera_x: float = 0.0, camera_y: float = 0.0) -> None:
		screen = get_screen()
		frame = self.animation.get_frame_flipped(flip_x=self.facing_dir < 0)

		if frame is None: return
		frame = self._get_draw_frame(frame, self.facing_dir < 0)

		blit_surface(frame, (self.x - camera_x, self.y - camera_y), target=screen)

		if self.hit_anim_time_left > 0.0:
			mask_surf = self._get_mask_frame(frame, self._hit_mask_cache, (255, 255, 255, 120))
			blit_surface(mask_surf, (self.x - camera_x, self.y - camera_y), target=screen)

		if self.freeze_timer > 0.0:
			mask_surf = self._get_mask_frame(frame, self._freeze_mask_cache, (80, 160, 255, 120))
			blit_surface(mask_surf, (self.x - camera_x, self.y - camera_y), target=screen)

	def _get_draw_frame(self, frame, flip_x: bool):
		if self.sprite_scale == 1.0:
			return frame

		key = (
			self.animation.current_action,
			self.animation.current_index,
			flip_x,
			int(self.width),
			int(self.height)
		)

		cached = self._draw_cache.get(key)
		if cached is not None:
			return cached

		scaled = scale_surface(frame, int(self.width), int(self.height), smooth=False)
		self._draw_cache[key] = scaled

		return scaled

	def _get_mask_frame(self, frame, cache: dict, color: tuple[int, int, int, int]):
		key = (
			self.animation.current_action,
			self.animation.current_index,
			self.facing_dir < 0,
			int(self.width),
			int(self.height)
		)

		cached = cache.get(key)
		if cached is not None:
			return cached

		mask = create_mask_surface(frame, color, (0, 0, 0, 0))
		cache[key] = mask

		return mask

class Soldier(Enemy):
	def __init__(
		self,
		sprite_path: str | Path,
		is_ranged: bool,
		base_health: int = 60,
		base_speed: float = 120.0,
		base_damage: int = 8,
		xp_value: int = 8
	) -> None:
		if is_ranged:
			base_health = 35
			base_speed = 145.0
			base_damage = 22
			xp_value = 10

		armor = 0.05 if is_ranged else 0.20

		super().__init__(
			sprite_path = sprite_path,
			frame_width = 0,
			frame_height = 0,
			frame_gap = 0,
			actions = ["IDLE", "WALK", "ATTACK_1", "ATTACK_2", "ATTACK_3", "HIT"],
			frame_rate = 120,
			base_health = base_health,
			base_speed = base_speed,
			base_damage = base_damage,
			xp_value = xp_value,
			armor = armor
		)

		self.is_ranged = is_ranged
		self.base_scale = 1.5
		self.set_scale(1.0)
		self.attack_timer = 0.0
		self.attack_cooldown = 2.0 if is_ranged else 0.8
		self.ranged_distance = 96.0
		self.ranged_hold_distance = 112.0
		self.melee_distance = 28.0
		self.contact_damage = False
		self.current_attack_action = ""
		self.attack_anim_time_left = 0.0
		self.melee_attack_actions = ["ATTACK_1", "ATTACK_2"]
		self.next_melee_attack_index = 0
		self.pending_ranged_shot = False
		self.ranged_shot_fired = False

	def spawn(self, x: float, y: float, speed_multiplier: float = 1.0) -> None:
		super().spawn(x, y, speed_multiplier=speed_multiplier)
		self.attack_timer = 0.0
		self.current_attack_action = ""
		self.attack_anim_time_left = 0.0
		self.pending_ranged_shot = False
		self.ranged_shot_fired = False

	def update_towards(
		self,
		target_x: float,
		target_y: float,
		dt: float,
		player: object | None = None,
		spawn_projectile: Callable[[float, float, float, float, int], None] | None = None,
		move_target_x: float | None = None,
		move_target_y: float | None = None
	) -> None:
		self._update_statuses(dt)
		self.animation.update(int(dt * 1000))

		self.attack_timer = max(0.0, self.attack_timer - dt * self.slow_factor)
		self.attack_anim_time_left = max(0.0, self.attack_anim_time_left - dt)

		if self.freeze_timer > 0.0:
			self._set_state(EnemyAction.IDLE)
			return

		if self.hit_anim_time_left > 0.0:
			self._set_state(EnemyAction.HIT)
			return

		cx, cy = self.center
		dx = target_x - cx
		dy = target_y - cy
		self.facing_dir = -1 if dx < 0 else 1
		dist_sq = dx * dx + dy * dy
		self._try_release_ranged_shot(
			origin_x = cx,
			origin_y = cy,
			target_dx = dx,
			target_dy = dy,
			spawn_projectile = spawn_projectile,
			force = self.attack_anim_time_left <= 0.0
		)

		if dist_sq <= 0.000001:
			self._set_state(EnemyAction.IDLE)
			return

		if self.attack_anim_time_left > 0.0 and self.current_attack_action:
			self._set_state(self._action_for_name(self.current_attack_action))
			return

		dist = math.sqrt(dist_sq)
		player_radius = float(getattr(player, "radius", 12.0))
		effective_melee_distance = max(self.melee_distance, self.radius + player_radius + 6.0)

		if self.is_ranged:
			effective_ranged_distance = self.radius + player_radius + self.ranged_distance
			effective_hold_distance = self.radius + player_radius + self.ranged_hold_distance

			if dist <= effective_ranged_distance:
				if self.attack_timer <= 0.0 and not self.pending_ranged_shot and spawn_projectile is not None:
					self.attack_timer = self.attack_cooldown
					self.pending_ranged_shot = True
					self.ranged_shot_fired = False
					self._play_attack("ATTACK_3")
				else:
					self._set_state(EnemyAction.IDLE)
				return

			if dist <= effective_hold_distance and self.attack_timer > 0.0:
				self._set_state(EnemyAction.IDLE)
				return

		if not self.is_ranged and dist <= effective_melee_distance:
			if self.attack_timer <= 0.0:
				self.attack_timer = self.attack_cooldown
				attack_action = self.melee_attack_actions[self.next_melee_attack_index]
				self.next_melee_attack_index = (self.next_melee_attack_index + 1) % len(self.melee_attack_actions)
				self._play_attack(attack_action)

				damage_fn = getattr(player, "take_damage", None)
				if callable(damage_fn):
					damage_fn(self.damage)
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
		speed = self.speed * self.slow_factor

		self.x += move_dx * inv_dist * speed * dt
		self.y += move_dy * inv_dist * speed * dt

		self._set_state(EnemyAction.WALK)

	def _try_release_ranged_shot(
		self,
		origin_x: float,
		origin_y: float,
		target_dx: float,
		target_dy: float,
		spawn_projectile: Callable[[float, float, float, float, int], None] | None,
		force: bool = False
	) -> None:
		if not self.pending_ranged_shot or self.ranged_shot_fired:
			return

		attack_frames = self.animation.frames.get("ATTACK_3", [])

		if not attack_frames:
			self.pending_ranged_shot = False
			self.ranged_shot_fired = True
			return

		on_last_frame = (
			self.animation.current_action == "ATTACK_3"
			and self.animation.current_index >= len(attack_frames) - 1
		)

		if not on_last_frame and not force:
			return

		dist_sq = target_dx * target_dx + target_dy * target_dy

		if spawn_projectile is not None and dist_sq > 0.000001:
			inv_dist = 1.0 / math.sqrt(dist_sq)
			spawn_projectile(origin_x, origin_y, target_dx * inv_dist, target_dy * inv_dist, self.damage)

		self.ranged_shot_fired = True
		self.pending_ranged_shot = False

	def _play_attack(self, action: str) -> None:
		if action not in self.animation.frames or not self.animation.frames[action]:
			self.current_attack_action = ""
			self.attack_anim_time_left = 0.0
			self._set_state(EnemyAction.IDLE)
			return

		action_duration = max(0.12, self.animation.get_duration(action) / 1000.0)
		self.current_attack_action = action
		self.attack_anim_time_left = min(action_duration, self.attack_cooldown)
		self._set_state(self._action_for_name(action))

_GUARD_DURATION       = 1.0
_GUARD_DAMAGE_REDUCTION = 0.60
_GUARD_COOLDOWN       = 3.0

class Knight(Enemy):
	def __init__(
		self,
		sprite_path: str | Path,
		base_health: int = 100,
		base_speed: float = 80.0,
		base_damage: int = 15,
		xp_value: int = 15
	) -> None:
		super().__init__(
			sprite_path = sprite_path,
			frame_width = 0,
			frame_height = 0,
			frame_gap = 0,
			actions = ["IDLE", "WALK", "ATTACK_1", "ATTACK_2", "GUARD", "HIT"],
			frame_rate = 120,
			base_health = base_health,
			base_speed = base_speed,
			base_damage = base_damage,
			xp_value = xp_value,
			armor = 0.35
		)
		self.base_scale = 1.5
		self.set_scale(1.0)
		self.attack_timer = 0.0
		self.attack_cooldown = 1.2
		self.melee_distance = 32.0
		self.contact_damage = False
		self.current_attack_action = ""
		self.attack_anim_time_left = 0.0
		self.melee_attack_actions = ["ATTACK_1", "ATTACK_2"]
		self.next_melee_attack_index = 0

		self.guard_timer = 0.0
		self.guard_cooldown_timer = 0.0

	def spawn(self, x: float, y: float, speed_multiplier: float = 1.0) -> None:
		super().spawn(x, y, speed_multiplier=speed_multiplier)
		self.attack_timer = 0.0
		self.current_attack_action = ""
		self.attack_anim_time_left = 0.0
		self.guard_timer = 0.0
		self.guard_cooldown_timer = 0.0

	@property
	def is_guarding(self) -> bool:
		return self.guard_timer > 0.0

	def take_damage(self, amount: int) -> None:
		if self.is_guarding:
			effective = int(amount * (1.0 - self.armor) * (1.0 - _GUARD_DAMAGE_REDUCTION))
			self.health -= max(1, effective)
		else:
			reduced = int(amount * (1.0 - self.armor))
			self.health -= max(1, reduced)

			if self.guard_cooldown_timer <= 0.0:
				self.guard_timer = _GUARD_DURATION
				self.guard_cooldown_timer = _GUARD_DURATION + _GUARD_COOLDOWN

		self._trigger_hit_animation()

	def update_towards(
		self,
		target_x: float,
		target_y: float,
		dt: float,
		player: object | None = None,
		spawn_projectile: Callable[[float, float, float, float, int], None] | None = None,
		move_target_x: float | None = None,
		move_target_y: float | None = None
	) -> None:
		self._update_statuses(dt)
		self.animation.update(int(dt * 1000))
		self.attack_timer = max(0.0, self.attack_timer - dt * self.slow_factor)
		self.attack_anim_time_left = max(0.0, self.attack_anim_time_left - dt)

		if self.guard_timer > 0.0:
			self.guard_timer = max(0.0, self.guard_timer - dt)
		if self.guard_cooldown_timer > 0.0:
			self.guard_cooldown_timer = max(0.0, self.guard_cooldown_timer - dt)

		if self.freeze_timer > 0.0:
			self._set_state(EnemyAction.IDLE)
			return

		if self.hit_anim_time_left > 0.0:
			self._set_state(EnemyAction.HIT)
			return

		if self.is_guarding and self.attack_anim_time_left <= 0.0:
			self._set_state(EnemyAction.GUARD)
			cx, cy = self.center
			dx = target_x - cx
			self.facing_dir = -1 if dx < 0 else 1
			return

		cx, cy = self.center
		dx = target_x - cx
		dy = target_y - cy
		self.facing_dir = -1 if dx < 0 else 1

		dist_sq = dx * dx + dy * dy
		if dist_sq <= 0.000001:
			self._set_state(EnemyAction.IDLE)
			return

		if self.attack_anim_time_left > 0.0 and self.current_attack_action:
			self._set_state(self._action_for_name(self.current_attack_action))
			return

		dist = math.sqrt(dist_sq)
		player_radius = float(getattr(player, "radius", 12.0))
		effective_melee_distance = max(self.melee_distance, self.radius + player_radius + 6.0)

		if dist <= effective_melee_distance:
			if self.attack_timer <= 0.0:
				self.attack_timer = self.attack_cooldown
				attack_action = self.melee_attack_actions[self.next_melee_attack_index]
				self.next_melee_attack_index = (self.next_melee_attack_index + 1) % len(self.melee_attack_actions)
				self._play_attack(attack_action)

				damage_fn = getattr(player, "take_damage", None)
				if callable(damage_fn):
					damage_fn(self.damage)
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
		speed = self.speed * self.slow_factor
		self.x += move_dx * inv_dist * speed * dt
		self.y += move_dy * inv_dist * speed * dt
		self._set_state(EnemyAction.WALK)

	def _play_attack(self, action: str) -> None:
		if action not in self.animation.frames or not self.animation.frames[action]:
			self.current_attack_action = ""
			self.attack_anim_time_left = 0.0
			self._set_state(EnemyAction.IDLE)
			return

		action_duration = max(0.12, self.animation.get_duration(action) / 1000.0)
		self.current_attack_action = action
		self.attack_anim_time_left = min(action_duration, self.attack_cooldown)
		self._set_state(self._action_for_name(action))


class EnemyCluster:
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
		max_spawn_rate: float = 1.35,
		max_active_enemies: int = 90,
	) -> None:
		self.assets_dir = Path(assets_dir)
		self.world_width = world_width
		self.world_height = world_height
		self.world_bounds = Rect(0, 0, max(1, world_width), max(1, world_height))
		self.soldier_sprite_path = self.assets_dir / "soldier_spritesheet.png"
		self.knight_sprite_path = self.assets_dir / "knight_spritesheet.png"
		self.arrow_sprite_path = self.assets_dir / "arrow.png"
		self.arrow_scale = 1.75

		from src.utils.window import load_image, scale_surface

		loaded_arrow = load_image(str(self.arrow_sprite_path), alpha=True)
        
		if self.arrow_scale != 1.0:
			scaled_w = max(1, int(loaded_arrow.get_width() * self.arrow_scale))
			scaled_h = max(1, int(loaded_arrow.get_height() * self.arrow_scale))
			self.arrow_sprite = scale_surface(loaded_arrow, scaled_w, scaled_h).convert_alpha()
		else:
			self.arrow_sprite = loaded_arrow

		self.arrow_radius = max(4.0, min(self.arrow_sprite.get_width(), self.arrow_sprite.get_height()) * 0.35)
		from typing import Any

		self._arrow_rotation_cache: dict[int, Any] = {}
		self._static_colliders: list[object] = []

		self.active: list[Enemy] = []
		self.pool: list[Enemy] = []
		self.arrows: list[Arrow] = []

		self.cluster = EnemyCluster(cell_size=96.0)

		self.elapsed_time = 0.0
		self.spawn_budget = 0.0
		self.base_spawn_rate = base_spawn_rate
		self.spawn_growth = spawn_growth
		self.max_spawn_rate = max_spawn_rate
		self.max_active_enemies = max(20, int(max_active_enemies))
		self._frame_index = 0
		self.sprite_scale = 2.0
		self.spawn_weights = [
			(lambda: Soldier(self.soldier_sprite_path, is_ranged=False), 0.5),
			(lambda: Soldier(self.soldier_sprite_path, is_ranged=True), 0.3),
			(lambda: Knight(self.knight_sprite_path), 0.2)
		]

	def update(self, player: object, dt: float) -> int:
		self._frame_index += 1
		self.elapsed_time += dt
		target_x, target_y = getattr(player, "center", (self.world_width * 0.5, self.world_height * 0.5))
		self._spawn_by_budget(dt, target_x=target_x, target_y=target_y)

		for enemy in self.active:
			enemy.update_towards(
				target_x,
				target_y,
				dt,
				player=player,
				spawn_projectile=self._spawn_arrow
			)
			self._resolve_enemy_static_collisions(enemy)
			self._clamp_enemy_to_world(enemy)

		self._update_arrows(player, dt)
		if len(self.active) <= 70 or self._frame_index % 2 == 0:
			self._resolve_enemy_collisions()

		return self._recycle_dead()

	def draw(self, camera_x: float = 0.0, camera_y: float = 0.0) -> None:
		screen = get_screen()
		left = camera_x - 96
		top = camera_y - 96
		right = camera_x + screen.get_width() + 96
		bottom = camera_y + screen.get_height() + 96

		for arrow in self.arrows:
			if arrow.x < left or arrow.x > right or arrow.y < top or arrow.y > bottom:
				continue

			arrow_surface = self._get_rotated_arrow_surface(arrow.angle_deg)
			blit_surface(
				arrow_surface,
				(
					arrow.x - camera_x - arrow_surface.get_width() * 0.5,
					arrow.y - camera_y - arrow_surface.get_height() * 0.5
				),
				target=screen
			)

		for enemy in self.active:
			if enemy.x + enemy.width < left or enemy.x > right or enemy.y + enemy.height < top or enemy.y > bottom:
				continue

			enemy.draw(camera_x=camera_x, camera_y=camera_y)

	def get_enemies(self) -> list[Enemy]:
		return self.active

	def collect_dead(self) -> int:
		return self._recycle_dead()

	def set_static_colliders(self, colliders: list[object]) -> None:
		self._static_colliders = [getattr(rect, 'copy')() if callable(getattr(rect, 'copy', None)) else rect for rect in colliders]

	def set_world_bounds(self, bounds: object) -> None:
		self.world_bounds = getattr(bounds, 'copy')() if callable(getattr(bounds, 'copy', None)) else bounds
		self.world_width = max(1, int(getattr(bounds, 'right', self.world_width)))
		self.world_height = max(1, int(getattr(bounds, 'bottom', self.world_height)))

	def set_scale(self, scale: float) -> None:
		self.sprite_scale = max(0.1, scale)

		for enemy in self.active:
			enemy.set_scale(self.sprite_scale)

		for enemy in self.pool:
			enemy.set_scale(self.sprite_scale)

	def _spawn_by_budget(self, dt: float, target_x: float, target_y: float) -> None:
		if len(self.active) >= self.max_active_enemies:
			self.spawn_budget = min(self.spawn_budget, 1.0)
			return

		rate = self.current_spawn_rate()
		self.spawn_budget += rate * dt

		spawned_this_frame = 0
		max_spawns_per_frame = 1

		while (
			self.spawn_budget >= 1.0
			and spawned_this_frame < max_spawns_per_frame
			and len(self.active) < self.max_active_enemies
		):
			self.spawn_budget -= 1.0
			self._spawn_enemy(target_x=target_x, target_y=target_y)
			spawned_this_frame += 1

	def current_spawn_rate(self) -> float:
		rate = self.base_spawn_rate * math.exp(self.spawn_growth * self.elapsed_time)
		return min(self.max_spawn_rate, rate)

	def _spawn_enemy(self, target_x: float, target_y: float) -> None:
		enemy = self.pool.pop() if self.pool else self._create_enemy()
		speed_multiplier = min(2.5, 1.0 + self.elapsed_time * 0.01)

		x, y = self._pick_spawn_position(enemy, target_x=target_x, target_y=target_y)
		enemy.spawn(x, y, speed_multiplier=speed_multiplier)
		enemy.set_scale(self.sprite_scale)

		self.active.append(enemy)

	def _create_enemy(self) -> Enemy:
		factories, weights = zip(*self.spawn_weights)
		factory = random.choices(factories, weights=weights, k=1)[0]

		return factory()

	def _pick_spawn_position(self, enemy: Enemy, target_x: float, target_y: float) -> tuple[float, float]:
		margin = max(enemy.width, enemy.height) + 24.0
		side = random.choice(["top", "bottom", "left", "right"])

		spawn_radius_x = min(max(280.0, self.world_bounds.width * 0.22), 780.0)
		spawn_radius_y = min(max(220.0, self.world_bounds.height * 0.22), 520.0)

		target_x = max(self.world_bounds.left, min(target_x, self.world_bounds.right))
		target_y = max(self.world_bounds.top, min(target_y, self.world_bounds.bottom))

		if side == "top":
			x = random.uniform(target_x - spawn_radius_x, target_x + spawn_radius_x)
			y = target_y - spawn_radius_y - margin
			return self._clamp_spawn_position(enemy, x, y)
		if side == "bottom":
			x = random.uniform(target_x - spawn_radius_x, target_x + spawn_radius_x)
			y = target_y + spawn_radius_y + margin
			return self._clamp_spawn_position(enemy, x, y)
		if side == "left":
			x = target_x - spawn_radius_x - margin
			y = random.uniform(target_y - spawn_radius_y, target_y + spawn_radius_y)
			return self._clamp_spawn_position(enemy, x, y)

		x = target_x + spawn_radius_x + margin
		y = random.uniform(target_y - spawn_radius_y, target_y + spawn_radius_y)

		return self._clamp_spawn_position(enemy, x, y)

	def _clamp_spawn_position(self, enemy: Enemy, x: float, y: float) -> tuple[float, float]:
		min_x = float(self.world_bounds.left)
		max_x = float(self.world_bounds.right - enemy.width)
		min_y = float(self.world_bounds.top)
		max_y = float(self.world_bounds.bottom - enemy.height)

		if max_x < min_x:
			center_x = self.world_bounds.centerx - enemy.width * 0.5
			x = center_x
		else:
			x = max(min_x, min(x, max_x))

		if max_y < min_y:
			center_y = self.world_bounds.centery - enemy.height * 0.5
			y = center_y
		else:
			y = max(min_y, min(y, max_y))

		return (x, y)

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

	def _clamp_enemy_to_world(self, enemy: Enemy) -> None:
		min_x = float(self.world_bounds.left)
		max_x = float(self.world_bounds.right - enemy.width)

		min_y = float(self.world_bounds.top)
		max_y = float(self.world_bounds.bottom - enemy.height)

		if max_x < min_x: enemy.x = self.world_bounds.centerx - enemy.width * 0.5
		else: enemy.x = max(min_x, min(enemy.x, max_x))

		if max_y < min_y: enemy.y = self.world_bounds.centery - enemy.height * 0.5
		else: enemy.y = max(min_y, min(enemy.y, max_y))

	def _resolve_enemy_static_collisions(self, enemy: Enemy) -> None:
		if not self._static_colliders:
			return

		center_x, center_y = enemy.center
		radius = enemy.radius

		for _ in range(2):
			resolved = False

			for rect in self._static_colliders:
				push_x, push_y = self._circle_rect_push(center_x, center_y, radius, rect)

				if push_x == 0.0 and push_y == 0.0:
					continue

				enemy.move_by(push_x, push_y)

				center_x += push_x
				center_y += push_y
				resolved = True

			if not resolved:
				break

	def _circle_rect_push(self, center_x: float, center_y: float, radius: float, rect: object) -> tuple[float, float]:
		closest_x = max(rect.left, min(center_x, rect.right))
		closest_y = max(rect.top, min(center_y, rect.bottom))

		dx = center_x - closest_x
		dy = center_y - closest_y
		dist_sq = dx * dx + dy * dy

		if dist_sq >= radius * radius:
			return (0.0, 0.0)

		if dist_sq <= 0.000001:
			left_clearance = center_x - rect.left
			right_clearance = rect.right - center_x
			top_clearance = center_y - rect.top
			bottom_clearance = rect.bottom - center_y

			min_clearance = min(left_clearance, right_clearance, top_clearance, bottom_clearance)
			if min_clearance == left_clearance:
				target_x = rect.left - radius - 0.01
				return (target_x - center_x, 0.0)
			if min_clearance == right_clearance:
				target_x = rect.right + radius + 0.01
				return (target_x - center_x, 0.0)
			if min_clearance == top_clearance:
				target_y = rect.top - radius - 0.01
				return (0.0, target_y - center_y)

			target_y = rect.bottom + radius + 0.01
			return (0.0, target_y - center_y)

		dist = max(0.000001, math.sqrt(dist_sq))
		overlap = radius - dist + 0.01

		nx = dx / dist
		ny = dy / dist

		return (nx * overlap, ny * overlap)

	def _intersects_static_colliders(self, center_x: float, center_y: float, radius: float) -> bool:
		for rect in self._static_colliders:
			if self._circle_intersects_rect(center_x, center_y, radius, rect):
				return True

		return False

	def _circle_intersects_rect(self, center_x: float, center_y: float, radius: float, rect: object) -> bool:
		closest_x = max(rect.left, min(center_x, rect.right))
		closest_y = max(rect.top, min(center_y, rect.bottom))

		dx = center_x - closest_x
		dy = center_y - closest_y

		return (dx * dx + dy * dy) < (radius * radius)

	def _spawn_arrow(self, x: float, y: float, dir_x: float, dir_y: float, damage: int) -> None:
		angle_deg = -math.degrees(math.atan2(dir_y, dir_x))
		arrow = Arrow(
			x=x,
			y=y,
			vel_x=dir_x,
			vel_y=dir_y,
			angle_deg=angle_deg,
			speed=260.0,
			damage=damage,
			radius=self.arrow_radius,
			life_left=3.0
		)
		self.arrows.append(arrow)

	def _get_rotated_arrow_surface(self, angle_deg: float):
		from src.utils.window import rotate_surface

		cache_key = int(round(angle_deg)) % 360
		cached = self._arrow_rotation_cache.get(cache_key)

		if cached is not None:
			return cached

		rotated = rotate_surface(self.arrow_sprite, cache_key).convert_alpha()
		self._arrow_rotation_cache[cache_key] = rotated

		return rotated

	def _update_arrows(self, player: object, dt: float) -> None:
		if not self.arrows:
			return

		player_center = getattr(player, "center", None)
		player_radius = getattr(player, "radius", 0)

		if player_center is None:
			return

		survivors: list[Arrow] = []
		for arrow in self.arrows:
			arrow.update(dt)

			if arrow.life_left <= 0.0:
				continue

			if not (self.world_bounds.left <= arrow.x <= self.world_bounds.right 
		   	   and self.world_bounds.top <= arrow.y <= self.world_bounds.bottom):
				continue

			if self._intersects_static_colliders(arrow.x, arrow.y, arrow.radius):
				continue

			dx = arrow.x - player_center[0]
			dy = arrow.y - player_center[1]
			dist_sq = dx * dx + dy * dy

			min_dist = arrow.radius + float(player_radius)

			if dist_sq <= min_dist * min_dist:
				damage_fn = getattr(player, "take_damage", None)
				if callable(damage_fn):
					damage_fn(arrow.damage)

				continue

			survivors.append(arrow)
		self.arrows = survivors
