"""Arcane Soul e janela do Arcane Surge (regras do Arthur, Sunfury).

- Entrada no Arcane Soul: entrar com 25 de Salvo. Os 2 últimos GCDs antes do Soul não podem
  ser Barrage, salvo se vier Overpowered Missiles, que sobe o Salvo para 25 na hora.
- Janela do Surge: chegar com Clearcasting para não encher o burst de Arcane Blast. Nos
  melhores logs, Blast dentro do Surge só aparece no de abertura.
Lê uma luta no formato de `wcl.fetch.fetch_fight` (tempos em ms do report).
"""

from dataclasses import dataclass
from typing import Any

from app.engine.rules import load_spec_rules
from app.engine.timeline import buff_windows, stacks_before

# Proc de Overpowered Missiles que vale para a entrada: até 3 s antes do Soul.
OVERPOWERED_LOOKBACK_MS = 3000


@dataclass(frozen=True)
class SoulEntry:
    start_s: float  # segundos desde o início da luta
    salvo: int
    barrage_in_last_gcds: bool
    overpowered: bool

    @property
    def mistake(self) -> bool:
        """Barrage nos últimos GCDs sem a exceção do Overpowered Missiles."""
        return self.barrage_in_last_gcds and not self.overpowered


@dataclass(frozen=True)
class SurgeWindow:
    start_s: float
    clearcasting: int  # cargas de Clearcasting no começo da janela
    arcane_blasts: int
    opener: bool


def soul_entries(fight: dict[str, Any], rules: dict[str, Any] | None = None) -> list[SoulEntry]:
    rules = rules or load_spec_rules()
    soul = rules["arcane_soul"]
    start = fight["meta"]["fight"]["startTime"]
    surge_cast = rules["abilities"]["arcane_surge"]
    # O cast do Surge não ocupa GCD de rotação; o resto conta como os "últimos GCDs".
    casts = sorted(
        (
            e
            for e in fight["events"]["casts"]
            if e["type"] == "cast" and e["abilityGameID"] != surge_cast
        ),
        key=lambda e: e["timestamp"],
    )
    overpowered = [
        e["timestamp"]
        for e in fight["events"]["buffs"]
        if e["abilityGameID"] == soul["exception_buff_id"] and e["type"] == "applybuff"
    ]
    windows = buff_windows(fight, soul["buff_id"])
    # +1 ms: o Salvo com que se entra no Soul, já contando o Overpowered do mesmo instante.
    salvos = stacks_before(fight, rules["buffs"]["arcane_salvo"], [s + 1 for s, _ in windows])

    entries = []
    for (begin, _), salvo in zip(windows, salvos, strict=True):
        last = [c for c in casts if c["timestamp"] < begin][-soul["no_barrage_last_gcds"] :]
        entries.append(
            SoulEntry(
                start_s=(begin - start) / 1000,
                salvo=salvo,
                barrage_in_last_gcds=any(
                    c["abilityGameID"] == rules["abilities"]["arcane_barrage"] for c in last
                ),
                overpowered=any(begin - OVERPOWERED_LOOKBACK_MS <= t <= begin for t in overpowered),
            )
        )
    return entries


def surge_windows(fight: dict[str, Any], rules: dict[str, Any] | None = None) -> list[SurgeWindow]:
    rules = rules or load_spec_rules()
    start = fight["meta"]["fight"]["startTime"]
    blast = rules["abilities"]["arcane_blast"]
    blasts = [
        e["timestamp"]
        for e in fight["events"]["casts"]
        if e["type"] == "cast" and e["abilityGameID"] == blast
    ]
    windows = buff_windows(fight, rules["surge_window"]["buff_id"])
    charges = stacks_before(fight, rules["buffs"]["clearcasting"], [s + 1 for s, _ in windows])
    return [
        SurgeWindow(
            start_s=(begin - start) / 1000,
            clearcasting=cc,
            arcane_blasts=sum(begin <= t <= end for t in blasts),
            opener=index == 0,
        )
        for index, ((begin, end), cc) in enumerate(zip(windows, charges, strict=True))
    ]
