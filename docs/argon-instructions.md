# Argon instructions

Training ran on an allocated Argon GPU node with Python 3.10.8, PyTorch
`2.14.1+cu126`, and torchvision `0.29.1+cu126`. The later Ubuntu memory experiment
used a CPU build and a separately compiled ARM64 executable.

## Training environment

The original Python environment needed a newer C++ runtime than Argon's system
library. The working setup was:

```bash
module load stack/2022.2
source /Users/smraalam/venvs/py3.10/bin/activate
export LD_LIBRARY_PATH="/cvmfs/argon.hpc.uiowa.edu/2022.2/x-tools/x86_64-unknown-linux-gnu/sysroot/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

python -c 'import torch; print(torch.__version__); print("CUDA:", torch.cuda.is_available())'
python -u train.py --epochs 25 --output-dir outputs
```

Run from `cifar10_cnn` on a compute node with a GPU allocation. Reuse these
commands in a shell setup file or job script when starting another session.
The runtime path addresses the observed `CXXABI_1.3.8` error. CUDA also requires
a compatible driver and PyTorch build; the successful run used CUDA 12.6.

## Apptainer build and debugging

The working image was `pytorch-cuda12.6.sif`, originally stored at
`/old_Users/smraalam/Projects/volatility/cifar10_cnn/pytorch-cuda12.6.sif`.
Its source was NVIDIA's `24.10-py3` image:

```bash
apptainer pull pytorch-cuda12.6.sif docker://nvcr.io/nvidia/pytorch:24.10-py3

unset LD_LIBRARY_PATH LD_PRELOAD
apptainer shell --cleanenv --nv \
  --bind "$PWD:/workspace" --pwd /workspace pytorch-cuda12.6.sif
```

Launch from the host's `cifar10_cnn` directory. The bind mount exposes it as
`/workspace`, so generated files persist on the host.

The container reported PyTorch `2.5.0a0+e000cf0ad9.nv24.10`, not the training
version. [NVIDIA's release notes](https://docs.nvidia.com/deeplearning/frameworks/pytorch-release-notes/rel-24-10.html)
identify upstream revision `e000cf0ad980e5d140dc895a646174e9b945cf26`.
Use the container's installed headers and debug types for inspection. The older
container version is separate from the training environment's release record.

Inside the container:

```bash
cd /workspace
export TORCH_CUDA_ARCH_LIST="8.0"
cmake --fresh -S cpp -B cpp/build-apptainer -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_PREFIX_PATH="$(python -c 'import torch; print(torch.utils.cmake_prefix_path)')"
cmake --build cpp/build-apptainer -j4

./cpp/build-apptainer/cifar10_inference \
  outputs/cifar10_torchscript.pt data/cifar10_test.bin outputs/cpp_predictions.csv
```

The architecture setting was for the allocated A100. `--nv` exposed the GPU,
but the C++ program itself uses CPU inference.

The image lacked GDB. An existing Micromamba installation supplied it through
a separate environment:

```bash
"$HOME/.local/bin/micromamba" create -y \
  -r "$HOME/.local/share/mamba" -p "$HOME/.local/argon-gdb" \
  --override-channels -c conda-forge gdb

"$HOME/.local/bin/micromamba" run \
  -r "$HOME/.local/share/mamba" -p "$HOME/.local/argon-gdb" \
  gdb -x cpp/inspect_model.gdb ./cpp/build-apptainer/cifar10_inference
```

Use `cpp/build-apptainer/cifar10_inference` for this build. The Ubuntu executable
and its captured addresses belong to a different environment. The
[GDB guide](gdb-instructions.md) explains the inspection commands.

If a host compiler segfaults after changing `LD_LIBRARY_PATH`, clear that variable
and `LD_PRELOAD` before starting Apptainer. The native Python runtime adjustment
above should not be carried into the clean container environment.
