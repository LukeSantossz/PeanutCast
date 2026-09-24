"""Números que sustentam as decisões de atributos.py e validacao.py.

Rodar depois do integrar.py:

    python scripts/analisar_dados.py

Não grava nada, só imprime. É o que o relatório cita na metodologia, e é o
que se roda de novo antes de mexer em qualquer constante de atributos.py.

Só olha para os anos de validação. Os anos de teste (2023 a 2025) ficam fora
de toda comparação aqui, porque escolher uma regra olhando o teste é treinar
no teste.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from peanutcast import atributos, caminhos, validacao  # noqa: E402

pd.set_option("display.width", 120)


def titulo(texto):
    print(f"\n{'=' * 78}\n{texto}\n{'=' * 78}")


def tendencia(dataset):
    titulo("1. Tendência: rendimento médio da região por ano, ponderado pela área")
    por_ano = dataset.groupby("ano").apply(
        lambda a: pd.Series(
            {
                "municipios": len(a),
                "area_ha": a["area_colhida_ha"].sum(),
                "rend_kg_ha": np.average(a["rendimento_kg_ha"], weights=a["area_colhida_ha"]),
            }
        ),
        include_groups=False,
    )
    print(por_ano.round(0).astype(int).to_string())
    inclinacao = np.polyfit(dataset["ano"], dataset["rendimento_kg_ha"], 1)[0]
    print(f"\nInclinação da reta: {inclinacao:+.0f} kg/ha por ano")

    print("\nCorrelação de cada variável de clima com o ano (clima que também tem tendência")
    print("pode levar o crédito da tecnologia):")
    correlacoes = dataset[atributos.CLIMA].corrwith(dataset["ano"]).sort_values()
    print(correlacoes.round(2).to_string())


def area_pequena(dataset):
    titulo(f"2. Município-ano com área pequena (corte atual: {atributos.AREA_MINIMA_HA} ha)")
    for corte in (20, 50, 100, 200):
        abaixo = dataset[dataset["area_colhida_ha"] < corte]["rendimento_kg_ha"]
        print(
            f"< {corte:>3} ha: {len(abaixo):>3} linhas, "
            f"rendimento de {abaixo.min():,.0f} a {abaixo.max():,.0f} kg/ha"
        )
    relativo = dataset["rendimento_kg_ha"] / dataset.groupby("ano")["rendimento_kg_ha"].transform("median")
    extremos = dataset.assign(x_mediana_do_ano=relativo.round(2))
    extremos = extremos[(relativo > 2) | (relativo < 0.4)]
    print("\nMais que o dobro, ou menos de 40%, da mediana regional do ano:")
    print(
        extremos[["municipio", "ano", "area_colhida_ha", "rendimento_kg_ha", "x_mediana_do_ano"]]
        .sort_values("x_mediana_do_ano")
        .to_string(index=False)
    )


def tabela_modelavel(tabela):
    titulo("3. Tabela modelável")
    desenvolvimento, teste = validacao.separar_teste(tabela)
    print(f"{len(tabela)} linhas, {tabela['codigo_ibge'].nunique()} municípios")
    print(f"desenvolvimento: {len(desenvolvimento)} linhas, {desenvolvimento['ano'].min()} a {desenvolvimento['ano'].max()}")
    print(f"teste reservado: {len(teste)} linhas, anos {list(validacao.ANOS_TESTE)}")
    primeira_dobra = desenvolvimento[desenvolvimento["ano"] < min(validacao.ANOS_VALIDACAO)]
    print(f"treino da primeira dobra: {len(primeira_dobra)} linhas, desde {primeira_dobra['ano'].min()}")
    print("\nDistribuição do rendimento no desenvolvimento:")
    print(desenvolvimento["rendimento_kg_ha"].describe().round(0).to_string())


def janelas(dataset):
    titulo("4. Baselines no walk-forward da validação: qual média histórica usar")
    base = dataset[dataset["area_colhida_ha"] >= atributos.AREA_MINIMA_HA].sort_values(["codigo_ibge", "ano"])
    anteriores = base.groupby("codigo_ibge")["rendimento_kg_ha"].shift(1)
    por_municipio = anteriores.groupby(base["codigo_ibge"])
    base = base.assign(safras_anteriores=por_municipio.transform(lambda s: s.expanding().count()))

    candidatas = {"persistencia (safra anterior)": anteriores}
    candidatas["media de todas as anteriores"] = por_municipio.transform(lambda s: s.expanding().mean())
    for janela in (3, 4, 5, 6, 8, 10):
        candidatas[f"media das ultimas {janela}"] = por_municipio.transform(
            lambda s, j=janela: s.rolling(j, min_periods=1).mean()
        )

    base = base.assign(**{nome: serie for nome, serie in candidatas.items()})
    base = base[base["safras_anteriores"] >= atributos.SAFRAS_ANTERIORES_MIN]
    desenvolvimento, _ = validacao.separar_teste(base)

    linhas = []
    for nome in candidatas:
        previsoes = validacao.walk_forward(desenvolvimento, lambda treino, val, c=nome: val[c])
        por_ano = validacao.metricas_por_ano(previsoes)
        m = validacao.metricas(previsoes)
        linhas.append({"baseline": nome, "MAE": m["mae"], "desvio entre anos": por_ano.std(), "RMSE": m["rmse"], "R2": m["r2"]})
    print(pd.DataFrame(linhas).set_index("baseline").round(2).to_string())


def main():
    dataset = pd.read_csv(caminhos.DATASET)
    tendencia(dataset)
    area_pequena(dataset)
    tabela_modelavel(atributos.montar(dataset))
    janelas(dataset)


if __name__ == "__main__":
    main()
