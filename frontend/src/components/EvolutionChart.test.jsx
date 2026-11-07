import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axeViolations } from "../test/axe.js";
import EvolutionChart from "./EvolutionChart.jsx";

// Meio-dia UTC: o dia não muda nos fusos usuais.
const points = [
  { id: 1, dps: 250_000, created_at: "2026-10-20T12:00:00Z" },
  { id: 2, dps: 262_000, created_at: "2026-10-27T12:00:00Z" },
  { id: 3, dps: 270_000, created_at: "2026-11-03T12:00:00Z" },
];

describe("EvolutionChart", () => {
  it("descreve a evolução do primeiro ao último ponto para o leitor de tela", () => {
    render(<EvolutionChart points={points} />);
    expect(
      screen.getByRole("img", {
        name: "DPS de 250 mil em 20 de out. de 2026 para 270 mil em 03 de nov. de 2026",
      }),
    ).toBeInTheDocument();
  });

  it("cada ponto tem um título com data e DPS", () => {
    const { container } = render(<EvolutionChart points={points} />);
    expect(container.querySelectorAll("circle")).toHaveLength(3);
    expect(container.querySelector("circle title").textContent).toBe("20 de out. de 2026: 250 mil");
    expect(
      screen.getByText("03 de nov. de 2026: 270 mil", { selector: "title" }),
    ).toBeInTheDocument();
  });

  it("desenha uma linha ligando todos os pontos, em ordem", () => {
    const { container } = render(<EvolutionChart points={points} />);
    const d = container.querySelector("path.chart-line").getAttribute("d");
    expect(d.startsWith("M")).toBe(true);
    expect(d.match(/L/g)).toHaveLength(2);
  });

  it("DPS maior fica mais alto (y menor) e as datas vão da esquerda para a direita", () => {
    const { container } = render(<EvolutionChart points={points} />);
    const dots = [...container.querySelectorAll("circle")].map((c) => ({
      x: Number(c.getAttribute("cx")),
      y: Number(c.getAttribute("cy")),
    }));
    expect(dots[0].x).toBeLessThan(dots[1].x);
    expect(dots[1].x).toBeLessThan(dots[2].x);
    expect(dots[0].y).toBeGreaterThan(dots[1].y);
    expect(dots[1].y).toBeGreaterThan(dots[2].y);
    // Respeita as margens do desenho.
    expect(dots[0].x).toBe(64);
    expect(dots[2].x).toBe(584);
  });

  it("mostra três marcas no eixo do DPS e as duas datas das pontas", () => {
    const { container } = render(<EvolutionChart points={points} />);
    const ticks = [...container.querySelectorAll("text")].map((t) => t.textContent);
    // Grade: mínimo −3%, meio e máximo +3%.
    expect(ticks.slice(0, 3)).toEqual(["243 mil", "260 mil", "278 mil"]);
    expect(ticks.slice(3)).toEqual(["20 de out. de 2026", "03 de nov. de 2026"]);
  });

  it("com um só ponto desenha sem quebrar (sem NaN)", () => {
    const { container } = render(<EvolutionChart points={[points[0]]} />);
    expect(container.querySelectorAll("circle")).toHaveLength(1);
    expect(container.innerHTML).not.toContain("NaN");
    expect(
      screen.getByRole("img", {
        name: "DPS de 250 mil em 20 de out. de 2026 para 250 mil em 20 de out. de 2026",
      }),
    ).toBeInTheDocument();
  });

  it("com DPS igual em todos os pontos não gera NaN nem Infinity", () => {
    const flat = points.map((p) => ({ ...p, dps: 260_000 }));
    const { container } = render(<EvolutionChart points={flat} />);
    expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
  });

  it("não tem violações de acessibilidade", async () => {
    const { container } = render(<EvolutionChart points={points} />);
    expect(await axeViolations(container)).toEqual([]);
  });
});
