"""Run Stage 3 and show event counts, timing, conversions, and worker PIDs."""

import argparse
from contextlib import nullcontext
from pathlib import Path

from stage2_database import SQLiteStateStore
from stage3_simulation import Stage3Simulation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", type=int, default=5_000)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--backend", choices=("serial", "threads", "processes"), default="processes")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--database", type=Path, help="Optional SQLite output file")
    args = parser.parse_args()
    if min(args.agents, args.steps, args.workers) < 1:
        parser.error("agents, steps, and workers must be positive")
    configuration = {
        "agent_count": args.agents, "steps": args.steps, "workers": args.workers,
        "parallel": args.backend != "serial" and args.workers > 1,
        "backend": args.backend, "seed": args.seed, "dt": 0.05,
    }
    store = SQLiteStateStore(args.database) if args.database is not None else nullcontext()
    with store as database, Stage3Simulation(
        backend=args.backend, agent_count=args.agents, workers=args.workers, seed=args.seed
    ) as simulation:
        if database is not None:
            run_id = database.start_run(configuration)
        print(f"agents={args.agents:,} backend={args.backend} workers={args.workers}")
        for _ in range(args.steps):
            metrics = simulation.step(configuration["dt"])
            if database is not None:
                database.save_step(run_id, metrics, simulation.agent_rows(), simulation.last_events)
            print(
                f"tick={metrics.step} humans={metrics.humans:,} zombies={metrics.zombies:,} "
                f"events={metrics.events_processed:,} conversions={metrics.conversions:,} "
                f"event_ms={metrics.event_time_ms:.2f} tick_ms={metrics.step_time_ms:.2f} "
                f"pids={sorted(simulation.events.worker_pids)}"
            )
        if database is not None:
            database.finish_run(run_id)
            print(f"SQLite run {run_id} saved to {args.database}")


if __name__ == "__main__":
    main()
