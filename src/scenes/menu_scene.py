from dataclasses import dataclass
from typing import Callable

from external.pplay.gameimage import GameImage

from src.game import Game
from src.scenes.game_scene import GameScene
from src.utils.services import GameServices
from src.utils.window import get_screen, get_window, set_mouse_visible
from src.utils.window import (
	create_surface,
	scale_surface,
	draw_line,
	draw_circle,
	blit_surface
)


@dataclass
class MenuButton:
	label: str
	x: int
	y: int
	width: int
	height: int
	action: Callable[[], None]

	def contains(self, mx: float, my: float) -> bool:
		return self.x <= mx <= self.x + self.width and self.y <= my <= self.y + self.height


class MenuScene:
	def __init__(self, game: Game, services: GameServices, world_width: int, world_height: int) -> None:
		self.game = game
		self.services = services

		self.world_width = world_width
		self.world_height = world_height

		self._mx_norm = 0.0
		self._my_norm = 0.0

		logo_path = self.services.images_dir / "logo.png"
		target_logo_width = int(self.world_width * 0.38)

		self.logo = GameImage(str(logo_path))
		self.logo_scale = target_logo_width / max(1, int(self.logo.width))
		self.logo.scale_x = self.logo_scale
		self.logo.scale_y = self.logo_scale
		self.logo_surface, self.logo_glow_surface = self._build_logo_layers()

		self.menu_font = self.services.fonts.title(74)
		self.menu_color = (120, 210, 235)
		self.menu_hover_color = (170, 235, 255)
		self.menu_shadow_color = (20, 60, 76)
		self.menu_glow_color = (80, 180, 205)

		self.background_base_layer = self._build_background_surface()
		self.background_blur_layer = self._build_blurred_layer(self.background_base_layer, downscale=0.18, passes=2)
		self.background_depth_layer = self._build_depth_layer()
		self.ui_layer_surface = create_surface(self.world_width, self.world_height, alpha=True)

		padding = 64
		gap = 8

		start_x = padding
		start_y = int(self.world_height * 0.34)

		labels = [
			("PLAY", self._start_game),
			("OPTIONS", self._open_settings),
			("QUIT", self._quit_game)
		]

		self.buttons = []
		cursor_y = start_y

		for label, action in labels:
			surface = self.menu_font.render(label, False, (255, 255, 255))

			self.buttons.append(
				MenuButton(
					label=label,
					x=start_x,
					y=cursor_y,
					width=surface.get_width(),
					height=surface.get_height(),
					action=action
				)
			)

			cursor_y += surface.get_height() + gap

		self._hover_index: int | None = None
		set_mouse_visible(True)

	def handle_events(self, input_manager) -> None:
		_ = input_manager

	def update(self, dt: float, input_manager) -> None:
		_ = dt
		mouse = input_manager.mouse if input_manager is not None else get_window().mouse
		mx, my = mouse.get_position()

		self._mx_norm = ((mx / max(1, self.world_width)) - 0.5) * 2.0
		self._my_norm = ((my / max(1, self.world_height)) - 0.5) * 2.0
		button_offset_x, button_offset_y = self._button_layer_offset()

		self._hover_index = None
		for index, button in enumerate(self.buttons):
			left = button.x + button_offset_x
			top = button.y + button_offset_y
			right = left + button.width
			bottom = top + button.height

			if left <= mx <= right and top <= my <= bottom:
				self._hover_index = index
				if mouse.button_down(mouse.LEFT):
					button.action()
				break

	def render(self) -> None:
		screen = get_screen()
		screen.blit(self.background_base_layer, (0, 0))
		screen.blit(self.background_blur_layer, (0, 0))

		logo_w = max(1, int(self.logo.width * self.logo_scale))
		logo_h = max(1, int(self.logo.height * self.logo_scale))
		logo_x = int(self.world_width * 0.50)
		logo_y = int(self.world_height * 0.35)

		logo_x = min(max(32, logo_x), self.world_width - logo_w - 32)
		logo_y = min(max(32, logo_y), self.world_height - logo_h - 32)
		logo_x += int(self._mx_norm * 10.0)
		logo_y += int(self._my_norm * 8.0)

		if logo_x >= 0 and logo_y >= 0 and logo_x + logo_w <= self.world_width and logo_y + logo_h <= self.world_height:
			region = self.background_base_layer.subsurface((logo_x, logo_y, logo_w, logo_h)).copy()
			blit_surface(region, (logo_x, logo_y), target=screen)

		screen.blit(self.background_depth_layer, (0, 0))

		self.ui_layer_surface.fill((0, 0, 0, 0))
		self._draw_logo(self.ui_layer_surface)
		self._draw_buttons(self.ui_layer_surface)

		blit_surface(self.ui_layer_surface, (0, 0), target=screen)

	def _build_background_surface(self):
		surface = create_surface(self.world_width, self.world_height)

		top_color = (2, 8, 14)
		bottom_color = (52, 126, 140)

		for y in range(self.world_height):
			t = y / max(1, self.world_height - 1)

			color = (
				int(top_color[0] + (bottom_color[0] - top_color[0]) * t),
				int(top_color[1] + (bottom_color[1] - top_color[1]) * t),
				int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
			)

			draw_line(color, (0, y), (self.world_width, y), target=surface)

		haze = create_surface(self.world_width, self.world_height, alpha=True)
		glow_center = (int(self.world_width * 0.34), int(self.world_height * 0.80))
		max_radius = int(max(self.world_width, self.world_height) * 0.58)

		for radius in range(max_radius, 0, -8):
			t = radius / max(1, max_radius)
			alpha = int((1.0 - t) * (1.0 - t) * 100)

			if alpha <= 0:
				continue

			draw_circle((90, 205, 225, alpha), glow_center, radius, target=haze)

		blit_surface(haze, (0, 0), target=surface)

		top_shadow = create_surface(self.world_width, self.world_height, alpha=True)
		shadow_height = int(self.world_height * 0.48)

		for y in range(shadow_height):
			t = y / max(1, shadow_height - 1)
			alpha = int((1.0 - t) * 105)

			draw_line((0, 0, 0, alpha), (0, y), (self.world_width, y), target=top_shadow)

		blit_surface(top_shadow, (0, 0), target=surface)

		return surface

	def _build_blurred_layer(self, source, downscale: float = 0.2, passes: int = 2):
		width, height = source.get_size()
		small_size = (max(1, int(width * downscale)), max(1, int(height * downscale)))

		blurred = source.copy()
		for _ in range(max(1, passes)):
			blurred = scale_surface(blurred, small_size[0], small_size[1], smooth=True)
			blurred = scale_surface(blurred, width, height, smooth=True)

		blurred = blurred.convert_alpha()
		blurred.set_alpha(132)

		return blurred

	def _build_depth_layer(self):
		overlay = create_surface(self.world_width, self.world_height, alpha=True)
		horizon_height = int(self.world_height * 0.50)

		for y in range(horizon_height):
			t = y / max(1, horizon_height - 1)
			alpha = int((1.0 - t) * 112)

			draw_line((0, 0, 0, alpha), (0, y), (self.world_width, y), target=overlay)

		return overlay

	def _build_logo_layers(self):
		logo_w = max(1, int(self.logo.width * self.logo_scale))
		logo_h = max(1, int(self.logo.height * self.logo_scale))

		raw = scale_surface(self.logo.image, logo_w, logo_h, smooth=True).convert_alpha()

		glow = create_surface(logo_w, logo_h, alpha=True)
		glow_center = (logo_w // 2, logo_h // 2)

		max_radius = max(logo_w, logo_h)
		step = max(1, int(max_radius / 12))
		for r in range(max_radius, 0, -step):
			t = r / max(1, max_radius)
			alpha = int((1.0 - t) * 90)

			if alpha <= 0:
				continue

			draw_circle((90, 210, 230, alpha), glow_center, r, target=glow)

		return raw, glow

	def _draw_logo(self, target) -> None:
		logo_w = self.logo_surface.get_width()
		logo_h = self.logo_surface.get_height()

		logo_x = int(self.world_width * 0.50)
		logo_y = int(self.world_height * 0.35)

		logo_x = min(max(32, logo_x), self.world_width - logo_w - 32)
		logo_y = min(max(32, logo_y), self.world_height - logo_h - 32)

		logo_x += int(self._mx_norm * 10.0)
		logo_y += int(self._my_norm * 8.0)

		blit_surface(self.logo_surface, (logo_x, logo_y), target=target)

	def _draw_buttons(self, target) -> None:
		offset_x, offset_y = self._button_layer_offset()

		for index, button in enumerate(self.buttons):
			is_hover = index == self._hover_index
			draw_x = button.x + offset_x
			draw_y = button.y + offset_y

			color = self.menu_hover_color if is_hover else self.menu_color
			glow = self.menu_shadow_color
			glow_color = self.menu_glow_color

			glow_surface = self.menu_font.render(button.label, False, glow_color)
			for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
				blit_surface(glow_surface, (draw_x + ox, draw_y + oy), target=target)

			shadow_surface = self.menu_font.render(button.label, False, glow)
			blit_surface(shadow_surface, (draw_x + 2, draw_y + 2), target=target)

			text_surface = self.menu_font.render(button.label, False, color)
			blit_surface(text_surface, (draw_x, draw_y), target=target)

	def _button_layer_offset(self) -> tuple[int, int]:
		return (int(self._mx_norm * 6.0), int(self._my_norm * 4.0))

	def _start_game(self) -> None:
		set_mouse_visible(False)
		self.game.set_scene(
			GameScene(
				services=self.services,
				world_width=self.world_width,
				world_height=self.world_height,
				game=self.game,
			)
		)

	def _open_settings(self) -> None:
		from src.scenes.settings_scene import SettingsScene

		self.game.set_scene(
			SettingsScene(
				game=self.game,
				services=self.services,
				world_width=self.world_width,
				world_height=self.world_height,
				on_back=self._return_to_menu,
			)
		)

	def _return_to_menu(self) -> None:
		self.game.set_scene(
			MenuScene(
				game=self.game,
				services=self.services,
				world_width=self.world_width,
				world_height=self.world_height,
			)
		)

	def _quit_game(self) -> None:
		get_window().close()
