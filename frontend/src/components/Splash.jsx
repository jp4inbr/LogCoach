import { useEffect, useState } from "react";

// Abertura ao entrar no site: a marca "Pulso" em tela cheia, o traço se desenha até o ponto
// e o ponto é "clicado". Decorativa (aria-hidden) e sem bloquear cliques (pointer-events no
// CSS). Quem pede menos movimento no sistema não vê a abertura.
export const SPLASH_MS = 2900; // fim do clique + um respiro antes de sumir
export const SPLASH_FADE_MS = 500; // saída (animação splash-out em index.css)

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
      <svg className="splash-mark" viewBox="0 0 64 64" focusable="false">
        <defs>
          <linearGradient id="splash-gradient" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" className="splash-stop-a" />
            <stop offset="1" className="splash-stop-b" />
          </linearGradient>
        </defs>
        <g className="splash-square">
          <rect x="2" y="2" width="60" height="60" rx="16" fill="url(#splash-gradient)" />
          <path
            className="splash-line"
            pathLength="100"
            d="M11 44 H19 L25 30 L32 46 L39 26 L45 34 L52 16"
          />
          <circle className="splash-ripple splash-ripple-1" cx="52" cy="16" r="4.5" />
          <circle className="splash-ripple splash-ripple-2" cx="52" cy="16" r="4.5" />
          <circle className="splash-dot" cx="52" cy="16" r="4.5" />
        </g>
      </svg>
    </div>
  );
}
