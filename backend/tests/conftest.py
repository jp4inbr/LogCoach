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
from app.schemas import (  # noqa: E402
    AnalysisResult,
    Coach,
    ComparedPlayer,
    Comparison,
    FightInfo,
    PlayerInfo,
    Summary,
)
from app.services.sources import (  # noqa: E402
    fight_data_store,
    players_cache,
    prefetch_limiter,
    query_limiter,
    report_cache,
    shutdown_prefetch,
    wcl_cooldown,
)
from app.services.tops import (  # noqa: E402
    brackets_cache,
    shutdown_tops,
    tops_failures,
    tops_fill_limiter,
    tops_store,
)
from app.wcl.client import close_shared_client  # noqa: E402

LINK = "https://www.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D#fight=34"
# Harmonist: ator 455 do report de referência.
ANALYSIS = {"report_code": "XhrmBaYkGCAQjH2D", "fight_id": 34, "actor_id": 455}


def make_result(
    comparison: Comparison | None = None,
    fight: FightInfo | None = None,
    player: PlayerInfo | None = None,
    report_code: str = "XhrmBaYkGCAQjH2D",
) -> AnalysisResult:
    """Um `AnalysisResult` mínimo e válido, para os testes que não dependem do motor."""
    comparison = comparison or Comparison(
        label="Top 10 do bracket 326–328",
        bracket="326–328",
        size=2,
        player_in_top=False,
        players=[ComparedPlayer(rank=n, display_name=f"top{n:02d}", dps=270_000.0) for n in (1, 2)],
        sample=True,
    )
    return AnalysisResult(
        source="motor",
        report_code=report_code,
        fight=fight
        or FightInfo(
            id=34,
            boss="Nek'zali, a Enrosca-almas",
            difficulty="Mítico",
            kill=True,
            duration_s=415.6,
        ),  # fmt: skip
        player=player or PlayerInfo(name="Harmonist", spec="Mago Arcano", item_level=327),
        comparison=comparison,
        summary=Summary(
            dps=230_000.0,
            top_avg_dps=270_000.0,
            dps_gap_pct=-14.8,
            active_time_pct=98.6,
            top_active_time_pct=99.0,
        ),  # fmt: skip
        coach=Coach(available=False),
        mistakes=[],
        rules=[],
        phases=[],
        timeline=[],
        abilities=[],
    )


def _clear_wcl_state() -> None:
    report_cache.clear()
    players_cache.clear()
    fight_data_store.clear()
    prefetch_limiter.clear()
    query_limiter.clear()
    wcl_cooldown.clear()
    tops_store.clear()
    brackets_cache.clear()
    tops_failures.clear()
    tops_fill_limiter.clear()
    close_shared_client()


@pytest.fixture(autouse=True)
def fresh_wcl_state():
    """Caches, pré-buscas, limites, falha lembrada e cliente do processo zerados: nada vaza
    entre testes.

    `shutdown_prefetch` espera as threads da pré-busca terminarem: nenhuma fica solta.
    """
    _clear_wcl_state()
    yield
    shutdown_prefetch()
    shutdown_tops()
    _clear_wcl_state()


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
