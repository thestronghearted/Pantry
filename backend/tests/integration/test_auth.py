from .conftest import signup


def test_signup_logs_in_and_me_returns_household(client):
    data = signup(client)
    assert data["household"]["name"] == "The Smiths"
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "family@example.com"


def test_session_cookie_is_httponly_and_samesite_lax(client):
    r = client.post(
        "/api/auth/signup",
        json={"household_name": "H", "email": "cookie@example.com", "password": "a-long-enough-password"},
    )
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_duplicate_email_is_409_case_insensitive(client, make_client):
    signup(client, email="Dup@Example.com")
    r = make_client().post(
        "/api/auth/signup", json={"household_name": "X", "email": "dup@example.com", "password": "another-long-password"}
    )
    assert r.status_code == 409


def test_short_password_rejected(client):
    r = client.post("/api/auth/signup", json={"household_name": "H", "email": "a@example.com", "password": "short"})
    assert r.status_code == 422


def test_login_logout_cycle(client, make_client):
    signup(client)
    other = make_client()
    ok = other.post("/api/auth/login", json={"email": "family@example.com", "password": "correct-horse-battery"})
    assert ok.status_code == 200
    assert other.get("/api/auth/me").status_code == 200
    other.post("/api/auth/logout")
    assert other.get("/api/auth/me").status_code == 401


def test_wrong_password_and_unknown_email_look_identical(client, make_client):
    signup(client)
    other = make_client()
    wrong = other.post("/api/auth/login", json={"email": "family@example.com", "password": "not-the-password"})
    unknown = other.post("/api/auth/login", json={"email": "nobody@example.com", "password": "not-the-password"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_password_is_stored_as_argon2_hash(app, client):
    from sqlalchemy import select

    from app.models import User

    signup(client)
    with app.state.session_factory() as s:
        stored = s.scalar(select(User.password_hash).where(User.email == "family@example.com"))
    assert stored.startswith("$argon2")
    assert "correct-horse-battery" not in stored


def test_data_endpoints_require_a_session(client):
    for method, url in [
        ("get", "/api/members"),
        ("get", "/api/recipes"),
        ("get", "/api/plan?week=2026-11-02"),
        ("get", "/api/shopping-list?week=2026-11-02"),
        ("post", "/api/plan/generate"),
    ]:
        assert getattr(client, method)(url).status_code == 401, url


def test_rate_limit_after_ten_attempts(client):
    codes = [
        client.post("/api/auth/login", json={"email": "x@example.com", "password": "whatever-it-is"}).status_code
        for _ in range(12)
    ]
    assert codes[:10] == [401] * 10
    assert codes[10:] == [429, 429]


def test_delete_household_removes_everything(app, family):
    from sqlalchemy import func, select

    from app.models import Household, Member, User
    from .conftest import generate

    client, _ = family
    generate(client)
    bad = client.request("DELETE", "/api/auth/household", json={"password": "wrong-password-here"})
    assert bad.status_code == 403
    ok = client.request("DELETE", "/api/auth/household", json={"password": "correct-horse-battery"})
    assert ok.status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    with app.state.session_factory() as s:
        assert s.scalar(select(func.count()).select_from(Member).where(Member.name == "Alex")) == 0
        assert s.scalar(select(func.count()).select_from(User).where(User.email == "family@example.com")) == 0
        assert s.scalar(select(func.count()).select_from(Household).where(Household.name == "The Smiths")) == 0
