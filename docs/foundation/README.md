# Foundation v0.1.0 — Shared Contracts & Capability Registry

Candidate; independent version. Source of truth remains AGENTS.md, the existing Lab index, Core 2 and Hyper roadmaps and runtime code. Read [references](../references/README.md), [Lab index](https://github.com/Jugadru/APEX-Simulation/blob/884e6c60b4b3ba8ca06a52850ee8ed097b9f7e18/docs/APEX_LAB_KNOWLEDGE_INDEX.md), [SaveGuard](https://github.com/Jugadru/APEX-Simulation/blob/884e6c60b4b3ba8ca06a52850ee8ed097b9f7e18/docs/APEX_SAVEGUARD_CROSS_VERSION.md). No runtime or game version change.

## Run from repository root (Python 3.10+ target)
```sh
python3 tools/apex_foundation_registry.py validate
python3 tools/apex_foundation_registry.py list
python3 tools/apex_foundation_registry.py search REF-001
python3 tools/apex_foundation_registry.py check artifact.v1 docs/foundation/artifact.example.json
python3 tools/apex_foundation_registry.py compatibility core2 03a73242b21854c22c9e0067f3192847be570de6 godot 4.7.2
python3 -m unittest discover -s tools/tests -p 'test_apex_foundation*.py' -v
python3 -m unittest discover -s tools/tests -p 'test_apex_asset_build.py' -v
```
Exit 0 structural success or recorded compatible pair; 1 incompatible/unknown pair; 2 invalid input. No execution authorization. Capability methods are descriptive, never executed by this CLI. Registry and schemas are trusted repository metadata; external JSON is bounded to 2 MiB, duplicate keys and nonfinite values rejected. No network, subprocess, write, secret or shell evaluation in this CLI. Existing Lab owner authorization and isolated staging remain mandatory. Unknown versions are blocked, not guessed. Compatibility PASS is scoped to the recorded exact pair, not other versions or all subsystems. Version null means unverified. Upstream entrypoints are pinned links validated against an offline manifest of Git blobs inspected at migration. They are never fetched or executed by the CLI.

## Contracts
schemas.json implements a small closed JSON-schema-like dialect (type, enum, pattern via Python fullmatch, minLength, properties, required, additionalProperties=false, items, uniqueItems). It is **not** a general JSON Schema validator. Only registered metadata shapes are active; runtime commands, snapshots, events, telemetry, assets, saves, replays, benchmark/report/job payloads are deferred pending reconciliation with their owners. No runtime event bus, writer or migration engine. artifact.example.json is synthetic, not evidence. Evidence PASS must come from executed tests, not shape validation.

## Architecture and onboarding
registry.json maps module responsibility and dependencies at a coarse level; it is not an exhaustive import graph. Existing version and runtime ownership must be verified before changes. Read AGENTS, then registry, linked source and test evidence; check exact SHA, choose one change, use Foundation CI; consumer changes still require their own FAST, report status and rollback. Search retains REF/IDEA IDs and original records; append new IDs, never recycle. No licenses were revalidated.

## Roadmap (independent, provisional)
0.1.x: catalog provenance, explicit module versions and contract ownership; 0.2: content/data and configuration contracts with historical/fictitious/estimated/scientific origin; 0.3: SaveGuard/replay adapters, evidence registry and migration records; 0.4: modding metadata and scoped permissions. Do not implement runtime features or duplicate current tools. Owner decision: Foundation now lives in Jugadru/APEX-Foundation to avoid conflicts. Keep consumers pinned to reviewed revisions; do not duplicate runtime code.

## Acceptance / rollback
Validate historical IDs and cross-links, schemas and registry, reject invalid inputs and unknown pairs, run legacy Foundation and Asset Factory unit tests and exact-SHA Foundation CI; consumer integrations still require their own exact-SHA FAST. Native Blender/GLB import and cross-revision SaveGuard are not proven by metadata validation. Logs retained by standalone CI. Source PR and original commits preserved for rollback. Source FAST 45920592893 and 45923094403 passed; standalone validation is separate.

## v0.1.1 — Knowledge Center
See [Research Intelligence](../knowledge/README.md). Foundation version 0.1.1 adds a research-observation metadata contract and research-only capabilities. Existing five schemas and compatibility entries remain intact; Python 3.10 exact compatibility is still NOT_RUN. The v0.1.0 section above documents the migrated baseline.

## v0.1.2 — Architecture Intelligence
[Architecture manual](../architecture/README.md): declared graph, ownership, pinned inventory, change impact, contract comparison and fail-closed planning gate. Runtime contracts remain deferred.

## v0.2.0 — Unified Data Center
[Data Center manual](../data/README.md): three metadata contracts, offline dataset integrity, exact unit conversion, version chain and blocked consumer gate. No production data adoption.

## v0.2.1 — Content Registry
[Content manual](../content/README.md): three additive contracts, versioned identities and explicit graph, dataset references and blocked consumer adoption. Previous twelve schemas remain unchanged.

## v0.2.2 — Configuration Management
[Config manual](../config/README.md): typed settings, exact profile inheritance, constraint validation, diff and rollback planning; no runtime adapter. Fifteen previous schemas preserved.
