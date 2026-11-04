"""Busca dos top N de um ranking do Warcraft Logs, com a luta completa de cada um.

Busca pura (sem cache, sem pausa, sem plano B): quem decide isso é `services/tops.py`. O
script `save_fixtures.py` usa a mesma função para gravar as fixtures.
"""

from typing import Any

import httpx

from app.wcl.client import WclClient, WclError, WclUnavailableError
from app.wcl.fetch import fetch_fight, fetch_rankings

# Rankings a mais, para cobrir os tops cuja luta não abre (personagem renomeado, report
# privado ou apagado depois de entrar no ranking).
SPARE = 3


def ranking_log(ranking: dict[str, Any]) -> tuple[str, int]:
    """(código do report, id da luta) de uma entrada do ranking."""
    return ranking["report"]["code"], ranking["report"]["fightID"]


def fetch_tops(
    client: WclClient,
    encounter_id: int,
    class_name: str,
    spec_name: str,
    difficulty: int,
    bracket: int | None,
    n: int = 10,
    spare: int = SPARE,
) -> dict[str, Any]:
    """Os n primeiros do ranking (bracket `None` = ranking geral, RF21) com a luta de cada um.

    Devolve `ranking_logs` (as lutas dos n primeiros do ranking, mesmo as que não abriram:
    é por elas que se sabe se o jogador está no top 10) e `tops`, em ordem, cada um com a
    entrada do ranking (`ranking`) e a luta no formato de `fetch_fight` (`fight`). Luta que
    não abre (jogador não achado, luta ou report indisponível) é pulada e o próximo do
    ranking entra; o WCL fora do ar (`WclUnavailableError`, erro de rede) interrompe tudo.
    """
    rankings = fetch_rankings(
        client, encounter_id, class_name, spec_name, difficulty, bracket=bracket, n=n + spare
    )
    tops: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for ranking in rankings:
        if len(tops) == n:
            break
        code, fight_id = ranking_log(ranking)
        try:
            fight = fetch_fight(
                client,
                code,
                fight_id,
                name=ranking["name"],
                server=(ranking.get("server") or {}).get("name"),
            )
        except (WclUnavailableError, httpx.HTTPError):
            raise
        except WclError as exc:
            # Inclui PlayerNotFoundError e FightNotFoundError (são WclError).
            skipped.append({"report": code, "fight_id": fight_id, "reason": str(exc)})
            continue
        tops.append({"ranking": ranking, "fight": fight})
    return {
        "ranking_logs": [ranking_log(r) for r in rankings[:n]],
        "tops": tops,
        "skipped": skipped,
    }
