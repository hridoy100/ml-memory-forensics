"""Reject capture truncation and check build-ID/symbol-offset prerequisites."""

import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from scripts.check_lime_ranges import check_capture
from scripts.plan_native_recovery import elf_metadata


class CaptureFormatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "capture"

    def test_complete_lime_range_preserves_physical_address_and_file_hash(self):
        data = struct.pack("<IIQQQ", 0x4C694D45, 1, 0x40000000, 0x40000003, 0) + b"abcd"
        self.path.write_bytes(data)
        result = check_capture(self.path)
        self.assertEqual(result["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(result["ranges"][0]["physical_start"], "0x40000000")
        self.assertEqual(result["ranges"][0]["bytes"], 4)

    def test_truncated_capture_does_not_pass_on_valid_magic_alone(self):
        self.path.write_bytes(
            struct.pack("<IIQQQ", 0x4C694D45, 1, 0x1000, 0x1FFF, 0) + b"short"
        )
        with self.assertRaises(ValueError):
            check_capture(self.path)

    def test_overlapping_physical_ranges_are_rejected(self):
        header = struct.pack("<IIQQQ", 0x4C694D45, 1, 0x1000, 0x1003, 0)
        self.path.write_bytes((header + b"abcd") * 2)
        with self.assertRaises(ValueError):
            check_capture(self.path)

    def test_wrong_endianness_is_rejected_before_symbol_planning(self):
        self.path.write_bytes(b"\x7fELF\x02\x02" + b"\0" * 58)
        with self.assertRaises(ValueError):
            elf_metadata(self.path)

    def test_build_id_location_is_a_file_offset_not_a_virtual_address(self):
        data = bytearray(0x300)
        ident = b"\x7fELF\x02\x01\x01" + b"\0" * 9
        data[:64] = struct.pack(
            "<16sHHIQQQIHHHHHH", ident, 3, 183, 1, 0, 64, 0, 0, 64, 56, 2, 0, 0, 0
        )
        data[64:120] = struct.pack(
            "<IIQQQQQQ", 1, 5, 0x200, 0x4000, 0x4000, 0x100, 0x100, 0x1000
        )
        data[120:176] = struct.pack("<IIQQQQQQ", 4, 4, 0x180, 0x8000, 0x8000, 36, 36, 4)
        build_id = bytes(range(20))
        data[0x180:0x1A4] = struct.pack("<III", 4, 20, 3) + b"GNU\0" + build_id
        self.path.write_bytes(data)
        machine, segments, identities = elf_metadata(self.path)
        self.assertEqual(machine, 183)
        self.assertEqual(segments[0]["vaddr"], 0x4000)
        self.assertEqual(identities[1]["file_offset"], 0x190)
        self.assertEqual(identities[1]["sha256"], hashlib.sha256(build_id).hexdigest())


if __name__ == "__main__":
    unittest.main()
