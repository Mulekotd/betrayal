from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pygame


@dataclass
class FontLibrary:
	font_path: Path
	_cache: dict[int, pygame.font.Font] = field(default_factory=dict)

	def get(self, size: int) -> pygame.font.Font:
		size = max(1, int(size))
		font = self._cache.get(size)
		
		if font is None:
			font = pygame.font.Font(str(self.font_path), size)
			self._cache[size] = font

		return font


@dataclass
class GameServices:
	assets_dir: Path
	images_dir: Path
	fonts_dir: Path
	font_path: Path
	fonts: FontLibrary = field(init=False)

	def __post_init__(self) -> None:
		self.fonts = FontLibrary(self.font_path)
