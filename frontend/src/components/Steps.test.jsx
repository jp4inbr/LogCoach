import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axeViolations } from "../test/axe.js";
import Steps from "./Steps.jsx";

function items() {
  return within(screen.getByRole("list", { name: "Andamento da análise" })).getAllByRole(
    "listitem",
  );
}

describe("Steps", () => {
  it("lista as três etapas na ordem", () => {
    render(<Steps current={0} />);
    expect(items().map((li) => li.textContent.replace(/^[✓\d]/, ""))).toEqual([
      "Buscando sua luta",
      "Comparando com os melhores",
      "Coach analisando",
    ]);
  });

  it("na etapa 1 só a primeira está ativa; as outras esperam", () => {
    render(<Steps current={0} />);
    const [a, b, c] = items();
    expect(a).toHaveClass("step-active");
    expect(a).toHaveAttribute("aria-current", "true");
    expect(a).toHaveTextContent("1");
    expect(b).toHaveClass("step-todo");
    expect(b).toHaveAttribute("aria-current", "false");
    expect(c).toHaveClass("step-todo");
  });

  it("as etapas anteriores à atual aparecem concluídas com ✓", () => {
    render(<Steps current={2} />);
    const [a, b, c] = items();
    expect(a).toHaveClass("step-done");
    expect(a).toHaveTextContent("✓");
    expect(b).toHaveClass("step-done");
    expect(c).toHaveClass("step-active");
    expect(c).toHaveTextContent("3");
  });

  it("depois da última etapa, todas aparecem concluídas", () => {
    render(<Steps current={3} />);
    items().forEach((li) => expect(li).toHaveClass("step-done"));
  });

  it("não tem violações de acessibilidade", async () => {
    const { container } = render(<Steps current={1} />);
    expect(await axeViolations(container)).toEqual([]);
  });
});
