import json

import pytest

from conftest import COMPLAINT_KWARGS


def test_save_and_load_complaint(isolated_store):
    saved = isolated_store.save_complaint("sess-1", dict(COMPLAINT_KWARGS, urgency="high"))
    assert saved["status"] == "new"
    assert saved["urgency"] == "high"
    assert saved["is_repeat"] is False

    loaded = isolated_store.load_complaints()
    assert len(loaded) == 1
    assert loaded[0]["name"] == "Ann Example"
    assert loaded[0]["order_no"] == "KC-1"


def test_repeat_customer_detection_is_case_insensitive(isolated_store):
    isolated_store.save_complaint("sess-1", COMPLAINT_KWARGS)
    second = isolated_store.save_complaint(
        "sess-2", dict(COMPLAINT_KWARGS, email="ANN@EXAMPLE.com", order_number="KC-2")
    )
    assert second["is_repeat"] is True


def test_invalid_urgency_defaults_to_normal(isolated_store):
    saved = isolated_store.save_complaint("sess-1", dict(COMPLAINT_KWARGS, urgency="extremely-mad"))
    assert saved["urgency"] == "normal"


def test_update_status(isolated_store):
    saved = isolated_store.save_complaint("sess-1", COMPLAINT_KWARGS)
    updated = isolated_store.update_status(saved["id"], "resolved")
    assert updated["status"] == "resolved"
    assert isolated_store.update_status("does-not-exist", "resolved") is None


def test_update_status_rejects_invalid_value(isolated_store):
    with pytest.raises(ValueError):
        isolated_store.update_status("anything", "not-a-real-status")


def test_get_complaint(isolated_store):
    saved = isolated_store.save_complaint("sess-1", COMPLAINT_KWARGS)
    assert isolated_store.get_complaint(saved["id"])["name"] == "Ann Example"
    assert isolated_store.get_complaint("nope") is None


def test_read_log_rejects_path_traversal(isolated_store):
    # A crafted id used as a filename component is exactly the hole that got
    # closed after finding it while building the conversation-viewer feature.
    with open(isolated_store.COMPLAINTS_FILE, "w") as f:
        json.dump([{"id": "../../etc/passwd", "name": "Evil"}], f)
    assert isolated_store.read_log("../../etc/passwd") is None


def test_read_log_parses_lines(isolated_store):
    saved = isolated_store.save_complaint("safe-session-1", COMPLAINT_KWARGS)
    log_path = f"{isolated_store.LOGS_DIR}/chat_safe-session-1.log"
    with open(log_path, "w") as f:
        f.write("[2026-01-01 10:00:00] USER: hello\n")
        f.write("[2026-01-01 10:00:01] BOT: hi there\n")

    assert isolated_store.read_log(saved["id"]) == [
        {"time": "2026-01-01 10:00:00", "who": "USER", "text": "hello"},
        {"time": "2026-01-01 10:00:01", "who": "BOT", "text": "hi there"},
    ]


def test_read_log_missing_file_returns_none(isolated_store):
    saved = isolated_store.save_complaint("no-log-for-this-one", COMPLAINT_KWARGS)
    assert isolated_store.read_log(saved["id"]) is None


def test_stats(isolated_store):
    isolated_store.save_complaint("s1", COMPLAINT_KWARGS)
    c2 = isolated_store.save_complaint("s2", dict(COMPLAINT_KWARGS, email="b@b.com"))
    isolated_store.update_status(c2["id"], "resolved")
    assert isolated_store.stats() == {"total": 2, "new": 1, "contacted": 0, "resolved": 1}
