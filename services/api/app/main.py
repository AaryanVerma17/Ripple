import time
from collections import defaultdict, deque

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from . import ai, store, vision
from .analysis import analyze_change
from .chat import handle_chat
from .config import settings
from .dataset import get_dataset, public_dataset
from .llm import LLMError
from .metrics import compute_metrics
from .report_md import to_markdown
from .resolve import ChangeError
from .schemas import ChangeRequest, ChatRequest, DecisionRequest, ParameterSupply
from .state import State
from .units import UnitError, dimension, normalize_unit
from .validator import validate_report

app = FastAPI(title="Ripple API", version="2.0.0", description="Engineering Change Impact Agent API")
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "Authorization"])

_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request) -> None:
    """Small per-client limiter for endpoints that call a paid model."""
    key = request.client.host if request.client else "local"
    now, q = time.monotonic(), _hits[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= settings.ai_rate_limit_per_minute:
        raise HTTPException(429, "Too many requests. Wait a minute and try again.")
    q.append(now)


def _check_project(pid: str) -> dict:
    d = get_dataset()
    if pid != d["project"]["id"]:
        raise HTTPException(404, "Project not found")
    return d


@app.get("/health")
def health():
    return {"status": "ok", "service": "ripple-api", "version": app.version, "environment": settings.app_env,
            "text_ai": settings.text_ai_configured, "vision": settings.vision_resolved}


@app.get("/api/v1/config")
def config():
    return {"text_ai": settings.text_ai_configured, "text_model": settings.nebius_model or None,
            "vision": settings.vision_resolved, "max_upload_mb": settings.max_upload_mb}


@app.get("/api/v1/projects")
def projects():
    return [get_dataset()["project"]]


@app.get("/api/v1/projects/{pid}")
def project(pid: str):
    d = _check_project(pid)
    return {**d["project"], "entity_count": len(d["entities"]), "relationship_count": len(d["relationships"]),
            "catalog_count": len(d["catalog"]), "fictional_fixture": True}


@app.get("/api/v1/projects/{pid}/graph")
def graph(pid: str):
    _check_project(pid)
    d = public_dataset()
    return {"project": d["project"], "nodes": d["entities"], "edges": d["relationships"]}


@app.get("/api/v1/projects/{pid}/entities")
def entities(pid: str):
    _check_project(pid)
    return public_dataset()["entities"]


@app.get("/api/v1/projects/{pid}/catalog")
def catalog(pid: str):
    _check_project(pid)
    return public_dataset()["catalog"]


@app.get("/api/v1/projects/{pid}/bom")
def bom(pid: str):
    d = _check_project(pid)
    rows, total = [], 0.0
    for e in d["entities"]:
        if e["type"] != "component":
            continue
        c = e.get("parameters", {}).get("unit_cost")
        qty = e.get("qty", 1)
        line = c["value"] * qty if c else None
        total += line or 0
        rows.append({"id": e["id"], "name": e["name"], "category": e.get("category"), "qty": qty,
                     "unit_cost": c and c["value"], "line_cost": line,
                     "mass_kg": (e.get("parameters", {}).get("mass") or {}).get("value"),
                     "alternatives": [{"id": i["id"], "name": i["name"], "unit_cost": i["parameters"]["unit_cost"]["value"]}
                                      for i in d["catalog"] if i["category"] == e.get("category")]})
    m = compute_metrics(State(d))
    return {"rows": rows, "total_cost": total,
            "metrics": {k: {"value": v["value"], "unit": v["unit"], "label": v["label"], "reason": v.get("reason")} for k, v in m.items()},
            "budget": next((e["threshold"] for e in d["entities"] if e["id"] == "REQ-COST-01" and "threshold" in e), None)}


@app.get("/api/v1/projects/{pid}/audit")
def audit(pid: str):
    """Which recorded values are missing, who supplied what, and which are only assumed."""
    d = _check_project(pid)
    labels = d["project"]["param_labels"]
    needed: dict[str, set] = {}
    for r in d["rules"]:
        for side in ("lhs", "rhs"):
            ref = r.get(side)
            if isinstance(ref, dict) and ref.get("entity") in d["by_id"]:
                needed.setdefault(ref["entity"], set()).add(ref["param"])
    unit_of: dict[str, str] = {}
    for e in d["entities"]:
        for k, v in e.get("parameters", {}).items():
            unit_of.setdefault(k, v["unit"])
    for c in d["catalog"]:
        for k, v in c["parameters"].items():
            unit_of.setdefault(k, v["unit"])
    missing = []
    for eid, params in needed.items():
        for p in sorted(params):
            if p not in d["by_id"][eid].get("parameters", {}) and p != "rail_voltage":
                missing.append({"entity_id": eid, "name": d["by_id"][eid]["name"], "parameter": p, "label": labels.get(p, p), "unit": unit_of.get(p, ""),
                                "needed_for": [r["id"] for r in d["rules"] if any(isinstance(r.get(s), dict) and r[s].get("entity") == eid and r[s].get("param") == p for s in ("lhs", "rhs"))]})
    return {"missing": missing, "overrides": store.list_overrides(), "assumptions": d["project"]["assumptions"]}


@app.post("/api/v1/projects/{pid}/parameters")
def supply_parameter(pid: str, body: ParameterSupply):
    d = _check_project(pid)
    ent = d["by_id"].get(body.entity_id)
    if not ent or ent["type"] != "component":
        raise HTTPException(422, "Unknown part.")
    if body.parameter not in d["project"]["param_kinds"]:
        raise HTTPException(422, "Unknown parameter.")
    try:
        unit = normalize_unit(body.unit)
        existing = ent.get("parameters", {}).get(body.parameter)
        if existing and dimension(existing["unit"]) != dimension(unit):
            raise HTTPException(422, f"{body.parameter} is measured in {existing['unit']}, not {body.unit}.")
    except UnitError as e:
        raise HTTPException(422, str(e))
    if body.value <= 0 and body.parameter != "unit_cost":
        raise HTTPException(422, "Value must be positive.")
    return store.add_override(body.entity_id, body.parameter, body.value, unit, body.source_note, body.author)


@app.delete("/api/v1/projects/{pid}/parameters")
def reset_parameters(pid: str):
    _check_project(pid)
    return {"removed": store.clear_overrides()}


@app.get("/api/v1/projects/{pid}/history")
def history(pid: str):
    _check_project(pid)
    return store.list_analyses()


@app.post("/api/v1/projects/{pid}/changes")
async def create_change(pid: str, request: ChangeRequest, http: Request):
    d = _check_project(pid)
    try:
        report = analyze_change(request)
    except ChangeError as exc:
        raise HTTPException(422, str(exc))
    report["validation"] = validate_report(report, d)
    if settings.text_ai_configured:
        rate_limit(http)
    report["ai_synthesis"] = await ai.synthesize(report, d)
    store.save_analysis(report, kind=request.kind)
    return store.get_analysis(report["analysis_id"])


@app.get("/api/v1/analyses")
def analyses():
    return store.list_analyses()


@app.get("/api/v1/analyses/{aid}")
def get_analysis(aid: str):
    r = store.get_analysis(aid)
    if not r:
        raise HTTPException(404, "Analysis not found")
    return r


@app.get("/api/v1/analyses/{aid}/report")
def get_report(aid: str):
    return get_analysis(aid)


@app.get("/api/v1/analyses/{aid}/export.md", response_class=PlainTextResponse)
def export_md(aid: str):
    return PlainTextResponse(to_markdown(get_analysis(aid)), media_type="text/markdown; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{aid}.md"'})


@app.post("/api/v1/analyses/{aid}/decision")
def decision(aid: str, request: DecisionRequest):
    if not store.get_analysis(aid):
        raise HTTPException(404, "Analysis not found")
    return store.save_decision(aid, request.model_dump())


@app.post("/api/v1/projects/{pid}/chat")
async def chat(pid: str, body: ChatRequest, http: Request):
    _check_project(pid)
    rate_limit(http)
    return await handle_chat(body)


@app.post("/api/v1/projects/{pid}/vision/identify")
async def identify(pid: str, http: Request, image: UploadFile = File(...), hint: str = Form(default="")):
    d = _check_project(pid)
    rate_limit(http)
    raw = await image.read(int(settings.max_upload_mb * 1024 * 1024) + 1)
    try:
        return await vision.identify(raw, d, hint or None)
    except vision.ImageError as e:
        raise HTTPException(422, str(e))
    except LLMError as e:
        raise HTTPException(503, str(e))
