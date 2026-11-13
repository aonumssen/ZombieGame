"""Exercise campaign transitions through the desktop simulation's public loop."""

from pathlib import Path
import tempfile
import unittest

from simulation import Simulation
from state_storage import JsonFileStateStore, InMemoryStateStore


def rescue(simulation: Simulation, count: int) -> None:
    """Set up player contacts, then let the simulation resolve them."""
    for civilian in simulation.civilians[:count]:
        civilian.x = simulation.player.x
        civilian.y = simulation.player.y
    simulation.update(0.0)


class CampaignTests(unittest.TestCase):
    def test_all_ten_levels_and_final_victory(self) -> None:
        simulation = Simulation(seed=7)
        simulation.start()
        for level in range(1, 11):
            with self.subTest(level=level):
                self.assertEqual(simulation.level, level)
                self.assertEqual(simulation.state, "running")
                self.assertEqual(len(simulation.zombies), 3 + 2 * (level - 1))
                self.assertEqual(len(simulation.civilians), 14)
                self.assertEqual(simulation.rescued, 0)
                self.assertEqual(simulation.player.health, 100)

                simulation.update(1 / 30)
                simulation.player.health = 64
                rescue(simulation, 7)
                self.assertEqual(simulation.state, "running")
                rescue(simulation, 1)

                self.assertEqual(simulation.rescued, 8)
                self.assertEqual(simulation.state, "won" if level == 10 else "level_cleared")
                cleared = simulation.to_state()
                simulation.update(1 / 30, {"d"})
                self.assertEqual(simulation.to_state(), cleared)

                simulation.start()
        self.assertEqual(simulation.level, 1)
        self.assertEqual(simulation.elapsed, 0.0)
        self.assertEqual(simulation.state, "running")

    def test_later_levels_spawn_reinforcements_sooner(self) -> None:
        simulation = Simulation(seed=7)
        simulation.start()
        simulation.spawn_timer = 2.3
        simulation.update(0.0)
        self.assertEqual(len(simulation.zombies), 3)

        for _ in range(9):
            rescue(simulation, 8)
            simulation.start()
        simulation.spawn_timer = 2.3
        simulation.update(0.0)
        self.assertEqual(len(simulation.zombies), 22)

    def test_loss_when_rescue_goal_becomes_impossible(self) -> None:
        simulation = Simulation(seed=7)
        simulation.start()
        for civilian in simulation.civilians[:7]:
            civilian.x, civilian.y = simulation.zombies[0].x, simulation.zombies[0].y
            civilian.infection = 1.0
        simulation.update(0.0)
        self.assertEqual(simulation.state, "lost")
        self.assertEqual(len(simulation.civilians), 7)
        self.assertEqual(len(simulation.zombies), 10)

    def test_final_rescue_requires_survival(self) -> None:
        simulation = Simulation(seed=7)
        simulation.start()
        for _ in range(9):
            rescue(simulation, 8)
            simulation.start()
        simulation.player.health = 18
        zombie = simulation.zombies[0]
        zombie.x, zombie.y = simulation.player.x, simulation.player.y
        rescue(simulation, 8)
        self.assertEqual(simulation.level, 10)
        self.assertEqual(simulation.rescued, 8)
        self.assertEqual(simulation.state, "lost")

    def test_checkpoint_round_trip_on_later_level_and_between_levels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileStateStore(Path(directory) / "checkpoint.json")
            simulation = Simulation(seed=7, state_store=store)
            simulation.start()
            rescue(simulation, 8)
            simulation.start()
            simulation.update(1 / 30)
            rescue(simulation, 3)
            restored = Simulation(seed=23, state_store=store)

            for extra_rescues in (0, 5):
                rescue(simulation, extra_rescues)
                saved = simulation.save_checkpoint()
                self.assertTrue(restored.load_checkpoint())
                self.assertEqual(restored.to_state(), saved)
            simulation.start()
            restored.start()
            self.assertEqual(restored.to_state(), simulation.to_state())
            self.assertEqual(restored.level, 3)

    def test_legacy_victory_loads_as_level_one_clear(self) -> None:
        store = InMemoryStateStore()
        simulation = Simulation(seed=7, state_store=store)
        simulation.start()
        rescue(simulation, 8)
        legacy = simulation.to_state()
        legacy["schema_version"] = 1
        legacy["runtime"]["state"] = "won"
        del legacy["runtime"]["level"]
        del legacy["runtime"]["level_elapsed"]
        store.save(legacy)

        self.assertTrue(simulation.load_checkpoint())
        self.assertEqual(simulation.level, 1)
        self.assertEqual(simulation.state, "level_cleared")
        simulation.start()
        self.assertEqual(simulation.level, 2)


if __name__ == "__main__":
    unittest.main()
