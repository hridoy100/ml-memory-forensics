"""Check native address mapping and strict handling of absent code bytes."""

import struct
import unittest

from volatility3.framework import exceptions
from forensics.plugins.mlnative import locate_range, read_code
from scripts.plan_native_recovery import executable_file_offset


class Memory:
    def __init__(self, data=None, missing=False, short=False):
        self.data = data
        self.missing = missing
        self.short = short

    def read(self, address, size, pad=False):
        if pad:
            raise AssertionError("Absent code must not be zero-filled")
        if self.missing:
            raise exceptions.InvalidAddressException("fixture", address)
        return self.data[: size - 1] if self.short else self.data[:size]


class NativeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.maps = [
            {
                "start": 0xFFFFEDE10000,
                "end": 0xFFFFF5B19000,
                "file_offset": 0xEC0000,
                "flags": "r-x",
            }
        ]
        self.segments = [
            {"vaddr": 0x12C0000, "offset": 0xEC0000, "filesz": 0x7D08FF4, "flags": 5}
        ]

    def test_nonzero_elf_load_address_is_not_assumed_to_be_file_offset(self):
        offset = executable_file_offset(0x1322F50, 0x248, self.segments)
        self.assertEqual(offset, 0xF22F50)
        self.assertEqual(locate_range(self.maps, offset, 0x248, True), 0xFFFFEDE72F50)

    def test_aslr_changes_the_process_address_not_the_file_offset(self):
        maps = [dict(self.maps[0], start=0x70000000, end=0x77D09000)]
        self.assertEqual(locate_range(maps, 0xF22F50, 0x248, True), 0x70062F50)

    def test_non_executable_mapping_is_not_accepted_as_code(self):
        maps = [dict(self.maps[0], flags="r--")]
        with self.assertRaises(ValueError):
            locate_range(maps, 0xF22F50, 0x248, True)
        self.assertEqual(locate_range(maps, 0xF22F50, 0x248, False), 0xFFFFEDE72F50)

    def test_ambiguous_duplicate_mapping_is_rejected(self):
        with self.assertRaises(ValueError):
            locate_range(self.maps * 2, 0xF22F50, 0x248, True)

    def test_function_cannot_run_past_mapping_boundary(self):
        with self.assertRaises(ValueError):
            locate_range(
                self.maps,
                0xEC0000,
                self.maps[0]["end"] - self.maps[0]["start"] + 1,
                True,
            )

    def test_symbol_in_non_file_backed_tail_is_rejected(self):
        with self.assertRaises(ValueError):
            executable_file_offset(0x12C0000 + 0x7D08FF4, 4, self.segments)

    def test_missing_page_is_not_replaced_with_reference_bytes(self):
        with self.assertRaises(exceptions.InvalidAddressException):
            read_code(Memory(missing=True), self.maps, 0xF22F50, 8, 1024)

    def test_short_read_is_not_reported_as_complete(self):
        with self.assertRaises(ValueError):
            read_code(Memory(b"\x01" * 8, short=True), self.maps, 0xF22F50, 8, 1024)

    def test_function_read_uses_actual_memory_bytes(self):
        data = struct.pack("<II", 0xD10443FF, 0xA9057BFD)
        address, result = read_code(Memory(data), self.maps, 0xF22F50, len(data), 1024)
        self.assertEqual(address, 0xFFFFEDE72F50)
        self.assertEqual(result, data)

    def test_oversized_function_is_rejected_before_reading(self):
        with self.assertRaises(ValueError):
            read_code(Memory(missing=True), self.maps, 0xF22F50, 1025, 1024)


if __name__ == "__main__":
    unittest.main()
