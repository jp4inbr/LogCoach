import { describe, expect, it } from "vitest";
import { parseSpellText, plainSpellText } from "./spellText.js";

describe("parseSpellText", () => {
  it("texto puro vira um segmento só", () => {
    expect(parseSpellText("sem magia aqui")).toEqual([{ type: "text", text: "sem magia aqui" }]);
  });

  it("uma marcação, com texto antes e depois", () => {
    expect(parseSpellText("Use o {{spell:365350|Surto}} agora")).toEqual([
      { type: "text", text: "Use o " },
      { type: "spell", id: "365350", text: "Surto" },
      { type: "text", text: " agora" },
    ]);
  });

  it("várias marcações, inclusive coladas e com pontuação", () => {
    expect(parseSpellText("{{spell:1|A}}{{spell:2|B}}, ({{spell:3|C}}).")).toEqual([
      { type: "spell", id: "1", text: "A" },
      { type: "spell", id: "2", text: "B" },
      { type: "text", text: ", (" },
      { type: "spell", id: "3", text: "C" },
      { type: "text", text: ")." },
    ]);
  });

  it("acentos e plural ficam no texto exibido", () => {
    expect(
      parseSpellText("{{spell:449569|meteoritos}} e {{spell:1295924|Seta Prismática}}"),
    ).toEqual([
      { type: "spell", id: "449569", text: "meteoritos" },
      { type: "text", text: " e " },
      { type: "spell", id: "1295924", text: "Seta Prismática" },
    ]);
  });

  it.each([
    "{{spell:abc|x}}",
    "{{spell:1}}",
    "{{spell:1|sem fechar",
    "{{spell:|x}}",
    "{{spell:1|}}",
  ])("marcação malformada %s fica como texto literal", (text) => {
    expect(parseSpellText(text)).toEqual([{ type: "text", text }]);
    expect(plainSpellText(text)).toBe(text);
  });

  it("null, undefined e vazio são seguros", () => {
    for (const value of [null, undefined, ""]) {
      expect(parseSpellText(value)).toEqual([]);
      expect(plainSpellText(value)).toBe("");
    }
  });
});

describe("plainSpellText", () => {
  it("devolve o texto exibido sem a marcação", () => {
    expect(
      plainSpellText("Depois do {{spell:365350|Surto}} vem a {{spell:451038|Alma Arcana}}."),
    ).toBe("Depois do Surto vem a Alma Arcana.");
  });
});
