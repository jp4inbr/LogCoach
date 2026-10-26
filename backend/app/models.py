"""Tabelas do banco."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, ForeignKey, String
from sqlmodel import JSON, Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid.uuid4().hex


class User(SQLModel, table=True):
    # RNF07 (LGPD): o único dado pessoal guardado é o e-mail; a senha só como hash.
    id: str = Field(default_factory=new_id, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    created_at: datetime = Field(default_factory=utcnow)


class Analysis(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    # Vazio quando a análise foi feita sem conta (RF01). Apagar o usuário apaga as análises.
    user_id: str | None = Field(
        default=None,
        sa_column=Column(String, ForeignKey("user.id", ondelete="CASCADE"), index=True),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)

    report_code: str
    fight_id: int
    player_name: str
    boss: str
    difficulty: str

    # Resumo para o histórico e o gráfico de evolução (RF12, RF13), sem abrir o resultado.
    dps: float
    dps_gap_pct: float
    mistakes_count: int

    # Resultado completo, no formato de app.schemas.analysis.AnalysisResult.
    result: dict = Field(sa_column=Column(JSON, nullable=False))
