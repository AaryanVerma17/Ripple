"""Validation of reports and of anything a language model writes about them.

The model may only restate what the engine computed. Every ID must exist, every number must trace back
to the data it was given, and it may not approve or certify anything."""
from __future__ import annotations

import json
import re

ID_RE = re.compile(r"\b(?:[A-Z]{2,5}-(?:ALT-)?[A-Z0-9]+(?:-[A-Z0-9]+)*|F-\d{3}|CALC-\d{3}|EV-[A-Z0-9-]+)\b")
NUM_RE = re.compile(r"(?<![A-Za-z\-])-?\d+(?:\.\d+)?")
FORBIDDEN = re.compile(r"\b(approved|approve|certified|certify|guarantee[sd]?|fully compliant|safe to (?:use|ship|build)|passes? all)\b", re.I)


def known_ids(report: dict, data: dict) -> set[str]:
    ids = set(data["by_id"]) | set(data["catalog_by_id"]) | set(data["evidence_index"]) | {r["id"] for r in data["rules"]}
    ids |= {r["id"] for r in data["relationships"]}
    for sc in report.get("scenarios", []):
        ids |= {f["id"] for f in sc["findings"]} | {c["calculation_id"] for c in sc["calculations"]}
        ids |= {sc["id"]}
    ids.add(report.get("analysis_id", ""))
    return ids


def validate_report(report: dict, data: dict) -> dict:
    checks = []
    ents = set(data["by_id"])
    ev = set(data["evidence_index"]) | set(report.get("evidence", {}))  # proposed values are recorded in the report itself

    def check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    bad_ev, bad_path, bad_calc, bad_counts = [], [], [], []
    for sc in report["scenarios"]:
        calc_ids = {c["calculation_id"] for c in sc["calculations"]}
        for f in sc["findings"]:
            bad_ev += [e for e in f.get("evidence_ids", []) if e not in ev]
            bad_path += [p for p in f.get("impact_path", []) if p not in ents]
            if f.get("calc_id") and f["calc_id"] not in calc_ids:
                bad_calc.append(f["calc_id"])
        for status, n in sc["counts"].items():
            if n != sum(1 for f in sc["findings"] if f["status"] == status):
                bad_counts.append(f"{sc['id']}:{status}")
    check("Every evidence ID exists", not bad_ev, ", ".join(sorted(set(bad_ev))[:5]))
    check("Every impact path uses real parts", not bad_path, ", ".join(sorted(set(bad_path))[:5]))
    check("Every calculation reference exists", not bad_calc, ", ".join(sorted(set(bad_calc))[:5]))
    check("Counts match the findings", not bad_counts, ", ".join(bad_counts))
    unverified = [f["id"] for sc in report["scenarios"] for f in sc["findings"]
                  if f["status"] == "verified_issue" and not f.get("evidence_ids")]
    check("Every verified issue cites evidence", not unverified, ", ".join(unverified[:5]))
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


def _numbers(obj) -> list[float]:
    out = []
    for m in NUM_RE.findall(json.dumps(obj, default=str)):
        try:
            out.append(float(m))
        except ValueError:
            pass
    return out


def validate_text(text: str, payload: dict, report: dict, data: dict) -> list[str]:
    """Problems found in a model-written text; empty list means it can be shown."""
    problems = []
    known = known_ids(report, data)
    for tok in set(ID_RE.findall(text)):
        if tok not in known:
            problems.append(f"unknown ID {tok}")
    if FORBIDDEN.search(text):
        problems.append("claims approval or certainty")
    allowed = _numbers(payload)
    for m in NUM_RE.findall(re.sub(ID_RE, " ", text)):
        try:
            x = float(m)
        except ValueError:
            continue
        if abs(x) < 10 and float(x).is_integer():  # counts like "3 issues", "two" etc.
            continue
        if not any(abs(x - y) <= max(0.051, 0.01 * abs(y)) for y in allowed):
            problems.append(f"number {m} is not in the analysis")
    return problems
