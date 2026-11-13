# Zombie Game Stage 2 Report

## Design

The desktop game has a small population. Stage 2 moves the larger experiments into a headless simulation so the timings reflect the simulation rather than the window.

`ScalableSimulation` owns the live `ScalableAgent` objects and moves them at the start of each step. It then gives the workers a snapshot of the agents. Each worker can read the snapshot and return its results while the live objects stay with the simulation.

**Finding neighbors.** A full search would check `n * (n - 1) / 2` pairs. `SpatialHashNeighborFinder` divides the map into grid cells. For each agent, it checks candidates in the surrounding cells. Workers handle chunks of sorted agent IDs, and each returns its own list of pairs. The finder merges and sorts those lists so the order stays the same across runs.

**Processing events.** `ParallelEventProcessor` takes the pairs and creates an infection event for each human–zombie contact. The event records the source zombie, target human, and an amount based on distance. A second pass adds up the amounts by target. The main thread applies the totals in agent-ID order and turns a human into a zombie when the total infection reaches 1.0. Keeping the writes on one thread prevents two workers from changing the same agent at once.

**Saving a step.** `SQLiteStateStore` writes each completed step in one transaction. `runs` holds settings and status, `agents` holds the latest state of each agent, `events` holds contacts by step, and `metrics` holds counts and timing. The simulation hands off Python objects, and the adapter handles the SQL.

These class boundaries also make it possible to change how the grid search, event processing, or storage works without changing the movement rules.

## Experiment

The serial and threaded runs used the same starting agents and seed. Each ran ten steps of 0.05 simulated seconds. The threaded runs used four workers, and both modes saved results to SQLite.

```bash
python3 stage2_experiment.py \
  --agents 1000 5000 10000 \
  --steps 10 \
  --workers 4 \
  --database stage2_results.sqlite \
  --json reproduced_stage2_results.json
```

The times are averages per step in milliseconds. Pair and event counts are from the final step. The original run is in [stage2_results.json](stage2_results.json).

| Agents | Mode | Step (ms) | Neighbor search (ms) | Event processing (ms) | Neighbor pairs | Final events |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1,000 | serial | 2.47 | 1.55 | 0.15 | 297 | 106 |
| 1,000 | threaded | 2.91 | 1.73 | 0.42 | 297 | 106 |
| 5,000 | serial | 22.00 | 14.48 | 3.17 | 7,645 | 2,422 |
| 5,000 | threaded | 21.73 | 14.13 | 3.38 | 7,645 | 2,422 |
| 10,000 | serial | 65.05 | 43.51 | 12.30 | 30,437 | 9,603 |
| 10,000 | threaded | 66.17 | 42.80 | 13.86 | 30,437 | 9,603 |

At 1,000 agents, starting and coordinating workers cost more time than it saved. The threaded run had a small lead at 5,000 agents. At 10,000 agents, it saved 0.71 ms on neighbor finding but spent an extra 1.56 ms on events, so the full step was slightly slower. Python's GIL limits how much CPU-bound Python work can run at once in threads. Stage 3 uses the same snapshot and update approach to try separate processes.

The two modes produced matching final pair and event counts at each size. At 10,000 agents, each SQLite run recorded 10,000 current agent rows, 10 metric rows, and 96,122 event rows.

## Demo and checks

```bash
python3 stage2_demo.py --agents 1000 --steps 5 --workers 4 --database stage2_demo.sqlite
python3 -m unittest -v test_storage.py test_stage2.py
```

The demo prints the agent and event counts as it runs. A sample run with 1,000 agents recorded 526 events over five steps. Look for the `database_rows` line to see what SQLite saved. The tests compare the serial and threaded neighbor pairs and events, check that a 1,000-agent run returns measurements, and verify that the database saves the results.
