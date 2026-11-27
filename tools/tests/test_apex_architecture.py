import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import apex_architecture as a
import apex_foundation_registry as r
import apex_knowledge as k

class ArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arch=a.load()
        cls.example=r.read(a.DOCS/"change.example.json")

    def test_coverage(self):
        s=self.arch.stats()
        self.assertEqual((s["modules"],s["capabilities"],s["active_contracts"],s["deferred_contracts"]),(21,37,18,10))
        self.assertEqual(s["pinned_external_repositories"],3)
        self.assertEqual(s["candidate_contract_bindings"],28)
        self.assertFalse(s["runtime_verified"])
        self.assertEqual(s["fingerprint"],a.load().fingerprint)

    def test_topological(self):
        graph=self.arch.graph()
        order=graph["dependency_first_order"]
        self.assertEqual(len(order),len(set(order)))
        for edge in graph["edges"]:
            self.assertLess(order.index(edge["dependency"]),order.index(edge["consumer"]))
        self.assertEqual(self.arch.show("core2")["direct_dependents"],["presentation","replay","saveguard"])

    def test_transitive_and_cycle(self):
        arch=copy.deepcopy(self.arch)
        arch.deps["foundation"]={"asset-factory"}
        with self.assertRaises(ValueError):
            arch.topological()
        self.assertEqual(a.Architecture.closure(["a"],{"a":{"b"},"b":{"c"}}),["b","c"])

    def test_consumer_impact(self):
        p=self.arch.impact(self.example)
        self.assertEqual(p["status"],"BLOCKED")
        self.assertIn("DEFERRED_RUNTIME_CONTRACT",p["reasons"])
        self.assertIn("CONSUMER_VALIDATION_REQUIRED",p["reasons"])
        self.assertIn("core2",p["direct_modules"])
        self.assertIn("hyper",p["contract_participants_proposed"])
        self.assertIn("saveguard",p["declared_downstream"])
        self.assertFalse(p["execution_authorized"])
        self.assertTrue(all(x["status"]=="NOT_RUN" for x in p["validation"]))

    def test_stale_unmapped_and_unsafe(self):
        p=self.arch.impact(dict(self.example,base_revision="0"*40,paths=["scripts/unknown.gd"]))
        self.assertIn("STALE_OR_UNKNOWN_REVISION",p["reasons"])
        self.assertIn("UNMAPPED_PATHS",p["reasons"])
        for path in ("../secret","/tmp/file","scripts//x.gd","scripts\\x.gd","https://example.com/a"):
            with self.assertRaises(ValueError):
                self.arch.impact(dict(self.example,paths=[path]))

    def test_foundation_gate(self):
        report=self.arch.gate(r.read(a.DOCS/"change.foundation.example.json"))
        self.assertEqual(report["status"],"NOT_RUN")
        self.assertFalse(report["execution_authorized"])
        self.assertIn("asset-factory",report["impact"]["declared_downstream"])

    def test_cross_repository_module_gate(self):
        manifest=r.read(a.DOCS/"change.foundation.example.json")
        report=self.arch.gate(dict(manifest,modules=["core2"]))
        self.assertEqual(report["status"],"BLOCKED")
        self.assertIn("MODULE_REPOSITORY_MISMATCH",report["reasons"])
        self.assertEqual(report["impact"]["foreign_declared_modules"],["core2"])

    def test_invalid_manifest(self):
        for change in ({"extra":True},{"modules":["missing"]},{"contracts":["missing"]},{"paths":["a","a"]},
                       {"paths":[],"modules":[],"contracts":[]}):
            with self.assertRaises(ValueError):
                self.arch.impact(dict(self.example,**change))

    def test_contract_diff(self):
        report=self.arch.contract_diff()
        self.assertEqual(report["status"],"PASS")
        self.assertEqual(sum(x["state"]=="UNCHANGED" for x in report["contracts"]),15)
        self.assertEqual(sum(x["state"]=="ADDED" for x in report["contracts"]),3)
        arch=copy.deepcopy(self.arch)
        arch.schemas["module.v1"]["properties"]["name"]["minLength"]=2
        self.assertEqual(arch.contract_diff()["status"],"BLOCKED")
        del arch.schemas["artifact.v1"]
        self.assertTrue(any(x["state"]=="REMOVED" for x in arch.contract_diff()["contracts"]))

    def test_inventory(self):
        for (repo,path),item in self.arch.paths.items():
            self.assertTrue(a.valid_path(path))
            self.assertTrue(a.sha(item["blob_sha"]))
            self.assertTrue(set(item["modules"])<=self.arch.modules.keys())
        self.assertIn(("hyper","README.md"),self.arch.paths)
        self.assertIn(("lab","tools/advanced_gdscript_analyzer.py"),self.arch.paths)

    def test_invalid_ownership_and_inventory(self):
        reg,schemas=r.load_registry()
        own=r.read(a.DOCS/"ownership.json")
        inv=r.read(a.DOCS/"source-inventory.json")
        baseline=r.read(a.DOCS/"contract-baseline.json")
        for mutate in (
            lambda o,i:o["modules"].pop(),
            lambda o,i:next(x for x in o["modules"] if x["id"]=="presentation").update(role="sporting-authority"),
            lambda o,i:o["contracts"][0].update(steward="missing"),
            lambda o,i:i["repositories"][0]["paths"][0].update(path="../escape"),
            lambda o,i:i["repositories"][0]["paths"][0].update(modules=["hyper"]),
        ):
            o,i=copy.deepcopy((own,inv))
            mutate(o,i)
            with self.assertRaises(ValueError):
                a.Architecture(reg,schemas,o,i,baseline)

if __name__=="__main__":
    unittest.main()
