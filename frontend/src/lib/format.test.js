import { describe, expect, it } from "vitest";
import {
  formatClock,
  formatDate,
  formatDateTime,
  formatDps,
  formatNumber,
  formatPseudonym,
  formatSignedPct,
} from "./format.js";

describe("formatClock", () => {
  it.each([
    [0, "0:00"],
    [5, "0:05"],
    [65, "1:05"],
    [415.6, "6:56"],
    [59.6, "1:00"],
    [600, "10:00"],
  ])("mostra %s s como %s", (seconds, expected) => {
    expect(formatClock(seconds)).toBe(expected);
  });

  it("não deixa o relógio ficar negativo", () => {
    expect(formatClock(-12)).toBe("0:00");
  });
});

describe("formatNumber", () => {
  it("usa vírgula decimal e uma casa", () => {
    expect(formatNumber(6.6)).toBe("6,6");
    expect(formatNumber(18)).toBe("18");
    expect(formatNumber(2.74)).toBe("2,7");
  });

  it("usa ponto como separador de milhar", () => {
    expect(formatNumber(1234.56)).toBe("1.234,6");
  });

  it("mostra traço para null e undefined, mas não para zero", () => {
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(undefined)).toBe("—");
    expect(formatNumber(0)).toBe("0");
  });
});

describe("formatDps", () => {
  it("abrevia milhões com duas casas", () => {
    expect(formatDps(1_184_000)).toBe("1,18 mi");
    expect(formatDps(1_000_000)).toBe("1,00 mi");
  });

  it("abrevia milhares sem casas decimais", () => {
    expect(formatDps(278_699.13)).toBe("279 mil");
    expect(formatDps(1_000)).toBe("1 mil");
  });

  it("mostra o valor inteiro abaixo de mil", () => {
    expect(formatDps(999.4)).toBe("999");
    expect(formatDps(0)).toBe("0");
  });
});

describe("formatSignedPct", () => {
  it("põe + nos positivos", () => {
    expect(formatSignedPct(18)).toBe("+18%");
  });

  it("usa o sinal de menos tipográfico nos negativos", () => {
    expect(formatSignedPct(-2.5)).toBe("−2,5%");
  });

  it("não põe sinal no zero", () => {
    expect(formatSignedPct(0)).toBe("0%");
  });
});

describe("formatDate e formatDateTime", () => {
  // Meio-dia UTC para o dia não mudar nos fusos usuais.
  const iso = "2026-11-04T12:00:00Z";

  it("escreve a data em português", () => {
    expect(formatDate(iso)).toBe("04 de nov. de 2026");
  });

  it("escreve data e hora em português, sem o ano", () => {
    const text = formatDateTime(iso);
    expect(text).toMatch(/^04 de nov\.,? \d{2}:\d{2}$/);
  });
});

describe("formatPseudonym", () => {
  it("transforma topNN em Top N", () => {
    expect(formatPseudonym("top01")).toBe("Top 1");
    expect(formatPseudonym("top10")).toBe("Top 10");
  });

  it("transforma raid_NN em Raide N", () => {
    expect(formatPseudonym("raid_03")).toBe("Raide 3");
  });

  it("mantém o que não é pseudônimo", () => {
    expect(formatPseudonym("Harmonist")).toBe("Harmonist");
    expect(formatPseudonym("top")).toBe("top");
    expect(formatPseudonym("topo01")).toBe("topo01");
  });

  it("aceita null e undefined sem quebrar", () => {
    expect(formatPseudonym(null)).toBeNull();
    expect(formatPseudonym(undefined)).toBeUndefined();
  });
});
