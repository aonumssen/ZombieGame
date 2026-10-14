# Outbreak: Last Light — Python Edition

This repository contains a concrete, runnable **Zombie Game — Stage 1** prototype. The primary implementation is now Python: the simulation rules are in `simulation.py`, and the playable desktop interface is in `main.py`.

GitHub repository: <https://github.com/aonumssen/ZombieGame>

## Group member

- Anthony Numssen

## Run the game

The game uses only Python's standard library. No third-party packages are required.

1. Download or clone this repository.
2. Open a terminal in the repository folder.
3. Start the desktop game:

   ```bash
   python3 main.py
   ```

The game window opens with a city map, civilians, zombies, a responder, population counters, and a live human/zombie history graph.

### Check the simulation without opening a window

This command runs a short automated smoke test of the Python engine:

```bash
python3 main.py --headless
```

It is useful on a server or any Python installation that does not have the Tkinter desktop bindings. For the full windowed game, use Python 3 with Tkinter enabled. Tkinter is included with most Python installations; on Linux it may be packaged separately as `python3-tk`.

### Choose a state-storage solution

The default app uses `InMemoryStateStore`, which is fast and lasts for the current process. To use durable JSON checkpoints instead, provide a file path:

```bash
python3 main.py --json-checkpoint save/checkpoint.json
```

The **Save state** and **Load state** buttons use whichever adapter was selected. The simulation code does not change when the adapter changes.

Run the storage tests with:

```bash
python3 -m unittest -v test_storage.py
```

## Controls and objective

- **WASD** or **arrow keys** — move the responder
- **Space** or **mouse click** — fire toward the pointer
- **P** or **Pause** — pause/resume
- Touch civilians to rescue them

Rescue 8 civilians before the responder loses all health or the human population reaches zero.

## How the simulation works

The game advances in small time steps. Every step:

1. The player moves according to the currently pressed keys.
2. Civilians wander. When a zombie is close, they flee; contact gradually increases their infection value.
3. Zombies pursue the nearest civilian or the player. A small separation force prevents the horde from collapsing into one point.
4. Bullets move, expire, and remove zombies on contact.
5. The player can rescue nearby civilians. Infected civilians are removed and become new zombies.
6. New zombies enter from the map edge on an increasingly shorter interval, creating changing population dynamics.
7. The engine records human and zombie counts for the live graph and checks victory/loss conditions.

These rules make the prototype nontrivial: the human and zombie populations change over time through rescue, infection, shooting, and spawning.

## Object-oriented Python design

`simulation.py` contains the complete game model and does not import Tkinter, so it can be tested independently:

- `Entity` — shared position, velocity, movement, and boundary behavior
- `Civilian(Entity)` — wandering, fleeing, and infection state
- `Zombie(Entity)` — target selection, pursuit, and horde separation
- `Player(Entity)` — keyboard movement, health, damage cooldown, and firing cooldown
- `Bullet(Entity)` — projectile movement and lifetime
- `Simulation` — game state, collisions, population changes, score, history, and win/loss rules

`main.py` contains `ZombieGameApp`, a Tkinter view/controller that draws those Python objects and sends keyboard/mouse input to `Simulation`. The interface is separate from the rules so the essential simulation remains clearly implemented in Python.

## Files

- `simulation.py` — testable Python simulation engine
- `main.py` — playable Tkinter desktop game and headless smoke-test entry point
- `state_storage.py` — storage interface, in-memory adapter, JSON-file adapter, and no-op adapter
- `test_storage.py` — tests proving the same simulation works with both storage solutions
- `requirements.txt` — documents that no third-party packages are needed
- `PROJECT_GUIDE.md` — project notes and assignment context

The game source is Python-only. There are no HTML, JavaScript, Java, CSS, or browser-game files in the submission.

## Assignment alignment

- [x] Concrete, runnable prototype
- [x] Essential simulation implemented in Python
- [x] Nontrivial human and zombie population dynamics
- [x] Interactive controls and clear win/loss states
- [x] Live population counts and history graph
- [x] Object-oriented design with interacting classes
- [x] Full group-member name included
- [x] Source files available in GitHub
