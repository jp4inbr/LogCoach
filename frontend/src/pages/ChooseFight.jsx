import { useEffect, useEffectEvent, useRef, useState } from "react";
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
// Enquanto alguma luta ainda está subindo para o Warcraft Logs, a lista se refaz sozinha.
const AUTO_REFRESH_MS = 30_000;
// Falhas passageiras (Warcraft Logs ou LogCoach fora do ar, sem conexão): vale tentar de novo
// sem mexer no link.
const TEMPORARY_ERRORS = new Set(["wcl_unavailable", "unexpected_error", "network", "unknown"]);

// Dentro do relatório o personagem é o id do ator do WCL (homônimos de reinos diferentes
// têm ids diferentes). É esse id que vai no POST /analyses.
function playerKey(player) {
  return String(player.actor_id);
}

// Personagem salvo: { name, server }, porque o id do ator muda de um relatório para outro.
// Versões antigas guardavam só o nome (string).
function loadCharacter() {
  const saved = load(CHARACTER_KEY);
  if (typeof saved === "string") return { name: saved, server: null };
  return saved?.name ? { name: saved.name, server: saved.server ?? null } : null;
}

// Sem reino salvo (formato antigo), casa só pelo nome; o reino entra quando existir.
function matchesCharacter(player, saved) {
  return player.name === saved.name && (!saved.server || player.server === saved.server);
}

// Hora em que a lista foi lida do Warcraft Logs: "21:04".
function formatTime(iso) {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

// O servidor sempre consulta o Warcraft Logs de novo (com uma trava de 15 s: dentro dela
// devolve a mesma lista, com o mesmo fetched_at). Serve para abrir, atualizar e para a
// atualização automática.
function resolveReport(code) {
  return api.post("/reports/resolve", {
    url: `https://www.warcraftlogs.com/reports/${code}`,
    refresh: true,
  });
}

// O que mudou entre duas listas: lutas com id novo e lutas que passaram a poder ser
// analisadas (ex.: terminaram de subir para o Warcraft Logs).
function compareFights(before, after) {
  const known = new Map(before.map((item) => [item.id, item]));
  let added = 0;
  let unlocked = 0;
  for (const item of after) {
    const previous = known.get(item.id);
    if (!previous) added += 1;
    else if (!previous.supported && item.supported) unlocked += 1;
  }
  return { added, unlocked };
}

function hasNews(news) {
  return news.added + news.unlocked > 0;
}

// "2 lutas novas", "1 luta liberada para análise", "2 lutas novas e 1 liberada para análise".
function newsText({ added, unlocked }) {
  const parts = [];
  if (added) parts.push(added === 1 ? "1 luta nova" : `${added} lutas novas`);
  if (unlocked) {
    const what = unlocked === 1 ? "liberada" : "liberadas";
    const noun = added ? "" : unlocked === 1 ? " luta" : " lutas";
    parts.push(`${unlocked}${noun} ${what} para análise`);
  }
  return parts.length ? parts.join(" e ") : "Nenhuma luta nova";
}

function refreshText(refresh) {
  // Mesmo fetched_at: o servidor devolveu a lista que tinha acabado de ler, sem consultar.
  if (refresh.unchanged) return "A lista já está atualizada";
  return newsText(refresh);
}

// Tela 2: escolher a luta e o personagem (RF04). A lista de lutas vem leve, sem jogadores;
// os Magos Arcanos são buscados quando o usuário escolhe a luta. "Atualizar lutas" traz os
// pulls novos de um log ao vivo, e a lista se refaz sozinha enquanto houver luta subindo.
// Com luta e jogador definidos, os eventos são pré-buscados em segundo plano. Depois do
// clique em Analisar, a mesma tela mostra o andamento em etapas (Tela 3) e abre o resultado
// quando termina.
export default function ChooseFight({ code }) {
  const { token, logout } = useAuth();
  const [report, setReport] = useState({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [refresh, setRefresh] = useState({ status: "idle" });
  const [fightId, setFightId] = useState(null);
  // Magos de cada luta já buscada: { [id]: { status, players | error } }.
  const [playersByFight, setPlayersByFight] = useState({});
  const [chosenPlayer, setChosenPlayer] = useState(null);
  const [run, setRun] = useState({ status: "idle" });
  const [step, setStep] = useState(0);
  const [resultId, setResultId] = useState(null);
  // Atualização da lista em andamento (manual ou automática), para não pedir duas vezes.
  const refreshing = useRef(false);
  const lastFetch = useRef(0);
  // Pré-buscas já pedidas nesta tela, por "luta:ator".
  const prefetched = useRef(new Set());

  useEffect(() => {
    let active = true;
    lastFetch.current = Date.now();
    resolveReport(code)
      .then((data) => active && setReport({ status: "ok", data }))
      .catch((error) => active && setReport({ status: "error", error }));
    return () => {
      active = false;
    };
  }, [code, attempt]);

  const data = report.status === "ok" ? report.data : null;
  const fight = data?.fights.find((item) => item.id === fightId) ?? null;
  const fightPlayers = (fight && playersByFight[fight.id]) ?? { status: "loading" };
  const players = fightPlayers.players ?? [];
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
  const uploading = Boolean(data?.fights.some((item) => item.in_progress));

  // Busca a lista de novo no Warcraft Logs. Se falhar, a lista que já está na tela continua.
  // A manual sempre diz o resultado; a automática só fala quando há novidade.
  function refreshFights(mode) {
    if (!data || refreshing.current) return;
    const before = data;
    refreshing.current = true;
    lastFetch.current = Date.now();
    if (mode === "manual") setRefresh({ status: "loading" });
    resolveReport(before.code)
      .then((fresh) => {
        setReport({ status: "ok", data: fresh });
        const news = compareFights(before.fights, fresh.fights);
        const unchanged = fresh.fetched_at === before.fetched_at;
        if (mode === "manual" || hasNews(news)) {
          setRefresh({ status: "ok", unchanged: unchanged && !hasNews(news), ...news });
        } else {
          // Automática sem novidade: mantém o último aviso de luta nova e apaga o resto
          // (um erro ou um "Nenhuma luta nova" que já não vale para a lista atual).
          setRefresh((current) =>
            current.status === "ok" && !current.unchanged && hasNews(current)
              ? current
              : { status: "idle" },
          );
        }
      })
      .catch((error) => {
        if (mode === "manual") setRefresh({ status: "error", error });
      })
      .finally(() => {
        refreshing.current = false;
      });
  }

  const autoRefresh = useEffectEvent(() => {
    if (document.visibilityState === "visible") refreshFights("auto");
  });

  // Enquanto houver luta subindo, refaz a lista a cada 30 s, só com a aba visível. Ao voltar
  // para a aba depois desse tempo, atualiza na hora. O intervalo recomeça a cada lista nova.
  useEffect(() => {
    if (!uploading) return undefined;
    const timer = setInterval(autoRefresh, AUTO_REFRESH_MS);
    function onVisibility() {
      if (Date.now() - lastFetch.current >= AUTO_REFRESH_MS) autoRefresh();
    }
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [uploading, data?.fetched_at]);

  // Pré-busca dos eventos assim que luta e jogador estão definidos (clicado, único Arcano ou
  // personagem lembrado), para a análise sair mais rápido. É só otimização: falha em
  // silêncio, porque o erro de verdade aparece no /analyses. Uma vez por luta e jogador.
  const prefetchCode = data?.code ?? null;
  const prefetchFight = fight && player ? fight.id : null;
  const prefetchActor = fight && player ? player.actor_id : null;
  useEffect(() => {
    if (!prefetchCode || prefetchFight === null || prefetchActor === null || demoBlocked) return;
    const key = `${prefetchFight}:${prefetchActor}`;
    if (prefetched.current.has(key)) return;
    prefetched.current.add(key);
    api
      .post(
        `/reports/${encodeURIComponent(prefetchCode)}/fights/${prefetchFight}/prefetch`,
        { actor_id: prefetchActor },
        token,
      )
      .catch(() => {});
  }, [prefetchCode, prefetchFight, prefetchActor, demoBlocked, token]);

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
    // Falha passageira: o principal é tentar de novo. Link errado ou relatório privado: o
    // usuário precisa mexer no link, então "Trocar o link" continua sendo o caminho.
    const temporary = TEMPORARY_ERRORS.has(report.error.code);
    return (
      <div className="stack">
        <Notice tone="erro" title="Não deu para abrir esse relatório">
          {report.error.message}
        </Notice>
        <div className="actions">
          {temporary && (
            <button
              type="button"
              className="button primary"
              onClick={() => {
                setReport({ status: "loading" });
                setAttempt((current) => current + 1);
              }}
            >
              Tentar de novo
            </button>
          )}
          <a className="button ghost" href={href("/")}>
            ← Trocar o link
          </a>
        </div>
      </div>
    );
  }

  function loadPlayers(id) {
    const setFor = (state) => setPlayersByFight((current) => ({ ...current, [id]: state }));
    setFor({ status: "loading" });
    api
      .get(`/reports/${encodeURIComponent(data.code)}/fights/${id}/players`)
      .then((body) => setFor({ status: "ok", players: body.players }))
      .catch((error) => setFor({ status: "error", error }));
  }

  function chooseFight(item) {
    if (!item.supported) return;
    setFightId(item.id);
    setChosenPlayer(null);
    setRun({ status: "idle" });
    if (!["ok", "loading"].includes(playersByFight[item.id]?.status)) loadPlayers(item.id);
  }

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
          actor_id: player.actor_id,
        },
        token,
      )
      .then((analysis) => {
        if (!analysis.saved) {
          save(DEMO_KEY, true);
          // Tinha token e mesmo assim não foi guardada: a sessão venceu no meio do uso.
          if (token) logout();
        }
        setResultId(analysis.id);
      })
      .catch((error) => setRun({ status: "error", error }));
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
          Sem conexão com o Warcraft Logs, a lista de lutas vem de um arquivo de exemplo. Os
          outros relatórios abrem quando a conexão voltar.
        </Notice>
      )}

      <section aria-labelledby="fights-title">
        <div className="fights-head">
          <h2 id="fights-title">1. Escolha a luta</h2>
          <div className="fights-refresh">
            <span className="field-hint" aria-live="polite">
              Lista de {formatTime(data.fetched_at)}
              {refresh.status === "ok" && ` · ${refreshText(refresh)}`}
            </span>
            <button
              type="button"
              className="button ghost small"
              disabled={refresh.status === "loading"}
              onClick={() => refreshFights("manual")}
            >
              {refresh.status === "loading" ? "Atualizando…" : "Atualizar lutas"}
            </button>
          </div>
        </div>
        {uploading && (
          <p className="field-hint">
            Tem luta subindo para o Warcraft Logs. A lista se atualiza sozinha a cada 30 segundos
            até ela ficar disponível.
          </p>
        )}
        {refresh.status === "error" && (
          <Notice tone="erro" title="Não deu para atualizar as lutas">
            {refresh.error.message}
          </Notice>
        )}
        <ul className="fight-list">
          {data.fights.map((item) => (
            <li key={item.id}>
              {item.in_progress ? (
                // Luta subindo: ainda não dá para escolher, mas vai dar. Fica focável
                // (aria-disabled em vez de disabled) para o leitor de tela ler o motivo.
                <button
                  type="button"
                  className="fight fight-uploading"
                  aria-disabled="true"
                  onClick={() => chooseFight(item)}
                >
                  <span className="fight-main">
                    <strong>{item.boss}</strong>
                    <span className="muted">
                      {item.difficulty} · luta {item.id}
                    </span>
                  </span>
                  <span className="pill pill-uploading">Subindo…</span>
                  <span className="fight-reason">{item.unsupported_reason}</span>
                </button>
              ) : (
                <button
                  type="button"
                  className={`fight ${item.id === fightId ? "fight-selected" : ""}`}
                  disabled={!item.supported}
                  aria-pressed={item.id === fightId}
                  onClick={() => chooseFight(item)}
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
                  {!item.supported && (
                    <span className="fight-reason">{item.unsupported_reason}</span>
                  )}
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>

      {fight && (
        <section aria-labelledby="players-title">
          <h2 id="players-title">2. Escolha seu Mago Arcano</h2>
          {fightPlayers.status === "loading" ? (
            <p className="field-hint" aria-live="polite">
              Buscando os Magos Arcanos da luta…
            </p>
          ) : fightPlayers.status === "error" ? (
            <Notice
              tone="erro"
              title="Não deu para buscar os personagens da luta"
              action={
                <button
                  type="button"
                  className="button ghost small"
                  onClick={() => loadPlayers(fight.id)}
                >
                  Tentar de novo
                </button>
              }
            >
              {fightPlayers.error.message}
            </Notice>
          ) : players.length === 0 ? (
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
