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
  // Erros de validação do FastAPI (422) chegam como lista; mostramos uma mensagem genérica.
  throw new ApiError("unknown", "Algo deu errado. Tente de novo em alguns instantes.", response.status);
}

export const api = {
  get: (path, token) => request("GET", path, { token }),
  post: (path, body, token) => request("POST", path, { body, token }),
  put: (path, body, token) => request("PUT", path, { body, token }),
  del: (path, token) => request("DELETE", path, { token }),
};
