import { afterEach, describe, expect, it, vi } from "vitest";
import { load, save } from "./storage.js";

describe("storage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("guarda e lê um valor em JSON", () => {
    save("x", { a: 1 });
    expect(load("x")).toEqual({ a: 1 });
  });

  it("devolve o padrão quando a chave não existe", () => {
    expect(load("nada", "padrao")).toBe("padrao");
  });

  it("remove a chave com null ou undefined", () => {
    save("x", 1);
    save("x", null);
    expect(load("x")).toBeNull();
  });

  it("segue sem lembrar quando o localStorage falha", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    expect(() => save("x", 1)).not.toThrow();
    expect(load("x", "padrao")).toBe("padrao");
  });

  it("devolve o padrão quando o valor guardado não é JSON", () => {
    window.localStorage.setItem("x", "{quebrado");
    expect(load("x", 7)).toBe(7);
  });
});
