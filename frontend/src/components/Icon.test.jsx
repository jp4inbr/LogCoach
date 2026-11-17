import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Icon from "./Icon.jsx";

const NAMES = [
  "arrow-left",
  "check",
  "x",
  "alert",
  "chevron-right",
  "sun",
  "moon",
  "eye",
  "eye-off",
  "message",
];

describe("Icon", () => {
  it.each(NAMES)("%s é um SVG de traço, escondido do leitor de tela", (name) => {
    const { container } = render(<Icon name={name} />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("data-icon", name);
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("focusable", "false");
    expect(svg).toHaveAttribute("stroke", "currentColor");
    expect(svg).toHaveAttribute("fill", "none");
    expect(svg.textContent).toBe("");
  });

  it("com label vira imagem com nome acessível", () => {
    render(<Icon name="check" label="Concluído" />);
    expect(screen.getByRole("img", { name: "Concluído" })).toHaveAttribute("data-icon", "check");
  });

  it("nome desconhecido falha alto", () => {
    expect(() => render(<Icon name="nao-existe" />)).toThrow(/Ícone desconhecido/);
  });
});
