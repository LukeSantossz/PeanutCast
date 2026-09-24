# Dados do PeanutCast

De onde vem cada número, por onde ele passa e o que cada coluna significa. Os números
desta página saem de `python scripts/analisar_dados.py`; se o script disser outra coisa,
vale o script.

## Caminho

```
coletar.py        ->  dados/brutos/          como as APIs entregam, com .origem.json
integrar.py       ->  dados/tratados/dataset.csv       518 linhas, 2000 a 2025
atributos.montar  ->  tabela modelável (em memória)    391 linhas
validacao         ->  324 de desenvolvimento + 67 de teste reservado
```

A tabela modelável não é gravada em disco de propósito. Ela é sempre recalculada a
partir do `dataset.csv` pela mesma função que o treino usa, para não existir uma cópia
que fique velha.

## Fontes

| Fonte | O que vem | Arquivo bruto |
|---|---|---|
| IBGE/SIDRA, tabela 1612 (PAM), produto 2691 "Amendoim (em casca)" | área plantada, área colhida, produção e rendimento por município e ano | `ibge_pam.csv` |
| IBGE, API de malhas v3 | centroide de cada município | `centroides.csv` |
| NASA POWER, API diária, comunidade AG | clima diário no centroide, de 01/09/1999 a 31/12/2025 | `nasa_power/<codigo>.csv` |

A chave de tudo é o **código IBGE de 7 dígitos**, nunca o nome.

## Da coleta ao dataset (`integrar.py`)

**Símbolos do SIDRA.** `-` é zero absoluto e `...` é não disponível (só Vera Cruz 2009).
Nos dois casos não há rendimento para prever e a linha sai. Não é dado faltante a
preencher: é ano sem amendoim ou sem levantamento.

**Consistência.** A integração para se o rendimento diferir de produção ÷ área colhida
por mais de 1 kg/ha, se a área colhida passar da plantada ou se sobrar linha de produção
sem clima. Hoje nenhuma das três acontece.

**Janela da safra.** O clima do ano *N* é o de **1º de setembro de N-1 a 31 de março de
N**: a safra das águas, plantada de setembro a novembro e colhida de janeiro a março, que
a PAM registra no ano da colheita. A safra da seca, plantada em fevereiro, também entra
no número do IBGE e fica fora da janela. Ela é menor em SP e vai como limitação.

## Da tabela integrada à modelável (`atributos.py`)

| Regra | Valor | Por quê |
|---|---|---|
| Área colhida mínima | 100 ha | Média municipal de poucos hectares é a lavoura de um ou dois produtores. Tira 55 linhas, entre elas Oriente 2015 (70 ha, 10.286 kg/ha). O corte é por área, nunca pelo rendimento |
| Safras anteriores mínimas | 3 | Com menos que isso a "média do município" é o ano passado com outro nome |
| Janela de `rend_medio_munic` | 3 safras | Ver abaixo |

**Por que 3 safras e não todas.** O rendimento da região sobe cerca de 80 kg/ha por ano
de 2000 a 2025. A média de todas as safras anteriores fica para trás da tendência. No
walk-forward da validação:

| Palpite | MAE (kg/ha) | RMSE | R² |
|---|---:|---:|---:|
| Média de todas as safras anteriores | 1.098 | 1.310 | -0,64 |
| Média das últimas 3 safras | **595** | **836** | **0,33** |
| Safra anterior (persistência) | 595 | 915 | 0,20 |

Com a média longa como baseline, o modelo pareceria ganhar uns 500 kg/ha só por
acompanhar a tendência, e esse ganho seria contado como clima. O risco é concreto: a
temperatura máxima e os dias de calor têm correlação de 0,5 com o ano. Entre as janelas
de 3 a 10 safras, a de 3 tem o melhor MAE, RMSE e R². A escolha olhou só os anos de
validação.

## Validação (`validacao.py`)

| Conjunto | Anos | Linhas |
|---|---|---:|
| Treino | anos anteriores ao ano validado; a primeira dobra treina de 2003 a 2011 | 127 a 303 |
| Validação | 2012 a 2022, um ano por dobra | 197 no total |
| Teste | 2023 a 2025, olhado uma vez, no fim da Semana 7 | 67 |

Os atributos das linhas de teste usam rendimentos de anos anteriores, inclusive de
outros anos do teste (a linha de 2025 usa 2023 e 2024). Isso não é vazamento: são
números publicados antes da safra que está sendo prevista, e o produtor os teria em
mãos. O modelo, esse sim, é treinado só até 2022.

## Colunas

### `dados/tratados/dataset.csv`

| Coluna | Unidade | Origem |
|---|---|---|
| `codigo_ibge` | | IBGE, 7 dígitos |
| `municipio` | | `peanutcast/municipios.py` |
| `ano` | | ano da colheita, como na PAM |
| `area_plantada_ha`, `area_colhida_ha` | ha | SIDRA 1612 |
| `producao_t` | t | SIDRA 1612 |
| `rendimento_kg_ha` | kg/ha | SIDRA 1612. **É o y** |
| `chuva_mm` | mm | soma na safra, `PRECTOTCORR` |
| `temp_med_c`, `temp_max_c`, `temp_min_c` | °C | média diária na safra, `T2M`, `T2M_MAX`, `T2M_MIN` |
| `umidade_pct` | % | média na safra, `RH2M` |
| `radiacao_mj_m2` | MJ/m²/dia | média na safra, `ALLSKY_SFC_SW_DWN` |
| `vento_m_s` | m/s | média na safra, `WS2M`, a 2 m |
| `dias_calor` | dias | dias da safra com máxima acima de 35 °C, quando a florada e a formação da vagem sofrem |

### Acrescentadas por `atributos.montar`

| Coluna | Papel |
|---|---|
| `rend_medio_munic` | média das 3 safras anteriores publicadas. Atributo de estrutura (D1) e baseline principal (D3) |
| `rend_safra_anterior` | rendimento da última safra publicada. Baseline de persistência (D3); não entra no X |
| `safras_anteriores` | quantas safras o município tem antes desta. Serve só ao filtro |

O X de D1 é `atributos.ATRIBUTOS`: `rend_medio_munic` mais as oito colunas de clima.
