#!/usr/bin/env python3
"""Data-only mod fixture registry and bounded ZIP inspection; never install or extract."""
import argparse
from collections import defaultdict
import hashlib
import heapq
import io
import json
from pathlib import Path
import stat
import sys
import zipfile

import apex_foundation_registry as r
import apex_knowledge as k
import apex_content_registry as content
import apex_data_center as dc
import apex_architecture as arch

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/"docs"/"modding"
VERSION="0.4.0"
MAX_ZIP=256*1024
MAX_MANIFEST=64*1024
MAX_MODS=1000
PERMISSION="content.label.preview"

def key(row):
    return row["id"],row["version"]

def ref(key):
    return {"id":key[0],"version":key[1]}

def json_bytes(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8")

class Modding:
    def __init__(self,catalog,schemas,registry):
        self.schemas=schemas
        self.registry=registry
        self.consumers=registry.data.consumers
        self.entries={}
        self.edges={}
        self.reverse=defaultdict(set)
        self.versions=defaultdict(list)
        rows=catalog["entries"]
        if type(rows) is not list or not 1<=len(rows)<=MAX_MODS:
            raise ValueError("invalid mod catalog size")
        for row in rows:
            r.check(row,schemas["mod-manifest.v1"])
            ident=key(row)
            dc.version_tuple(row["version"])
            if (ident in self.entries or not row["id"].startswith("demo.") or
                row["revision"]!=self.consumers[row["consumer"]] or
                row["season"]!=registry.data.era["season"] or row["permissions"]!=[PERMISSION]):
                raise ValueError("invalid fixture identity, scope or permission")
            if not 1<=len(row["overlays"])<=32 or len(row["dependencies"])>32 or len(row["conflicts"])>32:
                raise ValueError("mod metadata size limit")
            if len(json_bytes(row))>MAX_MANIFEST:
                raise ValueError("manifest too large")
            targets=set()
            for overlay in row["overlays"]:
                target=(overlay["target"],overlay["version"])
                if (target not in registry.entries or overlay["target"] in targets or
                    not 1<=len(overlay["label"].strip())<=120 or len(overlay["label"])>120 or
                    any(ord(c)<32 or ord(c)==127 for c in overlay["label"])):
                    raise ValueError("invalid content preview target or label")
                if registry.entries[target]["season"]!=row["season"]:
                    raise ValueError("content era mismatch")
                targets.add(overlay["target"])
            self.entries[ident]=row
            self.versions[row["id"]].append(row)
        for rows in self.versions.values():
            rows.sort(key=lambda x:dc.version_tuple(x["version"]))
            for i,row in enumerate(rows):
                previous=rows[i-1] if i else None
                if row["previous"]!=(previous["version"] if previous else None):
                    raise ValueError("broken mod version chain")
                if previous and any(row[x]!=previous[x] for x in ("consumer","season","origin","rights","usage")):
                    raise ValueError("mod identity scope changed")
        for ident,row in self.entries.items():
            deps=set()
            seen=set()
            for dependency in row["dependencies"]:
                target=key(dependency)
                if target not in self.entries or target[0]==ident[0] or target[0] in seen:
                    raise ValueError("invalid exact dependency")
                other=self.entries[target]
                if any(row[x]!=other[x] for x in ("consumer","revision","season")):
                    raise ValueError("cross-scope dependency")
                seen.add(target[0]);deps.add(target);self.reverse[target].add(ident)
            if row["id"] in row["conflicts"] or not set(row["conflicts"])<=self.versions.keys():
                raise ValueError("invalid explicit conflict")
            self.edges[ident]=deps
        self.order=self.topological()
        self.fingerprint=k.digest({"catalog":catalog,"content":registry.fingerprint})

    def topological(self):
        remaining={ident:len(deps) for ident,deps in self.edges.items()}
        ready=[ident for ident,n in remaining.items() if n==0]
        heapq.heapify(ready)
        order=[]
        while ready:
            ident=heapq.heappop(ready);order.append(ident)
            for child in self.reverse[ident]:
                remaining[child]-=1
                if remaining[child]==0:
                    heapq.heappush(ready,child)
        if len(order)!=len(remaining):
            raise ValueError("mod dependency cycle")
        return order

    def stats(self):
        return {"status":"PASS","scope":"synthetic mod metadata only","version":VERSION,
                "identities":len(self.versions),"versions":len(self.entries),
                "dependency_edges":sum(map(len,self.edges.values())),
                "overlay_records":sum(len(x["overlays"]) for x in self.entries.values()),
                "fingerprint":self.fingerprint,"runtime_installed":False,"execution_authorized":False}

    def show(self,ident,version):
        row=self.entries[(ident,version)]
        return {"manifest":row,"manifest_sha256":hashlib.sha256(json_bytes(row)).hexdigest(),
                "runtime_installed":False}

    def plan(self,selection):
        r.check(selection,self.schemas["mod-selection.v1"])
        if len(selection["requested"])>MAX_MODS:
            raise ValueError("selection size limit")
        reasons=[]
        roots=[key(x) for x in selection["requested"]]
        if selection["revision"]!=self.consumers[selection["consumer"]]:
            reasons.append({"code":"STALE_CONSUMER_REVISION"})
        chosen=set()
        todo=list(roots)
        while todo:
            ident=todo.pop()
            if ident in chosen:
                continue
            if ident not in self.entries:
                reasons.append({"code":"MISSING_EXACT_MOD","mod":ref(ident)})
                continue
            chosen.add(ident)
            todo.extend(self.edges[ident])
        ids=defaultdict(set)
        targets=defaultdict(list)
        for ident in sorted(chosen):
            row=self.entries[ident]
            ids[ident[0]].add(ident[1])
            if row["consumer"]!=selection["consumer"] or row["revision"]!=selection["revision"]:
                reasons.append({"code":"CONSUMER_SCOPE_MISMATCH","mod":ref(ident)})
            for overlay in row["overlays"]:
                targets[overlay["target"]].append(ident)
        for ident,versions in sorted(ids.items()):
            if len(versions)>1:
                reasons.append({"code":"VERSION_CONFLICT","id":ident,"versions":sorted(versions)})
        pairs=set()
        for ident in chosen:
            for other in self.entries[ident]["conflicts"]:
                if other in ids:
                    pairs.add(tuple(sorted((ident[0],other))))
        for pair in sorted(pairs):
            reasons.append({"code":"EXPLICIT_CONFLICT","mods":list(pair)})
        for target,owners in sorted(targets.items()):
            if len(owners)>1:
                reasons.append({"code":"OVERLAY_CONFLICT","target":target,"mods":[ref(x) for x in owners]})
        ordered=[x for x in self.order if x in chosen]
        preview=[]
        if not reasons:
            for ident in ordered:
                for overlay in self.entries[ident]["overlays"]:
                    original=self.registry.entries[(overlay["target"],overlay["version"])]
                    preview.append({"mod":ref(ident),"target":overlay["target"],"version":overlay["version"],
                                    "before":original["name"],"after":overlay["label"]})
        return {"status":"BLOCKED" if reasons else "NOT_RUN","scope":"offline preview plan only",
                "reasons":reasons,"load_order":[ref(x) for x in ordered] if not reasons else [],
                "preview":preview,"runtime_installed":False,"execution_authorized":False}

    def remove(self,selection,ident):
        current=self.plan(selection)
        if current["status"]=="BLOCKED":
            return current
        requested={x["id"] for x in selection["requested"]}
        if ident not in requested:
            return {"status":"BLOCKED","reason":"NOT_EXPLICIT_ROOT","runtime_installed":False}
        candidate=dict(selection,requested=[x for x in selection["requested"] if x["id"]!=ident])
        result=self.plan(candidate)
        remaining={key(x) for x in result["load_order"]}
        old={key(x) for x in current["load_order"]}
        if any(x[0]==ident for x in remaining):
            return {"status":"BLOCKED","reason":"STILL_REQUIRED","runtime_installed":False}
        return {"status":result["status"],"removed":[ref(x) for x in reversed(self.order) if x in old-remaining],
                "candidate_selection":candidate,"plan":result,"runtime_installed":False,"execution_authorized":False}

    def rollback(self,selection,ident):
        current=self.plan(selection)
        if current["status"]=="BLOCKED":
            return current
        matches=[x for x in selection["requested"] if x["id"]==ident]
        if len(matches)!=1:
            return {"status":"BLOCKED","reason":"NOT_EXPLICIT_ROOT","runtime_installed":False}
        row=self.entries[key(matches[0])]
        if row["previous"] is None:
            return {"status":"BLOCKED","reason":"NO_PREVIOUS_VERSION","runtime_installed":False}
        candidate=dict(selection,requested=[ref((ident,row["previous"])) if x["id"]==ident else x for x in selection["requested"]])
        result=self.plan(candidate)
        return {"status":result["status"],"candidate_selection":candidate,"plan":result,
                "runtime_installed":False,"execution_authorized":False}

    def gate(self,selection):
        plan=self.plan(selection)
        return {"status":"BLOCKED","reasons":["NO_NATIVE_MOD_LOADER","SYNTHETIC_ONLY","CONSUMER_VALIDATION_NOT_RUN"],
                "plan":plan,"runtime_installed":False,"execution_authorized":False}

    def package(self,ident,version):
        # Produce a ZIP only in memory; reproducible fixture, never an installed mod.
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,"w",compression=zipfile.ZIP_STORED) as z:
            info=zipfile.ZipInfo("manifest.json")
            info.create_system=3
            info.external_attr=(stat.S_IFREG|0o600)<<16
            z.writestr(info,json_bytes(self.entries[(ident,version)]))
        return self.inspect_zip(buf.getvalue())

    def inspect_zip(self,raw):
        if type(raw) is not bytes or not 1<=len(raw)<=MAX_ZIP:
            raise ValueError("package size limit")
        with zipfile.ZipFile(io.BytesIO(raw),"r") as z:
            entries=z.infolist()
            # Single data-only member, no extraction, nested archives, scripts, or paths.
            if len(entries)!=1 or z.comment:
                raise ValueError("expected one manifest and no archive comment")
            info=entries[0]
            mode=info.external_attr>>16
            if (info.filename!="manifest.json" or info.orig_filename!="manifest.json" or
                info.is_dir() or stat.S_IFMT(mode) not in (0,stat.S_IFREG) or
                info.flag_bits&1 or info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED) or
                not 1<=info.file_size<=MAX_MANIFEST or not 1<=info.compress_size<=MAX_ZIP or
                info.file_size>100*info.compress_size):
                raise ValueError("unsafe or oversized ZIP member")
            with z.open(info) as handle:
                body=handle.read(MAX_MANIFEST+1)
            if len(body)!=info.file_size or len(body)>MAX_MANIFEST:
                raise ValueError("manifest size mismatch")
        manifest=json.loads(body.decode("utf-8"),object_pairs_hook=r.pairs,parse_constant=r.bad_constant,parse_float=r.finite_float)
        r.check(manifest,self.schemas["mod-manifest.v1"])
        if key(manifest) not in self.entries or manifest!=self.entries[key(manifest)]:
            raise ValueError("unregistered or modified fixture manifest")
        return {"status":"PASS","scope":"registered synthetic ZIP manifest inspection only",
                "mod":ref(key(manifest)),"package_sha256":hashlib.sha256(raw).hexdigest(),
                "manifest_sha256":hashlib.sha256(body).hexdigest(),"extracted":False,
                "runtime_installed":False,"execution_authorized":False}

def load(*,registry=None):
    _,schemas=r.load_registry()
    return Modding(k.document(ROOT/"data/modding/catalog.json",{"entries"}),schemas,content.load() if registry is None else registry)

def read_zip(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("expected regular ZIP file")
    with path.open("rb") as f:
        return f.read(MAX_ZIP+1)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command",required=True)
    for name in ("validate","stats","list"):
        sub.add_parser(name)
    for name in ("show","package"):
        q=sub.add_parser(name);q.add_argument("id");q.add_argument("version")
    sub.add_parser("inspect-zip").add_argument("path",type=Path)
    for name in ("plan","gate","remove","rollback"):
        q=sub.add_parser(name);q.add_argument("selection",type=Path)
        if name in ("remove","rollback"):
            q.add_argument("id")
    args=p.parse_args(argv)
    try:
        m=load()
        if args.command in ("validate","stats"):
            result=m.stats()
        elif args.command=="list":
            result={"entries":[m.entries[x] for x in sorted(m.entries)]}
        elif args.command=="inspect-zip":
            result=m.inspect_zip(read_zip(args.path))
        elif args.command in ("show","package"):
            result=getattr(m,args.command)(args.id,args.version)
        else:
            selection=r.read(args.selection)
            result=getattr(m,args.command)(selection,args.id) if args.command in ("remove","rollback") else getattr(m,args.command)(selection)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if result.get("status")=="BLOCKED" else 0
    except (ValueError,TypeError,KeyError,OSError,AttributeError,RecursionError,RuntimeError,zipfile.BadZipFile,NotImplementedError) as exc:
        print(json.dumps({"status":"FAIL","error":str(exc)[:500]}),file=sys.stderr)
        return 2

if __name__=="__main__":
    sys.exit(main())
