import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import apex_persistence as p
import apex_foundation_registry as r

class PersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=p.load()

    def test_stats(self):
        s=self.p.stats()
        self.assertEqual((s["formats"],s["routes"],s["fixtures"],s["saveguard_pointers"]),(3,2,4,8))
        self.assertFalse(s["native_save_verified"])
        self.assertEqual(s["fingerprint"],p.load().fingerprint)

    def test_multistep_migration(self):
        before=copy.deepcopy(self.p.fixtures["career-baseline"])
        x=self.p.simulate("career-baseline","3.0.0")
        self.assertEqual(x["status"],"PASS")
        self.assertEqual(x["steps"],2)
        self.assertEqual(x["result"]["payload"],{"progress":{"round_index":3,"points":42},"budget_units":6500000})
        self.assertEqual(before,self.p.fixtures["career-baseline"])
        self.assertTrue(x["source_unchanged"])
        self.assertFalse(x["native_save_verified"])

    def test_identity_and_single_step(self):
        self.assertEqual(self.p.simulate("career-primary","3.0.0")["steps"],0)
        self.assertEqual(self.p.simulate("career-backup","3.0.0")["steps"],1)

    def test_downgrade_and_unknown(self):
        self.assertEqual(self.p.plan("career-primary","1.0.0")["status"],"BLOCKED")
        with self.assertRaises(ValueError):
            self.p.plan("career-baseline","latest")
        with self.assertRaises(KeyError):
            self.p.inspect("/tmp/player.json")

    def test_corruption(self):
        self.assertEqual(self.p.inspect("career-corrupt")["status"],"FAIL")
        self.assertEqual(self.p.simulate("career-corrupt","3.0.0")["status"],"BLOCKED")

    def test_semantic_validation_even_with_rehashed_payload(self):
        for val in (True,-1,21):
            envelope=copy.deepcopy(self.p.fixtures["career-primary"])
            envelope["payload"]["progress"]["round_index"]=val
            envelope["manifest"]["payload_sha256"]=p.digest(envelope["payload"])
            with self.assertRaises(ValueError):
                self.p.verify(envelope)

    def test_external_checksum(self):
        envelope=copy.deepcopy(self.p.fixtures["career-primary"])
        envelope["payload"]["budget_units"]+=1
        envelope["manifest"]["payload_sha256"]=p.digest(envelope["payload"])
        with self.assertRaises(ValueError):
            self.p.verify(envelope,self.p.expected["career-primary"])

    def test_recovery_candidates(self):
        x=self.p.recovery(self.p.scenario("corrupt-primary"))
        self.assertEqual(x["candidates"],["career-backup","career-baseline"])
        self.assertEqual(x["decision"],"REVIEW_BACKUPS")
        self.assertFalse(x["restored"])
        self.assertFalse(x["execution_authorized"])

    def test_valid_primary_and_no_backup(self):
        self.assertEqual(self.p.recovery(self.p.scenario("valid-primary"))["decision"],"KEEP_VALID_PRIMARY")
        self.assertEqual(self.p.recovery(self.p.scenario("no-backup"))["status"],"BLOCKED")

    def test_bad_backup_and_future_generation(self):
        s=self.p.scenario("corrupt-primary")
        s["backups"][1]["expected_sha256"]="0"*64
        self.assertEqual(self.p.recovery(s)["candidates"],["career-baseline"])
        s=self.p.scenario("corrupt-primary")
        s["backups"].append(s["backups"][0])
        with self.assertRaises(ValueError):
            self.p.recovery(s)

    def test_recovery_scope_and_untrusted_checksum(self):
        s=self.p.scenario("corrupt-primary")
        s.update(consumer="hyper",revision=self.p.consumers["hyper"])
        with self.assertRaises(ValueError):
            self.p.recovery(s)
        s=self.p.scenario("corrupt-primary")
        s["primary"]["expected_sha256"]=p.digest(self.p.fixtures["career-corrupt"])
        self.assertEqual(self.p.recovery(s)["decision"],"REVIEW_BACKUPS")
        s=self.p.scenario("corrupt-primary")
        s["primary"]={"id":"career-baseline","expected_sha256":"0"*64}
        s["backups"]=[{"id":"career-primary","expected_sha256":self.p.expected["career-primary"]}]
        self.assertEqual(self.p.recovery(s)["decision"],"NO_VALID_BACKUP")

    def test_scope_and_gate(self):
        s=self.p.scenario("corrupt-primary")
        s["revision"]="0"*40
        with self.assertRaises(ValueError):
            self.p.recovery(s)
        x=self.p.gate("career-baseline","core2",self.p.consumers["core2"])
        self.assertEqual(x["status"],"BLOCKED")
        self.assertFalse(x["execution_authorized"])
        self.assertIn("CONSUMER_MISMATCH",self.p.gate("career-baseline","hyper",self.p.consumers["hyper"])["reasons"])

    def test_route_tamper(self):
        routes=r.read(p.DOCS/"routes.json")
        fixtures=r.read(p.ROOT/"data/persistence/fixtures.json")
        inv=r.read(p.DOCS/"saveguard-inventory.json")
        for change in (lambda x:x["entries"].pop(),lambda x:x["entries"][0].update(to="3.0.0")):
            bad=copy.deepcopy(routes);change(bad)
            with self.assertRaises(ValueError):
                p.Persistence(bad,fixtures,inv,self.p.schemas,self.p.consumers)

if __name__=="__main__":
    unittest.main()
