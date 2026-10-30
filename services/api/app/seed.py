from copy import deepcopy

PROJECT = {
    "id": "ROVER-ALPHA",
    "name": "Rover Alpha",
    "revision": "A",
    "description": "Fictional small electromechanical rover for demonstrating change impact analysis.",
    "fictional_fixture": True,
}
ENTITIES = [
    {"id":"MTR-01","type":"component","name":"Drive motor","category":"electromechanical","description":"Baseline motor; fictional fixture.","parameters":{"rated_voltage":{"value":12,"unit":"V"},"mass":{"value":0.42,"unit":"kg"},"unit_cost":{"value":28.0,"unit":"USD"}}},
    {"id":"DRV-01","type":"component","name":"Motor driver","category":"electrical","description":"Fictional motor driver.","parameters":{"max_input_voltage":{"value":18,"unit":"V"},"unit_cost":{"value":16.0,"unit":"USD"}}},
    {"id":"BAT-01","type":"component","name":"Battery pack","category":"electrical","description":"Fictional 12 V nominal battery pack.","parameters":{"nominal_voltage":{"value":12,"unit":"V"},"usable_energy":{"value":96,"unit":"Wh"},"unit_cost":{"value":42.0,"unit":"USD"}}},
    {"id":"PWR-01","type":"subsystem","name":"Power system","category":"electrical","description":"Power distribution subsystem."},
    {"id":"CTRL-01","type":"component","name":"Main controller","category":"embedded","description":"Controller for motion subsystem."},
    {"id":"WIR-01","type":"component","name":"Motor wiring","category":"electrical","description":"Wiring rating is intentionally absent."},
    {"id":"REQ-PWR-01","type":"requirement","name":"Electrical compatibility","statement":"The power system and motor driver must operate within their applicable documented electrical limits."},
    {"id":"REQ-RUN-01","type":"requirement","name":"Runtime target","statement":"The rover should meet its approved runtime target; the target is not populated in this fixture."},
    {"id":"TEST-PWR-01","type":"test","name":"Electrical compatibility test","procedure":"Verify supply, driver, wiring and motor compatibility against controlled specifications."},
    {"id":"TEST-MTR-01","type":"test","name":"Motor loaded-operation test","procedure":"Verify motor operation under representative load."},
    {"id":"DOC-DRV-01","type":"document","name":"Driver specification (fictional)","revision":"A"},
]
RELATIONSHIPS = [
    {"id":"REL-001","source_id":"MTR-01","target_id":"DRV-01","type":"DEPENDS_ON","rationale":"Motor operation depends on the driver interface; this does not imply equal voltage parameters."},
    {"id":"REL-002","source_id":"DRV-01","target_id":"PWR-01","type":"DEPENDS_ON","rationale":"Driver input is supplied by the power subsystem."},
    {"id":"REL-003","source_id":"BAT-01","target_id":"PWR-01","type":"CONTRIBUTES_TO","rationale":"Battery contributes energy to the power subsystem."},
    {"id":"REL-004","source_id":"PWR-01","target_id":"CTRL-01","type":"SUPPLIES","rationale":"Power subsystem supplies controller."},
    {"id":"REL-005","source_id":"MTR-01","target_id":"REQ-PWR-01","type":"SUBJECT_TO","rationale":"Motor is in scope of electrical compatibility requirement."},
    {"id":"REL-006","source_id":"DRV-01","target_id":"REQ-PWR-01","type":"SUBJECT_TO","rationale":"Driver is in scope of electrical compatibility requirement."},
    {"id":"REL-007","source_id":"REQ-PWR-01","target_id":"TEST-PWR-01","type":"VERIFIED_BY","rationale":"Electrical compatibility test verifies this requirement."},
    {"id":"REL-008","source_id":"MTR-01","target_id":"TEST-MTR-01","type":"VERIFIED_BY","rationale":"Motor loaded-operation test covers motor operation."},
    {"id":"REL-009","source_id":"WIR-01","target_id":"TEST-PWR-01","type":"VERIFIED_BY","rationale":"Wiring should be checked in the electrical compatibility test."},
    {"id":"REL-010","source_id":"DRV-01","target_id":"DOC-DRV-01","type":"DOCUMENTED_BY","rationale":"Fictional driver rating source."},
]
CONSTRAINTS = [
    {"id":"CON-DRV-01","entity_id":"DRV-01","parameter":"max_input_voltage","operator":"upper_bound","limit_value":18,"unit":"V","evidence_id":"EV-DRV-01","scope":"driver_input_voltage","note":"Fictional sample limit; only applies to driver input."}
]
EVIDENCE = [
    {"id":"EV-MTR-01","entity_id":"MTR-01","property":"rated_voltage","value":12,"unit":"V","source_document_id":"DOC-MTR-FIXTURE","source_location":"Fixture parameter table, row MTR-01","status":"fictional_sample","revision":"A"},
    {"id":"EV-DRV-01","entity_id":"DRV-01","property":"max_input_voltage","value":18,"unit":"V","source_document_id":"DOC-DRV-01","source_location":"Fictional electrical ratings table","status":"fictional_sample","revision":"A"},
    {"id":"EV-BAT-01","entity_id":"BAT-01","property":"nominal_voltage","value":12,"unit":"V","source_document_id":"DOC-BAT-FIXTURE","source_location":"Fixture parameter table, row BAT-01","status":"fictional_sample","revision":"A"},
]
TESTS = [
    {"id":"TEST-PWR-01","name":"Electrical compatibility test","related_entity_ids":["MTR-01","DRV-01","BAT-01","WIR-01"],"status":"planned"},
    {"id":"TEST-MTR-01","name":"Motor loaded-operation test","related_entity_ids":["MTR-01"],"status":"planned"},
]
def dataset():
    return deepcopy({"project":PROJECT,"entities":ENTITIES,"relationships":RELATIONSHIPS,"constraints":CONSTRAINTS,"evidence":EVIDENCE,"tests":TESTS})
