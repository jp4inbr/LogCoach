// Termo técnico com uma dica curta ao passar o mouse ou tocar (heurística "ajuda e documentação").
// A dica nasce alinhada à esquerda do termo; perto da borda direita da tela ela é deslocada para
// a esquerda (variável --gap-tip-x), para nunca sair da tela, no celular ou no PC.
import { useRef } from "react";
import { tipShift } from "../lib/tip.js";

export default function Term({ children, tip, label }) {
  const ref = useRef(null);
  const place = () => {
    const el = ref.current;
    if (!el) return;
    const shift = tipShift(el.getBoundingClientRect().left, document.documentElement.clientWidth);
    el.style.setProperty("--gap-tip-x", `${shift}px`);
  };
  return (
    <span
      ref={ref}
      className="term"
      tabIndex={0}
      data-tip={tip}
      aria-label={`${label ?? children}: ${tip}`}
      onMouseEnter={place}
      onFocus={place}
      onTouchStart={place}
    >
      {children}
    </span>
  );
}
