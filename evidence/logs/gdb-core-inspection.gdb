set pagination off
set print pretty on
info inferiors
printf "Captured inference PID: 3183\n"
bt
p/x &model
p/x &images
source cpp/torch_inspect.py
python model_type = lambda pointer: pointer["type_"]["type_"]["repr_"]["_M_ptr"].cast(debug_type("c10::ClassType").pointer())
torch-tensor images
set $root = model._ivalue_.target_
torch-slots $root
torch-attr $root features
set $features = $torch_object
torch-slots $features
torch-attr $features 0
set $conv = $torch_object
torch-slots $conv
torch-attr $conv weight
torch-tensor *$torch_tensor
set $weight_data = (float*)$torch_data + $torch_offset
p/x $weight_data
x/8fw $weight_data
x/8xw $weight_data
torch-attr $root classifier
set $classifier = $torch_object
torch-slots $classifier
printf "GDB_CORE_INSPECTION_PASS\n"
