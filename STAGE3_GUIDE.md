# Stage 3: Parallel event processing

Two zombies can reach the same human in one tick. If both workers try to update that human directly, one update can overwrite the other. Stage 3 groups the contacts by human ID so each worker can calculate a complete total for the humans it gets.

## Try it

```bash
python3 stage3_demo.py --agents 5000 --steps 5 --backend processes --workers 4
python3 -m unittest discover -v
```

Watch the event and conversion counts and the worker process IDs in the demo output. To try another mode, pass `--backend serial` or `--backend threads`. Add `--database stage3_demo.sqlite` to save the ordered events, current agents, and timings.

For the ten-level desktop campaign, run `python3 main.py`. See the [game guide](PROJECT_GUIDE.md) for controls and checkpoints.

## What a worker gets

1. Move the agents, take a snapshot, and use the Stage 2 grid to find nearby pairs.
2. Keep the human–zombie pairs and group them by human ID. Within a group, sort contacts by zombie ID. Ties stay in the order they arrived.
3. Pack whole groups into batches. A human with 20 contacts takes more work than one with two, so the batch limit uses contact count. The processor aims for about four batches per worker. A human whose contacts exceed the limit still stays in one batch.
4. For each contact, calculate `0.12 * max(0, 1 - distance / 28)` and add it to the human's total in the same order as Stage 2 serial. Serial runs use one batch on the main process. The threaded and process modes reuse a pool when there is enough work to split. Process workers receive serialized batches and return compact arrays of amounts.
5. Wait for the results, rebuild the event log in human and zombie ID order, and update each affected human once. A human at 1.0 infection becomes a zombie and can contribute contacts on the next tick. If a worker fails, the tick restores positions and velocities and leaves the event updates unapplied.

Grouping and applying the results still take time on the main process. A single human with a lot of contacts can also make one batch take longer than the others.

## Benchmark

```bash
python3 stage3_experiment.py --output reproduced_results.json
```

Times are medians in milliseconds for the event phase, including grouping, dispatch, logging, and state updates. Each case measured four ticks after one warm-up tick for each of three seeds. The original run used CPython 3.15.0 on macOS 26.1 arm64 with eight logical CPUs. SQLite writes and replay hashing were outside the timers.

| Agents and placement | Median events | Stage 2 serial | Stage 3 serial | 4 threads | 2 processes | 4 processes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5,000 uniform | 2,417.5 | 2.85 | 2.70 | 2.96 | 4.18 | 4.63 |
| 15,000 uniform | 21,955.5 | 30.52 | 35.73 | 27.97 | 32.59 | 31.44 |
| 30,000 uniform | 89,337.5 | 135.30 | 177.43 | 183.85 | 195.11 | 200.20 |
| 15,000 clustered | 36,192 | 74.30 | 47.02 | 51.21 | 52.95 | 51.73 |

The four-process run matched Stage 2 serial in every workload, down to the event order and agent state. It recorded four worker PIDs within a measured tick in every workload. On the clustered case it took 51.73 ms, compared with 74.30 ms for Stage 2 serial. Stage 3 serial took just 47.02 ms on that same case. The batch algorithm helped there, and the extra process work did not make it faster.

See [stage3_results.json](stage3_results.json) for timings by tick, conversion counts, worker IDs, and replay hashes.

## Where to look

| File | What to look for |
| --- | --- |
| `stage3_events.py` | Grouping, batching, and applying results |
| `stage3_simulation.py` | Tick integration and what happens when a worker fails |
| `stage3_demo.py` | Terminal demo and optional SQLite output |
| `stage3_experiment.py` | Workloads, timers, and serial replay comparisons |
| `test_stage3.py` | Tests for event ordering, conversions, failure recovery, and replay |
| `test_campaign.py` | Tests for the desktop campaign and checkpoints |
