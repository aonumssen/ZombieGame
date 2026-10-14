"""Tkinter interface for Outbreak: Last Light.

Run ``python3 main.py`` for the game, add ``--json-checkpoint PATH`` for
durable checkpoints, or use ``python3 main.py --headless`` for a quick
command-line smoke test of the Python simulation.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk
except ModuleNotFoundError:  # Some minimal Python builds omit the Tk bindings.
    class _TkUnavailable:
        class Tk:
            pass

    tk = _TkUnavailable()
    ttk = None

from simulation import (
    RESCUE_TARGET,
    WORLD_HEIGHT,
    WORLD_WIDTH,
    Simulation,
)
from state_storage import InMemoryStateStore, JsonFileStateStore, StateStore


BG = "#101722"
PANEL = "#182333"
PANEL_LIGHT = "#223149"
TEXT = "#e8f0fb"
MUTED = "#9fb0c7"
CYAN = "#63d7ff"
GREEN = "#70e58b"
RED = "#ff6b7a"
YELLOW = "#ffd166"


class ZombieGameApp(tk.Tk):
    """Interactive desktop view of the Python simulation."""

    def __init__(self, state_store: StateStore) -> None:
        super().__init__()
        self.title("Outbreak: Last Light — Python Edition")
        self.configure(bg=BG)
        self.resizable(False, False)

        self.simulation = Simulation(state_store=state_store)
        self.keys: set[str] = set()
        self.aim_x = WORLD_WIDTH / 2
        self.aim_y = WORLD_HEIGHT / 2
        self.running = True

        self._build_layout()
        self._bind_controls()
        self.after(33, self._tick)

    def _build_layout(self) -> None:
        outer = tk.Frame(self, bg=BG, padx=18, pady=18)
        outer.pack()

        self.canvas = tk.Canvas(
            outer,
            width=WORLD_WIDTH,
            height=WORLD_HEIGHT,
            bg="#0b111b",
            highlightthickness=1,
            highlightbackground="#31435f",
        )
        self.canvas.grid(row=0, column=0, rowspan=2)

        panel = tk.Frame(outer, bg=PANEL, width=285, height=WORLD_HEIGHT, padx=18, pady=18)
        panel.grid(row=0, column=1, padx=(16, 0), sticky="n")
        panel.pack_propagate(False)

        tk.Label(panel, text="OUTBREAK", bg=PANEL, fg=TEXT, font=("Helvetica", 22, "bold")).pack(anchor="w")
        tk.Label(panel, text="LAST LIGHT  •  PYTHON EDITION", bg=PANEL, fg=CYAN, font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(0, 18))

        self.start_button = ttk.Button(panel, text="Start game", command=self._start_game)
        self.start_button.pack(fill="x", pady=(0, 8))
        self.pause_button = ttk.Button(panel, text="Pause", command=self._toggle_pause)
        self.pause_button.pack(fill="x", pady=(0, 18))
        checkpoint_row = tk.Frame(panel, bg=PANEL)
        checkpoint_row.pack(fill="x", pady=(0, 16))
        ttk.Button(checkpoint_row, text="Save state", command=self._save_checkpoint).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(checkpoint_row, text="Load state", command=self._load_checkpoint).pack(side="left", expand=True, fill="x", padx=(4, 0))

        self.status_var = tk.StringVar()
        tk.Label(panel, textvariable=self.status_var, bg=PANEL, fg=TEXT, wraplength=245, justify="left", font=("Helvetica", 10)).pack(anchor="w", pady=(0, 16))

        self.humans_var = tk.StringVar()
        self.zombies_var = tk.StringVar()
        self.rescued_var = tk.StringVar()
        for variable in (self.humans_var, self.zombies_var, self.rescued_var):
            tk.Label(panel, textvariable=variable, bg=PANEL_LIGHT, fg=TEXT, anchor="w", padx=10, pady=7, font=("Helvetica", 11, "bold")).pack(fill="x", pady=2)

        tk.Label(panel, text="RESPONDER HEALTH", bg=PANEL, fg=MUTED, font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(16, 4))
        self.health_bar = tk.Canvas(panel, width=245, height=14, bg="#0e1520", highlightthickness=0)
        self.health_bar.pack(fill="x")

        tk.Label(panel, text="POPULATION HISTORY", bg=PANEL, fg=MUTED, font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(16, 4))
        self.graph = tk.Canvas(panel, width=245, height=120, bg="#0e1520", highlightthickness=0)
        self.graph.pack(fill="x")

        tk.Label(panel, text="Controls", bg=PANEL, fg=MUTED, font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(16, 4))
        tk.Label(panel, text="WASD / arrows  Move\nSpace / click  Fire\nP  Pause or resume\nSave/Load state  Checkpoint\nRescue civilians by touching them", bg=PANEL, fg=TEXT, justify="left", font=("Helvetica", 10)).pack(anchor="w")

        tk.Label(panel, text="Python standard library only\nSimulation engine is separate from UI", bg=PANEL, fg=MUTED, justify="left", font=("Helvetica", 9), wraplength=245).pack(anchor="w", side="bottom")

        ttk.Label(outer, text="Python OO simulation • live population dynamics • no third-party packages", background=BG, foreground=MUTED).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def _bind_controls(self) -> None:
        self.canvas.bind("<Motion>", self._aim)
        self.canvas.bind("<Button-1>", self._shoot)
        self.bind("<KeyPress>", self._key_down)
        self.bind("<KeyRelease>", self._key_up)
        self.focus_set()

    def _start_game(self) -> None:
        self.simulation.start()
        self.start_button.configure(text="Restart" if self.simulation.state in {"won", "lost"} else "Running")

    def _toggle_pause(self) -> None:
        self.simulation.toggle_pause()

    def _save_checkpoint(self) -> None:
        self.simulation.save_checkpoint()
        self.status_var.set("Checkpoint saved through the selected storage adapter.")

    def _load_checkpoint(self) -> None:
        if self.simulation.load_checkpoint():
            self.status_var.set("Checkpoint loaded through the selected storage adapter.")
        else:
            self.status_var.set("No checkpoint exists yet.")

    def _aim(self, event: tk.Event) -> None:
        self.aim_x = event.x
        self.aim_y = event.y

    def _shoot(self, event: tk.Event) -> None:
        self.aim_x = event.x
        self.aim_y = event.y
        self.simulation.fire(self.aim_x, self.aim_y)

    def _key_down(self, event: tk.Event) -> None:
        key = event.keysym.lower()
        if key in {"w", "a", "s", "d", "up", "down", "left", "right"}:
            self.keys.add(key)
        elif key == "space":
            self.simulation.fire(self.aim_x, self.aim_y)
        elif key == "p":
            self.simulation.toggle_pause()

    def _key_up(self, event: tk.Event) -> None:
        self.keys.discard(event.keysym.lower())

    def _tick(self) -> None:
        if self.running:
            self.simulation.update(1 / 30, self.keys, (self.aim_x, self.aim_y))
            self._draw_world()
            self._update_panel()
            self.after(33, self._tick)

    def _draw_world(self) -> None:
        self.canvas.delete("all")
        self._draw_city()

        for civilian in self.simulation.civilians:
            fill = "#f2f6ff" if civilian.infection < 0.45 else "#b8a5ff"
            self.canvas.create_oval(civilian.x - civilian.radius, civilian.y - civilian.radius, civilian.x + civilian.radius, civilian.y + civilian.radius, fill=fill, outline="#6aa4d8", width=2)
            if civilian.infection > 0:
                self.canvas.create_arc(civilian.x - 13, civilian.y - 13, civilian.x + 13, civilian.y + 13, start=90, extent=-360 * civilian.infection, style="arc", outline=RED, width=3)

        for zombie in self.simulation.zombies:
            self.canvas.create_oval(zombie.x - zombie.radius, zombie.y - zombie.radius, zombie.x + zombie.radius, zombie.y + zombie.radius, fill="#72c879", outline="#d7ffb0", width=1)
            self.canvas.create_oval(zombie.x - 6, zombie.y - 3, zombie.x - 2, zombie.y + 1, fill="#172b1a", outline="")
            self.canvas.create_oval(zombie.x + 2, zombie.y - 3, zombie.x + 6, zombie.y + 1, fill="#172b1a", outline="")

        for bullet in self.simulation.bullets:
            self.canvas.create_oval(bullet.x - 3, bullet.y - 3, bullet.x + 3, bullet.y + 3, fill=YELLOW, outline="")

        player = self.simulation.player
        angle = math.atan2(self.aim_y - player.y, self.aim_x - player.x)
        tip = (player.x + math.cos(angle) * 19, player.y + math.sin(angle) * 19)
        left = (player.x + math.cos(angle + 2.35) * 13, player.y + math.sin(angle + 2.35) * 13)
        right = (player.x + math.cos(angle - 2.35) * 13, player.y + math.sin(angle - 2.35) * 13)
        player_color = RED if player.damage_cooldown > 0.45 else YELLOW
        self.canvas.create_polygon(tip, left, right, fill=player_color, outline="#fff3b0", width=2)

        self.canvas.create_text(14, 14, text=f"TIME  {self.simulation.elapsed:05.1f}s", anchor="nw", fill=TEXT, font=("Helvetica", 10, "bold"))
        if self.simulation.state != "running":
            self._draw_overlay()

    def _draw_city(self) -> None:
        for x in range(0, WORLD_WIDTH, 48):
            self.canvas.create_line(x, 0, x, WORLD_HEIGHT, fill="#121e2d")
        for y in range(0, WORLD_HEIGHT, 48):
            self.canvas.create_line(0, y, WORLD_WIDTH, y, fill="#121e2d")
        for x, y, width, height in ((70, 85, 145, 80), (315, 55, 180, 105), (560, 110, 135, 72), (110, 335, 185, 96), (390, 315, 145, 125), (600, 370, 95, 110)):
            self.canvas.create_rectangle(x, y, x + width, y + height, fill="#152337", outline="#243954")

    def _draw_overlay(self) -> None:
        if self.simulation.state == "ready":
            title = "OUTBREAK: LAST LIGHT"
            subtitle = "Press Start game to begin"
        elif self.simulation.state == "paused":
            title = "PAUSED"
            subtitle = "Press P or Pause to resume"
        elif self.simulation.state == "won":
            title = "VICTORY"
            subtitle = "Press Restart to play again"
        else:
            title = "CITY OVERRUN"
            subtitle = "Press Restart to try again"
        self.canvas.create_rectangle(150, 220, WORLD_WIDTH - 150, 335, fill="#0c1420", outline="#526984", width=2)
        self.canvas.create_text(WORLD_WIDTH / 2, 260, text=title, fill=TEXT, font=("Helvetica", 24, "bold"))
        self.canvas.create_text(WORLD_WIDTH / 2, 296, text=subtitle, fill=CYAN, font=("Helvetica", 12))

    def _update_panel(self) -> None:
        snapshot = self.simulation.snapshot()
        self.status_var.set(snapshot["message"])
        self.humans_var.set(f"HUMANS   {snapshot['humans']:02d}")
        self.zombies_var.set(f"ZOMBIES  {snapshot['zombies']:02d}")
        self.rescued_var.set(f"RESCUED  {snapshot['rescued']:02d} / {RESCUE_TARGET}")
        self.pause_button.configure(text="Resume" if self.simulation.state == "paused" else "Pause")
        self.start_button.configure(text="Restart" if self.simulation.state in {"won", "lost"} else ("Start game" if self.simulation.state == "ready" else "Running"))

        self.health_bar.delete("all")
        health = snapshot["health"]
        self.health_bar.create_rectangle(0, 0, 245 * health / 100, 14, fill=GREEN if health > 35 else RED, outline="")
        self._draw_graph()

    def _draw_graph(self) -> None:
        self.graph.delete("all")
        history = self.simulation.population_history
        if len(history) < 2:
            return
        maximum = max(1, max(max(humans, zombies) for humans, zombies in history))
        width, height = 245, 120
        self.graph.create_line(8, height - 8, width - 8, height - 8, fill="#31445e")
        self.graph.create_text(10, 8, text="humans", anchor="nw", fill=CYAN, font=("Helvetica", 8))
        self.graph.create_text(width - 10, 8, text="zombies", anchor="ne", fill=RED, font=("Helvetica", 8))
        for index, color, position in ((0, CYAN, 1), (1, RED, 0)):
            points: list[float] = []
            for point_index, values in enumerate(history):
                x = 8 + point_index * (width - 16) / (len(history) - 1)
                y = height - 10 - values[index] / maximum * (height - 25)
                points.extend((x, y))
            self.graph.create_line(*points, fill=color, width=2, smooth=True)


def run_headless() -> None:
    """Run enough frames to verify the engine without opening a window."""
    simulation = Simulation(seed=7, state_store=InMemoryStateStore())
    simulation.start()
    for _ in range(300):
        simulation.update(1 / 30)
    snapshot = simulation.snapshot()
    print("Python simulation smoke test passed")
    print(
        f"state={snapshot['state']} humans={snapshot['humans']} "
        f"zombies={snapshot['zombies']} rescued={snapshot['rescued']} "
        f"history_points={len(simulation.population_history)}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Outbreak: Last Light")
    parser.add_argument("--headless", action="store_true", help="run the simulation smoke test without a window")
    parser.add_argument(
        "--json-checkpoint",
        type=Path,
        help="use a JSON file for Save state and Load state instead of process memory",
    )
    arguments = parser.parse_args()
    if arguments.headless:
        run_headless()
    else:
        if ttk is None:
            raise SystemExit(
                "Tkinter is not installed in this Python build. "
                "Install a Python distribution with Tk support, then run python3 main.py again."
            )
        storage = JsonFileStateStore(arguments.json_checkpoint) if arguments.json_checkpoint else InMemoryStateStore()
        app = ZombieGameApp(storage)
        app.mainloop()
