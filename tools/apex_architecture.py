#!/usr/bin/env python3
"""Architecture intelligence over declared metadata; no runtime inspection or execution."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path, PurePosixPath
import re
import sys

import apex_foundation_registry as r
import apex_knowledge as k

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "architecture"
VERSION = "0.3.0"
BASE = "4232e91fcf1bb83414145fa42d8945ddb2a7cd9b"
REPOS = {"core2":"Jugadru/APEX-Simulation","hyper":"Jugadru/APEX-Hyper-Engine",
         "lab":"Jugadru/apex-godot-simulation-architect"}
SCOPE = "Declared dependency graph and candidate ownership; not a runtime import graph"

def sha(value):
    return isinstance(value,str) and bool(re.fullmatch(r"[0-9a-f]{40}",value))

def valid_path(value):
    if not isinstance(value,str) or not 1 <= len(value) <= 512:
        return False
    p = PurePosixPath(value)
    return (not p.is_absolute() and str(p)==value and
            all(part not in ("",".","..") for part in value.split("/")) and
            bool(re.fullmatch(r"[A-Za-z0-9_. /+-]+",value)))

def indexed(rows):
    if type(rows) is not list:
        raise ValueError("expected list")
    return r.unique(rows)

def load():
    reg, schemas = r.load_registry()
    r.validate_registry(reg,schemas)
    own=k.document(DOCS/"ownership.json",{"modules","contracts"})
    inv=k.document(DOCS/"source-inventory.json",{"repositories"})
    baseline=k.document(DOCS/"contract-baseline.json",{"revision","schemas"})
    return Architecture(reg,schemas,own,inv,baseline)

class Architecture:
    def __init__(self,reg,schemas,own,inv,baseline):
        self.registry=reg
        self.schemas=schemas
        self.modules=indexed(reg["modules"])
        self.caps=indexed(reg["capabilities"])
        self.contracts=indexed(reg["contracts"])
        self.owners=indexed(own["modules"])
        self.bindings=indexed(own["contracts"])
        self.repos=indexed(inv["repositories"])
        self.baseline=baseline
        if set(self.owners)!=set(self.modules) or set(self.bindings)!=set(self.contracts):
            raise ValueError("ownership coverage mismatch")
        if set(self.repos)!=set(REPOS) or baseline["revision"]!=BASE:
            raise ValueError("invalid baseline/repositories")
        if type(baseline["schemas"]) is not dict or not baseline["schemas"]:
            raise ValueError("empty contract baseline")
        for schema in baseline["schemas"].values():
            r.schema_check(schema)
        for row in self.owners.values():
            r.check(row,schemas["architecture-module.v1"])
            mid=row["id"]
            if (self.modules[mid]["maturity"]=="planned")!=(row["role"]=="planned"):
                raise ValueError("planned role mismatch")
        if {x["id"] for x in self.owners.values() if x["role"]=="sporting-authority"}!={"core2"}:
            raise ValueError("sporting authority conflict")
        if self.owners["hyper"]["role"]!="experimental-authority" or self.owners["presentation"]["role"]!="read-only-consumer":
            raise ValueError("authority boundary mismatch")
        for row in self.bindings.values():
            r.check(row,schemas["architecture-contract.v1"])
            if row["steward"] not in self.modules or not set(row["consumers"])<=self.modules.keys():
                raise ValueError("unknown contract participant")
            if (row["scope"]=="metadata")!=(self.contracts[row["id"]]["status"]=="active"):
                raise ValueError("contract maturity mismatch")
        self.paths={}
        for rid,row in self.repos.items():
            k.strict_fields(row,{"id","repository","revision","scope","paths"})
            if row["repository"]!=REPOS[rid] or not sha(row["revision"]) or not k.nonempty(row["scope"]):
                raise ValueError("invalid repo inventory")
            if type(row["paths"]) is not list or not row["paths"]:
                raise ValueError("empty repo inventory")
            for item in row["paths"]:
                k.strict_fields(item,{"path","blob_sha","modules"})
                key=(rid,item["path"])
                mids=item["modules"]
                if (not valid_path(item["path"]) or not sha(item["blob_sha"]) or key in self.paths
                    or type(mids) is not list or not mids or len(set(mids))!=len(mids)
                    or not set(mids)<=self.modules.keys()):
                    raise ValueError("invalid path mapping")
                if any(self.owners[m]["repository"]!=rid and self.owners[m]["repository"]!="external" for m in mids):
                    raise ValueError("path mapped across repository boundary")
                self.paths[key]=item
        self.deps={mid:set(row["dependencies"]) for mid,row in self.modules.items()}
        self.reverse=defaultdict(set)
        for mid,deps in self.deps.items():
            for dep in deps:
                if dep not in self.modules:
                    raise ValueError("unknown dependency")
                self.reverse[dep].add(mid)
        self.order=self.topological()
        self.fingerprint=k.digest({"registry":reg,"schemas":schemas,"ownership":own,"inventory":inv,"baseline":baseline})

    def topological(self):
        remaining={mid:set(deps) for mid,deps in self.deps.items()}
        order=[]
        while remaining:
            ready=sorted(mid for mid,deps in remaining.items() if not deps)
            if not ready:
                raise ValueError("architecture dependency cycle")
            order.extend(ready)
            for mid in ready:
                del remaining[mid]
            for deps in remaining.values():
                deps.difference_update(ready)
        return order

    @staticmethod
    def closure(seeds,graph):
        found=set(seeds)
        todo=list(seeds)
        while todo:
            for mid in graph.get(todo.pop(),set()):
                if mid not in found:
                    found.add(mid)
                    todo.append(mid)
        return sorted(found-set(seeds))

    def graph(self):
        return {"scope":SCOPE,"fingerprint":self.fingerprint,
                "nodes":[{"id":m,**self.owners[m]} for m in sorted(self.modules)],
                "edges":[{"consumer":m,"dependency":dep,"state":"DECLARED"}
                         for m in sorted(self.deps) for dep in sorted(self.deps[m])],
                "dependency_first_order":self.order,"runtime_verified":False}

    def show(self,mid):
        row=self.modules[mid]
        return {"module":row,"ownership":self.owners[mid],
                "direct_dependencies":sorted(self.deps[mid]),
                "transitive_dependencies":self.closure([mid],self.deps),
                "direct_dependents":sorted(self.reverse[mid]),
                "transitive_dependents":self.closure([mid],self.reverse),
                "capabilities":sorted(c for c,x in self.caps.items() if x["module"]==mid),
                "contract_bindings":[x for _,x in sorted(self.bindings.items())
                                    if mid==x["steward"] or mid in x["consumers"]],
                "source_candidates":[{"repository":repo,**x} for (repo,_),x in sorted(self.paths.items()) if mid in x["modules"]],
                "runtime_verified":False}

    def stats(self):
        return {"status":"PASS","scope":SCOPE,"version":VERSION,"fingerprint":self.fingerprint,
                "modules":len(self.modules),"capabilities":len(self.caps),
                "active_contracts":len(self.schemas),"deferred_contracts":len(self.contracts)-len(self.schemas),
                "declared_edges":sum(map(len,self.deps.values())),
                "candidate_contract_bindings":len(self.bindings),
                "pinned_external_repositories":len(self.repos),"candidate_paths":len(self.paths),
                "candidate_paths_by_repository":dict(sorted(Counter(repo for repo,_ in self.paths).items())),
                "unverified_module_versions":sorted(m for m,x in self.modules.items() if x["version"] is None),
                "runtime_verified":False,"execution_authorized":False}

    def contract_diff(self):
        old=self.baseline["schemas"]
        rows=[]
        for cid in sorted(old.keys()|self.schemas.keys()):
            before=old.get(cid)
            after=self.schemas.get(cid)
            state=("ADDED" if before is None else "REMOVED" if after is None else
                   "UNCHANGED" if before==after else "CHANGED_REVIEW_REQUIRED")
            rows.append({"id":cid,"state":state,"before_sha256":k.digest(before) if before is not None else None,
                         "after_sha256":k.digest(after) if after is not None else None})
        breaking=any(x["state"] in ("REMOVED","CHANGED_REVIEW_REQUIRED") for x in rows)
        return {"baseline":self.baseline["revision"],"status":"BLOCKED" if breaking else "PASS",
                "scope":"exact structural comparison only; no semantic compatibility claim",
                "contracts":rows,"execution_authorized":False}

    def impact(self,manifest):
        r.check(manifest,self.schemas["architecture-change.v1"])
        repo=manifest["repository"]
        expected=BASE if repo=="foundation" else self.repos[repo]["revision"]
        if not (manifest["modules"] or manifest["contracts"] or manifest["paths"]):
            raise ValueError("empty change manifest")
        if not set(manifest["modules"])<=self.modules.keys() or not set(manifest["contracts"])<=self.contracts.keys():
            raise ValueError("unknown module or contract")
        if len(manifest["paths"])>500:
            raise ValueError("path limit")
        seeds=set(manifest["modules"])
        contract_participants=set()
        unmapped=[]
        path_matches=[]
        for cid in manifest["contracts"]:
            binding=self.bindings[cid]
            contract_participants.update([binding["steward"],*binding["consumers"]])
        for path in manifest["paths"]:
            if not valid_path(path):
                raise ValueError("unsafe change path")
            if repo=="foundation":
                # Foundation is its own metadata repository, not a sporting runtime.
                mids=(["persistence-management"] if path.startswith(("docs/persistence/","data/persistence/")) or path in ("tools/apex_persistence.py","tools/tests/test_apex_persistence.py") else
                      ["configuration-management"] if path.startswith(("docs/config/","data/config/")) or path in ("tools/apex_config.py","tools/tests/test_apex_config.py") else
                      ["content-registry"] if path.startswith(("docs/content/","data/content/")) or path in ("tools/apex_content_registry.py","tools/tests/test_apex_content_registry.py") else
                      ["data-center"] if path.startswith(("docs/data/","data/datasets/")) or path in ("tools/apex_data_center.py","tools/tests/test_apex_data_center.py") else
                      ["asset-factory"] if path in ("tools/apex_asset_build.py","tools/apex_blender_scaffold.py","tools/tests/test_apex_asset_build.py") else
                      ["foundation"] if path in ("README.md","AGENTS.md",".gitignore",".github/workflows/foundation-ci.yml",
                          "tools/apex_foundation.py","tools/apex_foundation_registry.py","tools/apex_knowledge.py","tools/apex_architecture.py",
                          "tools/tests/test_apex_foundation.py","tools/tests/test_apex_foundation_registry.py","tools/tests/test_apex_knowledge.py","tools/tests/test_apex_architecture.py")
                          or path.startswith(("docs/architecture/","docs/foundation/","docs/knowledge/","docs/references/")) else [])
            else:
                mids=self.paths.get((repo,path),{}).get("modules",[])
            if not mids:
                unmapped.append(path)
            else:
                seeds.update(mids)
                path_matches.append({"path":path,"modules":sorted(mids),"state":"CANDIDATE"})
        affected=seeds|contract_participants
        downstream=self.closure(affected,self.reverse)
        impacted=sorted(affected|set(downstream))
        reasons=[]
        foreign=sorted(m for m in manifest["modules"] if self.owners[m]["repository"]!=repo)
        if foreign:
            reasons.append("MODULE_REPOSITORY_MISMATCH")
        if manifest["base_revision"]!=expected:
            reasons.append("STALE_OR_UNKNOWN_REVISION")
        if unmapped:
            reasons.append("UNMAPPED_PATHS")
        if any(self.contracts[c]["status"]=="deferred" for c in manifest["contracts"]):
            reasons.append("DEFERRED_RUNTIME_CONTRACT")
        if self.contract_diff()["status"]!="PASS":
            reasons.append("SCHEMA_CHANGE_REQUIRES_REVIEW")
        if repo!="foundation":
            reasons.append("CONSUMER_VALIDATION_REQUIRED")
        return {"status":"BLOCKED" if reasons else "NOT_RUN","scope":SCOPE,"repository":repo,
                "expected_revision":expected,"requested_revision":manifest["base_revision"],
                "direct_modules":sorted(seeds),"foreign_declared_modules":foreign,"contract_participants_proposed":sorted(contract_participants),
                "declared_downstream":downstream,"impacted_modules":impacted,
                "path_matches":path_matches,"unmapped_paths":sorted(unmapped),"reasons":reasons,
                "validation":[{"module":m,"plan":self.owners[m]["validation"],"status":"NOT_RUN"} for m in impacted],
                "execution_authorized":False,"fingerprint":self.fingerprint}

    def gate(self,manifest):
        report=self.impact(manifest)
        return {"status":report["status"],"reasons":report["reasons"],
                "impact":report,"execution_authorized":False,
                "note":"No PASS from metadata alone; actual owner review and exact-SHA tests required"}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command",required=True)
    for name in ("validate","stats","graph","contract-diff"):
        sub.add_parser(name)
    sub.add_parser("show").add_argument("module")
    for name in ("impact","gate"):
        sub.add_parser(name).add_argument("manifest",type=Path)
    a=p.parse_args(argv)
    try:
        arch=load()
        if a.command in ("validate","stats"):
            result=arch.stats()
        elif a.command=="graph":
            result=arch.graph()
        elif a.command=="show":
            result=arch.show(a.module)
        elif a.command=="contract-diff":
            result=arch.contract_diff()
        else:
            result=getattr(arch,a.command)(r.read(a.manifest))
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if a.command in ("gate","contract-diff") and result["status"]=="BLOCKED" else 0
    except (ValueError,TypeError,KeyError,OSError,AttributeError,RecursionError) as exc:
        print(json.dumps({"status":"FAIL","error":str(exc)[:500]}),file=sys.stderr)
        return 2

if __name__=="__main__":
    sys.exit(main())
