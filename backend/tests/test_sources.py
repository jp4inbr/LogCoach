"""WclReportSource com respostas falsas da API (nada aqui acessa a internet)."""

import copy
import json

import httpx
import pytest

from app.config import Settings, get_settings
from app.services.sources import (
    SAMPLE_REPORT_CODE,
    SHORT_FIGHT_REASON,
    UNSUPPORTED_BOSS_REASON,
    UNSUPPORTED_DIFFICULTY_REASON,
    ReportNotAvailableError,
    SampleReportSource,
    WclReportSource,
    build_report,
    get_report_source,
)
from app.wcl.client import TOKEN_URL, WclClient, WclError
from app.wcl.fetch import fetch_report

NEKZALI = 3470


def details(actor_id: int, spec: str, item_level: int) -> dict:
    return {
        "id": actor_id,
        "type": "Mage",
        "specs": [{"spec": spec, "count": 1}],
        "minItemLevel": item_level - 1,
        "maxItemLevel": item_level,
    }


# Resposta do REPORT_FIGHTS só com pseudônimos.
REPORT = {
    "code": "TESTE123",
    "title": "Raide de teste",
    "fights": [
        # Tentativa curta no Nek'zali.
        {"id": 1, "encounterID": NEKZALI, "name": "Nek'zali the Soulcoiler", "difficulty": 5,
         "kill": False, "startTime": 0, "endTime": 41_000, "friendlyPlayers": [10, 11, 12]},
        {"id": 2, "encounterID": NEKZALI, "name": "Nek'zali the Soulcoiler", "difficulty": 5,
         "kill": True, "startTime": 100_000, "endTime": 515_641,
         "friendlyPlayers": [10, 11, 12, 13]},
        {"id": 3, "encounterID": 9999, "name": "Outro Chefe", "difficulty": 4,
         "kill": True, "startTime": 600_000, "endTime": 900_000, "friendlyPlayers": [10]},
        {"id": 4, "encounterID": NEKZALI, "name": "Nek'zali the Soulcoiler", "difficulty": 3,
         "kill": True, "startTime": 1_000_000, "endTime": 1_200_000, "friendlyPlayers": [13]},
    ],
    "masterData": {
        "actors": [
            {"id": 10, "name": "arcano_a", "server": "Norte", "type": "Player", "subType": "Mage"},
            {"id": 11, "name": "fogo_a", "server": "Norte", "type": "Player", "subType": "Mage"},
            {"id": 12, "name": "guerreiro_a", "server": "Norte", "type": "Player",
             "subType": "Warrior"},
            # Mesmo nome, outro reino: os dois aparecem, com o reino para diferenciar.
            {"id": 13, "name": "arcano_a", "server": "Sul", "type": "Player", "subType": "Mage"},
        ]
    },
    "playerDetails": {
        "data": {
            "playerDetails": {
                "dps": [
                    details(10, "Arcane", 327),
                    details(11, "Fire", 330),
                    {"id": 12, "type": "Warrior", "specs": [{"spec": "Arms", "count": 1}]},
                    details(13, "Arcane", 324),
                ],
                "healers": [],
                "tanks": [],
            }
        }
    },
}  # fmt: skip


def fake_client(body: dict, status: int = 200) -> WclClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(status, json=body)

    return WclClient("id", "secret", transport=httpx.MockTransport(handler))


def source_for(report: dict | None, errors: list | None = None, status: int = 200):
    body: dict = {"data": {"reportData": {"report": report}}}
    if errors:
        body["errors"] = errors
    return WclReportSource(client_factory=lambda: fake_client(body, status))


def raw_report() -> dict:
    return fetch_report(fake_client({"data": {"reportData": {"report": REPORT}}}), "TESTE123")


def test_report_is_mapped_from_wcl():
    report = source_for(REPORT).get_report("TESTE123")

    assert report.code == "TESTE123"
    assert report.title == "Raide de teste"
    assert report.sample is False
    assert [f.id for f in report.fights] == [1, 2, 3, 4]
    fight = report.fights[1]
    assert fight.boss == "Nek'zali, a Enrosca-almas"  # nome em pt-BR do i18n
    assert fight.kill is True
    assert fight.duration_s == 415.6
    assert fight.supported is True
    assert fight.unsupported_reason is None


def test_only_arcane_mages_are_listed():
    fights = {f.id: f for f in source_for(REPORT).get_report("TESTE123").fights}

    assert [(p.name, p.spec, p.item_level) for p in fights[1].players] == [
        ("arcano_a", "Mago Arcano", 327)
    ]
    assert [p.item_level for p in fights[2].players] == [327, 324]


def test_players_keep_their_realm():
    fight = build_report(raw_report())["fights"][1]

    assert [(p["name"], p["server"]) for p in fight["players"]] == [
        ("arcano_a", "Norte"),
        ("arcano_a", "Sul"),
    ]
    # E o reino chega no contrato (PlayerOption.server), que é o que a tela e /analyses usam.
    fights = {f.id: f for f in source_for(REPORT).get_report("TESTE123").fights}
    assert [p.server for p in fights[2].players] == ["Norte", "Sul"]


def test_short_fight_is_not_supported():
    fight = source_for(REPORT).get_report("TESTE123").fights[0]

    assert fight.duration_s == 41.0
    assert fight.supported is False
    assert fight.unsupported_reason == SHORT_FIGHT_REASON


def test_boss_without_rules_is_not_supported():
    fight = source_for(REPORT).get_report("TESTE123").fights[2]

    assert fight.boss == "Outro Chefe"  # sem tradução: nome do Warcraft Logs
    assert fight.supported is False
    assert fight.unsupported_reason == UNSUPPORTED_BOSS_REASON


def test_difficulty_in_portuguese():
    fights = source_for(REPORT).get_report("TESTE123").fights

    assert [f.difficulty for f in fights] == ["Mítico", "Mítico", "Heroico", "Normal"]


def test_unknown_difficulty_keeps_wcl_value():
    raw = raw_report()
    raw["fights"] = [copy.deepcopy(raw["fights"][1]) | {"difficulty": 99}]

    assert build_report(raw)["fights"][0]["difficulty"] == "Dificuldade 99"


def test_only_mythic_nekzali_is_supported():
    fights = {f.id: f for f in source_for(REPORT).get_report("TESTE123").fights}

    # Luta 4: Nek'zali no Normal, com mais de 60 s. O YAML só traz regras do Mítico.
    assert fights[4].supported is False
    assert fights[4].unsupported_reason == UNSUPPORTED_DIFFICULTY_REASON


def test_sample_report_opens_when_wcl_is_down():
    # Plano B da demo: o link de exemplo abre mesmo com o Warcraft Logs fora do ar.
    report = source_for(REPORT, status=500).get_report(SAMPLE_REPORT_CODE)

    assert report.sample is True


@pytest.mark.parametrize(
    ("report", "errors", "status"),
    [
        (None, [{"message": "This report does not exist."}], 200),  # inexistente
        (None, [{"message": "You do not have permission to view this report."}], 200),  # privado
        (None, None, 200),  # report nulo sem erro
        (REPORT, None, 500),  # API fora do ar
    ],
)
def test_unavailable_report_raises(report, errors, status):
    with pytest.raises(ReportNotAvailableError):
        source_for(report, errors, status).get_report("NAOEXISTE")


def test_missing_credentials_is_report_not_available():
    def no_credentials() -> WclClient:
        raise WclError("WCL_CLIENT_ID e WCL_CLIENT_SECRET não definidos.")

    with pytest.raises(ReportNotAvailableError):
        WclReportSource(client_factory=no_credentials).get_report("TESTE123")


# --- Configuração (DATA_SOURCE, APP_ENV) --------------------------------------


@pytest.fixture
def clean_settings(monkeypatch):
    """Settings só das variáveis do teste: sem o backend/.env do desenvolvedor."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in ("DATA_SOURCE", "WCL_CLIENT_ID", "WCL_CLIENT_SECRET", "APP_ENV"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"DATA_SOURCE": "wcl", "WCL_CLIENT_ID": "a", "WCL_CLIENT_SECRET": "b"}, WclReportSource),
        ({"DATA_SOURCE": "exemplo", "WCL_CLIENT_ID": "a", "WCL_CLIENT_SECRET": "b"},
         SampleReportSource),
        ({"WCL_CLIENT_ID": "a", "WCL_CLIENT_SECRET": "b"}, WclReportSource),
        ({"WCL_CLIENT_ID": "a"}, SampleReportSource),
        ({}, SampleReportSource),
        ({"DATA_SOURCE": ""}, SampleReportSource),  # "DATA_SOURCE=" do .env.example
    ],
)  # fmt: skip
def test_get_report_source_follows_data_source(clean_settings, env, expected):
    for name, value in env.items():
        clean_settings.setenv(name, value)

    assert isinstance(get_report_source(), expected)


def test_wcl_without_credentials_fails_at_startup(clean_settings):
    clean_settings.setenv("DATA_SOURCE", "wcl")

    with pytest.raises(ValueError, match="WCL_CLIENT_ID"):
        get_settings()


def test_prod_requires_jwt_secret(clean_settings):
    clean_settings.setenv("APP_ENV", "prod")
    clean_settings.delenv("JWT_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        get_settings()


def test_dev_without_jwt_secret_uses_temporary_key(clean_settings):
    clean_settings.delenv("JWT_SECRET", raising=False)

    assert get_settings().jwt_secret


# --- Nomes reais no modo exemplo (RF25) ----------------------------------------


def test_sample_analysis_gets_real_names_from_local_file(tmp_path):
    from app.schemas import AnalysisResult
    from app.services.sources import SAMPLES_DIR, fill_real_names

    result = AnalysisResult.model_validate(
        json.loads((SAMPLES_DIR / "analysis_XhrmBaYkGCAQjH2D_34.json").read_text(encoding="utf-8"))
    )
    names = tmp_path / "names.local.json"
    names.write_text(
        json.dumps(
            {
                "nekzali_mythic_326_328": {
                    "top01.json.gz": {"top01": {"name": "Primeiro", "server": "Norte"}}
                }
            }
        ),
        encoding="utf-8",
    )

    fill_real_names(result, names)

    top1, top2 = result.comparison.players[:2]
    assert (top1.display_name, top1.name, top1.server) == ("top01", "Primeiro", "Norte")
    assert top2.name is None  # sem entrada no arquivo, continua oculto


def test_sample_analysis_without_local_file_keeps_names_hidden(tmp_path):
    from app.schemas import AnalysisResult
    from app.services.sources import SAMPLES_DIR, fill_real_names

    result = AnalysisResult.model_validate(
        json.loads((SAMPLES_DIR / "analysis_XhrmBaYkGCAQjH2D_34.json").read_text(encoding="utf-8"))
    )

    fill_real_names(result, tmp_path / "nao-existe.json")

    assert all(p.name is None for p in result.comparison.players)
