from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from external.pplay.gameimage import GameImage

from src.game import Game
from src.scenes.game_scene import GameScene
from src.system.input import Input
from src.utils.services import GameServices
from src.utils.types import SurfaceLike
from src.utils.window import blit_surface, create_surface, draw_circle, draw_line, get_screen, get_window, scale_surface, set_mouse_visible


@dataclass(slots=True)
class MenuButton:
	label: str
	x: int
	y: int
	width: int
	height: int
	action: Callable[[], None]
	text_surface: SurfaceLike
	hover_surface: SurfaceLike = field(init=False)
	shadow_surface: SurfaceLike = field(init=False)

	def contains(self, mouse_x: float, mouse_y: float, offset_x: int, offset_y: int) -> bool:
		left = self.x + offset_x
		top = self.y + offset_y
		return left <= mouse_x <= left + self.width and top <= mouse_y <= top + self.height


class MenuScene:
	def __init__(self, game: Game, services: GameServices, world_width: int, world_height: int) -> None:
		self.game = game
		self.services = services
		self.world_width = world_width
		self.world_height = world_height

		self._mouse_norm_x = 0.0
		self._mouse_norm_y = 0.0

		logo_path = self.services.images_dir / "logo.png"
		target_logo_width = int(self.world_width * 0.38)

		self.logo = GameImage(str(logo_path))
		self.logo_scale = target_logo_width / max(1, int(self.logo.width))
		self.logo.scale_x = self.logo_scale
		self.logo.scale_y = self.logo_scale
		self.logo_surface = self._build_logo_surface()

		self.menu_font = self.services.fonts.title(74)
		self.menu_color = (120, 210, 235)
		self.menu_hover_color = (170, 235, 255)
		self.menu_shadow_color = (20, 60, 76)
		self.menu_glow_color = (80, 180, 205)

		self.background_base_layer = self._build_background_surface()
		self.background_blur_layer = self._build_blurred_layer(self.background_base_layer, downscale=0.18, passes=2)
		self.background_depth_layer = self._build_depth_layer()
		self.ui_layer_surface = create_surface(self.world_width, self.world_height, alpha=True)

		self.buttons = self._build_buttons()
		self._hover_index: int | None = None
		set_mouse_visible(True)

	def handle_events(self, input_manager: Input | None) -> None:
		_ = input_manager

	def update(self, dt: float, input_manager: Input | None) -> None:
		_ = dt
		mouse = input_manager.mouse if input_manager is not None else get_window().mouse
		mouse_x, mouse_y = mouse.get_position()

		self._mouse_norm_x = ((mouse_x / max(1, self.world_width)) - 0.5) * 2.0
		self._mouse_norm_y = ((mouse_y / max(1, self.world_height)) - 0.5) * 2.0
		offset_x, offset_y = self._button_layer_offset()

		self._hover_index = None
		for index, button in enumerate(self.buttons):
			if not button.contains(mouse_x, mouse_y, offset_x, offset_y):
				continue

			self._hover_index = index
			if mouse.button_down(mouse.LEFT):
				button.action()

			break

	def render(self) -> None:
		screen = get_screen()
		screen.blit(self.background_base_layer, (0, 0))
		screen.blit(self.background_blur_layer, (0, 0))
		screen.blit(self.background_depth_layer, (0, 0))

		self.ui_layer_surface.fill((0, 0, 0, 0))
		self._draw_logo(self.ui_layer_surface)
		self._draw_buttons(self.ui_layer_surface)
		blit_surface(self.ui_layer_surface, (0, 0), target=screen)

	def _build_buttons(self) -> list[MenuButton]:
		padding = 64
		gap = 8
		start_x = padding
		start_y = int(self.world_height * 0.34)
		labels = [
			("PLAY", self._start_game),
			("OPTIONS", self._open_settings),
			("QUIT", self._quit_game)
		]

		buttons: list[MenuButton] = []
		cursor_y = start_y
		for label, action in labels:
			text_surface = self.menu_font.render(label, False, self.menu_color)
			
			button = MenuButton(
				label=label,
				x=start_x,
				y=cursor_y,
				width=text_surface.get_width(),
				height=text_surface.get_height(),
				action=action,
				text_surface=text_surface
			)
			button.hover_surface = self.menu_font.render(label, False, self.menu_hover_color)
			button.shadow_surface = self.menu_font.render(label, False, self.menu_shadow_color)
			buttons.append(button)
			
			cursor_y += text_surface.get_height() + gap

		return buttons

	def _build_background_surface(self) -> SurfaceLike:
		surface = create_surface(self.world_width, self.world_height)
		top_color = (2, 8, 14)
		bottom_color = (52, 126, 140)

		for y in range(self.world_height):
			progress = y / max(1, self.world_height - 1)
			color = (
				int(top_color[0] + (bottom_color[0] - top_color[0]) * progress),
				int(top_color[1] + (bottom_color[1] - top_color[1]) * progress),
				int(top_color[2] + (bottom_color[2] - top_color[2]) * progress),
			)
			draw_line(color, (0, y), (self.world_width, y), target=surface)

		haze = create_surface(self.world_width, self.world_height, alpha=True)
		glow_center = (int(self.world_width * 0.34), int(self.world_height * 0.80))
		max_radius = int(max(self.world_width, self.world_height) * 0.58)

		for radius in range(max_radius, 0, -8):
			progress = radius / max(1, max_radius)
			alpha = int((1.0 - progress) * (1.0 - progress) * 100)
			if alpha <= 0:
				continue

			draw_circle((90, 205, 225, alpha), glow_center, radius, target=haze)

		blit_surface(haze, (0, 0), target=surface)

		top_shadow = create_surface(self.world_width, self.world_height, alpha=True)
		shadow_height = int(self.world_height * 0.48)
		for y in range(shadow_height):
			progress = y / max(1, shadow_height - 1)
			alpha = int((1.0 - progress) * 105)
			draw_line((0, 0, 0, alpha), (0, y), (self.world_width, y), target=top_shadow)

		blit_surface(top_shadow, (0, 0), target=surface)
		return surface

	def _build_blurred_layer(self, source: SurfaceLike, downscale: float = 0.2, passes: int = 2) -> SurfaceLike:
		width, height = source.get_size()
		small_width = max(1, int(width * downscale))
		small_height = max(1, int(height * downscale))

		# Reescalar para baixo e para cima cria um blur barato e suficiente para o menu.
		blurred = source.copy()
		for _ in range(max(1, passes)):
			blurred = scale_surface(blurred, small_width, small_height, smooth=True)
			blurred = scale_surface(blurred, width, height, smooth=True)

		blurred = blurred.convert_alpha()
		blurred.set_alpha(132)
		return blurred

	def _build_depth_layer(self) -> SurfaceLike:
		overlay = create_surface(self.world_width, self.world_height, alpha=True)
		horizon_height = int(self.world_height * 0.50)

		for y in range(horizon_height):
			progress = y / max(1, horizon_height - 1)
			alpha = int((1.0 - progress) * 112)
			draw_line((0, 0, 0, alpha), (0, y), (self.world_width, y), target=overlay)

		return overlay

	def _build_logo_surface(self) -> SurfaceLike:
		logo_width = max(1, int(self.logo.width * self.logo_scale))
		logo_height = max(1, int(self.logo.height * self.logo_scale))
		return scale_surface(self.logo.image, logo_width, logo_height, smooth=True).convert_alpha()

	def _draw_logo(self, target: SurfaceLike) -> None:
		logo_width = self.logo_surface.get_width()
		logo_height = self.logo_surface.get_height()
		logo_x = min(max(32, int(self.world_width * 0.50)), self.world_width - logo_width - 32)
		logo_y = min(max(32, int(self.world_height * 0.35)), self.world_height - logo_height - 32)

		# O deslocamento leve pelo mouse dá profundidade sem atrapalhar a legibilidade.
		logo_x += int(self._mouse_norm_x * 10.0)
		logo_y += int(self._mouse_norm_y * 8.0)
		blit_surface(self.logo_surface, (logo_x, logo_y), target=target)

	def _draw_buttons(self, target: SurfaceLike) -> None:
		offset_x, offset_y = self._button_layer_offset()

		for index, button in enumerate(self.buttons):
			is_hovered = index == self._hover_index
			draw_x = button.x + offset_x
			draw_y = button.y + offset_y
			text_surface = button.hover_surface if is_hovered else button.text_surface

			blit_surface(button.shadow_surface, (draw_x + 2, draw_y + 2), target=target)
			blit_surface(text_surface, (draw_x, draw_y), target=target)

	def _button_layer_offset(self) -> tuple[int, int]:
		return (int(self._mouse_norm_x * 6.0), int(self._mouse_norm_y * 4.0))

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
		self.game.stop()
