import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { axeViolations } from "../test/axe.js";
import Term from "./Term.jsx";

describe("Term", () => {
  const tip = "Proc aleatório de Seta Prismática.";

  it("mostra o termo, guarda a dica e a lê no nome acessível", () => {
    render(<Term tip={tip}>Seta Prismática</Term>);
    const term = screen.getByText("Seta Prismática");
    expect(term).toHaveAttribute("data-tip", tip);
    expect(term).toHaveAttribute("aria-label", `Seta Prismática: ${tip}`);
  });

  it("é alcançável pelo teclado", async () => {
    render(<Term tip={tip}>Seta Prismática</Term>);
    await userEvent.tab();
    expect(screen.getByText("Seta Prismática")).toHaveFocus();
  });

  it("não tem violações de acessibilidade", async () => {
    const { container } = render(
      <p>
        Veja a <Term tip={tip}>Seta Prismática</Term> no relatório.
      </p>,
    );
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("tipShift", () => {
  it("não desloca quando a dica cabe à direita do termo", async () => {
    const { tipShift } = await import("../lib/tip.js");
    expect(tipShift(16, 390)).toBe(0);
  });

  it("desloca para a esquerda perto da borda direita, sem sair pela esquerda", async () => {
    const { tipShift } = await import("../lib/tip.js");
    // 390 px: dica de 280 px; termo em 243 iria até 523.
    const shift = tipShift(243, 390);
    expect(243 + shift).toBeGreaterThanOrEqual(12);
    expect(243 + shift + 280).toBeLessThanOrEqual(390 - 12);
  });

  it("em tela estreita, a dica fica entre as duas margens", async () => {
    const { tipShift } = await import("../lib/tip.js");
    // 320 px: dica de 256 px (80vw); termo quase na borda direita.
    const left = 300 + tipShift(300, 320);
    expect(left).toBeGreaterThanOrEqual(12);
    expect(left + 256).toBeLessThanOrEqual(320 - 12);
  });
});
