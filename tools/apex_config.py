#!/usr/bin/env python3
"""Offline configuration resolution; never apply settings to a running engine."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import apex_foundation_registry as r
import apex_knowledge as k
import apex_architecture as arch
import apex_data_center as dc

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/"docs"/"config"
VERSION="0.2.2"
MAX_PROFILES=1000
MAX_SETTINGS=1000
# Safety requirements are code invariants, not overridable profile values.
EXPERIMENTAL={"feature.longitudinal","feature.advanced-racecraft",
              "feature.strategy-preview","feature.randomized-seed"}

def key(row):
    return row["id"],row["version"]

def unique_values(rows):
    values={row["id"]:row["value"] for row in rows}
    if len(values)!=len(rows):
        raise ValueError("duplicate setting override")
    return values

class Config:
    def __init__(self,settings,constraints,profiles,schemas,consumers,season):
        self.schemas=schemas
        self.consumers=consumers
        self.season=season
        if not 1<=len(settings["entries"])<=MAX_SETTINGS or not 1<=len(profiles["entries"])<=MAX_PROFILES:
            raise ValueError("configuration registry size limit")
        self.settings=r.unique(settings["entries"])
        for row in self.settings.values():
            r.check(row,schemas["config-setting.v1"])
            kind=row["kind"]
            if kind=="integer":
                if (type(row["minimum"]) is not int or type(row["maximum"]) is not int or
                    row["minimum"]>row["maximum"] or row["choices"]):
                    raise ValueError("invalid integer setting")
            elif row["minimum"] is not None or row["maximum"] is not None:
                raise ValueError("noninteger bounds")
            if kind=="enum" and not row["choices"] or kind!="enum" and row["choices"]:
                raise ValueError("invalid enum choices")
            if row["experimental"] and (kind!="boolean" or row["default"] is not False):
                raise ValueError("experimental flags must default disabled")
            self.validate_value(row["id"],row["default"])
        if not EXPERIMENTAL<=self.settings.keys() or any(not self.settings[x]["experimental"] for x in EXPERIMENTAL):
            raise ValueError("required experimental flags cannot be downgraded")
        if self.settings.get("safety.manual-priority",{}).get("default") is not True:
            raise ValueError("manual priority default invariant")
        self.defaults={i:s["default"] for i,s in self.settings.items()}
        self.constraints=r.unique(constraints["entries"])
        for rule in self.constraints.values():
            r.check(rule,schemas["config-constraint.v1"])
            if not (rule["requires"] or rule["forbids"]):
                raise ValueError("empty constraint")
            for term in [rule["when"],*rule["requires"],*rule["forbids"]]:
                self.validate_value(term["id"],term["value"])
            requires=unique_values(rule["requires"])
            forbids=unique_values(rule["forbids"])
            if any(i in forbids and forbids[i]==v for i,v in requires.items()):
                raise ValueError("contradictory constraint")
        self.profiles={}
        versions={}
        for row in profiles["entries"]:
            r.check(row,schemas["config-profile.v1"])
            ident=key(row)
            dc.version_tuple(row["version"])
            if ident in self.profiles or row["revision"]!=consumers[row["consumer"]] or row["season"]!=season:
                raise ValueError("duplicate profile, stale consumer or wrong era")
            if not row["id"].startswith(row["consumer"]+"-"):
                raise ValueError("profile consumer prefix mismatch")
            for i,v in unique_values(row["overrides"]).items():
                self.validate_value(i,v)
            self.profiles[ident]=row
            versions.setdefault(ident[0],[]).append(row)
        for rows in versions.values():
            rows.sort(key=lambda x:dc.version_tuple(x["version"]))
            for n,row in enumerate(rows):
                prev=rows[n-1] if n else None
                if row["previous"]!=(prev["version"] if prev else None):
                    raise ValueError("broken profile version chain")
                if prev and any(row[x]!=prev[x] for x in ("consumer","environment","season")):
                    raise ValueError("profile identity scope changed")
        self.resolved={}
        # Iterative dependency resolution. Parent must be exact and in the same scope.
        remaining=set(self.profiles)
        while remaining:
            progress=False
            for ident in sorted(remaining):
                row=self.profiles[ident]
                parent=key(row["parent"]) if row["parent"] else None
                if parent:
                    if parent not in self.profiles:
                        raise ValueError("unknown exact parent profile")
                    p=self.profiles[parent]
                    if any(p[x]!=row[x] for x in ("consumer","environment","season","revision")):
                        raise ValueError("cross-scope profile inheritance")
                    if parent not in self.resolved:
                        continue
                    values=dict(self.resolved[parent]["values"])
                    origins=dict(self.resolved[parent]["origins"])
                else:
                    values=dict(self.defaults)
                    origins={i:"default" for i in values}
                for i,v in unique_values(row["overrides"]).items():
                    values[i]=v
                    origins[i]=ident[0]+"@"+ident[1]
                self.validate_effective(row,values)
                self.resolved[ident]={"values":values,"origins":origins}
                remaining.remove(ident)
                progress=True
            if not progress:
                raise ValueError("profile inheritance cycle")
        self.fingerprint=k.digest({"settings":settings,"constraints":constraints,"profiles":profiles})

    def validate_value(self,ident,value):
        if ident not in self.settings:
            raise ValueError("unknown configuration setting: "+ident)
        s=self.settings[ident]
        if s["kind"]=="boolean":
            valid=type(value) is bool
        elif s["kind"]=="integer":
            valid=type(value) is int and s["minimum"]<=value<=s["maximum"]
        else:
            valid=type(value) is str and value in s["choices"]
        if not valid:
            raise ValueError("invalid setting type, range or choice: "+ident)

    def validate_effective(self,row,values):
        if values["safety.manual-priority"] is not True:
            raise ValueError("manual command priority cannot be disabled")
        if row["environment"]=="production" or row["consumer"]=="core2":
            if any(values[i] for i,s in self.settings.items() if s["experimental"]):
                raise ValueError("experimental flags restricted to Hyper development")
        # Critical experimental relationships remain mandatory even if catalog rules change.
        if values["feature.longitudinal"] and (not values["diagnostics.replay"] or values["simulation.mode"]!="deterministic"):
            raise ValueError("longitudinal replay invariant")
        if values["feature.advanced-racecraft"] and (not values["feature.longitudinal"] or not values["diagnostics.telemetry"]):
            raise ValueError("racecraft prerequisite invariant")
        if values["feature.randomized-seed"] and (values["simulation.mode"]!="exploratory" or values["feature.longitudinal"]):
            raise ValueError("randomized seed invariant")
        if (values["feature.strategy-preview"] or values["simulation.realism"]=="technical") and not values["diagnostics.telemetry"]:
            raise ValueError("telemetry prerequisite invariant")
        for rule in self.constraints.values():
            when=rule["when"]
            if values[when["id"]]==when["value"]:
                if (any(values[x["id"]]!=x["value"] for x in rule["requires"]) or
                    any(values[x["id"]]==x["value"] for x in rule["forbids"])):
                    raise ValueError("configuration constraint: "+rule["id"])

    def stats(self):
        return {"status":"PASS","scope":"offline configuration structure only","version":VERSION,
                "settings":len(self.settings),"experimental_flags":sum(s["experimental"] for s in self.settings.values()),
                "constraints":len(self.constraints),"profiles":len({i for i,v in self.profiles}),
                "profile_versions":len(self.profiles),"environments":dict(sorted(Counter(x["environment"] for x in self.profiles.values()).items())),
                "fingerprint":self.fingerprint,"runtime_applied":False,"execution_authorized":False}

    def show(self,ident,version):
        return {"profile":self.profiles[(ident,version)],"runtime_applied":False}

    def resolve(self,ident,version):
        row=self.profiles[(ident,version)]
        effective=self.resolved[(ident,version)]
        return {"profile":row,"values":effective["values"],"origins":effective["origins"],
                "effective_sha256":k.digest({"consumer":row["consumer"],"revision":row["revision"],"environment":row["environment"],"season":row["season"],"values":effective["values"]}),
                "runtime_applied":False,"execution_authorized":False}

    def diff(self,ident,old,new):
        if dc.version_tuple(old)>=dc.version_tuple(new):
            raise ValueError("expected increasing profile versions")
        a,b=self.resolve(ident,old),self.resolve(ident,new)
        changes=[{"id":i,"before":a["values"][i],"after":b["values"][i]} for i in sorted(self.settings) if a["values"][i]!=b["values"][i]]
        return {"id":ident,"old":old,"new":new,"changes":changes,
                "before_sha256":a["effective_sha256"],"after_sha256":b["effective_sha256"],
                "status":"NOT_RUN","runtime_applied":False}

    def rollback(self,ident,version):
        row=self.profiles[(ident,version)]
        prev=row["previous"]
        if prev is None:
            return {"status":"BLOCKED","reason":"NO_PREVIOUS_VERSION","runtime_applied":False,"execution_authorized":False}
        target=self.resolve(ident,prev)
        return {"status":"NOT_RUN","id":ident,"from":version,"target":prev,"target_sha256":target["effective_sha256"],
                "steps":["Review exact consumer revision","Validate previous effective profile","Run consumer-specific regression before any application"],
                "runtime_applied":False,"execution_authorized":False}

    def gate(self,ident,version,consumer,revision):
        if consumer not in self.consumers or not arch.sha(revision):
            raise ValueError("invalid consumer or revision")
        p=self.profiles[(ident,version)]
        reasons=["NO_RUNTIME_ADAPTER","CONSUMER_VALIDATION_NOT_RUN"]
        if p["consumer"]!=consumer:
            reasons.append("CONSUMER_MISMATCH")
        if p["revision"]!=revision or self.consumers[consumer]!=revision:
            reasons.append("UNKNOWN_EXACT_CONSUMER_REVISION")
        return {"status":"BLOCKED","id":ident,"version":version,"consumer":consumer,"revision":revision,
                "reasons":reasons,"runtime_applied":False,"execution_authorized":False}

def load():
    _,schemas=r.load_registry()
    architecture=arch.load()
    data=dc.load()
    return Config(k.document(DOCS/"settings.json",{"entries"}),
                  k.document(DOCS/"constraints.json",{"entries"}),
                  k.document(ROOT/"data/config/profiles.json",{"entries"}),
                  schemas,{i:architecture.repos[i]["revision"] for i in ("core2","hyper")},data.era["season"])

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command",required=True)
    for name in ("validate","stats","list"):
        sub.add_parser(name)
    for name in ("show","resolve","rollback","gate","diff"):
        s=sub.add_parser(name)
        s.add_argument("id")
        if name=="diff":
            s.add_argument("old")
            s.add_argument("new")
        else:
            s.add_argument("version")
        if name=="gate":
            s.add_argument("consumer")
            s.add_argument("revision")
    a=p.parse_args(argv)
    try:
        c=load()
        if a.command in ("validate","stats"):
            out=c.stats()
        elif a.command=="list":
            out={"profiles":[c.profiles[i] for i in sorted(c.profiles)]}
        elif a.command=="diff":
            out=c.diff(a.id,a.old,a.new)
        elif a.command=="gate":
            out=c.gate(a.id,a.version,a.consumer,a.revision)
        else:
            out=getattr(c,a.command)(a.id,a.version)
        print(json.dumps(out,ensure_ascii=False,indent=2))
        return 1 if a.command in ("gate","rollback") and out.get("status")=="BLOCKED" else 0
    except (ValueError,TypeError,KeyError,OSError,AttributeError,RecursionError) as exc:
        print(json.dumps({"status":"FAIL","error":str(exc)[:500]}),file=sys.stderr)
        return 2

if __name__=="__main__":
    sys.exit(main())
