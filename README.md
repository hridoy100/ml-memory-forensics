# ML memory forensics

Recovering a trained neural network from a Linux memory image: its weights,
layer hierarchy, generated model code, and selected native functions.

The target is a custom CIFAR-10 CNN trained on Argon, exported to TorchScript,
and loaded by a C++ inference program. GDB identifies the live objects. LiME
captures RAM, and two Volatility 3 plugins recover the model and native code.
Separate checks compare the recovered artifacts with the original model.

Read the [project blog](https://hridoy100.github.io/ml-memory-forensics/) for the
illustrated walkthrough, results, and reproduction links.

## Results

| Check | Result |
| --- | --- |
| Dataset split | 48,000 training / 6,000 validation / 6,000 test images |
| Test accuracy after 25 epochs | 5,225/6,000 (87.0833%) |
| Model recovery | 26 modules, 31 tensors, 19 generated source files, 34 function graphs |
| State and source comparison | All recovered tensors and source files match byte for byte |
| Recovered-model inference | 6,000/6,000 predictions agree; maximum logit difference 0 |
| Native-code recovery | 10 selected function bodies, 23,340 bytes, all matching the reference library |

Prediction agreement measures whether reconstruction preserved the model's
behavior. It does not mean the classifier achieved 100% accuracy.

## Documentation

- [Project walkthrough](docs/project-walkthrough.md) — the experiment, step by step, with screenshots.
- [Running instructions](docs/running-instructions.md) — setup, extraction, validation, and inference.
- [GDB instructions](docs/gdb-instructions.md) — inspect objects, tensor storage, and layer metadata.
- [Native-code recovery](docs/native-code-recovery.md) — warm capture, entry tracing, and machine-code extraction.
- [Findings](docs/findings.md) — results, interpretation, and limits.
- [Argon instructions](docs/argon-instructions.md) — the training and Apptainer environment.
- [Evidence notes](docs/evidence-notes.md) — versions, screenshots, and reproduction records.
- [Background](docs/background.md) — the memory-forensics concepts used here.

## Repository layout

```text
cifar10_cnn/          Training, export, test preparation, C++ inference, GDB helpers
forensics/           Volatility plugins, ABI profile, validators, replay tools
scripts/             Environment setup, evidence checks, native tracing
tests/               Decoder, replay, and native-recovery tests
evidence/            Metrics, logs, reports, recovered source, disassembly
docs/images/         Screenshots and checksum index
manifests/           Artifact hashes, locations, and source provenance
patches/             ARM64 compatibility changes for the framework
```

Check the tracked evidence with standard Python:

```bash
python3 scripts/verify_evidence.py
```

Model binaries, datasets, memory images, kernel symbols, and generated build
files are excluded from Git. Their recorded locations and hashes are in
[artifacts.json](manifests/artifacts.json). Restore them before running extraction.

## Scope

The model extractor starts from a known PID and Object address and uses a
build-specific PyTorch ABI profile. The demonstrated tensors are contiguous CPU
allocations. Replay uses recovered TorchScript source through a Python
compatibility layer. Native recovery covers selected observed function bodies;
it does not establish a complete native call graph or recover original C++ source.

The final capture used Ubuntu ARM64, kernel `7.0.0-38-generic`, and PyTorch
`2.14.1+cpu`. The experimental Volatility 3 ARM64 framework is pinned in the
[running instructions](docs/running-instructions.md).

[Source provenance](manifests/source-repositories.json) records the original
repositories and imported files. See [NOTICE.md](NOTICE.md) for software credits
and licenses.

## Project page

The blog source is in `site/`. GitHub Actions publishes that directory and the
screenshots in `docs/images/` to GitHub Pages on pushes to `main`. The deployment
contains only the blog and images; model files and RAM images remain excluded.

To preview locally, stage the same files in a temporary directory:

```bash
preview_dir="$(mktemp -d)"
cp -R site/. "$preview_dir/"
mkdir "$preview_dir/images"
cp docs/images/*.png docs/images/*.jpg "$preview_dir/images/"
python3 -m http.server 8768 --bind 127.0.0.1 --directory "$preview_dir"
```
