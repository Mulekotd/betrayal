from __future__ import annotations

from pathlib import Path
from typing import Iterable

from typing import Any

from src.utils.window import create_surface, flip_surface, load_image, scale_surface


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
		self.frame_width = max(0, int(width))
		self.frame_height = max(0, int(height))
		self.gap = max(0, int(gap))
		self.actions = list(actions)
		self.frame_rate = max(1, frame_rate)
		self.alpha_threshold = 1
		self.gap_tolerance = max(1, min(4, self.gap if self.gap > 0 else 1))

		self.sheet = load_image(str(self.sprite_path), alpha=True)
		self.frames: dict[str, list[Any]] = {}
		self._flip_cache: dict[tuple[str, int, bool, bool], Any] = {}

		if self.frame_width > 0 and self.frame_height > 0:
			self._slice_hybrid()
		else:
			self._slice_auto()

		for action in self.actions:
			self.frames.setdefault(action, [])

		action_count = sum(1 for frames in self.frames.values() if frames)
		total_frames = sum(len(frames) for frames in self.frames.values())

		print(f"[Animation] {self.sprite_path.name}: actions={action_count} frames={total_frames}")

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

	def get_frame(self) -> Any | None:
		frames = self.frames.get(self.current_action, [])

		if not frames:
			return None

		return frames[self.current_index]

	def get_frame_flipped(self, flip_x: bool = False, flip_y: bool = False) -> Any | None:
		frame = self.get_frame()

		if frame is None:
			return None

		if not flip_x and not flip_y:
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
		frames = self.frames.get(lookup, [])

		return len(frames) * self.frame_rate

	def _slice_hybrid(self) -> None:
		# Hybrid parser: uses fixed rows (grid guidance) and auto-detected columns.
		sheet_height = self.sheet.get_height()
		step_y = max(1, self.frame_height + self.gap)

		max_w = self.frame_width
		max_h = self.frame_height

		for row_index, action in enumerate(self.actions):
			expected_top = row_index * step_y
			expected_bottom = expected_top + self.frame_height

			if expected_top >= sheet_height:
				self.frames[action] = []
				continue

			row_start, row_end = self._resolve_row_range(expected_top, expected_bottom)
			col_ranges = self._detect_col_ranges(row_start, row_end)

			if not col_ranges:
				col_ranges = self._fixed_col_ranges(row_start, row_end)

			frames: list[Any] = []
			for col_start, col_end in col_ranges:
				if col_end <= col_start:
					continue

				frame_width = col_end - col_start
				frame_height = row_end - row_start
				if frame_width <= 0 or frame_height <= 0:
					continue

				if not self._surface_has_pixels(col_start, row_start, frame_width, frame_height):
					continue

				frame = self.sheet.subsurface((col_start, row_start, frame_width, frame_height)).copy()
				frames.append(frame)

				max_w = max(max_w, frame.get_width())
				max_h = max(max_h, frame.get_height())

			self.frames[action] = frames

		self.frame_width = max_w
		self.frame_height = max_h

		if self.frame_width > 0 and self.frame_height > 0:
			self._normalize_frame_sizes(self.frame_width, self.frame_height)

	def _slice_auto(self) -> None:
		row_ranges = self._mask_to_ranges(self._row_mask(0, self.sheet.get_height()), gap_tolerance=self.gap_tolerance)

		if not row_ranges:
			return

		max_w = 0
		max_h = 0

		for row_index, (row_start, row_end) in enumerate(row_ranges):
			if row_index >= len(self.actions):
				break

			col_ranges = self._detect_col_ranges(row_start, row_end)

			frames: list[Any] = []
			for col_start, col_end in col_ranges:
				frame_width = col_end - col_start
				frame_height = row_end - row_start

				if frame_width <= 0 or frame_height <= 0:
					continue

				if not self._surface_has_pixels(col_start, row_start, frame_width, frame_height):
					continue

				frame = self.sheet.subsurface((col_start, row_start, frame_width, frame_height)).copy()
				frames.append(frame)

				max_w = max(max_w, frame.get_width())
				max_h = max(max_h, frame.get_height())

			action = self.actions[row_index]
			self.frames[action] = frames

		self.frame_width = max_w
		self.frame_height = max_h

		if self.frame_width > 0 and self.frame_height > 0:
			self._normalize_frame_sizes(self.frame_width, self.frame_height)

	def _resolve_row_range(self, expected_top: int, expected_bottom: int) -> tuple[int, int]:
		height = self.sheet.get_height()

		expected_top = max(0, min(expected_top, max(0, height - 1)))
		expected_bottom = max(expected_top + 1, min(expected_bottom, height))

		probe_pad = max(2, self.gap_tolerance * 2)
		probe_top = max(0, expected_top - probe_pad)
		probe_bottom = min(height, expected_bottom + probe_pad)

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

		col_mask = self._column_mask(row_start, row_end)

		return self._mask_to_ranges(col_mask, gap_tolerance=self.gap_tolerance)

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

	def _normalize_frame_sizes(self, width: int, height: int) -> None:
		for action, frames in self.frames.items():
			normalized: list[Any] = []

			for frame in frames:
				if frame.get_width() == width and frame.get_height() == height:
					normalized.append(frame)
					continue

				canvas = create_surface(width, height, alpha=True)

				offset_x = (width - frame.get_width()) // 2
				offset_y = height - frame.get_height()

				canvas.blit(frame, (offset_x, offset_y))
				normalized.append(canvas)

			self.frames[action] = normalized

	def _row_mask(self, top: int, bottom: int) -> list[bool]:
		mask: list[bool] = []
		for y in range(max(0, top), max(0, bottom)):
			mask.append(self._row_has_pixels(y))
		return mask

	def _column_mask(self, row_start: int, row_end: int) -> list[bool]:
		mask: list[bool] = []
		sheet_width = self.sheet.get_width()

		for x in range(sheet_width):
			mask.append(self._column_has_pixels(x, row_start, row_end))

		return mask

	def _row_has_pixels(self, y: int) -> bool:
		width = self.sheet.get_width()
		for x in range(width):
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
