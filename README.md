# Outbreak Last Light

This is my Python project for the CPS3100 Zombie Game assignment. It includes a ten-level rescue campaign and a headless population simulation. I built it as a solo project.

You play an emergency responder trying to rescue civilians while zombies move around the city, infect people, and continue to appear over time. The simulation and the desktop window are both written in Python.

GitHub repository: <https://github.com/aonumssen/ZombieGame>

## Group member

- Anthony Numssen

## Run the game

Use Python 3.10 or newer. The desktop game requires Tkinter. The project uses Python's standard library.

1. Download or clone this repository.
2. Open a terminal in the repository folder.
3. Start the game:

   ```bash
   python3 main.py
   ```

The game window shows the city, the responder, civilians, zombies, bullets, current population counts, and a small population-history graph.

### Run without opening a window

This command runs a short check of the Python engine:

```bash
python3 main.py --headless
```

It is useful on a server or on a Python installation that does not have the Tkinter desktop bindings. The windowed version needs Python with Tkinter enabled.

### Save and load state

The normal game uses `InMemoryStateStore`, so a checkpoint lasts only while the program is running. To save checkpoints in a JSON file instead, provide a file path:

```bash
python3 main.py --json-checkpoint save/checkpoint.json
```

The **Save state** and **Load state** buttons work the same way with either storage option. The game rules do not change when the storage option changes.

Run the storage tests with:

```bash
python3 -m unittest -v test_storage.py
```

## Controls and goal

- **WASD** or **arrow keys** — move the responder
- **Space** or **mouse click** — fire toward the pointer
- **P** or **Pause** — pause/resume
- Touch civilians to rescue them

Rescue eight civilians in each level, then click **Start Level** to continue. Your health refills between levels. Level 1 starts with three zombies and Level 10 starts with 21, with faster reinforcements as you advance. Clear Level 10 to win. The run ends if the responder loses all health or too few civilians remain to meet the rescue goal.

## What happens during a game

The game updates in small time steps. During each step:

1. The responder moves based on the keys being pressed.
2. Civilians wander, but flee when a zombie gets close. Nearby contact raises their infection level.
3. Zombies look for the closest civilian or the responder and move toward that target.
4. Bullets move across the map and can remove zombies when they hit.
5. The responder can rescue civilians by touching them.
6. A fully infected civilian is removed and replaced by a zombie.
7. New zombies enter from the edge of the map. Their spawn interval becomes shorter as the game continues.

Because people can be rescued or infected and zombies can be spawned or shot, both populations change over time. That is the nontrivial part of the simulation required by the assignment.

## Python classes

The main game model is in `simulation.py`. It does not import Tkinter, so the rules can be tested without the user interface.

- `Entity` — shared position, velocity, movement, and boundary behavior
- `Civilian(Entity)` — wandering, fleeing, and infection state
- `Zombie(Entity)` — target selection, pursuit, and horde separation
- `Player(Entity)` — keyboard movement, health, damage cooldown, and firing cooldown
- `Bullet(Entity)` — projectile movement and lifetime
- `Simulation` — game state, collisions, population changes, score, history, and win/loss rules

`main.py` contains `ZombieGameApp`, the Tkinter application that draws the objects and sends keyboard/mouse input to `Simulation`. Keeping the window code separate from the model makes the simulation easier to test and explain.

## Project files

- `simulation.py` — testable Python simulation engine
- `main.py` — playable Tkinter desktop game and headless smoke-test entry point
- `state_storage.py` — storage interface, in-memory adapter, JSON-file adapter, and no-op adapter
- `test_storage.py` — tests proving the same simulation works with both storage solutions
- `requirements.txt` — documents that no third-party packages are needed
- `PROJECT_GUIDE.md` — project notes and assignment context
- `stage2_simulation.py` — larger headless simulation for thousands of agents
- `stage2_parallel.py` — spatial-hash neighbor finding and event processing workers
- `stage2_database.py` — SQLite storage for runs, agents, events, and measurements
- `stage2_experiment.py` — command-line experiment runner
- `stage2_demo.py` — short demonstration that runs the engine and writes SQLite rows
- `test_stage2.py` — tests for Stage 2 behavior and persistence
- `STAGE2_GUIDE.md` — Stage 2 design explanation and measured results
- `STAGE2_REPORT.md` — direct response to the design, results, summary, and demonstration requirements

The submitted game code is Python. It does not use HTML, JavaScript, Java, CSS, or a browser runtime.

## What this demonstrates

- Runnable Stage 1 prototype
- Human and zombie population changes
- Autonomous movement and basic behavior
- Interactive controls and win/loss conditions
- Object-oriented Python classes
- Simulation logic separated from state storage
- In-memory and JSON-file storage implementations
- Tests showing that both storage options restore the same simulation

## Stage 2

The Stage 2 extension scales the population model to thousands of agents. It adds SQLite persistence, spatial-hash neighbor finding, parallel event processing, and a benchmark that compares serial and parallel runs.

See [`STAGE2_GUIDE.md`](STAGE2_GUIDE.md) for the design, commands, measured results, and demonstration plan.

For a submission-ready explanation of the two required points, see [`STAGE2_REPORT.md`](STAGE2_REPORT.md). To run the short demonstration, use `python3 stage2_demo.py`.

## Stage 3

The headless Stage 3 engine groups events by civilian target and uses a serial, threaded, or process backend with a deterministic commit. The desktop game includes the ten-level campaign and saves campaign progress in checkpoints.

```bash
python3 -m unittest discover -v
python3 stage3_demo.py --agents 5000 --steps 5 --workers 4
python3 stage3_experiment.py --output reproduced_results.json
```

See the [Stage 3 guide](STAGE3_GUIDE.md) for the algorithm, benchmark setup, and measured results. The [Stage 3 report and research proposal](Zombie_Game_Stage_3_Report_and_Proposal.pdf) includes the design, results, and proposed follow-up study.
