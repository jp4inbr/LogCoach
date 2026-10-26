"""Troca nomes de jogadores por pseudônimos antes de salvar no repositório (que é público).

Por padrão os nomes ficam ocultos. O mapa pseudônimo → nome real volta separado,
para ser guardado fora do git e permitir "mostrar nomes" na demo.
"""

import copy
from typing import Any

# Campos que identificam o personagem (nome, reino e GUID do jogo).
IDENTIFYING_FIELDS = ("name", "server", "region", "gameID", "guid")


def _strip(entry: dict[str, Any], display_name: str) -> dict[str, Any]:
    real = {k: entry[k] for k in IDENTIFYING_FIELDS if k in entry}
    for key in IDENTIFYING_FIELDS:
        entry.pop(key, None)
    entry["display_name"] = display_name
    return real


def anonymize_fight(
    fight: dict[str, Any],
    player_label: str,
    keep: frozenset[str] = frozenset(),
    hide_report: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Devolve (luta anonimizada, mapa pseudônimo → dados reais).

    O jogador analisado vira `player_label` (ex.: "top01"); os demais da raide viram
    "raid_01", "raid_02"… em ordem de ID. Nomes em `keep` não são trocados.
    Com hide_report, o código do report (que leva aos nomes) também sai do arquivo.
    """
    anon = copy.deepcopy(fight)
    mapping: dict[str, Any] = {}
    player_id = anon["player"]["actor"]["id"]

    labels: dict[int, str] = {}
    raid_n = 0
    for actor in sorted(anon["actors"], key=lambda a: a["id"]):
        if actor["type"] == "Player":
            if actor["name"] in keep:
                label = actor["name"]
            elif actor["id"] == player_id:
                label = player_label
            else:
                raid_n += 1
                label = f"raid_{raid_n:02d}"
        elif actor["type"] == "Pet":
            # Pets de caçador e bruxo podem ter nome escolhido pelo jogador.
            label = f"pet_{actor['id']}"
        else:
            continue
        labels[actor["id"]] = label
        real = _strip(actor, label)
        if label not in keep:
            mapping[label] = real
        else:
            actor["name"] = label

    player = anon["player"]
    player["actor"] = next(a for a in anon["actors"] if a["id"] == player_id)
    if player.get("details"):
        _strip(player["details"], labels[player_id])
        if labels[player_id] in keep:
            player["details"]["name"] = labels[player_id]

    if hide_report and labels[player_id] not in keep:
        mapping[labels[player_id]]["report"] = anon["meta"]["report"]
        anon["meta"]["report"] = None
        anon["meta"]["report_start_time"] = None

    return anon, mapping


def anonymize_ranking(ranking: dict[str, Any], label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Mantém só o que serve para a comparação (DPS, duração, ilvl do bracket)."""
    public = {
        "display_name": label,
        "amount": ranking["amount"],
        "duration_ms": ranking["duration"],
        "bracket_item_level": ranking.get("bracketData"),
    }
    real = {
        "name": ranking["name"],
        "server": ranking.get("server"),
        "guild": ranking.get("guild"),
        "report": ranking["report"],
    }
    return public, real
