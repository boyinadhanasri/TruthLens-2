# TruthLens – Misinformation Triage Platform

*Check information, not ideologies.*

## Hackathon

Code2Career AI Hackathon
Track 2 – Web Development / Real-World AI Products
Brief: TruthLens – A misinformation triage platform

## Hackathon ID

**AZIS-9G8CH8**

## Live Demo

Live Demo: https://truthlens-nine-khaki.vercel.app/

**Test credentials: none needed.** No authentication is implemented because the hackathon brief requires the application to be accessible without login.

## Standard API

**Standard API: Not implemented because the official Standard API specification was not available.** The endpoints below are TruthLens's own application REST API, not the official Code2Career/Azisly Standard API. If a specification is provided, the API will be adapted to match it exactly.

## Project Overview

TruthLens is a small Flask + SQLite web app for triaging viral claims. It flags risky-looking claims automatically, lets a human reviewer record a truth status, and shows everything in a public feed. It is neutral by design: it checks information, not ideologies. No authentication is implemented because the hackathon brief requires the application to be accessible without login.

## Problem

Social media moves faster than fact-checkers can. Newsrooms and citizen groups get flooded with viral claims and need a fast, neutral way to decide which ones to look at first.

## Solution

TruthLens lets anyone submit a viral claim. The backend automatically applies three deterministic risk rules (no AI, no external services) and ranks the claim for triage. A human reviewer then marks it Verified True, False or Misleading with a short note. Risk flags are triage signals, **not verdicts: High Risk ≠ False.**

## Risk Detection Rules

All rules are deterministic backend code (no AI API), so every flag is explainable:

| Flag | Rule |
|---|---|
| Sensational | Text contains "breaking", "shocking" or "share before deleted" (case-insensitive) |
| Shouting | MORE than 50% of alphabetic characters are uppercase (exactly 50% is not flagged; digits, spaces and punctuation are ignored) |
| Unsourced | No source link supplied |

0 flags = Low Risk · 1 flag = Risk Flag · 2+ flags = High Risk.
**Risk level and truth status are separate.** High Risk means "deserves closer review", never "False".

## Review Workflow

Every claim starts as **Unverified** with the note "Not reviewed yet." A reviewer opens the claim's detail view and sets the status (Unverified / Verified True / False / Misleading) plus a short note (max 500 characters). The change is saved to the database and shown immediately. Only status and note can change; the original claim and its flags are fixed.

## Features

1. **Submit a claim** – text, source platform (WhatsApp / X / Instagram / Other), category (Politics / Health / Finance / Other), optional source link. No login.
2. **Automatic risk flags** (calculated in the backend):
   - *Sensational* – contains "breaking", "shocking" or "share before deleted" (case-insensitive)
   - *Shouting* – more than 50% of alphabetic characters are uppercase (spaces, digits and punctuation not counted)
   - *Unsourced* – no source link
   - 2+ flags = **High Risk**, 1 flag = **Risk Flag**, 0 flags = **Low Risk**
3. **Review workflow** – new claims start as *Unverified*; a reviewer sets Verified True / False / Misleading and a note (saved in the database).
4. **Public feed** – all claims as cards, filterable by category and status; updates when filters change.
5. **Detail view** – full text, platform, category, source link, risk level and flags, status, reviewer note ("Not reviewed yet." if none), submission time, plus reviewer controls.

## Decision Points

Full reasoning is in [DECISIONS.md](DECISIONS.md).

1. **Feed order** – Risk + Recency: High Risk → Risk Flag → Low Risk, newest first within each group.
2. **Visibility** – Unverified claims are public and clearly labelled UNVERIFIED.
3. **Editing** – Claims cannot be edited after submission; only status and reviewer note can change.

## Technology

Python, Flask, SQLite, HTML, CSS, JavaScript (vanilla), REST API. No paid APIs, no AI API keys, no authentication.

## API Endpoints

All responses are JSON. Errors look like `{"error": "message"}`.

### POST /api/claims
Purpose: submit a claim. Flags and risk level are calculated by the server.

Request:
```json
{"text": "BREAKING: Something happened", "platform": "WhatsApp", "category": "Health", "source_link": ""}
```
Response (201):
```json
{"id": 1, "text": "BREAKING: Something happened", "platform": "WhatsApp", "category": "Health",
 "source_link": "", "flags": ["Sensational", "Unsourced"], "risk_level": "High Risk",
 "status": "Unverified", "reviewer_note": "", "created_at": "2026-09-24T10:00:00Z",
 "updated_at": "2026-09-24T10:00:00Z"}
```

### GET /api/claims
Purpose: list claims ordered High Risk → Risk Flag → Low Risk, newest first within each.
Optional filters: `?category=Health`, `?status=Unverified`, `?category=Health&status=Unverified` (`All` = no filter).

Request: `GET /api/claims?category=Health`
Response (200): a JSON array of claim objects (same shape as above).

### GET /api/claims/<id>
Purpose: one complete claim. Request: `GET /api/claims/1`
Response (200): a single claim object. 404 if not found.

### PATCH /api/claims/<id>/review
Purpose: set review status and note. Allowed statuses: `Unverified`, `Verified True`, `False`, `Misleading`. Invalid values return 400. Nothing else on the claim can be changed.

Request:
```json
{"status": "Misleading", "reviewer_note": "The claim uses outdated information."}
```
Response (200): the updated claim object.

### Demo helpers
- `POST /api/demo/load` – adds 6 neutral demo claims (no duplicates). Response: `{"added": 6}`
- `POST /api/demo/reset` – deletes all claims. Response: `{"cleared": true}`

## Project Structure

```
TruthLens/
├── app.py              Flask app, API, risk rules
├── seed.py             optional demo-data script
├── requirements.txt
├── Procfile            start command for Heroku-style hosts
├── README.md
├── DECISIONS.md
├── .gitignore
├── tests/test_app.py
├── templates/index.html
├── static/style.css
├── static/app.js
└── data/truthlens.db   (created automatically on first run)
```

## Local Setup

```
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
python app.py
```
Then open http://127.0.0.1:5000

The database is created automatically. Click **Load Demo Data** in the feed (or run `python seed.py`) to add example claims. To reset: click **Clear All**, or run `python seed.py --reset`, or delete `data/truthlens.db`.

## Testing

```
pytest
```
15 tests cover submission, all three flags (including the uppercase calculation), High Risk, initial status, review updates, filters, detail endpoint, feed ordering, validation and immutability.

## Deployment

Any Python host works. Example with Render (free):
1. Push this folder to a public GitHub repo.
2. On render.com choose **New → Web Service** and connect the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app --bind 0.0.0.0:$PORT`
5. After deploy, open the public URL, click **Load Demo Data**, and paste the URL into this README.

Note: free hosts may reset the SQLite file on redeploy/restart; use **Load Demo Data** to refill it.

## Deployment notes

- `PORT` is read from the environment; with `PORT` set the app binds to `0.0.0.0` (with `gunicorn app:app` the host is handled by gunicorn).
- Optional: set `TRUTHLENS_DB` to a path on a persistent disk (for example `/var/data/truthlens.db`) so claims survive restarts. If unset, `data/truthlens.db` is used.
