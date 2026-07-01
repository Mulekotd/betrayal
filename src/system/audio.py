from external.pplay.sound import Music, Sound, SoundManager


def _is_web_runtime() -> bool:
	try:
		import platform

		return hasattr(platform, "window")
	except Exception:
		return False


def _web_audio_unlocked() -> bool:
	if not _is_web_runtime():
		return True

	try:
		import platform

		return bool(platform.window.MM.UME)
	except Exception:
		return False


class Audio:
	def __init__(self, volume: int = 50) -> None:
		self._volume = 50
		self._sounds: dict[str, Sound] = {}
		self._sound_volumes: dict[str, float] = {}
		self._pending_sounds: dict[str, tuple[str, float]] = {}
		self._pending_loops: set[str] = set()
		self._active_loops: set[str] = set()
		self._music: dict[str, Music] = {}
		self._pending_music: dict[str, str] = {}
		self._music_key: str | None = None
		self._audio_available = self._ensure_audio_backend()
		self.set_volume(volume)

	def _ensure_audio_backend(self) -> bool:
		if not _web_audio_unlocked():
			return False

		try:
			SoundManager.inicializar()
			return True
		except Exception:
			return False

	def _ensure_ready(self) -> bool:
		self._audio_available = self._ensure_audio_backend()
		return self._audio_available

	def _apply_volume(self) -> None:
		SoundManager.set_sfx_volume(self._volume)
		SoundManager.set_music_volume(self._volume)

		for sound in self._sounds.values():
			sound.set_volume(self._volume)

	def _load_sound_now(self, key: str) -> Sound | None:
		if key in self._sounds:
			return self._sounds[key]

		pending = self._pending_sounds.get(key)
		if pending is None:
			return None

		filepath, volume = pending
		sound = Sound(filepath)
		self._sound_volumes[key] = volume
		sound.set_volume(int(self._volume * volume))
		self._sounds[key] = sound
		return sound

	def _load_music_now(self, key: str) -> Music | None:
		if key in self._music:
			return self._music[key]

		filepath = self._pending_music.get(key)
		if filepath is None:
			return None

		music = Music(filepath)
		self._music[key] = music
		return music

	def pump(self) -> None:
		if not self._ensure_ready():
			return

		self._apply_volume()

		for key in tuple(self._pending_loops):
			if key in self._active_loops:
				continue

			sound = self._load_sound_now(key)
			if sound is not None:
				sound.play(-1)
				self._active_loops.add(key)

	def set_volume(self, value: int) -> None:
		self._volume = max(0, min(100, int(value)))
		if not self._ensure_ready():
			return

		self._apply_volume()

	def get_volume(self) -> int:
		return self._volume

	def load_sound(self, key: str, filepath: str, volume: float = 1.0) -> None:
		self._pending_sounds[key] = (filepath, max(0.0, min(1.0, volume)))

		if not self._ensure_ready():
			return

		self._load_sound_now(key)

	def play_sound(self, key: str, repeat: bool = False) -> None:
		if repeat:
			self._pending_loops.add(key)
			if key in self._active_loops:
				return

		if not self._ensure_ready():
			return

		sound = self._load_sound_now(key)
		if sound is None:
			return

		sound.play(-1 if repeat else 0)
		if repeat:
			self._active_loops.add(key)

	def stop_sound(self, key: str) -> None:
		self._pending_loops.discard(key)
		self._active_loops.discard(key)

		if not self._audio_available:
			return

		sound = self._sounds.get(key)
		if sound is None:
			return

		sound.stop()

	def stop_all_sounds(self) -> None:
		self._pending_loops.clear()
		self._active_loops.clear()

		if not self._audio_available:
			return

		for sound in self._sounds.values():
			sound.stop()

	def load_music(self, filepath: str, key: str = "music") -> None:
		self._pending_music[key] = filepath
		self._music_key = key

		if not self._ensure_ready():
			return

		self._load_music_now(key)

	def play_music(self, repeat: bool = True) -> None:
		if not self._ensure_ready():
			return

		if self._music_key is None:
			return

		music = self._load_music_now(self._music_key)
		if music is None:
			return

		music.play(loops=-1 if repeat else 0)
