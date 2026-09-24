"""A previsão que o painel mostra: modelo, cenários, faixa e fatores.

O modelo do painel é a Huber com o clima da fase crítica, o principal da
avaliação final (scripts/avaliar_teste.py). O teste de 2023 a 2025 já foi
aberto, em 24/09, e por isso o painel treina com todas as safras: não há mais
nada a proteger, e a previsão de 2026 ganha os três anos mais recentes.

A faixa é o erro médio de um walk-forward de 2012 até a última safra, cada ano
previsto por um modelo treinado só com os anteriores. Ela inclui 2024, o ano da
quebra, e por isso é mais larga que o erro da validação sozinha (647 contra 579
kg/ha em 24/09).

Cenários, como em D2: o painel não prevê o clima. Os anos do município são
ordenados pela chuva de dezembro a fevereiro e divididos em terços; cada
cenário usa a mediana das variáveis nos anos do seu terço. Assim o cenário
seco carrega junto o calor e a radiação que os anos secos tiveram de fato, em
vez de uma combinação que nunca aconteceu.
"""
import numpy as np
import pandas as pd

from . import atributos, modelos, validacao

MODELO_PAINEL = "Regressão Linear (Huber)"
COLUNAS = atributos.CLIMA_CRITICO
CENARIOS = ["Seco", "Normal", "Chuvoso"]

ROTULOS = {
    "chuva_critica_mm": "Chuva de dez a fev (mm)",
    "temp_max_critica_c": "Máxima média de dez a fev (°C)",
    "radiacao_critica_mj_m2": "Radiação média de dez a fev (MJ/m²/dia)",
    "dias_calor_critica": "Dias acima de 35 °C, dez a fev",
}


def _fabrica():
    return modelos.AJUSTADOS[MODELO_PAINEL]


def treinar(tabela):
    """Modelo do painel, ajustado em todas as safras."""
    return modelos.treinar(_fabrica(), tabela, desvio=True, colunas=COLUNAS)


def erro_medio(tabela):
    """MAE do walk-forward de 2012 até a última safra: a largura da faixa."""
    previsor = modelos.como_previsor(_fabrica(), desvio=True, colunas=COLUNAS)
    erros = []
    for ano in range(min(validacao.ANOS_VALIDACAO), int(tabela["ano"].max()) + 1):
        treino, alvo = tabela[tabela["ano"] < ano], tabela[tabela["ano"] == ano]
        if len(alvo):
            erros.append((alvo[atributos.ALVO] - previsor(treino, alvo)).abs())
    return float(pd.concat(erros).mean())


def cenarios(clima_municipio):
    """Clima de cada cenário para um município, como DataFrame indexado pelo nome."""
    ordenado = clima_municipio.sort_values("chuva_critica_mm")
    cortes = np.array_split(np.arange(len(ordenado)), 3)
    return pd.DataFrame(
        {nome: ordenado.iloc[posicoes][COLUNAS].median() for nome, posicoes in zip(CENARIOS, cortes)}
    ).T


def limites(clima_municipio):
    """Mínimo e máximo já observados, para os controles deslizantes não saírem deles."""
    return clima_municipio[COLUNAS].agg(["min", "max"])


def prever(modelo, media_recente, clima):
    """Rendimento em kg/ha: a média recente mais o desvio que o clima sugere.

    `clima` é um dict ou uma Series com as colunas de COLUNAS.
    """
    x = pd.DataFrame([clima])[COLUNAS]
    return media_recente + float(modelo.predict(x)[0])


def fatores(modelo):
    """Quanto cada variável move a previsão, em kg/ha por desvio-padrão.

    Vale para os modelos lineares do painel: com as variáveis padronizadas, o
    coeficiente é o efeito de uma variação típica (um desvio-padrão) daquela
    variável, com as outras paradas.
    """
    coeficientes = modelo[-1].coef_
    return pd.Series(coeficientes, index=[ROTULOS[c] for c in COLUNAS]).sort_values()
