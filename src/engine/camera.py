from external.pplay.camera import Camera as PPlayCamera


class Camera(PPlayCamera):
	def __init__(self, viewport_width: int, viewport_height: int) -> None:
		super().__init__(viewport_width, viewport_height)
		self.viewport_width = viewport_width
		self.viewport_height = viewport_height

	def follow(self, target_x: float, target_y: float) -> None:
		self.x = target_x - self.viewport_width * 0.5
		self.y = target_y - self.viewport_height * 0.5

	def world_to_screen(self, world_x: float, world_y: float) -> tuple[float, float]:
		return self.transform_x(world_x), self.transform_y(world_y)
