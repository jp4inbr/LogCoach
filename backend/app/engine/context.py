"""Contexto da luta que não é erro do Mago: buffs de outros jogadores e mortes.

- Power Infusion (e outros externos do YAML): quantos o jogador recebeu e quantos caíram no
  Surge. Entra como contexto na comparação (o top que recebe PI em todo Surge tem vantagem).
- Mortes: o Warcraft Logs devolve as mortes da raide inteira; ficam só as do jogador. O tempo
  morto vai até o próximo cast dele (reviveu) ou o fim da luta.
"""

from dataclasses import dataclass
from typing import Any

from app.engine.fight import casts, end_ms, fight_s
from app.engine.timeline import buff_windows, inside


@dataclass(frozen=True)
class ExternalBuff:
    name: str  # chave do YAML (ex.: power_infusion)
    time_s: float
    with_surge: bool


@dataclass(frozen=True)
class Death:
    time_s: float
    dead_s: float


def player_id(fight: dict[str, Any]) -> int:
    return fight["player"]["actor"]["id"]


def external_buffs(fight: dict[str, Any], rules: dict[str, Any]) -> list[ExternalBuff]:
    """Buffs de outros jogadores no jogador. "Com o Surge" = começou dentro da janela do Surge
    ou até `surge_hold.coincide_s` antes dela (o PI costuma vir logo antes do Surge)."""
    early = rules["surge_hold"]["coincide_s"] * 1000
    surge = [(a - early, b) for a, b in buff_windows(fight, rules["surge_window"]["buff_id"])]
    result = []
    for name, buff_id in (rules.get("external_buffs") or {}).items():
        for start, _ in buff_windows(fight, buff_id):
            result.append(ExternalBuff(name, fight_s(fight, start), inside(start, surge)))
    return sorted(result, key=lambda b: b.time_s)


def deaths(fight: dict[str, Any]) -> list[Death]:
    pid = player_id(fight)
    own_casts = [e["timestamp"] for e in casts(fight)]
    result = []
    for event in sorted(fight["events"].get("deaths") or [], key=lambda e: e["timestamp"]):
        if event.get("targetID") != pid:
            continue
        t = event["timestamp"]
        back = next((c for c in own_casts if c > t), end_ms(fight))
        result.append(Death(fight_s(fight, t), (back - t) / 1000))
    return result
