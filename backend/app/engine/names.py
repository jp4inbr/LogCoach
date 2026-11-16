"""Nomes em português do cliente do jogo (`app/i18n/pt_br.yaml`), por ID.

O que não estiver no arquivo sai com o nome em inglês que veio do Warcraft Logs.
"""

import re
from functools import lru_cache
from typing import Any

import yaml

from app.engine.rules import APP_DIR

PT_BR_FILE = APP_DIR / "i18n" / "pt_br.yaml"


@lru_cache
def _pt_br() -> dict[str, Any]:
    """O `pt_br.yaml` lido uma vez: nomes por seção e `mage_spells` (na ordem do arquivo)."""
    data = yaml.safe_load(PT_BR_FILE.read_text(encoding="utf-8")) or {}
    out: dict[str, Any] = {
        section: {int(k): v for k, v in (data.get(section) or {}).items()}
        for section in ("spells", "npcs", "phases")
    }
    out["mage_spells"] = tuple(int(i) for i in data.get("mage_spells") or [])
    return out


def mage_spell_ids() -> frozenset[int]:
    """IDs do Mago Arcano que têm ícone na tela (`mage_spells` do `pt_br.yaml`)."""
    return frozenset(_pt_br()["mage_spells"])


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


# Marcação de magia do Mago nos textos ao jogador (item 12.9): `{{spell:365350|Surto}}`. O
# frontend troca por ícone + texto. O texto exibido não tem `|`, `{` nem `}`.
SPELL_REF_RE = re.compile(r"\{\{spell:(\d+)\|([^|{}]+)\}\}")


def spell_ref(ability_id: int, text: str | None = None) -> str:
    """Marca uma menção a magia ou talento do Mago. Texto padrão: o nome em pt-BR do ID."""
    shown = text if text is not None else spell_name(ability_id)
    if not shown or any(ch in shown for ch in "|{}"):
        raise ValueError(f"Texto inválido para a marcação de magia: {shown!r}")
    return f"{{{{spell:{ability_id}|{shown}}}}}"


def strip_spell_refs(text: str) -> str:
    """O texto como o jogador lê: cada marcação vira só o texto exibido."""
    return SPELL_REF_RE.sub(lambda m: m.group(2), text)


# Formas escritas de cada magia do Mago nos textos do motor → ID principal. As formas base saem
# dos nomes de `mage_spells` no `pt_br.yaml` (o ID que vem primeiro na lista é o principal; o "!"
# do proc da Seta Prismática fica de fora). Aqui só o que o nome não dá: plurais e formas curtas.
# Só o que é marcado por `mark_spells`; poção, lust (Distorção Temporal inclusive), Infusão de
# Poder e mecânicas do chefe ficam de fora.
EXTRA_SPELL_FORMS: dict[int, tuple[str, ...]] = {
    365350: ("Surtos Arcanos", "Surtos", "Surto"),
    321507: ("Toques dos Magos", "Toques", "Toque"),
    5143: ("Mísseis",),
    44425: ("Salvas Arcanas", "Salvas", "Salva"),
    30451: ("Impactos Arcanos", "Impactos", "Impacto"),
    153626: ("Orbes Arcanos", "Orbes", "Orbe"),
    1295924: ("Setas Prismáticas", "Setas", "Seta"),
    1242974: ("Saraivada",),
    263725: ("Abstrações",),
    449569: ("Meteoritos", "meteoritos", "meteorito"),
}


@lru_cache
def _forms_regex() -> tuple[re.Pattern[str], dict[str, int]]:
    by_form: dict[str, int] = {}
    for spell_id in _pt_br()["mage_spells"]:
        by_form.setdefault(spell_name(spell_id).rstrip("!"), spell_id)
    for spell_id, forms in EXTRA_SPELL_FORMS.items():
        by_form.update({form: spell_id for form in forms})
    alternatives = sorted(by_form, key=len, reverse=True)  # a mais longa casa primeiro
    pattern = (
        r"\{\{spell:\d+\|[^|{}]+\}\}"  # marcação que já existe: fica como está
        r"|(?<!\w)(" + "|".join(re.escape(f) for f in alternatives) + r")(?!\w)"
    )
    return re.compile(pattern), by_form


def mark_spells(text: str) -> str:
    """Marca toda menção a magia do Mago no texto (`spell_ref`), inclusive as formas curtas
    ("o Surto", "meteoritos"). O que já está marcado não é marcado de novo."""
    pattern, form_to_id = _forms_regex()
    return pattern.sub(
        lambda m: (
            m.group(0) if m.group(1) is None else spell_ref(form_to_id[m.group(1)], m.group(1))
        ),
        text,
    )
