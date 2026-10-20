# GDB instructions

Use a Debug executable built against the PyTorch installation being inspected.
The final Ubuntu experiment used PyTorch `2.14.1+cpu`, revision
[`5c4886908584029761b579af026dcfb627c84070`](https://github.com/pytorch/pytorch/tree/5c4886908584029761b579af026dcfb627c84070).
Check that revision rather than assuming the current upstream branch has the
same object layout.

## Stop before forward

From `cifar10_cnn`, after building and restoring the model and test binary:

```bash
mkdir -p outputs
gdb -x cpp/inspect_model.gdb ./cpp/build-ubuntu/cifar10_inference
```

The script sets the arguments, stops at `main.cpp:91`, loads the inspection
helpers, and appends evidence to `outputs/gdb_inspection.log`. The breakpoint is:

```cpp
auto logits = model.forward({images}).toTensor();
```

For a manual session:

```bash
gdb ./cpp/build-ubuntu/cifar10_inference
```

```gdb
set args outputs/cifar10_torchscript.pt data/cifar10_test.bin outputs/cpp_predictions_gdb.csv
break main.cpp:91
run
source cpp/torch_inspect.py
info inferiors
python print("Inference PID:", gdb.selected_inferior().pid)
```

## Inspect objects and storage

The CMake configuration uses `-g3 -O0 -fno-omit-frame-pointer` and retains unused
header-defined types. GCC also uses `-femit-class-debug-always`; Clang uses
`-fstandalone-debug`. These flags keep the types needed for inspection.

These commands print wrapper addresses, then follow the model to its first
convolution and weight allocation:

```gdb
print /x &model
print /x &images
print /x images.impl_.target_
torch-tensor images

set $root = model._ivalue_.target_
torch-slots $root
torch-attr $root features
set $features = $torch_object
torch-attr $features 0
set $conv = $torch_object
torch-slots $conv
torch-attr $conv weight
torch-tensor *$torch_tensor

set $weight_data = (float*)$torch_data + $torch_offset
print /x $weight_data
x/8fw $weight_data
x/8xw $weight_data
```

The tensor wrapper points to TensorImpl, which holds shape, strides, dtype,
device, storage, and offset. StorageImpl points to the allocation. For float32,
the first element is at `allocation_base + 4 * storage_offset`.

ClassType holds layer descriptions and constant settings. The Object's IValue
slots hold current attribute values, including child modules and parameters.
After `torch-slots $conv`, inspect its constants with:

```gdb
python for i, n in enumerate(vector_items(gdb.parse_and_eval("$torch_type->constantNames_"))): print(i, n["_M_dataplus"]["_M_p"].string())
print /r $torch_type->constantValues_
```

The helper reads debug types and memory without calling functions in the
inferior. Field layouts are measured in the
[ABI profile](../forensics/profiles/torch-2.14.1-cpu-aarch64.json).
Relevant PyTorch definitions include `ivalue_inl.h`, `class_type.h`,
`TensorImpl.h`, `StorageImpl.h`, and `Allocator.h` at the matching revision.

## Capture or step forward

For LiME acquisition, leave the process stopped and use another terminal as
described in the [walkthrough](project-walkthrough.md#6-capture-ram-and-identify-the-process-offline).
Record this run's PID and addresses before capture.

To execute one forward call:

```gdb
bt
next
torch-tensor logits
```

For a full 128-image batch, logits have shape `[128, 10]`. To finish the program,
enter `disable 1`, then `continue` at the next prompt. Keep
`outputs/gdb_inspection.log` with the capture's evidence.

## Common problems

| Problem | Check |
| --- | --- |
| No executable or symbols loaded | Load the compiled inference executable and confirm the Debug build succeeded. |
| Incomplete TensorImpl/ClassType | Rebuild with the type-retention flags in `cpp/CMakeLists.txt`, then restart GDB. |
| Missing field or unexpected layout | Use `ptype /o` and `print /r`; match the installed headers and package revision. |
| `torch-attr` usage error after pasting | Enter one command at each GDB prompt. |
| Breakpoint points at a different line | Locate `model.forward` in `cpp/main.cpp` and update the scripts. |

The earlier NVIDIA container used a different PyTorch layout; see the
[Argon instructions](argon-instructions.md). Its recorded addresses do not apply
to the Ubuntu capture.
