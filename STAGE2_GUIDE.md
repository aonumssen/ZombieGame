# Zombie Game Stage 2

For Stage 2, I kept the original game available through `main.py` and added a separate headless engine. This lets me create thousands of agents and measure the simulation without a graphics window affecting the results.

## What I added

The new code covers the four parts in the assignment:

1. `ScalableSimulation` creates a configurable number of agents. The default experiment uses 1,000, 5,000, and 10,000 agents.
2. `SQLiteStateStore` saves run settings, the latest agent snapshot, every interaction event, and per-step measurements in a SQLite database.
3. `SpatialHashNeighborFinder` divides the world into cells and checks nearby cells in parallel chunks instead of comparing every agent with every other agent.
4. `ParallelEventProcessor` creates infection events and reduces their per-agent changes in parallel chunks. The final state update happens in one deterministic commit on the main thread.

I kept the implementation in Python's standard library. SQLite comes from Python's built-in `sqlite3` module, and the parallel workers use `concurrent.futures.ThreadPoolExecutor`.

## Files

| File | Role |
| --- | --- |
| `stage2_simulation.py` | Large-agent simulation, movement, metrics, and snapshots |
| `stage2_parallel.py` | Spatial-hash neighbor finding and parallel event processing |
| `stage2_database.py` | SQLite schema and persistence adapter |
| `stage2_experiment.py` | Repeatable scale and serial-versus-parallel benchmark |
| `test_stage2.py` | Correctness tests for both parallel stages and SQLite persistence |
| `stage2_results.json` | Measured results from the documented ten-step experiment |

## How the design works

### Live state

Each `ScalableAgent` has an ID, a type (`human` or `zombie`), a position, a velocity, an infection value, and health. I keep these live objects in memory during a step because movement and state updates need quick access.

Before the expensive work starts, the simulation creates an immutable `AgentView` snapshot. Workers read that snapshot but never change a live agent. The flow is:

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

The simulation itself does not contain SQL statements. After each step, the experiment runner passes the snapshot and measurements to the database adapter. Each step is one transaction, so the database does not show a half-written step as if it were complete.

### Neighbor finding

A direct search compares every pair, which is approximately O(n²). That becomes too expensive as the population grows. My Stage 2 finder uses a spatial hash:

1. Put each agent into a grid cell based on its coordinates.
2. For each agent, inspect only its own cell and cells within the interaction radius.
3. Split the sorted agent IDs into independent chunks.
4. Run the chunks through a worker pool.
5. Merge and sort the returned pairs so the result is deterministic.

The grid cuts down the number of distance calculations when agents are spread out. The chunks do not share mutable state, so this stage does not need locks.

### Event processing

Every nearby human-zombie pair becomes an infection event. I split event creation into chunks, then use another worker stage to add the event amounts for each human. Once those worker results are ready, the main thread applies the totals and converts a human into a zombie when the infection reaches 1.0.

I use two phases on purpose. Workers calculate independent results, and one commit point changes the live agents. That prevents two workers from updating the same human at the same time. Sorting the event keys also makes repeated runs with the same seed easier to compare.

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

The command runs one serial case and one parallel case for each population size. It prints average step, neighbor, and event times, and stores the same measurements in SQLite. The JSON file is useful if I want to make a chart or include the results in a report.

To run only the parallel cases:

```bash
python3 stage2_experiment.py --agents 10000 --steps 20 --workers 4 --parallel-only
```

## Experimental results

I produced the following results from this repository with seed `7`, a time step of `0.05`, four workers, ten steps per case, and SQLite persistence enabled:

| Agents | Mode | Average step ms | Neighbor ms | Event ms | Final neighbor pairs | Final events |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1,000 | serial | 2.47 | 1.55 | 0.15 | 297 | 106 |
| 1,000 | parallel | 2.91 | 1.73 | 0.42 | 297 | 106 |
| 5,000 | serial | 22.00 | 14.48 | 3.17 | 7,645 | 2,422 |
| 5,000 | parallel | 21.73 | 14.13 | 3.38 | 7,645 | 2,422 |
| 10,000 | serial | 65.05 | 43.51 | 12.30 | 30,437 | 9,603 |
| 10,000 | parallel | 66.17 | 42.80 | 13.86 | 30,437 | 9,603 |

### Summary of the results

- The spatial hash keeps the simulation runnable at 10,000 agents. The neighbor count grows with the population, but the code does not check every possible pair.
- Serial and parallel modes return the same neighbor pairs and event counts for the same seed. That checks correctness as well as timing.
- The parallel neighbor stage is a little faster at 5,000 and 10,000 agents, while the event stage is close to the serial result. At 1,000 agents, setting up workers costs more than it saves.
- This version uses Python threads. CPU-bound Python code is affected by the GIL, so the parallel version is not guaranteed to be faster on every computer. The useful design choice is that the work is already split behind a snapshot and commit boundary; a future process-pool version could reuse that boundary.
- The database is part of the experiment too. Each case stores one current agent row per agent, one metrics row per step, and every generated event in `stage2_results.sqlite`.

## Demonstration plan

For a short demonstration, I would:

1. Run `python3 stage2_experiment.py --agents 1000 5000 10000 --steps 10 --workers 4`.
2. Explain that the same seed and rules are used for serial and parallel cases.
3. Point out that the neighbor and event counts match between modes.
4. Open `stage2_results.sqlite` with any SQLite viewer, or use the Python adapter's `read_metrics()` method to show the recorded measurements.
5. Show the spatial grid code in `stage2_parallel.py` and explain why it avoids all-pairs work.
6. Show the event reducer and explain why workers return deltas instead of mutating agents directly.
7. Run `python3 -m unittest -v test_stage2.py` to show that the serial and parallel results agree and that SQLite persistence works.

## Why this scales better than the Stage 1 loop

Stage 1 has a small population and can afford direct list searches. In Stage 2 I separated the expensive parts: finding nearby agents, turning contacts into events, applying changes, and recording measurements. The spatial hash avoids unnecessary distance checks, worker chunks keep independent calculations separate, and SQLite gives each run a durable record. Because those pieces are separated, one technique can be replaced later without rewriting the population rules.
