import { useEffect, useState } from "react";

// Segundos até a próxima busca automática. Remontado a cada busca (key), começa da hora em
// que a última terminou e conta de 1 em 1 s.
function Countdown({ from, to }) {
  const [now, setNow] = useState(from);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const seconds = Math.max(0, Math.ceil((to - now) / 1000));
  return seconds > 0 ? `Próxima atualização em ${seconds} s.` : "Atualizando em instantes…";
}

// Área do aviso de atualização automática da lista de lutas, enquanto houver luta subindo
// para o Warcraft Logs. A frase principal é anunciada pelo leitor de tela só quando muda
// (começou, parou); a contagem e o "buscando agora" ficam fora do anúncio (aria-live="off"),
// para não falar a cada segundo.
//
// Props: active (há luta subindo), stopped (passou do teto sem novidade), busy (busca em
// andamento, manual ou automática), lastDoneAt e intervalMs (para a contagem), limitMin.
export default function AutoRefreshNotice({
  active,
  stopped,
  busy,
  lastDoneAt,
  intervalMs,
  limitMin,
}) {
  const seconds = Math.round(intervalMs / 1000);
  return (
    <div aria-live="polite">
      {active && (
        <div className={`auto-refresh ${stopped ? "auto-refresh-stopped" : ""}`}>
          {stopped ? (
            <p>
              <strong>Atualização automática pausada.</strong> A luta está subindo há mais de{" "}
              {limitMin} minutos sem novidade; o envio do log pode ter parado. Clique em “Atualizar
              lutas” para conferir e voltar a atualizar sozinho.
            </p>
          ) : (
            <>
              <p>
                <strong>Atualizando automaticamente</strong> a cada {seconds} s enquanto houver luta
                subindo para o Warcraft Logs. Não precisa clicar em “Atualizar lutas”.
              </p>
              <p className="auto-refresh-status" aria-live="off">
                {busy ? (
                  <>
                    <span className="auto-refresh-dot" aria-hidden="true" />
                    Buscando agora…
                  </>
                ) : lastDoneAt !== null ? (
                  <Countdown key={lastDoneAt} from={lastDoneAt} to={lastDoneAt + intervalMs} />
                ) : null}
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
