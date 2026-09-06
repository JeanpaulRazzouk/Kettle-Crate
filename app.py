import hmac
import logging
import os
import re
import time
from collections import defaultdict
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from bot import chat, draft_reply
import store

load_dotenv(".env.example")  # holds the real local secrets, see .env.example itself

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")

DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")


def _missing_api_key():
    """(True, env var name) if the key for the configured provider isn't set
    — shown as a banner on the chat page instead of a silent fallback, so a
    fresh checkout that forgot to add a key is obvious immediately."""
    provider = os.getenv("PROVIDER", "openai")
    key_name = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    return not os.getenv(key_name), key_name

# The session id ends up in a log filename (logs/chat_<session>.log), so it
# must be restricted before it ever reaches that code path — otherwise a
# crafted session value could read or write outside the logs directory.
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Anyone can hit /chat with no login, and every message costs a real API
# call — a simple sliding-window limiter per IP keeps that from being spammed
# or run up into a real bill. In-memory is fine here: same tradeoff the rest
# of this app already makes (conversations, fallback_cases) for a single-process
# deploy, and it resets on restart same as they do.
_rate_buckets = defaultdict(list)
RATE_LIMIT_MAX = 30
RATE_LIMIT_WINDOW_SECONDS = 300


def _rate_limited(key):
    now = time.time()
    bucket = _rate_buckets[key]
    while bucket and bucket[0] < now - RATE_LIMIT_WINDOW_SECONDS:
        bucket.pop(0)
    if len(bucket) >= RATE_LIMIT_MAX:
        return True
    bucket.append(now)
    return False


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.route("/")
def index():
    missing_key, key_name = _missing_api_key()
    return render_template("index.html", missing_key=missing_key, key_name=key_name)


@app.route("/chat", methods=["POST"])
def chat_route():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session")
    message = data.get("message")
    if not session_id or not message:
        return jsonify({"error": "Missing session or message."}), 400
    if not SESSION_ID_RE.match(str(session_id)):
        return jsonify({"error": "Invalid session identifier."}), 400
    if _rate_limited(request.remote_addr):
        return jsonify({"error": "Too many messages — please slow down a little."}), 429

    try:
        reply, filed, current_field = chat(session_id, message)
    except Exception as exc:
        logging.error("Chat request failed: %s", exc.__class__.__name__)
        return jsonify({
            "error": (
                "The support bot could not reach the AI provider. "
                "Please check the configured API key and model."
            )
        }), 502

    return jsonify({"reply": reply, "filed": filed, "current_field": current_field})


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        attempt = request.form.get("password", "")
        if DASHBOARD_PASSWORD and hmac.compare_digest(attempt, DASHBOARD_PASSWORD):
            session["logged_in"] = True
            return redirect(request.args.get("next") or url_for("dashboard"))
        error = "Wrong password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/complaints")
@login_required
def api_complaints():
    return jsonify({"complaints": store.load_complaints(), "stats": store.stats()})


@app.route("/api/complaints/<complaint_id>/status", methods=["POST"])
@login_required
def api_update_status(complaint_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in store.VALID_STATUSES:
        return jsonify({"error": f"Status must be one of {store.VALID_STATUSES}"}), 400

    updated = store.update_status(complaint_id, new_status)
    if updated is None:
        return jsonify({"error": "Complaint not found."}), 404

    return jsonify({"complaint": updated})


@app.route("/api/complaints/<complaint_id>/draft-reply", methods=["POST"])
@login_required
def api_draft_reply(complaint_id):
    complaint = store.get_complaint(complaint_id)
    if complaint is None:
        return jsonify({"error": "Complaint not found."}), 404

    try:
        draft = draft_reply(complaint)
    except Exception as exc:
        logging.error("Draft reply failed: %s", exc.__class__.__name__)
        return jsonify({"error": "Could not generate a draft right now."}), 502

    return jsonify({"draft": draft})


@app.route("/api/complaints/<complaint_id>/log")
@login_required
def api_complaint_log(complaint_id):
    entries = store.read_log(complaint_id)
    if entries is None:
        return jsonify({"error": "No conversation log found for this complaint."}), 404

    return jsonify({"log": entries})


if __name__ == "__main__":
    if not DASHBOARD_PASSWORD:
        logging.warning("DASHBOARD_PASSWORD is not set — the dashboard cannot be logged into.")
    app.run(debug=True, host="0.0.0.0", port=9000)
