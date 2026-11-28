import copy
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import apex_hyper_metadata as m
import apex_foundation_registry as registry
import apex_sdk


class HyperReceiverTests(unittest.TestCase):
    def setUp(self):
        _, schemas = registry.load_registry()
        self.schema = schemas["hyper-metadata.v1"]
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        texts = ['const REVISION := "synthetic_fixture"\nconst STEP_S := 0.2\n'
                 'const MAX_PREVIEWS := 128\nconst ROUNDING_TOLERANCE_M := 0.001\n',
                 'const MAX_MPS := 100.0\n', 'extends SceneTree\n']
        for path, text in zip(m.PATHS, texts):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.rev = self.git("rev-parse", "HEAD")
        sources = []
        for path in m.PATHS:
            raw = (self.root / path).read_bytes()
            sources.append({"path": path, "git_blob": self.git("rev-parse", "HEAD:" + path),
                            "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        body = {"contract": "hyper-metadata.v1", "engine": "hyper",
                "scope": "isolated-longitudinal-lab", "revision": self.rev,
                "sources": sources, "parameters": {"adapter_revision": "synthetic_fixture",
                "step_us": 200000, "max_previews": 128,
                "rounding_tolerance_um": 1000, "max_speed_mps": 100}}
        self.report = {"body": body, "body_sha256": m.digest(body)}

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args]).decode().strip()

    def verify(self, report=None, rev=None):
        return m.verify(self.report if report is None else report, self.schema,
                        self.rev if rev is None else rev, self.root)

    def mutate(self, fn):
        report = copy.deepcopy(self.report)
        fn(report["body"])
        report["body_sha256"] = m.digest(report["body"])
        return report

    def test_exact_projection_and_boundary(self):
        result = self.verify()
        self.assertEqual(result, self.verify())
        self.assertTrue(result["source_bytes_verified"])
        for key in ("native_runtime_verified", "sporting_parity_verified",
                    "runtime_applied", "content_imported", "execution_authorized"):
            self.assertFalse(result[key])

    def test_wrong_revision_and_checksum(self):
        for revision in ("main", "0" * 40):
            with self.assertRaises(ValueError):
                self.verify(rev=revision)
        with self.assertRaises(ValueError):
            self.verify(dict(self.report, body_sha256="0" * 64))

    def test_forged_parameters_with_recomputed_digest(self):
        for key, value in (("step_us", 1), ("max_speed_mps", 99),
                           ("adapter_revision", "forged"), ("rounding_tolerance_um", 2),
                           ("max_previews", 1)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.verify(self.mutate(lambda b: b["parameters"].update({key: value})))

    def test_closed_schema_and_types(self):
        for fn in (lambda b: b.update(runtime_applied=True),
                   lambda b: b.update(engine="core2"),
                   lambda b: b["parameters"].update(step_us=True),
                   lambda b: b["parameters"].update(step_us=0),
                   lambda b: b["sources"].reverse(),
                   lambda b: b["sources"][0].update(path="../outside"),
                   lambda b: b["sources"][0].update(size_bytes=9999999)):
            with self.subTest(fn=fn), self.assertRaises(ValueError):
                self.verify(self.mutate(fn))

    def test_worktree_tampering(self):
        p = self.root / m.PATHS[0]
        p.write_bytes(p.read_bytes() + b"\n")
        with self.assertRaises(ValueError):
            self.verify()

    def test_nested_symlink(self):
        p = self.root / m.PATHS[0]
        d = p.parent
        moved = d.with_name("moved")
        d.rename(moved)
        d.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.verify()

    def test_git_env_cannot_redirect(self):
        with patch.dict(os.environ, {"GIT_DIR": "/nonexistent", "GIT_WORK_TREE": "/nonexistent"}):
            self.assertTrue(self.verify()["source_bytes_verified"])

    def test_replacement_ref_rejected(self):
        p = self.root / m.PATHS[0]
        old = p.read_bytes()
        p.write_bytes(old + b"\n")
        self.git("add", ".")
        self.git("commit", "-qm", "replacement")
        replacement = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "--detach", self.rev)
        self.git("replace", self.rev, replacement)
        self.assertTrue(self.verify()["source_bytes_verified"])
        p.write_bytes(old + b"\n")
        with self.assertRaises(ValueError):
            self.verify()

    def test_unsupported_and_duplicate_declarations(self):
        for text in ("const MAX_MPS := NAN", "const MAX_MPS := 1+2",
                     "const MAX_MPS := 100\nconst MAX_MPS := 100"):
            with self.assertRaises(ValueError):
                m.scaled(text, "MAX_MPS", 1)

    def test_duplicate_json_and_nonfinite(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}'):
            with self.assertRaises(ValueError):
                m.parse(raw)

    def test_sdk_boundary(self):
        sdk = apex_sdk.FoundationSDK()
        result = sdk.call("integration.hyper-contract")
        self.assertEqual(result["response"]["status"], "PASS")
        self.assertEqual(result["result"]["native_readiness"], "BLOCKED")
        self.assertEqual(sdk.call("integration.hyper-verify")["response"]["status"], "BLOCKED")
        self.assertEqual(sdk.call("integration.hyper-verify", profile="planner")["response"]["status"], "BLOCKED")
