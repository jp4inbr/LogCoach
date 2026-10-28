"""WclReportSource com respostas falsas da API (nada aqui acessa a internet)."""

import copy
import json

import httpx
import pytest

from app.config import Settings, get_settings
from app.services.sources import (
    IN_PROGRESS_REASON,
    REFRESH_MIN_INTERVAL_S,
    SAMPLE_REPORT_CODE,
    SHORT_FIGHT_REASON,
    UNSUPPORTED_BOSS_REASON,
    UNSUPPORTED_DIFFICULTY_REASON,
    ReportCache,
    ReportNotAvailableError,
    SampleReportSource,
    SourceUnavailableError,
    WclReportSource,
    build_report,
    get_report_source,
    players_cache,
    report_cache,
)
from app.wcl.client import TOKEN_URL, WclClient, WclUnavailableError, close_shared_client
from app.wcl.fetch import fetch_report

NEKZALI = 3470


@pytest.fixture(autouse=True)
def fresh_wcl_state():
    """Caches e cliente do processo zerados: nada vaza de um teste para outro."""
    report_cache.clear()
    players_cache.clear()
    close_shared_client()
    yield
    report_cache.clear()
    players_cache.clear()
    close_shared_client()


def nekzali(fight_id: int, start: int, end: int, **extra) -> dict:
    return {"id": fight_id, "encounterID": NEKZALI, "name": "Nek'zali the Soulcoiler",
            "difficulty": 5, "kill": False, "startTime": start, "endTime": end,
            "inProgress": False} | extra  # fmt: skip


# Resposta do REPORT_FIGHTS (só a lista de lutas), com pseudônimos.
REPORT = {
    "code": "TESTE123",
    "title": "Raide de teste",
    "fights": [
        nekzali(1, 0, 41_000),  # tentativa curta
        nekzali(2, 100_000, 515_641, kill=True),
        {"id": 3, "encounterID": 9999, "name": "Outro Chefe", "difficulty": 4, "kill": True,
         "startTime": 600_000, "endTime": 900_000, "inProgress": False},
        nekzali(4, 1_000_000, 1_200_000, kill=True, difficulty=3),
    ],
}  # fmt: skip

# Magos do report (masterData.actors com subType Mage), como o FIGHT_PLAYERS traz.
MAGES = [
    {"id": 10, "name": "arcano_a", "server": "Norte", "type": "Player", "subType": "Mage"},
    {"id": 11, "name": "fogo_a", "server": "Norte", "type": "Player", "subType": "Mage"},
    # Mesmo nome, outro reino: os dois aparecem, com o reino para diferenciar.
    {"id": 13, "name": "arcano_a", "server": "Sul", "type": "Player", "subType": "Mage"},
]

# Jogadores de cada luta (friendlyPlayers/Specs/ItemLevels). O 12 é um Guerreiro; o 13
# joga Arcano na luta 2 e Fogo na luta 4.
FIGHT_PLAYERS = {
    2: ([10, 11, 12, 13], ["Arcane", "Fire", "Arms", "Arcane"], [327, 330, 325, 324]),
    4: ([13], ["Fire"], [324]),
}


class FakeWcl:
    """API falsa que responde cada consulta pelo nome e conta as chamadas."""

    def __init__(self, report: dict | None = None, status: int = 200) -> None:
        self.report = copy.deepcopy(REPORT if report is None else report)
        self.mages = copy.deepcopy(MAGES)
        self.fight_players = copy.deepcopy(FIGHT_PLAYERS)
        self.details: dict = {}
        self.status = status
        self.calls: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        body = json.loads(request.content)
        name = body["query"].split("(")[0].split()[-1]
        self.calls.append(name)
        if self.status != 200:
            return httpx.Response(self.status, json={})
        if name == "ReportFights":
            return httpx.Response(200, json=report_body(self.report))
        fight_id = body["variables"]["fightID"]
        if name == "FightPlayerDetails":
            details = {"data": {"playerDetails": {"dps": self.details.get(fight_id, [])}}}
            return httpx.Response(200, json=report_body({"playerDetails": details}))
        ids, specs, item_levels = self.fight_players.get(fight_id, ([], [], []))
        fight = {"id": fight_id, "friendlyPlayers": ids, "friendlySpecs": specs,
                 "friendlyItemLevels": item_levels}  # fmt: skip
        fights = [fight] if any(f["id"] == fight_id for f in self.report["fights"]) else []
        return httpx.Response(
            200, json=report_body({"fights": fights, "masterData": {"actors": self.mages}})
        )

    def client(self) -> WclClient:
        return WclClient("id", "secret", transport=httpx.MockTransport(self.handler))

    def source(self, cache: ReportCache | None = None) -> WclReportSource:
        # Caches próprios por padrão: cada FakeWcl é uma API nova.
        client = self.client()
        return WclReportSource(
            client_factory=lambda: client,
            cache=ReportCache() if cache is None else cache,
            players=ReportCache(),
        )


def fake_client(body: dict, status: int = 200, calls: list | None = None) -> WclClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if calls is not None:
            calls.append(request)
        return httpx.Response(status, json=body)

    return WclClient("id", "secret", transport=httpx.MockTransport(handler))


def report_body(report: dict | None, errors: list | None = None) -> dict:
    body: dict = {"data": {"reportData": {"report": report}}}
    if errors:
        body["errors"] = errors
    return body


def source_for(report: dict | None, errors: list | None = None, status: int = 200):
    # Cache próprio: cada chamada aqui é uma API nova, sem reaproveitar a de outro teste.
    body = report_body(report, errors)
    return WclReportSource(
        client_factory=lambda: fake_client(body, status), cache=ReportCache(), players=ReportCache()
    )


def raw_report() -> dict:
    return fetch_report(fake_client({"data": {"reportData": {"report": REPORT}}}), "TESTE123")


def test_report_is_mapped_from_wcl():
    report = source_for(REPORT).get_report("TESTE123")

    assert report.code == "TESTE123"
    assert report.title == "Raide de teste"
    assert report.sample is False
    assert report.fetched_at.tzinfo is not None
    assert [f.id for f in report.fights] == [1, 2, 3, 4]
    fight = report.fights[1]
    assert fight.boss == "Nek'zali, a Enrosca-almas"  # nome em pt-BR do i18n
    assert fight.kill is True
    assert fight.duration_s == 415.6
    assert fight.supported is True
    assert fight.unsupported_reason is None


def test_fight_list_has_no_players():
    # Ao colar o link só vem a lista de lutas; os Magos vêm por luta.
    wcl = FakeWcl()
    report = wcl.source().get_report("TESTE123")

    assert wcl.calls == ["ReportFights"]
    assert "players" not in report.fights[1].model_dump()


def test_only_arcane_mages_of_the_fight_are_listed():
    players = FakeWcl().source().get_fight_players("TESTE123", 2)

    # Fogo (11) e Guerreiro (12) ficam de fora; spec e item level são os da luta.
    assert [(p.actor_id, p.name, p.spec, p.item_level) for p in players] == [
        (10, "arcano_a", "Mago Arcano", 327),
        (13, "arcano_a", "Mago Arcano", 324),
    ]


def test_mage_that_played_fire_in_this_fight_is_not_listed():
    # O 13 é Arcano na luta 2, mas jogou Fogo na luta 4: a spec é a da luta.
    assert FakeWcl().source().get_fight_players("TESTE123", 4) == []


def test_players_keep_their_realm():
    players = FakeWcl().source().get_fight_players("TESTE123", 2)

    assert [(p.name, p.server) for p in players] == [("arcano_a", "Norte"), ("arcano_a", "Sul")]


def test_missing_spec_is_completed_with_player_details():
    wcl = FakeWcl()
    wcl.fight_players[2] = ([10, 11], [None, "Fire"], [None, 330])
    wcl.details[2] = [{"id": 10, "specs": [{"spec": "Arcane", "count": 1}], "maxItemLevel": 328}]

    players = wcl.source().get_fight_players("TESTE123", 2)

    assert [(p.actor_id, p.item_level) for p in players] == [(10, 328)]
    assert wcl.calls == ["FightPlayers", "FightPlayerDetails"]


def test_player_details_only_when_a_spec_is_missing():
    wcl = FakeWcl()
    wcl.source().get_fight_players("TESTE123", 2)

    assert wcl.calls == ["FightPlayers"]


def test_short_fight_is_not_supported():
    fight = source_for(REPORT).get_report("TESTE123").fights[0]

    assert fight.duration_s == 41.0
    assert fight.supported is False
    assert fight.unsupported_reason == SHORT_FIGHT_REASON


def test_fight_still_uploading_is_not_supported():
    # Log ao vivo: a luta em andamento ainda vai crescer. Atualizar as lutas libera ela.
    report = copy.deepcopy(REPORT)
    report["fights"][1]["inProgress"] = True

    fight = source_for(report).get_report("TESTE123").fights[1]

    assert fight.supported is False
    assert fight.unsupported_reason == IN_PROGRESS_REASON


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
    source = source_for(REPORT, status=500)

    assert source.get_report(SAMPLE_REPORT_CODE).sample is True
    assert [p.name for p in source.get_fight_players(SAMPLE_REPORT_CODE, 34)] == ["Harmonist"]


@pytest.mark.parametrize(
    ("report", "errors"),
    [
        (None, [{"message": "This report does not exist."}]),  # inexistente
        (None, [{"message": "You do not have permission to view this report."}]),  # privado
        (None, None),  # report nulo sem erro
    ],
)
def test_unavailable_report_raises(report, errors):
    with pytest.raises(ReportNotAvailableError):
        source_for(report, errors).get_report("NAOEXISTE")
    with pytest.raises(ReportNotAvailableError):
        source_for(report, errors).get_fight_players("NAOEXISTE", 2)


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_wcl_down_is_not_report_not_available(status):
    # Limite de pontos ou API fora do ar: o report pode estar certo.
    with pytest.raises(SourceUnavailableError):
        source_for(REPORT, status=status).get_report("TESTE123")
    with pytest.raises(SourceUnavailableError):
        source_for(REPORT, status=status).get_fight_players("TESTE123", 2)


def test_network_error_is_source_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("sem rede", request=request)

    client = WclClient("id", "secret", transport=httpx.MockTransport(handler))
    source = WclReportSource(client_factory=lambda: client, cache=ReportCache())

    with pytest.raises(SourceUnavailableError):
        source.get_report("TESTE123")


def test_missing_credentials_is_source_unavailable():
    # Falta de chave é problema do servidor, não do relatório do usuário.
    def no_credentials() -> WclClient:
        raise WclUnavailableError("WCL_CLIENT_ID e WCL_CLIENT_SECRET não definidos.")

    with pytest.raises(SourceUnavailableError):
        WclReportSource(client_factory=no_credentials, cache=ReportCache()).get_report("TESTE123")


def test_sample_report_opens_with_missing_credentials():
    def no_credentials() -> WclClient:
        raise WclUnavailableError("WCL_CLIENT_ID e WCL_CLIENT_SECRET não definidos.")

    source = WclReportSource(client_factory=no_credentials, cache=ReportCache())

    assert source.get_report(SAMPLE_REPORT_CODE).sample is True


# --- Modo exemplo ---------------------------------------------------------------


def test_sample_source_lists_fights_without_players():
    report = SampleReportSource().get_report(SAMPLE_REPORT_CODE)

    assert report.sample is True
    assert [f.id for f in report.fights] == [33, 34, 41, 47]


def test_sample_source_has_harmonist_in_fight_34():
    players = SampleReportSource().get_fight_players(SAMPLE_REPORT_CODE, 34)

    assert [(p.actor_id, p.name) for p in players] == [(455, "Harmonist")]


def test_sample_source_refresh_brings_the_same_fights():
    source = SampleReportSource()

    refreshed = source.get_report(SAMPLE_REPORT_CODE, refresh=True)

    assert refreshed.fights == source.get_report(SAMPLE_REPORT_CODE).fights


def test_sample_source_has_only_the_sample_report():
    with pytest.raises(ReportNotAvailableError):
        SampleReportSource().get_fight_players("OUTRO", 34)


# --- Cache e "Atualizar lutas" ----------------------------------------------------


def counting_source(calls: list, status: int = 200, cache: ReportCache | None = None):
    client = fake_client(report_body(REPORT), status, calls)
    return WclReportSource(client_factory=lambda: client, cache=cache)


def test_report_is_fetched_once_while_cached():
    calls: list = []
    source = counting_source(calls, cache=ReportCache())

    first = source.get_report("TESTE123")
    second = source.get_report("TESTE123")

    assert len(calls) == 1
    assert second == first


def test_fight_players_are_fetched_once_per_fight():
    wcl = FakeWcl()
    source = wcl.source()

    first = source.get_fight_players("TESTE123", 2)
    assert source.get_fight_players("TESTE123", 2) == first
    source.get_fight_players("TESTE123", 4)

    assert wcl.calls == ["FightPlayers", "FightPlayers"]


def test_cache_is_shared_between_sources():
    # A rota cria um WclReportSource por pedido; o cache é do processo.
    calls: list = []

    counting_source(calls).get_report("TESTE123")
    counting_source(calls).get_report("TESTE123")

    assert len(calls) == 1


def test_cache_lasts_a_raid_night():
    # Luta que já subiu não muda: a lista fica no cache por horas, não minutos.
    now = [0.0]
    cache = ReportCache(clock=lambda: now[0])
    calls: list = []
    source = counting_source(calls, cache=cache)

    source.get_report("TESTE123")
    now[0] = 3 * 60 * 60
    source.get_report("TESTE123")

    assert len(calls) == 1


def test_cache_expires():
    now = [0.0]
    cache = ReportCache(ttl_s=300, clock=lambda: now[0])
    calls: list = []
    source = counting_source(calls, cache=cache)

    source.get_report("TESTE123")
    now[0] = 299
    source.get_report("TESTE123")
    now[0] = 300
    source.get_report("TESTE123")

    assert len(calls) == 2


def test_refresh_brings_new_fights_of_a_live_log():
    now = [0.0]
    wcl = FakeWcl()
    wcl.report["fights"] = REPORT["fights"][:2]
    source = wcl.source(cache=ReportCache(clock=lambda: now[0]))
    first = source.get_report("TESTE123")
    assert [f.id for f in first.fights] == [1, 2]

    # Novo pull na progressão: sem atualizar, a lista guardada continua valendo.
    wcl.report["fights"].append(nekzali(5, 1_300_000, 1_450_000))
    now[0] = 120
    assert [f.id for f in source.get_report("TESTE123").fights] == [1, 2]

    refreshed = source.get_report("TESTE123", refresh=True)

    assert [f.id for f in refreshed.fights] == [1, 2, 5]
    assert refreshed.fetched_at >= first.fetched_at  # a tela mostra a hora da lista nova
    # E o cache passa a ter a lista nova.
    assert [f.id for f in source.get_report("TESTE123").fights] == [1, 2, 5]
    assert wcl.calls == ["ReportFights", "ReportFights"]


def test_player_who_joined_in_the_middle_of_the_night():
    # Jogador que entrou na raide depois da lista guardada: aparece na luta nova.
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(cache=ReportCache(clock=lambda: now[0]))
    source.get_report("TESTE123")

    wcl.mages.append(
        {"id": 20, "name": "arcano_novo", "server": "Norte", "type": "Player", "subType": "Mage"}
    )
    wcl.report["fights"].append(nekzali(5, 1_300_000, 1_450_000))
    wcl.fight_players[5] = ([10, 20], ["Arcane", "Arcane"], [327, 321])
    now[0] = 120
    source.get_report("TESTE123", refresh=True)

    players = source.get_fight_players("TESTE123", 5)

    assert [(p.actor_id, p.name, p.item_level) for p in players] == [
        (10, "arcano_a", 327),
        (20, "arcano_novo", 321),
    ]


def test_refresh_right_after_a_fetch_uses_the_cache():
    # Cliques repetidos (ou dois magos da raide) não gastam pontos à toa.
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(cache=ReportCache(clock=lambda: now[0]))
    source.get_report("TESTE123")

    now[0] = REFRESH_MIN_INTERVAL_S - 1
    source.get_report("TESTE123", refresh=True)
    now[0] = REFRESH_MIN_INTERVAL_S + 1
    source.get_report("TESTE123", refresh=True)

    assert wcl.calls == ["ReportFights", "ReportFights"]


def test_failed_refresh_keeps_the_cached_list():
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(cache=ReportCache(clock=lambda: now[0]))
    source.get_report("TESTE123")

    wcl.status = 503
    now[0] = 120
    with pytest.raises(SourceUnavailableError):
        source.get_report("TESTE123", refresh=True)

    assert [f.id for f in source.get_report("TESTE123").fights] == [1, 2, 3, 4]
    assert wcl.calls == ["ReportFights", "ReportFights"]


def test_cache_keeps_only_the_newest_reports():
    cache = ReportCache(max_items=2)
    report = SampleReportSource().get_report(SAMPLE_REPORT_CODE)

    for code in ("A", "B", "C"):
        cache.put(code, report)

    assert cache.get("A") is None
    assert cache.get("B") is not None and cache.get("C") is not None


def test_cached_report_is_a_copy():
    source = counting_source([], cache=ReportCache())

    source.get_report("TESTE123").fights.clear()

    assert len(source.get_report("TESTE123").fights) == 4


def test_cached_players_are_a_copy():
    source = FakeWcl().source()

    source.get_fight_players("TESTE123", 2).clear()

    assert len(source.get_fight_players("TESTE123", 2)) == 2


def test_failures_are_not_cached():
    cache = ReportCache()
    failing = WclReportSource(
        client_factory=lambda: fake_client(report_body(REPORT), status=503), cache=cache
    )
    with pytest.raises(SourceUnavailableError):
        failing.get_report("TESTE123")
    private = WclReportSource(
        client_factory=lambda: fake_client(report_body(None, [{"message": "Sem permissão"}])),
        cache=cache,
    )
    with pytest.raises(ReportNotAvailableError):
        private.get_report("TESTE123")

    # Assim que a API volta (ou o report fica público), o próximo pedido já funciona.
    assert counting_source([], cache=cache).get_report("TESTE123").sample is False


def test_sample_fallback_is_not_cached():
    # O plano B não pode "grudar": com a API de volta, vem o report real.
    cache = ReportCache()
    down = WclReportSource(
        client_factory=lambda: fake_client(report_body(REPORT), status=500), cache=cache
    )
    assert down.get_report(SAMPLE_REPORT_CODE).sample is True

    up = WclReportSource(
        client_factory=lambda: fake_client(report_body(REPORT | {"code": SAMPLE_REPORT_CODE})),
        cache=cache,
    )
    assert up.get_report(SAMPLE_REPORT_CODE).sample is False


def test_source_does_not_close_the_shared_client():
    calls: list = []
    client = fake_client(report_body(REPORT), calls=calls)
    WclReportSource(client_factory=lambda: client, cache=ReportCache()).get_report("UM")
    WclReportSource(client_factory=lambda: client, cache=ReportCache()).get_report("DOIS")

    assert len(calls) == 2  # o segundo pedido usou o mesmo cliente, ainda aberto


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
