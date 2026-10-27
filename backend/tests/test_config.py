"""DATABASE_URL: banco SQLite relativo resolvido a partir de backend/, o resto intacto."""

import pytest

from app.config import BACKEND_DIR, Settings

DB = (BACKEND_DIR / "logcoach.db").as_posix()


def database_url(value: str | None = None) -> str:
    # _env_file=None: sem o backend/.env do desenvolvedor.
    kwargs = {} if value is None else {"database_url": value}
    return Settings(_env_file=None, **kwargs).database_url


@pytest.fixture(autouse=True)
def sem_database_url(monkeypatch):
    # O conftest define DATABASE_URL=sqlite:// para o app; aqui cada teste escolhe o seu.
    monkeypatch.delenv("DATABASE_URL", raising=False)


def test_padrao_e_backend_logcoach_db_absoluto():
    assert BACKEND_DIR.is_absolute()
    assert database_url() == f"sqlite:///{DB}"


@pytest.mark.parametrize("url", ["sqlite:///./logcoach.db", "sqlite:///logcoach.db"])
def test_relativo_resolvido_a_partir_do_backend(url):
    assert database_url(url) == f"sqlite:///{DB}"


def test_relativo_com_subpasta():
    assert database_url("sqlite:///dados/x.db") == f"sqlite:///{BACKEND_DIR.as_posix()}/dados/x.db"


def test_vazio_no_ambiente_vale_o_padrao(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    assert database_url() == f"sqlite:///{DB}"


def test_relativo_vindo_do_ambiente(monkeypatch):
    # O .env atual dos desenvolvedores tem esse valor e precisa continuar valendo.
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./logcoach.db")
    assert database_url() == f"sqlite:///{DB}"


@pytest.mark.parametrize(
    "url",
    [
        "sqlite://",
        "sqlite:///:memory:",
        "sqlite:////tmp/logcoach.db",
        "sqlite:///C:/LogCoach/logcoach.db",
        "sqlite:///C:\\LogCoach\\logcoach.db",
        "postgresql://user:senha@localhost:5432/logcoach",
        "postgresql+psycopg://user@db/logcoach?sslmode=require",
    ],
)
def test_memoria_absoluto_e_outros_bancos_intactos(url):
    assert database_url(url) == url


def test_query_string_preservada():
    assert database_url("sqlite:///./logcoach.db?timeout=10") == f"sqlite:///{DB}?timeout=10"
    assert database_url("sqlite:///:memory:?cache=shared") == "sqlite:///:memory:?cache=shared"
