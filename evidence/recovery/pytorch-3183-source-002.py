class ReLU(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : NoneType
  inplace : Final[bool] = False
  def forward(self: __torch__.torch.nn.modules.activation.ReLU,
    input: Tensor) -> Tensor:
    _0 = __torch__.torch.nn.functional.relu(input, False, )
    return _0
