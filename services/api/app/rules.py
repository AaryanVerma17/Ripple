"""Deterministic checks. A rule compares two recorded values (or a computed metric and a recorded value).

Outcomes follow one rule everywhere:
  * a missing input        -> unknown (never a guess)
  * a failed check on recorded values -> verified_issue
  * a failed check that relies on an assumption -> potential_issue
  * a passed check         -> no_violation_found (which is not proof of overall safety)
"""
from __future__ import annotations

from .state import State
from .units import UnitError, convert, fmt

EPS = 1e-9
SEVERITY = {"verified_issue": 4, "potential_issue": 3, "unknown": 2, "review_required": 1, "no_violation_found": 0}


def worst(statuses: list[str]) -> str:
    if not statuses:
        return "no_violation_found"
    return max(statuses, key=lambda s: SEVERITY.get(s, 0))


def _operand(state: State, metrics: dict, spec: dict) -> dict:
    if "metric" in spec:
        m = metrics.get(spec["metric"])
        if m and m["value"] is not None:
            return {"ok": True, "value": m["value"], "unit": m["unit"], "label": m["label"], "entity": None,
                    "param": spec["metric"], "evidence_id": None, "inputs": m["inputs"], "status": "computed"}
        reason = (m or {}).get("reason") or "could not be computed"
        return {"ok": False, "label": (m or {}).get("label", spec["metric"]), "missing": f"{(m or {}).get('label', spec['metric'])}: {reason}"}
    ent, param = spec["entity"], spec["param"]
    rec = state.get(ent, param)
    label = f"{state.part_name(ent)} {state.label(param).lower()}"
    if rec is None:
        return {"ok": False, "label": label, "entity": ent, "param": param,
                "missing": f"{state.part_name(ent)} · {state.label(param)} is not recorded"}
    factor = spec.get("factor", 1.0)
    if factor != 1.0:
        label = f"{factor * 100:g} % of {label}"
    return {"ok": True, "value": rec["value"] * factor, "unit": rec["unit"], "label": label, "entity": ent,
            "param": param, "evidence_id": rec.get("evidence_id"), "status": rec.get("status"), "inputs": []}


def _fmt(o: dict) -> str:
    return fmt(o["value"], o["unit"])


def evaluate_rule(rule: dict, state: State, metrics: dict) -> dict:
    lhs = _operand(state, metrics, rule["lhs"])
    rhs = _operand(state, metrics, rule["rhs"])
    involves = sorted({s["entity"] for s in (rule["lhs"], rule["rhs"]) if "entity" in s})
    base = {"rule_id": rule["id"], "title": rule["title"], "category": rule["category"], "group": rule.get("group"),
            "op": rule["op"], "basis": rule.get("basis", "recorded"), "assumption": rule.get("assumption"),
            "remedy": rule.get("remedy"), "involves": involves, "rail_coupled": bool(rule.get("rail_coupled"))}
    if not (lhs["ok"] and rhs["ok"]):
        missing = [o["missing"] for o in (lhs, rhs) if not o["ok"]]
        return {**base, "status": "unknown", "message": "Can't be checked: " + "; ".join(missing) + ".",
                "missing": missing, "evidence_ids": [o["evidence_id"] for o in (lhs, rhs) if o["ok"] and o.get("evidence_id")],
                "lhs": lhs, "rhs": rhs, "margin": None,
                "calc": _calc(rule, lhs, rhs, None, "unavailable", base["assumption"])}
    try:
        rv = convert(rhs["value"], rhs["unit"], lhs["unit"])
    except UnitError:
        return {**base, "status": "unknown", "message": f"Units can't be compared ({lhs['unit']} vs {rhs['unit']}).",
                "missing": ["compatible units"], "evidence_ids": [], "lhs": lhs, "rhs": rhs, "margin": None,
                "calc": _calc(rule, lhs, rhs, None, "unavailable", base["assumption"])}
    lv, unit, op = lhs["value"], lhs["unit"], rule["op"]
    A, B = lhs["label"], rhs["label"]
    if op == "<=":
        passed, margin = lv <= rv + EPS, rv - lv
        msg_pass = f"{A} ({_fmt(lhs)}) is within {B} ({_fmt(rhs)}). Margin {fmt(margin, unit)}."
        msg_fail = f"{A} ({_fmt(lhs)}) is above {B} ({_fmt(rhs)}) by {fmt(lv - rv, unit)}."
    elif op == ">=":
        passed, margin = lv >= rv - EPS, lv - rv
        msg_pass = f"{A} ({_fmt(lhs)}) meets {B} ({_fmt(rhs)}). Margin {fmt(margin, unit)}."
        msg_fail = f"{A} ({_fmt(lhs)}) is below {B} ({_fmt(rhs)}) by {fmt(rv - lv, unit)}."
    elif op == "==":
        tol = rule.get("tol", 0.0)
        diff = abs(lv - rv)
        passed, margin = diff <= tol + EPS, tol - diff
        msg_pass = f"{A} ({_fmt(lhs)}) matches {B} ({_fmt(rhs)})."
        msg_fail = f"{A} ({_fmt(lhs)}) does not match {B} ({_fmt(rhs)}); they differ by {fmt(diff, unit)}."
    elif op == "within_pct":
        tol = rule["tol"]
        pct = abs(lv - rv) / rv * 100 if rv else float("inf")
        passed, margin = pct <= tol + EPS, tol - pct
        msg_pass = f"{A} ({_fmt(lhs)}) is within {tol:g} % of {B} ({_fmt(rhs)})."
        msg_fail = f"{A} ({_fmt(lhs)}) differs from {B} ({_fmt(rhs)}) by {pct:.0f} %, more than the {tol:g} % allowed."
    else:  # pragma: no cover
        raise ValueError(f"Unknown operator {op}")
    if passed:
        status, msg = "no_violation_found", msg_pass
    else:
        status = "verified_issue" if base["basis"] == "recorded" else "potential_issue"
        msg = msg_fail
        if base["basis"] != "recorded" and base["assumption"]:
            msg += " This relies on an assumption: " + base["assumption"]
    evidence = [o["evidence_id"] for o in (lhs, rhs) if o.get("evidence_id")]
    for o in (lhs, rhs):
        for i in o.get("inputs", []):
            if i.get("evidence_id"):
                evidence.append(i["evidence_id"])
    eng = [o for o in (lhs, rhs) if o.get("status") == "engineer_supplied"]
    if eng:
        msg += " Uses an engineer-supplied value that has not been verified against a source."
    return {**base, "status": status, "message": msg, "missing": [], "evidence_ids": list(dict.fromkeys(evidence)),
            "lhs": lhs, "rhs": rhs, "margin": margin,
            "calc": _calc(rule, lhs, rhs, margin, "computed", base["assumption"], passed)}


def _calc(rule, lhs, rhs, margin, status, assumption, passed=None):
    sym = {"<=": "≤", ">=": "≥", "==": "=", "within_pct": "≈"}[rule["op"]]
    inputs = []
    for o in (lhs, rhs):
        if o["ok"]:
            inputs.append({"label": o["label"], "value": o["value"], "unit": o["unit"], "evidence_id": o.get("evidence_id")})
    return {"name": rule["title"], "formula": f"{lhs['label']} {sym} {rhs['label']}", "inputs": inputs,
            "result": None if margin is None else {"value": round(margin, 6), "unit": lhs.get("unit", ""),
                                                   "text": "margin" if passed else "shortfall" if passed is False else ""},
            "assumptions": [assumption] if assumption else [], "status": status}


def evaluate_rules(rules: list[dict], state: State, metrics: dict) -> list[dict]:
    return [evaluate_rule(r, state, metrics) for r in rules]


def evaluate_requirements(state: State, metrics: dict, rule_results: list[dict]) -> list[dict]:
    out = []
    for e in state.data["entities"]:
        if e["type"] != "requirement":
            continue
        base = {"id": e["id"], "name": e["name"], "statement": e["statement"], "metric": e.get("metric"),
                "operator": e.get("operator"), "threshold": e.get("threshold"), "unit": e.get("unit")}
        if e.get("metric"):
            m = metrics[e["metric"]]
            if m["value"] is None:
                out.append({**base, "value": None, "status": "unknown", "margin": None,
                            "message": f"{e['name']} can't be checked: {m['reason']}", "evidence_ids": [],
                            "model_assumption": False, "calc": None})
                continue
            v, t = m["value"], e["threshold"]
            ok = v >= t - EPS if e["operator"] == ">=" else v <= t + EPS
            margin = (v - t) if e["operator"] == ">=" else (t - v)
            word = "at least" if e["operator"] == ">=" else "at most"
            if ok:
                status = "no_violation_found"
                msg = f"{m['label']} is {fmt(v, e['unit'])}; the requirement is {word} {fmt(t, e['unit'])}. Margin {fmt(margin, e['unit'])}."
            else:
                status = "potential_issue" if m["model_assumption"] else "verified_issue"
                msg = (f"{m['label']} is {fmt(v, e['unit'])}; the requirement is {word} {fmt(t, e['unit'])}. "
                       f"Short by {fmt(-margin, e['unit'])}.")
                if m["model_assumption"]:
                    msg += " This is an estimate that relies on a modelling assumption."
            ev = [i["evidence_id"] for i in m["inputs"] if i.get("evidence_id")]
            out.append({**base, "value": v, "status": status, "margin": margin, "message": msg,
                        "evidence_ids": list(dict.fromkeys(ev)), "model_assumption": m["model_assumption"],
                        "calc": {"name": f"{e['id']}: {m['label']}", "formula": m["formula"], "inputs": m["inputs"],
                                 "result": {"value": round(v, 6), "unit": e["unit"], "text": "computed"},
                                 "assumptions": m["assumptions"], "status": "computed"}})
        else:  # qualitative: worst result of the rules in its group
            grp = [r for r in rule_results if r.get("group") == e.get("group")]
            status = worst([r["status"] for r in grp])
            bad = [r for r in grp if r["status"] in ("verified_issue", "potential_issue")]
            unk = [r for r in grp if r["status"] == "unknown"]
            if bad:
                msg = f"{len(bad)} electrical check(s) fail: " + "; ".join(r["title"] for r in bad[:3]) + ("…" if len(bad) > 3 else "")
            elif unk:
                msg = f"{len(unk)} electrical check(s) can't be completed because data is missing."
            else:
                msg = "All recorded electrical checks pass."
            ev = []
            for r in bad or unk:
                ev += [x for x in r.get("evidence_ids", []) if x not in ev]
            out.append({**base, "value": None, "status": status, "margin": None, "message": msg,
                        "evidence_ids": ev[:8], "model_assumption": False, "calc": None})
    return out
