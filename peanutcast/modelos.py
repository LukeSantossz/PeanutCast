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
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import HuberRegressor, LinearRegression, RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from . import atributos

SEMENTE = 42

def _media_corrigida(treino, val):
    """Média recente mais o quanto, em média, a safra ficou acima dela no treino.

    É o modelo de desvio com o clima removido: um desvio constante, aprendido
    só do passado. Corrige o atraso da média de 3 safras em relação à
    tendência sem usar clima nenhum, e por isso é a régua justa para medir o
    que o clima acrescenta. Sem ela, a correção da tendência, que vem de graça
    no intercepto de qualquer modelo de desvio, seria contada como clima.
    """
    desvio = treino[atributos.ALVO] - treino["rend_medio_munic"]
    return val["rend_medio_munic"] + desvio.mean()


def _media_corrigida_mediana(treino, val):
    """A mesma correção, com a mediana: é a régua da regressão robusta (Huber)."""
    desvio = treino[atributos.ALVO] - treino["rend_medio_munic"]
    return val["rend_medio_munic"] + desvio.median()


BASELINES = {
    "Média das 3 últimas safras": lambda treino, val: val["rend_medio_munic"],
    "Safra anterior": lambda treino, val: val["rend_safra_anterior"],
    "Média corrigida pela tendência": _media_corrigida,
    "Média corrigida pela tendência (mediana)": _media_corrigida_mediana,
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
        n_jobs=1,  # dado pequeno: mais threads só custam sincronização
    )


def ridge():
    # A Regressão Linear da Semana 7: a mesma reta, com os coeficientes
    # encolhidos. O quanto encolher é escolhido dentro do treino de cada dobra.
    return make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-1, 4, 30)))


def huber():
    # Regressão linear robusta: anos extremos pesam menos no ajuste. Sem clima,
    # ela se reduz à mediana do desvio, e por isso é comparada à baseline
    # corrigida pela mediana.
    return make_pipeline(StandardScaler(), HuberRegressor(alpha=1.0, max_iter=1000))


def random_forest_ajustado():
    return RandomForestRegressor(
        n_estimators=500,
        min_samples_leaf=10,
        max_features=0.5,
        random_state=SEMENTE,
        n_jobs=-1,
    )


def xgboost_ajustado():
    return XGBRegressor(
        n_estimators=200,
        max_depth=2,
        learning_rate=0.03,
        subsample=0.8,
        min_child_weight=10,
        reg_lambda=10,
        random_state=SEMENTE,
        n_jobs=1,
    )


FABRICAS = {
    "Regressão Linear": regressao_linear,
    "Random Forest": random_forest,
    "XGBoost": xgboost,
}


AJUSTADOS = {
    "Regressão Linear (Ridge)": ridge,
    "Regressão Linear (Huber)": huber,
    "Random Forest": random_forest_ajustado,
    "XGBoost": xgboost_ajustado,
}


def treinar(fabrica, tabela, desvio=False, colunas=None):
    """Modelo novo da fábrica, ajustado na tabela inteira que recebeu."""
    colunas = colunas or atributos.ATRIBUTOS
    y = tabela[atributos.ALVO]
    if desvio:
        y = y - tabela["rend_medio_munic"]
    return fabrica().fit(tabela[colunas], y)


def prever(modelo, tabela, desvio=False, colunas=None):
    """Previsão em kg/ha, nas duas formulações."""
    previsto = modelo.predict(tabela[colunas or atributos.ATRIBUTOS])
    return previsto + tabela["rend_medio_munic"].to_numpy() if desvio else previsto


def como_previsor(fabrica, desvio=False, colunas=None):
    """Transforma uma fábrica de modelo em prever(treino, validacao)."""

    def previsor(treino, val):
        return prever(treinar(fabrica, treino, desvio, colunas), val, desvio, colunas)

    return previsor


# Semana 6: parâmetros de partida, clima da safra inteira, nas duas formulações.
# Semana 7: parâmetros ajustados, desvio, só o clima da fase crítica, que foi a
# combinação que melhor se saiu na validação.
PREVISORES = {
    **BASELINES,
    **{f"{nome} (rendimento)": como_previsor(f) for nome, f in FABRICAS.items()},
    **{f"{nome} (desvio)": como_previsor(f, desvio=True) for nome, f in FABRICAS.items()},
    **{
        f"{nome} (desvio, fase crítica)": como_previsor(f, desvio=True, colunas=atributos.CLIMA_CRITICO)
        for nome, f in AJUSTADOS.items()
    },
}
