"""PeanutCast: painel de previsão de produtividade do amendoim.

Rodar com:  streamlit run app.py

Estado atual, Semana 1: entra, cadastra e guarda os municípios favoritos. O
gráfico do histórico chega na Semana 3 e a previsão de verdade na Semana 8.
Os espaços das duas já estão marcados na tela, para o app crescer trocando
peça e não sendo reescrito.
"""
import streamlit as st

from peanutcast import auth, favoritos
from peanutcast.caminhos import garantir_pastas
from peanutcast.municipios import NOMES

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

esquerda, direita = st.columns(2)

# Caixa com borda e legenda em vez de st.info: o st.info é azul, e azul está
# fora da paleta da marca. Assim as cores saem todas de .streamlit/config.toml.
with esquerda:
    st.subheader("Histórico de produtividade")
    with st.container(border=True):
        st.caption(
            "Chega na Semana 3, quando a extração do IBGE/SIDRA-PAM estiver pronta. "
            "Aqui entra o rendimento em kg/ha de cada safra do município."
        )

with direita:
    st.subheader("Previsão para a próxima safra")
    with st.container(border=True):
        st.caption(
            "Chega na Semana 8. Até lá a tela fica assim de propósito: o objetivo "
            "da Semana 1 é o caminho até aqui funcionar, não o número existir."
        )
