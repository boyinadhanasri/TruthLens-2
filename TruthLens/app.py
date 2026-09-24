"""TruthLens - Misinformation Triage Platform (Flask + SQLite, no auth, no external APIs)."""
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from flask import Flask, current_app, g, jsonify, render_template, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Set TRUTHLENS_DB to point at a persistent disk in deployment (e.g. /var/data/truthlens.db)
DEFAULT_DB = os.environ.get("TRUTHLENS_DB") or os.path.join(BASE_DIR, "data", "truthlens.db")

PLATFORMS = ["WhatsApp", "X", "Instagram", "Other"]
CATEGORIES = ["Politics", "Health", "Finance", "Other"]
STATUSES = ["Unverified", "Verified True", "False", "Misleading"]
SENSATIONAL_PHRASES = ["breaking", "shocking", "share before deleted"]
MAX_TEXT, MAX_LINK, MAX_NOTE = 5000, 500, 500

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    platform TEXT NOT NULL,
    category TEXT NOT NULL,
    source_link TEXT NOT NULL DEFAULT '',
    flags TEXT NOT NULL DEFAULT '[]',
    risk_level TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Unverified',
    reviewer_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


# ---------------------------------------------------------------- risk rules
def compute_flags(text, source_link):
    """Deterministic risk rules (no AI). Returns a list of flag names."""
    flags = []
    normalized = " ".join(text.lower().split())
    if any(phrase in normalized for phrase in SENSATIONAL_PHRASES):
        flags.append("Sensational")
    letters = [c for c in text if c.isalpha()]  # spaces, digits, punctuation ignored
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.5:
        flags.append("Shouting")
    if not (source_link or "").strip():
        flags.append("Unsourced")
    return flags


def risk_level_for(flags):
    if len(flags) >= 2:
        return "High Risk"
    return "Risk Flag" if len(flags) == 1 else "Low Risk"


# ------------------------------------------------------------------ helpers
def now_iso(offset_hours=0):
    t = datetime.now(timezone.utc) - timedelta(hours=offset_hours)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def row_to_dict(row):
    d = dict(row)
    d["flags"] = json.loads(d["flags"])
    return d


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
    return g.db


def insert_claim(db, text, platform, category, source_link,
                 status="Unverified", note="", created_at=None):
    flags = compute_flags(text, source_link)
    ts = created_at or now_iso()
    cur = db.execute(
        "INSERT INTO claims (text, platform, category, source_link, flags, risk_level,"
        " status, reviewer_note, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (text, platform, category, source_link, json.dumps(flags), risk_level_for(flags),
         status, note, ts, ts),
    )
    db.commit()
    return cur.lastrowid


DEMO_CLAIMS = [
    ("BREAKING: SHARE BEFORE DELETED - ALL BANK ACCOUNTS WILL BE FROZEN TOMORROW",
     "WhatsApp", "Finance", "", "False", "The bank confirmed no such freeze exists.", 30),
    ("Breaking: new voting deadline announced for the local election, share before deleted",
     "X", "Politics", "", "Unverified", "", 20),
    ("Vitamin C tablets cure the flu within 24 hours.",
     "WhatsApp", "Health", "", "Misleading",
     "Vitamin C may modestly shorten colds but does not cure the flu in a day.", 10),
    ("Shocking rise in online shopping scams reported this quarter.",
     "Instagram", "Finance", "https://example.org/scam-report", "Unverified", "", 6),
    ("The city library will extend weekend opening hours from October.",
     "Other", "Other", "https://example.org/library-notice", "Verified True",
     "Confirmed against the official council notice.", 4),
    ("A local bank announced new savings interest rates effective next month.",
     "X", "Finance", "https://example.org/bank-rates", "Unverified", "", 2),
]


def seed_demo(db):
    added = 0
    for text, platform, category, link, status, note, hours_ago in DEMO_CLAIMS:
        if db.execute("SELECT 1 FROM claims WHERE text = ?", (text,)).fetchone():
            continue
        insert_claim(db, text, platform, category, link, status, note, now_iso(hours_ago))
        added += 1
    return added


def validate_claim(data):
    if not isinstance(data, dict):
        return None, "Request body must be a JSON object."
    text = data.get("text")
    platform = data.get("platform")
    category = data.get("category")
    link = data.get("source_link") or ""
    if not isinstance(text, str) or not text.strip():
        return None, "Claim text is required."
    if len(text.strip()) > MAX_TEXT:
        return None, f"Claim text must be at most {MAX_TEXT} characters."
    if platform not in PLATFORMS:
        return None, "Platform must be one of: " + ", ".join(PLATFORMS) + "."
    if category not in CATEGORIES:
        return None, "Category must be one of: " + ", ".join(CATEGORIES) + "."
    if not isinstance(link, str) or len(link.strip()) > MAX_LINK:
        return None, f"Source link must be at most {MAX_LINK} characters."
    return {"text": text.strip(), "platform": platform,
            "category": category, "source_link": link.strip()}, None


# ---------------------------------------------------------------------- app
def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or DEFAULT_DB
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # reject oversized request bodies
    os.makedirs(os.path.dirname(app.config["DB_PATH"]), exist_ok=True)
    with sqlite3.connect(app.config["DB_PATH"]) as conn:  # auto-create DB + table
        conn.executescript(SCHEMA)

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        return resp

    def error(message, code):
        return jsonify({"error": message}), code

    @app.errorhandler(404)
    def not_found(_e):
        return error("Not found.", 404)

    @app.errorhandler(405)
    def not_allowed(_e):
        return error("Method not allowed. Claims cannot be edited after submission.", 405)

    @app.errorhandler(413)
    def too_large(_e):
        return error("Request body is too large.", 413)

    @app.errorhandler(500)
    def server_error(_e):
        return error("Something went wrong on the server.", 500)

    @app.get("/")
    def index():
        return render_template("index.html", platforms=PLATFORMS,
                               categories=CATEGORIES, statuses=STATUSES)

    @app.post("/api/claims")
    def create_claim():
        clean, err = validate_claim(request.get_json(silent=True))
        if err:
            return error(err, 400)
        db = get_db()
        new_id = insert_claim(db, clean["text"], clean["platform"],
                              clean["category"], clean["source_link"])
        row = db.execute("SELECT * FROM claims WHERE id = ?", (new_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201

    @app.get("/api/claims")
    def list_claims():
        category = request.args.get("category", "").strip()
        status = request.args.get("status", "").strip()
        where, params = [], []
        if category and category != "All":
            if category not in CATEGORIES:
                return error("Invalid category filter.", 400)
            where.append("category = ?")
            params.append(category)
        if status and status != "All":
            if status not in STATUSES:
                return error("Invalid status filter.", 400)
            where.append("status = ?")
            params.append(status)
        sql = "SELECT * FROM claims"
        if where:
            sql += " WHERE " + " AND ".join(where)  # fixed fragments only; values are bound
        # DP1: High Risk -> Risk Flag -> Low Risk, then newest first
        sql += (" ORDER BY CASE risk_level WHEN 'High Risk' THEN 0"
                " WHEN 'Risk Flag' THEN 1 ELSE 2 END, created_at DESC, id DESC")
        rows = get_db().execute(sql, params).fetchall()
        return jsonify([row_to_dict(r) for r in rows])

    @app.get("/api/claims/<int:claim_id>")
    def get_claim(claim_id):
        row = get_db().execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        if row is None:
            return error("Claim not found.", 404)
        return jsonify(row_to_dict(row))

    @app.patch("/api/claims/<int:claim_id>/review")
    def review_claim(claim_id):
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error("Request body must be a JSON object.", 400)
        status = data.get("status")
        note = data.get("reviewer_note", "")
        if status not in STATUSES:
            return error("Status must be one of: " + ", ".join(STATUSES) + ".", 400)
        if not isinstance(note, str) or len(note.strip()) > MAX_NOTE:
            return error(f"Reviewer note must be text of at most {MAX_NOTE} characters.", 400)
        db = get_db()
        if db.execute("SELECT 1 FROM claims WHERE id = ?", (claim_id,)).fetchone() is None:
            return error("Claim not found.", 404)
        # Only status + note change (DP3): text, platform, category, link, flags stay fixed.
        db.execute("UPDATE claims SET status = ?, reviewer_note = ?, updated_at = ? WHERE id = ?",
                   (status, note.strip(), now_iso(), claim_id))
        db.commit()
        row = db.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        return jsonify(row_to_dict(row))

    @app.post("/api/demo/load")
    def demo_load():
        return jsonify({"added": seed_demo(get_db())})

    @app.post("/api/demo/reset")
    def demo_reset():
        db = get_db()
        db.execute("DELETE FROM claims")
        db.commit()
        return jsonify({"cleared": True})

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    app.run(host=host, port=port, debug=False)
