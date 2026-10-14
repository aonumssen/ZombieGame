"""Tests showing that one simulation works with multiple state stores."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from simulation import Simulation
from state_storage import InMemoryStateStore, JsonFileStateStore, StateStore


class StateStorageTests(unittest.TestCase):
    def _assert_round_trip(self, store: StateStore) -> None:
        simulation = Simulation(seed=7, state_store=store)
        simulation.start()
        simulation.fire(100, 100)
        for _ in range(15):
            simulation.update(1 / 30, {"d"}, (100, 100))

        expected_state = simulation.to_state()
        expected_snapshot = simulation.snapshot()
        simulation.save_checkpoint()

        restored = Simulation(seed=999, state_store=store)
        self.assertTrue(restored.load_checkpoint())
        self.assertEqual(restored.snapshot(), expected_snapshot)
        self.assertEqual(restored.to_state(), expected_state)

    def test_in_memory_store_round_trip(self) -> None:
        self._assert_round_trip(InMemoryStateStore())

    def test_json_file_store_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "checkpoint.json"
            self._assert_round_trip(JsonFileStateStore(path))
            self.assertTrue(path.exists())

    def test_same_engine_can_use_periodic_json_checkpointing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "autosave.json"
            store = JsonFileStateStore(path)
            simulation = Simulation(seed=2, state_store=store, checkpoint_interval=0.25)
            simulation.start()
            for _ in range(10):
                simulation.update(1 / 30)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
