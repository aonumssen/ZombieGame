"""Run Stage 2 scale and parallelism experiments.

Example:
    python3 stage2_experiment.py --agents 1000 5000 10000 --steps 20
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import time
from typing import Any

from stage2_database import SQLiteStateStore
from stage2_simulation import ScalableSimulation


def run_case(
    agent_count: int,
    steps: int,
    workers: int,
    parallel: bool,
    seed: int,
    database_path: Path,
) -> dict[str, Any]:
    configuration = {
        "agent_count": agent_count,
        "steps": steps,
        "workers": workers,
        "parallel": parallel,
        "seed": seed,
        "dt": 0.05,
    }
    simulation = ScalableSimulation(
        agent_count=agent_count,
        workers=workers,
        parallel=parallel,
        seed=seed,
    )
    step_metrics = []
    started = time.perf_counter()
    with SQLiteStateStore(database_path) as database:
        run_id = database.start_run(configuration)
        try:
            for _ in range(steps):
                metrics = simulation.step(configuration["dt"])
                step_metrics.append(metrics)
                database.save_step(run_id, metrics, simulation.agent_rows(), simulation.last_events)
            database.finish_run(run_id)
        except Exception:
            database.finish_run(run_id, status="failed")
            raise
        persisted_agents = database.count_rows("agents", run_id)
        persisted_events = database.count_rows("events", run_id)
        persisted_metrics = database.count_rows("metrics", run_id)
    wall_seconds = time.perf_counter() - started
    neighbor_times = [metric.neighbor_time_ms for metric in step_metrics]
    event_times = [metric.event_time_ms for metric in step_metrics]
    step_times = [metric.step_time_ms for metric in step_metrics]
    last = step_metrics[-1] if step_metrics else None
    return {
        **configuration,
        "run_id": run_id,
        "wall_seconds_including_database": wall_seconds,
        "steps_completed": len(step_metrics),
        "average_step_ms": statistics.mean(step_times) if step_times else 0.0,
        "average_neighbor_ms": statistics.mean(neighbor_times) if neighbor_times else 0.0,
        "average_event_ms": statistics.mean(event_times) if event_times else 0.0,
        "final_humans": last.humans if last else 0,
        "final_zombies": last.zombies if last else 0,
        "final_neighbor_pairs": last.neighbor_pairs if last else 0,
        "final_events": last.events_processed if last else 0,
        "persisted_agent_rows": persisted_agents,
        "persisted_event_rows": persisted_events,
        "persisted_metric_rows": persisted_metrics,
    }


def print_results(results: list[dict[str, Any]]) -> None:
    columns = (
        ("agent_count", "Agents"),
        ("parallel", "Mode"),
        ("average_step_ms", "Avg step ms"),
        ("average_neighbor_ms", "Neighbors ms"),
        ("average_event_ms", "Events ms"),
        ("final_neighbor_pairs", "Pairs"),
        ("final_events", "Events"),
    )
    print("\nStage 2 experiment results")
    print(" | ".join(label for _, label in columns))
    print("-" * 112)
    for result in results:
        values = []
        for key, _ in columns:
            value = result[key]
            if key == "parallel":
                value = "parallel" if value else "serial"
            elif isinstance(value, float):
                value = f"{value:.2f}"
            values.append(str(value))
        print(" | ".join(values))


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the Stage 2 scalable simulation")
    parser.add_argument("--agents", nargs="+", type=int, default=[1000, 5000, 10000])
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--database", type=Path, default=Path("stage2_results.sqlite"))
    parser.add_argument("--json", type=Path, help="also write the result rows to JSON")
    parser.add_argument(
        "--parallel-only",
        action="store_true",
        help="run only the parallel cases instead of serial and parallel pairs",
    )
    arguments = parser.parse_args()
    if arguments.steps < 1:
        parser.error("--steps must be at least 1")
    if arguments.workers < 1:
        parser.error("--workers must be at least 1")

    results: list[dict[str, Any]] = []
    modes = (True,) if arguments.parallel_only else (False, True)
    for agent_count in arguments.agents:
        for parallel in modes:
            result = run_case(
                agent_count=agent_count,
                steps=arguments.steps,
                workers=arguments.workers,
                parallel=parallel,
                seed=arguments.seed,
                database_path=arguments.database,
            )
            results.append(result)
    print_results(results)
    print(f"\nSQLite database: {arguments.database}")
    if arguments.json:
        arguments.json.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(f"JSON results: {arguments.json}")


if __name__ == "__main__":
    main()
