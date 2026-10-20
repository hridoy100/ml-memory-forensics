# Current status

## Completed and evidenced

- Custom CIFAR-10 CNN, recorded 80/10/10 split, trained checkpoint and metrics.
- TorchScript export and C++ CPU inference with full application debug types.
- GDB PID/object inspection and a LiME-format image containing the target pages.
- PID/VMA analysis and Volshell verification of recorded model/input addresses.
- Build-specific model extractor, byte-level validation, and generated source recovery.
- Recovered-source inference with identical outputs on all 6,000 test images.
- Combined walkthrough, findings, interview notes, artifact manifest, and preserved evidence.
- Consolidated repository checks: all 15 tests pass, fresh extraction/validation and
  128-image replay pass, and the updated GDB helper reads the expected weights.
  See the [verification logs](../evidence/README.md#consolidated-repository-checks).

The raw imported `analysis-summary.json` describes an earlier working state.
This status file and the walkthrough reflect repository consolidation on
October 20, 2026. Original reports/logs are preserved rather than edited to
rewrite their history.
