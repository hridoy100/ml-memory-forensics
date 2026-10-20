#!/usr/bin/env bash
# Trace one forward call, then recover observed candidate bodies from a saved image.
set -euo pipefail

if [[ $# != 3 || ! $2 =~ ^[0-9]+$ ]]; then
    echo "Usage: bash scripts/collect_native_trace.sh CAPTURE PID NEW_OUTPUT_DIR" >&2
    exit 2
fi
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
capture="$(realpath "$1")"
captured_pid="$2"
output_dir="$3"
training_dir="${NATIVE_TRAINING_DIR:-$HOME/Downloads/volatility/cifar10_cnn}"
framework_dir="${NATIVE_FRAMEWORK_DIR:-$HOME/Downloads/volatility3-aarch64-experimental}"
python_bin="$training_dir/.venv/bin/python"
binary="${NATIVE_TRACE_BINARY:?Set NATIVE_TRACE_BINARY to the Debug cifar10_inference executable}"
library="$("$python_bin" -c 'import pathlib, torch; print(pathlib.Path(torch.__file__).parent / "lib/libtorch_cpu.so")')"

for tool in gdb nm objdump; do command -v "$tool" >/dev/null; done
for file in "$binary" "$library" "$capture" "$framework_dir/vol.py" \
    "$training_dir/outputs/cifar10_torchscript.pt" "$training_dir/data/cifar10_test.bin"; do
    [[ -r $file ]] || { echo "Cannot read: $file" >&2; exit 2; }
done
mkdir "$output_dir"  # Refuse to reuse an evidence directory.
output_dir="$(realpath "$output_dir")"
cd "$project_dir"

"$python_bin" scripts/plan_native_recovery.py --profile model-forward \
    --library "$library" --output "$output_dir/candidates.json" \
    > "$output_dir/plan.log" 2>&1

export NATIVE_TRACE_PLAN="$output_dir/candidates.json"
export NATIVE_TRACE_OUTPUT="$output_dir/trace.json"
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 gdb -q -nx -batch \
    -ex 'set script-extension soft' -ex 'source scripts/trace_native_forward.py' \
    --args "$binary" "$training_dir/outputs/cifar10_torchscript.pt" \
    "$training_dir/data/cifar10_test.bin" "$output_dir/trace-predictions.csv" \
    > "$output_dir/gdb.log" 2>&1

"$python_bin" scripts/select_traced_functions.py \
    --candidates "$output_dir/candidates.json" --trace "$output_dir/trace.json" \
    --output "$output_dir/observed-plan.json" > "$output_dir/selection.log" 2>&1

mkdir "$output_dir/recovery"
"$framework_dir/.venv/bin/python" "$framework_dir/vol.py" -q \
    -p "$project_dir/forensics/plugins" -f "$capture" -o "$output_dir/recovery" \
    mlnative.NativeCode --pid "$captured_pid" --plan "$output_dir/observed-plan.json" \
    > "$output_dir/extraction.log" 2>&1

"$python_bin" scripts/validate_native_recovery.py \
    --report "$output_dir/recovery/native-$captured_pid-report.json" \
    --library "$library" --output-dir "$output_dir/validation" \
    > "$output_dir/validation.log" 2>&1
echo "OBSERVED_NATIVE_RECOVERY_PASS: $output_dir"
