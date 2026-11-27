import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import apex_core2_metadata as m
import apex_foundation_registry as r
import apex_sdk as sdk

class MetadataReceiverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _,schemas=r.load_registry()
        cls.schema=schemas["core2-metadata.v1"]
        cls.tmp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.tmp.name)
        cls.addClassCleanup(cls.tmp.cleanup)
        subprocess.run(["git","init","-q",str(cls.root)],check=True)
        teams=[{"name":f"Synthetic Team {i}","drivers":[{"name":f"Synthetic Driver {i}-{j}"} for j in range(2)]} for i in range(12)]
        tracks=[{"code":"X"+chr(65+i//26)+chr(65+i%26),"name":f"Synthetic Track {i}","country":"Fixture","laps":50} for i in range(20)]
        for path,value in zip(m.PATHS,({"season":2012,"teams":teams,"tracks":tracks},teams)):
            target=cls.root/path
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(m.canonical(value))
        subprocess.run(["git","-C",str(cls.root),"add","data"],check=True)
        subprocess.run(["git","-C",str(cls.root),"-c","user.name=Fixture","-c","user.email=fixture@example.invalid","commit","-qm","fixture"],check=True)
        cls.revision=m.git(cls.root,"rev-parse","HEAD").decode().strip()
        sources=[]
        for path in m.PATHS:
            raw=(cls.root/path).read_bytes()
            sources.append({"path":path,"git_blob":hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest(),
                            "sha256":hashlib.sha256(raw).hexdigest(),"size_bytes":len(raw)})
        body={"contract":"core2-metadata.v1","repository":"Jugadru/APEX-Simulation","revision":cls.revision,
              "scope":"CORE2_METADATA_READ_ONLY","authority":"core2","identity_scope":"EXACT_REVISION_ONLY",
              "sources":sources,"catalog":{"season":2012,
                  "teams":[{"index":i,"name":x["name"]} for i,x in enumerate(teams)],
                  "drivers":[{"team_index":i,"slot":j,"name":x["drivers"][j]["name"]} for i,x in enumerate(teams) for j in range(2)],
                  "circuits":[{"index":i,**x} for i,x in enumerate(tracks)]},
              "runtime_applied":False,"execution_authorized":False}
        cls.report={"body":body,"body_sha256":m.digest(body)}

    def verify(self,report=None,revision=None):
        return m.verify(self.report if report is None else report,self.schema,self.revision if revision is None else revision,self.root)

    def modify(self,fn):
        report=copy.deepcopy(self.report)
        fn(report["body"])
        report["body_sha256"]=m.digest(report["body"])
        return report

    def test_exact_local_projection(self):
        x=self.verify()
        self.assertEqual(x["counts"],{"teams":12,"drivers":24,"circuits":20})
        self.assertTrue(x["source_bytes_verified"])
        self.assertFalse(x["native_runtime_verified"])
        self.assertFalse(x["content_imported"])
        self.assertFalse(x["execution_authorized"])
        self.assertEqual(x,self.verify())

    def test_bad_revision_and_hash(self):
        with self.assertRaises(ValueError):
            self.verify(revision="0"*40)
        with self.assertRaises(ValueError):
            self.verify(dict(self.report,body_sha256="0"*64))
        with self.assertRaises(ValueError):
            self.verify(revision="main")

    def test_forged_projection_with_new_digest(self):
        for fn in (lambda b:b["catalog"]["drivers"][0].update(name="Forged Driver"),
                   lambda b:b["catalog"]["circuits"][0].update(laps=51),
                   lambda b:b["catalog"]["teams"][0].update(name="Forged Team"),
                   lambda b:b["sources"][0].update(git_blob="0"*40)):
            with self.assertRaises(ValueError):
                self.verify(self.modify(fn))

    def test_closed_contract(self):
        for fn in (lambda b:b.update(runtime_applied=True),
                   lambda b:b.update(execution_authorized=True),
                   lambda b:b.update(extra="unrecognized"),
                   lambda b:b["sources"][0].update(path="../secret"),
                   lambda b:b["catalog"]["teams"][0].update(index=True),
                   lambda b:b["catalog"]["drivers"][0].update(slot=1)):
            with self.assertRaises(ValueError):
                self.verify(self.modify(fn))

    def test_tampered_checkout(self):
        path=self.root/m.PATHS[0]
        raw=path.read_bytes()
        try:
            path.write_bytes(raw+b"\n")
            with self.assertRaises(ValueError):
                self.verify()
            path.unlink()
            path.symlink_to(self.root/m.PATHS[1])
            with self.assertRaises(ValueError):
                self.verify()
        finally:
            if path.is_symlink():
                path.unlink()
            path.write_bytes(raw)

    def test_duplicate_json_rejected(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}'):
            with self.assertRaises(ValueError):
                m.parse(raw)

    def test_sdk_boundary(self):
        obj=sdk.FoundationSDK()
        response=obj.call("integration.core2-contract")
        self.assertEqual(response["response"]["status"],"PASS")
        self.assertEqual(response["result"]["native_readiness"],"BLOCKED")
        self.assertEqual(obj.call("integration.core2-verify")["response"]["status"],"BLOCKED")
        self.assertEqual(obj.call("integration.core2-verify",profile="planner")["response"]["status"],"BLOCKED")

if __name__=="__main__":
    unittest.main()
