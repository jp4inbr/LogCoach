import { useState } from "react";
import { formatDps, formatPseudonym } from "../lib/format.js";
import { load, save } from "../lib/storage.js";

const SHOW_NAMES_KEY = "logcoach.showNames";

// Com quem o jogador foi comparado (RF21) e nomes ocultos por padrão (RF25).
// Os outros jogadores aparecem como "Top 1", "Top 2"… e o botão de olho mostra os nomes reais,
// como o "ocultar saldo" de um app de banco (heurística "controle e liberdade do usuário").
// A escolha fica salva no navegador para não precisar repetir a cada análise.
export default function ComparedPlayers({ comparison }) {
  const players = comparison.players ?? [];
  const [showNames, setShowNames] = useState(() => load(SHOW_NAMES_KEY, false) === true);

  if (players.length === 0) return null;

  // Prevenção de erros: sem nenhum nome real (modo exemplo), o botão fica desabilitado e o
  // motivo aparece escrito, em vez de um clique que não faz nada.
  const hasNames = players.some((player) => player.name);
  const revealed = hasNames && showNames;

  function toggle() {
    const next = !showNames;
    setShowNames(next);
    save(SHOW_NAMES_KEY, next);
  }

  return (
    <details className="compared">
      <summary>
        <span className="compared-title">Com quem você foi comparado</span>
        <span className="muted">
          {comparison.label} · {players.length} {players.length === 1 ? "jogador" : "jogadores"}
        </span>
      </summary>

      <div className="compared-body">
        <div className="compared-head">
          <p className="field-hint" id="compared-hint">
            {hasNames
              ? "Os nomes dos outros jogadores ficam ocultos por padrão. Você sempre aparece com o seu."
              : "Nomes reais indisponíveis nos dados de exemplo."}
          </p>
          {/* O rótulo não muda: o estado ligado/desligado vem do aria-pressed e do ícone,
              como pede o padrão de botão de alternância (WAI-ARIA). */}
          <button
            type="button"
            className="button small ghost eye-toggle"
            aria-pressed={revealed}
            aria-describedby="compared-hint"
            disabled={!hasNames}
            title={hasNames ? undefined : "Nomes reais indisponíveis nos dados de exemplo"}
            onClick={toggle}
          >
            <EyeIcon open={revealed} />
            Mostrar nomes
          </button>
        </div>

        <div className="table-wrap">
          <table className="numbers compared-table">
            <caption className="sr-only">
              {comparison.label}: posição, jogador, item level e DPS
            </caption>
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Jogador</th>
                <th scope="col">Item level</th>
                <th scope="col">DPS</th>
              </tr>
            </thead>
            <tbody>
              {players.map((player) => (
                <tr key={player.rank}>
                  <td>{player.rank}º</td>
                  <th scope="row" className="compared-name">
                    {revealed && player.name ? (
                      <>
                        {player.name}
                        {player.server && <span className="muted"> ({player.server})</span>}
                      </>
                    ) : (
                      formatPseudonym(player.display_name)
                    )}
                  </th>
                  <td>{player.item_level ?? "—"}</td>
                  <td>{formatDps(player.dps)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </details>
  );
}

// Olho aberto = nomes visíveis; olho riscado = nomes ocultos.
function EyeIcon({ open }) {
  return (
    <svg className="eye-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
      {!open && <line x1="3" y1="3" x2="21" y2="21" />}
    </svg>
  );
}
