import pytest

from app.analysis import analyze_change
from app.dataset import get_dataset
from app.resolve import ChangeError
from app.schemas import ChangeRequest
from app.validator import validate_report


def run(**kw):
    return analyze_change(ChangeRequest(**kw))


def sc(report, sid):
    return next(s for s in report["scenarios"] if s["id"] == sid)


def test_baseline_metrics_are_computed_from_recorded_values():
    r = run(target_entity_id="CHS-01", parameter="mass", proposed_value=3.0, unit="kg")
    m = {x["name"]: x for x in sc(r, "S")["metrics"]}
    assert m["total_mass_kg"]["baseline"] == pytest.approx(5.74, abs=0.01)
    assert m["bom_cost_usd"]["baseline"] == pytest.approx(243)


def test_motor_24v_gives_three_scenarios_and_verified_issues_when_rail_raised():
    r = run(target_entity_id="MTR-01", replacement_id="MTR-ALT-24A")
    assert [s["id"] for s in r["scenarios"]] == ["A", "B", "C"]
    b = sc(r, "B")
    assert b["counts"]["verified_issue"] >= 3
    assert all(f["evidence_ids"] for f in b["findings"] if f["status"] == "verified_issue")
    c = sc(r, "C")
    assert any(l["swapped"] for l in c["cost"]["lines"])
    assert r["primary_scenario"] == "C"
    assert validate_report(r, get_dataset())["ok"]


def test_regulator_isolation_keeps_controller_unaffected():
    r = run(target_entity_id="MTR-01", replacement_id="MTR-ALT-24A")
    un = {u["entity_id"]: u["reason"] for u in sc(r, "B")["unaffected"]}
    assert "CTRL-01" in un and un["CTRL-01"]


def test_chassis_change_does_not_touch_electrical_parts():
    r = run(target_entity_id="CHS-01", parameter="mass", proposed_value=3.0, unit="kg")
    s = sc(r, "S")
    assert s["counts"]["verified_issue"] == 0
    assert not any(f["entity_id"] in ("DRV-01", "REG-01") for f in s["findings"] if f["status"] != "no_violation_found")


def test_cost_only_change_flags_budget_only():
    r = run(target_entity_id="CTRL-01", parameter="unit_cost", proposed_value=80, unit="USD")
    bad = [f for f in sc(r, "S")["findings"] if f["status"] == "verified_issue"]
    assert [f["entity_id"] for f in bad] == ["REQ-COST-01"]


def test_cheaper_motor_improves_runtime_and_missing_wiring_stays_unknown():
    r = run(target_entity_id="MTR-01", replacement_id="MTR-ALT-12L")
    s = sc(r, "S")
    m = {x["name"]: x for x in s["metrics"]}
    assert m["runtime_h"]["proposed"] > m["runtime_h"]["baseline"]
    assert any(f["status"] == "unknown" and f["entity_id"] == "WIR-01" for f in s["findings"])


def test_unit_mismatch_is_rejected():
    with pytest.raises(ChangeError):
        run(target_entity_id="MTR-01", parameter="rated_voltage", proposed_value=24, unit="A")


def test_wrong_category_swap_is_rejected():
    with pytest.raises(ChangeError):
        run(target_entity_id="MTR-01", replacement_id="BAT-ALT-24")


def test_engineer_supplied_value_resolves_an_unknown():
    from app import store
    before = run(target_entity_id="MTR-01", replacement_id="MTR-ALT-12L")
    assert any(f["status"] == "unknown" and f["entity_id"] == "WIR-01" for f in sc(before, "S")["findings"])
    store.add_override("WIR-01", "voltage_rating_max", 60, "V", "datasheet", "tester")
    store.add_override("WIR-01", "current_rating_max", 10, "A", "datasheet", "tester")
    after = run(target_entity_id="MTR-01", replacement_id="MTR-ALT-12L")
    assert not any(f["status"] == "unknown" and f["entity_id"] == "WIR-01" for f in sc(after, "S")["findings"])
    assert any(e["status"] == "engineer_supplied" for e in after["evidence"].values())


def test_risk_score_is_bounded_and_ordered():
    big = run(target_entity_id="MTR-01", replacement_id="MTR-ALT-24A")
    small = run(target_entity_id="CHS-01", parameter="mass", proposed_value=3.0, unit="kg")
    assert 0 <= small["risk"]["score"] <= big["risk"]["score"] <= 100
