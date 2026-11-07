import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axeViolations } from "../test/axe.js";
import StatusBadge from "./StatusBadge.jsx";

describe("StatusBadge", () => {
  it.each([
    ["ok", "OK", "✓"],
    ["atencao", "Atenção", "!"],
    ["erro", "Erro", "✕"],
  ])("status %s mostra o texto %s e esconde o ícone do leitor de tela", (status, label, icon) => {
    const { container } = render(<StatusBadge status={status} />);
    const badge = screen.getByText(label, { exact: false });
    expect(badge).toHaveClass(`badge-${status}`);
    const iconEl = container.querySelector("[aria-hidden='true']");
    expect(iconEl).toHaveTextContent(icon);
    // O nome acessível é só o texto, sem o símbolo.
    expect(badge.textContent.replace(icon, "").trim()).toBe(label);
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
