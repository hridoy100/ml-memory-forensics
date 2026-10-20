"""Check LiME range framing and hash a capture; this is not acquisition certification."""

import argparse
import hashlib
import json
import struct
from pathlib import Path


def check_capture(capture):
    ranges, digest = [], hashlib.sha256()
    size = capture.stat().st_size
    with capture.open("rb") as stream:
        position = 0
        while position < size:
            header = stream.read(32)
            if len(header) != 32:
                raise ValueError("Incomplete LiME header")
            magic, version, start, end, _ = struct.unpack("<IIQQQ", header)
            length = end - start + 1
            if (
                magic != 0x4C694D45
                or version != 1
                or length <= 0
                or position + 32 + length > size
            ):
                raise ValueError("Invalid or truncated LiME range")
            if ranges and start <= int(ranges[-1]["physical_end"], 16):
                raise ValueError("Overlapping or unordered physical ranges")
            digest.update(header)
            remaining = length
            while remaining:
                data = stream.read(min(remaining, 1024 * 1024))
                if not data:
                    raise ValueError("Truncated LiME payload")
                digest.update(data)
                remaining -= len(data)
            ranges.append(
                {
                    "header_file_offset": position,
                    "physical_start": hex(start),
                    "physical_end": hex(end),
                    "bytes": length,
                }
            )
            position += 32 + length
    if not ranges:
        raise ValueError("Empty capture")
    report = {
        "capture": str(capture.resolve()),
        "bytes": size,
        "sha256": digest.hexdigest(),
        "range_framing_valid": True,
        "ranges": ranges,
        "scope": "All stored ranges have complete payloads and valid framing. This does not prove all system RAM was acquired or that the capture is temporally atomic.",
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = check_capture(args.capture)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print("LIME_RANGE_CHECK_PASS")


if __name__ == "__main__":
    main()
