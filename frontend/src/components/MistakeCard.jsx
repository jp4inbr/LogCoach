import { formatNumber } from "../lib/format.js";
import { plainSpellText } from "../lib/spellText.js";
import Icon from "./Icon.jsx";
import SpellText from "./SpellText.jsx";

// Remove o trecho "Detalhes: ..." que o motor anexa na explicação quando os mesmos detalhes
// vão aparecer na seção expandível logo abaixo.
function stripInlineDetails(explanation, details) {
  if (!explanation || !details?.length) return explanation;
  const inline = `Detalhes: ${details.join("; ")}.`;
  if (!explanation.includes(inline)) return explanation;
  return explanation.replace(inline, "").replace(/\s{2,}/g, " ").trim();
}

// Um erro do relatório: título, quanto custou, explicação, o que fazer e os números do código.
// Na hipótese (RF23/RF24) não há custo confirmado: o número é a diferença que as regras não
// explicam, e o card fica sem posição na lista (rank nulo).
// id: âncora do trilho dos erros (MistakeRail); o cartão recebe o foco quando o link é usado.
export default function MistakeCard({ mistake, rank, id, details }) {
  const impact =
    mistake.impact_pct === null
      ? "Sem custo em dano calculado (risco de morte ou efeito indireto)"
      : mistake.kind === "hipotese"
        ? `As regras não explicam cerca de ${formatNumber(mistake.impact_pct)} pontos da diferença`
        : `Custou cerca de ${formatNumber(mistake.impact_pct)}% do seu dano`;
  const explanation = stripInlineDetails(mistake.explanation, details);

  return (
    <article
      className={`mistake mistake-${mistake.severity}`}
      id={id}
      tabIndex={id ? -1 : undefined}
    >
      <header className="mistake-head">
        {rank && (
          <span className="mistake-rank" aria-hidden="true">
            {rank}
          </span>
        )}
        <div>
          <h3>
            <SpellText text={mistake.title} />
          </h3>
          <p className="mistake-meta">
            <span className={`badge badge-${mistake.severity}`}>
              {mistake.severity === "erro" ? (
                <>
                  <Icon name="x" /> Erro
                </>
              ) : (
                <>
                  <Icon name="alert" /> Atenção
                </>
              )}
            </span>
            {mistake.kind === "hipotese" && (
              <span
                className="badge badge-hipotese"
                title="Diferença que nenhuma regra mede: pistas, não fatos"
              >
                Hipótese
              </span>
            )}
            {mistake.phase && <span className="muted">{mistake.phase}</span>}
          </p>
        </div>
      </header>

      <p className="mistake-impact">{impact}</p>
      <p>
        <SpellText text={explanation} />
      </p>
      <div className="mistake-todo">
        <strong>O que fazer</strong>
        <p>
          <SpellText text={mistake.what_to_do} />
        </p>
      </div>
      {details?.length > 0 && (
        <details className="mistake-details">
          <summary>
            <Icon name="chevron-right" className="mistake-details-chevron" />
            Ver detalhes ({details.length})
          </summary>
          <ul>
            {details.map((detail, index) => (
              <li key={index}>
                <SpellText text={detail} />
              </li>
            ))}
          </ul>
        </details>
      )}

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
              <tr key={plainSpellText(row.label)}>
                <th scope="row">
                  <SpellText text={row.label} />
                </th>
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
