"""Tests for the scalable database-backed Stage 2 design."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from stage2_database import SQLiteStateStore
from stage2_parallel import AgentView, ParallelEventProcessor, SpatialHashNeighborFinder
from stage2_simulation import ScalableSimulation


class Stage2Tests(unittest.TestCase):
    def test_parallel_neighbor_finding_matches_serial(self) -> None:
        agents = [
            AgentView(0, "human", 10, 10),
            AgentView(1, "zombie", 15, 10),
            AgentView(2, "human", 200, 200),
            AgentView(3, "zombie", 205, 200),
        ]
        serial = SpatialHashNeighborFinder(radius=10, workers=1, parallel=False).find_pairs(agents)
        parallel = SpatialHashNeighborFinder(radius=10, workers=2, parallel=True).find_pairs(agents)
        self.assertEqual(serial, parallel)

    def test_parallel_event_processing_matches_serial(self) -> None:
        agents = [
            AgentView(0, "human", 10, 10),
            AgentView(1, "zombie", 15, 10),
        ]
        pairs = SpatialHashNeighborFinder(radius=10, workers=1, parallel=False).find_pairs(agents)
        serial_processor = ParallelEventProcessor(workers=1, parallel=False)
        parallel_processor = ParallelEventProcessor(workers=2, parallel=True)
        self.assertEqual(
            serial_processor.build_events(agents, pairs),
            parallel_processor.build_events(agents, pairs),
        )

    def test_large_simulation_produces_metrics(self) -> None:
        simulation = ScalableSimulation(agent_count=1_000, workers=2, parallel=True, seed=3)
        metrics = simulation.step()
        self.assertEqual(metrics.active_agents, 1_000)
        self.assertGreaterEqual(metrics.neighbor_pairs, 0)
        self.assertGreaterEqual(metrics.events_processed, 0)

    def test_sqlite_store_persists_agents_events_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "stage2.sqlite"
            simulation = ScalableSimulation(agent_count=200, workers=2, parallel=True, seed=4)
            with SQLiteStateStore(database_path) as database:
                run_id = database.start_run(
                    {
                        "agent_count": 200,
                        "steps": 1,
                        "workers": 2,
                        "parallel": True,
                        "seed": 4,
                    }
                )
                metrics = simulation.step()
                database.save_step(run_id, metrics, simulation.agent_rows(), simulation.last_events)
                database.finish_run(run_id)
                self.assertEqual(database.count_rows("agents", run_id), 200)
                self.assertEqual(database.count_rows("metrics", run_id), 1)
                summary = database.run_summary(run_id)
                self.assertIsNotNone(summary)
                self.assertEqual(summary["status"], "complete")


if __name__ == "__main__":
    unittest.main()
