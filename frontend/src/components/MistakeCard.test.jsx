import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { axeViolations } from "../test/axe.js";
import { byMarkedText } from "../test/plainText.js";
import { mistakes } from "../test/fixtures/components.js";
import MistakeCard from "./MistakeCard.jsx";

const soulEntry = mistakes.find((m) => m.id === "soul_entry");
const hypothesis = mistakes.find((m) => m.kind === "hipotese");
const noCost = mistakes.find((m) => m.impact_pct === null);

describe("MistakeCard", () => {
  it("mostra um erro de regra com custo, explicação, o que fazer e a tabela de números", () => {
    render(<MistakeCard mistake={soulEntry} rank={1} />);
    expect(
      screen.getByRole("heading", { level: 3, name: "Entrada na Alma Arcana com pouca Saraivada" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Custou cerca de 2,7% do seu dano")).toBeInTheDocument();
    expect(screen.getByText("Erro")).toHaveClass("badge-erro");
    expect(
      screen.getByText("Erro").querySelector("[data-icon='x'][aria-hidden='true']"),
    ).not.toBeNull();
    expect(screen.getByText(byMarkedText(soulEntry.explanation))).toBeInTheDocument();
    expect(screen.getByText("O que fazer")).toBeInTheDocument();
    expect(screen.getByText(byMarkedText(soulEntry.what_to_do))).toBeInTheDocument();

    const table = screen.getByRole("table");
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((th) => th.textContent),
    ).toEqual(["Medida", "Você", "Melhores"]);
    const rowEl = within(table).getByRole("row", {
      name: /Entradas na Alma Arcana com menos de 12 de Saraivada/,
    });
    expect(rowEl).toHaveTextContent("2 de 5 (0, 20, 1, 18, 22)");
    expect(rowEl).toHaveTextContent("9 de 43");
  });

  it("usa a gravidade como classe e mostra o selo de Atenção com o símbolo", () => {
    const { container } = render(
      <MistakeCard mistake={{ ...soulEntry, severity: "atencao" }} rank={2} />,
    );
    expect(container.querySelector("article")).toHaveClass("mistake-atencao");
    expect(screen.getByText("Atenção")).toHaveClass("badge-atencao");
    expect(
      screen.getByText("Atenção").querySelector("[data-icon='alert'][aria-hidden='true']"),
    ).not.toBeNull();
  });

  it("mostra a posição na lista, escondida do leitor de tela", () => {
    render(<MistakeCard mistake={soulEntry} rank={3} />);
    const rank = screen.getByText("3");
    expect(rank).toHaveAttribute("aria-hidden", "true");
  });

  it("sem rank não mostra posição (hipótese)", () => {
    const { container } = render(<MistakeCard mistake={hypothesis} />);
    expect(container.querySelector(".mistake-rank")).toBeNull();
  });

  it("hipótese: selo próprio e texto de pontos da diferença, não de custo", () => {
    render(<MistakeCard mistake={hypothesis} />);
    expect(screen.getByText("Hipótese")).toBeInTheDocument();
    expect(
      screen.getByText("As regras não explicam cerca de 1,9 pontos da diferença"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Custou cerca de/)).not.toBeInTheDocument();
  });

  it("regra não mostra o selo de hipótese", () => {
    render(<MistakeCard mistake={soulEntry} rank={1} />);
    expect(screen.queryByText("Hipótese")).not.toBeInTheDocument();
  });

  it("impacto nulo avisa que não há custo calculado", () => {
    render(<MistakeCard mistake={noCost} rank={5} />);
    expect(
      screen.getByText("Sem custo em dano calculado (risco de morte ou efeito indireto)"),
    ).toBeInTheDocument();
  });

  it("impacto nulo vence a hipótese (não escreve ‘null pontos’)", () => {
    render(<MistakeCard mistake={{ ...hypothesis, impact_pct: null }} />);
    expect(screen.getByText(/Sem custo em dano calculado/)).toBeInTheDocument();
    expect(screen.queryByText(/null/)).not.toBeInTheDocument();
  });

  it("impacto zero é um custo (0%), não ‘sem custo’", () => {
    render(<MistakeCard mistake={{ ...soulEntry, impact_pct: 0 }} rank={1} />);
    expect(screen.getByText("Custou cerca de 0% do seu dano")).toBeInTheDocument();
  });

  it("mostra a fase quando existe", () => {
    render(<MistakeCard mistake={{ ...soulEntry, phase: "Fase 2" }} rank={1} />);
    expect(screen.getByText("Fase 2")).toHaveClass("muted");
  });

  it("sem números não desenha a tabela", () => {
    render(<MistakeCard mistake={{ ...soulEntry, numbers: [] }} rank={1} />);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it.each(mistakes.map((m) => [m.id ?? m.title, m]))(
    "não tem violações de acessibilidade: %s",
    async (_name, mistake) => {
      const { container } = render(<MistakeCard mistake={mistake} rank={1} />);
      expect(await axeViolations(container)).toEqual([]);
    },
  );

  it("mostra o ícone de cada magia citada e nenhuma marcação crua", () => {
    const { container } = render(<MistakeCard mistake={soulEntry} rank={1} />);
    expect(container.textContent).not.toMatch(/\{\{|spell:/);
    expect(container.querySelectorAll("h3 .spell-ref img.spell-icon").length).toBeGreaterThan(0);
    expect(container.querySelectorAll(".numbers .spell-ref").length).toBeGreaterThan(0);
  });

  it("coloca os detalhes numa seção expandível recolhida por padrão e remove o trecho inline", async () => {
    const user = userEvent.setup();
    const details = [
      "Entrada aos 0:20 com 0 de {{spell:1242974|Saraivada}} ({{spell:44425|Salva}} nos 2 últimos GCDs)",
      "Entrada aos 3:28 com 1 de {{spell:1242974|Saraivada}}",
    ];
    const { container } = render(<MistakeCard mistake={soulEntry} rank={1} details={details} />);

    const section = container.querySelector("details.mistake-details");
    const todo = container.querySelector(".mistake-todo");
    expect(section).not.toBeNull();
    expect(todo).not.toBeNull();
    expect(todo.compareDocumentPosition(section) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(section).not.toHaveAttribute("open");
    expect(within(section).getByText("Ver detalhes (2)")).toBeInTheDocument();
    expect(
      section.querySelector("summary [data-icon='chevron-right'][aria-hidden='true']"),
    ).not.toBeNull();
    // O parágrafo de explicação não repete "Detalhes: ..." inline.
    expect(container.querySelector("p:not(.mistake-meta):not(.mistake-impact)")).not.toHaveTextContent(
      "Detalhes:",
    );

    await user.click(within(section).getByText("Ver detalhes (2)"));
    expect(section).toHaveAttribute("open");
    expect(within(section).getAllByRole("listitem")).toHaveLength(2);
    expect(await axeViolations(container)).toEqual([]);
  });

  it("sem detalhes não renderiza a seção expandível", () => {
    const { container } = render(<MistakeCard mistake={soulEntry} rank={1} details={[]} />);
    expect(container.querySelector("details.mistake-details")).toBeNull();
  });
});
