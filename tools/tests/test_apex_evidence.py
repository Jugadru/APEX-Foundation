import copy
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import apex_evidence as e
import apex_foundation_registry as r

class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e=e.load()
        cls.docs=[r.read(e.DOCS/name) for name in ("ci-receipts.json","artifacts.json","benchmarks.json","notes.json")]

    def build(self,index=None,mutate=None,root=e.ROOT):
        docs=copy.deepcopy(self.docs)
        if mutate:
            mutate(docs[index])
        return e.Evidence(*docs,self.e.schemas,root=root)

    def test_timestamp_exact_fraction(self):
        base="2026-11-27T02:06:56"
        self.assertLess(e.timestamp(base+"Z"),e.timestamp(base+".0000001Z"))
        self.assertLess(e.timestamp(base+".7631184Z"),e.timestamp(base+".7631185Z"))
        self.assertEqual(e.timestamp(base+".1Z"),e.timestamp(base+".100000000000000000Z"))
        self.assertLess(e.timestamp(base+".999999999999999999Z"),e.timestamp("2026-11-27T02:06:57Z"))

    def test_invalid_timestamp(self):
        for invalid in ("2026-02-30T00:00:00Z","2026-11-27T24:00:00Z",
                        "2026-11-27T00:00:60Z","2026-11-27T00:60:00Z","2026-11-27T25:00:00Z",
                        "2026-11-27T00:00:00+00:00","0000-11-27T00:00:00Z",
                        "2026-11-27T00:00:00.Z","2026-11-27T00:00:00.1234567890123456789Z",None):
            with self.subTest(value=invalid),self.assertRaises(ValueError):
                e.timestamp(invalid)

    def test_receipt_submicrosecond_order(self):
        def mutate(doc):
            row=doc["entries"][0]
            row["markers"]=["2026-11-27T02:06:56.0000002Z Python 3.14.4",
                            "2026-11-27T02:06:56.0000001Z Ran 12 tests in 0.027s",
                            "2026-11-27T02:06:56.0000003Z OK"]
        with self.assertRaisesRegex(ValueError,"receipt time ordering"):
            self.build(0,mutate)

    def test_receipt_history_chronological_not_lexical(self):
        def mutate(doc):
            first,second=doc["entries"][:2]
            first["observed_at"]="2026-11-27T02:30:00.1Z"
            second["observed_at"]="2026-11-27T02:30:00Z"
        entries=self.build(0,mutate).history()["entries"]
        ids=[row["id"] for row in entries]
        self.assertLess(ids.index("v0.1.1"),ids.index("v0.1.0"))

    def test_stats(self):
        s=self.e.stats()
        self.assertEqual((s["receipts"],s["artifacts"],s["benchmarks"],s["notes"]),(14,1,3,2))
        self.assertEqual(s["status"],"PASS")
        self.assertFalse(s["live_attestation"])
        self.assertEqual(s["fingerprint"],e.load().fingerprint)

    def test_history(self):
        h=self.e.history()["entries"]
        self.assertEqual([x["test_count"] for x in h],[12,24,34,46,60,72,85,85,97,97,111,111,125,125])
        self.assertTrue(all(x["scope"]=="FOUNDATION_PYTHON_ONLY" for x in h))

    def test_exact_revision_gate(self):
        x=self.e.gate(self.e.receipts["v0.3.0-main"]["revision"])
        self.assertEqual(x["historical_receipts"],["v0.3.0-main"])
        self.assertEqual(x["status"],"BLOCKED")
        self.assertFalse(x["release_authorized"])
        self.assertIn("NO_EXACT_REVISION_RECEIPT",self.e.gate("0"*40)["reasons"])
        with self.assertRaises(ValueError):
            self.e.gate("latest")

    def test_receipt_tampering(self):
        for change in ({"test_count":999},{"run_url":"https://example.org"},{"conclusion":"failure"},
                       {"markers":["OK"]},{"observed_at":"2020-01-01T00:00:00Z"},{"attempt":0}):
            with self.assertRaises(ValueError):
                self.build(0,lambda x:x["entries"][0].update(change))

    def test_duplicate_receipt_identity(self):
        def mutate(doc):
            row=copy.deepcopy(doc["entries"][0])
            row["id"]="other.receipt"
            doc["entries"].append(row)
        with self.assertRaises(ValueError):
            self.build(0,mutate)

    def test_artifact_integrity(self):
        x=self.e.verify("fixture.bytes")
        self.assertEqual(x["status"],"PASS")
        self.assertFalse(x["execution_verified"])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=root/"data/evidence/fixture.txt"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"abd")
            self.assertEqual(self.build(root=root).verify("fixture.bytes")["status"],"FAIL")
            path.unlink()
            path.symlink_to(e.ROOT/"data/evidence/fixture.txt")
            with self.assertRaises(ValueError):
                self.build(root=root).verify("fixture.bytes")

    def test_artifact_path_status(self):
        for change in (lambda x:x["entries"][0].update(path="../secret"),
                       lambda x:x["entries"][0]["artifact"].update(status="PASS")):
            with self.assertRaises(ValueError):
                self.build(1,change)

    def test_benchmark_comparison(self):
        x=self.e.compare("demo.baseline","demo.candidate")
        self.assertEqual(x["delta_percent"],{"numerator":10,"denominator":1})
        self.assertEqual(x["direction"],"SLOWER")
        self.assertFalse(x["real_regression_verified"])
        self.assertEqual(self.e.compare("demo.baseline","demo.other-host")["status"],"BLOCKED")

    def test_invalid_benchmark(self):
        for samples in ([0,1,2],[True,1,2],[1,2],[1,2,3,4]):
            with self.assertRaises(ValueError):
                self.build(2,lambda x:x["entries"][0].update(samples=samples))
        with self.assertRaises(ValueError):
            self.e.compare("demo.baseline","demo.baseline")

    def test_notes(self):
        with self.assertRaises(ValueError):
            self.build(3,lambda x:x["entries"][0].update(status="PASS"))
        with self.assertRaises(ValueError):
            self.build(3,lambda x:x["entries"][1].update(revision="0"*40))

    def test_show(self):
        self.assertEqual(self.e.show("v0.3.0-main")["record"]["test_count"],85)
        self.assertFalse(self.e.show("fixture.bytes")["release_authorized"])
        with self.assertRaises(KeyError):
            self.e.show("unknown")

if __name__=="__main__":
    unittest.main()
