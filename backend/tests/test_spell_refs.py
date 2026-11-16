"""Marcação de magias do Mago nos textos ao jogador (item 12.9) e catálogo de ícones."""

import glob
import gzip
import json
import re
from pathlib import Path

import pytest
import yaml
from test_engine_report import reference

from app.engine.names import (
    PT_BR_FILE,
    SPELL_REF_RE,
    mage_spell_ids,
    mark_spells,
    spell_name,
    spell_names,
    spell_ref,
    strip_spell_refs,
)
from app.engine.report import TEXTS
from app.engine.rules import APP_DIR
from app.schemas import AnalysisResult

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
CATALOG = json.loads((FRONTEND / "src" / "data" / "spell-icons.json").read_text(encoding="utf-8"))
ICONS_DIR = FRONTEND / "public" / "icons"

# Toda forma escrita de magia ou talento do Mago que não pode sobrar sem marcação. Sensível a
# maiúsculas, igual à marcação (`mark_spells` só pega as formas listadas em `names.py`; as de
# minúscula são só as de "meteoritos"). "Impacto" e "Toque" não aparecem em sentido comum nos
# textos do motor.
FORMS = [
    "Surtos?",
    "Toques?",
    "Mísseis",
    "Salvas?",
    "Saraivada",
    "Impactos?",
    "Setas?(?: Prismáticas?)?",
    "Abstrações?",
    "Alma Arcana",
    "[Mm]eteoritos?",
    "Projéteis Potencializados",
    "Orbes?",
    "Barreira Prismática",
    "Bloco de Gelo",
    "Imagem Espelhada",
    "Alterar Tempo",
    "Cintilação",
    "Frio Enregelante",
    # Talentos
    "Intelecto Arcano",
    "Poder Cumulativo",
    "Cascata de Mana",
    "Tempestade Cerebral",
    "Energia Transbordante",
    "Intuição",
    "Esfera de Fogo Místico",
    "Poder Devastador",
    "Precisão do Falcodrago",
]
FORMS_RE = re.compile(r"(?<!\w)(?:" + "|".join(FORMS) + r")(?!\w)")


def without_refs(text: str) -> str:
    return SPELL_REF_RE.sub("", text)


def leftovers(text: str) -> list[str]:
    return FORMS_RE.findall(without_refs(text))


def marked_texts(result: AnalysisResult) -> list[tuple[str, str]]:
    """(campo, texto) de todos os campos do resultado que levam marcação."""
    out = []
    for m in result.mistakes:
        out += [(f"mistake {m.id} title", m.title), (f"mistake {m.id} explanation", m.explanation)]
        out.append((f"mistake {m.id} what_to_do", m.what_to_do))
        out += [(f"mistake {m.id} number", n.label) for n in m.numbers]
    for r in result.rules:
        out += [(f"rule {r.id} name", r.name)]
        out += [(f"rule {r.id} note", r.note)] if r.note else []
        out += [(f"rule {r.id} reference", r.reference)] if r.reference else []
        out += [(f"rule {r.id} detail", d) for d in r.details]
    return out


# --- spell_ref / strip_spell_refs / mark_spells --------------------------------------


def test_spell_ref_exact_values_and_default_text_from_pt_br():
    assert spell_ref(365350) == "{{spell:365350|Surto Arcano}}"
    assert spell_ref(365350, "Surto") == "{{spell:365350|Surto}}"
    assert spell_ref(1242974, "Saraivada") == "{{spell:1242974|Saraivada}}"
    assert spell_ref(44425) == f"{{{{spell:44425|{spell_name(44425)}}}}}"


@pytest.mark.parametrize("bad", ["a|b", "a{b", "a}b", ""])
def test_spell_ref_rejects_text_that_breaks_the_format(bad):
    with pytest.raises(ValueError):
        spell_ref(365350, bad)


def test_strip_spell_refs_returns_the_displayed_text():
    text = f"Use o {spell_ref(365350, 'Surto')}, depois o {spell_ref(321507, 'Toque')}. Sem {{}}"
    assert strip_spell_refs(text) == "Use o Surto, depois o Toque. Sem {}"
    assert strip_spell_refs("sem marcação") == "sem marcação"


def test_multiple_refs_with_punctuation_stuck_to_them():
    text = f"({spell_ref(44425, 'Salva')}), {spell_ref(5143, 'Mísseis')}; {spell_ref(1242974)}!"
    assert [m.groups() for m in SPELL_REF_RE.finditer(text)] == [
        ("44425", "Salva"),
        ("5143", "Mísseis"),
        ("1242974", "Saraivada Arcana"),
    ]
    assert strip_spell_refs(text) == "(Salva), Mísseis; Saraivada Arcana!"


def test_mark_spells_marks_short_forms_plurals_and_repeats():
    marked = mark_spells("O Surto e os Surtos Arcanos; 2 Impactos, a Salva, meteoritos, Salva.")
    assert marked == (
        "O {{spell:365350|Surto}} e os {{spell:365350|Surtos Arcanos}}; 2 "
        "{{spell:30451|Impactos}}, a {{spell:44425|Salva}}, {{spell:449569|meteoritos}}, "
        "{{spell:44425|Salva}}."
    )


def test_mark_spells_is_idempotent_and_leaves_other_names_alone():
    once = mark_spells("Surto Arcano com Infusão de Poder e Poção")
    assert once == "{{spell:365350|Surto Arcano}} com Infusão de Poder e Poção"
    assert mark_spells(once) == once
    assert mark_spells("Sectário Latente 75%") == "Sectário Latente 75%"
    assert mark_spells("Toquei o Surtoso") == "Toquei o Surtoso"  # só palavra inteira


# --- Cobertura dos textos ------------------------------------------------------------


def test_texts_have_no_unmarked_spell_name_once_marked():
    for check_id, parts in TEXTS.items():
        for part in parts:
            assert leftovers(mark_spells(part)) == [], (check_id, part)
            assert strip_spell_refs(mark_spells(part)) == part  # a marcação não muda o texto


def test_result_texts_have_no_unmarked_spell_name():
    result = reference()
    fields = marked_texts(result)
    assert len(fields) > 40  # o resultado de referência tem texto de sobra para a prova valer
    assert [(f, leftovers(t)) for f, t in fields if leftovers(t)] == []


def test_result_marks_what_the_texts_say():
    # Sanidade contra um `mark_spells` que não marcasse nada: a explicação do soul_entry
    # tem de levar a Alma Arcana, a Saraivada e a Salva marcadas.
    soul = next(m for m in reference().mistakes if m.id == "soul_entry")
    for sid in ("451038", "1242974", "44425"):
        assert f"{{{{spell:{sid}|" in soul.explanation


def test_all_peak_defensives_are_marked():
    from app.engine.rules import load_spec_rules

    for d in load_spec_rules()["defensives"]:
        name = spell_name(d["ability_id"], d["name"])
        assert leftovers(mark_spells(f"uso de {name} só depois da queda")) == [], name


# --- Integridade ---------------------------------------------------------------------


def test_every_brace_pair_is_a_valid_ref_and_every_id_has_an_icon():
    result = reference()
    texts = [t for _, t in marked_texts(result)]
    for text in texts:
        assert text.count("{{") == len(SPELL_REF_RE.findall(text)) == text.count("}}"), text
        for sid, shown in SPELL_REF_RE.findall(text):
            assert sid in CATALOG, (sid, text)
            assert shown.strip() == shown and shown
    assert any("{{" in t for t in texts)


def test_unmarked_fields_stay_plain_text():
    result = reference()
    plain = [r.name for t in result.abilities for r in t.rows]
    plain += [t.name for t in result.timeline] + [r.name for t in result.targets for r in t.rows]
    plain += [p.display_name for p in result.comparison.players]
    assert [t for t in plain if "{{" in t or "}}" in t] == []


def test_ability_rows_carry_the_id_and_mage_rows_have_an_icon():
    rows = [r for t in reference().abilities for r in t.rows]
    assert rows and all(r.ability_id is not None for r in rows)
    for name, ability_id in {
        "Salva Arcana": 44425,
        "Mísseis Arcanos": 5143,
        "Impacto Arcano": 30451,
    }.items():
        found = [r.ability_id for r in rows if r.name == name]
        assert found and set(found) == {ability_id}, (name, found)
    mage_names = {spell_name(i) for i in mage_spell_ids()}
    mage_rows = [r for r in rows if r.name in mage_names]
    assert mage_rows
    assert [r.name for r in mage_rows if str(r.ability_id) not in CATALOG] == []


def test_timeline_tracks_have_ability_ids():
    ids = {t.ability_id for t in reference().timeline}
    assert {365350, 321507, 451038} <= ids


# --- Catálogo de ícones --------------------------------------------------------------


def test_catalog_ids_are_exactly_the_mage_spells():
    assert {int(k) for k in CATALOG} == set(mage_spell_ids())
    assert list(CATALOG) == sorted(CATALOG, key=int)


def test_mage_spells_exclude_potion_and_other_classes_and_have_names():
    ids = mage_spell_ids()
    assert not {1236616, 10060, 2825, 32182, 80353} & ids  # poção, Infusão de Poder, lusts
    assert ids <= set(spell_names())


def test_every_catalog_file_exists_and_is_an_image():
    for spell_id, icon in CATALOG.items():
        path = ICONS_DIR / icon
        assert path.is_file() and path.stat().st_size > 0, (spell_id, icon)
        assert path.read_bytes()[:3] == b"\xff\xd8\xff", (spell_id, icon)  # JPEG


def test_every_name_in_mage_spells_is_marked_as_a_whole_with_a_cataloged_id():
    # Cada nome de magia do Mago, escrito no texto, vira uma marcação com ID do catálogo.
    # (Exceção: "Seta Prismática!" do proc leva a marcação só na parte do nome.)
    for spell_id in mage_spell_ids():
        name = spell_name(spell_id).rstrip("!")
        marked = mark_spells(f"x {name} y")
        found = SPELL_REF_RE.findall(marked)
        assert len(found) == 1, (spell_id, marked)
        assert found[0][1] == name and found[0][0] in CATALOG, (spell_id, marked)


def test_leftovers_detects_an_unmarked_name():
    # Prova de que a checagem pega o erro: sem marcação, o nome sobra.
    assert leftovers("Use o Surto e a Salva") == ["Surto", "Salva"]
    assert leftovers(mark_spells("Use o Surto e a Salva")) == []


def test_frontend_analysis_fixture_is_marked():
    path = FRONTEND / "src" / "test" / "fixtures" / "analysis.json"
    result = AnalysisResult.model_validate(json.loads(path.read_text(encoding="utf-8"))["result"])
    fields = marked_texts(result)
    assert any("{{spell:" in t for _, t in fields)
    assert [(f, leftovers(t)) for f, t in fields if leftovers(t)] == []
    assert all(r.ability_id is not None for t in result.abilities for r in t.rows)


# --- Nomes que não podem ser marcados por engano -------------------------------------


def fight_files() -> list[str]:
    root = Path(__file__).parent / "fixtures"
    files = [
        *glob.glob(str(root / "**" / "*.json.gz"), recursive=True),
        *glob.glob(str(APP_DIR / "samples" / "*.json.gz")),
    ]
    assert files
    return sorted(files)


def fixture_abilities() -> list[dict]:
    out = []
    for path in fight_files():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            out += json.load(f).get("abilities") or []
    return out


def strings_in(node) -> list[str]:
    """Todo valor de chave `name` de um YAML (em qualquer profundidade)."""
    if isinstance(node, dict):
        found = [v for k, v in node.items() if k == "name" and isinstance(v, str)]
        return found + [s for v in node.values() for s in strings_in(v)]
    if isinstance(node, list):
        return [s for v in node for s in strings_in(v)]
    return []


def test_names_that_are_not_mage_spells_are_never_marked():
    # `mark_spells` roda sobre texto já montado, que leva nomes vindos de dados (origem dos
    # picos de dano, buffs, mecânicas). Nenhum deles pode virar ícone por coincidência.
    data = yaml.safe_load(PT_BR_FILE.read_text(encoding="utf-8"))
    mage = {str(i) for i in mage_spell_ids()}
    names = [v for k, v in data["spells"].items() if str(k) not in mage]
    names += list(data["npcs"].values()) + list(data["phases"].values())
    encounters = APP_DIR / "encounters"
    for path in encounters.glob("*.yaml"):
        names += strings_in(yaml.safe_load(path.read_text(encoding="utf-8")))
    names += [a["name"] for a in fixture_abilities() if a.get("gameID") not in mage_spell_ids()]
    assert len(names) > 300
    assert [n for n in names if mark_spells(n) != n] == []


def test_the_guard_catches_a_name_that_would_be_marked():
    assert mark_spells("Surto de Mana") != "Surto de Mana"


def test_catalog_icons_match_the_fixtures_icons():
    from_fixtures: dict[int, set[str]] = {}
    for a in fixture_abilities():
        if str(a.get("gameID")) in CATALOG and a.get("icon"):
            from_fixtures.setdefault(a["gameID"], set()).add(a["icon"])
    assert len(from_fixtures) > 20
    assert {i: icons for i, icons in from_fixtures.items() if icons != {CATALOG[str(i)]}} == {}
