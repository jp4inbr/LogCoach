import { formatNumber } from "../lib/format.js";
import Term from "./Term.jsx";

// Diferença para os tops = erros + sorte + não explicado, em % do dano do próprio jogador
// (decisão de 03/11). Barra com as partes positivas; as negativas (ex.: o jogador teve sorte)
// aparecem só no texto, porque não cabem numa barra que soma o total.
const PARTS = [
  {
    key: "mistakes_pct",
    className: "gap-mistakes",
    label: "Erros",
    tip: "Soma do custo de cada erro que as regras medem no seu log (aba “Todas as regras”).",
    negative: "Erros",
  },
  {
    key: "luck_pct",
    className: "gap-luck",
    label: "Azar com a Seta Prismática",
    tip: "A Seta Prismática (Prismatic Bolt) é sorte: compara quantas vieram com quantas eram esperadas pelos seus acúmulos. Azar não é erro seu.",
    negative: "Sorte com a Seta Prismática (a seu favor)",
  },
  {
    key: "unexplained_pct",
    className: "gap-unexplained",
    label: "Não explicado",
    tip: "O que sobra da diferença depois dos erros e da sorte: nenhuma regra mede. Vale olhar a tabela por habilidade e a de dano por alvo.",
    negative: "Não explicado (a seu favor)",
  },
];

export default function GapBreakdown({ gap }) {
  if (!gap) return null;
  const total = gap.total_pct;
  const positive = PARTS.filter((part) => gap[part.key] > 0);
  const barTotal = positive.reduce((sum, part) => sum + gap[part.key], 0);

  return (
    <section className="gap" aria-label="De onde vem a diferença para os tops">
      <p className={`gap-headline ${total > 0 ? "text-down" : "text-up"}`}>
        {total > 0 ? (
          <>
            Os tops fizeram <strong>{formatNumber(total)}% mais dano</strong> que você.
          </>
        ) : (
          <>
            Você fez <strong>{formatNumber(-total)}% mais dano</strong> que a média dos tops.
          </>
        )}{" "}
        <span className="muted">De onde vem essa diferença:</span>
      </p>

      {barTotal > 0 && (
        <div className="gap-bar" aria-hidden="true">
          {positive.map((part) => (
            <span
              key={part.key}
              className={part.className}
              style={{ width: `${(gap[part.key] / barTotal) * 100}%` }}
            />
          ))}
        </div>
      )}

      <ul className="gap-list">
        {PARTS.map((part) => {
          const value = gap[part.key];
          const favor = value < 0;
          return (
            <li key={part.key}>
              <span className={`gap-dot ${favor ? "" : part.className}`} aria-hidden="true" />
              <Term tip={part.tip}>{favor ? part.negative : part.label}</Term>
              <strong className={favor ? "text-up" : undefined}>
                {favor ? "−" : ""}
                {formatNumber(Math.abs(value))}%
              </strong>
            </li>
          );
        })}
      </ul>
      <p className="field-hint">Em % do seu próprio dano na luta.</p>
    </section>
  );
}
