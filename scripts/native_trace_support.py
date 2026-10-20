"""Small, testable helpers for the bounded native-entry experiment."""

import hashlib
import json
from pathlib import Path


def parse_maps(text, library_name):
    mappings = []
    for line in text.splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) != 6 or Path(fields[5]).name != library_name:
            continue
        start, end = (int(value, 16) for value in fields[0].split("-"))
        mappings.append(
            dict(
                start=start,
                end=end,
                flags=fields[1],
                file_offset=int(fields[2], 16),
                path=fields[5],
            )
        )
    if len({item["path"] for item in mappings}) != 1:
        raise ValueError("Expected exactly one mapped library path")
    return mappings


def mapped_address(mappings, offset, size, executable=False):
    matches = [
        item
        for item in mappings
        if "r" in item["flags"]
        and (not executable or "x" in item["flags"])
        and size > 0
        and offset >= 0
        and item["file_offset"] <= offset
        and offset + size <= item["file_offset"] + item["end"] - item["start"]
    ]
    if len(matches) != 1:
        raise ValueError("Range must fit exactly one eligible mapping")
    item = matches[0]
    return item["start"] + offset - item["file_offset"]


def check_plan(plan):
    functions = plan.get("functions", [])
    if plan.get("schema") != 1 or not 0 < len(functions) <= 128:
        raise ValueError("Expected 1..128 candidate symbols")
    if not any(item["kind"] == "GNU build ID" for item in plan["identity_ranges"]):
        raise ValueError("Missing GNU build ID")
    offsets = [item["file_offset"] for item in functions]
    if len(set(offsets)) != len(offsets):
        raise ValueError("Symbol aliases share an entry; choose an unambiguous plan")
    if any(not 0 < item["size"] <= 1024 * 1024 for item in functions):
        raise ValueError("Invalid candidate size")


def select_observed(plan_bytes, trace):
    """Reject incomplete or mismatched runs before selecting recovery ranges."""
    plan = json.loads(plan_bytes)
    check_plan(plan)
    if trace.get("schema") != 1 or not trace.get("completed_forward"):
        raise ValueError("The trace did not complete the forward window")
    if trace.get("error") or trace.get("event_limit_hit"):
        raise ValueError("Trace contains an error or reached its event limit")
    if trace.get("candidate_plan_sha256") != hashlib.sha256(plan_bytes).hexdigest():
        raise ValueError("Trace belongs to a different candidate plan")
    candidates = plan["functions"]
    hits = trace.get("hits", [])
    if len(hits) != len(candidates):
        raise ValueError("Trace does not account for every candidate")
    for index, hit in enumerate(hits):
        if (
            hit.get("index") != index
            or type(hit.get("count")) is not int
            or hit["count"] < 0
        ):
            raise ValueError("Invalid trace hit counts")
    events = trace.get("events", [])
    counts = [0] * len(candidates)
    for event in events:
        index = event.get("index")
        if type(index) is not int or not 0 <= index < len(candidates):
            raise ValueError("Invalid event index")
        counts[index] += 1
    if counts != [hit["count"] for hit in hits]:
        raise ValueError("Trace events and hit counts disagree")
    expected_identity = [
        (item["kind"], item["sha256"]) for item in plan["identity_ranges"]
    ]
    observed_identity = [
        (item["kind"], item["sha256"]) for item in trace.get("identity_checks", [])
    ]
    if expected_identity != observed_identity:
        raise ValueError("Trace library identity is incomplete or mismatched")
    observed = [dict(item) for item, hit in zip(candidates, hits) if hit["count"]]
    if not observed:
        raise ValueError("No selected native entries were observed")
    plan.update(
        method="observed-entry-guided",
        functions=observed,
        trace_candidate_count=len(candidates),
        trace_observed_count=len(observed),
        scope="Observed entries among selected dynamic symbols in one forward window. "
        "This excludes undiscovered, inline and uninstrumented native code; "
        "recovery reads bytes only from the captured process layer.",
    )
    return plan
