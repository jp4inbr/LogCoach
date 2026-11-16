import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import AuthProvider from "../components/AuthProvider.jsx";
import { SAMPLE_LINK } from "../lib/links.js";
import { axeViolations } from "../test/axe.js";
import { apiError, lerSessao, mockApi, setSession } from "../test/mockApi.js";
import Home from "./Home.jsx";

function renderHome() {
  return render(
    <AuthProvider>
      <Home />
    </AuthProvider>,
  );
}

const campo = () => screen.getByLabelText("Link do relatório no Warcraft Logs");

describe("Home", () => {
  it("mostra a proposta, o passo a passo e o que já é suportado", () => {
    mockApi();
    renderHome();

    expect(
      screen.getByRole("heading", { level: 1, name: "Descubra os erros que mais custam seu dano" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Como funciona" })).toBeInTheDocument();
    const como = screen.getByRole("region", { name: "Como funciona" });
    const passos = within(como)
      .getAllByRole("listitem")
      .map((item) => item.textContent);
    expect(passos).toEqual([
      "Cole o linkDo relatório público no Warcraft Logs.",
      "Escolha a lutaE o seu Mago Arcano naquela tentativa.",
      "Leia o coachOs erros do maior para o menor impacto, com o que fazer.",
    ]);
    expect(screen.getByText("O que já é suportado")).toBeInTheDocument();
    expect(screen.getByText(/· Mítico\. Outros chefes aparecem na lista/)).toBeInTheDocument();
  });

  it("título em duas linhas: o h1 não muda e a segunda linha (atenuada) fica fora dele", () => {
    mockApi();
    renderHome();

    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1).toHaveAccessibleName("Descubra os erros que mais custam seu dano");
    const segunda = screen.getByText("Compare com os 10 melhores do seu item level.");
    expect(h1).not.toContainElement(segunda);
    expect(segunda).toHaveClass("hero-title-muted");
    // A segunda linha vem logo depois do h1, no mesmo bloco do título.
    expect(h1.nextElementSibling).toBe(segunda);
  });

  it("mostra os três selos, cada um com ícone decorativo", () => {
    mockApi();
    renderHome();

    const selos = within(screen.getByRole("list", { name: "Destaques" })).getAllByRole("listitem");
    expect(selos.map((selo) => selo.textContent)).toEqual([
      "Top 10 do seu item level",
      "Explicado em português",
      "Dados do Warcraft Logs",
    ]);
    for (const selo of selos) {
      const icone = selo.querySelector("svg");
      expect(icone).not.toBeNull();
      expect(icone).toHaveAttribute("aria-hidden", "true");
    }
  });

  it("barra estilo prompt: '+' (exemplo), campo rotulado e 'Analisar', nessa ordem", () => {
    mockApi();
    renderHome();

    const barra = screen.getByRole("search", { name: "Analisar um log" });
    expect(within(barra).getByRole("button", { name: "Usar o log de exemplo" })).toBeVisible();
    expect(within(barra).getByLabelText("Link do relatório no Warcraft Logs")).toBe(campo());
    expect(within(barra).getByRole("button", { name: "Analisar" })).toHaveAttribute(
      "type",
      "submit",
    );
    const ordem = [
      within(barra).getByRole("button", { name: "Usar o log de exemplo" }),
      campo(),
      within(barra).getByRole("button", { name: "Analisar" }),
    ];
    const todos = within(barra).getAllByRole(/button|textbox/);
    expect(todos).toEqual(ordem);
    // Sem erro, o campo é descrito pela dica, que explica o "+".
    expect(campo()).toHaveAccessibleDescription(/\+.*log de exemplo/);
  });

  it("o '+' preenche o link de exemplo e 'Analisar' abre o relatório de referência", async () => {
    mockApi();
    const user = userEvent.setup();
    renderHome();

    await user.click(screen.getByRole("button", { name: "Usar o log de exemplo" }));
    expect(campo()).toHaveValue(SAMPLE_LINK);
    expect(campo()).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Analisar" }));
    expect(window.location.hash).toBe("#/relatorio/XhrmBaYkGCAQjH2D");
  });

  it("o enfeite do fundo (a marca gravada) e os ícones ficam fora da leitura", () => {
    mockApi();
    const { container } = renderHome();

    const arte = container.querySelector(".hero-art");
    expect(arte).not.toBeNull();
    expect(arte).toHaveAttribute("aria-hidden", "true");
    expect(arte.textContent).toContain("LogCoach");
    for (const svg of container.querySelectorAll("svg")) {
      expect(svg.closest('[aria-hidden="true"]')).not.toBeNull();
    }
  });

  it("sem login, o convite fica no rodapé do hero, junto da barra do link", () => {
    mockApi();
    renderHome();

    const rodape = screen.getByRole("link", { name: "Criar conta grátis" }).closest(".hero-foot");
    expect(rodape).not.toBeNull();
    expect(within(rodape).getByText("Você pode fazer 1 análise sem conta.")).toBeInTheDocument();
    expect(within(rodape).getByRole("search", { name: "Analisar um log" })).toBeInTheDocument();
  });

  it("sem login avisa da análise grátis e leva ao cadastro", () => {
    mockApi();
    renderHome();

    expect(screen.getByText("Você pode fazer 1 análise sem conta.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Criar conta grátis" })).toHaveAttribute(
      "href",
      "#/entrar?modo=cadastro",
    );
  });

  it("com login não mostra o convite para criar conta", async () => {
    setSession();
    const api = mockApi({ "GET /me": { body: { email: "voce@exemplo.com" } } });
    renderHome();

    await waitFor(() => expect(api.calls("GET /me")).toHaveLength(1));
    expect(api.calls("GET /me")[0].authorization).toBe("Bearer token-de-teste");
    expect(screen.queryByText("Você pode fazer 1 análise sem conta.")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Criar conta grátis" })).not.toBeInTheDocument();
  });

  it("sessão vencida: sai da conta e volta a oferecer a análise sem conta", async () => {
    setSession("token-vencido");
    mockApi({
      "GET /me": apiError(401, "invalid_token", "Sua sessão expirou. Entre de novo."),
    });
    renderHome();

    expect(await screen.findByText("Você pode fazer 1 análise sem conta.")).toBeInTheDocument();
    expect(lerSessao()).toBeNull();
  });

  it("link vazio: avisa no campo e não navega", async () => {
    mockApi();
    const user = userEvent.setup();
    renderHome();

    await user.click(screen.getByRole("button", { name: "Analisar" }));

    expect(screen.getByText("Cole o link do seu log do Warcraft Logs.")).toBeInTheDocument();
    expect(campo()).toHaveAttribute("aria-invalid", "true");
    expect(campo()).toHaveAccessibleDescription("Cole o link do seu log do Warcraft Logs.");
    expect(window.location.hash).toBe("");
  });

  it("link de outro site: explica o formato esperado e não navega", async () => {
    mockApi();
    const user = userEvent.setup();
    renderHome();

    await user.type(campo(), "https://exemplo.com/reports/ABCDEF123456");
    await user.click(screen.getByRole("button", { name: "Analisar" }));

    expect(
      screen.getByText(
        "Esse link não parece ser do Warcraft Logs. Ele deve começar com warcraftlogs.com/reports/",
      ),
    ).toBeInTheDocument();
    expect(campo()).toHaveAttribute("aria-invalid", "true");
    expect(window.location.hash).toBe("");
  });

  it("o aviso some assim que a pessoa volta a digitar", async () => {
    mockApi();
    const user = userEvent.setup();
    renderHome();

    await user.click(screen.getByRole("button", { name: "Analisar" }));
    expect(screen.getByText("Cole o link do seu log do Warcraft Logs.")).toBeInTheDocument();

    await user.type(campo(), "h");

    expect(screen.queryByText("Cole o link do seu log do Warcraft Logs.")).not.toBeInTheDocument();
    expect(campo()).toHaveAttribute("aria-invalid", "false");
  });

  it.each([
    ["com https e www", "https://www.warcraftlogs.com/reports/AbCd1234EfGh"],
    ["sem protocolo", "warcraftlogs.com/reports/AbCd1234EfGh"],
    ["com a luta no fim", "https://www.warcraftlogs.com/reports/AbCd1234EfGh#fight=34"],
    ["com o idioma no subdomínio", "https://pt.warcraftlogs.com/reports/AbCd1234EfGh?fight=3"],
    ["com espaços em volta", "   https://www.warcraftlogs.com/reports/AbCd1234EfGh  "],
  ])("link válido %s: abre a escolha da luta", async (_nome, link) => {
    mockApi();
    const user = userEvent.setup();
    renderHome();

    await user.type(campo(), link);
    await user.click(screen.getByRole("button", { name: "Analisar" }));

    expect(window.location.hash).toBe("#/relatorio/AbCd1234EfGh");
  });

  it("Enter no campo também envia", async () => {
    mockApi();
    const user = userEvent.setup();
    renderHome();

    await user.type(campo(), "https://www.warcraftlogs.com/reports/AbCd1234EfGh{Enter}");

    expect(window.location.hash).toBe("#/relatorio/AbCd1234EfGh");
  });

  it("'Usar o log de exemplo' preenche o campo e leva ao relatório de referência", async () => {
    mockApi();
    const user = userEvent.setup();
    renderHome();

    await user.click(screen.getByRole("button", { name: "Usar o log de exemplo" }));
    expect(campo()).toHaveValue(SAMPLE_LINK);

    await user.click(screen.getByRole("button", { name: "Analisar" }));
    expect(window.location.hash).toBe("#/relatorio/XhrmBaYkGCAQjH2D");
  });

  it("não chama a API ao enviar o link (só a próxima tela fala com o servidor)", async () => {
    const api = mockApi();
    const user = userEvent.setup();
    renderHome();

    await user.type(campo(), "https://www.warcraftlogs.com/reports/AbCd1234EfGh{Enter}");

    expect(api.calls()).toEqual([]);
  });

  it("não tem violações de acessibilidade", async () => {
    mockApi();
    const { container } = renderHome();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("não tem violações de acessibilidade com o erro do campo à mostra", async () => {
    mockApi();
    const user = userEvent.setup();
    const { container } = renderHome();
    await user.click(screen.getByRole("button", { name: "Analisar" }));
    expect(await axeViolations(container)).toEqual([]);
  });
});
