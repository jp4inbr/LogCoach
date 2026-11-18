import { describe, expect, it } from "vitest";
import { passwordStrength } from "./passwordStrength.js";

const nivel = (senha) => passwordStrength(senha)?.label;

describe("passwordStrength", () => {
  it("vazio: sem medidor", () => {
    expect(passwordStrength("")).toBeNull();
  });

  it("menos de 8 caracteres é sempre fraca, com a dica do mínimo", () => {
    expect(passwordStrength("Ab1!xyz")).toMatchObject({
      label: "Fraca",
      tip: "Use pelo menos 8 caracteres.",
    });
  });

  it("sequências, repetições e palavras óbvias ficam fracas", () => {
    expect(nivel("12345678")).toBe("Fraca");
    expect(nivel("abcdefgh")).toBe("Fraca");
    expect(nivel("aaaaaaaaaaaa")).toBe("Fraca");
    expect(nivel("Senha123")).not.toBe("Forte");
    expect(passwordStrength("senha2026senha").tip).toMatch(/palavras comuns/);
  });

  it("sobe com tamanho e variedade", () => {
    expect(nivel("cavalobranco")).toBe("Razoável");
    expect(nivel("cavalo-branco")).toBe("Boa");
    expect(nivel("Lua-de-Prata-27")).toBe("Forte");
  });

  it("forte não tem dica", () => {
    expect(passwordStrength("Lua-de-Prata-27").tip).toBeNull();
  });
});
