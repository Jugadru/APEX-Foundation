#!/usr/bin/env python3
"""APEX Foundation unified, read-only SDK. No execution from registry strings."""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
import heapq
from pathlib import Path
import re

import apex_foundation as legacy
import apex_foundation_registry as reg
import apex_knowledge as knowledge
import apex_architecture as architecture
import apex_data_center as datasets
import apex_content_registry as content
import apex_config as config
import apex_persistence as persistence
import apex_evidence as evidence
import apex_modding as modding
import apex_reconcile as reconcile

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/"docs"/"integration"
VERSION="0.5.1"
STATES={"PASS","FAIL","NOT_RUN","INCONCLUSIVE","BLOCKED"}
# Static code routes. Neither manifests nor request data select Python attributes.
# Tuple: service, method, min/max positional arguments, profile, structured field.
ROUTES={
    "foundation.validate":("sdk","registry_report",0,0,"reader",None),
    "foundation.search":("sdk","legacy_search",1,1,"reader",None),
    "foundation.compatibility":("sdk","compatibility",4,4,"reader",None),
    "asset.plan":("sdk","asset_plan",1,1,"planner",None),
    "knowledge.inspect":("knowledge","stats",0,0,"reader",None),
    "knowledge.search":("knowledge","search",1,1,"reader",None),
    "knowledge.queue":("sdk","research_queue",0,1,"reader",None),
    "knowledge.plan":("knowledge","plan",1,1,"planner",None),
    "architecture.graph":("architecture","graph",0,0,"reader",None),
    "architecture.inspect":("architecture","show",1,1,"reader",None),
    "architecture.impact":("architecture","impact",0,0,"planner","change"),
    "architecture.contract-diff":("architecture","contract_diff",0,0,"reader",None),
    "architecture.gate":("architecture","gate",0,0,"planner","change"),
    "data.validate":("data","stats",0,0,"reader",None),
    "data.inspect":("data","show",2,2,"reader",None),
    "data.diff":("data","diff",3,3,"reader",None),
    "data.convert":("sdk","convert",3,3,"reader",None),
    "data.gate":("data","gate",4,4,"planner",None),
    "data.query":("data","query",2,3,"reader",None),
    "content.validate":("content","stats",0,0,"reader",None),
    "content.search":("content","search",1,2,"reader",None),
    "content.inspect":("content","show",2,2,"reader",None),
    "content.graph":("content","graph",2,2,"reader",None),
    "content.diff":("content","diff",3,3,"reader",None),
    "content.gate":("content","gate",4,4,"planner",None),
    "config.validate":("config","stats",0,0,"reader",None),
    "config.inspect":("config","show",2,2,"reader",None),
    "config.resolve":("config","resolve",2,2,"reader",None),
    "config.diff":("config","diff",3,3,"reader",None),
    "config.rollback":("config","rollback",2,2,"planner",None),
    "config.gate":("config","gate",4,4,"planner",None),
    "persistence.validate":("persistence","stats",0,0,"reader",None),
    "persistence.inspect":("persistence","inspect",1,1,"reader",None),
    "persistence.plan":("persistence","plan",2,2,"planner",None),
    "persistence.simulate":("persistence","simulate",2,2,"planner",None),
    "persistence.recovery":("sdk","recovery",1,1,"planner",None),
    "persistence.gate":("persistence","gate",3,3,"planner",None),
    "evidence.validate":("evidence","stats",0,0,"reader",None),
    "evidence.history":("evidence","history",0,0,"reader",None),
    "evidence.inspect":("evidence","show",1,1,"reader",None),
    "evidence.integrity":("evidence","verify",1,1,"reader",None),
    "evidence.compare":("evidence","compare",2,2,"reader",None),
    "evidence.gate":("evidence","gate",1,1,"planner",None),
    "evidence.notes":("sdk","notes",0,0,"reader",None),
    "modding.validate":("modding","stats",0,0,"reader",None),
    "modding.inspect":("modding","show",2,2,"reader",None),
    "modding.resolve":("modding","plan",0,0,"planner","selection"),
    "modding.package":("modding","package",2,2,"planner",None),
    "modding.remove":("modding","remove",1,1,"planner","selection"),
    "modding.rollback":("modding","rollback",1,1,"planner","selection"),
    "modding.gate":("modding","gate",0,0,"planner","selection"),
    "integration.health":("sdk","doctor",0,0,"reader",None),
    "integration.catalog":("sdk","catalog",0,0,"reader",None),
    "integration.plan":("sdk","plan",2,2,"planner",None),
    "integration.scenario":("sdk","scenario",0,0,"planner",None),
    "integration.debt":("sdk","debt_report",0,0,"reader",None),
    "integration.drift":("sdk","drift",0,0,"reader",None),
    "integration.reconcile":("reconciliation","stats",0,0,"reader",None),
    "integration.native-evidence":("reconciliation","native_report",0,0,"reader",None),
    "integration.candidates":("reconciliation","candidate_report",0,0,"reader",None),
}
DENIED={
    "lab.request":"OWNER_HOSTED_WORKFLOW_ONLY",
    "quality.fast":"NATIVE_CI_ONLY",
    "saveguard.check":"NATIVE_SAVEGUARD_ONLY",
    "performance.report":"EXPLICIT_LOCAL_TOOL_ONLY",
    "graphics.inspect":"OWNER_HOSTED_WORKFLOW_ONLY",
    "release.test-build":"OWNER_HOSTED_WORKFLOW_ONLY",
    "modding.zip":"EXPLICIT_LOCAL_TOOL_ONLY",
}
NATIVE={
    "core2":["FAST exact candidate SHA","Native SaveGuard baseline/candidate","Read-only metadata mapping and regressions"],
    "hyper":["Independent native longitudinal fixture","Exact candidate SHA contract tests","Read-only metadata mapping"],
    "lab":["Existing owner-authorized diagnostic workflow","Exact producer/consumer SHA and actual artifact hashes"],
}
SAFE_ERRORS=(ValueError,TypeError,KeyError,OSError,AttributeError,RecursionError,RuntimeError)

def topological(rows):
    deps={ident:set(row["depends_on"]) for ident,row in rows.items()}
    reverse=defaultdict(set)
    for ident,parents in deps.items():
        if ident in parents or not parents<=rows.keys():
            raise ValueError("invalid debt dependency")
        for parent in parents:
            reverse[parent].add(ident)
    ready=[(rows[i]["priority"],i) for i,parents in deps.items() if not parents]
    heapq.heapify(ready)
    order=[]
    while ready:
        _,ident=heapq.heappop(ready)
        order.append(ident)
        for child in reverse[ident]:
            deps[child].remove(ident)
            if not deps[child]:
                heapq.heappush(ready,(rows[child]["priority"],child))
    if len(order)!=len(rows):
        raise ValueError("debt cycle")
    return order

class FoundationSDK:
    def __init__(self):
        self._reg,self._schemas=reg.load_registry()
        self._registry_report=reg.validate_registry(self._reg,self._schemas)
        self._caps=reg.unique(self._reg["capabilities"])
        if set(ROUTES)&set(DENIED) or set(ROUTES)|set(DENIED)!=set(self._caps):
            raise ValueError("gateway route coverage mismatch")
        for cid in ROUTES:
            # One reviewed local alias is the sole read.local exception.
            allowed=["read.local"] if cid=="asset.plan" else ["read.repository"]
            if self._caps[cid]["permissions"]!=allowed:
                raise ValueError("gateway permission drift")
        self._services={}
        self._snapshots=reg.unique(knowledge.document(DOCS/"repositories.json",{"entries"})["entries"])
        self._debt=reg.unique(knowledge.document(DOCS/"debt.json",{"entries"})["entries"])
        self._validate_snapshots()
        self._validate_debt()
        self._snapshot_digest=knowledge.digest({"registry":self._reg,"schemas":self._schemas,
                                              "repositories":self._snapshots,"debt":self._debt})
    def _service(self,name):
        if name=="sdk":
            return self
        if name not in self._services:
            # Static loader selection; dependencies shared within this session.
            if name=="knowledge":
                obj=knowledge.load()
            elif name=="architecture":
                obj=architecture.load()
            elif name=="data":
                obj=datasets.load(knowledge=self._service("knowledge"),architecture=self._service("architecture"))
            elif name=="content":
                obj=content.load(data=self._service("data"))
            elif name=="config":
                obj=config.load(data=self._service("data"),architecture=self._service("architecture"))
            elif name=="persistence":
                obj=persistence.load(architecture=self._service("architecture"))
            elif name=="evidence":
                obj=evidence.load(architecture=self._service("architecture"))
            elif name=="modding":
                obj=modding.load(registry=self._service("content"))
            elif name=="reconciliation":
                obj=reconcile.load(self._schemas,self._snapshots,self._service("architecture"))
            else:
                raise ValueError("unknown internal service")
            self._services[name]=obj
        return self._services[name]

    def _validate_snapshots(self):
        arch=self._service("architecture")
        if set(self._snapshots)!=set(arch.repos):
            raise ValueError("repository coverage mismatch")
        for ident,row in self._snapshots.items():
            reg.check(row,self._schemas["integration-repository.v1"])
            source=arch.repos[ident]
            if (row["repository"]!=source["repository"] or row["pinned_revision"]!=source["revision"] or
                row["source_url"]!=f"https://github.com/{row['repository']}/commit/{row['observed_revision']}"):
                raise ValueError("snapshot/pin mismatch")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",row["observed_on"]):
                raise ValueError("invalid observation date")
            date.fromisoformat(row["observed_on"])
    def _validate_debt(self):
        if not 1<=len(self._debt)<=1000:
            raise ValueError("debt registry size")
        owners={x["id"] for x in self._reg["modules"]}
        for row in self._debt.values():
            reg.check(row,self._schemas["integration-debt.v1"])
            if row["owner"] not in owners:
                raise ValueError("unknown debt owner")
            if row["status"]!=("BLOCKED" if row["depends_on"] else "NOT_RUN"):
                raise ValueError("unsupported debt readiness claim")
        self._debt_order=topological(self._debt)

    def catalog(self):
        rows=[]
        for cid,cap in sorted(self._caps.items()):
            route=ROUTES.get(cid)
            rows.append({"id":cid,"module":cap["module"],"permissions":cap["permissions"],
                         "mode":"OFFLINE_ROUTE" if route else "EXTERNAL_ONLY",
                         "profile":route[4] if route else None,"structured_field":route[5] if route else None,
                         "arguments":{"minimum":route[2],"maximum":route[3]} if route else None,
                         "reason":DENIED.get(cid),"execution_authorized":False})
        return {"status":"PASS","capabilities":len(rows),"offline_routes":len(ROUTES),
                "external_only":len(DENIED),"entries":rows,"execution_authorized":False}

    def registry_report(self):
        return dict(self._registry_report,catalog=legacy.validate())

    def legacy_search(self,query):
        return reg.search(query)

    def compatibility(self,left,lv,right,rv):
        return reg.compatibility(self._reg,left,lv,right,rv)

    def asset_plan(self,alias):
        files={"original":"asset_jobs.original.example.json","blocked":"asset_jobs.example.json"}
        if alias not in files:
            raise ValueError("only registered asset example aliases allowed")
        result=legacy.plan(ROOT/"docs"/"references"/files[alias])
        return {"status":"NOT_RUN","scope":"original legacy plan only","plan":result,"execution_authorized":False}

    def research_queue(self,limit="20"):
        if not re.fullmatch(r"[0-9]{1,3}",limit) or not 1<=int(limit)<=100:
            raise ValueError("queue limit must be 1..100")
        return self._service("knowledge").queue(int(limit))

    def convert(self,value,source,target):
        return self._service("data").units.convert(value,source,target)

    def recovery(self,scenario):
        obj=self._service("persistence")
        return obj.recovery(obj.scenario(scenario))

    def notes(self):
        obj=self._service("evidence")
        return {"entries":[obj.notes[i] for i in sorted(obj.notes)],"release_authorized":False}

    def drift(self):
        rows=[dict(row,state="MATCH_OBSERVED" if row["pinned_revision"]==row["observed_revision"] else "DRIFT_OBSERVED")
              for _,row in sorted(self._snapshots.items())]
        return {"status":"NOT_RUN","scope":"historical head observation; no live check",
                "drift_count":sum(x["state"]=="DRIFT_OBSERVED" for x in rows),
                "repositories":rows,"live_verified":False,"execution_authorized":False}

    def debt_report(self):
        order=self._debt_order
        return {"status":"NOT_RUN","items":len(order),
                "priorities":dict(sorted(Counter(x["priority"] for x in self._debt.values()).items())),
                "ready_for_review":[i for i in order if not self._debt[i]["depends_on"]],
                "dependency_first_order":order,
                "entries":[self._debt[i] for i in order],"execution_authorized":False}

    def plan(self,repository,revision):
        if repository not in self._snapshots or not architecture.sha(revision):
            raise ValueError("expected registered repository and exact SHA")
        row=self._snapshots[repository]
        arch=self._service("architecture")
        modules=sorted(i for i,o in arch.owners.items() if o["repository"]==repository)
        contracts=sorted(i for i,b in arch.bindings.items() if {b["steward"],*b["consumers"]}&set(modules))
        deferred=[i for i in contracts if arch.contracts[i]["status"]=="deferred"]
        reasons=["NATIVE_VALIDATION_NOT_RUN","NO_RUNTIME_ADAPTER","OWNER_REVIEW_REQUIRED"]
        if revision!=row["pinned_revision"]:
            reasons.append("PIN_RECONCILIATION_REQUIRED")
        if revision not in (row["pinned_revision"],row["observed_revision"]):
            reasons.append("UNKNOWN_REVISION")
        if deferred:
            reasons.append("DEFERRED_RUNTIME_CONTRACTS")
        audit=self._service("reconciliation")
        matches=[x for x in audit.native.values() if x["repository"]==repository and x["revision"]==revision]
        if revision==row["observed_revision"]:
            reasons.append("SOURCE_REVIEW_REQUIRED")
        return {"status":"BLOCKED","repository":repository,"requested_revision":revision,
                "historical_native_observations":[{"id":x["id"],"scope":x["scope"],"status":x["status"],"run_url":x["run_url"]} for x in sorted(matches,key=lambda x:x["id"])],
                "pinned_revision":row["pinned_revision"],"observed_revision":row["observed_revision"],
                "modules":modules,"metadata_contracts":[i for i in contracts if i not in deferred],
                "deferred_contracts":deferred,"reasons":reasons,
                "validation":[{"requirement":x,"status":"NOT_RUN"} for x in NATIVE[repository]],
                "steps":["Audit requested exact revision","Review pin changes and existing native authority",
                         "Develop separate read-only consumer adapter if approved","Run native tests and retain exact evidence"],
                "runtime_verified":False,"execution_authorized":False}

    def doctor(self):
        checks=[]
        tasks=[("registry",self.registry_report)]
        for name in ("knowledge","architecture","data","content","config","persistence","evidence","modding","reconciliation"):
            tasks.append((name,lambda n=name:self._service(n).stats()))
        tasks.append(("asset-plan",lambda:self.asset_plan("original")))
        for name,fn in tasks:
            try:
                result=fn()
                # Asset plan is a non-executed plan; its check is structural only.
                valid=result.get("status")=="PASS" or (name=="asset-plan" and result["plan"]["executed"] is False
                       and all(x["status"]=="PLANNED" for x in result["plan"]["jobs"]))
                checks.append({"service":name,"status":"PASS" if valid else "FAIL",
                               "scope":result.get("scope","local structure"),"result_sha256":knowledge.digest(result)})
            except SAFE_ERRORS as exc:
                checks.append({"service":name,"status":"FAIL","error":str(exc)[:200]})
        return {"status":"PASS" if all(x["status"]=="PASS" for x in checks) else "FAIL",
                "scope":"local offline checks only","version":VERSION,"checks":checks,
                "local_checks":len(checks),"passed":sum(x["status"]=="PASS" for x in checks),
                "offline_routes":len(ROUTES),"external_only":len(DENIED),
                "snapshot_sha256":self._snapshot_digest,"drift_count":self.drift()["drift_count"],
                "native_readiness":"BLOCKED","runtime_verified":False,"execution_authorized":False}

    def scenario(self):
        """Exercise actual registered links, two isolated consumer plans, and negative gates."""
        data=self._service("data")
        c=self._service("content")
        cfg=self._service("config")
        p=self._service("persistence")
        e=self._service("evidence")
        m=self._service("modding")
        vehicle=c.show("vehicle.demo","1.0.0")["entity"]
        link=vehicle["datasets"][0]
        record=data.query(link["id"],link["version"],link["record"])["records"][0]
        converted=data.units.convert(str(record["values"]["speed_kmh"]),"kmh","mps")
        core_sha=self._snapshots["core2"]["pinned_revision"]
        hyper_sha=self._snapshots["hyper"]["pinned_revision"]
        core_selection={"consumer":"core2","revision":core_sha,"requested":[{"id":"demo.season","version":"1.0.0"}]}
        hyper_selection={"consumer":"hyper","revision":hyper_sha,"requested":[{"id":"demo.hyper","version":"1.0.0"}]}
        before=knowledge.digest({"content":list(c.entries.values()),"saves":p.fixtures})
        core_plan=m.plan(core_selection)
        hyper_plan=m.plan(hyper_selection)
        core_config=cfg.resolve("core2-development","1.1.0")
        hyper_config=cfg.resolve("hyper-technical","1.0.0")
        migration=p.simulate("career-baseline","3.0.0")
        recovery=self.recovery("corrupt-primary")
        history=e.show("v0.4.0-main")["record"]
        gates=[data.gate(link["id"],link["version"],"hyper",hyper_sha),
               c.gate("vehicle.demo","1.0.0","hyper",hyper_sha),
               cfg.gate("hyper-technical","1.0.0","hyper",hyper_sha),
               p.gate("career-baseline","core2",core_sha),
               m.gate(core_selection),e.gate(history["revision"])]
        after=knowledge.digest({"content":list(c.entries.values()),"saves":p.fixtures})
        checks={
            "shared_data_instance":c.data is data,
            "shared_content_instance":m.registry is c,
            "exact_dataset_link":record["id"]==link["record"],
            "core2_preview":core_plan["status"]=="NOT_RUN" and len(core_plan["preview"])==4,
            "hyper_preview":hyper_plan["status"]=="NOT_RUN" and hyper_plan["preview"][0]["target"]==vehicle["id"],
            "consumer_config_isolation":core_config["profile"]["consumer"]=="core2" and hyper_config["profile"]["consumer"]=="hyper",
            "migration_preserved":migration["status"]=="PASS" and migration["progress_preserved"] and migration["source_unchanged"],
            "recovery_not_applied":recovery["decision"]=="REVIEW_BACKUPS" and recovery["restored"] is False,
            "historical_receipt_scope":history["scope"]=="FOUNDATION_PYTHON_ONLY",
            "negative_gates":all(x["status"]=="BLOCKED" for x in gates),
            "source_immutable":before==after,
        }
        return {"status":"PASS" if all(checks.values()) else "FAIL","scope":"integrated synthetic scenario only",
                "checks":checks,"source_sha256":before,"source_unchanged":before==after,
                "core2":{"revision":core_sha,"mod_order":core_plan["load_order"],"config_sha256":core_config["effective_sha256"],
                         "migration_steps":migration["steps"],"recovery_candidates":recovery["candidates"]},
                "hyper":{"revision":hyper_sha,"vehicle":vehicle["id"],"dataset":link,"converted_speed":converted,
                         "mod_order":hyper_plan["load_order"],"config_sha256":hyper_config["effective_sha256"]},
                "historical_receipt":{"id":history["id"],"revision":history["revision"],"test_count":history["test_count"]},
                "native_readiness":"BLOCKED","runtime_verified":False,"execution_authorized":False}

    def request(self,request):
        reg.check(request,self._schemas["integration-request.v1"])
        cid=request["capability"]
        args=request["args"]
        if len(request["id"])>100 or len(cid)>100 or len(args)>8 or any(len(x)>256 or any(ord(c)<32 for c in x) for x in args):
            raise ValueError("request bounds exceeded")
        if cid not in self._caps:
            result={"status":"BLOCKED","reason":"UNKNOWN_CAPABILITY"}
        elif cid in DENIED:
            result={"status":"BLOCKED","reason":DENIED[cid]}
        else:
            service,method,lo,hi,profile,field=ROUTES[cid]
            if not lo<=len(args)<=hi or any((request[f] is not None)!=(f==field) for f in ("change","selection")):
                raise ValueError("argument or structured field mismatch")
            if profile=="planner" and request["profile"]!="planner":
                result={"status":"BLOCKED","reason":"PLANNER_PROFILE_REQUIRED"}
            else:
                # Method comes only from static reviewed ROUTES, never registry metadata.
                params=([deepcopy(request[field])] if field else [])+list(args)
                result=getattr(self._service(service),method)(*params)
        result=deepcopy(result)
        status=result.get("status","PASS") if isinstance(result,dict) else "PASS"
        if status not in STATES:
            raise ValueError("unsupported result status")
        envelope={"id":request["id"],"capability":cid,"status":status,"scope":"OFFLINE_ONLY",
                  "result_sha256":knowledge.digest(result),"execution_authorized":False}
        reg.check(envelope,self._schemas["integration-response.v1"])
        return {"response":envelope,"result":result}

    def call(self,capability,args=None,*,profile="reader",change=None,selection=None,request_id="request.local"):
        return self.request({"id":request_id,"capability":capability,"profile":profile,
                             "args":[] if args is None else list(args),"change":change,"selection":selection})
