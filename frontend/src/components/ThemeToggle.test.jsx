import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { THEME_KEY } from "../lib/theme.js";
import { axeViolations } from "../test/axe.js";
import { stubSystemTheme } from "../test/matchMedia.js";
import ThemeToggle from "./ThemeToggle.jsx";

afterEach(() => {
  vi.unstubAllGlobals();
  document.documentElement.style.colorScheme = "";
  document.head.querySelectorAll('meta[name="theme-color"]').forEach((m) => m.remove());
});

describe("ThemeToggle", () => {
  it("o nome diz a ação e muda depois do clique", async () => {
    stubSystemTheme("dark");
    const user = userEvent.setup();
    render(<ThemeToggle />);

    const button = screen.getByRole("button", { name: "Ativar tema claro" });
    expect(button).toHaveAttribute("type", "button");
    expect(button).toHaveAttribute("title", "Ativar tema claro");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");

    await user.click(button);
    expect(screen.getByRole("button", { name: "Ativar tema escuro" })).toHaveAttribute(
      "title",
      "Ativar tema escuro",
    );
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    expect(window.localStorage.getItem(THEME_KEY)).toBe("light");
  });

  it("o ícone fica escondido dos leitores de tela", () => {
    stubSystemTheme("light");
    render(<ThemeToggle />);
    const icon = screen.getByRole("button").querySelector("[aria-hidden='true']");
    expect(icon).toHaveTextContent("☾");
  });

  it("funciona pelo teclado com Enter e Espaço", async () => {
    stubSystemTheme("dark");
    const user = userEvent.setup();
    render(<ThemeToggle />);

    await user.tab();
    expect(screen.getByRole("button")).toHaveFocus();

    await user.keyboard("{Enter}");
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    await user.keyboard(" ");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(window.localStorage.getItem(THEME_KEY)).toBe("dark");
  });

  it("começa pela escolha salva", () => {
    stubSystemTheme("dark");
    window.localStorage.setItem(THEME_KEY, "light");
    render(<ThemeToggle />);
    expect(screen.getByRole("button", { name: "Ativar tema escuro" })).toBeInTheDocument();
  });

  it("não tem violações do axe", async () => {
    stubSystemTheme("dark");
    const { container } = render(<ThemeToggle />);
    expect(await axeViolations(container)).toEqual([]);
  });
});
