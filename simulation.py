"""Core rules for the Python version of Outbreak: Last Light.

This module intentionally has no GUI imports.  The simulation can therefore be
tested, explained, or reused by a different interface without changing the
game rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Any, Iterable, Mapping, Optional

from state_storage import NullStateStore, StateData, StateStore


WORLD_WIDTH = 760
WORLD_HEIGHT = 560
WORLD_MARGIN = 24
STARTING_CIVILIANS = 14
STARTING_ZOMBIES = 3
RESCUE_TARGET = 8
MAX_ZOMBIES = 28


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def distance(a: "Entity", b: "Entity") -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def direction(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy)
    if length == 0:
        return 0.0, 0.0
    return dx / length, dy / length


@dataclass
class Entity:
    """Shared position and movement state for every game object."""

    x: float
    y: float
    radius: float
    vx: float = 0.0
    vy: float = 0.0

    def move(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt

    def keep_inside_world(self) -> None:
        self.x = clamp(self.x, WORLD_MARGIN, WORLD_WIDTH - WORLD_MARGIN)
        self.y = clamp(self.y, WORLD_MARGIN, WORLD_HEIGHT - WORLD_MARGIN)


class Civilian(Entity):
    """A human who wanders, flees nearby zombies, and can become infected."""

    def __init__(self, x: float, y: float, rng: random.Random) -> None:
        super().__init__(x, y, radius=9)
        self.speed = rng.uniform(42, 64)
        self.infection = 0.0
        self.wander_time = rng.uniform(0.0, 1.5)
        self.wander_angle = rng.uniform(0.0, math.tau)

    def update(self, dt: float, zombies: list["Zombie"], rng: random.Random) -> None:
        nearest = min(zombies, key=lambda z: distance(self, z), default=None)
        if nearest is not None and distance(self, nearest) < 150:
            dx, dy = direction(self.x - nearest.x, self.y - nearest.y)
            desired_x, desired_y = dx * self.speed, dy * self.speed
        else:
            self.wander_time -= dt
            if self.wander_time <= 0:
                self.wander_time = rng.uniform(0.8, 2.2)
                self.wander_angle += rng.uniform(-1.3, 1.3)
            desired_x = math.cos(self.wander_angle) * self.speed * 0.55
            desired_y = math.sin(self.wander_angle) * self.speed * 0.55

        self.vx += (desired_x - self.vx) * min(1.0, dt * 3.2)
        self.vy += (desired_y - self.vy) * min(1.0, dt * 3.2)
        self.move(dt)
        self.keep_inside_world()


class Zombie(Entity):
    """A pursuer that seeks the closest civilian or player."""

    def __init__(self, x: float, y: float, rng: random.Random, level: float = 0) -> None:
        super().__init__(x, y, radius=12)
        self.speed = rng.uniform(34, 46) + min(level * 0.55, 16)
        self.wobble = rng.uniform(0.0, math.tau)

    def update(
        self,
        dt: float,
        player: "Player",
        civilians: list[Civilian],
        zombies: list["Zombie"],
    ) -> None:
        targets: list[Entity] = [player, *civilians]
        target = min(targets, key=lambda candidate: distance(self, candidate), default=player)
        dx, dy = direction(target.x - self.x, target.y - self.y)

        # A small separation force keeps a large horde readable instead of making
        # every zombie occupy exactly the same pixel.
        separation_x = 0.0
        separation_y = 0.0
        for other in zombies:
            if other is self:
                continue
            gap = distance(self, other)
            if 0 < gap < 28:
                away_x, away_y = direction(self.x - other.x, self.y - other.y)
                force = (28 - gap) / 28
                separation_x += away_x * force
                separation_y += away_y * force

        self.wobble += dt * 3.0
        wobble_x = math.cos(self.wobble) * 0.08
        wobble_y = math.sin(self.wobble) * 0.08
        steer_x, steer_y = direction(dx + separation_x * 0.8 + wobble_x, dy + separation_y * 0.8 + wobble_y)
        self.vx = steer_x * self.speed
        self.vy = steer_y * self.speed
        self.move(dt)
        self.keep_inside_world()


class Player(Entity):
    """The responder controlled by the keyboard and mouse."""

    def __init__(self) -> None:
        super().__init__(WORLD_WIDTH / 2, WORLD_HEIGHT / 2, radius=13)
        self.speed = 190.0
        self.health = 100.0
        self.fire_cooldown = 0.0
        self.damage_cooldown = 0.0

    def update(self, dt: float, keys: Iterable[str]) -> None:
        pressed = set(keys)
        horizontal = (1 if "d" in pressed or "right" in pressed else 0) - (
            1 if "a" in pressed or "left" in pressed else 0
        )
        vertical = (1 if "s" in pressed or "down" in pressed else 0) - (
            1 if "w" in pressed or "up" in pressed else 0
        )
        move_x, move_y = direction(horizontal, vertical)
        self.vx = move_x * self.speed
        self.vy = move_y * self.speed
        self.move(dt)
        self.keep_inside_world()
        self.fire_cooldown = max(0.0, self.fire_cooldown - dt)
        self.damage_cooldown = max(0.0, self.damage_cooldown - dt)

    def take_damage(self, amount: float) -> bool:
        if self.damage_cooldown > 0:
            return False
        self.health = max(0.0, self.health - amount)
        self.damage_cooldown = 0.72
        return True


class Bullet(Entity):
    """A short-lived projectile fired by the player."""

    def __init__(self, x: float, y: float, angle: float) -> None:
        super().__init__(x, y, radius=4)
        speed = 500.0
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = 1.25

    def update(self, dt: float) -> None:
        self.move(dt)
        self.life -= dt

    @property
    def expired(self) -> bool:
        return self.life <= 0 or not (
            -20 <= self.x <= WORLD_WIDTH + 20 and -20 <= self.y <= WORLD_HEIGHT + 20
        )


class Simulation:
    """State machine and rules for one complete game session.

    ``state_store`` is an injected interface.  The simulation only knows how
    to produce and consume a plain state dictionary; it does not know whether
    that dictionary is held in memory, written to JSON, or stored elsewhere.
    """

    def __init__(
        self,
        seed: Optional[int] = None,
        state_store: Optional[StateStore] = None,
        checkpoint_interval: float = 0.0,
    ) -> None:
        self.rng = random.Random(seed)
        self.state_store = state_store or NullStateStore()
        self.checkpoint_interval = max(0.0, checkpoint_interval)
        self.player = Player()
        self.civilians: list[Civilian] = []
        self.zombies: list[Zombie] = []
        self.bullets: list[Bullet] = []
        self.population_history: list[tuple[int, int]] = []
        self.state = "ready"
        self.elapsed = 0.0
        self.rescued = 0
        self.spawn_timer = 0.0
        self.history_timer = 0.0
        self.checkpoint_timer = 0.0
        self.last_event = "Press Start to begin the rescue."
        self.reset()

    def reset(self) -> None:
        self.player = Player()
        self.civilians = []
        self.zombies = []
        self.bullets = []
        self.population_history = []
        self.state = "ready"
        self.elapsed = 0.0
        self.rescued = 0
        self.spawn_timer = 0.0
        self.history_timer = 0.0
        self.checkpoint_timer = 0.0
        self.last_event = "Press Start to begin the rescue."

        for _ in range(STARTING_CIVILIANS):
            x, y = self._random_point(min_distance=105)
            self.civilians.append(Civilian(x, y, self.rng))
        for _ in range(STARTING_ZOMBIES):
            self.zombies.append(self._spawn_edge_zombie())
        self._record_history(force=True)

    def start(self) -> None:
        if self.state in {"won", "lost"}:
            self.reset()
        if self.state == "ready":
            self.state = "running"
            self.last_event = "Rescue civilians and survive the outbreak."
        elif self.state == "paused":
            self.state = "running"
            self.last_event = "Simulation resumed."

    def pause(self) -> None:
        if self.state == "running":
            self.state = "paused"
            self.last_event = "Simulation paused."

    def toggle_pause(self) -> None:
        if self.state == "running":
            self.pause()
        elif self.state in {"paused", "ready"}:
            self.start()

    def fire(self, aim_x: float, aim_y: float) -> bool:
        if self.state != "running" or self.player.fire_cooldown > 0:
            return False
        angle = math.atan2(aim_y - self.player.y, aim_x - self.player.x)
        muzzle_x = self.player.x + math.cos(angle) * 17
        muzzle_y = self.player.y + math.sin(angle) * 17
        self.bullets.append(Bullet(muzzle_x, muzzle_y, angle))
        self.player.fire_cooldown = 0.18
        return True

    def update(self, dt: float, keys: Iterable[str] = (), aim: tuple[float, float] = (0, 0)) -> None:
        if self.state != "running":
            return
        dt = clamp(dt, 0.0, 0.08)
        self.elapsed += dt
        self.player.update(dt, keys)
        for civilian in self.civilians:
            civilian.update(dt, self.zombies, self.rng)
        for zombie in self.zombies:
            zombie.update(dt, self.player, self.civilians, self.zombies)
        for bullet in self.bullets:
            bullet.update(dt)

        self._resolve_bullets()
        self._resolve_civilian_contacts(dt)
        self._resolve_player_contacts()
        self._spawn_over_time(dt)
        self._record_history()
        self._check_end_state()
        self._maybe_checkpoint(dt)

    def snapshot(self) -> dict[str, object]:
        """Return simple values suitable for a UI, test, or logger."""
        return {
            "state": self.state,
            "elapsed": self.elapsed,
            "humans": len(self.civilians),
            "zombies": len(self.zombies),
            "rescued": self.rescued,
            "health": self.player.health,
            "message": self.last_event,
        }

    def save_checkpoint(self) -> StateData:
        """Serialize all live state and send it through the injected store."""
        state = self.to_state()
        self.state_store.save(state)
        return state

    def load_checkpoint(self) -> bool:
        """Restore the latest checkpoint from the injected store, if present."""
        state = self.state_store.load()
        if state is None:
            return False
        self._restore_state(state)
        return True

    def to_state(self) -> StateData:
        """Convert agents, environment, and runtime into storage-neutral data."""
        return {
            "schema_version": 1,
            "environment": {
                "width": WORLD_WIDTH,
                "height": WORLD_HEIGHT,
                "margin": WORLD_MARGIN,
            },
            "runtime": {
                "state": self.state,
                "elapsed": self.elapsed,
                "rescued": self.rescued,
                "spawn_timer": self.spawn_timer,
                "history_timer": self.history_timer,
                "checkpoint_timer": self.checkpoint_timer,
                "last_event": self.last_event,
                "population_history": [list(point) for point in self.population_history],
                "random_state": self._random_state_to_data(),
            },
            "agents": {
                "player": self._entity_to_data(
                    self.player,
                    health=self.player.health,
                    speed=self.player.speed,
                    fire_cooldown=self.player.fire_cooldown,
                    damage_cooldown=self.player.damage_cooldown,
                ),
                "civilians": [
                    self._entity_to_data(
                        civilian,
                        speed=civilian.speed,
                        infection=civilian.infection,
                        wander_time=civilian.wander_time,
                        wander_angle=civilian.wander_angle,
                    )
                    for civilian in self.civilians
                ],
                "zombies": [
                    self._entity_to_data(zombie, speed=zombie.speed, wobble=zombie.wobble)
                    for zombie in self.zombies
                ],
                "bullets": [
                    self._entity_to_data(bullet, life=bullet.life) for bullet in self.bullets
                ],
            },
        }

    def _restore_state(self, state: Mapping[str, Any]) -> None:
        if state.get("schema_version") != 1:
            raise ValueError("Unsupported simulation state schema")
        environment = state.get("environment", {})
        if (
            environment.get("width") != WORLD_WIDTH
            or environment.get("height") != WORLD_HEIGHT
            or environment.get("margin") != WORLD_MARGIN
        ):
            raise ValueError("Saved state belongs to a different simulation environment")

        runtime = state["runtime"]
        agents = state["agents"]
        if not isinstance(runtime, Mapping) or not isinstance(agents, Mapping):
            raise ValueError("Simulation state is missing runtime or agent data")

        random_state = runtime.get("random_state")

        player_data = agents["player"]
        if not isinstance(player_data, Mapping):
            raise ValueError("Simulation state is missing player data")
        self.player = Player()
        self._apply_entity_data(self.player, player_data)
        self.player.speed = float(player_data["speed"])
        self.player.health = float(player_data["health"])
        self.player.fire_cooldown = float(player_data["fire_cooldown"])
        self.player.damage_cooldown = float(player_data["damage_cooldown"])

        self.civilians = []
        for civilian_data in agents["civilians"]:
            civilian = Civilian(float(civilian_data["x"]), float(civilian_data["y"]), self.rng)
            self._apply_entity_data(civilian, civilian_data)
            civilian.speed = float(civilian_data["speed"])
            civilian.infection = float(civilian_data["infection"])
            civilian.wander_time = float(civilian_data["wander_time"])
            civilian.wander_angle = float(civilian_data["wander_angle"])
            self.civilians.append(civilian)

        self.zombies = []
        for zombie_data in agents["zombies"]:
            zombie = Zombie(float(zombie_data["x"]), float(zombie_data["y"]), self.rng)
            self._apply_entity_data(zombie, zombie_data)
            zombie.speed = float(zombie_data["speed"])
            zombie.wobble = float(zombie_data["wobble"])
            self.zombies.append(zombie)

        self.bullets = []
        for bullet_data in agents["bullets"]:
            bullet = Bullet(float(bullet_data["x"]), float(bullet_data["y"]), 0.0)
            self._apply_entity_data(bullet, bullet_data)
            bullet.life = float(bullet_data["life"])
            self.bullets.append(bullet)

        # Constructors use randomness for default values. Restore the exact
        # generator state after reconstruction so the next simulation step is
        # identical to the step that would have followed the original save.
        if isinstance(random_state, Mapping):
            internal = random_state.get("internal")
            if isinstance(internal, list):
                self.rng.setstate(
                    (
                        int(random_state["version"]),
                        tuple(int(value) for value in internal),
                        random_state.get("gauss"),
                    )
                )

        self.state = str(runtime["state"])
        self.elapsed = float(runtime["elapsed"])
        self.rescued = int(runtime["rescued"])
        self.spawn_timer = float(runtime["spawn_timer"])
        self.history_timer = float(runtime["history_timer"])
        self.checkpoint_timer = float(runtime.get("checkpoint_timer", 0.0))
        self.last_event = str(runtime["last_event"])
        self.population_history = [
            (int(point[0]), int(point[1])) for point in runtime["population_history"]
        ]

    @staticmethod
    def _entity_to_data(entity: Entity, **extra: Any) -> dict[str, Any]:
        return {
            "x": entity.x,
            "y": entity.y,
            "radius": entity.radius,
            "vx": entity.vx,
            "vy": entity.vy,
            **extra,
        }

    @staticmethod
    def _apply_entity_data(entity: Entity, data: Mapping[str, Any]) -> None:
        entity.x = float(data["x"])
        entity.y = float(data["y"])
        entity.radius = float(data["radius"])
        entity.vx = float(data["vx"])
        entity.vy = float(data["vy"])

    def _random_state_to_data(self) -> dict[str, Any]:
        version, internal, gauss = self.rng.getstate()
        return {"version": version, "internal": list(internal), "gauss": gauss}

    def _maybe_checkpoint(self, dt: float) -> None:
        if self.checkpoint_interval <= 0:
            return
        self.checkpoint_timer += dt
        if self.checkpoint_timer >= self.checkpoint_interval:
            self.checkpoint_timer = 0.0
            self.save_checkpoint()

    def _random_point(self, min_distance: float = 0) -> tuple[float, float]:
        for _ in range(80):
            x = self.rng.uniform(WORLD_MARGIN + 12, WORLD_WIDTH - WORLD_MARGIN - 12)
            y = self.rng.uniform(WORLD_MARGIN + 12, WORLD_HEIGHT - WORLD_MARGIN - 12)
            if math.hypot(x - self.player.x, y - self.player.y) >= min_distance:
                return x, y
        return WORLD_MARGIN + 20, WORLD_MARGIN + 20

    def _spawn_edge_zombie(self) -> Zombie:
        side = self.rng.choice(("top", "right", "bottom", "left"))
        if side == "top":
            x, y = self.rng.uniform(30, WORLD_WIDTH - 30), WORLD_MARGIN
        elif side == "right":
            x, y = WORLD_WIDTH - WORLD_MARGIN, self.rng.uniform(30, WORLD_HEIGHT - 30)
        elif side == "bottom":
            x, y = self.rng.uniform(30, WORLD_WIDTH - 30), WORLD_HEIGHT - WORLD_MARGIN
        else:
            x, y = WORLD_MARGIN, self.rng.uniform(30, WORLD_HEIGHT - 30)
        return Zombie(x, y, self.rng, self.elapsed)

    def _resolve_bullets(self) -> None:
        remaining: list[Bullet] = []
        for bullet in self.bullets:
            if bullet.expired:
                continue
            hit = False
            for zombie in self.zombies:
                if distance(bullet, zombie) <= bullet.radius + zombie.radius:
                    self.zombies.remove(zombie)
                    self.last_event = "A zombie was eliminated."
                    hit = True
                    break
            if not hit:
                remaining.append(bullet)
        self.bullets = remaining

    def _resolve_civilian_contacts(self, dt: float) -> None:
        rescued_now: list[Civilian] = []
        infected_now: list[Civilian] = []
        for civilian in self.civilians:
            if distance(self.player, civilian) <= self.player.radius + civilian.radius + 5:
                rescued_now.append(civilian)
                continue
            nearest = min(self.zombies, key=lambda z: distance(civilian, z), default=None)
            if nearest is not None and distance(civilian, nearest) < civilian.radius + nearest.radius + 3:
                civilian.infection = min(1.0, civilian.infection + dt * 0.82)
            else:
                civilian.infection = max(0.0, civilian.infection - dt * 0.16)
            if civilian.infection >= 1.0:
                infected_now.append(civilian)

        for civilian in rescued_now:
            if civilian in self.civilians:
                self.civilians.remove(civilian)
                self.rescued += 1
                self.last_event = f"Civilian rescued ({self.rescued}/{RESCUE_TARGET})."
        for civilian in infected_now:
            if civilian in self.civilians:
                self.civilians.remove(civilian)
                self.zombies.append(Zombie(civilian.x, civilian.y, self.rng, self.elapsed))
                self.last_event = "A civilian was infected and joined the horde."

    def _resolve_player_contacts(self) -> None:
        for zombie in self.zombies:
            if distance(self.player, zombie) <= self.player.radius + zombie.radius:
                if self.player.take_damage(18):
                    dx, dy = direction(self.player.x - zombie.x, self.player.y - zombie.y)
                    self.player.x += dx * 16
                    self.player.y += dy * 16
                    self.player.keep_inside_world()
                    self.last_event = "The responder was hit!"

    def _spawn_over_time(self, dt: float) -> None:
        self.spawn_timer += dt
        interval = max(2.25, 5.8 - self.elapsed * 0.035)
        if self.spawn_timer >= interval and len(self.zombies) < MAX_ZOMBIES:
            self.spawn_timer = 0.0
            self.zombies.append(self._spawn_edge_zombie())
            self.last_event = "A new zombie entered from the edge of town."

    def _record_history(self, force: bool = False) -> None:
        if not force:
            self.history_timer += 1 / 30
            if self.history_timer < 1.0:
                return
            self.history_timer = 0.0
        self.population_history.append((len(self.civilians), len(self.zombies)))
        self.population_history = self.population_history[-42:]

    def _check_end_state(self) -> None:
        if self.rescued >= RESCUE_TARGET:
            self.state = "won"
            self.last_event = "Victory! Eight civilians reached safety."
        elif self.player.health <= 0:
            self.state = "lost"
            self.last_event = "The responder was overwhelmed."
        elif not self.civilians:
            self.state = "lost"
            self.last_event = "No civilians remain in the city."
