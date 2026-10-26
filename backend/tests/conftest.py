import os

# Antes de importar o app: chave fixa, banco em memória (sem tocar no logcoach.db)
# e dados de exemplo, para os testes não dependerem da API do Warcraft Logs.
os.environ.setdefault("JWT_SECRET", "chave-fixa-so-para-os-testes-0123456789")
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DATA_SOURCE"] = "exemplo"
# Sem o names.local.json da máquina: os testes veem os nomes ocultos, como no CI.
os.environ["NAMES_FILE"] = "/nao/existe/names.local.json"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

from app.db import create_tables, get_session  # noqa: E402
from app.main import app  # noqa: E402

LINK = "https://www.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D#fight=34"
ANALYSIS = {"report_code": "XhrmBaYkGCAQjH2D", "fight_id": 34, "player_name": "Harmonist"}


@pytest.fixture
def engine():
    # Um banco novo em memória por teste; StaticPool mantém a mesma conexão aberta.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    create_tables(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client(engine):
    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    response = client.post(
        "/auth/register", json={"email": "jogador@exemplo.com", "password": "senha-forte-1"}
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
