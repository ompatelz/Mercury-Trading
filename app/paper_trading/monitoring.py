from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class ComponentStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


@dataclass
class ComponentHealth:
    component: str
    status: ComponentStatus
    reason: str | None = None


@dataclass
class StrategyMonitoringState:
    session_id: UUID
    status: str
    last_market_event: dict[str, Any] | None = None
    last_signal: dict[str, Any] | None = None
    last_order: dict[str, Any] | None = None
    current_position: dict[str, Any] = field(default_factory=dict)
    pnl: dict[str, float] = field(default_factory=dict)
    equity: float = 0.0
    drawdown: float = 0.0
    number_of_trades: int = 0
    rejected_orders: int = 0
    processing_latency_ms: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def record_error(self, message: str) -> None:
        self.errors.append(message)
        self.updated_at = datetime.now(UTC)

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_id": str(self.session_id),
            "status": self.status,
            "last_market_event": self.last_market_event,
            "last_signal": self.last_signal,
            "last_order": self.last_order,
            "current_position": self.current_position,
            "pnl": self.pnl,
            "equity": self.equity,
            "drawdown": self.drawdown,
            "number_of_trades": self.number_of_trades,
            "rejected_orders": self.rejected_orders,
            "processing_latency_ms": self.processing_latency_ms,
            "errors": self.errors,
            "updated_at": self.updated_at.isoformat(),
        }


class LiveUpdateHub:
    def __init__(self) -> None:
        self._events: dict[UUID, list[dict[str, Any]]] = {}

    def publish(self, session_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
        event = {
            "type": event_type,
            "session_id": str(session_id),
            "payload": payload,
            "published_at": datetime.now(UTC).isoformat(),
        }
        self._events.setdefault(session_id, []).append(event)

    def list_events(self, session_id: UUID, *, after: int = 0) -> list[dict[str, Any]]:
        return self._events.get(session_id, [])[after:]


live_update_hub = LiveUpdateHub()
