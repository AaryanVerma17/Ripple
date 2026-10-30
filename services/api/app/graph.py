"""Impact tracing over typed, directed relationships.

A change spreads along an edge only if that edge type carries the *kind* of change (see EDGE_RULES).
For example a motor's voltage *rating* does not travel up the supply chain, but a change to the
battery's *supply* voltage travels down it. A regulator can isolate a kind of change, so parts
behind it are reported as unaffected, with the reason."""
from __future__ import annotations

from collections import deque

ALL = "*"
ELECTRICAL = {"rating", "load", "supply"}  # kinds that travel across electrical links; mass and cost do not

# edge type -> kinds carried when walking source->target ("fwd") or target->source ("rev")
EDGE_RULES: dict[str, dict] = {
    "INTERFACES_WITH": {"fwd": ELECTRICAL, "rev": ELECTRICAL, "why": "is electrically interfaced with"},
    "CONNECTS": {"fwd": ELECTRICAL, "rev": ELECTRICAL, "why": "is wired to"},
    "POWERED_BY": {"fwd": {"load"}, "rev": {"supply"}, "why": "shares a power supply with"},
    "DRIVES": {"fwd": {"mech", "perf"}, "rev": {"mech", "perf", "load"}, "why": "is mechanically coupled to"},
    "MOUNTED_ON": {"fwd": {"mech"}, "rev": {"mech"}, "why": "is mounted on"},
    "CONTROLS": {"fwd": {"control"}, "rev": {"control"}, "why": "is controlled with"},
}
KIND_NAMES = {"rating": "a rating", "load": "its load", "supply": "supply voltage / energy", "mech": "mechanical properties",
              "perf": "performance", "cost": "cost", "control": "control interface"}


def _edge_sentence(edge: dict, direction: str, a: str, b: str) -> str:
    t = edge["type"]
    if t == "POWERED_BY":
        return f"{a} draws power from {b}" if direction == "fwd" else f"{b} is supplied by {a}"
    if t == "DRIVES":
        return f"{a} drives {b}" if direction == "fwd" else f"{b} is driven by {a}"
    if t == "MOUNTED_ON":
        return f"{a} is mounted on {b}" if direction == "fwd" else f"{b} is mounted on {a}"
    if t == "CONNECTS":
        return f"{a} is wired to {b}" if direction == "fwd" else f"{b} is wired to {a}"
    if t == "INTERFACES_WITH":
        return f"{a} interfaces with {b}"
    if t == "CONTROLS":
        return f"{a} controls {b}" if direction == "fwd" else f"{b} controls {a}"
    return f"{a} – {b}"


def _adjacency(rels: list[dict]) -> dict:
    adj: dict[str, list] = {}
    for e in rels:
        if e["type"] in EDGE_RULES:
            adj.setdefault(e["source_id"], []).append((e["target_id"], e, "fwd"))
            adj.setdefault(e["target_id"], []).append((e["source_id"], e, "rev"))
    return adj


def trace(data: dict, sources: list[tuple[str, set, int]], max_depth: int = 6) -> dict:
    """Breadth-first spread over components/subsystems.

    sources: (entity_id, kinds_of_change, starting_hop)
    returns {"reached": {id: {hop, path, via, kinds}}, "isolated": {id: isolating_id}}"""
    by_id = data["by_id"]
    adj = _adjacency(data["relationships"])
    reached: dict[str, dict] = {}
    isolated: dict[str, str] = {}
    queue: deque[str] = deque()
    src_ids = {s[0] for s in sources}
    for sid, kinds, hop in sources:
        if sid not in reached or reached[sid]["hop"] > hop:
            reached[sid] = {"hop": hop, "path": [sid], "via": [], "kinds": set(kinds)}
            queue.append(sid)
    while queue:
        cur = queue.popleft()
        info = reached[cur]
        if info["hop"] >= max_depth:
            continue
        iso = set(by_id[cur].get("isolates", [])) if cur not in src_ids else set()
        kinds_out = info["kinds"] - iso
        blocked = bool(info["kinds"] & iso)
        for nb, edge, direction in adj.get(cur, []):
            nb_ent = by_id[nb]
            if nb_ent["type"] not in ("component", "subsystem"):
                continue
            allowed = EDGE_RULES[edge["type"]][direction]
            carried = set(kinds_out) if allowed == ALL else (set(kinds_out) & allowed)
            if not carried:
                if blocked and (allowed == ALL or (info["kinds"] & iso & allowed)) and nb not in reached:
                    isolated.setdefault(nb, cur)
                continue
            nh = info["hop"] + 1
            if nb in reached and reached[nb]["hop"] <= nh:
                continue
            step = {"edge_id": edge["id"], "type": edge["type"], "direction": direction, "from": cur, "to": nb,
                    "why": _edge_sentence(edge, direction, by_id[cur]["name"], nb_ent["name"])}
            reached[nb] = {"hop": nh, "path": info["path"] + [nb], "via": info["via"] + [step], "kinds": carried}
            isolated.pop(nb, None)
            queue.append(nb)
    return {"reached": reached, "isolated": isolated}


def derived_impacts(data: dict, reached: dict, requirement_ids: list[str], doc_entities: set[str]) -> list[dict]:
    """Requirements, tests and documents that follow from the reached components.

    requirement_ids: requirements whose result changed materially or fails.
    doc_entities: parts that actually change (their documents need updating)."""
    by_id = data["by_id"]
    rels = data["relationships"]
    out: list[dict] = []
    seen: set[str] = set()

    def add(eid, hop, path, via, note):
        if eid in seen:
            return
        seen.add(eid)
        out.append({"entity_id": eid, "hop": hop, "path": path, "via": via, "note": note})

    # requirements
    for rid in requirement_ids:
        best = None
        for r in rels:
            if r["type"] == "SATISFIES" and r["target_id"] == rid and r["source_id"] in reached:
                h = reached[r["source_id"]]["hop"]
                if best is None or h < best[0]:
                    best = (h, r["source_id"])
        if best:
            src = best[1]
            add(rid, best[0] + 1, reached[src]["path"] + [rid], reached[src]["via"], "Satisfied by an affected part.")
        else:
            root = min(reached, key=lambda k: reached[k]["hop"]) if reached else None
            add(rid, 1, ([root, rid] if root else [rid]), [], "System-level result changed.")
    # tests verifying reached entities or impacted requirements
    for r in rels:
        if r["type"] != "VERIFIED_BY":
            continue
        s, t = r["source_id"], r["target_id"]
        if s in reached:
            add(t, reached[s]["hop"] + 1, reached[s]["path"] + [t], reached[s]["via"], "Verifies an affected part.")
        elif s in seen and by_id[s]["type"] == "requirement":
            prev = next(o for o in out if o["entity_id"] == s)
            add(t, prev["hop"] + 1, prev["path"] + [t], prev["via"], "Verifies an affected requirement.")
    # documents of reached components
    for r in rels:
        if r["type"] == "DOCUMENTED_BY" and r["source_id"] in reached and r["source_id"] in doc_entities:
            s = r["source_id"]
            add(r["target_id"], reached[s]["hop"] + 1, reached[s]["path"] + [r["target_id"]], reached[s]["via"],
                "Documents a part that changes.")
    return out


def unaffected_reasons(data: dict, reached: dict, isolated: dict, kinds: set) -> list[dict]:
    by_id = data["by_id"]
    kind_text = ", ".join(KIND_NAMES.get(k, k) for k in sorted(kinds)) or "this change"
    out = []
    for e in data["entities"]:
        if e["type"] not in ("component", "subsystem") or e["id"] in reached:
            continue
        if e["id"] in isolated:
            iso = isolated[e["id"]]
            reason = f"Isolated by {by_id[iso]['name']} ({iso}), which regulates its own output."
        else:
            reason = f"No recorded relationship carries {kind_text} to it."
        out.append({"entity_id": e["id"], "name": e["name"], "reason": reason})
    return out
