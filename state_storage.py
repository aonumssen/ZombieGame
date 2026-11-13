"""Save and load campaign checkpoints in memory or in a JSON file."""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Optional


StateData = dict[str, Any]


class StateStorageError(RuntimeError):
    """Raised when a storage adapter cannot read or write a state."""


class StateStore(ABC):
    """Small persistence boundary used by the simulation layer."""

    @abstractmethod
    def save(self, state: Mapping[str, Any]) -> None:
        """Persist one complete simulation state."""

    @abstractmethod
    def load(self) -> Optional[StateData]:
        """Return the last saved state, or ``None`` if no state exists."""

    @abstractmethod
    def clear(self) -> None:
        """Remove the saved state, if one exists."""


class NullStateStore(StateStore):
    """No-op adapter used when a caller does not need persistence."""

    def save(self, state: Mapping[str, Any]) -> None:
        del state

    def load(self) -> Optional[StateData]:
        return None

    def clear(self) -> None:
        return None


class InMemoryStateStore(StateStore):
    """Keep a checkpoint in memory and copy it on save and load."""

    def __init__(self) -> None:
        self._state: Optional[StateData] = None

    def save(self, state: Mapping[str, Any]) -> None:
        self._state = deepcopy(dict(state))

    def load(self) -> Optional[StateData]:
        return deepcopy(self._state) if self._state is not None else None

    def clear(self) -> None:
        self._state = None


class JsonFileStateStore(StateStore):
    """Durable storage adapter that writes one state as readable JSON."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save(self, state: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(dict(state), temporary_file, indent=2, sort_keys=True)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self.path)
            temporary_path = None
        except (OSError, TypeError, ValueError) as exc:
            raise StateStorageError(f"Could not save simulation state to {self.path}") from exc
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    def load(self) -> Optional[StateData]:
        if not self.path.exists():
            return None
        try:
            with self.path.open("r", encoding="utf-8") as state_file:
                loaded = json.load(state_file)
        except (OSError, json.JSONDecodeError) as exc:
            raise StateStorageError(f"Could not load simulation state from {self.path}") from exc
        if not isinstance(loaded, dict):
            raise StateStorageError(f"Simulation state in {self.path} must be a JSON object")
        return loaded

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            raise StateStorageError(f"Could not clear simulation state at {self.path}") from exc


__all__ = [
    "InMemoryStateStore",
    "JsonFileStateStore",
    "NullStateStore",
    "StateData",
    "StateStorageError",
    "StateStore",
]
