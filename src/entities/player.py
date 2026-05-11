import math
from enum import Enum
from pathlib import Path
from typing import Iterable

from src.engine.animation import Animation
from src.engine.state_machine import StateMachine
from src.system.input import Input
from src.utils.window import get_screen, draw_rect, blit_surface, scale_surface, create_mask_surface
from src.utils.rect import Rect


class PlayerAction(Enum):
	IDLE     = "IDLE"
	WALK     = "WALK"
	HIT      = "HIT"
	DEATH    = "DEATH"
	GUARD    = "GUARD"


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

		# ------------------------------------------------------------------ #
		# Animation                                                            #
		# ------------------------------------------------------------------ #
		self.animation = Animation(
			sprite_path = self.assets_dir / "player_spritesheet.png",
			width=0,
			height=0,
			gap=0,
			actions=[a.value for a in PlayerAction],
			frame_rate=120
		)

		self.state_machine = StateMachine(list(PlayerAction), PlayerAction.IDLE)

		# Cache frame dimensions coming from the spritesheet slicer
		self.frame_width  = self.animation.frame_width
		self.frame_height = self.animation.frame_height

		self.base_scale = 1.25
		self.scale_multiplier = 1.0
		self.sprite_scale = self.base_scale * self.scale_multiplier

		# ------------------------------------------------------------------ #
		# Position                                                             #
		# ------------------------------------------------------------------ #
		self.x = float(spawn_x)
		self.y = float(spawn_y)

		# ------------------------------------------------------------------ #
		# Attributes                                                           #
		# ------------------------------------------------------------------ #
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
		self.health     = float(self.max_health)

		# ------------------------------------------------------------------ #
		# Invulnerability / blink                                              #
		# ------------------------------------------------------------------ #
		self.invuln_duration = 0.6
		self.invuln_left     = 0.0
		self.blink_interval  = 0.08
		self._blink_timer    = 0.0
		self._blink_on       = False

		# ------------------------------------------------------------------ #
		# Collision radius                                                     #
		# ------------------------------------------------------------------ #
		self.base_radius = max(10.0, min(self.frame_width, self.frame_height) * 0.45)
		self.radius      = self.base_radius
		self.set_scale(1.5)

		# ------------------------------------------------------------------ #
		# Misc                                                                 #
		# ------------------------------------------------------------------ #
		self.regen_timer = 0.0
		self.facing      = (0.0, 1.0)
		self.facing_dir  = 1               # 1 = right, -1 = left (mirrors sprite)
		self.last_facing_dir = 1

		# Attack / HIT / DEATH animation state
		self.hit_anim_time_left    = 0.0
		self.death_anim_time_left  = 0.0
		self.attack_anim_time_left = 0.0
		self.current_attack_action = ""
		self.next_attack_index = 0
		self.guard_anim_time_left = 0.0
		self.guard_hold = False
		self.death_hold = False

		self._sync_state_animation()
		self.init_progression()

	# ------------------------------------------------------------------ #
	# Properties                                                         #
	# ------------------------------------------------------------------ #

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

	# ------------------------------------------------------------------ #
	# Animation helpers                                                  #
	# ------------------------------------------------------------------ #

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

	# ------------------------------------------------------------------ #
	# Update                                                               #
	# ------------------------------------------------------------------ #

	def update(
		self,
		input_manager: Input,
		dt: float,
		world_width: int,
		world_height: int,
		world_bounds: Rect | None = None
	) -> None:
		# Always tick animation
		self.animation.update(int(dt * 1000))

		# Tick timed animation states
		self.hit_anim_time_left    = max(0.0, self.hit_anim_time_left    - dt)
		self.death_anim_time_left  = max(0.0, self.death_anim_time_left  - dt)
		self.attack_anim_time_left = max(0.0, self.attack_anim_time_left - dt)

		# ---- DEATH: lock animation, no input ----
		if self.is_dead():
			if self.death_anim_time_left > 0.0 or self.state_machine.state != PlayerAction.DEATH:
				self._set_state(PlayerAction.DEATH)
			elif not self.death_hold:
				self.death_hold = True
				self._hold_death_frame()

			self._blink_on  = False
			self.invuln_left = 0.0

			return

		keyboard = input_manager.keyboard
		guard_pressed = keyboard.key_pressed("SPACE")

		dx = 0.0
		dy = 0.0
		move_speed = self.attributes["move_speed"]

		if not guard_pressed:
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
				self.facing     = (dx / length, dy / length)

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

		# ---- Resolve animation state priority ----
		if guard_pressed and guard_available:
			self.hit_anim_time_left = 0.0
			self._set_state(PlayerAction.GUARD)
			if self.guard_hold:
				self._hold_guard_frame()
			return

		# HIT overrides everything while active
		if self.hit_anim_time_left > 0.0:
			self._set_state(PlayerAction.HIT)
			return

		# Attack animation holds until it finishes
		if self.attack_anim_time_left > 0.0 and self.current_attack_action:
			self._set_state(self._action_for_name(self.current_attack_action))
			return

		# Locomotion
		if is_moving: self._set_state(PlayerAction.WALK)
		else: self._set_state(PlayerAction.IDLE)

	# ------------------------------------------------------------------ #
	# World clamping                                                       #
	# ------------------------------------------------------------------ #

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

	# ------------------------------------------------------------------ #
	# Combat                                                               #
	# ------------------------------------------------------------------ #

	def resolve_enemy_collisions(self, enemies: Iterable[object]) -> None:
		max_damage = 0
		collided   = False

		player_center_x, player_center_y = self.center

		for enemy in enemies:
			enemy_center   = getattr(enemy, "center",         None)
			enemy_radius   = getattr(enemy, "radius",         None)
			enemy_damage   = getattr(enemy, "damage",         0)
			contact_damage = bool(getattr(enemy, "contact_damage", True))

			if enemy_center is None or enemy_radius is None:
				continue

			enemy_dx = enemy_center[0] - player_center_x
			enemy_dy = enemy_center[1] - player_center_y
			dist_sq  = enemy_dx * enemy_dx + enemy_dy * enemy_dy
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
				dist    = math.sqrt(max(dist_sq, 0.000001))
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

		reduced    = max(1, int(amount - self.attributes["defense"]))
		self.health = max(0.0, self.health - reduced)

		if self.is_dead():
			self._trigger_death_animation()
		else:
			self.invuln_left  = self.invuln_duration
			self._blink_timer = 0.0
			self._blink_on    = True
			if not self.is_guarding():
				self._trigger_hit_animation()

		return True

	# ------------------------------------------------------------------ #
	# Draw                                                                 #
	# ------------------------------------------------------------------ #

	def draw(self, camera_x: float = 0.0, camera_y: float = 0.0) -> None:
		screen = get_screen()

		frame = self.animation.get_frame_flipped(flip_x=self.facing_dir < 0)
		if frame is None:
			return

		if self.sprite_scale != 1.0:
			frame = scale_surface(frame, int(self.width), int(self.height))

		draw_x = int(self.x - camera_x)
		draw_y = int(self.y - camera_y)

		# Normal draw (skip if blinking OFF during invuln)
		if not self.invuln_left > 0.0 or self._blink_on:
			blit_surface(frame, (draw_x, draw_y), target=screen)

		# White-mask flash while invulnerable (same logic as Enemy HIT tint)
		if self.invuln_left > 0.0 and self._blink_on:
			mask_surf = create_mask_surface(frame, (255, 255, 255, 120), (0, 0, 0, 0))
			blit_surface(mask_surf, (draw_x, draw_y), target=screen)

		self._draw_health_bar(camera_x, camera_y)

	def _draw_health_bar(self, camera_x: float, camera_y: float) -> None:
		screen     = get_screen()
		bar_width  = int(self.width)
		bar_height = 6
		bar_gap    = 12
		bar_x      = int(self.x - camera_x)
		bar_y      = int(self.y - camera_y + self.height + bar_gap)

		draw_rect((200, 0, 0), (bar_x, bar_y, bar_width, bar_height), target=screen)

		missing = int(bar_width * (1.0 - self.health / self.max_health)) if self.max_health > 0 else bar_width
		if missing > 0:
			draw_rect((0, 0, 0), (bar_x + bar_width - missing, bar_y, missing, bar_height), target=screen)

	def _update_invulnerability(self, dt: float) -> None:
		if self.invuln_left <= 0.0:
			self._blink_on = False
			return

		self.invuln_left   = max(0.0, self.invuln_left - dt)
		self._blink_timer += dt

		if self._blink_timer >= self.blink_interval:
			self._blink_timer = 0.0
			self._blink_on    = not self._blink_on

	def _update_regen(self, dt: float) -> None:
		if self.is_dead():
			return

		self.regen_timer += dt

		if self.regen_timer >= 1.0:
			self.regen_timer = 0.0
			heal             = self.max_health * self.attributes["health_regen"]
			self.health      = min(self.max_health, self.health + heal)

	# ------------------------------------------------------------------ #
	# Progression                                                          #
	# ------------------------------------------------------------------ #

	def init_progression(self) -> None:
		self.level       = 1
		self.xp          = 0
		self.xp_to_next  = 25

	def add_xp(self, amount: int) -> int:
		self.xp        += amount
		levels_gained   = 0

		while self.xp >= self.xp_to_next:
			self.xp -= self.xp_to_next
			self._level_up()
			levels_gained += 1

		return levels_gained

	def _level_up(self) -> None:
		self.level      += 1
		self.xp_to_next  = int(self.xp_to_next * 1.45)

	def upgrade_attribute(self, name: str) -> bool:
		if name not in self.attribute_levels:
			return False
		if self.attribute_levels[name] >= self.max_attribute_level:
			return False

		self.attribute_levels[name] += 1

		if name == "max_health":
			self.max_health  = int(self.max_health * 1.15)
			self.health      = min(self.max_health, self.health + self.max_health * 0.15)
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
		return math.hypot(target_x - cx, target_y - cy)
