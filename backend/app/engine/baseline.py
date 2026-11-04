"""Referência dos tops para cada métrica: os limites saem dos logs puxados, não de número fixo.

Decisão de 03/11 (CLAUDE.md): para cada métrica de desempenho, o jogador é comparado com os
mesmos números dos top 10 da comparação.
- **atenção**: pior que 3 de cada 4 tops (pior que o quartil do lado ruim);
- **erro**: pior que o pior dos tops.
Com poucos tops (menos de `MIN_TOPS`), valem os valores reserva do YAML (`warn` e `error`).
O relatório mostra a referência usada ("mediana dos 10 tops: 6%").
"""

import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from app.schemas import Status

# Menos tops que isso e a régua dos tops não é confiável: usa a reserva do YAML.
MIN_TOPS = 5

Better = Literal["higher", "lower"]


@dataclass(frozen=True)
class Reference:
    values: tuple[float, ...]  # a métrica em cada top
    better: Better  # "lower": menos é melhor (ex.: % de Barrage abaixo de 12)
    warn: float  # a partir daqui (exclusivo) é atenção
    error: float  # a partir daqui (exclusivo) é erro
    from_tops: bool  # falso quando usou a reserva do YAML

    @property
    def median(self) -> float | None:
        return statistics.median(self.values) if self.values else None

    @property
    def mean(self) -> float | None:
        return statistics.fmean(self.values) if self.values else None

    def status(self, player: float) -> Status:
        if self._worse(player, self.error):
            return "erro"
        if self._worse(player, self.warn):
            return "atencao"
        return "ok"

    def text(self, fmt: Callable[[float], str]) -> str:
        """De onde saiu o limite, para o usuário: "mediana dos 10 tops: 6%"."""
        if not self.from_tops:
            return f"limite de referência (poucos tops): atenção além de {fmt(self.warn)}"
        return f"mediana dos {len(self.values)} tops: {fmt(self.median)}"

    def _worse(self, player: float, limit: float) -> bool:
        return player > limit if self.better == "lower" else player < limit


def reference(
    values: Sequence[float],
    better: Better,
    reserve: dict[str, float] | None = None,
) -> Reference:
    """Monta a régua de uma métrica a partir dos valores dos tops (ou da reserva do YAML)."""
    tops = tuple(float(v) for v in values)
    if len(tops) < MIN_TOPS:
        if reserve is None:
            raise ValueError("Poucos tops e nenhum valor reserva para a métrica.")
        return Reference(tops, better, reserve["warn"], reserve["error"], from_tops=False)
    # Quartis no método inclusivo: com 10 tops, o do lado ruim fica entre o 7º e o 8º valor.
    low_quartile, _, high_quartile = statistics.quantiles(tops, n=4, method="inclusive")
    if better == "lower":
        return Reference(tops, better, high_quartile, max(tops), from_tops=True)
    return Reference(tops, better, low_quartile, min(tops), from_tops=True)
