# Detailed explanation of the project

## A short introduction

"I built a custom CIFAR-10 CNN, exported it to TorchScript, and ran it through a
C++ executable. I used GDB to inspect its live objects, captured Linux Ubuntu 26.04 version RAM with
LiME, and wrote a Volatility 3 plugin to recover the model's tensors, hierarchy,
and generated implementation. I validated those artifacts against the original,
then reconstructed the model from the recovered information. On all 6,000 test
images, its predictions and output logits matched the original exactly."

## Why each tool was used

| Tool | Role |
| --- | --- |
| PyTorch | Define/train the custom model and save the reference |
| TorchScript / LibTorch | Deploy its code and state in a C++ inference process |
| CMake Debug configuration | Retain line and C++ type information |
| GDB | Record PID, root addresses, types, and field layouts in a live process |
| LiME | Acquire system RAM from an authorized Linux VM |
| Volatility | Locate the captured task and translate its virtual addresses |
| Volshell | Verify the GDB addresses and tensor metadata offline |
| Custom plugin | Follow model objects and recover their contents |
| Separate validator/replay helper | Check byte-level correctness and execution behavior |

The project used Argon's GPU for training and CPU inference in an Ubuntu ARM64
VM for memory capture. The VM allowed kernel-module loading. Weights and scripted
model files transferred between environments; native executables were rebuilt.

## What the plugin follows

The root TorchScript Object references its ClassType and IValue slots. ClassType
descriptors identify attribute names, kinds, constants, and methods. Slots lead
to child objects and tensors. TensorImpl and StorageImpl lead to CPU allocations,
with shape, dtype, strides, and offset describing how to interpret the bytes.

Methods lead to GraphFunctions and graphs. SourceRanges reference resident Source
text. That source contains the generated implementation, including functional
helpers needed by the model's forward pass.

## Important numbers

- Custom split: 48,000 / 6,000 / 6,000; seed 42.
- Training: 25 epochs, 87.0833% test accuracy.
- Captured PID: 3183; 128 VMAs.
- Recovery: 26 module objects; 31 parameter/buffer tensors; 19 source files;
  34 function graphs.
- All recovered tensor and archived `.py` source bytes matched the reference.
- Replay: 6,000/6,000 predictions agreed; maximum logit difference was zero.
- Ten decoder tests and five replay integrity tests passed.

The 31 tensors include nine batch-normalization buffers. The 26 modules include
the root and containers. They are not counts of convolution layers.

## Explaining the validation part

The recovery plugin did not load the checkpoint. The reference was used later
to compare state and source. For replay, construction used captured classes,
function bodies, settings, and tensor files. The reference model was opened
after construction to compare the same normalized images.

The helper executes generated source as Python through a compatibility layer;
it does not produce a newly exported standalone TorchScript archive. Native
PyTorch operators remain installed runtime dependencies.

Agreement is not accuracy: both models agreed on every prediction and were
correct on 5,225 of 6,000 ground-truth labels.

## Challenges and limitations

The ARM64 kernel needed suitable framework translation support and an exact
kernel symbol table. **The kernel symbol conversion exceeded VM RAM, so it was
performed on the Mac using the same debug ELF.** PyTorch's C++ layout also changed
between builds, so offsets were measured from target debug types rather than
assumed.

The approach is GDB-guided and build-specific. It does not discover unknown
models automatically, recover GPU VRAM, recreate the original training script,
or reconstruct native C++ kernel source. Evaluation-path tracing does not prove
all-branch coverage. These limits are part of the findings.
