"""Export a PyTorch ABI profile using GDB's retained C++ debug types.

Run with GDB's ``source`` command, not with normal Python. Set
PYTORCH_LAYOUT_METADATA and PYTORCH_LAYOUT_OUTPUT to JSON file paths first.
No inferior needs to be running; this script never calls inferior functions.
"""

import json
import os
import re
from pathlib import Path

import gdb


def offset(type_name, path):
    value = gdb.Value(0).cast(gdb.lookup_type(type_name).pointer()).dereference()
    for field in path.split("."):
        value = value[field]
    return int(value.address)


def enum(type_name):
    return {
        str(field.enumval): field.name.rsplit("::", 1)[-1]
        for field in gdb.lookup_type(type_name).fields()
    }


fields = {
    "object_type": ("c10::ivalue::Object", "type_.type_.repr_._M_ptr"),
    "object_slots": ("c10::ivalue::Object", "slots_"),
    "object_cu": (
        "c10::ivalue::Object",
        "type_.cu_.strong_ptr_._M_payload._M_payload._M_value._M_ptr",
    ),
    "object_cu_engaged": (
        "c10::ivalue::Object",
        "type_.cu_.strong_ptr_._M_payload._M_engaged",
    ),
    "class_name": (
        "c10::ClassType",
        "name_._M_payload._M_payload._M_value.qualifiedName_",
    ),
    "class_attributes": ("c10::ClassType", "attributes_"),
    "class_constants_names": ("c10::ClassType", "constantNames_"),
    "class_constants_values": ("c10::ClassType", "constantValues_"),
    "class_methods": ("c10::ClassType", "methods_"),
    "attribute_kind": ("c10::ClassAttribute", "kind_"),
    "attribute_name": ("c10::ClassAttribute", "attributeName_"),
    "ivalue_tag": ("c10::IValue", "tag"),
    "tensor_storage": ("c10::TensorImpl", "storage_.storage_impl_.target_"),
    "tensor_rank": ("c10::TensorImpl", "sizes_and_strides_.size_"),
    "tensor_sizes": ("c10::TensorImpl", "sizes_and_strides_.inlineStorage_"),
    "tensor_offset": ("c10::TensorImpl", "storage_offset_"),
    "tensor_numel": ("c10::TensorImpl", "numel_"),
    "tensor_dtype": ("c10::TensorImpl", "data_type_.index_"),
    "storage_data": ("c10::StorageImpl", "data_ptr_.ptr_.data_"),
    "storage_device": ("c10::StorageImpl", "data_ptr_.device_.type_"),
    "storage_nbytes": ("c10::StorageImpl", "size_bytes_.data_"),
    "list_values": ("c10::detail::ListImpl", "list"),
    "string_value": ("c10::ivalue::ConstantString", "str_"),
    "tuple_inline_size": ("c10::ivalue::Tuple", "elements_.inlineSize_"),
    "tuple_values": ("c10::ivalue::Tuple", "elements_.elementsInline_"),
    "function_name": ("torch::jit::GraphFunction", "name_.qualifiedName_"),
    "function_graph": ("torch::jit::GraphFunction", "graph_._M_ptr"),
    "cu_functions": ("torch::jit::CompilationUnit", "functions_"),
    "graph_block": ("torch::jit::Graph", "block_"),
    "block_output": ("torch::jit::Block", "output_"),
    "block_input": ("torch::jit::Block", "input_"),
    "node_kind": ("torch::jit::Node", "kind_.value"),
    "node_inputs": ("torch::jit::Node", "inputs_"),
    "node_outputs": ("torch::jit::Node", "outputs_"),
    "node_blocks": ("torch::jit::Node", "blocks_"),
    "node_next": ("torch::jit::Node", "next_in_graph"),
    "node_source": (
        "torch::jit::Node",
        "source_range_._M_payload._M_payload._M_value.source_view_._M_ptr",
    ),
    "node_source_engaged": ("torch::jit::Node", "source_range_._M_payload._M_engaged"),
    "node_source_start": (
        "torch::jit::Node",
        "source_range_._M_payload._M_payload._M_value.start_",
    ),
    "node_source_end": (
        "torch::jit::Node",
        "source_range_._M_payload._M_payload._M_value.end_",
    ),
    "value_name": ("torch::jit::Value", "unique_name_"),
    "value_id": ("torch::jit::Value", "unique_"),
    "source_pieces": ("torch::jit::Source", "text_view_.pieces_"),
    "source_filename": (
        "torch::jit::Source",
        "filename_._M_payload._M_payload._M_value",
    ),
    "source_filename_engaged": (
        "torch::jit::Source",
        "filename_._M_payload._M_engaged",
    ),
    "source_starting_line": ("torch::jit::Source", "starting_line_no_"),
}

metadata = json.loads(Path(os.environ["PYTORCH_LAYOUT_METADATA"]).read_text())
profile = {
    "schema": 1,
    "metadata": metadata,
    "pointer_size": gdb.lookup_type("void").pointer().sizeof,
    "byteorder": "little",
    "offsets": {key: offset(*spec) for key, spec in fields.items()},
    "sizes": {
        "ivalue": gdb.lookup_type("c10::IValue").sizeof,
        "attribute": gdb.lookup_type("c10::ClassAttribute").sizeof,
        "string": gdb.lookup_type("std::string").sizeof,
        "tensor_impl": gdb.lookup_type("c10::TensorImpl").sizeof,
    },
    "tags": enum("c10::IValue::Tag"),
    "attribute_kinds": enum("c10::AttributeKind"),
}
# Built-in Symbol IDs come from the matching header, not a different release.
header = Path(metadata["torch_include"]) / "ATen/core/interned_strings.h"
pairs = re.findall(r"^\s*_\((\w+),\s*(\w+)\)", header.read_text(), re.MULTILINE)
profile["symbols"] = {str(i): f"{ns}::{name}" for i, (ns, name) in enumerate(pairs)}
Path(os.environ["PYTORCH_LAYOUT_OUTPUT"]).write_text(
    json.dumps(profile, indent=2) + "\n"
)
gdb.write(f"Exported {len(fields)} offsets and {len(pairs)} symbols.\n")
