# APEX Foundation v0.2.0

Unified Data Center + Architecture Intelligence + Knowledge Center + Shared Contracts & Capability Registry — infraestrutura compartilhada do ecossistema APEX, independente do motor esportivo.

[Contratos e comandos](docs/foundation/README.md) · [Biblioteca de referências](docs/references/README.md) · [Migração e evidências](docs/foundation/MIGRATION.md) · [AGENTS.md](AGENTS.md)

- [198 referências](docs/references/BIBLIOTECA_198.md) e [120 possibilidades](docs/references/CATALOGO_120.md), IDs preservados.
- [Registro de módulos, capacidades e compatibilidade](docs/foundation/registry.json).
- [Schemas](docs/foundation/schemas.json) e [Asset Factory](docs/references/PIPELINE_GRAFICO.md).
- [Roadmap Hyper](docs/references/ROADMAP_HYPER.md) — independente do Core 2.

## Repositórios consumidores
- [APEX-Simulation](https://github.com/Jugadru/APEX-Simulation): jogo, Core 2 e Labs existentes.
- [APEX-Hyper-Engine](https://github.com/Jugadru/APEX-Hyper-Engine): motor experimental.
- Development Lab: Jugadru/apex-godot-simulation-architect (acesso autorizado).

## Validação (Python 3.10+)
```sh
python3 tools/apex_foundation_registry.py validate
python3 -m unittest discover -s tools/tests -p 'test_*.py' -v
```

Foundation CI é independente; não substitui FAST esportivo. Sem promoção de assets nem execução automática de capacidades. Origem: PR #177; versão preservada.

## Knowledge Center v0.1.1
[Manual de pesquisa](docs/knowledge/README.md) · [Observações verificadas em páginas públicas](docs/knowledge/observations.json) · [Política](docs/knowledge/policy.json).

## Architecture Intelligence v0.1.2
[Manual de arquitetura](docs/architecture/README.md) · [Responsabilidades](docs/architecture/ownership.json) · [Inventário de fontes](docs/architecture/source-inventory.json).

## Unified Data Center v0.2.0
[Manual](docs/data/README.md) · [Catálogo](docs/data/catalog.json) · [Unidades](docs/data/units.json) · [Matriz de consumidores](docs/data/consumer-matrix.json). Somente fixtures sintéticos; nenhuma adoção esportiva.
