CREDENTIALS = {"email": "Jogador@Exemplo.com", "password": "senha-forte-1"}


def test_register_returns_token(client):
    response = client.post("/auth/register", json=CREDENTIALS)

    assert response.status_code == 201
    assert response.json()["access_token"]


def test_register_rejects_duplicate_email_ignoring_case(client):
    client.post("/auth/register", json=CREDENTIALS)

    response = client.post(
        "/auth/register", json={"email": "jogador@exemplo.com", "password": "outra-senha-1"}
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "email_taken"


def test_register_rejects_short_password_and_bad_email(client):
    short = client.post("/auth/register", json={"email": "a@exemplo.com", "password": "123"})
    bad_email = client.post("/auth/register", json={"email": "nao-e-email", "password": "x" * 10})

    assert short.status_code == 422
    assert bad_email.status_code == 422


def test_password_is_not_stored_in_plain_text(client, engine):
    from sqlmodel import Session, select

    from app.models import User

    client.post("/auth/register", json=CREDENTIALS)

    with Session(engine) as session:
        user = session.exec(select(User)).one()
    assert CREDENTIALS["password"] not in user.password_hash
    assert user.password_hash.startswith("$argon2")


def test_login_with_right_and_wrong_password(client):
    client.post("/auth/register", json=CREDENTIALS)

    ok = client.post("/auth/login", json=CREDENTIALS)
    wrong = client.post("/auth/login", json={**CREDENTIALS, "password": "senha-errada"})
    unknown = client.post("/auth/login", json={"email": "x@exemplo.com", "password": "qualquer"})

    assert ok.status_code == 200
    assert wrong.status_code == 401
    # Mesma resposta para e-mail inexistente: não revela quem tem conta.
    assert unknown.json() == wrong.json()


def test_me_requires_valid_token(client, auth_headers):
    me = client.get("/me", headers=auth_headers)
    no_token = client.get("/me")
    bad_token = client.get("/me", headers={"Authorization": "Bearer token-falso"})

    assert me.status_code == 200
    assert me.json()["email"] == "jogador@exemplo.com"
    assert me.json()["analyses_this_month"] == 0
    assert me.json()["monthly_limit"] == 5
    assert no_token.status_code == 401
    assert bad_token.status_code == 401


def test_change_password(client, auth_headers):
    wrong = client.put(
        "/me/password",
        headers=auth_headers,
        json={"current_password": "errada", "new_password": "nova-senha-123"},
    )
    ok = client.put(
        "/me/password",
        headers=auth_headers,
        json={"current_password": "senha-forte-1", "new_password": "nova-senha-123"},
    )
    login = client.post(
        "/auth/login", json={"email": "jogador@exemplo.com", "password": "nova-senha-123"}
    )

    assert wrong.status_code == 400
    assert ok.status_code == 204
    assert login.status_code == 200
