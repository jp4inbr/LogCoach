"""Plano grátis: limite de análises por mês (RF14)."""

from datetime import UTC, datetime

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Analysis


def month_start(now: datetime | None = None) -> datetime:
    """Primeiro instante do mês corrente (em UTC)."""
    now = now or datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def analyses_this_month(session: Session, user_id: str, now: datetime | None = None) -> int:
    query = (
        select(func.count())
        .select_from(Analysis)
        .where(Analysis.user_id == user_id, Analysis.created_at >= month_start(now))
    )
    return session.exec(query).one()
