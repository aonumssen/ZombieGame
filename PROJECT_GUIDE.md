# How Outbreak Last Light works

## Playing the campaign

Run `python3 main.py` and click **Start game**. Move with WASD or the arrow keys, aim with the mouse, and click or press Space to fire. Touch a civilian to rescue them. Press P to pause.

Each level starts with 14 civilians, and you need to reach eight of them. Once you do, the game stops the action so you can choose when to start the next level. A new level refills health and starts with a fresh group of civilians and zombies. Clear Level 10 to win. Taking too much damage or letting the horde turn too many civilians ends the run.

| Setting | Value |
| --- | --- |
| Starting horde | 3 on Level 1, plus 2 per level |
| Starting reinforcement interval | 5.8 seconds on Level 1, down to 2.2 seconds on Level 10 |
| Reinforcement limit | Edge spawns stop while 28 or more zombies are active. Civilians can still turn. |
| Player speed | 190 pixels per second |
| Civilian speed | 42–64 pixels per second |
| Damage per hit | 18 health, with a short cooldown between hits |
| Time between shots | 0.18 seconds |

Later levels also increase zombie speed. Reinforcements pick a random map edge, and the wait between spawns gets shorter as the level goes on.

## What happens each tick

`ZombieGameApp` in `main.py` passes input to `Simulation` about 30 times a second and draws the result on a Tkinter canvas. The window shows the current level, rescue count, health, and a graph of the two populations.

- `Entity` supplies position, velocity, radius, and movement for the objects on the map.
- `Civilian` wanders until a zombie comes within 150 pixels, then moves away from the nearest one. Close contact fills the red infection ring. It drains when the civilian gets away. A full ring turns the civilian into a zombie in the same spot.
- `Zombie` chases the closest civilian or the player. Nearby zombies also push away from one another a little, which helps keep the horde visible.
- `Player` tracks health and movement, plus the cooldowns for taking damage and firing. Zombie contact pushes the player away. Touching a civilian takes that civilian off the map and adds to the rescue count.
- `Bullet` disappears on impact, after 1.25 seconds, or after leaving the map. A hit also removes the zombie.

The simulation moves the objects, checks contacts using their positions and radii, and decides whether to spawn another zombie or end the level. Run `python3 main.py --headless` to check the engine without the window.

## Saving the game

`Simulation` takes a `StateStore` when it starts. The store exposes three methods: `save()`, `load()`, and `clear()`. The simulation builds the checkpoint dictionary and the store decides where it goes.

| Store | What it does |
| --- | --- |
| `InMemoryStateStore` | Keeps a deep copy while the game is open. Later moves cannot change that copy. |
| `JsonFileStateStore` | Writes to a temporary file, then replaces the old checkpoint. |
| `NullStateStore` | Gives callers a way to run the simulation without storing checkpoints. |

To keep a checkpoint between sessions, launch with `python3 main.py --json-checkpoint save/checkpoint.json`. The checkpoint includes positions, health, level progress, timers, population history, and the random generator's state so play can continue from the same point. An old single-level victory save loads as a Level 1 clear.

## Demo

Start Level 1 and watch the initial 14 civilians and three zombies. Rescue someone and watch the count change. The red ring shows when a civilian is close to turning. Save, move the player, and load to see the position and progress restored.

Run `python3 -m unittest -v test_storage.py test_campaign.py` for checkpoint and campaign tests. The [Stage 2 guide](STAGE2_GUIDE.md) covers the larger headless simulation.
