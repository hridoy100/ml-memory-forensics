# Native recovery evidence

The original image had an unreadable code range. A separate capture after one
completed inference batch allowed that function to be recovered.

| File | Meaning |
| --- | --- |
| [plan.json](plan.json) | Symbol/segment/build-ID plan; no function code bytes |
| [original-recheck/native-3183-report.json](original-recheck/native-3183-report.json) | Identity checks pass; selected code raises a page fault in the original image |
| [warm/ready.json](warm/ready.json) | New PID 4540 and the 128-image warm-up boundary |
| [warm/gdb.log](warm/gdb.log) | Held process, breakpoint, recorded pointers, and termination after capture |
| [warm/acquisition.log](warm/acquisition.log) | LiME exit status 0 and range-check output |
| [warm/capture.json](warm/capture.json) | New image location, range framing, byte count, SHA-256 |
| [warm/recovery/native-4540-report.json](warm/recovery/native-4540-report.json) | Captured library identity, VMAs, complete selected function and its checksum |
| [warm/validation/validation.json](warm/validation/validation.json) | All 584 recovered function bytes match the reference |
| [warm/validation/native-000.asm.txt](warm/validation/native-000.asm.txt) | ARM64 disassembly of the memory-extracted function |
| [tests.log](tests.log) | Initial ten native mapping/read tests |
| [native-tests-final.log](native-tests-final.log) | All fifteen native and capture-format tests passed |
| [model-tests-final.log](model-tests-final.log) | Ten existing model-decoder tests passed |
| [replay-tests-final.log](replay-tests-final.log) | Five existing replay integrity tests passed |
| [artifacts.json](artifacts.json) | Raw image and native binary locations/checksums; those files stay local |

No zero padding or file-backed fallback supplies code bytes. Symbols and identity
metadata come from the reference library; validation opens that library later.
Only the selected function was recovered. Exhaustive native call/branch coverage
and original native source are not established. See the
[experiment guide](../../docs/native-code-recovery.md).
