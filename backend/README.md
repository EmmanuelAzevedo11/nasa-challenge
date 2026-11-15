# AgroSat SP · Backend

API FastAPI para consultar dados agroambientais, planejar plantio e rotação de culturas e conversar com o AgroSat IA em São Paulo. A API recebe coordenadas WGS84 em graus decimais e usa a malha oficial do IBGE para validar o ponto e identificar o município quando houver uma única correspondência. Open-Meteo e NASA POWER são consultados de forma assíncrona via HTTPX, com cache em memória.

## Executar

O projeto usa Python 3.12 ou superior. Execute os comandos na pasta `backend`.

```bash
python3.12 -m venv .venv  # apenas se o ambiente ainda não existir
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env  # cria o arquivo se necessário e preserva o .env existente
python -m uvicorn app.main:app --reload
```

Com o servidor em execução, abra o [Swagger](https://nasa-challenge-nvrf.onrender.com/docs). No React, a URL-base de desenvolvimento é `https://nasa-challenge-nvrf.onrender.com`. A interface de mapa usa React-Leaflet no frontend e envia os campos `latitude` e `longitude` para a API.

### Ambiente

- `FRONTEND_ORIGINS` contém as origens CORS como lista separada por vírgulas. Informe as origens exatas do frontend em produção, incluindo a URL do Lovable se for consumir a API.
- `HTTP_TIMEOUT_SECONDS` e `HTTP_RETRIES` configuram o timeout e o número de novas tentativas em falhas transitórias. Erros de autenticação, parâmetros e limite de requisições encerram a consulta ao provedor.
- `CACHE_TTL_SECONDS` controla o cache da previsão e `CLIMATE_CACHE_TTL_SECONDS` controla o histórico. Os valores padrão são 15 minutos e 6 horas, respectivamente. `CACHE_MAX_ENTRIES` limita o cache por processo.
- `NASA_POWER_BASE_URL` e `OPEN_METEO_BASE_URL` apontam para os serviços oficiais.
- `GEMINI_API_KEY` habilita o AgroSat IA. Credenciais locais ficam no `.env`, ignorado pelo Git. `GEMINI_MODEL` tem como padrão `gemini-3.1-flash-lite`. `GEMINI_TIMEOUT_SECONDS` limita cada interação e `GEMINI_MAX_REQUESTS_PER_MINUTE` configura o limite local por cliente, por processo.

## Endpoints

| Método | Caminho | Resultado |
|---|---|---|
| GET | `/health` | Status de execução da API |
| GET | `/api/v1/regions/summary` | Município, estimativas atuais e 30 dias de histórico solicitado |
| GET | `/api/v1/weather/forecast` | Estimativas atuais e previsão diária. `days` aceita 1 a 16, incluindo hoje, e tem padrão 7 |
| GET | `/api/v1/climate/history` | Histórico diário. `days` aceita 30, 90, 180 ou 365 e tem padrão 30 |
| GET | `/api/v1/climate/series` | Séries diárias, mensais ou anuais com filtros de mês e até cinco anos de dados |
| GET | `/api/v1/crops` | Catálogo agronômico com referências |
| GET | `/api/v1/crops/zarc?season_start_year=2026` | Safras locais, municípios e culturas/modalidades da safra selecionada |
| POST | `/api/v1/crops/suitability` | Avaliação regional de alternativas de plantio por período e cenário |
| POST | `/api/v1/crops/rotation` | Até três estratégias para o próximo plantio |
| POST | `/api/v1/ai/chat` | Assistente Gemini com ferramentas do backend |
| GET | `/api/v1/terrain` | Altitude do SRTM em metros |
| GET | `/api/v1/soil` | Propriedades estimadas do solo na camada de 0 a 5 cm |
| GET | `/api/v1/risks` | Triagem de riscos nos próximos `days` de 1 a 7 |

```bash
curl 'https://nasa-challenge-nvrf.onrender.com/health'
curl 'https://nasa-challenge-nvrf.onrender.com/api/v1/regions/summary?latitude=-23.5886&longitude=-48.0483'
curl 'https://nasa-challenge-nvrf.onrender.com/api/v1/weather/forecast?latitude=-23.5886&longitude=-48.0483&days=7'
curl 'https://nasa-challenge-nvrf.onrender.com/api/v1/climate/history?latitude=-23.5886&longitude=-48.0483&days=90'
```

Coordenadas fora da malha estadual e parâmetros inválidos retornam HTTP 422, com `detail.code` e `detail.message`. Consultas válidas retornam HTTP 200 e um status de dados como `available`, `partial`, `insufficient_data` ou `provider_error`. No resumo, cada fonte mantém seu próprio status e valores ausentes são representados por `null`.

## Fontes e interpretação

- **NASA POWER.** Série diária da comunidade AG em horário solar local (LST). A janela solicitada termina ontem no calendário de São Paulo. A API mantém lacunas internas como valores nulos, descarta os dias sem publicação no fim da série e informa a última data com dados em `last_available_date`. As unidades por variável estão em `metrics`. A resolução nominal acima indicada na resposta refere-se à grade meteorológica da fonte. [API diária](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) · [Resolução e disponibilidade](https://power.larc.nasa.gov/docs/tutorials/).
- **Open-Meteo.** Condições atuais estimadas por modelos e previsão diária em `America/Sao_Paulo`. A resposta informa o intervalo de acumulação da precipitação atual quando disponibilizado. A umidade do solo é volumétrica (m³/m³), nas camadas de 0–1, 1–3 e 3–9 cm quando disponíveis. As unidades das séries diárias ficam em `daily_metrics`. [Documentação de previsão](https://open-meteo.com/en/docs).
- **IBGE.** A malha estadual e a municipal de São Paulo foram baixadas em 14/11/2026 com qualidade máxima na API de malhas simplificadas. O arquivo estadual foi preservado em GeoJSON. O arquivo municipal reúne 645 geometrias, com os nomes cruzados com os códigos da API de Localidades, e está compactado em gzip. A identificação municipal requer um ponto no interior de um único polígono. Um ponto sobre uma divisa ou sem correspondência única recebe município e código nulos. [API de Malhas](https://servicodados.ibge.gov.br/api/docs/malhas?versao=4) · [Municípios de SP](https://servicodados.ibge.gov.br/api/v1/localidades/estados/35/municipios).

As fontes em grade descrevem condições regionais. Para decisões agronômicas em uma propriedade, é necessário verificar as condições locais e consultar um profissional habilitado quando apropriado.

## Estrutura e testes

`app/core` contém configurações, cliente e cache. `app/api` contém os endpoints. `app/services` integra os provedores. `app/schemas` define os contratos. `app/data` e `app/utils/geo.py` permitem a validação geográfica local. `tests` verifica contratos, coordenadas, normalização, falhas e cache com provedores simulados.

```bash
python -m pytest -q
```

## Séries climáticas para gráficos

A rota `/api/v1/climate/series` aceita `latitude`, `longitude`, `start_year`, `end_year`, `month`, `metric` e `group_by`. Sem filtro de anos, a janela cobre cinco anos-calendário, incluindo o atual. O intervalo informado aceita até cinco anos inclusivos. A consulta dos dias do ano corrente termina em ontem.

```bash
curl 'https://nasa-challenge-nvrf.onrender.com/api/v1/climate/series?latitude=-23.5886&longitude=-48.0483&start_year=2022&end_year=2026&month=5&group_by=year&metric=precipitation'
```

Use `group_by=year` para comparar o mesmo mês entre anos, `group_by=month` para totais ou médias mensais e `group_by=day` para valores por dia. Repita `month=5&month=6` ou `metric=precipitation&metric=temperature` para selecionar mais opções. O padrão é chuva agrupada por mês. As demais métricas são `temperature`, `temperature_min`, `temperature_max`, `relative_humidity` e `wind_speed`.

Cada série retorna `period`, `unit` e valores prontos para o gráfico. A precipitação é somada em milímetros. Temperaturas mínimas e máximas usam os extremos das mínimas e máximas diárias, e temperatura média, umidade relativa e vento usam a média dos valores diários. Para um agrupamento anual com meses selecionados, somente os dias desses meses entram no cálculo.

`days_available` e `days_expected` indicam a cobertura de cada ponto. Quando faltar qualquer dia, `value` fica nulo e `partial_value` traz o cálculo dos dias disponíveis, se houver. Um mês em andamento segue essa mesma regra. Meses que ainda não começaram ficam fora da resposta mensal. Os filtros e as agregações usam o cache do mesmo intervalo consultado na NASA POWER.

## Planejamento agrícola

A avaliação usa as coordenadas para identificar o município pelo IBGE. Envie o mês e o ano civil do plantio. Sem um `planting_day`, o endpoint consulta os três decêndios do mês. Com o dia, consulta o decêndio correspondente.

```bash
curl 'https://nasa-challenge-nvrf.onrender.com/api/v1/crops'
curl 'https://nasa-challenge-nvrf.onrender.com/api/v1/crops/zarc?season_start_year=2026'
curl 'https://nasa-challenge-nvrf.onrender.com/api/v1/crops/suitability' \
  -H 'Content-Type: application/json' \
  -d '{
    "location": {"latitude": -23.5886, "longitude": -48.0483},
    "planting_month": 10,
    "planting_year": 2026
  }'
```

`season_start_year` é opcional. A convenção padrão da API associa julho a dezembro ao primeiro ano da safra e janeiro a junho ao segundo. Para selecionar a safra declarada em uma portaria, informe o ano inicial explicitamente. Uma safra ausente retorna `season_unavailable` e os indicadores históricos que estiverem disponíveis.

`zarc_conditions` aceita `soil_code`, `cultivar_group_code`, `management_code`, `climate_code`, `management_level_code` e `productivity`. Use os códigos oficiais da Tábua de Risco. Os cenários retornados registram as condições de solo, grupo, manejo, clima aplicável e outras dimensões presentes. Por exemplo, `{"soil_code": 14, "cultivar_group_code": 20, "management_code": 1}` filtra a combinação AD4, Grupo I e sequeiro. O campo `missing_conditions` lista as condições do cenário que ainda precisam ser informadas. [Dicionário de dados do MAPA](https://dados.agricultura.gov.br/dataset/tabua-de-risco-zoneamento-agricola-de-risco-climatico/resource/bebb0ebb-bc75-460c-b900-a7a1ebd87bee).

### Metodologia

- O ZARC é consultado pela safra selecionada, geocódigo IBGE, cultura ou modalidade e condições informadas. O nível oficial de risco é preservado por decêndio. Códigos 20, 30 e 40 representam percentuais de risco climático do registro. O código 0 indica ausência de janela na combinação, e valores ausentes ou desconhecidos geram `unknown`. [Painel de Indicação de Riscos](https://mapa-indicadores.agricultura.gov.br/publico/extensions/Zarc/Zarc.html).
- A NASA POWER fornece a temperatura média do ar e a precipitação acumulada do mês homólogo mais recente que tenha terminado antes do mês do plantio e da data da consulta. Cada cálculo exige a série diária completa e unidade compatível. O recorte descreve um único mês histórico.
- Quando a variável e a unidade são compatíveis, o histórico é comparado com a referência do catálogo. A faixa de 20 a 30 °C para desenvolvimento da soja é usada como contexto térmico. Culturas com referências em outra escala ficam com contexto qualitativo. A chuva acumulada no mês descreve a precipitação recebida nesse recorte. O suprimento de água no ciclo depende de balanço hídrico e condições locais. [Tecnologias de produção de soja — Embrapa](https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/1123928/1/SP-17-2020-online-1.pdf).
- `potentially_favorable` exige janela com risco de 20% em todos os cenários e decêndios consultados, condições preenchidas, histórico mensal completo e ausência de restrição térmica detectada. `restricted` indica pelo menos uma janela com condicionantes. `unfavorable` descreve ausência explícita de janela em todos os registros filtrados. `insufficient_data` indica falta de registros aplicáveis ou dados oficiais inconclusivos.
- Consulte a portaria para validar cultivar, modalidade, restrições sanitárias e demais condições oficiais. As avaliações são orientativas e regionais. Para decisões de manejo, considere análise local do solo e orientação profissional.

### Base local e atualização

O backend inclui dois recortes estaduais de CSVs do MAPA de 13/11/2026, sob licença Creative Commons Attribution.

- `app/data/zarc/2026-2027.csv.gz` reúne 163.005 registros da safra 2026/2027 em 645 municípios. [Tábua de risco da safra 2026/2027](https://dados.agricultura.gov.br/dataset/tabua-de-risco-zoneamento-agricola-de-risco-climatico/resource/139e5a60-1f43-4cc8-aeab-a35dbbf816c0).
- `app/data/zarc/sem-safra.csv.gz` reúne 369.418 registros paulistas da tábua de perenes, olerícolas e culturas sem safra. A cana-de-açúcar tem 7.079 registros, distribuídos pelas modalidades de sequeiro das portarias 4 e 5 de 2026. [Tábua de risco sem safra](https://dados.agricultura.gov.br/dataset/tabua-de-risco-zoneamento-agricola-de-risco-climatico/resource/dae65d31-683f-4ac4-ab90-3abd0c1583ba).

O importador valida os registros e prepara índices SQLite locais em `app/data/zarc/.index/`. A API reusa os índices persistidos e consulta pelo município e pela cultura. Ela gera os índices quando ausentes ou desatualizados. A pasta dos dados precisa aceitar gravação para criá-los. Uma cultura nova pode reutilizar os registros importados ao receber no catálogo os nomes oficiais das modalidades e, quando aplicável, `zarc_without_season: true`.

Para atualizar, baixe a publicação e execute o importador na pasta `backend`.

```bash
.venv/bin/python -m app.services.zarc ~/Downloads/dados-abertos-tabua-de-risco-safra-2026-2027.csv --safra-inicio 2026
.venv/bin/python -m app.services.zarc ~/Downloads/dados-abertos-tabua-de-risco-safra-perene-olericola-sem-safra.csv --sem-safra
```

`ZARC_DATA_DIR` configura o diretório dos recortes. Reinicie o servidor após importar. Para culturas sem safra, a avaliação considera a data de publicação registrada na portaria e retorna `zarc.season: null` na análise. O endpoint de cobertura por safra continua descrevendo a tábua anual selecionada.

## Rotação de culturas

```bash
curl 'https://nasa-challenge-nvrf.onrender.com/api/v1/crops/rotation' \
  -H 'Content-Type: application/json' \
  -d '{
    "location": {"latitude": -23.5886, "longitude": -48.0483},
    "previous_crop": "soybean",
    "objective": "soil_conservation",
    "planting_month": 10,
    "planting_year": 2026
  }'
```

Use o identificador da cultura anterior em `previous_crop` ou digite o nome em `previous_crop_name`. Para nomes fora do catálogo, o serviço informa que a família botânica e a compatibilidade da sequência precisam ser verificadas. Os objetivos são `soil_conservation`, `diversification`, `grain_production` e `risk_reduction`. O endpoint usa a avaliação de plantio e mantém as condições de cada janela oficial. Selecione solo, cultivar e manejo com `zarc_conditions` quando conhecidos.

Com `previous_planting_date`, o serviço consegue identificar uma possível sucessão dentro da safra ou uma candidata a rotação entre anos na mesma época. O uso como cultura de cobertura aparece com a finalidade e as restrições a validar. Quando a data anterior falta, a sequência fica marcada para validação. A ordenação considera o objetivo, a alternância de famílias botânicas, a classificação regional e o menor nível de risco nos cenários retornados. Confirme colheita, janela e manejo antes de decidir. [Manual de Sistema Plantio Direto da Embrapa](https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/98258/1/500perguntassistemaplantiodireto.pdf).

## AgroSat IA

```bash
curl 'https://nasa-challenge-nvrf.onrender.com/api/v1/ai/chat' \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "Qual a altitude do ponto selecionado?",
    "location": {"latitude": -23.5886, "longitude": -48.0483},
    "history": []
  }'
```

A requisição pode incluir até oito mensagens em `history` com `role` igual a `user` ou `assistant` e `content` de até 2.000 caracteres. `context` aceita cultura anterior, objetivo, mês, ano, data anterior e condições do ZARC. Envie a localização para consultas regionais.

O assistente executa até cinco chamadas às funções internas por mensagem. A resposta inclui texto, status, localização, fontes consultadas e limitações. A API devolve HTTP 429 para o limite local. Chave ausente, limite do provedor e indisponibilidade aparecem no campo `status`. [Function calling do Gemini](https://ai.google.dev/gemini-api/docs/generate-content/function-calling).

## Indicadores complementares

Em todos os endpoints abaixo, informe `latitude` e `longitude` de um ponto paulista. Adicione `include_indicators=true` na consulta a `/api/v1/regions/summary` para incluir os três indicadores no resumo. Cada fonte mantém seu próprio status.

- **Altitude** consulta a grade `srtm90m` do Open Topo Data. [Documentação do SRTM](https://www.opentopodata.org/datasets/srtm/).
- **Solo** usa o WCS do SoilGrids para consultar pH em água, argila, areia, silte e carbono orgânico na camada de 0 a 5 cm. Cada valor é uma estimativa espacial. Uma célula sem cobertura retorna `null`. [WCS do SoilGrids](https://docs.isric.org/globaldata/soilgrids/wcs.html).
- **Riscos** usa previsões do Open-Meteo para geada, chuva intensa e vento forte, com critérios de triagem inspirados nos limites do INMET. O calor depende da cultura escolhida por `crop_id` e tem referências para soja, milho e cana-de-açúcar. Para cana-de-açúcar, a triagem sinaliza a máxima diária prevista acima de 35 °C, com base no capítulo de Fábio R. Marin em *Agrometeorologia dos cultivos*. O sinal de déficit hídrico usa chuva menos ET₀ em pelo menos cinco dias completos e a estimativa de umidade de 3 a 9 cm. Os indicadores servem como triagem regional. Para avisos oficiais, consulte o INMET. [Guia de alertas e critérios do INMET](https://www.gov.br/mdr/pt-br/centrais-de-conteudo/publicacoes/protecao-e-defesa-civil-sedec/guiapraticodesastres.pdf).
