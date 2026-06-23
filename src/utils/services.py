from dataclasses import dataclass, field
from pathlib import Path

from src.utils.types import FontLike
from src.utils.window import get_window


@dataclass
class FontLibrary:
	font_path: Path
	title_path: Path | None = None
	mini_path: Path | None = None
	_cache: dict[tuple[str, int], FontLike] = field(default_factory=dict)

	def get(self, size: int) -> FontLike:
		return self._load("ui", self.font_path, size)

	def title(self, size: int) -> FontLike:
		return self._load("title", self.title_path or self.font_path, size)

	def mini(self, size: int) -> FontLike:
		return self._load("mini", self.mini_path or self.font_path, size)

	def _load(self, family: str, path: Path, size: int) -> FontLike:
		size = max(1, int(size))
		key = (family, size)
		font = self._cache.get(key)
		
		if font is None:
			font = get_window().load_font(path, size)
			self._cache[key] = font

		return font


@dataclass
class GameServices:
	assets_dir: Path
	images_dir: Path
	fonts_dir: Path
	font_path: Path
	fonts: FontLibrary = field(init=False)

	def __post_init__(self) -> None:
		title_path = self.fonts_dir / "Kenney High.ttf"
		mini_path = self.fonts_dir / "Kenney Mini.ttf"
		self.fonts = FontLibrary(
			font_path=self.font_path,
			title_path=title_path if title_path.exists() else None,
			mini_path=mini_path if mini_path.exists() else None,
		)
