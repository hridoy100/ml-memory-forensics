"""Compare memory-extracted native code with its separately supplied library."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--library", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    if file_hash(args.library) != report["plan"]["reference_library_sha256"]:
        raise ValueError("Reference library differs from the symbol plan")
    if report["plan"]["elf_machine"] != 183:
        raise ValueError("The initial disassembly workflow supports AArch64 only")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    checks = []
    with args.library.open("rb") as reference:
        for index, function in enumerate(report["functions"]):
            result = {
                "name": function["name"],
                "status": function["status"],
                "match": False,
            }
            if function["status"] == "recovered":
                name = function["file"]
                if Path(name).name != name:
                    raise ValueError("Expected a simple recovered filename")
                path = args.report.parent / name
                actual = path.read_bytes()
                digest = hashlib.sha256(actual).hexdigest()
                if len(actual) != function["size"] or digest != function["sha256"]:
                    raise ValueError("Recovered code was modified after extraction")
                reference.seek(function["file_offset"])
                expected = reference.read(function["size"])
                assembly = args.output_dir / f"native-{index:03}.asm.txt"
                with assembly.open("w") as stream:
                    subprocess.run(
                        [
                            "objdump",
                            "-D",
                            "-b",
                            "binary",
                            "-m",
                            "aarch64",
                            f"--adjust-vma={function['address']}",
                            str(path),
                        ],
                        stdout=stream,
                        check=True,
                    )
                result.update(
                    match=actual == expected,
                    bytes=len(actual),
                    address=function["address"],
                    memory_sha256=digest,
                    reference_sha256=hashlib.sha256(expected).hexdigest(),
                    disassembly=assembly.name,
                )
            checks.append(result)
    passed = bool(checks) and all(item["match"] for item in checks)
    result = {
        "passed": passed,
        "pid": report["pid"],
        "functions": checks,
        "scope": "Exact bytes of selected functions, not all native functions or all forward-pass calls.",
    }
    (args.output_dir / "validation.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps(result, indent=2))
    print("NATIVE_CODE_VALIDATION_PASS" if passed else "NATIVE_CODE_VALIDATION_FAIL")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
