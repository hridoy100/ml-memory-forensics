"""Display saved check logs as labeled HTML reports for browser screenshots."""

import argparse
import hashlib
import html
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path


PAGES = {
    "05-training-record": ("Recorded training checkpoint", ["training-record.log"]),
    "06-export": ("Fresh TorchScript export", ["export.log"]),
    "07-debug-build": (
        "Fresh C++ Debug build",
        ["configure.log", "build.log", "debug-sections.log", "cpp-inference.log"],
    ),
    "08-extraction": (
        "Fresh extraction from the original LiME image",
        ["extraction.log"],
    ),
    "09-validation": ("Recovered state and source validation", ["validation.log"]),
    "10-replay": ("Full recovered-model replay", ["replay.log"]),
    "11-native-forward": ("Live native convolution sample", ["native-forward.log"]),
}


def excerpt(name, text):
    lines = text.splitlines()
    if name == "debug-sections.log":
        return "\n".join(
            line
            for line in lines
            if any(
                part in line
                for part in (
                    "Reproduction check:",
                    ".debug_info",
                    ".debug_line",
                    ".debug_macro",
                    "STEP_PASS",
                )
            )
        )
    if name == "native-forward.log":
        selected = []
        instructions = 0
        for line in lines:
            if line.startswith("=> "):
                instructions = 3
            if instructions:
                selected.append(line)
                instructions -= 1
            elif line.startswith(
                (
                    "Live reproduction PID:",
                    "Native implementation address:",
                    "#0 ",
                    "#9 ",
                    "#14 ",
                    "NATIVE_FORWARD_SAMPLE_PASS",
                )
            ):
                selected.append(line)
            elif "in section .text" in line:
                selected.append(line)
        return "\n".join(selected)
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    style = """body{margin:36px auto;padding:0 28px;max-width:1440px;font-family:system-ui,sans-serif;color:#162431;background:#fff}h1{font-size:30px;margin-bottom:12px}p{line-height:1.5}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f5f7;border:1px solid #d6dde3;border-radius:6px;padding:16px;font:13px/1.45 Menlo,monospace}.notice{border-left:4px solid #277252;padding:8px 16px;background:#eef7f1}.hash{font:12px/1.5 monospace;overflow-wrap:anywhere}h2{font-size:18px;margin-top:24px}a{color:#145a91}"""
    summary = json.loads((args.logs / "summary.json").read_text())
    date = (
        datetime.fromisoformat(summary["checked_at"])
        .astimezone(ZoneInfo("America/Chicago"))
        .strftime("%B %d, %Y")
    )
    links = []
    for stem, (title, files) in PAGES.items():
        sections = []
        for name in files:
            data = (args.logs / name).read_bytes()
            text = data.decode()
            shown = excerpt(name, text)
            note = (
                "Selected lines; complete original log linked below."
                if shown != text
                else "Complete saved step log."
            )
            (args.output_dir / name).write_bytes(data)
            sections.append(
                f"<h2>{html.escape(name)}</h2><p>{note} <a href='{name}'>Raw log</a></p><p class='hash'>SHA-256: {hashlib.sha256(data).hexdigest()}</p><pre>{html.escape(shown)}</pre>"
            )
        notice = f"Report view of recorded check output. Reproduction date: {date}. This is not a historical terminal screenshot."
        if "training" in stem:
            notice += " The training record is historical; the checkpoint check is new. Training was not rerun."
        if "native" in stem:
            notice += f" This sample is live PID {summary['live_native_sample_pid']}, not captured PID {summary['captured_pid']}. It is not a complete native trace."
        page = f"<!doctype html><html lang='en'><meta charset='utf-8'><title>{title}</title><style>{style}</style><main><h1>{title}</h1><p class='notice'>{notice}</p>{''.join(sections)}</main></html>"
        (args.output_dir / f"{stem}.html").write_text(page)
        links.append(f"<li><a href='{stem}.html'>{title}</a></li>")
    (args.output_dir / "index.html").write_text(
        f"<!doctype html><meta charset='utf-8'><title>Submission check reports</title><style>{style}</style><h1>Submission check reports</h1><p>Browser views of saved logs. No historical terminal sessions are recreated.</p><ul>{''.join(links)}</ul>"
    )
    print(args.output_dir / "index.html")


if __name__ == "__main__":
    main()
