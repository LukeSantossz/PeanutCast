"""PeanutCast: painel de previsão de produtividade do amendoim.

Rodar com:  streamlit run app.py

Depois do login, a tela inteira é o painel (peanutcast/painel.py): o mapa
regional com o rendimento esperado no cenário escolhido, a ficha de cada
município com a previsão, o porquê e a simulação do clima, a comparação entre
municípios e o método. O Streamlit cuida do login, dos favoritos e dos dados;
o desenho fica em peanutcast/interface/.

O modelo da previsão é o principal da avaliação final, treinado com todas as
safras (ver peanutcast/previsao.py).
"""
import streamlit as st

from peanutcast import auth, estilo, favoritos, painel
from peanutcast.caminhos import garantir_pastas

st.set_page_config(
    page_title="PeanutCast",
    page_icon="🥜",
    layout="wide",
    initial_sidebar_state="collapsed",
)

garantir_pastas()

autenticador = auth.criar_autenticador()
if not st.session_state.get("authentication_status"):
    estilo.entrada()
usuario = auth.tela_de_entrada(autenticador, capa=painel.capa)
if usuario is None:
    st.stop()

# =====================================================================
# Daqui para baixo só roda quem está logado.
# =====================================================================
if not painel.pronto():
    estilo.entrada()
    st.html(
        '<div class="pc-marca">Peanut<i>Cast</i></div>'
        '<div class="pc-titulo">Os dados ainda não foram baixados nesta máquina.</div>'
        '<p class="pc-tag">Rode <code>python scripts/coletar.py</code> e depois '
        "<code>python scripts/integrar.py</code>. Quando terminarem, clique em Verificar de novo.</p>"
    )
    st.button("Verificar de novo")   # o clique já roda o script outra vez
    if st.button("Sair", type="tertiary"):
        auth.sair(autenticador)
    st.stop()

estilo.painel()
resultado = painel.mostrar(auth.nome_de_quem_entrou(), favoritos.listar(usuario))

# O painel avisa o clique em Guardar com o município e o estado que a tela
# passou a mostrar. A tela já mudou no navegador; aqui a escolha vai para o
# arquivo. Gravar o estado, e não inverter o que está no arquivo, é o que
# impede tela e arquivo de ficarem trocados quando um aviso se perde.
if resultado.favorito:
    escolha = resultado.favorito
    if escolha["guardar"]:
        favoritos.adicionar(usuario, escolha["nome"])
    else:
        favoritos.remover(usuario, escolha["nome"])
if resultado.sair:
    auth.sair(autenticador)
