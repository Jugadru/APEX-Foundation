#!/usr/bin/env python3
"""Offline research intelligence: inspect, never adopt or execute external code."""
import argparse
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import urlsplit, urlunsplit

import apex_foundation as legacy
import apex_foundation_registry as registry

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "knowledge"
VERSION = "0.1.1"
MAX_RESULTS = 200
REF_FIELDS = {"id", "group", "name", "idea", "url", "status", "license"}
IDEA_FIELDS = {"id", "department", "name", "status", "references"}

def norm(value):
    return " ".join(re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKD", value)
                              .encode("ascii", "ignore").decode().casefold()))

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()

def canonical_url(value):
    if not isinstance(value, str) or len(value) > 2048 or any(c.isspace() for c in value):
        raise ValueError("invalid source URL")
    url = urlsplit(value)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.port:
        raise ValueError("expected public HTTPS URL without credentials or port")
    if not re.fullmatch(r"[a-zA-Z0-9.-]+", url.hostname) or "." not in url.hostname:
        raise ValueError("invalid source host")
    # Preserve query semantics and path case; only normalize host, trailing slash, fragment.
    return urlunsplit(("https", url.hostname.lower(), url.path.rstrip("/") or "/", url.query, ""))

def nonempty(value):
    return isinstance(value, str) and bool(value.strip())

def strict_fields(row, fields):
    if type(row) is not dict or set(row) != fields:
        raise ValueError("missing or unknown fields")

def document(path, fields):
    v = registry.read(path)
    strict_fields(v, fields | {"schema"})
    if type(v["schema"]) is not int or v["schema"] != 1:
        raise ValueError("unsupported knowledge schema")
    return v

def history_check(root=ROOT, docs=DOCS):
    lock = document(docs / "history-lock.json", {"source_revision", "files"})
    expected = {"docs/references/references.json", "docs/references/possibilities.json",
                "docs/references/ROADMAP_HYPER.md", "docs/references/domains.json",
                "docs/references/BIBLIOTECA_198.md", "docs/references/CATALOGO_120.md"}
    if set(lock["files"]) != expected or not re.fullmatch(r"[0-9a-f]{40}", lock["source_revision"]):
        raise ValueError("invalid historical lock")
    for path, blob in lock["files"].items():
        raw = (root / path).read_bytes()
        # Git blob ID, not a security signature or claim of external authenticity.
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if actual != blob:
            raise ValueError("historical file changed without reviewed lock migration: " + path)
    return {"source_revision":lock["source_revision"], "files_checked":len(expected)}

def consumer_inventory(departments, docs=DOCS):
    inv = document(docs / "consumer-inventory.json", {"repository","revision","scope","departments"})
    if (inv["repository"] != "Jugadru/APEX-Simulation"
            or not re.fullmatch(r"[0-9a-f]{40}", inv["revision"])
            or not nonempty(inv["scope"]) or set(inv["departments"]) != set(departments)):
        raise ValueError("invalid consumer inventory")
    for rows in inv["departments"].values():
        if type(rows) is not list or not rows:
            raise ValueError("empty consumer inventory")
        seen = set()
        for row in rows:
            strict_fields(row, {"path","blob_sha","url"})
            path = row["path"]
            if (not re.fullmatch(r"(scripts|tools)/[A-Za-z0-9_./-]+\.(gd|py)",path)
                    or any(p in ("",".","..") for p in path.split("/"))
                    or path in seen or not re.fullmatch(r"[0-9a-f]{40}",row["blob_sha"])
                    or row["url"] != f"https://github.com/{inv['repository']}/blob/{inv['revision']}/{path}"):
                raise ValueError("invalid consumer path")
            seen.add(path)
    return inv

def load():
    history = history_check()
    refs = document(legacy.DOCS / "references.json", {"source", "entries"})
    ideas = document(legacy.DOCS / "possibilities.json", {"entries"})
    policy = document(DOCS / "policy.json", {"priority_references", "departments", "score", "notice"})
    obs = document(DOCS / "observations.json", {"entries"})
    reg, schemas = registry.load_registry()
    registry.validate_registry(reg, schemas)
    domains = registry.read(legacy.DOCS / "domains.json")["domains"]
    knowledge = Knowledge(refs, ideas, policy, obs, reg, schemas, domains)
    knowledge.history = history
    knowledge.inventory = consumer_inventory(knowledge.departments)
    knowledge.fingerprint = digest({"catalog":knowledge.fingerprint,"history":history,"inventory":knowledge.inventory})
    return knowledge

class Knowledge:
    def __init__(self, refs, ideas, policy, obs, reg, schemas, domains):
        self.source = refs["source"]
        r, _ = legacy.catalog(refs, "REF", 198)
        i, _ = legacy.catalog(ideas, "IDEA", 120)
        self.refs = {x["id"]: x for x in r}
        self.ideas = {x["id"]: x for x in i}
        self.policy = policy
        self.obs = defaultdict(list)
        self.links = defaultdict(list)
        self.groups = Counter()
        self.departments = Counter()
        self.urls = defaultdict(list)
        self.names = defaultdict(list)
        self.modules = {x["id"] for x in reg["modules"]}
        self.domains = set(domains)
        if not nonempty(self.source):
            raise ValueError("missing catalog provenance")
        for key, row in self.refs.items():
            strict_fields(row, REF_FIELDS)
            if not all(nonempty(row[k]) for k in REF_FIELDS - {"url"}):
                raise ValueError("empty reference " + key)
            if row["status"] != "REVALIDAR" or row["license"] != "NÃO AUDITADA":
                raise ValueError("historical catalog status changed: " + key)
            self.groups[row["group"]] += 1
            self.names[norm(row["name"])].append(key)
            if row["url"] is not None:
                self.urls[canonical_url(row["url"])].append(key)
        for key, row in self.ideas.items():
            strict_fields(row, IDEA_FIELDS)
            if not all(nonempty(row[k]) for k in IDEA_FIELDS - {"references"}):
                raise ValueError("empty idea " + key)
            links = row["references"]
            if (type(links) is not list or not links or len(set(links)) != len(links)
                    or not set(links) <= self.refs.keys() or row["status"] != "AUDITAR_EXISTENTE"):
                raise ValueError("invalid idea links/status " + key)
            self.departments[row["department"]] += 1
            for rid in links:
                self.links[rid].append(key)
        priorities = policy["priority_references"]
        if type(priorities) is not list or len(set(priorities)) != len(priorities) or not set(priorities) <= self.refs.keys():
            raise ValueError("invalid priority references")
        if set(policy["departments"]) != set(self.departments):
            raise ValueError("department policy coverage mismatch")
        for row in policy["departments"].values():
            strict_fields(row, {"domain", "owner_module", "acceptance", "roadmap"})
            if (row["domain"] not in self.domains or row["owner_module"] not in self.modules
                    or not all(nonempty(x) for x in row.values())):
                raise ValueError("invalid department mapping")
        strict_fields(policy["score"], {"priority_reference", "has_url", "linked_idea", "linked_idea_cap", "documented_source"})
        if any(type(n) is not int or not 0 <= n <= 100 for n in policy["score"].values()) or not nonempty(policy["notice"]):
            raise ValueError("invalid research scoring policy")
        seen = set()
        for row in obs["entries"]:
            registry.check(row, schemas["research-observation.v1"])
            if row["id"] in seen or row["reference_id"] not in self.refs:
                raise ValueError("duplicate or orphan observation")
            seen.add(row["id"])
            date.fromisoformat(row["observed_on"])
            canonical_url(row["source_url"])
            # This first version records document observations, never license/adoption clearance.
            self.obs[row["reference_id"]].append(row)
        self.fingerprint = digest({"refs": refs, "ideas": ideas, "policy": policy, "observations": obs})

    def reference(self, key):
        row = self.refs[key]
        return {"record": row, "source": self.source, "record_sha256": digest(row),
                "linked_ideas": sorted(self.links[key]), "observations": self.obs[key],
                "evidence_state": "DOCUMENT_OBSERVED" if self.obs[key] else "UNVERIFIED",
                "license_state": "UNREVIEWED", "reuse": "BLOCKED",
                "implementation_authorized": False}

    def idea(self, key):
        row = self.ideas[key]
        policy = self.policy["departments"][row["department"]]
        return {"record": row, "record_sha256": digest(row), **policy,
                "references": [self.reference(r) for r in row["references"]],
                "audit_state": "NOT_RUN", "implementation_authorized": False}

    def duplicates(self):
        return {"scope": "candidates only; no automatic merge",
                "same_normalized_name": [sorted(ids) for _, ids in sorted(self.names.items()) if len(ids) > 1],
                "same_normalized_url": [sorted(ids) for _, ids in sorted(self.urls.items()) if len(ids) > 1]}

    def stats(self):
        return {"status": "PASS", "scope": "offline catalog structure only",
                "version": VERSION, "fingerprint": self.fingerprint,
                "references": len(self.refs), "ideas": len(self.ideas),
                "groups": dict(sorted(self.groups.items())), "departments": dict(sorted(self.departments.items())),
                "with_url": sum(x["url"] is not None for x in self.refs.values()),
                "without_url": sum(x["url"] is None for x in self.refs.values()),
                "document_observed": sum(bool(self.obs[k]) for k in self.refs),
                "observations": sum(len(v) for v in self.obs.values()),
                "unlinked_references": sorted(set(self.refs) - {k for k,v in self.links.items() if v}),
                "historical_files_checked": self.history["files_checked"],
                "consumer_revision": self.inventory["revision"],
                "consumer_candidate_paths": sum(len(v) for v in self.inventory["departments"].values()),
                "links": sum(len(v) for v in self.links.values()),
                "license_approved": 0, "implementation_authorized": False,
                "duplicates": self.duplicates()}

    def search(self, query, kind="all", department=None, limit=20):
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 200:
            raise ValueError("query length must be 1..200")
        if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
            raise ValueError("limit must be 1..200")
        if kind not in ("all", "reference", "idea") or (department is not None and department not in self.departments):
            raise ValueError("unknown search filter")
        terms = norm(query).split()
        if not terms:
            raise ValueError("no searchable terms")
        results = []
        if kind != "idea":
            for key, row in self.refs.items():
                if department and not any(self.ideas[i]["department"] == department for i in self.links[key]):
                    continue
                results.append(("reference", key, row["name"], row["idea"] + " " + row["group"]))
        if kind != "reference":
            for key, row in self.ideas.items():
                if department and row["department"] != department:
                    continue
                results.append(("idea", key, row["name"], row["department"] + " " + " ".join(row["references"])))
        matches = []
        for typ, key, name, detail in results:
            heading = norm(key + " " + name)
            full = heading + " " + norm(detail)
            if all(t in full for t in terms):
                score = (100 if norm(query) == norm(key) else 0) + sum(5 if t in heading else 1 for t in terms)
                matches.append({"id":key, "kind":typ, "name":name, "score":score})
        matches.sort(key=lambda x: (-x["score"], x["id"]))
        return {"total": len(matches), "matches": matches[:limit], "truncated": len(matches) > limit}

    def queue(self, limit=20):
        if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
            raise ValueError("limit must be 1..200")
        weights = self.policy["score"]
        items = []
        for key, row in self.refs.items():
            parts = {"priority_reference": weights["priority_reference"] if key in self.policy["priority_references"] else 0,
                     "has_url": weights["has_url"] if row["url"] else 0,
                     "linked_ideas": min(len(self.links[key]), weights["linked_idea_cap"]) * weights["linked_idea"],
                     "documented_source": weights["documented_source"] if self.obs[key] else 0}
            items.append({"id":key,"name":row["name"],"score":sum(parts.values()),"components":parts,
                          "next_action":"DISCOVER_SOURCE" if not row["url"] else
                          "REVIEW_REVISION_AND_LICENSE" if self.obs[key] else "VERIFY_SOURCE",
                          "reuse":"BLOCKED"})
        items.sort(key=lambda x:(-x["score"], x["id"]))
        return {"scope":self.policy["notice"],"total":len(items),"items":items[:limit]}

    def plan(self, key):
        idea = self.idea(key)
        return {"id":key,"title":idea["record"]["name"],"domain":idea["domain"],
                "owner_module":idea["owner_module"],"roadmap":idea["roadmap"],
                "acceptance":idea["acceptance"],"status":"BLOCKED",
                "implementation_authorized":False,"reference_ids":idea["record"]["references"],
                "steps":["Audit current consumer at exact SHA and identify existing implementation",
                         "Review source revisions, license and applicable rights",
                         "Specify contracts, units, baseline and targeted regression",
                         "Request owner review before implementation; preserve rollback"],
                "consumer_revision":self.inventory["revision"],
                "consumer_candidates":self.inventory["departments"][idea["record"]["department"]],
                "consumer_audit":"NOT_RUN", "fingerprint":self.fingerprint}

    def audit(self, department=None):
        if department is not None and department not in self.departments:
            raise ValueError("unknown department")
        rows = []
        for name, policy in sorted(self.policy["departments"].items()):
            if department is not None and name != department:
                continue
            ids = sorted(k for k,v in self.ideas.items() if v["department"] == name)
            ref_ids = sorted({r for key in ids for r in self.ideas[key]["references"]})
            rows.append({"department":name, **policy, "idea_ids":ids, "reference_ids":ref_ids,
                         "document_observed":[r for r in ref_ids if self.obs[r]],
                         "missing_url":[r for r in ref_ids if not self.refs[r]["url"]],
                         "candidate_files":self.inventory["departments"][name], "audit_state":"NOT_RUN"})
        return {"scope":self.inventory["scope"], "revision":self.inventory["revision"],
                "implementation_authorized":False, "departments":rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "stats", "duplicates"):
        sub.add_parser(name)
    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--kind", choices=["all","reference","idea"], default="all")
    p.add_argument("--department")
    p.add_argument("--limit",type=int,default=20)
    for name in ("show","plan"):
        sub.add_parser(name).add_argument("id")
    sub.add_parser("audit").add_argument("--department")
    sub.add_parser("queue").add_argument("--limit",type=int,default=20)
    args = parser.parse_args(argv)
    try:
        k = load()
        if args.command in ("validate","stats"):
            result = k.stats()
        elif args.command == "search":
            result = k.search(args.query,args.kind,args.department,args.limit)
        elif args.command == "show":
            result = k.reference(args.id) if args.id in k.refs else k.idea(args.id)
        elif args.command == "duplicates":
            result = k.duplicates()
        elif args.command == "audit":
            result = k.audit(args.department)
        elif args.command == "queue":
            result = k.queue(args.limit)
        else:
            result = k.plan(args.id)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError, TypeError, KeyError, OSError, AttributeError, RecursionError) as exc:
        print(json.dumps({"status":"FAIL","error":str(exc)[:500]}),file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
