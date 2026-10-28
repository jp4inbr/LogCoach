import { formatNumber } from "../lib/format.js";

// Um erro do relatório: título, quanto custou, explicação, o que fazer e os números do código.
// Na hipótese (RF23/RF24) não há custo confirmado: o número é a diferença que as regras não
// explicam, e o card fica sem posição na lista (rank nulo).
export default function MistakeCard({ mistake, rank }) {
  const impact =
    mistake.impact_pct === null
      ? "Risco de morte, sem perda direta de dano"
      : mistake.kind === "hipotese"
        ? `As regras não explicam cerca de ${formatNumber(mistake.impact_pct)} pontos da diferença`
        : `Custou cerca de ${formatNumber(mistake.impact_pct)}% do seu dano`;

  return (
    <article className={`mistake mistake-${mistake.severity}`}>
      <header className="mistake-head">
        {rank && (
          <span className="mistake-rank" aria-hidden="true">
            {rank}
          </span>
        )}
        <div>
          <h3>{mistake.title}</h3>
          <p className="mistake-meta">
            <span className={`badge badge-${mistake.severity}`}>
              {mistake.severity === "erro" ? "✕ Erro" : "! Atenção"}
            </span>
            {mistake.kind === "hipotese" && (
              <span className="badge badge-hipotese" title="Apontado pelo coach, sem regra fixa">
                Hipótese do coach
              </span>
            )}
            {mistake.phase && <span className="muted">{mistake.phase}</span>}
          </p>
        </div>
      </header>

      <p className="mistake-impact">{impact}</p>
      <p>{mistake.explanation}</p>
      <div className="mistake-todo">
        <strong>O que fazer</strong>
        <p>{mistake.what_to_do}</p>
      </div>

      {mistake.numbers.length > 0 && (
        <table className="numbers">
          <thead>
            <tr>
              <th scope="col">Medida</th>
              <th scope="col">Você</th>
              <th scope="col">Melhores</th>
            </tr>
          </thead>
          <tbody>
            {mistake.numbers.map((row) => (
              <tr key={row.label}>
                <th scope="row">{row.label}</th>
                <td>{row.player}</td>
                <td>{row.top}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </article>
  );
}
