"""Verify excluded artifacts using a storage root or recorded local locations."""

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--root", type=Path, help="Artifact directory using manifest relative paths"
    )
    group.add_argument(
        "--known-locations",
        action="store_true",
        help="Check original Mac/Ubuntu locations",
    )
    parser.add_argument("--only", nargs="+", help="Manifest artifact names to check")
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    records = json.loads((project / "manifests/artifacts.json").read_text())[
        "artifacts"
    ]
    names = {record["name"] for record in records}
    if args.only and set(args.only) - names:
        parser.error(f"Unknown artifacts: {sorted(set(args.only) - names)}")
    failures = 0
    for record in records:
        if args.only and record["name"] not in args.only:
            continue
        candidates = (
            [args.root / record["relative_path"]]
            if args.root
            else [Path(p) for p in record["known_locations"]]
        )
        path = next((p for p in candidates if p.is_file()), None)
        if path is None:
            print(f"MISSING {record['name']}")
            failures += 1
        elif path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
            print(f"MISMATCH {record['name']}: {path}")
            failures += 1
        else:
            print(f"VERIFIED {record['name']}: {path}")
    print("ARTIFACT_CHECK_PASS" if not failures else f"ARTIFACT_CHECK_FAIL: {failures}")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
