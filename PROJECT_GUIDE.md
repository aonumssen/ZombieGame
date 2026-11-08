# Outbreak Last Light Project Guide

This guide explains how I built the Python game and how it meets the Zombie Game Stage 1 requirements.

## 1. What I built

**Outbreak Last Light** is a real-time rescue game and population simulation. The player is an emergency responder in a city containing civilians and zombies. The goal is to rescue 8 civilians before the responder is defeated or all civilians become infected.

I kept the prototype small enough to explain in class, but there is still more happening than just moving colored shapes. Entities move independently, zombies choose targets, civilians flee danger, infection can turn a civilian into a zombie, new zombies appear over time, bullets collide with zombies, and the interface records population history.

## 2. How to run and play

Run the desktop interface from the project folder:

```bash
python3 main.py
```

- Press **Start game**.
- Move with **WASD** or the **arrow keys**.
- Aim with the mouse pointer.
- Fire with **Space** or a **mouse click**.
- Touch a civilian to rescue that person.
- Avoid direct contact with zombies because each successful hit removes 18 health.
- Press **P** or select **Pause** to pause the game.

I win after rescuing 8 civilians. I lose when health reaches zero or when no civilians remain in the city.

The Python engine can also be checked without a window:

```bash
python3 main.py --headless
```

## 3. How the populations change

The assignment asks for changing human and/or zombie populations. This game models both.

### Civilian population

The game begins with 14 civilians. The number changes in two ways:

1. A civilian leaves the active population when rescued by the player.
2. A civilian leaves the human population when infection reaches 100%.

### Zombie population

The game begins with 3 zombies. The number changes in three ways:

1. A new zombie is created when a civilian becomes fully infected.
2. Zombies enter from a random map edge on a timer.
3. A zombie is removed when hit by a bullet.

The normal spawn interval begins at 5.8 seconds and gradually falls toward a minimum of 2.25 seconds. This makes the game gradually harder instead of leaving the population static.

### Infection and behavior

When a zombie stays close enough to a civilian, that civilian's infection meter increases. A red ring in the interface shows infection progress. If contact stops, infection slowly decreases. At 100%, the `Civilian` object is removed and a new `Zombie` object is created in the same location.

- Civilians normally wander in random directions.
- A civilian detects the nearest zombie within 150 pixels and flees in the opposite direction.
- A zombie compares the distance to the player and every civilian, then pursues the closest target.
- Zombies repel one another slightly so they remain distinguishable instead of occupying exactly the same point.

The population graph records the number of civilians and zombies once per second and displays recent samples.

## 4. How the Python classes fit together

All of the important simulation code is in `simulation.py`. It does not import Tkinter, so I can test the game rules separately from the window.

### `Entity`

The base dataclass shared by movable game objects. It stores position, velocity, and radius, and provides movement and boundary behavior.

### `Civilian(Entity)`

Represents a human NPC. Each civilian has an individual speed, wandering direction, direction timer, and infection level. Its update method searches for nearby zombies and decides whether to wander or flee.

### `Zombie(Entity)`

Represents an infected NPC. Each zombie has a randomized speed that increases slightly with elapsed time. Its update method finds the closest eligible target, moves toward that target, and applies separation from other zombies.

### `Player(Entity)`

Represents the user-controlled responder. It tracks speed, health, damage cooldown, firing cooldown, and keyboard-driven movement.

### `Bullet(Entity)`

Represents one projectile. A bullet moves in its firing direction at a fixed speed and disappears after 1.25 seconds, after leaving the game area, or after striking a zombie.

### `Simulation`

This is the class that coordinates the model. It owns the objects and handles game state (`ready`, `running`, `paused`, `won`, or `lost`), timed spawning, collisions, rescue, infection, damage, shooting, graph history, and ending conditions.

### `ZombieGameApp`

`main.py` contains the Tkinter window. It draws the Python objects, sends keyboard and mouse input to `Simulation`, and displays counters, health, status messages, and the population graph. The UI is separate from the rules, so the game model stays in Python and can be tested on its own.

## 5. Keeping storage separate from the game rules

I did not want the simulation to care whether a checkpoint was kept in memory, a file, a database, or another service. The design uses dependency injection and one abstract storage interface.

### `StateStore`

`state_storage.py` defines the abstract `StateStore` class with three operations:

- `save(state)` stores one complete checkpoint.
- `load()` returns the latest checkpoint or `None`.
- `clear()` removes the checkpoint.

`StateStore` is the only storage API used by `Simulation`. The simulation converts agents, environment values, and runtime values into ordinary dictionaries. It never opens a file or calls JSON directly.

### `InMemoryStateStore`

This adapter keeps a deep copy of the checkpoint in the Python process. It is fast and useful for the normal game window, tests, and temporary checkpoints. The deep copy matters because later changes to game objects should not change an older checkpoint.

### `JsonFileStateStore`

This adapter writes the same dictionary to a JSON file. It writes to a temporary file and then replaces the target file, which helps prevent a half-written checkpoint if the program stops during a save. JSON also makes the saved state easy to inspect and keeps it available after the program restarts.

### `NullStateStore`

This no-op adapter allows the simulation to run without persistence when a caller does not need checkpoints.

### Why this separation works

`Simulation.save_checkpoint()` calls only `self.state_store.save(...)`, and `Simulation.load_checkpoint()` calls only `self.state_store.load()`. The simulation does not know which concrete class is behind that object. That gives me a few useful results:

1. The game rules stay unchanged when storage changes.
2. Each storage adapter can be tested independently.
3. A future SQLite or network adapter only needs to implement `StateStore`.
4. The UI can choose a backend at startup using `--json-checkpoint` without changing agent behavior.

The state dictionary is divided into `environment`, `agents`, and `runtime`. It includes positions, velocities, health, infection, bullets, timers, score, game state, population history, and the random-generator state needed to continue the simulation consistently.

`test_storage.py` runs the same round-trip test with both `InMemoryStateStore` and `JsonFileStateStore`, demonstrating that the simulation layer is independent of the storage solution.

## 6. The update loop

Tkinter calls the app's `_tick()` method about 30 times per second. Each tick sends a small time step to `Simulation.update()` and then redraws the current state.

The simulation updates movement using elapsed time, so movement remains approximately consistent across computers. The time step is capped to prevent a delayed frame from making objects jump across the map.

## 7. Collision rules

Every character is represented by a center point and collision radius. Two entities touch when the distance between their centers is smaller than the sum of their radii.

- Player + civilian: rescue the civilian.
- Zombie + civilian: increase infection.
- Zombie + player: remove health and push the player away.
- Bullet + zombie: remove the bullet and zombie.

The engine resolves each interaction in dedicated methods, keeping population changes explicit and easy to defend.

## 8. What is on the screen

The Tkinter window contains:

- a dark city map drawn on a `Canvas`
- civilian, zombie, player, and bullet shapes
- start, pause, and restart controls
- live human, zombie, rescued, and health values
- a population-history graph
- a status message and controls guide

I did not use downloaded images, a game engine, or third-party packages. The only UI dependency is Python's standard-library Tkinter module.

## 9. Important balancing values

The constants near the top of `simulation.py` make the prototype easy to tune:

- starting civilians: `14`
- starting zombies: `3`
- rescue target: `8`
- maximum active zombies: `28`
- player speed: `190` pixels per second
- zombie speed: approximately `34–62` pixels per second, increasing with time
- civilian speed: approximately `42–64` pixels per second
- player damage per zombie contact: `18`
- firing cooldown: `0.18` seconds

## 10. File map

| File | Purpose |
| --- | --- |
| `simulation.py` | Python classes, rules, agent behavior, collisions, population changes, and game state |
| `main.py` | Tkinter interface, rendering, input, graph, and headless smoke-test entry point |
| `state_storage.py` | `StateStore` interface plus in-memory, JSON-file, and no-op adapters |
| `test_storage.py` | Round-trip and backend-independence tests |
| `requirements.txt` | Documents that no third-party packages are required |
| `README.md` | Repository overview, setup instructions, controls, and assignment checklist |
| `PROJECT_GUIDE.md` | Detailed explanation for reviewing or defending the project |
| `STAGE2_GUIDE.md` | Stage 2 design, database schema, parallelism, experiments, and demonstration plan |

The submitted game source is Python. The repository does not use HTML, JavaScript, Java, CSS, or a browser runtime.

## 11. How this meets the assignment

- **Concrete:** it has a player objective, controls, feedback, and ending conditions.
- **Runnable:** `python3 main.py` starts the desktop application, and `python3 main.py --headless` verifies the engine without a display.
- **Simple but nontrivial:** the code includes autonomous agents, targeting, fleeing, infection, conversion, collisions, escalating spawns, and population tracking.
- **Varying population dynamics:** people are rescued or infected, zombies are created or eliminated, and both populations are graphed over time.
- **Python-first:** the essential model is implemented in readable Python classes, independent of the interface.
- **Storage decoupling:** the same simulation state can be saved to memory or JSON through one abstract interface.
- **Available for review:** the source files and documentation are in this repository.

## 12. A short demonstration plan

For a short class demonstration, I would:

1. Run `python3 main.py` and show the starting counts of 14 civilians and 3 zombies.
2. Start the game and point out that civilians wander independently.
3. Let a zombie approach a civilian so the red infection ring becomes visible.
4. Rescue one civilian and show the count and graph change.
5. Shoot one zombie and show the zombie count change.
6. Explain that infection converts one object type into another.
7. Show `Entity`, `Civilian`, `Zombie`, `Player`, `Bullet`, and `Simulation` in `simulation.py`.
8. Save a checkpoint, restart the simulation object, and load the checkpoint.
9. Explain that the same simulation works with the in-memory adapter and the JSON-file adapter.
10. Explain the escalating spawn timer and the win/loss rules.
