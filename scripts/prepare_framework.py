"""Apply the measured ARM64 plugin requirements to the exact framework base."""

import argparse
import subprocess
from pathlib import Path

BASE = "5ee05ce7b440c0d6a0d45f7f9a343b702c7b38e4"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("framework", type=Path)
    args = parser.parse_args()
    framework = args.framework.resolve()
    head = subprocess.check_output(
        ["git", "-C", str(framework), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != BASE:
        raise SystemExit(
            f"Expected framework base {BASE}; found {head}. No files changed."
        )
    patch = Path(__file__).resolve().parents[1] / "patches/arm64-process-plugins.patch"
    command = ["git", "-C", str(framework), "apply"]
    if (
        subprocess.run(
            command + ["--check", str(patch)], capture_output=True
        ).returncode
        == 0
    ):
        subprocess.run(command + [str(patch)], check=True)
        print("Applied ARM64 requirements for PsList and Maps.")
    elif (
        subprocess.run(
            command + ["--reverse", "--check", str(patch)], capture_output=True
        ).returncode
        == 0
    ):
        print("ARM64 requirements already applied.")
    else:
        raise SystemExit("Patch does not apply cleanly. Existing files were preserved.")


if __name__ == "__main__":
    main()
