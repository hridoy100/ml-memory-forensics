"""Verify the reproduction logs and summarize a completed submission run."""

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    root = args.run_dir.resolve()
    steps = (
        "environment",
        "training-record",
        "export",
        "configure",
        "build",
        "debug-sections",
        "cpp-inference",
        "extraction",
        "validation",
        "replay",
    )
    for name in steps:
        assert f"STEP_PASS: {name}" in (root / f"{name}.log").read_text(), name
    native = (root / "native-forward.log").read_text()
    assert "NATIVE_FORWARD_SAMPLE_PASS" in native
    assert "in section .text" in native
    sections = (root / "debug-sections.log").read_text()
    assert all(
        name in sections for name in (".debug_info", ".debug_line", ".debug_macro")
    )
    validation = json.loads((root / "recovery/validation.json").read_text())
    replay = json.loads((root / "replay/inference-comparison.json").read_text())
    assert validation["passed"] and replay["passed"]
    assert replay["images_compared"] == replay["prediction_matches"] == 6000
    summary = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "guest_run_dir": str(root),
        "kind": "New reproduction checks, not historical training/capture screenshots",
        "steps_verified": list(steps) + ["native-forward"],
        "captured_pid": validation["pid"],
        "live_native_sample_pid": int(
            re.search(r"Live reproduction PID: (\d+)", native)[1]
        ),
        "tensor_count": validation["tensor_count"],
        "source_count": validation["source_count"],
        "images_compared": replay["images_compared"],
        "prediction_matches": replay["prediction_matches"],
        "max_absolute_logit_difference": replay["max_absolute_logit_difference"],
        "accuracy": replay["recovered_accuracy"],
        "native_scope": "One live native convolution entry, its backtrace and 12 instructions. Not an exhaustive call trace or native code extraction from the LiME image.",
        "passed": True,
    }
    paths = [root / "reexported.pt", root / "build/cifar10_inference"]
    for directory in ("recovery", "replay"):
        paths.extend(
            p for p in (root / directory).iterdir() if p.suffix in (".npy", ".pt")
        )
    artifacts = []
    for path in sorted(paths):
        artifacts.append(
            {
                "relative_path": str(path.relative_to(root)),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (root / "artifacts.json").write_text(
        json.dumps({"guest_run_dir": str(root), "artifacts": artifacts}, indent=2)
        + "\n"
    )
    print(json.dumps(summary, indent=2))
    print("SUBMISSION_EVIDENCE_PASS")


if __name__ == "__main__":
    main()
