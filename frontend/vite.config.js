/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    // Testes de unidade, componente, integração (telas com a API simulada) e acessibilidade.
    // Os testes ponta a ponta no navegador ficam em e2e/ e rodam com o Playwright.
    environment: "jsdom",
    setupFiles: ["./src/test/setup.js"],
    include: ["src/**/*.test.{js,jsx}"],
    restoreMocks: true,
    unstubGlobals: true,
    unstubEnvs: true,
  },
});
