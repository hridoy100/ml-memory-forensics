# Recovering a CIFAR-10 model from Linux memory

The goal was to recover a deployed model from RAM and check whether its weights
and code could reproduce the original inference results. Training a custom CNN
provided a known reference for validating the recovered artifacts.

The experiment moved through three environments: Argon for GPU training, an
Apptainer environment for the earlier C++/GDB work, and an Ubuntu ARM64 VM for
privileged memory capture and the final recovery. The trained model transferred
between environments; the native executable and structure layouts were matched
to each target.

The recorded result is a recovery of 31 tensors, 26 module objects, 19 generated
TorchScript source files, and 34 function graphs. A reconstructed implementation
agreed with the original on all 6,000 test-image predictions and output logits.

## 1. Train a custom model

The network in [train.py](../cifar10_cnn/train.py) uses six 3×3 convolutions,
batch normalization, ReLU activations, and three pooling stages. The classifier
flattens the resulting 128×4×4 features, applies a 256-unit linear layer and
dropout, and returns ten class logits. No pretrained network is used.

I pooled CIFAR-10's original 50,000-image training set and 10,000-image test set, then made a disjoint stratified split with seed 42:

| Partition | Images | Images per class |
| --- | ---: | ---: |
| Training | 48,000 | 4,800 |
| Validation | 6,000 | 600 |
| Testing | 6,000 | 600 |

Random crop and horizontal flip apply only to training images. Input pixels are
normalized with `(pixel / 255.0 - 0.5) / 0.5`. This is a custom split, so its
accuracy should not be compared directly with the official 10,000-image test
benchmark.

In an allocated Argon GPU environment, from `cifar10_cnn`:

```bash
python -u train.py --epochs 25 --output-dir outputs
```

The run used Python 3.10.8, PyTorch 2.14.1+cu126, batch size 128, and learning
rate 0.001. The best validation epoch was 25. Final accuracy was 5,225/6,000,
or 87.0833%, as recorded in [metrics.json](../evidence/training/metrics.json).
The [version record](evidence-notes.md#environments-and-versions) compares
the installed package with releases available by the October 17 artifact commit.

![Checkpoint and saved training metrics, checked October 20](images/05-training-record.jpg)

This screenshot checks the saved training record; it is not a screenshot of the
original training job.

## 2. Export the trained checkpoint

The training checkpoint saves state and metadata. I exported a separate
TorchScript archive using [export_model.py](../cifar10_cnn/export_model.py):

```bash
python export_model.py \
  --checkpoint outputs/best_model.pt \
  --output outputs/cifar10_torchscript.pt
```

The exporter loads weights on CPU, sets evaluation mode, uses `torch.jit.script`,
saves the archive, and checks the reloaded model against the Python model.
The archive contains generated model code, weights, and class labels for LibTorch.
This follows the
[TorchScript C++ export workflow](https://docs.pytorch.org/tutorials/advanced/cpp_export.html).

![TorchScript export check](images/06-export.jpg)

The saved checkpoint, exported model, and recovered state dictionary all use
`.pt`, but they are different artifacts. Hashes and storage locations are in the
[external artifact manifest](../manifests/artifacts.json).

## 3. Run inference in C++ with debug information

[prepare_test_images.py](../cifar10_cnn/prepare_test_images.py) writes the exact
held-out records selected by the checkpoint. Each record is one class-label byte
followed by 3,072 planar RGB bytes. It checks for overlap with training/validation
indices before writing the test binary.

```bash
python prepare_test_images.py --checkpoint outputs/best_model.pt

cmake -S cpp -B cpp/build-ubuntu -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_PREFIX_PATH="$(python -c 'import torch; print(torch.utils.cmake_prefix_path)')"
cmake --build cpp/build-ubuntu --parallel 2

./cpp/build-ubuntu/cifar10_inference \
  outputs/cifar10_torchscript.pt data/cifar10_test.bin outputs/cpp_predictions.csv
```

The [C++ program](../cifar10_cnn/cpp/main.cpp) uses `torch::jit::load`, applies the
same normalization, runs batches of 128, and writes predictions. It explicitly
uses CPU inference, making its tensor allocations available in system RAM.

The [CMake configuration](../cifar10_cnn/cpp/CMakeLists.txt) uses C++20 and retains
full debugging information. GNU/Clang flags include `-g3`, `-O0`, and
`-fno-omit-frame-pointer`, together with type-retention options. Retaining complete
header-defined class types mattered because the prebuilt library did not provide
all the debug types needed for inspection.

![Debug build and C++ inference check](images/07-debug-build.jpg)

The [Argon guide](argon-instructions.md) documents the earlier Apptainer route. The final Ubuntu forensic target was rebuilt natively for ARM64;
an x86 executable is not interchangeable with an ARM64 executable.

## 4. Stop at the forward pass in GDB

The forward call is at line 91 of the preserved `main.cpp`:

```cpp
auto logits = model.forward({images}).toTensor();
```

From `cifar10_cnn`, the supplied script sets the arguments, breakpoint, logging,
and read-only inspection commands:

```bash
gdb -x cpp/inspect_model.gdb ./cpp/build-ubuntu/cifar10_inference
```

Stopping before forward leaves the loaded model and input batch in memory.
Keep the inferior stopped while capturing memory from another terminal. A new
run gets a new PID and usually different addresses; the recorded values below
belong only to the original capture.

## 5. Record PID and inspect PyTorch structures

The captured Ubuntu process was PID **3183**. GDB reported:

| Object | Captured address |
| --- | --- |
| Model wrapper | `0xffffffffe588` |
| `model._ivalue_.target_` | `0xaaaaae062af0` |
| Input tensor wrapper | `0xffffffffe4a8` |
| Input TensorImpl | `0xaaaaadfce280` |

![GDB PID and model/input addresses](images/01-gdb-pid-and-addresses.png)

This original-session image shows PID 3183, the model/input wrapper and target
addresses, and type-layout inspection. The
[GDB helper verification log](../evidence/logs/repository-gdb-helper-check.log)
contains a later forward-breakpoint, ClassType/slot, and weight-storage check
in live PID 3391; its addresses are not those of the original capture.

The Object's ClassType describes named attributes, parameter/buffer kinds, layer
constants, and methods. Object IValue slots hold the corresponding values.
Object-valued slots lead to child modules; tensor-valued slots lead to TensorImpl,
StorageImpl, and the allocation holding the values.

The target package reported PyTorch 2.14.1+cpu and source revision
`5c4886908584029761b579af026dcfb627c84070`. I measured field paths and offsets
from the executable's retained DWARF types and matching installed headers, rather
than borrowing offsets from a different build. The
[ABI profile](../forensics/profiles/torch-2.14.1-cpu-aarch64.json) records those
measurements and the executable hash. The corresponding build-reported revision
is referenced in [PyTorch GitHub](https://github.com/pytorch/pytorch/tree/5c4886908584029761b579af026dcfb627c84070);
the installed headers and debug types are the direct evidence for the layout.

The [GDB helper](../cifar10_cnn/cpp/torch_inspect.py) provides `torch-slots`,
`torch-attr`, and `torch-tensor`. It reads memory and types without invoking
functions in the stopped inferior. The inspection script follows the first
convolution's weight tensor through storage and displays floats and hexadecimal
words.

## 6. Capture RAM and identify the process offline

LiME was built against the running Ubuntu kernel. For a new acquisition in an
authorized VM, build the module, create a private output directory, and load it
while the inference process remains stopped:

```bash
make -C "$HOME/Downloads/LiME/src"
mkdir -p "$HOME/Downloads/memory-evidence"

sudo insmod "$HOME/Downloads/LiME/src/lime-$(uname -r).ko" \
  "path=$HOME/Downloads/memory-evidence/new-capture.lime" format=lime
```

Do not overwrite the original image. The original acquisition reported an
`Invalid parameters` insertion error, but left a LiME-format file. Its header
was checked, the file was hashed, and the target process pages were successfully
analyzed. This is evidence that the target artifacts were present; it does not
independently certify completeness of every system page.

The retained image is 4,289,855,648 bytes with SHA-256:

```text
17444d6e2daa1089feb8e1c7c1d01e5effb4c8500f60c4455102d0af4d57a769
```

The exact kernel debug ELF was needed to build the Volatility kernel ISF. Symbol
conversion exceeded the VM's available RAM, so I transferred the ELF through the
QEMU guest agent and generated the ISF on the Mac. The ISF was copied back and its
kernel banner matched the capture. The kernel ELF/ISF and memory image stay out
of Git.

The existing ARM64 translation support came from an experimental Volatility 3
branch. Two plugin requirements were patched to allow AArch64 for PsList and
Maps. See [the patch](../patches/arm64-process-plugins.patch) and the exact
[reproduction commands](running-instructions.md).

PsList found PID 3183 with parent PID 3174. Maps produced 128 VMAs:

```bash
framework_dir="$HOME/Downloads/volatility3-aarch64-experimental"
"$framework_dir/.venv/bin/python" "$framework_dir/vol.py" -q \
  -f "$HOME/Downloads/memory-evidence/ubuntu.lime" linux.pslist.PsList --pid 3183
"$framework_dir/.venv/bin/python" "$framework_dir/vol.py" -q \
  -f "$HOME/Downloads/memory-evidence/ubuntu.lime" linux.proc.Maps --pid 3183
```

![Volatility identifies PID 3183](images/02-volatility-pid.png)

The [PID table](../evidence/capture/pslist-3183.tsv) and
[VMA table](../evidence/capture/maps-3183.tsv) preserve the complete results.
The PsList screenshot shows PID 3183; the screenshot in step 7 shows the tail of its VMA listing. The
128-mapping count comes from the complete table, not just the visible tail.

## 7. Check the recorded addresses with Volshell

Volshell switched to the captured process layer and read its virtual addresses.
The wrapper pointers matched GDB. The input TensorImpl reported rank four,
shape `[128, 3, 32, 32]`, and 393,216 elements.

![VMA listing and successful Volshell verification](images/03-vmas-and-volshell.png)

From the project root, run the recorded address check:

```bash
"$framework_dir/.venv/bin/python" "$framework_dir/volshell.py" -q -l \
  -f "$HOME/Downloads/memory-evidence/ubuntu.lime" \
  --script "$PWD/forensics/verify_addresses.py"
```

The verification script is [verify_addresses.py](../forensics/verify_addresses.py).
It reads real pages without padding missing data and ends with
`ADDRESS_CHECK_PASS`. The Object and TensorImpl targets were inside the anonymous
mapping `0xaaaaaac00000–0xaaaaae200000`; their wrappers were on the stack.

An optional GDB core-file attempt lacked a heap page. Its
[failure log](../evidence/logs/gdb-core-inspection.log) is preserved. The successful
checks used the original LiME image.

## 8. Recover and execute the model

The [custom plugin](../forensics/plugins/mlmodel.py) locates the task,
constructs a process layer, and starts at the supplied root Object pointer.
It pairs ClassType descriptors with IValue slots, walks child modules, and
extracts tensor allocations after checking shape, dtype, strides, storage offset,
and allocation bounds. Parameters and batch-normalization buffers are retained.

![Model extraction from the preserved capture](images/08-extraction.jpg)

GraphFunction methods and the CompilationUnit lead to graphs and SourceRanges.
Resident Source objects hold string-view pieces containing generated TorchScript
code. The plugin joins those pieces and saves their actual bytes and provenance.
It also records graph topology and source relationships.

The plugin does not open the checkpoint or import the original model definition.
The separately run validator compares recovered artifacts with the reference.
Its [report](../evidence/recovery/validation.json) confirms 31/31 tensors and
19/19 archived `.py` files are byte-identical, with matching module names, types,
and registration order. There are 26 module objects and 34 function graphs.

![Recovered state and source comparison](images/09-validation.jpg)

### Recovery summary

| Artifact | Result from the original PID-3183 image |
| --- | --- |
| Weights and buffers | 22 parameters and 9 batch-normalization buffers; all 31 tensors match in name, shape, dtype, and bytes |
| Model hierarchy | 26 module objects with matching names, types, and registration order |
| Function graphs | 34 materialized graphs with topology/source records; not a complete IR serializer |
| Implementation code | All 19 archived generated TorchScript `.py` files recovered byte for byte |
| Inference validation | Reconstructed model matches all 6,000 predictions and logits; both models score 5,225/6,000 |

The October 20 extraction, validation, and replay checks reuse the original
image. Their screenshots are browser views of saved check logs, not terminal
screenshots from the acquisition session. The later warm image is used only
for the separate native-code results below.

I then used [confirm_recovery.py](../forensics/confirm_recovery.py) to instantiate
the captured hierarchy and assign its recovered settings and tensor values. The
captured function bodies were compiled as Python after annotation/cast erasure,
with explicit adapters to the installed CPU runtime. The original archive was
opened only after reconstruction for comparison.

The [full comparison](../evidence/replay/inference-comparison.json) records:

```text
Recovered definitions found: 34/34
Unresolved script/runtime dependencies: 0
Predictions matching: 6000/6000
Maximum absolute logit difference: 0
Observed layer forward order matches recovered tree: True
INFERENCE_COMPARISON_PASS
```

![Full test-set comparison](images/10-replay.jpg)

Matching predictions means agreement between implementations. Both were correct
on 5,225 images, or 87.0833%. The first batch of the recovered-source Python
replay made 49 calls to 31 distinct recovered functions; the remaining definitions
were two `__len__` methods and the training-only `_verify_batch_size` helper.

The [code map](../evidence/replay/code-coverage.json),
[predictions](../evidence/replay/predictions.csv), and original
[replay log](../evidence/logs/replay-confirmation-6000.log) are tracked here.
The ten decoder tests and five replay tests cover bounds, missing pages, storage
offsets, unsupported layouts, source integrity, and missing definitions. Every
observed generated-code function has a recovered definition. Calls through the
installed PyTorch runtime or Python intrinsic adapters are dependencies, not
additional recovered implementations. The [coverage audit](findings.md#forward-pass-implementation-coverage)
separates those cases and identifies the unexercised definitions.

## Native-code recovery

A later live GDB sample in PID 3220 followed the forward pass through the graph
executor, interpreter, dispatcher, and native convolution implementation:

![Native convolution backtrace and instructions](images/11-native-forward.jpg)

The original capture could not read the selected native code range. A second
LiME capture, taken after one completed batch, recovered the full 584-byte
convolution function from captured PID 4540. A separate live entry trace in
PID 2782 observed ten of twelve candidate functions during one forward call.
All ten symbol-bounded bodies were extracted from the warm PID-4540 image and
compared with the reference library: 23,340 bytes, all matching. Their library
build identity was checked; they are not bytes recovered from the original
PID-3183 image.

The [native-code guide](native-code-recovery.md) gives the commands and reports.
This extends recovery to selected native function bodies; internal callees,
backend libraries, and all possible execution paths are not exhaustively covered.

## What this shows

The captured state and generated implementation were enough to reconstruct this
model and reproduce its outputs on the held-out test set. The
[findings](findings.md) describe the build-specific, guided recovery and replay
limits. [Evidence notes](evidence-notes.md) distinguish original-session images
from later browser views of reproduction logs and document the historical
version check.

The related [AI Psychiatry work](https://www.usenix.org/conference/usenixsecurity24/presentation/oygenblik)
studies recovery and rehosting of deployed models from memory. The
[ZEN paper](https://www.ndss-symposium.org/wp-content/uploads/2026-s1628-paper.pdf)
emphasizes recovering programmatic implementations alongside mathematical model
representations. This project uses a controlled, GDB-guided TorchScript target;
it does not reproduce those systems' full discovery, attribution, GPU recovery,
or model-patching techniques.
