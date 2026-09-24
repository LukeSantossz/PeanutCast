"""Acesso às três APIs de onde saem os dados do PeanutCast.

Cada função baixa e devolve um DataFrame no formato mais próximo possível do
que a fonte entrega. Tratamento não entra aqui: o que sai destas funções é
gravado em dados/brutos/ como veio, e quem limpa é o integrar.py. Assim, um
erro de tratamento se corrige rodando a integração de novo, sem baixar nada.

Fontes:
  IBGE/SIDRA, tabela 1612 (PAM)   produção de amendoim por município e ano
  IBGE, API de malhas             centroide e contorno de cada município
  NASA POWER, API diária          clima diário no centroide
"""
import time

import pandas as pd
import requests

# Recorte temporal da dependência 2. A série do SIDRA começa em 1974; 2000 em
# diante evita as mudanças de metodologia antigas e ainda dá 26 safras. 2025
# entrou depois de o recorte ser decidido: o IBGE publicou a PAM 2025 em 2026.
ANO_INICIAL = 2000
ANO_FINAL = 2025

SIDRA_TABELA = 1612
SIDRA_AMENDOIM = 2691   # categoria "Amendoim (em casca)" da classificação 81

# Código da variável no SIDRA -> nome da coluna no projeto.
SIDRA_VARIAVEIS = {
    109: "area_plantada_ha",
    216: "area_colhida_ha",
    214: "producao_t",
    112: "rendimento_kg_ha",
}

# Parâmetro da NASA POWER -> nome da coluna no projeto. Comunidade AG, que é a
# de agricultura: radiação em MJ/m²/dia em vez de kWh.
NASA_PARAMETROS = {
    "PRECTOTCORR": "chuva_mm",
    "T2M": "temp_med_c",
    "T2M_MAX": "temp_max_c",
    "T2M_MIN": "temp_min_c",
    "RH2M": "umidade_pct",
    "ALLSKY_SFC_SW_DWN": "radiacao_mj_m2",
    "WS2M": "vento_m_s",
}
NASA_VALOR_AUSENTE = -999.0


def _get_json(url, params=None, tentativas=3):
    """GET com nova tentativa. As três APIs são públicas e às vezes oscilam."""
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = requests.get(url, params=params, timeout=120)
            resposta.raise_for_status()
            return resposta.json()
        except (requests.RequestException, ValueError):
            if tentativa == tentativas:
                raise
            time.sleep(5 * tentativa)


def baixar_pam(codigos):
    """Produção de amendoim dos municípios, de ANO_INICIAL a ANO_FINAL.

    Uma linha por município, ano e variável, com o valor como texto. O texto é
    proposital: o SIDRA usa símbolos no lugar de número ("-" para zero, "..."
    para não disponível, "X" para dado omitido), e decidir o que cada um
    significa é tratamento, não coleta.
    """
    url = (
        f"https://apisidra.ibge.gov.br/values/t/{SIDRA_TABELA}"
        f"/n6/{','.join(str(c) for c in codigos)}"
        f"/v/{','.join(str(v) for v in SIDRA_VARIAVEIS)}"
        f"/p/{ANO_INICIAL}-{ANO_FINAL}"
        f"/c81/{SIDRA_AMENDOIM}"
    )
    linhas = _get_json(url, params={"formato": "json"})
    # A primeira linha da resposta é o cabeçalho com a descrição das colunas.
    return pd.DataFrame(
        {
            "codigo_ibge": int(linha["D1C"]),
            "ano": int(linha["D3C"]),
            "variavel": SIDRA_VARIAVEIS[int(linha["D2C"])],
            "valor": linha["V"],
            "unidade": linha["MN"],
        }
        for linha in linhas[1:]
    )


def baixar_centroide(codigo):
    """Latitude e longitude do centroide do município, pela API de malhas."""
    dados = _get_json(
        f"https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{codigo}/metadados"
    )
    centroide = dados[0]["centroide"]
    return centroide["latitude"], centroide["longitude"]


def baixar_malha(codigo):
    """Contorno do município em GeoJSON, com o código IBGE como id da feição.

    Qualidade intermediária: o mapa é regional, e o contorno detalhado só
    deixaria o arquivo mais pesado sem mudar nada na tela.
    """
    dados = _get_json(
        f"https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{codigo}",
        params={"formato": "application/vnd.geo+json", "qualidade": "intermediaria"},
    )
    feicao = dados["features"][0]
    feicao["id"] = int(feicao["properties"]["codarea"])
    return feicao


def baixar_clima_diario(latitude, longitude):
    """Clima diário no ponto, cobrindo todas as safras do recorte.

    Começa em setembro do ano anterior ao primeiro ano do recorte, porque a
    safra das águas que o IBGE registra em 2000 foi plantada em 1999.
    """
    dados = _get_json(
        "https://power.larc.nasa.gov/api/temporal/daily/point",
        params={
            "parameters": ",".join(NASA_PARAMETROS),
            "community": "AG",
            "latitude": latitude,
            "longitude": longitude,
            "start": f"{ANO_INICIAL - 1}0901",
            "end": f"{ANO_FINAL}1231",
            "format": "JSON",
        },
    )
    series = dados["properties"]["parameter"]
    clima = pd.DataFrame({NASA_PARAMETROS[p]: series[p] for p in NASA_PARAMETROS})
    clima.index = pd.to_datetime(clima.index, format="%Y%m%d")
    clima.index.name = "data"
    return clima
