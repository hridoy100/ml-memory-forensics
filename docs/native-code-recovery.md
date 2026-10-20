# Native-code recovery

The model extractor recovers generated TorchScript source. This experiment
also recovers selected ARM64 function bodies from `libtorch_cpu.so` in a LiME
image and compares them with the matching library.

## Results

| Check | Result |
| --- | --- |
| Original image, PID 3183 | ELF/build ID match; selected convolution range is unreadable |
| Warm image, PID 4540 | Captured after one completed 128-image batch |
| Initial function recovery | All 584 bytes of `at::native::convolution(...)` match |
| Later live trace, PID 2782 | 40 entry hits across 10 of 12 candidate symbols |
| Trace-selected recovery from the warm image | 10/10 bodies, 23,340 bytes, all match |

The [first recovery reports](../evidence/native-recovery-2026-10-20/README.md)
preserve both the unreadable original range and the successful warm capture.
The [trace reports](../evidence/native-trace-2026-10-20/README.md) contain the
candidate set, events, selected plan, extraction results, and disassembly.

The trace stops immediately before and after the first forward call, at
`main.cpp:91` and line 92. It uses images 0–127 with OMP/MKL thread limits of one.
GDB verifies the loaded ELF header and GNU build ID before installing exact
function-entry breakpoints. All process threads can hit those entries during
the window; this run observed hits on one thread.

The ten reached entries include convolution wrappers, batch normalization,
ReLU, pooling, linear, and flatten. Calls are nested, so 40 entry hits do not
represent 40 model layers. One convolution overload and in-place ReLU had no
hits. Three requested prefixes had no matching dynamic symbol; they remain
discovery gaps.

## Repeat the trace and recovery

Use the Ubuntu setup in [running-instructions.md](running-instructions.md).
The original working paths below identify private artifacts already present
in that VM:

```bash
cd "$HOME/Downloads/ml-memory-forensics"
export NATIVE_TRACE_BINARY="$HOME/Downloads/memory-evidence/submission-20261020-113652/build/cifar10_inference"

run_dir="$HOME/Downloads/memory-evidence/native-trace-$(date +%Y%m%d-%H%M%S)"
bash scripts/collect_native_trace.sh \
  "$HOME/Downloads/memory-evidence/native-recovery-20261020-125554/warm/memory.lime" \
  4540 "$run_dir"
```

The runner uses the existing CPU Python environment under
`~/Downloads/volatility/cifar10_cnn` and the experimental framework under
`~/Downloads/volatility3-aarch64-experimental`. Set `NATIVE_TRAINING_DIR` and
`NATIVE_FRAMEWORK_DIR` to override those locations.

Each stage saves its output. A successful run ends with
`OBSERVED_NATIVE_RECOVERY_PASS`. Inspect the reports:

```bash
tail -n 20 "$run_dir/gdb.log" "$run_dir/selection.log"
tail -n 30 "$run_dir/extraction.log" "$run_dir/validation.log"
```

| Output | Contents |
| --- | --- |
| `candidates.json` | Symbol sizes, ELF offsets, library identity, absent prefixes |
| `trace.json` | Live PID, batch bounds, event counts, threads, sample stacks |
| `observed-plan.json` | Reached candidates, bound to the trace and candidate hashes |
| `recovery/native-4540-report.json` | Saved-image addresses, recovered hashes, or read failures |
| `validation/validation.json` | Independent comparison with the reference library |
| `validation/native-*.asm.txt` | Disassembly of the recovered bodies |

The trace runs in its own process, which GDB ends afterward. Software
breakpoints do not modify the saved image used for extraction. A different
live PID or ASLR layout is expected: selection carries file offsets and build
identity into the captured process, rather than reusing live addresses.

## How addresses are translated

ELF symbol values are not always file offsets. The initial convolution had:

```text
Symbol value:                0x1322f50
Executable PT_LOAD vaddr:    0x12c0000
Executable PT_LOAD offset:   0xec0000
Function file offset:        0xf22f50
Captured executable VMA:     0xffffede10000
VMA file offset:             0xec0000
Captured function address:   0xffffede72f50
```

First compute `p_offset + st_value - p_vaddr`. Then translate that file offset
through the captured VMA. Assuming a zero ELF load base would select the wrong
bytes in this library.

The planner reads symbol locations, sizes, and identity metadata from the
reference ELF. The Volatility plugin reads code only from the captured process
layer, with `pad=False`. Missing pages, short reads, ambiguous mappings, and
non-executable ranges are rejected. Validation opens the reference library
separately and never uses it to fill recovery gaps.

## Capture after warm-up

For a new image, start a held process in terminal A:

```bash
cd "$HOME/Downloads/ml-memory-forensics"
warm_dir="$HOME/Downloads/memory-evidence/native-warm-$(date +%Y%m%d-%H%M%S)"
mkdir "$warm_dir"
export NATIVE_CAPTURE_READY="$warm_dir/ready.json"
export NATIVE_CAPTURE_RESUME="$warm_dir/resume"

OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 gdb -q -batch \
  -x scripts/hold_after_warmup.gdb --args \
  "$HOME/Downloads/memory-evidence/submission-20261020-113652/build/cifar10_inference" \
  "$HOME/Downloads/volatility/cifar10_cnn/outputs/cifar10_torchscript.pt" \
  "$HOME/Downloads/volatility/cifar10_cnn/data/cifar10_test.bin" \
  "$warm_dir/predictions.csv"
```

Wait for `WARMUP_CAPTURE_READY`. The script records the new PID and holds the
process before the second batch for up to ten minutes. In terminal B, use that
same `warm_dir`:

```bash
sudo insmod "$HOME/Downloads/LiME/src/lime-$(uname -r).ko" \
  "path=$warm_dir/memory.lime" format=lime
sudo python3 scripts/check_lime_ranges.py "$warm_dir/memory.lime" \
  --output "$warm_dir/capture.json"
```

Retain the acquisition output and exit status. If this invocation loaded LiME
and it remains loaded, unload it with `sudo rmmod lime`. Set the capture's owner
and permissions for the analysis account, then `touch "$warm_dir/resume"` to
end the held experiment. Use the new PID and capture path for extraction.

The preserved warm image is 4,289,855,648 bytes with SHA-256
`5dc577eda3b17f4d79697263810269ed41147aea72913409eacfb87c3f56121e`.
Its acquisition returned status zero and passed the stored-range framing check.

## Interpretation

The result establishes recovery of the ten selected function bodies, including
bytes that may not have executed. It is not executed-instruction coverage,
all-branch coverage, a complete native call graph, original C++ source, or a
reconstructed shared library. Internal/indirect callees, inline code, backend
libraries, and system/runtime calls need broader tracing.

A zero hit count means an entry was not observed in this window. An absent
export does not mean the model omitted an operation. Likewise, the original
image's page fault does not establish that the bytes were absent everywhere
in physical memory.

The Ubuntu validator compared the recovered binaries with the private library.
The transferred reports were checked separately for metadata/hash consistency.
The raw binaries, library, and RAM image remain outside Git. The 39-test local
run covers decoder, mapping, capture-format, and trace-selection integrity;
the live GDB and extraction results are recorded separately.
