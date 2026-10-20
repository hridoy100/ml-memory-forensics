"""Replay this experiment's recovered TorchScript source as ordinary Python.

Only the recovery report, captured source files and captured tensor files build
the replay model. The original TorchScript model is loaded afterward, solely to
compare outputs. This is a small compatibility layer for this experiment, not
a general TorchScript interpreter. Run only with your trusted experiment files.
"""

import argparse
import ast
import csv
import functools
import hashlib
import json
import operator
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
import torch.nn.functional as functional


class Trace:
    def __init__(self):
        self.enabled = False
        self.calls = []
        self.operators = Counter()

    def wrap(self, function, name, method=False):
        @functools.wraps(function)
        def call(*args, **kwargs):
            if self.enabled:
                self.calls.append(
                    {
                        "function": name,
                        "module": (
                            getattr(args[0], "_recovery_path", None) if method else None
                        ),
                    }
                )
            return function(*args, **kwargs)

        return call


class TorchRuntime:
    """Lower the scalar and tensor intrinsics used in the recovered script."""

    def __init__(self, trace):
        self.trace = trace
        self.aliases = {
            "dim": lambda tensor: tensor.dim(),
            "size": lambda tensor: list(tensor.size()),
            "len": len,
            "format": lambda template, *args: template.format(*args),
            "__is__": operator.is_,
            "__isnot__": operator.is_not,
            "__not__": operator.not_,
            "linear": functional.linear,
            "add_": lambda tensor, value: tensor.add_(value),
            **{
                name: getattr(operator, name)
                for name in ("add", "sub", "mul", "eq", "ne", "lt", "le", "gt", "ge")
            },
        }

    def __getattr__(self, name):
        function = self.aliases.get(name)
        if function is None:
            function = getattr(torch, name)
        if not callable(function):
            raise ValueError(f"Unsupported recovered operation torch.{name}")

        def call(*args, **kwargs):
            if self.trace.enabled:
                self.trace.operators[f"torch.{name}"] += 1
            return function(*args, **kwargs)

        return call


def raise_exception(message, exception_name="builtins.RuntimeError"):
    exceptions = {
        "builtins.ValueError": ValueError,
        "builtins.RuntimeError": RuntimeError,
    }
    raise exceptions.get(exception_name, RuntimeError)(message)


def namespace(root, name):
    result = root
    for part in name.removeprefix("__torch__.").split("."):
        if not hasattr(result, part):
            setattr(result, part, SimpleNamespace())
        result = getattr(result, part)
    return result


class PythonSource(ast.NodeTransformer):
    """Erase annotations and identity casts; preserve recovered function bodies."""

    def visit_ClassDef(self, node):
        node.bases = []
        node.keywords = []
        node.decorator_list = []
        node.body = [
            self.visit(item) for item in node.body if isinstance(item, ast.FunctionDef)
        ]
        return node

    def visit_FunctionDef(self, node):
        node.returns = None
        node.decorator_list = []
        for argument in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            argument.annotation = None
        for argument in (node.args.vararg, node.args.kwarg):
            if argument:
                argument.annotation = None
        return self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id in (
            "annotate",
            "unchecked_cast",
        ):
            if len(node.args) != 2:
                raise ValueError("Unexpected recovered cast syntax")
            return ast.copy_location(self.visit(node.args[1]), node)
        return self.generic_visit(node)


def decoded(value):
    tag = value["tag"]
    if tag in ("Tuple", "GenericList"):
        result = [decoded(item) for item in value["value"]]
        return tuple(result) if tag == "Tuple" else result
    if tag in ("None", "Int", "UInt", "Double", "Bool", "String"):
        return value["value"]
    raise ValueError(f"Unsupported recovered value: {tag}")


def build_recovered(report, directory, trace):
    if report["errors"]:
        raise ValueError("Recovery report contains errors")
    root = SimpleNamespace()
    runtime = TorchRuntime(trace)
    classes, definitions, class_sources = {}, {}, {}
    native_calls, script_references = set(), set()
    for source in report["sources"]:
        path = directory / source["file"]
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != source["sha256"]:
            raise ValueError(f"Source checksum mismatch: {path}")
        original = source["original_filename"]
        if not original.startswith("code/__torch__/") or not original.endswith(".py"):
            raise ValueError(f"Unsupported source namespace: {original}")
        module_name = original.removeprefix("code/")[:-3].replace("/", ".")
        tree = ast.parse(data, filename=str(path))
        for item in ast.walk(tree):
            if isinstance(item, ast.Call):
                callee = ast.unparse(item.func)
                if callee.startswith("torch."):
                    native_calls.add(callee)
        if any(
            not isinstance(item, (ast.ClassDef, ast.FunctionDef)) for item in tree.body
        ):
            raise ValueError(f"Unexpected top-level code in {path}")
        env = {
            "__name__": module_name,
            "__torch__": root,
            "torch": runtime,
            "ops": SimpleNamespace(
                prim=SimpleNamespace(RaiseException=raise_exception)
            ),
        }
        tree = ast.fix_missing_locations(PythonSource().visit(tree))
        for item in ast.walk(tree):
            if isinstance(item, ast.Attribute):
                reference = ast.unparse(item)
                if reference.startswith("__torch__."):
                    script_references.add(reference)
        exec(compile(tree, str(path), "exec"), env)
        destination = namespace(root, module_name)
        for item in tree.body:
            qualified = f"{module_name}.{item.name}"
            if isinstance(item, ast.ClassDef):
                cls = env[item.name]
                classes[qualified] = cls
                class_sources[qualified] = source["file"]
                for method in item.body:
                    name = f"{qualified}.{method.name}"
                    definitions[name] = source["file"]
                    setattr(
                        cls,
                        method.name,
                        trace.wrap(getattr(cls, method.name), name, method=True),
                    )
                setattr(destination, item.name, cls)
            else:
                definitions[qualified] = source["file"]
                setattr(destination, item.name, trace.wrap(env[item.name], qualified))

    unresolved = []
    for name in sorted(script_references):
        value = root
        try:
            for part in name.removeprefix("__torch__.").split("."):
                value = getattr(value, part)
        except AttributeError:
            unresolved.append(name)
    for name in sorted(native_calls):
        if name.count(".") != 1:
            unresolved.append(name)
        else:
            try:
                getattr(runtime, name.split(".")[1])
            except (AttributeError, ValueError):
                unresolved.append(name)
    expected = {item["name"] for item in report["functions"]}
    missing = sorted(expected - set(definitions))
    if unresolved or missing:
        raise ValueError(
            f"Unresolved calls: {unresolved}; missing function definitions: {missing}"
        )

    state = {}
    for item in report["tensors"]:
        array = np.load(directory / item["file"], allow_pickle=False)
        if list(array.shape) != item["shape"] or str(array.dtype.str) != item["dtype"]:
            raise ValueError(f"Tensor metadata mismatch: {item['name']}")
        if hashlib.sha256(array.tobytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Tensor checksum mismatch: {item['name']}")
        state[item["name"]] = torch.from_numpy(array.copy())

    instances, layers = {}, []

    def module(record):
        if "reference" in record:
            return instances[record["reference"]]
        path, type_name = record["path"], record["type"]
        cls = classes[type_name]
        obj = cls()
        obj._recovery_path = path
        instances[path] = obj
        layers.append(
            {
                "path": path or "<root>",
                "type": type_name,
                "source": class_sources[type_name],
                "forward": f"{type_name}.forward",
            }
        )
        for name, value in record["constants"].items():
            setattr(obj, name, decoded(value))
        for attribute in record["attributes"]:
            name = attribute["name"]
            if attribute["tag"] == "Object":
                value = module(attribute["module"])
            elif attribute["tag"] == "Tensor":
                key = f"{path}.{name}" if path else name
                value = (
                    None
                    if attribute.get("status") == "Undefined tensor"
                    else state[key]
                )
            else:
                value = decoded(attribute)
            setattr(obj, name, value)
        if obj.training:
            raise ValueError(
                f"Expected the captured evaluation model, got training=True at {path}"
            )
        return obj

    model = module(report["architecture"])
    coverage = {
        "source_files_verified": len(report["sources"]),
        "tensor_files_verified": len(state),
        "layers": layers,
        "function_definitions": definitions,
        "reported_functions_found": len(expected),
        "unresolved_dependencies": unresolved,
        "runtime_operator_dependencies": sorted(native_calls),
        "replay_method": "Recovered source compiled as Python after annotation/cast erasure, using explicit TorchScript intrinsic adapters and the installed CPU PyTorch runtime.",
        "scope": "Static recovered definitions and observed first-batch evaluation calls. This is not all-branch coverage or native C++ kernel/source recovery.",
    }
    return model, coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--test-bin", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=128)
    args = parser.parse_args()
    if args.limit < 1 or args.batch_size < 1:
        parser.error("limit and batch-size must be positive")
    torch.set_num_threads(1)
    report = json.loads(args.report.read_text())
    trace = Trace()
    # Construction completes before the reference model is opened.
    model, coverage = build_recovered(report, args.report.parent, trace)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "code-coverage.json").write_text(
        json.dumps(coverage, indent=2) + "\n"
    )
    print(
        f"Recovered definitions found: {coverage['reported_functions_found']}/{len(report['functions'])}",
        flush=True,
    )
    print(
        f"Unresolved script/runtime dependencies: {len(coverage['unresolved_dependencies'])}",
        flush=True,
    )

    record_size = 3073
    file_size = args.test_bin.stat().st_size
    if not file_size or file_size % record_size:
        raise ValueError("Test file must contain complete 3073-byte CIFAR records")
    count = min(args.limit, file_size // record_size)
    records = np.fromfile(
        args.test_bin, dtype=np.uint8, count=count * record_size
    ).reshape(count, record_size)
    labels = records[:, 0].copy()
    if labels.max() >= 10:
        raise ValueError("Invalid CIFAR class label")
    images = torch.from_numpy(records[:, 1:].copy()).reshape(count, 3, 32, 32).float()
    images = (images / 255.0 - 0.5) / 0.5
    reference = torch.jit.load(str(args.reference), map_location="cpu").eval()
    actual_batches, expected_batches = [], []
    with torch.inference_mode():
        for start in range(0, count, args.batch_size):
            batch = images[start : start + args.batch_size]
            trace.enabled = start == 0
            actual_batches.append(model.forward(batch))
            trace.enabled = False
            expected_batches.append(reference(batch))
    actual, expected = torch.cat(actual_batches), torch.cat(expected_batches)
    if actual.shape != (count, 10) or expected.shape != actual.shape:
        raise ValueError("Unexpected output shape")
    predictions, reference_predictions = actual.argmax(1), expected.argmax(1)
    finite = bool(torch.isfinite(actual).all() and torch.isfinite(expected).all())
    close = finite and torch.allclose(actual, expected, rtol=1e-5, atol=1e-5)
    agreement = int((predictions == reference_predictions).sum())
    forward_order = [
        item["module"]
        for item in trace.calls
        if item["module"] is not None and item["function"].endswith(".forward")
    ]
    expected_order = [
        "" if item["path"] == "<root>" else item["path"] for item in coverage["layers"]
    ]
    order_match = forward_order == expected_order
    passed = close and agreement == count and order_match
    result = {
        "passed": passed,
        "pid": report["pid"],
        "images_compared": count,
        "prediction_matches": agreement,
        "max_absolute_logit_difference": float((actual - expected).abs().max()),
        "logits_allclose": close,
        "rtol": 1e-5,
        "atol": 1e-5,
        "finite_logits": finite,
        "first_batch_forward_order_matches_recovered_tree": order_match,
        "first_batch_forward_order": forward_order,
        "first_batch_function_calls": trace.calls,
        "first_batch_runtime_operator_calls": dict(trace.operators),
        "recovered_accuracy": float((predictions.numpy() == labels).mean()),
        "reference_accuracy": float((reference_predictions.numpy() == labels).mean()),
        "torch_version": torch.__version__,
        "torch_git_version": torch.version.git_version,
        "reference_sha256": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
        "test_bin_sha256": hashlib.sha256(args.test_bin.read_bytes()).hexdigest(),
        "recovery_report_sha256": hashlib.sha256(args.report.read_bytes()).hexdigest(),
        "scope": coverage["scope"],
    }
    (args.output_dir / "inference-comparison.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    np.save(args.output_dir / "recovered-logits.npy", actual.numpy())
    np.save(args.output_dir / "reference-logits.npy", expected.numpy())
    with (args.output_dir / "predictions.csv").open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "image_index",
                "label",
                "recovered_prediction",
                "reference_prediction",
                "match",
            ]
        )
        for i, (label, a, b) in enumerate(
            zip(labels, predictions.tolist(), reference_predictions.tolist())
        ):
            writer.writerow([i, int(label), a, b, a == b])
    print(f"Predictions matching: {agreement}/{count}")
    print(
        f"Maximum absolute logit difference: {result['max_absolute_logit_difference']:.9g}"
    )
    print(f"Logits within rtol=1e-5, atol=1e-5: {close}")
    print(f"Observed layer forward order matches recovered tree: {order_match}")
    print("INFERENCE_COMPARISON_PASS" if passed else "INFERENCE_COMPARISON_FAIL")
    print(args.output_dir / "inference-comparison.json")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
