# Artifact & Evidence Center v0.3.1

Offline historical evidence registry. Eight real GitHub CI observations were re-read from run metadata, successful job steps and exact log excerpts on 2026-11-27 (seven PR runs and v0.3.0 main). Receipt timestamps are source run updated_at, not local collection time. Test counts and Python 3.14.4 are copied from the logs. No full log, ZIP hash or artifact download is claimed. The stored receipts are not signed attestations, cannot be refreshed offline and do not prove current status. Links need private repository access. Historical times are not simulation benchmarks.

Existing artifact.v1 is reused inside a fixture record. One local three-byte synthetic fixture verifies SHA256 and length, not execution. Three synthetic benchmark observations exercise matched-context median comparison; incompatible environment/harness/workload/metric blocks. Positive delta means slower duration; no real performance regression claim. Two notes record a prior decision and observed regression. No consumer code, screenshots, binary builds, saves or external assets are imported. Existing Labs remain authoritative.

```sh
python3 tools/apex_evidence.py validate
python3 tools/apex_evidence.py history
python3 tools/apex_evidence.py show v0.3.0-main
python3 tools/apex_evidence.py verify fixture.bytes
python3 tools/apex_evidence.py compare demo.baseline demo.candidate
python3 tools/apex_evidence.py notes
python3 tools/apex_evidence.py gate 47f18184ece6473242b56c695e06512f5ef769d6
```

Gate always BLOCKED, including exact historical matches; stale/unknown SHA has no matching receipt. No network, dispatch, automatic adoption, release authorization or artifact promotion. Exit 0 valid query, 1 blocked or failed integrity, 2 invalid input. Fingerprints identify stored records, not truth or authenticity. CI logs retained 14 days; minimal historical excerpts survive expiration in Git. Native FAST, Godot, GPU, SaveGuard, benchmark and graphics evidence remain distinct.

Regression: persistence recovery rejects a primary from the wrong consumer scope, checks caller-provided expected hashes against the registered original and uses registered generations when filtering future backups. This protects synthetic scenarios, not live saves. Rollback: revert PR. Next: Modding Infrastructure.

## Python 3.10 compatibility correction (v0.5.1)
GitHub log timestamps can contain seven fractional digits. Python 3.10 datetime.fromisoformat rejected the original values in CI run 46069436994. Parse whole UTC seconds and compare exact fractional seconds separately (1–18 ASCII digits, no truncation); retain original text and hashes. History uses the same ordering key. Four regression tests cover precision, invalid timestamps, reversed submicrosecond markers and mixed-precision history ordering.

Second candidate 0fb212722d7546a5ae876a53d5d2ab7fa54aa1c7 passed 139 tests on 3.10.22, but Python 3.14.4 normalized hour 24 rather than rejecting it. Replace ISO whole-second parsing with explicit datetime constructor fields and UTC timezone; retain all rejection assertions and add invalid minute/hour/year cases. [CI evidence](https://github.com/Jugadru/APEX-Foundation/actions/runs/46070290387).
