from decimal import Decimal
from pathlib import Path
from kds.adapters.akkaya_demo import ensure_demo, SOURCE_COMMIT, SOURCE_VERSION
from kds.data.project_store import FileProjectStore


def test_akkaya_references_and_idempotency(tmp_path):
    store = FileProjectStore(tmp_path)
    source_dir = Path(__file__).resolve().parents[1] / "data"
    doc = ensure_demo(store, source_dir)
    assert doc["project"]["name"] == "Akkaya 2024 Demo"
    assert len(doc["analysis_units"]) == 179
    assert sum(Decimal(str(r["area_da"])) for r in doc["analysis_units"]) == Decimal("134919")
    assert doc["water_budget"]["amount"] == 100700080.81
    assert doc["water_budget"]["kind"] == "calculated_reference"
    assert sum(Decimal(r["metadata"]["current_profit_tl"]) for r in doc["analysis_units"]) == Decimal("1041499119.212")
    assert sum(Decimal(r["metadata"]["current_water_m3"]) for r in doc["analysis_units"]) == Decimal("100700080.81")
    assert len(doc["crops"]) == len(doc["economics"]) == 58
    assert doc["metadata"]["source_version"] == SOURCE_VERSION
    assert doc["metadata"]["source_commit"] == SOURCE_COMMIT
    refs = doc["metadata"]["references"]
    assert refs["raw_candidate_rows"] == 6859
    assert refs["raw_water_quota_flagged_rows"] == 3673
    assert "final_suitable_candidates" not in refs
    assert ensure_demo(store, source_dir) == doc
    assert store.get("akkaya-2024-demo") == doc
