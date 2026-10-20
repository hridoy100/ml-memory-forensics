# A bounded native sample, not a complete forward-pass call trace.
set pagination off
set confirm off
set debuginfod enabled off
set breakpoint pending on
break main.cpp:91
run
python print("Live reproduction PID:", gdb.selected_inferior().pid)
printf "\nStopped before the C++ model forward pass:\n"
bt 5
disable 1
python
import re
symbols = gdb.execute("info functions at::native::convolution", to_string=True)
addresses = []
for line in symbols.splitlines():
    match = re.match(r"(0x[0-9a-fA-F]+)\s+at::native::convolution\(", line)
    if match and "@plt" not in line:
        addresses.append(match.group(1))
if len(addresses) != 1:
    raise gdb.GdbError(f"Expected one native convolution implementation, got {addresses}")
gdb.Breakpoint("*" + addresses[0])
print("Native implementation address:", addresses[0])
end
continue
printf "\nSample native operator call during model.forward:\n"
bt 18
info symbol $pc
printf "\nInstructions at the stopped native entry:\n"
x/12i $pc
printf "\nLoaded CPU runtime:\n"
info sharedlibrary libtorch_cpu
python
frame = gdb.newest_frame()
names = []
while frame:
    names.append(frame.name() or "")
    frame = frame.older()
if not any("at::native::" in name and "convolution" in name for name in names):
    raise gdb.GdbError("Expected native convolution breakpoint was not reached")
if "@plt" in names[0]:
    raise gdb.GdbError("Stopped at a PLT stub rather than the implementation")
print("NATIVE_FORWARD_SAMPLE_PASS")
end
kill
