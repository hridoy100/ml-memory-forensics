# Trace-guided native recovery — October 20, 2026

The user ran `scripts/collect_native_trace.sh` in Ubuntu ARM64 with GDB 17.1.
The small reports were transferred to the Mac and checked for plan/trace hashes,
function metadata, counts and matching memory/reference hashes. The reference
library, memory image and recovered binary bodies remain in Ubuntu; no new
byte comparison was performed on the Mac.

| Measurement | Result |
| --- | --- |
| Live trace PID / captured PID | 2782 / 4540 |
| Workload | First 128-image CPU evaluation forward, OMP/MKL thread limits 1 |
| Candidate entries / observed entries | 12 / 10 |
| Entry events / observed threads | 40 / 1 |
| Selected bodies recovered / matching | 10 / 10 |
| Selected function-body bytes | 23,340, all byte-identical in the Ubuntu validator |

The ten reached entries include six calls each to conv2d, convolution and its
selected internal wrapper; three calls each to batch_norm, its implementation
index wrapper and batch_norm_cpu; three pooling calls; seven ReLUs; two linear
calls; and one flatten. These are nested calls, not 40 independent model layers.
One other convolution overload and in-place ReLU had zero hits. Three requested
prefixes had no matching dynamic symbol. See `candidates.json`.

`local-tests.log` records 39 passing local checks, including 14 new trace tests.
`gdb.log` and `trace.json` establish the completed observation window.
`observed-plan.json` binds selection to the candidate plan and trace hashes.
`recovery/native-4540-report.json` records strict memory reads and library identity.
`validation/validation.json` and `validation.log` record the independent Ubuntu
byte comparison. `validation/*.asm.txt` disassemble the recovered bodies.
`summary.json` records measured counts and the private report archive hash.

The [walkthrough](../../docs/NATIVE_TRACE.md) defines scope and commands.
These are complete selected function bodies, including bytes that may not have
executed. This is not a complete native call graph, all-instruction coverage,
original C++ source recovery or a reconstructed executable library. The earlier
warm image is reused unchanged; its acquisition evidence and hash are in
[the first native experiment](../native-recovery-2026-10-20/README.md).
