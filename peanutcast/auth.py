"""Cadastro e login, em cima do streamlit-authenticator.

O caminho do YAML é passado direto para a biblioteca. Com isso ela lê as
credenciais na abertura e grava de volta sozinha a cada cadastro ou troca de
senha, então não há código de persistência aqui.

Senha escrita em texto puro no YAML é convertida para hash na primeira
execução, pelo auto_hash. Serve para criar o primeiro usuário sem script.

A sessão dura enquanto a aba fica aberta: expiry_days está em 0, então não há
cookie de "continuar conectado". A razão está no comentário do YAML.

A biblioteca fala inglês nas regras de senha e nos erros de cadastro. As
regras continuam as dela (o validador só troca a explicação), e os erros são
traduzidos aqui. Tudo isso foi escrito contra a 0.4.2, travada no
requirements.txt: ao atualizar, confira as mensagens de _ERROS_CADASTRO.
"""
import re

import streamlit as st
import streamlit_authenticator as stauth
import yaml

from .caminhos import CREDENCIAIS

# Os símbolos que a biblioteca aceita na senha, na mesma ordem do padrão dela.
_SIMBOLOS = r"""!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?`~"""

REGRAS_SENHA = (
    "A senha precisa ter de 8 a 20 caracteres, com pelo menos uma letra minúscula, "
    "uma maiúscula, um número e um símbolo, como ! @ # $ % & *. "
    "Letras com acento e espaços não são aceitos."
)

_ERROS_CADASTRO = {
    "First name is not valid": "Nome inválido.",
    "Last name is not valid": "Sobrenome inválido.",
    "Email is not valid": "E-mail inválido.",
    "Username is not valid": "Usuário inválido: use até 20 letras sem acento, números, _ ou -.",
    "Password/repeat password fields cannot be empty": "Preencha a senha e a repetição da senha.",
    "Passwords do not match": "As duas senhas não são iguais.",
    "Email already taken": "Este e-mail já tem conta.",
    "Username/email already taken": "Este usuário ou e-mail já tem conta.",
}


def _juntar(itens):
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


class _Validador(stauth.Validator):
    """As regras de senha da biblioteca, explicadas em português.

    validate_password continua o da biblioteca. Só diagnose_password, que monta
    a mensagem de erro, é reescrito, com um item a mais: a biblioteca recusa
    acento e espaço sem dizer por quê, e a mensagem dela saía vazia nesse caso.
    """

    def diagnose_password(self, password):
        faltas = []
        if not 8 <= len(password) <= 20:
            faltas.append("de 8 a 20 caracteres")
        if not re.search(r"[a-z]", password):
            faltas.append("uma letra minúscula")
        if not re.search(r"[A-Z]", password):
            faltas.append("uma letra maiúscula")
        if not re.search(r"\d", password):
            faltas.append("um número")
        if not re.search(f"[{_SIMBOLOS}]", password):
            faltas.append("um símbolo, como ! @ # $ % & *")
        frases = ["A senha precisa ter " + _juntar(faltas) + "."] if faltas else []
        if re.search(f"[^A-Za-z\\d{_SIMBOLOS}]", password):
            frases.append(("Ela" if frases else "A senha") + " não pode ter acento nem espaço.")
        return " ".join(frases) or REGRAS_SENHA

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
    autenticador = stauth.Authenticate(
        str(CREDENCIAIS),          # caminho, não dicionário: a biblioteca grava de volta
        cookie["name"],
        cookie["key"],
        cookie["expiry_days"],
        validator=_Validador(),
        password_instructions=REGRAS_SENHA,
    )
    _marcar_login_vazio(autenticador)
    return autenticador


def _marcar_login_vazio(autenticador):
    """Marca na sessão quando Entrar é clicado com usuário ou senha em branco.

    A biblioteca devolve None nesse caso, o mesmo valor de "ninguém clicou",
    e a tela ficava muda. O formulário é dela, então a única forma de saber
    do clique é olhar a chamada que ela faz ao controlador. A outra chamada,
    com token, vem do cookie e não passa por aqui como clique.
    """
    controlador = autenticador.authentication_controller
    original = controlador.login

    def login(username=None, password=None, *args, token=None, **kwargs):
        if token is None and not (username and password and password.strip()):
            st.session_state["pc_login_vazio"] = True
        return original(username, password, *args, token=token, **kwargs)

    controlador.login = login


def tela_de_entrada(autenticador, capa=None):
    """Desenha login e cadastro. Devolve o usuário logado, ou None.

    Enquanto ninguém está logado, esta função ocupa a tela inteira. Quem chama
    deve parar a execução quando o retorno for None. `capa`, se vier, desenha
    a coluna da direita: no app, o mapa da região.
    """
    # Primeiro tenta reaproveitar o cookie, sem desenhar nada na tela. É o que
    # o modo "unrendered" faz. Sem esta chamada, o formulário de login seria
    # desenhado antes de a sessão ser recuperada, e a página apareceria com a
    # tela de login e a tela de quem está logado ao mesmo tempo.
    autenticador.login(location="unrendered")
    if st.session_state.get("authentication_status"):
        return st.session_state["username"]

    formulario, direita = st.columns([1, 1.5], gap="large")
    if capa is not None:
        with direita:
            capa()

    with formulario:
        st.html(
            '<div class="pc-marca">Peanut<i>Cast</i></div>'
            '<div class="pc-titulo">Onde plantar não devia ser palpite.</div>'
            '<p class="pc-tag">Rendimento esperado do amendoim, município a município, '
            "antes do plantio.</p>"
        )
        _formularios(autenticador)

    # Se a senha acabou de ser aceita, recarrega em vez de devolver o usuário.
    # O formulário já foi desenhado acima neste mesmo ciclo, então devolver
    # aqui deixaria a página com a tela de login em cima e a tela de quem está
    # logado embaixo. No ciclo seguinte o login "unrendered" lá em cima
    # reconhece a sessão e nada disso é desenhado.
    if st.session_state.get("authentication_status"):
        st.rerun()
    return None


def _formularios(autenticador):
    aba_entrar, aba_cadastrar = st.tabs(["Entrar", "Criar conta"])

    with aba_entrar:
        autenticador.login(fields=CAMPOS_LOGIN)
        if st.session_state.pop("pc_login_vazio", False):
            st.error("Preencha usuário e senha.")
        elif st.session_state.get("authentication_status") is False:
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
            # inválido por exceção. Mostrar a mensagem é melhor que engolir;
            # a de senha já vem em português do _Validador, as outras daqui.
            st.error(_ERROS_CADASTRO.get(str(erro), str(erro)))


def nome_de_quem_entrou():
    return st.session_state.get("name") or st.session_state.get("username") or ""


def sair(autenticador):
    """Encerra a sessão. O botão Sair fica no painel, que chama esta função.

    O modo "unrendered" da biblioteca faz o logout sem desenhar botão. Ela
    zera authentication_status mas não recarrega a página, então o resto do
    script continuaria desenhando a tela de quem está logado. O rerun faz o
    Sair valer no mesmo clique.

    Isso só é seguro porque expiry_days está em 0 e não existe cookie a
    apagar. Com cookie, o rerun cortaria o componente que manda a instrução
    de remoção para o navegador, e o usuário sairia sem sair de verdade.

    No terminal aparece "peanutcast_sessao" a cada logout. É a biblioteca
    tentando apagar um cookie que nunca foi criado e imprimindo o erro em vez
    de ignorá-lo. Não quebra nada.
    """
    autenticador.logout(location="unrendered")
    st.rerun()
