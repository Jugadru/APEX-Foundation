#!/usr/bin/env python3
"""Offline evidence catalog. Recorded observations are not live attestations."""
import argparse
from datetime import datetime
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

import apex_foundation_registry as r
import apex_knowledge as k
import apex_architecture as a

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/"docs"/"evidence"
REPO="Jugadru/APEX-Foundation"
VERSION="0.3.1"
MAX_ROWS=1000
MAX_BYTES=2*1024*1024
TIME_RE=r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z"

def timestamp(value):
    if not re.fullmatch(TIME_RE,value):
        raise ValueError("expected UTC timestamp")
    return datetime.fromisoformat(value.replace("Z","+00:00"))

def index(doc):
    rows=doc["entries"]
    if type(rows) is not list or not 1<=len(rows)<=MAX_ROWS:
        raise ValueError("evidence collection size")
    return r.unique(rows)

def exact_int(v,lo,hi):
    return type(v) is int and lo<=v<=hi

def fraction(value):
    return {"numerator":value.numerator,"denominator":value.denominator}

class Evidence:
    def __init__(self,receipts,artifacts,benchmarks,notes,schemas,root=ROOT):
        self.root=Path(root).resolve()
        self.receipts=index(receipts)
        self.artifacts=index(artifacts)
        self.benchmarks=index(benchmarks)
        self.notes=index(notes)
        self.schemas=schemas
        all_ids=[i for group in (self.receipts,self.artifacts,self.benchmarks,self.notes) for i in group]
        if len(all_ids)!=len(set(all_ids)):
            raise ValueError("evidence ID collision")
        seen=set()
        for row in self.receipts.values():
            r.check(row,schemas["evidence-ci-receipt.v1"])
            run,job,attempt=row["run_id"],row["job_id"],row["attempt"]
            key=(run,job,attempt)
            if key in seen or not all(exact_int(x,1,10**16) for x in key):
                raise ValueError("duplicate or invalid receipt identity")
            seen.add(key)
            if row["run_url"]!=f"https://github.com/{REPO}/actions/runs/{run}" or row["job_url"]!=f"https://github.com/{REPO}/actions/runs/{run}/job/{job}":
                raise ValueError("receipt URL mismatch")
            if not exact_int(row["test_count"],1,100000) or not re.fullmatch(r"3\.\d+\.\d+",row["python"]):
                raise ValueError("invalid test count or Python")
            patterns=[r"Python "+re.escape(row["python"]),r"Ran "+str(row["test_count"])+r" tests in \d+(?:\.\d+)?s",r"OK"]
            if len(row["markers"])!=3:
                raise ValueError("missing log excerpts")
            stamps=[]
            for marker,pattern in zip(row["markers"],patterns):
                match=re.fullmatch("("+TIME_RE+") "+pattern,marker)
                if not match:
                    raise ValueError("receipt marker mismatch")
                stamps.append(timestamp(match.group(1)))
            if stamps!=sorted(stamps) or stamps[-1]>timestamp(row["observed_at"]):
                raise ValueError("receipt time ordering")
        for row in self.artifacts.values():
            r.check(row,schemas["evidence-artifact-record.v1"])
            if row["id"]!=row["artifact"]["id"] or row["artifact"]["status"]!="NOT_RUN" or row["artifact"]["producer"]!="evidence-center":
                raise ValueError("fixture cannot claim execution evidence")
            if not exact_int(row["size_bytes"],1,MAX_BYTES) or row["path"]!="data/evidence/fixture.txt":
                raise ValueError("unregistered artifact fixture path or size")
        for row in self.benchmarks.values():
            r.check(row,schemas["evidence-benchmark.v1"])
            if not 3<=len(row["samples"])<=1001 or len(row["samples"])%2!=1 or not all(exact_int(x,1,10**12) for x in row["samples"]):
                raise ValueError("benchmark requires odd bounded positive samples")
        for row in self.notes.values():
            r.check(row,schemas["evidence-note.v1"])
            url=row["source_url"]
            if not (url==f"https://github.com/{REPO}/blob/{row['revision']}/docs/persistence/README.md" or
                    any(x["run_url"]==url and x["revision"]==row["revision"] for x in self.receipts.values())):
                raise ValueError("note source not pinned")
            if (row["kind"]=="decision")!=(row["scope"]=="DOCUMENTED_DECISION"):
                raise ValueError("note scope mismatch")
            if row["status"]=="PASS" and (row["kind"]!="regression" or not any(x["run_url"]==url and x["revision"]==row["revision"] for x in self.receipts.values())):
                raise ValueError("unsupported note PASS")
        self.fingerprint=k.digest({"receipts":receipts,"artifacts":artifacts,"benchmarks":benchmarks,"notes":notes})

    def verify(self,ident):
        row=self.artifacts[ident]
        path=self.root/row["path"]
        if any(x.is_symlink() for x in (path,*path.parents) if self.root in x.parents):
            raise ValueError("symlink artifact blocked")
        resolved=path.resolve(strict=True)
        if self.root not in resolved.parents or not resolved.is_file():
            raise ValueError("unsafe artifact")
        with resolved.open("rb") as handle:
            raw=handle.read(MAX_BYTES+1)
        actual=hashlib.sha256(raw).hexdigest()
        ok=len(raw)<=MAX_BYTES and len(raw)==row["size_bytes"] and actual==row["artifact"]["sha256"]
        return {"status":"PASS" if ok else "FAIL","scope":"local synthetic byte integrity only",
                "id":ident,"expected_sha256":row["artifact"]["sha256"],"actual_sha256":actual,
                "size_bytes":len(raw),"execution_verified":False,"release_authorized":False}

    def stats(self):
        verified=[self.verify(i) for i in sorted(self.artifacts)]
        return {"status":"PASS" if all(x["status"]=="PASS" for x in verified) else "FAIL",
                "scope":"offline catalog structure and synthetic byte integrity",
                "version":VERSION,"receipts":len(self.receipts),"artifacts":len(self.artifacts),
                "benchmarks":len(self.benchmarks),"notes":len(self.notes),
                "fingerprint":self.fingerprint,"live_attestation":False,"release_authorized":False}

    def history(self):
        return {"scope":"historical observed CI excerpts, not fresh validation",
                "entries":sorted(self.receipts.values(),key=lambda x:(x["observed_at"],x["id"])),
                "release_authorized":False}

    def show(self,ident):
        for group in (self.receipts,self.artifacts,self.benchmarks,self.notes):
            if ident in group:
                row=group[ident]
                return {"record":row,"record_sha256":k.digest(row),"release_authorized":False}
        raise KeyError(ident)

    def compare(self,baseline,candidate):
        if baseline==candidate:
            raise ValueError("comparison requires distinct observations")
        left,right=self.benchmarks[baseline],self.benchmarks[candidate]
        mismatch=[key for key in ("environment","harness","workload","metric","origin","scope") if left[key]!=right[key]]
        if mismatch:
            return {"status":"BLOCKED","mismatch":mismatch,"scope":"synthetic comparison only","release_authorized":False}
        l=statistics.median(left["samples"])
        c=statistics.median(right["samples"])
        delta=Fraction(c-l,l)*100
        return {"status":"NOT_RUN","scope":"synthetic comparison only",
                "baseline":baseline,"candidate":candidate,"baseline_median":l,"candidate_median":c,
                "unit":"us","delta_percent":fraction(delta),"direction":"SLOWER" if c>l else "FASTER" if c<l else "EQUAL",
                "real_regression_verified":False,"release_authorized":False}

    def gate(self,revision):
        if not a.sha(revision):
            raise ValueError("expected exact SHA")
        matches=sorted(i for i,x in self.receipts.items() if x["revision"]==revision)
        reasons=["NO_LIVE_ATTESTATION","NO_RELEASE_AUTHORIZATION"]
        if not matches:
            reasons.append("NO_EXACT_REVISION_RECEIPT")
        return {"status":"BLOCKED","revision":revision,"historical_receipts":matches,
                "reasons":reasons,"release_authorized":False}

def load(*,architecture=None):
    _,schemas=r.load_registry()
    if architecture is None:
        a.load()
    return Evidence(*(k.document(DOCS/name,{"entries"}) for name in
                      ("ci-receipts.json","artifacts.json","benchmarks.json","notes.json")),schemas)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    for name in ("validate","stats","history","notes"):
        sub.add_parser(name)
    for name in ("show","verify","gate"):
        sub.add_parser(name).add_argument("id")
    s=sub.add_parser("compare")
    s.add_argument("baseline");s.add_argument("candidate")
    args=parser.parse_args(argv)
    try:
        e=load()
        if args.command in ("validate","stats"):
            result=e.stats()
        elif args.command=="history":
            result=e.history()
        elif args.command=="notes":
            result={"entries":[e.notes[i] for i in sorted(e.notes)],"release_authorized":False}
        elif args.command=="compare":
            result=e.compare(args.baseline,args.candidate)
        else:
            result=getattr(e,args.command)(args.id)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if result.get("status") in ("FAIL","BLOCKED") else 0
    except (ValueError,TypeError,KeyError,OSError,AttributeError,RecursionError) as exc:
        print(json.dumps({"status":"FAIL","error":str(exc)[:500]}),file=sys.stderr)
        return 2

if __name__=="__main__":
    sys.exit(main())
