from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.utils.types import SurfaceLike
from src.utils.window import create_surface, flip_surface, load_image


class Animation:
	def __init__(
		self,
		sprite_path: str | Path,
		width: int,
		height: int,
		gap: int,
		actions: Iterable[str],
		frame_rate: int = 120,
	) -> None:
		self.sprite_path = Path(sprite_path)
		self.sheet = load_image(self.sprite_path, alpha=True)

		self.frame_rate = max(1, frame_rate)
		self.frame_width = max(0, int(width))
		self.frame_height = max(0, int(height))
		self.frames: dict[str, list[SurfaceLike]] = {}

		self.gap = max(0, int(gap))
		self.gap_tolerance = max(1, min(4, self.gap if self.gap > 0 else 1))
		self.actions = list(actions)
		self.alpha_threshold = 1
		self._flip_cache: dict[tuple[str, int, bool, bool], SurfaceLike] = {}

		if self.frame_width > 0 and self.frame_height > 0:
			self._slice_hybrid()
		else:
			self._slice_auto()

		for action in self.actions:
			self.frames.setdefault(action, [])

		self.current_action = self.actions[0] if self.actions else ""
		self.current_index = 0
		self.elapsed_ms = 0

	def play(self, action: str) -> None:
		if action == self.current_action:
			return

		self.current_action = action
		self.current_index = 0
		self.elapsed_ms = 0

	def update(self, delta_ms: int) -> None:
		frames = self.frames.get(self.current_action, [])
		if not frames:
			return

		self.elapsed_ms += delta_ms
		while self.elapsed_ms >= self.frame_rate:
			self.elapsed_ms -= self.frame_rate
			self.current_index = (self.current_index + 1) % len(frames)

	def get_frame(self) -> SurfaceLike | None:
		frames = self.frames.get(self.current_action, [])
		if not frames:
			return None

		return frames[self.current_index]

	def get_frame_flipped(self, flip_x: bool = False, flip_y: bool = False) -> SurfaceLike | None:
		frame = self.get_frame()
		if frame is None or (not flip_x and not flip_y):
			return frame

		key = (self.current_action, self.current_index, flip_x, flip_y)
		cached = self._flip_cache.get(key)
		if cached is not None:
			return cached

		flipped = flip_surface(frame, flip_x=flip_x, flip_y=flip_y)
		self._flip_cache[key] = flipped
		return flipped

	def get_duration(self, action: str | None = None) -> int:
		lookup = action or self.current_action
		return len(self.frames.get(lookup, [])) * self.frame_rate

	def _slice_hybrid(self) -> None:
		sheet_height = self.sheet.get_height()
		step_y = max(1, self.frame_height + self.gap)
		max_width = self.frame_width
		max_height = self.frame_height

		for row_index, action in enumerate(self.actions):
			expected_top = row_index * step_y
			expected_bottom = expected_top + self.frame_height

			if expected_top >= sheet_height:
				self.frames[action] = []
				continue

			row_start, row_end = self._resolve_row_range(expected_top, expected_bottom)
			col_ranges = self._detect_col_ranges(row_start, row_end) or self._fixed_col_ranges(row_start, row_end)

			frames: list[SurfaceLike] = []
			for col_start, col_end in col_ranges:
				frame_width = col_end - col_start
				frame_height = row_end - row_start
				if frame_width <= 0 or frame_height <= 0:
					continue

				if not self._surface_has_pixels(col_start, row_start, frame_width, frame_height):
					continue

				frame = self.sheet.subsurface((col_start, row_start, frame_width, frame_height)).copy()
				frames.append(frame)
				max_width = max(max_width, frame.get_width())
				max_height = max(max_height, frame.get_height())

			self.frames[action] = frames

		self.frame_width = max_width
		self.frame_height = max_height
		if self.frame_width > 0 and self.frame_height > 0:
			self._normalize_frame_sizes(self.frame_width, self.frame_height)

	def _slice_auto(self) -> None:
		row_ranges = self._mask_to_ranges(self._row_mask(0, self.sheet.get_height()), gap_tolerance=self.gap_tolerance)
		if not row_ranges:
			return

		max_width = 0
		max_height = 0
		for row_index, (row_start, row_end) in enumerate(row_ranges):
			if row_index >= len(self.actions):
				break

			frames: list[SurfaceLike] = []
			for col_start, col_end in self._detect_col_ranges(row_start, row_end):
				frame_width = col_end - col_start
				frame_height = row_end - row_start
				if frame_width <= 0 or frame_height <= 0:
					continue

				if not self._surface_has_pixels(col_start, row_start, frame_width, frame_height):
					continue

				frame = self.sheet.subsurface((col_start, row_start, frame_width, frame_height)).copy()
				frames.append(frame)
				max_width = max(max_width, frame.get_width())
				max_height = max(max_height, frame.get_height())

			self.frames[self.actions[row_index]] = frames

		self.frame_width = max_width
		self.frame_height = max_height
		if self.frame_width > 0 and self.frame_height > 0:
			self._normalize_frame_sizes(self.frame_width, self.frame_height)

	def _resolve_row_range(self, expected_top: int, expected_bottom: int) -> tuple[int, int]:
		sheet_height = self.sheet.get_height()
		expected_top = max(0, min(expected_top, max(0, sheet_height - 1)))
		expected_bottom = max(expected_top + 1, min(expected_bottom, sheet_height))

		probe_padding = max(2, self.gap_tolerance * 2)
		probe_top = max(0, expected_top - probe_padding)
		probe_bottom = min(sheet_height, expected_bottom + probe_padding)
		ranges = self._mask_to_ranges(self._row_mask(probe_top, probe_bottom), gap_tolerance=self.gap_tolerance)
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

	def _detect_col_ranges(self, row_start: int, row_end: int) -> list[tuple[int, int]]:
		if row_end <= row_start:
			return []

		return self._mask_to_ranges(self._column_mask(row_start, row_end), gap_tolerance=self.gap_tolerance)

	def _fixed_col_ranges(self, row_start: int, row_end: int) -> list[tuple[int, int]]:
		if self.frame_width <= 0 or row_end <= row_start:
			return []

		sheet_width = self.sheet.get_width()
		step_x = max(1, self.frame_width + self.gap)
		ranges: list[tuple[int, int]] = []

		for x in range(0, max(1, sheet_width - self.frame_width + 1), step_x):
			x_end = min(sheet_width, x + self.frame_width)
			if x_end <= x:
				continue

			if not self._surface_has_pixels(x, row_start, x_end - x, row_end - row_start):
				continue

			ranges.append((x, x_end))

		return ranges

	def _mask_to_ranges(self, mask: list[bool], gap_tolerance: int = 0) -> list[tuple[int, int]]:
		ranges: list[tuple[int, int]] = []
		start: int | None = None
		gap_start: int | None = None

		for index, value in enumerate(mask):
			if value and start is None:
				start = index
				gap_start = None
			elif not value and start is not None:
				if gap_start is None:
					gap_start = index

				if gap_tolerance <= 0:
					ranges.append((start, index))
					start = None
					gap_start = None
			elif value and start is not None and gap_start is not None:
				gap_length = index - gap_start
				if gap_length > gap_tolerance:
					ranges.append((start, gap_start))
					start = index

				gap_start = None

		if start is not None:
			ranges.append((start, gap_start if gap_start is not None else len(mask)))

		return ranges

	def _normalize_frame_sizes(self, width: int, height: int) -> None:
		for action, frames in self.frames.items():
			normalized: list[SurfaceLike] = []

			for frame in frames:
				if frame.get_width() == width and frame.get_height() == height:
					normalized.append(frame)
					continue

				# Centralizamos os sprites menores em uma tela comum para simplificar colisão e desenho.
				canvas = create_surface(width, height, alpha=True)
				offset_x = (width - frame.get_width()) // 2
				offset_y = height - frame.get_height()
				canvas.blit(frame, (offset_x, offset_y))
				normalized.append(canvas)

			self.frames[action] = normalized

	def _row_mask(self, top: int, bottom: int) -> list[bool]:
		return [self._row_has_pixels(y) for y in range(max(0, top), max(0, bottom))]

	def _column_mask(self, row_start: int, row_end: int) -> list[bool]:
		sheet_width = self.sheet.get_width()
		return [self._column_has_pixels(x, row_start, row_end) for x in range(sheet_width)]

	def _row_has_pixels(self, y: int) -> bool:
		for x in range(self.sheet.get_width()):
			if self.sheet.get_at((x, y)).a > self.alpha_threshold:
				return True

		return False

	def _column_has_pixels(self, x: int, row_start: int, row_end: int) -> bool:
		for y in range(max(0, row_start), max(0, row_end)):
			if self.sheet.get_at((x, y)).a > self.alpha_threshold:
				return True

		return False

	def _surface_has_pixels(self, start_x: int, start_y: int, width: int, height: int) -> bool:
		end_x = min(self.sheet.get_width(), start_x + width)
		end_y = min(self.sheet.get_height(), start_y + height)

		for y in range(max(0, start_y), max(0, end_y)):
			for x in range(max(0, start_x), max(0, end_x)):
				if self.sheet.get_at((x, y)).a > self.alpha_threshold:
					return True

		return False
