import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import AuthProvider from "../components/AuthProvider.jsx";
import { axeViolations } from "../test/axe.js";
import { apiError, lerSessao, mockApi } from "../test/mockApi.js";
import Login from "./Login.jsx";

function renderLogin(props = { mode: "login" }) {
  return render(
    <AuthProvider>
      <Login {...props} />
    </AuthProvider>,
  );
}

const campoEmail = () => screen.getByLabelText("E-mail");
const campoSenha = () => screen.getByLabelText("Senha");
const enviar = (nome) => screen.getByRole("button", { name: nome });
const EMAIL_INVALIDO = "Digite um e-mail válido, como voce@exemplo.com.";

async function preencher(user, email, senha) {
  if (email) await user.type(campoEmail(), email);
  if (senha) await user.type(campoSenha(), senha);
}

describe("Login (entrar)", () => {
  it("mostra o formulário de entrada, com a aba Entrar marcada", () => {
    mockApi();
    renderLogin();

    expect(screen.getByRole("heading", { name: "Entre na sua conta" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Entrar" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Criar conta" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
    expect(enviar("Entrar")).toBeEnabled();
    expect(screen.queryByText("Mínimo de 8 caracteres.")).not.toBeInTheDocument();
  });

  it("não mostra erro antes da primeira tentativa de enviar", async () => {
    mockApi();
    const user = userEvent.setup();
    renderLogin();

    await user.type(campoEmail(), "isso-nao-e-email");

    expect(screen.queryByText(EMAIL_INVALIDO)).not.toBeInTheDocument();
    expect(campoEmail()).toHaveAttribute("aria-invalid", "false");
  });

  it("campos vazios: mostra os dois erros no lugar e não chama a API", async () => {
    const api = mockApi();
    const user = userEvent.setup();
    renderLogin();

    await user.click(enviar("Entrar"));

    expect(screen.getByText(EMAIL_INVALIDO)).toBeInTheDocument();
    expect(screen.getByText("Digite sua senha.")).toBeInTheDocument();
    expect(campoEmail()).toHaveAttribute("aria-invalid", "true");
    expect(campoSenha()).toHaveAttribute("aria-invalid", "true");
    expect(api.calls()).toEqual([]);
    expect(window.location.hash).toBe("");
  });

  it.each(["sem-arroba.com", "voce@semponto", "voce @exemplo.com", "@exemplo.com"])(
    "e-mail %j é recusado antes de enviar",
    async (email) => {
      const api = mockApi();
      const user = userEvent.setup();
      renderLogin();

      await preencher(user, email, "qualquer");
      await user.click(enviar("Entrar"));

      expect(screen.getByText(EMAIL_INVALIDO)).toBeInTheDocument();
      expect(screen.queryByText("Digite sua senha.")).not.toBeInTheDocument();
      expect(api.calls()).toEqual([]);
    },
  );

  it("ao entrar não exige o mínimo de 8 caracteres (só que a senha não esteja vazia)", async () => {
    const api = mockApi({
      "POST /auth/login": { body: { access_token: "jwt-123", token_type: "bearer" } },
    });
    const user = userEvent.setup();
    renderLogin();

    await preencher(user, "voce@exemplo.com", "curta");
    await user.click(enviar("Entrar"));

    expect(api.calls("POST /auth/login")).toHaveLength(1);
  });

  it("entra: envia e-mail e senha, guarda a sessão e abre o perfil", async () => {
    const api = mockApi({
      "POST /auth/login": { body: { access_token: "jwt-123", token_type: "bearer" } },
      "GET /me": { body: {} },
    });
    const user = userEvent.setup();
    renderLogin();

    // O e-mail é aparado antes de enviar e guardado em minúsculas.
    await preencher(user, "  Voce@Exemplo.com ", "senha-longa-1");
    await user.click(enviar("Entrar"));

    const [chamada] = api.calls("POST /auth/login");
    expect(chamada.body).toEqual({ email: "Voce@Exemplo.com", password: "senha-longa-1" });
    expect(chamada.authorization).toBeNull();
    expect(lerSessao()).toEqual({ token: "jwt-123", email: "voce@exemplo.com" });
    expect(window.location.hash).toBe("#/perfil");
  });

  it("volta para a tela pedida em `depois` (next) depois de entrar", async () => {
    mockApi({
      "POST /auth/login": { body: { access_token: "jwt-123", token_type: "bearer" } },
      "GET /me": { body: {} },
    });
    const user = userEvent.setup();
    renderLogin({ mode: "login", next: "/analise/abc123" });

    await preencher(user, "voce@exemplo.com", "senha-longa-1");
    await user.click(enviar("Entrar"));

    expect(window.location.hash).toBe("#/analise/abc123");
  });

  it("as abas carregam o destino `depois` para o outro modo", () => {
    mockApi();
    renderLogin({ mode: "login", next: "/relatorio/ABCDEF" });

    expect(screen.getByRole("tab", { name: "Entrar" })).toHaveAttribute(
      "href",
      "#/entrar?modo=login&depois=%2Frelatorio%2FABCDEF",
    );
    expect(screen.getByRole("tab", { name: "Criar conta" })).toHaveAttribute(
      "href",
      "#/entrar?modo=cadastro&depois=%2Frelatorio%2FABCDEF",
    );
  });

  it("e-mail ou senha errados: mostra a mensagem do servidor, sem sair da tela", async () => {
    mockApi({
      "POST /auth/login": apiError(401, "invalid_credentials", "E-mail ou senha incorretos."),
    });
    const user = userEvent.setup();
    renderLogin();

    await preencher(user, "voce@exemplo.com", "senha-errada");
    await user.click(enviar("Entrar"));

    expect(await screen.findByRole("alert")).toHaveTextContent("E-mail ou senha incorretos.");
    expect(enviar("Entrar")).toBeEnabled();
    expect(lerSessao()).toBeNull();
    expect(window.location.hash).toBe("");
    // O que a pessoa digitou continua lá para corrigir.
    expect(campoEmail()).toHaveValue("voce@exemplo.com");
  });

  it("servidor fora do ar: mostra a mensagem de rede e deixa tentar de novo", async () => {
    const api = mockApi({ "POST /auth/login": new TypeError("Failed to fetch") });
    const user = userEvent.setup();
    renderLogin();

    await preencher(user, "voce@exemplo.com", "senha-longa-1");
    await user.click(enviar("Entrar"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "O servidor do LogCoach não respondeu. Confira sua conexão e tente de novo.",
    );
    api.set("POST /auth/login", { body: { access_token: "jwt-9" } });
    api.set("GET /me", { body: {} });
    await user.click(enviar("Entrar"));
    await waitFor(() => expect(window.location.hash).toBe("#/perfil"));
    expect(lerSessao()?.token).toBe("jwt-9");
  });

  it("erro inesperado do servidor (500 sem código) vira a mensagem de erro nosso", async () => {
    mockApi({
      "POST /auth/login": { status: 500, body: "<html>Internal Server Error</html>", html: true },
    });
    const user = userEvent.setup();
    renderLogin();

    await preencher(user, "voce@exemplo.com", "senha-longa-1");
    await user.click(enviar("Entrar"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Erro inesperado no LogCoach. O problema é nosso, não do seu relatório.",
    );
  });

  it("enquanto envia, o botão fica desabilitado e diz 'Enviando…'", async () => {
    let liberar;
    mockApi({
      "POST /auth/login": () =>
        new Promise((resolve) => {
          liberar = () => resolve({ body: { access_token: "jwt-1" } });
        }),
      "GET /me": { body: {} },
    });
    const user = userEvent.setup();
    renderLogin();

    await preencher(user, "voce@exemplo.com", "senha-longa-1");
    await user.click(enviar("Entrar"));

    expect(screen.getByRole("button", { name: "Enviando…" })).toBeDisabled();
    liberar();
    await waitFor(() => expect(window.location.hash).toBe("#/perfil"));
  });

  it("sem violações de acessibilidade, com e sem erros na tela", async () => {
    mockApi();
    const user = userEvent.setup();
    const { container } = renderLogin();
    expect(await axeViolations(container)).toEqual([]);

    await user.click(enviar("Entrar"));
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("Login (criar conta)", () => {
  const cadastro = { mode: "cadastro" };

  it("mostra o convite, o limite grátis e a dica da senha", () => {
    mockApi();
    renderLogin(cadastro);

    expect(screen.getByRole("heading", { name: "Crie sua conta grátis" })).toBeInTheDocument();
    expect(screen.getByText(/faz até 5 análises por mês/)).toBeInTheDocument();
    expect(screen.getByText("Mínimo de 8 caracteres.")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Criar conta" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(enviar("Criar conta")).toBeEnabled();
  });

  it("senha com menos de 8 caracteres é recusada antes de enviar", async () => {
    const api = mockApi();
    const user = userEvent.setup();
    renderLogin(cadastro);

    await preencher(user, "voce@exemplo.com", "1234567");
    await user.click(enviar("Criar conta"));

    expect(screen.getByText("A senha precisa ter pelo menos 8 caracteres.")).toBeInTheDocument();
    // O erro substitui a dica (não ficam os dois).
    expect(screen.queryByText("Mínimo de 8 caracteres.")).not.toBeInTheDocument();
    expect(campoSenha()).toHaveAttribute("aria-invalid", "true");
    expect(api.calls()).toEqual([]);
  });

  it("com 8 caracteres cria a conta, já entra e abre o perfil", async () => {
    const api = mockApi({
      "POST /auth/register": { status: 201, body: { access_token: "jwt-novo" } },
      "GET /me": { body: {} },
    });
    const user = userEvent.setup();
    renderLogin(cadastro);

    await preencher(user, "Nova@Exemplo.com", "12345678");
    await user.click(enviar("Criar conta"));

    expect(api.calls("POST /auth/register")[0].body).toEqual({
      email: "Nova@Exemplo.com",
      password: "12345678",
    });
    expect(api.calls("POST /auth/login")).toEqual([]);
    expect(lerSessao()).toEqual({ token: "jwt-novo", email: "nova@exemplo.com" });
    expect(window.location.hash).toBe("#/perfil");
  });

  it("e-mail já cadastrado: mostra a mensagem do servidor", async () => {
    mockApi({
      "POST /auth/register": apiError(
        409,
        "email_taken",
        "Já existe uma conta com esse e-mail. Tente entrar.",
      ),
    });
    const user = userEvent.setup();
    renderLogin(cadastro);

    await preencher(user, "voce@exemplo.com", "12345678");
    await user.click(enviar("Criar conta"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Já existe uma conta com esse e-mail. Tente entrar.",
    );
    expect(lerSessao()).toBeNull();
  });

  it("depois de criar a conta, volta para onde a pessoa estava (ex.: a escolha da luta)", async () => {
    mockApi({
      "POST /auth/register": { status: 201, body: { access_token: "jwt-novo" } },
      "GET /me": { body: {} },
    });
    const user = userEvent.setup();
    renderLogin({ mode: "cadastro", next: "/relatorio/XhrmBaYkGCAQjH2D" });

    await preencher(user, "voce@exemplo.com", "12345678");
    await user.click(enviar("Criar conta"));

    expect(window.location.hash).toBe("#/relatorio/XhrmBaYkGCAQjH2D");
  });

  it("sem violações de acessibilidade, com e sem erros na tela", async () => {
    mockApi();
    const user = userEvent.setup();
    const { container } = renderLogin(cadastro);
    expect(await axeViolations(container)).toEqual([]);

    await user.click(enviar("Criar conta"));
    expect(await axeViolations(container)).toEqual([]);
  });
});
