"""Recover a CPU TorchScript module from a Linux process address space.

The ABI profile is exported from the target executable's debug information.
This plugin does not load PyTorch, a checkpoint, or the original model source.
"""

import ast
import hashlib
import json
import math
import re
import struct
from pathlib import Path

from volatility3.framework import exceptions, interfaces, renderers
from volatility3.framework.configuration import requirements
from volatility3.framework.renderers import format_hints
from volatility3.plugins.linux import pslist


class RecoveryError(ValueError):
    pass


class TorchMemory:
    """Bounded reads of the profiled GNU C++ structures; never pad missing pages."""

    def __init__(self, layer, profile, max_bytes):
        if profile.get("schema") != 1 or profile.get("pointer_size") != 8:
            raise RecoveryError("Expected a schema-1, 64-bit ABI profile")
        if profile.get("byteorder") != "little":
            raise RecoveryError("Only little-endian profiles are supported")
        self.layer = layer
        self.profile = profile
        self.offsets = profile["offsets"]
        self.max_bytes = max_bytes

    def read(self, address, size):
        if size < 0 or size > self.max_bytes or (size and address < 4096):
            raise RecoveryError(f"Invalid read: 0x{address:x}, {size} bytes")
        return self.layer.read(address, size, pad=False) if size else b""

    def number(self, address, fmt="Q"):
        return struct.unpack("<" + fmt, self.read(address, struct.calcsize(fmt)))[0]

    def field(self, address, name, fmt="Q"):
        return self.number(address + self.offsets[name], fmt)

    def vector(self, address, item_size, limit=10000):
        start, end, capacity = struct.unpack("<QQQ", self.read(address, 24))
        if end < start or capacity < end or (end - start) % item_size:
            raise RecoveryError(f"Invalid vector at 0x{address:x}")
        count = (end - start) // item_size
        if count > limit:
            raise RecoveryError(f"Vector at 0x{address:x} exceeds {limit} items")
        return [start + i * item_size for i in range(count)]

    def string(self, address):
        # GNU libstdc++ C++11 ABI: data pointer, length, SSO/capacity union.
        pointer, size = struct.unpack("<QQ", self.read(address, 16))
        if size > 1024 * 1024:
            raise RecoveryError(f"Unreasonable string length {size}")
        return self.read(pointer, size).decode("utf-8", errors="strict")

    def ivalue(self, address, depth=0):
        if depth > 12:
            raise RecoveryError("IValue nesting exceeds 12 levels")
        payload = self.number(address)
        tag = self.profile["tags"].get(str(self.field(address, "ivalue_tag", "I")))
        result = {"slot": hex(address), "tag": tag}
        if tag == "None":
            result["value"] = None
        elif tag in ("Int", "UInt", "Bool", "Double"):
            fmt = {"Int": "q", "UInt": "Q", "Bool": "?", "Double": "d"}[tag]
            result["value"] = self.number(address, fmt)
        elif tag == "String":
            result["value"] = self.string(payload + self.offsets["string_value"])
        elif tag in ("Object", "Tensor"):
            result["pointer"] = hex(payload)
        elif tag in ("GenericList", "Tuple"):
            if tag == "GenericList":
                slots = self.vector(payload + self.offsets["list_values"], 16)
            else:
                size = self.field(payload, "tuple_inline_size")
                start = payload + self.offsets["tuple_values"]
                # TupleElements uses zero to select its vector arm, including
                # empty tuples; sizes 1..3 select inline IValues.
                if size == 0:
                    slots = self.vector(start, 16)
                elif 1 <= size <= 3:
                    slots = [start + i * 16 for i in range(size)]
                else:
                    raise RecoveryError("Invalid TupleElements inline size")
            result["value"] = [self.ivalue(slot, depth + 1) for slot in slots]
        else:
            result["raw_payload"] = hex(payload)
        return result

    def tensor(self, pointer):
        rank = self.field(pointer, "tensor_rank")
        if rank > 32:
            raise RecoveryError(f"Invalid tensor rank {rank}")
        start = pointer + self.offsets["tensor_sizes"]
        if rank > 5:
            start = self.number(start)
        shape = list(struct.unpack("<" + "q" * rank, self.read(start, rank * 8)))
        strides_start = start + (5 if rank <= 5 else rank) * 8
        strides = list(
            struct.unpack("<" + "q" * rank, self.read(strides_start, rank * 8))
        )
        numel = self.field(pointer, "tensor_numel", "q")
        if any(dim < 0 for dim in shape) or math.prod(shape) != numel:
            raise RecoveryError("Tensor shape and numel disagree")
        expected = 1
        for dim, stride in reversed(list(zip(shape, strides))):
            if dim > 1 and stride != expected:
                raise RecoveryError("Only contiguous tensors can be exported")
            expected *= dim
        dtype_index = self.field(pointer, "tensor_dtype", "H")
        dtypes = {3: ("<i4", 4), 4: ("<i8", 8), 6: ("<f4", 4), 7: ("<f8", 8)}
        if dtype_index not in dtypes:
            raise RecoveryError(f"Unsupported TypeMeta index {dtype_index}")
        dtype, item_size = dtypes[dtype_index]
        storage = self.field(pointer, "tensor_storage")
        device = self.field(storage, "storage_device", "b")
        if device != 0:
            raise RecoveryError(f"Expected CPU storage, got device type {device}")
        base = self.field(storage, "storage_data")
        offset = self.field(pointer, "tensor_offset", "q")
        storage_size = self.field(storage, "storage_nbytes", "q")
        size = numel * item_size
        if offset < 0 or storage_size < 0 or (offset * item_size + size) > storage_size:
            raise RecoveryError("Tensor exceeds its storage allocation")
        data_address = base + offset * item_size
        data = self.read(data_address, size)
        return {
            "tensor_impl": hex(pointer),
            "storage_impl": hex(storage),
            "allocation_base": hex(base),
            "data_address": hex(data_address),
            "storage_offset": offset,
            "storage_bytes": storage_size,
            "shape": shape,
            "strides": strides,
            "numel": numel,
            "dtype": dtype,
            "type_meta_index": dtype_index,
            "device": "cpu",
            "nbytes": size,
            "sha256": hashlib.sha256(data).hexdigest(),
        }, data


def npy_bytes(shape, dtype, data):
    """Encode NumPy v1 format without making NumPy a plugin dependency."""
    header = repr(
        {"descr": dtype, "fortran_order": False, "shape": tuple(shape)}
    ).encode("ascii")
    padding = (-(10 + len(header) + 1)) % 64
    header += b" " * padding + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + data


class PytorchModel(interfaces.plugins.PluginInterface):
    """Recover a GDB-identified CPU TorchScript model, tensors, and source text."""

    _required_framework_version = (2, 0, 0)
    _version = (1, 0, 0)

    @classmethod
    def get_requirements(cls):
        return [
            requirements.ModuleRequirement(
                name="kernel",
                description="Linux kernel",
                architectures=["AArch64", "Intel64"],
            ),
            requirements.PluginRequirement(
                name="pslist", plugin=pslist.PsList, version=(2, 0, 0)
            ),
            requirements.IntRequirement(
                name="pid", description="Captured inference PID"
            ),
            requirements.IntRequirement(
                name="root_object", description="GDB address of model._ivalue_.target_"
            ),
            requirements.StringRequirement(
                name="layout",
                description="JSON ABI profile exported from the target debug types",
            ),
            requirements.IntRequirement(
                name="max_bytes",
                description="Maximum bytes per tensor/source read",
                default=256 * 1024 * 1024,
                optional=True,
            ),
        ]

    def write_file(self, name, data):
        with self.open(name) as handle:
            handle.write(data)
        return handle.preferred_filename

    def write_json(self, name, value):
        return self.write_file(
            name, (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
        )

    def source(self, pointer):
        if pointer in self.sources:
            return self.sources[pointer]
        mem = self.mem
        pieces = mem.vector(pointer + mem.offsets["source_pieces"], 16, limit=4096)
        chunks = []
        total = 0
        for piece in pieces:
            length, address = struct.unpack("<QQ", mem.read(piece, 16))
            total += length
            if total > mem.max_bytes:
                raise RecoveryError("Source text exceeds read limit")
            chunks.append(mem.read(address, length))
        data = b"".join(chunks)
        filename = None
        if mem.field(pointer, "source_filename_engaged", "?"):
            filename = mem.string(pointer + mem.offsets["source_filename"])
        name = f"{self.prefix}-source-{len(self.sources):03d}.py"
        result = {
            "source_object": hex(pointer),
            "original_filename": filename,
            "starting_line": mem.field(pointer, "source_starting_line"),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "file": self.write_file(name, data),
        }
        # This is a static inventory of the recovered script, not a runtime trace.
        try:
            tree = ast.parse(data)
            result["definitions"] = [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.ClassDef, ast.FunctionDef))
            ]
            result["torch_calls"] = sorted(
                {
                    ast.unparse(node.func)
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and ast.unparse(node.func).startswith(("torch.", "ops."))
                }
            )
        except (SyntaxError, UnicodeError) as exc:
            result["parse_note"] = str(exc)
        self.sources[pointer] = result
        return result

    def graph(self, graph_pointer):
        mem = self.mem
        seen = set()

        def value(pointer):
            return {
                "address": hex(pointer),
                "id": mem.field(pointer, "value_id"),
                "name": mem.string(pointer + mem.offsets["value_name"]),
            }

        def values(node, field):
            return [
                value(mem.number(p)) for p in mem.vector(node + mem.offsets[field], 8)
            ]

        def block(pointer, depth=0):
            if depth > 32:
                raise RecoveryError("Graph block nesting exceeds 32")
            end = mem.field(pointer, "block_output")
            input_node = mem.field(pointer, "block_input")
            node = mem.field(end, "node_next")
            nodes = []
            while node != end:
                if node in seen or len(seen) >= 10000:
                    raise RecoveryError("Cyclic or oversized TorchScript graph")
                seen.add(node)
                kind = mem.field(node, "node_kind", "I")
                item = {
                    "address": hex(node),
                    "symbol_id": kind,
                    "kind": mem.profile["symbols"].get(
                        str(kind), f"dynamic_symbol_{kind}"
                    ),
                    "inputs": values(node, "node_inputs"),
                    "outputs": values(node, "node_outputs"),
                    "blocks": [
                        block(mem.number(p), depth + 1)
                        for p in mem.vector(node + mem.offsets["node_blocks"], 8)
                    ],
                }
                if mem.field(node, "node_source_engaged", "?"):
                    source_pointer = mem.field(node, "node_source")
                    if source_pointer:
                        try:
                            item["source"] = self.source(source_pointer)["file"]
                            item["source_range"] = [
                                mem.field(node, "node_source_start"),
                                mem.field(node, "node_source_end"),
                            ]
                        except (
                            RecoveryError,
                            exceptions.InvalidAddressException,
                            UnicodeError,
                        ) as exc:
                            item["source_error"] = str(exc)
                            self.errors.append(
                                {"source": hex(source_pointer), "error": str(exc)}
                            )
                nodes.append(item)
                node = mem.field(node, "node_next")
            return {
                "address": hex(pointer),
                "inputs": values(input_node, "node_outputs"),
                "nodes": nodes,
                "outputs": values(end, "node_inputs"),
            }

        return block(mem.field(graph_pointer, "graph_block"))

    def function(self, pointer):
        if pointer in self.functions:
            return self.functions[pointer]
        mem = self.mem
        result = {"address": hex(pointer)}
        self.functions[pointer] = result
        try:
            result["name"] = mem.string(pointer + mem.offsets["function_name"])
            graph = mem.field(pointer, "function_graph")
            result["graph_address"] = hex(graph)
            if graph:
                result["graph"] = self.graph(graph)
            else:
                result["status"] = "Graph not materialized at capture time"
        except (RecoveryError, exceptions.InvalidAddressException, UnicodeError) as exc:
            result["error"] = str(exc)
            self.errors.append({"function": hex(pointer), "error": str(exc)})
        return result

    def module(self, pointer, path, depth=0):
        if pointer in self.modules:
            return {"reference": self.modules[pointer]["path"], "address": hex(pointer)}
        if depth > 32 or len(self.modules) >= 512:
            raise RecoveryError("Module traversal limit exceeded")
        mem = self.mem
        class_pointer = mem.field(pointer, "object_type")
        result = {
            "path": path,
            "object_address": hex(pointer),
            "class_type_address": hex(class_pointer),
            "type": mem.string(class_pointer + mem.offsets["class_name"]),
            "attributes": [],
            "constants": {},
            "methods": [],
        }
        self.modules[pointer] = result
        descriptors = mem.vector(
            class_pointer + mem.offsets["class_attributes"],
            mem.profile["sizes"]["attribute"],
        )
        slots = mem.vector(pointer + mem.offsets["object_slots"], 16)
        if len(descriptors) != len(slots):
            raise RecoveryError(
                "Module attribute descriptors and IValue slots disagree"
            )
        for descriptor, slot in zip(descriptors, slots):
            name = mem.string(descriptor + mem.offsets["attribute_name"])
            full_name = f"{path}.{name}" if path else name
            kind = mem.profile["attribute_kinds"].get(
                str(mem.field(descriptor, "attribute_kind", "I"))
            )
            entry = {"name": name, "descriptor": hex(descriptor), "kind": kind}
            result["attributes"].append(entry)
            try:
                entry.update(mem.ivalue(slot))
                if entry["tag"] == "Object":
                    entry["module"] = self.module(
                        int(entry["pointer"], 16), full_name, depth + 1
                    )
                elif entry["tag"] == "Tensor":
                    tensor_pointer = int(entry["pointer"], 16)
                    if not tensor_pointer:
                        entry["status"] = "Undefined tensor"
                        continue
                    info, data = mem.tensor(tensor_pointer)
                    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", full_name)
                    info.update(
                        {
                            "name": full_name,
                            "kind": kind,
                            "file": self.write_file(
                                f"{self.prefix}-{safe_name}.npy",
                                npy_bytes(info["shape"], info["dtype"], data),
                            ),
                        }
                    )
                    entry["tensor"] = info
                    self.tensors.append(info)
            except (
                RecoveryError,
                exceptions.InvalidAddressException,
                UnicodeError,
            ) as exc:
                entry["error"] = str(exc)
                self.errors.append({"attribute": full_name, "error": str(exc)})
        names = mem.vector(
            class_pointer + mem.offsets["class_constants_names"],
            mem.profile["sizes"]["string"],
        )
        constants = mem.vector(
            class_pointer + mem.offsets["class_constants_values"], 16
        )
        if len(names) != len(constants):
            raise RecoveryError("Constant names and values disagree")
        for name, slot in zip(names, constants):
            result["constants"][mem.string(name)] = mem.ivalue(slot)
        for item in mem.vector(class_pointer + mem.offsets["class_methods"], 8):
            result["methods"].append(self.function(mem.number(item))["address"])
        return result

    def _generator(self):
        profile = json.loads(Path(self.config["layout"]).read_text())
        pid = self.config["pid"]
        root = self.config["root_object"]
        max_bytes = self.config["max_bytes"]
        if max_bytes <= 0:
            raise RecoveryError("max-bytes must be positive")
        task = next(
            pslist.PsList.list_tasks(
                self.context,
                self.config["kernel"],
                pslist.PsList.create_pid_filter([pid]),
            ),
            None,
        )
        if task is None:
            raise RecoveryError(f"PID {pid} is not present in the capture")
        layer_name = task.add_process_layer()
        if not layer_name:
            raise RecoveryError(f"Cannot construct process layer for PID {pid}")
        self.mem = TorchMemory(self.context.layers[layer_name], profile, max_bytes)
        self.prefix = f"pytorch-{pid}"
        self.sources, self.functions, self.modules = {}, {}, {}
        self.tensors, self.errors = [], []
        architecture = self.module(root, "")
        # The CompilationUnit also owns free functions called by module methods.
        if self.mem.field(root, "object_cu_engaged", "?"):
            cu = self.mem.field(root, "object_cu")
            for entry in self.mem.vector(cu + self.mem.offsets["cu_functions"], 8):
                self.function(self.mem.number(entry))
        report = {
            "schema": 1,
            "pid": pid,
            "root_object": hex(root),
            "process_layer": layer_name,
            "abi_profile": profile,
            "architecture": architecture,
            "tensors": self.tensors,
            "functions": list(self.functions.values()),
            "sources": list(self.sources.values()),
            "errors": self.errors,
            "scope": "CPU contiguous tensors; registered module hierarchy; materialized TorchScript graphs and their resident Source text. Native library source and runtime call coverage are not inferred.",
        }
        report_name = self.write_json(f"{self.prefix}-model.json", report)
        for tensor in self.tensors:
            yield 0, (
                pid,
                "tensor",
                tensor["name"],
                format_hints.Hex(int(tensor["data_address"], 16)),
                str(tensor["shape"]),
                tensor["file"],
            )
        yield 0, (
            pid,
            "summary",
            f"{len(self.modules)} modules, {len(self.tensors)} tensors, {len(self.sources)} sources, {len(self.errors)} errors",
            format_hints.Hex(root),
            "",
            report_name,
        )

    def run(self):
        return renderers.TreeGrid(
            [
                ("PID", int),
                ("Kind", str),
                ("Name", str),
                ("Address", format_hints.Hex),
                ("Shape", str),
                ("File", str),
            ],
            self._generator(),
        )
