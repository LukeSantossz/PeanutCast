"""Do dataset integrado à tabela modelável: o X e o y de D1.

Toda coluna criada aqui olha só para safras anteriores à da própria linha.
É a regra que impede o modelo de ver o futuro, e os testes em
tests/test_atributos.py a verificam trocando um ano futuro e conferindo que
nada do passado muda.

As três constantes abaixo são decisões de metodologia. Os números que as
sustentam saem de scripts/analisar_dados.py; mudar uma delas sem rodar o
script de novo é decidir no escuro.
"""
import pandas as pd

ALVO = "rendimento_kg_ha"

# Município-ano com menos de 100 ha colhidos sai. Média municipal de poucos
# hectares é a lavoura de um ou dois produtores, e é ali que estão os valores
# absurdos (Oriente 2015: 70 ha, 10.286 kg/ha). O corte é por área, nunca pelo
# rendimento: cortar pelo y escolheria a dedo os anos que o modelo erra.
AREA_MINIMA_HA = 100

# rend_medio_munic é a média das últimas 3 safras publicadas, não de todas.
# O rendimento da região subiu 80 kg/ha por ano de 2000 a 2025, e a média de
# todos os anos fica para trás: na validação erra 1.098 kg/ha, contra 595 da
# média de 3. Com a média longa, o modelo pareceria ganhar do palpite só por
# acompanhar a tendência, e esse ganho seria contado como clima.
#
# Entre as janelas de 3 a 10, a de 3 tem o menor MAE, o menor RMSE e o maior
# R² na validação. A escolha olhou só os anos de validação, nunca o teste.
JANELA_SAFRAS = 3

# Linha com menos de 3 safras anteriores não tem média que valha a pena: com
# uma só, a "média do município" é o ano passado por outro nome.
SAFRAS_ANTERIORES_MIN = 3

ESTRUTURA = ["rend_medio_munic"]
CLIMA = [
    "chuva_mm",
    "temp_med_c",
    "temp_max_c",
    "temp_min_c",
    "umidade_pct",
    "radiacao_mj_m2",
    "vento_m_s",
    "dias_calor",
]
ATRIBUTOS = ESTRUTURA + CLIMA


def montar(dataset):
    """Tabela modelável a partir de dados/tratados/dataset.csv.

    Acrescenta rend_medio_munic (estrutura, D1), rend_safra_anterior (a
    baseline de persistência, D3) e safras_anteriores, e remove as linhas que
    não entram no treino: área pequena demais e histórico curto demais.
    """
    tabela = dataset[dataset["area_colhida_ha"] >= AREA_MINIMA_HA]
    tabela = tabela.sort_values(["codigo_ibge", "ano"]).copy()

    # shift(1) dentro do município: a linha do ano N só enxerga até a safra
    # publicada antes de N. Todas as colunas abaixo partem dele.
    anteriores = tabela.groupby("codigo_ibge")[ALVO].shift(1)
    por_municipio = anteriores.groupby(tabela["codigo_ibge"])

    tabela["rend_medio_munic"] = por_municipio.transform(
        lambda s: s.rolling(JANELA_SAFRAS, min_periods=1).mean()
    )
    tabela["rend_safra_anterior"] = anteriores
    tabela["safras_anteriores"] = por_municipio.transform(lambda s: s.expanding().count())

    tabela = tabela[tabela["safras_anteriores"] >= SAFRAS_ANTERIORES_MIN]
    tabela["safras_anteriores"] = tabela["safras_anteriores"].astype(int)
    return tabela.reset_index(drop=True)


def media_recente(safras):
    """rend_medio_munic da safra que ainda vai acontecer.

    Recebe o histórico de um município e devolve a média e os anos usados,
    pelas mesmas regras de montar(): só safras com área suficiente, as últimas
    JANELA_SAFRAS. É a baseline que o painel mostra no lugar da previsão.
    """
    validas = safras[safras["area_colhida_ha"] >= AREA_MINIMA_HA].sort_values("ano")
    ultimas = validas.tail(JANELA_SAFRAS)
    return ultimas[ALVO].mean(), ultimas["ano"].tolist()


def separar(tabela):
    """X e y, nessa ordem, com as colunas de ATRIBUTOS."""
    return tabela[ATRIBUTOS], tabela[ALVO]
