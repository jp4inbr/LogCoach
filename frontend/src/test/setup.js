// Preparação comum dos testes do Vitest (jsdom).
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  window.location.hash = "";
  document.documentElement.removeAttribute("data-theme");
});
