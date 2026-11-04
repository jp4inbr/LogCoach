"""Leitura dos YAML de regras (app/rules/ e app/encounters/)."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

APP_DIR = Path(__file__).resolve().parent.parent


@lru_cache
def load_spec_rules(name: str = "arcane_mage") -> dict[str, Any]:
    return yaml.safe_load((APP_DIR / "rules" / f"{name}.yaml").read_text(encoding="utf-8"))


@lru_cache
def load_encounter_rules(encounter_id: int) -> dict[str, Any] | None:
    """Regras do encontro pelo ID do Warcraft Logs; None se o chefe não tem arquivo."""
    for path in sorted((APP_DIR / "encounters").glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data.get("encounter_id") == encounter_id:
            return data
    return None
