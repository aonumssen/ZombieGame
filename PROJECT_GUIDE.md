# Outbreak: Last Light — Python Project Guide

This guide explains the Python implementation and how it satisfies Zombie Game — Stage 1.

## 1. Project idea

**Outbreak: Last Light** is a real-time rescue game and population simulation. The player is an emergency responder in a city containing civilians and zombies. The goal is to reach and rescue 8 civilians before the responder is defeated or all civilians become infected.

The prototype is intentionally simple enough to explain and defend, but it is not trivial: autonomous entities move independently, zombies select targets, civilians flee danger, infection converts humans into zombies, new zombies spawn over time, bullets collide with zombies, and the interface records population history.

## 2. How to play

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

The player wins after rescuing 8 civilians. The player loses when health reaches zero or when no civilians remain in the city.

The Python engine can also be checked without a window:

```bash
python3 main.py --headless
```

## 3. Population dynamics

The assignment asks for varying human and/or zombie populations. This game models both.

### Civilian population

The game begins with 14 civilians. The number changes in two ways:

1. A civilian leaves the active population when rescued by the player.
2. A civilian leaves the human population when infection reaches 100%.

### Zombie population

The game begins with 3 zombies. The number changes in three ways:

1. A new zombie is created when a civilian becomes fully infected.
2. Zombies enter from a random map edge on a timer.
3. A zombie is removed when hit by a bullet.

The normal spawn interval begins at 5.8 seconds and gradually falls toward a minimum of 2.25 seconds. This creates escalating difficulty instead of a static simulation.

### Infection and behavior

When a zombie stays close enough to a civilian, that civilian's infection meter increases. A red ring in the interface shows infection progress. If contact stops, infection slowly decreases. At 100%, the `Civilian` object is removed and a new `Zombie` object is created in the same location.

- Civilians normally wander in random directions.
- A civilian detects the nearest zombie within 150 pixels and flees in the opposite direction.
- A zombie compares the distance to the player and every civilian, then pursues the closest target.
- Zombies repel one another slightly so they remain distinguishable instead of occupying exactly the same point.

The population graph records the number of civilians and zombies once per second and displays recent samples.

## 4. Object-oriented Python design

All essential simulation code is in `simulation.py`. It does not import Tkinter, which makes it testable independently from the interface.

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

Coordinates the complete model. It owns all objects and handles game state (`ready`, `running`, `paused`, `won`, or `lost`), timed spawning, collisions, rescue, infection, damage, shooting, graph history, and ending conditions.

### `ZombieGameApp`

`main.py` contains the Tkinter view/controller. It draws the Python objects, sends keyboard and mouse input to `Simulation`, and displays counters, health, status messages, and the population graph. The UI is separate from the rules, so the essential simulation is plainly Python code.

## 5. The game loop

Tkinter calls the app's `_tick()` method about 30 times per second. Each tick sends a small time step to `Simulation.update()` and then redraws the current state.

The simulation updates movement using elapsed time, so movement remains approximately consistent across computers. The time step is capped to prevent a delayed frame from making objects jump across the map.

## 6. Collision rules

Every character is represented by a center point and collision radius. Two entities touch when the distance between their centers is smaller than the sum of their radii.

- Player + civilian: rescue the civilian.
- Zombie + civilian: increase infection.
- Zombie + player: remove health and push the player away.
- Bullet + zombie: remove the bullet and zombie.

The engine resolves each interaction in dedicated methods, keeping population changes explicit and easy to defend.

## 7. Interface and visual design

The Tkinter window contains:

- a dark city map drawn on a `Canvas`
- civilian, zombie, player, and bullet shapes
- start, pause, and restart controls
- live human, zombie, rescued, and health values
- a population-history graph
- a status message and controls guide

The project uses no downloaded images, game engines, or third-party packages. The only UI dependency is Python's standard-library Tkinter module.

## 8. Important balancing values

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

## 9. File map

| File | Purpose |
| --- | --- |
| `simulation.py` | Python classes, rules, AI behavior, collisions, population changes, and game state |
| `main.py` | Tkinter interface, rendering, input, graph, and headless smoke-test entry point |
| `requirements.txt` | Documents that no third-party packages are required |
| `README.md` | Repository overview, setup instructions, controls, and assignment checklist |
| `PROJECT_GUIDE.md` | Detailed explanation for reviewing or defending the project |

The game source is Python-only. The repository does not use HTML, JavaScript, Java, CSS, or a browser runtime.

## 10. How it satisfies the assignment

- **Concrete:** it contains a complete player objective, controls, feedback, and ending conditions.
- **Runnable:** `python3 main.py` starts the desktop application, and `python3 main.py --headless` verifies the engine without a display.
- **Simple but nontrivial:** the code includes autonomous agents, targeting, fleeing, infection, conversion, collisions, escalating spawns, and population tracking.
- **Varying population dynamics:** people are rescued or infected, zombies are created or eliminated, and both populations are graphed over time.
- **Python-first:** the essential model is implemented in readable Python classes, independent of the interface.
- **GitHub-ready:** all source files and documentation are available in the repository.

## 11. Suggested demonstration

For a short class demonstration:

1. Run `python3 main.py` and show the starting counts of 14 civilians and 3 zombies.
2. Start the game and point out that civilians wander independently.
3. Let a zombie approach a civilian so the red infection ring becomes visible.
4. Rescue one civilian and show the count and graph change.
5. Shoot one zombie and show the zombie count change.
6. Explain that infection converts one object type into another.
7. Show `Entity`, `Civilian`, `Zombie`, `Player`, `Bullet`, and `Simulation` in `simulation.py`.
8. Explain the escalating spawn timer and the win/loss rules.
