// API simulada para os testes das telas: troca o `fetch` global e registra cada chamada.
//
//   const api = mockApi({
//     "POST /reports/resolve": { status: 200, body: report },
//     "GET /me": [{ status: 200, body: me }, { status: 401, body: erro }], // uma por chamada
//     "POST /analyses": (call) => ({ status: 200, body: { ... } }),       // calculada
//     "GET /reports/X/fights/34/players": new TypeError("sem rede"),      // rede fora
//   });
//   api.calls("POST /analyses")[0].body  // corpo enviado (já em objeto)
//
// - Chave: "MÉTODO /caminho" (sem o host e sem query).
// - Lista de respostas: usa uma por chamada e repete a última quando acaba.
// - `delay` (ms) na resposta segura o retorno; vale com timers falsos.
// - Chamada sem resposta simulada derruba o fetch com erro de rede e fica em `api.unmatched`
//   (os testes conferem que está vazio quando precisam).
import { vi } from "vitest";

export const SESSION_KEY = "logcoach.session";

// Resposta de erro da API: { detail: { code, message } }, como o backend devolve (12.3).
export function apiError(status, code, message) {
  return { status, body: { detail: { code, message } } };
}

// Deixa a pessoa "logada" antes de renderizar (o AuthProvider lê daqui).
export function setSession(token = "token-de-teste", email = "voce@exemplo.com") {
  window.localStorage.setItem(SESSION_KEY, JSON.stringify({ token, email }));
}

export function lerSessao() {
  return JSON.parse(window.localStorage.getItem(SESSION_KEY) ?? "null");
}

function toResponse({ status = 200, body = null, html = false }) {
  if (status === 204) return new Response(null, { status });
  if (html) return new Response(String(body), { status, headers: { "Content-Type": "text/html" } });
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function mockApi(routes = {}) {
  const log = [];
  const unmatched = [];
  const used = new Map(); // quantas respostas de cada rota já foram entregues

  const fetchMock = vi.fn(async (input, init = {}) => {
    const url = new URL(String(input));
    const method = (init.method ?? "GET").toUpperCase();
    const key = `${method} ${url.pathname}`;
    const headers = init.headers ?? {};
    const call = {
      key,
      method,
      path: url.pathname,
      headers,
      authorization: headers.Authorization ?? null,
      body: init.body === undefined ? undefined : JSON.parse(init.body),
    };
    log.push(call);

    const route = routes[key];
    if (route === undefined) {
      unmatched.push(key);
      throw new TypeError(`Sem resposta simulada para ${key}`);
    }

    const index = used.get(key) ?? 0;
    used.set(key, index + 1);
    let answer = Array.isArray(route) ? route[Math.min(index, route.length - 1)] : route;
    if (typeof answer === "function") answer = await answer(call, index);
    if (answer instanceof Error) throw answer;
    if (answer.delay) await new Promise((resolve) => setTimeout(resolve, answer.delay));
    return toResponse(answer);
  });

  vi.stubGlobal("fetch", fetchMock);

  return {
    fetch: fetchMock,
    unmatched,
    // Todas as chamadas, ou só as de uma rota ("POST /analyses").
    calls: (key) => (key ? log.filter((call) => call.key === key) : [...log]),
    // Troca ou acrescenta respostas no meio do teste.
    set: (key, answer) => {
      routes[key] = answer;
      used.delete(key);
    },
  };
}
