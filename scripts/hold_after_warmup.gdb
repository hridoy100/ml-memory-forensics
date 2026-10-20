# Execute one batch, then hold the process while LiME captures its resident code.
set pagination off
set confirm off
set debuginfod enabled off
break main.cpp:91
ignore 1 1
run
python
import json
import os
import time
from pathlib import Path
start = int(gdb.parse_and_eval("start"))
if start != 128:
    raise gdb.GdbError(f"Expected one completed batch, got start={start}")
record = {
    "pid": gdb.selected_inferior().pid,
    "completed_images_before_stop": start,
    "model_object": hex(int(gdb.parse_and_eval("model._ivalue_.target_"))),
    "input_tensor_impl": hex(int(gdb.parse_and_eval("images.impl_.target_"))),
    "scope": "Paused before the second forward call after one completed CPU batch. This does not establish all-branch coverage.",
}
ready = Path(os.environ["NATIVE_CAPTURE_READY"])
ready.write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
print("WARMUP_CAPTURE_READY", flush=True)
resume = Path(os.environ["NATIVE_CAPTURE_RESUME"])
deadline = time.monotonic() + 600
while not resume.exists():
    if time.monotonic() >= deadline:
        raise gdb.GdbError("Timed out waiting for memory capture")
    time.sleep(0.25)
end
kill
