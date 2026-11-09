import js from "@eslint/js";
import globals from "globals";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import prettier from "eslint-config-prettier";
import { defineConfig, globalIgnores } from "eslint/config";

export default defineConfig([
  globalIgnores(["dist", "coverage", "test-results", "playwright-report"]),
  {
    files: ["**/*.{js,jsx}"],
    extends: [
      js.configs.recommended,
      react.configs.flat.recommended,
      react.configs.flat["jsx-runtime"],
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
      prettier,
    ],
    settings: { react: { version: "detect" } },
    languageOptions: {
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: {
      // Sem TypeScript nem prop-types no projeto: as props ficam documentadas no próprio componente.
      "react/prop-types": "off",
    },
  },
  {
    // Configurações e testes ponta a ponta rodam no Node; testes do Vitest usam o jsdom.
    files: ["*.config.js", "e2e/**/*.js"],
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
  },
  {
    files: ["src/**/*.test.{js,jsx}", "src/test/**/*.{js,jsx}"],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    // Testes exportam helpers e componentes de apoio sem precisar de Fast Refresh.
    rules: { "react-refresh/only-export-components": "off" },
  },
]);
