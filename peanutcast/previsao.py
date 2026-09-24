"""A previsão que o painel mostra: modelo, cenários, faixa e fatores.

O modelo do painel é provisório até a equipe congelar o modelo final (prazo
16/10). Trocar é mudar MODELO_PAINEL; o resto da tela não depende da escolha.

O modelo é treinado só com as safras de desenvolvimento (até 2022). O teste de
2023 a 2025 continua fechado: treinar com ele antes de avaliá-lo estragaria a
única medida honesta que o projeto vai ter. Depois da avaliação, o modelo do
painel pode passar a usar todas as safras.

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
    """Modelo do painel, ajustado nas safras de desenvolvimento."""
    desenvolvimento, _ = validacao.separar_teste(tabela)
    return modelos.treinar(_fabrica(), desenvolvimento, desvio=True, colunas=COLUNAS)


def erro_medio(tabela):
    """MAE do modelo do painel no walk-forward da validação: a largura da faixa."""
    desenvolvimento, _ = validacao.separar_teste(tabela)
    previsor = modelos.como_previsor(_fabrica(), desvio=True, colunas=COLUNAS)
    return validacao.metricas(validacao.walk_forward(desenvolvimento, previsor))["mae"]


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
