"""Loads the project model and expands it: parameters get provenance, evidence records are generated,
and engineer-supplied values from the store are merged in (clearly marked as such)."""
from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from . import store

DATA_FILE = Path(__file__).parent / "data" / "rover_alpha.json"


@lru_cache(maxsize=1)
def _raw() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _slug(text: str) -> str:
    return text.upper().replace("_", "-")


def _expand_params(owner_id: str, params: dict, evidence: list[dict], source_doc: str, status: str,
                   evidence_per_param: bool = True, shared_evidence_id: str | None = None) -> dict:
    out = {}
    for key, raw in params.items():
        value, unit = raw[0], raw[1]
        ev_id = shared_evidence_id or f"EV-{owner_id}-{_slug(key)}"
        rec = {"value": float(value), "unit": unit, "evidence_id": ev_id, "status": status}
        out[key] = rec
        if evidence_per_param:
            evidence.append({
                "id": ev_id, "entity_id": owner_id, "property": key, "value": float(value), "unit": unit,
                "source_document_id": source_doc, "source_location": "Fixture parameter table",
                "status": status, "revision": "A",
            })
    return out


def get_dataset() -> dict:
    """Fresh, fully expanded copy of the project data (safe to mutate)."""
    raw = deepcopy(_raw())
    evidence: list[dict] = []
    docs_for: dict[str, str] = {}
    for rel in raw["relationships"]:
        if rel["type"] == "DOCUMENTED_BY":
            docs_for[rel["source_id"]] = rel["target_id"]
    for e in raw["entities"]:
        if "parameters" in e:
            e["parameters"] = _expand_params(e["id"], e["parameters"], evidence,
                                             docs_for.get(e["id"], "FIXTURE"), "fictional_sample")
    for c in raw["catalog"]:
        ev_id = f"EV-CAT-{c['id']}"
        c["evidence_id"] = ev_id
        c["parameters"] = _expand_params(c["id"], c["parameters"], evidence, "CATALOG", "catalog_listing",
                                         evidence_per_param=False, shared_evidence_id=ev_id)
        evidence.append({
            "id": ev_id, "entity_id": c["id"], "property": "*", "value": None, "unit": "",
            "source_document_id": "CATALOG", "source_location": f"Fictional catalogue listing for {c['id']}",
            "status": "catalog_listing", "revision": "A",
        })
    by_id = {e["id"]: e for e in raw["entities"]}
    for o in store.list_overrides():
        ent = by_id.get(o["entity_id"])
        if not ent or ent["type"] not in ("component", "subsystem"):
            continue
        ev_id = f"EV-ENG-{o['id']}"
        ent.setdefault("parameters", {})[o["param"]] = {
            "value": float(o["value"]), "unit": o["unit"], "evidence_id": ev_id, "status": "engineer_supplied"}
        evidence.append({
            "id": ev_id, "entity_id": o["entity_id"], "property": o["param"], "value": float(o["value"]),
            "unit": o["unit"], "source_document_id": "ENGINEER", "source_location": o.get("source_note") or "Supplied by engineer",
            "status": "engineer_supplied", "revision": "A", "author": o.get("author", ""),
        })
    raw["evidence"] = evidence
    raw["evidence_index"] = {ev["id"]: ev for ev in evidence}
    raw["by_id"] = by_id
    raw["catalog_by_id"] = {c["id"]: c for c in raw["catalog"]}
    return raw


def public_dataset() -> dict:
    d = get_dataset()
    for k in ("evidence_index", "by_id", "catalog_by_id"):
        d.pop(k, None)
    return d
