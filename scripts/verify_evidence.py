"""Check imported evidence hashes and the consistency of recorded results."""

import csv
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "manifests/evidence-files.json").read_text())
    for item in manifest["files"]:
        path = root / item["path"]
        assert path.is_file(), f"Missing evidence: {item['path']}"
        assert path.stat().st_size == item["bytes"], f"Size mismatch: {item['path']}"
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
        ), f"Checksum mismatch: {item['path']}"
    load = lambda name: json.loads((root / name).read_text())
    validation = load("evidence/recovery/validation.json")
    replay = load("evidence/replay/inference-comparison.json")
    coverage = load("evidence/replay/code-coverage.json")
    metrics = load("evidence/training/metrics.json")
    model = load("evidence/recovery/pytorch-3183-model.json")
    assert validation["passed"] and not validation["recovery_errors"]
    assert validation["tensor_count"] == 31 and all(
        item["match"] for item in validation["tensors"]
    )
    assert validation["source_count"] == 19 and all(
        item["match"] for item in validation["sources"]
    )
    assert (
        validation["module_count"] == 26
        and validation["module_names_types_and_order_match"]
    )
    assert (
        validation["all_archive_sources_recovered"] and validation["graph_count"] == 34
    )
    assert (
        coverage["reported_functions_found"] == 34
        and not coverage["unresolved_dependencies"]
    )
    assert (
        replay["passed"]
        and replay["prediction_matches"] == replay["images_compared"] == 6000
    )
    assert replay["max_absolute_logit_difference"] == 0 and replay["finite_logits"]
    assert replay["first_batch_forward_order_matches_recovered_tree"]
    assert metrics["split_sizes"] == {"train": 48000, "validation": 6000, "test": 6000}
    assert (
        metrics["test_accuracy"]
        == replay["reference_accuracy"]
        == replay["recovered_accuracy"]
    )
    for source in model["sources"]:
        path = root / "evidence/recovery" / source["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
    rows = list(csv.DictReader((root / "evidence/replay/predictions.csv").open()))
    assert len(rows) == 6000 and all(row["match"].lower() == "true" for row in rows)
    correct = sum(row["label"] == row["recovered_prediction"] for row in rows)
    assert correct == 5225
    print(
        f"Evidence hashes: {len(manifest['files'])}/{len(manifest['files'])} verified"
    )
    print("Recovery: 31 tensors, 26 modules, 19 source files, 34 graphs")
    print("Replay: 6000/6000 predictions agree; maximum logit difference 0")
    print("Ground-truth accuracy: 5225/6000 (87.0833%)")
    print("EVIDENCE_CHECK_PASS")


if __name__ == "__main__":
    main()
