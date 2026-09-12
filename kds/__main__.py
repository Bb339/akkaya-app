"""Explicit local demo initialization: python -m kds seed-demo --source-dir data."""
import argparse
import json
from pathlib import Path
from kds.adapters.akkaya_demo import ensure_demo
from kds.config import project_store_path
from kds.data.project_store import FileProjectStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["seed-demo"])
    parser.add_argument("--source-dir", type=Path, required=True)
    args = parser.parse_args()
    result = ensure_demo(FileProjectStore(project_store_path()), args.source_dir)
    print(json.dumps({"project": result["project"]["name"], "references": result["metadata"]["references"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
