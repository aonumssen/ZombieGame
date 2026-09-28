# Outbreak: Last Light

A simple, runnable zombie rescue game created for **Zombie Game — Stage 1**. The project uses plain HTML, CSS, and JavaScript, so it runs in a browser without installing packages.

GitHub repository: <https://github.com/aonumssen/ZombieGame>

## Group members

> Replace this line with the full names of every group member before submitting.

- Your Name

## Play the game

### From GitHub Pages

After publishing the repository with GitHub Pages, open the Pages link shown in the repository settings.

### On your computer

Either open `index.html` directly in a browser, or start a small local web server from this folder:

```bash
python3 -m http.server 8000
```

Then visit <http://localhost:8000>.

## Controls

- **WASD** or **arrow keys** — move the responder
- **Space** or **mouse click** — fire toward the pointer
- **P** or the **Pause** button — pause/resume

## Goal and simulation rules

Rescue 8 civilians by touching them before the city is overrun.

- Civilians wander and flee when a zombie comes close.
- Zombies chase the nearest target, either a civilian or the player.
- A civilian who stays in contact with a zombie becomes infected and joins the zombie population.
- New zombies enter from the edge of the map over time, and the spawn rate increases.
- The player can eliminate zombies, but direct contact costs health.
- The game ends in victory after 8 rescues, or in defeat if the player loses all health or no civilians remain.

The live population graph makes the changing human and zombie populations visible while the simulation runs.

## Object-oriented design

The JavaScript models the simulation with these classes:

- `Entity` — shared position and movement behavior
- `Civilian` — wandering, fleeing, and infection behavior
- `Zombie` — targeting and pursuit behavior
- `Player` — input, movement, health, and firing
- `Bullet` — projectile movement and lifetime
- `Game` — the game loop, collisions, population changes, scoring, and interface

## Files

- `index.html` — page structure and game interface
- `styles.css` — visual design and responsive layout
- `game.js` — simulation and gameplay code

## Publish with GitHub Pages

1. Create a new GitHub repository and add these files.
2. Commit and push them to the `main` branch.
3. In the repository, open **Settings → Pages**.
4. Under **Build and deployment**, choose **Deploy from a branch**.
5. Select the `main` branch and `/ (root)`, then click **Save**.
6. GitHub will display the public game link after deployment finishes.

## Assignment requirement checklist

- [x] Concrete, runnable prototype
- [x] Nontrivial human and zombie population dynamics
- [x] Interactive game controls and clear win/loss states
- [x] Live population counts and history graph
- [x] Object-oriented simulation classes
- [ ] Full names of all group members added to this README
- [x] Repository submitted through GitHub
