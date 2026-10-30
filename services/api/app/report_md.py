"""Markdown export of an analysis, for pasting into a change request or review."""
from __future__ import annotations

from .units import fmt


def _row(*cells) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def to_markdown(report: dict) -> str:
    L = [f"# Change impact report {report['analysis_id']}", "", f"**{report['change_summary']}**", "",
         f"_{report.get('fixture_notice', '')}_", "", f"Created {report['created_at']}. Requires engineer review; Ripple does not approve changes.", ""]
    if report.get("review_decision"):
        d = report["review_decision"]
        L += [f"**Review:** {d['decision'].replace('_', ' ')} by {d['reviewer']} on {d['recorded_at']}" + (f" — {d['comments']}" if d.get("comments") else ""), ""]
    for sc in report["scenarios"]:
        L += [f"## Scenario {sc['id']} · {sc['title']}", "", sc["summary"], ""]
        c = sc["counts"]
        L += [f"{c['verified_issue']} verified, {c['potential_issue']} potential, {c['unknown']} unknown, "
              f"{c['no_violation_found']} no violation found. Risk score {sc['risk']['score']}/100.", ""]
        L += ["### Metrics", "", _row("Metric", "Before", "After", "Requirement"), _row("---", "---", "---", "---")]
        for m in sc["metrics"]:
            r = m.get("requirement")
            L.append(_row(m["label"], fmt(m["baseline"], m["unit"]), fmt(m["proposed"], m["unit"]) if m["proposed"] is not None else f"n/a ({m.get('reason') or 'missing data'})",
                          f"{r['id']}: {r['status'].replace('_', ' ')}" if r else ""))
        L += ["", "### Findings", ""]
        for f in sc["findings"]:
            if f["status"] == "no_violation_found":
                continue
            L.append(f"- **{f['status'].replace('_', ' ')}** · {f['title']}: {f['summary']} _Next: {f['recommended_action']}_ ({', '.join(f.get('evidence_ids', [])[:4])})")
        co = sc["cost"]
        L += ["", "### Cost", ""]
        if co["parts_delta"] is not None:
            L.append(f"- Parts per unit: {fmt(co['bom_before'], 'USD')} → {fmt(co['bom_after'], 'USD')} ({fmt(co['parts_delta'], 'USD')})")
        L.append(f"- One-off effort (estimate): {fmt(co['labour']['total'], 'USD')} for {co['labour']['hours']:g} h")
        for l in co["lines"]:
            if l.get("swapped"):
                L.append(f"  - {l['entity_id']}: {l['from_part']} → {l['to_part']}, {fmt(l['unit_cost_from'], 'USD')} → {fmt(l['unit_cost_to'], 'USD')} × {l['qty']}")
        if sc["tests"]:
            L += ["", "### Tests to reconsider", ""] + [f"- {t['id']} · {t['name']}" for t in sc["tests"]]
        if sc["unresolved"]:
            L += ["", "### Missing data", ""] + [f"- {u['text']}" for u in sc["unresolved"]]
        L.append("")
    if report.get("ai_synthesis") and report["ai_synthesis"].get("status") == "completed":
        s = report["ai_synthesis"]
        L += ["## AI summary (validated)", "", s["summary"], ""] + [f"- {a}" for a in s["review_actions"]] + [""]
    L += ["## Assumptions", ""] + [f"- {a['label']}: {a['value']}" for a in report["assumptions"].values()]
    return "\n".join(L) + "\n"
