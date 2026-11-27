# AGENTS — APEX Foundation

Escopo exclusivo: infraestrutura compartilhada, referências, contratos, manifestos, compatibilidade, evidências e ferramentas opt-in. Não alterar motor, física, saves, replays, HUD ou scripts do jogo a partir deste repo. Preservar IDs históricos e roadmaps; uma funcionalidade principal por versão; não duplicar ferramentas existentes.

Leia [README](README.md), [contratos](docs/foundation/README.md), [biblioteca](docs/references/README.md), [arquitetura](docs/references/INFRAESTRUTURA.md) e [migração](docs/foundation/MIGRATION.md). Regras esportivas e FAST continuam sob [AGENTS do APEX-Simulation](https://github.com/Jugadru/APEX-Simulation/blob/884e6c60b4b3ba8ca06a52850ee8ed097b9f7e18/AGENTS.md); não exigir FULL sem autorização. Não executar código de PR não revisado em runner pessoal. Não solicitar tokens ou secrets no chat. Não promover assets automaticamente; licenças devem ser verificadas. Métodos cadastrados não autorizam execução.

Antes de integrar: validar catálogos e registry, rodar todos os testes Python, verificar CI no SHA exato, documentar PASS/FAIL/NOT_RUN/INCONCLUSIVE/BLOCKED, manter rollback. Testes do jogo e do Lab pertencem aos respectivos repositórios; mudanças de integração requerem validação no consumidor. CI Foundation não comprova simulação, GPU, Blender ou saves. O responsável autorizou a evolução ampla da Foundation. Manter mudanças coesas por versão, com testes independentes e sem autorização implícita para alterar consumidores. Pesquisa documental não equivale a licença nem autorização de implementação.

Para mudanças arquiteturais, consultar [Architecture Intelligence](docs/architecture/README.md), executar impact/gate com base exata e encaminhar validação ao consumidor. Gate não autoriza execução nem substitui o grafo literal do Lab.

Para datasets, consultar [Data Center](docs/data/README.md); preservar origem, revisão, unidades, política temporal e hash. Fixtures não são dados históricos. Nunca promover automaticamente para runtime.

Para conteúdo, consultar [Content Registry](docs/content/README.md). Usar identidades e versões exatas, relações fechadas e direitos explícitos. Fixtures não são conteúdo jogável; assets metadata-only não são arquivos reais.

Para configurações, consultar [Configuration Management](docs/config/README.md). Usar versões exatas, separar ambientes e consumidores, preservar prioridade manual; nenhum perfil autoriza aplicação em runtime.
