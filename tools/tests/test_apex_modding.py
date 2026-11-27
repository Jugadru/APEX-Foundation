import copy
import io
import json
from pathlib import Path
import stat
import sys
import unittest
import warnings
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import apex_modding as m
import apex_foundation_registry as r

class ModdingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m=m.load()
        cls.cat=r.read(m.ROOT/"data/modding/catalog.json")
        cls.selection=r.read(m.DOCS/"selection.example.json")

    def build(self,mutate):
        cat=copy.deepcopy(self.cat)
        mutate(cat["entries"])
        return m.Modding(cat,self.m.schemas,self.m.registry)

    def select(self,*roots):
        return dict(self.selection,requested=[{"id":i,"version":v} for i,v in roots])

    def test_stats(self):
        s=self.m.stats()
        self.assertEqual((s["identities"],s["versions"],s["dependency_edges"],s["overlay_records"]),(6,7,6,7))
        self.assertFalse(s["runtime_installed"])
        self.assertEqual(s["fingerprint"],m.load().fingerprint)

    def test_dependency_order_and_immutable_preview(self):
        before=copy.deepcopy(self.m.registry.entries)
        p=self.m.plan(self.selection)
        self.assertEqual(p["status"],"NOT_RUN")
        order=[x["id"] for x in p["load_order"]]
        self.assertEqual(order,["demo.base","demo.circuit","demo.driver","demo.season"])
        self.assertEqual(len(p["preview"]),4)
        self.assertEqual(before,self.m.registry.entries)
        self.assertFalse(p["execution_authorized"])

    def test_explicit_and_overlay_conflicts(self):
        p=self.m.plan(r.read(m.DOCS/"conflict.example.json"))
        self.assertEqual(p["status"],"BLOCKED")
        self.assertEqual({x["code"] for x in p["reasons"]},{"EXPLICIT_CONFLICT","OVERLAY_CONFLICT"})
        self.assertEqual(p["preview"],[])

    def test_version_conflict_and_unknown(self):
        p=self.m.plan(self.select(("demo.driver","1.0.0"),("demo.season","1.0.0")))
        self.assertIn("VERSION_CONFLICT",{x["code"] for x in p["reasons"]})
        p=self.m.plan(self.select(("demo.driver","9.0.0")))
        self.assertEqual(p["reasons"][0]["code"],"MISSING_EXACT_MOD")

    def test_scope(self):
        p=self.m.plan(self.select(("demo.hyper","1.0.0")))
        self.assertIn("CONSUMER_SCOPE_MISMATCH",{x["code"] for x in p["reasons"]})
        p=self.m.plan(dict(self.selection,revision="0"*40))
        self.assertIn("STALE_CONSUMER_REVISION",{x["code"] for x in p["reasons"]})

    def test_remove(self):
        s=self.select(("demo.season","1.0.0"),("demo.base","1.0.0"))
        self.assertEqual(self.m.remove(s,"demo.base")["reason"],"STILL_REQUIRED")
        p=self.m.remove(s,"demo.season")
        self.assertEqual([x["id"] for x in p["removed"]],["demo.season","demo.driver","demo.circuit"])
        self.assertEqual(self.m.remove(self.selection,"demo.base")["reason"],"NOT_EXPLICIT_ROOT")

    def test_rollback(self):
        s=self.select(("demo.driver","1.1.0"))
        p=self.m.rollback(s,"demo.driver")
        self.assertEqual(p["candidate_selection"]["requested"],[{"id":"demo.driver","version":"1.0.0"}])
        self.assertEqual(p["status"],"NOT_RUN")
        self.assertEqual(self.m.rollback(self.selection,"demo.season")["reason"],"NO_PREVIOUS_VERSION")

    def test_cycle(self):
        def mutate(rows):
            rows[0]["dependencies"]=[{"id":"demo.driver","version":"1.0.0"}]
        with self.assertRaises(ValueError):
            self.build(mutate)

    def test_bad_manifest(self):
        for change in ({"permissions":["execute.script"]},{"season":2026},{"rights":"APPROVED"},
                       {"usage":"PRODUCTION"},{"dependencies":[{"id":"demo.hyper","version":"1.0.0"}]},
                       {"overlays":[{"target":"driver.demo","version":"9.0.0","label":"x"}]}):
            with self.assertRaises(ValueError):
                self.build(lambda rows:rows[0].update(change))

    def test_registered_package(self):
        x=self.m.package("demo.driver","1.0.0")
        self.assertEqual(x["status"],"PASS")
        self.assertEqual(x,self.m.package("demo.driver","1.0.0"))
        self.assertFalse(x["extracted"])

    def zipped(self,entries):
        b=io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore",UserWarning)
            with zipfile.ZipFile(b,"w") as z:
                for name,body in entries:
                    z.writestr(name,body)
        return b.getvalue()

    def test_package_rejects_paths_scripts_duplicates(self):
        body=m.json_bytes(self.m.entries[("demo.base","1.0.0")])
        for entries in ([("../manifest.json",body)],[("manifest.json",body),("script.gd",b"bad")],
                        [("manifest.json",body),("manifest.json",body)],[("/manifest.json",body)],
                        [("manifest.json",b"x"*(m.MAX_MANIFEST+1))]):
            with self.assertRaises(ValueError):
                self.m.inspect_zip(self.zipped(entries))

    def test_package_rejects_symlink_tamper_and_duplicate_keys(self):
        row=copy.deepcopy(self.m.entries[("demo.base","1.0.0")])
        row["title"]="changed"
        with self.assertRaises(ValueError):
            self.m.inspect_zip(self.zipped([("manifest.json",m.json_bytes(row))]))
        with self.assertRaises(ValueError):
            self.m.inspect_zip(self.zipped([("manifest.json",b'{"id":"a","id":"b"}')]))
        info=zipfile.ZipInfo("manifest.json");info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
        with self.assertRaises(ValueError):
            self.m.inspect_zip(self.zipped([(info,b"outside")]))
        with self.assertRaises(zipfile.BadZipFile):
            self.m.inspect_zip(b"not a zip")

    def test_gate(self):
        p=self.m.gate(self.selection)
        self.assertEqual(p["status"],"BLOCKED")
        self.assertFalse(p["execution_authorized"])

if __name__=="__main__":
    unittest.main()
