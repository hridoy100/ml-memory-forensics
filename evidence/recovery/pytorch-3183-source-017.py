class CIFAR10CNN(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  features : __torch__.torch.nn.modules.container.Sequential
  classifier : __torch__.torch.nn.modules.container.___torch_mangle_8.Sequential
  def forward(self: __torch__.train.CIFAR10CNN,
    images: Tensor) -> Tensor:
    classifier = self.classifier
    features = self.features
    _0 = (classifier).forward((features).forward(images, ), )
    return _0
