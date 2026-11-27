# Persistence & Migration v0.3.0

Offline synthetic migration laboratory, not a native save reader/writer. No file paths accepted by the CLI; it only reads fixed repository fixture definitions and emits JSON. No personal saves, backup files, game directories, automatic restore, native binary parsing or runtime migration. Native save/replay contracts remain deferred.

Three synthetic formats, two allowlisted migrations, four fixtures (including deliberate corruption). Envelopes are constructed in memory from fixture definitions; expected hashes are computed before deliberate corruption, not independently authenticated historical evidence. The payload SHA256 and expected full-envelope SHA256 serve distinct checks. Semantic invariants preserve round, points and integer budget; no claim about actual game fields, format or financial units. Migration returns a new in-memory copy, never modifies the source. Downgrades blocked. Recovery lists valid backup candidates by generation after explicit expected-hash and scope checks; never restores automatically. A valid primary takes precedence. A newer backup generation is excluded. No valid backup blocks.

## Existing SaveGuard
[Source documentation](https://github.com/Jugadru/APEX-Simulation/blob/9dfc18de49083260b1a9524513b415e1551fdabf/docs/APEX_SAVEGUARD_CROSS_VERSION.md) confirms native Godot cross-revision checks for career, garage and replay, isolated HOME/XDG, baseline SHA256 preservation, manual recovery only. The current garage .bak is not restored automatically. Foundation does not replace or launch that workflow. Eight pinned source pointers are recorded; actual native validation remains NOT_RUN. Do not expose save data in CI artifacts.

## Commands
```sh
python3 tools/apex_persistence.py validate
python3 tools/apex_persistence.py inspect career-baseline
python3 tools/apex_persistence.py plan career-baseline 3.0.0
python3 tools/apex_persistence.py simulate career-baseline 3.0.0
python3 tools/apex_persistence.py recover corrupt-primary
python3 tools/apex_persistence.py gate career-baseline core2 9dfc18de49083260b1a9524513b415e1551fdabf
```
Exit 0 successful query or synthetic check, 1 expected block/corruption, 2 malformed or unknown input. PASS in simulate refers only to synthetic in-memory migration. Real save adoption always blocked. Revert PR to roll back Foundation only. Next: Artifact & Evidence Center.

Regression: strategy preview and technical realism require telemetry even if declarative config constraints are removed.
