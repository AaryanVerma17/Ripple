"""The analysis orchestrator: change -> scenarios -> impacts, checks, requirements, cost, fix options -> report.

Everything in here is deterministic. The language model only ever sees the finished result."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from uuid import uuid4

from . import graph
from .dataset import get_dataset
from .metrics import METRIC_LABELS, compute_metrics
from .resolve import resolve_change
from .rules import SEVERITY, evaluate_requirements, evaluate_rules, worst
from .schemas import ChangeRequest
from .state import State
from .units import fmt

FAIL = ("verified_issue", "potential_issue")
BANDS = [(20, "low"), (45, "moderate"), (70, "high"), (101, "critical")]


# ----------------------------------------------------------------------------- evaluation helpers
def _evaluate(state: State) -> dict:
    metrics = compute_metrics(state)
    rules = evaluate_rules(state.data["rules"], state, metrics)
    reqs = evaluate_requirements(state, metrics, rules)
    return {"metrics": metrics, "rules": rules, "reqs": reqs}


def _val(o: dict | None):
    return o.get("value") if o and o.get("ok") else None


def _changed(a, b, rel: float = 1e-9) -> bool:
    if a is None and b is None:
        return False
    if a is None or b is None:
        return True
    return abs(a - b) > rel * max(1.0, abs(a), abs(b))


# ----------------------------------------------------------------------------- fix options
def _cost_of(state: State, entity_id: str, catalog_item: dict | None = None) -> float | None:
    rec = catalog_item["parameters"].get("unit_cost") if catalog_item else state.get(entity_id, "unit_cost")
    return None if rec is None else rec["value"] * state.qty(entity_id)


def fix_options(state: State, evaluation: dict, exclude: set[str]) -> list[dict]:
    """For each part whose rules fail (or can't be checked), list catalogue parts that would resolve it."""
    failing: dict[str, list[dict]] = {}
    for r in evaluation["rules"]:
        if r["status"] in FAIL or (r["status"] == "unknown" and r.get("remedy")):
            ent = r.get("remedy")
            if ent and ent not in exclude and ent in state.by_id:
                failing.setdefault(ent, []).append(r)
    old_status = {r["rule_id"]: r["status"] for r in evaluation["rules"]}
    out = []
    for ent, rules in sorted(failing.items()):
        cur_cost = _cost_of(state, ent)
        cat = state.by_id[ent].get("category")
        options = []
        for item in state.data["catalog"]:
            if item["category"] != cat or item["id"] == state.part_id(ent):
                continue
            cand = state.with_replacement(ent, item["id"])
            ev2 = _evaluate(cand)
            new = {r["rule_id"]: r["status"] for r in ev2["rules"]}
            resolves = [r["rule_id"] for r in rules if new[r["rule_id"]] == "no_violation_found"]
            introduces = [rid for rid, s in new.items() if s in FAIL and old_status.get(rid) not in FAIL]
            if not resolves or introduces:
                continue
            c = _cost_of(cand, ent, item)
            options.append({
                "catalog_id": item["id"], "name": item["name"], "unit_cost": item["parameters"]["unit_cost"]["value"],
                "line_cost": c, "cost_delta": None if (c is None or cur_cost is None) else c - cur_cost,
                "lead_time_days": item.get("lead_time_days"), "resolves": resolves, "evidence_id": item["evidence_id"],
                "mass_delta": (item["parameters"].get("mass", {}).get("value", 0) - (state.value(ent, "mass") or 0)) * state.qty(ent),
            })
        options.sort(key=lambda o: (o["cost_delta"] is None, o["cost_delta"] or 0))
        if not options and not any(r["status"] in FAIL for r in rules):
            continue
        out.append({"entity_id": ent, "name": state.by_id[ent]["name"], "current_part": state.part_name(ent),
                    "issues": [{"rule_id": r["rule_id"], "title": r["title"], "status": r["status"]} for r in rules],
                    "options": options, "chosen": None})
    return out


def apply_remediation(state: State, target_id: str, max_rounds: int = 4) -> tuple[State, list[dict]]:
    chosen: list[dict] = []
    exclude = {target_id}
    for _ in range(max_rounds):
        ev = _evaluate(state)
        opts = [o for o in fix_options(state, ev, exclude) if o["options"]]
        if not opts:
            break
        for o in opts:
            best = o["options"][0]
            state = state.with_replacement(o["entity_id"], best["catalog_id"])
            exclude.add(o["entity_id"])
            o2 = dict(o)
            o2["chosen"] = best["catalog_id"]
            chosen.append(o2)
    return state, chosen


# ----------------------------------------------------------------------------- scenarios
def _scenario_specs(data: dict, resolved: dict) -> list[dict]:
    base, after, target = resolved["base"], resolved["after"], resolved["target"]
    tid = target["id"]
    changed_params = {c["param"] for c in resolved["changes"]}
    rail = base.roles["rail"]
    coupled = [r for r in data["rules"] if r.get("rail_coupled")
               and any(s.get("entity") == tid and s.get("param") in changed_params for s in (r["lhs"], r["rhs"]))]
    new_v = None
    for p in changed_params:
        if any(s.get("param") == p and s.get("entity") == tid for r in coupled for s in (r["lhs"], r["rhs"])):
            new_v = after.value(tid, p)
    rail_v = after.value(rail, "rail_voltage")
    if coupled and new_v and rail_v and abs(new_v / rail_v - 1) > 0.10:
        rail_name = after.part_name(rail)
        proposed = {"value": float(new_v), "unit": "V", "evidence_id": "EV-PROPOSED-RAIL", "status": "proposed"}
        if "EV-PROPOSED-RAIL" not in data["evidence_index"]:
            ev = {"id": "EV-PROPOSED-RAIL", "entity_id": rail, "property": "rail_voltage", "value": float(new_v), "unit": "V",
                  "source_document_id": "CHANGE-PROPOSAL", "source_location": "Scenario assumption: the rail follows the new motor voltage",
                  "status": "proposed", "revision": "-"}
            data["evidence"].append(ev)
            data["evidence_index"][ev["id"]] = ev
        raised = after.with_override(rail, "rail_voltage", proposed)
        return [
            {"id": "A", "title": f"Keep the {fmt(rail_v, 'V')} rail", "state": after, "extra": [], "remediate": False,
             "summary": f"Only the part changes. The {rail_name.lower()} stays at {fmt(rail_v, 'V')}, so the new part runs below its rating."},
            {"id": "B", "title": f"Raise the rail to {fmt(new_v, 'V')}", "state": raised, "extra": [(rail, {"supply"})],
             "remediate": False,
             "summary": f"The rail moves to {fmt(new_v, 'V')} and nothing else changes. This shows what breaks."},
            {"id": "C", "title": f"Raise the rail to {fmt(new_v, 'V')} and swap what fails", "state": raised,
             "extra": [(rail, {"supply"})], "remediate": True,
             "summary": "Same as B, plus the cheapest catalogue part that fixes each failing check."},
        ]
    return [{"id": "S", "title": "Proposed change", "state": after, "extra": [], "remediate": False,
             "summary": "The change as proposed, with everything else left as recorded."}]


def _edge_lookup(data: dict) -> dict:
    return {frozenset((r["source_id"], r["target_id"])): r["id"] for r in data["relationships"]}


def _recommend(r: dict, state: State, target_id: str) -> str:
    if r["status"] == "unknown":
        if r.get("missing"):
            return "Record the missing value from a controlled source, or choose a part that documents it."
        return "Resolve the unit or data problem, then re-run."
    if r["status"] in FAIL:
        rem = r.get("remedy")
        if rem and rem != target_id and rem in state.by_id:
            return f"Change the {state.by_id[rem]['name'].lower()} ({rem}) or revisit the change. See the fix options."
        if r["category"] == "mechanical_fit":
            return "Choose a part with matching mounting dimensions, or add a matching adapter."
        return "Revisit the change; no recorded part fixes this on its own."
    return "No action needed for this check."


def evaluate_scenario(data: dict, resolved: dict, spec: dict, baseline: dict, edge_ids: dict) -> dict:
    tid = resolved["target"]["id"]
    base_state: State = resolved["base"]
    state: State = spec["state"]
    remediation: list[dict] = []
    if spec["remediate"]:
        state, remediation = apply_remediation(state, tid)
    ev = _evaluate(state)

    kinds: set = set()
    for c in resolved["changes"]:
        kinds.add(data["project"]["param_kinds"].get(c["param"], "mech"))
    sources = [(tid, kinds, 0)]
    first = graph.trace(data, sources)
    extra = []
    for ent, k in spec["extra"]:
        extra.append((ent, k, first["reached"].get(ent, {}).get("hop", 1)))
    tr = graph.trace(data, sources + extra)
    reached = tr["reached"]
    swapped = {e for e in state.replacements if e != tid}
    for e in swapped:  # parts swapped as part of the plan are part of the change
        if e not in reached:
            reached[e] = {"hop": 1, "path": [tid, e], "via": [], "kinds": set()}

    base_rules = {r["rule_id"]: r for r in baseline["rules"]}
    checks, findings_src = [], []
    for r in ev["rules"]:
        b = base_rules[r["rule_id"]]
        value_changed = _changed(_val(r["lhs"]), _val(b["lhs"])) or _changed(_val(r["rhs"]), _val(b["rhs"]))
        status_changed = r["status"] != b["status"]
        in_reach = any(e in reached for e in r["involves"])
        relevant = value_changed or status_changed or (r["status"] != "no_violation_found" and in_reach)
        r["relevant"] = relevant
        r["pre_existing"] = (r["status"] == b["status"] and r["status"] != "no_violation_found" and not value_changed)
        checks.append(r)
        if relevant:
            findings_src.append(r)

    for r in findings_src:  # parts named by a failing or unverifiable check belong in the impact set
        if r["status"] == "no_violation_found":
            continue
        hops = [reached[e]["hop"] for e in r["involves"] if e in reached]
        for e in r["involves"]:
            if e not in reached and hops:
                anchor = min((x for x in r["involves"] if x in reached), key=lambda x: reached[x]["hop"])
                reached[e] = {"hop": min(hops) + 1, "path": reached[anchor]["path"] + [e], "via": [], "kinds": set()}

    base_reqs = {q["id"]: q for q in baseline["reqs"]}
    req_changed: list[str] = []
    req_rows = []
    for q in ev["reqs"]:
        b = base_reqs[q["id"]]
        changed = _changed(q["value"], b["value"], 0.02) or q["status"] != b["status"] or q["status"] != "no_violation_found"
        q["relevant"] = changed
        q["baseline_status"], q["baseline_value"] = b["status"], b["value"]
        if q["metric"] is None:
            # qualitative requirements are only 'impacted' when a check in their group is relevant
            q["relevant"] = any(r["relevant"] for r in ev["rules"] if r.get("group") == next(
                (e.get("group") for e in data["entities"] if e["id"] == q["id"]), None))
        if q["relevant"]:
            req_changed.append(q["id"])
        req_rows.append(q)

    derived = graph.derived_impacts(data, reached, req_changed, {tid} | swapped)
    tests = [d for d in derived if by_type(data, d["entity_id"]) == "test"]
    docs = [d for d in derived if by_type(data, d["entity_id"]) == "document"]

    # ---------------- findings
    findings: list[dict] = []
    calcs: list[dict] = []

    def add_calc(c):
        if not c:
            return None
        cid = f"CALC-{len(calcs) + 1:03d}"
        calcs.append({"calculation_id": cid, **c})
        return cid

    def add(**f):
        f["id"] = f"F-{len(findings) + 1:03d}"
        f.setdefault("evidence_ids", [])
        f.setdefault("pre_existing", False)
        f.setdefault("impact_path", [tid])
        f.setdefault("hop", 0)
        findings.append(f)

    ch_lines = []
    for c in resolved["changes"]:
        b = fmt(c["before"]["value"], c["before"]["unit"]) if c["before"] else "not recorded"
        a = fmt(c["after"]["value"], c["after"]["unit"]) if c["after"] else "not recorded"
        ch_lines.append(f"{c['label']}: {b} → {a}")
    add(category="change_scope", entity_id=tid, status="review_required", title="Proposed change",
        summary=resolved["description"] + ". " + "; ".join(ch_lines[:6]) + ("…" if len(ch_lines) > 6 else "") + ".",
        evidence_ids=[c["after"]["evidence_id"] for c in resolved["changes"] if c["after"]] ,
        recommended_action="Confirm the new specification and the conditions it applies to.", source="change",
        calc_id=add_calc({"name": "Change as proposed", "formula": "before → after", "inputs": [
            {"label": f"{state.part_name(tid)} · {c['label']}", "value": c["after"]["value"] if c["after"] else None,
             "unit": (c["after"] or c["before"] or {}).get("unit", ""),
             "evidence_id": (c["after"] or {}).get("evidence_id")} for c in resolved["changes"]],
            "result": None, "assumptions": [c["note"] for c in resolved["changes"] if c["note"]], "status": "computed"}))

    for c in resolved["changes"]:
        if c["after"] is None:
            add(category="data_gap", entity_id=tid, status="unknown",
                title=f"{c['label']} is no longer known",
                summary=c["note"], recommended_action=f"Enter the new {c['label'].lower()}, or pick a catalogue part that lists it.",
                source="rule_engine", evidence_ids=[c["before"]["evidence_id"]] if c["before"] else [],
                data_gap={"entity_id": tid, "param": c["param"], "unit": (c["before"] or {}).get("unit", "")})

    for r in sorted(findings_src, key=lambda x: -SEVERITY[x["status"]]):
        hop = min([reached[e]["hop"] for e in r["involves"] if e in reached] or [0])
        path = next((reached[e]["path"] for e in r["involves"] if e in reached and reached[e]["hop"] == hop), [tid])
        gap = None
        if r["status"] == "unknown" and r.get("missing"):
            for s in (r["lhs"], r["rhs"]):
                if not s.get("ok") and s.get("entity"):
                    gap = {"entity_id": s["entity"], "param": s["param"], "unit": _unit_hint(data, s["entity"], s["param"])}
        subject = r.get("remedy") or next((e for e in r["involves"] if e != state.roles["rail"]), None) or (r["involves"] or [tid])[0]
        add(category=r["category"], entity_id=subject, status=r["status"],
            title=r["title"], summary=r["message"], evidence_ids=r["evidence_ids"], impact_path=path, hop=hop,
            recommended_action=_recommend(r, state, tid), source="rule_engine", rule_id=r["rule_id"],
            pre_existing=r["pre_existing"], calc_id=add_calc(r["calc"]), assumption=r.get("assumption"), data_gap=gap)

    for q in req_rows:
        if not q["relevant"] or q["status"] == "no_violation_found" and q["metric"] is None:
            continue
        imp = next((d for d in derived if d["entity_id"] == q["id"]), None)
        add(category="requirements", entity_id=q["id"], status=q["status"], title=f"{q['id']} · {q['name']}",
            summary=q["message"], evidence_ids=q["evidence_ids"], impact_path=(imp or {}).get("path", [tid, q["id"]]),
            hop=(imp or {}).get("hop", 1),
            recommended_action=("Rework the change or formally revise the requirement." if q["status"] in FAIL else
                                "Provide the missing data to evaluate it." if q["status"] == "unknown" else "No action needed."),
            source="requirement", calc_id=add_calc(q["calc"]))

    for d in tests:
        t = data["by_id"][d["entity_id"]]
        add(category="verification_testing", entity_id=t["id"], status="review_required", title=f"Re-run: {t['name']}",
            summary=f"{t['name']} verifies something this change touches ({d['note'].lower()}) {t.get('procedure', '')}".strip(),
            impact_path=d["path"], hop=d["hop"], recommended_action="Confirm the acceptance criteria still apply, then re-run it.",
            source="graph")
    for d in docs:
        t = data["by_id"][d["entity_id"]]
        add(category="documentation", entity_id=t["id"], status="review_required", title=f"Update: {t['name']}",
            summary=f"{t['name']} describes a part that changes.", impact_path=d["path"], hop=d["hop"],
            recommended_action="Revise the document to match the new part or value.", source="graph")

    findings.sort(key=lambda f: (-SEVERITY[f["status"]], f["hop"], f["id"]))
    for i, f in enumerate(findings):  # readable ids in display order
        f["id"] = f"F-{i + 1:03d}"

    counts = {s: sum(1 for f in findings if f["status"] == s) for s in SEVERITY}
    risk_score = min(100, counts["verified_issue"] * 20 + counts["potential_issue"] * 10 + counts["unknown"] * 5 + len(tests))
    band = next(b for lim, b in BANDS if risk_score < lim)
    risk = {"score": risk_score, "band": band,
            "formula": "20 × verified issues + 10 × potential issues + 5 × unknowns + 1 × tests to re-run (max 100)"}

    # ---------------- metrics comparison
    m_rows = []
    req_by_metric = {q["metric"]: q for q in ev["reqs"] if q["metric"]}
    for name, (label, unit) in METRIC_LABELS.items():
        b, a = baseline["metrics"][name], ev["metrics"][name]
        q = req_by_metric.get(name)
        m_rows.append({"name": name, "label": label, "unit": unit, "baseline": b["value"], "proposed": a["value"],
                       "delta": None if (a["value"] is None or b["value"] is None) else a["value"] - b["value"],
                       "reason": a["reason"], "assumptions": a["assumptions"], "model_assumption": a["model_assumption"],
                       "requirement": None if not q else {"id": q["id"], "operator": q["operator"], "threshold": q["threshold"],
                                                          "status": q["status"], "margin": q["margin"]}})

    # ---------------- cost
    cost = _cost(data, resolved, state, base_state, ev, baseline, len(tests), tid)

    # ---------------- graph nodes
    node_status: dict[str, str] = {}
    for f in findings:
        if f["entity_id"] and f["category"] not in ("change_scope",):
            node_status[f["entity_id"]] = worst([node_status.get(f["entity_id"], "no_violation_found"), f["status"]])
    nodes = []
    for eid, info in reached.items():
        nodes.append({"entity_id": eid, "hop": info["hop"], "role": "changed" if eid == tid else "affected",
                      "status": node_status.get(eid, "no_violation_found"), "path": info["path"],
                      "why": [v["why"] for v in info["via"]]})
    for d in derived:
        et = by_type(data, d["entity_id"])
        nodes.append({"entity_id": d["entity_id"], "hop": d["hop"], "role": et,
                      "status": node_status.get(d["entity_id"], "review_required" if et != "requirement" else "no_violation_found"),
                      "path": d["path"], "why": [d["note"]]})
    active_edges = set()
    for n in nodes:
        p = n["path"]
        for a, b in zip(p, p[1:]):
            eid = edge_ids.get(frozenset((a, b)))
            if eid:
                active_edges.add(eid)

    unaffected = graph.unaffected_reasons(data, reached, tr["isolated"], kinds)

    # ---------------- unresolved
    unresolved, seen = [], set()
    for f in findings:
        g = f.get("data_gap")
        if g and (g["entity_id"], g["param"]) not in seen:
            seen.add((g["entity_id"], g["param"]))
            unresolved.append({"text": f"What is the {state.label(g['param']).lower()} of {state.part_name(g['entity_id'])} ({g['entity_id']})?",
                               "entity_id": g["entity_id"], "param": g["param"], "unit": g["unit"]})
    for q in req_rows:
        if q["status"] == "unknown" and q["metric"]:
            m = ev["metrics"][q["metric"]]
            unresolved.append({"text": f"{q['name']} can't be evaluated: {m['reason']}", "entity_id": None, "param": None, "unit": ""})

    options = fix_options(state, ev, {tid} | ({e for e in state.replacements if e != tid} if spec["remediate"] else set()))
    if spec["remediate"]:
        options = remediation

    verdict = ("blocked" if counts["verified_issue"] else "caution" if counts["potential_issue"] or counts["unknown"] else "clear")
    return {
        "id": spec["id"], "title": spec["title"], "summary": spec["summary"], "verdict": verdict, "counts": counts, "risk": risk,
        "findings": findings, "checks": [_slim_check(c) for c in checks], "requirements": req_rows,
        "metrics": m_rows, "cost": cost, "nodes": nodes, "active_edges": sorted(active_edges), "unaffected": unaffected,
        "tests": [{"id": d["entity_id"], "name": data["by_id"][d["entity_id"]]["name"], "path": d["path"]} for d in tests],
        "docs": [{"id": d["entity_id"], "name": data["by_id"][d["entity_id"]]["name"]} for d in docs],
        "fix_options": options, "unresolved": unresolved, "calculations": calcs,
        "replacements": {k: {"catalog_id": v, "name": state.catalog[v]["name"]} for k, v in state.replacements.items()},
        "rail_voltage": state.value(state.roles["rail"], "rail_voltage"),
    }


def by_type(data: dict, eid: str) -> str:
    return data["by_id"][eid]["type"]


def _unit_hint(data: dict, entity: str, param: str) -> str:
    for src in (data["by_id"][entity].get("parameters", {}),):
        if param in src:
            return src[param]["unit"]
    for item in data["catalog"]:
        if param in item["parameters"]:
            return item["parameters"][param]["unit"]
    return ""


def _slim_check(c: dict) -> dict:
    keep = ("rule_id", "title", "category", "group", "status", "message", "margin", "involves", "basis", "assumption",
            "relevant", "pre_existing", "evidence_ids", "missing")
    return {k: c.get(k) for k in keep}


def _cost(data, resolved, state: State, base_state: State, ev, baseline, n_tests: int, tid: str) -> dict:
    lines = []
    ents = {tid} | set(state.replacements)
    for eid in sorted(ents):
        b_cost, a_cost = base_state.value(eid, "unit_cost"), state.value(eid, "unit_cost")
        changed_part = state.part_id(eid) != base_state.part_id(eid)
        if not changed_part and (b_cost == a_cost):
            continue
        q = state.qty(eid)
        lines.append({"entity_id": eid, "qty": q, "from_part": base_state.part_name(eid),
                      "to_part": state.part_name(eid) if changed_part else f"{state.part_name(eid)} (modified)",
                      "unit_cost_from": b_cost, "unit_cost_to": a_cost,
                      "line_delta": None if (b_cost is None or a_cost is None) else q * (a_cost - b_cost),
                      "swapped": changed_part})
    a = data["project"]["assumptions"]
    swapped = sum(1 for l in lines if l["swapped"])
    hours = swapped * a["integration_hours_per_part"]["value"] + n_tests * a["retest_hours_per_test"]["value"]
    rate = a["engineer_rate_usd"]["value"]
    bom_b, bom_a = baseline["metrics"]["bom_cost_usd"]["value"], ev["metrics"]["bom_cost_usd"]["value"]
    parts_delta = None if (bom_a is None or bom_b is None) else bom_a - bom_b
    labour = hours * rate
    budget = next((e["threshold"] for e in data["entities"] if e.get("metric") == "bom_cost_usd"), None)
    return {"lines": lines, "bom_before": bom_b, "bom_after": bom_a, "parts_delta": parts_delta,
            "labour": {"swapped_parts": swapped, "tests": n_tests, "hours": hours, "rate": rate, "total": labour,
                       "assumptions": [a["integration_hours_per_part"]["label"] + f": {a['integration_hours_per_part']['value']:g}",
                                       a["retest_hours_per_test"]["label"] + f": {a['retest_hours_per_test']['value']:g}",
                                       a["engineer_rate_usd"]["label"] + f": {rate:g}"]},
            "first_build_total": None if parts_delta is None else parts_delta + labour,
            "budget": budget, "budget_margin_after": None if (budget is None or bom_a is None) else budget - bom_a,
            "note": "Per-unit parts change plus a one-off engineering effort estimate. Prices are fictional catalogue values; "
                    "effort figures are editable project assumptions, not quotes."}


# ----------------------------------------------------------------------------- top level
def analyze_change(req: ChangeRequest) -> dict:
    data = get_dataset()
    resolved = resolve_change(data, req)
    baseline = _evaluate(resolved["base"])
    edge_ids = _edge_lookup(data)
    specs = _scenario_specs(data, resolved)
    scenarios = [evaluate_scenario(data, resolved, s, baseline, edge_ids) for s in specs]
    primary = scenarios[-1]  # the most complete plan
    target = resolved["target"]

    # catalogue parts that match a proposed value (helps param-only changes become full analyses)
    suggestions = []
    if not req.replacement_id:
        for c in resolved["changes"]:
            if c["after"] is None or c["after"]["status"] != "proposed":
                continue
            for item in data["catalog"]:
                rec = item["parameters"].get(c["param"])
                if item["category"] == target.get("category") and rec and abs(rec["value"] - c["after"]["value"]) < 1e-6 * max(1, abs(rec["value"])):
                    suggestions.append({"catalog_id": item["id"], "name": item["name"], "unit_cost": item["parameters"]["unit_cost"]["value"],
                                        "why": f"Lists {c['label'].lower()} of {fmt(rec['value'], rec['unit'])} and a full specification."})
    used_ev = set()
    for sc in scenarios:
        for f in sc["findings"]:
            used_ev.update(f.get("evidence_ids", []))
        for c in sc["calculations"]:
            used_ev.update(i.get("evidence_id") for i in c["inputs"] if i.get("evidence_id"))
    evidence = {k: data["evidence_index"][k] for k in sorted(used_ev) if k in data["evidence_index"]}

    headline = _headline(resolved, primary, scenarios)
    report = {
        "analysis_id": f"AN-{uuid4().hex[:8].upper()}", "project_id": data["project"]["id"], "kind": req.kind,
        "status": "completed", "overall_status": "review_required", "requires_engineer_review": True,
        "created_at": datetime.now(timezone.utc).isoformat(), "change_summary": resolved["description"],
        "change": {"target_entity_id": target["id"], "target_name": target["name"], "reason": req.reason,
                   "mode": "swap" if req.replacement_id else "parameter", "replacement": resolved["replacement"],
                   "changes": [{"param": c["param"], "label": c["label"],
                                "before": c["before"] and {"value": c["before"]["value"], "unit": c["before"]["unit"], "evidence_id": c["before"].get("evidence_id")},
                                "after": c["after"] and {"value": c["after"]["value"], "unit": c["after"]["unit"], "evidence_id": c["after"].get("evidence_id")},
                                "note": c["note"]} for c in resolved["changes"]]},
        "primary_scenario": primary["id"], "scenarios": scenarios, "headline": headline,
        "counts": primary["counts"], "risk": primary["risk"], "verdict": primary["verdict"],
        "baseline": {"metrics": {k: {"value": v["value"], "unit": v["unit"], "label": v["label"]} for k, v in baseline["metrics"].items()},
                     "requirements": [{"id": q["id"], "status": q["status"]} for q in baseline["reqs"]]},
        "suggestions": suggestions, "evidence": evidence, "assumptions": data["project"]["assumptions"],
        "ai_synthesis": None, "fixture_notice": "Fictional sample data. Findings are illustrative and are not an engineering approval.",
        "unresolved_questions": [u["text"] for u in primary["unresolved"]],
        "required_tests": [t["id"] for t in primary["tests"]],
        "direct_impacts": sum(1 for n in primary["nodes"] if n["role"] == "affected" and n["hop"] == 1),
        "indirect_impacts": sum(1 for n in primary["nodes"] if n["role"] == "affected" and n["hop"] > 1),
    }
    return report


def _headline(resolved, primary, scenarios) -> str:
    c = primary["counts"]
    parts = []
    if c["verified_issue"]:
        parts.append(f"{c['verified_issue']} verified issue{'s' if c['verified_issue'] != 1 else ''}")
    if c["potential_issue"]:
        parts.append(f"{c['potential_issue']} potential issue{'s' if c['potential_issue'] != 1 else ''}")
    if c["unknown"]:
        parts.append(f"{c['unknown']} unknown{'s' if c['unknown'] != 1 else ''}")
    body = ", ".join(parts) if parts else "no violations found in the recorded checks"
    if len(scenarios) > 1:
        return f"{resolved['description']}. Fullest plan, “{primary['title']}”: {body}."
    return f"{resolved['description']}: {body}."
