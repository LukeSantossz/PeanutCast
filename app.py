"""PeanutCast: painel de previsão de produtividade do amendoim.

Rodar com:  streamlit run app.py

Estado atual: entra, cadastra, guarda os municípios favoritos e mostra o
histórico de rendimento do IBGE. A previsão de verdade chega na Semana 8; até
lá o espaço dela mostra a média histórica, que é a baseline que o modelo vai
precisar bater (D3). O app cresce trocando peça, não sendo reescrito.
"""
import plotly.express as px
import streamlit as st

from peanutcast import auth, dados, favoritos
from peanutcast.caminhos import garantir_pastas
from peanutcast.municipios import NOMES

# Mesmos valores de .streamlit/config.toml. O Plotly não lê o tema do
# Streamlit para a cor da linha, então ela precisa ser dita aqui.
COR_AMENDOIM = "#C8945F"

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

# O município escolhido aqui vale para a tela toda. Guardar no session_state
# faz a escolha sobreviver ao clique no botão de favoritar.
municipio = st.selectbox(
    "Município",
    NOMES,
    key="municipio",
)

ja_e_favorito = municipio in meus
rotulo = "Remover dos favoritos" if ja_e_favorito else "Favoritar município"
if st.button(rotulo):
    favoritos.alternar(usuario, municipio)
    st.rerun()

st.divider()

dataset = dados.carregar_dataset()

# Caixa com borda e legenda em vez de st.info: o st.info é azul, e azul está
# fora da paleta da marca. Assim as cores saem todas de .streamlit/config.toml.
if dataset is None:
    with st.container(border=True):
        st.caption(
            "Os dados ainda não foram baixados nesta máquina. Rode "
            "`python scripts/coletar.py` e depois `python scripts/integrar.py`."
        )
    st.stop()

historico = dados.historico(dataset, municipio)

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

with direita:
    st.subheader("Previsão para a próxima safra")
    with st.container(border=True):
        media = historico["rendimento_kg_ha"].mean()
        st.metric("Média histórica do município", f"{media:,.0f} kg/ha".replace(",", "."))
        st.caption(
            "Ainda não é previsão: a previsão com clima chega na Semana 8. Esta média "
            "é o palpite que o modelo vai precisar superar para mostrar que o clima "
            "acrescenta alguma coisa."
        )
