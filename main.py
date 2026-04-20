from src.engine.game import Game
from src.scenes.menu_scene import MenuScene


def main() -> None:
	game = Game(width=1280, height=720, title="Betrayal", fps=60)
	game.initialize()
	if game.services is None:
		raise RuntimeError("Game services not initialized.")
	game.set_scene(
		MenuScene(
			game=game,
			services=game.services,
			world_width=game.width,
			world_height=game.height,
		)
	)
	game.loop()


if __name__ == "__main__":
	main()
