"""Check ASLR mapping and reject incomplete evidence before trace-guided recovery."""

import copy
import hashlib
import json
import unittest

from scripts.native_trace_support import (
    check_plan,
    mapped_address,
    parse_maps,
    select_observed,
)


class NativeTraceTests(unittest.TestCase):
    def setUp(self):
        self.plan = dict(
            schema=1,
            functions=[
                dict(name="conv", file_offset=0x250, size=32),
                dict(name="relu", file_offset=0x290, size=16),
            ],
            identity_ranges=[dict(kind="GNU build ID", sha256="example")],
        )
        self.plan_bytes = json.dumps(self.plan).encode()
        self.trace = dict(
            schema=1,
            completed_forward=True,
            event_limit_hit=False,
            candidate_plan_sha256=hashlib.sha256(self.plan_bytes).hexdigest(),
            identity_checks=copy.deepcopy(self.plan["identity_ranges"]),
            events=[dict(index=1), dict(index=1)],
            hits=[dict(index=0, count=0), dict(index=1, count=2)],
        )
        self.maps = parse_maps(
            """10000-10200 r--p 00000000 00:01 9 /opt/libtorch_cpu.so
20000-20400 r-xp 00000200 00:01 9 /opt/libtorch_cpu.so
30000-30400 r-xp 00000200 00:01 8 /opt/unrelated.so""",
            "libtorch_cpu.so",
        )

    def test_rebase_uses_file_offset_instead_of_elf_virtual_value(self):
        self.assertEqual(mapped_address(self.maps, 0x250, 32, True), 0x20050)

    def test_identity_can_be_read_from_non_executable_mapping(self):
        self.assertEqual(mapped_address(self.maps, 0, 64), 0x10000)
        with self.assertRaises(ValueError):
            mapped_address(self.maps, 0, 64, True)

    def test_two_library_paths_are_ambiguous(self):
        with self.assertRaises(ValueError):
            parse_maps(
                "1000-2000 r-xp 0 00:00 1 /a/lib.so\n"
                "3000-4000 r-xp 0 00:00 2 /b/lib.so",
                "lib.so",
            )

    def test_range_crossing_mapping_boundary_is_rejected(self):
        with self.assertRaises(ValueError):
            mapped_address(self.maps, 0x5F0, 32, True)

    def test_duplicate_entry_aliases_are_rejected(self):
        self.plan["functions"][1]["file_offset"] = 0x250
        with self.assertRaises(ValueError):
            check_plan(self.plan)

    def test_only_observed_functions_are_selected_in_candidate_order(self):
        selected = select_observed(self.plan_bytes, self.trace)
        self.assertEqual([item["name"] for item in selected["functions"]], ["relu"])
        self.assertEqual(selected["trace_candidate_count"], 2)
        self.assertEqual(len(self.plan["functions"]), 2)

    def test_a_partial_forward_cannot_become_a_recovery_plan(self):
        self.trace["completed_forward"] = False
        with self.assertRaises(ValueError):
            select_observed(self.plan_bytes, self.trace)

    def test_event_limit_hit_invalidates_even_a_completed_flag(self):
        self.trace["event_limit_hit"] = True
        with self.assertRaises(ValueError):
            select_observed(self.plan_bytes, self.trace)

    def test_other_plan_or_library_cannot_be_substituted(self):
        self.trace["candidate_plan_sha256"] = "wrong"
        with self.assertRaises(ValueError):
            select_observed(self.plan_bytes, self.trace)

    def test_truncated_events_cannot_pass_on_aggregate_counts(self):
        self.trace["events"].pop()
        with self.assertRaises(ValueError):
            select_observed(self.plan_bytes, self.trace)

    def test_identity_checks_are_required(self):
        self.trace["identity_checks"] = []
        with self.assertRaises(ValueError):
            select_observed(self.plan_bytes, self.trace)

    def test_callback_failure_invalidates_trace(self):
        self.trace["error"] = "unwind failed"
        with self.assertRaises(ValueError):
            select_observed(self.plan_bytes, self.trace)

    def test_malformed_event_index_is_rejected(self):
        self.trace["events"][0]["index"] = -1
        with self.assertRaises(ValueError):
            select_observed(self.plan_bytes, self.trace)

    def test_negative_count_is_not_silently_treated_as_observed(self):
        self.trace["hits"][0]["count"] = -1
        with self.assertRaises(ValueError):
            select_observed(self.plan_bytes, self.trace)


if __name__ == "__main__":
    unittest.main()
