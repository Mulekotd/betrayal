import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.utils.box import Rect

from src.engine.tileset import TileObject, TileSet


@dataclass(frozen=True)
class WorldConfig:
	width_scale: float = 3.2
	height_scale: float = 3.0
	min_extra_width: int = 1800
	min_extra_height: int = 1200
	margin: int = 96
	background_color: tuple[int, int, int] = (71, 155, 75)
	tree_tile_scale: float = 2.0
	placement_inset: int = 80
	safe_radius_padding: float = 170.0
	spacing: float = 292.0
	min_gap: int = 56
	min_object_count: int = 30
	area_per_object: int = 115000
	extra_ratio: float = 0.15


class World:
	def __init__(
		self,
		images_dir: str | Path,
		viewport_width: int,
		viewport_height: int,
		config: WorldConfig | None = None,
	) -> None:
		self.images_dir = Path(images_dir)
		self.config = config or WorldConfig()

		self.width = max(int(viewport_width * self.config.width_scale), viewport_width + self.config.min_extra_width)
		total_height = max(int(viewport_height * self.config.height_scale), viewport_height + self.config.min_extra_height)
		self.height = total_height
		self.background_color = self.config.background_color

		self.bounds = Rect(
			self.config.margin,
			self.config.margin,
			max(1, self.width - self.config.margin * 2),
			max(1, self.height - self.config.margin * 2),
		)

		self.tree_tileset: TileSet | None = None
		self.objects: list[TileObject] = []
		self.static_colliders: list[Rect] = []
		self._rng = np.random.default_rng()

	def rebuild(self, player_center: tuple[float, float], player_radius: float) -> None:
		trees_path = self.images_dir / "trees.png"
		self.objects = []
		self.static_colliders = []

		if not trees_path.exists():
			self.tree_tileset = None
			return

		self.tree_tileset = TileSet(
			tileset_path=trees_path,
			tile_width=0,
			tile_height=0,
			gap=0,
			tile_scale=self.config.tree_tile_scale,
		)
		self.objects = self._generate_tree_layout(player_center=player_center, player_radius=player_radius)
		self.static_colliders = [obj.rect for obj in self.objects if obj.collidable]

	def draw(self, camera_x: float = 0.0, camera_y: float = 0.0) -> None:
		for obj in sorted(self.objects, key=lambda item: item.y + item.height):
			obj.draw(camera_x=camera_x, camera_y=camera_y)

	def _generate_tree_layout(self, player_center: tuple[float, float], player_radius: float) -> list[TileObject]:
		if self.tree_tileset is None or not self.tree_tileset.tiles:
			return []

		placement_bounds = self.bounds.inflate(-self.config.placement_inset, -self.config.placement_inset)
		if placement_bounds.width <= 0 or placement_bounds.height <= 0:
			placement_bounds = self.bounds.copy()

		objects: list[TileObject] = []
		safe_radius = player_radius + self.config.safe_radius_padding
		spacing = self.config.spacing
		min_gap = self.config.min_gap

		target_count = max(
			self.config.min_object_count,
			int((placement_bounds.width * placement_bounds.height) / self.config.area_per_object),
		)

		bin_size = max(96, int(spacing * 0.76))

		x_coords = np.arange(
			placement_bounds.left + spacing * 0.5,
			placement_bounds.right,
			spacing,
			dtype=np.float32,
		)
		y_coords = np.arange(
			placement_bounds.top + spacing * 0.5,
			placement_bounds.bottom,
			spacing,
			dtype=np.float32,
		)

		if x_coords.size == 0:
			x_coords = np.array([placement_bounds.centerx], dtype=np.float32)
		if y_coords.size == 0:
			y_coords = np.array([placement_bounds.centery], dtype=np.float32)

		mesh_x, mesh_y = np.meshgrid(x_coords, y_coords)
		candidate_points = np.column_stack((mesh_x.ravel(), mesh_y.ravel())).astype(np.float32)

		if candidate_points.size == 0:
			return []

		jitter = self._rng.uniform(-spacing * 0.32, spacing * 0.32, size=candidate_points.shape).astype(np.float32)
		candidate_points += jitter

		extra_count = max(12, int(candidate_points.shape[0] * self.config.extra_ratio))
		extra_points = np.column_stack(
			(
				self._rng.uniform(placement_bounds.left, placement_bounds.right, size=extra_count),
				self._rng.uniform(placement_bounds.top, placement_bounds.bottom, size=extra_count),
			)
		).astype(np.float32)

		candidate_points = np.vstack((candidate_points, extra_points))
		self._rng.shuffle(candidate_points)

		occupied_bins: dict[tuple[int, int], list[Rect]] = {}

		for point_x, point_y in candidate_points:
			if len(objects) >= target_count:
				break

			tile_index = int(self._rng.integers(0, len(self.tree_tileset.tiles)))
			tile = self.tree_tileset.tiles[tile_index]

			x = float(point_x - tile.width * 0.5)
			y = float(point_y - tile.height * 0.5)
			x = max(float(placement_bounds.left), min(x, float(placement_bounds.right - tile.width)))
			y = max(float(placement_bounds.top), min(y, float(placement_bounds.bottom - tile.height)))

			obj = self.tree_tileset.create_object(tile_index, x, y, collidable=True)

			if self._circle_intersects_rect(player_center[0], player_center[1], safe_radius, obj.rect):
				continue

			if not self._is_tree_position_free(obj.rect, occupied_bins, bin_size=bin_size, min_gap=min_gap):
				continue

			objects.append(obj)
			self._register_tree_rect(obj.rect, occupied_bins, bin_size=bin_size)

		return objects

	def _is_tree_position_free(
		self,
		candidate: object,
		occupied_bins: dict[tuple[int, int], list[object]],
		bin_size: int,
		min_gap: int,
	) -> bool:
		probe = candidate.inflate(min_gap, min_gap)
		left = int(math.floor(probe.left / bin_size))
		right = int(math.floor(probe.right / bin_size))
		top = int(math.floor(probe.top / bin_size))
		bottom = int(math.floor(probe.bottom / bin_size))

		for bx in range(left - 1, right + 2):
			for by in range(top - 1, bottom + 2):
				for existing in occupied_bins.get((bx, by), []):
					if probe.colliderect(existing.inflate(min_gap, min_gap)):
						return False

		return True

	def _register_tree_rect(
		self,
		rect: object,
		occupied_bins: dict[tuple[int, int], list[object]],
		bin_size: int,
	) -> None:
		left = int(math.floor(rect.left / bin_size))
		right = int(math.floor(rect.right / bin_size))
		top = int(math.floor(rect.top / bin_size))
		bottom = int(math.floor(rect.bottom / bin_size))

		for bx in range(left, right + 1):
			for by in range(top, bottom + 1):
				occupied_bins.setdefault((bx, by), []).append(rect)

	def _circle_intersects_rect(self, center_x: float, center_y: float, radius: float, rect: object) -> bool:
		closest_x = max(rect.left, min(center_x, rect.right))
		closest_y = max(rect.top, min(center_y, rect.bottom))

		dx = center_x - closest_x
		dy = center_y - closest_y

		return (dx * dx + dy * dy) < (radius * radius)
