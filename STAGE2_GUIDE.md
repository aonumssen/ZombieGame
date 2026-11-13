# Stage 2: Scaling up the simulation

Stage 2 runs thousands of agents from Terminal. That makes it possible to time neighbor searches and infection events without drawing every agent in a window.

## Run it

```bash
python3 -m unittest -v test_storage.py test_stage2.py
python3 stage2_experiment.py \
  --agents 1000 5000 10000 \
  --steps 10 \
  --workers 4 \
  --database stage2_results.sqlite \
  --json reproduced_stage2_results.json
```

The experiment runs each population once in serial mode and once with four threads. It prints average step, neighbor, and event times and saves the measurements to SQLite and JSON. To run just the parallel case, add `--parallel-only`.

For a shorter demo, run `python3 stage2_demo.py --agents 1000 --steps 5 --workers 4`. It prints the population and event counts as the simulation runs, then shows how many rows were written to `stage2_demo.sqlite`.

## Follow a tick through the code

1. `ScalableSimulation` moves its agents and makes a snapshot of their IDs, positions, and current state. Workers read the snapshot.
2. `SpatialHashNeighborFinder` puts each agent in a grid cell. It splits the sorted IDs into chunks for workers, which check agents in nearby cells. Each pair is returned once. The simulation merges and sorts the lists.
3. `ParallelEventProcessor` turns nearby human–zombie pairs into infection events. A second worker pass adds up the amounts by human. The main thread applies the totals in ID order. A human who reaches 1.0 becomes a zombie.
4. The experiment runner passes the result to `SQLiteStateStore`. It saves the latest agent state, events, and metrics for that step in one transaction.

The grid saves distance checks when agents are spread out. The thread pool uses `ThreadPoolExecutor` from the standard library. Workers return their own results, so they never have to lock and update the same live agent.

## What the benchmark showed

The [Stage 2 report](STAGE2_REPORT.md) has the full timing table and demo output. At 5,000 agents, the average step was 21.73 ms with four threads and 22.00 ms in serial. At 10,000 agents, the threaded neighbor search was a little faster, but the threaded event phase took longer. The final pair and event counts matched at all three population sizes.

## Where to look

| File | What to look for |
| --- | --- |
| `stage2_simulation.py` | Agent movement, snapshots, and per-step metrics |
| `stage2_parallel.py` | Grid search, infection events, and the final state update |
| `stage2_database.py` | SQLite tables for runs, agents, events, and metrics |
| `stage2_experiment.py` | Serial and threaded runs at different population sizes |
| `stage2_demo.py` | Step output and database row counts |
| `test_stage2.py` | Pair and event comparisons and SQLite tests |
| `stage2_results.json` | Measurements from the ten-step benchmark |
