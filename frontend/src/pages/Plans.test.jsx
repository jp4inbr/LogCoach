import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AuthProvider from "../components/AuthProvider.jsx";
import { axeViolations } from "../test/axe.js";
import { mockApi, setSession } from "../test/mockApi.js";
import Plans from "./Plans.jsx";

function renderPlans() {
  return render(
    <AuthProvider>
      <Plans />
    </AuthProvider>,
  );
}

const cartao = (nome) => screen.getByRole("heading", { name: nome }).closest("section");

describe("Plans", () => {
  it("mostra o plano Grátis com o que ele inclui", () => {
    mockApi();
    renderPlans();

    expect(
      screen.getByRole("heading", { level: 1, name: "Escolha como quer evoluir" }),
    ).toBeInTheDocument();
    const gratis = within(cartao("Grátis"));
    expect(gratis.getByText("R$ 0")).toBeInTheDocument();
    expect(gratis.getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "5 análises por mês",
      "Histórico das suas análises",
      "Gráfico de evolução por chefe",
    ]);
  });

  it("o plano Pro aparece como 'Em breve' e o botão não pode ser usado", () => {
    mockApi();
    renderPlans();

    const pro = within(cartao("Pro"));
    expect(pro.getByText("Em breve")).toBeInTheDocument();
    expect(pro.getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "Análises ilimitadas",
      "Pergunte ao coach sobre cada erro",
      "Comparação entre duas análises suas",
    ]);
    expect(pro.getByRole("button", { name: "Disponível depois da versão beta" })).toBeDisabled();
  });

  it("sem login oferece criar a conta grátis", () => {
    mockApi();
    renderPlans();

    const gratis = within(cartao("Grátis"));
    expect(gratis.getByRole("link", { name: "Criar conta grátis" })).toHaveAttribute(
      "href",
      "#/entrar?modo=cadastro",
    );
    expect(gratis.queryByText("Seu plano atual")).not.toBeInTheDocument();
  });

  it("com login marca o Grátis como plano atual e tira o convite", () => {
    setSession();
    mockApi({ "GET /me": { body: {} } });
    renderPlans();

    const gratis = within(cartao("Grátis"));
    expect(gratis.getByText("Seu plano atual")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Criar conta grátis" })).not.toBeInTheDocument();
  });

  it("sem violações de acessibilidade", async () => {
    mockApi();
    const { container } = renderPlans();
    expect(await axeViolations(container)).toEqual([]);
  });
});
