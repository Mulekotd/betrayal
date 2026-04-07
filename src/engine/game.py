from external.pplay.window import Window

from src.system.audio import Audio
from src.system.input import Input


class Game:
	def __init__(
		self,
		width: int,
		height: int,
		title: str,
		fps: int,
		background_color: tuple[int, int, int] = (15, 20, 30),
	) -> None:
		self.width = width
		self.height = height
		self.title = title
		self.fps = fps
		self.background_color = background_color

		self.window: Window | None = None

		self.input: Input | None = None
		self.audio = Audio()
		self.running = False
		self.current_scene = None

	def initialize(self) -> None:
		self.window = Window(self.width, self.height)
		self.window.set_title(self.title)
		self.window.set_background_color(list(self.background_color))

		self.input = Input()
		# Use the Keyboard/Mouse objects created by Window.
		self.input.keyboard = Window.get_keyboard()
		self.input.mouse = Window.get_mouse()

	def set_scene(self, scene: object) -> None:
		self.current_scene = scene

	def stop(self) -> None:
		self.running = False

	def handle_events(self) -> None:
		pass

	def update(self, dt: float) -> None:
		pass

	def render(self) -> None:
		if self.window is None:
			return

		self.window.set_background_color(list(self.background_color))
		self.window.update()

	def loop(self) -> None:
		if self.window is None:
			self.initialize()

		self.running = True
		
		while self.running:
			if self.window is None:
				break
			
			dt = self.window.delta_time()
			
			self.handle_events()
			self.update(dt)
			self.render()
			
			if self.fps > 0:
				self.window.delay(int(1000 / self.fps))
