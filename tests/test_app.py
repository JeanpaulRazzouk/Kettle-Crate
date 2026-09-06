from collections import defaultdict

from conftest import COMPLAINT_KWARGS


def test_chat_requires_session_and_message(client):
    assert client.post("/chat", json={}).status_code == 400


def test_chat_rejects_path_traversal_session_id(client):
    res = client.post("/chat", json={"session": "../../etc/passwd", "message": "hi"})
    assert res.status_code == 400
    assert "Invalid session" in res.get_json()["error"]


def test_chat_rejects_overlong_session_id(client):
    res = client.post("/chat", json={"session": "a" * 65, "message": "hi"})
    assert res.status_code == 400


def test_dashboard_requires_login(client):
    res = client.get("/dashboard")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_api_complaints_requires_login(client):
    assert client.get("/api/complaints").status_code == 302


def test_login_wrong_password(client):
    res = client.post("/login", data={"password": "wrong"})
    assert res.status_code == 200
    assert b"Wrong password" in res.data


def test_login_correct_password_then_dashboard(logged_in_client):
    assert logged_in_client.get("/dashboard").status_code == 200


def test_status_update_rejects_invalid_status(logged_in_client, isolated_store):
    saved = isolated_store.save_complaint("s1", COMPLAINT_KWARGS)
    res = logged_in_client.post(f"/api/complaints/{saved['id']}/status", json={"status": "bogus"})
    assert res.status_code == 400


def test_status_update_success(logged_in_client, isolated_store):
    saved = isolated_store.save_complaint("s1", COMPLAINT_KWARGS)
    res = logged_in_client.post(f"/api/complaints/{saved['id']}/status", json={"status": "resolved"})
    assert res.status_code == 200
    assert res.get_json()["complaint"]["status"] == "resolved"


def test_draft_reply_404_for_unknown_complaint(logged_in_client, monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "draft_reply", lambda c: "should not be called")
    res = logged_in_client.post("/api/complaints/does-not-exist/draft-reply")
    assert res.status_code == 404


def test_draft_reply_success(logged_in_client, isolated_store, monkeypatch):
    import app as app_module

    saved = isolated_store.save_complaint("s1", COMPLAINT_KWARGS)
    monkeypatch.setattr(app_module, "draft_reply", lambda c: "Hi Ann, sorry about that!")
    res = logged_in_client.post(f"/api/complaints/{saved['id']}/draft-reply")
    assert res.status_code == 200
    assert res.get_json()["draft"] == "Hi Ann, sorry about that!"


def test_rate_limit_blocks_after_threshold(client, monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "RATE_LIMIT_MAX", 3)
    monkeypatch.setattr(app_module, "_rate_buckets", defaultdict(list))
    monkeypatch.setattr(app_module, "chat", lambda session_id, message: ("ok", False, "name"))

    for _ in range(3):
        res = client.post("/chat", json={"session": "abcdef012345", "message": "hi"})
        assert res.status_code == 200

    res = client.post("/chat", json={"session": "abcdef012345", "message": "hi"})
    assert res.status_code == 429
