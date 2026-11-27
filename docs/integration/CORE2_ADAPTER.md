# Core 2 read-only metadata adapter (Foundation v0.6.0)

Two reviewed components: public Core 2 producer and private Foundation verifier. Producer reads two exact HEAD data blobs; receiver validates a closed contract, checks body SHA256 and verifies the explicit source checkout's exact commit, Git blob identity, byte size, SHA256 and every projected name/index/slot/code/country/lap count. No source code is executed by the receiver. No automatic import into Content Registry, runtime mutations, saves, geometry, ratings, assets, telemetry, network calls or license grant. Source positions are revision-scoped and must not be used as persistent cross-version IDs.

```sh
# In exact Core 2 checkout:
python3 tools/apex_foundation_metadata.py > /tmp/core2-metadata.json
# In Foundation:
python3 tools/apex_core2_metadata.py /tmp/core2-metadata.json --revision <exact-sha> --source-root <core2-checkout>
python3 tools/apex.py call integration.core2-contract
```

Explicit local file and checkout inputs are confined to the standalone verifier, not exposed through the gateway. PASS means only exact local source projection; it is not a native runtime check or a release authorization. The consumer FAST verifies native loader parity separately. A synthetically generated repository exercises negative cases without importing real historical data into Foundation. No historical pins changed. Native evidence and cross-repository CI recorded separately when actually available.

## Corrective review: Git identity
The receiver ignores inherited GIT_* overrides, disables replacement refs and network transports, and requires regular-file Git tree entries for both exact source paths. The explicit local checkout must be trusted; this is not an OS sandbox or authentication of arbitrary repositories. If objects are missing, verification fails rather than downloading them. Four added regressions cover environment redirection, replacement refs, committed symlinks and malformed decimal report values. Existing checks remain mandatory.
