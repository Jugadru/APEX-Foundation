import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import apex_config as c
import apex_foundation_registry as r

class ConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=c.load()
        cls.settings=r.read(c.DOCS/"settings.json")
        cls.constraints=r.read(c.DOCS/"constraints.json")
        cls.profiles=r.read(c.ROOT/"data/config/profiles.json")

    def build(self,profiles=None,settings=None,constraints=None):
        return c.Config(settings if settings is not None else self.settings,
                        constraints if constraints is not None else self.constraints,
                        profiles if profiles is not None else self.profiles,
                        self.config.schemas,self.config.consumers,self.config.season)

    def edit(self,ident,fn,version="1.0.0"):
        p=copy.deepcopy(self.profiles)
        fn(next(x for x in p["entries"] if x["id"]==ident and x["version"]==version))
        return p

    def override(self,ident,setting,value):
        def apply(row):
            row["overrides"]=[x for x in row["overrides"] if x["id"]!=setting]+[{"id":setting,"value":value}]
        return self.edit(ident,apply)

    def test_stats(self):
        s=self.config.stats()
        self.assertEqual((s["settings"],s["experimental_flags"],s["constraints"],s["profiles"],s["profile_versions"]),(12,4,5,5,6))
        self.assertFalse(s["runtime_applied"])
        self.assertEqual(s["fingerprint"],c.load().fingerprint)

    def test_inheritance_and_origins(self):
        x=self.config.resolve("hyper-technical","1.0.0")
        self.assertTrue(x["values"]["feature.longitudinal"])
        self.assertTrue(x["values"]["feature.advanced-racecraft"])
        self.assertEqual(x["origins"]["feature.longitudinal"],"hyper-development@1.0.0")
        self.assertEqual(x["origins"]["simulation.seed"],"default")
        self.assertEqual(x["origins"]["simulation.realism"],"hyper-technical@1.0.0")

    def test_diff_rollback(self):
        x=self.config.diff("core2-development","1.0.0","1.1.0")
        self.assertEqual(x["changes"],[{"id":"diagnostics.sample-ms","before":100,"after":50}])
        roll=self.config.rollback("core2-development","1.1.0")
        self.assertEqual(roll["target"],"1.0.0")
        self.assertEqual(roll["target_sha256"],x["before_sha256"])
        self.assertFalse(roll["runtime_applied"])
        self.assertEqual(self.config.rollback("core2-development","1.0.0")["status"],"BLOCKED")

    def test_types_bounds_unknown(self):
        for setting,value in (("simulation.seed",True),("simulation.tick-hz",241),("simulation.realism","unknown"),
                              ("diagnostics.replay",1),("unknown.setting",False)):
            with self.assertRaises(ValueError):
                self.build(self.override("hyper-development",setting,value))

    def test_experimental_scope(self):
        for profile in ("core2-development","core2-production-candidate","hyper-production-candidate"):
            with self.assertRaises(ValueError):
                self.build(self.override(profile,"feature.longitudinal",True))

    def test_manual_priority(self):
        with self.assertRaises(ValueError):
            self.build(self.override("hyper-development","safety.manual-priority",False))

    def test_constraints(self):
        for profile,setting,value in (("hyper-development","diagnostics.replay",False),
                                      ("hyper-development","feature.randomized-seed",True),
                                      ("hyper-technical","diagnostics.telemetry",False),
                                      ("hyper-technical","feature.longitudinal",False),
                                      ("hyper-production-candidate","simulation.realism","technical")):
            with self.assertRaises(ValueError):
                self.build(self.override(profile,setting,value))

    def test_scope_parent(self):
        for parent in ({"id":"core2-development","version":"1.0.0"},
                       {"id":"hyper-production-candidate","version":"1.0.0"},
                       {"id":"hyper-development","version":"9.0.0"},
                       {"id":"hyper-technical","version":"1.0.0"}):
            with self.assertRaises(ValueError):
                self.build(self.edit("hyper-technical",lambda x:x.update(parent=parent)))

    def test_versions_and_duplicate_overrides(self):
        for p in (self.edit("core2-development",lambda x:x.update(previous=None),"1.1.0"),
                  self.edit("hyper-development",lambda x:x["overrides"].append(dict(x["overrides"][0]))),
                  self.edit("hyper-development",lambda x:x.update(revision="0"*40)),
                  self.edit("hyper-development",lambda x:x.update(season=2026))):
            with self.assertRaises(ValueError):
                self.build(p)
        with self.assertRaises(KeyError):
            self.config.resolve("hyper-development","latest")

    def test_policy_hardening(self):
        settings=copy.deepcopy(self.settings)
        next(x for x in settings["entries"] if x["id"]=="feature.longitudinal")["experimental"]=False
        with self.assertRaises(ValueError):
            self.build(settings=settings)
        constraints=copy.deepcopy(self.constraints)
        constraints["entries"]=[x for x in constraints["entries"] if x["id"]!="longitudinal-replay"]
        with self.assertRaises(ValueError):
            self.build(self.override("hyper-development","diagnostics.replay",False),constraints=constraints)

    def test_gate(self):
        for consumer,sha in self.config.consumers.items():
            x=self.config.gate("hyper-development","1.0.0",consumer,sha)
            self.assertEqual(x["status"],"BLOCKED")
            self.assertFalse(x["execution_authorized"])
            if consumer=="core2":
                self.assertIn("CONSUMER_MISMATCH",x["reasons"])
        self.assertIn("UNKNOWN_EXACT_CONSUMER_REVISION",self.config.gate("hyper-development","1.0.0","hyper","0"*40)["reasons"])

if __name__=="__main__":
    unittest.main()
