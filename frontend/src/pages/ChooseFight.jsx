import { useEffect, useEffectEvent, useRef, useState } from "react";
import AutoRefreshNotice from "../components/AutoRefreshNotice.jsx";
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
// Log ao vivo (luta subindo ou liberada nesta sessão): a lista se refaz sozinha a cada 4 min.
// Um pull dura 3–7 min, mais a conversa entre pulls; atualizar mais cedo não traz nada, e quem
// quiser adiantar clica em "Atualizar lutas" (que reinicia a contagem).
const AUTO_REFRESH_MS = 4 * 60_000;
// Para depois de 3 automáticas seguidas sem novidade (~12 min: um pull longo + conversa). Daí
// em diante só pelo botão, que volta a ligar.
const AUTO_STOP_AFTER = 3;
// Espera da seleção (luta + jogador) parada antes da pré-busca, para não gastar pontos do
// Warcraft Logs com cliques exploratórios.
const PREFETCH_DELAY_MS = 1000;
// Erros em que vale oferecer "Tentar de novo" sem mexer no link: Warcraft Logs ou LogCoach fora
// do ar, sem conexão. unexpected_error também (o usuário pode tentar), mas ele cobre ainda
// credenciais do servidor e consulta com defeito, que só passam com correção do nosso lado:
// por isso os textos em volta do botão não prometem que vai funcionar; quem diz o que fazer é
// a mensagem do servidor.
const TEMPORARY_ERRORS = new Set(["wcl_unavailable", "unexpected_error", "network"]);

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

// Hora com segundos ("21:04:37"), para o resultado de cliques seguidos não parecer repetido.
function formatSeconds(ms) {
  return new Date(ms).toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// O servidor sempre consulta o Warcraft Logs de novo (com uma trava de 8 s: dentro dela
// devolve a mesma lista, com o mesmo fetched_at). Se o Warcraft Logs falhar e houver lista
// guardada, ela volta com stale: true, a mensagem do erro (stale_message), o código (stale_code,
// se vier) e o fetched_at antigo. Serve para abrir, atualizar e para a atualização automática.
function resolveReport(code) {
  return api.post("/reports/resolve", {
    url: `https://www.warcraftlogs.com/reports/${code}`,
    refresh: true,
  });
}

// O que mudou entre duas listas: lutas com id novo, lutas que passaram a poder ser analisadas
// (ex.: terminaram de subir para o Warcraft Logs), lutas que começaram a subir e lutas que
// terminaram de subir (mesmo sem poder ser analisadas, ex.: outro chefe).
function compareFights(before, after) {
  const known = new Map(before.map((item) => [item.id, item]));
  let added = 0;
  let unlocked = 0;
  let started = 0;
  let finished = 0;
  for (const item of after) {
    const previous = known.get(item.id);
    if (!previous) {
      added += 1;
      if (item.in_progress) started += 1;
      continue;
    }
    if (!previous.supported && item.supported) unlocked += 1;
    if (!previous.in_progress && item.in_progress) started += 1;
    if (previous.in_progress && !item.in_progress) finished += 1;
  }
  return { added, unlocked, started, finished };
}

function hasUploading(fights) {
  return fights.some((item) => item.in_progress);
}

// Novidade que vale anunciar ("1 luta nova", "1 liberada para análise").
function hasNews(news) {
  return news.added + news.unlocked > 0;
}

// Sinal de log ao vivo: qualquer novidade, inclusive luta começando ou terminando de subir.
// Liga o acompanhamento e zera a contagem de automáticas sem novidade.
function hasLiveNews(news) {
  return hasNews(news) || news.started + news.finished > 0;
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
  // Clique com a lista guardada: o servidor continua sem conseguir a lista nova. A hora com
  // segundos mostra que o clique foi atendido. unexpected_error é do nosso lado, não do WCL.
  if (refresh.status === "stale") {
    const time = formatSeconds(refresh.at);
    if (refresh.code === "unexpected_error") {
      return `${refresh.again ? "Ainda não" : "Não"} deu para atualizar (${time})`;
    }
    return `${refresh.again ? "Ainda sem" : "Sem"} resposta do Warcraft Logs (${time})`;
  }
  // Mesmo fetched_at: o servidor devolveu a lista que tinha acabado de ler, sem consultar.
  if (refresh.unchanged) return "A lista já está atualizada";
  return newsText(refresh);
}

// Tela 2: escolher a luta e o personagem (RF04). A lista de lutas vem leve, sem jogadores;
// os Magos Arcanos são buscados quando o usuário escolhe a luta. "Atualizar lutas" traz os
// pulls novos de um log ao vivo, e a lista se refaz sozinha a cada 4 min (com aviso na tela)
// enquanto houver luta subindo ou depois de uma luta liberada nesta sessão, até 3 atualizações
// seguidas sem novidade. Com luta e jogador definidos por 1 s, os
// eventos são pré-buscados em segundo plano. Depois do clique em Analisar, a mesma tela
// mostra o andamento em etapas (Tela 3) e abre o resultado quando termina.
export default function ChooseFight({ code }) {
  const { token, logout } = useAuth();
  const [report, setReport] = useState({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [refresh, setRefresh] = useState({ status: "idle" });
  const [fightId, setFightId] = useState(null);
  // Magos de cada luta já buscada: { [id]: { status, players | error } }; status "empty"
  // (nenhum Arcano) é buscado de novo.
  const [playersByFight, setPlayersByFight] = useState({});
  const [chosenPlayer, setChosenPlayer] = useState(null);
  const [run, setRun] = useState({ status: "idle" });
  const [step, setStep] = useState(0);
  const [resultId, setResultId] = useState(null);
  // Busca da lista em andamento: "manual" | "auto" | null. O ref evita pedir duas vezes
  // antes de o estado chegar à tela.
  const [busy, setBusy] = useState(null);
  const refreshing = useRef(false);
  // Hora em que a última busca da lista terminou (a próxima automática conta daí), se esta
  // sessão já viu o log ao vivo (luta subindo, nova ou liberada) e quantas automáticas seguidas
  // vieram sem novidade (em AUTO_STOP_AFTER, para).
  const [lastDoneAt, setLastDoneAt] = useState(null);
  const [followingLive, setFollowingLive] = useState(false);
  const [autoMisses, setAutoMisses] = useState(0);
  // Pré-buscas já pedidas nesta tela, por "luta:ator".
  const prefetched = useRef(new Set());

  useEffect(() => {
    let active = true;
    resolveReport(code)
      .then((data) => {
        if (!active) return;
        setReport({ status: "ok", data });
        setLastDoneAt(Date.now());
        setAutoMisses(0);
        if (hasUploading(data.fights)) setFollowingLive(true);
      })
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
  const uploading = Boolean(data && hasUploading(data.fights));
  // Log ao vivo: luta subindo agora ou já vista nesta sessão (entre um pull e outro a lista
  // fica sem luta subindo, e o próximo costuma começar em 1–2 min).
  const live = uploading || followingLive;
  const autoStopped = live && autoMisses >= AUTO_STOP_AFTER;
  const autoActive = live && !autoStopped;
  const autoState = !live ? "off" : autoStopped ? "stopped" : uploading ? "uploading" : "waiting";

  // Busca a lista de novo no Warcraft Logs. Se falhar, a lista que já está na tela continua.
  // A manual sempre diz o resultado; a automática só fala quando há novidade. A lista
  // guardada (stale) tem aviso próprio, que só se atualiza (não empilha a cada busca).
  // Clique ou novidade zeram a contagem de automáticas sem novidade; automática sem novidade
  // (inclusive com erro ou lista guardada) soma uma.
  function refreshFights(mode) {
    if (!data || refreshing.current) return;
    const before = data;
    let liveNews = false;
    refreshing.current = true;
    setBusy(mode);
    if (mode === "manual") setRefresh({ status: "idle" });
    resolveReport(before.code)
      .then((fresh) => {
        setReport({ status: "ok", data: fresh });
        const news = compareFights(before.fights, fresh.fights);
        const unchanged = fresh.fetched_at === before.fetched_at;
        liveNews = hasLiveNews(news);
        if (liveNews || hasUploading(fresh.fights)) setFollowingLive(true);
        if (fresh.stale && !hasNews(news)) {
          // "A lista já está atualizada" seria falso. O clique ganha uma resposta com a hora,
          // para não parecer ignorado; a automática deixa o aviso da lista guardada falar.
          if (mode === "manual") {
            setRefresh({
              status: "stale",
              at: Date.now(),
              again: Boolean(before.stale),
              code: fresh.stale_code ?? null,
            });
          }
        } else if (mode === "manual" || hasNews(news)) {
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
        setBusy(null);
        setLastDoneAt(Date.now());
        if (mode === "manual" || liveNews) setAutoMisses(0);
        else setAutoMisses((current) => current + 1);
      });
  }

  const autoRefresh = useEffectEvent(() => {
    if (document.visibilityState === "visible") refreshFights("auto");
  });

  // Com o log ao vivo (e antes de parar), refaz a lista 4 min depois de a última busca terminar
  // (automática ou clique), só com a aba visível: com a aba escondida nada é buscado nem
  // contado. Ao voltar para a aba depois desse tempo, atualiza na hora. Busca em andamento
  // suspende o relógio; ele recomeça quando ela termina.
  useEffect(() => {
    if (!autoActive || busy || lastDoneAt === null) return undefined;
    const delay = Math.max(0, lastDoneAt + AUTO_REFRESH_MS - Date.now());
    const timer = setTimeout(autoRefresh, delay);
    function onVisibility() {
      if (Date.now() - lastDoneAt >= AUTO_REFRESH_MS) autoRefresh();
    }
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [autoActive, busy, lastDoneAt]);

  // Pré-busca dos eventos quando luta e jogador ficam definidos (clicado, único Arcano ou
  // personagem lembrado) e parados por 1 s, para a análise sair mais rápido. É só otimização:
  // falha em silêncio (inclusive prefetch_limit e plan_limit), porque o erro de verdade
  // aparece no /analyses. Uma vez por luta e jogador; não dispara com a análise rodando.
  const prefetchCode = data?.code ?? null;
  const prefetchFight = fight && player ? fight.id : null;
  const prefetchActor = fight && player ? player.actor_id : null;
  const analyzing = run.status === "running";
  useEffect(() => {
    if (!prefetchCode || prefetchFight === null || prefetchActor === null) return undefined;
    if (demoBlocked || analyzing) return undefined;
    const key = `${prefetchFight}:${prefetchActor}`;
    if (prefetched.current.has(key)) return undefined;
    const timer = setTimeout(() => {
      prefetched.current.add(key);
      api
        .post(
          `/reports/${encodeURIComponent(prefetchCode)}/fights/${prefetchFight}/prefetch`,
          { actor_id: prefetchActor },
          token,
        )
        .catch(() => {});
    }, PREFETCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [prefetchCode, prefetchFight, prefetchActor, demoBlocked, analyzing, token]);

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
      // Lista vazia não é definitiva: o Warcraft Logs pode ainda não ter processado a luta.
      // Fica como "empty", que volta a ser buscado ao escolher a luta de novo.
      .then((body) =>
        setFor(body.players.length ? { status: "ok", players: body.players } : { status: "empty" }),
      )
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

  // Falha passageira na análise: o botão principal vira "Tentar de novo" (mesma ação).
  const retryAnalysis = run.status === "error" && TEMPORARY_ERRORS.has(run.error.code);

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
          Sem conexão com o Warcraft Logs, a lista de lutas vem de um arquivo de exemplo. Os outros
          relatórios abrem quando a conexão voltar.
        </Notice>
      )}

      <section aria-labelledby="fights-title">
        <div className="fights-head">
          <h2 id="fights-title">1. Escolha a luta</h2>
          <div className="fights-refresh">
            {/* Só o resultado da atualização é anunciado; a hora da lista fica fora da região
                viva, para não ser lida a cada busca. */}
            <span className="field-hint">
              Lista de {formatTime(data.fetched_at)}
              <span aria-live="polite">
                {["ok", "stale"].includes(refresh.status) && ` · ${refreshText(refresh)}`}
              </span>
            </span>
            {/* aria-disabled em vez de disabled: a busca automática não tira o foco do botão.
                O clique durante uma busca é ignorado em refreshFights. */}
            <button
              type="button"
              className="button ghost small"
              aria-disabled={busy ? "true" : undefined}
              onClick={() => refreshFights("manual")}
            >
              {busy ? "Atualizando…" : "Atualizar lutas"}
            </button>
          </div>
        </div>
        <AutoRefreshNotice
          state={autoState}
          busy={busy !== null}
          lastDoneAt={lastDoneAt}
          intervalMs={AUTO_REFRESH_MS}
          stopAfter={AUTO_STOP_AFTER}
        />
        {/* Título neutro: a causa (WCL fora do ar ou erro nosso) vem na mensagem do servidor. */}
        {data.stale && (
          <Notice tone="atencao" title="Não deu para atualizar a lista">
            {data.stale_message} Mostrando a lista de {formatTime(data.fetched_at)}.
          </Notice>
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
          ) : fightPlayers.status === "empty" ? (
            <Notice
              tone="atencao"
              title="Não achamos nenhum Mago Arcano nessa luta"
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
              Se a luta acabou de terminar, o Warcraft Logs pode ainda estar processando. Tente de
              novo em alguns segundos.
            </Notice>
          ) : (
            <div className="player-list" role="radiogroup" aria-labelledby="players-title">
              {players.map((option) => (
                <label key={playerKey(option)} className="player">
                  <input
                    type="radio"
                    name="player"
                    value={playerKey(option)}
                    checked={selectedKey === playerKey(option)}
                    onChange={() => {
                      setChosenPlayer(playerKey(option));
                      setRun({ status: "idle" });
                    }}
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
              href={href(
                `/entrar?modo=cadastro&depois=${encodeURIComponent(`/relatorio/${code}`)}`,
              )}
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
            {retryAnalysis ? "Tentar de novo" : "Analisar"}
          </button>
          {!fight && <span className="field-hint">Escolha uma luta para continuar.</span>}
        </div>
      )}
    </div>
  );
}
