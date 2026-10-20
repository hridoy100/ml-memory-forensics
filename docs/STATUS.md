# Current status

## Completed and evidenced

- Custom CIFAR-10 CNN, recorded 80/10/10 split, checkpoint and training metrics.
- TorchScript export and C++ CPU inference with full application debug types.
- GDB PID/object inspection, LiME capture, PID/VMA analysis, and Volshell checks.
- Recovery of 31 tensors, 26 modules, 19 archived source files, and 34 function graphs.
- Recovered-source inference with identical outputs on all 6,000 test images.
- All 15 decoder/replay tests and the original consolidation checks passed.
- October 20 reproduction: fresh export, Debug build, C++ inference, extraction,
  validation, and full replay passed. A live native convolution sample also passed.
- Three original screenshots plus eight new browser screenshots are preserved.
  New report views are labeled accurately; they do not recreate historical terminals.
- Official release metadata confirms that recorded PyTorch 2.14.1 matches the
  latest stable release as of the October 17 training-artifact commit. See
  [version verification](VERSION_VERIFICATION.md) for the timestamp limitation.

## Remaining scope clarification

The instructor has not clarified whether the model-code requirement extends to
every native library/kernel call. The recovered TorchScript implementation and
one live native sample are evidenced; exhaustive native coverage and native
code extraction from the original image are not claimed. Use the ready-to-send
[scope question](CODE_SCOPE.md#clarification-to-send-to-the-instructor).

If historical training-terminal screenshots or exact start/end times are
required, obtain the original Argon job stdout and scheduler record. The current
training screenshot checks the saved checkpoint and metrics; it is labeled as
a new check. The Git commit is a dated artifact record, not a scheduler timestamp.

The raw imported `analysis-summary.json` describes an earlier working state.
Original reports/logs are preserved. The [submission evidence supplement](SUBMISSION_EVIDENCE.md)
records the October 20 reproduction and the scope of each new screenshot.
