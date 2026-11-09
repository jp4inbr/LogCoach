import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../lib/api.js";
import { useAuth } from "../lib/auth-context.js";
import AuthProvider from "./AuthProvider.jsx";

const KEY = "logcoach.session";

function Probe() {
  const auth = useAuth();
  return (
    <div>
      <p data-testid="token">{auth.token ?? "sem token"}</p>
      <p data-testid="email">{auth.email ?? "sem e-mail"}</p>
      <button onClick={() => auth.login("tok-novo", "ana@exemplo.com")}>Entrar</button>
      <button onClick={() => auth.logout()}>Sair</button>
    </div>
  );
}

function renderProvider() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
}

const stored = () => JSON.parse(window.localStorage.getItem(KEY));

describe("AuthProvider", () => {
  it("sem sessão salva começa deslogado e não confere nada com a API", () => {
    const get = vi.spyOn(api, "get");
    renderProvider();
    expect(screen.getByTestId("token")).toHaveTextContent("sem token");
    expect(screen.getByTestId("email")).toHaveTextContent("sem e-mail");
    expect(get).not.toHaveBeenCalled();
  });

  it("login guarda a sessão no navegador e atualiza quem usa o contexto", async () => {
    vi.spyOn(api, "get").mockResolvedValue({});
    renderProvider();
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));

    expect(screen.getByTestId("token")).toHaveTextContent("tok-novo");
    expect(screen.getByTestId("email")).toHaveTextContent("ana@exemplo.com");
    expect(stored()).toEqual({ token: "tok-novo", email: "ana@exemplo.com" });
  });

  it("logout apaga a sessão salva", async () => {
    vi.spyOn(api, "get").mockResolvedValue({});
    window.localStorage.setItem(KEY, JSON.stringify({ token: "t", email: "a@b.com" }));
    renderProvider();
    await userEvent.click(screen.getByRole("button", { name: "Sair" }));

    expect(screen.getByTestId("token")).toHaveTextContent("sem token");
    expect(window.localStorage.getItem(KEY)).toBeNull();
  });

  it("recupera a sessão salva e confere o token em /me", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValue({ email: "a@b.com" });
    window.localStorage.setItem(KEY, JSON.stringify({ token: "t-salvo", email: "a@b.com" }));
    renderProvider();

    expect(screen.getByTestId("token")).toHaveTextContent("t-salvo");
    expect(screen.getByTestId("email")).toHaveTextContent("a@b.com");
    await waitFor(() => expect(get).toHaveBeenCalledWith("/me", "t-salvo"));
    expect(get).toHaveBeenCalledTimes(1);
    expect(stored()).toEqual({ token: "t-salvo", email: "a@b.com" });
  });

  it("token vencido (invalid_token) sai da conta e limpa a sessão salva", async () => {
    vi.spyOn(api, "get").mockRejectedValue(
      new ApiError("invalid_token", "Sua sessão venceu. Entre de novo.", 401),
    );
    window.localStorage.setItem(KEY, JSON.stringify({ token: "vencido", email: "a@b.com" }));
    renderProvider();

    await waitFor(() => expect(screen.getByTestId("token")).toHaveTextContent("sem token"));
    expect(screen.getByTestId("email")).toHaveTextContent("sem e-mail");
    expect(window.localStorage.getItem(KEY)).toBeNull();
  });

  it.each([
    ["rede fora do ar", new ApiError("network", "sem rede", 0)],
    ["erro inesperado", new ApiError("unexpected_error", "falha nossa", 500)],
  ])("%s não derruba a sessão", async (_name, error) => {
    const get = vi.spyOn(api, "get").mockRejectedValue(error);
    window.localStorage.setItem(KEY, JSON.stringify({ token: "t", email: "a@b.com" }));
    renderProvider();

    await waitFor(() => expect(get).toHaveBeenCalled());
    await act(async () => {});
    expect(screen.getByTestId("token")).toHaveTextContent("t");
    expect(stored()).toEqual({ token: "t", email: "a@b.com" });
  });

  it("depois de logar, confere o token novo em /me", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValue({});
    renderProvider();
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
    await waitFor(() => expect(get).toHaveBeenCalledWith("/me", "tok-novo"));
  });

  it("ignora a resposta de invalid_token de uma sessão que já foi trocada", async () => {
    let rejectOld;
    const get = vi.spyOn(api, "get").mockImplementation((_path, token) =>
      token === "velho"
        ? new Promise((_res, rej) => {
            rejectOld = () => rej(new ApiError("invalid_token", "venceu", 401));
          })
        : Promise.resolve({}),
    );
    window.localStorage.setItem(KEY, JSON.stringify({ token: "velho", email: "v@b.com" }));
    renderProvider();
    await waitFor(() => expect(get).toHaveBeenCalledWith("/me", "velho"));

    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
    await act(async () => rejectOld());

    expect(screen.getByTestId("token")).toHaveTextContent("tok-novo");
    expect(stored().token).toBe("tok-novo");
  });
});
