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


def ranking_id(rank: int, ranking: dict[str, Any]) -> dict[str, Any]:
    """Quem é cada posição do ranking: o log exato (report, luta) e o personagem. Dois Magos
    da mesma raide têm o mesmo report e a mesma luta; o nome separa os dois."""
    code, fight_id = ranking_log(ranking)
    return {
        "rank": rank,
        "report": code,
        "fight_id": fight_id,
        "name": ranking["name"],
        "server": (ranking.get("server") or {}).get("name"),
    }


def fetch_tops(
    client: WclClient,
    encounter_id: int,
    class_name: str,
    spec_name: str,
    difficulty: int,
    bracket: int,
    n: int = 10,
    spare: int = SPARE,
) -> dict[str, Any]:
    """Os n primeiros do ranking do bracket com a luta de cada um.

    Devolve `rankings` (quem é cada posição, de todas as entradas lidas, mesmo as que não
    abriram: é por elas que se sabe se o log analisado está no top 10, RF21) e `tops`, em
    ordem, cada um com a posição real no ranking (`rank`), a entrada do ranking (`ranking`)
    e a luta no formato de `fetch_fight` (`fight`). Luta que não abre (jogador não achado,
    luta ou report indisponível) é pulada e o próximo do ranking entra; o WCL fora do ar
    (`WclUnavailableError`, erro de rede) interrompe tudo.
    """
    rankings = fetch_rankings(
        client, encounter_id, class_name, spec_name, difficulty, bracket=bracket, n=n + spare
    )
    tops: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for rank, ranking in enumerate(rankings, start=1):
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
            skipped.append({"rank": rank, "report": code, "fight_id": fight_id, "reason": str(exc)})
            continue
        tops.append({"rank": rank, "ranking": ranking, "fight": fight})
    return {
        "rankings": [ranking_id(rank, r) for rank, r in enumerate(rankings, start=1)],
        "tops": tops,
        "skipped": skipped,
    }
