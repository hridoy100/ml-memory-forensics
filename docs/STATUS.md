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

## Still needed for the final assignment submission

- Add training/export/build and extraction/validation/replay screenshots. Three
  original GDB/PID/Volshell screenshots are already preserved.
- Independently verify the historical "most recent PyTorch" requirement against
  the date of the experiment; keep observed package versions distinct from that claim.
- Complete the requested textbook reading personally. The repository does not
  certify that reading or reproduction of the reference papers' full systems.
- Establish any instructor-required native machine-code/call coverage beyond
  the recovered TorchScript implementation. Current limits are explicit in
  [FINDINGS.md](FINDINGS.md).

The raw imported `analysis-summary.json` describes an earlier working state.
This status file and the walkthrough reflect repository consolidation on
October 20, 2026. Original reports/logs are preserved rather than edited to
rewrite their history.
