# CIFAR-10 CNN

`train.py` defines a custom network with six convolution layers, three
batch-normalization layers, ReLU, pooling, and a two-layer classifier. No prebuilt
network is used. CIFAR-10 is pooled and split with seed 42 into 48,000 training,
6,000 validation, and 6,000 test images. Only training images are augmented.

```bash
python -u train.py --epochs 25 --output-dir outputs
python export_model.py --checkpoint outputs/best_model.pt \
  --output outputs/cifar10_torchscript.pt
python prepare_test_images.py --checkpoint outputs/best_model.pt
```

The checkpoint saves training state and split indices. The TorchScript archive
contains the inference model for LibTorch. The test binary has 6,000 records,
each holding a label byte and 3,072 planar RGB bytes. Inference uses batches of
128 and normalization `(pixel / 255.0 - 0.5) / 0.5`.

The recorded run achieved 87.0833% test accuracy after 25 epochs. This custom
80/10/10 split differs from CIFAR-10's official 10,000-image test benchmark.
Metrics and test indices are in [training evidence](../evidence/training).

See [running instructions](../docs/running-instructions.md) for environment and
C++ build commands, [GDB instructions](../docs/gdb-instructions.md) for object
inspection, and [Argon instructions](../docs/argon-instructions.md) for the
training/container setup. Model, data, and build files are excluded from Git.
