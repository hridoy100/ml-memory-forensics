"""Recover selected native function bytes from a captured Linux process."""

import hashlib
import json
from pathlib import Path

from volatility3.framework import exceptions, interfaces, renderers
from volatility3.framework.configuration import requirements
from volatility3.plugins.linux import proc, pslist


def locate_range(mappings, file_offset, size, executable):
    if file_offset < 0 or size <= 0:
        raise ValueError("Invalid file range")
    candidates = [
        item
        for item in mappings
        if "r" in item["flags"]
        and (not executable or "x" in item["flags"])
        and item["file_offset"] <= file_offset
        and file_offset + size <= item["file_offset"] + item["end"] - item["start"]
    ]
    if len(candidates) != 1:
        raise ValueError("Range must fit exactly one eligible library mapping")
    mapping = candidates[0]
    return mapping["start"] + file_offset - mapping["file_offset"]


def read_code(layer, mappings, file_offset, size, max_bytes):
    if not 0 < size <= max_bytes:
        raise ValueError("Function exceeds configured read bounds")
    address = locate_range(mappings, file_offset, size, executable=True)
    data = layer.read(address, size, pad=False)
    if len(data) != size:
        raise ValueError("Process layer returned an incomplete function")
    return address, data


class NativeCode(interfaces.plugins.PluginInterface):
    """Symbols-guided CPU code extraction; never fills gaps from a disk library."""

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
            requirements.IntRequirement(name="pid", description="Captured process PID"),
            requirements.StringRequirement(
                name="plan", description="Reference-symbol plan JSON"
            ),
            requirements.IntRequirement(
                name="max_bytes",
                description="Maximum bytes per function",
                default=1024 * 1024,
                optional=True,
            ),
        ]

    def write_file(self, name, data):
        with self.open(name) as stream:
            stream.write(data)
        return stream.preferred_filename

    def _generator(self):
        plan = json.loads(Path(self.config["plan"]).read_text())
        if plan.get("schema") != 1 or not 0 < len(plan["functions"]) <= 128:
            raise ValueError("Unsupported or empty native plan")
        if not any(item["kind"] == "GNU build ID" for item in plan["identity_ranges"]):
            raise ValueError("Plan must include the reference build ID")
        pid = self.config["pid"]
        task = next(
            pslist.PsList.list_tasks(
                self.context,
                self.config["kernel"],
                pslist.PsList.create_pid_filter([pid]),
            ),
            None,
        )
        if task is None:
            raise ValueError(f"PID {pid} is absent")
        layer_name = task.add_process_layer()
        if not layer_name:
            raise ValueError("No process translation layer")
        layer = self.context.layers[layer_name]
        mappings = []
        for vma in proc.Maps.list_vmas(task):
            path = str(vma.get_name(self.context, task))
            if Path(path).name == plan["library_name"]:
                mappings.append(
                    {
                        "start": int(vma.vm_start),
                        "end": int(vma.vm_end),
                        "file_offset": int(vma.get_page_offset()),
                        "flags": vma.get_protection(),
                        "path": path,
                    }
                )
        identities = []
        for item in plan["identity_ranges"]:
            if not 0 < item["size"] <= 4096:
                raise ValueError("Unreasonable identity read")
            address = locate_range(
                mappings, item["file_offset"], item["size"], executable=False
            )
            data = layer.read(address, item["size"], pad=False)
            digest = hashlib.sha256(data).hexdigest()
            if digest != item["sha256"]:
                raise ValueError(f"Captured library identity mismatch: {item['kind']}")
            identities.append(
                {
                    "kind": item["kind"],
                    "address": hex(address),
                    "sha256": digest,
                    "match": True,
                }
            )
        results = []
        for index, function in enumerate(plan["functions"]):
            result = dict(function)
            try:
                address, data = read_code(
                    layer,
                    mappings,
                    function["file_offset"],
                    function["size"],
                    self.config["max_bytes"],
                )
                result.update(
                    status="recovered",
                    address=hex(address),
                    sha256=hashlib.sha256(data).hexdigest(),
                    file=self.write_file(f"native-{pid}-{index:03}.bin", data),
                )
            except (exceptions.InvalidAddressException, ValueError) as error:
                result.update(
                    status="unreadable",
                    error=str(error) or type(error).__name__,
                    error_type=type(error).__name__,
                )
                if isinstance(error, exceptions.InvalidAddressException):
                    result["invalid_address"] = hex(error.invalid_address)
            results.append(result)
            yield 0, (
                pid,
                function["name"],
                result["status"],
                function["size"],
                result.get("file", ""),
            )
        report = {
            "schema": 1,
            "pid": pid,
            "process_layer": layer_name,
            "plan": plan,
            "mappings": mappings,
            "identity_checks": identities,
            "functions": results,
            "complete_selected_functions": all(
                item["status"] == "recovered" for item in results
            ),
            "scope": "Selected native functions only. Code bytes come from the memory image, without padding or disk fallback. This is not exhaustive forward-path discovery, branch coverage, or native source recovery.",
        }
        name = self.write_file(
            f"native-{pid}-report.json", (json.dumps(report, indent=2) + "\n").encode()
        )
        yield 0, (
            pid,
            "report",
            "complete" if report["complete_selected_functions"] else "incomplete",
            0,
            name,
        )

    def run(self):
        return renderers.TreeGrid(
            [
                ("PID", int),
                ("Symbol", str),
                ("Status", str),
                ("Bytes", int),
                ("File", str),
            ],
            self._generator(),
        )
