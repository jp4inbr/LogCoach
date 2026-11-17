import { useRef, useState } from "react";
import Backdrop from "../components/Backdrop.jsx";
import Notice from "../components/Notice.jsx";
import { useAuth } from "../lib/auth-context.js";
import { parseReportCode, SAMPLE_LINK } from "../lib/links.js";
import { href, navigate } from "../lib/router.js";

// Ícones (SVG inline, traço na cor do texto). Sempre decorativos: o texto ao lado diz tudo.
function Icon({ children, size = 18 }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  );
}

const SEALS = [
  {
    text: "Top 10 do seu item level",
    // Pódio: três degraus.
    icon: <path d="M4 20v-6h5v6M9 20V8h6v12M15 20v-9h5v9M3 20h18M12 3v2" />,
  },
  {
    text: "Explicado em português",
    // Balão de fala com duas linhas.
    icon: <path d="M4 5h16v11H9l-5 4zM8 9h8M8 12h5" />,
  },
  {
    text: "Dados do Warcraft Logs",
    // Gráfico de linha.
    icon: <path d="M4 4v16h16M7 15l4-4 3 3 5-6" />,
  },
];

// Tela 1: início. O link é validado antes de enviar (RF03, heurística "prevenção de erros").
// O hero segue a linguagem de um painel escuro com a marca gravada em perspectiva ao fundo
// (o cenário de todas as telas, Backdrop) e a barra do link no rodapé, em formato de prompt.
export default function Home() {
  const { token } = useAuth();
  const [link, setLink] = useState("");
  const [error, setError] = useState(null);
  const input = useRef(null);

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
      <section className="hero" aria-labelledby="hero-title">
        <Backdrop />

        <div className="hero-inner">
          <div className="hero-copy">
            <p className="eyebrow">Coach de logs para Mago Arcano</p>
            <div className="hero-title">
              <h1 id="hero-title">Descubra os erros que mais custam seu dano</h1>
              <p className="hero-title-muted">Compare com os 10 melhores do seu item level.</p>
            </div>
            <p className="hero-lead">
              Cole o link de uma luta sua no Warcraft Logs. <br />O LogCoach explica, em português,
              o que mudar.
            </p>
            <ul className="hero-seals" aria-label="Destaques">
              {SEALS.map((seal) => (
                <li key={seal.text}>
                  <Icon>{seal.icon}</Icon>
                  {seal.text}
                </li>
              ))}
            </ul>
          </div>

          <div className="hero-foot">
            {!token && (
              <div className="hero-cta">
                <a className="button primary small" href={href("/entrar?modo=cadastro")}>
                  <Icon size={16}>
                    <circle cx="12" cy="8" r="4" />
                    <path d="M4 20c1.5-4 4.5-6 8-6s6.5 2 8 6" />
                  </Icon>
                  Criar conta grátis
                </a>
                <span>Você pode fazer 1 análise sem conta.</span>
              </div>
            )}

            <form
              className="prompt"
              role="search"
              aria-label="Analisar um log"
              onSubmit={submit}
              noValidate
            >
              <label htmlFor="link" className="prompt-label">
                Link do relatório no Warcraft Logs
              </label>
              <div className="prompt-bar">
                <button
                  type="button"
                  className="prompt-icon"
                  title="Usar o log de exemplo"
                  onClick={() => {
                    setLink(SAMPLE_LINK);
                    setError(null);
                    input.current?.focus();
                  }}
                >
                  <Icon>
                    <path d="M12 5v14M5 12h14" />
                  </Icon>
                  <span className="sr-only">Usar o log de exemplo</span>
                </button>
                <input
                  ref={input}
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
                <button type="submit" className="prompt-send">
                  <Icon>
                    <path d="M12 19V5M6 11l6-6 6 6" />
                  </Icon>
                  <span className="prompt-send-text">Analisar</span>
                </button>
              </div>
              {error ? (
                <p id="link-error" className="field-error">
                  {error}
                </p>
              ) : (
                <p id="link-hint" className="field-hint">
                  Não tem um log à mão? Use o + para carregar o log de exemplo.
                </p>
              )}
            </form>
          </div>
        </div>
      </section>

      <div className="home-below">
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
          Mago Arcano · Nek&apos;zali, a Enrosca-almas (The Venomous Abyss) · Mítico. Outros chefes
          aparecem na lista, mas ainda não podem ser analisados.
        </Notice>
      </div>
    </div>
  );
}
