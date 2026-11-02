import { useEffect, useState } from "react";

// Tempo até a próxima busca automática, em minutos (o intervalo é de minutos; segundos só
// fariam a linha mudar à toa). Remontado a cada busca (key), conta da hora em que a última
// terminou.
function Countdown({ from, to }) {
  const [now, setNow] = useState(from);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const seconds = Math.ceil((to - now) / 1000);
  if (seconds <= 0) return "atualizando em instantes…";
  const when = seconds < 60 ? "menos de 1 min" : `${Math.ceil(seconds / 60)} min`;
  return `próxima atualização em ${when} (ou clique em “Atualizar lutas”).`;
}

// Aviso da atualização automática da lista de lutas (log ao vivo).
//
// A frase de estado fica numa região viva, sempre montada (vazia quando a automática está
// desligada), para o leitor de tela anunciar só as mudanças de estado: ligou, luta começou a
// subir, esperando o próximo pull, parou. A contagem e o "buscando agora" ficam numa irmã
// fora da região viva, para não serem lidos a cada mudança.
//
// Props: state ("off" | "uploading" | "waiting" | "stopped"), busy (busca em andamento,
// manual ou automática), lastDoneAt e intervalMs (para a contagem), stopAfter (quantas
// automáticas seguidas sem novidade até parar).
export default function AutoRefreshNotice({ state, busy, lastDoneAt, intervalMs, stopAfter }) {
  const running = state === "uploading" || state === "waiting";
  const stoppedMin = Math.round((stopAfter * intervalMs) / 60_000);
  const className =
    state === "off"
      ? "sr-only"
      : `auto-refresh ${state === "stopped" ? "auto-refresh-stopped" : ""}`;

  let text = null;
  if (state === "uploading") {
    text = (
      <>
        <strong>Acompanhando o log ao vivo</strong> (luta subindo para o Warcraft Logs)
      </>
    );
  } else if (state === "waiting") {
    text = (
      <>
        <strong>Acompanhando o log ao vivo</strong> (esperando o próximo pull)
      </>
    );
  } else if (state === "stopped") {
    text = (
      <>
        <strong>Atualização automática parada:</strong> nada mudou nas últimas {stopAfter}{" "}
        atualizações (cerca de {stoppedMin} min). “Atualizar lutas” confere de novo e volta a
        acompanhar.
      </>
    );
  }

  return (
    <div className={className}>
      <p>
        <span aria-live="polite">{text}</span>
        {running && (
          <span className="auto-refresh-status">
            {": "}
            {busy ? (
              <>
                buscando agora…
                <span className="auto-refresh-dot" aria-hidden="true" />
              </>
            ) : lastDoneAt !== null ? (
              <Countdown key={lastDoneAt} from={lastDoneAt} to={lastDoneAt + intervalMs} />
            ) : null}
          </span>
        )}
      </p>
    </div>
  );
}
