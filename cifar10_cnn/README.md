# Custom CIFAR-10 CNN and C++ inference

The network in `train.py` is defined directly with `torch.nn`; no pretrained or
prebuilt network is used. CIFAR-10's original train/test datasets are pooled and
split with seed 42 into 48,000 training, 6,000 validation, and 6,000 test images.
Only training images receive random crop and horizontal-flip augmentation.

The recorded training environment is pinned in `requirements.txt`. It used
Python 3.10.8 and PyTorch 2.14.1+cu126. These are observed experiment versions,
not an independently verified claim about the latest release today.

```bash
cd cifar10_cnn
python -u train.py --epochs 25 --output-dir outputs
python export_model.py --checkpoint outputs/best_model.pt --output outputs/cifar10_torchscript.pt
python prepare_test_images.py --checkpoint outputs/best_model.pt

cmake -S cpp -B cpp/build-ubuntu -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_PREFIX_PATH="$(python -c 'import torch; print(torch.utils.cmake_prefix_path)')"
cmake --build cpp/build-ubuntu --parallel 2
```

`best_model.pt` is a training checkpoint. `cifar10_torchscript.pt` is the scripted
inference archive loaded by LibTorch. The recovered `recovered_state_dict.pt`
described elsewhere contains weights/buffers, not an executable TorchScript
archive. All three binary artifacts stay outside Git.

The test binary consists of 6,000 records, each containing one label byte and
3,072 planar RGB bytes. C++ inference normalizes pixels with
`(pixel / 255.0 - 0.5) / 0.5` and uses batches of 128.

```bash
./cpp/build-ubuntu/cifar10_inference \
  outputs/cifar10_torchscript.pt data/cifar10_test.bin outputs/cpp_predictions.csv
gdb -x cpp/inspect_model.gdb ./cpp/build-ubuntu/cifar10_inference
```

The current GDB helper supports the measured GNU C++ TypePtr representations of
the Ubuntu 2.14.1 and earlier NVIDIA 24.10 environments. The historical
[Argon guide](ARGON.md) and [inspection notes](GDB_INSPECTION.md) preserve earlier
troubleshooting and addresses; follow the [current walkthrough](../docs/WALKTHROUGH.md)
for the Ubuntu capture and its exact PID/address evidence.

The 25-epoch run achieved 87.0833% test accuracy. Recorded metrics and original
test indices are in [evidence/training](../evidence/training). This is a custom
80/10/10 split, so the score is not directly comparable with the official
10,000-image CIFAR-10 test benchmark.
