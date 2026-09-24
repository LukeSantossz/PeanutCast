"""Baixa os dados brutos do IBGE e da NASA POWER para dados/brutos/.

Rodar da raiz do projeto ou de qualquer lugar:

    python scripts/coletar.py            baixa só o que ainda não existe
    python scripts/coletar.py --forcar   baixa tudo de novo

A NASA POWER leva alguns segundos por município, então o que já foi baixado é
reaproveitado. Use --forcar quando mudar o recorte de anos em fontes.py.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# O script mora em scripts/, e o pacote peanutcast/ está na pasta de cima.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from peanutcast import caminhos, fontes  # noqa: E402
from peanutcast.municipios import MUNICIPIOS  # noqa: E402


def registrar_origem(arquivo, fonte):
    """Grava ao lado do arquivo bruto de onde e quando ele veio."""
    origem = {
        "fonte": fonte,
        "baixado_em": datetime.now().isoformat(timespec="seconds"),
        "anos": [fontes.ANO_INICIAL, fontes.ANO_FINAL],
    }
    Path(f"{arquivo}.origem.json").write_text(
        json.dumps(origem, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def coletar_pam(forcar):
    if caminhos.IBGE_PAM.exists() and not forcar:
        print(f"IBGE/PAM: já existe, pulando ({caminhos.IBGE_PAM.name})")
        return
    print("IBGE/PAM: baixando a tabela 1612...")
    pam = fontes.baixar_pam(MUNICIPIOS)
    pam.to_csv(caminhos.IBGE_PAM, index=False)
    registrar_origem(caminhos.IBGE_PAM, f"IBGE/SIDRA, tabela {fontes.SIDRA_TABELA}")
    print(f"IBGE/PAM: {len(pam)} valores gravados")


def coletar_centroides(forcar):
    if caminhos.CENTROIDES.exists() and not forcar:
        print(f"Centroides: já existem, pulando ({caminhos.CENTROIDES.name})")
        return pd.read_csv(caminhos.CENTROIDES)
    print("Centroides: consultando a API de malhas do IBGE...")
    linhas = []
    for codigo in MUNICIPIOS:
        latitude, longitude = fontes.baixar_centroide(codigo)
        linhas.append({"codigo_ibge": codigo, "latitude": latitude, "longitude": longitude})
    centroides = pd.DataFrame(linhas)
    centroides.to_csv(caminhos.CENTROIDES, index=False)
    registrar_origem(caminhos.CENTROIDES, "IBGE, API de malhas v3 (metadados)")
    return centroides


def coletar_clima(centroides, forcar):
    for linha in centroides.itertuples():
        nome = MUNICIPIOS[linha.codigo_ibge]
        arquivo = caminhos.NASA_POWER / f"{linha.codigo_ibge}.csv"
        if arquivo.exists() and not forcar:
            print(f"NASA POWER: {nome} já existe, pulando")
            continue
        print(f"NASA POWER: {nome}...")
        clima = fontes.baixar_clima_diario(linha.latitude, linha.longitude)
        clima.to_csv(arquivo)
        registrar_origem(
            arquivo,
            f"NASA POWER, diário, comunidade AG, ponto ({linha.latitude}, {linha.longitude})",
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--forcar", action="store_true", help="baixa tudo de novo")
    args = parser.parse_args()

    caminhos.garantir_pastas()
    coletar_pam(args.forcar)
    centroides = coletar_centroides(args.forcar)
    coletar_clima(centroides, args.forcar)
    print("Coleta concluída.")


if __name__ == "__main__":
    main()
