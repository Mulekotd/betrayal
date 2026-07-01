import math
import random
from dataclasses import dataclass
from pathlib import Path

from src.utils.rect import Rect
from src.utils.types import SurfaceLike
from src.utils.window import get_screen, load_image, create_surface, scale_surface

from src.engine.tileset import Tile, TileObject, TileSet


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
	spacing: float = 332.0
	min_gap: int = 56
	min_object_count: int = 10
	area_per_object: int = 260000
	extra_ratio: float = 0.04
	building_tile_scale: float = 5.0
	building_base_height: int = 68
	village_house_count: int = 8
	village_columns: int = 2
	village_gap_x: int = 170
	village_gap_y: int = 120
	village_safe_radius_padding: float = 120.0
	village_tree_buffer: int = 180
	village_attempts: int = 28
	building_crop_padding: int = 24
	boss_arena_clear_radius: float = 360.0


class World:
	def __init__(
		self,
		images_dir: str | Path,
		viewport_width: int,
		viewport_height: int,
		config: WorldConfig | None = None
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
			max(1, self.height - self.config.margin * 2)
		)

		self.tree_tileset: TileSet | None = None
		self.building_tiles: list[Tile] = []
		self.objects: list[TileObject] = []
		self._sorted_objects: list[TileObject] = []
		self.static_colliders: list[Rect] = []
		self._rng = random.Random()

	def rebuild(self, player_center: tuple[float, float], player_radius: float) -> None:
		trees_path = self.images_dir / "trees.png"
		buildings_path = self.images_dir / "buildings.png"
		self.objects = []
		self.static_colliders = []
		self.tree_tileset = None
		self.building_tiles = []

		blocked_areas: list[Rect] = [self.boss_arena_rect()]
		if buildings_path.exists():
			self.building_tiles = self._load_building_tiles(buildings_path)
			village_objects, blocked_areas = self._generate_village_layout(
				player_center=player_center,
				player_radius=player_radius,
				blocked_areas=blocked_areas
			)
			self.objects.extend(village_objects)
			blocked_areas = [self.boss_arena_rect(), *blocked_areas]

		if trees_path.exists():
			self.tree_tileset = TileSet(
				tileset_path=trees_path,
				tile_width=0,
				tile_height=0,
				gap=0,
				tile_scale=self.config.tree_tile_scale
			)
			self.objects.extend(
				self._generate_tree_layout(
					player_center=player_center,
					player_radius=player_radius,
					blocked_areas=blocked_areas
				)
			)

		self._sorted_objects = sorted(self.objects, key=lambda item: item.y + item.height)
		self.static_colliders = [obj.rect for obj in self.objects if obj.collidable]

	def boss_arena_rect(self) -> Rect:
		radius = max(64.0, float(self.config.boss_arena_clear_radius))
		return Rect(
			float(self.bounds.centerx - radius),
			float(self.bounds.centery - radius),
			radius * 2.0,
			radius * 2.0
		)

	def clear_area(self, area: Rect) -> None:
		self.objects = [
			obj
			for obj in self.objects
			if not obj.collidable or not obj.rect.colliderect(area)
		]
		self._sorted_objects = sorted(self.objects, key=lambda item: item.y + item.height)
		self.static_colliders = [obj.rect for obj in self.objects if obj.collidable]

	def draw(self, camera_x: float = 0.0, camera_y: float = 0.0) -> None:
		if not self._sorted_objects:
			return

		screen = get_screen()
		left = camera_x - 96.0
		top = camera_y - 96.0
		right = camera_x + screen.get_width() + 96.0
		bottom = camera_y + screen.get_height() + 96.0

		for obj in self._sorted_objects:
			if obj.left + obj.width < left or obj.left > right or obj.top + obj.height < top or obj.top > bottom:
				continue

			obj.draw(camera_x=camera_x, camera_y=camera_y)

	def _generate_tree_layout(
		self,
		player_center: tuple[float, float],
		player_radius: float,
		blocked_areas: list[Rect] | None = None
	) -> list[TileObject]:
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
			int((placement_bounds.width * placement_bounds.height) / self.config.area_per_object)
		)

		bin_size = max(96, int(spacing * 0.76))

		x_coords = self._float_range(
			placement_bounds.left + spacing * 0.5,
			placement_bounds.right,
			spacing,
		)
		y_coords = self._float_range(
			placement_bounds.top + spacing * 0.5,
			placement_bounds.bottom,
			spacing,
		)

		if not x_coords:
			x_coords = [float(placement_bounds.centerx)]

		if not y_coords:
			y_coords = [float(placement_bounds.centery)]

		candidate_points = [(x, y) for y in y_coords for x in x_coords]
		if not candidate_points:
			return []

		jitter_amount = spacing * 0.32
		candidate_points = [
			(
				x + self._rng.uniform(-jitter_amount, jitter_amount),
				y + self._rng.uniform(-jitter_amount, jitter_amount),
			)
			for x, y in candidate_points
		]

		extra_count = max(12, int(len(candidate_points) * self.config.extra_ratio))
		candidate_points.extend(
			(
				self._rng.uniform(placement_bounds.left, placement_bounds.right),
				self._rng.uniform(placement_bounds.top, placement_bounds.bottom),
			)
			for _ in range(extra_count)
		)
		self._rng.shuffle(candidate_points)

		occupied_bins: dict[tuple[int, int], list[Rect]] = {}
		for blocked_area in blocked_areas or []:
			self._register_tree_rect(blocked_area, occupied_bins, bin_size=bin_size)

		for point_x, point_y in candidate_points:
			if len(objects) >= target_count:
				break

			tile_index = self._rng.randrange(len(self.tree_tileset.tiles))
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

	def _float_range(self, start: float, stop: float, step: float) -> list[float]:
		values: list[float] = []
		current = float(start)
		while current < stop:
			values.append(current)
			current += step

		return values

	def _generate_village_layout(
		self,
		player_center: tuple[float, float],
		player_radius: float,
		blocked_areas: list[Rect] | None = None
	) -> tuple[list[TileObject], list[Rect]]:
		if not self.building_tiles:
			return ([], [])

		house_count = max(self.config.village_house_count, len(self.building_tiles))
		tile_indices = [index % len(self.building_tiles) for index in range(house_count)]
		for start in range(0, house_count, len(self.building_tiles)):
			chunk = tile_indices[start:start + len(self.building_tiles)]
			self._rng.shuffle(chunk)
			tile_indices[start:start + len(chunk)] = chunk

		cols = max(1, self.config.village_columns)
		rows = int(math.ceil(house_count / cols))
		gap_x = float(self.config.village_gap_x)
		gap_y = float(self.config.village_gap_y)

		col_widths = [0.0] * cols
		row_heights = [0.0] * rows
		for index, tile_index in enumerate(tile_indices):
			tile = self.building_tiles[tile_index]
			row = index // cols
			col = index % cols
			col_widths[col] = max(col_widths[col], float(tile.width))
			row_heights[row] = max(row_heights[row], float(tile.height))

		total_width = sum(col_widths) + gap_x * max(0, cols - 1)
		total_height = sum(row_heights) + gap_y * max(0, rows - 1)
		col_offsets = self._stack_offsets(col_widths, gap_x)
		row_offsets = self._stack_offsets(row_heights, gap_y)
		safe_radius = player_radius + self.config.village_safe_radius_padding

		for bounds in (self._placement_bounds(), self.bounds.copy()):
			min_x = float(bounds.left)
			max_x = float(bounds.right - total_width)
			min_y = float(bounds.top)
			max_y = float(bounds.bottom - total_height)

			if max_x < min_x or max_y < min_y:
				continue

			for _ in range(self.config.village_attempts):
				anchor_x = float(self._rng.uniform(min_x, max_x)) if max_x > min_x else min_x
				anchor_y = float(self._rng.uniform(min_y, max_y)) if max_y > min_y else min_y
				objects = self._build_village_objects(
					tile_indices=tile_indices,
					anchor_x=anchor_x,
					anchor_y=anchor_y,
					cols=cols,
					col_widths=col_widths,
					row_heights=row_heights,
					col_offsets=col_offsets,
					row_offsets=row_offsets
				)
				village_bounds = self._bounds_for_objects(objects)
				if village_bounds is None:
					continue

				reserved_area = village_bounds.inflate(
					self.config.village_tree_buffer * 2,
					self.config.village_tree_buffer * 2
				)
				if self._circle_intersects_rect(player_center[0], player_center[1], safe_radius, reserved_area):
					continue

				if self._rect_intersects_any(reserved_area, blocked_areas):
					continue

				return (objects, [reserved_area])

		fallback_bounds = self._placement_bounds()
		fallback_positions = [
			(float(fallback_bounds.left), float(fallback_bounds.top)),
			(float(fallback_bounds.right - total_width), float(fallback_bounds.top)),
			(float(fallback_bounds.left), float(fallback_bounds.bottom - total_height)),
			(float(fallback_bounds.right - total_width), float(fallback_bounds.bottom - total_height)),
		]

		for fallback_x, fallback_y in fallback_positions:
			objects = self._build_village_objects(
				tile_indices=tile_indices,
				anchor_x=fallback_x,
				anchor_y=fallback_y,
				cols=cols,
				col_widths=col_widths,
				row_heights=row_heights,
				col_offsets=col_offsets,
				row_offsets=row_offsets
			)
			village_bounds = self._bounds_for_objects(objects)
			if village_bounds is None:
				continue

			reserved_area = village_bounds.inflate(
				self.config.village_tree_buffer * 2,
				self.config.village_tree_buffer * 2
			)
			if self._circle_intersects_rect(player_center[0], player_center[1], safe_radius, reserved_area):
				continue

			if self._rect_intersects_any(reserved_area, blocked_areas):
				continue

			return (objects, [reserved_area])

		return ([], [])

	def _build_village_objects(
		self,
		tile_indices: list[int],
		anchor_x: float,
		anchor_y: float,
		cols: int,
		col_widths: list[float],
		row_heights: list[float],
		col_offsets: list[float],
		row_offsets: list[float]
	) -> list[TileObject]:
		objects: list[TileObject] = []

		if not self.building_tiles:
			return objects

		for index, tile_index in enumerate(tile_indices):
			tile = self.building_tiles[tile_index]
			row = index // cols
			col = index % cols

			x = anchor_x + col_offsets[col] + (col_widths[col] - tile.width) * 0.5
			y = anchor_y + row_offsets[row] + (row_heights[row] - tile.height)

			x = max(float(self.bounds.left), min(x, float(self.bounds.right - tile.width)))
			y = max(float(self.bounds.top), min(y, float(self.bounds.bottom - tile.height)))

			objects.append(self._create_building_object(tile, x, y))

		return objects

	def _load_building_tiles(self, buildings_path: Path) -> list[Tile]:
		sheet = load_image(str(buildings_path), alpha=True)
		tiles: list[Tile] = []
		for crop_rect in self._building_crop_rects(sheet):
			cropped = create_surface(crop_rect.width, crop_rect.height, alpha=True)
			cropped.blit(
				sheet,
				(0, 0),
				(crop_rect.left, crop_rect.top, crop_rect.width, crop_rect.height)
			)

			normalized_height = max(1, int(self.config.building_base_height))
			normalized_width = max(
				1,
				int(round(cropped.get_width() * (normalized_height / cropped.get_height())))
			)
			normalized = scale_surface(cropped, normalized_width, normalized_height, smooth=False)

			final_width = max(1, int(round(normalized_width * self.config.building_tile_scale)))
			final_height = max(1, int(round(normalized_height * self.config.building_tile_scale)))
			final_surface = scale_surface(normalized, final_width, final_height, smooth=False)
			tiles.append(Tile(final_surface))

		return tiles

	def _building_crop_rects(self, sheet: SurfaceLike) -> list[Rect]:
		sheet_width = sheet.get_width()
		sheet_height = sheet.get_height()
		padding = int(self.config.building_crop_padding)
		row_ranges = self._alpha_ranges(
			[self._row_has_alpha(sheet, y) for y in range(sheet_height)],
			gap_tolerance=6,
			min_span=48
		)
		crop_rects: list[Rect] = []

		for row_start, row_end in row_ranges:
			col_ranges = self._alpha_ranges(
				[self._column_has_alpha(sheet, x, row_start, row_end) for x in range(sheet_width)],
				gap_tolerance=6,
				min_span=48
			)

			for col_start, col_end in col_ranges:
				left = max(0, col_start - padding)
				top = max(0, row_start - padding)
				right = min(sheet_width, col_end + padding)
				bottom = min(sheet_height, row_end + padding)
				crop_rects.append(Rect(left, top, max(1, right - left), max(1, bottom - top)))

		if len(crop_rects) >= 4:
			return crop_rects[:4]

		fallback_rects = [
			Rect(221, 296, 683, 728),
			Rect(1101, 161, 598, 863),
			Rect(296, 976, 528, 1027),
			Rect(1136, 976, 608, 997),
		]
		crop_rects = []
		for rect in fallback_rects:
			left = max(0, int(rect.left))
			top = max(0, int(rect.top))
			right = min(sheet_width, int(rect.right))
			bottom = min(sheet_height, int(rect.bottom))
			crop_rects.append(Rect(left, top, max(1, right - left), max(1, bottom - top)))

		return crop_rects

	def _row_has_alpha(self, surface: SurfaceLike, y: int) -> bool:
		width = surface.get_width()
		for x in range(width):
			if surface.get_at((x, y))[3] > 0:
				return True

		return False

	def _column_has_alpha(self, surface: SurfaceLike, x: int, top: int, bottom: int) -> bool:
		for y in range(top, bottom):
			if surface.get_at((x, y))[3] > 0:
				return True

		return False

	def _alpha_ranges(self, mask: list[bool], gap_tolerance: int, min_span: int) -> list[tuple[int, int]]:
		ranges: list[tuple[int, int]] = []
		start: int | None = None
		gap_start: int | None = None

		for index, filled in enumerate(mask):
			if filled:
				if start is None:
					start = index
				elif gap_start is not None and (index - gap_start) > gap_tolerance:
					if gap_start - start >= min_span:
						ranges.append((start, gap_start))
					start = index
				gap_start = None
				continue

			if start is not None and gap_start is None:
				gap_start = index

		if start is not None:
			end = gap_start if gap_start is not None else len(mask)
			if end - start >= min_span:
				ranges.append((start, end))

		return ranges

	def _create_building_object(self, tile: Tile, x: float, y: float) -> TileObject:
		obj = TileObject(tile, x, y, collidable=True)
		inset_x = obj.width * 0.04
		inset_y = obj.height * 0.03
		collider_x = obj.left + inset_x
		collider_y = obj.top + inset_y
		collider_width = max(24.0, obj.width - inset_x * 2.0)
		collider_height = max(24.0, obj.height - inset_y * 2.0)
		obj.rect = Rect(collider_x, collider_y, collider_width, collider_height)

		return obj

	def _stack_offsets(self, sizes: list[float], gap: float) -> list[float]:
		offsets: list[float] = []
		cursor = 0.0

		for size in sizes:
			offsets.append(cursor)
			cursor += size + gap

		return offsets

	def _placement_bounds(self) -> Rect:
		placement_bounds = self.bounds.inflate(-self.config.placement_inset, -self.config.placement_inset)
		if placement_bounds.width <= 0 or placement_bounds.height <= 0:
			return self.bounds.copy()

		return placement_bounds

	def _bounds_for_objects(self, objects: list[TileObject]) -> Rect | None:
		if not objects:
			return None

		left = min(obj.left for obj in objects)
		top = min(obj.top for obj in objects)
		right = max(obj.left + obj.width for obj in objects)
		bottom = max(obj.top + obj.height for obj in objects)

		return Rect(left, top, right - left, bottom - top)

	def _is_tree_position_free(
		self,
		candidate: object,
		occupied_bins: dict[tuple[int, int], list[object]],
		bin_size: int,
		min_gap: int
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
		bin_size: int
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

	def _rect_intersects_any(self, rect: Rect, areas: list[Rect] | None) -> bool:
		return any(rect.colliderect(area) for area in areas or [])
