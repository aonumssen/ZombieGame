"""SQLite persistence for the Stage 2 scalable simulation."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping, Optional

from stage2_parallel import SimulationEvent
from stage2_simulation import ScalableAgent, Stage2StepMetrics


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    agent_count INTEGER NOT NULL,
    workers INTEGER NOT NULL,
    parallel INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    steps INTEGER NOT NULL,
    configuration_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS agents (
    run_id INTEGER NOT NULL,
    agent_id INTEGER NOT NULL,
    step INTEGER NOT NULL,
    kind TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    vx REAL NOT NULL,
    vy REAL NOT NULL,
    infection REAL NOT NULL,
    health REAL NOT NULL,
    PRIMARY KEY (run_id, agent_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
    run_id INTEGER NOT NULL,
    step INTEGER NOT NULL,
    event_index INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    PRIMARY KEY (run_id, step, event_index),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS metrics (
    run_id INTEGER NOT NULL,
    step INTEGER NOT NULL,
    simulated_seconds REAL NOT NULL,
    active_agents INTEGER NOT NULL,
    humans INTEGER NOT NULL,
    zombies INTEGER NOT NULL,
    neighbor_pairs INTEGER NOT NULL,
    events_processed INTEGER NOT NULL,
    conversions INTEGER NOT NULL,
    step_time_ms REAL NOT NULL,
    neighbor_time_ms REAL NOT NULL,
    event_time_ms REAL NOT NULL,
    PRIMARY KEY (run_id, step),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_events_run_step ON events(run_id, step);
CREATE INDEX IF NOT EXISTS idx_metrics_run_step ON metrics(run_id, step);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteStateStore:
    """Write the agent state, events, and timings for each tick in one transaction."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "SQLiteStateStore":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def start_run(self, configuration: Mapping[str, Any]) -> int:
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO runs (
                    started_at, agent_count, workers, parallel, seed, steps,
                    configuration_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'running')
                """,
                (
                    _now(),
                    int(configuration["agent_count"]),
                    int(configuration["workers"]),
                    int(bool(configuration["parallel"])),
                    int(configuration["seed"]),
                    int(configuration["steps"]),
                    json.dumps(dict(configuration), sort_keys=True),
                ),
            )
        return int(cursor.lastrowid)

    def save_step(
        self,
        run_id: int,
        metrics: Stage2StepMetrics,
        agents: Iterable[ScalableAgent],
        events: Iterable[SimulationEvent],
    ) -> None:
        agent_rows = [
            (
                run_id,
                agent.agent_id,
                metrics.step,
                agent.kind,
                agent.x,
                agent.y,
                agent.vx,
                agent.vy,
                agent.infection,
                agent.health,
            )
            for agent in agents
        ]
        event_rows = [
            (
                run_id,
                metrics.step,
                index,
                event.event_type,
                event.source_id,
                event.target_id,
                event.amount,
            )
            for index, event in enumerate(events)
        ]
        values = metrics.as_dict()
        with self.connection:
            self.connection.executemany(
                """
                INSERT INTO agents (
                    run_id, agent_id, step, kind, x, y, vx, vy, infection, health
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, agent_id) DO UPDATE SET
                    step = excluded.step,
                    kind = excluded.kind,
                    x = excluded.x,
                    y = excluded.y,
                    vx = excluded.vx,
                    vy = excluded.vy,
                    infection = excluded.infection,
                    health = excluded.health
                """,
                agent_rows,
            )
            self.connection.executemany(
                """
                INSERT INTO events (
                    run_id, step, event_index, event_type, source_id, target_id, amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                event_rows,
            )
            self.connection.execute(
                """
                INSERT OR REPLACE INTO metrics (
                    run_id, step, simulated_seconds, active_agents, humans, zombies,
                    neighbor_pairs, events_processed, conversions, step_time_ms,
                    neighbor_time_ms, event_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    metrics.step,
                    values["simulated_seconds"],
                    values["active_agents"],
                    values["humans"],
                    values["zombies"],
                    values["neighbor_pairs"],
                    values["events_processed"],
                    values["conversions"],
                    values["step_time_ms"],
                    values["neighbor_time_ms"],
                    values["event_time_ms"],
                ),
            )

    def finish_run(self, run_id: int, status: str = "complete") -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE runs SET finished_at = ?, status = ? WHERE run_id = ?",
                (_now(), status, run_id),
            )

    def run_summary(self, run_id: int) -> Optional[dict[str, Any]]:
        row = self.connection.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        metrics = self.connection.execute(
            """
            SELECT COUNT(*) AS steps,
                   AVG(step_time_ms) AS avg_step_ms,
                   AVG(neighbor_time_ms) AS avg_neighbor_ms,
                   AVG(event_time_ms) AS avg_event_ms,
                   MAX(neighbor_pairs) AS max_neighbor_pairs,
                   MAX(events_processed) AS max_events
            FROM metrics WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        result = dict(row)
        result.update(dict(metrics) if metrics is not None else {})
        return result

    def read_metrics(self, run_id: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM metrics WHERE run_id = ? ORDER BY step", (run_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def read_agents(self, run_id: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM agents WHERE run_id = ? ORDER BY agent_id", (run_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def count_rows(self, table: str, run_id: int) -> int:
        if table not in {"agents", "events", "metrics"}:
            raise ValueError("unsupported table")
        row = self.connection.execute(
            f"SELECT COUNT(*) AS count FROM {table} WHERE run_id = ?", (run_id,)
        ).fetchone()
        return int(row["count"])


__all__ = ["SQLiteStateStore"]
