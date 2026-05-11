from __future__ import annotations

from dataclasses import dataclass

from .commands import ResourceKind


@dataclass(frozen=True)
class TelemetryFrame:
    kind: ResourceKind
    resource_id: int
    value: int


@dataclass(frozen=True)
class EdgeEvent:
    kind: ResourceKind
    resource_id: int
    value: int
    timestamp_us: int
