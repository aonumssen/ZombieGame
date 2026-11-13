"""Target-owned event batches with interchangeable serial, thread, and process execution."""

from __future__ import annotations

from array import array
from collections.abc import Iterable, Iterator, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from multiprocessing import get_context
import os
from typing import Literal

from stage2_parallel import AgentView, NeighborPair, SimulationEvent
from stage2_simulation import ScalableAgent

Backend = Literal["serial", "threads", "processes"]
TargetGroup = tuple[int, list[tuple[int, float]]]


def _calculate_batch(
    groups: Sequence[TargetGroup], radius: float
) -> tuple[array, list[float], int]:
    """Return per-contact amounts and per-target totals in input order."""
    amounts = array("d")
    totals = []
    for _, contacts in groups:
        total = 0.0
        for _, distance in contacts:
            amount = 0.12 * max(0.0, 1.0 - distance / radius)
            amounts.append(amount)
            # Match the Stage 2 serial floating-point addition order.
            total += amount
        totals.append(total)
    return amounts, totals, os.getpid()


def _make_batches(
    groups: list[TargetGroup], contact_count: int, workers: int
) -> Iterator[list[TargetGroup]]:
    """Make roughly four batches per worker while keeping targets intact."""
    desired_batches = 4 * workers
    budget = (contact_count + desired_batches - 1) // desired_batches
    start = load = 0
    for index, (_, contacts) in enumerate(groups):
        if load and load + len(contacts) > budget:
            yield groups[start:index]
            start = index
            load = 0
        load += len(contacts)
    if start < len(groups):
        yield groups[start:]


class TargetEventProcessor:
    """Group by target, compute effects in batches, then commit on the caller."""

    def __init__(self, backend: Backend = "processes", workers: int = 4) -> None:
        if backend not in ("serial", "threads", "processes"):
            raise ValueError(f"unknown event backend: {backend}")
        if workers < 1:
            raise ValueError("workers must be positive")
        self.backend = backend
        self.workers = workers
        self.worker_pids: set[int] = set()
        self._pool: ProcessPoolExecutor | ThreadPoolExecutor | None = None
        self._closed = False

    def __enter__(self) -> TargetEventProcessor:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown()
            self._pool = None
        self._closed = True

    def process(
        self,
        views: Iterable[AgentView],
        pairs: Sequence[NeighborPair],
        agents: Mapping[int, ScalableAgent],
        radius: float = 28.0,
    ) -> tuple[list[SimulationEvent], int]:
        """Process one tick from a snapshot and update each affected target once."""
        if self._closed:
            raise RuntimeError("the event processor is closed")
        self.worker_pids = set()
        kinds = {agent.agent_id: agent.kind for agent in views}
        by_target: dict[int, list[tuple[int, float]]] = {}
        contact_count = 0
        for pair in pairs:
            left_kind = kinds[pair.left_id]
            right_kind = kinds[pair.right_id]
            if left_kind == right_kind:
                continue
            target, source = (pair.left_id, pair.right_id) if left_kind == "human" else (
                pair.right_id, pair.left_id
            )
            by_target.setdefault(target, []).append((source, pair.distance))
            contact_count += 1

        # Stable sort preserves input order even for repeated source IDs.
        groups = sorted(by_target.items())
        for _, contacts in groups:
            contacts.sort(key=lambda contact: contact[0])
        if not groups:
            return [], 0

        batches = [groups]
        if self.backend != "serial" and self.workers > 1 and len(groups) > 1:
            batches = list(_make_batches(groups, contact_count, self.workers))

        if len(batches) == 1:
            results = [_calculate_batch(groups, radius)]
        else:
            if self._pool is None:
                if self.backend == "processes":
                    self._pool = ProcessPoolExecutor(
                        max_workers=self.workers, mp_context=get_context("spawn")
                    )
                else:
                    self._pool = ThreadPoolExecutor(max_workers=self.workers)
            try:
                pending = [self._pool.submit(_calculate_batch, batch, radius) for batch in batches]
                # A worker failure leaves the event batch uncommitted.
                results = [future.result() for future in pending]
            except BrokenProcessPool:
                self._pool.shutdown(cancel_futures=True)
                self._pool = None
                raise

        events = []
        updates = []
        for batch, (amounts, totals, pid) in zip(batches, results):
            self.worker_pids.add(pid)
            ordered_amounts = iter(amounts)
            for (target, contacts), total in zip(batch, totals):
                for source, _ in contacts:
                    events.append(SimulationEvent("infection", source, target, next(ordered_amounts)))
                agent = agents.get(target)
                if agent is not None and agent.kind == "human":
                    updates.append((agent, min(1.0, agent.infection + total)))

        conversions = 0
        for agent, infection in updates:
            if infection >= 1.0:
                agent.kind = "zombie"
                agent.infection = 0.0
                conversions += 1
            else:
                agent.infection = infection
        return events, conversions
