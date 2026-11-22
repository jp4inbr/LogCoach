import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axeViolations } from "../test/axe.js";
import StatusBadge from "./StatusBadge.jsx";

describe("StatusBadge", () => {
  it.each([
    ["ok", "OK", "check"],
    ["atencao", "Atenção", "alert"],
    ["erro", "Erro", "x"],
  ])("status %s mostra o texto %s e esconde o ícone do leitor de tela", (status, label, icon) => {
    const { container } = render(<StatusBadge status={status} />);
    const badge = screen.getByText(label, { exact: false });
    expect(badge).toHaveClass(`badge-${status}`);
    const iconEl = container.querySelector("[aria-hidden='true']");
    expect(iconEl).toHaveAttribute("data-icon", icon);
    expect(badge).toContainElement(iconEl);
    // O nome acessível é só o texto: o ícone é um desenho sem texto.
    expect(badge.textContent.trim()).toBe(label);
  });

  it("não tem violações de acessibilidade", async () => {
    const { container } = render(
      <>
        <StatusBadge status="ok" />
        <StatusBadge status="atencao" />
        <StatusBadge status="erro" />
      </>,
    );
    expect(await axeViolations(container)).toEqual([]);
  });
});
