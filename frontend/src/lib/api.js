// Cliente da API do backend. Toda resposta de erro vira um ApiError com `code` e `message`
// em português, no formato que o backend devolve em `detail` (item 8.2).

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(code, message, status) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function request(method, path, { body, token } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(
      "network",
      "O servidor do LogCoach não respondeu. Confira sua conexão e tente de novo.",
      0,
    );
  }

  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (response.ok) return data;

  const detail = data?.detail;
  if (detail?.code) throw new ApiError(detail.code, detail.message, response.status);
  // Erros de validação do FastAPI (422) chegam como lista, sem `code`: dado que a tela
  // mandou fora do formato. Raro, porque as telas validam antes de enviar.
  if (response.status === 422) {
    throw new ApiError(
      "invalid_request",
      "Algum dado enviado não está no formato esperado. Confira e tente de novo.",
      response.status,
    );
  }
  // Qualquer outra resposta sem `code` (500 cru, 502/504 do proxy, página HTML) não veio
  // das nossas rotas: é erro inesperado do LogCoach, não do relatório nem do Warcraft Logs.
  throw new ApiError(
    "unexpected_error",
    // Mesmo texto do UNEXPECTED_ERROR_MESSAGE do backend (app/errors.py).
    "Erro inesperado no LogCoach. O problema é nosso, não do seu relatório. " +
      "Tente de novo; se continuar, recarregue a página.",
    response.status,
  );
}

export const api = {
  get: (path, token) => request("GET", path, { token }),
  post: (path, body, token) => request("POST", path, { body, token }),
  put: (path, body, token) => request("PUT", path, { body, token }),
  del: (path, token) => request("DELETE", path, { token }),
};
