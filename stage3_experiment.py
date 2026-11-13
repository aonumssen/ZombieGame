"""Benchmark Stage 3 against Stage 2 serial with exact replay checks."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import json
import os
import platform
import random
import statistics
import struct

from stage2_simulation import ScalableSimulation
from stage3_simulation import Stage3Simulation

MODES = (
    ("stage2-serial", "serial", 1),
    ("stage3-serial", "serial", 1),
    ("stage3-threads-4", "threads", 4),
    ("stage3-processes-2", "processes", 2),
    ("stage3-processes-4", "processes", 4),
)


def cluster_agents(simulation: ScalableSimulation) -> None:
    """Move 30% of agents into a 400 × 400 region, with both agent kinds."""
    rng = random.Random(simulation.seed + 8_197)
    for agent in rng.sample(list(simulation.agents.values()), round(simulation.agent_count * 0.30)):
        agent.x = rng.uniform(800.0, 1_200.0)
        agent.y = rng.uniform(800.0, 1_200.0)


def fingerprint(simulation: ScalableSimulation, metrics) -> str:
    """Hash ordered events and exact binary agent state after each tick."""
    digest = sha256()
    digest.update(struct.pack("!5q", metrics.step, metrics.humans, metrics.zombies,
                              metrics.neighbor_pairs, metrics.conversions))
    for event in simulation.last_events:
        digest.update(event.event_type.encode("ascii") + b"\x00")
        digest.update(struct.pack("!qqd", event.source_id, event.target_id, event.amount))
    for agent in simulation.agent_rows():
        digest.update(struct.pack("!q?6d", agent.agent_id, agent.kind == "zombie",
                                  agent.x, agent.y, agent.vx, agent.vy,
                                  agent.infection, agent.health))
    return digest.hexdigest()


def run_trial(count: int, layout: str, seed: int, warmup: int, steps: int, mode: tuple) -> dict:
    name, backend, workers = mode
    if name == "stage2-serial":
        runner = nullcontext(ScalableSimulation(agent_count=count, seed=seed, parallel=False))
    else:
        runner = Stage3Simulation(agent_count=count, seed=seed, backend=backend, workers=workers)
    ticks = []
    with runner as simulation:
        if layout == "clustered":
            cluster_agents(simulation)
        for index in range(warmup + steps):
            metrics = simulation.step(0.05)
            ticks.append({
                **asdict(metrics),
                "warmup": index < warmup,
                "digest": fingerprint(simulation, metrics),
                "worker_pids": sorted(simulation.events.worker_pids)
                if isinstance(simulation, Stage3Simulation) else [],
            })
    return {"mode": name, "seed": seed, "ticks": ticks}


def summarize(trials: list[dict], mode: str) -> dict:
    rows = [trial for trial in trials if trial["mode"] == mode]
    measured = [tick for trial in rows for tick in trial["ticks"] if not tick["warmup"]]
    return {
        "mode": mode,
        "event_median_ms": statistics.median(tick["event_time_ms"] for tick in measured),
        "tick_median_ms": statistics.median(tick["step_time_ms"] for tick in measured),
        "cold_event_median_ms": statistics.median(trial["ticks"][0]["event_time_ms"] for trial in rows),
        "event_median_count": statistics.median(tick["events_processed"] for tick in measured),
        "event_max_count": max(tick["events_processed"] for tick in measured),
        "total_conversions_measured": sum(tick["conversions"] for tick in measured),
        "max_worker_pids_in_one_tick": max(len(tick["worker_pids"]) for tick in measured),
        "event_ms_by_seed": {
            trial["seed"]: statistics.median(
                tick["event_time_ms"] for tick in trial["ticks"] if not tick["warmup"]
            ) for trial in rows
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", type=int, nargs="+", default=[5_000, 15_000, 30_000])
    parser.add_argument("--clustered-agents", type=int, default=15_000, help="Use 0 to skip")
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 23, 101])
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("stage3_results.json"))
    args = parser.parse_args()
    if min(*args.agents, args.steps, args.warmup) < 1 or args.clustered_agents < 0:
        parser.error("agents, steps, and warmup must be positive and clustered-agents nonnegative")
    cases = [(count, "uniform") for count in args.agents]
    if args.clustered_agents:
        cases.append((args.clustered_agents, "clustered"))
    results = {
        "environment": {
            "platform": platform.platform(), "python": platform.python_version(),
            "implementation": platform.python_implementation(), "logical_cpus": os.cpu_count(),
        },
        "settings": {"seeds": args.seeds, "warmup": args.warmup, "steps": args.steps, "dt": 0.05},
        "cases": [],
    }
    for count, layout in cases:
        trials = []
        for index, seed in enumerate(args.seeds):
            offset = index % len(MODES)
            order = MODES[offset:] + MODES[:offset]
            seeded = [run_trial(count, layout, seed, args.warmup, args.steps, mode) for mode in order]
            reference = next(trial for trial in seeded if trial["mode"] == "stage2-serial")
            expected = [tick["digest"] for tick in reference["ticks"]]
            for trial in seeded:
                if [tick["digest"] for tick in trial["ticks"]] != expected:
                    raise RuntimeError(f"Replay diverged: {count=} {layout=} {seed=} mode={trial['mode']}")
            trials.extend(seeded)
            print(f"{count:,} {layout}, seed {seed}: all five replays match", flush=True)
        summaries = [summarize(trials, mode[0]) for mode in MODES]
        baseline = summaries[0]
        for row in summaries:
            row["event_speedup_vs_stage2"] = baseline["event_median_ms"] / row["event_median_ms"]
            print(f"  {row['mode']:19} event {row['event_median_ms']:8.2f} ms  "
                  f"tick {row['tick_median_ms']:8.2f} ms  "
                  f"vs Stage 2 {row['event_speedup_vs_stage2']:.2f}x", flush=True)
        results["cases"].append({
            "agents": count, "layout": layout, "exact_replay_match": True,
            "summary": summaries, "trials": trials,
        })
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
