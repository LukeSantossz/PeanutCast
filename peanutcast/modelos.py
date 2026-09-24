"""As duas baselines de D3 e os três modelos, no formato que o walk-forward usa.

Cada item é uma função prever(treino, validacao) -> previsões. As baselines
ignoram o treino; os modelos treinam do zero a cada chamada, só com o treino
que o walk-forward entrega, e por isso não têm como ver o futuro.

Cada modelo roda em duas formulações. "Rendimento" é a de D1: o modelo prevê
kg/ha direto, com rend_medio_munic entre os atributos. "Desvio" prevê quanto
a safra fica acima ou abaixo de rend_medio_munic e soma a média de volta. A
tela continua em kg/ha nas duas. A segunda existe porque árvore não extrapola:
com o rendimento subindo 80 kg/ha por ano, a safra nova quase sempre fica
acima do que a árvore viu no treino, e o desvio não tem esse problema.

Os parâmetros são os de partida da Semana 6, conservadores de propósito: com
127 linhas na primeira dobra, árvore funda decora município. O ajuste fino é
da Semana 7, e só na validação.
"""
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from . import atributos

SEMENTE = 42

BASELINES = {
    "Média das 3 últimas safras": lambda treino, val: val["rend_medio_munic"],
    "Safra anterior": lambda treino, val: val["rend_safra_anterior"],
}


def regressao_linear():
    # A escala não muda a previsão da regressão linear, mas deixa os
    # coeficientes comparáveis entre si, que é o que se lê na Semana 7.
    return make_pipeline(StandardScaler(), LinearRegression())


def random_forest():
    return RandomForestRegressor(
        n_estimators=500,
        min_samples_leaf=5,
        max_features=0.5,
        random_state=SEMENTE,
        n_jobs=-1,
    )


def xgboost():
    return XGBRegressor(
        n_estimators=300,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        random_state=SEMENTE,
        n_jobs=-1,
    )


FABRICAS = {
    "Regressão Linear": regressao_linear,
    "Random Forest": random_forest,
    "XGBoost": xgboost,
}


def treinar(fabrica, tabela, desvio=False):
    """Modelo novo da fábrica, ajustado na tabela inteira que recebeu."""
    x, y = atributos.separar(tabela)
    if desvio:
        y = y - tabela["rend_medio_munic"]
    return fabrica().fit(x, y)


def prever(modelo, tabela, desvio=False):
    """Previsão em kg/ha, nas duas formulações."""
    x, _ = atributos.separar(tabela)
    previsto = modelo.predict(x)
    return previsto + tabela["rend_medio_munic"].to_numpy() if desvio else previsto


def como_previsor(fabrica, desvio=False):
    """Transforma uma fábrica de modelo em prever(treino, validacao)."""

    def previsor(treino, val):
        return prever(treinar(fabrica, treino, desvio), val, desvio)

    return previsor


PREVISORES = {
    **BASELINES,
    **{f"{nome} (rendimento)": como_previsor(f) for nome, f in FABRICAS.items()},
    **{f"{nome} (desvio)": como_previsor(f, desvio=True) for nome, f in FABRICAS.items()},
}
