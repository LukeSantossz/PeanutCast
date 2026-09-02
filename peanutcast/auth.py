"""Cadastro e login, em cima do streamlit-authenticator.

O caminho do YAML é passado direto para a biblioteca. Com isso ela lê as
credenciais na abertura e grava de volta sozinha a cada cadastro ou troca de
senha, então não há código de persistência aqui.

Senha escrita em texto puro no YAML é convertida para hash na primeira
execução, pelo auto_hash. Serve para criar o primeiro usuário sem script.

A sessão dura enquanto a aba fica aberta: expiry_days está em 0, então não há
cookie de "continuar conectado". A razão está no comentário do YAML.
"""
import streamlit as st
import streamlit_authenticator as stauth
import yaml

from .caminhos import CREDENCIAIS

# Mensagens em português. A biblioteca aceita os rótulos por parâmetro.
CAMPOS_LOGIN = {
    "Form name": "Entrar",
    "Username": "Usuário",
    "Password": "Senha",
    "Login": "Entrar",
}

CAMPOS_CADASTRO = {
    "Form name": "Criar conta",
    "First name": "Nome",
    "Last name": "Sobrenome",
    "Email": "E-mail",
    "Username": "Usuário",
    "Password": "Senha",
    "Repeat password": "Repita a senha",
    "Register": "Cadastrar",
}


def _ler_configuracao():
    """Lê o YAML só para pegar a seção de cookie.

    As credenciais em si não passam por aqui: quem cuida delas é a biblioteca,
    a partir do caminho do arquivo.
    """
    if not CREDENCIAIS.exists():
        raise FileNotFoundError(
            f"{CREDENCIAIS.name} não encontrado. Copie credenciais.exemplo.yaml "
            f"para {CREDENCIAIS.name} e troque a chave do cookie."
        )
    return yaml.safe_load(CREDENCIAIS.read_text(encoding="utf-8"))


def criar_autenticador():
    """Monta o objeto de autenticação a partir do arquivo de credenciais."""
    config = _ler_configuracao()
    cookie = config["cookie"]
    return stauth.Authenticate(
        str(CREDENCIAIS),          # caminho, não dicionário: a biblioteca grava de volta
        cookie["name"],
        cookie["key"],
        cookie["expiry_days"],
    )


def tela_de_entrada(autenticador):
    """Desenha login e cadastro. Devolve o usuário logado, ou None.

    Enquanto ninguém está logado, esta função ocupa a tela inteira. Quem chama
    deve parar a execução quando o retorno for None.
    """
    # Primeiro tenta reaproveitar o cookie, sem desenhar nada na tela. É o que
    # o modo "unrendered" faz. Sem esta chamada, o formulário de login seria
    # desenhado antes de a sessão ser recuperada, e a página apareceria com a
    # tela de login e a tela de quem está logado ao mesmo tempo.
    autenticador.login(location="unrendered")
    if st.session_state.get("authentication_status"):
        return st.session_state["username"]

    st.title("PeanutCast")
    st.caption("Previsão de produtividade do amendoim na Alta Paulista")

    aba_entrar, aba_cadastrar = st.tabs(["Entrar", "Criar conta"])

    with aba_entrar:
        autenticador.login(fields=CAMPOS_LOGIN)
        if st.session_state.get("authentication_status") is False:
            st.error("Usuário ou senha incorretos.")

    with aba_cadastrar:
        try:
            # captcha desligado: atrapalha mais do que protege num app interno.
            _, usuario_novo, _ = autenticador.register_user(
                fields=CAMPOS_CADASTRO,
                captcha=False,
                password_hint=False,
            )
            if usuario_novo:
                st.success("Conta criada. Volte para a aba Entrar.")
        except Exception as erro:
            # A biblioteca sinaliza senha fraca, usuário repetido e e-mail
            # inválido por exceção. Mostrar a mensagem é melhor que engolir.
            st.error(str(erro))

    # Se a senha acabou de ser aceita, recarrega em vez de devolver o usuário.
    # O formulário já foi desenhado acima neste mesmo ciclo, então devolver
    # aqui deixaria a página com a tela de login em cima e a tela de quem está
    # logado embaixo. No ciclo seguinte o login "unrendered" lá em cima
    # reconhece a sessão e nada disso é desenhado.
    if st.session_state.get("authentication_status"):
        st.rerun()
    return None


def barra_lateral_do_usuario(autenticador):
    """Nome de quem está logado e o botão de sair, na barra lateral."""
    st.sidebar.write(f"**{st.session_state['name']}**")
    autenticador.logout("Sair", "sidebar")

    # A biblioteca zera authentication_status no clique, mas não recarrega a
    # página, então o resto do script continuaria desenhando a tela de quem
    # está logado. O rerun faz o Sair valer no mesmo clique.
    #
    # Isso só é seguro porque expiry_days está em 0 e não existe cookie a
    # apagar. Com cookie, o rerun cortaria o componente que manda a instrução
    # de remoção para o navegador, e o usuário sairia sem sair de verdade.
    #
    # No terminal aparece "peanutcast_sessao" a cada logout. É a biblioteca
    # tentando apagar um cookie que nunca foi criado e imprimindo o erro em
    # vez de ignorá-lo. Não quebra nada.
    if not st.session_state.get("authentication_status"):
        st.rerun()
