from src.engine.game import Game


def main() -> None:
	game = Game(width=1280, height=720, title="Betrayal", fps=60)
	game.initialize()
	game.loop()


if __name__ == "__main__":
	main()
