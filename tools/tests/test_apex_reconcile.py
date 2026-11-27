import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import apex_sdk as sdk
import apex_reconcile as q
import apex_foundation_registry as r

class ReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sdk=sdk.FoundationSDK()
        cls.audit=cls.sdk._service("reconciliation")
        cls.docs=[r.read(q.DOCS/n) for n in ("reconciliation.json","corrections.json","native-ci.json","candidates.json")]
        cls.expected,cls.upstream=q.collect_inventory()

    def build(self,index,mutate):
        docs=copy.deepcopy(self.docs)
        mutate(docs[index])
        return q.Reconciliation(self.sdk._schemas,self.sdk._snapshots,self.sdk._service("architecture"),
                                *docs,self.expected,self.upstream)

    def test_stats_and_correction(self):
        x=self.audit.stats()
        self.assertEqual(x["status"],"PASS")
        self.assertEqual(x["pairs"],85)
        self.assertEqual(x["counts"],{"BASELINE_MISMATCH":1,"CHANGED":9,"UNCHANGED":75})
        self.assertEqual(len(x["corrections"]),1)
        self.assertEqual(x["unresolved"],[])
        self.assertFalse(x["pins_changed"])
        self.assertEqual(x["native_readiness"],"BLOCKED")

    def test_path_coverage(self):
        with self.assertRaises(ValueError):
            self.build(0,lambda doc:doc["entries"][0]["paths"].pop())
        with self.assertRaises(ValueError):
            self.build(0,lambda doc:doc["entries"][0]["paths"].append(doc["entries"][0]["paths"][0]))

    def test_state_recomputation(self):
        with self.assertRaises(ValueError):
            self.build(0,lambda doc:doc["entries"][0]["paths"][0].update(state="MISSING"))

    def test_stale_candidate(self):
        with self.assertRaises(ValueError):
            self.build(0,lambda doc:doc["entries"][1].update(candidate="0"*40))

    def test_corrected_pointer_required(self):
        with self.assertRaises(ValueError):
            self.build(1,lambda doc:doc["entries"].clear())
        with self.assertRaises(ValueError):
            self.build(1,lambda doc:doc["entries"][0].update(after="0"*40))

    def test_unchanged_revision_integrity(self):
        with self.assertRaises(ValueError):
            self.build(0,lambda doc:doc["entries"][2].update(candidate_tree="0"*40))

    def test_native_observations(self):
        x=self.audit.native_report()
        self.assertEqual(x["counts"],{"PASS":5})
        self.assertFalse(x["native_adapter_verified"])
        self.assertEqual(self.audit.native["hyper-game"]["status"],"PASS")

    def test_native_scope_and_marker_checks(self):
        for changes in ({"revision":"0"*40},{"markers":[]},{"scope":"HYPER_ISOLATED_LAB"},{"job_url":"https://example.org"}):
            with self.assertRaises(ValueError):
                self.build(2,lambda doc:doc["entries"][0].update(changes))
        with self.assertRaises(ValueError):
            self.build(2,lambda doc:doc["entries"][2].update(status="PASS",markers=["HYPER_FIXTURE"]))

    def test_hyper_candidates(self):
        x=self.audit.candidate_report()
        self.assertEqual(len(x["entries"]),11)
        self.assertFalse(x["implementation_audited"])
        with self.assertRaises(ValueError):
            self.build(3,lambda doc:doc["entries"][0].update(path="../private"))
        with self.assertRaises(ValueError):
            self.build(3,lambda doc:doc["entries"][0].update(revision="0"*40))

    def test_gateway_and_detachment(self):
        x=self.sdk.call("integration.reconcile")
        self.assertEqual(x["response"]["status"],"PASS")
        x["result"]["corrections"].clear()
        self.assertEqual(len(self.sdk.call("integration.reconcile")["result"]["corrections"]),1)
        self.assertEqual(self.sdk.call("integration.native-evidence")["response"]["status"],"NOT_RUN")
        self.assertEqual(self.sdk.call("integration.candidates")["response"]["status"],"NOT_RUN")

if __name__=="__main__":
    unittest.main()
