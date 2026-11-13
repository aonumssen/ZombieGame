# Outbreak Last Light

You're a responder trying to get civilians out of a city overrun by zombies. Touch a civilian to rescue them. If a zombie stays close to them for too long, they can join the horde.

Python project for CPS3100 by Anthony Numssen.

## Play

Open Terminal in the project folder (`ZombieGame-main` if you downloaded the GitHub ZIP) and run:

```bash
python3 main.py
```

Use Python 3.10 or newer with Tkinter. Click **Start game** when the window opens.

- **WASD** or **arrow keys** to move
- **Mouse** to aim, **click** or **Space** to fire
- **P** to pause or resume

Rescue eight civilians, then click **Start Level** to continue. Health refills between levels, but the horde gets bigger and reinforcements come sooner. You start against three zombies on Level 1 and 21 on Level 10. Clear Level 10 to win. The run ends if you run out of health or too few civilians are left to reach eight rescues.

**Save state** keeps one checkpoint in memory. To keep it after closing the game, launch with:

```bash
python3 main.py --json-checkpoint save/checkpoint.json
```

## Run it from Terminal

```bash
python3 main.py --headless                             # Check the game engine
python3 -m unittest discover -v                        # Run all tests
python3 stage3_demo.py --agents 5000 --steps 5 --workers 4
```

The Stage 3 demo prints the event counts, timings, and worker process IDs for each tick. In the benchmark, the four-process run matched the serial replay at every tick tested, up to 30,000 agents. At 15,000 clustered agents, Stage 3 serial still had the fastest event phase.

```bash
python3 stage3_experiment.py --output reproduced_results.json
```

## Project notes

- [Game and checkpoint guide](PROJECT_GUIDE.md) covers the campaign, population changes, and saved state.
- [Stage 2 guide](STAGE2_GUIDE.md) and [report](STAGE2_REPORT.md) explain the spatial grid, threaded workers, and SQLite experiment.
- [Stage 3 guide](STAGE3_GUIDE.md) walks through event batching and the benchmark. The [report and research proposal](Zombie_Game_Stage_3_Report_and_Proposal.pdf) describes what to test next.
