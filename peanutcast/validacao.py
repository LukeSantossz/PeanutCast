"""Protocolo de validação de D5: walk-forward e teste final reservado.

Os dados são painel, município × ano. Split aleatório põe Tupã-2023 no treino
e Tupã-2022 no teste, e o modelo prevê o passado tendo visto o futuro. Aqui
cada ano é previsto só por um modelo treinado com os anos anteriores a ele.

Três conjuntos:
  treino       anos anteriores ao ano validado, cresce a cada dobra
  validação    2012 a 2022, um ano por dobra; escolhe modelo e parâmetros
  teste        2023 a 2025, olhado uma vez só, no fim da Semana 7

Mexer no modelo depois de olhar o teste transforma o teste em validação, e o
número deixa de valer como estimativa do erro em ano novo.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# 2012 como primeiro ano validado deixa pelo menos nove safras de treino
# (2003 a 2011, já que as primeiras linhas precisam de três safras anteriores).
ANOS_VALIDACAO = range(2012, 2023)
ANOS_TESTE = (2023, 2024, 2025)


def separar_teste(tabela):
    """Desenvolvimento (treino e validação) e teste, nessa ordem."""
    no_teste = tabela["ano"].isin(ANOS_TESTE)
    return tabela[~no_teste], tabela[no_teste]


def dobras(desenvolvimento):
    """Uma dobra por ano validado: (ano, treino, validação)."""
    for ano in ANOS_VALIDACAO:
        treino = desenvolvimento[desenvolvimento["ano"] < ano]
        validacao = desenvolvimento[desenvolvimento["ano"] == ano]
        if len(validacao):
            yield ano, treino, validacao


def walk_forward(desenvolvimento, prever, alvo="rendimento_kg_ha"):
    """Roda `prever` em todas as dobras e devolve as previsões linha a linha.

    `prever(treino, validacao)` recebe as duas tabelas e devolve um valor por
    linha da validação. Ajustar o modelo é responsabilidade dela, e ela só
    recebe o treino da dobra, então não há como treinar com o futuro por
    descuido.
    """
    partes = []
    for ano, treino, validacao in dobras(desenvolvimento):
        partes.append(
            pd.DataFrame(
                {
                    "ano": ano,
                    "codigo_ibge": validacao["codigo_ibge"].to_numpy(),
                    "real": validacao[alvo].to_numpy(),
                    "previsto": np.asarray(prever(treino, validacao), dtype=float),
                }
            )
        )
    return pd.concat(partes, ignore_index=True)


def metricas(previsoes):
    """MAE, RMSE e R² de um conjunto de previsões."""
    real, previsto = previsoes["real"], previsoes["previsto"]
    return {
        "n": len(previsoes),
        "mae": mean_absolute_error(real, previsto),
        "rmse": mean_squared_error(real, previsto) ** 0.5,
        "r2": r2_score(real, previsto),
    }


def metricas_por_ano(previsoes):
    """MAE de cada dobra. A dispersão entre anos é a barra de erro do MAE."""
    return previsoes.groupby("ano").apply(
        lambda p: mean_absolute_error(p["real"], p["previsto"]), include_groups=False
    )
