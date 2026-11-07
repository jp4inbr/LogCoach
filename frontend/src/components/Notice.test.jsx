import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axeViolations } from "../test/axe.js";
import Notice from "./Notice.jsx";

describe("Notice", () => {
  it("avisos de erro usam role alert", () => {
    render(
      <Notice tone="erro" title="Não deu certo">
        Tente de novo.
      </Notice>,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Não deu certo");
    expect(alert).toHaveTextContent("Tente de novo.");
    expect(alert).toHaveClass("notice-erro");
  });

  it.each(["info", "atencao"])("tom %s usa role status", (tone) => {
    render(<Notice tone={tone} title="Aviso" />);
    expect(screen.getByRole("status")).toHaveClass(`notice-${tone}`);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("o tom padrão é info", () => {
    render(<Notice title="Oi" />);
    expect(screen.getByRole("status")).toHaveClass("notice-info");
  });

  it("sem título nem corpo só mostra a ação", () => {
    const { container } = render(<Notice action={<button>Tentar de novo</button>} />);
    expect(container.querySelector("strong")).toBeNull();
    expect(container.querySelector(".notice-body")).toBeNull();
    expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeInTheDocument();
  });

  it("não tem violações de acessibilidade", async () => {
    const { container } = render(
      <Notice tone="atencao" title="Dados de exemplo" action={<button>Entendi</button>}>
        Estes números são ilustrativos.
      </Notice>,
    );
    expect(await axeViolations(container)).toEqual([]);
  });
});
