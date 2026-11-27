#!/usr/bin/env python3
"""Read-only content identities, exact links and fixture validation."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

import apex_foundation_registry as r
import apex_knowledge as k
import apex_data_center as dc
import apex_architecture as arch

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/"docs"/"content"
KINDS={"driver","staff","team","manufacturer","supplier","circuit","layout","category",
       "championship","season","regulation","vehicle","component","asset"}
VERSION="0.2.1"
MAX_ENTITIES=5000

class ContentRegistry:
    def __init__(self,catalog,policy,matrix,inventory,schemas,data):
        self.schemas=schemas
        self.data=data
        self.entries={}
        self.reverse=defaultdict(set)
        self.matrix={}
        self.inventory=inventory
        self.policy=policy
        if set(policy["relations"])!=KINDS or set(policy["attributes"])!=KINDS or not k.nonempty(policy["scope"]):
            raise ValueError("content kind coverage mismatch")
        for kind,rules in policy["relations"].items():
            if type(rules) is not dict:
                raise ValueError("invalid relations")
            for role,spec in rules.items():
                k.strict_fields(spec,{"target","minimum","maximum"})
                if (not k.nonempty(role) or spec["target"] not in KINDS or
                    any(type(spec[x]) is not int for x in ("minimum","maximum")) or
                    not 0<=spec["minimum"]<=spec["maximum"]<=100):
                    raise ValueError("invalid relation policy")
        for rules in policy["attributes"].values():
            if type(rules) is not dict or not rules:
                raise ValueError("empty attribute policy")
            for key,values in rules.items():
                if not k.nonempty(key) or type(values) is not list or not values or len(set(values))!=len(values) or not all(k.nonempty(x) for x in values):
                    raise ValueError("invalid attribute policy")
        rows=catalog["entries"]
        if type(rows) is not list or not 1<=len(rows)<=MAX_ENTITIES:
            raise ValueError("invalid content count")
        versions=defaultdict(list)
        for row in rows:
            r.check(row,schemas["content-entity.v1"])
            key=(row["id"],row["version"])
            kind=row["kind"]
            dc.version_tuple(row["version"])
            if (key in self.entries or not row["id"].startswith(kind+".") or
                row["season"]!=data.era["season"] or row["technology"] not in data.era["allowed"]):
                raise ValueError("duplicate identity, kind prefix, era or technology mismatch")
            attrs={x["key"]:x["value"] for x in row["attributes"]}
            if (len(attrs)!=len(row["attributes"]) or set(attrs)!=set(policy["attributes"][kind]) or
                any(v not in policy["attributes"][kind][a] for a,v in attrs.items())):
                raise ValueError("invalid kind-specific attributes")
            if len(row["links"])>100 or len(row["datasets"])>20:
                raise ValueError("relationship limit")
            self.entries[key]=row
            versions[key[0]].append(row)
        for ident,items in versions.items():
            items.sort(key=lambda x:dc.version_tuple(x["version"]))
            for i,row in enumerate(items):
                prev=items[i-1] if i else None
                if row["previous"]!=(prev["version"] if prev else None):
                    raise ValueError("broken content version chain")
                if prev and any(row[x]!=prev[x] for x in ("kind","season","origin","rights","usage")):
                    raise ValueError("identity metadata changed across versions")
        self.edges={}
        for key,row in self.entries.items():
            rules=policy["relations"][row["kind"]]
            counts=Counter()
            edges=set()
            seen=set()
            for relation in row["links"]:
                role=relation["role"]
                target=(relation["target"],relation["version"])
                if (role not in rules or target not in self.entries or target==key or
                    self.entries[target]["kind"]!=rules[role]["target"] or
                    self.entries[target]["season"]!=row["season"] or (role,target) in seen):
                    raise ValueError("invalid exact content relationship")
                seen.add((role,target))
                counts[role]+=1
                edges.add(target)
                self.reverse[target].add(key)
            for role,spec in rules.items():
                if not spec["minimum"]<=counts[role]<=spec["maximum"]:
                    raise ValueError("required relation cardinality mismatch")
            self.edges[key]=edges
            if row["datasets"] and row["kind"]!="vehicle":
                raise ValueError("dataset links not allowed for content kind")
            for link in row["datasets"]:
                ds=(link["id"],link["version"])
                if ds not in data.entries or link["record"] not in data.payloads[ds]:
                    raise ValueError("missing exact dataset record")
                manifest=data.entries[ds]
                if manifest["season"]!=row["season"] or manifest["provenance"]["origin"]!="synthetic" or manifest["domain"]!="vehicle_dynamics":
                    raise ValueError("incompatible dataset provenance or domain")
        self.order=self.topological()
        for row in matrix["entries"]:
            r.check(row,schemas["content-consumer.v1"])
            c=row["consumer"]
            if c in self.matrix or data.consumers.get(c)!=row["revision"]:
                raise ValueError("invalid exact consumer revision")
            self.matrix[c]=row
        if set(self.matrix)!=set(data.consumers):
            raise ValueError("missing consumer")
        if (inventory["repository"]!="Jugadru/APEX-Simulation" or
            inventory["revision"]!=data.consumers["core2"] or not k.nonempty(inventory["scope"])):
            raise ValueError("invalid consumer source inventory")
        seen=set()
        for row in inventory["paths"]:
            k.strict_fields(row,{"path","blob_sha","url"})
            path=row["path"]
            if (not arch.valid_path(path) or not path.startswith("data/") or path in seen or
                not arch.sha(row["blob_sha"]) or row["url"]!=f"https://github.com/{inventory['repository']}/blob/{inventory['revision']}/{path}"):
                raise ValueError("invalid content source path")
            seen.add(path)
        if not seen:
            raise ValueError("empty source inventory")
        self.fingerprint=k.digest({"catalog":catalog,"policy":policy,"matrix":matrix,"inventory":inventory,"data":data.fingerprint})

    def topological(self):
        # Kahn traversal: O(nodes + edges), stable ordering, no recursion.
        import heapq
        remaining={key:len(targets) for key,targets in self.edges.items()}
        ready=[key for key,n in remaining.items() if not n]
        heapq.heapify(ready)
        order=[]
        while ready:
            key=heapq.heappop(ready)
            order.append(key)
            for child in self.reverse[key]:
                remaining[child]-=1
                if remaining[child]==0:
                    heapq.heappush(ready,child)
        if len(order)!=len(remaining):
            raise ValueError("content dependency cycle")
        return order

    @staticmethod
    def keyrow(key):
        return {"id":key[0],"version":key[1]}

    def closure(self,key,graph):
        seen={key}
        todo=[key]
        while todo:
            for target in graph.get(todo.pop(),()):
                if target not in seen:
                    seen.add(target)
                    todo.append(target)
        return sorted(seen-{key})

    def stats(self):
        return {"status":"PASS","scope":"synthetic content structure only","version":VERSION,
                "fingerprint":self.fingerprint,"identities":len({i for i,v in self.entries}),
                "versions":len(self.entries),"kinds":len({x["kind"] for x in self.entries.values()}),
                "relations":sum(len(x["links"]) for x in self.entries.values()),
                "dataset_links":sum(len(x["datasets"]) for x in self.entries.values()),
                "source_candidates":len(self.inventory["paths"]),
                "by_kind":dict(sorted(Counter(x["kind"] for x in self.entries.values()).items())),
                "production_approved":0,"execution_authorized":False}

    def show(self,ident,version):
        key=(ident,version)
        row=self.entries[key]
        return {"entity":row,"record_sha256":k.digest(row),
                "direct_dependents":[self.keyrow(x) for x in sorted(self.reverse[key])],
                "production_approved":False}

    def search(self,query,kind=None,limit=50):
        if not isinstance(query,str) or not 1<=len(query.strip())<=200 or not k.norm(query):
            raise ValueError("invalid query")
        if kind is not None and kind not in KINDS:
            raise ValueError("invalid kind")
        if type(limit) is not int or not 1<=limit<=200:
            raise ValueError("invalid limit")
        terms=k.norm(query).split()
        rows=[{"id":i,"version":v,"kind":row["kind"],"name":row["name"]}
              for (i,v),row in sorted(self.entries.items())
              if (kind is None or row["kind"]==kind) and
              all(t in k.norm(i+" "+row["name"]+" "+row["kind"]) for t in terms)]
        return {"total":len(rows),"matches":rows[:limit],"truncated":len(rows)>limit}

    def graph(self,ident,version):
        key=(ident,version)
        self.entries[key]
        return {"root":self.keyrow(key),
                "dependencies":[self.keyrow(x) for x in self.closure(key,self.edges)],
                "dependents":[self.keyrow(x) for x in self.closure(key,self.reverse)],
                "dependency_first_order":[self.keyrow(x) for x in self.order if x in set(self.closure(key,self.edges))|{key}],
                "production_approved":False}

    def diff(self,ident,old,new):
        a,b=self.entries[(ident,old)],self.entries[(ident,new)]
        if dc.version_tuple(old)>=dc.version_tuple(new):
            raise ValueError("expected increasing versions")
        changes=[key for key in sorted(a) if a[key]!=b[key] and key not in ("version","previous")]
        return {"id":ident,"old":old,"new":new,"changed_fields":changes,
                "status":"BLOCKED" if any(x in changes for x in ("links","datasets","technology")) else "NOT_RUN",
                "production_approved":False}

    def gate(self,ident,version,consumer,revision):
        self.entries[(ident,version)]
        if consumer not in self.matrix or not arch.sha(revision):
            raise ValueError("invalid consumer or revision")
        m=self.matrix[consumer]
        return {"status":"BLOCKED","id":ident,"version":version,"consumer":consumer,"revision":revision,
                "reasons":["TEST_ONLY","NO_RUNTIME_ADOPTION",
                           "CONSUMER_VALIDATION_"+m["status"] if m["revision"]==revision else "UNKNOWN_EXACT_CONSUMER_REVISION"],
                "execution_authorized":False,"production_approved":False}

def load():
    _,schemas=r.load_registry()
    data=dc.load()
    return ContentRegistry(k.document(ROOT/"data/content/catalog.json",{"entries"}),
                           k.document(DOCS/"policy.json",{"relations","attributes","scope"}),
                           k.document(DOCS/"consumer-matrix.json",{"entries"}),
                           k.document(DOCS/"source-inventory.json",{"repository","revision","scope","paths"}),
                           schemas,data)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    s=p.add_subparsers(dest="command",required=True)
    for name in ("validate","stats"):
        s.add_parser(name)
    q=s.add_parser("search")
    q.add_argument("query")
    q.add_argument("--kind")
    q.add_argument("--limit",type=int,default=50)
    for name in ("show","graph","diff","gate"):
        q=s.add_parser(name)
        q.add_argument("id")
        if name=="diff":
            q.add_argument("old")
            q.add_argument("new")
        else:
            q.add_argument("version")
        if name=="gate":
            q.add_argument("consumer")
            q.add_argument("revision")
    a=p.parse_args(argv)
    try:
        c=load()
        if a.command in ("validate","stats"):
            out=c.stats()
        elif a.command=="search":
            out=c.search(a.query,a.kind,a.limit)
        elif a.command=="diff":
            out=c.diff(a.id,a.old,a.new)
        elif a.command=="gate":
            out=c.gate(a.id,a.version,a.consumer,a.revision)
        else:
            out=getattr(c,a.command)(a.id,a.version)
        print(json.dumps(out,ensure_ascii=False,indent=2))
        return 1 if a.command=="gate" else 0
    except (ValueError,TypeError,KeyError,OSError,AttributeError,RecursionError) as exc:
        print(json.dumps({"status":"FAIL","error":str(exc)[:500]}),file=sys.stderr)
        return 2

if __name__=="__main__":
    sys.exit(main())
