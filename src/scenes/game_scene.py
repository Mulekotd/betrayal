from __future__ import annotations

from pathlib import Path
import random
from typing import Any

import pygame
from external.pplay.gameimage import GameImage

from src.entities.enemy import EnemyManager
from src.entities.player import Player
from src.system.camera import Camera
from src.system.input import Input
from src.system.hud import HUD
from src.system.services import GameServices
from src.utils.window import get_screen


class GameScene:
	def __init__(self, services: GameServices, world_width: int, world_height: int) -> None:
		self.services = services
		assets_dir = self.services.images_dir

		self.viewport_width = world_width
		self.viewport_height = world_height

		self.world_width = world_width
		self.world_height = world_height
		self.camera = Camera(viewport_width=self.viewport_width, viewport_height=self.viewport_height)
		
		self.player = Player(
			assets_dir=assets_dir,
			spawn_x=world_width * 0.5,
			spawn_y=world_height * 0.5,
		)
		
		self.player.init_progression()
        
		self.enemy_manager = EnemyManager(
			assets_dir=assets_dir,
			world_width=world_width,
			world_height=world_height,
		)

		self.total_kills = 0

		self.background_tile = self._load_background_tile(assets_dir)

		self.cursor = GameImage(str(assets_dir / "cursor_lg.png"))
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
			padding=32,
		)

	def handle_events(self, input_manager: Input | None) -> None:
		_ = input_manager

	def update(self, dt: float, input_manager: Input | None) -> None:
		if input_manager is None:
			return

		if self.level_up_active:
			self._update_level_up(input_manager)
			return

		self.player.update(input_manager, dt, self.world_width, self.world_height)
		before_update = len(self.enemy_manager.get_enemies())
		xp_gained = self.enemy_manager.update(self.player, dt)
		after_update = len(self.enemy_manager.get_enemies())

		self.player.resolve_enemy_collisions(self.enemy_manager.get_enemies())

		if xp_gained:
			levels_gained = self.player.add_xp(xp_gained)

			if levels_gained:
				self.pending_level_ups += levels_gained
				self._open_level_up()

		player_center_x, player_center_y = self.player.center
		self.camera.follow(player_center_x, player_center_y)

		if after_update < before_update:
			self.total_kills += before_update - after_update

	def render(self, window: Any) -> None:
		self._draw_repeating_background()

		pygame.mouse.set_visible(False)
		window.get_mouse().hide()

		self.enemy_manager.draw(camera_x=self.camera.x, camera_y=self.camera.y)
		self.player.draw(camera_x=self.camera.x, camera_y=self.camera.y)
		self.hud.draw(self.player, self.total_kills)

		if self.level_up_active:
			self._draw_level_up_overlay()

		mouse_x, mouse_y = window.get_mouse().get_position()

		self.cursor.set_position(
			mouse_x - self.cursor_hotspot_x,
			mouse_y - self.cursor_hotspot_y,
		)

		self.cursor.draw()

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

	def _get_level_up_layout(self) -> tuple[pygame.Rect, list[pygame.Rect]]:
		panel_width = int(self.viewport_width * 0.52)
		panel_height = int(self.viewport_height * 0.55)
		panel_x = (self.viewport_width - panel_width) // 2
		panel_y = (self.viewport_height - panel_height) // 2
		panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)

		option_height = 78
		option_gap = 14
		option_x = panel_x + 28
		option_width = panel_width - 56
		option_start_y = panel_y + 86

		rects = []
		for index in range(len(self.level_up_options)):
			y = option_start_y + index * (option_height + option_gap)
			rects.append(pygame.Rect(option_x, y, option_width, option_height))

		return panel_rect, rects

	def _update_level_up(self, input_manager: Input) -> None:
		mouse = input_manager.mouse
		mx, my = mouse.get_position()
		_, option_rects = self._get_level_up_layout()
		self.level_up_hover = None

		for index, rect in enumerate(option_rects):
			if rect.collidepoint(mx, my):
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

		overlay = pygame.Surface((self.viewport_width, self.viewport_height), pygame.SRCALPHA)
		overlay.fill((0, 0, 0, 140))
		screen.blit(overlay, (0, 0))

		panel_rect, option_rects = self._get_level_up_layout()
		pygame.draw.rect(screen, (78, 82, 120), panel_rect, border_radius=10)
		pygame.draw.rect(screen, (200, 170, 90), panel_rect, 2, border_radius=10)

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

			pygame.draw.rect(screen, fill, rect, border_radius=8)
			pygame.draw.rect(screen, border, rect, 2, border_radius=8)

			attribute = self.level_up_options[index]
			label = label_map.get(attribute, attribute)
			text_surface = self.ui_font_medium.render(label, True, (240, 240, 240))
			text_x = rect.x + 18
			text_y = rect.y + (rect.height - text_surface.get_height()) // 2
			screen.blit(text_surface, (text_x, text_y))

	def _draw_repeating_background(self) -> None:
		if self.background_tile is None:
			self._draw_procedural_background()
			return

		screen = get_screen()

		tile_width = int(self.background_tile.width)
		tile_height = int(self.background_tile.height)

		if tile_width <= 0 or tile_height <= 0:
			return

		start_x = -int(self.camera.x % tile_width) - tile_width
		start_y = -int(self.camera.y % tile_height) - tile_height

		end_x = self.viewport_width + tile_width
		end_y = self.viewport_height + tile_height
		tile_surface = self.background_tile.image

		for draw_x in range(start_x, end_x, tile_width):
			for draw_y in range(start_y, end_y, tile_height):
				screen.blit(tile_surface, (draw_x, draw_y))

	def _draw_procedural_background(self) -> None:
		tile_size = 96
		start_x = -int(self.camera.x % tile_size) - tile_size
		start_y = -int(self.camera.y % tile_size) - tile_size
		end_x = self.viewport_width + tile_size
		end_y = self.viewport_height + tile_size

		screen = get_screen()

		for draw_x in range(start_x, end_x, tile_size):
			for draw_y in range(start_y, end_y, tile_size):
				cell_x = int((draw_x + self.camera.x) // tile_size)
				cell_y = int((draw_y + self.camera.y) // tile_size)
				is_even = (cell_x + cell_y) % 2 == 0
				color = (24, 28, 34) if is_even else (19, 22, 27)

				pygame.draw.rect(screen, color, (draw_x, draw_y, tile_size, tile_size))

	def _load_background_tile(self, assets_dir: Path) -> GameImage | None:
		for filename in ("map_tile.png", "tile_0001.png", "logo.png"):
			candidate = assets_dir / filename

			if candidate.exists():
				return GameImage(str(candidate))

		return None
