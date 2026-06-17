import math
from enum import Enum
from pathlib import Path
from typing import Iterable

from src.engine.animation import Animation
from src.engine.state_machine import StateMachine
from src.system.input import Input
from src.utils.window import get_screen, blit_surface, scale_surface, create_mask_surface, flip_surface
from src.utils.rect import Rect


class PlayerAction(Enum):
	IDLE = "IDLE"
	WALK = "WALK"
	HIT = "HIT"
	DEATH = "DEATH"
	GUARD = "GUARD"
	ROLL = "ROLL"


class Player:
	def __init__(
		self,
		assets_dir: str | Path,
		spawn_x: float,
		spawn_y: float,
		move_speed: float = 220.0,
		attack_speed: float = 1.2,
		strength: int = 6,
		max_health: int = 250,
		health_regen: float = 0.02,
		defense: int = 2
	) -> None:
		self.assets_dir = Path(assets_dir)

		self.animation = Animation(
			sprite_path = self.assets_dir / "player_spritesheet.png",
			width=0,
			height=0,
			gap=0,
			actions=[a.value for a in PlayerAction],
			frame_rate=120
		)

		self.state_machine = StateMachine(list(PlayerAction), PlayerAction.IDLE)

		self.frame_width = self.animation.frame_width
		self.frame_height = self.animation.frame_height

		self.base_scale = 1.25
		self.scale_multiplier = 1.0
		self.sprite_scale = self.base_scale * self.scale_multiplier

		self.x = float(spawn_x)
		self.y = float(spawn_y)

		self.attributes = {
			"max_health":   max_health,
			"health_regen": health_regen,
			"defense":      defense,
			"strength":     strength,
			"move_speed":   move_speed,
			"attack_speed": attack_speed
		}

		self.attribute_levels = { k: 0 for k in self.attributes }
		self.max_attribute_level = 5

		self.max_health = self.attributes["max_health"]
		self.health = float(self.max_health)

		self.invuln_duration = 0.6
		self.invuln_left = 0.0
		self.blink_interval = 0.08
		self._blink_timer = 0.0
		self._blink_on = False

		self.base_radius = max(10.0, min(self.frame_width, self.frame_height) * 0.45)
		self.radius = self.base_radius
		self.set_scale(1.5)

		self.regen_timer = 0.0
		self.facing = (0.0, 1.0)
		self.facing_dir = 1
		self.last_facing_dir = 1

		self.hit_anim_time_left = 0.0
		self.death_anim_time_left = 0.0
		self.attack_anim_time_left = 0.0
		self.current_attack_action = ""
		self.next_attack_index = 0
		self.guard_anim_time_left = 0.0
		self.guard_hold = False
		self.death_hold = False

		self.roll_duration = 0.28
		self.roll_speed = 520.0
		self.roll_cooldown = 0.8
		self.roll_time_left = 0.0
		self.roll_cooldown_left = 0.0
		self.roll_dir_x = 0.0
		self.roll_dir_y = 0.0
		self._shift_was_down = False
		self.roll_visual_time = 0.0
		self.damage_popups: list[tuple[int, float, float]] = []
		self.slow_factor = 1.0
		self.slow_timer = 0.0
		self.burn_dps = 0.0
		self.burn_timer = 0.0
		self.freeze_timer = 0.0
		self.ice_hits = 0
		self.ice_freeze_hits = 0
		self.ice_combo_timer = 0.0
		self._burn_popup_accumulator = 0.0
		self._burn_popup_timer = 0.0
		self._draw_cache: dict[tuple[str, int, bool, int, int], object] = {}
		self._mask_cache: dict[tuple[str, int, bool, int, int], object] = {}
		self._freeze_mask_cache: dict[tuple[str, int, bool, int, int], object] = {}
		self._burn_mask_cache: dict[tuple[str, int, bool, int, int], object] = {}
		self.xp_gain_multiplier = 1.45
		self.xp_growth_factor = 1.15
		self.base_xp_to_next = 25

		self._sync_state_animation()
		self.init_progression()

	@property
	def width(self) -> float:
		return float(self.frame_width) * self.sprite_scale

	@property
	def height(self) -> float:
		return float(self.frame_height) * self.sprite_scale

	@property
	def center(self) -> tuple[float, float]:
		return (
			self.x + self.width  * 0.5,
			self.y + self.height * 0.5
		)

	def set_scale(self, scale: float) -> None:
		self.scale_multiplier = max(0.1, scale)
		self.sprite_scale = max(0.1, self.base_scale * self.scale_multiplier)
		self.radius = self.base_radius * self.sprite_scale

	def is_dead(self) -> bool:
		return self.health <= 0.0

	def is_rolling(self) -> bool:
		return self.roll_time_left > 0.0

	def _start_roll(self, dx: float, dy: float) -> None:
		length = math.hypot(dx, dy)
		if length > 0.0:
			self.roll_dir_x = dx / length
			self.roll_dir_y = dy / length
		else:
			self.roll_dir_x = float(self.facing_dir)
			self.roll_dir_y = 0.0

		self.roll_time_left = self.roll_duration
		self.roll_visual_time = self.roll_duration
		self.roll_cooldown_left = self.roll_cooldown
		self.invuln_left = self.roll_duration
		self._blink_timer = 0.0
		self._blink_on = True
		self._set_state(PlayerAction.ROLL)

	def _sync_state_animation(self) -> None:
		self.animation.play(self.state_machine.state.value)

	def _set_state(self, state: PlayerAction) -> None:
		if self.state_machine.state != state:
			self.state_machine.set(state)

		self._sync_state_animation()

	def _action_for_name(self, action: str) -> PlayerAction:
		try:
			return PlayerAction(action)
		except ValueError:
			return PlayerAction.IDLE

	def _trigger_hit_animation(self) -> None:
		hit_frames = self.animation.frames.get("HIT", [])

		if hit_frames:
			duration = max(0.08, self.animation.get_duration("HIT") / 1000.0)
			self.hit_anim_time_left = duration
			self._set_state(PlayerAction.HIT)

	def _trigger_death_animation(self) -> None:
		death_frames = self.animation.frames.get("DEATH", [])

		if death_frames:
			duration = max(0.1, self.animation.get_duration("DEATH") / 1000.0)
			self.death_anim_time_left = duration

		self._set_state(PlayerAction.DEATH)
		self.death_hold = False

	def _hold_death_frame(self) -> None:
		frames = self.animation.frames.get("DEATH", [])
		if not frames:
			return

		self.animation.current_action = "DEATH"
		self.animation.current_index = max(0, len(frames) - 1)
		self.animation.elapsed_ms = 0

	def play_attack(self, action: str) -> bool:
		if self.attack_anim_time_left > 0.0:
			return False

		if action not in self.animation.frames or not self.animation.frames[action]:
			return False

		duration = max(0.12, self.animation.get_duration(action) / 1000.0)
		self.current_attack_action = action
		self.attack_anim_time_left = duration
		self._set_state(self._action_for_name(action))

		return True

	def is_guarding(self) -> bool:
		return self.guard_hold or self.guard_anim_time_left > 0.0

	def _hold_guard_frame(self) -> None:
		frames = self.animation.frames.get("GUARD", [])
		if not frames:
			return

		self.animation.current_action = "GUARD"
		self.animation.current_index = max(0, len(frames) - 1)
		self.animation.elapsed_ms = 0

	def update(
		self,
		input_manager: Input,
		dt: float,
		world_width: int,
		world_height: int,
		world_bounds: Rect | None = None,
		move_speed_multiplier: float = 1.0,
	) -> None:
		self.animation.update(int(dt * 1000))

		self.hit_anim_time_left = max(0.0, self.hit_anim_time_left    - dt)
		self.death_anim_time_left = max(0.0, self.death_anim_time_left  - dt)
		self.attack_anim_time_left = max(0.0, self.attack_anim_time_left - dt)
		self.roll_visual_time = max(0.0, self.roll_visual_time      - dt)
		self._update_statuses(dt)

		if self.is_dead():
			if self.death_anim_time_left > 0.0 or self.state_machine.state != PlayerAction.DEATH:
				self._set_state(PlayerAction.DEATH)
			elif not self.death_hold:
				self.death_hold = True
				self._hold_death_frame()

			self._blink_on = False
			self.invuln_left = 0.0

			return

		keyboard = input_manager.keyboard
		guard_pressed = keyboard.key_pressed("SPACE")

		self.roll_time_left = max(0.0, self.roll_time_left     - dt)
		self.roll_cooldown_left = max(0.0, self.roll_cooldown_left - dt)

		dx = 0.0
		dy = 0.0
		move_speed = self.attributes["move_speed"] * max(0.1, float(move_speed_multiplier)) * self.slow_factor
		is_frozen = self.freeze_timer > 0.0

		if self.is_rolling():
			self.x += self.roll_dir_x * self.roll_speed * dt
			self.y += self.roll_dir_y * self.roll_speed * dt
			self._clamp_to_world(world_width, world_height, world_bounds)
			self._update_invulnerability(dt)
			self._set_state(PlayerAction.ROLL)
			self._shift_was_down = keyboard.key_pressed("LSHIFT")
			return

		shift_now = keyboard.key_pressed("LSHIFT")
		shift_just_pressed = shift_now and not self._shift_was_down
		self._shift_was_down = shift_now

		if shift_just_pressed and self.roll_cooldown_left <= 0.0 and not self.is_dead() and not is_frozen:
			rdx = 0.0
			rdy = 0.0
			if keyboard.key_pressed("A") or keyboard.key_pressed("LEFT"):  rdx -= 1.0
			if keyboard.key_pressed("D") or keyboard.key_pressed("RIGHT"): rdx += 1.0
			if keyboard.key_pressed("W") or keyboard.key_pressed("UP"):    rdy -= 1.0
			if keyboard.key_pressed("S") or keyboard.key_pressed("DOWN"):  rdy += 1.0
			self._start_roll(rdx, rdy)
			return

		if not guard_pressed and not is_frozen:
			if keyboard.key_pressed("A") or keyboard.key_pressed("LEFT"):
				dx -= move_speed * dt
			if keyboard.key_pressed("D") or keyboard.key_pressed("RIGHT"):
				dx += move_speed * dt
			if keyboard.key_pressed("W") or keyboard.key_pressed("UP"):
				dy -= move_speed * dt
			if keyboard.key_pressed("S") or keyboard.key_pressed("DOWN"):
				dy += move_speed * dt

		self.x += dx
		self.y += dy
		self._clamp_to_world(world_width, world_height, world_bounds)

		is_moving = (dx != 0.0 or dy != 0.0)

		if is_moving:
			length = math.hypot(dx, dy)
			if length > 0.0:
				self.facing = (dx / length, dy / length)

				if dx != 0.0:
					self.last_facing_dir = -1 if dx < 0 else 1

				self.facing_dir = self.last_facing_dir

		self._update_invulnerability(dt)
		self._update_regen(dt)

		guard_frames = self.animation.frames.get("GUARD", [])
		guard_available = bool(guard_frames)
		if guard_pressed and guard_available:
			if not self.is_guarding():
				guard_duration = max(0.12, self.animation.get_duration("GUARD") / 1000.0)
				self.guard_anim_time_left = guard_duration
				self.guard_hold = False
			else:
				self.guard_anim_time_left = max(0.0, self.guard_anim_time_left - dt)
				if self.guard_anim_time_left <= 0.0:
					self.guard_hold = True
		else:
			self.guard_anim_time_left = 0.0
			self.guard_hold = False

		if guard_pressed and guard_available:
			self.hit_anim_time_left = 0.0
			self._set_state(PlayerAction.GUARD)
			if self.guard_hold:
				self._hold_guard_frame()
			return

		if self.hit_anim_time_left > 0.0:
			self._set_state(PlayerAction.HIT)
			return

		if self.attack_anim_time_left > 0.0 and self.current_attack_action:
			self._set_state(self._action_for_name(self.current_attack_action))
			return

		if is_moving: self._set_state(PlayerAction.WALK)
		else: self._set_state(PlayerAction.IDLE)

	def _clamp_to_world(
		self,
		world_width: int,
		world_height: int,
		world_bounds: object | None = None
	) -> None:
		if world_bounds is None:
			min_x, max_x = 0.0, float(world_width  - self.width)
			min_y, max_y = 0.0, float(world_height - self.height)
		else:
			min_x = float(world_bounds.left)
			max_x = float(world_bounds.right  - self.width)
			min_y = float(world_bounds.top)
			max_y = float(world_bounds.bottom - self.height)

		self.x = max(min_x, min(self.x, max_x)) if max_x >= min_x else min_x
		self.y = max(min_y, min(self.y, max_y)) if max_y >= min_y else min_y

	def resolve_enemy_collisions(self, enemies: Iterable[object]) -> None:
		max_damage = 0
		collided = False

		player_center_x, player_center_y = self.center

		for enemy in enemies:
			enemy_center = getattr(enemy, "center",         None)
			enemy_radius = getattr(enemy, "radius",         None)
			enemy_damage = getattr(enemy, "damage",         0)
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

	def take_damage(self, amount: int, defense_pierce: float = 0.0, bonus_vs_defense: float = 0.0) -> bool:
		if self.is_dead() or self.invuln_left > 0.0:
			return False

		defense = max(0.0, float(self.attributes["defense"]))
		defense_pierce = max(0.0, min(1.0, float(defense_pierce)))
		effective_defense = defense * (1.0 - defense_pierce)
		scaled_amount = float(amount) + defense * max(0.0, float(bonus_vs_defense))
		reduced = max(1, int(round(scaled_amount - effective_defense)))
		self.health = max(0.0, self.health - reduced)
		cx, cy = self.center
		self.damage_popups.append((reduced, cx, cy - self.height * 0.35))

		if self.is_dead():
			self._trigger_death_animation()
		else:
			self.invuln_left = self.invuln_duration
			self._blink_timer = 0.0
			self._blink_on = True
			if not self.is_guarding():
				self._trigger_hit_animation()

		return True

	def draw(self, camera_x: float = 0.0, camera_y: float = 0.0) -> None:
		screen = get_screen()

		frame = self.animation.get_frame_flipped(flip_x=self.facing_dir < 0)
		if frame is None:
			frame = self._fallback_frame(self.facing_dir < 0)
			if frame is None:
				return

		frame = self._get_draw_frame(frame, self.facing_dir < 0)

		draw_x = int(self.x - camera_x)
		draw_y = int(self.y - camera_y)

		if self.roll_visual_time > 0.0:
			progress = 1.0 - (self.roll_visual_time / max(0.001, self.roll_duration))
			for i in range(2, 0, -1):
				offset = i * 14.0 * (1.0 - progress)
				ghost_x = int(draw_x - self.roll_dir_x * offset)
				ghost_y = int(draw_y - self.roll_dir_y * offset)
				ghost = create_mask_surface(frame, (140, 210, 255, 35 + i * 25), (0, 0, 0, 0))
				blit_surface(ghost, (ghost_x, ghost_y), target=screen)

		if not self.invuln_left > 0.0 or self._blink_on:
			blit_surface(frame, (draw_x, draw_y), target=screen)

		if self.invuln_left > 0.0 and self._blink_on:
			mask_surf = self._get_mask_frame(frame, self.facing_dir < 0)
			blit_surface(mask_surf, (draw_x, draw_y), target=screen)

		if self.burn_timer > 0.0:
			burn_mask = self._get_tinted_mask_frame(frame, self._burn_mask_cache, self.facing_dir < 0, (255, 140, 80, 95))
			blit_surface(burn_mask, (draw_x, draw_y), target=screen)

		if self.freeze_timer > 0.0:
			freeze_mask = self._get_tinted_mask_frame(frame, self._freeze_mask_cache, self.facing_dir < 0, (80, 160, 255, 110))
			blit_surface(freeze_mask, (draw_x, draw_y), target=screen)

	def _get_draw_frame(self, frame, flip_x: bool):
		if self.sprite_scale == 1.0:
			return frame

		key = (
			self.animation.current_action,
			self.animation.current_index,
			flip_x,
			int(self.width),
			int(self.height),
		)
		cached = self._draw_cache.get(key)
		if cached is not None:
			return cached

		scaled = scale_surface(frame, int(self.width), int(self.height), smooth=False)
		self._draw_cache[key] = scaled
		return scaled

	def _fallback_frame(self, flip_x: bool):
		for action in ("WALK", "IDLE"):
			frames = self.animation.frames.get(action, [])
			if frames:
				index = min(self.animation.current_index, len(frames) - 1)
				frame = frames[index]
				return flip_surface(frame, flip_x=True) if flip_x else frame
		return None

	def _get_mask_frame(self, frame, flip_x: bool):
		key = (
			self.animation.current_action,
			self.animation.current_index,
			flip_x,
			int(self.width),
			int(self.height),
		)
		cached = self._mask_cache.get(key)
		if cached is not None:
			return cached

		mask = create_mask_surface(frame, (255, 255, 255, 120), (0, 0, 0, 0))
		self._mask_cache[key] = mask
		return mask

	def _get_tinted_mask_frame(self, frame, cache: dict, flip_x: bool, color: tuple[int, int, int, int]):
		key = (
			self.animation.current_action,
			self.animation.current_index,
			flip_x,
			int(self.width),
			int(self.height),
		)
		cached = cache.get(key)
		if cached is not None:
			return cached

		mask = create_mask_surface(frame, color, (0, 0, 0, 0))
		cache[key] = mask
		return mask

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

	def apply_burn(self, dps: float, duration: float, stack_cap: int = 1) -> None:
		dps = max(0.0, float(dps))
		stack_cap = max(1, int(stack_cap))

		if self.burn_timer <= 0.0:
			self.burn_dps = dps
		else:
			max_burn_dps = max(self.burn_dps, dps * stack_cap)
			self.burn_dps = min(max_burn_dps, self.burn_dps + dps)

		self.burn_timer = max(self.burn_timer, duration)

	def apply_slow(self, slow_factor: float, duration: float) -> None:
		self.slow_factor = min(self.slow_factor, float(slow_factor))
		self.slow_timer = max(self.slow_timer, float(duration))

	def register_ice_hit(self, freeze_hits: int, freeze_duration: float, combo_window: float = 0.0) -> None:
		if combo_window > 0.0 and self.ice_combo_timer <= 0.0:
			self.ice_hits = 0

		self.ice_hits += 1
		self.ice_freeze_hits += 1
		self.ice_combo_timer = max(self.ice_combo_timer, combo_window)

		if self.ice_freeze_hits >= max(1, int(freeze_hits)):
			self.ice_freeze_hits = 0
			self.ice_hits = 0
			self.ice_combo_timer = 0.0
			self.freeze_timer = max(self.freeze_timer, float(freeze_duration))

	def _update_statuses(self, dt: float) -> None:
		if self.is_dead():
			return

		if self.burn_timer > 0.0:
			before_health = float(self.health)
			self.burn_timer = max(0.0, self.burn_timer - dt)
			self.health = max(0.0, self.health - self.burn_dps * dt)
			self._record_burn_damage(before_health - float(self.health), dt)

			if self.burn_timer <= 0.0:
				self._flush_burn_popup()
				self.burn_dps = 0.0

		if self.slow_timer > 0.0:
			self.slow_timer = max(0.0, self.slow_timer - dt)
			if self.slow_timer <= 0.0:
				self.slow_factor = 1.0

		if self.freeze_timer > 0.0:
			self.freeze_timer = max(0.0, self.freeze_timer - dt)

		if self.ice_combo_timer > 0.0:
			self.ice_combo_timer = max(0.0, self.ice_combo_timer - dt)
			if self.ice_combo_timer <= 0.0:
				self.ice_hits = 0

		if self.health <= 0.0 and self.death_anim_time_left <= 0.0 and not self.death_hold:
			self._trigger_death_animation()

	def _record_burn_damage(self, amount: float, dt: float) -> None:
		if amount <= 0.0:
			return

		self._burn_popup_accumulator += amount
		self._burn_popup_timer += dt

		if self._burn_popup_accumulator >= 1.0 and self._burn_popup_timer >= 0.3:
			self._flush_burn_popup()

	def _flush_burn_popup(self) -> None:
		if self._burn_popup_accumulator < 0.5:
			self._burn_popup_accumulator = 0.0
			self._burn_popup_timer = 0.0
			return

		cx, cy = self.center
		self.damage_popups.append((
			max(1, int(round(self._burn_popup_accumulator))),
			float(cx),
			float(cy) - self.height * 0.35
		))
		self._burn_popup_accumulator = 0.0
		self._burn_popup_timer = 0.0

	def init_progression(self) -> None:
		self.level = 1
		self.xp = 0
		self.xp_to_next = self.base_xp_to_next

	def add_xp(self, amount: int) -> int:
		scaled_amount = max(1, int(round(amount * self.xp_gain_multiplier)))
		self.xp        += scaled_amount
		levels_gained = 0

		while self.xp >= self.xp_to_next:
			self.xp -= self.xp_to_next
			self._level_up()
			levels_gained += 1

		return levels_gained

	def _level_up(self) -> None:
		self.level      += 1
		self.xp_to_next = max(self.base_xp_to_next, int(self.xp_to_next * self.xp_growth_factor))

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
