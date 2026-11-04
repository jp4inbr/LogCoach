"""O analisador do motor (passo 4.3): junta a luta do jogador, os tops e as regras do chefe e
entrega ao `engine.report.build_analysis`.

Não conhece rotas nem HTTP: os erros saem como exceções das fontes (`SourceUnavailableError`,
`QueryLimitError`, `ReportNotAvailableError`) ou `AnalysisNotAvailableError` (luta que o motor
não sabe analisar), e a rota traduz (`api/analyses.py`).
"""

from typing import Annotated

from fastapi import Depends

from app.config import get_settings
from app.engine.report import build_analysis
from app.engine.rules import load_encounter_rules
from app.schemas import (
    AnalysisResult,
    Comparison,
    FightInfo,
    FightOption,
    PlayerInfo,
    PlayerOption,
    ReportResolved,
)
from app.services.sources import (
    AnalysisNotAvailableError,
    Analyzer,
    ReportSource,
    fill_real_names,
    get_report_source,
)
from app.services.tops import (
    OwnLog,
    TopsComparison,
    TopsNotAvailableError,
    TopsSource,
    get_tops_source,
)


class EngineAnalyzer:
    """`source` dá os eventos do jogador (a pré-busca já deixou no cache, em geral) e `tops`
    os tops do bracket (cache de 24 h). No modo exemplo, as duas são as de `app/samples/`."""

    def __init__(self, source: ReportSource, tops: TopsSource) -> None:
        self._source = source
        self._tops = tops

    def analyze(
        self, report: ReportResolved, fight: FightOption, player: PlayerOption
    ) -> AnalysisResult:
        where = f"{report.code}/{fight.id}/{player.actor_id}"
        # Lista guardada antes dos ids existirem: sem eles não há regras nem tops.
        if fight.encounter_id is None or fight.difficulty_id is None:
            raise AnalysisNotAvailableError(f"{where}: luta sem encounter_id/difficulty_id")
        encounter = load_encounter_rules(fight.encounter_id)
        if encounter is None:
            raise AnalysisNotAvailableError(f"{where}: encontro {fight.encounter_id} sem YAML")
        # O bracket dos tops sai do item level: sem ele não há com quem comparar.
        if player.item_level is None:
            raise AnalysisNotAvailableError(f"{where}: jogador sem item level")

        # Primeiro os tops: no WCL podem demorar, mas falham antes de baixar a luta inteira.
        own = OwnLog(report.code, fight.id, player.name)
        tops = self._tops.get_tops(fight.encounter_id, fight.difficulty_id, player.item_level, own)
        if not tops.entries:
            # Só acontece se o RF21 tirar o único top que abriu: sem tops, a média seria o
            # próprio jogador e a diferença sairia 0%.
            raise TopsNotAvailableError(f"{where}: nenhum top além do próprio log")
        player_fight = self._source.get_fight_data(report.code, fight.id, player.actor_id)

        result = build_analysis(
            report_code=report.code,
            fight_info=FightInfo(
                id=fight.id,
                boss=fight.boss,
                difficulty=fight.difficulty,
                kill=fight.kill,
                duration_s=fight.duration_s,
            ),
            player_info=PlayerInfo(
                name=player.name,
                server=player.server,
                spec=player.spec,
                item_level=player.item_level,
            ),
            comparison=comparison_of(tops),
            player_fight=player_fight,
            # Gerador: cada luta de top (~4,5 MB) é descomprimida, medida e largada.
            top_fights=((entry.fight(), entry.dps) for entry in tops.entries),
            encounter=encounter,
        )
        if result.comparison.sample:
            # Cópias anonimizadas do exemplo: o nome real só vem do names.local.json local.
            fill_real_names(result, get_settings().names_file)
        return result


def comparison_of(tops: TopsComparison) -> Comparison:
    return Comparison(
        label=tops.label,
        bracket=tops.bracket,
        size=len(tops.entries),
        player_in_top=tops.player_in_top,
        players=[entry.compared() for entry in tops.entries],
        stale=tops.stale,
        sample=tops.sample,
    )


def get_analyzer(
    source: Annotated[ReportSource, Depends(get_report_source)],
    tops: Annotated[TopsSource, Depends(get_tops_source)],
) -> Analyzer:
    """Dependência da rota: a mesma fonte do pedido (FastAPI guarda por pedido), então um
    `dependency_overrides[get_report_source]` vale para a rota e para o motor."""
    return EngineAnalyzer(source, tops)
