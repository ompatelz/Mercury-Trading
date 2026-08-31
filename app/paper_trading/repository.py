from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.paper_trading import (
    PaperFillRecord,
    PaperOrderRecord,
    PaperTraceEventRecord,
    PaperTradingSession,
)


class PaperTradingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_session(self, session_id: UUID) -> PaperTradingSession | None:
        return self.session.get(PaperTradingSession, session_id)

    def list_sessions(self, *, limit: int) -> list[PaperTradingSession]:
        return list(
            self.session.scalars(
                select(PaperTradingSession)
                .order_by(PaperTradingSession.started_at.desc())
                .limit(limit)
            )
        )

    def list_orders(self, session_id: UUID) -> list[PaperOrderRecord]:
        return list(
            self.session.scalars(
                select(PaperOrderRecord)
                .where(PaperOrderRecord.session_id == session_id)
                .order_by(PaperOrderRecord.created_at, PaperOrderRecord.id)
            )
        )

    def list_fills(self, session_id: UUID) -> list[PaperFillRecord]:
        return list(
            self.session.scalars(
                select(PaperFillRecord)
                .where(PaperFillRecord.session_id == session_id)
                .order_by(PaperFillRecord.timestamp, PaperFillRecord.id)
            )
        )

    def list_events(self, session_id: UUID) -> list[PaperTraceEventRecord]:
        return list(
            self.session.scalars(
                select(PaperTraceEventRecord)
                .where(PaperTraceEventRecord.session_id == session_id)
                .order_by(PaperTraceEventRecord.sequence)
            )
        )
