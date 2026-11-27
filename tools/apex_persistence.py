#!/usr/bin/env python3
"""Offline synthetic persistence checks. Never reads or writes player saves."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

import apex_foundation_registry as r
import apex_knowledge as k
import apex_architecture as a

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/"docs"/"persistence"
VERSION="0.3.0"
VERSIONS=("1.0.0","2.0.0","3.0.0")
ROUTES={"1.0.0":("2.0.0","rename-budget"),"2.0.0":("3.0.0","expand-progress")}
FIXTURE_IDS={"career-baseline","career-backup","career-primary","career-corrupt"}
LIMIT=65536

def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8")

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def exact_int(value,low,high):
    return type(value) is int and low<=value<=high

def payload(version,round_index,points,budget):
    if version=="1.0.0":
        return {"round_index":round_index,"points":points,"budget":budget}
    if version=="2.0.0":
        return {"round_index":round_index,"points":points,"budget_units":budget}
    if version=="3.0.0":
        return {"progress":{"round_index":round_index,"points":points},"budget_units":budget}
    raise ValueError("unsupported fixture format")

def semantic(version,value):
    if version=="1.0.0":
        k.strict_fields(value,{"round_index","points","budget"})
        round_index,points,budget=value["round_index"],value["points"],value["budget"]
    elif version=="2.0.0":
        k.strict_fields(value,{"round_index","points","budget_units"})
        round_index,points,budget=value["round_index"],value["points"],value["budget_units"]
    elif version=="3.0.0":
        k.strict_fields(value,{"progress","budget_units"})
        k.strict_fields(value["progress"],{"round_index","points"})
        round_index,points,budget=value["progress"]["round_index"],value["progress"]["points"],value["budget_units"]
    else:
        raise ValueError("unsupported version")
    if not (exact_int(round_index,0,20) and exact_int(points,0,100000) and exact_int(budget,0,10**12)):
        raise ValueError("invalid fixture progression or budget")
    return (round_index,points,budget)

class Persistence:
    def __init__(self,routes,fixtures,inventory,schemas,consumers):
        self.schemas=schemas
        self.consumers=consumers
        self.routes={}
        for row in routes["entries"]:
            r.check(row,schemas["persistence-route.v1"])
            if row["from"] in self.routes or ROUTES.get(row["from"])!=(row["to"],row["operation"]) or row["id"]!=row["operation"]:
                raise ValueError("unknown, duplicate or altered route")
            self.routes[row["from"]]=row
        if set(self.routes)!=set(ROUTES):
            raise ValueError("migration route coverage")
        if inventory["repository"]!="Jugadru/APEX-Simulation" or inventory["revision"]!=consumers["core2"] or not k.nonempty(inventory["scope"]):
            raise ValueError("invalid SaveGuard inventory")
        seen=set()
        for row in inventory["paths"]:
            k.strict_fields(row,{"path","blob_sha","url"})
            path=row["path"]
            if not a.valid_path(path) or path in seen or not a.sha(row["blob_sha"]) or row["url"]!=f"https://github.com/{inventory['repository']}/blob/{inventory['revision']}/{path}":
                raise ValueError("invalid SaveGuard pointer")
            seen.add(path)
        if not {"tools/apex_saveguard_ci.py",".github/workflows/apex-saveguard-ci.yml","docs/APEX_SAVEGUARD_CROSS_VERSION.md"}<=seen:
            raise ValueError("missing SaveGuard pointer")
        self.inventory=inventory
        self.fixtures={}
        self.expected={}
        for row in fixtures["entries"]:
            k.strict_fields(row,{"id","version","generation","round","points","budget","corrupt"})
            ident=row["id"]
            if ident not in FIXTURE_IDS or ident in self.fixtures or type(row["corrupt"]) is not bool:
                raise ValueError("unknown or duplicate fixture")
            value=payload(row["version"],row["round"],row["points"],row["budget"])
            manifest={"id":ident,"kind":"career-fixture","format":"foundation-fixture","version":row["version"],
                      "consumer":"core2","revision":consumers["core2"],"season":2012,
                      "generation":row["generation"],"payload_sha256":digest(value),"usage":"TEST_ONLY"}
            envelope={"manifest":manifest,"payload":value}
            self.verify(envelope)
            self.expected[ident]=digest(envelope)
            if row["corrupt"]:
                envelope["payload"]["budget_units"]+=1
            self.fixtures[ident]=envelope
        if set(self.fixtures)!=FIXTURE_IDS:
            raise ValueError("fixture coverage")
        self.fingerprint=k.digest({"routes":routes,"fixtures":fixtures,"inventory":inventory})
        # Registered fixture scenario must remain meaningful.
        if self.inspect("career-corrupt")["status"]!="FAIL" or any(self.inspect(i)["status"]!="PASS" for i in FIXTURE_IDS-{"career-corrupt"}):
            raise ValueError("invalid fixture scenario")

    def verify(self,envelope,expected=None):
        k.strict_fields(envelope,{"manifest","payload"})
        if len(canonical(envelope))>LIMIT:
            raise ValueError("fixture size limit")
        m=envelope["manifest"]
        r.check(m,self.schemas["persistence-manifest.v1"])
        if m["id"] not in FIXTURE_IDS or m["revision"]!=self.consumers[m["consumer"]] or m["season"]!=2012 or not exact_int(m["generation"],1,10**9):
            raise ValueError("invalid fixture identity, era or revision")
        values=semantic(m["version"],envelope["payload"])
        if digest(envelope["payload"])!=m["payload_sha256"]:
            raise ValueError("payload checksum mismatch")
        if expected is not None and digest(envelope)!=expected:
            raise ValueError("envelope checksum mismatch")
        return values

    def inspect(self,ident):
        envelope=self.fixtures[ident]
        try:
            self.verify(envelope,self.expected[ident])
            status,reason="PASS","Synthetic envelope and semantic checks passed"
        except (ValueError,TypeError,KeyError) as exc:
            status,reason="FAIL",str(exc)
        return {"id":ident,"status":status,"reason":reason,"version":envelope["manifest"]["version"],
                "sha256":digest(envelope),"expected_sha256":self.expected[ident],
                "native_save_verified":False,"execution_authorized":False}

    def plan(self,ident,target):
        if target not in VERSIONS:
            raise ValueError("unknown target format")
        info=self.inspect(ident)
        start=info["version"]
        if info["status"]!="PASS":
            return {"status":"BLOCKED","reason":"CORRUPT_SOURCE","steps":[],"execution_authorized":False}
        if VERSIONS.index(target)<VERSIONS.index(start):
            return {"status":"BLOCKED","reason":"DOWNGRADE_UNSUPPORTED","steps":[],"execution_authorized":False}
        steps=[]
        current=start
        while current!=target:
            row=self.routes[current]
            steps.append(row)
            current=row["to"]
        return {"status":"NOT_RUN","id":ident,"source":start,"target":target,"steps":steps,
                "source_sha256":info["sha256"],"native_save_verified":False,"execution_authorized":False}

    def simulate(self,ident,target):
        plan=self.plan(ident,target)
        if plan["status"]=="BLOCKED":
            return plan
        original=self.fixtures[ident]
        before=digest(original)
        value=copy.deepcopy(original)
        expected=self.verify(value,before)
        for row in plan["steps"]:
            m=value["manifest"]
            if m["version"]!=row["from"]:
                raise ValueError("unexpected migration source")
            value["payload"]=payload(row["to"],*semantic(m["version"],value["payload"]))
            m["version"]=row["to"]
            m["payload_sha256"]=digest(value["payload"])
            if self.verify(value)!=expected:
                raise ValueError("migration changed protected progression")
        if self.verify(value)!=expected or digest(original)!=before:
            raise ValueError("source changed or semantic mismatch")
        return {"status":"PASS","scope":"in-memory synthetic migration only","id":ident,"source":plan["source"],"target":target,
                "steps":len(plan["steps"]),"source_sha256":before,"target_sha256":digest(value),
                "source_unchanged":True,"progress_preserved":True,"result":value,
                "native_save_verified":False,"execution_authorized":False}

    def recovery(self,scenario):
        r.check(scenario,self.schemas["persistence-recovery.v1"])
        primary=scenario["primary"]
        primary_id=primary["id"]
        if primary_id not in self.fixtures or scenario["revision"]!=self.consumers[scenario["consumer"]]:
            raise ValueError("unknown recovery fixture or revision")
        def candidate(row):
            ident=row["id"]
            envelope=self.fixtures[ident]
            m=envelope["manifest"]
            try:
                self.verify(envelope,row["expected_sha256"])
                if m["consumer"]!=scenario["consumer"] or m["revision"]!=scenario["revision"]:
                    raise ValueError("consumer scope mismatch")
                return True
            except (ValueError,TypeError,KeyError):
                return False
        ids=[x["id"] for x in scenario["backups"]]
        if primary_id in ids or len(ids)!=len(set(ids)) or not set(ids)<=self.fixtures.keys():
            raise ValueError("duplicate or unknown backup")
        if candidate(primary):
            return {"status":"NOT_RUN","decision":"KEEP_VALID_PRIMARY","candidates":[],"restored":False,"execution_authorized":False}
        generation=self.fixtures[primary_id]["manifest"]["generation"]
        valid=[x["id"] for x in scenario["backups"] if candidate(x) and self.fixtures[x["id"]]["manifest"]["generation"]<=generation]
        valid.sort(key=lambda ident:(-self.fixtures[ident]["manifest"]["generation"],ident))
        # Never select automatically, even when only one candidate remains.
        return {"status":"NOT_RUN" if valid else "BLOCKED","decision":"REVIEW_BACKUPS" if valid else "NO_VALID_BACKUP",
                "candidates":valid,"restored":False,"execution_authorized":False,"native_save_verified":False}

    def scenario(self,name):
        if name not in ("corrupt-primary","valid-primary","no-backup"):
            raise ValueError("unknown built-in scenario")
        primary="career-primary" if name=="valid-primary" else "career-corrupt"
        backups=[] if name=="no-backup" else ["career-baseline","career-backup"]
        ref=lambda i:{"id":i,"expected_sha256":self.expected[i]}
        return {"id":name,"primary":ref(primary),"backups":[ref(i) for i in backups],
                "consumer":"core2","revision":self.consumers["core2"],"policy":"EXPLICIT_BACKUP_REVIEW"}

    def gate(self,ident,consumer,revision):
        self.fixtures[ident]
        if consumer not in self.consumers or not a.sha(revision):
            raise ValueError("invalid consumer or revision")
        reasons=["SYNTHETIC_ONLY","NATIVE_SAVEGUARD_NOT_RUN","NO_RUNTIME_ADAPTER"]
        if self.consumers[consumer]!=revision:
            reasons.append("UNKNOWN_EXACT_CONSUMER_REVISION")
        if self.fixtures[ident]["manifest"]["consumer"]!=consumer:
            reasons.append("CONSUMER_MISMATCH")
        return {"status":"BLOCKED","reasons":reasons,"execution_authorized":False}

    def stats(self):
        return {"status":"PASS","scope":"synthetic persistence registry only","version":VERSION,"formats":len(VERSIONS),
                "routes":len(self.routes),"fixtures":len(self.fixtures),"saveguard_pointers":len(self.inventory["paths"]),
                "fingerprint":self.fingerprint,"native_save_verified":False,"execution_authorized":False}

def load():
    _,schemas=r.load_registry()
    architecture=a.load()
    return Persistence(k.document(DOCS/"routes.json",{"entries"}),
                       k.document(ROOT/"data/persistence/fixtures.json",{"entries"}),
                       k.document(DOCS/"saveguard-inventory.json",{"repository","revision","scope","paths"}),
                       schemas,{i:architecture.repos[i]["revision"] for i in ("core2","hyper")})

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("validate")
    sub.add_parser("stats")
    sub.add_parser("inspect").add_argument("id")
    for name in ("plan","simulate"):
        s=sub.add_parser(name);s.add_argument("id");s.add_argument("target")
    sub.add_parser("recover").add_argument("scenario")
    g=sub.add_parser("gate");g.add_argument("id");g.add_argument("consumer");g.add_argument("revision")
    arg=p.parse_args(argv)
    try:
        obj=load()
        if arg.command in ("validate","stats"):
            out=obj.stats()
        elif arg.command=="recover":
            out=obj.recovery(obj.scenario(arg.scenario))
        elif arg.command=="gate":
            out=obj.gate(arg.id,arg.consumer,arg.revision)
        elif arg.command=="inspect":
            out=obj.inspect(arg.id)
        else:
            out=getattr(obj,arg.command)(arg.id,arg.target)
        print(json.dumps(out,ensure_ascii=False,indent=2))
        return 1 if out["status"] in ("FAIL","BLOCKED") else 0
    except (ValueError,TypeError,KeyError,OSError,AttributeError,RecursionError) as exc:
        print(json.dumps({"status":"FAIL","error":str(exc)[:500]}),file=sys.stderr)
        return 2

if __name__=="__main__":
    sys.exit(main())
