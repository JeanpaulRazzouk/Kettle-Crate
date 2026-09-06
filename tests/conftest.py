import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DASHBOARD_PASSWORD", "test-password")
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret")
os.environ.setdefault("PROVIDER", "anthropic")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")
os.environ.setdefault("MODEL", "test-model")

import pytest


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    """Points store.py (and bot.py's logging) at a throwaway complaints.json
    and logs/ dir, so tests never read or write real customer data."""
    import store

    complaints_file = tmp_path / "complaints.json"
    complaints_file.write_text("[]")
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    monkeypatch.setattr(store, "COMPLAINTS_FILE", str(complaints_file))
    monkeypatch.setattr(store, "LOGS_DIR", str(logs_dir))

    import bot

    monkeypatch.setattr(bot, "LOGS_DIR", str(logs_dir))

    return store


@pytest.fixture
def client(isolated_store, monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "DASHBOARD_PASSWORD", "test-password")
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture
def logged_in_client(client):
    client.post("/login", data={"password": "test-password"})
    return client


COMPLAINT_KWARGS = dict(
    name="Ann Example",
    email="ann@example.com",
    order_number="KC-1",
    item="Kettle",
    issue="Arrived cracked",
    resolution="Refund",
    phone="555-0000",
)
