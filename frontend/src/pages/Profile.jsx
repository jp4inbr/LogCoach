import { useState } from "react";
import EvolutionChart from "../components/EvolutionChart.jsx";
import Notice from "../components/Notice.jsx";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth-context.js";
import { formatDateTime, formatDps, formatSignedPct } from "../lib/format.js";
import { href, navigate } from "../lib/router.js";
import { useRequest } from "../lib/useRequest.js";

// Tela 4: perfil, uso do plano, histórico e evolução (RF12, RF13, RF14, RNF07).
export default function Profile() {
  const { token, logout } = useAuth();
  const me = useRequest("/me", token);
  const history = useRequest("/me/analyses", token);

  if (!token) {
    return (
      <Notice
        title="Entre para ver seu perfil"
        action={
          <a className="button primary" href={href("/entrar?modo=login&depois=/perfil")}>
            Entrar
          </a>
        }
      >
        O histórico e a evolução ficam guardados na sua conta.
      </Notice>
    );
  }

  const failed = me.status === "error" ? me : history.status === "error" ? history : null;
  if (failed) {
    const expired = failed.error.code === "invalid_token";
    return (
      <Notice
        tone="erro"
        title={expired ? "Sua sessão expirou" : "Não deu para abrir seu perfil"}
        action={
          expired && (
            <button
              type="button"
              className="button primary"
              onClick={() => {
                logout();
                navigate("/entrar?modo=login&depois=/perfil");
              }}
            >
              Entrar de novo
            </button>
          )
        }
      >
        {failed.error.message}
      </Notice>
    );
  }
  if (me.status === "loading" || history.status === "loading") {
    return <p className="loading">Carregando seu perfil…</p>;
  }

  const account = me.data;
  const analyses = history.data;
  const used = Math.min(account.analyses_this_month, account.monthly_limit);

  return (
    <div className="profile stack">
      <div className="page-head">
        <div>
          <p className="eyebrow">Plano grátis</p>
          <h1>Seu perfil</h1>
          <p className="muted">{account.email}</p>
        </div>
        <a className="button primary" href={href("/")}>
          Nova análise
        </a>
      </div>

      <section className="card">
        <h2>Análises deste mês</h2>
        <div
          className="meter"
          role="meter"
          aria-valuemin={0}
          aria-valuemax={account.monthly_limit}
          aria-valuenow={used}
          aria-label="Análises usadas no mês"
        >
          <span style={{ width: `${(used / account.monthly_limit) * 100}%` }} />
        </div>
        <p className="muted">
          {used} de {account.monthly_limit} usadas · o limite volta no dia 1º.{" "}
          <a href={href("/planos")}>Ver o plano Pro</a>
        </p>
      </section>

      <section className="card">
        <h2>Sua evolução</h2>
        <Evolution analyses={analyses} />
      </section>

      <section className="card">
        <h2>Histórico</h2>
        {analyses.length === 0 ? (
          <p className="muted">Suas análises aparecem aqui depois da primeira.</p>
        ) : (
          <ul className="history">
            {analyses.map((item) => (
              <li key={item.id}>
                <a href={href(`/analise/${item.id}`)} className="history-item">
                  <span>
                    <strong>{item.boss}</strong>
                    <span className="muted">
                      {item.difficulty} · {item.player_name} · {formatDateTime(item.created_at)}
                    </span>
                  </span>
                  <span className="history-numbers">
                    <strong>{formatDps(item.dps)}</strong>
                    <span className={item.dps_gap_pct < 0 ? "text-down" : "text-up"}>
                      {formatSignedPct(item.dps_gap_pct)} vs. tops
                    </span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card">
        <h2>Alterar senha</h2>
        <PasswordForm token={token} />
      </section>

      <section className="card danger-zone">
        <h2>Excluir conta</h2>
        <DeleteAccount token={token} onDeleted={logout} />
      </section>
    </div>
  );
}

function Evolution({ analyses }) {
  // Usa o chefe com mais análises; o histórico vem do mais novo para o mais antigo.
  const byBoss = new Map();
  for (const item of analyses) byBoss.set(item.boss, [...(byBoss.get(item.boss) ?? []), item]);
  const [boss, points] = [...byBoss.entries()].sort((a, b) => b[1].length - a[1].length)[0] ?? [];

  if (!points || points.length < 2) {
    return (
      <p className="muted">
        Faça pelo menos duas análises do mesmo chefe para ver a evolução do seu DPS.
      </p>
    );
  }
  return (
    <>
      <p className="muted">DPS por análise · {boss}</p>
      <EvolutionChart points={[...points].reverse()} />
    </>
  );
}

function PasswordForm({ token }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [state, setState] = useState({ status: "idle" });

  async function submit(event) {
    event.preventDefault();
    if (next.length < 8) {
      setState({ status: "error", message: "A nova senha precisa ter pelo menos 8 caracteres." });
      return;
    }
    setState({ status: "sending" });
    try {
      await api.put("/me/password", { current_password: current, new_password: next }, token);
      setCurrent("");
      setNext("");
      setState({ status: "done" });
    } catch (error) {
      setState({ status: "error", message: error.message });
    }
  }

  return (
    <form className="form form-inline" onSubmit={submit} noValidate>
      <div className="field">
        <label htmlFor="current-password">Senha atual</label>
        <input
          id="current-password"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(event) => setCurrent(event.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="new-password">Nova senha</label>
        <input
          id="new-password"
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={(event) => setNext(event.target.value)}
        />
      </div>
      <button type="submit" className="button ghost" disabled={state.status === "sending"}>
        Salvar nova senha
      </button>
      {state.status === "error" && <p className="field-error">{state.message}</p>}
      {state.status === "done" && <p className="field-ok">Senha alterada.</p>}
    </form>
  );
}

function DeleteAccount({ token, onDeleted }) {
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState(null);

  async function remove() {
    try {
      await api.del("/me", token);
      onDeleted();
      navigate("/");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="stack">
      <p className="muted">
        Apaga seu e-mail, sua senha e todo o seu histórico. Não dá para desfazer.
      </p>
      {confirming ? (
        <div className="actions">
          <button type="button" className="button danger" onClick={remove}>
            Sim, excluir minha conta
          </button>
          <button type="button" className="button ghost" onClick={() => setConfirming(false)}>
            Cancelar
          </button>
        </div>
      ) : (
        <div className="actions">
          <button type="button" className="button danger-ghost" onClick={() => setConfirming(true)}>
            Excluir conta
          </button>
        </div>
      )}
      {error && <p className="field-error">{error}</p>}
    </div>
  );
}
