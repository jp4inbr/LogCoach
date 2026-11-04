"""WclReportSource com respostas falsas da API (nada aqui acessa a internet)."""

import copy
import json
import threading
import time
from typing import get_args

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.schemas import FIGHT_REASON_MESSAGES, FightOption, FightReasonCode
from app.services import sources
from app.services.sources import (
    LIVE_WINDOW_S,
    QUERY_LIMIT,
    QUERY_WINDOW_S,
    REFRESH_MIN_INTERVAL_S,
    SAMPLE_REPORT_CODE,
    WCL_COOLDOWN_MAX_S,
    WCL_COOLDOWN_S,
    WCL_RATE_LIMIT_COOLDOWN_S,
    ClientLimiter,
    FightDataStore,
    FightNotFoundError,
    PlayerNotFoundError,
    QueryLimitError,
    ReportCache,
    ReportNotAvailableError,
    SampleReportSource,
    SourceUnavailableError,
    WclCooldown,
    WclReportSource,
    build_report,
    get_report_source,
)
from app.wcl.client import (
    CONFIG_MESSAGE,
    QUERY_MESSAGE,
    TOKEN_URL,
    UNAVAILABLE_MESSAGE,
    WclClient,
    WclUnavailableError,
)
from app.wcl.fetch import fetch_report

NEKZALI = 3470


def wait_prefetch() -> None:
    """Espera a fila de pré-busca do processo rodar até o fim e desliga o executor.

    O `shutdown_prefetch` cancela o que está na fila (desligamento do app); aqui o teste
    quer que a pré-busca aconteça.
    """
    with sources._prefetch_lock:
        executor, sources._prefetch_executor = sources._prefetch_executor, None
    if executor is not None:
        executor.shutdown(wait=True)


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


def now_ms() -> float:
    return time.time() * 1000


class FakeWcl:
    """API falsa que responde cada consulta pelo nome e conta as chamadas."""

    def __init__(self, report: dict | None = None, status: int = 200) -> None:
        self.report = copy.deepcopy(REPORT if report is None else report)
        self.mages = copy.deepcopy(MAGES)
        self.fight_players = copy.deepcopy(FIGHT_PLAYERS)
        self.details: dict = {}
        self.status = status
        # `endTime` do report (último evento recebido). None = agora: log ao vivo.
        self.end_time: float | None = None
        self.headers: dict[str, str] = {}  # da resposta de erro (ex.: Retry-After)
        self.calls: list[str] = []
        # Consulta (pelo nome) → exceção levantada no transporte (timeout, rede).
        self.raise_on: dict[str, Exception] = {}
        # Eventos da luta: com `gate`, cada página espera o teste liberar (busca "lenta").
        self.gate: threading.Event | None = None
        self.fetching = threading.Event()  # a busca de uma luta completa começou

    def handler(self, request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        body = json.loads(request.content)
        name = body["query"].split("(")[0].split()[-1]
        self.calls.append(name)
        if name in self.raise_on:
            raise self.raise_on[name]
        if name == "FightMeta":
            self.fetching.set()
        if name == "Events" and self.gate is not None:
            assert self.gate.wait(timeout=5), "o teste não liberou a busca"
        if self.status != 200:
            return httpx.Response(self.status, json={}, headers=self.headers)
        if name == "ReportFights":
            end_time = now_ms() if self.end_time is None else self.end_time
            return httpx.Response(200, json=report_body(self.report | {"endTime": end_time}))
        fight_id = body["variables"]["fightID"]
        if name == "FightMeta":
            return httpx.Response(200, json=report_body(self.fight_meta(fight_id)))
        if name == "Events":
            return httpx.Response(200, json=report_body({"events": self.events(body)}))
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

    def fight_meta(self, fight_id: int) -> dict:
        """FIGHT_META: a luta, os atores e as habilidades do report."""
        fights = [
            f | {"size": 20, "phaseTransitions": []}
            for f in self.report["fights"]
            if f["id"] == fight_id
        ]
        actors = [a | {"petOwner": None, "gameID": 0} for a in self.mages]
        details = {"data": {"playerDetails": {"dps": [{"id": a["id"]} for a in self.mages]}}}
        return {"code": self.report["code"], "startTime": 0, "fights": fights, "phases": [],
                "masterData": {"actors": actors,
                               "abilities": [{"gameID": 30451, "name": "Arcane Blast"}]},
                "playerDetails": details}  # fmt: skip

    @staticmethod
    def events(body: dict) -> dict:
        """Uma página de eventos: um Arcane Blast do jogador nos casts, nada no resto."""
        variables = body["variables"]
        data = []
        if variables["dataType"] == "Casts" and variables["sourceID"] is not None:
            data = [{"timestamp": variables["startTime"] + 1000, "type": "cast",
                     "sourceID": variables["sourceID"], "targetID": -1,
                     "abilityGameID": 30451, "fight": variables["fightID"]}]  # fmt: skip
        return {"data": data, "nextPageTimestamp": None}

    def count(self, name: str) -> int:
        return self.calls.count(name)

    def client(self) -> WclClient:
        return WclClient("id", "secret", transport=httpx.MockTransport(self.handler))

    def source(
        self,
        cache: ReportCache | None = None,
        fight_data: FightDataStore | None = None,
        executor=None,
        limiter: ClientLimiter | None = None,
        clock=None,
        queries: ClientLimiter | None = None,
    ) -> WclReportSource:
        # Caches, limite e falha lembrada próprios por padrão: cada FakeWcl é uma API nova.
        # `clock` (lista de um número, como nos outros testes) vale para o cache da lista e
        # para a falha lembrada. A pré-busca usa o executor do processo (que o
        # `fresh_wcl_state` desliga no fim de cada teste), a menos que o teste passe o dele.
        client = self.client()
        extra = {} if executor is None else {"executor_factory": lambda: executor}
        tick = time.monotonic if clock is None else (lambda: clock[0])
        return WclReportSource(
            client_factory=lambda: client,
            cache=ReportCache(clock=tick) if cache is None else cache,
            players=ReportCache(),
            fight_data=FightDataStore() if fight_data is None else fight_data,
            limiter=ClientLimiter() if limiter is None else limiter,
            cooldown=WclCooldown(clock=tick),
            queries=query_limiter_for(tick) if queries is None else queries,
            **extra,
        )


def query_limiter_for(clock) -> ClientLimiter:
    return ClientLimiter(QUERY_LIMIT, QUERY_WINDOW_S, global_max_calls=None, clock=clock)


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
    assert fight.unsupported_code is None
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
    assert fight.unsupported_code == "short"
    assert fight.unsupported_reason == FIGHT_REASON_MESSAGES["short"]


def test_fight_still_uploading_is_not_supported():
    # Log ao vivo: a luta em andamento ainda vai crescer. Atualizar as lutas libera ela.
    report = copy.deepcopy(REPORT) | {"endTime": now_ms()}  # recebendo dados agora
    report["fights"][1]["inProgress"] = True

    fights = source_for(report).get_report("TESTE123").fights

    assert fights[1].supported is False
    assert fights[1].unsupported_code == "in_progress"
    assert fights[1].unsupported_reason == FIGHT_REASON_MESSAGES["in_progress"]
    # A tela mostra a luta subindo diferente das não suportadas e atualiza sozinha.
    assert fights[1].in_progress is True
    assert [f.in_progress for f in fights if f.id != 2] == [False, False, False]


def test_fight_still_uploading_with_few_seconds_is_not_short():
    # A duração parcial (41 s até agora) ainda vai crescer: o motivo é estar subindo.
    report = copy.deepcopy(REPORT) | {"endTime": now_ms()}
    report["fights"][0]["inProgress"] = True

    fight = source_for(report).get_report("TESTE123").fights[0]

    assert (fight.in_progress, fight.unsupported_code) == (True, "in_progress")
    assert fight.unsupported_reason == FIGHT_REASON_MESSAGES["in_progress"]


@pytest.mark.parametrize(
    ("fight_id", "code"),
    [(3, "unsupported_boss"), (4, "unsupported_difficulty")],
)
def test_unsupported_fight_still_uploading_is_not_marked_as_uploading(fight_id, code):
    # Outro chefe ou Nek'zali Normal terminariam cinza de qualquer jeito: nada de "subindo".
    report = copy.deepcopy(REPORT) | {"endTime": now_ms()}
    for fight in report["fights"]:
        fight["inProgress"] = True
        if fight["id"] == fight_id:
            fight["endTime"] = fight["startTime"] + 20_000  # poucos segundos até agora

    fight = next(f for f in source_for(report).get_report("TESTE123").fights if f.id == fight_id)

    assert fight.in_progress is False
    assert fight.supported is False
    assert fight.unsupported_code == code
    assert fight.unsupported_reason == FIGHT_REASON_MESSAGES[code]


def test_boss_without_rules_is_not_supported():
    fight = source_for(REPORT).get_report("TESTE123").fights[2]

    assert fight.boss == "Outro Chefe"  # sem tradução: nome do Warcraft Logs
    assert fight.supported is False
    assert fight.unsupported_code == "unsupported_boss"
    assert fight.unsupported_reason == FIGHT_REASON_MESSAGES["unsupported_boss"]


def test_every_fight_reason_code_has_a_message():
    # Código novo no Literal sem texto quebraria a tela com KeyError.
    assert set(get_args(FightReasonCode)) == set(FIGHT_REASON_MESSAGES)


@pytest.mark.parametrize(("supported", "code"), [(False, None), (True, "short")])
def test_fight_option_refuses_code_that_does_not_match_supported(supported, code):
    # Luta em cinza sem código cairia num motivo errado (ex.: chave antiga no exemplo).
    with pytest.raises(ValidationError):
        FightOption(id=1, boss="Chefe", difficulty="Mítico", kill=True, duration_s=300.0,
                    supported=supported, unsupported_code=code)  # fmt: skip


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
    assert fights[4].unsupported_code == "unsupported_difficulty"
    assert fights[4].unsupported_reason == FIGHT_REASON_MESSAGES["unsupported_difficulty"]


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


def test_empty_mage_list_is_not_cached():
    # Logo depois da luta o WCL pode ainda não ter os dados de combate: "nenhum Arcano"
    # guardado por 6 h esconderia o mago quando o WCL terminar.
    wcl = FakeWcl()
    wcl.fight_players[2] = ([], [], [])
    source = wcl.source()
    assert source.get_fight_players("TESTE123", 2) == []

    wcl.fight_players[2] = FIGHT_PLAYERS[2]

    assert [p.actor_id for p in source.get_fight_players("TESTE123", 2)] == [10, 13]
    assert [p.actor_id for p in source.get_fight_players("TESTE123", 2)] == [10, 13]
    assert wcl.calls == ["FightPlayers", "FightPlayers"]  # a lista com Magos ficou no cache


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
    source = wcl.source(clock=now)
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
    source = wcl.source(clock=now)
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
    source = wcl.source(clock=now)
    source.get_report("TESTE123")

    now[0] = REFRESH_MIN_INTERVAL_S - 1
    source.get_report("TESTE123", refresh=True)
    now[0] = REFRESH_MIN_INTERVAL_S + 1
    source.get_report("TESTE123", refresh=True)

    assert wcl.calls == ["ReportFights", "ReportFights"]


def test_refresh_interval_is_short():
    # Quem acabou de ver a luta terminar e cola o link não pode receber a lista de antes.
    assert REFRESH_MIN_INTERVAL_S == 8


def test_failed_refresh_returns_the_cached_list_as_stale():
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(clock=now)
    first = source.get_report("TESTE123")

    wcl.status = 503
    now[0] = 120
    stale = source.get_report("TESTE123", refresh=True)

    assert [f.id for f in stale.fights] == [1, 2, 3, 4]
    assert stale.stale is True
    assert "fora do ar" in stale.stale_message
    assert stale.stale_code == "wcl_unavailable"
    assert stale.fetched_at == first.fetched_at  # hora da lista guardada
    assert (first.stale, first.stale_message, first.stale_code) == (False, None, None)
    # O guardado não vira "stale": a lista do cache continua como veio da API.
    assert source.get_report("TESTE123").stale is False
    assert wcl.calls == ["ReportFights", "ReportFights"]


def test_failed_refresh_with_rate_limit_brings_its_message():
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(clock=now)
    source.get_report("TESTE123")

    wcl.status = 429
    now[0] = 120

    assert "limitando os pedidos" in source.get_report("TESTE123", refresh=True).stale_message


def test_failed_fetch_without_cached_list_raises():
    with pytest.raises(SourceUnavailableError):
        FakeWcl(status=503).source().get_report("TESTE123", refresh=True)


def test_report_gone_private_is_not_stale():
    # A API respondeu (sem o report): não é falha do WCL, então nada de lista guardada.
    now = [0.0]
    cache = ReportCache(clock=lambda: now[0])
    WclReportSource(
        client_factory=lambda: fake_client(report_body(REPORT)), cache=cache, players=ReportCache()
    ).get_report("TESTE123")
    now[0] = 120

    private = WclReportSource(
        client_factory=lambda: fake_client(report_body(None)), cache=cache, players=ReportCache()
    )
    with pytest.raises(ReportNotAvailableError):
        private.get_report("TESTE123", refresh=True)


def test_broken_query_is_our_error_not_wcl_down():
    body = {"errors": [{"message": 'Cannot query field "x" on type "Report".'}]}
    source = WclReportSource(
        client_factory=lambda: fake_client(body), cache=ReportCache(), players=ReportCache()
    )

    with pytest.raises(SourceUnavailableError) as info:
        source.get_report("TESTE123")

    assert info.value.error_code == "unexpected_error"
    assert info.value.user_message == QUERY_MESSAGE
    assert str(info.value) == "TESTE123"


def test_failed_refresh_with_config_error_keeps_its_code():
    # Erro nosso (credencial recusada): a lista guardada leva o código, não "fora do ar".
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(clock=now)
    source.get_report("TESTE123")

    wcl.status = 403  # JSON, não Cloudflare: acesso negado à nossa credencial
    now[0] = 120
    stale = source.get_report("TESTE123", refresh=True)

    assert stale.stale is True
    assert (stale.stale_code, stale.stale_message) == ("unexpected_error", CONFIG_MESSAGE)


# --- Falha lembrada (WclCooldown) ---------------------------------------------------


def test_failure_is_remembered_and_the_api_is_not_called_again():
    # Várias abas atualizando a lista com o WCL fora do ar: uma consulta só até a pausa passar.
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(clock=now)
    source.get_report("TESTE123")
    wcl.status = 503
    now[0] = 120
    first = source.get_report("TESTE123", refresh=True)

    now[0] = 120 + WCL_COOLDOWN_S - 1
    again = [source.get_report("TESTE123", refresh=True) for _ in range(5)]

    assert wcl.calls == ["ReportFights", "ReportFights"]
    assert all(r.stale and r.stale_message == first.stale_message for r in again)
    assert all(r.stale_code == "wcl_unavailable" for r in again)
    # Passada a pausa, uma consulta testa a API de novo.
    now[0] = 120 + WCL_COOLDOWN_S
    wcl.status = 200
    assert source.get_report("TESTE123", refresh=True).stale is False
    assert wcl.count("ReportFights") == 3


def test_pause_is_at_least_the_refresh_interval():
    assert WCL_COOLDOWN_S >= REFRESH_MIN_INTERVAL_S


def test_remembered_failure_without_cached_list_is_the_same_error():
    now = [0.0]
    wcl = FakeWcl(status=403)
    source = wcl.source(clock=now)
    with pytest.raises(SourceUnavailableError):
        source.get_report("TESTE123")

    with pytest.raises(SourceUnavailableError) as info:
        source.get_report("OUTRO456")  # vale para o processo: o limite e a queda são do WCL

    assert (info.value.error_code, info.value.user_message) == ("unexpected_error", CONFIG_MESSAGE)
    assert str(info.value) == "OUTRO456"
    assert wcl.count("ReportFights") == 1


def test_remembered_failure_also_holds_players_and_fight_data():
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(clock=now)
    source.get_report("TESTE123")
    wcl.status = 503
    with pytest.raises(SourceUnavailableError):
        source.get_fight_players("TESTE123", 2)
    calls = len(wcl.calls)

    with pytest.raises(SourceUnavailableError):
        source.get_fight_players("TESTE123", 4)
    with pytest.raises(SourceUnavailableError):
        source.get_fight_data("TESTE123", 2, 10)
    with pytest.raises(SourceUnavailableError):
        source.prefetch("TESTE123", 2, 10, client="ana")

    assert len(wcl.calls) == calls


def test_remembered_failure_does_not_spend_the_prefetch_limit():
    now = [0.0]
    wcl = FakeWcl(status=503)
    limiter = ClientLimiter(max_calls=1, clock=lambda: now[0])
    source = wcl.source(clock=now, limiter=limiter)
    with pytest.raises(SourceUnavailableError):
        source.get_report("TESTE123")

    with pytest.raises(SourceUnavailableError):
        source.prefetch("TESTE123", 2, 10, client="ana")

    assert limiter.take("ana") is True  # a pré-busca negada pela pausa não contou


def test_sample_report_opens_during_the_pause():
    now = [0.0]
    wcl = FakeWcl(status=503)
    source = wcl.source(clock=now)
    with pytest.raises(SourceUnavailableError):
        source.get_report("TESTE123")

    assert source.get_report(SAMPLE_REPORT_CODE).sample is True
    assert wcl.count("ReportFights") == 1


def test_private_report_does_not_pause_the_api():
    # A API respondeu (sem o report): nada a esperar.
    now = [0.0]
    pause = WclCooldown(clock=lambda: now[0])
    private = WclReportSource(
        client_factory=lambda: fake_client(report_body(None)),
        cache=ReportCache(),
        players=ReportCache(),
        cooldown=pause,
    )
    with pytest.raises(ReportNotAvailableError):
        private.get_report("TESTE123")

    assert pause.active() is None


@pytest.mark.parametrize(
    ("headers", "pause_s"),
    [
        ({"retry-after": "120"}, 120),  # o tempo que o WCL pediu
        ({"retry-after": "2"}, WCL_COOLDOWN_S),  # no mínimo a pausa comum
        ({"retry-after": "7200"}, WCL_COOLDOWN_MAX_S),  # com teto
        ({}, WCL_RATE_LIMIT_COOLDOWN_S),  # sem o cabeçalho
    ],
)
def test_rate_limit_pauses_for_the_time_the_wcl_asked(headers, pause_s):
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(clock=now)
    source.get_report("TESTE123")
    wcl.status, wcl.headers = 429, headers
    now[0] = 120
    source.get_report("TESTE123", refresh=True)

    now[0] = 120 + pause_s - 0.5
    assert source.get_report("TESTE123", refresh=True).stale is True
    assert wcl.count("ReportFights") == 2
    now[0] = 120 + pause_s
    source.get_report("TESTE123", refresh=True)
    assert wcl.count("ReportFights") == 3


def test_rate_limit_constants():
    # Limite sem Retry-After: 1 min (o de pontos é por hora); Retry-After respeitado até 5 min.
    assert (WCL_RATE_LIMIT_COOLDOWN_S, WCL_COOLDOWN_MAX_S) == (60, 300)


def test_rate_limit_message_counts_down_during_the_pause():
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(clock=now)
    source.get_report("TESTE123")
    wcl.status, wcl.headers = 429, {"retry-after": "180"}
    now[0] = 120

    assert "uns 3 minutos" in source.get_report("TESTE123", refresh=True).stale_message
    now[0] = 120 + 90
    assert "uns 2 minutos" in source.get_report("TESTE123", refresh=True).stale_message
    now[0] = 120 + 170
    assert "uns 1 minuto" in source.get_report("TESTE123", refresh=True).stale_message
    assert wcl.count("ReportFights") == 2


def test_longer_pause_wins():
    # Uma consulta que já estava no ar e falha com 503 não encurta a pausa do 429.
    now = [0.0]
    pause = WclCooldown(clock=lambda: now[0])
    pause.fail(WclUnavailableError("429", "limite", rate_limited=True, retry_after_s=120))
    pause.fail(WclUnavailableError("503", "fora do ar"))

    now[0] = 119
    assert pause.active() is not None
    now[0] = 120
    assert pause.active() is None


def test_network_error_outside_the_client_also_pauses():
    now = [0.0]
    pause = WclCooldown(clock=lambda: now[0])
    pause.fail(httpx.ConnectError("sem rede"))

    assert pause.active() == (UNAVAILABLE_MESSAGE, "wcl_unavailable")
    now[0] = WCL_COOLDOWN_S
    assert pause.active() is None


class LockProbe:
    """Valor que anota se algum dos locks estava preso quando foi copiado."""

    def __init__(self, *locks) -> None:
        self.locks = locks
        self.locked_on_copy: list[bool] = []

    def __deepcopy__(self, memo):
        self.locked_on_copy.append(any(lock.locked() for lock in self.locks))
        return self


def test_cache_copies_outside_the_lock():
    # Os eventos de uma luta são MB: copiar com o lock preso travaria as outras rotas.
    cache = ReportCache()
    probe = LockProbe(cache._lock)

    cache.put("chave", probe)
    cache.get("chave")

    assert probe.locked_on_copy == [False, False]


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
    now = [0.0]
    cache = ReportCache()
    pause = WclCooldown(clock=lambda: now[0])
    failing = WclReportSource(
        client_factory=lambda: fake_client(report_body(REPORT), status=503),
        cache=cache,
        cooldown=pause,
    )
    with pytest.raises(SourceUnavailableError):
        failing.get_report("TESTE123")
    now[0] = WCL_COOLDOWN_S  # passada a pausa depois da falha
    private = WclReportSource(
        client_factory=lambda: fake_client(report_body(None, [{"message": "Sem permissão"}])),
        cache=cache,
        cooldown=pause,
    )
    with pytest.raises(ReportNotAvailableError):
        private.get_report("TESTE123")

    # Assim que a API volta (ou o report fica público), o próximo pedido já funciona.
    assert counting_source([], cache=cache).get_report("TESTE123").sample is False


def test_sample_fallback_is_not_cached():
    # O plano B não pode "grudar": com a API de volta, vem o report real.
    now = [0.0]
    cache = ReportCache()
    pause = WclCooldown(clock=lambda: now[0])
    down = WclReportSource(
        client_factory=lambda: fake_client(report_body(REPORT), status=500),
        cache=cache,
        cooldown=pause,
    )
    assert down.get_report(SAMPLE_REPORT_CODE).sample is True

    now[0] = WCL_COOLDOWN_S
    up = WclReportSource(
        client_factory=lambda: fake_client(report_body(REPORT | {"code": SAMPLE_REPORT_CODE})),
        cache=cache,
        cooldown=pause,
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
    from conftest import make_result

    from app.services.sources import fill_real_names

    result = make_result()
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
    from conftest import make_result

    from app.services.sources import fill_real_names

    result = make_result()

    fill_real_names(result, tmp_path / "nao-existe.json")

    assert all(p.name is None for p in result.comparison.players)


# --- Log ao vivo e envio parado (build_report) -----------------------------------------

LIVE_ENCOUNTERS = {NEKZALI: {"boss_npc_id": None, "difficulties": [5]}}
NOW_MS = 2_000_000_000_000.0


def live_raw(end_time: float | None) -> dict:
    # Luta 5: Nek'zali Mítico subindo; luta 6: outro chefe subindo.
    other = {"id": 6, "encounterID": 9999, "name": "Outro Chefe", "difficulty": 5,
             "kill": False, "startTime": 0, "endTime": 20_000, "inProgress": True}  # fmt: skip
    fights = [nekzali(2, 0, 415_000, kill=True), nekzali(5, 0, 20_000, inProgress=True), other]
    return {"code": "TESTE123", "title": "Ao vivo", "end_time": end_time, "fights": fights}


def built(end_time: float | None) -> dict:
    report = build_report(live_raw(end_time), LIVE_ENCOUNTERS, {}, now_ms=NOW_MS)
    return report | {"fights": {f["id"]: f for f in report["fights"]}}


def test_log_receiving_data_is_live_and_its_fight_is_uploading():
    report = built(NOW_MS - LIVE_WINDOW_S * 1000)  # último evento há 10 min: ainda vale

    assert report["live"] is True
    fight = report["fights"][5]
    assert (fight["in_progress"], fight["upload_paused"]) == (True, False)
    assert fight["unsupported_code"] == "in_progress"


def test_log_without_new_data_pauses_the_uploading_fight():
    report = built(NOW_MS - LIVE_WINDOW_S * 1000 - 1)

    assert report["live"] is False
    fight = report["fights"][5]
    assert (fight["in_progress"], fight["upload_paused"], fight["supported"]) == (
        False,
        True,
        False,
    )
    assert fight["unsupported_code"] == "upload_paused"
    # As lutas que terminaram não mudam.
    assert report["fights"][2]["supported"] is True
    assert report["fights"][2]["upload_paused"] is False


@pytest.mark.parametrize("end_time", [NOW_MS, NOW_MS - 3_600_000])
def test_other_boss_uploading_stays_plain_unsupported(end_time):
    fight = built(end_time)["fights"][6]

    assert (fight["in_progress"], fight["upload_paused"]) == (False, False)
    assert fight["unsupported_code"] == "unsupported_boss"


def test_report_without_end_time_is_not_live():
    report = built(None)

    assert report["live"] is False
    assert report["fights"][5]["upload_paused"] is True


def test_fetch_report_passes_the_end_time():
    body = report_body(REPORT | {"endTime": NOW_MS})

    assert fetch_report(fake_client(body), "TESTE123")["end_time"] == NOW_MS


def test_live_comes_in_the_report():
    wcl = FakeWcl()
    assert wcl.source().get_report("TESTE123").live is True

    wcl.end_time = now_ms() - (LIVE_WINDOW_S + 60) * 1000
    assert wcl.source().get_report("TESTE123").live is False


def test_sample_report_is_not_live_and_has_no_paused_fight():
    report = SampleReportSource().get_report(SAMPLE_REPORT_CODE)

    assert report.live is False
    assert not any(f.upload_paused for f in report.fights)


# --- Limite de consultas por cliente ---------------------------------------------------


def spend_queries(source: WclReportSource, now: list[float], client: str = "ana") -> None:
    """Gasta as `QUERY_LIMIT` consultas do cliente, todas indo à API (passada a trava)."""
    for _ in range(QUERY_LIMIT):
        now[0] += REFRESH_MIN_INTERVAL_S
        source.get_report("TESTE123", refresh=True, client=client)


def test_query_limit_per_client():
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(clock=now)
    spend_queries(source, now)
    assert wcl.count("ReportFights") == QUERY_LIMIT

    with pytest.raises(QueryLimitError) as info:
        source.get_fight_players("TESTE123", 2, client="ana")

    assert wcl.count("FightPlayers") == 0
    # A 1ª foi em t=8 e agora é t=160: faltam 30 min - 152 s (~28 min).
    assert info.value.wait_s == QUERY_WINDOW_S - (now[0] - REFRESH_MIN_INTERVAL_S)
    assert info.value.error_code == "query_limit"
    assert "20 a cada 30 minutos" in info.value.user_message
    assert info.value.user_message.endswith("Tente de novo em 28 min.")


def test_query_limit_window_slides():
    now = [0.0]
    source = FakeWcl().source(clock=now)
    spend_queries(source, now)

    now[0] = REFRESH_MIN_INTERVAL_S + QUERY_WINDOW_S  # a 1ª saiu da janela
    assert source.get_fight_players("TESTE123", 2, client="ana")


def test_query_limit_message_has_at_least_one_minute():
    assert QueryLimitError("X", 5).user_message.endswith("Tente de novo em 1 min.")


def test_cache_hit_does_not_count_in_the_query_limit():
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(clock=now)
    for _ in range(QUERY_LIMIT + 5):
        source.get_report("TESTE123", client="ana")  # da lista guardada
        source.get_report("TESTE123", refresh=True, client="ana")  # menos de 8 s depois

    assert wcl.count("ReportFights") == 1
    assert source.get_fight_players("TESTE123", 2, client="ana")


def test_query_limit_brings_the_cached_list_as_stale():
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(clock=now)
    spend_queries(source, now)

    now[0] += REFRESH_MIN_INTERVAL_S
    report = source.get_report("TESTE123", refresh=True, client="ana")

    assert wcl.count("ReportFights") == QUERY_LIMIT
    assert (report.stale, report.stale_code) == (True, "query_limit")
    assert "20 a cada 30 minutos" in report.stale_message


def test_query_limit_without_cached_list_raises():
    now = [0.0]
    source = FakeWcl().source(clock=now)
    for _ in range(QUERY_LIMIT):
        source.get_fight_players("TESTE123", 4, client="ana")  # vem vazia: não fica no cache

    with pytest.raises(QueryLimitError):
        source.get_report("TESTE123", client="ana")


def test_query_limit_is_per_client():
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(clock=now)
    spend_queries(source, now, client="ana")

    assert source.get_fight_players("TESTE123", 2, client="bia")
    assert wcl.count("FightPlayers") == 1


def test_sample_report_does_not_count_in_the_query_limit():
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(clock=now)
    for _ in range(QUERY_LIMIT + 5):
        now[0] += REFRESH_MIN_INTERVAL_S
        source.get_report(SAMPLE_REPORT_CODE, refresh=True, client="ana")

    assert wcl.count("ReportFights") == QUERY_LIMIT + 5
    assert source.get_fight_players("TESTE123", 2, client="ana")


def test_without_client_there_is_no_query_limit():
    # Pré-busca e motor (get_fight_data) não passam cliente: têm o próprio limite.
    now = [0.0]
    wcl = FakeWcl()
    source = wcl.source(clock=now)
    for _ in range(QUERY_LIMIT + 5):
        now[0] += REFRESH_MIN_INTERVAL_S
        source.get_report("TESTE123", refresh=True)

    assert wcl.count("ReportFights") == QUERY_LIMIT + 5


def test_query_limit_defaults():
    assert (QUERY_LIMIT, QUERY_WINDOW_S) == (20, 30 * 60)
    assert sources.query_limiter.take("ana") is True  # zerado entre testes


# --- Luta e jogador que não existem; relatório arquivado -------------------------------


def test_fight_missing_in_the_players_query_is_fight_not_found():
    wcl = FakeWcl()
    source = wcl.source()

    with pytest.raises(FightNotFoundError):
        source.get_fight_players("TESTE123", 99)
    # A API respondeu: nada de pausa.
    assert source.get_report("TESTE123")


def test_player_missing_in_the_fight_data_is_player_not_found():
    with pytest.raises(PlayerNotFoundError):
        FakeWcl().source().get_fight_data("TESTE123", 2, 999)


def test_archived_report_is_report_not_available_marked_archived():
    errors = [{"message": "This report has been archived.", "path": ["reportData", "report"]}]

    with pytest.raises(ReportNotAvailableError) as info:
        source_for(None, errors).get_report("TESTE123")

    assert info.value.archived is True


def test_private_report_is_not_archived():
    errors = [{"message": "You do not have permission to view this report."}]

    with pytest.raises(ReportNotAvailableError) as info:
        source_for(None, errors).get_report("TESTE123")

    assert info.value.archived is False


# --- Pausa depois de falha da busca pesada ---------------------------------------------


@pytest.mark.parametrize(
    "error", [httpx.ReadTimeout("lento"), httpx.ConnectError("sem rede")], ids=["timeout", "rede"]
)
def test_heavy_fetch_timeout_or_network_does_not_pause(error):
    wcl = FakeWcl()
    wcl.raise_on["FightMeta"] = error
    source = wcl.source()

    with pytest.raises(SourceUnavailableError):
        source.get_fight_data("TESTE123", 2, 10)

    # A lista e os Magos continuam indo à API.
    assert source.get_report("TESTE123")
    assert source.get_fight_players("TESTE123", 2)
    assert wcl.count("ReportFights") == wcl.count("FightPlayers") == 1


@pytest.mark.parametrize("status", [429, 503])
def test_heavy_fetch_rate_limit_or_5xx_pauses(status):
    wcl = FakeWcl(status=status)
    source = wcl.source()

    with pytest.raises(SourceUnavailableError):
        source.get_fight_data("TESTE123", 2, 10)
    wcl.status = 200

    with pytest.raises(SourceUnavailableError):
        source.get_report("TESTE123")
    assert wcl.count("ReportFights") == 0


def test_light_query_timeout_still_pauses():
    wcl = FakeWcl()
    wcl.raise_on["ReportFights"] = httpx.ReadTimeout("lento")
    source = wcl.source()

    with pytest.raises(SourceUnavailableError):
        source.get_report("TESTE123")
    del wcl.raise_on["ReportFights"]

    with pytest.raises(SourceUnavailableError):
        source.get_fight_players("TESTE123", 2)
    assert wcl.count("FightPlayers") == 0
