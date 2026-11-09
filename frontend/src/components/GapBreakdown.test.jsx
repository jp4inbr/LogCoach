import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axeViolations } from "../test/axe.js";
import { gap } from "../test/fixtures/components.js";
import GapBreakdown from "./GapBreakdown.jsx";

function row(label) {
  return screen.getByText(label).closest("li");
}

describe("GapBreakdown", () => {
  it("não mostra nada sem a diferença (gap nulo)", () => {
    const { container } = render(<GapBreakdown gap={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("com o kill de referência: 18% = 6,6% de erros + 9,5% de sorte + 1,9% não explicado", () => {
    render(<GapBreakdown gap={gap} />);
    const region = screen.getByRole("region", { name: "De onde vem a diferença para os tops" });
    expect(region).toHaveTextContent("Os tops fizeram 18% mais dano que você.");
    expect(within(row("Erros")).getByText("6,6%")).toBeInTheDocument();
    expect(within(row("Azar com a Seta Prismática")).getByText("9,5%")).toBeInTheDocument();
    expect(within(row("Não explicado")).getByText("1,9%")).toBeInTheDocument();
    expect(screen.getByText("Em % do seu próprio dano na luta.")).toBeInTheDocument();
  });

  it("a barra reparte a largura em proporção às partes positivas", () => {
    const { container } = render(
      <GapBreakdown gap={{ total_pct: 10, mistakes_pct: 5, luck_pct: 3, unexplained_pct: 2 }} />,
    );
    const widths = [...container.querySelectorAll(".gap-bar span")].map((s) => s.style.width);
    expect(widths).toEqual(["50%", "30%", "20%"]);
  });

  it("partes negativas ficam fora da barra e aparecem como a seu favor, com sinal de menos", () => {
    const { container } = render(
      <GapBreakdown
        gap={{ total_pct: 4, mistakes_pct: 6, luck_pct: -2.5, unexplained_pct: 0.5 }}
      />,
    );
    const widths = [...container.querySelectorAll(".gap-bar span")].map((s) => s.style.width);
    // Só erros (6) e não explicado (0,5) entram: 6/6,5 e 0,5/6,5.
    expect(widths).toHaveLength(2);
    expect(parseFloat(widths[0])).toBeCloseTo(92.31, 1);
    expect(parseFloat(widths[1])).toBeCloseTo(7.69, 1);

    const luck = row("Sorte com a Seta Prismática (a seu favor)");
    expect(within(luck).getByText("−2,5%")).toHaveClass("text-up");
    expect(screen.queryByText("Azar com a Seta Prismática")).not.toBeInTheDocument();
  });

  it("não aparece ‘Erros’ com o rótulo errado quando o valor é favorável", () => {
    render(
      <GapBreakdown gap={{ total_pct: -1, mistakes_pct: 0, luck_pct: 1, unexplained_pct: -3 }} />,
    );
    expect(screen.getByText("Não explicado (a seu favor)")).toBeInTheDocument();
    expect(screen.getByText("Erros")).toBeInTheDocument();
  });

  it("quando o jogador fez mais dano que os tops, a frase inverte", () => {
    render(
      <GapBreakdown
        gap={{ total_pct: -3.2, mistakes_pct: 1, luck_pct: -4.2, unexplained_pct: 0 }}
      />,
    );
    const headline = screen.getByText(/Você fez/).closest("p");
    expect(headline).toHaveTextContent("Você fez 3,2% mais dano que a média dos tops.");
    expect(headline).toHaveClass("text-up");
    expect(screen.queryByText(/Os tops fizeram/)).not.toBeInTheDocument();
  });

  it("a frase de diferença positiva usa a cor de perda", () => {
    render(<GapBreakdown gap={gap} />);
    expect(screen.getByText(/Os tops fizeram/).closest("p")).toHaveClass("text-down");
  });

  it("sem nenhuma parte positiva não desenha a barra", () => {
    const { container } = render(
      <GapBreakdown gap={{ total_pct: -2, mistakes_pct: 0, luck_pct: -1, unexplained_pct: -1 }} />,
    );
    expect(container.querySelector(".gap-bar")).toBeNull();
  });

  it("cada parte tem uma dica acessível pelo termo", () => {
    render(<GapBreakdown gap={gap} />);
    expect(screen.getByText("Erros")).toHaveAttribute(
      "aria-label",
      expect.stringContaining("Soma do custo de cada erro"),
    );
  });

  it("não tem violações de acessibilidade", async () => {
    const { container } = render(<GapBreakdown gap={gap} />);
    expect(await axeViolations(container)).toEqual([]);
  });
});
