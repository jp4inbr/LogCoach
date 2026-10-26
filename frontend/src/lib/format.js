const number = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
const integer = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const millions = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatClock(seconds) {
  const total = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(total / 60);
  return `${minutes}:${String(total % 60).padStart(2, "0")}`;
}

export function formatNumber(value) {
  return value === null || value === undefined ? "—" : number.format(value);
}

// 1184000 -> "1,18 mi"
export function formatDps(value) {
  if (value >= 1_000_000) return `${millions.format(value / 1_000_000)} mi`;
  if (value >= 1_000) return `${integer.format(value / 1_000)} mil`;
  return integer.format(value);
}

export function formatSignedPct(value) {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${number.format(Math.abs(value))}%`;
}

export function formatDate(iso) {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
}

export function formatDateTime(iso) {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Pseudônimo da API (RF25) para a tela: "top01" -> "Top 1", "raid_03" -> "Raide 3".
export function formatPseudonym(displayName) {
  const match = /^(top|raid_)(\d+)$/.exec(displayName ?? "");
  if (!match) return displayName;
  return `${match[1] === "top" ? "Top" : "Raide"} ${Number(match[2])}`;
}
