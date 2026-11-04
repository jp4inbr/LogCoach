"""Nomes em português do cliente do jogo (`app/i18n/pt_br.yaml`), por ID.

O que não estiver no arquivo sai com o nome em inglês que veio do Warcraft Logs.
"""

from functools import lru_cache
from typing import Any

import yaml

from app.engine.rules import APP_DIR

PT_BR_FILE = APP_DIR / "i18n" / "pt_br.yaml"


@lru_cache
def _pt_br() -> dict[str, dict[int, str]]:
    data = yaml.safe_load(PT_BR_FILE.read_text(encoding="utf-8")) or {}
    return {
        section: {int(k): v for k, v in (data.get(section) or {}).items()}
        for section in ("spells", "npcs", "phases")
    }


def spell_names() -> dict[int, str]:
    return _pt_br()["spells"]


def npc_names() -> dict[int, str]:
    return _pt_br()["npcs"]


def spell_name(ability_id: int, fallback: str | None = None) -> str:
    return spell_names().get(ability_id) or fallback or str(ability_id)


def npc_name(game_id: int, fallback: str | None = None) -> str:
    return npc_names().get(game_id) or fallback or str(game_id)


def phase_name(phase_id: int, fallback: str | None = None) -> str:
    return _pt_br()["phases"].get(phase_id) or fallback or f"Fase {phase_id}"


def wcl_ability_names(fight: dict[str, Any]) -> dict[int, str]:
    """Nomes em inglês das habilidades usadas na luta (masterData do Warcraft Logs)."""
    return {a["gameID"]: a["name"] for a in fight.get("abilities") or []}
