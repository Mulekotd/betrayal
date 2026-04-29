from __future__ import annotations

import math
import random
from typing import Any

from external.pplay.gameimage import GameImage

from src.engine.camera import Camera
from src.engine.world import World
from src.entities.enemy import EnemyManager
from src.entities.player import Player
from src.system.input import Input
from src.system.hud import HUD
from src.utils.services import GameServices
from src.utils.window import get_screen
from src.utils.window import load_image, create_surface, draw_rect, blit_surface, set_mouse_visible, scale_surface
from src.utils.rect import Rect


class GameScene:
	def __init__(self, services: GameServices, world_width: int, world_height: int) -> None:
		self.services = services
		assets_dir = self.services.images_dir

		self.viewport_width = world_width
		self.viewport_height = world_height

		self.world = World(
			images_dir=assets_dir,
			viewport_width=self.viewport_width,
			viewport_height=self.viewport_height,
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
			spawn_y=spawn_y,
		)
		
		self.player.init_progression()
        
		self.enemy_manager = EnemyManager(
			assets_dir=assets_dir,
			world_width=self.world_width,
			world_height=self.world_height,
		)
		self.enemy_manager.set_world_bounds(self.world.bounds)
		self.world.rebuild(player_center=self.player.center, player_radius=self.player.radius)
		self.enemy_manager.set_static_colliders(self.world.static_colliders)

		self.total_kills = 0

		self.cursor = GameImage(str(assets_dir / "cursor.png"))
		self.cursor_hotspot_x = self.cursor.width * 0.5
		self.cursor_hotspot_y = self.cursor.height * 0.5

		self.pending_level_ups = 0
		self.level_up_active = False
		self.level_up_options: list[str] = []
		self.level_up_hover: int | None = None

		self.ui_font_medium = self.services.fonts.get(26)
		self.ui_font_title = self.services.fonts.get(38)

		self.hud = HUD(
			viewport_width=self.viewport_width,
			viewport_height=self.viewport_height,
			fonts=self.services.fonts,
			padding=64,
		)

		self.player_dead = False
		self.game_over_title_font = self.services.fonts.get(68)
		self.game_over_hint_font = self.services.fonts.get(24)

	def handle_events(self, input_manager: Input | None) -> None:
		_ = input_manager

	def update(self, dt: float, input_manager: Input | None) -> None:
		if input_manager is None:
			return

		if self.player_dead:
			self._update_game_over(input_manager)
			return

		if self.level_up_active:
			self._update_level_up(input_manager)
			return

		self.player.update(
			input_manager,
			dt,
			self.world_width,
			self.world_height,
			world_bounds=self.world.bounds,
		)
		self._resolve_player_static_collisions()
		before_update = len(self.enemy_manager.get_enemies())
		xp_gained = self.enemy_manager.update(self.player, dt)
		after_update = len(self.enemy_manager.get_enemies())

		self.player.resolve_enemy_collisions(self.enemy_manager.get_enemies())

		if self.player.is_dead():
			self.player_dead = True
			self.level_up_active = False
			self.level_up_options = []
			self.level_up_hover = None
			self.pending_level_ups = 0

			return

		if xp_gained:
			levels_gained = self.player.add_xp(xp_gained)

			if levels_gained:
				self.pending_level_ups += levels_gained
				self._open_level_up()

		player_center_x, player_center_y = self.player.center
		self.camera.follow(player_center_x, player_center_y)
		self._clamp_camera_to_world()

		if after_update < before_update:
			self.total_kills += before_update - after_update

	def render(self, window: Any) -> None:
		self._draw_tiled_ground()
		self.world.draw(camera_x=self.camera.x, camera_y=self.camera.y)

		set_mouse_visible(False)
		window.get_mouse().hide()

		self.enemy_manager.draw(camera_x=self.camera.x, camera_y=self.camera.y)
		self.player.draw(camera_x=self.camera.x, camera_y=self.camera.y)
		self.hud.draw(self.player, self.total_kills)

		if self.level_up_active:
			self._draw_level_up_overlay()

		if self.player_dead:
			self._draw_game_over_overlay()

		mouse_x, mouse_y = window.get_mouse().get_position()

		self.cursor.set_position(
			mouse_x - self.cursor_hotspot_x,
			mouse_y - self.cursor_hotspot_y,
		)

		self.cursor.draw()

	def _draw_tiled_ground(self) -> None:
		screen = get_screen()

		start_x = (-int(self.camera.x) % self.ground_tile_width) - self.ground_tile_width
		start_y = (-int(self.camera.y) % self.ground_tile_height) - self.ground_tile_height

		for y in range(start_y, self.viewport_height + self.ground_tile_height, self.ground_tile_height):
			for x in range(start_x, self.viewport_width + self.ground_tile_width, self.ground_tile_width):
				screen.blit(self.ground_tile, (x, y))

	def _update_game_over(self, input_manager: Input) -> None:
		keyboard = input_manager.keyboard

		if (keyboard.key_pressed("ENTER")):
			self._restart_run()

	def _restart_run(self) -> None:
		assets_dir = self.services.images_dir

		self.player = Player(
			assets_dir=assets_dir,
			spawn_x=float(self.world.bounds.centerx),
			spawn_y=float(self.world.bounds.centery),
		)
		self.player.init_progression()

		self.enemy_manager = EnemyManager(
			assets_dir=assets_dir,
			world_width=self.world_width,
			world_height=self.world_height,
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

		self.camera.follow(*self.player.center)
		self._clamp_camera_to_world()

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

	def _clamp_camera_to_world(self) -> None:
		max_x = max(0.0, float(self.world_width - self.viewport_width))
		max_y = max(0.0, float(self.world_height - self.viewport_height))

		self.camera.x = max(0.0, min(self.camera.x, max_x))
		self.camera.y = max(0.0, min(self.camera.y, max_y))

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

				self.player.sprite.x += push_x
				self.player.sprite.y += push_y

				center_x += push_x
				center_y += push_y

				resolved = True

			if not resolved:
				break

		self._clamp_player_to_world()

	def _clamp_player_to_world(self) -> None:
		min_x = float(self.world.bounds.left)
		max_x = float(self.world.bounds.right - self.player.sprite.width)
		min_y = float(self.world.bounds.top)
		max_y = float(self.world.bounds.bottom - self.player.sprite.height)

		if max_x < min_x:
			self.player.sprite.x = self.world.bounds.centerx - self.player.sprite.width * 0.5
		else:
			self.player.sprite.x = max(min_x, min(self.player.sprite.x, max_x))

		if max_y < min_y:
			self.player.sprite.y = self.world.bounds.centery - self.player.sprite.height * 0.5
		else:
			self.player.sprite.y = max(min_y, min(self.player.sprite.y, max_y))

	def _circle_intersects_rect(self, center_x: float, center_y: float, radius: float, rect: Rect) -> bool:
		closest_x = max(rect.left, min(center_x, rect.right))
		closest_y = max(rect.top, min(center_y, rect.bottom))

		dx = center_x - closest_x
		dy = center_y - closest_y

		return (dx * dx + dy * dy) < (radius * radius)

	def _circle_rect_push(self, center_x: float, center_y: float, radius: float, rect: Rect) -> tuple[float, float]:
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

	def _open_level_up(self) -> None:
		available = [
			name
			for name in self.player.attribute_levels
			if self.player.attribute_levels[name] < self.player.max_attribute_level
		]

		if not available:
			self.pending_level_ups = 0
			self.level_up_active = False
			self.level_up_options = []
			return

		random.shuffle(available)

		self.level_up_options = available[:3]
		self.level_up_hover = None
		self.level_up_active = True

	def _get_level_up_layout(self) -> tuple[Rect, list[Rect]]:
		panel_width = int(self.viewport_width * 0.52)
		panel_height = int(self.viewport_height * 0.55)
		panel_x = (self.viewport_width - panel_width) // 2
		panel_y = (self.viewport_height - panel_height) // 2
		panel_rect = Rect(panel_x, panel_y, panel_width, panel_height)

		option_height = 78
		option_gap = 14
		option_x = panel_x + 28
		option_width = panel_width - 56
		option_start_y = panel_y + 86

		rects: list[Rect] = []
		for index in range(len(self.level_up_options)):
			y = option_start_y + index * (option_height + option_gap)
			rects.append(Rect(option_x, y, option_width, option_height))

		return panel_rect, rects

	def _update_level_up(self, input_manager: Input) -> None:
		mouse = input_manager.mouse
		mx, my = mouse.get_position()
		_, option_rects = self._get_level_up_layout()
		self.level_up_hover = None

		for index, rect in enumerate(option_rects):
			if rect.left <= mx <= rect.right and rect.top <= my <= rect.bottom:
				self.level_up_hover = index

				if mouse.button_down(mouse.LEFT):
					attribute = self.level_up_options[index]
					self.player.upgrade_attribute(attribute)
					self.pending_level_ups = max(0, self.pending_level_ups - 1)

					if self.pending_level_ups > 0:
						self._open_level_up()
					else:
						self.level_up_active = False
						self.level_up_options = []
						self.level_up_hover = None
					break

	def _draw_level_up_overlay(self) -> None:
		screen = get_screen()

		overlay = create_surface(self.viewport_width, self.viewport_height, alpha=True)
		overlay.fill((0, 0, 0, 140))

		blit_surface(overlay, (0, 0), target=screen)

		panel_rect, option_rects = self._get_level_up_layout()
		draw_rect((78, 82, 120), panel_rect, border_radius=10, target=screen)
		draw_rect((200, 170, 90), panel_rect, width=2, border_radius=10, target=screen)

		title_surface = self.ui_font_title.render("Level Up!", True, (245, 245, 245))
		title_x = panel_rect.centerx - (title_surface.get_width() // 2)
		title_y = panel_rect.y + 24

		screen.blit(title_surface, (title_x, title_y))

		label_map = {
			"max_health": "Max Health",
			"health_regen": "Recovery",
			"defense": "Armor",
			"strength": "Strength",
			"move_speed": "Move Speed",
			"attack_speed": "Attack Speed",
		}

		for index, rect in enumerate(option_rects):
			is_hover = index == self.level_up_hover
			fill = (120, 120, 140) if is_hover else (96, 96, 112)
			border = (220, 190, 110) if is_hover else (180, 150, 90)

			draw_rect(fill, rect, border_radius=8, target=screen)
			draw_rect(border, rect, width=2, border_radius=8, target=screen)

			attribute = self.level_up_options[index]
			label = label_map.get(attribute, attribute)

			text_surface = self.ui_font_medium.render(label, True, (240, 240, 240))
			text_x = rect.x + 18
			text_y = rect.y + (rect.height - text_surface.get_height()) // 2

			screen.blit(text_surface, (text_x, text_y))
