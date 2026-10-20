class Sequential(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : NoneType
  __annotations__["0"] = __torch__.torch.nn.modules.flatten.Flatten
  __annotations__["1"] = __torch__.torch.nn.modules.linear.Linear
  __annotations__["2"] = __torch__.torch.nn.modules.activation.ReLU
  __annotations__["3"] = __torch__.torch.nn.modules.dropout.Dropout
  __annotations__["4"] = __torch__.torch.nn.modules.linear.___torch_mangle_7.Linear
  def forward(self: __torch__.torch.nn.modules.container.___torch_mangle_8.Sequential,
    input: Tensor) -> Tensor:
    _0 = getattr(self, "0")
    _1 = getattr(self, "1")
    _2 = getattr(self, "2")
    _3 = getattr(self, "3")
    _4 = getattr(self, "4")
    input0 = (_0).forward(input, )
    input1 = (_1).forward(input0, )
    input2 = (_2).forward(input1, )
    input3 = (_3).forward(input2, )
    return (_4).forward(input3, )
  def __len__(self: __torch__.torch.nn.modules.container.___torch_mangle_8.Sequential) -> int:
    return 5
