// localStorage pode não existir ou falhar (janela anônima, bloqueio do navegador).
// Nesse caso o site funciona igual, só não lembra nada entre visitas.

export function load(key, fallback = null) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}

export function save(key, value) {
  try {
    if (value === null || value === undefined) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Sem armazenamento: segue sem lembrar.
  }
}
