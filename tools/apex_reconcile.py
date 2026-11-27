#!/usr/bin/env python3
"""Validate recorded tree comparisons and scoped CI observations, never query/repin."""
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
import re

import apex_foundation_registry as r
import apex_knowledge as k
import apex_architecture as a

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/"docs"/"integration"
VERSION="0.5.1"
SCOPE="Git tree identity comparison only; not functional source audit or authorization"
SCOPES={"CORE2_FAST_PUSH":"core2","HYPER_ISOLATED_LAB":"hyper",
        "HYPER_GAME_FAST":"hyper","LAB_PYTHON_310":"lab","LAB_PYTHON_313":"lab"}
MARKERS={
    "CORE2_FAST_PUSH":("APEX_CI_IMPORT_PASS","APEX_LAB_TRACK_PASS","APEX_LAB_PERF_PASS"),
    "HYPER_ISOLATED_LAB":("HYPER22_LONGITUDINAL_PASS",),
    "HYPER_GAME_FAST":("HYPER_FIXTURE",),
    "LAB_PYTHON_310":("Create Python 3.10.22 folder","Ran 34 tests"," OK"),
    "LAB_PYTHON_313":("Ran 34 tests"," OK"),
}

def valid_date(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",value):
        raise ValueError("invalid observation date")
    date.fromisoformat(value)

def classification(row):
    if any(c["blob"]!=row["baseline_blob"] for c in row["claims"]):
        return "BASELINE_MISMATCH"
    if row["candidate_blob"] is None:
        return "MISSING"
    return "UNCHANGED" if row["baseline_blob"]==row["candidate_blob"] else "CHANGED"

def collect_inventory():
    groups=defaultdict(lambda:defaultdict(set))
    inv=k.document(ROOT/"docs/architecture/source-inventory.json",{"repositories"})
    for row in inv["repositories"]:
        for path in row["paths"]:
            groups[row["id"]][path["path"]].add(("architecture",path["blob_sha"]))
    for source,path in (("knowledge","docs/knowledge/consumer-inventory.json"),
                        ("content","docs/content/source-inventory.json"),
                        ("persistence","docs/persistence/saveguard-inventory.json")):
        doc=r.read(ROOT/path)
        rows=[x for entries in doc["departments"].values() for x in entries] if source=="knowledge" else doc["paths"]
        for row in rows:
            groups["core2"][row["path"]].add((source,row["blob_sha"]))
    upstream=r.read(ROOT/"docs/foundation/upstream-entrypoints.json")
    prefix=f"https://github.com/{upstream['repository']}/blob/{upstream['revision']}/"
    for url,blob in upstream["entries"].items():
        if not url.startswith(prefix):
            raise ValueError("invalid upstream inventory URL")
        groups["core2-upstream"][url[len(prefix):]].add(("upstream",blob))
    return dict(groups),upstream

class Reconciliation:
    def __init__(self,schemas,snapshots,architecture,comparison,corrections,native,candidates,expected,upstream):
        self.schemas=schemas
        self.snapshots=snapshots
        self.comparison=r.unique(comparison["entries"])
        self.corrections=r.unique(corrections["entries"])
        self.native=r.unique(native["entries"])
        self.candidates=candidates["entries"]
        self.counts=Counter()
        if comparison["scope"]!=SCOPE:
            raise ValueError("comparison scope mismatch")
        valid_date(comparison["observed_on"])
        if set(self.comparison)!={"core2","hyper","lab","core2-upstream"} or set(expected)!=set(self.comparison):
            raise ValueError("incomplete comparison group coverage")
        corrected={}
        for row in self.corrections.values():
            k.strict_fields(row,{"id","group","source","path","before","after","reason","source_url"})
            group=row["group"]
            if group not in self.comparison or not a.valid_path(row["path"]) or not a.sha(row["before"]) or not a.sha(row["after"]) or row["before"]==row["after"] or not k.nonempty(row["reason"]):
                raise ValueError("invalid correction")
            g=self.comparison[group]
            if row["source_url"]!=f"https://github.com/{g['repository']}/blob/{g['baseline']}/{row['path']}":
                raise ValueError("correction URL mismatch")
            key=(group,row["path"],row["source"],row["before"])
            if key in corrected:
                raise ValueError("duplicate correction")
            corrected[key]=row["after"]
        used=set()
        unresolved=[]
        for ident,g in self.comparison.items():
            r.check(g,schemas["source-comparison.v1"])
            scope="core2" if ident=="core2-upstream" else ident
            s=snapshots[scope]
            baseline=upstream["revision"] if ident=="core2-upstream" else architecture.repos[scope]["revision"]
            if (g["repository"]!=s["repository"] or g["baseline"]!=baseline or g["candidate"]!=s["observed_revision"] or
                not g["paths"] or len(g["paths"])>10000):
                raise ValueError("comparison revision or repository mismatch")
            if g["baseline"]==g["candidate"] and g["baseline_tree"]!=g["candidate_tree"]:
                raise ValueError("identical revision cannot have different tree")
            seen=set()
            for row in g["paths"]:
                path=row["path"]
                if not a.valid_path(path) or path in seen or not row["claims"]:
                    raise ValueError("invalid or repeated comparison path")
                seen.add(path)
                if row["state"]!=classification(row):
                    raise ValueError("incorrect comparison state")
                if g["baseline"]==g["candidate"] and row["baseline_blob"]!=row["candidate_blob"]:
                    raise ValueError("identical revision cannot have different blob")
                sources=set()
                current=set()
                for claim in row["claims"]:
                    source,blob=claim["source"],claim["blob"]
                    if source in sources:
                        raise ValueError("duplicate inventory source claim")
                    sources.add(source)
                    ck=(ident,path,source,blob)
                    if ck in corrected:
                        if corrected[ck]!=row["baseline_blob"] or blob==row["baseline_blob"]:
                            raise ValueError("correction not supported by observed baseline blob")
                        used.add(ck)
                        current.add((source,corrected[ck]))
                    else:
                        current.add((source,blob))
                        if blob!=row["baseline_blob"]:
                            unresolved.append({"group":ident,"path":path,"source":source})
                if current!=expected[ident].get(path,set()):
                    raise ValueError("comparison/current inventory claim mismatch")
                self.counts[row["state"]]+=1
            if seen!=set(expected[ident]):
                raise ValueError("comparison path coverage mismatch")
        if used!=set(corrected):
            raise ValueError("unused correction")
        self.unresolved=unresolved
        run_keys=set()
        scopes=set()
        for row in self.native.values():
            r.check(row,schemas["native-ci-observation.v1"])
            repo=snapshots[row["repository"]]
            if row["scope"] in scopes or SCOPES[row["scope"]]!=row["repository"] or row["revision"]!=repo["observed_revision"]:
                raise ValueError("native evidence scope or revision mismatch")
            scopes.add(row["scope"])
            valid_date(row["observed_on"])
            run,job=row["run_id"],row["job_id"]
            if not (0<run<10**16 and 0<job<10**16) or (repo["repository"],run,job) in run_keys:
                raise ValueError("invalid native job identity")
            run_keys.add((repo["repository"],run,job))
            if row["run_url"]!=f"https://github.com/{repo['repository']}/actions/runs/{run}" or row["job_url"]!=row["run_url"]+f"/job/{job}":
                raise ValueError("native evidence URL mismatch")
            if len(row["markers"])>30 or any(len(x)>500 for x in row["markers"]):
                raise ValueError("native excerpt size")
            if row["status"]=="PASS" and not all(any(marker in line for line in row["markers"]) for marker in MARKERS[row["scope"]]):
                raise ValueError("missing observed native marker")
            # In-progress game observation cannot be promoted by an edited label.
            if row["scope"]=="HYPER_GAME_FAST" and row["status"]=="PASS":
                raise ValueError("game FAST was not completed at this observation; record a new reviewed observation")
        if scopes!=set(SCOPES):
            raise ValueError("missing native evidence scope")
        seen=set()
        for row in self.candidates:
            r.check(row,schemas["source-candidate.v1"])
            key=(row["repository"],row["path"])
            if key in seen or not a.valid_path(row["path"]) or row["revision"]!=snapshots[row["repository"]]["observed_revision"]:
                raise ValueError("invalid source candidate")
            seen.add(key)
        if not {("hyper","game/project.godot"),("hyper",".github/workflows/hyper-game-fast.yml"),
                ("hyper","game/scripts/race_engine.gd")}<=seen:
            raise ValueError("missing playable Hyper candidates")
        self.fingerprint=k.digest({"comparison":comparison,"corrections":corrections,"native":native,"candidates":candidates})

    def stats(self):
        return {"status":"FAIL" if self.unresolved else "PASS","scope":"recorded comparison structure only",
                "version":VERSION,"pairs":sum(self.counts.values()),"counts":dict(sorted(self.counts.items())),
                "groups":[{"id":i,"baseline":g["baseline"],"candidate":g["candidate"],"paths":len(g["paths"]),
                           "counts":dict(sorted(Counter(x["state"] for x in g["paths"]).items())),
                           "review_paths":[x["path"] for x in g["paths"] if x["state"]!="UNCHANGED"]}
                          for i,g in sorted(self.comparison.items())],
                "corrections":list(self.corrections.values()),"unresolved":self.unresolved,
                "fingerprint":self.fingerprint,"pins_changed":False,"native_readiness":"BLOCKED",
                "live_verified":False,"execution_authorized":False}

    def native_report(self):
        return {"status":"NOT_RUN","scope":"historical native CI observations only",
                "entries":[self.native[i] for i in sorted(self.native)],
                "counts":dict(sorted(Counter(x["status"] for x in self.native.values()).items())),
                "native_adapter_verified":False,"live_verified":False,"execution_authorized":False}

    def candidate_report(self):
        return {"status":"NOT_RUN","scope":"observed candidate tree presence only",
                "entries":sorted(self.candidates,key=lambda x:(x["repository"],x["path"])),
                "implementation_audited":False,"execution_authorized":False}

def load(schemas,snapshots,architecture):
    expected,upstream=collect_inventory()
    return Reconciliation(schemas,snapshots,architecture,
        k.document(DOCS/"reconciliation.json",{"observed_on","scope","entries"}),
        k.document(DOCS/"corrections.json",{"entries"}),
        k.document(DOCS/"native-ci.json",{"entries"}),
        k.document(DOCS/"candidates.json",{"entries"}),expected,upstream)
