import AuthProvider from "./components/AuthProvider.jsx";
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
      <a className="skip" href="#conteudo">
        Pular para o conteúdo
      </a>
      <header className="topbar">
        <a className="brand" href={href("/")} aria-label="LogCoach, página inicial">
          <span className="brand-mark" aria-hidden="true">
            ✦
          </span>
          LogCoach
        </a>
        <nav aria-label="Principal">
          <a href={href("/")} aria-current={!section ? "page" : undefined}>
            Analisar
          </a>
          <a href={href("/planos")} aria-current={section === "planos" ? "page" : undefined}>
            Planos
          </a>
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
        LogCoach · Trabalho A3 de Usabilidade de Software · UNA · Dados do Warcraft Logs
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
      return <ChooseFight code={id} />;
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
            ← Voltar ao início
          </a>
        </div>
      );
  }
}
