import { useState } from "react";
import Notice from "../components/Notice.jsx";
import { useAuth } from "../lib/auth-context.js";
import { parseReportCode, SAMPLE_LINK } from "../lib/links.js";
import { href, navigate } from "../lib/router.js";

// Tela 1: início. O link é validado antes de enviar (RF03, heurística "prevenção de erros").
export default function Home() {
  const { token } = useAuth();
  const [link, setLink] = useState("");
  const [error, setError] = useState(null);

  function submit(event) {
    event.preventDefault();
    const code = parseReportCode(link);
    if (!code) {
      setError(
        link.trim()
          ? "Esse link não parece ser do Warcraft Logs. Ele deve começar com warcraftlogs.com/reports/"
          : "Cole o link do seu log do Warcraft Logs.",
      );
      return;
    }
    navigate(`/relatorio/${code}`);
  }

  return (
    <div className="home">
      <section className="hero">
        <p className="eyebrow">Coach de logs para Mago Arcano</p>
        <h1>Descubra os erros que mais custam seu dano</h1>
        <p className="lead">
          Cole o link do seu log. O LogCoach compara sua luta com os 10 melhores do seu item level e
          explica, em português, o que mudar.
        </p>

        <form className="link-form" onSubmit={submit} noValidate>
          <label htmlFor="link">Link do relatório no Warcraft Logs</label>
          <div className="link-row">
            <input
              id="link"
              type="url"
              inputMode="url"
              placeholder="https://www.warcraftlogs.com/reports/..."
              value={link}
              onChange={(event) => {
                setLink(event.target.value);
                setError(null);
              }}
              aria-invalid={error ? "true" : "false"}
              aria-describedby={error ? "link-error" : "link-hint"}
              autoComplete="off"
            />
            <button type="submit" className="button primary">
              Analisar
            </button>
          </div>
          {error ? (
            <p id="link-error" className="field-error">
              {error}
            </p>
          ) : (
            <p id="link-hint" className="field-hint">
              Não tem um log à mão?{" "}
              <button
                type="button"
                className="link-button"
                onClick={() => {
                  setLink(SAMPLE_LINK);
                  setError(null);
                }}
              >
                Usar o log de exemplo
              </button>
            </p>
          )}
        </form>

        {!token && (
          <div className="hero-actions">
            <span>Você pode fazer 1 análise sem conta.</span>
            <a className="button ghost" href={href("/entrar?modo=cadastro")}>
              Criar conta grátis
            </a>
          </div>
        )}
      </section>

      <section className="how" aria-labelledby="how-title">
        <h2 id="how-title">Como funciona</h2>
        <ol className="how-list">
          <li>
            <strong>Cole o link</strong>
            <span>Do relatório público no Warcraft Logs.</span>
          </li>
          <li>
            <strong>Escolha a luta</strong>
            <span>E o seu Mago Arcano naquela tentativa.</span>
          </li>
          <li>
            <strong>Leia o coach</strong>
            <span>Os erros do maior para o menor impacto, com o que fazer.</span>
          </li>
        </ol>
      </section>

      <Notice title="O que já é suportado">
        Mago Arcano · Nek&apos;zali, a Enrosca-almas (The Venomous Abyss) · Heroico e Mítico. Outros
        chefes aparecem na lista, mas ainda não podem ser analisados.
      </Notice>
    </div>
  );
}
