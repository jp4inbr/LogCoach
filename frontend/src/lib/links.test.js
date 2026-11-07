import { describe, expect, it } from "vitest";
import { parseReportCode, SAMPLE_LINK } from "./links.js";

describe("parseReportCode", () => {
  it.each([
    ["https://www.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D", "XhrmBaYkGCAQjH2D"],
    ["https://www.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D#fight=34", "XhrmBaYkGCAQjH2D"],
    ["https://pt.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D?fight=34", "XhrmBaYkGCAQjH2D"],
    ["https://www.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D/", "XhrmBaYkGCAQjH2D"],
    ["warcraftlogs.com/reports/XhrmBaYkGCAQjH2D", "XhrmBaYkGCAQjH2D"],
    ["http://warcraftlogs.com/reports/abc123", "abc123"],
  ])("extrai o código de %s", (url, code) => {
    expect(parseReportCode(url)).toBe(code);
  });

  it("ignora espaços em volta do link colado", () => {
    expect(parseReportCode("  https://www.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D \n")).toBe(
      "XhrmBaYkGCAQjH2D",
    );
  });

  it.each([
    "",
    "texto qualquer",
    "https://example.com/reports/XhrmBaYkGCAQjH2D",
    "https://www.warcraftlogs.com/reports/abc",
    "https://www.warcraftlogs.com/reports/",
    "https://www.warcraftlogs.com/reports/abc123_ruim",
    "https://notwarcraftlogs.com/reports/XhrmBaYkGCAQjH2D",
    "https://www.warcraftlogs.com/reports/" + "a".repeat(41),
  ])("devolve null para %j", (url) => {
    expect(parseReportCode(url)).toBeNull();
  });

  it("o link de exemplo é válido e aponta para o kill de referência", () => {
    expect(parseReportCode(SAMPLE_LINK)).toBe("XhrmBaYkGCAQjH2D");
  });
});
