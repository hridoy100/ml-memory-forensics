# Native-code recovery experiment

This work is isolated on `codex/native-code-recovery`. The completed model-level
experiment remains on `main`. The first native milestone is recovery of one
complete ELF-symbol-bounded function from a LiME image, with a separate byte-level
comparison and ARM64 disassembly. Exhaustive native coverage is not claimed.

## Measured result

| Check | Result |
| --- | --- |
| Selected function | `at::native::convolution(...)` in `libtorch_cpu.so` |
| Function size from ELF symbols | 584 bytes (`0x248`) |
| Original capture, PID 3183 | ELF/build ID match; selected code range raises `PagedInvalidAddressException` |
| New capture after one completed batch | PID 4540, stopped before the second forward call |
| New image acquisition | LiME exit status 0; stored range framing valid |
| Recovery from the new image | All 584 selected function bytes recovered |
| Reference comparison | Byte-identical; SHA-256 `32eed4e332633b1cd18abe29ad2cee997e1baa81f8c123b39fc42f8fad85f740` |

The original capture's unreadable range is a result, not silently repaired data.
It is consistent with the pre-forward capture not having that native code range
resident. It does not establish the cause of every missing page or invalidate
the earlier model-state recovery. A process-page-table fault also does not prove
the bytes are absent everywhere in physical memory. The new capture is a
separate experiment.

Evidence is in [native-recovery-2026-10-20](../evidence/native-recovery-2026-10-20/README.md).
The new 4,289,855,648-byte image stays in private local storage; its SHA-256 is
`5dc577eda3b17f4d79697263810269ed41147aea72913409eacfb87c3f56121e`.

## What the new tools do

- `scripts/plan_native_recovery.py` reads ELF program headers, GNU build ID, and
  dynamic symbols from the matching on-disk library. It supplies locations and
  lengths, not the function's code bytes.
- `forensics/plugins/mlnative.py` locates the captured process and library VMAs,
  checks the captured ELF header/build ID, translates file offsets to process
  addresses, and reads code exclusively from the captured process layer.
- `scripts/validate_native_recovery.py` independently compares the recovered
  bytes with the separately supplied reference library, then runs ARM64 objdump
  on the recovered binary. It does not replace missing bytes with reference data.
- `scripts/hold_after_warmup.gdb` executes one 128-image batch, records the new
  PID and object pointers, and holds the process for acquisition.
- `scripts/check_lime_ranges.py` checks every stored range's framing/payload
  length and hashes the entire image. Valid framing is not proof that all RAM
  was acquired or that acquisition was atomic.

The native plugin uses `pad=False`. Missing pages, short reads, ambiguous mappings,
and ranges outside executable mappings are rejected. The initial test run has
ten native mapping/read tests; five additional ELF/capture-format tests cover
truncation, overlapping physical ranges, endianness, and build-ID offsets.

## Why ELF symbols cannot be used as file offsets

This library has a nonzero load address. For the selected function:

```text
ELF symbol value:            0x1322f50
Executable PT_LOAD vaddr:   0x12c0000
Executable PT_LOAD offset:   0xec0000
Function file offset:        0xf22f50
Captured executable VMA:     0xffffede10000
VMA file offset:             0xec0000
Function process address:    0xffffede72f50
```

First compute `p_offset + st_value - p_vaddr`, then translate that file offset
through the captured VMA. Assuming a zero ELF virtual base would select the
wrong bytes here. Addresses are recomputed for each captured process.

## Repeat recovery on the preserved images

Use the working Ubuntu environment from [REPRODUCE.md](REPRODUCE.md):

```bash
cd "$HOME/Downloads/ml-memory-forensics"
project_dir="$PWD"
framework_dir="$HOME/Downloads/volatility3-aarch64-experimental"
run_dir="$HOME/Downloads/memory-evidence/native-recovery-20261020-125554"
library="$HOME/Downloads/volatility/cifar10_cnn/.venv/lib/python3.14/site-packages/torch/lib/libtorch_cpu.so"

python3 scripts/plan_native_recovery.py \
  --library "$library" --output /tmp/native-plan-new.json

mkdir "$run_dir/warm/recovery-new"
"$framework_dir/.venv/bin/python" "$framework_dir/vol.py" -q \
  -p "$project_dir/forensics/plugins" \
  -f "$run_dir/warm/memory.lime" -o "$run_dir/warm/recovery-new" \
  mlnative.NativeCode --pid 4540 --plan /tmp/native-plan-new.json

python3 scripts/validate_native_recovery.py \
  --report "$run_dir/warm/recovery-new/native-4540-report.json" \
  --library "$library" --output-dir "$run_dir/warm/validation-new"
```

Choose new output paths on subsequent runs. The plan defaults to the selected
convolution function. `--prefix` can be repeated to select other demangled symbol
prefixes; selection does not prove those functions execute during forward.

To repeat the cold-image check, use the original `ubuntu.lime`, PID 3183, and a
different output directory. The recorded result is incomplete, with no code
binary emitted. The validator must fail rather than manufacture a match.

## Make a new capture after warm-up

The existing Debug inference executable is at
`$HOME/Downloads/memory-evidence/submission-20261020-113652/build/cifar10_inference`.
It can be rebuilt from the repository's CMake project if restoring elsewhere.
In terminal A, create a new evidence directory and start the held process:

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

Wait for `WARMUP_CAPTURE_READY`; read the new PID from `ready.json`. The script
waits at most ten minutes. In terminal B, set `warm_dir` to that exact new
directory, then acquire with the existing module built for the running kernel:

```bash
sudo insmod "$HOME/Downloads/LiME/src/lime-$(uname -r).ko" \
  "path=$warm_dir/memory.lime" format=lime

sudo python3 scripts/check_lime_ranges.py "$warm_dir/memory.lime" \
  --output "$warm_dir/capture.json"
```

Retain acquisition stdout/stderr and its exit status. If this invocation loaded
LiME successfully and it remains loaded, unload that instance with `sudo rmmod lime`. Set the new image's owner/read permissions appropriately for your analysis
account, then `touch "$warm_dir/resume"` to release the held experiment. The GDB
script ends its own inferior after capture. Never overwrite the original image.

Run extraction using the new image and the PID from `ready.json`. The matching
kernel ISF is still required. New raw images and extracted `.bin` files remain
excluded from Git.

## What remains before any exhaustive claim

1. Define a finite workload and boundary: evaluation batch size/input set,
   participating threads, and whether scope includes only ATen, backend libraries,
   or runtime/system calls too.
2. Inventory the operators and native callees actually reached in that workload.
   A symbol list is not a call trace; inline functions and indirect calls need
   additional treatment.
3. Recover the necessary executable ranges and dependencies, with explicit
   missing-page/byte coverage reports. Preserve unmapped/swapped cases as gaps.
4. Connect executed addresses to ELF symbols and library build IDs, and validate
   recovered bytes independently. Keep inferred disk reconstruction separate
   from memory-extracted evidence.
5. Report observed-path coverage separately from all-branch coverage. Recovering
   584 bytes of this function does not recover its callees, the full convolution
   backend, original C++ source, or every possible execution path.

The disassembly tool labels a raw binary's synthetic section `.data`; the
captured `r-x` VMA and ELF PT_LOAD metadata establish its code provenance. This
is not a newly reconstructed shared library or a self-contained native model.
