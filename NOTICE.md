# Source and software notices

The custom CNN/C++ code was copied from the project's existing
[repository](https://github.com/hridoy100/volatility/tree/800a2100d3e04dba7931512aeeb1746cd01cc582/cifar10_cnn).
The extractor and supporting tools were developed in the
[ARM64 framework fork](https://github.com/hridoy100/volatility3-arm64).
See [source provenance](manifests/source-repositories.json) for the snapshot
commits, local changes, and file hashes.

Volatility framework components and the ARM64 compatibility patch retain the
upstream notices. The [Volatility Software License](licenses/Volatility-VSL-1.0.txt)
was copied from that framework checkout.

The generated TorchScript sources in `evidence/recovery/pytorch-3183-source-*.py`
include the custom model and serialized PyTorch module/helper implementations.
The [PyTorch license](licenses/PyTorch-LICENSE.txt) was copied from the installed
target PyTorch distribution. The repository does not redistribute LibTorch,
CUDA, or other runtime binaries. The native-recovery branch includes ARM64 disassembly of one
function from the installed PyTorch CPU runtime under the same PyTorch notice. The extracted binary itself remains outside Git.

CIFAR-10 is obtained separately through torchvision. Dataset attribution and
download information are available from the
[CIFAR-10 authors](https://www.cs.toronto.edu/~kriz/cifar.html).

No new blanket license is assigned to third-party material by consolidation
into this private repository.
