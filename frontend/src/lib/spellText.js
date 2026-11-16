import icons from "../data/spell-icons.json";

// Textos do motor com menção a magia: "{{spell:<id>|<texto exibido>}}" (item 12.9). Mesmo formato
// de SPELL_REF_RE em backend/app/engine/names.py. Marcação malformada fica como texto literal.
const SPELL_REF = /\{\{spell:(\d+)\|([^|{}]+)\}\}/g;

/** Quebra o texto em segmentos { type: "text", text } | { type: "spell", id, text }. */
export function parseSpellText(str) {
  if (typeof str !== "string" || str === "") return [];
  const segments = [];
  let last = 0;
  for (const match of str.matchAll(SPELL_REF)) {
    if (match.index > last) segments.push({ type: "text", text: str.slice(last, match.index) });
    segments.push({ type: "spell", id: match[1], text: match[2] });
    last = match.index + match[0].length;
  }
  if (last < str.length) segments.push({ type: "text", text: str.slice(last) });
  return segments;
}

/** O texto como a pessoa lê, sem a marcação (para title, aria-label, key e document.title). */
export function plainSpellText(str) {
  if (typeof str !== "string") return "";
  return str.replace(SPELL_REF, (_all, _id, text) => text);
}

/** O ID tem ícone no catálogo (`src/data/spell-icons.json`, gerado por `scripts/save_icons.py`). */
export function hasSpellIcon(id) {
  return Object.hasOwn(icons, String(id));
}
