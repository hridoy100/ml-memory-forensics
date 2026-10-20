# Reproduce the recovery and comparison

These commands use Ubuntu. The completed experiment already has the required
framework and CPU PyTorch environment. A clone of this repository holds project
code and small evidence files; private binary artifacts remain separate.

## 1. Set paths

After cloning this repository into `~/Downloads/ml-memory-forensics`, use one
terminal for the following commands:

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

The external plugin identifier is `mlmodel.PytorchModel`. The earlier
framework-installed copy was named `linux.pytorch_model.PytorchModel`.
The plugin should report 26 modules, 31 tensors, 19 sources, and zero errors.
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

For a readable code map:

```bash
python3 - "$comparison_dir/code-coverage.json" <<'PY'
import json
import sys

coverage = json.load(open(sys.argv[1]))
print("Layer\tType\tRecovered source")
for layer in coverage["layers"]:
    print(layer["path"], layer["type"].rsplit(".", 1)[-1], layer["source"], sep="\t")
PY
```

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

The decoder suite has ten tests; the source replay suite has five. The latter
skips when PyTorch is unavailable, so use the CIFAR Python to actually run it.

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

## 9. Reproduce the submission evidence

The [October 20 supplement](SUBMISSION_EVIDENCE.md) documents a new Debug build,
export, full recovery/replay, and bounded native inspection. From this project:

```bash
bash scripts/collect_submission_evidence.sh
```

It writes a new directory under `~/Downloads/memory-evidence`. Restore private
artifacts and the existing environments first. The checkpoint-record check does
not rerun historical training. The native sample is a new live process.
