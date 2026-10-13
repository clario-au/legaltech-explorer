"""Regression tests for the October 2026 audit fixes (round 1)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from starlette.requests import Request


def make_request(headers: dict, client_host: str = "10.0.0.1") -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (client_host, 1234),
    }
    return Request(scope)


# ---------- Client IP / rate limiting ----------

def test_client_ip_prefers_cloudflare_header(api):
    req = make_request({"CF-Connecting-IP": "203.0.113.7", "X-Forwarded-For": "1.1.1.1, 198.51.100.2"})
    assert api.get_client_ip(req) == "203.0.113.7"


def test_client_ip_ignores_spoofed_leftmost_forwarded_for(api):
    req = make_request({"X-Forwarded-For": "6.6.6.6, 198.51.100.2"})
    assert api.get_client_ip(req) == "198.51.100.2"


def test_client_ip_falls_back_to_socket_peer(api):
    assert api.get_client_ip(make_request({})) == "10.0.0.1"


def test_login_rate_limit_not_bypassed_by_rotating_forwarded_for(api, client, monkeypatch):
    monkeypatch.setattr(api, "sign_in", lambda email, pw: {"error": "Invalid email or password"})
    limit, _ = api.AUTH_RATE_LIMITS["login"]
    codes = []
    for i in range(limit + 1):
        r = client.post(
            "/auth/login",
            json={"email": "victim@example.com", "password": "guess"},
            headers={"X-Forwarded-For": f"10.9.9.{i}, 198.51.100.2"},
        )
        codes.append(r.status_code)
    assert codes[:limit] == [401] * limit
    assert codes[limit] == 429


# ---------- Cookies ----------

def test_cookies_secure_by_default(api, monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert api.get_cookie_secure() is True


def test_cookies_insecure_only_for_explicit_local_development(api, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert api.get_cookie_secure() is False


def test_login_sets_secure_httponly_cookies(api, client, monkeypatch):
    monkeypatch.setattr(api, "sign_in", lambda e, p: {
        "user": {"email": e, "role": "authenticated"},
        "session": {"access_token": "acc", "refresh_token": "ref"},
    })
    r = client.post("/auth/login", json={"email": "a@example.com", "password": "pw123456"})
    assert r.status_code == 200
    cookies = r.headers.get_list("set-cookie")
    assert len(cookies) == 2
    for c in cookies:
        assert "HttpOnly" in c and "Secure" in c


# ---------- /tools ----------

def fake_tools_client(rows):
    table = MagicMock()
    table.select.return_value.execute.return_value = SimpleNamespace(data=rows)
    admin = MagicMock()
    admin.table.return_value = table
    return admin, table


def test_tools_selects_explicit_columns_without_embedding(api, client, monkeypatch):
    admin, table = fake_tools_client([{"Vendor Name": "Clio", "Product Name": "Clio Manage"}])
    monkeypatch.setattr(api, "supabase_admin", admin)

    r = client.get("/tools")

    assert r.status_code == 200
    select_arg = table.select.call_args.args[0]
    assert select_arg != "*"
    assert "embedding" not in select_arg
    assert '"Approx. Price Range (AUD)"' in select_arg
    assert r.json()["tools"][0]["Vendor Name"] == "Clio"
    assert "__logo_url" in r.json()["tools"][0]


def test_tools_response_is_cached(api, client, monkeypatch):
    admin, table = fake_tools_client([{"Vendor Name": "Clio"}])
    monkeypatch.setattr(api, "supabase_admin", admin)

    client.get("/tools")
    client.get("/tools")

    assert table.select.return_value.execute.call_count == 1


# ---------- Admin user status ----------

@pytest.fixture
def as_admin(api):
    api.app.dependency_overrides[api.require_admin] = lambda: {"id": "admin-id", "email": "admin@example.com", "role": "admin"}
    yield
    api.app.dependency_overrides.clear()


def test_disable_user_updates_supabase_without_legacy_table(api, client, as_admin, monkeypatch):
    calls = []
    monkeypatch.setattr(api, "admin_set_user_status", lambda email, status: calls.append((email, status)) or {"success": True})

    r = client.post("/admin/users/someone@example.com/status", json={"status": "disabled"})

    assert r.status_code == 200
    assert calls == [("someone@example.com", "disabled")]


def test_disable_unknown_user_returns_404(api, client, as_admin, monkeypatch):
    monkeypatch.setattr(api, "admin_set_user_status", lambda e, s: {"error": "User not found", "not_found": True})
    r = client.post("/admin/users/nobody@example.com/status", json={"status": "disabled"})
    assert r.status_code == 404


def test_admin_user_list_comes_from_supabase_with_usage_counts(api, client, as_admin, monkeypatch):
    monkeypatch.setattr(api, "admin_list_users", lambda: {"users": [
        {"id": "1", "email": "a@example.com", "role": "user", "status": "active"},
        {"id": "2", "email": "b@example.com", "role": "user", "status": "disabled"},
    ]})
    monkeypatch.setattr(api, "get_usage_counts", lambda: {"b@example.com": {"total_requests": 5, "last_request": "2026-10-13"}})

    users = client.get("/admin/users").json()["users"]

    assert [u["email"] for u in users] == ["b@example.com", "a@example.com"]
    assert users[0]["total_requests"] == 5 and users[1]["total_requests"] == 0


# ---------- Logout ----------

def test_logout_revokes_callers_own_session(api, client, monkeypatch):
    calls = []
    monkeypatch.setattr(api, "sign_out", lambda access, refresh=None: calls.append((access, refresh)) or {"success": True})
    client.cookies.set("sb_access_token", "acc-123")
    client.cookies.set("sb_refresh_token", "ref-456")

    r = client.post("/auth/logout")

    assert r.status_code == 200
    assert calls == [("acc-123", "ref-456")]


def test_sign_out_uses_admin_logout_with_local_scope(monkeypatch):
    import supabase_auth
    admin = MagicMock()
    monkeypatch.setattr(supabase_auth, "supabase_admin", admin)
    monkeypatch.setattr(supabase_auth, "get_user_from_token", lambda t: {"id": "u1"})

    assert supabase_auth.sign_out("acc-123") == {"success": True}
    admin.auth.admin.sign_out.assert_called_once_with("acc-123", "local")


def test_sign_out_with_expired_access_token_revokes_via_refresh(monkeypatch):
    import supabase_auth
    admin = MagicMock()
    monkeypatch.setattr(supabase_auth, "supabase_admin", admin)
    monkeypatch.setattr(supabase_auth, "get_user_from_token", lambda t: None)
    monkeypatch.setattr(supabase_auth, "refresh_session", lambda r: {"session": {"access_token": "fresh"}})

    supabase_auth.sign_out("expired", "ref-456")
    admin.auth.admin.sign_out.assert_called_once_with("fresh", "local")


def test_sign_in_never_stores_session_on_shared_client(monkeypatch):
    import supabase_auth
    shared = MagicMock()
    fresh = MagicMock()
    fresh.auth.sign_in_with_password.return_value = SimpleNamespace(
        user=SimpleNamespace(id="u1", email="a@example.com", role="authenticated", created_at="t"),
        session=SimpleNamespace(access_token="acc", refresh_token="ref", expires_at=1),
    )
    monkeypatch.setattr(supabase_auth, "supabase", shared)
    monkeypatch.setattr(supabase_auth, "_auth_client", lambda: fresh)

    result = supabase_auth.sign_in("a@example.com", "pw")

    assert result["session"]["access_token"] == "acc"
    shared.auth.sign_in_with_password.assert_not_called()


def test_shared_clients_hold_no_session_state():
    import supabase_auth
    for c in (supabase_auth.supabase, supabase_auth.supabase_admin):
        assert c.auth._auto_refresh_token is False
        assert c.auth._persist_session is False


def test_find_user_by_email_pages_past_first_50(monkeypatch):
    import supabase_auth
    page1 = [SimpleNamespace(email=f"u{i}@example.com") for i in range(supabase_auth.ADMIN_PAGE_SIZE)]
    page2 = [SimpleNamespace(email="Late@Example.com")]
    admin = MagicMock()
    admin.auth.admin.list_users.side_effect = lambda page, per_page: page1 if page == 1 else page2
    monkeypatch.setattr(supabase_auth, "supabase_admin", admin)

    assert supabase_auth.find_user_by_email("late@example.com") is page2[0]


# ---------- Usage logging ----------

def test_log_usage_never_raises(monkeypatch):
    import usage_store
    admin = MagicMock()
    admin.table.return_value.insert.return_value.execute.side_effect = RuntimeError("table missing")
    monkeypatch.setattr(usage_store, "supabase_admin", admin)

    usage_store.log_usage("uuid-1", "a@example.com", "/search", "contract review")  # must not raise


def test_search_still_works_when_usage_logging_fails(api, client, monkeypatch):
    api.app.dependency_overrides[api.rate_limit_dependency] = lambda: {"id": "uuid-1", "email": "a@example.com"}
    try:
        monkeypatch.setattr(api, "log_usage", MagicMock(side_effect=None))
        admin = MagicMock()
        admin.rpc.return_value.execute.return_value = SimpleNamespace(data=[{"Vendor Name": "Clio", "similarity": 0.7}])
        monkeypatch.setattr(api, "supabase_admin", admin)
        monkeypatch.setattr(api.client.embeddings, "create", lambda **kw: SimpleNamespace(data=[SimpleNamespace(embedding=[0.1] * 3)]))

        r = client.post("/search", json={"query": "contract review"})

        assert r.status_code == 200
        assert r.json()["results"][0]["Vendor Name"] == "Clio"
        api.log_usage.assert_called_once_with("uuid-1", "a@example.com", "/search", "contract review")
    finally:
        api.app.dependency_overrides.clear()


# ---------- Logo path traversal ----------

def test_logo_lookup_cannot_escape_logos_dir(api, tmp_path, monkeypatch):
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"not a logo")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "logos").mkdir()
    assert api.get_logo_b64("../secret") is None
