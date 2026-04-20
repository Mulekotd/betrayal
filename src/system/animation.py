from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pygame


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

		self.sheet = pygame.image.load(str(self.sprite_path)).convert_alpha()
		self.frames: dict[str, list[pygame.Surface]] = {}

		if self.frame_width > 0 and self.frame_height > 0:
			for row_index, action in enumerate(self.actions):
				self.frames[action] = self._slice_row(row_index)
		else:
			self._slice_auto()

		total_frames = sum(len(frames) for frames in self.frames.values())
		print(f"[Animation] {self.sprite_path.name}: actions={len(self.frames)} frames={total_frames}")

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

	def get_frame(self) -> pygame.Surface | None:
		frames = self.frames.get(self.current_action, [])

		if not frames:
			return None

		return frames[self.current_index]

	def get_frame_flipped(self, flip_x: bool = False, flip_y: bool = False) -> pygame.Surface | None:
		frame = self.get_frame()

		if frame is None:
			return None

		if not flip_x and not flip_y:
			return frame

		return pygame.transform.flip(frame, flip_x, flip_y)

	def get_duration(self, action: str | None = None) -> int:
		lookup = action or self.current_action
		frames = self.frames.get(lookup, [])

		return len(frames) * self.frame_rate

	def _slice_row(self, row_index: int) -> list[pygame.Surface]:
		frames: list[pygame.Surface] = []

		sheet_width, sheet_height = self.sheet.get_size()
		step_x = self.frame_width + self.gap
		step_y = self.frame_height + self.gap

		y = row_index * step_y
		if y + self.frame_height > sheet_height:
			return frames

		for x in range(0, sheet_width - self.frame_width + 1, step_x):
			rect = pygame.Rect(x, y, self.frame_width, self.frame_height)

			if rect.right > sheet_width or rect.bottom > sheet_height:
				break

			frames.append(self.sheet.subsurface(rect).copy())

		return frames

	def _slice_auto(self) -> None:
		alpha = pygame.surfarray.array_alpha(self.sheet)
		height, width = alpha.shape

		row_mask = (alpha > 1).any(axis=1)
		row_ranges = self._mask_to_ranges(row_mask, gap_tolerance=6)

		if not row_ranges:
			return

		max_w = 0
		max_h = 0

		for row_index, (row_start, row_end) in enumerate(row_ranges):
			if row_index >= len(self.actions):
				break

			row_slice = alpha[row_start:row_end, :]
			col_mask = (row_slice > 1).any(axis=0)
			col_ranges = self._mask_to_ranges(col_mask, gap_tolerance=6)

			frames: list[pygame.Surface] = []
			for col_start, col_end in col_ranges:
				pad = 1

				x0 = max(0, col_start - pad)
				x1 = min(width, col_end + pad)
				y0 = max(0, row_start - pad)
				y1 = min(height, row_end + pad)

				rect = pygame.Rect(x0, y0, x1 - x0, y1 - y0)

				if rect.width <= 0 or rect.height <= 0:
					continue

				frame = self.sheet.subsurface(rect).copy()
				frames.append(frame)

				max_w = max(max_w, rect.width)
				max_h = max(max_h, rect.height)

			action = self.actions[row_index]
			self.frames[action] = frames

		self.frame_width = max_w
		self.frame_height = max_h
		if self.frame_width > 0 and self.frame_height > 0:
			self._normalize_frame_sizes(self.frame_width, self.frame_height)

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
			normalized: list[pygame.Surface] = []
			for frame in frames:
				if frame.get_width() == width and frame.get_height() == height:
					normalized.append(frame)
					continue
				canvas = pygame.Surface((width, height), pygame.SRCALPHA)
				canvas.blit(frame, (0, 0))
				normalized.append(canvas)
			self.frames[action] = normalized
