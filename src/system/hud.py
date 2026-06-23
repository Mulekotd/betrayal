from __future__ import annotations

from pathlib import Path

from src.utils.rect import Rect
from src.utils.services import FontLibrary
from src.utils.types import SurfaceLike
from src.utils.window import blit_surface, draw_rect, get_screen, load_image, scale_surface


def _load_image_scaled(path: Path, width: int | None = None, height: int | None = None) -> SurfaceLike | None:
	if not path.exists():
		return None

	surface = load_image(path, alpha=True)
	if width is None and height is None:
		return surface

	if width is not None and height is not None:
		return scale_surface(surface, width, height, smooth=False)

	if width is not None:
		ratio = width / max(1, surface.get_width())
		return scale_surface(surface, width, int(surface.get_height() * ratio), smooth=False)

	ratio = height / max(1, surface.get_height())
	return scale_surface(surface, int(surface.get_width() * ratio), height, smooth=False)


class HUDColors:
	HUD_TEXT = (245, 245, 235)
	HP_BG = (20, 10, 10)
	HP_FILL = (200, 50, 50)
	HP_FILL_LOW = (230, 100, 30)
	HP_BORDER = (80, 30, 30)
	HP_TEXT = HUD_TEXT
	XP_BG = (10, 10, 24)
	XP_FILL = (50, 120, 255)
	XP_BORDER = (30, 60, 120)
	XP_TEXT = HUD_TEXT
	KILLS_TEXT = HUD_TEXT
	TIMER_TEXT = HUD_TEXT
	TIMER_SHADOW = (0, 0, 0)
	WEAPON_BG = (18, 22, 28)
	WEAPON_BORDER = (70, 80, 90)
	WEAPON_SELECTED_BORDER = (235, 210, 120)
	WEAPON_INNER = (8, 10, 14)


class HUD:
	def __init__(
		self,
		viewport_width: int,
		viewport_height: int,
		fonts: FontLibrary,
		images_dir: Path,
		padding: int = 0,
	) -> None:
		self.viewport_width = viewport_width
		self.viewport_height = viewport_height
		self.padding = max(0, int(padding))

		self.font_hud = fonts.mini(30)
		self.font_xp = fonts.mini(22)
		self.font_small = fonts.mini(18)

		self.hp_bar_width = 190
		self.hp_bar_height = 20
		self.hp_bar_x = self.padding + 8
		self.hp_bar_y = self.padding + 8

		self.xp_bar_height = 20
		self.xp_bar_x = 0
		self.xp_bar_y = viewport_height - self.xp_bar_height

		self.weapon_order = ("fire", "ice", "wind")
		self.weapon_slot_size = 64
		self.weapon_icon_padding = 10
		self.weapon_gap = 8

		icon_inner = max(1, self.weapon_slot_size - self.weapon_icon_padding * 2)
		self.weapon_icons: dict[str, SurfaceLike | None] = {
			key: _load_image_scaled(images_dir / filename, icon_inner, icon_inner)
			for key, filename in {
				"fire": "fire_sword.png",
				"ice": "ice_sword.png",
				"wind": "wind_sword.png",
			}.items()
		}
		self._weapon_rect_cache = self._build_weapon_rects()

	def draw(
		self,
		player: object,
		total_kills: int,
		selected_weapon: str | None = None,
		run_time: float = 0.0,
		fps_value: float | None = None,
	) -> None:
		self._draw_hp_bar(player)
		self._draw_xp_bar(player)
		self._draw_weapon_bar(selected_weapon)
		self._draw_timer(run_time)
		self._draw_kills_counter(total_kills)
		if fps_value is not None:
			self._draw_fps(fps_value)

	def pick_weapon(self, x: float, y: float) -> str | None:
		for key, rect in self._weapon_rect_cache.items():
			if rect.left <= x <= rect.right and rect.top <= y <= rect.bottom:
				return key

		return None

	def _draw_hp_bar(self, player: object) -> None:
		screen = get_screen()
		current_hp = float(getattr(player, "health", 0.0))
		max_hp = float(getattr(player, "max_health", 1.0))
		ratio = min(1.0, max(0.0, current_hp / max(1.0, max_hp)))

		draw_rect(
			HUDColors.HP_BG,
			(self.hp_bar_x, self.hp_bar_y, self.hp_bar_width, self.hp_bar_height),
			target=screen,
		)

		fill_width = max(0, int(self.hp_bar_width * ratio))
		if fill_width > 0:
			fill_color = HUDColors.HP_FILL_LOW if ratio < 0.30 else HUDColors.HP_FILL
			draw_rect(
				fill_color,
				(self.hp_bar_x, self.hp_bar_y, fill_width, self.hp_bar_height),
				target=screen,
			)

		self._draw_box_border(self.hp_bar_x, self.hp_bar_y, self.hp_bar_width, self.hp_bar_height, HUDColors.HP_BORDER)

		label = f"HP  {int(current_hp)} / {int(max_hp)}"
		surface = self.font_xp.render(label, False, HUDColors.HP_TEXT)
		screen.blit(
			surface,
			(
				self.hp_bar_x + (self.hp_bar_width - surface.get_width()) // 2,
				self.hp_bar_y + (self.hp_bar_height - surface.get_height()) // 2,
			),
		)

	def _draw_xp_bar(self, player: object) -> None:
		screen = get_screen()
		current_xp = int(getattr(player, "xp", 0))
		xp_to_next = max(1, int(getattr(player, "xp_to_next", 1)))
		level = int(getattr(player, "level", 1))
		ratio = min(1.0, max(0.0, current_xp / xp_to_next))

		draw_rect(
			HUDColors.XP_BG,
			(self.xp_bar_x, self.xp_bar_y, self.viewport_width, self.xp_bar_height),
			target=screen,
		)

		fill_width = max(0, int(self.viewport_width * ratio))
		if fill_width > 0:
			draw_rect(HUDColors.XP_FILL, (self.xp_bar_x, self.xp_bar_y, fill_width, self.xp_bar_height), target=screen)

		draw_rect(HUDColors.XP_BORDER, (self.xp_bar_x, self.xp_bar_y, self.viewport_width, 1), target=screen)

		label = f"LV {level}"
		surface = self.font_xp.render(label, False, HUDColors.XP_TEXT)
		screen.blit(surface, ((self.viewport_width - surface.get_width()) // 2, self.xp_bar_y + (self.xp_bar_height - surface.get_height()) // 2))

	def _draw_kills_counter(self, total_kills: int) -> None:
		screen = get_screen()
		label = f"Kills: {total_kills}"
		shadow = self.font_hud.render(label, False, HUDColors.TIMER_SHADOW)
		surface = self.font_hud.render(label, False, HUDColors.KILLS_TEXT)
		x = self.hp_bar_x
		y = self.hp_bar_y + self.hp_bar_height + 8

		screen.blit(shadow, (x + 1, y + 1))
		screen.blit(surface, (x, y))

	def _draw_timer(self, run_time: float) -> None:
		screen = get_screen()
		label = self._timer_label(run_time)
		text_surface = self.font_hud.render(label, False, HUDColors.TIMER_TEXT)
		shadow_surface = self.font_hud.render(label, False, HUDColors.TIMER_SHADOW)
		text_x, text_y, _, _ = self._timer_rect(label)

		screen.blit(shadow_surface, (text_x + 1, text_y + 1))
		screen.blit(text_surface, (text_x, text_y))

	def _draw_fps(self, fps_value: float) -> None:
		screen = get_screen()
		label = f"FPS: {int(round(fps_value))}" if fps_value > 0.0 else "FPS: --"
		text_surface = self.font_small.render(label, False, HUDColors.TIMER_TEXT)
		shadow_surface = self.font_small.render(label, False, HUDColors.TIMER_SHADOW)

		x = self.viewport_width - text_surface.get_width() - self.padding - 12
		y = self.padding + 10
		screen.blit(shadow_surface, (x + 1, y + 1))
		screen.blit(text_surface, (x, y))

	def _draw_weapon_bar(self, selected_weapon: str | None) -> None:
		screen = get_screen()

		for key, rect in self._weapon_rect_cache.items():
			selected = key == selected_weapon
			border_color = HUDColors.WEAPON_SELECTED_BORDER if selected else HUDColors.WEAPON_BORDER
			border_width = 2 if selected else 1

			draw_rect(HUDColors.WEAPON_BG, rect, target=screen)
			draw_rect(
				HUDColors.WEAPON_INNER,
				(rect.left + 4, rect.top + 4, rect.width - 8, rect.height - 8),
				target=screen,
			)
			draw_rect(border_color, rect, width=border_width, target=screen)

			icon = self.weapon_icons.get(key)
			if icon is None:
				continue

			icon_x = rect.left + self.weapon_icon_padding + ((self.weapon_slot_size - self.weapon_icon_padding * 2 - icon.get_width()) // 2)
			icon_y = rect.top + self.weapon_icon_padding + ((self.weapon_slot_size - self.weapon_icon_padding * 2 - icon.get_height()) // 2)
			blit_surface(icon, (icon_x, icon_y), target=screen)

	def _timer_label(self, run_time: float) -> str:
		total_seconds = int(run_time)
		return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"

	def _timer_rect(self, label: str) -> tuple[int, int, int, int]:
		surface = self.font_hud.render(label, False, HUDColors.TIMER_TEXT)
		text_width = surface.get_width()
		text_height = surface.get_height()
		return (
			(self.viewport_width - text_width) // 2,
			self.padding + 8,
			text_width,
			text_height,
		)

	def _draw_box_border(self, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
		screen = get_screen()
		draw_rect(color, (x, y, width, 1), target=screen)
		draw_rect(color, (x, y + height - 1, width, 1), target=screen)
		draw_rect(color, (x, y, 1, height), target=screen)
		draw_rect(color, (x + width - 1, y, 1, height), target=screen)

	def _build_weapon_rects(self) -> dict[str, Rect]:
		base_x = self.padding + 8
		base_y = self.xp_bar_y - self.weapon_gap - self.weapon_slot_size

		return {
			key: Rect(
				base_x + index * (self.weapon_slot_size + self.weapon_gap),
				base_y,
				self.weapon_slot_size,
				self.weapon_slot_size,
			)
			for index, key in enumerate(self.weapon_order)
		}
