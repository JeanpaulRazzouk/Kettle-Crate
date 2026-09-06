import json
import os
import re
import uuid
from datetime import datetime

COMPLAINTS_FILE = os.path.join(os.path.dirname(__file__), "complaints.json")
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
VALID_STATUSES = ["new", "contacted", "resolved"]

# Mirrors the session id format app.py already validates on the way in —
# enforced again here since older complaints were written before that check
# existed, and this id gets interpolated straight into a log file path.
_SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_LOG_LINE = re.compile(r"^\[(?P<time>[^\]]+)\]\s(?P<who>USER|BOT):\s(?P<text>.*)$")


def _read_raw():
    if not os.path.exists(COMPLAINTS_FILE):
        return []
    with open(COMPLAINTS_FILE) as f:
        return json.load(f)


def _write_raw(complaints):
    with open(COMPLAINTS_FILE, "w") as f:
        json.dump(complaints, f, indent=2)


def _normalize(entry):
    return {
        "id": str(entry.get("id")),
        "date": entry.get("date") or "",
        "name": entry.get("name") or "",
        "email": entry.get("email") or "",
        "order_no": entry.get("order_no") or "",
        "item": entry.get("item") or "",
        "issue": entry.get("issue") or "",
        "resolution": entry.get("resolution") or "",
        "phone": entry.get("phone") or "",
        "urgency": entry.get("urgency") if entry.get("urgency") in ("normal", "high") else "normal",
        "is_repeat": bool(entry.get("is_repeat")),
        "status": entry.get("status") if entry.get("status") in VALID_STATUSES else "new",
    }


def load_complaints():
    """All complaints, newest first, with a consistent shape regardless of how old the record is."""
    complaints = [_normalize(e) for e in _read_raw()]
    complaints.sort(key=lambda c: c["date"], reverse=True)
    return complaints


def save_complaint(session_id, data):
    complaints = _read_raw()

    email = (data.get("email") or "").strip().lower()
    is_repeat = bool(email) and any((c.get("email") or "").strip().lower() == email for c in complaints)

    complaint = {
        "id": uuid.uuid4().hex[:8],
        "session_id": session_id,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "name": data.get("name"),
        "email": data.get("email"),
        "order_no": data.get("order_number"),
        "item": data.get("item"),
        "issue": data.get("issue"),
        "resolution": data.get("resolution"),
        "phone": data.get("phone"),
        "urgency": data.get("urgency") if data.get("urgency") in ("normal", "high") else "normal",
        "is_repeat": is_repeat,
        "status": "new",
    }
    complaints.append(complaint)
    _write_raw(complaints)
    return complaint


def get_complaint(complaint_id):
    return next((c for c in load_complaints() if c["id"] == str(complaint_id)), None)


def read_log(complaint_id):
    """Parsed [{time, who, text}] transcript for a complaint's session, or None."""
    entry = next((c for c in _read_raw() if str(c.get("id")) == str(complaint_id)), None)
    if entry is None:
        return None

    # Complaints filed before the id/session split used the session id as
    # the complaint id directly, so fall back to that for older records.
    session_id = str(entry.get("session_id") or entry.get("id") or "")
    if not _SAFE_SESSION_ID.match(session_id):
        return None

    path = os.path.join(LOGS_DIR, f"chat_{session_id}.log")
    if not os.path.exists(path):
        return None

    lines = []
    with open(path) as f:
        for raw_line in f:
            m = _LOG_LINE.match(raw_line.rstrip("\n"))
            if m:
                lines.append(m.groupdict())
    return lines


def update_status(complaint_id, new_status):
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")

    complaints = _read_raw()
    updated = None
    for c in complaints:
        if str(c.get("id")) == str(complaint_id):
            c["status"] = new_status
            updated = c
            break

    if updated is None:
        return None

    _write_raw(complaints)
    return _normalize(updated)


def stats():
    complaints = load_complaints()
    counts = {"total": len(complaints), "new": 0, "contacted": 0, "resolved": 0}
    for c in complaints:
        counts[c["status"]] += 1
    return counts
