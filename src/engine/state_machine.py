from enum import Enum
from typing import Generic, Iterable, TypeVar


TState = TypeVar("TState", bound=Enum)


class StateMachine(Generic[TState]):
	def __init__(self, states: Iterable[TState], initial: TState) -> None:
		self._states = list(states)

		if not self._states:
			raise ValueError("StateMachine requires at least one state.")

		if initial not in self._states:
			raise ValueError("Initial state must be part of states list.")

		self._state = initial

	@property
	def state(self) -> TState:
		return self._state

	def set(self, state: TState) -> None:
		if state not in self._states:
			raise ValueError("State not allowed for this state machine.")

		self._state = state
