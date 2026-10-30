from collections import deque
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any
from .seed import dataset
from .schemas import ChangeRequest

# Traversal is intentionally limited to typed, explicit edges. Unknown edge types are not used.
TRAVERSABLE = {"DEPENDS_ON", "CONTRIBUTES_TO", "SUPPLIES", "SUBJECT_TO", "VERIFIED_BY", "AFFECTS", "DOCUMENTED_BY"}
REVERSE_TRAVERSABLE = {"DEPENDS_ON", "CONTRIBUTES_TO", "SUPPLIES", "SUBJECT_TO", "VERIFIED_BY", "AFFECTS", "DOCUMENTED_BY"}

def trace_impacts(target_id: str, entities: list[dict], relationships: list[dict], max_depth: int = 5) -> list[dict]:
    """Trace impacts along explicitly directed relationships only.

    The edge direction is treated as authored model semantics; we do not reverse
    edges merely to increase recall because that creates false-positive impacts.
    """
    entity_ids = {e["id"] for e in entities}
    if target_id not in entity_ids:
        raise ValueError(f"Unknown target entity: {target_id}")
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for edge in relationships:
        if edge["type"] not in TRAVERSABLE:
            continue
        a, b = edge["source_id"], edge["target_id"]
        if a in entity_ids and b in entity_ids:
            adjacency.setdefault(a, []).append((b, edge["type"]))
    queue = deque([(target_id, [target_id], 0)])
    visited_depth = {target_id: 0}
    impacts = []
    while queue:
        current, path, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for neighbor, edge_type in adjacency.get(current, []):
            # DEPENDS_ON records what an entity relies on; do not recursively
            # traverse the dependency's own dependencies as if they were impacted.
            if edge_type == "DEPENDS_ON" and current != target_id:
                continue
            if neighbor in path:
                continue
            next_depth = depth + 1
            if neighbor in visited_depth and visited_depth[neighbor] <= next_depth:
                continue
            visited_depth[neighbor] = next_depth
            next_path = path + [neighbor]
            impacts.append({"entity_id": neighbor, "depth": next_depth, "impact_type": "direct" if next_depth == 1 else "indirect", "path": next_path, "edge_type": edge_type})
            queue.append((neighbor, next_path, next_depth))
    return impacts

def check_upper_bound(value: float | None, maximum: float | None, unit: str = "") -> dict[str, Any]:
    if value is None or maximum is None:
        return {"status":"unknown","reason":"Required value or limit is missing."}
    if value > maximum:
        return {"status":"verified_issue","reason":f"Value {value:g} {unit} exceeds maximum {maximum:g} {unit}."}
    return {"status":"no_violation_found","reason":f"Value {value:g} {unit} is within maximum {maximum:g} {unit}."}

def calculate_power(voltage: float, current: float) -> dict[str, Any]:
    if voltage < 0 or current < 0:
        raise ValueError("Voltage and current must be non-negative.")
    return {"name":"DC electrical power","formula":"P = V * I","inputs":{"voltage":{"value":voltage,"unit":"V"},"current":{"value":current,"unit":"A"}},"result":{"value":round(voltage*current, 6),"unit":"W"},"assumptions":["DC values; supplied current is applicable to the operating condition."],"status":"computed"}

def analyze_change(request: ChangeRequest, live_ai: bool = False, ai_synthesis: dict | None = None) -> dict:
    data = dataset()
    entities = data["entities"]
    by_id = {e["id"]: e for e in entities}
    target = by_id.get(request.target_entity_id)
    if not target:
        raise ValueError(f"Unknown target entity: {request.target_entity_id}")
    old_param = target.get("parameters", {}).get(request.parameter)
    baseline = old_param.get("value") if old_param else None
    baseline_unit = old_param.get("unit") if old_param else None
    if baseline is not None and baseline_unit != request.unit:
        raise ValueError(f"Unit mismatch: baseline is {baseline_unit}, request is {request.unit}. MVP does not silently convert units.")
    impacts = trace_impacts(request.target_entity_id, entities, data["relationships"])
    evidence_by_id = {e["id"]:e for e in data["evidence"]}
    findings = []
    counter = 1
    findings.append({
        "id":f"F-{counter:03d}","category":"change_scope","entity_id":request.target_entity_id,
        "status":"review_required","summary":f"{target['name']} parameter {request.parameter} proposed to change from {baseline if baseline is not None else 'unknown'} {baseline_unit or request.unit} to {request.proposed_value:g} {request.unit}.",
        "evidence_ids":[e["id"] for e in data["evidence"] if e["entity_id"]==request.target_entity_id and e["property"]==request.parameter],
        "impact_path":[request.target_entity_id],"recommended_action":"Confirm the proposed component specification and applicable operating conditions.","source":"rule_engine"
    })
    counter += 1
    # Only compare values where the data model explicitly says the changed parameter is applicable.
    # Motor rated voltage is NOT implicitly compared with driver input voltage.
    for constraint in data["constraints"]:
        if constraint["entity_id"] == request.target_entity_id and constraint["parameter"] == request.parameter:
            result = check_upper_bound(request.proposed_value, constraint["limit_value"], request.unit)
            findings.append({"id":f"F-{counter:03d}","category":"electrical_compatibility","entity_id":request.target_entity_id,"status":result["status"],"summary":result["reason"],"evidence_ids":[constraint["evidence_id"]] if constraint.get("evidence_id") in evidence_by_id else [],"impact_path":[request.target_entity_id],"recommended_action":"Review the applicable constraint and its controlled source before disposition.","source":"rule_engine"})
            counter += 1
    for impact in impacts:
        entity = by_id[impact["entity_id"]]
        if entity["type"] == "test":
            findings.append({"id":f"F-{counter:03d}","category":"verification_testing","entity_id":entity["id"],"status":"review_required","summary":f"Reconsider {entity['name']} because the recorded relationship path connects it to the changed entity.","evidence_ids":[],"impact_path":impact["path"],"recommended_action":"Confirm whether this test procedure and acceptance criteria remain applicable to the proposed revision.","source":"graph"})
            counter += 1
    unresolved = []
    if request.target_entity_id == "MTR-01" and request.parameter == "rated_voltage" and request.proposed_value != baseline:
        driver = by_id.get("DRV-01", {})
        driver_path = next((i["path"] for i in impacts if i["entity_id"] == "DRV-01"), [request.target_entity_id, "DRV-01"])
        # A motor's rated voltage is not the same quantity as the driver's input voltage.
        # Without a recorded driver output rating / actual supply rail, report uncertainty,
        # not a fabricated verified violation.
        findings.append({"id":f"F-{counter:03d}","category":"electrical_compatibility","entity_id":"DRV-01","status":"unknown","summary":"Driver compatibility cannot be confirmed: the fixture records an 18 V maximum input, but does not record the driver's output-voltage capability or establish the proposed motor's actual supply rail. The 24 V motor rating is not directly comparable to the driver's input limit.","evidence_ids":["EV-DRV-01"] if "EV-DRV-01" in evidence_by_id else [],"impact_path":driver_path,"recommended_action":"Verify the controlled driver input and output ratings, motor supply topology, and the actual rail voltage before declaring compatibility or a violation.","source":"rule_engine"})
        counter += 1
        unresolved.extend([
            "Confirm the actual motor supply rail and driver output-voltage configuration.",
            "Driver input limit is not interchangeable with motor rated voltage; the applicable electrical path and output rating are not recorded.",
            "Wiring and connector current ratings are missing.",
            "Runtime impact cannot be quantified without representative current/load data."
        ])
    if baseline is None:
        unresolved.append(f"No baseline value is recorded for {request.target_entity_id}.{request.parameter}.")
    required_tests = sorted({f["entity_id"] for f in findings if f["category"]=="verification_testing" and f.get("entity_id")})
    report = {
        "analysis_id":f"AN-{uuid4().hex[:10].upper()}","project_id":data["project"]["id"],"status":"completed",
        "overall_status":"review_required","change_summary":request.change_description,"findings":findings,
        "calculations":[],"unresolved_questions":unresolved,"required_tests":required_tests,
        "direct_impacts":sum(1 for i in impacts if i["impact_type"]=="direct"),
        "indirect_impacts":sum(1 for i in impacts if i["impact_type"]=="indirect"),
        "ai_synthesis":ai_synthesis,"requires_engineer_review":True,
        "created_at":datetime.now(timezone.utc).isoformat(),
        "change":{"target_entity_id":request.target_entity_id,"parameter":request.parameter,"baseline_value":baseline,"baseline_unit":baseline_unit,"proposed_value":request.proposed_value,"unit":request.unit,"reason":request.reason},
        "impacts":impacts,
        "fixture_notice":"Fictional sample data. Findings are illustrative and are not an engineering approval."
    }
    return report
