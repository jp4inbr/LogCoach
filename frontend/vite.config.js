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
    // Fuso fixo (o do público do LogCoach): datas e horas formatadas saem iguais em qualquer
    // máquina e no CI (Ubuntu e Windows rodam em UTC), mesmo nos fusos extremos.
    env: { TZ: "America/Sao_Paulo" },
  },
});
