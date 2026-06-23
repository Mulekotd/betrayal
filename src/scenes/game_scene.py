from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, Callable

from src.engine.camera import Camera
from src.engine.world import World
from src.entities.boss import Boss
from src.entities.enemy import EnemyManager
from src.entities.player import Player
from src.system.hud import HUD
from src.system.input import Input
from src.ui.damage_numbers import DamageNumbers
from src.ui.pause_menu import PauseMenu
from src.utils.rect import Rect
from src.utils.services import GameServices
from src.utils.types import SurfaceLike
from src.utils.window import blit_surface, create_surface, draw_arc, draw_circle, draw_line, draw_rect, get_screen, get_window, load_image, scale_surface, set_mouse_visible
from src.entities.weapon import FireSword, IceSword, Slash, Sword, WindSword

if TYPE_CHECKING:
	from src.game import Game


class GameScene:
	def __init__(self, services: GameServices, world_width: int, world_height: int, game: Game | None = None) -> None:
		self.game = game
		self.services = services
		assets_dir = self.services.images_dir

		self.viewport_width = world_width
		self.viewport_height = world_height

		self.world = World(
			images_dir=assets_dir,
			viewport_width=self.viewport_width,
			viewport_height=self.viewport_height
		)
		self.world_width = self.world.width
		self.world_height = self.world.height

		self.background_color = self.world.background_color
		grass_path = assets_dir / "grass.png"

		if grass_path.exists():
			self.ground_tile = load_image(str(grass_path), alpha=False)
		else:
			self.ground_tile = create_surface(64, 64)
			self.ground_tile.fill(self.background_color)

		self.ground_tile_width = max(1, self.ground_tile.get_width())
		self.ground_tile_height = max(1, self.ground_tile.get_height())
		self.camera = Camera(viewport_width=self.viewport_width, viewport_height=self.viewport_height)

		spawn_x = float(self.world.bounds.centerx)
		spawn_y = float(self.world.bounds.centery)

		self.player = Player(
			assets_dir=assets_dir,
			spawn_x=spawn_x,
			spawn_y=spawn_y
		)

		self.enemy_manager = EnemyManager(
			assets_dir=assets_dir,
			world_width=self.world_width,
			world_height=self.world_height
		)

		self.enemy_manager.set_world_bounds(self.world.bounds)
		self.world.rebuild(player_center=self.player.center, player_radius=self.player.radius)
		self.enemy_manager.set_static_colliders(self.world.static_colliders)

		self.total_kills = 0

		self.pending_level_ups = 0
		self.level_up_active = False
		self.level_up_options: list[str] = []
		self.level_up_hover: int | None = None

		self.card_hover_t: list[float] = [0.0, 0.0, 0.0]
		self.CARD_ANIM_SPEED = 8.0

		self.ui_font_medium = self.services.fonts.mini(28)
		self.ui_font_title = self.services.fonts.title(42)
		self.damage_numbers = DamageNumbers(self.services.fonts.mini(24))

		self.pause_menu = PauseMenu(
			self.viewport_width,
			self.viewport_height,
			self.services.fonts.title(56),
			self.services.fonts.mini(30)
		)

		self.pause_menu.set_actions(
			resume=self._resume_game,
			options=self._open_settings,
			quit_game=self._quit_to_menu
		)

		self.hud = HUD(
			viewport_width=self.viewport_width,
			viewport_height=self.viewport_height,
			fonts=self.services.fonts,
			images_dir=self.services.images_dir,
			padding=0
		)

		self.level_up_icon_size = 38
		self.level_up_icon: SurfaceLike | None = None
		level_up_icon_path = self.services.images_dir / "health_up.png"

		if level_up_icon_path.exists():
			self.level_up_icon = load_image(str(level_up_icon_path), alpha=True)
			if self.level_up_icon is not None:
				self.level_up_icon = scale_surface(
					self.level_up_icon,
					self.level_up_icon_size,
					self.level_up_icon_size,
					smooth=True
				)

		self.level_up_icons: dict[str, SurfaceLike] = {}
		upgrade_dir = self.services.images_dir / "upgrades"
		upgrade_icon_files = {
			"max_health":   "health_up.png",
			"defense":      "armor.png",
			"health_regen": "regen.png",
			"move_speed":   "move_speed.png",
			"attack_speed": "attack_speed.png",
			"strength":     "strength.png"
		}

		for attribute, filename in upgrade_icon_files.items():
			icon_path = upgrade_dir / filename
			if icon_path.exists():
				icon = load_image(str(icon_path), alpha=True)
				if icon is not None:
					self.level_up_icons[attribute] = scale_surface(
						icon,
						self.level_up_icon_size,
						self.level_up_icon_size,
						smooth=False
					)

		self.weapon_type = "fire"
		self.weapon_timer = 0.0
		self.run_time: float = 0.0
		self.weapon_slashes: list[Slash] = []
		self._slash_arc_cache: dict[tuple[int, int, int, int, int, tuple[int, int, int], int], SurfaceLike] = {}
		self._slash_circle_cache: dict[tuple[int, int, tuple[int, int, int], int], SurfaceLike] = {}
		self.enemy_activity_margin_x = max(220.0, self.viewport_width * 0.45)
		self.enemy_activity_margin_y = max(180.0, self.viewport_height * 0.45)
		self.show_fps = False
		self.swords: dict[str, Sword] = {
			"fire": FireSword(),
			"ice": IceSword(),
			"wind": WindSword()
		}
		self.boss: Boss | None = None
		self.boss_spawned = False
		self.boss_spawn_time = 180.0
		self.boss_slashes: list[Slash] = []
		self.boss_spawn_rate_multiplier = 0.08
		self.victory_active = False
		self.victory_hover: int | None = None

		self.player_dead = False
		self.game_over_title_font = self.services.fonts.get(68)
		self.game_over_hint_font = self.services.fonts.get(24)

		# Iniciamos a trilha aqui para o menu poder reutilizar a mesma instância de áudio.
		if self.game and self.game.audio:
			self.game.audio.play_sound("theme", repeat=True)

	def handle_events(self, input_manager: Input | None) -> None:
		if input_manager is None:
			return

		if input_manager.keyboard.key_down("X"):
			self.show_fps = not self.show_fps

		if self.victory_active:
			return

		if input_manager.keyboard.key_down("ESC"):
			self.pause_menu.toggle()

	def update(self, dt: float, input_manager: Input | None) -> None:
		if input_manager is None:
			return

		if self.victory_active:
			self._update_victory(input_manager)
			return

		if self._is_game_paused():
			self.pause_menu.update(input_manager)
			return

		if self.player_dead:
			self._update_game_over(input_manager)
			return

		if self.level_up_active:
			self.damage_numbers.update(dt)
			self._update_level_up(input_manager)
			return

		self._handle_weapon_selection(input_manager)
		self._apply_current_weapon_modifiers()
		self.player.update(
			input_manager,
			dt,
			self.world_width,
			self.world_height,
			world_bounds=self.world.bounds,
			move_speed_multiplier=self._current_move_speed_multiplier(),
		)

		self.run_time += dt
		self._resolve_player_static_collisions()

		player_center_x, player_center_y = self.player.center

		self.camera.follow(player_center_x, player_center_y)
		self._clamp_camera_to_world()

		if self.player.is_dead():
			if self.player.death_anim_time_left > 0.0:
				return

			self.player_dead = True
			self.level_up_active = False
			self.level_up_options = []
			self.level_up_hover = None
			self.pending_level_ups = 0
			return

		self._spawn_boss_if_ready()

		self.enemy_manager.set_spawn_rate_multiplier(
			self.boss_spawn_rate_multiplier if self._is_boss_active() else 1.0
		)

		before_update = len(self.enemy_manager.get_enemies()) + (1 if self._is_boss_active() else 0)
		xp_gained = self.enemy_manager.update(
			self.player,
			dt,
			active_bounds=self._camera_world_bounds(self.enemy_activity_margin_x, self.enemy_activity_margin_y)
		)
		xp_gained += self._update_boss(dt)
		self._update_player_slashes(dt)
		self._update_boss_slashes(dt)

		xp_gained += self.enemy_manager.collect_dead()
		after_update = len(self.enemy_manager.get_enemies()) + (1 if self._is_boss_active() else 0)

		self.player.resolve_enemy_collisions(self._near_player_enemies(90.0))
		self._drain_enemy_damage_popups()
		self._drain_player_damage_popups()
		self.damage_numbers.update(dt)

		if xp_gained:
			levels_gained = self.player.add_xp(xp_gained)
			if levels_gained:
				if self._available_upgrade_attributes():
					self.pending_level_ups += levels_gained
					self._open_level_up()

		if after_update < before_update:
			self.total_kills += before_update - after_update

	def render(self) -> None:
		self._draw_tiled_ground()
		self.world.draw(camera_x=self.camera.x, camera_y=self.camera.y)

		is_paused = self._is_game_paused()
		set_mouse_visible(self.level_up_active or is_paused or self.victory_active)

		self.enemy_manager.draw(camera_x=self.camera.x, camera_y=self.camera.y)
		if self.boss is not None:
			self.boss.draw(camera_x=self.camera.x, camera_y=self.camera.y)
		self._draw_slashes(self.boss_slashes)
		self.player.draw(camera_x=self.camera.x, camera_y=self.camera.y)
		self._draw_player_slashes()
		self.damage_numbers.draw(self.camera.x, self.camera.y)
		self._draw_boss_direction_indicator()
		self.hud.draw(
			self.player,
			self.total_kills,
			self.weapon_type,
			run_time=self.run_time,
			fps_value=get_window().get_fps() if self.show_fps else None
		)

		if self.level_up_active and not is_paused:
			self._draw_level_up_overlay()

		if self.player_dead:
			self._draw_game_over_overlay()
		elif self.victory_active:
			self._draw_victory_overlay()

		self.pause_menu.draw()

	def _is_game_paused(self) -> bool:
		return self.pause_menu.active

	def _draw_tiled_ground(self) -> None:
		screen = get_screen()

		start_x = (-int(self.camera.x) % self.ground_tile_width) - self.ground_tile_width
		start_y = (-int(self.camera.y) % self.ground_tile_height) - self.ground_tile_height

		for y in range(start_y, self.viewport_height + self.ground_tile_height, self.ground_tile_height):
			for x in range(start_x, self.viewport_width + self.ground_tile_width, self.ground_tile_width):
				screen.blit(self.ground_tile, (x, y))

	def _update_game_over(self, input_manager: Input) -> None:
		if input_manager.keyboard.key_pressed("ENTER"):
			self._restart_run()
			self.run_time = 0

	def _resume_game(self) -> None:
		self.pause_menu.close()

	def _open_settings(self) -> None:
		from src.scenes.settings_scene import SettingsScene

		if self.game is None:
			return

		self.game.set_scene(
			SettingsScene(
				game=self.game,
				services=self.services,
				world_width=self.viewport_width,
				world_height=self.viewport_height,
				on_back=lambda: self.game.set_scene(self)
			)
		)

	def _quit_to_menu(self) -> None:
		from src.scenes.menu_scene import MenuScene

		if self.game is None:
			return

		# Encerramos a trilha antes de recriar o menu para evitar sobreposição de playback.
		if self.game.audio:
			self.game.audio.stop_sound("theme")

		self.pause_menu.close()
		self.game.set_scene(
			MenuScene(
				game=self.game,
				services=self.services,
				world_width=self.viewport_width,
				world_height=self.viewport_height
			)
		)

	def _restart_run(self) -> None:
		assets_dir = self.services.images_dir

		self.player = Player(
			assets_dir=assets_dir,
			spawn_x=float(self.world.bounds.centerx),
			spawn_y=float(self.world.bounds.centery)
		)

		self.enemy_manager = EnemyManager(
			assets_dir=assets_dir,
			world_width=self.world_width,
			world_height=self.world_height
		)
		self.enemy_manager.set_world_bounds(self.world.bounds)
		self.world.rebuild(player_center=self.player.center, player_radius=self.player.radius)
		self.enemy_manager.set_static_colliders(self.world.static_colliders)

		self.total_kills = 0
		self.pending_level_ups = 0
		self.level_up_active = False
		self.level_up_options = []
		self.level_up_hover = None
		self.player_dead = False
		self.weapon_type = "fire"
		self.weapon_timer = 0.0
		self.weapon_slashes = []
		self.boss = None
		self.boss_spawned = False
		self.boss_slashes = []
		self.victory_active = False
		self.victory_hover = None

		self.camera.follow(*self.player.center)
		self._clamp_camera_to_world()

	def _start_new_run(self) -> None:
		self._restart_run()
		self.run_time = 0.0

	def _draw_game_over_overlay(self) -> None:
		screen = get_screen()

		overlay = create_surface(self.viewport_width, self.viewport_height, alpha=True)
		overlay.fill((0, 0, 0, 170))
		blit_surface(overlay, (0, 0), target=screen)

		title_surface = self.game_over_title_font.render("YOU DIED", True, (235, 100, 100))
		title_x = (self.viewport_width - title_surface.get_width()) // 2
		title_y = int(self.viewport_height * 0.32)
		screen.blit(title_surface, (title_x, title_y))

		hint_surface = self.game_over_hint_font.render("Press Enter to restart", True, (230, 230, 230))
		hint_x = (self.viewport_width - hint_surface.get_width()) // 2
		hint_y = title_y + title_surface.get_height() + 18
		screen.blit(hint_surface, (hint_x, hint_y))

	def _activate_victory(self) -> None:
		self.victory_active = True
		self.victory_hover = None
		self.boss_slashes = []
		self.level_up_active = False
		self.level_up_options = []
		self.level_up_hover = None
		self.pending_level_ups = 0
		self.pause_menu.close()

	def _victory_buttons(self) -> list[tuple[str, Rect, Callable[[], None]]]:
		button_w = 250
		button_h = 56
		gap = 18
		total_w = button_w * 2 + gap
		start_x = (self.viewport_width - total_w) // 2
		y = int(self.viewport_height * 0.58)

		return [
			("RESTART", Rect(start_x, y, button_w, button_h), self._start_new_run),
			("MENU", Rect(start_x + button_w + gap, y, button_w, button_h), self._quit_to_menu),
		]

	def _update_victory(self, input_manager: Input) -> None:
		mouse = input_manager.mouse
		mx, my = mouse.get_position()
		self.victory_hover = None

		for index, (_, rect, action) in enumerate(self._victory_buttons()):
			if rect.left <= mx <= rect.right and rect.top <= my <= rect.bottom:
				self.victory_hover = index
				if mouse.button_down(mouse.LEFT):
					action()
				return

	def _draw_victory_overlay(self) -> None:
		screen = get_screen()
		overlay = create_surface(self.viewport_width, self.viewport_height, alpha=True)
		overlay.fill((0, 0, 0, 185))
		blit_surface(overlay, (0, 0), target=screen)

		title_surface = self.game_over_title_font.render("CONGRATULATIONS", True, (245, 220, 120))
		subtitle_surface = self.ui_font_medium.render("You defeated the boss", False, (235, 235, 225))
		title_x = (self.viewport_width - title_surface.get_width()) // 2
		title_y = int(self.viewport_height * 0.28)
		subtitle_x = (self.viewport_width - subtitle_surface.get_width()) // 2
		subtitle_y = title_y + title_surface.get_height() + 20
		screen.blit(title_surface, (title_x, title_y))
		screen.blit(subtitle_surface, (subtitle_x, subtitle_y))

		for index, (label, rect, _) in enumerate(self._victory_buttons()):
			hover = index == self.victory_hover
			fill = (48, 58, 42) if hover else (28, 34, 28)
			border = (245, 220, 120) if hover else (120, 135, 110)
			draw_rect(fill, rect, border_radius=10, target=screen)
			draw_rect(border, rect, width=2, border_radius=10, target=screen)

			text = self.pause_menu.button_font.render(label, False, (245, 245, 235))
			screen.blit(
				text,
				(
					rect.centerx - text.get_width() // 2,
					rect.centery - text.get_height() // 2
				)
			)

	def _handle_weapon_selection(self, input_manager: Input) -> None:
		keyboard = input_manager.keyboard
		mouse = input_manager.mouse

		if keyboard.key_pressed("1"):
			self.weapon_type = "fire"
		elif keyboard.key_pressed("2"):
			self.weapon_type = "ice"
		elif keyboard.key_pressed("3"):
			self.weapon_type = "wind"

		if mouse.button_down(mouse.LEFT):
			mx, my = mouse.get_position()
			picked = self.hud.pick_weapon(mx, my)
			if picked is not None:
				self.weapon_type = picked

	def _current_sword(self) -> Sword | None:
		return self.swords.get(self.weapon_type)

	def _current_move_speed_multiplier(self) -> float:
		sword = self._current_sword()
		if sword is None:
			return 1.0

		return float(getattr(sword, "get_move_speed_multiplier", lambda: 1.0)())

	def _current_attack_speed_multiplier(self) -> float:
		sword = self._current_sword()
		if sword is None:
			return 1.0

		return float(getattr(sword, "get_attack_speed_multiplier", lambda: 1.0)())

	def _apply_current_weapon_modifiers(self) -> None:
		sword = self._current_sword()
		if sword is None:
			self.player.set_combat_modifiers()
			return

		self.player.set_combat_modifiers(
			defense_multiplier=float(getattr(sword, "get_defense_multiplier", lambda: 1.0)()),
			health_regen_multiplier=float(getattr(sword, "get_health_regen_multiplier", lambda: 1.0)())
		)

	def _is_boss_active(self) -> bool:
		return self.boss is not None and not self.boss.is_dead()

	def _spawn_boss_if_ready(self) -> None:
		if self.boss_spawned or self.run_time < self.boss_spawn_time:
			return

		boss = Boss(self.services.images_dir / "boss_spritesheet.png")
		self.world.clear_area(self.world.boss_arena_rect())
		self.enemy_manager.set_static_colliders(self.world.static_colliders)

		spawn_x = float(self.world.bounds.centerx - boss.width * 0.5)
		spawn_y = float(self.world.bounds.centery - boss.height * 0.5)
		boss.spawn(spawn_x, spawn_y)
		self.boss = boss
		self.boss_spawned = True
		self.enemy_manager.clear_spawn_budget()

	def _update_boss(self, dt: float) -> int:
		if self.boss is None:
			return 0

		self.boss.set_damage_multiplier(self.enemy_manager.current_damage_multiplier(self.player))
		player_x, player_y = self.player.center
		self.boss.update_towards(
			player_x,
			player_y,
			dt,
			player=self.player,
			spawn_slash=self._spawn_boss_slash
		)
		self.enemy_manager.resolve_static_collisions_for(self.boss)
		self.enemy_manager.clamp_to_world(self.boss)

		if not self.boss.is_dead():
			return 0

		xp_reward = int(getattr(self.boss, "xp_value", 0))
		self._spawn_enemy_status_popups(self.boss)
		self.boss = None
		self.boss_slashes = []
		self._activate_victory()
		return xp_reward

	def _spawn_boss_slash(self, slash: Slash) -> None:
		self.boss_slashes.append(slash)

	def _update_player_slashes(self, dt: float) -> None:
		sword = self._current_sword()

		if sword is None:
			return

		attack_speed = float(self.player.attributes.get("attack_speed", 1.0)) * self._current_attack_speed_multiplier()

		self.weapon_timer = max(0.0, self.weapon_timer - dt)
		if self.weapon_timer <= 0.0 and not self.player.is_guarding():
			self.weapon_slashes.extend(sword.spawn_slashes(self.player))
			self.weapon_timer = sword.get_cooldown(attack_speed)

			# O som acompanha o disparo do slash, não o impacto, para manter o feedback responsivo.
			sound_key = f"{self.weapon_type}_slash"
			if self.game and self.game.audio:
				self.game.audio.play_sound(sound_key)

		enemies = self._near_player_enemies(180.0)

		player_strength = int(self.player.attributes.get("strength", 1))
		for slash in self.weapon_slashes:
			slash.update(dt)

			if not slash.is_active():
				continue

			self._apply_slash_damage(slash, enemies, player_strength)

		self.weapon_slashes = [slash for slash in self.weapon_slashes if slash.is_alive()]

	def _near_player_enemies(self, extra_radius: float) -> list[object]:
		px, py = self.player.center
		player_radius = float(getattr(self.player, "radius", 0.0))
		result: list[object] = []

		for enemy in self.enemy_manager.get_enemies():
			center = getattr(enemy, "center", None)
			if center is None:
				continue

			radius = player_radius + float(getattr(enemy, "radius", 0.0)) + extra_radius
			dx = center[0] - px
			dy = center[1] - py
			if dx * dx + dy * dy <= radius * radius:
				result.append(enemy)

		if self._is_boss_active():
			boss_center = getattr(self.boss, "center", None)
			if boss_center is not None:
				radius = player_radius + float(getattr(self.boss, "radius", 0.0)) + extra_radius
				dx = boss_center[0] - px
				dy = boss_center[1] - py
				if dx * dx + dy * dy <= radius * radius:
					result.append(self.boss)

		return result

	def _update_boss_slashes(self, dt: float) -> None:
		if not self.boss_slashes or self.player.is_dead():
			self.boss_slashes = [slash for slash in self.boss_slashes if slash.is_alive()]
			return

		for slash in self.boss_slashes:
			slash.update(dt)

			if not slash.is_active():
				continue

			self._apply_slash_to_player(slash)

		self.boss_slashes = [slash for slash in self.boss_slashes if slash.is_alive()]

	def _apply_slash_damage(self, slash: Slash, enemies: list[object], player_strength: int) -> None:
		if not slash.is_active():
			return

		for enemy in enemies:
			if getattr(enemy, "is_dead", None) and enemy.is_dead():
				continue

			enemy_id = id(enemy)
			if enemy_id in slash.hit_ids:
				continue

			enemy_center = getattr(enemy, "center", None)
			if enemy_center is None:
				continue

			enemy_radius = float(getattr(enemy, "radius", 0.0))

			dx = enemy_center[0] - slash.x
			dy = enemy_center[1] - slash.y
			dist_sq = dx * dx + dy * dy

			hit_range = slash.radius + enemy_radius * 0.5
			if dist_sq > hit_range * hit_range:
				continue

			if slash.shape != "circle":
				enemy_angle = math.atan2(dy, dx)
				slash_angle = math.atan2(slash.dir_y, slash.dir_x)
				angle_diff = (enemy_angle - slash_angle + math.pi) % (2 * math.pi) - math.pi
				if abs(angle_diff) > math.radians(slash.arc_deg * 0.5):
					continue

			damage_fn = getattr(enemy, "take_damage", None)
			if callable(damage_fn):
				before_health = float(getattr(enemy, "health", 0.0))
				resolve_hit_damage = getattr(slash, "resolve_hit_damage", None)
				hit_damage = int(slash.damage)
				if callable(resolve_hit_damage):
					hit_damage = max(1, int(resolve_hit_damage(enemy, player_strength, slash)))

				damage_fn(hit_damage)

				if slash.on_hit is not None:
					slash.on_hit(enemy, player_strength, slash)

				after_health = float(getattr(enemy, "health", before_health))
				damage_done = max(1, int(round(before_health - after_health)))
				enemy_center = getattr(enemy, "center", (slash.x, slash.y))
				self._spawn_damage_number(
					damage_done,
					float(enemy_center[0]),
					float(enemy_center[1]) - float(getattr(enemy, "height", 0.0)) * 0.35,
					(255, 235, 120),
				)

			slash.hit_ids.add(enemy_id)

	def _apply_slash_to_player(self, slash: Slash) -> None:
		if not slash.is_active() or self.player.is_dead():
			return

		player_id = id(self.player)
		if player_id in slash.hit_ids:
			return

		player_center = self.player.center
		player_radius = float(getattr(self.player, "radius", 0.0))
		dx = player_center[0] - slash.x
		dy = player_center[1] - slash.y
		dist_sq = dx * dx + dy * dy

		hit_range = slash.radius + player_radius * 0.5
		if dist_sq > hit_range * hit_range:
			return

		if slash.shape != "circle":
			player_angle = math.atan2(dy, dx)
			slash_angle = math.atan2(slash.dir_y, slash.dir_x)
			angle_diff = (player_angle - slash_angle + math.pi) % (2 * math.pi) - math.pi
			if abs(angle_diff) > math.radians(slash.arc_deg * 0.5):
				return

		resolve_hit_damage = getattr(slash, "resolve_hit_damage", None)
		hit_damage = int(slash.damage)
		if callable(resolve_hit_damage):
			hit_damage = max(1, int(resolve_hit_damage(self.player, 0, slash)))

		took_damage = self.player.take_damage(hit_damage, damage_type="melee")
		if took_damage and slash.on_hit is not None:
			slash.on_hit(self.player, 0, slash)

		if took_damage:
			slash.hit_ids.add(player_id)

	def _spawn_damage_number(self, amount: int, x: float, y: float, color: tuple[int, int, int]) -> None:
		self.damage_numbers.spawn(amount, x, y, color)

	def _drain_player_damage_popups(self) -> None:
		popups = getattr(self.player, "damage_popups", None)
		if not popups:
			return

		for amount, x, y in popups:
			self._spawn_damage_number(int(amount), float(x), float(y), (255, 85, 85))

		popups.clear()

	def _drain_enemy_damage_popups(self) -> None:
		for enemy in self.enemy_manager.get_enemies():
			self._spawn_enemy_status_popups(enemy)

		if self.boss is not None:
			self._spawn_enemy_status_popups(self.boss)

	def _spawn_enemy_status_popups(self, enemy: object) -> None:
		popups = getattr(enemy, "status_damage_popups", None)
		if not popups:
			return

		for amount, x, y in popups:
			self._spawn_damage_number(int(amount), float(x), float(y), (255, 150, 80))

		popups.clear()

	def _draw_player_slashes(self) -> None:
		self._draw_slashes(self.weapon_slashes)

	def _draw_slashes(self, slashes: list[Slash]) -> None:
		if not slashes:
			return

		screen = get_screen()

		for slash in slashes:
			if not slash.is_active():
				continue

			alpha = slash.alpha()
			if alpha <= 0:
				continue

			if slash.shape == "circle":
				arc_surface, radius, pad = self._get_slash_circle_surface(slash, alpha)
			else:
				arc_surface, radius, pad = self._get_slash_arc_surface(slash, alpha)

			blit_surface(
				arc_surface,
				(
					slash.x - self.camera.x - radius - pad,
					slash.y - self.camera.y - radius - pad
				),
				target=screen
			)

	def _draw_boss_direction_indicator(self) -> None:
		if not self._is_boss_active() or self.boss is None:
			return

		boss_left = self.boss.x - self.camera.x
		boss_top = self.boss.y - self.camera.y
		boss_right = boss_left + self.boss.width
		boss_bottom = boss_top + self.boss.height
		if boss_right >= 0 and boss_left <= self.viewport_width and boss_bottom >= 0 and boss_top <= self.viewport_height:
			return

		screen = get_screen()
		center_x = self.viewport_width * 0.5
		center_y = self.viewport_height * 0.5
		boss_x, boss_y = self.boss.center
		dir_x = boss_x - (self.camera.x + center_x)
		dir_y = boss_y - (self.camera.y + center_y)
		length = max(0.0001, math.hypot(dir_x, dir_y))
		dir_x /= length
		dir_y /= length

		margin = 54.0
		half_w = max(1.0, center_x - margin)
		half_h = max(1.0, center_y - margin)
		scale_x = half_w / max(0.0001, abs(dir_x))
		scale_y = half_h / max(0.0001, abs(dir_y))
		scale = min(scale_x, scale_y)

		tip_x = center_x + dir_x * scale
		tip_y = center_y + dir_y * scale
		tail_x = tip_x - dir_x * 30.0
		tail_y = tip_y - dir_y * 30.0
		angle = math.atan2(dir_y, dir_x)

		left_wing = angle + math.pi - 0.65
		right_wing = angle + math.pi + 0.65
		wing_length = 18.0
		left_x = tip_x + math.cos(left_wing) * wing_length
		left_y = tip_y + math.sin(left_wing) * wing_length
		right_x = tip_x + math.cos(right_wing) * wing_length
		right_y = tip_y + math.sin(right_wing) * wing_length

		draw_circle((25, 18, 12, 170), (tip_x, tip_y), 24, target=screen)
		draw_line((255, 226, 112), (tail_x, tail_y), (tip_x, tip_y), width=6, target=screen)
		draw_line((255, 226, 112), (tip_x, tip_y), (left_x, left_y), width=5, target=screen)
		draw_line((255, 226, 112), (tip_x, tip_y), (right_x, right_y), width=5, target=screen)
		draw_line((95, 38, 24), (tail_x, tail_y), (tip_x, tip_y), width=2, target=screen)

	def _get_slash_arc_surface(self, slash: Slash, alpha: int) -> tuple[SurfaceLike, float, int]:
		center_angle_deg = int(round(math.degrees(math.atan2(slash.dir_y, slash.dir_x)))) % 360
		arc_deg = int(round(slash.arc_deg))
		radius = float(slash.radius)
		pad = int(slash.line_width + 2)
		alpha_bucket = max(0, min(255, int(round(alpha / 16.0) * 16)))
		cache_key = (
			center_angle_deg,
			arc_deg,
			int(round(radius)),
			pad,
			slash.line_width,
			slash.color,
			alpha_bucket
		)

		cached = self._slash_arc_cache.get(cache_key)
		if cached is not None:
			return cached, radius, pad

		size = max(1, int(radius * 2 + pad * 2))
		start_angle = math.radians(center_angle_deg - arc_deg * 0.5)
		end_angle = math.radians(center_angle_deg + arc_deg * 0.5)

		arc_surface = create_surface(size, size, alpha=True)
		draw_arc(
			(*slash.color, alpha_bucket),
			(pad, pad, int(radius * 2), int(radius * 2)),
			start_angle,
			end_angle,
			width=slash.line_width,
			target=arc_surface
		)
		self._slash_arc_cache[cache_key] = arc_surface

		return arc_surface, radius, pad

	def _get_slash_circle_surface(self, slash: Slash, alpha: int) -> tuple[SurfaceLike, float, int]:
		radius = float(slash.radius)
		pad = int(slash.line_width + 2)
		alpha_bucket = max(0, min(255, int(round(alpha / 16.0) * 16)))
		cache_key = (
			int(round(radius)),
			slash.line_width,
			slash.color,
			alpha_bucket
		)

		cached = self._slash_circle_cache.get(cache_key)
		if cached is not None:
			return cached, radius, pad

		size = max(1, int(radius * 2 + pad * 2))
		circle_surface = create_surface(size, size, alpha=True)
		draw_circle(
			(*slash.color, alpha_bucket),
			(radius + pad, radius + pad),
			int(radius),
			width=slash.line_width,
			target=circle_surface
		)
		self._slash_circle_cache[cache_key] = circle_surface

		return circle_surface, radius, pad

	def _clamp_camera_to_world(self) -> None:
		max_x = max(0.0, float(self.world_width - self.viewport_width))
		max_y = max(0.0, float(self.world_height - self.viewport_height))

		self.camera.x = max(0.0, min(self.camera.x, max_x))
		self.camera.y = max(0.0, min(self.camera.y, max_y))

	def _camera_world_bounds(self, margin_x: float = 0.0, margin_y: float = 0.0) -> Rect:
		left = max(float(self.world.bounds.left), self.camera.x - margin_x)
		top = max(float(self.world.bounds.top), self.camera.y - margin_y)
		right = min(float(self.world.bounds.right), self.camera.x + self.viewport_width + margin_x)
		bottom = min(float(self.world.bounds.bottom), self.camera.y + self.viewport_height + margin_y)

		return Rect(left, top, max(1.0, right - left), max(1.0, bottom - top))

	def _resolve_player_static_collisions(self) -> None:
		if not self.world.static_colliders:
			self._clamp_player_to_world()
			return

		center_x, center_y = self.player.center
		radius = self.player.radius

		for _ in range(2):
			resolved = False

			for rect in self.world.static_colliders:
				push_x, push_y = self._circle_rect_push(center_x, center_y, radius, rect)
				if push_x == 0.0 and push_y == 0.0:
					continue

				self.player.x += push_x
				self.player.y += push_y

				center_x += push_x
				center_y += push_y
				resolved = True

			if not resolved:
				break

		self._clamp_player_to_world()

	def _clamp_player_to_world(self) -> None:
		min_x = float(self.world.bounds.left)
		max_x = float(self.world.bounds.right  - self.player.width)
		min_y = float(self.world.bounds.top)
		max_y = float(self.world.bounds.bottom - self.player.height)

		if max_x < min_x:
			self.player.x = self.world.bounds.centerx - self.player.width * 0.5
		else:
			self.player.x = max(min_x, min(self.player.x, max_x))

		if max_y < min_y:
			self.player.y = self.world.bounds.centery - self.player.height * 0.5
		else:
			self.player.y = max(min_y, min(self.player.y, max_y))

	def _circle_intersects_rect(self, center_x: float, center_y: float, radius: float, rect: Rect) -> bool:
		closest_x = max(rect.left, min(center_x, rect.right))
		closest_y = max(rect.top,  min(center_y, rect.bottom))

		dx = center_x - closest_x
		dy = center_y - closest_y

		return (dx * dx + dy * dy) < (radius * radius)

	def _circle_rect_push(self, center_x: float, center_y: float, radius: float, rect: Rect) -> tuple[float, float]:
		closest_x = max(rect.left, min(center_x, rect.right))
		closest_y = max(rect.top,  min(center_y, rect.bottom))

		dx = center_x - closest_x
		dy = center_y - closest_y

		dist_sq = dx * dx + dy * dy
		if dist_sq >= radius * radius:
			return (0.0, 0.0)

		if dist_sq <= 0.000001:
			left_clearance = center_x - rect.left
			right_clearance = rect.right  - center_x
			top_clearance = center_y - rect.top
			bottom_clearance = rect.bottom - center_y

			min_clearance = min(left_clearance, right_clearance, top_clearance, bottom_clearance)

			if min_clearance == left_clearance:
				return (rect.left - radius - 0.01 - center_x, 0.0)
			if min_clearance == right_clearance:
				return (rect.right + radius + 0.01 - center_x, 0.0)
			if min_clearance == top_clearance:
				return (0.0, rect.top - radius - 0.01 - center_y)

			return (0.0, rect.bottom + radius + 0.01 - center_y)

		dist = max(0.000001, math.sqrt(dist_sq))
		overlap = radius - dist + 0.01

		nx = dx / dist
		ny = dy / dist

		return (nx * overlap, ny * overlap)

	def _open_level_up(self) -> None:
		available = self._available_upgrade_attributes()

		if not available:
			self.pending_level_ups = 0
			self.level_up_active = False
			self.level_up_options = []
			return

		random.shuffle(available)

		self.level_up_options = available[:3]
		self.level_up_hover = None
		self.level_up_active = True
		self.card_hover_t = [0.0, 0.0, 0.0]

	def _available_upgrade_attributes(self) -> list[str]:
		return [
			name
			for name, level in self.player.attribute_levels.items()
			if level < self.player.max_attribute_level
		]

	def _get_card_rects(self) -> list[Rect]:
		card_w = int(self.viewport_width  * 0.17)
		card_h = int(self.viewport_height * 0.52)
		gap = int(self.viewport_width  * 0.03)

		n = len(self.level_up_options)

		total_w = n * card_w + (n - 1) * gap
		start_x = (self.viewport_width  - total_w) // 2
		center_y = self.viewport_height // 2

		rects: list[Rect] = []
		for i in range(n):
			x = start_x + i * (card_w + gap)
			y = center_y - card_h // 2
			rects.append(Rect(x, y, card_w, card_h))

		return rects

	def _get_scaled_card_rect(self, base: Rect, t: float) -> Rect:
		scale = 1.0 + 0.08 * t
		new_w = int(base.width  * scale)
		new_h = int(base.height * scale)
		new_x = base.centerx - new_w // 2
		new_y = base.centery - new_h // 2
		return Rect(new_x, new_y, new_w, new_h)

	def _update_level_up(self, input_manager: Input) -> None:
		mouse = input_manager.mouse
		mx, my = mouse.get_position()
		base_rects = self._get_card_rects()

		while len(self.card_hover_t) < len(self.level_up_options):
			self.card_hover_t.append(0.0)

		dt_approx = 1.0 / 60.0

		self.level_up_hover = None
		for index, base in enumerate(base_rects):
			hovering = base.left <= mx <= base.right and base.top <= my <= base.bottom

			if hovering:
				self.level_up_hover = index
				self.card_hover_t[index] = min(1.0, self.card_hover_t[index] + self.CARD_ANIM_SPEED * dt_approx)

				if mouse.button_down(mouse.LEFT):
					attribute = self.level_up_options[index]
					self.player.upgrade_attribute(attribute)
					self.pending_level_ups = max(0, self.pending_level_ups - 1)
					self.card_hover_t = [0.0, 0.0, 0.0]

					if self.pending_level_ups > 0:
						self._open_level_up()
					else:
						self.level_up_active = False
						self.level_up_options = []
						self.level_up_hover = None
					return
			else:
				self.card_hover_t[index] = max(0.0, self.card_hover_t[index] - self.CARD_ANIM_SPEED * dt_approx)

	def _draw_level_up_overlay(self) -> None:
		screen = get_screen()
		base_rects = self._get_card_rects()

		label_map = {
			"max_health":   "Max Health",
			"health_regen": "Recovery",
			"defense":      "Armor",
			"strength":     "Strength",
			"move_speed":   "Move Speed",
			"attack_speed": "Attack Speed"
		}

		icon_map = {
			"max_health":   self.level_up_icons.get("max_health", self.level_up_icon),
			"health_regen": self.level_up_icons.get("health_regen", self.level_up_icon),
			"defense":      self.level_up_icons.get("defense", self.level_up_icon),
			"strength":     self.level_up_icons.get("strength", self.level_up_icon),
			"move_speed":   self.level_up_icons.get("move_speed", self.level_up_icon),
			"attack_speed": self.level_up_icons.get("attack_speed", self.level_up_icon)
		}

		color_map = {
			"max_health":   ((180, 60,  60),  (255, 100, 100)),
			"health_regen": ((60,  140, 80),  (100, 220, 130)),
			"defense":      ((60,  80,  160), (100, 140, 255)),
			"strength":     ((160, 80,  40),  (255, 150,  80)),
			"move_speed":   ((80,  160, 160), (120, 230, 230)),
			"attack_speed": ((130, 60,  160), (200, 100, 255))
		}

		overlay = create_surface(self.viewport_width, self.viewport_height, alpha=True)
		overlay.fill((0, 0, 0, 170))
		blit_surface(overlay, (0, 0), target=screen)

		title_surf = self.ui_font_title.render("Choose an Upgrade", False, (255, 230, 140))
		tx = (self.viewport_width - title_surf.get_width()) // 2
		ty = int(self.viewport_height * 0.10)
		screen.blit(title_surf, (tx, ty))

		for index, base in enumerate(base_rects):
			t = self.card_hover_t[index] if index < len(self.card_hover_t) else 0.0
			rect = self._get_scaled_card_rect(base, t)
			attribute = self.level_up_options[index]

			dark_col, light_col = color_map.get(attribute, ((80, 80, 100), (150, 150, 200)))

			def lerp_color(c1, c2, t):
				return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

			bg_color = lerp_color((30, 28, 45), dark_col, t * 0.55)
			border_color = lerp_color((100, 90, 70), light_col, t)
			border_w = 2 if t < 0.5 else 3

			shadow_surf = create_surface(rect.width + 8, rect.height + 8, alpha=True)
			shadow_alpha = int(80 + 60 * t)
			shadow_surf.fill((0, 0, 0, shadow_alpha))

			blit_surface(shadow_surf, (rect.x - 4, rect.y + 6), target=screen)
			draw_rect(bg_color, rect, border_radius=12, target=screen)

			glow_h = rect.height // 3
			glow_alpha = int(30 + 50 * t)
			glow_surf = create_surface(rect.width - 4, glow_h, alpha=True)
			glow_surf.fill((*light_col, glow_alpha))

			blit_surface(glow_surf, (rect.x + 2, rect.y + 2), target=screen)
			draw_rect(border_color, rect, width=border_w, border_radius=12, target=screen)

			icon = icon_map.get(attribute)
			icon_size = int(self.level_up_icon_size * (1.0 + 0.15 * t))
			icon_y_base = rect.y + int(rect.height * 0.18)

			if icon is not None:
				scaled_icon = scale_surface(icon, icon_size, icon_size, smooth=False)
				icon_x = rect.centerx - icon_size // 2
				screen.blit(scaled_icon, (icon_x, icon_y_base))

			label = label_map.get(attribute, attribute)
			label_surf = self.ui_font_medium.render(label, False, (240, 240, 240))

			lx = rect.centerx - label_surf.get_width() // 2
			ly = icon_y_base + icon_size + 14

			screen.blit(label_surf, (lx, ly))

			level = int(self.player.attribute_levels.get(attribute, 0))
			max_level = int(self.player.max_attribute_level)

			dot_r = 5
			dot_gap = 5
			dots_total_w = max_level * (dot_r * 2) + (max_level - 1) * dot_gap
			dot_start_x = rect.centerx - dots_total_w // 2
			dot_y = ly + label_surf.get_height() + 16

			for d in range(max_level):
				dx = dot_start_x + d * (dot_r * 2 + dot_gap) + dot_r

				filled = d < level

				dot_color = light_col if filled else (60, 58, 75)
				dot_border = light_col if filled else (80, 78, 95)

				draw_circle(dot_color, (dx, dot_y), dot_r, target=screen)

				if not filled:
					draw_circle(dot_border, (dx, dot_y), dot_r, width=1, target=screen)

			if t > 0.3:
				hint_font = self.services.fonts.get(18)
				hint_surf = hint_font.render("Click to choose", False, (220, 220, 180))

				hint_s2 = create_surface(hint_surf.get_width(), hint_surf.get_height(), alpha=True)
				hint_s2.fill((0, 0, 0, 0))
				hint_s2.blit(hint_surf, (0, 0))

				hx = rect.centerx - hint_surf.get_width() // 2
				hy = rect.bottom   - hint_surf.get_height() - 16

				blit_surface(hint_s2, (hx, hy), target=screen)
