#!/usr/bin/env python3
"""Unified APEX Foundation command line; offline, no dispatch or native writes."""
import argparse
import json
from pathlib import Path
import sys
import apex_foundation_registry as reg
from apex_sdk import FoundationSDK, SAFE_ERRORS

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command",required=True)
    for name in ("doctor","catalog","scenario","drift","debt","reconcile","native-evidence","candidates"):
        sub.add_parser(name)
    plan=sub.add_parser("plan")
    plan.add_argument("repository");plan.add_argument("revision")
    q=sub.add_parser("call")
    q.add_argument("--profile",choices=("reader","planner"),default="reader")
    q.add_argument("capability");q.add_argument("args",nargs="*")
    sub.add_parser("request").add_argument("file",type=Path)
    args=p.parse_args(argv)
    try:
        sdk=FoundationSDK()
        if args.command=="call":
            result=sdk.call(args.capability,args.args,profile=args.profile)
        elif args.command=="request":
            result=sdk.request(reg.read(args.file))
        elif args.command=="plan":
            result=sdk.call("integration.plan",[args.repository,args.revision],profile="planner")
        else:
            mapping={"doctor":"integration.health","catalog":"integration.catalog","scenario":"integration.scenario",
                     "drift":"integration.drift","debt":"integration.debt","reconcile":"integration.reconcile",
                     "native-evidence":"integration.native-evidence","candidates":"integration.candidates"}
            result=sdk.call(mapping[args.command],profile="planner" if args.command=="scenario" else "reader")
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if result["response"]["status"] in ("FAIL","BLOCKED","INCONCLUSIVE") else 0
    except SAFE_ERRORS as exc:
        print(json.dumps({"status":"FAIL","error":str(exc)[:500],"execution_authorized":False}),file=sys.stderr)
        return 2

if __name__=="__main__":
    sys.exit(main())
