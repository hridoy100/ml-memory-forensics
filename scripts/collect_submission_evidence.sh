#!/usr/bin/env bash
# Reproduce submission evidence without overwriting the original capture/model.
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
original_dir="${ORIGINAL_CIFAR_DIR:-$HOME/Downloads/volatility/cifar10_cnn}"
framework_dir="${FRAMEWORK_DIR:-$HOME/Downloads/volatility3-aarch64-experimental}"
evidence_dir="${EVIDENCE_DIR:-$HOME/Downloads/memory-evidence}"
run_dir="${1:-$evidence_dir/submission-$(date +%Y%m%d-%H%M%S)}"
python="$original_dir/.venv/bin/python"
reference="$original_dir/outputs/cifar10_torchscript.pt"
images="$original_dir/data/cifar10_test.bin"
mkdir "$run_dir"
run_dir="$(cd "$run_dir" && pwd)"
printf '%s\n' "$run_dir" > "$evidence_dir/latest-submission-run.txt"

step() {
    local name="$1"
    shift
    {
        printf 'Reproduction check: %s\n' "$name"
        date -Is
        printf 'Command:'
        printf ' %q' "$@"
        printf '\n\n'
        "$@"
        printf '\nSTEP_PASS: %s\n' "$name"
    } 2>&1 | tee "$run_dir/$name.log"
}

step environment "$python" -c 'import platform, torch, torchvision; print("Python:", platform.python_version()); print("Architecture:", platform.machine()); print("PyTorch:", torch.__version__); print("PyTorch commit:", torch.version.git_version); print("torchvision:", torchvision.__version__)'

step training-record "$python" - "$original_dir/outputs/best_model.pt" "$project_dir/evidence/training/metrics.json" <<'PY'
import hashlib, json, sys, torch
from pathlib import Path
path, metrics_path = map(Path, sys.argv[1:])
checkpoint = torch.load(path, map_location="cpu", weights_only=True)
metrics = json.loads(metrics_path.read_text())
print("Historical training record; this check does not rerun training.")
print("Checkpoint SHA256:", hashlib.sha256(path.read_bytes()).hexdigest())
print("Checkpoint epoch:", checkpoint["epoch"])
print("State tensors:", len(checkpoint["model_state_dict"]))
for key, value in metrics.items():
    print(f"{key}: {value}")
assert checkpoint["epoch"] == metrics["best_epoch"] == 25
assert metrics["split_sizes"] == {"train":48000,"validation":6000,"test":6000}
print("TRAINING_RECORD_CHECK_PASS")
PY

step export "$python" "$project_dir/cifar10_cnn/export_model.py" \
    --checkpoint "$original_dir/outputs/best_model.pt" \
    --output "$run_dir/reexported.pt"

prefix="$("$python" -c 'import torch; print(torch.utils.cmake_prefix_path)')"
step configure cmake -S "$project_dir/cifar10_cnn/cpp" -B "$run_dir/build" \
    -DCMAKE_BUILD_TYPE=Debug -DCMAKE_PREFIX_PATH="$prefix"
step build cmake --build "$run_dir/build" --parallel 1 --verbose
step debug-sections readelf -S "$run_dir/build/cifar10_inference"
step cpp-inference env OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    "$run_dir/build/cifar10_inference" "$run_dir/reexported.pt" "$images" \
    "$run_dir/cpp-predictions.csv"

mkdir "$run_dir/recovery"
step extraction "$framework_dir/.venv/bin/python" "$framework_dir/vol.py" -q \
    -p "$project_dir/forensics/plugins" -f "$evidence_dir/ubuntu.lime" \
    -o "$run_dir/recovery" mlmodel.PytorchModel --pid 3183 \
    --root-object 0xaaaaae062af0 \
    --layout "$project_dir/forensics/profiles/torch-2.14.1-cpu-aarch64.json"
step validation "$python" "$project_dir/forensics/validate_recovery.py" \
    --report "$run_dir/recovery/pytorch-3183-model.json" --reference "$reference"
step replay env OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 "$python" \
    "$project_dir/forensics/confirm_recovery.py" \
    --report "$run_dir/recovery/pytorch-3183-model.json" --reference "$reference" \
    --test-bin "$images" --output-dir "$run_dir/replay" --limit 6000

step native-forward env OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    gdb -q -batch -x "$project_dir/scripts/inspect_native_forward.gdb" \
    --args "$run_dir/build/cifar10_inference" "$reference" "$images" \
    "$run_dir/gdb-predictions.csv"
step summary "$python" "$project_dir/scripts/summarize_submission_run.py" "$run_dir"
printf '\nSUBMISSION_RUN_PASS\n%s\n' "$run_dir"
