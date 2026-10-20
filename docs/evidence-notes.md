# Evidence notes

Logs and JSON reports are kept under [evidence](../evidence/README.md).
Memory images, model binaries, extracted tensors, kernel files, and build
directories remain outside Git. [Artifact manifests](../manifests/artifacts.json)
record their known locations, sizes, and hashes.

## Environments and versions

| Stage | Recorded environment |
| --- | --- |
| Training | Argon, Python 3.10.8, PyTorch 2.14.1+cu126, torchvision 0.29.1+cu126 |
| Earlier container debugging | NVIDIA 24.10, PyTorch 2.5.0a0+e000cf0ad9.nv24.10 |
| Final capture and recovery | Ubuntu ARM64, kernel 7.0.0-38-generic, Python 3.14.4, PyTorch 2.14.1+cpu |
| Linux analysis | Experimental Volatility 3 ARM64 revision 5ee05ce7b440c0d6a0d45f7f9a343b702c7b38e4, with two plugin requirement fixes |

The experimental framework reports version `2.10.0`; this is a Volatility 3
framework version, not Volatility 2. The PyTorch ABI profile is based on the
Ubuntu build's reported revision `5c4886908584029761b579af026dcfb627c84070`.

The October 20, 2026 release check compared the training record with official
[PyTorch release metadata](https://github.com/pytorch/pytorch/releases/tag/v2.14.1)
and [PyPI metadata](https://pypi.org/pypi/torch/json). Version 2.14.1 was published
September 30 and was the latest stable release in the retrieved history as of
the October 17 training-artifact commit. The `+cu126` suffix identifies the CUDA
variant. Python 3.10.8 satisfies the Python >3.9 requirement.

The original training artifacts were added by
[`280a385`](https://github.com/hridoy100/volatility/commit/280a385a8722a449d013c70e2a20175575eb4809),
dated October 17, 2026 at 11:50:14 -05:00. That is a repository timestamp; exact
Argon job start/end times were not stored. The
[release comparison](../evidence/release-history/pytorch-release-check.json) and
[commit record](../evidence/release-history/training-commit.txt) preserve the
basis for the historical version check.

## Captures and process IDs

| Process | Role |
| --- | --- |
| PID 3183 | Original LiME image; model, tensor, source, and VMA recovery |
| PID 3220 | Later live native-convolution backtrace sample |
| PID 3391 | GDB helper verification |
| PID 4540 | Separate warm LiME image; native function-body recovery |
| PID 2782 | Later live entry trace used to select ten bodies from the warm image |

Addresses and PIDs identify particular runs. The native trace and warm capture
use separate processes; library build identity and file offsets connect them.

## Screenshots

The [image index](images/index.json) records captions and checksums. Images 1–3
show the original GDB, PID, and Volshell sessions. Images 4–11 were captured on
October 20: the official release page and browser reports displaying saved
training/export/build/extraction/validation/replay/native logs. Those report
views are new checks, not historical terminal screenshots. Image revisions and
their earlier hashes remain in the index.

The training report reads the preserved epoch-25 checkpoint and metrics; it does
not rerun training. The [reproduction summary](../evidence/submission-2026-10-20/summary.json)
records a fresh export, Debug build, C++ inference, extraction, validation, full
replay, and one native sample. The Python 3.14 TorchScript warnings remain in
the logs; the recorded runs completed.

## Repeat the checks

After restoring the private artifacts and environments in the
[running instructions](running-instructions.md):

```bash
bash scripts/collect_evidence.sh
python3 scripts/verify_evidence.py
```

The collector creates a timestamped directory under `~/Downloads/memory-evidence`.
For the separate native-code pipeline, use the
[native recovery instructions](native-code-recovery.md).

To make browser views of a reproduction's logs:

```bash
python3 scripts/build_evidence_pages.py \
  --logs /path/to/run --output-dir /tmp/experiment-reports
python3 -m http.server 8766 --bind 127.0.0.1 --directory /tmp/experiment-reports
```

Open `http://127.0.0.1:8766/`. Keep the report labels and raw logs with any
screenshots. `scripts/verify_evidence.py` checks file hashes and the consistency
of the recorded model and native results; it does not repeat extraction from RAM.
