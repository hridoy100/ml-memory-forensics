"""Compare recovered tensors, module order, and resident code with a reference.

The recovery plugin never reads this reference. This separate check requires
PyTorch and NumPy and also saves the recovered state dictionary as a .pt file.
"""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import torch


def modules(root):
    yield root
    for attribute in root["attributes"]:
        child = attribute.get("module")
        if child and "reference" not in child:
            yield from modules(child)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--reference",
        type=Path,
        required=True,
        help="Original TorchScript .pt; validation only",
    )
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    root = args.report.parent
    reference = torch.jit.load(str(args.reference), map_location="cpu").eval()
    expected = reference.state_dict()
    recovered = {}
    checks = []
    for item in report["tensors"]:
        array = np.load(root / item["file"], allow_pickle=False)
        data = array.tobytes(order="C")
        actual_hash = hashlib.sha256(data).hexdigest()
        original = expected.get(item["name"])
        reference_hash = (
            None
            if original is None
            else hashlib.sha256(original.contiguous().numpy().tobytes()).hexdigest()
        )
        passed = (
            original is not None
            and actual_hash == reference_hash == item["sha256"]
            and list(array.shape) == item["shape"] == list(original.shape)
            and array.dtype == original.numpy().dtype
        )
        checks.append(
            {
                "name": item["name"],
                "sha256": actual_hash,
                "reference_sha256": reference_hash,
                "match": passed,
            }
        )
        recovered[item["name"]] = torch.from_numpy(array.copy())
    recovered_modules = [
        (module["path"], module["type"].rsplit(".", 1)[-1])
        for module in modules(report["architecture"])
    ]
    reference_modules = [
        (name, module.original_name) for name, module in reference.named_modules()
    ]
    sources = []
    with zipfile.ZipFile(args.reference) as archive:
        code = {
            name.split("/code/", 1)[1]: name
            for name in archive.namelist()
            if "/code/" in name and name.endswith(".py")
        }
        for item in report["sources"]:
            key = (item.get("original_filename") or "").removeprefix("code/")
            data = (root / item["file"]).read_bytes()
            original = archive.read(code[key]) if key in code else None
            sources.append(
                {
                    "file": item["file"],
                    "archive_path": key,
                    "match": original is not None
                    and original == data
                    and hashlib.sha256(data).hexdigest() == item["sha256"],
                }
            )
        all_archive_sources_recovered = set(code) == {
            item["archive_path"] for item in sources
        }
    passed = (
        not report["errors"]
        and set(recovered) == set(expected)
        and all(item["match"] for item in checks)
        and recovered_modules == reference_modules
        and bool(sources)
        and all(item["match"] for item in sources)
        and all_archive_sources_recovered
    )
    result = {
        "passed": passed,
        "pid": report["pid"],
        "reference_sha256": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
        "tensor_count": len(checks),
        "total_tensor_bytes": sum(item["nbytes"] for item in report["tensors"]),
        "tensors": checks,
        "module_count": len(recovered_modules),
        "module_names_types_and_order_match": recovered_modules == reference_modules,
        "source_count": len(sources),
        "sources": sources,
        "all_archive_sources_recovered": all_archive_sources_recovered,
        "graph_count": sum(
            bool(function.get("graph")) for function in report["functions"]
        ),
        "recovery_errors": report["errors"],
    }
    if passed:
        # Only captured bytes populate this dictionary; nothing is filled from the reference.
        state_path = root / "recovered_state_dict.pt"
        torch.save(recovered, state_path)
        result["recovered_state_dict"] = str(state_path)
    output = root / "validation.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        f"Tensors: {sum(item['match'] for item in checks)}/{len(checks)} byte-identical"
    )
    print(
        f"Module names, types, and order: {'MATCH' if result['module_names_types_and_order_match'] else 'MISMATCH'}"
    )
    print(
        f"TorchScript source files: {sum(item['match'] for item in sources)}/{len(sources)} byte-identical"
    )
    print(f"All archived source files recovered: {all_archive_sources_recovered}")
    print(f"Materialized graphs: {result['graph_count']}")
    print("VALIDATION_PASS" if passed else "VALIDATION_FAIL")
    print(output)
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
