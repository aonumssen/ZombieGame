# Outbreak Last Light · Stage 3

Stage 3 adds target-based parallel event processing to the existing scalable Python simulation. An event represents an in-game human–zombie contact. Every contact for a given human goes to the same batch, and the main process applies each human's result at the end of the tick. The three backends use the same event algorithm.

## Run it

Requires Python 3.10 or newer. The headless simulation, tests, and benchmark use the standard library.

```bash
python3 main.py
```

Click **Start game** to play. Move with WASD or the arrow keys, aim with the mouse, and click or press Space to fire. Touch eight civilians to clear a level, then select **Start Level** to continue. Each level starts with 14 civilians and restores your health. Starting zombie counts rise by two per level, from 3 on Level 1 to 21 on Level 10, and reinforcements arrive faster. Clear Level 10 to win the campaign. Losing all health or too many civilians ends the run.

**Save state** and **Load state** include your current level and progress. Run `python3 main.py --json-checkpoint checkpoint.json` to keep a save after closing the game.

## Run the tests and Stage 3 benchmark

```bash
python3 -m unittest discover -v
python3 stage3_demo.py --agents 5000 --steps 5 --backend processes --workers 4
python3 stage3_experiment.py --output reproduced_results.json
```

The demo prints each tick's population, event and conversion counts, elapsed times, and worker process IDs. Use `--backend serial` or `--backend threads` to change the execution mode. Add `--database stage3_demo.sqlite` to store ordered events, current agent state, and step metrics. Run `python3 main.py --headless` for a smoke test of the desktop campaign engine.

## Event algorithm

1. Advance positions, take an immutable agent snapshot, and find candidate pairs using the Stage 2 spatial grid.
2. Keep mixed human–zombie pairs and group them by the human's ID. Sort targets by ID and each target's contacts by zombie ID. Equal source IDs preserve input order.
3. Make batches of whole targets using contact count as the cost estimate. The default contact budget is the ceiling of total contacts divided by four times the worker count. A target with more contacts than the budget stays intact.
4. The serial backend evaluates one batch on the caller. The threaded and process backends submit batches to a reusable executor when there are multiple batches and workers. Workers compute contact amounts and left-to-right totals in isolated batches. The process backend uses spawn and transfers serialized batches and compact arrays of results.
5. Wait for all batches, assemble the event log in target/source order, and apply one update per human on the caller. Conversions take effect for source eligibility in the next tick. If event computation fails, Stage 3 restores positions and velocities and propagates the error without advancing the tick.

Every accepted contact uses `0.12 * max(0, 1 - distance / 28)` in the game. Each human's previous infection plus the ordered total is capped at 1.0. A human who reaches that threshold becomes a zombie and the infection meter resets. A single target is indivisible, which bounds the amount of parallelism available in a hotspot. Sorting, batch setup, data transfer, logging, and commit contribute to the elapsed event time.

## Measured results

Median milliseconds per event phase, including grouping, worker dispatch and waits, logging, and commit. Each cell uses four measured ticks from each of three seeds after one warm-up tick per run. All five modes match the Stage 2 serial replay for every tick in each workload. Timings were taken on macOS 26.1 arm64 with CPython 3.15.0 and eight logical CPUs.

| Agents and placement | Median events | Stage 2 serial | Stage 3 serial | 4 threads | 2 processes | 4 processes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5,000 uniform | 2,417.5 | 2.85 | 2.70 | 2.96 | 4.18 | 4.63 |
| 15,000 uniform | 21,955.5 | 30.52 | 35.73 | 27.97 | 32.59 | 31.44 |
| 30,000 uniform | 89,337.5 | 135.30 | 177.43 | 183.85 | 195.11 | 200.20 |
| 15,000 clustered | 36,192 | 74.30 | 47.02 | 51.21 | 52.95 | 51.73 |

At 15,000 clustered agents, the four-process event phase was 1.44× as fast as the Stage 2 baseline. Stage 3 serial was 1.58× as fast as that same baseline. The four-process backend recorded four distinct worker PIDs within a measured tick in every workload. See `stage3_results.json` for the full tick timings, event counts, conversions, worker IDs, and replay hashes. SQLite I/O and replay hashing were outside the benchmark timers.

## Files

| File | Purpose |
| --- | --- |
| `stage3_events.py` | Target grouping, contact-weighted batches, worker evaluation, deterministic commit |
| `stage3_simulation.py` | Stage 3 engine and failed-tick recovery |
| `stage3_demo.py` | Command-line demonstration with optional SQLite output |
| `stage3_experiment.py` | Repeatable four-workload benchmark with exact replay checks |
| `stage3_results.json` | Raw benchmark data and aggregate results |
| `test_stage3.py` | Stage 3 correctness and integration tests |
| `test_campaign.py` | Campaign progression and checkpoint tests |
| `stage2_*.py` | Stage 2 baseline, shared simulation, and SQLite adapter |
| `main.py`, `simulation.py`, `state_storage.py` | Desktop game and checkpoint adapters |
