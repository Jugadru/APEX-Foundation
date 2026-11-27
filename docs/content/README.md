# Content Registry v0.2.1

Registro de identidades persistentes, versões exatas, atributos específicos por tipo, dependências, proveniência e direitos. Não é editor de carreira nem banco de conteúdo esportivo. Os 21 registros versionados (20 identidades) são inteiramente fictícios, de teste; os quatro assets são somente metadados, não arquivos. Nenhuma imagem, modelo, áudio ou dado de terceiros foi importado.

## Tipos
driver, staff, team, manufacturer, supplier, circuit, layout, category, championship, season, regulation, vehicle, component, asset. Staff distingue engenheiro, mecânico e estrategista. Relações fechadas e cardinalidades em policy.json; vínculos exigem ID, versão, tipo e temporada. Grafo acíclico, dependências e dependentes transitivos. O veículo de teste aponta a um registro exato no Data Center. Não se aceita latest, promoção, direitos externos ou conteúdo histórico nesta versão. A política de 2012 continua conservadora; atributos e intervalos são fixtures, não regras FIA.

## Uso
```sh
python3 tools/apex_content_registry.py validate
python3 tools/apex_content_registry.py search "piloto fictício" --kind driver
python3 tools/apex_content_registry.py show driver.demo 1.0.0
python3 tools/apex_content_registry.py graph vehicle.demo 1.0.0
python3 tools/apex_content_registry.py diff driver.demo 1.0.0 1.1.0
python3 tools/apex_content_registry.py gate vehicle.demo 1.0.0 core2 9dfc18de49083260b1a9524513b415e1551fdabf
```
Exit 0 consulta ou estrutura válida, 1 gate bloqueado, 2 entrada inválida. Fingerprint e hashes são identificadores de conteúdo, não verificação de verdade. Inventário de cinco caminhos no Core 2 em SHA exato; apenas existência de blobs observada, não extração nem auditoria funcional. Hyper e Core 2 permanecem NOT_RUN para adaptação. Reverter PR para rollback.

## Correções transversais
Data Center: whitelist de tecnologias de 2012 fixada, proibições mínimas não podem ser removidas. Architecture Gate: módulo explicitamente atribuído a outro repositório bloqueia plano; participantes propostos continuam separados. Testes de regressão incluídos. Sem mudanças em engines, Lab ou saves. Próxima etapa: Configuration Management.
