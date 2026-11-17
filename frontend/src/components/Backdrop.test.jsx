import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../App.jsx";
import { axeViolations } from "../test/axe.js";
import { mockApi } from "../test/mockApi.js";
import Backdrop from "./Backdrop.jsx";

describe("Backdrop (cenário de fundo de todas as telas)", () => {
  it("é decorativo: escondido do leitor de tela, com a marca gravada", () => {
    const { container } = render(<Backdrop />);
    const cenario = container.querySelector('[data-testid="cenario"]');
    expect(cenario).not.toBeNull();
    expect(cenario).toHaveAttribute("aria-hidden", "true");
    expect(cenario).toHaveClass("backdrop");
    expect(cenario.textContent).toContain("LogCoach");
    expect(cenario.querySelectorAll("a, button, input, [tabindex]")).toHaveLength(0);
  });

  it("não tem violações de acessibilidade", async () => {
    const { container } = render(<Backdrop />);
    expect(await axeViolations(container)).toEqual([]);
  });

  it.each(["", "#/planos", "#/entrar?modo=login", "#/relatorio/XhrmBaYkGCAQjH2D"])(
    "no app, a rota '%s' tem exatamente um cenário",
    (hash) => {
      mockApi();
      window.location.hash = hash;
      const { container } = render(<App />);
      expect(container.querySelectorAll('[data-testid="cenario"]')).toHaveLength(1);
    },
  );
});
