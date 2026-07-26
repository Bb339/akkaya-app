import json
from pathlib import Path

from app import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = PROJECT_ROOT / "data" / "defense" / "savunma_veri_paketi.json"


def _source_package():
    return json.loads(PACKAGE_PATH.read_text(encoding="utf-8"))


def test_defense_dataset_list_is_metadata_only_and_main_first():
    with app.test_client() as client:
        response = client.get("/api/defense-datasets")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "OK"
    assert payload["count"] == len(_source_package()["datasets"])
    assert all("values" not in dataset for dataset in payload["datasets"])
    roles = [dataset["defense_role"] for dataset in payload["datasets"]]
    assert roles == sorted(roles, key=lambda role: 0 if role == "ana" else 1)
    assert all(payload["policy"].values())


def test_defense_dataset_detail_preserves_source_values_and_paginates():
    package = _source_package()
    source = next(
        dataset
        for dataset in package["datasets"]
        if dataset["dataset_id"] == "bahceli_model__1_meteoroloji_2024"
    )
    with app.test_client() as client:
        response = client.get(
            f"/api/defense-datasets/{source['dataset_id']}?offset=0&limit=5"
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["dataset"]["values"] == source["values"][:5]
    assert payload["dataset"]["row_count"] == source["row_count"]
    assert payload["dataset"]["column_count"] == source["column_count"]
    assert payload["pagination"]["returned_rows"] == 5


def test_defense_dataset_search_validation_and_not_found():
    dataset_id = "bahceli_model__1_meteoroloji_2024"
    with app.test_client() as client:
        search = client.get(
            f"/api/defense-datasets/{dataset_id}?q=Ocak&offset=0&limit=100"
        )
        invalid_limit = client.get(
            f"/api/defense-datasets/{dataset_id}?limit=201"
        )
        invalid_offset = client.get(
            f"/api/defense-datasets/{dataset_id}?offset=-1"
        )
        missing = client.get("/api/defense-datasets/bilinmeyen-veri-kumesi")

    assert search.status_code == 200
    search_payload = search.get_json()
    assert search_payload["pagination"]["filtered_rows"] >= 1
    assert all(
        any("ocak" in str(cell).casefold() for cell in row if cell is not None)
        for row in search_payload["dataset"]["values"]
    )
    assert invalid_limit.status_code == 400
    assert invalid_offset.status_code == 400
    assert missing.status_code == 404
    assert missing.get_json()["error"] == "dataset_not_found"
