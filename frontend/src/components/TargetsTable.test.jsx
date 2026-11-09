import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axeViolations } from "../test/axe.js";
import { targets } from "../test/fixtures/components.js";
import TargetsTable from "./TargetsTable.jsx";

describe("TargetsTable", () => {
  it.each([[null], [undefined], [[]]])("não mostra nada com %j", (value) => {
    const { container } = render(<TargetsTable targets={value} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("mostra uma tabela por fase, com a fase como legenda", () => {
    render(<TargetsTable targets={targets} />);
    expect(screen.getByRole("heading", { level: 2, name: /Dano por alvo/ })).toBeInTheDocument();
    expect(screen.getAllByRole("table")).toHaveLength(3);
    expect(screen.getByRole("table", { name: "Fase 1" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Intermissão" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Fase 2" })).toBeInTheDocument();
  });

  it("mostra a % do jogador e dos tops com vírgula decimal", () => {
    render(<TargetsTable targets={targets} />);
    const phase1 = screen.getByRole("table", { name: "Fase 1" });
    expect(
      within(phase1).getByRole("row", { name: /Nek'zali, a Enrosca-almas/ }),
    ).toHaveTextContent("81,7 / 81,9");
    expect(within(phase1).getByRole("row", { name: /Eco de Jawae/ })).toHaveTextContent(
      "1,5 / 2,4",
    );
  });

  it("destaca o chefe com o selo ‘Chefe’ e não os adds", () => {
    render(<TargetsTable targets={targets} />);
    const phase1 = screen.getByRole("table", { name: "Fase 1" });
    const boss = within(phase1).getByRole("row", { name: /Nek'zali/ });
    expect(boss).toHaveClass("target-boss");
    expect(within(boss).getByText("Chefe")).toBeInTheDocument();
    const add = within(phase1).getByRole("row", { name: /Amani Indócil/ });
    expect(add).not.toHaveClass("target-boss");
    expect(within(add).queryByText("Chefe")).not.toBeInTheDocument();
  });

  it("na intermissão não há chefe nem selo", () => {
    render(<TargetsTable targets={targets} />);
    const inter = screen.getByRole("table", { name: "Intermissão" });
    expect(within(inter).queryByText("Chefe")).not.toBeInTheDocument();
  });

  it("mostra traço quando falta um percentual", () => {
    render(
      <TargetsTable
        targets={[
          {
            phase: "Fase 1",
            rows: [{ name: "Alvo", boss: false, player_pct: 12.5, top_pct: null }],
          },
        ]}
      />,
    );
    expect(screen.getByRole("cell")).toHaveTextContent("12,5 / —");
  });

  it("a dica ‘o que é?’ explica que bater em add não é erro", () => {
    render(<TargetsTable targets={targets} />);
    expect(screen.getByText("(o que é?)")).toHaveAttribute(
      "data-tip",
      expect.stringContaining("Bater nos adds não é erro"),
    );
  });

  it("não tem violações de acessibilidade", async () => {
    const { container } = render(<TargetsTable targets={targets} />);
    expect(await axeViolations(container)).toEqual([]);
  });
});
