"""Checks for forensic read integrity and tensor bounds."""

import json
import struct
import unittest
from pathlib import Path

from volatility3.framework import exceptions
from forensics.plugins.mlmodel import (
    PytorchModel,
    RecoveryError,
    TorchMemory,
    npy_bytes,
)


class SparseMemory:
    def __init__(self):
        self.data = {}

    def put(self, address, data):
        self.data.update({address + i: byte for i, byte in enumerate(data)})

    def read(self, address, size, pad=False):
        if pad:
            raise AssertionError("Forensic reads must not pad absent bytes")
        for i in range(size):
            if address + i not in self.data:
                raise exceptions.InvalidAddressException("fixture", address + i)
        return bytes(self.data[address + i] for i in range(size))


class TensorRecoveryTests(unittest.TestCase):
    def setUp(self):
        profile = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "forensics/profiles/torch-2.14.1-cpu-aarch64.json"
            ).read_text()
        )
        self.memory = SparseMemory()
        self.reader = TorchMemory(self.memory, profile, 1024)
        self.impl, self.storage, self.data = 0x1000, 0x2000, 0x3000
        self.memory.put(self.impl, b"\0" * 176)
        self.memory.put(self.storage, b"\0" * 96)
        self.set_field(self.impl, "tensor_storage", self.storage)
        self.set_field(self.impl, "tensor_rank", 2)
        self.memory.put(
            self.impl + self.reader.offsets["tensor_sizes"],
            struct.pack("<10q", 2, 3, 0, 0, 0, 3, 1, 0, 0, 0),
        )
        self.set_field(self.impl, "tensor_numel", 6)
        self.set_field(self.impl, "tensor_dtype", 6, "H")
        self.set_field(self.storage, "storage_data", self.data)
        self.set_field(self.storage, "storage_nbytes", 28)
        self.set_field(self.impl, "tensor_offset", 1)
        self.memory.put(self.data, struct.pack("<7f", -99, 1, 2, 3, 4, 5, 6))

    def set_field(self, base, name, value, fmt="Q"):
        self.memory.put(base + self.reader.offsets[name], struct.pack("<" + fmt, value))

    def test_storage_offset_excludes_unrelated_prefix(self):
        info, data = self.reader.tensor(self.impl)
        self.assertEqual(struct.unpack("<6f", data), (1, 2, 3, 4, 5, 6))
        self.assertEqual(info["data_address"], hex(self.data + 4))

    def test_missing_page_is_not_zero_filled(self):
        del self.memory.data[self.data + 12]
        with self.assertRaises(exceptions.InvalidAddressException):
            self.reader.tensor(self.impl)

    def test_invalid_shape_is_rejected(self):
        self.set_field(self.impl, "tensor_numel", 7)
        with self.assertRaisesRegex(RecoveryError, "shape and numel"):
            self.reader.tensor(self.impl)

    def test_storage_bounds_are_checked(self):
        self.set_field(self.storage, "storage_nbytes", 24)
        with self.assertRaisesRegex(RecoveryError, "storage allocation"):
            self.reader.tensor(self.impl)

    def test_gpu_storage_is_rejected(self):
        self.set_field(self.storage, "storage_device", 1, "b")
        with self.assertRaisesRegex(RecoveryError, "CPU storage"):
            self.reader.tensor(self.impl)

    def test_noncontiguous_tensor_is_rejected(self):
        self.memory.put(
            self.impl + self.reader.offsets["tensor_sizes"] + 40, struct.pack("<q", 4)
        )
        with self.assertRaisesRegex(RecoveryError, "contiguous"):
            self.reader.tensor(self.impl)

    def test_vector_cycle_or_bad_bounds_is_rejected(self):
        self.memory.put(0x4000, struct.pack("<3Q", 0x5000, 0x5010, 0x5008))
        with self.assertRaisesRegex(RecoveryError, "Invalid vector"):
            self.reader.vector(0x4000, 8)

    def test_numpy_header_keeps_scalar_shape(self):
        data = npy_bytes([], "<i8", struct.pack("<q", 15))
        size = struct.unpack("<H", data[8:10])[0]
        self.assertIn(b"'shape': ()", data[10 : 10 + size])
        self.assertEqual((10 + size) % 64, 0)

    def test_tuple_vector_arm_does_not_look_empty(self):
        self.memory.put(0x4000, struct.pack("<QII", 0x5000, 11, 0))
        self.memory.put(0x5010, struct.pack("<Q", 0))
        self.memory.put(0x5018, struct.pack("<3Q", 0x6000, 0x6040, 0x6040))
        for index in range(4):
            self.memory.put(0x6000 + index * 16, struct.pack("<qII", index, 5, 0))
        result = self.reader.ivalue(0x4000)
        self.assertEqual([item["value"] for item in result["value"]], [0, 1, 2, 3])

    def test_manifest_uses_filename_resolved_on_close(self):
        class RenamingOutput:
            def __init__(self, name):
                self.preferred_filename = name

            def __enter__(self):
                return self

            def write(self, data):
                pass

            def __exit__(self, *args):
                self.preferred_filename = "resolved.npy"

        writer = object.__new__(PytorchModel)
        writer._file_handler = RenamingOutput
        self.assertEqual(writer.write_file("requested.npy", b"data"), "resolved.npy")


if __name__ == "__main__":
    unittest.main()
