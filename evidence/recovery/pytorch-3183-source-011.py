class Sequential(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : NoneType
  __annotations__["0"] = __torch__.torch.nn.modules.conv.Conv2d
  __annotations__["1"] = __torch__.torch.nn.modules.batchnorm.BatchNorm2d
  __annotations__["2"] = __torch__.torch.nn.modules.activation.ReLU
  __annotations__["3"] = __torch__.torch.nn.modules.conv.___torch_mangle_0.Conv2d
  __annotations__["4"] = __torch__.torch.nn.modules.activation.ReLU
  __annotations__["5"] = __torch__.torch.nn.modules.pooling.MaxPool2d
  __annotations__["6"] = __torch__.torch.nn.modules.conv.___torch_mangle_1.Conv2d
  __annotations__["7"] = __torch__.torch.nn.modules.batchnorm.___torch_mangle_2.BatchNorm2d
  __annotations__["8"] = __torch__.torch.nn.modules.activation.ReLU
  __annotations__["9"] = __torch__.torch.nn.modules.conv.___torch_mangle_3.Conv2d
  __annotations__["10"] = __torch__.torch.nn.modules.activation.ReLU
  __annotations__["11"] = __torch__.torch.nn.modules.pooling.MaxPool2d
  __annotations__["12"] = __torch__.torch.nn.modules.conv.___torch_mangle_4.Conv2d
  __annotations__["13"] = __torch__.torch.nn.modules.batchnorm.___torch_mangle_5.BatchNorm2d
  __annotations__["14"] = __torch__.torch.nn.modules.activation.ReLU
  __annotations__["15"] = __torch__.torch.nn.modules.conv.___torch_mangle_6.Conv2d
  __annotations__["16"] = __torch__.torch.nn.modules.activation.ReLU
  __annotations__["17"] = __torch__.torch.nn.modules.pooling.MaxPool2d
  def forward(self: __torch__.torch.nn.modules.container.Sequential,
    input: Tensor) -> Tensor:
    _0 = getattr(self, "0")
    _1 = getattr(self, "1")
    _2 = getattr(self, "2")
    _3 = getattr(self, "3")
    _4 = getattr(self, "4")
    _5 = getattr(self, "5")
    _6 = getattr(self, "6")
    _7 = getattr(self, "7")
    _8 = getattr(self, "8")
    _9 = getattr(self, "9")
    _10 = getattr(self, "10")
    _11 = getattr(self, "11")
    _12 = getattr(self, "12")
    _13 = getattr(self, "13")
    _14 = getattr(self, "14")
    _15 = getattr(self, "15")
    _16 = getattr(self, "16")
    _17 = getattr(self, "17")
    input0 = (_0).forward(input, )
    input1 = (_1).forward(input0, )
    input2 = (_2).forward(input1, )
    input3 = (_3).forward(input2, )
    input4 = (_4).forward(input3, )
    input5 = (_5).forward(input4, )
    input6 = (_6).forward(input5, )
    input7 = (_7).forward(input6, )
    input8 = (_8).forward(input7, )
    input9 = (_9).forward(input8, )
    input10 = (_10).forward(input9, )
    input11 = (_11).forward(input10, )
    input12 = (_12).forward(input11, )
    input13 = (_13).forward(input12, )
    input14 = (_14).forward(input13, )
    input15 = (_15).forward(input14, )
    input16 = (_16).forward(input15, )
    return (_17).forward(input16, )
  def __len__(self: __torch__.torch.nn.modules.container.Sequential) -> int:
    return 18
