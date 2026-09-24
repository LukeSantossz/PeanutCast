"""Onde cada coisa fica no disco.

Um módulo só para caminhos evita que cada arquivo monte o seu próprio e faz o
app rodar igual de qualquer diretório, porque tudo parte da posição deste
arquivo e não do diretório atual.
"""
from pathlib import Path

# Este arquivo está em peanutcast/, então a raiz do projeto é a pasta de cima.
RAIZ = Path(__file__).resolve().parent.parent

DADOS = RAIZ / "dados"
DADOS_BRUTOS = DADOS / "brutos"        # o que sai do IBGE e da NASA, sem tratamento
DADOS_TRATADOS = DADOS / "tratados"    # a tabela integrada, pronta para treinar
MODELOS = RAIZ / "modelos"             # modelos treinados e serializados

IBGE_PAM = DADOS_BRUTOS / "ibge_pam.csv"            # SIDRA 1612, formato longo
CENTROIDES = DADOS_BRUTOS / "centroides.csv"        # latitude e longitude por município
MALHAS = DADOS_BRUTOS / "municipios.geojson"        # contorno dos municípios, para o mapa
NASA_POWER = DADOS_BRUTOS / "nasa_power"            # um CSV diário por município
DATASET = DADOS_TRATADOS / "dataset.csv"            # produção + clima, uma linha por município e ano
CLIMA_SAFRAS = DADOS_TRATADOS / "clima_safras.csv"  # clima de todas as safras, com ou sem amendoim

CREDENCIAIS = RAIZ / "credenciais.yaml"
FAVORITOS = DADOS / "favoritos.json"


def garantir_pastas():
    """Cria as pastas de trabalho se ainda não existirem.

    Chamado na abertura do app para ninguém precisar criar pasta à mão. As
    pastas ficam fora do Git, então cada máquina cria as suas.
    """
    for pasta in (DADOS_BRUTOS, NASA_POWER, DADOS_TRATADOS, MODELOS):
        pasta.mkdir(parents=True, exist_ok=True)
