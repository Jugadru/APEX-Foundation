#!/usr/bin/env python3
"""Verify an explicit Core 2 metadata report against an exact local source checkout.

No network, execution of consumer code, persistence or Content Registry mutation.
"""
import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import apex_foundation_registry as registry

PATHS=("data/season_2012.json","data/teams.json")
MAX_SOURCE=4*1024*1024
MAX_REPORT=256*1024
SHA=re.compile(r"[0-9a-f]{40}\Z")

def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8")

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def load_bytes(path,limit):
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=limit:
        raise ValueError("expected bounded regular file")
    with path.open("rb") as handle:
        raw=handle.read(limit+1)
    if not 0<len(raw)<=limit:
        raise ValueError("file size bound")
    return raw

def bad_constant(value):
    raise ValueError("non-finite JSON constant")

def parse(raw):
    return json.loads(raw.decode("utf-8"),object_pairs_hook=registry.pairs,
                      parse_constant=bad_constant,parse_float=Decimal)

def git(root,*args):
    # Exact identity must not follow replacement refs or inherited Git overrides.
    # Read-only verifier: no lazy fetch of missing objects, even in a partial clone.
    env={k:v for k,v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_ALLOW_PROTOCOL="",GIT_NO_LAZY_FETCH="1",GIT_OPTIONAL_LOCKS="0",
               GIT_CONFIG_NOSYSTEM="1",GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT="0")
    return subprocess.check_output(["git","--no-replace-objects","-C",str(root),*args],
                                   env=env,timeout=20)

def committed_blob(root,revision,path):
    raw=git(root,"ls-tree","-z",revision,"--",path)
    match=re.fullmatch(rb"100(?:644|755) blob ([0-9a-f]{40})\t"+re.escape(path.encode("ascii"))+rb"\x00",raw)
    if not match:
        raise ValueError("expected committed regular source blob")
    return match.group(1).decode("ascii")

def name(value):
    if not isinstance(value,str) or not 1<=len(value)<=160 or value!=value.strip() or any(ord(c)<32 or 127<=ord(c)<=159 for c in value):
        raise ValueError("invalid metadata label")
    return value

def validate_report(report,schema,expected_revision):
    if not isinstance(expected_revision,str) or not SHA.fullmatch(expected_revision):
        raise ValueError("expected exact consumer SHA")
    try:
        registry.check(report,schema)
    except TypeError as exc:
        raise ValueError("invalid report value") from exc
    body=report["body"]
    if body["revision"]!=expected_revision or digest(body)!=report["body_sha256"]:
        raise ValueError("report revision or checksum mismatch")
    sources=body["sources"]
    if [x["path"] for x in sources]!=list(PATHS) or any(not 0<x["size_bytes"]<=MAX_SOURCE for x in sources):
        raise ValueError("source identity coverage or size")
    c=body["catalog"]
    teams,drivers,circuits=c["teams"],c["drivers"],c["circuits"]
    if c["season"]!=2012 or (len(teams),len(drivers),len(circuits))!=(12,24,20):
        raise ValueError("unexpected 2012 catalog dimensions")
    if [x["index"] for x in teams]!=list(range(12)) or [(x["team_index"],x["slot"]) for x in drivers]!=[(i,j) for i in range(12) for j in range(2)] or [x["index"] for x in circuits]!=list(range(20)):
        raise ValueError("catalog ordering or slot mapping mismatch")
    if len({name(x["name"]) for x in teams})!=12 or len({name(x["name"]) for x in drivers})!=24 or len({x["code"] for x in circuits})!=20:
        raise ValueError("duplicate native identity")
    for row in circuits:
        name(row["name"]);name(row["country"])
        if not 1<=row["laps"]<=200:
            raise ValueError("invalid lap count")
    return body

def verify(report,schema,expected_revision,source_root):
    body=validate_report(report,schema,expected_revision)
    root=Path(source_root).resolve(strict=True)
    # Ensure Git commands are bound to the actual consumer root, not a parent repository.
    top=Path(git(root,"rev-parse","--show-toplevel").decode("utf-8").strip()).resolve()
    revision=git(root,"rev-parse","--verify","HEAD^{commit}").decode("ascii").strip()
    if top!=root or revision!=expected_revision:
        raise ValueError("source checkout is not the expected exact revision")
    values=[]
    for source in body["sources"]:
        path=source["path"]
        local=root/path
        if local.parent.is_symlink():
            raise ValueError("symlink source directory")
        raw=load_bytes(local,MAX_SOURCE)
        blob=committed_blob(root,revision,path)
        actual=hashlib.sha1(b"blob "+str(len(raw)).encode("ascii")+b"\0"+raw).hexdigest()
        if blob!=actual or blob!=source["git_blob"] or len(raw)!=source["size_bytes"] or hashlib.sha256(raw).hexdigest()!=source["sha256"]:
            raise ValueError("source bytes or Git blob differ")
        values.append(parse(raw))
    season,teams=values
    if (type(season) is not dict or type(teams) is not list or type(season.get("teams")) is not list or
        type(season.get("tracks")) is not list or type(season.get("season")) is not int or
        season["season"]!=2012 or season["teams"]!=teams):
        raise ValueError("native source roster or era mismatch")
    c=body["catalog"]
    if len(teams)!=len(c["teams"]) or len(season["tracks"])!=len(c["circuits"]):
        raise ValueError("native source dimensions mismatch")
    # Compare only the projected fields; no ratings, geometry, or sporting state are imported.
    for row,original in zip(c["teams"],teams):
        if (type(original) is not dict or type(original.get("drivers")) is not list or
            row["name"]!=original["name"] or len(original["drivers"])!=2):
            raise ValueError("native team projection mismatch")
    for row in c["drivers"]:
        if row["name"]!=teams[row["team_index"]]["drivers"][row["slot"]]["name"]:
            raise ValueError("native driver projection mismatch")
    for row,original in zip(c["circuits"],season["tracks"]):
        if type(original["laps"]) is not int or any(row[field]!=original[field] for field in ("code","name","country","laps")):
            raise ValueError("native circuit projection mismatch")
    return {"status":"PASS","scope":"exact local metadata projection only","contract":"core2-metadata.v1",
            "revision":revision,"body_sha256":report["body_sha256"],"counts":{"teams":12,"drivers":24,"circuits":20},
            "source_bytes_verified":True,"native_runtime_verified":False,"content_imported":False,
            "runtime_applied":False,"execution_authorized":False}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("report",type=Path)
    p.add_argument("--revision",required=True)
    p.add_argument("--source-root",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        _,schemas=registry.load_registry()
        report=parse(load_bytes(args.report,MAX_REPORT))
        result=verify(report,schemas["core2-metadata.v1"],args.revision,args.source_root)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,TypeError,KeyError,OSError,UnicodeError,subprocess.SubprocessError,RecursionError) as exc:
        print(json.dumps({"status":"FAIL","error":str(exc)[:250],"execution_authorized":False}),file=sys.stderr)
        return 2

if __name__=="__main__":
    sys.exit(main())
