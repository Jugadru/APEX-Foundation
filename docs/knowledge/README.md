# Knowledge Center v0.1.1 — Research Intelligence

Central offline de inteligência para pesquisa, não mecanismo de adoção automática. Catálogos de 198 REF e 120 IDEA continuam originais. Observações são separadas; nenhuma altera status legado, autoriza código externo ou prova que um sistema existe. A revisão original é preservada via Git. SHA-256 canônico dos registros e fingerprint dos catálogos/política/observações identificam o conteúdo analisado, não autenticam sua verdade.

## Fluxo operacional
```sh
python3 tools/apex_knowledge.py validate
python3 tools/apex_knowledge.py stats
python3 tools/apex_knowledge.py search "curva de torque" --kind idea
python3 tools/apex_knowledge.py search "estratégia" --department strategy
python3 tools/apex_knowledge.py show REF-106
python3 tools/apex_knowledge.py show IDEA-001
python3 tools/apex_knowledge.py duplicates
python3 tools/apex_knowledge.py queue --limit 20
python3 tools/apex_knowledge.py plan IDEA-001
python3 tools/apex_knowledge.py audit --department physics
```

JSON no stdout, erros no stderr (exit 2); exit 0 significa consulta bem-sucedida, não aprovação. Sem rede, subprocessos, downloads ou gravação. Busca com normalização de acentos, termos AND, pontuação explicável e ordenação estável; não é busca semântica. Duplicidades são apenas nomes/URLs normalizados idênticos; nunca fundir automaticamente. A fila ordena prioridades por soma de pesos em policy.json; não mede qualidade nem maturidade. O mapeamento dos sete departamentos é orientação de investigação, não decisão sobre quem implementará Hyper. O plano é sempre BLOCKED até auditoria de consumidor, revisão de fontes/licença, baseline, contratos, testes e decisão do responsável.

## Evidência e limites
observations.json registra quatro leituras de páginas públicas (TUM Race Simulation, Lap Time Simulation, Global Racetrajectory Optimization, Godot Demo Projects). As URLs são referências consultadas, não snapshots imutáveis; revision=null é explícito. Nenhuma licença aprovada, nenhuma dependência importada. Godot Demo Projects informa MIT para demos, mas assets individuais e revisão precisam ser verificados. Os demais registros continuam não verificados. Não confundir observação com execução.

## Evolução e rollback
Não modificar IDs antigos; acrescentar observações com IDs permanentes. O contrato research-observation.v1 é fechado e aceita somente observação de README, licença UNREVIEWED e reutilização BLOCKED. Uma futura auditoria de licença exige contrato e revisão próprios. Validar catálogos, registry e todos os testes no SHA exato; manter CI esportivo no consumidor. Reverter o commit desta versão para rollback. Não muda Core 2, Hyper, Lab, roadmap nem saves.

## Auditoria de consumidores e histórico
`consumer-inventory.json` contém caminhos candidatos identificados na árvore Git de uma revisão exata de APEX-Simulation. A presença do arquivo não prova a existência, qualidade ou integração de um recurso; o status continua NOT_RUN. `audit` reúne as ideias, referências, lacunas e caminhos por departamento. `plan` inclui o SHA e os caminhos para começar a auditoria. `history-lock.json` protege seis arquivos históricos por Git blob SHA; futuras extensões exigem uma migração explícita e revisada do lock, nunca substituição silenciosa. O fingerprint inclui inventário e lock.
