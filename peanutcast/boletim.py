"""Previsão sazonal do CPTEC: em que tercil deve cair a chuva de dez a fev.

O CPTEC publica todo mês, no modelo BAM-1.2 calibrado, a probabilidade do tercil
de chuva mais provável para os trimestres seguintes. Cada figura é uma grade
float32 de 192 × 384 (gaussiana T126), latitude do sul para o norte e longitude
de 0 a 359,0625. O valor traz o tercil no sinal: negativo = abaixo da normal,
positivo = acima, 0 = normal; o módulo é a probabilidade.

A emissão do mês M cobre M+2 a M+4 (SEAS01) e M+3 a M+5 (SEAS02). Dez a fev, a
janela do modelo, só aparece na emissão de setembro (SEAS02) e na de outubro
(SEAS01). A previsão escolhe o cenário do painel; o modelo continua recebendo
os terços do histórico (decisão D2).
"""
import math
from collections import Counter

import numpy as np

URL = (
    "https://dataserver.cptec.inpe.br/dataserver_sazonal/calibrated/prec_seas/prob_terciles/"
    "{ano}/{mes:02d}/01/BAM12_CALB_{ano}{mes:02d}0100_SEAS{figura:02d}.dat"
)
NLAT, NLON = 192, 384
AUSENTE = -9.99e8
MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def figura_djf(ano, mes):
    """(figura, safra) da emissão ano/mes que cobre dez a fev, ou None."""
    figura = {9: 2, 10: 1}.get(mes)
    return None if figura is None else (figura, ano + 1)


def safra_alvo(hoje):
    """Safra que ainda não acabou: até fevereiro é a do ano, depois a do ano seguinte."""
    return hoje.year if hoje.month <= 2 else hoje.year + 1


def candidatos(hoje):
    """Emissões a tentar, da mais nova para a mais velha."""
    ano = safra_alvo(hoje) - 1
    return [(ano, 10), (ano, 9)]


def vigente(origem, hoje):
    return origem.get("safra") == safra_alvo(hoje)


def latitudes():
    return np.degrees(np.arcsin(np.polynomial.legendre.leggauss(NLAT)[0]))


def longitudes():
    return np.arange(NLON) * (360 / NLON)


def ler_grade(bruto):
    if len(bruto) != NLAT * NLON * 4:
        raise ValueError(f"grade do CPTEC com {len(bruto)} bytes; esperado {NLAT * NLON * 4}")
    grade = np.frombuffer(bruto, dtype="<f4").reshape(NLAT, NLON).astype(float)
    grade[grade <= AUSENTE / 2] = np.nan
    return grade


def tercil(valor):
    """(cenário, probabilidade) de uma célula, ou None se ela não tem valor."""
    if math.isnan(valor):
        return None
    if valor == 0:
        return "Normal", None
    return ("Seco" if valor < 0 else "Chuvoso"), round(abs(float(valor)), 2)


def por_municipio(grade, centros):
    """{código: (cenário, probabilidade)} pela célula mais próxima de cada centro (lon, lat)."""
    lat, lon = latitudes(), longitudes()
    leitura = {}
    for codigo, (x, y) in centros.items():
        i = int(np.argmin(abs(lat - y)))
        distancia = abs(lon - x % 360)
        j = int(np.argmin(np.minimum(distancia, 360 - distancia)))
        t = tercil(grade[i, j])
        if t is not None:
            leitura[codigo] = t
    return leitura


def cenario_regiao(cenarios):
    """O tercil mais frequente; empate entre os primeiros vira Normal."""
    contagem = Counter(cenarios).most_common()
    if not contagem:
        return None
    if len(contagem) > 1 and contagem[0][1] == contagem[1][1]:
        return "Normal"
    return contagem[0][0]


def resumo(grade, origem, centros):
    """O que o painel recebe: cenário da região, janela e tercil por município."""
    leitura = por_municipio(grade, centros)
    ano, mes = origem["emissao"]
    safra = origem["safra"]
    return {
        "cenario": cenario_regiao([c for c, _ in leitura.values()]),
        "safra": safra,
        "janela": f"dez/{safra - 1} a fev/{safra}",
        "emissao": f"{MESES[mes - 1]}/{ano}",
        "municipios": {str(k): {"cen": c, "prob": p} for k, (c, p) in leitura.items()},
    }
