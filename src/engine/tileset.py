from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pygame

from src.utils.window import get_screen


@dataclass
class TileDefinition:
	id: int
	surface: pygame.Surface
	collidable_by_default: bool = True

	@property
	def width(self) -> int:
		return self.surface.get_width()

	@property
	def height(self) -> int:
		return self.surface.get_height()


@dataclass
class TileObject:
	tile: TileDefinition
	x: float
	y: float
	collidable: bool = True

	@property
	def width(self) -> int:
		return self.tile.width

	@property
	def height(self) -> int:
		return self.tile.height

	@property
	def rect(self) -> pygame.Rect:
		return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

	@property
	def center(self) -> tuple[float, float]:
		return (self.x + self.width * 0.5, self.y + self.height * 0.5)

	@property
	def radius(self) -> float:
		return max(2.0, min(self.width, self.height) * 0.5)

	def draw(self, camera_x: float = 0.0, camera_y: float = 0.0) -> None:
		get_screen().blit(self.tile.surface, (self.x - camera_x, self.y - camera_y))


class TileSet:
	def __init__(
		self,
		tileset_path: str | Path,
		tile_width: int = 0,
		tile_height: int = 0,
		gap: int = 0,
		tile_scale: float = 1.0,
		alpha_threshold: int = 1,
		gap_tolerance: int | None = None,
	) -> None:
		self.tileset_path = Path(tileset_path)
		self.tile_width = max(0, int(tile_width))
		self.tile_height = max(0, int(tile_height))
		self.gap = max(0, int(gap))
		self.tile_scale = max(0.1, float(tile_scale))
		self.alpha_threshold = max(0, int(alpha_threshold))
		self.gap_tolerance = (
			max(1, min(4, self.gap if self.gap > 0 else 1))
			if gap_tolerance is None
			else max(0, int(gap_tolerance))
		)

		self.sheet = pygame.image.load(str(self.tileset_path)).convert_alpha()
		self.tiles: list[TileDefinition] = []

		if self.tile_width > 0 and self.tile_height > 0:
			self._slice_hybrid()
		else:
			self._slice_auto()

	def create_object(self, tile_index: int, x: float, y: float, collidable: bool | None = None) -> TileObject:
		if not self.tiles:
			raise ValueError("TileSet has no parsed tiles.")

		tile = self.tiles[tile_index % len(self.tiles)]
		can_collide = tile.collidable_by_default if collidable is None else bool(collidable)

		return TileObject(tile=tile, x=x, y=y, collidable=can_collide)

	def _slice_hybrid(self) -> None:
		alpha = pygame.surfarray.array_alpha(self.sheet).T
		sheet_height = alpha.shape[0]
		step_y = max(1, self.tile_height + self.gap)
		seen_rects: set[tuple[int, int, int, int]] = set()

		for expected_top in range(0, sheet_height, step_y):
			expected_bottom = min(sheet_height, expected_top + self.tile_height)
			row_start, row_end = self._resolve_row_range(alpha, expected_top, expected_bottom)

			if row_end <= row_start:
				continue

			row_area = alpha[row_start:row_end, :]
			if row_area.size == 0 or not (row_area > self.alpha_threshold).any():
				continue

			col_ranges = self._detect_col_ranges(alpha, row_start, row_end)

			if not col_ranges:
				col_ranges = self._fixed_col_ranges(alpha, row_start, row_end)

			for col_start, col_end in col_ranges:
				rect = (col_start, row_start, col_end - col_start, row_end - row_start)

				if rect[2] <= 0 or rect[3] <= 0:
					continue

				if rect in seen_rects:
					continue

				seen_rects.add(rect)
				self._append_tile(rect)

	def _slice_auto(self) -> None:
		alpha = pygame.surfarray.array_alpha(self.sheet).T
		row_mask = (alpha > self.alpha_threshold).any(axis=1)
		row_ranges = self._mask_to_ranges(row_mask, gap_tolerance=self.gap_tolerance)

		for row_start, row_end in row_ranges:
			col_ranges = self._detect_col_ranges(alpha, row_start, row_end)

			for col_start, col_end in col_ranges:
				rect = (col_start, row_start, col_end - col_start, row_end - row_start)

				if rect[2] <= 0 or rect[3] <= 0:
					continue

				self._append_tile(rect)

	def _append_tile(self, rect_tuple: tuple[int, int, int, int]) -> None:
		x, y, w, h = rect_tuple
		rect = pygame.Rect(x, y, w, h)
		frame = self.sheet.subsurface(rect).copy()

		if self.tile_scale != 1.0:
			scaled_w = max(1, int(frame.get_width() * self.tile_scale))
			scaled_h = max(1, int(frame.get_height() * self.tile_scale))
			frame = pygame.transform.scale(frame, (scaled_w, scaled_h)).convert_alpha()

		tile_id = len(self.tiles)
		self.tiles.append(TileDefinition(id=tile_id, surface=frame, collidable_by_default=True))

	def _resolve_row_range(self, alpha, expected_top: int, expected_bottom: int) -> tuple[int, int]:
		height = alpha.shape[0]

		expected_top = max(0, min(expected_top, max(0, height - 1)))
		expected_bottom = max(expected_top + 1, min(expected_bottom, height))

		probe_pad = max(2, self.gap_tolerance * 2)
		probe_top = max(0, expected_top - probe_pad)
		probe_bottom = min(height, expected_bottom + probe_pad)
		probe = alpha[probe_top:probe_bottom, :]

		row_mask = (probe > self.alpha_threshold).any(axis=1)
		ranges = self._mask_to_ranges(row_mask, gap_tolerance=self.gap_tolerance)

		if not ranges:
			return expected_top, expected_bottom

		expected_center = (expected_top + expected_bottom) * 0.5
		best_start = expected_top
		best_end = expected_bottom
		best_distance = float("inf")

		for local_start, local_end in ranges:
			global_start = probe_top + local_start
			global_end = probe_top + local_end
			center = (global_start + global_end) * 0.5
			distance = abs(center - expected_center)

			if distance < best_distance:
				best_distance = distance
				best_start = global_start
				best_end = global_end

		return best_start, best_end

	def _detect_col_ranges(self, alpha, row_start: int, row_end: int) -> list[tuple[int, int]]:
		if row_end <= row_start:
			return []

		row_slice = alpha[row_start:row_end, :]
		col_mask = (row_slice > self.alpha_threshold).any(axis=0)

		return self._mask_to_ranges(col_mask, gap_tolerance=self.gap_tolerance)

	def _fixed_col_ranges(self, alpha, row_start: int, row_end: int) -> list[tuple[int, int]]:
		if self.tile_width <= 0 or row_end <= row_start:
			return []

		row_slice = alpha[row_start:row_end, :]
		sheet_width = row_slice.shape[1]
		step_x = max(1, self.tile_width + self.gap)

		ranges: list[tuple[int, int]] = []
		for x in range(0, max(1, sheet_width - self.tile_width + 1), step_x):
			x_end = min(sheet_width, x + self.tile_width)
			if x_end <= x:
				continue

			segment = row_slice[:, x:x_end]
			if segment.size == 0 or not (segment > self.alpha_threshold).any():
				continue

			ranges.append((x, x_end))

		return ranges

	def _mask_to_ranges(self, mask, gap_tolerance: int = 0) -> list[tuple[int, int]]:
		ranges: list[tuple[int, int]] = []
		start = None
		gap_start = None

		for idx, value in enumerate(mask):
			if value and start is None:
				start = idx
				gap_start = None
			elif not value and start is not None:
				if gap_start is None:
					gap_start = idx

				if gap_tolerance <= 0:
					ranges.append((start, idx))
					start = None
					gap_start = None
			elif value and start is not None and gap_start is not None:
				gap_len = idx - gap_start

				if gap_len > gap_tolerance:
					ranges.append((start, gap_start))
					start = idx

				gap_start = None

		if start is not None:
			end = gap_start if gap_start is not None else len(mask)
			ranges.append((start, end))

		return ranges
