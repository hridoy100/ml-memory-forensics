# Run from cifar10_cnn. The inferior stays stopped before forward.
# See ../docs/WALKTHROUGH.md and the historical GDB_INSPECTION.md.
set logging file outputs/gdb_inspection.log
set logging overwrite off
set logging enabled on
source cpp/torch_inspect.py
source cpp/inference.gdb

# The inferior is the inference program, not GDB or a shell subprocess.
info inferiors
python print("Inference PID:", gdb.selected_inferior().pid)

printf "\nStack objects and fields (hex):\n"
print /x &model
print /x &model._ivalue_
print /x &images
print /x &images.impl_

printf "\nInput tensor metadata and allocation:\n"
torch-tensor images

printf "\nRoot module attributes:\n"
set $root = model._ivalue_.target_
torch-slots $root

# Inspect the first convolution parameter without calling inferior functions.
printf "\nFirst convolution attributes and CPU weights:\n"
torch-attr $root features
set $features = $torch_object
torch-attr $features 0
set $conv = $torch_object
torch-slots $conv
torch-attr $conv weight
torch-tensor *$torch_tensor
set $weight_data = (float*)$torch_data + $torch_offset
print /x $weight_data
x/8fw $weight_data
x/8xw $weight_data
