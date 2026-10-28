"""Prismatic Bolt: quanto veio da decisão (Salvo no Barrage) e quanto foi sorte (RNG).

Cada Salvo no Barrage dá uma chance fixa de proc (2% no YAML). Com os acúmulos de cada
Barrage dá para saber quantos procs o jogador deveria esperar; a diferença para os que
ele recebeu, medida em desvios (z), é sorte. Assim o relatório não cobra azar como erro.
Lê uma luta no formato de `wcl.fetch.fetch_fight` (tempos em ms do report).
"""

import math
from dataclasses import dataclass
from typing import Any

from app.engine.rules import load_spec_rules


@dataclass(frozen=True)
class BoltProcs:
    barrages: int
    mean_salvo: float
    below_min_pct: float  # % de Barrages abaixo do mínimo de Salvo (12)
    expected: float  # procs esperados pelos acúmulos: mede a decisão
    received: int  # procs que vieram logo após um Barrage
    luck_z: float  # (recebidos − esperado) ÷ desvio: mede o RNG
    expected_per_min: float
    received_per_min: float

    @property
    def luck(self) -> str:
        """Devolve "azar", "normal" ou "sorte", pelos limites de luck_z do YAML."""
        limits = load_spec_rules()["prismatic_bolt_rng"]["luck_z"]
        if self.luck_z <= limits["unlucky"]:
            return "azar"
        if self.luck_z >= limits["lucky"]:
            return "sorte"
        return "normal"


def salvo_at_barrages(fight: dict[str, Any], rules: dict[str, Any] | None = None) -> list[int]:
    """Acúmulos de Salvo no instante de cada Barrage, na ordem dos casts."""
    rules = rules or load_spec_rules()
    barrage, salvo = rules["abilities"]["arcane_barrage"], rules["buffs"]["arcane_salvo"]
    casts = sorted(
        e["timestamp"]
        for e in fight["events"]["casts"]
        if e["type"] == "cast" and e["abilityGameID"] == barrage
    )
    changes = sorted(
        (e for e in fight["events"]["buffs"] if e["abilityGameID"] == salvo),
        key=lambda e: e["timestamp"],
    )

    stacks, current, i = [], 0, 0
    for cast in casts:
        # Só o que aconteceu antes do cast: o próprio Barrage consome os acúmulos.
        while i < len(changes) and changes[i]["timestamp"] < cast:
            event = changes[i]
            if event["type"] == "applybuff":
                current = event.get("stack", 1)
            elif event["type"] in ("applybuffstack", "removebuffstack"):
                current = event["stack"]
            elif event["type"] == "removebuff":
                current = 0
            i += 1
        stacks.append(current)
    return stacks


def bolt_procs(fight: dict[str, Any], rules: dict[str, Any] | None = None) -> BoltProcs:
    rules = rules or load_spec_rules()
    rng = rules["prismatic_bolt_rng"]
    chance, window_ms = rng["proc_per_salvo"], rng["proc_window_s"] * 1000
    proc_buff, barrage = rules["buffs"]["prismatic_bolt_proc"], rules["abilities"]["arcane_barrage"]

    stacks = salvo_at_barrages(fight, rules)
    casts = sorted(
        e["timestamp"]
        for e in fight["events"]["casts"]
        if e["type"] == "cast" and e["abilityGameID"] == barrage
    )
    procs = [
        e["timestamp"]
        for e in fight["events"]["buffs"]
        if e["abilityGameID"] == proc_buff
        and e["type"] in ("applybuff", "applybuffstack", "refreshbuff")
    ]
    received = sum(1 for cast in casts if any(0 <= p - cast <= window_ms for p in procs))

    chances = [min(1.0, chance * s) for s in stacks]
    expected = sum(chances)
    spread = math.sqrt(sum(p * (1 - p) for p in chances)) or 1.0
    minutes = (fight["meta"]["fight"]["endTime"] - fight["meta"]["fight"]["startTime"]) / 60_000
    minimum = rules["barrage"]["min_salvo"]
    return BoltProcs(
        barrages=len(stacks),
        mean_salvo=sum(stacks) / len(stacks) if stacks else 0.0,
        below_min_pct=100 * sum(s < minimum for s in stacks) / len(stacks) if stacks else 0.0,
        expected=expected,
        received=received,
        luck_z=(received - expected) / spread,
        expected_per_min=expected / minutes,
        received_per_min=received / minutes,
    )
