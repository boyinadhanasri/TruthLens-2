import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import compute_flags, create_app  # noqa: E402


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "test.db"))
    app.config["TESTING"] = True
    return app.test_client()


def post(client, text="a calm claim", platform="WhatsApp", category="Health", link="https://example.org"):
    return client.post("/api/claims", json={"text": text, "platform": platform,
                                            "category": category, "source_link": link})


def test_submit_claim(client):
    r = post(client)
    assert r.status_code == 201
    body = r.get_json()
    assert body["id"] == 1 and body["platform"] == "WhatsApp" and body["category"] == "Health"
    assert body["source_link"] == "https://example.org" and body["created_at"]


def test_sensational_flag_case_insensitive(client):
    assert "Sensational" in post(client, "BREAKING: Something happened").get_json()["flags"]
    assert "Sensational" in compute_flags("Please Share Before Deleted!", "x")
    assert "Sensational" in compute_flags("so shocking", "x")
    assert "Sensational" not in compute_flags("A normal sentence", "x")


def test_shouting_flag_calculation():
    assert "Shouting" in compute_flags("THIS IS A VIRAL CLAIM", "x")
    assert "Shouting" in compute_flags("AAAA bb", "x")            # 4 of 6 letters = 66%
    assert "Shouting" not in compute_flags("AAA bbb", "x")        # exactly 50% is NOT more than 50%
    assert "Shouting" in compute_flags("AB 1234567890 !!!", "x")  # digits/punctuation ignored
    assert "Shouting" not in compute_flags("1234 5678 !!!", "x")  # no letters at all


def test_unsourced_flag(client):
    assert "Unsourced" in post(client, link="").get_json()["flags"]
    assert "Unsourced" in post(client, link="   ").get_json()["flags"]
    assert "Unsourced" not in post(client, link="https://example.org").get_json()["flags"]


def test_risk_levels(client):
    high = post(client, "BREAKING THIS IS A SHOCKING CLAIM", link="").get_json()
    assert set(high["flags"]) == {"Sensational", "Shouting", "Unsourced"}
    assert high["risk_level"] == "High Risk"
    assert post(client, "calm text", link="").get_json()["risk_level"] == "Risk Flag"
    low = post(client, "calm text", link="https://example.org").get_json()
    assert low["flags"] == [] and low["risk_level"] == "Low Risk"


def test_initial_status_unverified(client):
    body = post(client).get_json()
    assert body["status"] == "Unverified" and body["reviewer_note"] == ""


def test_review_update(client):
    cid = post(client).get_json()["id"]
    r = client.patch(f"/api/claims/{cid}/review",
                     json={"status": "Misleading", "reviewer_note": "Outdated information."})
    assert r.status_code == 200
    saved = client.get(f"/api/claims/{cid}").get_json()
    assert saved["status"] == "Misleading" and saved["reviewer_note"] == "Outdated information."


def test_review_rejects_invalid_status_and_long_note(client):
    cid = post(client).get_json()["id"]
    assert client.patch(f"/api/claims/{cid}/review", json={"status": "Maybe"}).status_code == 400
    assert client.patch(f"/api/claims/{cid}/review",
                        json={"status": "False", "reviewer_note": "x" * 501}).status_code == 400
    assert client.patch("/api/claims/999/review", json={"status": "False"}).status_code == 404


def test_category_filter(client):
    post(client, category="Health")
    post(client, category="Finance")
    res = client.get("/api/claims?category=Health").get_json()
    assert len(res) == 1 and res[0]["category"] == "Health"
    assert len(client.get("/api/claims?category=All").get_json()) == 2
    assert client.get("/api/claims?category=Sports").status_code == 400


def test_status_filter_and_combined(client):
    a = post(client, category="Health").get_json()["id"]
    post(client, category="Health")
    client.patch(f"/api/claims/{a}/review", json={"status": "False", "reviewer_note": "n"})
    assert [c["id"] for c in client.get("/api/claims?status=False").get_json()] == [a]
    assert len(client.get("/api/claims?status=Unverified").get_json()) == 1
    assert len(client.get("/api/claims?category=Health&status=Unverified").get_json()) == 1
    assert client.get("/api/claims?category=Finance&status=Unverified").get_json() == []


def test_detail_endpoint(client):
    cid = post(client).get_json()["id"]
    assert client.get(f"/api/claims/{cid}").get_json()["id"] == cid
    assert client.get("/api/claims/999").status_code == 404


def test_feed_order_risk_then_recency(client):
    low1 = post(client, "low one", link="https://e.org").get_json()["id"]
    low2 = post(client, "low two", link="https://e.org").get_json()["id"]
    mid = post(client, "mid", link="").get_json()["id"]
    high = post(client, "BREAKING NEWS", link="").get_json()["id"]
    assert [c["id"] for c in client.get("/api/claims").get_json()] == [high, mid, low2, low1]


def test_validation(client):
    assert post(client, text="   ").status_code == 400
    assert post(client, platform="Facebook").status_code == 400
    assert post(client, category="Sports").status_code == 400
    assert post(client, link="h" * 501).status_code == 400
    assert client.post("/api/claims", data="not json").status_code == 400


def test_claims_cannot_be_edited(client):
    cid = post(client).get_json()["id"]
    assert client.put(f"/api/claims/{cid}", json={"text": "changed"}).status_code == 405
    assert client.patch(f"/api/claims/{cid}", json={"text": "changed"}).status_code == 405
    client.patch(f"/api/claims/{cid}/review",
                 json={"status": "False", "reviewer_note": "n", "text": "hacked", "flags": []})
    assert client.get(f"/api/claims/{cid}").get_json()["text"] == "a calm claim"


def test_demo_data_and_homepage(client):
    assert client.get("/").status_code == 200
    assert client.post("/api/demo/load").get_json()["added"] == 6
    assert client.post("/api/demo/load").get_json()["added"] == 0  # no duplicates
    claims = client.get("/api/claims").get_json()
    assert {c["risk_level"] for c in claims} == {"High Risk", "Risk Flag", "Low Risk"}
    assert {c["status"] for c in claims} == {"Unverified", "Verified True", "False", "Misleading"}
    client.post("/api/demo/reset")
    assert client.get("/api/claims").get_json() == []


# ---------------------------------------------------------------- extra tests
def test_no_letters_and_platform_category_values(client):
    assert "Shouting" not in compute_flags("12345 !!! ???", "x")
    for p in ["WhatsApp", "X", "Instagram", "Other"]:
        assert post(client, platform=p).status_code == 201
    for c in ["Politics", "Health", "Finance", "Other"]:
        assert post(client, category=c).status_code == 201


def test_invalid_ids_and_malformed_json_on_review(client):
    assert client.get("/api/claims/abc").status_code == 404
    assert client.get("/api/claims/-1").status_code == 404
    cid = post(client).get_json()["id"]
    r = client.patch(f"/api/claims/{cid}/review", data="{bad json", content_type="application/json")
    assert r.status_code == 400 and "error" in r.get_json()
    assert client.post("/api/claims", data="{bad json", content_type="application/json").status_code == 400


def test_text_length_limit_and_oversized_body(client):
    assert post(client, text="a" * 5000).status_code == 201
    assert post(client, text="a" * 5001).status_code == 400
    big = client.post("/api/claims", json={"text": "a" * 200000, "platform": "X", "category": "Other"})
    assert big.status_code == 413


def test_review_does_not_change_flags_or_risk(client):
    body = post(client, "BREAKING NEWS", link="").get_json()
    client.patch(f"/api/claims/{body['id']}/review", json={"status": "Verified True", "reviewer_note": "ok"})
    after = client.get(f"/api/claims/{body['id']}").get_json()
    assert after["flags"] == body["flags"] and after["risk_level"] == "High Risk"  # High Risk != False
    assert after["status"] == "Verified True"


def test_no_authentication_routes(client):
    for path in ["/login", "/signup", "/api/login", "/api/auth"]:
        assert client.get(path).status_code == 404
    assert client.get("/api/claims").status_code == 200  # open access


def test_demo_covers_platforms_categories_and_reset(client):
    client.post("/api/demo/load")
    claims = client.get("/api/claims").get_json()
    assert {c["platform"] for c in claims} == {"WhatsApp", "X", "Instagram", "Other"}
    assert {c["category"] for c in claims} == {"Politics", "Health", "Finance", "Other"}
    assert client.delete("/api/claims/1").status_code == 405
