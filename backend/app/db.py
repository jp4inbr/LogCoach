"""Conexão com o banco (SQLite em desenvolvimento, PostgreSQL em produção)."""

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings


def make_engine(url: str):
    # O SQLite só aceita a conexão na thread que a criou; o FastAPI usa várias.
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


engine = make_engine(get_settings().database_url)


def create_tables(target_engine=engine) -> None:
    # Importa os modelos para o SQLModel conhecer as tabelas antes de criar.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(target_engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
