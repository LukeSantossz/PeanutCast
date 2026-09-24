"""Junta produção e clima numa tabela só, em dados/tratados/dataset.csv.

Rodar depois do coletar.py:

    python scripts/integrar.py

Uma linha por município e ano, só onde o IBGE publicou rendimento. Não baixa
nada: lê dados/brutos/, então pode rodar quantas vezes precisar.

A safra do ano N é o clima de setembro de N-1 a março de N. É a safra das
águas: plantio de setembro a novembro, colheita quatro a cinco meses depois,
e é ela que a PAM registra no ano da colheita. A safra da seca, plantada em
fevereiro, também entra no número do IBGE e fica fora desta janela. É menor
em SP e entra no relatório como limitação.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from peanutcast import caminhos  # noqa: E402
from peanutcast.municipios import MUNICIPIOS  # noqa: E402

MES_INICIO_SAFRA = 9    # setembro do ano anterior
MES_FIM_SAFRA = 3       # março do ano da colheita

# Acima de 35 °C a florada e a formação da vagem do amendoim sofrem. É o
# extremo térmico que D1 pede, contado em dias da safra.
LIMIAR_CALOR_C = 35


def ler_producao():
    """PAM em formato largo, com os símbolos do SIDRA resolvidos.

    "-" é zero absoluto e "..." é não disponível. Nos dois casos não há
    rendimento para prever, então a linha sai. Não é dado faltante a
    preencher: é ano sem amendoim, ou sem levantamento.
    """
    pam = pd.read_csv(caminhos.IBGE_PAM, dtype={"valor": str})
    pam["valor"] = pd.to_numeric(pam["valor"], errors="coerce")
    largo = pam.pivot_table(
        index=["codigo_ibge", "ano"], columns="variavel", values="valor"
    ).reset_index()
    largo.columns.name = None
    return largo[largo["rendimento_kg_ha"] > 0]


def conferir_producao(producao):
    """Para a execução se o IBGE entregar algo que contradiga a si mesmo."""
    recalculado = producao["producao_t"] * 1000 / producao["area_colhida_ha"]
    diferenca = (recalculado - producao["rendimento_kg_ha"]).abs()
    # O IBGE arredonda o rendimento para kg inteiro; mais que 1 kg é erro.
    if (diferenca > 1).any():
        raise ValueError(f"rendimento não bate com produção/área em {(diferenca > 1).sum()} linhas")
    if (producao["area_colhida_ha"] > producao["area_plantada_ha"]).any():
        raise ValueError("área colhida maior que a plantada")


def ano_da_safra(datas):
    """Ano de colheita a que cada dia pertence, ou nulo fora da janela."""
    ano = datas.dt.year + (datas.dt.month >= MES_INICIO_SAFRA)
    na_janela = (datas.dt.month >= MES_INICIO_SAFRA) | (datas.dt.month <= MES_FIM_SAFRA)
    return ano.where(na_janela)


def clima_por_safra(codigo):
    """Clima diário de um município resumido em uma linha por safra."""
    diario = pd.read_csv(caminhos.NASA_POWER / f"{codigo}.csv", parse_dates=["data"])
    diario["ano"] = ano_da_safra(diario["data"])
    diario = diario.dropna(subset=["ano"])
    diario["ano"] = diario["ano"].astype(int)
    diario["dias_calor"] = diario["temp_max_c"] > LIMIAR_CALOR_C

    safra = diario.groupby("ano").agg(
        dias=("data", "size"),
        chuva_mm=("chuva_mm", "sum"),
        temp_med_c=("temp_med_c", "mean"),
        temp_max_c=("temp_max_c", "mean"),
        temp_min_c=("temp_min_c", "mean"),
        umidade_pct=("umidade_pct", "mean"),
        radiacao_mj_m2=("radiacao_mj_m2", "mean"),
        vento_m_s=("vento_m_s", "mean"),
        dias_calor=("dias_calor", "sum"),
    )
    # Safra incompleta nas pontas da série (a primeira começa em set/1999, mas
    # a de 1999 começaria em set/1998) não entra: chuva somada em meia safra
    # pareceria seca.
    completa = safra["dias"] >= 212
    return safra[completa].drop(columns="dias").reset_index().assign(codigo_ibge=codigo)


def main():
    producao = ler_producao()
    conferir_producao(producao)

    clima = pd.concat(clima_por_safra(codigo) for codigo in MUNICIPIOS)
    dataset = producao.merge(clima, on=["codigo_ibge", "ano"], how="left", validate="one_to_one")

    sem_clima = dataset["chuva_mm"].isna()
    if sem_clima.any():
        raise ValueError(f"{sem_clima.sum()} linhas de produção sem clima correspondente")

    dataset.insert(1, "municipio", dataset["codigo_ibge"].map(MUNICIPIOS))
    dataset = dataset.sort_values(["municipio", "ano"]).round(2)
    caminhos.DADOS_TRATADOS.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(caminhos.DATASET, index=False)

    print(
        f"{len(dataset)} linhas, {dataset['codigo_ibge'].nunique()} municípios, "
        f"{dataset['ano'].min()} a {dataset['ano'].max()} -> {caminhos.DATASET}"
    )


if __name__ == "__main__":
    main()
