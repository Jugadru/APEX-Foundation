# Unified Data Center v0.2.0

Central offline de datasets versionados, proveniência, unidades, integridade e planejamento de consumo. Não é banco de dados de runtime, importador de telemetria, simulador, pipeline paralelo de saves ou autorização de promoção.

## Dados iniciais
Dois datasets de teste, três versões, sete registros contados entre versões. Todos os valores são originais e inventados, não representam carros reais, telemetria histórica, ciência validada ou calibração. `vehicle-fixture` tem versões 1.0.0 e 1.1.0; `strategy-fixture` tem 1.0.0. Os contratos distinguem historical, fictional, estimated, scientific, calibrated e synthetic. Os cinco primeiros exigem referência, URL, revisão de fonte e uso RESEARCH_ONLY; nenhum recebe aprovação de licença ou produção. A classificação é declarada, não verificação de verdade. Não há importador externo nesta versão.

## Comandos
```sh
python3 tools/apex_data_center.py validate
python3 tools/apex_data_center.py list
python3 tools/apex_data_center.py show vehicle-fixture 1.1.0
python3 tools/apex_data_center.py query vehicle-fixture 1.1.0 --record fixture-a
python3 tools/apex_data_center.py diff vehicle-fixture 1.0.0 1.1.0
python3 tools/apex_data_center.py convert 180 kmh mps
python3 tools/apex_data_center.py gate vehicle-fixture 1.1.0 core2 9dfc18de49083260b1a9524513b415e1551fdabf
```
Exit 0 consulta/validação estrutural, 1 gate bloqueado, 2 entrada inválida. Conversão exata por frações, sem arredondamento oculto, com unidade e dimensão. Dez unidades cobrem massa, potência, velocidade, tempo e razão. Os payloads usam inteiros com unidade explícita no manifesto, sem conversão automática. Limite 2 MiB e 10 mil registros por versão. Git blob identifica bytes e SHA-256 é relatado; isso não autentica a veracidade. IDs únicos, contagem, caminho seguro, ausência de symlink, campos fechados e intervalos declarados. Versões exatas e cadeia linear; mudança de campos exige major novo. Diff não garante compatibilidade semântica.

## Política de 2012
A política conservadora deriva de [arquitetura APEX](../references/INFRAESTRUTURA.md): V8, KERS, DRS, sem cost cap moderno. Tecnologias não listadas são bloqueadas por padrão; não é regulamento FIA completo. Os intervalos numéricos são limites de fixtures, não especificações históricas. Ano e tecnologia não comprovam autenticidade.

## Integração
Matriz de seis pares dataset/versão × consumidor com SHA exato; NOT_RUN. Gate sempre BLOCKED até existir uma etapa de aprovação independente; não executa testes nem autoriza consumo. Core 2 e Hyper não foram alterados. A arquitetura integra Data Center como autoridade de metadados, jamais estado esportivo. CI testa e retém relatórios, incluindo gate negativo esperado. Reverter PR para rollback. Próxima versão: Content Registry.
