import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import apex_data_center as d
import apex_foundation_registry as r
import apex_knowledge as k

class DataCenterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dc=d.load()
        cls.catalog=r.read(d.DOCS/"catalog.json")
        cls.units=r.read(d.DOCS/"units.json")
        cls.era=r.read(d.DOCS/"era-policy.json")
        cls.matrix=r.read(d.DOCS/"consumer-matrix.json")
        _,cls.schemas=r.load_registry()
        knowledge=k.load()
        cls.references=set(knowledge.refs)
        cls.domains=knowledge.domains

    def build(self,catalog=None,units=None,era=None,matrix=None,root=d.ROOT):
        return d.DataCenter(catalog if catalog is not None else self.catalog,
                            units if units is not None else self.units,
                            era if era is not None else self.era,
                            matrix if matrix is not None else self.matrix,
                            self.schemas,self.references,self.domains,self.dc.consumers,root)

    def test_stats(self):
        s=self.dc.stats()
        self.assertEqual((s["datasets"],s["versions"],s["records_across_versions"],s["units"],s["consumer_pairs"]),(2,3,7,10,6))
        self.assertEqual(s["origins"],{"synthetic":3})
        self.assertEqual(s["production_approved"],0)
        self.assertEqual(s["fingerprint"],d.load().fingerprint)

    def test_exact_conversion(self):
        for value,source,target,expected in [("180","kmh","mps",(50,1)),("1","kmh","mps",(5,18)),
                                             ("650000","g","kg",(650,1)),("0.5","kw","w",(500,1)),
                                             ("90000","ms","s",(90,1)),("800","permille","ratio",(4,5))]:
            x=self.dc.units.convert(value,source,target)["exact"]
            self.assertEqual((x["numerator"],x["denominator"]),expected)

    def test_invalid_units(self):
        for value in ("NaN","inf","1e3","1/2",""):
            with self.assertRaises(ValueError):
                self.dc.units.convert(value,"g","kg")
        with self.assertRaises(ValueError):
            self.dc.units.convert("1","g","s")
        with self.assertRaises(KeyError):
            self.dc.units.convert("1","unknown","kg")
        units=copy.deepcopy(self.units)
        units["units"][0]["denominator"]=0
        with self.assertRaises(ValueError):
            self.build(units=units)

    def test_query_and_diff(self):
        q=self.dc.query("vehicle-fixture","1.1.0",limit=1)
        self.assertEqual(q["total"],3)
        self.assertTrue(q["truncated"])
        self.assertEqual(self.dc.query("vehicle-fixture","1.0.0","fixture-a")["records"][0]["values"]["mass_g"],650000)
        diff=self.dc.diff("vehicle-fixture","1.0.0","1.1.0")
        self.assertEqual(diff["added"],["fixture-c"])
        self.assertEqual(diff["changed"],["fixture-a"])
        self.assertEqual(diff["removed"],[])
        self.assertEqual(diff["status"],"NOT_RUN")
        with self.assertRaises(ValueError):
            self.dc.diff("vehicle-fixture","1.1.0","1.0.0")

    def test_gate_exact_and_unknown(self):
        for consumer,sha in self.dc.consumers.items():
            report=self.dc.gate("vehicle-fixture","1.0.0",consumer,sha)
            self.assertEqual(report["status"],"BLOCKED")
            self.assertIn("CONSUMER_VALIDATION_NOT_RUN",report["reasons"])
            self.assertFalse(report["execution_authorized"])
            self.assertIn("UNKNOWN_EXACT_CONSUMER_REVISION",self.dc.gate("vehicle-fixture","1.0.0",consumer,"0"*40)["reasons"])
        with self.assertRaises(ValueError):
            self.dc.gate("vehicle-fixture","1.0.0","core2","latest")

    def test_invalid_provenance(self):
        for mutation in (lambda x:x.update(usage="RESEARCH_ONLY"),
                         lambda x:x["provenance"].update(origin="historical"),
                         lambda x:x["provenance"].update(reference_ids=["REF-999"]),
                         lambda x:x["provenance"].update(source_url="https://example.org")):
            catalog=copy.deepcopy(self.catalog)
            mutation(catalog["entries"][0])
            with self.assertRaises(ValueError):
                self.build(catalog=catalog)

    def test_version_chain(self):
        for mutation in (lambda x:x["entries"][1].update(previous=None),
                         lambda x:x["entries"].append(x["entries"][0]),
                         lambda x:x["entries"][1]["fields"][0].update(maximum=2100000)):
            catalog=copy.deepcopy(self.catalog)
            mutation(catalog)
            with self.assertRaises(ValueError):
                self.build(catalog=catalog)

    def test_matrix(self):
        for mutation in (lambda x:x["entries"].pop(),
                         lambda x:x["entries"][0].update(status="PASS"),
                         lambda x:x["entries"][0].update(revision="0"*40),
                         lambda x:x["entries"].append(x["entries"][0])):
            matrix=copy.deepcopy(self.matrix)
            mutation(matrix)
            with self.assertRaises(ValueError):
                self.build(matrix=matrix)

    def test_unsafe_payload_path(self):
        catalog=copy.deepcopy(self.catalog)
        catalog["entries"][0]["payload"]="../outside.json"
        with self.assertRaises(ValueError):
            self.build(catalog=catalog)

    def test_payload_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            shutil.copytree(d.ROOT/"data",root/"data")
            path=root/self.catalog["entries"][0]["payload"]
            path.write_bytes(path.read_bytes()+b" ")
            with self.assertRaises(ValueError):
                self.build(root=root)

    def test_invalid_records_even_with_matching_hash(self):
        for change in (lambda row:row.update(year=2026),
                       lambda row:row.update(technology="modern-cost-cap"),
                       lambda row:row.update(technology="unknown"),
                       lambda row:row["values"].update(mass_g=True),
                       lambda row:row["values"].update(mass_g=-1),
                       lambda row:row["values"].update(extra=1)):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                shutil.copytree(d.ROOT/"data",root/"data")
                catalog=copy.deepcopy(self.catalog)
                manifest=catalog["entries"][0]
                path=root/manifest["payload"]
                payload=json.loads(path.read_text())
                change(payload["records"][0])
                raw=json.dumps(payload).encode()
                path.write_bytes(raw)
                manifest["blob_sha"]=d.blob_id(raw)
                with self.assertRaises(ValueError):
                    self.build(catalog=catalog,root=root)

    def test_era_policy_cannot_be_weakened(self):
        for mutate in (lambda e:e["blocked"].remove("modern-cost-cap"),
                       lambda e:(e["blocked"].remove("modern-cost-cap"),e["allowed"].append("modern-cost-cap")),
                       lambda e:e["allowed"].append("unknown-modern")):
            era=copy.deepcopy(self.era)
            mutate(era)
            with self.assertRaises(ValueError):
                self.build(era=era)

    def test_schema_and_era_policy(self):
        m=self.catalog["entries"][0]
        r.check(m,self.schemas["dataset-manifest.v1"])
        with self.assertRaises(ValueError):
            r.check(dict(m,extra=True),self.schemas["dataset-manifest.v1"])
        era=copy.deepcopy(self.era)
        era["allowed"].append("modern-cost-cap")
        with self.assertRaises(ValueError):
            self.build(era=era)

if __name__=="__main__":
    unittest.main()
