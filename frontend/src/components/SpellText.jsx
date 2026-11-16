import { hasSpellIcon, parseSpellText } from "../lib/spellText.js";
import SpellIcon from "./SpellIcon.jsx";

// Uma menção a magia: ícone do jogo à esquerda do nome. O ícone e a primeira palavra ficam juntos
// (sem quebra), para o ícone nunca ficar sozinho no fim da linha; o resto do nome pode quebrar.
// Sem ícone no catálogo, o nome sai como texto puro, sem span.
function SpellRef({ id, text }) {
  if (!hasSpellIcon(id)) return text;
  const [, first, rest] = /^(\S+)([\s\S]*)$/.exec(text) ?? [null, text, ""];
  return (
    <span className="spell-ref" data-spell-id={id}>
      <span className="spell-lead">
        <SpellIcon id={id} />
        {first}
      </span>
      {rest}
    </span>
  );
}

// Nome de magia que já vem com o ID separado (tabela por habilidade, linha do tempo).
export function SpellName({ id, children }) {
  return <SpellRef id={id} text={String(children)} />;
}

// Texto do motor com a marcação `{{spell:<id>|<texto>}}` (item 12.9).
export default function SpellText({ text }) {
  return parseSpellText(text).map((segment, index) =>
    segment.type === "text" ? (
      segment.text
    ) : (
      <SpellRef key={index} id={segment.id} text={segment.text} />
    ),
  );
}
