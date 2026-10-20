import json
import struct
from pathlib import Path
cp(3183)
layer = context.layers[self.current_layer]
def u64(address):
    return struct.unpack('<Q', layer.read(address, 8))[0]
checks = {
    'model_wrapper': 0xffffffffe588,
    'model_object': 0xaaaaae062af0,
    'input_wrapper': 0xffffffffe4a8,
    'input_tensor_impl': 0xaaaaadfce280,
}
print('Captured PID: 3183')
print('Process layer:', self.current_layer)
model_pointer = u64(checks['model_wrapper'])
input_pointer = u64(checks['input_wrapper'])
print('Model pointer:', hex(model_pointer))
print('Input TensorImpl pointer:', hex(input_pointer))
assert model_pointer == checks['model_object'], 'Model pointer differs from GDB'
assert input_pointer == checks['input_tensor_impl'], 'Input pointer differs from GDB'
impl = checks['input_tensor_impl']
rank = u64(impl + 56)
shape = list(struct.unpack('<4q', layer.read(impl + 64, 32)))
numel = u64(impl + 152)
print('Input rank:', rank, 'shape:', shape, 'numel:', numel)
assert rank == 4 and shape == [128, 3, 32, 32] and numel == 393216
print('Model object bytes:')
dq(checks['model_object'], count=64)
report = dict(checks, pid=3183, model_pointer=model_pointer, input_pointer=input_pointer, input_shape=shape, input_numel=numel)
Path('/home/raihan/Downloads/memory-evidence/verified-addresses.json').write_text(json.dumps(report, indent=2))
print('ADDRESS_CHECK_PASS')
raise SystemExit(0)
