import asyncio
import json

import httpx

from app import ai, llm
from app.analysis import analyze_change
from app.config import settings
from app.dataset import get_dataset
from app.intent import parse_intent
from app.schemas import ChangeRequest
from app.validator import validate_text

D = get_dataset()


def test_parser_voltage_change():
    r = parse_intent("what if the motor is 24 V?", D)
    assert r["request"] == {"target_entity_id": "MTR-01", "parameter": "rated_voltage", "proposed_value": 24.0, "unit": "V"}


def test_parser_catalogue_swap():
    r = parse_intent("what if I replace the motor with MTR-ALT-12L", D)
    assert r["request"]["replacement_id"] == "MTR-ALT-12L"


def test_parser_relative_changes():
    assert parse_intent("what if battery capacity doubles", D)["request"]["proposed_value"] == 192.0
    assert parse_intent("what if the chassis is 0.5 kg lighter", D)["request"]["proposed_value"] == 2.7


def test_parser_asks_when_unclear_and_never_invents():
    assert parse_intent("what if we use a cheaper wheel", D)["kind"] == "clarify"
    assert parse_intent("hello", D)["kind"] == "none"
    assert parse_intent("why did the driver fail", D)["kind"] == "question"


def test_validator_rejects_invented_ids_numbers_and_approval():
    rep = analyze_change(ChangeRequest(target_entity_id="MTR-01", replacement_id="MTR-ALT-24A"))
    payload = ai.compact(rep)
    assert validate_text("Check DRV-01 against the rail.", payload, rep, D) == []
    assert validate_text("Replace XYZ-99 now.", payload, rep, D)
    assert validate_text("This design is approved.", payload, rep, D)
    assert validate_text("Peak current will be 987.65 A.", payload, rep, D)


def _mock(handler):
    return httpx.MockTransport(handler)


def test_synthesis_accepts_grounded_text_and_rejects_hallucination(monkeypatch):
    for k, v in dict(nebius_api_key="k", nebius_base_url="https://x.test/v1", nebius_model="m").items():
        monkeypatch.setattr(settings, k, v)
    rep = analyze_change(ChangeRequest(target_entity_id="MTR-01", replacement_id="MTR-ALT-24A"))

    def ok(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(
            {"summary": "The change affects DRV-01 and REG-01.", "review_actions": ["Review REG-01."], "caveats": []})}}]})
    monkeypatch.setattr(llm, "_transport", _mock(ok))
    assert asyncio.run(ai.synthesize(rep, D))["status"] == "completed"

    def bad(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(
            {"summary": "Fully compliant; costs 12345 USD for ZZZ-99.", "review_actions": [], "caveats": []})}}]})
    monkeypatch.setattr(llm, "_transport", _mock(bad))
    assert asyncio.run(ai.synthesize(rep, D))["status"] == "rejected"

    monkeypatch.setattr(llm, "_transport", _mock(lambda r: httpx.Response(500)))
    assert asyncio.run(ai.synthesize(rep, D))["status"] == "failed"


def test_extract_json_tolerates_fences():
    assert llm.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm.extract_json("Sure! {\"a\": 2} done") == {"a": 2}
    assert llm.extract_json("nope") is None
