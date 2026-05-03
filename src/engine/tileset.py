from pathlib import Path
from typing import Any, List, Tuple

import pygame as _pygame

from src.utils.box import Rect
from src.utils.window import load_image, scale_surface


class Tile:
    def __init__(self, image: Any) -> None:
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

        draw_x = int(self.left - camera_x)
        draw_y = int(self.top - camera_y)
        blit_surface(self.tile.image, (draw_x, draw_y))


class TileSet:
    def __init__(
        self,
        tileset_path: Path | str,
        tile_width: int = 0,
        tile_height: int = 0,
        gap: int = 0,
        tile_scale: float = 1.0,
    ) -> None:
        path = Path(tileset_path)
        self.path = path
        self.tiles: List[Tile] = []

        full = load_image(str(path))
        fw, fh = full.get_width(), full.get_height()

        # If tile size provided, slice as grid; otherwise auto-detect by alpha connected components
        if tile_width and tile_height and tile_width > 0 and tile_height > 0:
            self._slice_grid(full, fw, fh, tile_width, tile_height, gap, tile_scale)
        else:
            self._slice_by_alpha(full, fw, fh, gap, tile_scale)

    def _slice_grid(self, full: Any, fw: int, fh: int, tw: int, th: int, gap: int, scale: float) -> None:
        y = 0

        while y + th <= fh:
            x = 0
            while x + tw <= fw:
                surf = _pygame.Surface((tw, th), flags=_pygame.SRCALPHA)
                surf.blit(full, (0, 0), (x, y, tw, th))
                if scale != 1.0:
                    surf = scale_surface(surf, int(tw * scale), int(th * scale))
                self.tiles.append(Tile(surf))
                if tw == fw:
                    break
                x += tw + gap
            if th == fh:
                break

            y += th + gap

    def _slice_by_alpha(self, full: Any, fw: int, fh: int, gap: int, scale: float) -> None:
        visited = [[False] * fh for _ in range(fw)]

        def get_alpha(x: int, y: int) -> int:
            return full.get_at((x, y))[3]

        neighbors = ((1, 0), (-1, 0), (0, 1), (0, -1))

        for x in range(fw):
            for y in range(fh):
                if visited[x][y]:
                    continue
                if get_alpha(x, y) == 0:
                    visited[x][y] = True
                    continue

                stack: List[Tuple[int, int]] = [(x, y)]
                visited[x][y] = True
                minx, maxx = x, x
                miny, maxy = y, y

                while stack:
                    sx, sy = stack.pop()
                    a = get_alpha(sx, sy)
                    if a == 0:
                        continue
                    if sx < minx:
                        minx = sx
                    if sx > maxx:
                        maxx = sx
                    if sy < miny:
                        miny = sy
                    if sy > maxy:
                        maxy = sy

                    for dx, dy in neighbors:
                        nx, ny = sx + dx, sy + dy
                        if 0 <= nx < fw and 0 <= ny < fh and not visited[nx][ny]:
                            visited[nx][ny] = True
                            if get_alpha(nx, ny) != 0:
                                stack.append((nx, ny))

                bw = maxx - minx + 1
                bh = maxy - miny + 1

                if bw < 4 and bh < 4:
                    continue

                # extract surface
                surf = _pygame.Surface((bw, bh), flags=_pygame.SRCALPHA)
                surf.blit(full, (0, 0), (minx, miny, bw, bh))

                if scale != 1.0:
                    surf = scale_surface(surf, int(bw * scale), int(bh * scale))

                self.tiles.append(Tile(surf))

    def create_object(self, index: int, x: float, y: float, collidable: bool = False) -> TileObject:
        tile = self.tiles[index]
        return TileObject(tile, x, y, collidable=collidable)


__all__ = ["TileSet", "TileObject", "Tile"]
