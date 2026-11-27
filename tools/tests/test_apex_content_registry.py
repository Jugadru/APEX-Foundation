import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import apex_content_registry as c
import apex_foundation_registry as r

class ContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=c.load()
        cls.catalog=r.read(c.ROOT/"data/content/catalog.json")
        cls.policy=r.read(c.DOCS/"policy.json")
        cls.matrix=r.read(c.DOCS/"consumer-matrix.json")
        cls.inv=r.read(c.DOCS/"source-inventory.json")

    def build(self,cat=None,policy=None,matrix=None,inv=None):
        return c.ContentRegistry(cat if cat is not None else self.catalog,
          policy if policy is not None else self.policy,matrix if matrix is not None else self.matrix,
          inv if inv is not None else self.inv,self.c.schemas,self.c.data)

    def mutate(self,ident,fn,version="1.0.0"):
        cat=copy.deepcopy(self.catalog)
        row=next(x for x in cat["entries"] if x["id"]==ident and x["version"]==version)
        fn(row)
        return cat

    def test_coverage(self):
        s=self.c.stats()
        self.assertEqual((s["identities"],s["versions"],s["kinds"],s["dataset_links"],s["source_candidates"]),(20,21,14,1,5))
        self.assertEqual(s["production_approved"],0)
        self.assertEqual(s["fingerprint"],c.load().fingerprint)

    def test_search(self):
        self.assertEqual(self.c.search("piloto ficticio","driver")["total"],2)
        self.assertEqual(self.c.search("piloto fictício","driver",1)["truncated"],True)
        with self.assertRaises(ValueError):
            self.c.search("x",kind="unknown")

    def test_versions_and_diff(self):
        self.assertEqual(self.c.diff("driver.demo","1.0.0","1.1.0")["changed_fields"],["name"])
        with self.assertRaises(KeyError):
            self.c.show("driver.demo","latest")
        with self.assertRaises(ValueError):
            self.c.diff("driver.demo","1.1.0","1.0.0")

    def test_relationships(self):
        g=self.c.graph("vehicle.demo","1.0.0")
        deps={x["id"] for x in g["dependencies"]}
        self.assertTrue({"team.demo","manufacturer.demo","supplier.demo","component.engine","asset.model3d"}<=deps)
        self.assertNotIn("driver.demo",deps)
        order=self.c.order
        for key,targets in self.c.edges.items():
            for target in targets:
                self.assertLess(order.index(target),order.index(key))
        self.assertTrue(any(x["id"]=="season.demo" for x in self.c.graph("team.demo","1.0.0")["dependents"]))

    def test_invalid_relationships(self):
        for fn in (lambda x:x["links"].clear(),
                   lambda x:x["links"][0].update(version="9.0.0"),
                   lambda x:x["links"][0].update(target="supplier.demo"),
                   lambda x:x["links"][0].update(target="driver.demo"),
                   lambda x:x["links"].append(dict(x["links"][0],version="1.1.0"))):
            with self.assertRaises(ValueError):
                self.build(cat=self.mutate("driver.demo",fn))

    def test_relationship_identity_not_duplicated_across_versions(self):
        cat=copy.deepcopy(self.catalog)
        engine=copy.deepcopy(next(x for x in cat["entries"] if x["id"]=="component.engine"))
        engine.update(version="1.1.0",previous="1.0.0")
        cat["entries"].append(engine)
        vehicle=next(x for x in cat["entries"] if x["id"]=="vehicle.demo")
        vehicle["links"].append({"role":"component","target":"component.engine","version":"1.1.0"})
        with self.assertRaises(ValueError):
            self.build(cat=cat)

    def test_cycle(self):
        p=copy.deepcopy(self.policy)
        p["relations"]["manufacturer"]["partner"]={"target":"team","minimum":1,"maximum":1}
        cat=self.mutate("manufacturer.demo",lambda x:x["links"].append({"role":"partner","target":"team.demo","version":"1.0.0"}))
        with self.assertRaises(ValueError):
            self.build(cat=cat,policy=p)

    def test_era_rights_and_attributes(self):
        for fn in (lambda x:x.update(season=2026),lambda x:x.update(technology="modern-cost-cap"),
                   lambda x:x.update(origin="historical"),lambda x:x.update(usage="PRODUCTION"),
                   lambda x:x.update(rights="APPROVED"),lambda x:x["attributes"][0].update(value="unknown"),
                   lambda x:x["attributes"].append({"key":"role","value":"driver"})):
            with self.assertRaises(ValueError):
                self.build(cat=self.mutate("driver.demo",fn))

    def test_dataset_binding(self):
        for fn in (lambda x:x["datasets"][0].update(record="missing"),
                   lambda x:x["datasets"][0].update(version="9.0.0"),
                   lambda x:x["datasets"][0].update(id="strategy-fixture",version="1.0.0",record="dry-demo")):
            with self.assertRaises(ValueError):
                self.build(cat=self.mutate("vehicle.demo",fn))

    def test_version_chain(self):
        with self.assertRaises(ValueError):
            self.build(cat=self.mutate("driver.demo",lambda x:x.update(previous=None),"1.1.0"))
        cat=copy.deepcopy(self.catalog)
        cat["entries"].append(cat["entries"][0])
        with self.assertRaises(ValueError):
            self.build(cat=cat)

    def test_gate(self):
        for consumer,revision in self.c.data.consumers.items():
            q=self.c.gate("vehicle.demo","1.0.0",consumer,revision)
            self.assertEqual(q["status"],"BLOCKED")
            self.assertIn("CONSUMER_VALIDATION_NOT_RUN",q["reasons"])
            self.assertFalse(q["execution_authorized"])
            self.assertIn("UNKNOWN_EXACT_CONSUMER_REVISION",self.c.gate("vehicle.demo","1.0.0",consumer,"0"*40)["reasons"])

    def test_matrix_inventory(self):
        for mutate in (lambda m:m["entries"].pop(),lambda m:m["entries"][0].update(status="PASS"),lambda m:m["entries"][0].update(revision="0"*40)):
            matrix=copy.deepcopy(self.matrix)
            mutate(matrix)
            with self.assertRaises(ValueError):
                self.build(matrix=matrix)
        inv=copy.deepcopy(self.inv)
        inv["paths"][0]["path"]="../escape"
        with self.assertRaises(ValueError):
            self.build(inv=inv)

    def test_asset_metadata_only(self):
        for media in ("portrait","model3d","texture","audio"):
            row=self.c.show("asset."+media,"1.0.0")["entity"]
            self.assertEqual(dict((a["key"],a["value"]) for a in row["attributes"])["availability"],"metadata-only")
        with self.assertRaises(ValueError):
            self.build(cat=self.mutate("asset.model3d",lambda x:x.update(file="model.glb")))

if __name__=="__main__":
    unittest.main()
