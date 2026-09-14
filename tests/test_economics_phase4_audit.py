import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "audits" / "economics_phase4"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_economics_audit_is_deterministic_and_read_only():
    protected = [ROOT / "app.py", *sorted((ROOT / "kds" / "science").glob("**/*")),
                 *sorted((ROOT / "data").glob("**/*"))]
    protected = [p for p in protected if p.is_file()]
    before_sources = {str(p.relative_to(ROOT)): digest(p) for p in protected}
    before_outputs = {p.name: digest(p) for p in OUT.iterdir() if p.is_file()}
    subprocess.run([sys.executable, "-B", "tools/scientific_audit/economics_phase4.py"], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    assert before_sources == {str(p.relative_to(ROOT)): digest(p) for p in protected}
    assert before_outputs == {p.name: digest(p) for p in OUT.iterdir() if p.is_file()}

    with (OUT / "current_profit_by_unit.csv").open(encoding="utf-8-sig", newline="") as stream:
        current = list(csv.DictReader(stream))
    assert len(current) == 179
    assert sum(float(row["current_profit_total_tl"]) for row in current) == 1041499119.212
    assert all(row["notes"] == "matches catalog" for row in current)

    mismatch = json.loads((OUT / "profit_identity_mismatch_summary.json").read_text(encoding="utf-8"))
    assert mismatch["numeric_profit_conflict_count"] == 0
    assert mismatch["reported_approximately_45_reproduced"] is False
    assert mismatch["crosswalk_counts"] == {"EXACT": 214, "MISSING_RIGHT": 6, "NORMALIZED_MATCH": 12}

    turp = json.loads((OUT / "turp_economic_summary.json").read_text(encoding="utf-8"))
    assert turp["profit_per_da"] == 4000.0
    assert turp["candidate_count"] == turp["candidate_unit_count"] == 43
    assert "No 6000 TL/da" in turp["value_6000_verdict"]
