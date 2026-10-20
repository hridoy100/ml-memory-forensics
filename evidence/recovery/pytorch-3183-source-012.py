class Flatten(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : NoneType
  start_dim : Final[int] = 1
  end_dim : Final[int] = -1
  def forward(self: __torch__.torch.nn.modules.flatten.Flatten,
    input: Tensor) -> Tensor:
    return torch.flatten(input, 1)
