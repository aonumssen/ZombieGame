# Zombie Game Stage 2 Report

This report addresses the two parts that need to be visible in the submission:

1. a clear explanation of the design; and
2. experimental results with summaries and a runnable demonstration.

The Stage 2 work is separate from the small Tkinter game in `main.py`. It is a headless Python simulation so the agent count and the performance measurements can be increased without the user interface becoming the bottleneck.

## 1. Design explanation

### What the design needs to do

Stage 2 needs to handle many agents, store the data in a database, and use parallel work in two places: finding neighbors and processing events. I used four main components:

| Component | Responsibility |
| --- | --- |
| `ScalableSimulation` | Owns the live agents, advances time, and records step measurements. |
| `SpatialHashNeighborFinder` | Finds nearby agent pairs using grid cells and worker chunks. |
| `ParallelEventProcessor` | Turns human-zombie contacts into infection events and reduces event amounts in parallel. |
| `SQLiteStateStore` | Stores runs, current agent rows, events, and metrics in SQLite. |

The classes are connected through ordinary Python data objects. `ScalableSimulation` does not contain SQL, and the workers do not directly mutate the simulation. That keeps the rules, parallel work, and persistence separate.

### Data flow for one step

```text
live ScalableAgent objects
          |
          v
immutable AgentView snapshot
          |
          +--> SpatialHashNeighborFinder --> NeighborPair list
          |
          +--> ParallelEventProcessor --> infection events --> deltas
                                                             |
                                                             v
                                           deterministic state commit
                                                             |
                                                             v
                                  SQLiteStateStore saves state and metrics
```

The snapshot is important. Worker tasks only read `AgentView` values. They return pairs, events, or numeric deltas. The main simulation applies the final deltas in sorted agent-ID order. This avoids race conditions while still allowing the expensive calculations to be split across workers.

### Neighbor-finding design

A direct all-pairs search would compare roughly `n * (n - 1) / 2` pairs. That grows too quickly when `n` becomes large. The spatial hash puts each agent into a grid cell based on its `(x, y)` position. For one agent, the finder checks its cell and nearby cells only. Agents are split into chunks, and each chunk is sent to a worker.

Each worker returns its own list of `NeighborPair` objects. The lists are merged and sorted after the workers finish. Since each worker has a read-only snapshot and its own output list, no lock is needed for this stage.

### Event-processing design

Each nearby human-zombie pair becomes an infection event. The event contains the source zombie, the target human, and an infection amount based on the distance between them.

Event processing has two steps:

1. Worker chunks create infection events from neighbor pairs.
2. Worker chunks add event amounts into per-human deltas.

The main thread then applies those deltas once. If a human reaches infection `1.0`, the main thread changes that agent's type to `zombie`. This is safer than having multiple workers change agent objects directly.

### Database design

`SQLiteStateStore` uses four tables:

- `runs`: configuration, worker count, seed, status, and timestamps;
- `agents`: the latest saved row for each agent in a run;
- `events`: every infection event, organized by run and step; and
- `metrics`: population counts, neighbor counts, event counts, and timing values.

The simulation sends a complete step to the storage adapter after the calculation finishes. The adapter writes the agent snapshot, events, and metrics in one transaction. This gives the experiment a durable record without placing database code inside the simulation rules.

### Why this is object-oriented

- `ScalableAgent` encapsulates one agent's state and movement.
- `ScalableSimulation` owns a collection of agents and coordinates the game rules.
- `SpatialHashNeighborFinder` hides the grid and worker details behind `find_pairs()`.
- `ParallelEventProcessor` hides event creation and reduction behind `build_events()` and `apply_events()`.
- `SQLiteStateStore` hides the schema and SQL statements behind `start_run()`, `save_step()`, and `finish_run()`.

Each class has one main responsibility. The simulation can use a different neighbor finder, event processor, or database adapter later without rewriting the agent rules.

## 2. Experimental results

### Experiment setup

I ran serial and parallel versions with the same random seed and the same initial agents. Each case ran ten steps with a time step of `0.05`, four workers in parallel mode, and SQLite persistence enabled.

The command was:

```bash
python3 stage2_experiment.py \
  --agents 1000 5000 10000 \
  --steps 10 \
  --workers 4 \
  --database stage2_results.sqlite \
  --json stage2_results.json
```

The benchmark records average time for a complete step, the neighbor-finding stage, and the event-processing stage. It also records the final neighbor and event counts so that serial and parallel runs can be compared for correctness.

### Results

These are the measured results saved in `stage2_results.json`:

| Agents | Mode | Average step ms | Neighbor ms | Event ms | Neighbor pairs | Events |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1,000 | serial | 2.47 | 1.55 | 0.15 | 297 | 106 |
| 1,000 | parallel | 2.91 | 1.73 | 0.42 | 297 | 106 |
| 5,000 | serial | 22.00 | 14.48 | 3.17 | 7,645 | 2,422 |
| 5,000 | parallel | 21.73 | 14.13 | 3.38 | 7,645 | 2,422 |
| 10,000 | serial | 65.05 | 43.51 | 12.30 | 30,437 | 9,603 |
| 10,000 | parallel | 66.17 | 42.80 | 13.86 | 30,437 | 9,603 |

### Summary

The spatial hash lets the simulation continue running with 10,000 agents without doing a full all-pairs comparison. The amount of neighbor work grows with the population, but it stays much smaller than checking every possible pair.

The serial and parallel versions produce the same neighbor-pair and event counts for every tested population size. That shows the parallel path is producing the same result for the same seed, not just a different timing number.

The parallel version is not automatically faster in every case. At 1,000 agents, worker setup costs more than it saves. At 5,000 agents, the average parallel step is slightly faster. At 10,000 agents, neighbor finding is slightly faster in parallel, but event-worker overhead makes the total step about the same. This is expected for Python threads because CPU-bound work is affected by the GIL. The important result for this assignment is that the work is actually partitioned into parallel stages, and the snapshot/commit boundary leaves room for a future process-pool implementation.

The database also captured the work. For the 10,000-agent runs, SQLite stored 10,000 current agent rows, 10 metric rows, and 96,122 event rows per run.

## 3. Demonstration

### Automated correctness check

```bash
python3 -m unittest -v test_storage.py test_stage2.py
```

This checks that:

- serial and parallel neighbor finding return the same pairs;
- serial and parallel event creation return the same events;
- a 1,000-agent simulation produces measurements; and
- SQLite stores agents, events, metrics, and the completed run status.

### Live database demonstration

Run:

```bash
python3 stage2_demo.py --agents 1000 --steps 5 --workers 4 --database stage2_demo.sqlite
```

The demonstration prints the population counts, neighbor count, event count, step time, and database row counts. A typical run looks like this:

```text
Stage 2 demonstration
agents=1000 workers=4 database=stage2_demo.sqlite
run_id=1
step=1 humans=800 zombies=200 neighbors=291 events=106 step_ms=5.15
step=2 humans=800 zombies=200 neighbors=280 events=103 step_ms=3.33
...
database_rows=agents:1000 events:526 metrics:5
```

For a class presentation, I would show the command first, then open `stage2_parallel.py` to explain the spatial grid and event workers, and finally open the SQLite database or the `run_summary()` output to show that the run was saved. The main point to demonstrate is that the same simulation step both uses the parallel stages and produces a durable database record.

## Conclusion

The design meets the two requested points. The data flow, classes, database boundary, parallel stages, and safe commit step are explained above. The benchmark provides repeatable measurements at three population sizes, the summaries explain what those numbers mean, and `stage2_demo.py` gives a short runnable demonstration instead of relying only on screenshots or claims.
