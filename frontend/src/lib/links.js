// Mesma regra do backend (backend/app/services/links.py), para avisar antes de enviar (RF03).
const REPORT_LINK =
  /^(?:https?:\/\/)?(?:[a-z]+\.)?warcraftlogs\.com\/reports\/([A-Za-z0-9]{8,40})(?:[/?#].*)?$/;

export function parseReportCode(url) {
  const match = REPORT_LINK.exec(url.trim());
  return match ? match[1] : null;
}

export const SAMPLE_LINK = "https://www.warcraftlogs.com/reports/XhrmBaYkGCAQjH2D#fight=34";
