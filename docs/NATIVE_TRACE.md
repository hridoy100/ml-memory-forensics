# Trace-guided native recovery

This second experiment is on `codex/native-code-recovery`. The earlier
[584-byte convolution recovery](NATIVE_RECOVERY.md) is followed here by a live
trace and recovery of ten selected native function bodies. The Ubuntu runner
completed successfully; the small reports were transferred to the Mac and
checked for consistency. Raw memory, reference libraries and recovered binaries
remain in Ubuntu.

## Measured result

| Measurement | Result |
| --- | --- |
| Live trace PID / saved-image PID | 2782 / 4540 |
| Candidate symbols / reached candidates | 12 / 10 |
| Entry events / observed threads | 40 / 1 |
| Recovered and independently matching selected bodies | 10 / 10 |
| Recovered selected body bytes | 23,340 |

The reached entries cover conv2d/convolution wrappers, batch normalization,
ReLU, max pooling, linear and flatten. They include nested calls; the 40 hits
are not 40 model layers. One convolution overload and in-place ReLU had no hits.
Three requested dynamic-symbol prefixes were absent and remain discovery gaps.
All ten sample stacks unwound without reported errors or hitting the 32-frame
limit; this does not establish a complete native call graph.

Evidence and exact reports are in
[native-trace-2026-10-20](../evidence/native-trace-2026-10-20/README.md).

## Workload and boundary

Trace the first CPU evaluation forward call over images 0–127, with
`OMP_NUM_THREADS=1` and `MKL_NUM_THREADS=1`. The Debug executable stops at
`main.cpp:91`, immediately before `model.forward`, and at line 92 after it
returns. The script verifies the local batch bounds and the main thread.

The candidate set is a small, explicit group of `at::native` dynamic-symbol
prefixes associated with this CNN: convolution, batch normalization, ReLU,
max pooling, linear/addmm and flatten. `--profile model-forward` records absent
prefixes as `unmatched_prefixes`. They remain discovery gaps; an absent export
does not mean the model omitted an operation. The planner's default remains
the original single convolution function.

GDB installs exact entry breakpoints after checking the loaded ELF header and
GNU build ID. All process threads can hit the candidate breakpoints during the
window. The report records each event's thread/PTID and a representative stack
for each reached candidate. A worker's temporal overlap does not by itself prove
causality to the forward call. Stack unwinding can also be partial.

This is **selected-entry observation**, not an instruction trace or a complete
call graph. Internal/non-exported callees, inlined functions, backend libraries,
runtime/system calls and paths through other inputs are outside the measured
denominator. A zero hit count does not prove a function can never execute.

The GDB Python callback records data without changing inferior execution state
or breakpoints, following the [GDB breakpoint API](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Breakpoints-In-Python.html).
The script is loaded using GDB's [Python source command](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Python-Commands.html).

## Run in Ubuntu

Use the existing Ubuntu ARM64 VM and experimental Volatility framework. No
retraining, kernel change or new LiME capture is needed for this first attempt.
The saved warm image already contains PID 4540 after the same first batch. The
trace uses a new process; ASLR addresses and PID will differ. Selection transfers
file offsets and build identity, not live virtual addresses, to the saved image.

Update the existing research checkout without disturbing local edits:

```bash
cd "$HOME/Downloads/ml-memory-forensics"
git status --short --branch
git switch codex/native-code-recovery
git pull --ff-only origin codex/native-code-recovery
```

If GitHub authentication is unavailable in Ubuntu, the Mac checkout is available
under `/mnt/software/ml-memory-forensics` when the existing shared mount is
active. If it is unmounted, first run `sudo mount -t 9p -o trans=virtio,version=9p2000.L,rw share /mnt/software`. Root can copy just the tools into the guest checkout:

```bash
project_dir="$HOME/Downloads/ml-memory-forensics"
sudo cp /mnt/software/ml-memory-forensics/scripts/{plan_native_recovery.py,native_trace_support.py,trace_native_forward.py,select_traced_functions.py,collect_native_trace.sh} \
  "$project_dir/scripts/"
```

Then run as your ordinary Ubuntu account:

```bash
cd "$HOME/Downloads/ml-memory-forensics"
export NATIVE_TRACE_BINARY="$HOME/Downloads/memory-evidence/submission-20261020-113652/build/cifar10_inference"

run_dir="$HOME/Downloads/memory-evidence/native-trace-$(date +%Y%m%d-%H%M%S)"
bash scripts/collect_native_trace.sh \
  "$HOME/Downloads/memory-evidence/native-recovery-20261020-125554/warm/memory.lime" \
  4540 "$run_dir"
```

`NATIVE_TRAINING_DIR` and `NATIVE_FRAMEWORK_DIR` can override the runner's existing
`$HOME/Downloads/volatility/cifar10_cnn` and
`$HOME/Downloads/volatility3-aarch64-experimental` paths. The framework still
needs the matching kernel symbols and experimental AArch64 fixes described in
[REPRODUCE.md](REPRODUCE.md).

The runner creates a new output directory, retains each stage's stdout/stderr,
and stops on failure. It starts and ends its own GDB inferior. Do not source the
tracer inside a session holding another process. Software breakpoint bytes are
confined to this separate tracing process; the preserved LiME image is unchanged.

## Inspect the result

```bash
tail -n 20 "$run_dir/plan.log" "$run_dir/gdb.log" "$run_dir/selection.log"
tail -n 30 "$run_dir/extraction.log" "$run_dir/validation.log"
```

| File | What to inspect |
| --- | --- |
| `candidates.json` | Candidate symbols, sizes, ELF offsets, library identity, absent prefixes |
| `trace.json` | New PID, batch bounds, hit counts/events, threads and sample stacks |
| `observed-plan.json` | Only entries observed in a completed trace; hashes bind it to the trace and candidates |
| `recovery/native-4540-report.json` | Each selected body's saved-image address, bytes/hash or strict-read failure |
| `validation/validation.json` | Independent byte comparison against the matching library |
| `validation/native-*.asm.txt` | Disassembly of each recovered body |

Expected stage markers are `NATIVE_TRACE_PASS`, `OBSERVED_NATIVE_PLAN_PASS`,
`NATIVE_CODE_VALIDATION_PASS`, then `OBSERVED_NATIVE_RECOVERY_PASS`. A marker
is only a stage result; inspect the JSON reports before making a coverage claim.
If extraction leaves unreadable pages, validation must fail and retain that
gap. Do not substitute disk code for missing memory bytes. A further warm capture
can be considered after reviewing which ranges failed.

Report the candidate count, reached candidate count, total entry events, recovered
selected bodies/bytes, and independently matching bodies/bytes separately.
For example, recovering every reached candidate would mean 100% of **those
selected bodies**, not 100% of native code executed by forward. Symbol sizes can
also include padding and cold blocks, so recovered body bytes are not executed
instruction bytes. Symbol aliases at one entry are rejected rather than double
counted.

For later runs, only add the small JSON reports, logs and disassembly to
repository evidence after checking the live results. The `.lime`, reference `.so`, model `.pt` and recovered `.bin`
artifacts remain private and ignored. Hash the reports in
`manifests/evidence-files.json` once reviewed. Take screenshots of the PID/trace
summary and extraction/validation result for the write-up.

## Verification

The local run passed 39 tests covering native mapping/read integrity, trace
selection, LiME/ELF framing and model decoding. Fourteen of these are new trace
helper tests. They include ASLR rebasing, ambiguous library mappings/aliases,
partial runs, event-limit failures, missing identity checks and truncated event
lists. Python parsing and shell syntax checks also pass. The GDB callback and
full pipeline also completed in Ubuntu. The Mac check
verifies consistency of the transferred reports and recorded hashes; byte
comparison against the private library was performed by the Ubuntu validator.

The next research step is a broader callee inventory and an appropriate tracing mechanism for internal/indirect
calls. No exhaustive native coverage or original C++ source reconstruction is
claimed by this experiment.
