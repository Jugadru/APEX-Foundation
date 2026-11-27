# Revision Reconciliation v0.5.1

Observed 2026-11-27: compared full, non-truncated Git trees at exact historical pins and current main heads for Core 2, Hyper and Development Lab, plus older Core 2 upstream entrypoints. 85 path/revision pairs (56 Core 2, 13 Hyper, 6 Lab, 10 older Core 2). 75 unchanged, 9 changed, one original baseline mismatch, none missing. This is a blob identity audit, not a line-by-line implementation audit. A changed file needs review, an unchanged file is not automatically compatible. All pins remain unchanged.

SaveGuard pointer tools/tests/test_apex_saveguard_ci.py was transcribed incorrectly in v0.3.0. Correction recorded separately and validated against the original audit observation; no change to actual consumer or revision. The observed historical mismatch is retained even after the inventory correction.

Native evidence: existing Core 2 push FAST, Hyper isolated longitudinal lab and Development Lab Python regressions were observed successful at exact consumer heads. Hyper Game FAST was still running at observation time (INCONCLUSIVE). No new workflow dispatched, no FULL, no native adapter test, no release proof. Core 2 push is not a PR premerge receipt. Native CI entries store scoped excerpts, not signed attestations or actual artifact hashes. Hyper playable game candidates are new tree pointers, not a completed source audit. Existing authorities preserved.

Commands:
```sh
python3 tools/apex.py reconcile
python3 tools/apex.py native-evidence
python3 tools/apex.py candidates
python3 tools/apex.py plan hyper bc8c161878bbef7f1b3dd24a54711c2518736a88
```
Reconciliation validates coverage across all historical inventory sources, recomputes classifications and verifies the recorded correction against the corrected current inventory. Offline report cannot re-query GitHub. Doctor checks reconciliation structure but never grants native readiness. Separate CI tests exact Python 3.10.22, alongside the existing runner interpreter; actual success is recorded in GitHub run, not self-certified by the candidate. Revert PR to roll back. Next: review Core 2 native read-only adapter in its own PR after confirming exact candidate and requirements.
