# Running instructions

Use Linux for capture and analysis. The recorded target is Ubuntu ARM64 with
PyTorch 2.14.1+cpu. Restore the private artifacts listed in
[artifacts.json](../manifests/artifacts.json); a Git clone contains code and small
reports, not the model, test binary, RAM images, or kernel symbols.

## Train, export, and build

Use Python 3.10 or newer with the pinned torch/torchvision versions in
`cifar10_cnn/requirements.txt`, plus Pillow. A fresh CPU environment can be
prepared from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --index-url https://download.pytorch.org/whl/cpu \
  -r cifar10_cnn/requirements.txt
python -m pip install Pillow
```

For Argon GPU training, use the [Argon setup](argon-instructions.md). Then, from
`cifar10_cnn`:

```bash
python -u train.py --epochs 25 --output-dir outputs
python export_model.py --checkpoint outputs/best_model.pt \
  --output outputs/cifar10_torchscript.pt
python prepare_test_images.py --checkpoint outputs/best_model.pt

cmake -S cpp -B cpp/build-ubuntu -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_PREFIX_PATH="$(python -c 'import torch; print(torch.utils.cmake_prefix_path)')"
cmake --build cpp/build-ubuntu --parallel 1
./cpp/build-ubuntu/cifar10_inference \
  outputs/cifar10_torchscript.pt data/cifar10_test.bin outputs/cpp_predictions.csv
```

This needs CMake, a C++20 compiler, and GDB for inspection. The checkpoint,
TorchScript archive, and test binary belong under `cifar10_cnn/outputs/` and
`cifar10_cnn/data/` as shown. A `.pt` state dictionary is not an executable
TorchScript archive.

For live inspection and a new capture, follow the
[GDB guide](gdb-instructions.md) and [walkthrough](project-walkthrough.md).
The commands below analyze the preserved capture in the existing VM.

## 1. Set analysis paths

These paths match the existing VM, including the CPU environment and reference
files in the earlier checkout. On a fresh setup, point `cifar_python` to the new
venv and `reference`/`test_images` to the restored files:

```bash
cd "$HOME/Downloads/ml-memory-forensics"
project_dir="$PWD"
framework_dir="$HOME/Downloads/volatility3-aarch64-experimental"
evidence_dir="$HOME/Downloads/memory-evidence"
cifar_python="$HOME/Downloads/volatility/cifar10_cnn/.venv/bin/python"
reference="$HOME/Downloads/volatility/cifar10_cnn/outputs/cifar10_torchscript.pt"
test_images="$HOME/Downloads/volatility/cifar10_cnn/data/cifar10_test.bin"
```

On a different machine, change these paths and restore the artifacts listed in
[artifacts.json](../manifests/artifacts.json). Do not expect the supplied PID and
addresses to match a newly launched process: they identify the original capture.

## 2. Prepare a framework if needed

Skip the clone when using the existing working checkout. For a separate fresh
checkout:

```bash
git clone --branch aarch64-support \
  https://github.com/Abyss-W4tcher/volatility3.git "$framework_dir"
git -C "$framework_dir" checkout 5ee05ce7b440c0d6a0d45f7f9a343b702c7b38e4
python3 -m venv "$framework_dir/.venv"
"$framework_dir/.venv/bin/python" -m pip install -e "$framework_dir"
```

Apply the two architecture requirement fixes from the project root:

```bash
python3 scripts/prepare_framework.py "$framework_dir"
```

This checks the framework base commit, applies only the supplied patch, and
recognizes an already-applied patch. It does not replace other framework files.
The patch enables existing ARM64 translation support for PsList and Maps; it
does not implement a new translation layer.

The exact kernel ISF must be present in
`$framework_dir/volatility3/symbols/linux/`. In the original setup it is
`kernel-7.0.0-38-arm64.json`. Its hash and exact banner are recorded in the
[capture metadata](../evidence/capture/kernel-7.0.0-38-arm64.metadata.json).
The kernel ELF and ISF remain outside Git.

## 3. Check PID and VMAs

```bash
"$framework_dir/.venv/bin/python" "$framework_dir/vol.py" -q \
  -f "$evidence_dir/ubuntu.lime" linux.pslist.PsList --pid 3183

"$framework_dir/.venv/bin/python" "$framework_dir/vol.py" -q \
  -f "$evidence_dir/ubuntu.lime" linux.proc.Maps --pid 3183
```

The recorded process is `cifar10_inferen`, with 128 VMAs. To reproduce the
pointer checks:

```bash
"$framework_dir/.venv/bin/python" "$framework_dir/volshell.py" -q -l \
  -f "$evidence_dir/ubuntu.lime" \
  --script "$project_dir/forensics/verify_addresses.py"
```

The verifier deliberately uses the original capture's PID and addresses. It
should end with `ADDRESS_CHECK_PASS`.

## 4. Extract the model with this repository's external plugin

Use a new output directory for each run:

```bash
recovery_dir="$evidence_dir/recovery-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$recovery_dir"

"$framework_dir/.venv/bin/python" "$framework_dir/vol.py" -q \
  -p "$project_dir/forensics/plugins" \
  -f "$evidence_dir/ubuntu.lime" \
  -o "$recovery_dir" \
  mlmodel.PytorchModel \
  --pid 3183 \
  --root-object 0xaaaaae062af0 \
  --layout "$project_dir/forensics/profiles/torch-2.14.1-cpu-aarch64.json"
```

The external plugin identifier is `mlmodel.PytorchModel`. It should report 26 modules, 31 tensors, 19 sources, and zero errors.
It imports no checkpoint or original training model.

To review the original extraction instead, set:

```bash
recovery_dir="$evidence_dir/recovered-model-verified"
```

## 5. Validate recovered bytes and source

The analysis environment needs no PyTorch. Use the separate CIFAR Python for
these model checks:

```bash
"$cifar_python" forensics/validate_recovery.py \
  --report "$recovery_dir/pytorch-3183-model.json" \
  --reference "$reference"
```

Expected: 31/31 tensor byte matches, matching module names/types/order, 19/19
source-file byte matches, all archived `.py` files recovered, and
`VALIDATION_PASS`. The validator also saves `recovered_state_dict.pt` from the
captured tensors. It supplies no values from the reference.

## 6. Execute the recovered implementation

```bash
comparison_dir="$evidence_dir/comparison-$(date +%Y%m%d-%H%M%S)"

"$cifar_python" forensics/confirm_recovery.py \
  --report "$recovery_dir/pytorch-3183-model.json" \
  --reference "$reference" \
  --test-bin "$test_images" \
  --output-dir "$comparison_dir" \
  --limit 6000
```

The helper builds objects from captured metadata, sources, and NumPy tensors
before opening the original model. It compiles recovered function bodies as
ordinary Python after annotation/cast erasure. Explicit adapters connect the
TorchScript intrinsics used here to Python and installed CPU PyTorch operators.
This is a tested compatibility layer for this experiment, not a general
TorchScript interpreter.

The recorded full run produced:

```text
Recovered definitions found: 34/34
Unresolved script/runtime dependencies: 0
Predictions matching: 6000/6000
Maximum absolute logit difference: 0
Logits within rtol=1e-5, atol=1e-5: True
Observed layer forward order matches recovered tree: True
INFERENCE_COMPARISON_PASS
```

The helper writes `code-coverage.json`, `inference-comparison.json`, both logits
arrays, and `predictions.csv`. Its output directory must not already exist.
Use `--limit 128` for a shorter check. PyTorch's Python 3.14 TorchScript warning
appeared in the measured environment; the recorded runs completed successfully.

## 7. Run focused tests

From this project's root, point Python at the framework for the decoder tests:

```bash
PYTHONPATH="$framework_dir:$project_dir" \
  "$framework_dir/.venv/bin/python" -m unittest discover \
  -s tests -p test_pytorch_model.py -v

"$cifar_python" -m unittest discover \
  -s tests -p test_pytorch_confirmation.py -v

python3 scripts/verify_evidence.py
```

The decoder suite has ten tests; the source replay suite has five. Replay
checks skip when PyTorch is unavailable, so use the CIFAR Python for them.
For native recovery and trace helpers, also run:

```bash
PYTHONPATH="$framework_dir:$project_dir" \
  "$framework_dir/.venv/bin/python" -m unittest \
  tests.test_native_recovery tests.test_native_capture_formats tests.test_native_trace -v
```

## 8. Generate a profile for another build

Use a Debug executable retaining complete PyTorch C++ types. Write a metadata
JSON containing the build's `torch_version`, `torch_git_version`, `machine`,
`torch_include`, `executable_sha256`, and `gdb_layout_source`. Then:

```bash
PYTORCH_LAYOUT_METADATA=/path/to/target-build-metadata.json \
PYTORCH_LAYOUT_OUTPUT=/path/to/new-layout.json \
gdb -q -batch /path/to/cifar10_inference \
  -ex 'source forensics/export_layout.py'
```

This reads DWARF types and the matching installed header. It does not run
inferior functions. A changed build may require updating decoder logic and field
paths, not just generating a different JSON file.

## 9. Repeat the recorded checks

With private artifacts and environments restored:

```bash
bash scripts/collect_evidence.sh
```

The script writes logs and results to a new timestamped directory under
`~/Downloads/memory-evidence`. It checks the saved checkpoint rather than rerunning
historical training. See [evidence notes](evidence-notes.md) for the recorded
results and screenshot provenance. The separate
[native-code pipeline](native-code-recovery.md) traces and recovers selected
native function bodies.
