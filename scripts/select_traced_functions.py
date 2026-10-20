"""Turn a completed entry trace into a memory-recovery plan."""

import argparse
import hashlib
import json
from pathlib import Path

from native_trace_support import select_observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    trace_bytes = args.trace.read_bytes()
    plan = select_observed(args.candidates.read_bytes(), json.loads(trace_bytes))
    plan["trace_sha256"] = hashlib.sha256(trace_bytes).hexdigest()
    with args.output.open("x") as stream:
        stream.write(json.dumps(plan, indent=2) + "\n")
    print(
        f"Selected {len(plan['functions'])}/{plan['trace_candidate_count']} candidate entries"
    )
    print("OBSERVED_NATIVE_PLAN_PASS")


if __name__ == "__main__":
    main()
