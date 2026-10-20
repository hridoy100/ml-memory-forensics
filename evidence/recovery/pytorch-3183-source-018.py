def batch_norm(input: Tensor,
    running_mean: Optional[Tensor],
    running_var: Optional[Tensor],
    weight: Optional[Tensor]=None,
    bias: Optional[Tensor]=None,
    training: bool=False,
    momentum: float=0.10000000000000001,
    eps: float=1.0000000000000001e-05) -> Tensor:
  _0 = __torch__.torch.nn.functional._verify_batch_size
  _1 = "batch_norm eps must be positive during training, but got {}"
  _2 = "batch_norm eps must be non-negative, but got {}"
  if training:
    _3 = _0(torch.size(input), )
  else:
    pass
  if training:
    _4 = torch.le(eps, 0.)
  else:
    _4 = False
  if _4:
    ops.prim.RaiseException(torch.format(_1, eps), "builtins.ValueError")
  else:
    if torch.lt(eps, 0.):
      ops.prim.RaiseException(torch.format(_2, eps), "builtins.ValueError")
    else:
      pass
  _5 = torch.batch_norm(input, weight, bias, running_mean, running_var, training, momentum, eps, True)
  return _5
def relu(input: Tensor,
    inplace: bool=False) -> Tensor:
  if inplace:
    result = torch.relu_(input)
  else:
    result = torch.relu(input)
  return result
def _max_pool2d(input: Tensor,
    kernel_size: List[int],
    stride: Optional[List[int]]=None,
    padding: List[int]=[0, 0],
    dilation: List[int]=[1, 1],
    ceil_mode: bool=False,
    return_indices: bool=False) -> Tensor:
  if torch.__is__(stride, None):
    stride0 = annotate(List[int], [])
  else:
    stride0 = unchecked_cast(List[int], stride)
  _6 = torch.max_pool2d(input, kernel_size, stride0, padding, dilation, ceil_mode)
  return _6
def dropout(input: Tensor,
    p: float=0.5,
    training: bool=True,
    inplace: bool=False) -> Tensor:
  _7 = "dropout probability has to be between 0 and 1, but got {}"
  if torch.lt(p, 0.):
    _8 = True
  else:
    _8 = torch.gt(p, 1.)
  if _8:
    ops.prim.RaiseException(torch.format(_7, p), "builtins.ValueError")
  else:
    pass
  if inplace:
    _9 = torch.dropout_(input, p, training)
  else:
    _9 = torch.dropout(input, p, training)
  return _9
def _verify_batch_size(size: List[int]) -> NoneType:
  _10 = "Expected more than 1 value per channel when training, got input size {}"
  size_prods = size[0]
  size_prods0 = size_prods
  for i in range(torch.sub(torch.len(size), 2)):
    size_prods1 = torch.mul(size_prods0, size[torch.add(i, 2)])
    size_prods0 = size_prods1
  if torch.eq(size_prods0, 1):
    ops.prim.RaiseException(torch.format(_10, size), "builtins.ValueError")
  else:
    pass
  return None
