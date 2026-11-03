"""Formatos de entrada e saída da API.

`AnalysisResult` é o contrato entre o motor de análise e o frontend: o motor
(frente do Arthur) devolve um objeto nesse formato, e as telas só leem dele.
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, computed_field, model_validator

Status = Literal["ok", "atencao", "erro"]


# --- Contas ---------------------------------------------------------------


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginData(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class Me(BaseModel):
    email: EmailStr
    created_at: datetime
    plan: Literal["gratis"] = "gratis"
    analyses_this_month: int
    monthly_limit: int


# --- Relatório do Warcraft Logs ------------------------------------------


class ReportResolveRequest(BaseModel):
    # Colar o link, "Atualizar lutas" e a atualização automática buscam a lista de novo no
    # Warcraft Logs (com a trava de 8 s). O antigo campo `refresh`, se vier, é ignorado.
    url: str


class PlayerOption(BaseModel):
    # Na escolha da luta o nome não é ocultado: o usuário está escolhendo a si mesmo.
    # Id do ator no report do WCL (masterData.actors): chave do jogador do resolve até o motor.
    actor_id: int
    name: str
    # O mesmo nome se repete entre reinos: na tela o reino diferencia; na API vale o actor_id.
    server: str | None = None
    spec: str
    item_level: int | None = None


# Motivo para a luta aparecer em cinza (item 8.2), como código fixo: a lógica compara o
# código, e o texto da tela sai de `FIGHT_REASON_MESSAGES`, num lugar só.
FightReasonCode = Literal[
    "short", "unsupported_boss", "unsupported_difficulty", "in_progress", "upload_paused"
]
FIGHT_REASON_MESSAGES: dict[FightReasonCode, str] = {
    "short": "A luta tem menos de 60 s. Escolha uma tentativa mais longa",
    "unsupported_boss": "Chefe ainda não suportado",
    "unsupported_difficulty": "Dificuldade ainda não suportada para esse chefe",
    "in_progress": (
        "A luta ainda está subindo para o Warcraft Logs. "
        "Ela fica disponível aqui assim que terminar."
    ),
    # Luta que estava subindo, mas o log parou de receber dados (nada novo há mais de 10 min).
    "upload_paused": (
        "O envio deste log parou no Warcraft Logs (nada novo há mais de 10 min). "
        "Se o uploader voltar a enviar, clique em Atualizar lutas."
    ),
}


class FightOption(BaseModel):
    id: int
    boss: str
    difficulty: str
    kill: bool
    duration_s: float
    supported: bool
    # Motivo da luta em cinza como código fixo (item 8.2), quando supported é falso. A lógica
    # compara ele, nunca o texto.
    unsupported_code: FightReasonCode | None = None
    # Luta ainda subindo para o Warcraft Logs (log ao vivo): não suportada por enquanto, mas
    # a tela mostra diferente e atualiza a lista sozinha enquanto houver uma assim.
    in_progress: bool = False
    # Luta que estava subindo, mas o log parou de receber dados (nada novo há mais de 10 min):
    # não suportada, com o motivo dizendo para atualizar se o envio voltar.
    upload_paused: bool = False
    # Sem jogadores: os Magos Arcanos vêm por luta, em GET /reports/{code}/fights/{id}/players.

    @model_validator(mode="after")
    def _code_matches_supported(self) -> "FightOption":
        # Luta em cinza sempre tem código (a lógica decide por ele); suportada nunca tem.
        if self.supported != (self.unsupported_code is None):
            raise ValueError("supported e unsupported_code não combinam")
        return self

    @computed_field
    @property
    def unsupported_reason(self) -> str | None:
        """Texto do motivo para a tela, montado a partir de `unsupported_code`."""
        if self.unsupported_code is None:
            return None
        return FIGHT_REASON_MESSAGES[self.unsupported_code]


class ReportResolved(BaseModel):
    code: str
    title: str
    # Verdadeiro enquanto os dados vêm do arquivo de exemplo e não da API real.
    sample: bool
    # Quando a lista foi lida do Warcraft Logs (UTC); a tela mostra "lista de 21:04".
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    fights: list[FightOption]
    # Log ao vivo: o Warcraft Logs recebeu dados dele há menos de 10 min.
    live: bool = False
    # Lista guardada: a busca nova falhou (Warcraft Logs fora do ar, limite de pontos ou erro
    # nosso) e veio a última lista lida, de `fetched_at`. `stale_message` diz o porquê e
    # `stale_code` é o código do erro (`wcl_unavailable`, `unexpected_error` ou
    # `query_limit`, item 12.3).
    stale: bool = False
    stale_message: str | None = None
    stale_code: str | None = None


class FightPlayers(BaseModel):
    """Magos Arcanos de uma luta, com spec e item level dessa luta (RF04)."""

    report_code: str
    fight_id: int
    players: list[PlayerOption]


class PrefetchRequest(BaseModel):
    # Jogador já definido na tela (escolhido, único Arcano da luta ou personagem lembrado).
    actor_id: int


# started: a busca entrou na fila agora; running: já estava na fila ou baixando; ready: já
# está no cache.
PrefetchState = Literal["started", "running", "ready"]


class PrefetchStatus(BaseModel):
    """Resposta da pré-busca dos eventos da luta (202): a análise depois aproveita a busca."""

    status: PrefetchState


# --- Resultado da análise --------------------------------------------------


class FightInfo(BaseModel):
    id: int
    boss: str
    difficulty: str
    kill: bool
    duration_s: float


class PlayerInfo(BaseModel):
    name: str
    server: str | None = None
    # RF25: o jogador analisado nunca é ocultado, então é sempre igual a `name`.
    # Preenchido sozinho, inclusive em análises gravadas antes deste campo existir.
    display_name: str = ""
    spec: str
    item_level: int

    @model_validator(mode="after")
    def _display_name_is_name(self) -> "PlayerInfo":
        self.display_name = self.name
        return self


class ComparedPlayer(BaseModel):
    """Um dos tops da comparação. RF25: a tela mostra `display_name` por padrão."""

    rank: int
    display_name: str  # "top01"…, igual às fixtures (anonymize.py); a tela mostra "Top 1"
    # Nome real, só para o botão de mostrar nomes; nulo quando não há (ex.: exemplo).
    name: str | None = None
    server: str | None = None
    item_level: int | None = None
    dps: float


class Comparison(BaseModel):
    label: str  # ex.: "Top 10 do bracket 326–328"
    bracket: str
    size: int
    player_in_top: bool  # RF21
    players: list[ComparedPlayer] = []  # em ordem de rank


class Summary(BaseModel):
    dps: float
    top_avg_dps: float
    dps_gap_pct: float  # negativo quando o jogador fez menos dano que os tops
    active_time_pct: float
    top_active_time_pct: float


class Coach(BaseModel):
    # Falso quando a IA falhou: o relatório sai só com as regras (RF17).
    available: bool
    headline: str | None = None


class Number(BaseModel):
    label: str
    player: str
    top: str


class Mistake(BaseModel):
    id: str
    title: str
    # Quanto custou, em % do dano. None quando o erro é de risco (ex.: defensivo).
    impact_pct: float | None
    severity: Literal["atencao", "erro"]
    # "regra" = fato calculado pelo código; "hipotese" = o que as regras não explicam (RF23),
    # com as pistas do coach (RF24). Na hipótese, impact_pct é a diferença sem regra que a explique.
    kind: Literal["regra", "hipotese"]
    phase: str | None = None
    explanation: str
    what_to_do: str
    numbers: list[Number] = []


class RuleCheck(BaseModel):
    id: str
    name: str
    player_value: str
    top_value: str
    status: Status
    note: str | None = None


class Phase(BaseModel):
    id: int
    name: str
    start_s: float
    end_s: float
    intermission: bool = False


class TimelineTrack(BaseModel):
    """Usos de uma habilidade no tempo (RF11).

    Eixo: segundos desde o início da LUTA. O motor calcula por fase e converte
    somando `phases[].start_s`, para as telas não precisarem saber das fases.
    """

    ability_id: int
    name: str
    player_s: list[float]  # segundos desde o início da luta
    top_s: list[float]  # mesmo eixo, log de referência dos tops


class AbilityRow(BaseModel):
    name: str
    player_cpm: float | None
    top_cpm: float | None
    player_dmg_pct: float | None
    top_dmg_pct: float | None


class AbilityTable(BaseModel):
    phase: str
    rows: list[AbilityRow]


class AnalysisResult(BaseModel):
    source: Literal["exemplo", "motor"]
    report_code: str
    fight: FightInfo
    player: PlayerInfo
    comparison: Comparison
    summary: Summary
    coach: Coach
    # Regras do maior para o menor impacto (risco, sem impacto, no fim); hipóteses depois (RF10).
    mistakes: list[Mistake]
    rules: list[RuleCheck]
    phases: list[Phase]
    timeline: list[TimelineTrack]  # RF11
    abilities: list[AbilityTable]  # RF22


# --- Análises -------------------------------------------------------------


class AnalysisRequest(BaseModel):
    report_code: str = Field(min_length=1, max_length=40)
    fight_id: int
    # Jogador escolhido: o actor_id do PlayerOption (sem ambiguidade entre homônimos).
    actor_id: int


class AnalysisOut(BaseModel):
    id: str
    created_at: datetime
    saved: bool  # falso na análise sem conta: não entra em histórico nenhum
    result: AnalysisResult


class AnalysisSummary(BaseModel):
    id: str
    created_at: datetime
    report_code: str
    fight_id: int
    player_name: str
    boss: str
    difficulty: str
    dps: float
    dps_gap_pct: float
    mistakes_count: int
