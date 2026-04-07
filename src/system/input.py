from external.pplay.keyboard import Keyboard
from external.pplay.mouse import Mouse


class Input:
	def __init__(self) -> None:
		self.keyboard = Keyboard()
		self.mouse = Mouse()
