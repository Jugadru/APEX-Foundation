# Modding Infrastructure v0.4.0

Experimental data-only mod registry. Six identities / seven versions, six exact dependency edges, seven preview labels. All are original synthetic fixtures. Only permission content.label.preview is accepted. No native mod loader, installation, filesystem overlays, script execution, assets, archives with arbitrary members, save mutations or runtime configuration. Content Registry is read-only; preview labels are returned in JSON only. Production and third-party content remain blocked.

Exact version dependency graph, dependency-first deterministic order, missing dependencies, cycles, version conflicts, explicit conflicts, overlapping logical content targets, scope and era validation. No silent last-writer-wins. Removal and rollback return candidate selections, not operations; implicit dependencies still required cannot be removed. Consumer revisions are pinned; native tests NOT_RUN.

ZIP inspection accepts only a bounded single regular manifest.json member, stored/deflated, no encryption, path traversal, duplicate members, symlinks, excessive uncompressed size or ratio; no extraction. JSON rejects duplicate keys; manifest must equal an already registered synthetic fixture. Package command constructs a deterministic fixture ZIP in memory and inspects it; inspect-zip accepts an explicitly supplied local regular ZIP file. This is a narrow parser, not an OS sandbox or proof arbitrary third-party packages are safe. No code is run from the package.

```sh
python3 tools/apex_modding.py validate
python3 tools/apex_modding.py plan docs/modding/selection.example.json
python3 tools/apex_modding.py package demo.driver 1.0.0
python3 tools/apex_modding.py inspect-zip /path/to/fixture.zip
python3 tools/apex_modding.py remove docs/modding/selection.example.json demo.season
python3 tools/apex_modding.py gate docs/modding/selection.example.json
```
Exit 0 valid query/fixture check, 1 blocked plan or gate, 2 invalid input. Gate always BLOCKED. Rollback PR via revert. Registry dependency validation now uses iterative traversal, avoiding recursion and repeated shared-edge visits. Next: Foundation Ecosystem Integration; native adapters remain separate reviewed work.
