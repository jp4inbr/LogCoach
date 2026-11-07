import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App.jsx";
import { axeViolations } from "./test/axe.js";
import { stubSystemTheme } from "./test/matchMedia.js";

beforeEach(() => {
  // A Home não chama a API; se alguma tela chamar, falha alto em vez de ir à rede.
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.reject(new Error("fetch inesperado"))),
  );
  stubSystemTheme("dark");
});

afterEach(() => {
  vi.unstubAllGlobals();
  document.documentElement.style.colorScheme = "";
  document.head.querySelectorAll('meta[name="theme-color"]').forEach((m) => m.remove());
});

describe("cabeçalho do App", () => {
  it("tem a navegação principal e o botão de tema antes de Entrar", () => {
    render(<App />);
    const nav = screen.getByRole("navigation", { name: "Principal" });
    const items = [...nav.querySelectorAll("a, button")];
    const names = items.map((el) => el.getAttribute("aria-label") ?? el.textContent);
    expect(names).toEqual(["Analisar", "Planos", "Ativar tema claro", "Entrar"]);
  });

  it("alterna o tema pelo cabeçalho", async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");

    await user.click(screen.getByRole("button", { name: "Ativar tema claro" }));
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    expect(screen.getByRole("button", { name: "Ativar tema escuro" })).toBeInTheDocument();
  });

  it("não tem violações do axe", async () => {
    const { container } = render(<App />);
    expect(await axeViolations(container)).toEqual([]);
  });
});
