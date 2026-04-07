from external.pplay.sound import Sound


class Audio:
	def __init__(self, volume: int = 50) -> None:
		self._volume = 50
		self._sounds: dict[str, Sound] = {}
		self._music_key: str | None = None
		self.set_volume(volume)

	def set_volume(self, value: int) -> None:
		self._volume = max(0, min(100, int(value)))
		
		for sound in self._sounds.values():
			sound.set_volume(self._volume)

	def get_volume(self) -> int:
		return self._volume

	def increase_volume(self, value: int = 5) -> None:
		self.set_volume(self._volume + value)

	def decrease_volume(self, value: int = 5) -> None:
		self.set_volume(self._volume - value)

	def load_sound(self, key: str, filepath: str) -> None:
		sound = Sound(filepath)
		sound.set_volume(self._volume)
		
		self._sounds[key] = sound

	def play_sound(self, key: str, repeat: bool = False) -> None:
		sound = self._sounds.get(key)
		
		if sound is None:
			return
		
		sound.set_repeat(repeat)
		sound.play()

	def stop_sound(self, key: str) -> None:
		sound = self._sounds.get(key)
		
		if sound is not None:
			sound.stop()

	def load_music(self, filepath: str, key: str = "music") -> None:
		self.load_sound(key, filepath)
		self._music_key = key

	def play_music(self, repeat: bool = True) -> None:
		if self._music_key is None:
			return
		
		self.play_sound(self._music_key, repeat=repeat)

	def stop_music(self) -> None:
		if self._music_key is None:
			return
		
		self.stop_sound(self._music_key)

	def pause_music(self) -> None:
		if self._music_key is None:
			return
		
		sound = self._sounds.get(self._music_key)
		
		if sound is not None:
			sound.pause()

	def unpause_music(self) -> None:
		if self._music_key is None:
			return
		
		sound = self._sounds.get(self._music_key)
		
		if sound is not None:
			sound.unpause()

	def is_playing(self, key: str | None = None) -> bool:
		if key is None:
			return any(sound.is_playing() for sound in self._sounds.values())
		
		sound = self._sounds.get(key)
		
		return sound.is_playing() if sound is not None else False
