from __future__ import annotations

from pathlib import Path

import pytest

from kds.imports.detection import detect
from test_unified_decision_demo import package_files, project_payload


ROOT = Path(__file__).resolve().parents[1]


def annual_supply(rows: list[tuple[str, str]], *, unit: str = "m3/year") -> bytes:
    body = ["planning_year,amount,unit,geographic_scope,authority_class,note"]
    body.extend(f"{year},{amount},{unit},project,MEASURED," for year, amount in rows)
    return ("\n".join(body) + "\n").encode()


def issue(result: dict, code: str) -> dict:
    return next(value for value in result["issues"] if value["code"] == code)


@pytest.mark.parametrize("count", [1, 3, 10])
def test_every_required_numeric_value_must_parse(count: int):
    rows = [("2025", str(100 + index)) for index in range(count)]
    valid = detect(annual_supply(rows), "annual_water_supply.csv", project=project_payload())
    assert valid["state"] == "AUTO_MATCHED"

    rows[-1] = ("2025", "not-a-number")
    invalid = detect(annual_supply(rows), "annual_water_supply.csv", project=project_payload())
    evidence = issue(invalid, "required_numeric_field_not_parseable")
    assert invalid["state"] == "REVIEW_REQUIRED"
    assert evidence == {
        "code": "required_numeric_field_not_parseable",
        "message": "A required numeric field contains a non-numeric value.",
        "field": "amount",
        "source_column": "amount",
        "populated": count,
        "parseable": count - 1,
        "unparseable": 1,
        "invalid_examples": ["not-a-number"],
    }


def test_several_malformed_numeric_values_report_bounded_unique_examples():
    rows = [("2025", value) for value in ("1", "bad-a", "2", "bad-b", "bad-a", "3")]
    result = detect(annual_supply(rows), "annual_water_supply.csv", project=project_payload())
    evidence = issue(result, "required_numeric_field_not_parseable")
    assert result["state"] == "REVIEW_REQUIRED"
    assert evidence["populated"] == 6
    assert evidence["parseable"] == 3
    assert evidence["unparseable"] == 3
    assert evidence["invalid_examples"] == ["bad-a", "bad-b"]


@pytest.mark.parametrize("count", [3, 10])
def test_every_explicit_year_value_must_parse(count: int):
    rows = [("2025", str(100 + index)) for index in range(count)]
    valid = detect(annual_supply(rows), "annual_water_supply.csv", project=project_payload())
    assert valid["state"] == "AUTO_MATCHED"

    rows[-1] = ("not-a-year", rows[-1][1])
    invalid = detect(annual_supply(rows), "annual_water_supply.csv", project=project_payload())
    evidence = issue(invalid, "explicit_year_not_parseable")
    assert invalid["state"] == "REVIEW_REQUIRED"
    assert evidence["field"] == "planning_year"
    assert evidence["populated"] == count
    assert evidence["parseable"] == count - 1
    assert evidence["unparseable"] == 1
    assert evidence["invalid_examples"] == ["not-a-year"]


def test_numeric_strings_and_structurally_unusual_numbers_remain_parseable():
    rows = [("2025.0", value) for value in ("-5", "999999", "1.5")]
    result = detect(annual_supply(rows), "annual_water_supply.csv", project=project_payload())
    assert result["state"] == "AUTO_MATCHED"
    assert not {"required_numeric_field_not_parseable", "explicit_year_not_parseable"} & {
        value["code"] for value in result["issues"]
    }


def test_empty_optional_and_arbitrary_textual_fields_do_not_trigger_numeric_guard():
    result = detect(
        annual_supply([("2025", "100")], unit="arbitrary-text-unit"),
        "annual_water_supply.csv",
        project=project_payload(),
    )
    assert result["state"] == "AUTO_MATCHED"
    assert not {"required_numeric_field_not_parseable", "explicit_year_not_parseable"} & {
        value["code"] for value in result["issues"]
    }


def test_accepted_package_remains_twenty_of_twenty_auto_matched():
    results = [detect(path.read_bytes(), path.name, project=project_payload()) for path in package_files()]
    assert len(results) == 20
    assert [result["state"] for result in results] == ["AUTO_MATCHED"] * 20

