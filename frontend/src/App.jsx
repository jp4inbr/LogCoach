import AuthProvider from "./components/AuthProvider.jsx";
import Backdrop from "./components/Backdrop.jsx";
import Icon from "./components/Icon.jsx";
import Splash from "./components/Splash.jsx";
import ThemeToggle from "./components/ThemeToggle.jsx";
import { useAuth } from "./lib/auth-context.js";
import { href, navigate, useRoute } from "./lib/router.js";
import ChooseFight from "./pages/ChooseFight.jsx";
import Home from "./pages/Home.jsx";
import Login from "./pages/Login.jsx";
import Plans from "./pages/Plans.jsx";
import Profile from "./pages/Profile.jsx";
import Result from "./pages/Result.jsx";

export default function App() {
  return (
    <AuthProvider>
      {/* Fora do Layout: toca uma vez por carregamento, sem depender da rota. */}
      <Splash />
      <Layout />
    </AuthProvider>
  );
}

function Layout() {
  const route = useRoute();
  const { token, email, logout } = useAuth();
  const [section] = route.parts;

  return (
    <div className="app">
      <Backdrop mode={!section || section === "entrar" ? "pleno" : "fundo"} />
      <a className="skip" href="#conteudo">
        Pular para o conteúdo
      </a>
      <header className="topbar">
        <a className="brand" href={href("/")} aria-label="LogCoach, página inicial">
          <span className="brand-mark" aria-hidden="true">
            {/* Marca "Pulso": o traço de um gráfico de desempenho subindo. */}
            <svg viewBox="0 0 64 64" focusable="false">
              <path d="M11 44 H19 L25 30 L32 46 L39 26 L45 34 L52 16" />
            </svg>
          </span>
          {/* Num span só: o gap do .brand separaria "Log" de "Coach". */}
          <span>
            Log<span className="brand-accent">Coach</span>
          </span>
        </a>
        <p className="topbar-context">Coach de logs para Mago Arcano</p>
        <nav aria-label="Principal">
          <a href={href("/")} aria-current={!section ? "page" : undefined}>
            Analisar
          </a>
          <a href={href("/planos")} aria-current={section === "planos" ? "page" : undefined}>
            Planos
          </a>
          <ThemeToggle />
          {token ? (
            <>
              <a
                href={href("/perfil")}
                aria-current={section === "perfil" ? "page" : undefined}
                title={email ?? undefined}
              >
                Perfil
              </a>
              <button
                type="button"
                className="link-button"
                onClick={() => {
                  logout();
                  navigate("/");
                }}
              >
                Sair
              </button>
            </>
          ) : (
            <a className="button small" href={href("/entrar?modo=login")}>
              Entrar
            </a>
          )}
        </nav>
      </header>

      <main id="conteudo" className="content">
        {/* key: cada endereço monta a tela do zero, sem herdar dados da anterior. */}
        <Page key={`${route.path}?${route.params}`} route={route} />
      </main>

      <footer className="footer">
        <p>LogCoach · Trabalho A3 de Usabilidade de Software · UNA · Dados do Warcraft Logs</p>
        <p>
          Cenários de Silvermoon e Suramar, de World of Warcraft © Blizzard Entertainment. Projeto
          acadêmico, sem fins comerciais.
        </p>
      </footer>
    </div>
  );
}

function Page({ route }) {
  const [section, id] = route.parts;
  switch (section) {
    case undefined:
      return <Home />;
    case "entrar":
      return (
        <Login
          mode={route.params.get("modo") === "cadastro" ? "cadastro" : "login"}
          next={route.params.get("depois")}
        />
      );
    case "relatorio":
      // key: relatório novo monta a tela do zero (pré-buscas, Magos por luta, buscas em
      // andamento e timers não passam de um relatório para outro), mesmo se o key de Page mudar.
      return <ChooseFight key={id} code={id} />;
    case "analise":
      return <Result id={id} />;
    case "perfil":
      return <Profile />;
    case "planos":
      return <Plans />;
    default:
      return (
        <div className="stack">
          <h1>Página não encontrada</h1>
          <a className="button ghost" href={href("/")}>
            <Icon name="arrow-left" /> Voltar ao início
          </a>
        </div>
      );
  }
}
