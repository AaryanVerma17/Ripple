"""A State is the product as it would be after a set of changes: the baseline plus part swaps and
parameter overrides. States are cheap to copy, so each scenario gets its own."""
from __future__ import annotations

from typing import Optional


class State:
    def __init__(self, data: dict, replacements: Optional[dict] = None, overrides: Optional[dict] = None):
        self.data = data
        self.by_id: dict = data["by_id"]
        self.catalog: dict = data["catalog_by_id"]
        self.roles: dict = data["project"]["roles"]
        self.rail_follows: Optional[dict] = data["project"].get("rail_follows")
        self.replacements: dict[str, str] = dict(replacements or {})
        self.overrides: dict[tuple[str, str], Optional[dict]] = dict(overrides or {})

    def copy(self) -> "State":
        return State(self.data, self.replacements, self.overrides)

    # ---- building new states
    def with_replacement(self, entity_id: str, catalog_id: str) -> "State":
        s = self.copy()
        s.replacements[entity_id] = catalog_id
        # a swap supersedes earlier single-parameter overrides on that entity
        s.overrides = {k: v for k, v in s.overrides.items() if k[0] != entity_id}
        return s

    def with_override(self, entity_id: str, param: str, rec: Optional[dict]) -> "State":
        s = self.copy()
        s.overrides[(entity_id, param)] = rec
        return s

    # ---- reading
    def base_params(self, entity_id: str) -> dict:
        if entity_id in self.replacements:
            return self.catalog[self.replacements[entity_id]]["parameters"]
        return self.by_id[entity_id].get("parameters", {})

    def get(self, entity_id: str, param: str) -> Optional[dict]:
        key = (entity_id, param)
        if key in self.overrides:
            return self.overrides[key]
        if self.rail_follows and entity_id == self.roles.get("rail") and param == "rail_voltage":
            f = self.rail_follows
            rec = self.get(f["entity"], f["param"])
            if rec:
                return {**rec, "followed_from": f["entity"]}
        return self.base_params(entity_id).get(param)

    def value(self, entity_id: str, param: str) -> Optional[float]:
        rec = self.get(entity_id, param)
        return None if rec is None else rec["value"]

    def qty(self, entity_id: str) -> int:
        return int(self.by_id[entity_id].get("qty", 1))

    def part_id(self, entity_id: str) -> str:
        return self.replacements.get(entity_id, entity_id)

    def part_name(self, entity_id: str) -> str:
        if entity_id in self.replacements:
            return self.catalog[self.replacements[entity_id]]["name"]
        return self.by_id[entity_id]["name"]

    def label(self, param: str) -> str:
        return self.data["project"]["param_labels"].get(param, param.replace("_", " "))

    def components(self) -> list[dict]:
        return [e for e in self.data["entities"] if e["type"] in ("component", "subsystem")]
