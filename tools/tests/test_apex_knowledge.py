import copy
from pathlib import Path
import sys
import unittest
import tempfile
import shutil
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import apex_knowledge as k
import apex_foundation_registry as r

class KnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.k = k.load()

    def test_coverage(self):
        s = self.k.stats()
        self.assertEqual((s["references"],s["ideas"],s["with_url"],s["without_url"]),(198,120,104,94))
        self.assertEqual(s["document_observed"],4)
        self.assertEqual(s["license_approved"],0)
        self.assertFalse(s["implementation_authorized"])
        self.assertEqual(s["fingerprint"],k.load().fingerprint)

    def test_links(self):
        for ident, idea in self.k.ideas.items():
            for ref in idea["references"]:
                self.assertIn(ident,self.k.reference(ref)["linked_ideas"])
        self.assertEqual(self.k.stats()["links"],sum(len(x["references"]) for x in self.k.ideas.values()))

    def test_search_accent_and_exact(self):
        self.assertEqual(self.k.search("REF-106")["matches"][0]["id"],"REF-106")
        self.assertEqual(self.k.search("curva de torque", "idea")["matches"][0]["id"],"IDEA-001")
        self.assertEqual(self.k.search("estratégia"),self.k.search("estrategia"))
        self.assertEqual(self.k.search("xyznotfound")["total"],0)
        self.assertTrue(all(x["kind"]=="idea" for x in self.k.search("IDEA","idea","physics")["matches"]))

    def test_search_limits(self):
        for query in (""," ","!"*10,"x"*201):
            with self.assertRaises(ValueError):
                self.k.search(query)
        for limit in (0,201,True):
            with self.assertRaises(ValueError):
                self.k.search("IDEA",limit=limit)
        with self.assertRaises(ValueError):
            self.k.search("IDEA",department="unknown")
        self.assertTrue(self.k.search("IDEA",limit=1)["truncated"])

    def test_queue(self):
        q=self.k.queue(198)["items"]
        self.assertEqual(len(q),198)
        self.assertEqual(q,sorted(q,key=lambda x:(-x["score"],x["id"])))
        for row in q:
            self.assertEqual(row["score"],sum(row["components"].values()))
            self.assertEqual(row["reuse"],"BLOCKED")

    def test_plan_all(self):
        for ident in self.k.ideas:
            p=self.k.plan(ident)
            self.assertEqual(p["status"],"BLOCKED")
            self.assertFalse(p["implementation_authorized"])
            self.assertTrue(p["acceptance"])
        with self.assertRaises(KeyError):
            self.k.plan("IDEA-999")

    def test_duplicate_candidates(self):
        dup=self.k.duplicates()
        for group in dup["same_normalized_name"]+dup["same_normalized_url"]:
            self.assertGreater(len(group),1)
            self.assertTrue(set(group)<=self.k.refs.keys())

    def test_url(self):
        self.assertEqual(k.canonical_url("https://GitHub.com/A/B/#section"),"https://github.com/A/B")
        self.assertNotEqual(k.canonical_url("https://github.com/A"),k.canonical_url("https://github.com/a"))
        for url in ("http://example.org","https://u:p@example.org","https://example.org:443","file:///etc/passwd","https://localhost","https://example.org/a b"):
            with self.assertRaises(ValueError):
                k.canonical_url(url)

    def test_observation_contract(self):
        _, schemas=r.load_registry()
        row=self.k.reference("REF-106")["observations"][0]
        r.check(row,schemas["research-observation.v1"])
        for change in ({"reuse":"APPROVED"},{"license_state":"APPROVED"},{"revision":"latest"},{"extra":1}):
            with self.assertRaises(ValueError):
                r.check(dict(row,**change),schemas["research-observation.v1"])
        self.assertEqual(self.k.reference("REF-106")["evidence_state"],"DOCUMENT_OBSERVED")
        self.assertEqual(self.k.reference("REF-001")["evidence_state"],"UNVERIFIED")

    def test_inventory_and_audit(self):
        audit = self.k.audit()
        self.assertEqual(len(audit["departments"]),7)
        self.assertEqual(sum(len(x["idea_ids"]) for x in audit["departments"]),120)
        self.assertFalse(audit["implementation_authorized"])
        for row in audit["departments"]:
            self.assertEqual(row["audit_state"],"NOT_RUN")
            self.assertTrue(row["candidate_files"])
        self.assertEqual(self.k.plan("IDEA-001")["consumer_audit"],"NOT_RUN")
        self.assertEqual(len(self.k.audit("physics")["departments"]),1)
        with self.assertRaises(ValueError):
            self.k.audit("unknown")

    def test_historical_lock(self):
        self.assertEqual(k.history_check()["files_checked"],6)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = r.read(k.DOCS/"history-lock.json")
            for path in lock["files"]:
                target=root/path
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(k.ROOT/path,target)
            self.assertEqual(k.history_check(root)["files_checked"],6)
            path=root/"docs/references/references.json"
            path.write_bytes(path.read_bytes()+b" ")
            with self.assertRaises(ValueError):
                k.history_check(root)

    def test_mutated_catalog(self):
        refs=r.read(k.legacy.DOCS/"references.json")
        ideas=r.read(k.legacy.DOCS/"possibilities.json")
        policy=r.read(k.DOCS/"policy.json")
        obs=r.read(k.DOCS/"observations.json")
        reg,schemas=r.load_registry()
        domains=r.read(k.legacy.DOCS/"domains.json")["domains"]
        for mutate in (
            lambda a,b,c,d:a["entries"][0].update(license="MIT"),
            lambda a,b,c,d:b["entries"][0]["references"].append("REF-999"),
            lambda a,b,c,d:c["departments"].pop("physics"),
            lambda a,b,c,d:d["entries"].append(d["entries"][0]),
            lambda a,b,c,d:d["entries"][0].update(observed_on="2026-02-30"),
        ):
            a,b,c,d=copy.deepcopy((refs,ideas,policy,obs))
            mutate(a,b,c,d)
            with self.assertRaises(ValueError):
                k.Knowledge(a,b,c,d,reg,schemas,domains)

if __name__=="__main__":
    unittest.main()
