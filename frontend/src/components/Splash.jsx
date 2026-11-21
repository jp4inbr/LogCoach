import { useEffect, useState } from "react";

// Abertura ao entrar no site ("A luz acende"): sobre o fundo do tema, a luz quente nasce no
// centro, o traço "Pulso" se desenha até o ponto aceso e a marca LOGCOACH surge abaixo; depois
// o véu some em fade deixando o cenário aparecer. Decorativa (aria-hidden) e sem bloquear
// cliques (pointer-events no CSS). Quem pede menos movimento no sistema não vê a abertura.
export const SPLASH_MS = 2300; // luz + traço + marca + respiro curto antes de sair
export const SPLASH_FADE_MS = 550; // saída em fade (animação splash-out em index.css)

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

export default function Splash() {
  // "playing" → "leaving" (some com fade) → "gone" (sai do DOM).
  const [phase, setPhase] = useState(() => (prefersReducedMotion() ? "gone" : "playing"));

  useEffect(() => {
    if (phase === "gone") return undefined;
    const leave = setTimeout(() => setPhase("leaving"), SPLASH_MS);
    const gone = setTimeout(() => setPhase("gone"), SPLASH_MS + SPLASH_FADE_MS);
    return () => {
      clearTimeout(leave);
      clearTimeout(gone);
    };
    // Só na montagem: a abertura toca uma vez por carregamento da página.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (phase === "gone") return null;

  return (
    <div
      className={`splash${phase === "leaving" ? " splash-leaving" : ""}`}
      aria-hidden="true"
      data-testid="splash"
    >
      <div className="splash-light" />
      <div className="splash-content">
        <svg className="splash-mark" viewBox="0 0 64 64" focusable="false">
          <path
            className="splash-line"
            pathLength="100"
            d="M11 44 H19 L25 30 L32 46 L39 26 L45 34 L52 16"
          />
          <circle className="splash-dot" cx="52" cy="16" r="4.5" />
        </svg>
        <span className="splash-word">
          LOG<span className="brand-accent">COACH</span>
        </span>
      </div>
    </div>
  );
}
