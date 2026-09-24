"""PeanutCast: painel de previsão de produtividade do amendoim.

Rodar com:  streamlit run app.py

Três abas. "Município" traz o histórico, o clima de cada safra e a previsão
para a próxima, com cenário, ajuste fino do clima e faixa de erro. "Comparar
municípios" põe todos lado a lado sob o mesmo cenário, em mapa e tabela.
"Modelos" mostra como cada modelo se saiu na validação e o que pesa na
previsão.

O modelo da previsão é o principal da avaliação final, treinado com todas as
safras (ver peanutcast/previsao.py).
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from peanutcast import atributos, auth, dados, favoritos, previsao
from peanutcast.caminhos import garantir_pastas
from peanutcast.municipios import MUNICIPIOS, NOMES

# Mesmos valores de .streamlit/config.toml. O Plotly não lê o tema do
# Streamlit para a cor das marcas, então ela precisa ser dita aqui.
COR_AMENDOIM = "#C8945F"
COR_CASCA = "#3D2B1F"
ESCALA_MAPA = ["#F5EFE4", "#C8945F", "#3D2B1F"]


def kg(valor):
    """3577.4 -> "3.577 kg/ha", no formato brasileiro."""
    return f"{valor:,.0f} kg/ha".replace(",", ".")


def centro(malhas):
    """Centro do retângulo que contém todos os municípios, para o mapa."""
    pontos = [
        ponto
        for feicao in malhas["features"]
        for anel in feicao["geometry"]["coordinates"]
        for ponto in anel
    ]
    lons, lats = zip(*pontos)
    return {"lon": (min(lons) + max(lons)) / 2, "lat": (min(lats) + max(lats)) / 2}


st.set_page_config(page_title="PeanutCast", page_icon="🥜", layout="wide")

garantir_pastas()

autenticador = auth.criar_autenticador()
usuario = auth.tela_de_entrada(autenticador)
if usuario is None:
    st.stop()

# =====================================================================
# Daqui para baixo só roda quem está logado.
# =====================================================================
auth.barra_lateral_do_usuario(autenticador)

st.sidebar.divider()
st.sidebar.subheader("Meus municípios")
meus = favoritos.listar(usuario)
if meus:
    for nome in meus:
        st.sidebar.write(nome)
else:
    st.sidebar.caption("Nenhum município favoritado ainda.")

st.title("PeanutCast")
st.caption("Previsão de produtividade do amendoim na Alta Paulista")

dataset = dados.carregar_dataset()
clima = dados.carregar_clima()

# Caixa com borda e legenda em vez de st.info: o st.info é azul, e azul está
# fora da paleta da marca. Assim as cores saem todas de .streamlit/config.toml.
if dataset is None or clima is None:
    with st.container(border=True):
        st.caption(
            "Os dados ainda não foram baixados nesta máquina. Rode "
            "`python scripts/coletar.py` e depois `python scripts/integrar.py`."
        )
    st.stop()

modelo, erro_medio = dados.modelo_do_painel()
proxima_safra = int(dataset["ano"].max()) + 1
codigo_de = {nome: codigo for codigo, nome in MUNICIPIOS.items()}

aba_municipio, aba_comparar, aba_modelos = st.tabs(
    ["Município", "Comparar municípios", "Modelos"]
)

# =====================================================================
# Município
# =====================================================================
with aba_municipio:
    # O município escolhido aqui vale para a aba toda. Guardar no session_state
    # faz a escolha sobreviver ao clique no botão de favoritar.
    municipio = st.selectbox("Município", NOMES, key="municipio")

    ja_e_favorito = municipio in meus
    rotulo = "Remover dos favoritos" if ja_e_favorito else "Favoritar município"
    if st.button(rotulo):
        favoritos.alternar(usuario, municipio)
        st.rerun()

    historico = dados.historico(dataset, municipio)
    clima_municipio = clima[clima["codigo_ibge"] == codigo_de[municipio]]

    esquerda, direita = st.columns([2, 1])

    with esquerda:
        st.subheader("Histórico de produtividade")
        figura = px.line(
            historico,
            x="ano",
            y="rendimento_kg_ha",
            markers=True,
            labels={"ano": "Safra", "rendimento_kg_ha": "Rendimento (kg/ha)"},
            color_discrete_sequence=[COR_AMENDOIM],
        )
        # Ano como número inteiro no eixo, sem o "2,000" que o Plotly põe por
        # padrão. Ano sem safra chega como linha vazia (ver dados.historico) e
        # aparece como buraco, em vez de a linha ligar dois anos distantes.
        figura.update_xaxes(tickformat="d", dtick=2)
        st.plotly_chart(figura, width="stretch")
        publicadas = historico.dropna(subset=["rendimento_kg_ha"])
        st.caption(
            f"{len(publicadas)} safras com rendimento publicado pelo IBGE/SIDRA-PAM "
            f"entre {publicadas['ano'].min()} e {publicadas['ano'].max()}."
        )

        st.subheader("Clima na floração e no enchimento da vagem")
        figura_clima = px.bar(
            clima_municipio,
            x="ano",
            y="chuva_critica_mm",
            hover_data={"dias_calor_critica": True, "temp_max_critica_c": ":.1f"},
            labels={
                "ano": "Safra",
                "chuva_critica_mm": "Chuva de dez a fev (mm)",
                "dias_calor_critica": "Dias acima de 35 °C",
                "temp_max_critica_c": "Máxima média (°C)",
            },
            color_discrete_sequence=[COR_AMENDOIM],
        )
        figura_clima.update_xaxes(tickformat="d", dtick=2)
        st.plotly_chart(figura_clima, width="stretch")
        st.caption(
            "Dezembro a fevereiro é quando o amendoim floresce e enche a vagem. "
            "Passe o mouse numa barra para ver o calor da safra. Fonte: NASA POWER."
        )

    with direita:
        st.subheader(f"Previsão para a safra {proxima_safra}")
        media, anos = atributos.media_recente(historico)
        with st.container(border=True):
            if not anos:
                st.caption(
                    f"Nenhuma safra com pelo menos {atributos.AREA_MINIMA_HA} ha "
                    "colhidos, então não há histórico para prever."
                )
            else:
                cenario = st.radio(
                    "Cenário climático",
                    previsao.CENARIOS,
                    index=1,
                    horizontal=True,
                    key="cenario_municipio",
                )
                base = previsao.cenarios(clima_municipio).loc[cenario]
                faixa = previsao.limites(clima_municipio)

                # A chave dos controles inclui município e cenário: trocar
                # qualquer um dos dois volta os controles para o cenário novo,
                # em vez de manter o ajuste feito em outro contexto.
                ajustado = {}
                with st.expander("Ajustar o clima"):
                    for coluna in previsao.COLUNAS:
                        inteiro = coluna == "dias_calor_critica"
                        conv = int if inteiro else float
                        ajustado[coluna] = st.slider(
                            previsao.ROTULOS[coluna],
                            min_value=conv(faixa.loc["min", coluna]),
                            max_value=conv(faixa.loc["max", coluna]),
                            value=conv(round(base[coluna], 0 if inteiro else 1)),
                            step=1 if inteiro else 0.1,
                            key=f"{municipio}-{cenario}-{coluna}",
                        )
                    st.caption(
                        "Os limites são o mínimo e o máximo que o município já "
                        "teve desde 2000. Fora deles o modelo estaria chutando."
                    )

                valor = previsao.prever(modelo, media, ajustado)
                st.metric("Rendimento esperado", kg(valor))
                st.caption(
                    f"Faixa típica: {kg(valor - erro_medio)} a {kg(valor + erro_medio)}. "
                    f"É o erro médio do modelo em safras que ele não tinha visto "
                    f"(± {kg(erro_medio)}), não um intervalo de confiança."
                )
                st.divider()
                st.caption(
                    f"Média das safras de {', '.join(str(a) for a in anos)}: {kg(media)}. "
                    "A previsão parte dela, corrige a tendência de alta do rendimento "
                    "e ajusta pelo clima do cenário. O PeanutCast simula o cenário "
                    "escolhido; ele não prevê o tempo."
                )

# =====================================================================
# Comparar municípios
# =====================================================================
with aba_comparar:
    cenario_comum = st.radio(
        "Cenário climático para todos os municípios",
        previsao.CENARIOS,
        index=1,
        horizontal=True,
        key="cenario_comparar",
    )

    linhas = []
    for nome in NOMES:
        media, anos = atributos.media_recente(dados.historico(dataset, nome))
        if not anos:
            continue
        clima_nome = clima[clima["codigo_ibge"] == codigo_de[nome]]
        valor = previsao.prever(modelo, media, previsao.cenarios(clima_nome).loc[cenario_comum])
        linhas.append(
            {
                "codigo_ibge": codigo_de[nome],
                "Município": nome,
                "Favorito": "★" if nome in meus else "",
                "Média das 3 últimas safras": round(media),
                "Rendimento esperado": round(valor),
            }
        )
    comparacao = pd.DataFrame(linhas).sort_values("Rendimento esperado", ascending=False)

    malhas = dados.carregar_malhas()
    if malhas is None:
        st.caption("O contorno dos municípios não foi baixado. Rode `python scripts/coletar.py`.")
    else:
        # Fundo branco, sem imagem de mapa: só os contornos do IBGE. Não
        # depende de servidor de mapas nem de chave de acesso, e funciona
        # sem internet. O choropleth_map lê o GeoJSON no padrão do IBGE;
        # o choropleth antigo exige os polígonos no sentido contrário.
        figura_mapa = px.choropleth_map(
            comparacao,
            geojson=malhas,
            locations="codigo_ibge",
            color="Rendimento esperado",
            hover_name="Município",
            hover_data={"codigo_ibge": False, "Média das 3 últimas safras": True},
            color_continuous_scale=ESCALA_MAPA,
            map_style="white-bg",
            center=centro(malhas),
            zoom=7.2,
            opacity=0.9,
        )
        figura_mapa.update_layout(
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            height=480,
            # Barra de cores deitada, embaixo: em pé ela come metade do mapa.
            coloraxis_colorbar={"orientation": "h", "y": -0.02, "yanchor": "top",
                                "thickness": 12, "title": {"text": "kg/ha", "side": "top"}},
        )
        st.plotly_chart(figura_mapa, width="stretch")
    st.dataframe(
        comparacao.drop(columns="codigo_ibge"),
        hide_index=True,
        width="stretch",
        column_config={
            "Média das 3 últimas safras": st.column_config.NumberColumn(format="%d kg/ha"),
            "Rendimento esperado": st.column_config.NumberColumn(format="%d kg/ha"),
        },
    )
    st.caption(
        f"Cada município recebe o seu próprio clima do cenário {cenario_comum.lower()}, "
        "tirado da sua história. Vizinhos na mesma célula da NASA POWER têm o mesmo "
        "clima, e o que os separa é o histórico. Faixa típica de cada previsão: "
        f"± {kg(erro_medio)}."
    )

# =====================================================================
# Modelos
# =====================================================================
with aba_modelos:
    resultado = dados.carregar_comparacao()
    if resultado is None:
        with st.container(border=True):
            st.caption(
                "A comparação entre modelos ainda não rodou nesta máquina. "
                "Rode `python scripts/comparar.py` (cerca de 40 segundos)."
            )
    else:
        st.subheader("Como cada modelo se saiu na validação")
        metricas = pd.DataFrame(resultado["previsores"]).T
        metricas = metricas[["mae", "mae_desvio_entre_anos", "rmse", "r2", "ganho_sobre_baseline"]]
        metricas.columns = ["Erro médio (kg/ha)", "Variação entre anos", "RMSE", "R²", "Ganho sobre a régua"]
        st.dataframe(
            metricas.astype(float).sort_values("Erro médio (kg/ha)"),
            width="stretch",
            column_config={
                "Erro médio (kg/ha)": st.column_config.NumberColumn(format="%.0f"),
                "Variação entre anos": st.column_config.NumberColumn(format="%.0f"),
                "RMSE": st.column_config.NumberColumn(format="%.0f"),
                "R²": st.column_config.NumberColumn(format="%.2f"),
                "Ganho sobre a régua": st.column_config.NumberColumn(format="%+.0f"),
            },
        )
        inicio, fim = resultado["anos_validacao"]
        st.caption(
            f"Cada safra de {inicio} a {fim} foi prevista por um modelo treinado só com "
            "as safras anteriores. A régua é o melhor palpite sem clima nenhum; o ganho "
            "mostra quanto o clima acrescenta a ela. As safras de 2023 a 2025 ficaram "
            "guardadas para a avaliação final, logo abaixo."
        )

    avaliacao = dados.carregar_teste()
    if avaliacao is not None:
        st.subheader("Avaliação final, safras de 2023 a 2025")
        teste = pd.DataFrame(avaliacao["metricas"]).T[["mae", "rmse", "ganho_sobre_regua"]]
        por_ano = pd.DataFrame(avaliacao["mae_por_ano"]).T
        teste = teste.join(por_ano.add_prefix("Erro em "))
        teste = teste.rename(
            columns={"mae": "Erro médio (kg/ha)", "rmse": "RMSE", "ganho_sobre_regua": "Ganho sobre a régua"}
        )
        st.dataframe(
            teste.astype(float).round(0).sort_values("Erro médio (kg/ha)"),
            width="stretch",
            column_config={"Ganho sobre a régua": st.column_config.NumberColumn(format="%+.0f")},
        )
        st.caption(
            f"Modelos treinados até 2022, avaliados uma única vez com regras registradas "
            f"antes. Régua: {avaliacao['regua']}. Em 2024, a seca do El Niño derrubou a "
            "safra e todos os palpites erraram muito; o clima puxou a previsão para baixo "
            "e errou menos que a régua. A média simples das 3 safras, sem correção da "
            "tendência, teve o menor erro médio no teste."
        )

    st.subheader("O que pesa na previsão")
    pesos = previsao.fatores(modelo).rename_axis("Variável").rename("kg/ha").reset_index()
    figura_pesos = px.bar(
        pesos,
        x="kg/ha",
        y="Variável",
        orientation="h",
        color_discrete_sequence=[COR_CASCA],
        labels={"kg/ha": "Efeito de uma variação típica (kg/ha)", "Variável": ""},
    )
    st.plotly_chart(figura_pesos, width="stretch")
    st.caption(
        f"Modelo do painel: {previsao.MODELO_PAINEL}, com o clima de dezembro a fevereiro. "
        "Cada barra é quanto a previsão muda quando a variável sobe uma variação "
        "típica (um desvio-padrão), com as outras paradas. Calor e radiação na floração "
        "puxam o rendimento para baixo, mas o efeito é pequeno perto do erro médio."
    )
