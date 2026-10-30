"""System-level numbers (speed, runtime, mass, cost, current), computed from recorded values only.

When an input is missing, or can't be derived honestly, the metric is `unavailable` with a reason.
Nothing is guessed."""
from __future__ import annotations

import math

from .state import State
from .units import convert, fmt

METRIC_LABELS = {
    "top_speed_mps": ("Top speed", "m/s"),
    "runtime_h": ("Runtime", "h"),
    "total_mass_kg": ("Total mass", "kg"),
    "bom_cost_usd": ("Parts cost (BOM)", "USD"),
    "peak_current_a": ("Peak battery current", "A"),
    "peak_power_w": ("Peak motor power", "W"),
    "avg_power_w": ("Average power", "W"),
}


def _inp(state: State, entity: str, param: str, unit: str | None = None):
    rec = state.get(entity, param)
    if rec is None:
        return None
    val = rec["value"] if unit is None else convert(rec["value"], rec["unit"], unit)
    return {"label": f"{state.part_name(entity)} · {state.label(param)}", "entity": entity, "param": param,
            "value": val, "unit": unit or rec["unit"], "evidence_id": rec.get("evidence_id"),
            "status": rec.get("status")}


def _m(name, value, formula, inputs, assumptions=None, reason=None, model_assumption=False):
    label, unit = METRIC_LABELS[name]
    return {"name": name, "label": label, "unit": unit, "value": value, "status": "computed" if value is not None else "unavailable",
            "formula": formula, "inputs": [i for i in inputs if i], "assumptions": assumptions or [],
            "reason": reason, "model_assumption": model_assumption}


def _missing(state: State, pairs) -> list[str]:
    return [f"{state.part_name(e)} · {state.label(p)}" for e, p in pairs if state.get(e, p) is None]


def compute_metrics(state: State) -> dict:
    r = state.roles
    proj = state.data["project"]["assumptions"]
    lf = proj["load_factor"]["value"]
    M: dict = {}

    # ---- mass and cost: sum over every part with a recorded value
    mass_inputs, cost_inputs, mass_total, cost_total = [], [], 0.0, 0.0
    no_mass, no_cost = [], []
    for e in state.components():
        q = state.qty(e["id"])
        m = _inp(state, e["id"], "mass", "kg")
        c = _inp(state, e["id"], "unit_cost", "USD")
        if m:
            mass_total += q * m["value"]
            mass_inputs.append({**m, "label": f"{m['label']} × {q}"})
        elif e["type"] == "component":
            no_mass.append(e["name"])
        if c:
            cost_total += q * c["value"]
            cost_inputs.append({**c, "label": f"{c['label']} × {q}"})
        elif e["type"] == "component":
            no_cost.append(e["name"])
    M["total_mass_kg"] = _m("total_mass_kg", None if no_mass else mass_total, "Σ quantity × mass", mass_inputs,
                            reason=("Mass is not recorded for: " + ", ".join(no_mass)) if no_mass else None)
    M["bom_cost_usd"] = _m("bom_cost_usd", None if no_cost else cost_total, "Σ quantity × unit cost", cost_inputs,
                           reason=("Unit cost is not recorded for: " + ", ".join(no_cost)) if no_cost else None,
                           assumptions=["Parts only: no tax, shipping or tooling."])

    # ---- electrical operating point
    rail = _inp(state, r["rail"], "rail_voltage", "V")
    rated_v = _inp(state, r["motor"], "rated_voltage", "V")
    rated_i = _inp(state, r["motor"], "rated_current", "A")
    n0 = _inp(state, r["motor"], "no_load_speed_rpm", "rpm")
    dia = _inp(state, r["wheel"], "diameter_mm", "mm")
    nmot = state.qty(r["motor"])

    ratio = None
    if rail and rated_v and rated_v["value"] > 0:
        ratio = rail["value"] / rated_v["value"]

    # speed
    miss = _missing(state, [(r["rail"], "rail_voltage"), (r["motor"], "rated_voltage"),
                            (r["motor"], "no_load_speed_rpm"), (r["wheel"], "diameter_mm")])
    if miss:
        M["top_speed_mps"] = _m("top_speed_mps", None, "speed = rpm × π × diameter / 60", [rail, rated_v, n0, dia],
                                reason="Not recorded: " + ", ".join(miss))
    else:
        rpm = n0["value"] * ratio
        speed = rpm * math.pi * (dia["value"] / 1000.0) / 60.0
        scaled = abs(ratio - 1) > 0.02
        M["top_speed_mps"] = _m(
            "top_speed_mps", speed, "speed = no-load rpm × (rail ÷ rated voltage) × π × diameter ÷ 60",
            [rail, rated_v, n0, dia],
            assumptions=(["No-load speed scales linearly with voltage, so this is an estimate."] if scaled else [])
            + ["No-load speed; ignores load and wheel slip."],
            model_assumption=scaled)

    # motor current at the operating point
    cur = None
    cur_reason = None
    if ratio is not None and rated_i:
        if abs(ratio - 1) <= 0.10:
            cur = rated_i["value"]
        else:
            cur_reason = (f"The motor's current at {fmt(rail['value'], 'V')} isn't recorded, and it can't be derived "
                          f"from a rating at {fmt(rated_v['value'], 'V')}.")
    elif ratio is not None:
        cur_reason = f"{state.part_name(r['motor'])} · {state.label('rated_current')} is not recorded."
    else:
        cur_reason = "Rail voltage or motor rated voltage is not recorded."

    if cur is None:
        for name in ("peak_power_w", "avg_power_w", "runtime_h", "peak_current_a"):
            M[name] = _m(name, None, "", [rail, rated_v, rated_i], reason=cur_reason)
    else:
        peak_p = nmot * rail["value"] * cur
        ctrl = _inp(state, r["controller"], "power_draw", "W")
        energy = _inp(state, r["battery"], "usable_energy", "Wh")
        M["peak_power_w"] = _m("peak_power_w", peak_p, "P = motors × V × I", [rail, rated_i],
                               assumptions=["DC values; both motors at rated current."])
        M["peak_current_a"] = _m("peak_current_a", nmot * cur, "I = motors × motor current", [rated_i],
                                 assumptions=["Both motors at rated current at the same time."])
        if ctrl is None or energy is None:
            miss2 = _missing(state, [(r["controller"], "power_draw"), (r["battery"], "usable_energy")])
            M["avg_power_w"] = _m("avg_power_w", None, "", [ctrl], reason="Not recorded: " + ", ".join(miss2))
            M["runtime_h"] = _m("runtime_h", None, "", [energy], reason="Not recorded: " + ", ".join(miss2))
        else:
            avg = lf * peak_p + ctrl["value"]
            M["avg_power_w"] = _m("avg_power_w", avg, "P_avg = load factor × peak motor power + controller power",
                                  [rail, rated_i, ctrl],
                                  assumptions=[f"Average motor load is {lf:.0%} of peak (project assumption)."])
            M["runtime_h"] = _m("runtime_h", energy["value"] / avg, "t = usable energy ÷ average power",
                                [energy, ctrl, rated_i, rail],
                                assumptions=[f"Average motor load is {lf:.0%} of peak (project assumption).",
                                             "Ignores discharge curve, conversion losses and temperature."])
    return M
