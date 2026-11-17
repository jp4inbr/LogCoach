import { useAuth } from "../lib/auth-context.js";
import { href } from "../lib/router.js";
import PageBand from "../components/PageBand.jsx";

// Tela extra: planos (RF15). Sem pagamento real no MVP.
export default function Plans() {
  const { token } = useAuth();
  return (
    <div className="stack">
      <PageBand eyebrow="Planos" title="Escolha como quer evoluir" />
      <div className="plans">
        <section className="card plan">
          <h2>Grátis</h2>
          <p className="plan-price">R$ 0</p>
          <ul>
            <li>5 análises por mês</li>
            <li>Histórico das suas análises</li>
            <li>Gráfico de evolução por chefe</li>
          </ul>
          {token ? (
            <span className="pill">Seu plano atual</span>
          ) : (
            <a className="button primary block" href={href("/entrar?modo=cadastro")}>
              Criar conta grátis
            </a>
          )}
        </section>
        <section className="card plan plan-pro">
          <h2>Pro</h2>
          <p className="plan-price">Em breve</p>
          <ul>
            <li>Análises ilimitadas</li>
            <li>Pergunte ao coach sobre cada erro</li>
            <li>Comparação entre duas análises suas</li>
          </ul>
          <button type="button" className="button ghost block" disabled>
            Disponível depois da versão beta
          </button>
        </section>
      </div>
    </div>
  );
}
