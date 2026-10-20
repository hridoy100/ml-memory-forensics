# ML memory forensics

This project recovers a custom CIFAR-10 model from a Linux memory image, then
checks that the recovered implementation produces the same outputs as the
original. It brings together the training code, C++ inference program, GDB
inspection, Volatility recovery plugin, evidence, and reproduction instructions.

## Recorded results

| Check | Result |
| --- | --- |
| Dataset split | 48,000 training / 6,000 validation / 6,000 testing |
| Training | 25 epochs; 87.0833% held-out accuracy |
| Captured process | PID 3183, `cifar10_inferen`; 128 VMAs |
| Recovered modules | 26, with matching names, types, and registration order |
| Recovered tensors | 31 parameters/buffers; all byte-identical to the reference |
| Recovered source | All 19 archived TorchScript `.py` files; byte-identical |
| Recovered function graphs | 34 |
| Recovered-code replay | 6,000/6,000 predictions agree with the original |
| Largest output-logit difference | 0 |

Prediction agreement is not ground-truth accuracy. Both implementations made
the same 5,225 correct predictions out of 6,000 images.

## Start here

- [Step-by-step walkthrough](docs/WALKTHROUGH.md): assignment steps 1–8, commands,
  explanations, existing screenshots, and measured results.
- [Reproduce recovery and inference](docs/REPRODUCE.md): use the existing Ubuntu
  setup or prepare the pinned experimental framework.
- [Findings and scope](docs/FINDINGS.md): what the evidence establishes and the
  limits of this implementation.
- [Interview notes](docs/INTERVIEW.md): explain the goal, methods, and results.
- [Current status](docs/STATUS.md): completed evidence and remaining submission checks.
- [Evidence inventory](evidence/README.md): which reports to inspect.
- [Artifacts kept outside Git](manifests/artifacts.json): hashes, sizes, and known
  locations of captures, kernel files, and model/data binaries.

```text
cifar10_cnn/          Custom CNN, export, test-image preparation, C++ and GDB
forensics/plugins/   Volatility model recovery plugin
forensics/profiles/  Measured PyTorch C++ ABI profile
forensics/           Layout exporter, validator, recovered-source replay
patches/             Two ARM64 plugin requirement fixes
tests/               Decoder and replay integrity tests
evidence/            Recorded metrics, reports, logs, recovered source, predictions
docs/images/         Original screenshots and their checksum index
manifests/           Artifact locations and source/evidence provenance
```

## Verify the tracked evidence

This check needs only standard Python, not the memory image or PyTorch:

```bash
python3 scripts/verify_evidence.py
```

To check selected excluded files at their original local locations:

```bash
python3 scripts/verify_artifacts.py --known-locations \
  --only reference-torchscript test-images
```

For the full experiment, follow [REPRODUCE.md](docs/REPRODUCE.md). The original
LiME image and generated tensor files stay in private local storage. Tracked
reports are evidence snapshots; a fresh extraction writes to an ignored output
directory.

## Environment and provenance

Training ran on Argon with Python 3.10.8 and the recorded PyTorch
`2.14.1+cu126` environment. The memory experiment used Ubuntu ARM64, kernel
`7.0.0-38-generic`, and the recorded PyTorch `2.14.1+cpu` build. The framework
is an experimental ARM64 Volatility **3** branch reporting framework version
`2.10.0`, pinned to `5ee05ce7b440c0d6a0d45f7f9a343b702c7b38e4`.

The earlier source repositories remain available:

- [CNN/C++ project in the Volatility 2 fork](https://github.com/hridoy100/volatility/tree/800a2100d3e04dba7931512aeeb1746cd01cc582/cifar10_cnn)
- [ARM64 framework fork](https://github.com/hridoy100/volatility3-arm64/tree/codex/arm64-process-inspection)
- [Experimental ARM64 framework upstream](https://github.com/Abyss-W4tcher/volatility3/tree/aarch64-support)

This repository is the combined project record. It loads the extractor as an
external Volatility plugin and does not vendor the complete framework or the
older repository's generated build trees.

## Scope and remaining submission work

Recovery is guided by a PID and root Object address recorded with GDB. It uses a
build-specific ABI profile and supports the CPU, contiguous tensors in this
experiment. Recovered source is TorchScript's generated model implementation;
native C++ kernel source, GPU VRAM, and automatic discovery of unknown models
are outside this implementation.

The replay checks the evaluation path on this test set. It does not establish
all-branch or native call coverage. See [FINDINGS.md](docs/FINDINGS.md).

Three original screenshots are preserved. Additional training/build and
recovery/replay screenshots remain to be collected for the final submission.
Package versions are recorded as observed; the historical "most recent PyTorch"
requirement needs its own release-date verification. Textbook reading is a
separate prerequisite and is not certified by these artifacts.

See [NOTICE.md](NOTICE.md) for third-party software and recovered-source notices.
