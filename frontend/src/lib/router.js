// Roteador mínimo por hash (#/caminho). Mantém o botão "voltar" do navegador funcionando
// (heurística "controle e liberdade") sem adicionar dependência ao projeto.
import { useSyncExternalStore } from "react";

function subscribe(callback) {
  window.addEventListener("hashchange", callback);
  return () => window.removeEventListener("hashchange", callback);
}

function getHash() {
  return window.location.hash.slice(1) || "/";
}

export function useRoute() {
  const hash = useSyncExternalStore(subscribe, getHash);
  const [path, query = ""] = hash.split("?");
  return { path, parts: path.split("/").filter(Boolean), params: new URLSearchParams(query) };
}

export function navigate(to) {
  window.location.hash = to;
}

export function href(to) {
  return `#${to}`;
}
