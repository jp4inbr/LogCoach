// Barra de progresso em etapas durante a análise (RNF02, heurística "visibilidade do status").
import { ANALYSIS_STEPS } from "../lib/steps.js";

export default function Steps({ current }) {
  return (
    <ol className="steps" aria-label="Andamento da análise">
      {ANALYSIS_STEPS.map((label, index) => {
        const state = index < current ? "done" : index === current ? "active" : "todo";
        return (
          <li key={label} className={`step step-${state}`} aria-current={state === "active"}>
            <span className="step-dot" aria-hidden="true">
              {state === "done" ? "✓" : index + 1}
            </span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
