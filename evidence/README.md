# Evidence inventory

These files record training, capture, recovery, and validation. Logs retain the
original paths, addresses, and versions.

| Location | What it establishes |
| --- | --- |
| [training/metrics.json](training/metrics.json) | Recorded training versions, split sizes, epoch, loss, and test accuracy |
| [training/test-indices.json](training/test-indices.json) | Original pooled-dataset indices used for the held-out test binary |
| [capture/pslist-3183.tsv](capture/pslist-3183.tsv) | PID 3183 and process identity in the memory image |
| [capture/maps-3183.tsv](capture/maps-3183.tsv) | 128 process VMAs, permissions, and paths |
| [capture/volshell-address-check.log](capture/volshell-address-check.log) | Recorded model/input pointers and input dimensions match |
| [recovery/pytorch-3183-model.json](recovery/pytorch-3183-model.json) | Recovered hierarchy, settings, tensor metadata, functions, source provenance |
| [recovery/validation.json](recovery/validation.json) | 31 tensors and 19 source files match the reference; module names/types/order match |
| [replay/code-coverage.json](replay/code-coverage.json) | 34 recovered definitions and layer-to-source mapping |
| [replay/inference-comparison.json](replay/inference-comparison.json) | Full 6,000-image comparison, first-batch call trace, and output differences |
| [replay/predictions.csv](replay/predictions.csv) | Per-image labels, predictions, and agreement |
| [logs/replay-confirmation-6000.log](logs/replay-confirmation-6000.log) | Console confirmation of the successful full replay |
| [screenshots](../docs/images/index.json) | Three original screenshots and eight browser captures, with captions and SHA-256 checksums |

The 19 `recovery/pytorch-3183-source-*.py` files are recovered generated
TorchScript source. File `017` contains the custom `CIFAR10CNN.forward` code.
They are preserved as evidence; run the controlled confirmation helper rather
than treating them as standalone original training files.

The archived model report refers to `.npy` files produced by extraction. Those
binary tensors are intentionally excluded here and listed in the external
[artifact manifest](../manifests/artifacts.json). Restore the private backup or
run extraction against the original image before validating those tensors again.

The optional [GDB core inspection log](logs/gdb-core-inspection.log) records a
missing heap page. That attempt failed. Successful address and recovery results
came from the original LiME image, not the incomplete core inspection.

## Repository checks

[The final repository check](logs/repository-check-final.log) passed all 10
decoder tests and 5 replay tests, extracted the model using the external
`mlmodel.PytorchModel` plugin, matched all recovered tensors and sources, and
replayed a fresh 128-image batch with identical logits. The earlier
[initial check](logs/repository-check-initial.log) records the plugin-name
collision that was fixed by giving the external module its own name.

[The GDB helper check](logs/repository-gdb-helper-check.log) confirms that the
helper follows the Ubuntu build's object/type layout and reads the
known first eight weight values. Its PID **3391** belongs to a new live test;
the memory capture and recovery evidence still refer to PID **3183**.

## October 20 reproduction

[New reproduction evidence](submission-2026-10-20/summary.json) verifies export,
Debug build, inference, recovery, validation, and full replay. Logs and small
reports are preserved in that directory. The final native sample is live PID
3220; the original capture remains PID 3183. Initial wrapper/PLT attempts are
retained with explicit filenames. [Release metadata](release-history/pytorch-release-check.json)
and [training commit dates](release-history/training-commit.txt) support the
historical version comparison. See the [evidence notes](../docs/evidence-notes.md).

## Native-code recovery

The [warm-capture experiment](native-recovery-2026-10-20/README.md) recovered
584 bytes of the convolution implementation after the original image returned
a page fault. The [trace-guided run](native-trace-2026-10-20/README.md) recorded
40 entry hits across ten candidate functions and recovered all ten bodies:
23,340 bytes, matching the reference library. These reports cover selected
native functions, not exhaustive native execution.
