import base64
import json

import httpx
from fastapi.testclient import TestClient

from app import llm
from app.config import settings
from app.main import app

c = TestClient(app)
P = "/api/v1/projects/ROVER-ALPHA"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def test_health_and_static_endpoints():
    assert c.get("/health").json()["status"] == "ok"
    assert c.get(f"{P}/graph").json()["nodes"]
    assert c.get(f"{P}/bom").json()["total_cost"] == 243
    assert c.get(f"{P}/catalog").status_code == 200
    assert c.get("/api/v1/projects/NOPE").status_code == 404


def test_change_review_history_and_export_flow():
    r = c.post(f"{P}/changes", json={"target_entity_id": "MTR-01", "replacement_id": "MTR-ALT-24A"})
    assert r.status_code == 200
    aid = r.json()["analysis_id"]
    assert r.json()["validation"]["ok"]
    c.post(f"/api/v1/analyses/{aid}/decision", json={"decision": "needs_revision", "reviewer": "A", "comments": "x"})
    c.post(f"/api/v1/analyses/{aid}/decision", json={"decision": "rejected", "reviewer": "B"})
    got = c.get(f"/api/v1/analyses/{aid}").json()
    assert len(got["decisions"]) == 2 and got["review_decision"]["decision"] == "rejected"
    assert any(h["analysis_id"] == aid and h["review_decision"] for h in c.get(f"{P}/history").json())
    md = c.get(f"/api/v1/analyses/{aid}/export.md")
    assert md.status_code == 200 and aid in md.text


def test_bad_changes_return_422():
    assert c.post(f"{P}/changes", json={"target_entity_id": "MTR-01", "parameter": "rated_voltage", "proposed_value": 24, "unit": "A"}).status_code == 422
    assert c.post(f"{P}/changes", json={"target_entity_id": "MTR-01"}).status_code == 422


def test_supply_parameter_then_reset():
    r = c.post(f"{P}/parameters", json={"entity_id": "WIR-01", "parameter": "voltage_rating_max", "value": 60, "unit": "V"})
    assert r.status_code == 200
    assert c.post(f"{P}/parameters", json={"entity_id": "WIR-01", "parameter": "voltage_rating_max", "value": 60, "unit": "A"}).status_code == 422
    assert not any(m["parameter"] == "voltage_rating_max" for m in c.get(f"{P}/audit").json()["missing"])
    assert c.delete(f"{P}/parameters").json()["removed"] >= 1


def test_chat_whatif_question_and_clarify():
    r = c.post(f"{P}/chat", json={"message": "what if the motor is 24 V?"}).json()
    assert r["kind"] == "analysis" and r["card"]["scenarios"]
    q = c.post(f"{P}/chat", json={"message": "what does it cost?", "analysis_id": r["analysis_id"]}).json()
    assert q["kind"] == "answer" and "USD" in q["reply"]
    assert c.post(f"{P}/chat", json={"message": "what if we use a cheaper wheel"}).json()["kind"] == "clarify"
    assert c.post(f"{P}/chat", json={"message": "what if the motor is 24 A?"}).json()["kind"] in ("error", "clarify", "analysis")


def test_vision_requires_a_provider_and_validates_files():
    assert c.post(f"{P}/vision/identify", files={"image": ("x.png", PNG, "image/png")}).status_code == 503
    assert c.post(f"{P}/vision/identify", files={"image": ("x.png", b"not an image", "image/png")}).status_code == 422


def test_vision_with_mocked_gemini_validates_output(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    reply = {"component_type": "DC motor", "category": "motor", "best_match_part_id": "MTR-FAKE", "best_match_catalog_id": "MTR-ALT-24A",
             "description": "motor", "visible_text": ["24V"], "confidence": 0.9,
             "label_specs": [{"parameter": "rated_voltage", "value": 24, "unit": "V"}, {"parameter": "bogus", "value": 1, "unit": "V"}]}

    def h(req):
        assert req.headers["x-goog-api-key"] == "k"
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(reply)}]}}]})
    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(h))
    r = c.post(f"{P}/vision/identify", files={"image": ("x.png", PNG, "image/png")})
    assert r.status_code == 200
    j = r.json()
    assert j["read"]["matched_part_id"] is None and j["read"]["matched_catalog_id"] == "MTR-ALT-24A"
    assert len(j["read"]["label_specs"]) == 1
    assert j["target"]["entity_id"] == "MTR-01" and any(x["kind"] == "swap" for x in j["changes"])
    # the suggested request can be analysed directly
    swap = next(x for x in j["changes"] if x["kind"] == "swap")["request"]
    assert c.post(f"{P}/changes", json=swap).status_code == 200


def test_rate_limit(monkeypatch):
    from app import main
    main._hits.clear()
    monkeypatch.setattr(settings, "ai_rate_limit_per_minute", 2)
    codes = [c.post(f"{P}/chat", json={"message": "hello"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    main._hits.clear()
