"""Corrective Phase 2 presentation contracts; no scientific result mutation."""
from copy import deepcopy

import pytest

from kds.application.result_presentation import present_run_for_ui, presentation_units


def unit(unit_id, **values):
    return {"external_id": unit_id, "area_da": 10, "current_crop": "ARPA", **values}


def run(scenario="S1", profile="VERIFIED_INSTITUTIONAL", **result):
    return {
        "id": "run-1", "scenario": scenario, "execution_profile": profile,
        "provenance": {"input_snapshot": {"preview_revision": 3}},
        "result": result,
    }


def document(*units):
    return {"analysis_units": list(units), "data_revision": 4,
            "analysis_state": {"requires_reanalysis": True, "latest_run_id": "run-2"}}


def test_unit_presentation_join_is_id_based_order_independent_and_authority_explicit():
    value = run(
        unit_results=[
            {"analysis_unit_id": "P2", "area_da": 20, "selected_crops": [{"crop": "MISIR", "season": "PRIMARY"}], "total_water_m3": 90},
            {"analysis_unit_id": "P1", "area_da": 10, "selected_crops": [{"crop": "NOHUT", "season": "PRIMARY"}], "total_water_m3": 40},
        ],
        details=[
            {"parcelId": "P1", "chosenCrop": "NOHUT", "profit_tl": 900, "status": "PASS"},
            {"parcelId": "P2", "chosenCrop": "MISIR", "profit_tl": 1200, "warnings": ["review"]},
        ],
    )
    units = presentation_units(value, document(
        unit("P1", latitude=38.1, longitude=34.1),
        unit("P2", area_da=20, current_crop="BUGDAY", latitude=38.2, longitude=34.2),
    ))
    assert [row["analysis_unit_id"] for row in units] == ["P1", "P2"]
    assert units[0]["authoritative_unit_water_m3"] == 40
    assert units[0]["unit_water_authority"] == "VERIFIED_UNIT_PROFILE"
    assert units[0]["unit_profit_tl"] == 900 and units[0]["current_crop"] == "ARPA"
    assert units[1]["warnings"] == ["review"] and units[1]["latitude"] == 38.2


def test_missing_geometry_and_optional_current_crop_are_truthful():
    value = run(unit_results=[{"analysis_unit_id": "P1", "total_water_m3": 3}],
                details=[{"parcelId": "P1", "chosenCrop": "ARPA"}])
    rows = presentation_units(value, document(unit("P1", current_crop=None, geometry=None)))
    assert rows[0]["geometry"] is None and rows[0]["current_crop"] is None
    assert {"geometry", "current_crop", "unit_profit_tl"} <= set(rows[0]["missing_presentation_metadata"])


def test_duplicate_conflicting_project_identity_fails_visibly():
    with pytest.raises(ValueError, match="Duplicate conflicting unit identity 'P1'.*project.analysis_units"):
        presentation_units(run(unit_results=[]), document(unit("P1"), unit("P1", current_crop="MISIR")))


def test_duplicate_identical_identity_is_safe():
    row = unit("P1", latitude=38, longitude=34)
    result = run(unit_results=[{"analysis_unit_id": "P1", "total_water_m3": 10}])
    assert len(presentation_units(result, document(row, deepcopy(row)))) == 1


def test_s2_unit_results_and_details_merge_profit_and_selections():
    value = run("S2",
        unit_results=[{"analysis_unit_id": "P1", "area_da": 10, "total_water_m3": 90,
                       "selected_crops": [{"crop": "ARPA", "season": "PRIMARY"}, {"crop": "NOHUT", "season": "SECONDARY"}]}],
        details=[{"parcelId": "P1", "primary": {"crop": "ARPA", "profit_tl": 400},
                  "secondary": {"crop": "NOHUT", "profit_tl": 500}}])
    row = presentation_units(value, document(unit("P1")))[0]
    assert row["unit_profit_tl"] == 900
    assert [item["season"] for item in row["selected_crops"]] == ["PRIMARY", "SECONDARY"]


@pytest.mark.parametrize("profile,authority", [
    ("VERIFIED_INSTITUTIONAL", "VERIFIED_UNIT_PROFILE"),
    ("REFERENCE_DEMO", "OPTIMIZER_RESULT"),
])
def test_verified_and_reference_water_authority_remain_distinct(profile, authority):
    value = run(profile=profile, unit_results=[{"analysis_unit_id": "P1", "total_water_m3": 10}])
    assert presentation_units(value, document(unit("P1")))[0]["unit_water_authority"] == authority


def test_synthetic_verified_project_uses_same_id_safe_view_without_losing_label():
    value = run(profile="VERIFIED_INSTITUTIONAL", unit_results=[{"analysis_unit_id": "P1", "total_water_m3": 10}])
    value["result_authority_label"] = "SYNTHETIC / NOT_OFFICIAL"
    presented = present_run_for_ui(value, document(unit("P1", latitude=38, longitude=34)))
    assert presented["result_authority_label"] == "SYNTHETIC / NOT_OFFICIAL"
    assert presented["result"]["presentation_units"][0]["latitude"] == 38


def test_reanalysis_context_comes_from_current_backend_state():
    presented = present_run_for_ui(run(unit_results=[]), document())
    assert presented["presentation_context"] == {
        "requires_reanalysis": True,
        "pinned_to_older_input_snapshot": True,
        "current_project_revision": 4,
        "run_project_revision": 3,
        "revision_relationship": "RUN_OLDER_THAN_PROJECT",
        "latest_run_id": "run-2",
    }
