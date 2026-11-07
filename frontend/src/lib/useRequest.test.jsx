import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api.js";
import { useRequest } from "./useRequest.js";

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("useRequest", () => {
  it("começa carregando e passa para ok com os dados", async () => {
    const pending = deferred();
    const get = vi.spyOn(api, "get").mockReturnValue(pending.promise);

    const { result } = renderHook(() => useRequest("/me/analyses", "tok"));
    expect(result.current).toEqual({ status: "loading", data: null, error: null });
    expect(get).toHaveBeenCalledWith("/me/analyses", "tok");

    await act(async () => pending.resolve([{ id: 1 }]));
    expect(result.current).toEqual({ status: "ok", data: [{ id: 1 }], error: null });
  });

  it("guarda o erro da API em caso de falha", async () => {
    const error = new ApiError("invalid_token", "Sessão vencida.", 401);
    vi.spyOn(api, "get").mockRejectedValue(error);

    const { result } = renderHook(() => useRequest("/me", "tok"));
    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.error).toBe(error);
    expect(result.current.data).toBeNull();
  });

  it("refaz o pedido quando o caminho muda", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValue("a");
    const { result, rerender } = renderHook(({ path }) => useRequest(path, null), {
      initialProps: { path: "/a" },
    });
    await waitFor(() => expect(result.current.data).toBe("a"));

    get.mockResolvedValue("b");
    rerender({ path: "/b" });
    await waitFor(() => expect(result.current.data).toBe("b"));
    expect(get).toHaveBeenCalledTimes(2);
    expect(get).toHaveBeenLastCalledWith("/b", null);
  });

  it("refaz o pedido quando o token muda", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValue("x");
    const { rerender } = renderHook(({ token }) => useRequest("/me", token), {
      initialProps: { token: "t1" },
    });
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1));
    rerender({ token: "t2" });
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
    expect(get).toHaveBeenLastCalledWith("/me", "t2");
  });

  it("descarta a resposta de um pedido antigo que chega depois do novo", async () => {
    const first = deferred();
    const second = deferred();
    vi.spyOn(api, "get").mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);

    const { result, rerender } = renderHook(({ path }) => useRequest(path), {
      initialProps: { path: "/a" },
    });
    rerender({ path: "/b" });

    await act(async () => second.resolve("novo"));
    await act(async () => first.resolve("velho"));
    expect(result.current.data).toBe("novo");
  });

  it("descarta o erro de um pedido antigo", async () => {
    const first = deferred();
    const second = deferred();
    vi.spyOn(api, "get").mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);

    const { result, rerender } = renderHook(({ path }) => useRequest(path), {
      initialProps: { path: "/a" },
    });
    rerender({ path: "/b" });
    await act(async () => second.resolve("novo"));
    await act(async () => first.reject(new ApiError("network", "caiu", 0)));

    expect(result.current).toEqual({ status: "ok", data: "novo", error: null });
  });

  it("não atualiza o estado depois de desmontar", async () => {
    const pending = deferred();
    vi.spyOn(api, "get").mockReturnValue(pending.promise);
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});

    const { unmount } = renderHook(() => useRequest("/a"));
    unmount();
    await act(async () => pending.resolve("tarde"));
    expect(errors).not.toHaveBeenCalled();
  });
});
