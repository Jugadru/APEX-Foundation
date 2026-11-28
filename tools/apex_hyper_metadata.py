#!/usr/bin/env python3
"""Independent read-only Hyper longitudinal metadata verifier."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import apex_foundation_registry as registry
# Reuse generic audited Git and bounded-input helpers, not Core 2 rules.
from apex_core2_metadata import git, committed_blob, load_bytes, parse, digest

PATHS = (
    "lab/longitudinal/experimental/hyper22/longitudinal_adapter.gd",
    "lab/longitudinal/experimental/hyper22/longitudinal_primitives.gd",
    "lab/longitudinal/tests/hyper22_longitudinal_adapter_test.gd",
)
MAX_SOURCE = 256 * 1024
MAX_REPORT = 64 * 1024
SHA = re.compile(r"[0-9a-f]{40}\Z")


def declaration(text, key):
    matches = re.findall(r"(?m)^const[ \t]+" + re.escape(key)
                         + r"[ \t]*:=[ \t]*([^\r\n]+)$", text)
    if len(matches) != 1:
        raise ValueError("missing or ambiguous declaration: " + key)
    return matches[0].strip()


def scaled(text, key, factor, integer=False):
    token = declaration(text, key)
    pattern = r"[0-9]{1,6}" if integer else r"[0-9]{1,6}(?:\.[0-9]{1,9})?"
    if not re.fullmatch(pattern, token):
        raise ValueError("unsupported declaration: " + key)
    value = Decimal(token) * factor
    if not 0 < value <= 10**9 or value != value.to_integral_value():
        raise ValueError("non-integral or out-of-range declaration: " + key)
    return int(value)


def project(adapter, primitives):
    token = declaration(adapter, "REVISION")
    if not re.fullmatch(r'"[a-z0-9_]{1,100}"', token):
        raise ValueError("unsupported adapter revision")
    return {
        "adapter_revision": token[1:-1],
        "step_us": scaled(adapter, "STEP_S", 1000000),
        "max_previews": scaled(adapter, "MAX_PREVIEWS", 1, integer=True),
        "rounding_tolerance_um": scaled(adapter, "ROUNDING_TOLERANCE_M", 1000000),
        "max_speed_mps": scaled(primitives, "MAX_MPS", 1),
    }


def validate_report(report, schema, expected_revision):
    if not isinstance(expected_revision, str) or not SHA.fullmatch(expected_revision):
        raise ValueError("expected exact source SHA")
    try:
        registry.check(report, schema)
        body = report["body"]
        if body["revision"] != expected_revision or digest(body) != report["body_sha256"]:
            raise ValueError("report revision or digest mismatch")
    except (TypeError, ArithmeticError) as exc:
        raise ValueError("invalid report value") from exc
    if [s["path"] for s in body["sources"]] != list(PATHS):
        raise ValueError("source coverage or order mismatch")
    if any(not 0 < s["size_bytes"] <= MAX_SOURCE for s in body["sources"]):
        raise ValueError("source size limit")
    for key, value in body["parameters"].items():
        if key != "adapter_revision" and (type(value) is not int or not 0 < value <= 10**9):
            raise ValueError("invalid numeric parameter")
    return body


def verify(report, schema, expected_revision, source_root):
    body = validate_report(report, schema, expected_revision)
    root = Path(source_root).resolve(strict=True)
    top = Path(git(root, "rev-parse", "--show-toplevel").decode("utf-8").strip()).resolve()
    revision = git(root, "rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip()
    if top != root or revision != expected_revision:
        raise ValueError("source checkout is not the exact expected root and SHA")
    texts = []
    for row in body["sources"]:
        local = root / row["path"]
        for ancestor in local.parents:
            if ancestor == root:
                break
            if ancestor.is_symlink():
                raise ValueError("symlink source directory")
        raw = load_bytes(local, MAX_SOURCE)
        blob = committed_blob(root, revision, row["path"])
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        if (blob != actual or blob != row["git_blob"] or len(raw) != row["size_bytes"]
                or hashlib.sha256(raw).hexdigest() != row["sha256"]):
            raise ValueError("source bytes or Git blob differ")
        texts.append(raw.decode("utf-8"))
    if project(texts[0], texts[1]) != body["parameters"]:
        raise ValueError("native declaration projection mismatch")
    return {"status": "PASS", "scope": "exact local laboratory declaration projection only",
            "contract": "hyper-metadata.v1", "revision": revision,
            "body_sha256": report["body_sha256"], "parameters": dict(body["parameters"]),
            "source_bytes_verified": True, "native_runtime_verified": False,
            "sporting_parity_verified": False, "runtime_applied": False,
            "content_imported": False, "execution_authorized": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        _, schemas = registry.load_registry()
        result = verify(parse(load_bytes(args.report, MAX_REPORT)),
                        schemas["hyper-metadata.v1"], args.revision, args.source_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, TypeError, KeyError, OSError, UnicodeError,
            subprocess.SubprocessError, ArithmeticError, RecursionError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)[:250],
                          "execution_authorized": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
