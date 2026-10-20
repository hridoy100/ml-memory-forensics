"""Source inside GDB to trace selected native entries during one forward call.

Run from the project root; see docs/NATIVE_TRACE.md. This starts and terminates
its own inferior. Do not use it in an existing debugging session.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

import gdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_trace_support import check_plan, mapped_address, parse_maps


def stack_frames():
    frames = []
    frame = gdb.newest_frame()
    try:
        while frame is not None and len(frames) < 32:
            frames.append({"pc": hex(frame.pc()), "name": frame.name()})
            frame = frame.older()
        return {"frames": frames, "limit_reached": frame is not None}
    except gdb.error as error:
        return {"frames": frames, "unwind_error": str(error)}


class EntryBreakpoint(gdb.Breakpoint):
    def __init__(self, address, index, report):
        super().__init__(f"*{address:#x}", internal=True)
        self.index = index
        self.report = report

    def stop(self):
        # GDB forbids changing execution state or breakpoints in this callback.
        try:
            report = self.report
            if len(report["events"]) >= report["event_limit"]:
                report["event_limit_hit"] = True
                return True
            thread = gdb.selected_thread()
            hit = report["hits"][self.index]
            hit["count"] += 1
            if hit["count"] == 1:
                hit["first_stack"] = stack_frames()
            report["events"].append(
                {
                    "index": self.index,
                    "thread": thread.global_num,
                    "ptid": list(thread.ptid),
                }
            )
            return False
        except Exception as error:
            self.report["error"] = f"Entry callback: {error}"
            return True


def main():
    if gdb.selected_inferior().pid or gdb.breakpoints():
        raise ValueError("Start a fresh GDB session without existing breakpoints")
    plan_path = Path(os.environ["NATIVE_TRACE_PLAN"])
    output_path = Path(os.environ["NATIVE_TRACE_OUTPUT"])
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    check_plan(plan)
    # Reserve a new output before starting; never replace prior evidence.
    output = output_path.open("x")
    report = dict(
        schema=1,
        completed_forward=False,
        event_limit_hit=False,
        candidate_plan_sha256=hashlib.sha256(plan_bytes).hexdigest(),
        event_limit=10000,
        events=[],
        hits=[
            dict(index=i, count=0, name=item["name"])
            for i, item in enumerate(plan["functions"])
        ],
        scope="Temporal entry hits at selected libtorch_cpu dynamic symbols "
        "across observed process threads, during the first forward call. "
        "Not a full call graph, instruction trace or all-branch coverage.",
    )
    breakpoints = []
    try:
        for command in (
            "set pagination off",
            "set confirm off",
            "set debuginfod enabled off",
            "set non-stop off",
        ):
            gdb.execute(command)
        start = gdb.Breakpoint("main.cpp:91", internal=True, temporary=True)
        breakpoints.append(start)
        gdb.execute("run")
        frame = gdb.newest_frame()
        if frame.name() != "main" or frame.find_sal().line != 91:
            raise ValueError("Did not reach the expected forward boundary")
        batch_start = int(gdb.parse_and_eval("start"))
        batch_end = int(gdb.parse_and_eval("end"))
        if (batch_start, batch_end) != (0, 128):
            raise ValueError("Expected the first 128-image batch")
        inferior = gdb.selected_inferior()
        main_thread = gdb.selected_thread().global_num
        report.update(
            pid=inferior.pid,
            main_thread=main_thread,
            batch_start=batch_start,
            batch_end=batch_end,
            gdb_version=gdb.VERSION,
            executable=gdb.current_progspace().filename,
        )
        maps = Path(f"/proc/{inferior.pid}/maps").read_text()
        mappings = parse_maps(maps, plan["library_name"])
        report["library_mappings"] = mappings
        report["identity_checks"] = []
        for identity in plan["identity_ranges"]:
            if not 0 < identity["size"] <= 4096:
                raise ValueError("Unreasonable identity size")
            address = mapped_address(
                mappings, identity["file_offset"], identity["size"]
            )
            data = bytes(inferior.read_memory(address, identity["size"]))
            digest = hashlib.sha256(data).hexdigest()
            if digest != identity["sha256"]:
                raise ValueError(f"Runtime library mismatch: {identity['kind']}")
            report["identity_checks"].append(
                dict(kind=identity["kind"], address=hex(address), sha256=digest)
            )
        # Set exact non-PLT entry addresses only after checking library identity.
        for index, item in enumerate(plan["functions"]):
            address = mapped_address(mappings, item["file_offset"], item["size"], True)
            report["hits"][index]["address"] = hex(address)
            breakpoints.append(EntryBreakpoint(address, index, report))
        end = gdb.Breakpoint("main.cpp:92", internal=True, temporary=True)
        end.thread = main_thread
        breakpoints.append(end)
        gdb.execute("continue")
        if report.get("error") or report["event_limit_hit"]:
            raise ValueError("Entry tracing stopped before forward completed")
        frame = gdb.newest_frame()
        if (
            frame.name() != "main"
            or frame.find_sal().line != 92
            or gdb.selected_thread().global_num != main_thread
        ):
            raise ValueError("Unexpected stop before the end of forward")
        report["observed_candidate_count"] = sum(
            hit["count"] > 0 for hit in report["hits"]
        )
        report["completed_forward"] = True
    except Exception as error:
        report["error"] = str(error)
    finally:
        for breakpoint in breakpoints:
            if breakpoint.is_valid():
                breakpoint.delete()
        if gdb.selected_inferior().pid:
            gdb.execute("kill", to_string=True)
        with output:
            output.write(json.dumps(report, indent=2) + "\n")
    if not report["completed_forward"]:
        raise gdb.GdbError(f"NATIVE_TRACE_INCOMPLETE: {report.get('error', 'unknown')}")
    print(
        f"NATIVE_TRACE_PASS: {len(report['events'])} entries, "
        f"{report['observed_candidate_count']}/{len(report['hits'])} candidate symbols"
    )


main()
