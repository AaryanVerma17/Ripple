"""Turns a ChangeRequest into a concrete 'after' state, listing exactly which parameters change."""
from __future__ import annotations

from .schemas import ChangeRequest
from .state import State
from .units import UnitError, convert, fmt, normalize_unit


class ChangeError(ValueError):
    """The request can't be analysed as asked (unknown part, unit mismatch...). Shown to the user as-is."""


def _proposed_rec(data: dict, entity_id: str, param: str, value: float, unit: str, status: str = "proposed") -> dict:
    ev_id = f"EV-PROPOSED-{entity_id}-{param.upper().replace('_', '-')}"
    rec = {"value": float(value), "unit": unit, "evidence_id": ev_id, "status": status}
    if ev_id not in data["evidence_index"]:
        ev = {"id": ev_id, "entity_id": entity_id, "property": param, "value": float(value), "unit": unit,
              "source_document_id": "CHANGE-PROPOSAL", "source_location": "Proposed by the engineer",
              "status": "proposed", "revision": "-"}
        data["evidence"].append(ev)
        data["evidence_index"][ev_id] = ev
    return rec


def _same(a: dict | None, b: dict | None) -> bool:
    if a is None or b is None:
        return a is b
    try:
        return abs(convert(b["value"], b["unit"], a["unit"]) - a["value"]) < 1e-9
    except UnitError:
        return False


def resolve_change(data: dict, req: ChangeRequest) -> dict:
    by_id = data["by_id"]
    target = by_id.get(req.target_entity_id)
    if not target or target["type"] not in ("component", "subsystem"):
        raise ChangeError(f"Unknown part '{req.target_entity_id}'. Pick a component from the project.")
    base = State(data)
    after = base
    changes: list[dict] = []
    replacement = None
    tid = target["id"]

    if req.replacement_id:
        item = data["catalog_by_id"].get(req.replacement_id)
        if not item:
            raise ChangeError(f"'{req.replacement_id}' is not in the parts catalogue.")
        if item["category"] != target.get("category"):
            raise ChangeError(f"{item['name']} is a {item['category']}; {target['name']} is a {target.get('category')}.")
        after = base.with_replacement(tid, item["id"])
        for p in sorted(set(base.base_params(tid)) | set(item["parameters"])):
            b, a = base.get(tid, p), after.get(tid, p)
            if not _same(b, a):
                changes.append({"param": p, "label": base.label(p), "before": b, "after": a, "note": ""})
        replacement = {"id": item["id"], "name": item["name"], "unit_cost": item["parameters"]["unit_cost"]["value"],
                       "lead_time_days": item.get("lead_time_days"), "evidence_id": item["evidence_id"]}
        desc = f"Replace {target['name']} ({tid}) with {item['name']} ({item['id']})"
    else:
        param = req.parameter
        try:
            unit_in = normalize_unit(req.unit)
        except UnitError as e:
            raise ChangeError(str(e))
        before = base.get(tid, param)
        if before is not None:
            try:
                new_val = convert(req.proposed_value, unit_in, before["unit"])
            except UnitError:
                raise ChangeError(f"Unit mismatch: {base.label(param)} of {target['name']} is recorded in {before['unit']}, "
                                  f"but the change is in {unit_in}. Ripple doesn't convert between different quantities.")
            unit = before["unit"]
        else:
            new_val, unit = req.proposed_value, unit_in
        rec = _proposed_rec(data, tid, param, new_val, unit)
        after = after.with_override(tid, param, rec)
        if not _same(before, rec):
            changes.append({"param": param, "label": base.label(param), "before": before, "after": rec, "note": ""})
        # parameters that can't be assumed unchanged
        for dep in data["project"].get("param_dependencies", {}).get(param, []):
            if dep in req.parameter_overrides:
                continue
            b = base.get(tid, dep)
            if b is not None:
                after = after.with_override(tid, dep, None)
                changes.append({"param": dep, "label": base.label(dep), "before": b, "after": None,
                                "note": f"No longer assumed: {base.label(dep).lower()} depends on {base.label(param).lower()} and the new value isn't recorded."})
        desc = (f"Change {base.label(param).lower()} of {target['name']} ({tid}) from "
                f"{fmt(before['value'], before['unit']) if before else 'unrecorded'} to {fmt(new_val, unit)}")

    for p, pv in req.parameter_overrides.items():
        b = base.get(tid, p)
        try:
            unit_in = normalize_unit(pv.unit)
            val = convert(pv.value, unit_in, b["unit"]) if b else pv.value
        except UnitError as e:
            raise ChangeError(f"{p}: {e}")
        rec = _proposed_rec(data, tid, p, val, b["unit"] if b else unit_in)
        after = after.with_override(tid, p, rec)
        changes = [c for c in changes if c["param"] != p]
        if not _same(b, rec):
            changes.append({"param": p, "label": base.label(p), "before": b, "after": rec, "note": "Supplied with the change."})

    if not changes:
        raise ChangeError("That change doesn't differ from what's already recorded.")
    return {"target": target, "base": base, "after": after, "changes": changes, "replacement": replacement,
            "description": req.change_description or desc}
