import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubSystemTheme } from "../test/matchMedia.js";
import {
  applyTheme,
  getStoredTheme,
  getSystemTheme,
  resolveTheme,
  saveTheme,
  THEME_COLORS,
  THEME_KEY,
  useTheme,
} from "./theme.js";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.documentElement.style.colorScheme = "";
  document.head.querySelectorAll('meta[name="theme-color"]').forEach((m) => m.remove());
});

function breakStorage() {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("bloqueado");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("bloqueado");
  });
}

describe("resolução do tema", () => {
  it("sem escolha salva, segue o sistema", () => {
    stubSystemTheme("light");
    expect(resolveTheme()).toBe("light");
    stubSystemTheme("dark");
    expect(resolveTheme()).toBe("dark");
  });

  it("a escolha salva vale mais que o sistema", () => {
    stubSystemTheme("light");
    window.localStorage.setItem(THEME_KEY, "dark");
    expect(resolveTheme()).toBe("dark");
  });

  it("valor inválido no storage é ignorado", () => {
    stubSystemTheme("light");
    window.localStorage.setItem(THEME_KEY, "roxo");
    expect(getStoredTheme()).toBeNull();
    expect(resolveTheme()).toBe("light");
  });

  it("storage que lança exceção não derruba nada", () => {
    stubSystemTheme("light");
    breakStorage();
    expect(getStoredTheme()).toBeNull();
    expect(() => saveTheme("dark")).not.toThrow();
    expect(resolveTheme()).toBe("light");
  });

  it("sem matchMedia, o padrão é o escuro", () => {
    vi.stubGlobal("matchMedia", undefined);
    expect(getSystemTheme()).toBe("dark");
  });
});

describe("applyTheme", () => {
  it("põe data-theme, color-scheme e theme-color", () => {
    applyTheme("light");
    const root = document.documentElement;
    expect(root).toHaveAttribute("data-theme", "light");
    expect(root.style.colorScheme).toBe("light");
    const meta = document.querySelector('meta[name="theme-color"]');
    expect(meta).toHaveAttribute("content", THEME_COLORS.light);

    applyTheme("dark");
    expect(root).toHaveAttribute("data-theme", "dark");
    expect(root.style.colorScheme).toBe("dark");
    expect(document.querySelectorAll('meta[name="theme-color"]')).toHaveLength(1);
    expect(meta).toHaveAttribute("content", THEME_COLORS.dark);
  });

  it("ignora tema inválido", () => {
    applyTheme("roxo");
    expect(document.documentElement).not.toHaveAttribute("data-theme");
  });
});

describe("useTheme", () => {
  it("começa pelo sistema, aplica e alterna salvando a escolha", () => {
    stubSystemTheme("light");
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("light");
    expect(document.documentElement).toHaveAttribute("data-theme", "light");

    act(() => result.current.toggle());
    expect(result.current.theme).toBe("dark");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(window.localStorage.getItem(THEME_KEY)).toBe("dark");
  });

  it("sem escolha salva, acompanha o sistema com a página aberta", () => {
    const system = stubSystemTheme("dark");
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("dark");

    act(() => system.set("light"));
    expect(result.current.theme).toBe("light");
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
  });

  it("com escolha salva, o sistema não muda o tema", () => {
    const system = stubSystemTheme("dark");
    window.localStorage.setItem(THEME_KEY, "dark");
    const { result } = renderHook(() => useTheme());

    act(() => system.set("light"));
    expect(result.current.theme).toBe("dark");
  });

  it("depois de alternar à mão, o sistema deixa de mandar", () => {
    const system = stubSystemTheme("dark");
    const { result } = renderHook(() => useTheme());
    act(() => result.current.toggle());
    expect(result.current.theme).toBe("light");

    act(() => system.set("dark"));
    expect(result.current.theme).toBe("light");
  });

  it("remove o listener ao desmontar", () => {
    const system = stubSystemTheme("dark");
    const { unmount } = renderHook(() => useTheme());
    expect(system.listenerCount()).toBe(1);
    unmount();
    expect(system.listenerCount()).toBe(0);
  });

  it("alterna mesmo com o storage quebrado (vale só nesta visita)", () => {
    const system = stubSystemTheme("dark");
    breakStorage();
    const { result } = renderHook(() => useTheme());
    act(() => result.current.toggle());
    expect(result.current.theme).toBe("light");
    expect(document.documentElement).toHaveAttribute("data-theme", "light");

    // Escolha feita à mão vale na visita, mesmo sem ter sido salva: o sistema não a desfaz.
    act(() => system.set("dark"));
    expect(result.current.theme).toBe("light");
  });
});

describe("script inline do index.html (sem flash)", () => {
  const html = readFileSync(resolve(process.cwd(), "index.html"), "utf8");
  const script = /<script>([\s\S]*?)<\/script>/.exec(html)?.[1];

  function run() {
    document.head.insertAdjacentHTML("beforeend", '<meta name="theme-color" content="#0f0e17" />');
    new Function(script)();
    return document.documentElement.getAttribute("data-theme");
  }

  it("existe um script inline antes do módulo da aplicação", () => {
    expect(script).toBeTruthy();
    expect(html.indexOf("<script>")).toBeLessThan(html.indexOf('type="module"'));
  });

  it("segue o sistema sem escolha salva", () => {
    stubSystemTheme("light");
    expect(run()).toBe("light");
    expect(document.documentElement.style.colorScheme).toBe("light");
    expect(document.querySelector('meta[name="theme-color"]')).toHaveAttribute(
      "content",
      THEME_COLORS.light,
    );
  });

  it("a escolha salva vence o sistema", () => {
    stubSystemTheme("light");
    window.localStorage.setItem(THEME_KEY, "dark");
    expect(run()).toBe("dark");
  });

  it("ignora valor inválido salvo", () => {
    stubSystemTheme("light");
    window.localStorage.setItem(THEME_KEY, "azul");
    expect(run()).toBe("light");
  });

  it("com localStorage quebrado, cai no sistema", () => {
    stubSystemTheme("light");
    breakStorage();
    expect(run()).toBe("light");
  });

  it("sem matchMedia nem storage, fica no escuro", () => {
    vi.stubGlobal("matchMedia", undefined);
    breakStorage();
    expect(run()).toBe("dark");
  });

  it("dá o mesmo resultado que resolveTheme() em todos os cenários", () => {
    for (const saved of [null, "light", "dark", "xis"]) {
      for (const system of ["light", "dark"]) {
        window.localStorage.clear();
        document.documentElement.removeAttribute("data-theme");
        document.head.querySelectorAll('meta[name="theme-color"]').forEach((m) => m.remove());
        stubSystemTheme(system);
        if (saved) window.localStorage.setItem(THEME_KEY, saved);
        expect(run(), `salvo=${saved} sistema=${system}`).toBe(resolveTheme());
      }
    }
  });
});
