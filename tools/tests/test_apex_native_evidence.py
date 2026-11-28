import copy
import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import warnings
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import apex_native_evidence as m
import apex_foundation_registry as r
import apex_hyper_metadata as h
import apex_sdk


class NativeArchiveTests(unittest.TestCase):
    def setUp(self):
        _, self.schemas = r.load_registry()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "evidence.zip"
        self.revision = "a" * 40
        self.params = {"adapter_revision": "synthetic_fixture", "step_us": 200000,
                       "max_previews": 128, "rounding_tolerance_um": 1000, "max_speed_mps": 100}
        body = {"contract": "hyper-metadata.v1", "engine": "hyper",
                "scope": "isolated-longitudinal-lab", "revision": self.revision,
                "sources": [{"path": p, "git_blob": "b" * 40, "size_bytes": 10,
                             "sha256": "c" * 64} for p in h.PATHS], "parameters": self.params}
        self.report = {"body": body, "body_sha256": h.digest(body)}
        self.log = "HYPER22_LONGITUDINAL_PASS checks=24\nHYPER_METADATA_NATIVE " + json.dumps(self.params) + "\n"
        self.receipt = {"contract": "native-artifact-receipt.v1", "repository": "Jugadru/APEX-Hyper-Engine",
                        "scope": "HYPER_ISOLATED_LAB", "revision": self.revision, "event": "push",
                        "run_id": 1, "attempt": 1, "artifact_id": 2, "size_bytes": 1,
                        "sha256": "d" * 64, "body_sha256": self.report["body_sha256"], "native_checks": 24}
        self.write()

    def write(self, report=None, log=None, extra=(), compression=zipfile.ZIP_DEFLATED):
        entries = [("hyper-metadata.json", json.dumps(self.report if report is None else report)),
                   ("hyper-fast.log", self.log if log is None else log)] + list(extra)
        with zipfile.ZipFile(self.path, "w", compression=compression) as z:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                for name, data in entries:
                    z.writestr(name, data)
        self.rehash()

    def rehash(self):
        raw = self.path.read_bytes()
        self.receipt.update(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

    def check(self, receipt=None, revision=None):
        return m.verify(self.receipt if receipt is None else receipt, self.path,
                        self.revision if revision is None else revision, self.schemas)

    def test_consistent_archive_does_not_authorize(self):
        result = self.check()
        self.assertEqual(result, self.check())
        self.assertTrue(result["archive_bytes_verified"])
        self.assertTrue(result["crc_verified"])
        for key in ("receipt_authenticity_verified", "live_attestation", "source_checkout_verified",
                    "native_runtime_executed", "sporting_parity_verified", "execution_authorized", "release_authorized"):
            self.assertFalse(result[key])

    def test_digest_and_length(self):
        for change in ({"sha256": "0"*64}, {"size_bytes": 1}):
            with self.assertRaises(ValueError):
                self.check(dict(self.receipt, **change))

    def test_scope_revision_and_closed_fields(self):
        for change in ({"scope": "CORE2_FAST_PUSH"}, {"repository": "Other/Repo"},
                       {"revision": "b"*40}, {"release_authorized": True}, {"attempt": 0},
                       {"native_checks": True}):
            with self.assertRaises(ValueError):
                self.check(dict(self.receipt, **change))
        with self.assertRaises(ValueError):
            self.check(revision="main")

    def test_wrong_embedded_revision(self):
        report = copy.deepcopy(self.report)
        report["body"]["revision"] = "b"*40
        report["body_sha256"] = h.digest(report["body"])
        self.write(report=report)
        with self.assertRaises(ValueError):
            self.check(dict(self.receipt, body_sha256=report["body_sha256"]))

    def test_native_marker_and_parameters(self):
        for log in ("", self.log.replace("checks=24", "checks=23"),
                    self.log + self.log, self.log + "SCRIPT ERROR: fixture\n",
                    self.log.replace('"max_previews": 128', '"max_previews": 129')):
            self.write(log=log)
            with self.assertRaises((ValueError, zipfile.BadZipFile)):
                self.check()

    def test_member_paths_and_duplicates(self):
        for name in ("../secret", "hyper-fast.log", "other.log"):
            self.write(extra=[(name, "bad")])
            with self.assertRaises(ValueError):
                self.check()

    def test_crc_even_with_rehashed_archive(self):
        self.write(compression=zipfile.ZIP_STORED)
        raw = self.path.read_bytes()
        self.assertIn(b"HYPER22_LONGITUDINAL_PASS", raw)
        self.path.write_bytes(raw.replace(b"HYPER22_LONGITUDINAL_PASS", b"XYPER22_LONGITUDINAL_PASS", 1))
        self.rehash()
        with self.assertRaises((zipfile.BadZipFile, ValueError)):
            self.check()

    def test_zip_bomb_and_unsupported_compression(self):
        self.write(log="x"*(m.MAX_ENTRY+1))
        with self.assertRaises(ValueError):
            self.check()
        self.write(compression=zipfile.ZIP_BZIP2)
        with self.assertRaises(ValueError):
            self.check()

    def test_gateway_blocks_local_archive_paths(self):
        sdk = apex_sdk.FoundationSDK()
        for profile in ("reader", "planner"):
            self.assertEqual(sdk.call("evidence.native-archive-verify", profile=profile)["response"]["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
