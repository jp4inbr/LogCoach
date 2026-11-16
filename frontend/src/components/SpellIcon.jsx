import { useState } from "react";
import icons from "../data/spell-icons.json";
import { hasSpellIcon } from "../lib/spellText.js";

/** Ícone do jogo de uma magia pelo ID. Sem ID no catálogo ou com a imagem quebrada, some. */
export default function SpellIcon({ id }) {
  const [failed, setFailed] = useState(false);
  const file = hasSpellIcon(id) ? icons[String(id)] : null;
  if (!file || failed) return null;
  return (
    <img
      className="spell-icon"
      src={`${import.meta.env.BASE_URL}icons/${file}`}
      alt=""
      aria-hidden="true"
      loading="lazy"
      width="18"
      height="18"
      onError={() => setFailed(true)}
    />
  );
}
