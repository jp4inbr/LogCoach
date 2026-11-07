import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axeViolations } from "../test/axe.js";
import { mistakes } from "../test/fixtures/components.js";
import MistakeCard from "./MistakeCard.jsx";

const soulEntry = mistakes.find((m) => m.id === "soul_entry");
const hypothesis = mistakes.find((m) => m.kind === "hipotese");
const noCost = mistakes.find((m) => m.impact_pct === null);

describe("MistakeCard", () => {
  it("mostra um erro de regra com custo, explicação, o que fazer e a tabela de números", () => {
    render(<MistakeCard mistake={soulEntry} rank={1} />);
    expect(
      screen.getByRole("heading", { level: 3, name: "Entrada na Alma Arcana com pouco Salvo" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Custou cerca de 2,7% do seu dano")).toBeInTheDocument();
    expect(screen.getByText("✕ Erro")).toHaveClass("badge-erro");
    expect(screen.getByText(soulEntry.explanation)).toBeInTheDocument();
    expect(screen.getByText("O que fazer")).toBeInTheDocument();
    expect(screen.getByText(soulEntry.what_to_do)).toBeInTheDocument();

    const table = screen.getByRole("table");
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((th) => th.textContent),
    ).toEqual(["Medida", "Você", "Melhores"]);
    const rowEl = within(table).getByRole("row", {
      name: /Entradas na Alma Arcana com menos de 12 de Salvo/,
    });
    expect(rowEl).toHaveTextContent("2 de 5 (0, 20, 1, 18, 22)");
    expect(rowEl).toHaveTextContent("9 de 43");
  });

  it("usa a gravidade como classe e mostra ‘! Atenção’", () => {
    const { container } = render(
      <MistakeCard mistake={{ ...soulEntry, severity: "atencao" }} rank={2} />,
    );
    expect(container.querySelector("article")).toHaveClass("mistake-atencao");
    expect(screen.getByText("! Atenção")).toHaveClass("badge-atencao");
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
});
