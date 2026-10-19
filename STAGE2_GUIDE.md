# Zombie Game Stage 2

Stage 2 scales the population model from a small game prototype to a larger experiment. The Stage 1 window is still available through `main.py`. The new Stage 2 code is a separate, headless engine so it can create thousands of agents and measure the work without a graphics window getting in the way.

## What Stage 2 adds

The implementation covers the four requested parts:

1. `ScalableSimulation` creates a configurable number of agents. The default experiment uses 1,000, 5,000, and 10,000 agents.
2. `SQLiteStateStore` saves run settings, the latest agent snapshot, every interaction event, and per-step measurements in a SQLite database.
3. `SpatialHashNeighborFinder` divides the world into cells and checks nearby cells in parallel chunks instead of comparing every agent with every other agent.
4. `ParallelEventProcessor` creates infection events and reduces their per-agent changes in parallel chunks. The final state update happens in one deterministic commit on the main thread.

The implementation uses only Python's standard library. The database is SQLite through Python's built-in `sqlite3` module, and the parallel workers use `concurrent.futures.ThreadPoolExecutor`.

## Files

| File | Role |
| --- | --- |
| `stage2_simulation.py` | Large-agent simulation, movement, metrics, and snapshots |
| `stage2_parallel.py` | Spatial-hash neighbor finding and parallel event processing |
| `stage2_database.py` | SQLite schema and persistence adapter |
| `stage2_experiment.py` | Repeatable scale and serial-versus-parallel benchmark |
| `test_stage2.py` | Correctness tests for both parallel stages and SQLite persistence |
| `stage2_results.json` | Measured results from the documented ten-step experiment |

## Design

### Live state

Each `ScalableAgent` has an ID, type (`human` or `zombie`), position, velocity, infection value, and health. The live objects stay in memory during a step because movement and state updates need fast access.

The simulation exposes an immutable `AgentView` snapshot to the worker stages. A worker never changes a live agent. This gives a clear boundary:

```text
live agents -> immutable snapshot -> parallel neighbor search
                                -> parallel event creation
                                -> parallel delta reduction
                                -> deterministic state commit
                                -> SQLite snapshot and metrics
```

### Database layer

`SQLiteStateStore` creates four tables:

- `runs` stores the configuration and status of each experiment.
- `agents` stores the latest position and state of every agent for a run.
- `events` stores infection events by step, including source, target, and amount.
- `metrics` stores population counts, neighbor counts, event counts, and timing measurements.

The simulation does not contain SQL statements. The experiment runner passes snapshots and metrics to the database adapter after each step. Each step is committed as one transaction, so a partial step is not presented as complete data.

### Neighbor finding

A naive search compares all pairs, which is approximately O(n²). That becomes impractical as the population grows. The Stage 2 finder uses a spatial hash:

1. Put each agent into a grid cell based on its coordinates.
2. For each agent, inspect only its own cell and cells within the interaction radius.
3. Split the sorted agent IDs into independent chunks.
4. Run the chunks through a worker pool.
5. Merge and sort the returned pairs so the result is deterministic.

The grid reduces the number of distance calculations when agents are spread out. The worker chunks do not share mutable state, so the neighbor stage does not need locks.

### Event processing

Every nearby human-zombie pair becomes an infection event. Event creation is split into chunks, and a second worker stage reduces event amounts into per-human infection deltas. Only after all worker results are available does the main thread apply the deltas and convert a human into a zombie when the infection reaches 1.0.

This is a deliberate two-phase design. Parallel workers calculate independent results; the single commit point prevents two workers from racing while changing the same agent. Sorting event keys before the commit also makes repeated runs with the same seed easier to compare.

## Running Stage 2

Run the correctness tests first:

```bash
python3 -m unittest -v test_storage.py test_stage2.py
```

Run a scale experiment with the default population sizes:

```bash
python3 stage2_experiment.py \
  --agents 1000 5000 10000 \
  --steps 10 \
  --workers 4 \
  --database stage2_results.sqlite \
  --json stage2_results.json
```

The command runs a serial and a parallel case for each population size. It prints average step, neighbor, and event times, and stores the same measurements in SQLite. The JSON file is convenient for making a chart or attaching results to a report.

To run only the parallel cases:

```bash
python3 stage2_experiment.py --agents 10000 --steps 20 --workers 4 --parallel-only
```

## Experimental results

The following results were produced from this repository on the development machine with seed `7`, a time step of `0.05`, four workers, ten steps per case, and SQLite persistence enabled:

| Agents | Mode | Average step ms | Neighbor ms | Event ms | Final neighbor pairs | Final events |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1,000 | serial | 2.47 | 1.55 | 0.15 | 297 | 106 |
| 1,000 | parallel | 2.91 | 1.73 | 0.42 | 297 | 106 |
| 5,000 | serial | 22.00 | 14.48 | 3.17 | 7,645 | 2,422 |
| 5,000 | parallel | 21.73 | 14.13 | 3.38 | 7,645 | 2,422 |
| 10,000 | serial | 65.05 | 43.51 | 12.30 | 30,437 | 9,603 |
| 10,000 | parallel | 66.17 | 42.80 | 13.86 | 30,437 | 9,603 |

### Summary of the results

- The spatial hash keeps the simulation runnable at 10,000 agents. The neighbor count grows with the population, but the code does not perform a full all-pairs comparison.
- Serial and parallel modes return the same neighbor pairs and event counts for the same seed. That is a correctness check, not just a timing comparison.
- The parallel neighbor stage is slightly faster at 5,000 and 10,000 agents, while the event stage is close to the serial result. At 1,000 agents, worker setup costs more than it saves.
- This implementation uses Python threads. Because CPU-bound Python code is affected by the GIL, a thread pool is not guaranteed to be faster on every machine. The important design result is that the work is partitioned cleanly; a future process-pool or native-vectorized backend can use the same snapshot and commit interfaces without changing the simulation rules.
- The database row counts are also part of the experiment. Every case stores one latest agent row per agent, one metrics row per step, and all generated events in `stage2_results.sqlite`.

## Demonstration plan

For a short demonstration, I would:

1. Run `python3 stage2_experiment.py --agents 1000 5000 10000 --steps 10 --workers 4`.
2. Explain that the same seed and rules are used for serial and parallel cases.
3. Point out that the neighbor and event counts match between modes.
4. Open `stage2_results.sqlite` with any SQLite viewer, or use the Python adapter's `read_metrics()` method to show the recorded measurements.
5. Show the spatial grid code in `stage2_parallel.py` and explain why it avoids all-pairs work.
6. Show the event reducer and explain why workers return deltas instead of mutating agents directly.
7. Run `python3 -m unittest -v test_stage2.py` to show that the serial and parallel results agree and that SQLite persistence works.

## Why the design scales better than the Stage 1 loop

Stage 1 has a small population and can afford direct list searches. Stage 2 makes the expensive parts explicit: finding nearby agents, turning contacts into events, applying state changes, and storing measurements. The spatial hash reduces unnecessary distance checks, worker chunks keep independent calculations separate, and SQLite gives the run a durable record. Those boundaries make it possible to replace one technique later without rewriting the population rules.
