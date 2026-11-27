#!/usr/bin/env python3
"""Offline versioned dataset catalog; no runtime adoption or external ingestion."""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import sys

import apex_foundation_registry as r
import apex_knowledge as k
import apex_architecture as arch

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "data"
VERSION = "0.2.0"
SCOPE = "Offline dataset integrity and project-era policy; not sporting validity"
MAX_RECORDS = 10000

def version_tuple(value):
    if not isinstance(value,str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)",value) or len(value)>40:
        raise ValueError("invalid exact dataset version")
    return tuple(map(int,value.split(".")))

def blob_id(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def payload_read(root, manifest):
    expected=f"data/datasets/{manifest['id']}/{manifest['version']}.json"
    if manifest["payload"]!=expected:
        raise ValueError("unexpected dataset payload path")
    p=root/expected
    if any(x.is_symlink() for x in (p,*p.parents) if x!=root and root in x.parents):
        raise ValueError("symlink payload forbidden")
    resolved=p.resolve(strict=True)
    if root.resolve() not in resolved.parents or not resolved.is_file():
        raise ValueError("payload outside root")
    with resolved.open("rb") as f:
        raw=f.read(r.LIMIT+1)
    if len(raw)>r.LIMIT or blob_id(raw)!=manifest["blob_sha"]:
        raise ValueError("payload size or Git blob integrity mismatch")
    payload=json.loads(raw.decode("utf-8"),object_pairs_hook=r.pairs,
                       parse_constant=r.bad_constant,parse_float=r.finite_float)
    k.strict_fields(payload,{"schema","records"})
    if type(payload["schema"]) is not int or payload["schema"]!=1:
        raise ValueError("unsupported payload schema")
    return payload,hashlib.sha256(raw).hexdigest()

class Units:
    def __init__(self,doc):
        self.units={}
        canonical={}
        for row in doc["units"]:
            k.strict_fields(row,{"id","dimension","si","numerator","denominator"})
            ident=row["id"]
            if (not k.nonempty(ident) or ident in self.units or
                not k.nonempty(row["dimension"]) or not k.nonempty(row["si"]) or
                any(type(row[x]) is not int or not 0<row[x]<=10**9 for x in ("numerator","denominator"))):
                raise ValueError("invalid unit")
            dim=row["dimension"]
            if dim in canonical and canonical[dim]!=row["si"]:
                raise ValueError("inconsistent SI dimension")
            canonical[dim]=row["si"]
            self.units[ident]=row
        if not self.units:
            raise ValueError("empty unit registry")

    def convert(self,value,source,target):
        if not isinstance(value,str) or len(value)>60 or not re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?",value):
            raise ValueError("expected finite decimal string")
        a,b=self.units[source],self.units[target]
        if a["dimension"]!=b["dimension"]:
            raise ValueError("incompatible dimensions")
        result=Fraction(value)*Fraction(a["numerator"],a["denominator"])/Fraction(b["numerator"],b["denominator"])
        return {"input":value,"from":source,"to":target,"dimension":a["dimension"],
                "exact":{"numerator":result.numerator,"denominator":result.denominator},
                "unit":target,"rounding":"none"}

class DataCenter:
    def __init__(self,catalog,units,era,matrix,schemas,references,domains,consumers,root=ROOT):
        self.root=root
        self.units=Units(units)
        self.era=era
        self.schemas=schemas
        self.consumers=consumers
        self.entries={}
        self.payloads={}
        self.hashes={}
        self.matrix={}
        if (era["season"]!=2012 or era["unknown"]!="BLOCKED" or
            era["source"]!="docs/references/INFRAESTRUTURA.md" or not k.nonempty(era["scope"])):
            raise ValueError("invalid era policy")
        for name in ("allowed","blocked"):
            if type(era[name]) is not list or len(set(era[name]))!=len(era[name]) or not all(k.nonempty(x) for x in era[name]):
                raise ValueError("invalid era technology list")
        if (set(era["allowed"])!={"none","v8","kers","drs"} or
            not {"v6-hybrid","mgu-h","modern-cost-cap","active-aero-2026"}<=set(era["blocked"]) or
            set(era["allowed"])&set(era["blocked"])):
            raise ValueError("era policy conflict")
        if type(catalog["entries"]) is not list or not catalog["entries"]:
            raise ValueError("empty catalog")
        for m in catalog["entries"]:
            r.check(m,schemas["dataset-manifest.v1"])
            key=(m["id"],m["version"])
            version_tuple(m["version"])
            if key in self.entries or m["domain"] not in domains or m["season"]!=era["season"]:
                raise ValueError("duplicate dataset, unknown domain or wrong era")
            if not 1<=m["record_count"]<=MAX_RECORDS:
                raise ValueError("invalid record count")
            p=m["provenance"]
            r.check(p,schemas["dataset-provenance.v1"])
            if not set(p["reference_ids"])<=references:
                raise ValueError("unknown provenance reference")
            if p["source_url"] is not None:
                k.canonical_url(p["source_url"])
            if p["origin"]=="synthetic":
                if m["usage"]!="TEST_ONLY" or p["license_state"]!="ORIGINAL_FIXTURE" or p["source_url"] is not None or p["reference_ids"] or p["source_revision"] is not None:
                    raise ValueError("synthetic provenance must remain test-only original")
            else:
                if m["usage"]!="RESEARCH_ONLY" or p["license_state"]!="UNREVIEWED" or not p["source_url"] or not p["source_revision"] or not p["reference_ids"]:
                    raise ValueError("non-synthetic provenance requires source, revision, reference and research-only usage")
            fieldmap=r.unique(m["fields"])
            if not fieldmap or any(x["unit"] not in self.units.units or x["minimum"]>x["maximum"] for x in fieldmap.values()):
                raise ValueError("invalid dataset fields")
            payload,sha=payload_read(root,m)
            records=payload["records"]
            if type(records) is not list or len(records)!=m["record_count"]:
                raise ValueError("record count mismatch")
            seen=set()
            for row in records:
                k.strict_fields(row,{"id","year","technology","values"})
                ident=row["id"]
                if (not isinstance(ident,str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}",ident) or ident in seen
                    or type(row["year"]) is not int or row["year"]!=m["season"] or row["technology"] not in era["allowed"]):
                    raise ValueError("invalid record ID, era or technology")
                seen.add(ident)
                k.strict_fields(row["values"],set(fieldmap))
                for f,v in row["values"].items():
                    spec=fieldmap[f]
                    if type(v) is not int or not spec["minimum"]<=v<=spec["maximum"]:
                        raise ValueError("invalid integer value/range: "+f)
            self.entries[key]=m
            self.payloads[key]={x["id"]:x for x in records}
            self.hashes[key]=sha
        by_id={}
        for key,m in self.entries.items():
            by_id.setdefault(key[0],[]).append(m)
        for ident,versions in by_id.items():
            versions.sort(key=lambda x:version_tuple(x["version"]))
            for i,m in enumerate(versions):
                prev=versions[i-1] if i else None
                if m["previous"]!=(prev["version"] if prev else None):
                    raise ValueError("broken version chain")
                if prev and (m["domain"]!=prev["domain"] or m["season"]!=prev["season"] or
                             m["provenance"]["origin"]!=prev["provenance"]["origin"]):
                    raise ValueError("dataset identity/provenance changed across versions")
                if prev and m["fields"]!=prev["fields"] and version_tuple(m["version"])[0]==version_tuple(prev["version"])[0]:
                    raise ValueError("field change requires new major version")
        for row in matrix["entries"]:
            r.check(row,schemas["dataset-consumer.v1"])
            key=(row["dataset"],row["version"],row["consumer"],row["revision"])
            if key in self.matrix or key[:2] not in self.entries or self.consumers[row["consumer"]]!=row["revision"]:
                raise ValueError("duplicate, orphan or stale consumer matrix")
            self.matrix[key]=row
        expected={(i,v,c,s) for i,v in self.entries for c,s in consumers.items()}
        if set(self.matrix)!=expected:
            raise ValueError("consumer matrix coverage mismatch")
        self.fingerprint=k.digest({"catalog":catalog,"units":units,"era":era,"matrix":matrix,"payload_sha256":sorted((i,v,h) for (i,v),h in self.hashes.items())})

    def stats(self):
        return {"status":"PASS","scope":SCOPE,"version":VERSION,"fingerprint":self.fingerprint,
                "datasets":len({i for i,_ in self.entries}),"versions":len(self.entries),
                "records_across_versions":sum(len(x) for x in self.payloads.values()),
                "origins":dict(sorted(Counter(x["provenance"]["origin"] for x in self.entries.values()).items())),
                "units":len(self.units.units),"consumer_pairs":len(self.matrix),
                "production_approved":0,"execution_authorized":False}

    def show(self,ident,version):
        key=(ident,version)
        return {"manifest":self.entries[key],"payload_sha256":self.hashes[key],
                "consumer_matrix":[x for key2,x in sorted(self.matrix.items()) if key2[:2]==key],
                "production_approved":False}

    def query(self,ident,version,record=None,limit=100):
        if type(limit) is not int or not 1<=limit<=MAX_RECORDS:
            raise ValueError("invalid query limit")
        rows=self.payloads[(ident,version)]
        selected=[rows[record]] if record is not None else [rows[x] for x in sorted(rows)]
        return {"dataset":ident,"version":version,"origin":self.entries[(ident,version)]["provenance"]["origin"],
                "total":len(selected),"records":selected[:limit],"truncated":len(selected)>limit,
                "production_approved":False}

    def diff(self,ident,old,new):
        a,b=self.entries[(ident,old)],self.entries[(ident,new)]
        if version_tuple(old)>=version_tuple(new):
            raise ValueError("diff requires increasing versions")
        left,right=self.payloads[(ident,old)],self.payloads[(ident,new)]
        added=sorted(right.keys()-left.keys())
        removed=sorted(left.keys()-right.keys())
        changed=sorted(i for i in left.keys()&right.keys() if left[i]!=right[i])
        return {"dataset":ident,"old":old,"new":new,"added":added,"removed":removed,"changed":changed,
                "field_schema_changed":a["fields"]!=b["fields"],
                "status":"BLOCKED" if removed or a["fields"]!=b["fields"] else "NOT_RUN",
                "scope":"record comparison; no semantic or consumer compatibility assertion",
                "production_approved":False}

    def gate(self,ident,version,consumer,revision):
        m=self.entries[(ident,version)]
        if consumer not in self.consumers or not arch.sha(revision):
            raise ValueError("invalid consumer or SHA")
        entry=self.matrix.get((ident,version,consumer,revision))
        reasons=["NO_RUNTIME_ADOPTION","TEST_FIXTURE_ONLY" if m["usage"]=="TEST_ONLY" else "RESEARCH_ONLY"]
        if entry is None:
            reasons.append("UNKNOWN_EXACT_CONSUMER_REVISION")
        else:
            reasons.append("CONSUMER_VALIDATION_"+entry["status"])
        return {"status":"BLOCKED","dataset":ident,"version":version,"consumer":consumer,"revision":revision,
                "reasons":reasons,"matrix":entry,"execution_authorized":False,"production_approved":False}

def load():
    reg,schemas=r.load_registry()
    r.validate_registry(reg,schemas)
    catalog=k.document(DOCS/"catalog.json",{"entries"})
    units=k.document(DOCS/"units.json",{"units"})
    era=k.document(DOCS/"era-policy.json",{"season","source","scope","allowed","blocked","unknown"})
    matrix=k.document(DOCS/"consumer-matrix.json",{"entries"})
    knowledge=k.load()
    architecture=arch.load()
    consumers={c:architecture.repos[c]["revision"] for c in ("core2","hyper")}
    return DataCenter(catalog,units,era,matrix,schemas,set(knowledge.refs),knowledge.domains,consumers)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    s=p.add_subparsers(dest="command",required=True)
    for name in ("validate","stats","list"):
        s.add_parser(name)
    for name in ("show","query","gate","diff"):
        cmd=s.add_parser(name)
        cmd.add_argument("id")
        if name=="diff":
            cmd.add_argument("old")
            cmd.add_argument("new")
        else:
            cmd.add_argument("version")
        if name=="query":
            cmd.add_argument("--record")
            cmd.add_argument("--limit",type=int,default=100)
        if name=="gate":
            cmd.add_argument("consumer")
            cmd.add_argument("revision")
    c=s.add_parser("convert")
    c.add_argument("value")
    c.add_argument("source")
    c.add_argument("target")
    a=p.parse_args(argv)
    try:
        dc=load()
        if a.command in ("validate","stats"):
            out=dc.stats()
        elif a.command=="list":
            out={"datasets":[dc.entries[key] for key in sorted(dc.entries)]}
        elif a.command=="convert":
            out=dc.units.convert(a.value,a.source,a.target)
        elif a.command=="diff":
            out=dc.diff(a.id,a.old,a.new)
        elif a.command=="query":
            out=dc.query(a.id,a.version,a.record,a.limit)
        elif a.command=="gate":
            out=dc.gate(a.id,a.version,a.consumer,a.revision)
        else:
            out=dc.show(a.id,a.version)
        print(json.dumps(out,ensure_ascii=False,indent=2))
        return 1 if a.command=="gate" else 0
    except (ValueError,TypeError,KeyError,OSError,AttributeError,RecursionError) as exc:
        print(json.dumps({"status":"FAIL","error":str(exc)[:500]}),file=sys.stderr)
        return 2

if __name__=="__main__":
    sys.exit(main())
