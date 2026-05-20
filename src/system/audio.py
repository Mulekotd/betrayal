from external.pplay.sound import Music, Sound, SoundManager


class Audio:
	def __init__(self, volume: int = 50) -> None:
		self._volume = 50
		self._sounds: dict[str, Sound] = {}
		self._music: dict[str, Music] = {}
		self._music_key: str | None = None
		self._audio_available = self._ensure_audio_backend()
		self.set_volume(volume)

	def _ensure_audio_backend(self) -> bool:
		try:
			SoundManager.inicializar()
			return True
		except Exception:
			return False

	def set_volume(self, value: int) -> None:
		self._volume = max(0, min(100, int(value)))
		self._audio_available = self._ensure_audio_backend()

		if not self._audio_available:
			return

		SoundManager.set_sfx_volume(self._volume)
		SoundManager.set_music_volume(self._volume)

		for sound in self._sounds.values():
			sound.set_volume(self._volume)

	def get_volume(self) -> int:
		return self._volume

	def load_sound(self, key: str, filepath: str) -> None:
		if not self._ensure_audio_backend():
			self._audio_available = False
			return

		sound = Sound(filepath)
		sound.set_volume(self._volume)

		self._sounds[key] = sound

	def play_sound(self, key: str, repeat: bool = False) -> None:
		if not self._audio_available:
			return

		sound = self._sounds.get(key)
		if sound is None:
			return

		sound.play(-1 if repeat else 0)

	def load_music(self, filepath: str, key: str = "music") -> None:
		if not self._ensure_audio_backend():
			self._audio_available = False
			return

		self._music[key] = Music(filepath)
		self._music_key = key

	def play_music(self, repeat: bool = True) -> None:
		if not self._audio_available:
			return

		if self._music_key is None:
			return

		music = self._music.get(self._music_key)
		if music is None:
			return

		music.play(loops=-1 if repeat else 0)
