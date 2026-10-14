# Outbreak Last Light

This is my Python version of the CPS3100 Zombie Game Stage 1 assignment. It is a small rescue game and a population simulation. I built it as a solo project.

You play an emergency responder trying to rescue civilians while zombies move around the city, infect people, and continue to appear over time. The simulation and the desktop window are both written in Python.

GitHub repository: <https://github.com/aonumssen/ZombieGame>

## Group member

- Anthony Numssen

## Run the game

The project uses Python's standard library, so there are no third-party packages to install.

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

The goal is to rescue 8 civilians. The game ends if the responder loses all health or if no humans remain.

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
