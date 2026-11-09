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
