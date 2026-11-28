#!/usr/bin/env python3
"""Offline verification of existing native producer artifacts, without extraction.

A caller-supplied receipt is not an authenticated GitHub statement. A PASS
means consistency of local bytes, receipt, and embedded scoped evidence only.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import sys
import zipfile
import zlib

import apex_foundation_registry as registry
from apex_core2_metadata import load_bytes, parse, canonical
import apex_hyper_metadata as hyper

MAX_ZIP = 2 * 1024 * 1024
MAX_ENTRY = 1024 * 1024
MAX_RECEIPT = 16 * 1024
NAMES = ("hyper-metadata.json", "hyper-fast.log")


def verify(receipt, archive_path, revision, schemas):
    registry.check(receipt, schemas["native-artifact-receipt.v1"])
    if not isinstance(revision, str) or not hyper.SHA.fullmatch(revision) or revision != receipt["revision"]:
        raise ValueError("expected exact matching revision")
    for field, maximum in (("run_id", 10**16), ("attempt", 1000), ("artifact_id", 10**16),
                           ("size_bytes", MAX_ZIP), ("native_checks", 100000)):
        if not 0 < receipt[field] <= maximum:
            raise ValueError("invalid receipt bound: " + field)
    raw = load_bytes(Path(archive_path), MAX_ZIP)
    if len(raw) != receipt["size_bytes"] or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
        raise ValueError("archive size or SHA-256 mismatch")
    values = {}
    with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
        entries = archive.infolist()
        if len(entries) != len(NAMES) or {x.filename for x in entries} != set(NAMES):
            raise ValueError("unexpected, missing or duplicate archive members")
        if sum(x.file_size for x in entries) > 2 * MAX_ENTRY:
            raise ValueError("uncompressed total exceeds bound")
        for info in entries:
            mode = stat.S_IFMT(info.external_attr >> 16)
            if (info.orig_filename != info.filename or info.is_dir()
                    or mode not in (0, stat.S_IFREG) or info.flag_bits & 1
                    or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                    or not 0 < info.file_size <= MAX_ENTRY
                    or not 0 < info.compress_size <= MAX_ZIP):
                raise ValueError("unsupported archive member")
            with archive.open(info, "r") as member:
                data = member.read(MAX_ENTRY + 1)
            if len(data) != info.file_size or len(data) > MAX_ENTRY:
                raise ValueError("archive member size mismatch")
            # Reading to EOF validates CRC via zipfile; explicit check is redundant
            # by design and documents the expected digest semantics.
            if zlib.crc32(data) & 0xffffffff != info.CRC:
                raise ValueError("archive CRC mismatch")
            values[info.filename] = data
    report = parse(values["hyper-metadata.json"])
    body = hyper.validate_report(report, schemas["hyper-metadata.v1"], revision)
    if report["body_sha256"] != receipt["body_sha256"]:
        raise ValueError("receipt body digest mismatch")
    lines = values["hyper-fast.log"].decode("utf-8").splitlines()
    passes = [x for x in lines if re.fullmatch(r"HYPER22_LONGITUDINAL_PASS checks=[1-9][0-9]*", x)]
    native = [x.removeprefix("HYPER_METADATA_NATIVE ") for x in lines if x.startswith("HYPER_METADATA_NATIVE ")]
    if (passes != [f'HYPER22_LONGITUDINAL_PASS checks={receipt["native_checks"]}']
            or len(native) != 1 or any(re.search(r"SCRIPT ERROR:|Parse Error:|^ERROR:|^HYPER22_FAIL", x) for x in lines)):
        raise ValueError("missing or inconsistent native log evidence")
    if canonical(parse(native[0].encode("utf-8"))) != canonical(body["parameters"]):
        raise ValueError("native parameter evidence mismatch")
    return {"status": "PASS", "scope": "local archive and embedded Hyper laboratory evidence consistency only",
            "revision": revision, "repository": receipt["repository"], "run_id": receipt["run_id"],
            "attempt": receipt["attempt"], "artifact_id": receipt["artifact_id"],
            "archive_sha256": receipt["sha256"], "body_sha256": report["body_sha256"],
            "archive_bytes_verified": True, "crc_verified": True,
            "native_marker_checks": receipt["native_checks"],
            "receipt_authenticity_verified": False, "live_attestation": False,
            "source_checkout_verified": False, "native_runtime_executed": False,
            "sporting_parity_verified": False, "execution_authorized": False,
            "release_authorized": False}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("receipt", type=Path)
    p.add_argument("archive", type=Path)
    p.add_argument("--revision", required=True)
    args = p.parse_args(argv)
    try:
        _, schemas = registry.load_registry()
        result = verify(parse(load_bytes(args.receipt, MAX_RECEIPT)), args.archive, args.revision, schemas)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, TypeError, KeyError, OSError, UnicodeError, ArithmeticError,
            RecursionError, RuntimeError, zipfile.BadZipFile, NotImplementedError, zlib.error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)[:250],
                          "execution_authorized": False, "release_authorized": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
