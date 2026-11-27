# Architecture Intelligence v0.1.2

A Foundation organiza metadados; não substitui o grafo literal já existente no Engineering Lab nem o analisador privado. A autoridade esportiva de Core 2 e o laboratório Hyper permanecem independentes. A apresentação consome estado sem autoridade esportiva. Nenhum contrato de runtime foi ativado.

## Fontes fixadas
- core2: [Jugadru/APEX-Simulation @ 9dfc18de4908](https://github.com/Jugadru/APEX-Simulation/tree/9dfc18de49083260b1a9524513b415e1551fdabf).
- hyper: [Jugadru/APEX-Hyper-Engine @ 80faba053743](https://github.com/Jugadru/APEX-Hyper-Engine/tree/80faba05374355f31906a630f576036aecca4f56).
- lab: [Jugadru/apex-godot-simulation-architect @ e3494473d7fc](https://github.com/Jugadru/apex-godot-simulation-architect/tree/e3494473d7fc642a0209980802367f4f72dc4a1e).
O Hyper README desta revisão diz que o laboratório longitudinal é o estágio 0, não o Alpha 2 jogável. O Development Lab contém diagnóstico genérico e não deve ter código privado copiado. O índice técnico Core 2 descreve a árvore de responsabilidades e testes existentes. O inventário registra presença de arquivos e blobs Git nas árvores consultadas; a atribuição de módulo é uma política candidata, não análise de imports ou verificação de implementação. Os links privados exigem acesso.

## Comandos
```sh
python3 tools/apex_architecture.py validate
python3 tools/apex_architecture.py stats
python3 tools/apex_architecture.py graph
python3 tools/apex_architecture.py show core2
python3 tools/apex_architecture.py contract-diff
python3 tools/apex_architecture.py impact docs/architecture/change.example.json
python3 tools/apex_architecture.py gate docs/architecture/change.foundation.example.json
```
`graph` usa exclusivamente dependencies do registry e ordena dependências primeiro. `show` apresenta dependências, dependentes, capacidade, papéis e arquivos candidatos. `impact` cruza mudanças explícitas, caminhos mapeados e participantes propostos de contratos; expande dependentes declarados, não imports inferidos. Caminho desconhecido, SHA divergente, contrato adiado ou consumidor externo bloqueiam gate. O gate nunca retorna PASS: um plano local válido é NOT_RUN até evidência real. Exit 0 consulta bem-sucedida (inclusive impact BLOCKED), exit 1 gate/diff bloqueado, exit 2 entrada inválida. Não executa comandos, lê rede, grava arquivos ou autoriza mudanças.

## Contratos e versionamento
ownership.json cobre todos os módulos e contratos. A atribuição de steward/consumers é proposta, não adoção comprovada. Os seis schemas anteriores são preservados e comparados com contract-baseline.json (v0.1.1). Adição de schema é aceita estruturalmente; alteração ou remoção bloqueia a comparação. Isso não é prova de compatibilidade semântica. Uma mudança futura precisa revisão, versão nova e migração do baseline. O SHA de Foundation para manifests é a base da versão (não auto-referência impossível); para consumidores são os snapshots explícitos. Atualizar inventários mediante revisão quando o consumidor avançar.

## Aceite e rollback
Cobertura total de ownership, ausência de ciclos, autoridade exclusiva, caminhos seguros, diff de schemas e impactos fail-closed; testes existentes preservados. CI local apenas, sem FULL esportivo. Reverter PR para rollback. Próxima versão: Data Center com proveniência e contratos de datasets, sem pipeline concorrente.

## Atualização v0.2.0
Baseline de schemas avançado para v0.1.2 (nove schemas preservados). Data Center passa de planejado a experimental, depende da Foundation e tem três novos contratos de metadados. O mapa de impacto reconhece docs/data, data/datasets e ferramentas do Data Center. Inventários externos continuam pinados.
