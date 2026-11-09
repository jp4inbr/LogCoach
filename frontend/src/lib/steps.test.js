import { describe, expect, it } from "vitest";
import { ANALYSIS_STEPS } from "./steps.js";

describe("ANALYSIS_STEPS", () => {
  it("lista as três etapas da análise, em ordem", () => {
    expect(ANALYSIS_STEPS).toEqual([
      "Buscando sua luta",
      "Comparando com os melhores",
      "Coach analisando",
    ]);
  });
});
