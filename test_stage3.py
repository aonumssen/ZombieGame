"""Correctness checks for target partitioning and Stage 3 integration."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stage2_database import SQLiteStateStore
from stage2_parallel import AgentView, NeighborPair, ParallelEventProcessor
from stage2_simulation import ScalableAgent, ScalableSimulation
from stage3_events import TargetEventProcessor
from stage3_simulation import Stage3Simulation


class Stage3Tests(unittest.TestCase):
    def test_many_sources_match_stage2_serial_exactly(self) -> None:
        sources = range(80)
        targets = range(100, 112)
        views = [AgentView(source, "zombie", 0, 0) for source in sources]
        views += [AgentView(target, "human", 1, 0) for target in targets]
        # One popular target deliberately dominates the workload. Include a
        # reversed pair, an equal-source pair and a same-kind pair.
        pairs = [NeighborPair(source, 100, 27.1 + source / 100) for source in sources]
        pairs += [NeighborPair(target, 0, 2.0) for target in targets if target != 100]
        pairs += [NeighborPair(0, 100, 27.8), NeighborPair(100, 101, 1.0)]
        pairs.reverse()

        def live_agents():
            return {
                target: ScalableAgent(
                    target, "human", 1, 0, 0, 0, infection=0.98 if target == 101 else 0
                )
                for target in targets
            }

        reference = ParallelEventProcessor(workers=1)
        expected_agents = live_agents()
        expected_events = reference.build_events(views, pairs)
        expected_conversions = reference.apply_events(expected_agents, expected_events)
        self.assertEqual(expected_conversions, 1)
        for backend, workers in (("serial", 1), ("threads", 4), ("processes", 2), ("processes", 4)):
            with self.subTest(backend=backend, workers=workers):
                actual_agents = live_agents()
                with TargetEventProcessor(backend, workers) as processor:
                    events, conversions = processor.process(views, pairs, actual_agents)
                    if backend == "processes":
                        self.assertTrue(processor.worker_pids)
                        self.assertNotIn(os.getpid(), processor.worker_pids)
                self.assertEqual(events, expected_events)
                self.assertEqual(conversions, expected_conversions)
                self.assertEqual(actual_agents, expected_agents)

    def test_empty_and_same_kind_inputs(self) -> None:
        with TargetEventProcessor("processes", 4) as processor:
            self.assertEqual(processor.process([], [], {}), ([], 0))
            views = [AgentView(0, "human", 0, 0), AgentView(1, "human", 1, 0)]
            self.assertEqual(processor.process(views, [NeighborPair(0, 1, 1)], {}), ([], 0))
            self.assertEqual(processor.worker_pids, set())

    def test_new_zombie_can_send_events_on_following_tick(self) -> None:
        with Stage3Simulation(backend="processes", workers=2, agent_count=3) as sim:
            sim.agents = {
                0: ScalableAgent(0, "zombie", 0, 5, 0, 0),
                1: ScalableAgent(1, "human", 20, 5, 0, 0, infection=0.99),
                2: ScalableAgent(2, "human", 40, 5, 0, 0),
            }
            self.assertEqual(sim.step().conversions, 1)
            self.assertEqual([(event.source_id, event.target_id) for event in sim.last_events], [(0, 1)])
            self.assertEqual(sim.step().conversions, 0)
            self.assertEqual([(event.source_id, event.target_id) for event in sim.last_events], [(1, 2)])

    def test_worker_error_does_not_commit_any_target(self) -> None:
        views = [
            AgentView(0, "zombie", 0, 0),
            AgentView(1, "human", 1, 0),
            AgentView(2, "human", 2, 0),
        ]
        pairs = [NeighborPair(0, 1, 1.0), NeighborPair(0, 2, 2.0)]
        agents = {view.agent_id: ScalableAgent(view.agent_id, view.kind, view.x, 0, 0, 0) for view in views}
        with TargetEventProcessor("processes", 2) as processor:
            with self.assertRaises(ZeroDivisionError):
                processor.process(views, pairs, agents, radius=0.0)
            self.assertEqual([(agent.kind, agent.infection) for agent in agents.values()],
                             [("zombie", 0.0), ("human", 0.0), ("human", 0.0)])
            self.assertEqual(len(processor.process(views, pairs, agents)[0]), 2)

    def test_failed_step_can_be_retried(self) -> None:
        reference = ScalableSimulation(agent_count=200, parallel=False)
        with Stage3Simulation(backend="serial", agent_count=200) as sim:
            with patch.object(sim.events, "process", side_effect=RuntimeError("worker failed")):
                with self.assertRaisesRegex(RuntimeError, "worker failed"):
                    sim.step()
            self.assertEqual(sim.agents, reference.agents)
            self.assertEqual(sim.step_number, 0)
            self.assertEqual(sim.last_events, [])
            sim.step()
            reference.step()
            self.assertEqual(sim.agents, reference.agents)
            self.assertEqual(sim.last_events, reference.last_events)

    def test_seeded_replay_and_sqlite_event_log(self) -> None:
        reference = ScalableSimulation(agent_count=1_000, seed=23, parallel=False)
        with tempfile.TemporaryDirectory() as directory, Stage3Simulation(
            backend="processes", workers=2, agent_count=1_000, seed=23
        ) as sim, SQLiteStateStore(Path(directory) / "stage3.sqlite") as store:
            run_id = store.start_run(
                {"agent_count": 1_000, "workers": 2, "parallel": True, "seed": 23, "steps": 6}
            )
            event_count = conversions = 0
            # Seed an imminent conversion to exercise the event log and state update.
            for simulation in (reference, sim):
                simulation.agents[0].x = 1_000.0
                simulation.agents[0].y = 1_000.0
                target = simulation.agents[200]
                target.x, target.y, target.infection = 1_001.0, 1_000.0, 0.999
            for _ in range(6):
                expected = reference.step()
                actual = sim.step()
                self.assertEqual(sim.last_events, reference.last_events)
                self.assertEqual(sim.agents, reference.agents)
                self.assertEqual(actual.conversions, expected.conversions)
                event_count += actual.events_processed
                conversions += actual.conversions
                store.save_step(run_id, actual, sim.agent_rows(), sim.last_events)
            store.finish_run(run_id)
            self.assertGreater(conversions, 0)
            self.assertEqual(store.count_rows("events", run_id), event_count)
            self.assertEqual(store.count_rows("agents", run_id), 1_000)
            self.assertEqual(store.count_rows("metrics", run_id), 6)
            self.assertEqual(store.run_summary(run_id)["status"], "complete")


if __name__ == "__main__":
    unittest.main()
