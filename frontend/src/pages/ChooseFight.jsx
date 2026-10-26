import { useEffect, useState } from "react";
import Notice from "../components/Notice.jsx";
import Steps from "../components/Steps.jsx";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth-context.js";
import { formatClock } from "../lib/format.js";
import { href, navigate } from "../lib/router.js";
import { ANALYSIS_STEPS } from "../lib/steps.js";
import { load, save } from "../lib/storage.js";

const DEMO_KEY = "logcoach.demoUsed";
const CHARACTER_KEY = "logcoach.character";
const STEP_MS = 900;

// O mesmo nome pode existir em reinos diferentes: o personagem é sempre nome + reino.
function playerKey(player) {
  return `${player.name}|${player.server ?? ""}`;
}

// Personagem salvo: { name, server }. Versões antigas guardavam só o nome (string).
function loadCharacter() {
  const saved = load(CHARACTER_KEY);
  if (typeof saved === "string") return { name: saved, server: null };
  return saved?.name ? { name: saved.name, server: saved.server ?? null } : null;
}

// Sem reino salvo (formato antigo), casa só pelo nome; o reino entra quando existir.
function matchesCharacter(player, saved) {
  return player.name === saved.name && (!saved.server || player.server === saved.server);
}

// Tela 2: escolher a luta e o personagem (RF04). Depois do clique, a mesma tela mostra o
// andamento em etapas (Tela 3) e abre o resultado quando termina.
export default function ChooseFight({ code }) {
  const { token, logout } = useAuth();
  const [report, setReport] = useState({ status: "loading" });
  const [fightId, setFightId] = useState(null);
  const [chosenPlayer, setChosenPlayer] = useState(null);
  const [run, setRun] = useState({ status: "idle" });
  const [step, setStep] = useState(0);
  const [resultId, setResultId] = useState(null);

  useEffect(() => {
    let active = true;
    api
      .post("/reports/resolve", { url: `https://www.warcraftlogs.com/reports/${code}` })
      .then((data) => active && setReport({ status: "ok", data }))
      .catch((error) => active && setReport({ status: "error", error }));
    return () => {
      active = false;
    };
  }, [code]);

  // Avança as etapas enquanto a análise roda; a última espera o resultado chegar.
  useEffect(() => {
    if (run.status !== "running") return undefined;
    const timer = setInterval(
      () => setStep((current) => Math.min(current + 1, ANALYSIS_STEPS.length - 1)),
      STEP_MS,
    );
    return () => clearInterval(timer);
  }, [run.status]);

  useEffect(() => {
    if (!resultId || step < ANALYSIS_STEPS.length - 1) return undefined;
    const timer = setTimeout(() => navigate(`/analise/${resultId}`), STEP_MS);
    return () => clearTimeout(timer);
  }, [resultId, step]);

  if (report.status === "loading") {
    return <p className="loading">Abrindo o relatório…</p>;
  }

  if (report.status === "error") {
    return (
      <div className="stack">
        <Notice tone="erro" title="Não deu para abrir esse relatório">
          {report.error.message}
        </Notice>
        <a className="button ghost" href={href("/")}>
          ← Trocar o link
        </a>
      </div>
    );
  }

  const { data } = report;
  const fight = data.fights.find((item) => item.id === fightId) ?? null;
  const players = fight?.players ?? [];
  const savedCharacter = loadCharacter();
  const savedMatches = savedCharacter
    ? players.filter((p) => matchesCharacter(p, savedCharacter))
    : [];
  // Personagem salvo ou único da luta já vem marcado (heurística "flexibilidade e eficiência").
  // Se o nome salvo bater com mais de um reino, nada vem marcado: o usuário escolhe.
  const selectedKey =
    chosenPlayer ??
    (savedMatches.length === 1 ? playerKey(savedMatches[0]) : null) ??
    (players.length === 1 ? playerKey(players[0]) : null);
  const player = players.find((p) => playerKey(p) === selectedKey) ?? null;
  const demoBlocked = !token && load(DEMO_KEY, false);

  function startAnalysis() {
    setRun({ status: "running" });
    setStep(0);
    save(CHARACTER_KEY, { name: player.name, server: player.server ?? null });
    api
      .post(
        "/analyses",
        {
          report_code: data.code,
          fight_id: fight.id,
          player_name: player.name,
          server: player.server ?? null,
        },
        token,
      )
      .then((analysis) => {
        if (!token) save(DEMO_KEY, true);
        setResultId(analysis.id);
      })
      .catch((error) => {
        if (error.code === "invalid_token") logout();
        setRun({ status: "error", error });
      });
  }

  if (run.status === "running") {
    return (
      <div className="card analyzing" aria-live="polite">
        <h1>Analisando sua luta</h1>
        <p className="muted">
          {fight.boss} · {fight.difficulty} · {player.name}
        </p>
        <Steps current={resultId && step === ANALYSIS_STEPS.length - 1 ? step + 1 : step} />
        <p className="field-hint">Leva menos de 2 minutos. Você pode deixar esta aba aberta.</p>
      </div>
    );
  }

  return (
    <div className="choose">
      <div className="page-head">
        <div>
          <p className="eyebrow">Relatório {data.code}</p>
          <h1>{data.title}</h1>
        </div>
        <a className="button ghost" href={href("/")}>
          ← Trocar o link
        </a>
      </div>

      {data.sample && (
        <Notice tone="atencao" title="Relatório de exemplo">
          Nesta versão alfa, a lista de lutas vem de um arquivo de exemplo. A busca real no Warcraft
          Logs entra na próxima etapa.
        </Notice>
      )}

      <section aria-labelledby="fights-title">
        <h2 id="fights-title">1. Escolha a luta</h2>
        <ul className="fight-list">
          {data.fights.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={`fight ${item.id === fightId ? "fight-selected" : ""}`}
                disabled={!item.supported}
                aria-pressed={item.id === fightId}
                onClick={() => {
                  setFightId(item.id);
                  setChosenPlayer(null);
                  setRun({ status: "idle" });
                }}
              >
                <span className="fight-main">
                  <strong>{item.boss}</strong>
                  <span className="muted">
                    {item.difficulty} · luta {item.id} · {formatClock(item.duration_s)}
                  </span>
                </span>
                <span className={`pill ${item.kill ? "pill-kill" : "pill-wipe"}`}>
                  {item.kill ? "Kill" : "Wipe"}
                </span>
                {!item.supported && <span className="fight-reason">{item.unsupported_reason}</span>}
              </button>
            </li>
          ))}
        </ul>
      </section>

      {fight && (
        <section aria-labelledby="players-title">
          <h2 id="players-title">2. Escolha seu Mago Arcano</h2>
          {players.length === 0 ? (
            <Notice tone="atencao">Não achamos nenhum Mago Arcano nessa luta.</Notice>
          ) : (
            <div className="player-list" role="radiogroup" aria-labelledby="players-title">
              {players.map((option) => (
                <label key={playerKey(option)} className="player">
                  <input
                    type="radio"
                    name="player"
                    value={playerKey(option)}
                    checked={selectedKey === playerKey(option)}
                    onChange={() => setChosenPlayer(playerKey(option))}
                  />
                  <span>
                    <span className="player-name">
                      <strong>{option.name}</strong>
                      {option.server && <span className="muted">{option.server}</span>}
                    </span>
                    <span className="muted">
                      {option.spec}
                      {option.item_level ? ` · item level ${option.item_level}` : ""}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          )}
        </section>
      )}

      {run.status === "error" && (
        <Notice
          tone="erro"
          title="A análise não foi concluída"
          action={
            run.error.code === "plan_limit" ? (
              <a className="button ghost" href={href("/planos")}>
                Ver planos
              </a>
            ) : run.error.code === "invalid_token" ? (
              <a className="button ghost" href={href("/entrar?modo=login")}>
                Entrar de novo
              </a>
            ) : null
          }
        >
          {run.error.message}
        </Notice>
      )}

      {demoBlocked ? (
        <Notice
          tone="atencao"
          title="Você já usou a análise de demonstração"
          action={
            <a
              className="button primary"
              href={href(`/entrar?modo=cadastro&depois=${encodeURIComponent(`/relatorio/${code}`)}`)}
            >
              Criar conta grátis
            </a>
          }
        >
          Crie uma conta grátis para fazer até 5 análises por mês e guardar o histórico.
        </Notice>
      ) : (
        <div className="actions">
          <button
            type="button"
            className="button primary"
            disabled={!fight || !player}
            onClick={startAnalysis}
          >
            Analisar
          </button>
          {!fight && <span className="field-hint">Escolha uma luta para continuar.</span>}
        </div>
      )}
    </div>
  );
}
