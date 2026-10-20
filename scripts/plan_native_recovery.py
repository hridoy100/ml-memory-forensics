"""Plan symbols-guided native recovery; this tool supplies locations, not code."""

import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path


MODEL_FORWARD_PREFIXES = [
    "at::native::conv2d_symint(",
    "at::native::convolution(",
    "at::native::_convolution(",
    "at::native::batch_norm(",
    "at::native::_batch_norm_impl_index(",
    "at::native::native_batch_norm(",
    "at::native::batch_norm_cpu(",
    "at::native::relu(",
    "at::native::relu_(",
    "at::native::max_pool2d(",
    "at::native::max_pool2d_with_indices(",
    "at::native::linear(",
    "at::native::addmm(",
    "at::native::flatten(",
]


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def elf_metadata(path):
    with path.open("rb") as stream:
        header = stream.read(64)
        if header[:6] != b"\x7fELF\x02\x01":
            raise ValueError("Expected a little-endian ELF64 library")
        fields = struct.unpack("<16sHHIQQQIHHHHHH", header)
        phoff, entry_size, count = fields[5], fields[9], fields[10]
        if entry_size < 56 or not 0 < count <= 1024:
            raise ValueError("Invalid ELF program header table")
        segments, identities = [], [
            {
                "kind": "ELF header",
                "file_offset": 0,
                "size": 64,
                "sha256": hashlib.sha256(header).hexdigest(),
            }
        ]
        for index in range(count):
            stream.seek(phoff + index * entry_size)
            kind, flags, offset, vaddr, _, filesz, memsz, _ = struct.unpack(
                "<IIQQQQQQ", stream.read(56)
            )
            if kind == 1:
                segments.append(
                    {
                        "offset": offset,
                        "vaddr": vaddr,
                        "filesz": filesz,
                        "memsz": memsz,
                        "flags": flags,
                    }
                )
            if kind == 4:
                if filesz > 1024 * 1024:
                    raise ValueError("Unreasonable ELF note size")
                stream.seek(offset)
                notes = stream.read(filesz)
                cursor = 0
                while cursor + 12 <= len(notes):
                    namesz, descsz, note_type = struct.unpack_from(
                        "<III", notes, cursor
                    )
                    name_start = cursor + 12
                    desc_start = name_start + ((namesz + 3) & ~3)
                    end = desc_start + descsz
                    next_note = desc_start + ((descsz + 3) & ~3)
                    if end > len(notes) or next_note <= cursor:
                        raise ValueError("Invalid ELF note bounds")
                    if (
                        note_type == 3
                        and notes[name_start : name_start + namesz] == b"GNU\0"
                    ):
                        value = notes[desc_start:end]
                        identities.append(
                            {
                                "kind": "GNU build ID",
                                "file_offset": offset + desc_start,
                                "size": len(value),
                                "hex": value.hex(),
                                "sha256": hashlib.sha256(value).hexdigest(),
                            }
                        )
                    cursor = next_note
        if not any(item["kind"] == "GNU build ID" for item in identities):
            raise ValueError("The first implementation requires a GNU build ID")
        return fields[2], segments, identities


def executable_file_offset(value, size, segments):
    matches = [
        segment
        for segment in segments
        if segment["flags"] & 1
        and size > 0
        and segment["vaddr"] <= value
        and value + size <= segment["vaddr"] + segment["filesz"]
    ]
    if len(matches) != 1:
        raise ValueError("Symbol must fit inside one file-backed executable PT_LOAD")
    segment = matches[0]
    return segment["offset"] + value - segment["vaddr"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", required=True, type=Path)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--profile",
        choices=["model-forward"],
        help="Candidate entries for this CNN; not all native callees",
    )
    selection.add_argument(
        "--prefix",
        action="append",
        help="Exact start of a demangled symbol; repeat for multiple prefixes",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new plan path")
    prefixes = (
        MODEL_FORWARD_PREFIXES
        if args.profile
        else args.prefix or ["at::native::convolution("]
    )
    machine, segments, identities = elf_metadata(args.library)
    symbols = []
    with subprocess.Popen(
        ["nm", "-D", "-S", "--defined-only", "-C", str(args.library)],
        stdout=subprocess.PIPE,
        text=True,
    ) as process:
        for line in process.stdout:
            parts = line.split(maxsplit=3)
            if len(parts) != 4 or parts[2] not in ("T", "t", "W", "w"):
                continue
            name = parts[3].strip()
            if any(name.startswith(prefix) for prefix in prefixes):
                value, size = int(parts[0], 16), int(parts[1], 16)
                if not 0 < size <= 1024 * 1024 or len(symbols) >= 128:
                    raise ValueError("Selected symbol exceeds this experiment's bounds")
                symbols.append(
                    {
                        "name": name,
                        "elf_value": value,
                        "file_offset": executable_file_offset(value, size, segments),
                        "size": size,
                    }
                )
        if process.wait():
            raise RuntimeError("nm failed")
    unmatched = [
        prefix
        for prefix in prefixes
        if not any(symbol["name"].startswith(prefix) for symbol in symbols)
    ]
    if not symbols or (unmatched and not args.profile):
        raise ValueError("At least one requested symbol prefix was not found")
    result = {
        "schema": 1,
        "method": "symbols-guided",
        "library_name": args.library.name,
        "reference_library": str(args.library.resolve()),
        "reference_library_sha256": file_hash(args.library),
        "elf_machine": machine,
        "identity_ranges": identities,
        "functions": symbols,
        "scope": "Symbol locations and sizes come from the reference ELF. The recovery plugin reads code bytes only from the captured process layer.",
    }
    if args.profile:
        result.update(candidate_profile=args.profile, unmatched_prefixes=unmatched)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    for symbol in symbols:
        print(
            f"{symbol['name']}: file offset {symbol['file_offset']:#x}, {symbol['size']} bytes"
        )
    print("NATIVE_PLAN_PASS")


if __name__ == "__main__":
    main()
