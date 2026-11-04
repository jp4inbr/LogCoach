import { useState } from "react";
import ComparedPlayers from "../components/ComparedPlayers.jsx";
import GapBreakdown from "../components/GapBreakdown.jsx";
import MistakeCard from "../components/MistakeCard.jsx";
import Notice from "../components/Notice.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import TargetsTable from "../components/TargetsTable.jsx";
import Term from "../components/Term.jsx";
import Timeline from "../components/Timeline.jsx";
import { useAuth } from "../lib/auth-context.js";
import { formatClock, formatDps, formatNumber, formatSignedPct } from "../lib/format.js";
import { href } from "../lib/router.js";
import { useRequest } from "../lib/useRequest.js";

const TABS = [
  { id: "resumo", label: "Resumo" },
  { id: "linha", label: "Linha do tempo" },
  { id: "regras", label: "Todas as regras" },
];

// Telas 3 e 5: resumo do coach e resultado completo em abas (RF10, RF11, RF17, RF22).
export default function Result({ id }) {
  const { token } = useAuth();
  const request = useRequest(`/analyses/${id}`, token);
  const [tab, setTab] = useState("resumo");

  if (request.status === "loading") return <p className="loading">Carregando a análise…</p>;
  if (request.status === "error") {
    return (
      <div className="stack">
        <Notice
          tone="erro"
          title="Não deu para abrir essa análise"
          action={
            // Análise de uma conta só abre para o dono: sem login, oferece entrar e voltar aqui.
            !token ? (
              <a
                className="button ghost"
                href={href(`/entrar?modo=login&depois=${encodeURIComponent(`/analise/${id}`)}`)}
              >
                Entrar
              </a>
            ) : null
          }
        >
          {request.error.message}
          {!token && " Se ela é da sua conta, entre para abrir."}
        </Notice>
        <a className="button ghost" href={href("/")}>
          ← Fazer uma nova análise
        </a>
      </div>
    );
  }

  const { result, saved } = request.data;
  const { fight, player, summary, comparison } = result;

  return (
    <div className="result">
      <div className="page-head">
        <div>
          <p className="eyebrow">
            {fight.difficulty} · {fight.kill ? "Kill" : "Wipe"} em {formatClock(fight.duration_s)}
          </p>
          <h1>{fight.boss}</h1>
          <p className="muted">
            {player.name}
            {player.server && ` (${player.server})`} · {player.spec} · item level{" "}
            {player.item_level}
          </p>
        </div>
        <a className="button ghost" href={href(`/relatorio/${result.report_code}`)}>
          ← Escolher outra luta
        </a>
      </div>

      {result.source === "exemplo" && (
        <Notice tone="atencao" title="Resultado de exemplo">
          Os números desta tela ainda não vêm do seu log: são um exemplo para mostrar como o
          relatório funciona. O motor de análise entra na próxima etapa.
        </Notice>
      )}

      <div className="stats">
        <div className="stat">
          <span className="stat-label">Seu DPS</span>
          <strong>{formatDps(summary.dps)}</strong>
        </div>
        <div className="stat">
          <span className="stat-label">
            Média do{" "}
            <Term tip="Faixa de 3 níveis de item level do Warcraft Logs. Você é comparado só com quem tem equipamento parecido.">
              {comparison.label}
            </Term>
          </span>
          <strong>{formatDps(summary.top_avg_dps)}</strong>
        </div>
        {result.gap ? (
          // Diferença em % do dano do próprio jogador (decisão de 03/11), detalhada no resumo.
          <div className={`stat ${result.gap.total_pct > 0 ? "stat-down" : "stat-up"}`}>
            <span className="stat-label">Os tops fizeram</span>
            <strong>
              {formatSignedPct(result.gap.total_pct)} <small className="muted">de dano</small>
            </strong>
          </div>
        ) : (
          <div className={`stat ${summary.dps_gap_pct < 0 ? "stat-down" : "stat-up"}`}>
            <span className="stat-label">Diferença</span>
            <strong>{formatSignedPct(summary.dps_gap_pct)}</strong>
          </div>
        )}
        <div className="stat">
          <span className="stat-label">
            <Term tip="Parte da luta em que você estava conjurando algo. A intermissão não conta como tempo parado.">
              Tempo ativo
            </Term>
          </span>
          <strong>
            {formatNumber(summary.active_time_pct)}%{" "}
            <small className="muted">(tops {formatNumber(summary.top_active_time_pct)}%)</small>
          </strong>
        </div>
      </div>

      {comparison.player_in_top && (
        <Notice title="Você está entre os 10 melhores do seu bracket">
          Este log está no ranking: ele saiu da comparação e entrou o 11º colocado, para você não
          ser comparado com você mesmo.
        </Notice>
      )}

      {comparison.stale && (
        <Notice title="Comparação com tops guardados">
          O Warcraft Logs estava fora do ar, então usamos os melhores do bracket guardados há mais
          de 24 horas. O ranking de hoje pode estar um pouco diferente.
        </Notice>
      )}
      {comparison.sample && (
        <Notice title="Comparação com tops de exemplo">
          Não deu para buscar os melhores do seu bracket agora: a comparação usa a cópia de exemplo
          do LogCoach.
        </Notice>
      )}

      {/* Logo abaixo da "Média do bracket", que é a média desses jogadores (proximidade). */}
      <ComparedPlayers comparison={comparison} />

      <div className="tabs" role="tablist" aria-label="Partes do relatório">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`tab-${item.id}`}
            aria-selected={tab === item.id}
            aria-controls={`panel-${item.id}`}
            className={`tab ${tab === item.id ? "tab-active" : ""}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "resumo" && <Summary result={result} />}
        {tab === "linha" && (
          <Timeline duration={fight.duration_s} phases={result.phases} tracks={result.timeline} />
        )}
        {tab === "regras" && <Rules result={result} />}
      </div>

      {!saved && (
        <Notice
          title="Esta análise não foi guardada"
          action={
            <a className="button primary" href={href("/entrar?modo=cadastro")}>
              Criar conta grátis
            </a>
          }
        >
          Com uma conta você guarda o histórico e acompanha sua evolução no chefe.
        </Notice>
      )}
    </div>
  );
}

function Summary({ result }) {
  const { coach } = result;
  // Primeiro os erros que as regras confirmam; as hipóteses vêm depois, separadas (RF23, RF24).
  const mistakes = result.mistakes.filter((mistake) => mistake.kind === "regra");
  const hypotheses = result.mistakes.filter((mistake) => mistake.kind === "hipotese");
  return (
    <div className="stack">
      {coach.available ? (
        <div className="coach">
          <span className="coach-avatar" aria-hidden="true">
            ✦
          </span>
          <div>
            <strong>Resumo do coach</strong>
            <p>{coach.headline}</p>
          </div>
        </div>
      ) : result.source === "motor" ? (
        <Notice title="Explicação do coach em breve">
          Por enquanto o relatório sai só das regras, calculadas direto do seu log. O coach vai
          explicar e ordenar os erros na próxima versão.
        </Notice>
      ) : (
        <Notice tone="atencao" title="Explicação do coach indisponível agora">
          Os erros abaixo vêm só das regras, que são calculadas direto do log e continuam valendo.
        </Notice>
      )}

      <GapBreakdown gap={result.gap} />

      <h2>Erros do maior para o menor impacto</h2>
      {mistakes.length === 0 ? (
        <Notice title="Nenhum erro encontrado">
          Sua luta bateu com os melhores em todas as regras.
        </Notice>
      ) : (
        mistakes.map((mistake, index) => (
          <MistakeCard key={mistake.id} mistake={mistake} rank={index + 1} />
        ))
      )}

      {hypotheses.length > 0 && (
        <>
          <h2>O que as regras não explicam</h2>
          <p className="muted">
            Diferença que nenhuma regra mede. As tabelas apontam onde olhar, mas são pistas, não
            erros confirmados.
          </p>
          {hypotheses.map((mistake) => (
            <MistakeCard key={mistake.id} mistake={mistake} rank={null} />
          ))}
        </>
      )}

      <div className="ask">
        <label htmlFor="ask">Pergunte ao coach sobre um erro</label>
        <div className="link-row">
          <input id="ask" type="text" placeholder="Ex.: por que segurar a Salva Arcana?" disabled />
          <button type="button" className="button ghost" disabled>
            Perguntar
          </button>
        </div>
        <p className="field-hint">Em breve, no plano Pro.</p>
      </div>
    </div>
  );
}

function Rules({ result }) {
  // Coluna "Referência" só quando o motor manda a régua (análises antigas não têm).
  const hasReference = result.rules.some((rule) => rule.reference);
  return (
    <div className="stack">
      <div className="table-wrap">
        <table className="rules">
          <thead>
            <tr>
              <th scope="col">Regra</th>
              <th scope="col">Você</th>
              <th scope="col">Melhores</th>
              {hasReference && <th scope="col">Referência</th>}
              <th scope="col">Situação</th>
            </tr>
          </thead>
          <tbody>
            {result.rules.map((rule) => (
              <tr key={rule.id}>
                <th scope="row">
                  {rule.name}
                  {rule.note && <span className="rule-note">{rule.note}</span>}
                  {rule.details?.length > 0 && (
                    <details className="rule-details">
                      <summary>
                        {rule.details.length === 1
                          ? "1 detalhe"
                          : `${rule.details.length} detalhes`}
                      </summary>
                      <ul>
                        {rule.details.map((detail, index) => (
                          <li key={index}>{detail}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                </th>
                <td>{rule.player_value}</td>
                <td>{rule.top_value}</td>
                {hasReference && <td className="rule-reference">{rule.reference ?? "—"}</td>}
                <td>
                  <StatusBadge status={rule.status} />
                  {rule.impact_pct != null && rule.impact_pct > 0 && (
                    <span className="rule-note">
                      custou ~{formatNumber(rule.impact_pct)}% do dano
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>
        Por habilidade{" "}
        <Term tip="Casts por minuto e parte do dano total de cada habilidade, ao lado da média dos melhores. Serve para achar o que destoa mesmo sem regra própria.">
          (o que é?)
        </Term>
      </h2>
      {result.abilities.map((table) => (
        <div className="table-wrap" key={table.phase}>
          <table className="abilities">
            <caption>{table.phase}</caption>
            <thead>
              <tr>
                <th scope="col">Habilidade</th>
                <th scope="col">Por minuto (você / tops)</th>
                <th scope="col">% do dano (você / tops)</th>
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row) => (
                <tr key={row.name}>
                  <th scope="row">{row.name}</th>
                  <td>
                    {formatNumber(row.player_cpm)} / {formatNumber(row.top_cpm)}
                  </td>
                  <td>
                    {formatNumber(row.player_dmg_pct)} / {formatNumber(row.top_dmg_pct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      <TargetsTable targets={result.targets} />
    </div>
  );
}
