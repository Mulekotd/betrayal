from pathlib import Path

from src.utils.rect import Rect
from src.utils.services import FontLibrary
from src.utils.window import draw_rect, get_screen, load_image, scale_surface, blit_surface


class HUD:
	def __init__(
		self,
		viewport_width: int,
		viewport_height: int,
		fonts: FontLibrary,
		images_dir: Path,
		padding: int = 0
	) -> None:
		self.viewport_width = viewport_width
		self.viewport_height = viewport_height
		self.padding = max(0, int(padding))
		self.font_small = fonts.get(22)

		self.weapon_order = ["fire", "ice", "wind"]
		self.weapon_icon_size = 44
		self.weapon_icon_gap = 12
		self.weapon_icon_padding = 8
		self.weapon_icons: dict[str, object] = {}

		sword_files = {
			"fire": images_dir / "fire_sword.png",
			"ice": images_dir / "ice_sword.png",
			"wind": images_dir / "wind_sword.png"
		}

		icon_target = max(1, self.weapon_icon_size - (self.weapon_icon_padding * 2))
		for key, path in sword_files.items():
			if not path.exists():
				continue

			icon = load_image(str(path), alpha=True)
			if icon is not None:
				icon = scale_surface(icon, icon_target, icon_target, smooth=True)
				self.weapon_icons[key] = icon

	def draw(self, player: object, total_kills: int, selected_weapon: str | None = None) -> None:
		self._draw_xp_bar(player)
		self._draw_kills_counter(total_kills)
		self._draw_weapon_bar(selected_weapon)

	def pick_weapon(self, x: float, y: float) -> str | None:
		for key, rect in self._get_weapon_rects().items():
			if rect.left <= x <= rect.right and rect.top <= y <= rect.bottom:
				return key
		return None

	def _draw_xp_bar(self, player: object) -> None:
		bar_margin = self.padding
		bar_height = 22
		bar_width = max(0, self.viewport_width - (bar_margin * 2))

		bar_x = bar_margin
		bar_y = bar_margin

		draw_rect((16, 18, 22), (bar_x, bar_y, bar_width, bar_height))

		xp_value = int(getattr(player, "xp", 0))
		xp_to_next = max(1, int(getattr(player, "xp_to_next", 1)))

		fill_ratio = min(1.0, max(0.0, xp_value / xp_to_next))
		fill_width = int(bar_width * fill_ratio)

		if fill_width > 0:
			draw_rect((30, 120, 255), (bar_x, bar_y, fill_width, bar_height))

		level = int(getattr(player, "level", 1))

		label = f"LV {level}"
		label_surface = self.font_small.render(label, True, (255, 255, 255))
		label_x = bar_x + bar_width - label_surface.get_width() - 8
		label_y = bar_y + (bar_height - label_surface.get_height()) // 2

		screen = get_screen()
		screen.blit(label_surface, (label_x, label_y))

	def _draw_kills_counter(self, total_kills: int) -> None:
		screen = get_screen()

		bar_margin = self.padding
		bar_height = 22

		label = f"Kills: {total_kills}"
		label_surface = self.font_small.render(label, True, (255, 255, 255))
		label_x = bar_margin
		label_y = bar_margin + bar_height + 6

		screen.blit(label_surface, (label_x, label_y))

	def _get_weapon_rects(self) -> dict[str, Rect]:
		base_x = self.padding
		base_y = self.viewport_height - self.padding - self.weapon_icon_size
		rects: dict[str, Rect] = {}

		for index, key in enumerate(self.weapon_order):
			x = base_x + index * (self.weapon_icon_size + self.weapon_icon_gap)
			rects[key] = Rect(x, base_y, self.weapon_icon_size, self.weapon_icon_size)

		return rects

	def _draw_weapon_bar(self, selected_weapon: str | None) -> None:
		screen = get_screen()

		for key, rect in self._get_weapon_rects().items():
			is_selected = key == selected_weapon
			border_color = (235, 210, 120) if is_selected else (70, 80, 90)
			bg_color = (18, 22, 28)

			draw_rect(bg_color, (rect.left, rect.top, rect.width, rect.height), border_radius=8, target=screen)
			draw_rect(border_color, (rect.left, rect.top, rect.width, rect.height), width=2, border_radius=8, target=screen)

			icon = self.weapon_icons.get(key)
			if icon is not None:
				inner_left = rect.left + self.weapon_icon_padding
				inner_top = rect.top + self.weapon_icon_padding
				inner_size = rect.width - (self.weapon_icon_padding * 2)
				icon_x = inner_left + (inner_size - icon.get_width()) // 2
				icon_y = inner_top + (inner_size - icon.get_height()) // 2

				blit_surface(icon, (icon_x, icon_y), target=screen)
