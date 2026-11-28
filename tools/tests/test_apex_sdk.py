import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import io
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import apex_sdk as s
import apex as cli
import apex_foundation_registry as r
import apex_knowledge as k

class SDKTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sdk=s.FoundationSDK()

    def test_catalog_coverage(self):
        c=self.sdk.catalog()
        self.assertEqual((c["capabilities"],c["offline_routes"],c["external_only"]),(71,62,9))
        self.assertTrue(all(not x["execution_authorized"] for x in c["entries"]))
        self.assertEqual(set(s.ROUTES)|set(s.DENIED),set(self.sdk._caps))

    def test_doctor(self):
        x=self.sdk.doctor()
        self.assertEqual((x["status"],x["local_checks"],x["passed"]),("PASS",11,11))
        self.assertEqual(x["native_readiness"],"BLOCKED")
        self.assertFalse(x["runtime_verified"])

    def test_real_data_conversion_and_digest(self):
        x=self.sdk.call("data.convert",["180","kmh","mps"])
        self.assertEqual(x["result"]["exact"],{"numerator":50,"denominator":1})
        self.assertEqual(x["response"]["result_sha256"],k.digest(x["result"]))
        r.check(x["response"],self.sdk._schemas["integration-response.v1"])
        self.assertFalse(x["response"]["execution_authorized"])
        self.assertEqual(x,self.sdk.call("data.convert",["180","kmh","mps"]))

    def test_reuse_and_detachment(self):
        c=self.sdk._service("content")
        self.assertIs(c.data,self.sdk._service("data"))
        self.assertIs(self.sdk._service("modding").registry,c)
        x=self.sdk.call("content.inspect",["vehicle.demo","1.0.0"])
        x["result"]["entity"]["name"]="tamper"
        self.assertNotEqual(self.sdk.call("content.inspect",["vehicle.demo","1.0.0"])["result"]["entity"]["name"],"tamper")

    def test_permissions_and_unknown(self):
        for cid in s.DENIED:
            for profile in ("reader","planner"):
                self.assertEqual(self.sdk.call(cid,profile=profile)["response"]["status"],"BLOCKED")
        self.assertEqual(self.sdk.call("unknown.capability")["result"]["reason"],"UNKNOWN_CAPABILITY")
        self.assertEqual(self.sdk.call("persistence.simulate",["career-baseline","3.0.0"])["result"]["reason"],"PLANNER_PROFILE_REQUIRED")
        self.assertEqual(self.sdk.call("asset.plan",["original"],profile="planner")["response"]["status"],"NOT_RUN")

    def test_no_arbitrary_method_or_path(self):
        with self.assertRaises(ValueError):
            self.sdk.call("asset.plan",["../private"],profile="planner")
        with self.assertRaises(ValueError):
            self.sdk.call("data.convert",["180","kmh","mps","extra"])
        with self.assertRaises(ValueError):
            self.sdk.call("knowledge.queue",["999999"])
        with self.assertRaises(ValueError):
            self.sdk.call("knowledge.search",["x\nx"])
        with self.assertRaises(ValueError):
            self.sdk.call("data.validate",profile="owner")
        with self.assertRaises(ValueError):
            self.sdk.call("data.validate",["x"*257])

    def test_structured_request(self):
        change=r.read(s.ROOT/"docs/architecture/change.foundation.example.json")
        x=self.sdk.call("architecture.impact",profile="planner",change=change)
        self.assertEqual(x["response"]["status"],"NOT_RUN")
        with self.assertRaises(ValueError):
            self.sdk.call("architecture.impact",profile="planner")
        with self.assertRaises(ValueError):
            self.sdk.call("data.validate",change=change)
        selection=r.read(s.ROOT/"docs/modding/selection.example.json")
        x=self.sdk.call("modding.resolve",profile="planner",selection=selection)
        self.assertEqual(len(x["result"]["load_order"]),4)
        self.assertEqual(self.sdk.call("modding.gate",profile="planner",selection=selection)["response"]["status"],"BLOCKED")

    def test_request_schema_closed(self):
        x=r.read(s.DOCS/"request.example.json")
        self.assertEqual(self.sdk.request(x)["response"]["status"],"PASS")
        with self.assertRaises(ValueError):
            self.sdk.request(dict(x,command="shell"))
        with self.assertRaises(ValueError):
            self.sdk.request(dict(x,args=[True]))

    def test_scenario(self):
        x=self.sdk.scenario()
        self.assertEqual(x["status"],"PASS")
        self.assertEqual(len(x["checks"]),11)
        self.assertTrue(all(x["checks"].values()))
        self.assertTrue(x["source_unchanged"])
        self.assertEqual(x["core2"]["migration_steps"],2)
        self.assertEqual(x["hyper"]["vehicle"],"vehicle.demo")
        self.assertEqual(x["historical_receipt"]["test_count"],111)
        self.assertEqual(x["native_readiness"],"BLOCKED")

    def test_drift(self):
        x=self.sdk.drift()
        self.assertEqual(x["drift_count"],2)
        self.assertFalse(x["live_verified"])
        by_id={r["id"]:r for r in x["repositories"]}
        self.assertEqual(by_id["lab"]["state"],"MATCH_OBSERVED")
        self.assertEqual(by_id["core2"]["state"],"DRIFT_OBSERVED")

    def test_consumer_plan(self):
        row=self.sdk._snapshots["core2"]
        x=self.sdk.plan("core2",row["observed_revision"])
        self.assertEqual(x["status"],"BLOCKED")
        self.assertIn("PIN_RECONCILIATION_REQUIRED",x["reasons"])
        self.assertIn("save",x["deferred_contracts"])
        self.assertEqual(x["historical_native_observations"][0]["scope"],"CORE2_FAST_PUSH")
        self.assertEqual(x["historical_native_observations"][0]["status"],"PASS")
        self.assertTrue(all(y["status"]=="NOT_RUN" for y in x["validation"]))
        self.assertIn("UNKNOWN_REVISION",self.sdk.plan("core2","0"*40)["reasons"])
        self.assertNotIn("PIN_RECONCILIATION_REQUIRED",self.sdk.plan("core2",row["pinned_revision"])["reasons"])

    def test_debt_order_and_cycles(self):
        x=self.sdk.debt_report()
        self.assertEqual(x["items"],15)
        order=x["dependency_first_order"]
        for item in x["entries"]:
            for parent in item["depends_on"]:
                self.assertLess(order.index(parent),order.index(item["id"]))
        bad=copy.deepcopy(self.sdk._debt)
        bad["pin-core2"]["depends_on"]=["core2-adapter"]
        with self.assertRaises(ValueError):
            s.topological(bad)

    def test_doctor_failure_not_hidden(self):
        with patch.object(self.sdk._service("evidence"),"stats",return_value={"status":"FAIL"}):
            x=self.sdk.doctor()
            self.assertEqual(x["status"],"FAIL")
            self.assertEqual(x["passed"],10)

    def test_cli_exit_status(self):
        with patch("sys.stdout",new_callable=io.StringIO) as out:
            self.assertEqual(cli.main(["call","data.convert","180","kmh","mps"]),0)
            self.assertEqual(json.loads(out.getvalue())["response"]["status"],"PASS")
        with patch("sys.stdout",new_callable=io.StringIO):
            self.assertEqual(cli.main(["call","release.test-build"]),1)
        with patch("sys.stderr",new_callable=io.StringIO):
            self.assertEqual(cli.main(["call","data.convert","180"]),2)

if __name__=="__main__":
    unittest.main()
