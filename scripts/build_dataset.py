"""Builds services/api/app/data/rover_alpha.json and the CSV exports in data/sample_product/.

Everything here is FICTIONAL sample data for demonstrating Ripple. Part numbers, prices and
ratings are invented and must never be used for a real design.

Usage:  python scripts/build_dataset.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_OUT = ROOT / "services" / "api" / "app" / "data" / "rover_alpha.json"
CSV_DIR = ROOT / "data" / "sample_product"

# Parameters are written compactly as [value, unit]; the API loader expands them and
# generates one evidence record per parameter.
ENTITIES = [
    dict(id="MTR-01", type="component", name="Drive motor", category="motor", qty=2,
         aliases=["motor", "motors", "drive motor", "dc motor", "wheel motor"],
         description="Brushed DC gear motor, one per drive wheel.",
         parameters={"rated_voltage": [12, "V"], "rated_current": [4, "A"], "no_load_speed_rpm": [300, "rpm"],
                     "mass": [0.42, "kg"], "unit_cost": [28, "USD"], "mount_pitch_mm": [31, "mm"],
                     "shaft_diameter_mm": [6, "mm"]}),
    dict(id="DRV-01", type="component", name="Motor driver", category="driver", qty=1,
         aliases=["driver", "motor driver", "h-bridge", "h bridge", "motor controller board"],
         description="Dual-channel DC motor driver.",
         parameters={"input_voltage_min": [9, "V"], "input_voltage_max": [18, "V"], "channel_current_max": [5, "A"],
                     "mass": [0.06, "kg"], "unit_cost": [16, "USD"]}),
    dict(id="BAT-01", type="component", name="Battery pack", category="battery", qty=1,
         aliases=["battery", "pack", "battery pack", "cell", "cells", "lipo"],
         description="Rechargeable battery pack feeding the main power rail.",
         parameters={"nominal_voltage": [12, "V"], "usable_energy": [96, "Wh"], "max_discharge_current": [15, "A"],
                     "mass": [0.9, "kg"], "unit_cost": [42, "USD"]}),
    dict(id="PWR-01", type="subsystem", name="Main power rail", category="rail", qty=1,
         aliases=["rail", "power rail", "supply", "power system", "main rail"],
         description="Distribution rail between the battery, the driver and the regulator.",
         parameters={"rail_voltage": [12, "V"]}),
    dict(id="REG-01", type="component", name="5 V regulator", category="regulator", qty=1,
         aliases=["regulator", "buck", "converter", "buck converter", "5v regulator"],
         description="Buck regulator that isolates the controller from the main rail.",
         isolates=["supply"],
         parameters={"input_voltage_min": [7, "V"], "input_voltage_max": [20, "V"], "mass": [0.02, "kg"],
                     "unit_cost": [6, "USD"]}),
    dict(id="CTRL-01", type="component", name="Main controller", category="controller", qty=1,
         aliases=["controller", "mcu", "microcontroller", "brain", "main controller"],
         description="Motion controller board, supplied at 5 V by REG-01.",
         parameters={"power_draw": [5, "W"], "mass": [0.05, "kg"], "unit_cost": [22, "USD"]}),
    dict(id="WIR-01", type="component", name="Motor wiring harness", category="wiring", qty=1,
         aliases=["wiring", "harness", "wires", "wire", "cable", "cables", "wiring harness"],
         description="Harness between the driver outputs and the motors. Ratings are deliberately NOT recorded in this fixture.",
         parameters={"mass": [0.15, "kg"], "unit_cost": [9, "USD"]}),
    dict(id="CHS-01", type="component", name="Chassis", category="chassis", qty=1,
         aliases=["chassis", "frame", "body", "base plate"],
         description="Aluminium base chassis.",
         parameters={"mass": [3.2, "kg"], "unit_cost": [60, "USD"]}),
    dict(id="BRK-01", type="component", name="Motor bracket", category="bracket", qty=2,
         aliases=["bracket", "brackets", "mount", "motor mount", "motor bracket"],
         description="Bracket that fixes a motor to the chassis.",
         parameters={"mount_pitch_mm": [31, "mm"], "mass": [0.08, "kg"], "unit_cost": [5, "USD"]}),
    dict(id="WHL-01", type="component", name="Drive wheel", category="wheel", qty=2,
         aliases=["wheel", "wheels", "tire", "tyre"],
         description="Drive wheel pressed onto the motor shaft.",
         parameters={"diameter_mm": [120, "mm"], "bore_diameter_mm": [6, "mm"], "mass": [0.18, "kg"],
                     "unit_cost": [11, "USD"]}),
    # Requirements
    dict(id="REQ-PWR-01", type="requirement", name="Electrical limits respected", category="requirement",
         statement="Every powered component must operate within its documented electrical limits.",
         group="electrical", aliases=["electrical requirement"]),
    dict(id="REQ-RUN-01", type="requirement", name="Runtime target", category="requirement",
         statement="The rover shall run for at least 1.5 hours on one charge at the standard duty cycle.",
         metric="runtime_h", operator=">=", threshold=1.5, unit="h", aliases=["runtime"]),
    dict(id="REQ-SPD-01", type="requirement", name="Top speed", category="requirement",
         statement="The rover shall reach at least 1.5 m/s on level ground.",
         metric="top_speed_mps", operator=">=", threshold=1.5, unit="m/s", aliases=["speed", "top speed"]),
    dict(id="REQ-MASS-01", type="requirement", name="Mass limit", category="requirement",
         statement="The assembled rover shall not exceed 6.0 kg.",
         metric="total_mass_kg", operator="<=", threshold=6.0, unit="kg", aliases=["mass limit", "weight limit"]),
    dict(id="REQ-COST-01", type="requirement", name="Parts budget", category="requirement",
         statement="The parts cost (BOM) shall not exceed 260 USD per unit.",
         metric="bom_cost_usd", operator="<=", threshold=260, unit="USD", aliases=["budget", "cost limit"]),
    # Tests
    dict(id="TEST-PWR-01", type="test", name="Electrical compatibility test", category="test",
         procedure="Measure supply, driver, regulator and wiring voltages and currents against the recorded limits."),
    dict(id="TEST-MTR-01", type="test", name="Motor loaded-operation test", category="test",
         procedure="Run both motors under representative load and log current, temperature and speed."),
    dict(id="TEST-RUN-01", type="test", name="Endurance run", category="test",
         procedure="Drive the standard duty cycle until the battery cut-off and record the elapsed time."),
    dict(id="TEST-SPD-01", type="test", name="Top-speed run", category="test",
         procedure="Measure speed over a 10 m level course."),
    dict(id="TEST-MECH-01", type="test", name="Mounting fit check", category="test",
         procedure="Check motor, bracket and wheel fit and alignment."),
    dict(id="TEST-MASS-01", type="test", name="Weigh-in", category="test",
         procedure="Weigh the assembled rover."),
    # Documents
    dict(id="DOC-MTR-01", type="document", name="Motor datasheet (fictional)", category="document", revision="A"),
    dict(id="DOC-DRV-01", type="document", name="Driver datasheet (fictional)", category="document", revision="A"),
    dict(id="DOC-BAT-01", type="document", name="Battery datasheet (fictional)", category="document", revision="A"),
    dict(id="DOC-WIR-01", type="document", name="Harness drawing (fictional)", category="document", revision="A"),
]

# source REL target. The meaning of each type is defined in app/graph.py.
RELATIONSHIPS = [
    ("MTR-01", "INTERFACES_WITH", "DRV-01", "Motor terminals connect to the driver outputs."),
    ("WIR-01", "CONNECTS", "MTR-01", "The harness is wired to the motor."),
    ("WIR-01", "CONNECTS", "DRV-01", "The harness is wired to the driver outputs."),
    ("DRV-01", "POWERED_BY", "PWR-01", "The driver takes its supply from the main rail."),
    ("REG-01", "POWERED_BY", "PWR-01", "The regulator takes its input from the main rail."),
    ("PWR-01", "POWERED_BY", "BAT-01", "The rail is fed by the battery."),
    ("CTRL-01", "POWERED_BY", "REG-01", "The controller is supplied by the regulator."),
    ("CTRL-01", "CONTROLS", "DRV-01", "The controller sends commands to the driver."),
    ("MTR-01", "DRIVES", "WHL-01", "The motor shaft drives the wheel."),
    ("MTR-01", "MOUNTED_ON", "BRK-01", "The motor is bolted to the bracket."),
    ("BRK-01", "MOUNTED_ON", "CHS-01", "The bracket is bolted to the chassis."),
    ("MTR-01", "SATISFIES", "REQ-SPD-01", "Motor speed sets the top speed."),
    ("MTR-01", "SATISFIES", "REQ-RUN-01", "Motor power draw sets the runtime."),
    ("BAT-01", "SATISFIES", "REQ-RUN-01", "Battery energy sets the runtime."),
    ("DRV-01", "SATISFIES", "REQ-PWR-01", "Driver limits are part of the electrical requirement."),
    ("BAT-01", "SATISFIES", "REQ-PWR-01", "Battery limits are part of the electrical requirement."),
    ("REG-01", "SATISFIES", "REQ-PWR-01", "Regulator limits are part of the electrical requirement."),
    ("WIR-01", "SATISFIES", "REQ-PWR-01", "Wiring limits are part of the electrical requirement."),
    ("CHS-01", "SATISFIES", "REQ-MASS-01", "The chassis is the largest mass item."),
    ("REQ-PWR-01", "VERIFIED_BY", "TEST-PWR-01", ""),
    ("REQ-RUN-01", "VERIFIED_BY", "TEST-RUN-01", ""),
    ("REQ-SPD-01", "VERIFIED_BY", "TEST-SPD-01", ""),
    ("REQ-MASS-01", "VERIFIED_BY", "TEST-MASS-01", ""),
    ("MTR-01", "VERIFIED_BY", "TEST-MTR-01", "Motor behaviour is checked under load."),
    ("MTR-01", "VERIFIED_BY", "TEST-MECH-01", "Motor fit is checked at assembly."),
    ("BRK-01", "VERIFIED_BY", "TEST-MECH-01", "Bracket fit is checked at assembly."),
    ("MTR-01", "DOCUMENTED_BY", "DOC-MTR-01", ""),
    ("DRV-01", "DOCUMENTED_BY", "DOC-DRV-01", ""),
    ("BAT-01", "DOCUMENTED_BY", "DOC-BAT-01", ""),
    ("WIR-01", "DOCUMENTED_BY", "DOC-WIR-01", ""),
]

RULES = [
    dict(id="R-DRV-IN-MAX", title="Rail voltage is within the driver's maximum input", category="electrical_compatibility",
         group="electrical", lhs=dict(entity="PWR-01", param="rail_voltage"), op="<=",
         rhs=dict(entity="DRV-01", param="input_voltage_max"), remedy="DRV-01", basis="recorded"),
    dict(id="R-DRV-IN-MIN", title="Rail voltage is above the driver's minimum input", category="electrical_compatibility",
         group="electrical", lhs=dict(entity="DRV-01", param="input_voltage_min"), op="<=",
         rhs=dict(entity="PWR-01", param="rail_voltage"), remedy="DRV-01", basis="recorded"),
    dict(id="R-REG-IN-MAX", title="Rail voltage is within the regulator's maximum input", category="electrical_compatibility",
         group="electrical", lhs=dict(entity="PWR-01", param="rail_voltage"), op="<=",
         rhs=dict(entity="REG-01", param="input_voltage_max"), remedy="REG-01", basis="recorded"),
    dict(id="R-REG-IN-MIN", title="Rail voltage is above the regulator's minimum input", category="electrical_compatibility",
         group="electrical", lhs=dict(entity="REG-01", param="input_voltage_min"), op="<=",
         rhs=dict(entity="PWR-01", param="rail_voltage"), remedy="REG-01", basis="recorded"),
    dict(id="R-BAT-RAIL", title="Battery nominal voltage matches the rail (within 15 %)", category="electrical_compatibility",
         group="electrical", lhs=dict(entity="PWR-01", param="rail_voltage"), op="within_pct", tol=15,
         rhs=dict(entity="BAT-01", param="nominal_voltage"), remedy="BAT-01", basis="recorded"),
    dict(id="R-MTR-RAIL-OV", title="Rail is no more than 110 % of the motor's rated voltage", category="electrical_compatibility",
         group="electrical", lhs=dict(entity="PWR-01", param="rail_voltage"), op="<=",
         rhs=dict(entity="MTR-01", param="rated_voltage", factor=1.10), basis="assumption", rail_coupled=True,
         assumption="Motors are expected to run between 80 % and 110 % of rated voltage (project assumption)."),
    dict(id="R-MTR-RAIL-UV", title="Rail is at least 80 % of the motor's rated voltage", category="electrical_compatibility",
         group="electrical", lhs=dict(entity="MTR-01", param="rated_voltage", factor=0.80), op="<=",
         rhs=dict(entity="PWR-01", param="rail_voltage"), basis="assumption", rail_coupled=True,
         assumption="Motors are expected to run between 80 % and 110 % of rated voltage (project assumption)."),
    dict(id="R-DRV-I", title="Motor current is within the driver's channel limit", category="electrical_compatibility",
         group="electrical", lhs=dict(entity="MTR-01", param="rated_current"), op="<=",
         rhs=dict(entity="DRV-01", param="channel_current_max"), remedy="DRV-01", basis="recorded"),
    dict(id="R-BAT-I", title="Peak current is within the battery's discharge limit", category="electrical_compatibility",
         group="electrical", lhs=dict(metric="peak_current_a"), op="<=",
         rhs=dict(entity="BAT-01", param="max_discharge_current"), remedy="BAT-01", basis="recorded"),
    dict(id="R-WIR-V", title="Rail voltage is within the wiring's voltage rating", category="electrical_compatibility",
         group="electrical", lhs=dict(entity="PWR-01", param="rail_voltage"), op="<=",
         rhs=dict(entity="WIR-01", param="voltage_rating_max"), remedy="WIR-01", basis="recorded"),
    dict(id="R-WIR-I", title="Peak current is within the wiring's current rating", category="electrical_compatibility",
         group="electrical", lhs=dict(metric="peak_current_a"), op="<=",
         rhs=dict(entity="WIR-01", param="current_rating_max"), remedy="WIR-01", basis="recorded"),
    dict(id="R-MTR-BRK", title="Motor mounting pitch matches the bracket", category="mechanical_fit",
         group="mechanical", lhs=dict(entity="MTR-01", param="mount_pitch_mm"), op="==", tol=0.2,
         rhs=dict(entity="BRK-01", param="mount_pitch_mm"), remedy="BRK-01", basis="recorded"),
    dict(id="R-MTR-WHL", title="Motor shaft matches the wheel bore", category="mechanical_fit",
         group="mechanical", lhs=dict(entity="MTR-01", param="shaft_diameter_mm"), op="==", tol=0.05,
         rhs=dict(entity="WHL-01", param="bore_diameter_mm"), remedy="WHL-01", basis="recorded"),
]

# Fictional catalogue of replacement parts. Prices and ratings are invented.
CATALOG = [
    dict(id="MTR-ALT-12L", name="12 V low-power gear motor", category="motor", lead_time_days=7,
         parameters={"rated_voltage": [12, "V"], "rated_current": [3.2, "A"], "no_load_speed_rpm": [280, "rpm"],
                     "mass": [0.38, "kg"], "unit_cost": [24, "USD"], "mount_pitch_mm": [31, "mm"],
                     "shaft_diameter_mm": [6, "mm"]}),
    dict(id="MTR-ALT-24A", name="24 V compact gear motor", category="motor", lead_time_days=10,
         parameters={"rated_voltage": [24, "V"], "rated_current": [2.2, "A"], "no_load_speed_rpm": [300, "rpm"],
                     "mass": [0.40, "kg"], "unit_cost": [34, "USD"], "mount_pitch_mm": [31, "mm"],
                     "shaft_diameter_mm": [6, "mm"]}),
    dict(id="MTR-ALT-24B", name="24 V high-torque gear motor", category="motor", lead_time_days=14,
         parameters={"rated_voltage": [24, "V"], "rated_current": [3.4, "A"], "no_load_speed_rpm": [260, "rpm"],
                     "mass": [0.55, "kg"], "unit_cost": [46, "USD"], "mount_pitch_mm": [36, "mm"],
                     "shaft_diameter_mm": [8, "mm"]}),
    dict(id="DRV-ALT-36", name="36 V dual driver", category="driver", lead_time_days=6,
         parameters={"input_voltage_min": [12, "V"], "input_voltage_max": [36, "V"], "channel_current_max": [8, "A"],
                     "mass": [0.07, "kg"], "unit_cost": [24, "USD"]}),
    dict(id="DRV-ALT-18B", name="18 V dual driver, 10 A", category="driver", lead_time_days=5,
         parameters={"input_voltage_min": [8, "V"], "input_voltage_max": [18, "V"], "channel_current_max": [10, "A"],
                     "mass": [0.06, "kg"], "unit_cost": [19, "USD"]}),
    dict(id="BAT-ALT-24", name="24 V battery pack, 96 Wh", category="battery", lead_time_days=12,
         parameters={"nominal_voltage": [24, "V"], "usable_energy": [96, "Wh"], "max_discharge_current": [12, "A"],
                     "mass": [1.0, "kg"], "unit_cost": [68, "USD"]}),
    dict(id="BAT-ALT-12XL", name="12 V battery pack, 144 Wh", category="battery", lead_time_days=9,
         parameters={"nominal_voltage": [12, "V"], "usable_energy": [144, "Wh"], "max_discharge_current": [20, "A"],
                     "mass": [1.3, "kg"], "unit_cost": [64, "USD"]}),
    dict(id="REG-ALT-36", name="36 V input buck regulator", category="regulator", lead_time_days=4,
         parameters={"input_voltage_min": [9, "V"], "input_voltage_max": [36, "V"], "mass": [0.03, "kg"],
                     "unit_cost": [9, "USD"]}),
    dict(id="WIR-ALT-60", name="60 V / 10 A rated harness", category="wiring", lead_time_days=5,
         parameters={"voltage_rating_max": [60, "V"], "current_rating_max": [10, "A"], "mass": [0.17, "kg"],
                     "unit_cost": [14, "USD"]}),
    dict(id="CHS-ALT-LITE", name="Lightweight chassis", category="chassis", lead_time_days=15,
         parameters={"mass": [2.6, "kg"], "unit_cost": [78, "USD"]}),
    dict(id="BRK-ALT-36", name="Motor bracket, 36 mm pitch", category="bracket", lead_time_days=4,
         parameters={"mount_pitch_mm": [36, "mm"], "mass": [0.09, "kg"], "unit_cost": [7, "USD"]}),
    dict(id="WHL-ALT-8", name="Drive wheel, 8 mm bore", category="wheel", lead_time_days=6,
         parameters={"diameter_mm": [120, "mm"], "bore_diameter_mm": [8, "mm"], "mass": [0.19, "kg"],
                     "unit_cost": [14, "USD"]}),
]

PROJECT = dict(
    id="ROVER-ALPHA", name="Rover Alpha", revision="A", fictional_fixture=True,
    description="Fictional small electromechanical rover used to demonstrate change impact analysis.",
    roles=dict(motor="MTR-01", driver="DRV-01", battery="BAT-01", rail="PWR-01", regulator="REG-01",
               controller="CTRL-01", wheel="WHL-01"),
    rail_follows=dict(entity="BAT-01", param="nominal_voltage"),
    assumptions=dict(
        load_factor=dict(value=0.5, label="Average motor load as a share of peak power",
                         note="Used for the runtime estimate. Edit to match the real duty cycle."),
        integration_hours_per_part=dict(value=1.5, label="Engineering hours to integrate one replaced part"),
        retest_hours_per_test=dict(value=4.0, label="Engineering hours to re-run one test"),
        engineer_rate_usd=dict(value=35.0, label="Engineering cost per hour (USD)"),
    ),
    param_labels={
        "rated_voltage": "Rated voltage", "rated_current": "Rated current", "no_load_speed_rpm": "No-load speed",
        "mass": "Mass", "unit_cost": "Unit cost", "mount_pitch_mm": "Mounting pitch", "shaft_diameter_mm": "Shaft diameter",
        "input_voltage_min": "Minimum input voltage", "input_voltage_max": "Maximum input voltage",
        "channel_current_max": "Channel current limit", "nominal_voltage": "Nominal voltage",
        "usable_energy": "Usable energy", "max_discharge_current": "Maximum discharge current",
        "rail_voltage": "Rail voltage", "power_draw": "Power draw", "diameter_mm": "Diameter",
        "bore_diameter_mm": "Bore diameter", "voltage_rating_max": "Voltage rating", "current_rating_max": "Current rating",
    },
    # How a changed parameter spreads through the graph (see app/graph.py).
    param_kinds={
        "rated_voltage": "rating", "rated_current": "load", "no_load_speed_rpm": "perf", "mass": "mech",
        "unit_cost": "cost", "mount_pitch_mm": "mech", "shaft_diameter_mm": "mech", "input_voltage_min": "rating",
        "input_voltage_max": "rating", "channel_current_max": "rating", "nominal_voltage": "supply",
        "usable_energy": "supply", "max_discharge_current": "rating", "rail_voltage": "supply", "power_draw": "load",
        "diameter_mm": "mech", "bore_diameter_mm": "mech", "voltage_rating_max": "rating", "current_rating_max": "rating",
    },
    # Parameters that cannot be assumed to stay the same when the named parameter changes.
    param_dependencies={"rated_voltage": ["rated_current", "no_load_speed_rpm"]},
)


def main() -> None:
    entity_ids = {e["id"] for e in ENTITIES}
    for s, _t, t, _w in RELATIONSHIPS:
        assert s in entity_ids and t in entity_ids, (s, t)
    cats = {e.get("category") for e in ENTITIES}
    for c in CATALOG:
        assert c["category"] in cats, c["id"]
    data = dict(project=PROJECT, entities=ENTITIES,
                relationships=[dict(id=f"REL-{i + 1:03d}", source_id=s, type=t, target_id=g, rationale=w)
                               for i, (s, t, g, w) in enumerate(RELATIONSHIPS)],
                rules=RULES, catalog=CATALOG)
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")

    CSV_DIR.mkdir(parents=True, exist_ok=True)

    def write(name, header, rows):
        with open(CSV_DIR / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    comps = [e for e in ENTITIES if e["type"] in ("component", "subsystem")]
    write("components.csv", ["id", "type", "name", "category", "qty", "description", "source", "status"],
          [[e["id"], e["type"], e["name"], e["category"], e.get("qty", 1), e.get("description", ""),
            "Fictional fixture", "fictional_sample"] for e in comps])
    write("parameters.csv", ["entity_id", "parameter", "value", "unit", "source", "status"],
          [[e["id"], k, v[0], v[1], "Fictional fixture", "fictional_sample"] for e in comps
           for k, v in e["parameters"].items()])
    write("requirements.csv", ["id", "name", "statement", "metric", "operator", "threshold", "unit", "status"],
          [[e["id"], e["name"], e["statement"], e.get("metric", ""), e.get("operator", ""), e.get("threshold", ""),
            e.get("unit", ""), "fictional_sample"] for e in ENTITIES if e["type"] == "requirement"])
    write("tests.csv", ["id", "name", "procedure", "status"],
          [[e["id"], e["name"], e["procedure"], "planned"] for e in ENTITIES if e["type"] == "test"])
    write("relationships.csv", ["id", "source_id", "type", "target_id", "rationale"],
          [[r["id"], r["source_id"], r["type"], r["target_id"], r["rationale"]] for r in data["relationships"]])
    write("constraints.csv", ["id", "title", "lhs", "op", "rhs", "basis"],
          [[r["id"], r["title"], json.dumps(r["lhs"]), r["op"], json.dumps(r["rhs"]), r["basis"]] for r in RULES])
    write("catalog.csv", ["id", "name", "category", "unit_cost_usd", "lead_time_days", "parameters"],
          [[c["id"], c["name"], c["category"], c["parameters"]["unit_cost"][0], c["lead_time_days"],
            json.dumps(c["parameters"])] for c in CATALOG])
    print("wrote", JSON_OUT, "and CSVs in", CSV_DIR)


if __name__ == "__main__":
    main()
