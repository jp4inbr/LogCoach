import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import AuthProvider from "../components/AuthProvider.jsx";
import { axeViolations } from "../test/axe.js";
import { apiError, lerSessao, mockApi, setSession } from "../test/mockApi.js";
import Profile from "./Profile.jsx";

function renderProfile() {
  return render(
    <AuthProvider>
      <Profile />
    </AuthProvider>,
  );
}

const ME = {
  email: "voce@exemplo.com",
  created_at: "2026-10-01T12:00:00Z",
  plan: "gratis",
  analyses_this_month: 3,
  monthly_limit: 5,
};

// Histórico da API (do mais novo para o mais antigo). Só pseudônimo e o jogador de exemplo.
function analise(id, dia, dps, gap, boss = "Nek'zali, a Enrosca-almas") {
  return {
    id,
    created_at: `2026-11-${dia}T15:00:00Z`,
    report_code: "XhrmBaYkGCAQjH2D",
    fight_id: 34,
    player_name: "Harmonist",
    boss,
    difficulty: "Mítico",
    dps,
    dps_gap_pct: gap,
    mistakes_count: 4,
  };
}
const HISTORICO = [
  analise("a3", "06", 240000, -9.5),
  analise("a2", "03", 225680.6, -15.2),
  analise("a1", "01", 1_180_000, 3.1),
];

function logado(rotas = {}) {
  setSession();
  return mockApi({
    "GET /me": { body: ME },
    "GET /me/analyses": { body: HISTORICO },
    ...rotas,
  });
}

async function carregado() {
  return screen.findByRole("heading", { level: 1, name: "Seu perfil" });
}

describe("Profile", () => {
  describe("sem login", () => {
    it("pede para entrar e volta ao perfil depois", async () => {
      mockApi({
        "GET /me": apiError(401, "login_required", "Entre para continuar."),
        "GET /me/analyses": apiError(401, "login_required", "Entre para continuar."),
      });
      renderProfile();

      expect(screen.getByText("Entre para ver seu perfil")).toBeInTheDocument();
      expect(
        screen.getByText("O histórico e a evolução ficam guardados na sua conta."),
      ).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Entrar" })).toHaveAttribute(
        "href",
        "#/entrar?modo=login&depois=/perfil",
      );
    });
  });

  describe("com login", () => {
    it("mostra o carregamento e depois e-mail, plano e uso do mês", async () => {
      const pendentes = [];
      const api = logado({
        "GET /me": () =>
          new Promise((resolve) => {
            pendentes.push(() => resolve({ body: ME }));
          }),
      });
      renderProfile();

      expect(screen.getByText("Carregando seu perfil…")).toBeInTheDocument();
      // O AuthProvider e a tela pedem /me; as duas respostas ficam presas até aqui.
      await waitFor(() => expect(pendentes).toHaveLength(2));
      pendentes.forEach((liberar) => liberar());

      await carregado();
      expect(screen.getByText("Plano grátis")).toBeInTheDocument();
      expect(screen.getByText("voce@exemplo.com")).toBeInTheDocument();
      expect(screen.getByText(/3 de 5 usadas · o limite volta no dia 1º\./)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Ver o plano Pro" })).toHaveAttribute(
        "href",
        "#/planos",
      );
      expect(screen.getByRole("link", { name: "Nova análise" })).toHaveAttribute("href", "#/");
      // Todas as chamadas de dados vão com o token da sessão.
      for (const chamada of [...api.calls("GET /me"), ...api.calls("GET /me/analyses")]) {
        expect(chamada.authorization).toBe("Bearer token-de-teste");
      }
    });

    it("o medidor do plano reflete o uso", async () => {
      logado();
      renderProfile();
      await carregado();

      const medidor = screen.getByRole("meter", { name: "Análises usadas no mês" });
      expect(medidor).toHaveAttribute("aria-valuenow", "3");
      expect(medidor).toHaveAttribute("aria-valuemax", "5");
      expect(medidor.firstChild).toHaveStyle({ width: "60%" });
    });

    it("limite esgotado: o medidor para no máximo e o texto mostra 5 de 5", async () => {
      logado({ "GET /me": { body: { ...ME, analyses_this_month: 7 } } });
      renderProfile();
      await carregado();

      const medidor = screen.getByRole("meter", { name: "Análises usadas no mês" });
      expect(medidor).toHaveAttribute("aria-valuenow", "5");
      expect(medidor.firstChild).toHaveStyle({ width: "100%" });
      expect(screen.getByText(/5 de 5 usadas/)).toBeInTheDocument();
    });

    it("lista o histórico com DPS, diferença para os tops e link para cada análise", async () => {
      logado();
      renderProfile();
      await carregado();

      const itens = within(screen.getByRole("list")).getAllByRole("link");
      expect(itens).toHaveLength(3);
      expect(itens.map((link) => link.getAttribute("href"))).toEqual([
        "#/analise/a3",
        "#/analise/a2",
        "#/analise/a1",
      ]);
      const [maisNova, , maisAntiga] = itens;
      expect(maisNova).toHaveTextContent("Nek'zali, a Enrosca-almas");
      expect(maisNova).toHaveTextContent("Mítico · Harmonist ·");
      expect(maisNova).toHaveTextContent("240 mil");
      expect(maisNova).toHaveTextContent("−9,5% no DPS vs. média dos tops");
      expect(maisNova.querySelector(".text-down")).not.toBeNull();
      // DPS acima de 1 milhão e diferença positiva (a favor do jogador).
      expect(maisAntiga).toHaveTextContent("1,18 mi");
      expect(maisAntiga).toHaveTextContent("+3,1% no DPS vs. média dos tops");
      expect(maisAntiga.querySelector(".text-up")).not.toBeNull();
    });

    it("histórico vazio: explica quando as análises aparecem e não mostra evolução", async () => {
      logado({ "GET /me/analyses": { body: [] } });
      renderProfile();
      await carregado();

      expect(
        screen.getByText("Suas análises aparecem aqui depois da primeira."),
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          "Faça pelo menos duas análises do mesmo chefe para ver a evolução do seu DPS.",
        ),
      ).toBeInTheDocument();
      expect(screen.queryByRole("img")).not.toBeInTheDocument();
    });

    it("evolução: só com duas análises do mesmo chefe, em ordem de data", async () => {
      logado();
      renderProfile();
      await carregado();

      expect(screen.getByText("DPS por análise · Nek'zali, a Enrosca-almas")).toBeInTheDocument();
      const grafico = screen.getByRole("img");
      // Do mais antigo (1,18 mi) para o mais novo (240 mil).
      expect(grafico).toHaveAccessibleName(/^DPS de 1,18 mi em .* para 240 mil em /);
    });

    it("evolução: uma análise de cada chefe não forma gráfico", async () => {
      logado({
        "GET /me/analyses": {
          body: [analise("b2", "05", 200000, -10, "Outro chefe"), HISTORICO[0]],
        },
      });
      renderProfile();
      await carregado();

      expect(screen.queryByRole("img")).not.toBeInTheDocument();
      expect(screen.getByText(/Faça pelo menos duas análises do mesmo chefe/)).toBeInTheDocument();
    });

    it("evolução usa o chefe com mais análises", async () => {
      logado({
        "GET /me/analyses": {
          body: [
            analise("c4", "06", 200000, -10, "Outro chefe"),
            HISTORICO[0],
            analise("c2", "02", 210000, -12, "Outro chefe"),
            analise("c1", "01", 205000, -13, "Outro chefe"),
          ],
        },
      });
      renderProfile();
      await carregado();

      expect(screen.getByText("DPS por análise · Outro chefe")).toBeInTheDocument();
    });

    it("sem violações de acessibilidade", async () => {
      logado();
      const { container } = renderProfile();
      await carregado();
      expect(await axeViolations(container)).toEqual([]);
    });
  });

  describe("erros ao carregar", () => {
    it("token vencido em /me: a sessão cai e a tela pede para entrar", async () => {
      logado({
        "GET /me": apiError(401, "invalid_token", "Sua sessão expirou. Entre de novo."),
      });
      renderProfile();

      expect(await screen.findByText("Entre para ver seu perfil")).toBeInTheDocument();
      expect(lerSessao()).toBeNull();
    });

    it("token vencido só no histórico: avisa e 'Entrar de novo' sai da conta e abre o login", async () => {
      logado({
        "GET /me/analyses": apiError(401, "invalid_token", "Sua sessão expirou. Entre de novo."),
      });
      const user = userEvent.setup();
      renderProfile();

      const aviso = await screen.findByRole("alert");
      expect(aviso).toHaveTextContent("Sua sessão expirou");
      expect(aviso).toHaveTextContent("Sua sessão expirou. Entre de novo.");

      await user.click(screen.getByRole("button", { name: "Entrar de novo" }));

      expect(lerSessao()).toBeNull();
      expect(window.location.hash).toBe("#/entrar?modo=login&depois=/perfil");
    });

    it("erro nosso: mostra a mensagem sem oferecer 'Entrar de novo'", async () => {
      logado({ "GET /me/analyses": { status: 502, body: "<html>Bad Gateway</html>", html: true } });
      renderProfile();

      const aviso = await screen.findByRole("alert");
      expect(aviso).toHaveTextContent("Não deu para abrir seu perfil");
      expect(aviso).toHaveTextContent("Erro inesperado no LogCoach.");
      expect(screen.queryByRole("button", { name: "Entrar de novo" })).not.toBeInTheDocument();
      expect(lerSessao()).not.toBeNull();
    });

    it("servidor fora do ar: mostra a mensagem de rede", async () => {
      logado({ "GET /me/analyses": new TypeError("Failed to fetch") });
      renderProfile();

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "O servidor do LogCoach não respondeu. Confira sua conexão e tente de novo.",
      );
    });
  });

  describe("alterar senha", () => {
    async function abrir() {
      const user = userEvent.setup();
      const api = logado();
      renderProfile();
      await carregado();
      return { user, api };
    }
    const atual = () => screen.getByLabelText("Senha atual");
    const nova = () => screen.getByLabelText("Nova senha");
    const salvar = () => screen.getByRole("button", { name: "Salvar nova senha" });

    it("nova senha curta é recusada sem chamar a API", async () => {
      const { user, api } = await abrir();

      await user.type(atual(), "senha-antiga");
      await user.type(nova(), "1234567");
      await user.click(salvar());

      expect(
        screen.getByText("A nova senha precisa ter pelo menos 8 caracteres."),
      ).toBeInTheDocument();
      expect(api.calls("PUT /me/password")).toEqual([]);
    });

    it("troca a senha, avisa e limpa os campos", async () => {
      const { user, api } = await abrir();
      api.set("PUT /me/password", { status: 204 });

      await user.type(atual(), "senha-antiga");
      await user.type(nova(), "senha-nova-123");
      await user.click(salvar());

      expect(await screen.findByText("Senha alterada.")).toBeInTheDocument();
      const [chamada] = api.calls("PUT /me/password");
      expect(chamada.body).toEqual({
        current_password: "senha-antiga",
        new_password: "senha-nova-123",
      });
      expect(chamada.authorization).toBe("Bearer token-de-teste");
      expect(atual()).toHaveValue("");
      expect(nova()).toHaveValue("");
    });

    it("senha atual errada: mostra a mensagem do servidor e mantém o que foi digitado", async () => {
      const { user, api } = await abrir();
      api.set("PUT /me/password", apiError(400, "wrong_password", "A senha atual não confere."));

      await user.type(atual(), "errada");
      await user.type(nova(), "senha-nova-123");
      await user.click(salvar());

      expect(await screen.findByText("A senha atual não confere.")).toBeInTheDocument();
      expect(screen.queryByText("Senha alterada.")).not.toBeInTheDocument();
      expect(nova()).toHaveValue("senha-nova-123");
    });
  });

  describe("excluir conta", () => {
    async function abrir() {
      const user = userEvent.setup();
      const api = logado();
      renderProfile();
      await carregado();
      return { user, api };
    }

    it("pede confirmação e dá para cancelar sem apagar nada", async () => {
      const { user, api } = await abrir();

      await user.click(screen.getByRole("button", { name: "Excluir conta" }));
      expect(screen.getByRole("button", { name: "Sim, excluir minha conta" })).toBeInTheDocument();
      expect(api.calls("DELETE /me")).toEqual([]);

      await user.click(screen.getByRole("button", { name: "Cancelar" }));

      expect(screen.getByRole("button", { name: "Excluir conta" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Sim, excluir minha conta" })).toBeNull();
      expect(api.calls("DELETE /me")).toEqual([]);
      expect(lerSessao()).not.toBeNull();
    });

    it("confirmando: apaga na API, sai da conta e volta ao início", async () => {
      const { user, api } = await abrir();
      api.set("DELETE /me", { status: 204 });

      await user.click(screen.getByRole("button", { name: "Excluir conta" }));
      await user.click(screen.getByRole("button", { name: "Sim, excluir minha conta" }));

      await waitFor(() => expect(window.location.hash).toBe("#/"));
      expect(api.calls("DELETE /me")[0].authorization).toBe("Bearer token-de-teste");
      expect(lerSessao()).toBeNull();
    });

    it("falha ao excluir: mostra o erro e continua logado", async () => {
      const { user, api } = await abrir();
      api.set("DELETE /me", new TypeError("Failed to fetch"));

      await user.click(screen.getByRole("button", { name: "Excluir conta" }));
      await user.click(screen.getByRole("button", { name: "Sim, excluir minha conta" }));

      expect(await screen.findByText(/O servidor do LogCoach não respondeu/)).toBeInTheDocument();
      expect(lerSessao()).not.toBeNull();
      expect(window.location.hash).toBe("");
    });
  });
});
