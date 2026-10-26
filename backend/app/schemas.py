"""Formatos de entrada e saída da API.

`AnalysisResult` é o contrato entre o motor de análise e o frontend: o motor
(frente do Arthur) devolve um objeto nesse formato, e as telas só leem dele.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

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
    url: str


class PlayerOption(BaseModel):
    name: str
    spec: str
    item_level: int | None = None


class FightOption(BaseModel):
    id: int
    boss: str
    difficulty: str
    kill: bool
    duration_s: float
    supported: bool
    # Motivo para a luta aparecer em cinza (item 8.2), quando supported é falso.
    unsupported_reason: str | None = None
    players: list[PlayerOption] = []


class ReportResolved(BaseModel):
    code: str
    title: str
    # Verdadeiro enquanto os dados vêm do arquivo de exemplo e não da API real.
    sample: bool
    fights: list[FightOption]


# --- Resultado da análise --------------------------------------------------


class FightInfo(BaseModel):
    id: int
    boss: str
    difficulty: str
    kill: bool
    duration_s: float


class PlayerInfo(BaseModel):
    name: str
    spec: str
    item_level: int


class Comparison(BaseModel):
    label: str  # ex.: "Top 10 do bracket 326–328"
    bracket: str
    size: int
    player_in_top: bool  # RF21


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
    # "regra" = fato calculado pelo código; "hipotese" = apontado pela IA (RF24).
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
    mistakes: list[Mistake]  # ordenados do maior para o menor impacto (RF10)
    rules: list[RuleCheck]
    phases: list[Phase]
    timeline: list[TimelineTrack]  # RF11
    abilities: list[AbilityTable]  # RF22


# --- Análises -------------------------------------------------------------


class AnalysisRequest(BaseModel):
    report_code: str = Field(min_length=1, max_length=40)
    fight_id: int
    player_name: str = Field(min_length=1, max_length=40)


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
