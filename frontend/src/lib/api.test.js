import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api.js";

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

let fetchMock;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

async function failure(promise) {
  try {
    await promise;
  } catch (error) {
    return error;
  }
  throw new Error("a chamada deveria ter falhado");
}

describe("pedidos", () => {
  it("GET devolve o JSON da resposta, sem corpo nem Content-Type", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));
    await expect(api.get("/me")).resolves.toEqual({ ok: true });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/me");
    expect(init.method).toBe("GET");
    expect(init.body).toBeUndefined();
    expect(init.headers).toEqual({});
  });

  it("POST manda o corpo em JSON com Content-Type", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: 1 }, 201));
    await api.post("/analyses", { report_code: "XhrmBaYkGCAQjH2D", fight_id: 34 });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ report_code: "XhrmBaYkGCAQjH2D", fight_id: 34 });
  });

  it("POST sem corpo (undefined) não manda Content-Type", async () => {
    fetchMock.mockResolvedValue(jsonResponse({}));
    await api.post("/reports/x/fights/1/prefetch", undefined, "tok");

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["Content-Type"]).toBeUndefined();
    expect(init.body).toBeUndefined();
  });

  it("um corpo falso mas definido (null) ainda é enviado como JSON", async () => {
    fetchMock.mockResolvedValue(jsonResponse({}));
    await api.put("/x", null);

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("PUT");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.body).toBe("null");
  });

  it("DELETE usa o método certo", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await api.del("/analyses/3", "tok");
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE");
  });

  it("manda o token no Authorization quando há token", async () => {
    fetchMock.mockResolvedValue(jsonResponse({}));
    await api.get("/me", "abc.def");
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer abc.def");
  });

  it("não manda Authorization sem token", async () => {
    fetchMock.mockResolvedValue(jsonResponse({}));
    await api.get("/me", null);
    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty("Authorization");
  });

  it("resposta 204 devolve null sem tentar ler JSON", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(api.del("/x")).resolves.toBeNull();
  });

  it("sucesso com corpo que não é JSON devolve null", async () => {
    fetchMock.mockResolvedValue(new Response("ok", { status: 200 }));
    await expect(api.get("/x")).resolves.toBeNull();
  });
});

describe("URL base", () => {
  it("usa VITE_API_URL quando definida", async () => {
    vi.stubEnv("VITE_API_URL", "https://api.logcoach.example");
    vi.resetModules();
    const { api: custom } = await import("./api.js");
    fetchMock.mockResolvedValue(jsonResponse({}));
    await custom.get("/me");
    expect(fetchMock.mock.calls[0][0]).toBe("https://api.logcoach.example/me");
  });
});

describe("erros", () => {
  it("falha de rede vira ApiError network, status 0", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const error = await failure(api.get("/me"));
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("network");
    expect(error.status).toBe(0);
    expect(error.message).toBe(
      "O servidor do LogCoach não respondeu. Confira sua conexão e tente de novo.",
    );
  });

  it("detail com code vira ApiError com code, mensagem e status do servidor", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        { detail: { code: "wcl_unavailable", message: "O Warcraft Logs está fora do ar." } },
        503,
      ),
    );
    const error = await failure(api.post("/analyses", {}));
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toBeInstanceOf(Error);
    expect(error.code).toBe("wcl_unavailable");
    expect(error.message).toBe("O Warcraft Logs está fora do ar.");
    expect(error.status).toBe(503);
  });

  it("o code do detail vale mesmo num 422", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: { code: "invalid_link", message: "Link inválido." } }, 422),
    );
    const error = await failure(api.post("/reports/resolve", {}));
    expect(error.code).toBe("invalid_link");
  });

  it("422 de validação do FastAPI (lista, sem code) vira invalid_request", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: [{ loc: ["body", "email"], msg: "field required" }] }, 422),
    );
    const error = await failure(api.post("/auth/register", {}));
    expect(error.code).toBe("invalid_request");
    expect(error.status).toBe(422);
    expect(error.message).toBe(
      "Algum dado enviado não está no formato esperado. Confira e tente de novo.",
    );
  });

  it.each([500, 502, 504])("%s sem code vira unexpected_error", async (status) => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Internal Server Error" }, status));
    const error = await failure(api.get("/me"));
    expect(error.code).toBe("unexpected_error");
    expect(error.status).toBe(status);
    expect(error.message).toContain("O problema é nosso, não do seu relatório.");
  });

  it("página HTML de erro do proxy vira unexpected_error", async () => {
    fetchMock.mockResolvedValue(new Response("<html>Bad Gateway</html>", { status: 502 }));
    const error = await failure(api.get("/me"));
    expect(error.code).toBe("unexpected_error");
    expect(error.status).toBe(502);
  });

  it("401 sem code também é tratado como inesperado", async () => {
    fetchMock.mockResolvedValue(jsonResponse({}, 401));
    const error = await failure(api.get("/me"));
    expect(error.code).toBe("unexpected_error");
    expect(error.status).toBe(401);
  });

  it("detail com texto simples (sem code) não quebra", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Not Found" }, 404));
    const error = await failure(api.get("/nada"));
    expect(error.code).toBe("unexpected_error");
  });
});
