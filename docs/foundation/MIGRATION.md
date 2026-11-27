# Migração da Foundation v0.1.0

Origem: [PR #177](https://github.com/Jugadru/APEX-Simulation/pull/177), SHA `884e6c60b4b3ba8ca06a52850ee8ed097b9f7e18`.
[FAST final da origem](https://github.com/Jugadru/APEX-Simulation/actions/runs/45923094403): PASS, não comprova o novo repositório.
[Relatório original](https://github.com/Jugadru/APEX-Simulation/pull/177#issuecomment-7207385627).

A branch original e seus commits permanecem preservados. Sem merge da PR de origem. AGENTS e CI adaptados; catálogos, schemas e versões preservados. Entrypoints externos são links pinados, registrados com SHA de blob; não se executa código remoto. Workspace de assets continua fora de projetos Git/Godot. Não copiar o jogo ou o Lab privado. Licenças externas não revalidadas.

## Inventário de origem
- `docs/foundation/README.md`: `34488eb1098a0e2de99625ddc69fe95b54969dac`
- `docs/foundation/artifact.example.json`: `ef3c69f1f1de47fbd0b98bded6e1cd19cc4112eb`
- `docs/foundation/registry.json`: `891704fe24571668f00f1af819b14f1e2897b2e2`
- `docs/foundation/schemas.json`: `e25cf74809b914bd623e671fb13dfe6ddca3710a`
- `docs/references/BIBLIOTECA_198.md`: `89d8ceaadae07cacf718cbf9ff8b00ab22047805`
- `docs/references/CATALOGO_120.md`: `7a32429d8b73b3155d0c157470d24f4902b95e24`
- `docs/references/CHANGELOG.md`: `2985be9ebc77fd6bf7dd519e94ba9f12672cb429`
- `docs/references/INFRAESTRUTURA.md`: `745ffbd5d3db33a00fbd5202e131c46113834591`
- `docs/references/PIPELINE_GRAFICO.md`: `fbd936e4169a0ec57dc32dc77a883dd35ad86e2e`
- `docs/references/README.md`: `a33af85b37db7222c0ac750c85e60d32e95af084`
- `docs/references/ROADMAP_HYPER.md`: `1516249c923126c85d462d1131416d4ff54a2ff9`
- `docs/references/asset_jobs.example.json`: `0ff8bfef017abedd71d322063e2092262c817343`
- `docs/references/asset_jobs.original.example.json`: `e1d81e552a3e3bd0d46fb33fd8f51db682770fe0`
- `docs/references/domains.json`: `5d28db6758a36b68912e547f4ac0e2db93cb025e`
- `docs/references/possibilities.json`: `72f40cd5b876bd68c5ab0d0a7df4852d866ae2d9`
- `docs/references/references.json`: `2556dc59594cfede4201c3ccfc56e6892f25d54f`
- `tools/apex_asset_build.py`: `15a60572612f32e36f39ab262f5cbd05d63ac108`
- `tools/apex_blender_scaffold.py`: `e2f80d5d62b08dd816e4817f1b18aa775007d80a`
- `tools/apex_foundation.py`: `93c427307b450125dc4d34c9062b64da034ee735`
- `tools/apex_foundation_registry.py`: `6d9b50e1dad7ca8fe824567fe870b40112a3526f`
- `tools/tests/test_apex_asset_build.py`: `ac1c88e97dfc51b545e631d46e906cd7fac46799`
- `tools/tests/test_apex_foundation.py`: `33f9896ab4e84cbf8f2f9f2fbf6e7be3e21f8e42`
- `tools/tests/test_apex_foundation_registry.py`: `bf63ec7b82a5a58af6e7daddb99b346ed5714ee9`

O CI standalone precisa passar separadamente. Blender real, import GLB e SaveGuard cross-revision permanecem NOT_RUN.
