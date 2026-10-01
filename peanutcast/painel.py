"""O painel: os dados que vão para o navegador e o componente que os desenha.

A tela é um componente do Streamlit (st.components.v2) com HTML, CSS e JS em
peanutcast/interface/. O Python continua dono dos dados e do modelo: monta
aqui um pacote com o histórico, o clima, os cenários, as previsões e os
números do modelo, e o navegador só desenha. A única conta que o navegador
refaz é a da previsão enquanto o usuário arrasta um controle de clima, com os
coeficientes de previsao.parametros(); tests/test_previsao.py confere que essa
conta é a mesma do modelo.

Do navegador para o Python voltam só dois avisos: um município favoritado ou
desfavoritado, e o clique em Sair.
"""
import math
from pathlib import Path

import pandas as pd
import streamlit as st

from . import atributos, dados, previsao
from .municipios import MUNICIPIOS

INTERFACE = Path(__file__).parent / "interface"

_componente = st.components.v2.component(
    "painel",
    css=(INTERFACE / "painel.css").read_text(encoding="utf-8"),
    js=(INTERFACE / "painel.js").read_text(encoding="utf-8"),
)


def _num(valor, casas=None):
    """Número para JSON: NaN vira None, porque JSON não tem NaN."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)) or pd.isna(valor):
        return None
    return round(float(valor), casas) if casas is not None else float(valor)


def _celulas(clima):
    """Municípios com a mesma série de clima da NASA POWER recebem o mesmo número.

    A NASA POWER tem células de cerca de 50 km, e os 24 municípios caem em 6
    delas. Vizinhos na mesma célula têm o mesmo cenário, e o painel mostra isso.
    """
    assinaturas, celula = {}, {}
    for codigo in MUNICIPIOS:
        serie = clima[clima["codigo_ibge"] == codigo].sort_values("ano")["chuva_critica_mm"].round(2)
        celula[codigo] = assinaturas.setdefault(tuple(serie), len(assinaturas))
    return celula


def _municipio(codigo, nome, dataset, clima, modelo, anos, celula, centro, por_safra):
    historico = dataset[dataset["codigo_ibge"] == codigo].set_index("ano").reindex(anos)
    clima_municipio = clima[clima["codigo_ibge"] == codigo].sort_values("ano")
    media, anos_media = atributos.media_recente(historico.rename_axis("ano").reset_index())
    tem_media = bool(anos_media)
    cenarios = previsao.cenarios(clima_municipio) if len(clima_municipio) >= 3 else None
    limites = previsao.limites(clima_municipio) if len(clima_municipio) else None
    serie_clima = clima_municipio.set_index("ano").reindex(anos)
    safras = por_safra[por_safra["codigo_ibge"] == codigo]
    return {
        "codigo": codigo,
        "nome": nome,
        "celula": celula,
        "centro": centro,
        "hist": [
            None if pd.isna(linha.rendimento_kg_ha) else {
                "r": _num(linha.rendimento_kg_ha, 0),
                "ac": _num(linha.area_colhida_ha, 0),
                "p": _num(linha.producao_t, 0),
            }
            for linha in historico.itertuples()
        ],
        "clima": {coluna: [_num(v, 2) for v in serie_clima[coluna]] for coluna in previsao.COLUNAS},
        "media": float(media) if tem_media else None,
        "anosMedia": [int(a) for a in anos_media],
        "cenarios": None if cenarios is None else {
            nome_cenario: {c: float(cenarios.loc[nome_cenario, c]) for c in previsao.COLUNAS}
            for nome_cenario in previsao.CENARIOS
        },
        "lim": None if limites is None else {
            c: [float(limites.loc["min", c]), float(limites.loc["max", c])] for c in previsao.COLUNAS
        },
        "prev": {} if not tem_media or cenarios is None else {
            nome_cenario: previsao.prever(modelo, media, cenarios.loc[nome_cenario])
            for nome_cenario in previsao.CENARIOS
        },
        "wf": [
            {"a": int(s.ano), "p": round(float(s.previsto)), "r": round(float(s.real))}
            for s in safras.itertuples()
        ],
    }


def _geometria(malhas):
    """Contornos do IBGE como listas de anéis [lon, lat], com 4 casas (~10 m)."""
    if malhas is None:
        return None
    geo = {}
    for feicao in malhas["features"]:
        g = feicao["geometry"]
        aneis = g["coordinates"] if g["type"] == "Polygon" else [a for p in g["coordinates"] for a in p]
        geo[str(int(feicao["properties"]["codarea"]))] = [
            [[round(x, 4), round(y, 4)] for x, y in anel] for anel in aneis
        ]
    return geo


def _centros(malhas):
    """Ponto de cada município para o rótulo: o centro do maior anel, por área.

    O centroides.csv do IBGE fica fora do caminho do app; o centro calculado
    daqui cai dentro do polígono nos 24 municípios, que é o que o rótulo pede.
    """
    if malhas is None:
        return {}
    centros = {}
    for feicao in malhas["features"]:
        g = feicao["geometry"]
        aneis = g["coordinates"] if g["type"] == "Polygon" else [p[0] for p in g["coordinates"]]

        def area_e_centro(anel):
            a = cx = cy = 0.0
            for (x0, y0), (x1, y1) in zip(anel, anel[1:]):
                k = x0 * y1 - x1 * y0
                a, cx, cy = a + k, cx + (x0 + x1) * k, cy + (y0 + y1) * k
            return abs(a / 2), ([cx / (3 * a), cy / (3 * a)] if a else anel[0])

        centros[int(feicao["properties"]["codarea"])] = max(map(area_e_centro, aneis))[1]
    return centros


@st.cache_data(show_spinner="Preparando o painel…")
def _pacote(versao):
    """Tudo o que o navegador precisa, menos o que é do usuário. Recalcula só
    quando algum arquivo lido muda (versao entra na chave do cache)."""
    dataset, clima, malhas = dados.carregar_dataset(), dados.carregar_clima(), dados.carregar_malhas()
    modelo, erro = dados.modelo_do_painel()
    por_safra = dados.previsto_por_safra()
    anos = list(range(int(dataset["ano"].min()), int(dataset["ano"].max()) + 1))
    celula, centros = _celulas(clima), _centros(malhas)
    p = previsao.parametros(modelo)

    comparacao, teste = dados.carregar_comparacao(), dados.carregar_teste()
    metricas = ["mae", "mae_desvio_entre_anos", "rmse", "r2", "ganho_sobre_baseline"]
    return {
        "versao": versao,
        "anos": anos,
        "proxima": anos[-1] + 1,
        "erro": erro,
        "areaMin": atributos.AREA_MINIMA_HA,
        "colunas": previsao.COLUNAS,
        "modelo": {"nome": previsao.MODELO_PAINEL, "mu": p["media"], "sd": p["desvio"], "coef": p["coef"], "b": p["intercepto"]},
        "municipios": [
            _municipio(codigo, nome, dataset, clima, modelo, anos, celula[codigo], centros.get(codigo), por_safra)
            for codigo, nome in MUNICIPIOS.items()
        ],
        "geo": _geometria(malhas),
        "validacao": None if comparacao is None else {
            "anos": comparacao["anos_validacao"],
            "previsores": {k: {m: v[m] for m in metricas} for k, v in comparacao["previsores"].items()},
        },
        "teste": None if teste is None else {k: teste[k] for k in ("regua", "principal", "metricas", "mae_por_ano")},
    }


def pronto():
    """O painel só abre com o dataset e o clima integrados."""
    return dados.carregar_dataset() is not None and dados.carregar_clima() is not None


def mostrar(usuario_nome, meus_favoritos):
    """Desenha o painel. Devolve o resultado do componente: .favorito traz o
    município clicado em Guardar, e .sair vem preenchido no clique em Sair."""
    pacote = dict(_pacote(dados.versao()), modo="painel", usuario=usuario_nome, favoritos=list(meus_favoritos))
    return _componente(
        data=pacote,
        key="painel",
        on_favorito_change=lambda: None,
        on_sair_change=lambda: None,
    )


def capa():
    """O mapa da tela de entrada: os 24 municípios no cenário normal.

    Sem dados ou sem contornos baixados, a capa não aparece, e a entrada
    funciona igual.
    """
    if not pronto() or dados.carregar_malhas() is None:
        return
    _componente(data=dict(_pacote(dados.versao()), modo="capa"), key="capa")
