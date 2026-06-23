from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.utils.rect import Rect
from src.utils.types import SurfaceLike
from src.utils.window import create_surface, load_image, scale_surface


class Tile:
	def __init__(self, image: SurfaceLike) -> None:
		self.image = image
		self.width = image.get_width()
		self.height = image.get_height()


class TileObject:
	def __init__(self, tile: Tile, x: float, y: float, collidable: bool = False) -> None:
		self.tile = tile
		self.left = float(x)
		self.top = float(y)
		self.width = float(tile.width)
		self.height = float(tile.height)
		self.rect = Rect(self.left, self.top, self.width, self.height)
		self.collidable = collidable

	@property
	def x(self) -> float:
		return self.left

	@property
	def y(self) -> float:
		return self.top

	def draw(self, camera_x: float = 0.0, camera_y: float = 0.0) -> None:
		from src.utils.window import blit_surface

		blit_surface(self.tile.image, (int(self.left - camera_x), int(self.top - camera_y)))


class TileSet:
	def __init__(
		self,
		tileset_path: Path | str,
		tile_width: int = 0,
		tile_height: int = 0,
		gap: int = 0,
		tile_scale: float = 1.0,
		load_image_fn: Callable[[Path | str, bool], SurfaceLike] = load_image,
		create_surface_fn: Callable[[int, int, bool], SurfaceLike] = create_surface,
		scale_surface_fn: Callable[[SurfaceLike, int, int, bool], SurfaceLike] = scale_surface,
	) -> None:
		self.path = Path(tileset_path)
		self.tiles: list[Tile] = []
		self._load_image = load_image_fn
		self._create_surface = create_surface_fn
		self._scale_surface = scale_surface_fn

		full = self._load_image(self.path, True)
		full_width = full.get_width()
		full_height = full.get_height()

		if tile_width > 0 and tile_height > 0:
			self._slice_grid(full, full_width, full_height, tile_width, tile_height, gap, tile_scale)
		else:
			self._slice_by_alpha(full, full_width, full_height, tile_scale)

	def _slice_grid(
		self,
		full: SurfaceLike,
		full_width: int,
		full_height: int,
		tile_width: int,
		tile_height: int,
		gap: int,
		scale: float,
	) -> None:
		# Quando a folha já está organizada em grade, iteramos com passos fixos para evitar heurística.
		y = 0
		while y + tile_height <= full_height:
			x = 0
			while x + tile_width <= full_width:
				surface = self._create_surface(tile_width, tile_height, True)
				surface.blit(full, (0, 0), (x, y, tile_width, tile_height))
				self.tiles.append(Tile(self._scale_if_needed(surface, scale)))

				if tile_width == full_width:
					break

				x += tile_width + gap

			if tile_height == full_height:
				break

			y += tile_height + gap

	def _slice_by_alpha(self, full: SurfaceLike, full_width: int, full_height: int, scale: float) -> None:
		visited = [[False] * full_height for _ in range(full_width)]
		neighbors = ((1, 0), (-1, 0), (0, 1), (0, -1))

		def alpha_at(x: int, y: int) -> int:
			return full.get_at((x, y))[3]

		for x in range(full_width):
			for y in range(full_height):
				if visited[x][y]:
					continue

				if alpha_at(x, y) == 0:
					visited[x][y] = True
					continue

				stack: list[tuple[int, int]] = [(x, y)]
				visited[x][y] = True
				min_x = max_x = x
				min_y = max_y = y

				# A busca por componente conectado encontra cada sprite sem depender de grade fixa.
				while stack:
					source_x, source_y = stack.pop()
					if alpha_at(source_x, source_y) == 0:
						continue

					min_x = min(min_x, source_x)
					max_x = max(max_x, source_x)
					min_y = min(min_y, source_y)
					max_y = max(max_y, source_y)

					for offset_x, offset_y in neighbors:
						next_x = source_x + offset_x
						next_y = source_y + offset_y
						if not (0 <= next_x < full_width and 0 <= next_y < full_height):
							continue

						if visited[next_x][next_y]:
							continue

						visited[next_x][next_y] = True
						if alpha_at(next_x, next_y) != 0:
							stack.append((next_x, next_y))

				box_width = max_x - min_x + 1
				box_height = max_y - min_y + 1
				if box_width < 4 and box_height < 4:
					continue

				surface = self._create_surface(box_width, box_height, True)
				surface.blit(full, (0, 0), (min_x, min_y, box_width, box_height))
				self.tiles.append(Tile(self._scale_if_needed(surface, scale)))

	def _scale_if_needed(self, surface: SurfaceLike, scale: float) -> SurfaceLike:
		if scale == 1.0:
			return surface

		return self._scale_surface(
			surface,
			int(surface.get_width() * scale),
			int(surface.get_height() * scale),
			False,
		)

	def create_object(self, index: int, x: float, y: float, collidable: bool = False) -> TileObject:
		return TileObject(self.tiles[index], x, y, collidable=collidable)


__all__ = ["TileSet", "TileObject", "Tile"]
