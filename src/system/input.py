from external.pplay.keyboard import Keyboard
from external.pplay.mouse import Mouse

from src.utils.types import KeyboardLike, MouseLike


class Input:
	def __init__(self) -> None:
		self.keyboard: KeyboardLike = Keyboard()
		self.mouse: MouseLike = Mouse()
