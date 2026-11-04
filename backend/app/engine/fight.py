"""Leitura básica de uma luta no formato de `wcl.fetch.fetch_fight` (tempos em ms do report).

Fases: o Warcraft Logs manda as transições (`meta.fight.phaseTransitions`, id e início) e,
à parte, os nomes de cada id (`phases`). Uma fase pode se repetir na luta (ex.: volta para
a Fase 1); cada trecho vira um `PhaseSpan`, e as tabelas somam os trechos do mesmo id.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.engine.names import phase_name
from app.engine.rules import load_spec_rules


@dataclass(frozen=True)
class PhaseSpan:
    id: int
    name: str  # em português (pt_br.yaml), ou o nome do Warcraft Logs
    start_ms: float  # ms do report
    end_ms: float
    intermission: bool

    @property
    def duration_s(self) -> float:
        return (self.end_ms - self.start_ms) / 1000


def start_ms(fight: dict[str, Any]) -> float:
    return fight["meta"]["fight"]["startTime"]


def end_ms(fight: dict[str, Any]) -> float:
    return fight["meta"]["fight"]["endTime"]


def duration_s(fight: dict[str, Any]) -> float:
    return (end_ms(fight) - start_ms(fight)) / 1000


def fight_s(fight: dict[str, Any], timestamp: float) -> float:
    """Segundos desde o início da luta (o eixo do `AnalysisResult`)."""
    return (timestamp - start_ms(fight)) / 1000


def phase_spans(fight: dict[str, Any]) -> list[PhaseSpan]:
    """Trechos de fase em ordem. Luta sem transições = uma fase só (id 1), a luta inteira."""
    names = {p["id"]: p for p in fight.get("phases") or []}
    transitions = sorted(
        fight["meta"]["fight"].get("phaseTransitions") or [{"id": 1, "startTime": start_ms(fight)}],
        key=lambda t: t["startTime"],
    )
    spans = []
    for i, transition in enumerate(transitions):
        end = transitions[i + 1]["startTime"] if i + 1 < len(transitions) else end_ms(fight)
        info = names.get(transition["id"], {})
        spans.append(
            PhaseSpan(
                id=transition["id"],
                name=phase_name(transition["id"], info.get("name")),
                start_ms=transition["startTime"],
                end_ms=end,
                intermission=bool(info.get("isIntermission")),
            )
        )
    return spans


def phase_at(spans: list[PhaseSpan], timestamp: float) -> PhaseSpan | None:
    for span in spans:
        if span.start_ms <= timestamp < span.end_ms:
            return span
    # O último evento pode cair exatamente no fim da luta.
    return spans[-1] if spans and timestamp == spans[-1].end_ms else None


def amount(event: dict[str, Any]) -> float:
    """Dano de um golpe, contando o que foi absorvido (escudos também são dano feito)."""
    return event.get("amount", 0) + event.get("absorbed", 0)


def damage_done(fight: dict[str, Any], rules: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Dano do jogador sem o que o Warcraft Logs credita a quem o apoiou (Evocador
    Aumentação): sem as habilidades do Evocador que aparecem nos eventos do Mago
    (`damage_credited_to_others`) e com o crédito do Ebon Might/Prescience/Shifting Sands
    descontado de cada golpe pelos buffs ativos nele (`engine/support.py`). Sem `rules`, as
    do Arcano.

    Com os números do WCL, a soma bate com o dano oficial; sem eles (luta antiga), só as
    habilidades do Evocador saem."""
    from app.engine.support import without_support  # support.py usa este módulo

    rules = rules or load_spec_rules()
    credited = frozenset(rules.get("damage_credited_to_others") or ())
    events = [e for e in fight["events"]["damage_done"] if e["abilityGameID"] not in credited]
    return without_support(
        fight,
        events,
        frozenset(rules.get("support_buffs") or ()),
        frozenset(rules.get("support_uniform_abilities") or ()),
    )


def total_damage(fight: dict[str, Any], rules: dict[str, Any] | None = None) -> float:
    """Dano do jogador pelos eventos, sem o creditado a quem o apoiou (`damage_done`): base
    das proporções (% por habilidade, alvo, impacto). Com os números do WCL, igual ao total
    oficial; o DPS em si vem do WCL (`official_dps`)."""
    return sum(amount(e) for e in damage_done(fight, rules))


def official_dps(fight: dict[str, Any]) -> float | None:
    """DPS do Warcraft Logs (tabela DamageDone, o mesmo do ranking); None em luta sem ele
    (fixtures e cópias antigas)."""
    damage = (fight.get("player") or {}).get("damage")
    return damage["dps"] if damage else None


def casts(fight: dict[str, Any], ability_ids: int | Iterable[int] | None = None) -> list[dict]:
    """Casts concluídos (sem os `begincast`), em ordem, de uma ou mais habilidades."""
    if isinstance(ability_ids, int):
        ability_ids = {ability_ids}
    wanted = None if ability_ids is None else set(ability_ids)
    return sorted(
        (
            e
            for e in fight["events"]["casts"]
            if e["type"] == "cast" and (wanted is None or e["abilityGameID"] in wanted)
        ),
        key=lambda e: e["timestamp"],
    )
