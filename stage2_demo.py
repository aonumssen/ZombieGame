"""Small live demonstration for the Stage 2 design.

Run ``python3 stage2_demo.py`` to see a parallel simulation step, the
population counts, and the SQLite rows written by the same run.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from stage2_database import SQLiteStateStore
from stage2_simulation import ScalableSimulation


def main() -> None:
    parser = argparse.ArgumentParser(description="Demonstrate the Stage 2 simulation and database")
    parser.add_argument("--agents", type=int, default=1_000)
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--database", type=Path, default=Path("stage2_demo.sqlite"))
    arguments = parser.parse_args()

    simulation = ScalableSimulation(
        agent_count=arguments.agents,
        workers=arguments.workers,
        parallel=True,
        seed=7,
    )
    configuration = {
        "agent_count": arguments.agents,
        "steps": arguments.steps,
        "workers": arguments.workers,
        "parallel": True,
        "seed": 7,
        "dt": 0.05,
    }

    print("Stage 2 demonstration")
    print(f"agents={arguments.agents} workers={arguments.workers} database={arguments.database}")
    with SQLiteStateStore(arguments.database) as database:
        run_id = database.start_run(configuration)
        print(f"run_id={run_id}")
        for _ in range(arguments.steps):
            metrics = simulation.step(configuration["dt"])
            database.save_step(run_id, metrics, simulation.agent_rows(), simulation.last_events)
            print(
                f"step={metrics.step} humans={metrics.humans} zombies={metrics.zombies} "
                f"neighbors={metrics.neighbor_pairs} events={metrics.events_processed} "
                f"step_ms={metrics.step_time_ms:.2f}"
            )
        database.finish_run(run_id)
        print(
            "database_rows="
            f"agents:{database.count_rows('agents', run_id)} "
            f"events:{database.count_rows('events', run_id)} "
            f"metrics:{database.count_rows('metrics', run_id)}"
        )
        print(f"summary={database.run_summary(run_id)}")


if __name__ == "__main__":
    main()
