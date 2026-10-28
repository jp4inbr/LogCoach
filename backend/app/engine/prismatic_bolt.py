"""Prismatic Bolt: quanto veio da decisão (Salvo no Barrage) e quanto foi sorte (RNG).

Cada Salvo no Barrage dá uma chance fixa de proc (2% no YAML). Com os acúmulos de cada
Barrage dá para saber quantos procs o jogador deveria esperar; a diferença para os que
ele recebeu, medida em desvios (z), é sorte. Assim o relatório não cobra azar como erro.
Dentro do Arcane Soul o Barrage não gasta Salvo, então é ali que a decisão mais pesa: o
cálculo sai para a luta inteira, só dentro do Soul e só fora.
Lê uma luta no formato de `wcl.fetch.fetch_fight` (tempos em ms do report).
"""

import math
from dataclasses import dataclass
from typing import Any

from app.engine.rules import load_spec_rules
from app.engine.timeline import buff_windows, inside, stacks_before


@dataclass(frozen=True)
class BoltProcs:
    barrages: int
    mean_salvo: float
    below_min_pct: float  # % de Barrages abaixo do mínimo de Salvo (12)
    expected: float  # procs esperados pelos acúmulos: mede a decisão
    received: int  # Barrages seguidos de proc
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


def barrage_casts(fight: dict[str, Any], rules: dict[str, Any]) -> list[float]:
    barrage = rules["abilities"]["arcane_barrage"]
    return sorted(
        e["timestamp"]
        for e in fight["events"]["casts"]
        if e["type"] == "cast" and e["abilityGameID"] == barrage
    )


def salvo_at_barrages(fight: dict[str, Any], rules: dict[str, Any] | None = None) -> list[int]:
    """Acúmulos de Salvo no instante de cada Barrage, na ordem dos casts."""
    rules = rules or load_spec_rules()
    # Só o que aconteceu antes do cast: o próprio Barrage consome os acúmulos.
    return stacks_before(fight, rules["buffs"]["arcane_salvo"], barrage_casts(fight, rules))


def bolt_procs(
    fight: dict[str, Any], rules: dict[str, Any] | None = None, soul: bool | None = None
) -> BoltProcs:
    """Procs da luta inteira (soul=None), só dentro do Arcane Soul (True) ou só fora (False)."""
    rules = rules or load_spec_rules()
    rng = rules["prismatic_bolt_rng"]
    chance, window_ms = rng["proc_per_salvo"], rng["proc_window_s"] * 1000

    casts = barrage_casts(fight, rules)
    stacks = salvo_at_barrages(fight, rules)
    if soul is not None:
        windows = buff_windows(fight, rules["arcane_soul"]["buff_id"])
        kept = [(c, s) for c, s in zip(casts, stacks, strict=True) if inside(c, windows) == soul]
        casts, stacks = [c for c, _ in kept], [s for _, s in kept]

    proc_buff = rules["buffs"]["prismatic_bolt_proc"]
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
