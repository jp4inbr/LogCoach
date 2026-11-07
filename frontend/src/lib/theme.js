// Tema claro/escuro. Ordem de decisão: escolha salva > tema do sistema > escuro.
//
// ATENÇÃO: o script inline do index.html repete esta mesma lógica (resolve o tema antes da
// primeira pintura, para não piscar). Os dois precisam ficar iguais; o teste
// src/lib/theme.test.js executa o script do index.html e confere o resultado.
//
// localStorage pode não existir ou falhar (janela anônima, bloqueio do navegador): tudo aqui
// vai em try/catch e o site funciona igual, só sem lembrar a escolha. Guardamos o texto
// puro ("light" ou "dark"), sem JSON, para o script inline ler sem depender de nada.
import { useCallback, useEffect, useState } from "react";

export const THEME_KEY = "logcoach.theme";
export const THEMES = ["light", "dark"];

// Cor da barra do navegador (meta theme-color): o fundo de cada tema (docs/15).
export const THEME_COLORS = { light: "#fffffe", dark: "#0f0e17" };

const LIGHT_QUERY = "(prefers-color-scheme: light)";

export function isTheme(value) {
  return THEMES.includes(value);
}

/** Tema salvo pela pessoa, ou null (sem escolha, valor inválido ou storage quebrado). */
export function getStoredTheme() {
  try {
    const value = window.localStorage.getItem(THEME_KEY);
    return isTheme(value) ? value : null;
  } catch {
    return null;
  }
}

/** Tema do sistema. Sem suporte a matchMedia, vale o escuro (o padrão do CSS). */
export function getSystemTheme() {
  try {
    return window.matchMedia(LIGHT_QUERY).matches ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function resolveTheme() {
  return getStoredTheme() ?? getSystemTheme();
}

/** Aplica no <html>: data-theme, color-scheme (formulários e rolagem nativos) e theme-color. */
export function applyTheme(theme) {
  if (!isTheme(theme)) return;
  const root = document.documentElement;
  root.setAttribute("data-theme", theme);
  root.style.colorScheme = theme;
  let meta = document.querySelector('meta[name="theme-color"]');
  if (!meta) {
    meta = document.createElement("meta");
    meta.setAttribute("name", "theme-color");
    document.head.appendChild(meta);
  }
  meta.setAttribute("content", THEME_COLORS[theme]);
}

export function saveTheme(theme) {
  if (!isTheme(theme)) return;
  try {
    window.localStorage.setItem(THEME_KEY, theme);
  } catch {
    // Sem armazenamento: o tema vale só nesta visita.
  }
}

/** { theme, toggle }. Sem escolha salva, acompanha o sistema enquanto a página está aberta. */
export function useTheme() {
  const [theme, setTheme] = useState(resolveTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    let media;
    try {
      media = window.matchMedia(LIGHT_QUERY);
    } catch {
      return undefined;
    }
    if (!media || typeof media.addEventListener !== "function") return undefined;
    const onChange = () => {
      // Com escolha salva, o sistema não manda mais.
      if (getStoredTheme() === null) setTheme(getSystemTheme());
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const toggle = useCallback(() => {
    const next = theme === "dark" ? "light" : "dark";
    saveTheme(next);
    setTheme(next);
  }, [theme]);

  return { theme, toggle };
}
