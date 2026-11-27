# Configuration Management v0.2.2

Offline typed configuration metadata. No engine reads these files, no settings are applied, no secrets, environment-variable overrides, command execution or production deployment. All profiles are proposals, including production candidates. Existing engines and their real configuration remain authoritative.

12 settings (integer bounds, enum, boolean), 4 experimental flags, 5 rules, 5 profile identities / 6 versions. Defaults are explicit, inheritance is exact and restricted to same consumer, environment, season and pinned revision; each override reports its source. Resolution order: defaults -> exact parent effective values -> local overrides. No implicit latest or previous inheritance. Manual authority is mandatory; experimental flags are off by default and restricted to Hyper development. Critical prerequisites are enforced in code independently of the declarative rules. These switches do not implement physics or racecraft.

```sh
python3 tools/apex_config.py validate
python3 tools/apex_config.py list
python3 tools/apex_config.py resolve hyper-technical 1.0.0
python3 tools/apex_config.py diff core2-development 1.0.0 1.1.0
python3 tools/apex_config.py rollback core2-development 1.1.0
python3 tools/apex_config.py gate hyper-development 1.0.0 hyper 80faba05374355f31906a630f576036aecca4f56
```
Exit 0 valid query or structural validation; 1 blocked gate or rollback without previous version; 2 invalid input. Rollback is a plan, not a write. Fingerprint of effective configuration includes consumer, exact revision, environment, season and values. Gate always BLOCKED until future reviewed runtime adapter and consumer tests.

Cross-cutting correction: Content Registry rejects repeated logical target identity under the same relation even when two versions are supplied, and caches dependency closure once per graph query instead of recomputing it for each node. Existing content fixtures unchanged. Revert PR for rollback. Next: Persistence & Migration, preserving existing SaveGuard ownership.
