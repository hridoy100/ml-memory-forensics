# What model code was recovered and observed?

The extractor recovers the model's generated TorchScript implementation from
resident Source objects reached through GraphFunction/graph SourceRanges. It
does not decompile the native PyTorch library or reconstruct the training script.

The [code inventory](../evidence/replay/code-coverage.json) maps the 26 module
objects to their recovered implementation files. All 19 archived `.py` files
matched the reference in bytes; 34 function definitions were found for the
reported graphs. The first evaluation batch executed 31 distinct recovered
functions. The unused definitions were the two Sequential `__len__` methods
and the training-only `_verify_batch_size` helper. This is an evaluation-path
measurement, not all-branch coverage.

The recovered implementation depends on installed PyTorch operations including
convolution, batch normalization, ReLU, max pooling, flattening, and linear
layers. The inventory also contains scalar/shape helpers and training branches.
A listed dependency does not imply that it executed during evaluation.

## New native evidence

The October 20 reproduction adds a live GDB sample in PID **3220**. This PID
does not identify the original memory-image process, **3183**.

The [native log](../evidence/submission-2026-10-20/native-forward.log) shows:

1. A breakpoint at the application's `model.forward` call, `main.cpp:91`.
2. An observed stack from `main` through `Module::forward`, the graph executor,
   interpreter, dispatcher, `conv2d_symint`, and `at::native::convolution`.
3. A stop at the implementation address `0xffffede72f50` in the library's `.text`
   section, rather than a PLT forwarding stub.
4. Twelve ARM64 instructions at that entry. The first instruction allocates
   stack space; subsequent instructions save registers and establish a frame.

This establishes one native boundary on this execution path. It does not
enumerate every native call, instrument the convolution's full inner kernels,
or extract native executable pages from the original LiME image. The application
has Debug information, but the prebuilt CPU runtime reports missing debugging
information; its available symbol names still support this bounded inspection.

The initial wrapper breakpoint was not reached. A second attempt stopped at a
PLT stub. Both logs are retained with explicit names; the final sample selects
the non-PLT symbol and checks that the stopped frame is an implementation.

![Native convolution implementation sample](images/11-native-forward.jpg)

## Clarification to send to the instructor

> For the requirement to recover "any code called during the model's forward
> pass," is recovering the model-level TorchScript implementation and its helper
> functions sufficient, or do you require extraction of native PyTorch/kernel
> machine code and an exhaustive native call trace? I recovered and validated
> the TorchScript source and model state, and added a native convolution
> backtrace/disassembly sample. The current work does not claim exhaustive
> native coverage.

No message has been sent. If exhaustive native coverage is required, define the
boundary first: model operators, PyTorch internals, or also runtime/system and
threaded backend calls. That scope determines whether additional library symbols,
instruction tracing, and capture-time executable-page extraction are needed.
