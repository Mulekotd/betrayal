from __future__ import annotations

import math
from pathlib import Path
from typing import cast

from external.pplay.window import Window

from src.utils.types import ColorValue, Point, RectTuple, SurfaceLike

_custom_cursor_enabled = False
_custom_cursor_visible = True


def _rect_tuple(rect: RectTuple | object) -> RectTuple:
	if all(hasattr(rect, attr) for attr in ("left", "top", "width", "height")):
		return (
			getattr(rect, "left"),
			getattr(rect, "top"),
			getattr(rect, "width"),
			getattr(rect, "height"),
		)

	return cast(RectTuple, rect)


def get_screen() -> SurfaceLike:
	screen = Window.get_screen()

	if screen is None:
		raise RuntimeError("Window screen is not initialized.")

	return screen


def get_window() -> Window:
	window = Window.get_instance()

	if window is None:
		raise RuntimeError("Window instance is not initialized.")

	return window


def load_image(image_path: str | Path, alpha: bool = True) -> SurfaceLike:
	return get_window().load_image(str(image_path), alpha=alpha)


def create_surface(width: int, height: int, alpha: bool = False) -> SurfaceLike:
	return get_window().create_surface(width, height, alpha=alpha)


def scale_surface(surface: SurfaceLike, width: int, height: int, smooth: bool = False) -> SurfaceLike:
	return get_window().scale_surface(surface, width, height, smooth=smooth)


def rotate_surface(surface: SurfaceLike, angle_deg: float) -> SurfaceLike:
	return get_window().rotate_surface(surface, angle_deg)


def flip_surface(surface: SurfaceLike, flip_x: bool = False, flip_y: bool = False) -> SurfaceLike:
	return get_window().flip_surface(surface, flip_x=flip_x, flip_y=flip_y)


def draw_rect(
	color: ColorValue,
	rect: RectTuple | object,
	width: int = 0,
	border_radius: int = 0,
	target: SurfaceLike | None = None,
) -> None:
	get_window().draw_rect(
		color,
		_rect_tuple(rect),
		width=width,
		border_radius=border_radius,
		target=target,
	)


def draw_circle(
	color: ColorValue,
	center: Point,
	radius: int,
	width: int = 0,
	target: SurfaceLike | None = None,
) -> None:
	get_window().draw_circle(color, center, radius, width=width, target=target)


def draw_line(
	color: ColorValue,
	start_pos: Point,
	end_pos: Point,
	width: int = 1,
	target: SurfaceLike | None = None,
) -> None:
	get_window().draw_line(color, start_pos, end_pos, width=width, target=target)


def draw_arc(
	color: ColorValue,
	rect: RectTuple | object,
	start_angle: float,
	end_angle: float,
	width: int = 1,
	target: SurfaceLike | None = None,
) -> None:
	x, y, rect_width, rect_height = _rect_tuple(rect)
	radius = max(1.0, min(rect_width, rect_height) * 0.5)
	center_x = x + rect_width * 0.5
	center_y = y + rect_height * 0.5

	# A biblioteca não expõe arco nativo aqui, então rasterizamos o contorno por segmentos.
	arc_span = end_angle - start_angle
	steps = max(8, int(abs(arc_span) * radius * 0.12))

	prev_x = center_x + math.cos(start_angle) * radius
	prev_y = center_y + math.sin(start_angle) * radius

	for step in range(1, steps + 1):
		progress = step / steps
		angle = start_angle + arc_span * progress

		next_x = center_x + math.cos(angle) * radius
		next_y = center_y + math.sin(angle) * radius
		draw_line(color, (prev_x, prev_y), (next_x, next_y), width=width, target=target)
		prev_x, prev_y = next_x, next_y


def blit_surface(surface: SurfaceLike, pos: Point, target: SurfaceLike | None = None) -> None:
	get_window().blit_surface(surface, pos, target=target)


def create_mask_surface(surface: SurfaceLike, setcolor: ColorValue, unsetcolor: ColorValue) -> SurfaceLike:
	width = surface.get_width()
	height = surface.get_height()
	mask_surface = create_surface(width, height, alpha=True)

	# Reaproveitamos a transparência original para gerar sobreposições de dano/status sem novos assets.
	for y in range(height):
		for x in range(width):
			mask_surface.set_at((x, y), setcolor if surface.get_at((x, y))[3] > 0 else unsetcolor)

	return mask_surface


def set_icon(icon_path: str | Path) -> None:
	get_window().set_icon(icon_path)


def enable_custom_cursor(enabled: bool) -> None:
	global _custom_cursor_enabled
	_custom_cursor_enabled = bool(enabled)

	if _custom_cursor_enabled:
		get_window().set_mouse_visible(False)
		return

	get_window().set_mouse_visible(_custom_cursor_visible)


def set_mouse_visible(visible: bool) -> None:
	global _custom_cursor_visible
	_custom_cursor_visible = bool(visible)

	# Quando o cursor customizado está ativo, mantemos o cursor nativo oculto.
	if _custom_cursor_enabled:
		get_window().set_mouse_visible(False)
		return

	get_window().set_mouse_visible(_custom_cursor_visible)


def is_mouse_visible() -> bool:
	return _custom_cursor_visible
