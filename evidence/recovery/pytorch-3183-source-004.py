class MaxPool2d(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : NoneType
  ceil_mode : Final[bool] = False
  dilation : Final[int] = 1
  stride : Final[int] = 2
  padding : Final[int] = 0
  return_indices : Final[bool] = False
  kernel_size : Final[int] = 2
  def forward(self: __torch__.torch.nn.modules.pooling.MaxPool2d,
    input: Tensor) -> Tensor:
    _0 = __torch__.torch.nn.functional._max_pool2d
    _1 = _0(input, [2, 2], [2, 2], [0, 0], [1, 1], False, False, )
    return _1
