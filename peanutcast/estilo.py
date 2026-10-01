"""CSS da página em volta do painel: fontes e o que é do próprio Streamlit.

O painel tem o seu CSS isolado (peanutcast/interface/painel.css). Este aqui
cuida do resto: declara as fontes servidas de static/fonts/ (o app não depende
de internet para elas) e ajusta os elementos do Streamlit, que na tela do
painel somem para o mapa ocupar a janela inteira.
"""
import streamlit as st

# Archivo é variável em peso e em largura: o painel usa a largura estreita nos
# títulos. Sem o intervalo de font-stretch aqui, o navegador ignoraria a largura.
_FONTES = """
@font-face{font-family:'Archivo';font-style:normal;font-weight:300 800;font-stretch:62% 125%;font-display:swap;src:url(app/static/fonts/archivo.woff2) format('woff2')}
@font-face{font-family:'IBM Plex Mono';font-style:normal;font-weight:400;font-display:swap;src:url(app/static/fonts/ibm-plex-mono-400.woff2) format('woff2')}
@font-face{font-family:'IBM Plex Mono';font-style:normal;font-weight:500;font-display:swap;src:url(app/static/fonts/ibm-plex-mono-500.woff2) format('woff2')}
@font-face{font-family:'IBM Plex Mono';font-style:normal;font-weight:600;font-display:swap;src:url(app/static/fonts/ibm-plex-mono-600.woff2) format('woff2')}
"""

_SEM_CROMO = """
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
/* O gerenciador de cookies do streamlit-authenticator é um iframe que ocupa
   uma linha vazia. Ele precisa existir para funcionar, então só sai do fluxo. */
[data-testid="stElementContainer"]:has(> div > iframe.stCustomComponentV1){position:absolute;height:0;overflow:hidden}
"""

_ENTRADA = """
[data-testid="stMainBlockContainer"]{max-width:1280px;padding:4vh 32px 32px}
.pc-marca{font-family:'Archivo',sans-serif;font-weight:800;font-stretch:80%;font-size:20px;letter-spacing:.01em;margin-top:6vh}
.pc-marca i{font-style:normal;color:#D6A26B}
.pc-titulo{font-family:'Archivo',sans-serif;font-weight:700;font-stretch:85%;font-size:38px;line-height:1.04;letter-spacing:-.01em;margin:40px 0 12px}
.pc-tag{color:#BDAC97;margin:0 0 28px;max-width:34ch}
[data-testid="stForm"]{border:0;padding:0}
[data-testid="stForm"] [data-testid="stHeading"]{display:none}
[data-testid="stForm"] [data-testid="stElementContainer"]:has([data-testid="stFormSubmitButton"]),
[data-testid="stFormSubmitButton"]{width:100%!important}
[data-testid="stTextInputRootElement"]{border-radius:6px}
[data-testid="stFormSubmitButton"] button{width:100%;background:#D6A26B;border-color:#D6A26B;color:#14100C;font-weight:700;padding:10px 0}
[data-testid="stFormSubmitButton"] button:hover{background:#E2B47F;border-color:#E2B47F;color:#14100C}
[data-baseweb="tab-list"]{gap:22px}
.pc-nota{font-size:12.5px;color:#8B7A69;line-height:1.5;margin-top:18px}
.pc-nota code{font-size:12px}
"""

_PAINEL = """
[data-testid="stMainBlockContainer"]{max-width:none;padding:0}
[data-testid="stAppViewContainer"] [data-testid="stVerticalBlock"]{gap:0}
/* No desktop o painel cabe na janela e rola por dentro; no celular ele vira
   uma coluna, e quem rola é a página. */
@media (min-width:861px){[data-testid="stMain"]{overflow:hidden}}
"""


def _aplicar(css):
    st.html(f"<style>{_FONTES}{_SEM_CROMO}{css}</style>")


def entrada():
    """Tela de login e de cadastro, e os avisos antes do painel."""
    _aplicar(_ENTRADA)


def painel():
    """Tela do painel: o componente ocupa a janela inteira."""
    _aplicar(_PAINEL)
