"""Tabelas do banco."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, ForeignKey, LargeBinary, String
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


class TopsSnapshot(SQLModel, table=True):
    """Tops de um bracket (encontro, dificuldade, bracket) guardados por 24 h (RNF03).

    Fica no banco para um reinício do processo não gastar de novo os ~135 pontos do Warcraft
    Logs (item 12.13). As lutas ficam em `TopsLog`, uma linha por top. A mesma tabela guarda
    os brackets de cada encontro (chave "brackets:<encontro>", sem tops).
    """

    key: str = Field(primary_key=True)  # "3470:5:19" ou "brackets:3470"
    fetched_at: float  # segundos desde 1970 (time.time()), sem fuso para o SQLite estragar
    # Tops: `rankings` (rank, report, luta, nome de cada posição lida). Brackets: `brackets`.
    info: dict = Field(sa_column=Column(JSON, nullable=False))


class TopsLog(SQLModel, table=True):
    """Um top de um `TopsSnapshot`: dados do ranking e a luta comprimida (~130 KB)."""

    key: str = Field(
        sa_column=Column(
            String, ForeignKey("topssnapshot.key", ondelete="CASCADE"), primary_key=True
        )
    )
    rank: int = Field(primary_key=True)
    # Nome real, reino, item level, DPS, report e luta: nunca vai para a IA (RF25).
    meta: dict = Field(sa_column=Column(JSON, nullable=False))
    fight_gz: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
