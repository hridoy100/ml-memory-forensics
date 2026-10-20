"""Focused checks for the recovered-source replay helper."""

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

HAS_TORCH = importlib.util.find_spec("torch") is not None
if HAS_TORCH:
    import torch
    from forensics.confirm_recovery import Trace, build_recovered


@unittest.skipUnless(HAS_TORCH, "Replay checks require the target PyTorch environment")
class RecoveredSourceTests(unittest.TestCase):
    def fixture(self, directory, body):
        source = (
            "class Tiny(Module):\n"
            "  def forward(self: __torch__.fixture.Tiny, input: Tensor) -> Tensor:\n"
            + body
        ).encode()
        path = directory / "captured.py"
        path.write_bytes(source)
        return {
            "errors": [],
            "sources": [
                {
                    "file": path.name,
                    "original_filename": "code/__torch__/fixture.py",
                    "sha256": hashlib.sha256(source).hexdigest(),
                }
            ],
            "functions": [{"name": "__torch__.fixture.Tiny.forward"}],
            "tensors": [],
            "architecture": {
                "path": "",
                "type": "__torch__.fixture.Tiny",
                "constants": {},
                "attributes": [{"name": "training", "tag": "Bool", "value": False}],
            },
        }

    def test_recovered_body_is_executed_and_traced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = self.fixture(root, "    return torch.relu(input) + 2\n")
            trace = Trace()
            model, coverage = build_recovered(report, root, trace)
            trace.enabled = True
            torch.testing.assert_close(
                model.forward(torch.tensor([-1.0, 3.0])), torch.tensor([2.0, 5.0])
            )
            self.assertEqual(
                trace.calls[0]["function"], "__torch__.fixture.Tiny.forward"
            )
            self.assertEqual(coverage["unresolved_dependencies"], [])

    def test_changed_source_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = self.fixture(root, "    return input\n")
            (root / "captured.py").write_text(
                "raise RuntimeError('must not execute')\n"
            )
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                build_recovered(report, root, Trace())

    def test_missing_helper_via_local_alias_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = self.fixture(
                root,
                "    helper = __torch__.missing.helper\n    return helper(input)\n",
            )
            with self.assertRaisesRegex(ValueError, "Unresolved calls"):
                build_recovered(report, root, Trace())

    def test_cast_type_is_erased_without_changing_tensor_value(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = self.fixture(root, "    return unchecked_cast(Tensor, input)\n")
            model, _ = build_recovered(report, root, Trace())
            data = torch.tensor([1.0, 2.0])
            self.assertIs(model.forward(data), data)

    def test_missing_reported_definition_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = self.fixture(root, "    return input\n")
            report["functions"].append({"name": "__torch__.fixture.Tiny.missing"})
            with self.assertRaisesRegex(ValueError, "missing function definitions"):
                build_recovered(report, root, Trace())


if __name__ == "__main__":
    unittest.main()
