"""Baixa os dados brutos do IBGE, da NASA POWER e do CPTEC para dados/brutos/.

Rodar da raiz do projeto ou de qualquer lugar:

    python scripts/coletar.py            baixa só o que ainda não existe
    python scripts/coletar.py --forcar   baixa tudo de novo

A NASA POWER leva alguns segundos por município, então o que já foi baixado é
reaproveitado. Use --forcar quando mudar o recorte de anos em fontes.py.
"""
import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

# O script mora em scripts/, e o pacote peanutcast/ está na pasta de cima.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from peanutcast import boletim, caminhos, fontes  # noqa: E402
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


def coletar_malhas(forcar):
    if caminhos.MALHAS.exists() and not forcar:
        print(f"Malhas: já existem, pulando ({caminhos.MALHAS.name})")
        return
    print("Malhas: baixando o contorno dos municípios...")
    colecao = {"type": "FeatureCollection", "features": [fontes.baixar_malha(c) for c in MUNICIPIOS]}
    caminhos.MALHAS.write_text(json.dumps(colecao), encoding="utf-8")
    registrar_origem(caminhos.MALHAS, "IBGE, API de malhas v3 (GeoJSON, qualidade intermediária)")


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


def coletar_cptec(forcar, hoje=None):
    """Previsão sazonal de dez a fev: a emissão de outubro, senão a de setembro.

    Fora da época (março a meados de outubro) nenhuma das duas existe e nada é
    gravado; o painel abre no cenário normal.
    """
    hoje = hoje or date.today()
    origem_arquivo = Path(f"{caminhos.CPTEC_SAZONAL}.origem.json")
    if caminhos.CPTEC_SAZONAL.exists() and origem_arquivo.exists() and not forcar:
        origem = json.loads(origem_arquivo.read_text(encoding="utf-8"))
        if boletim.vigente(origem, hoje) and tuple(origem["emissao"]) == boletim.candidatos(hoje)[0]:
            print("CPTEC: previsão de outubro já existe, pulando")
            return
    for ano, mes in boletim.candidatos(hoje):
        figura, safra = boletim.figura_djf(ano, mes)
        url = boletim.URL.format(ano=ano, mes=mes, figura=figura)
        print(f"CPTEC: tentando a emissão de {mes:02d}/{ano}...")
        bruto = fontes.baixar_cptec(url)
        if bruto is None:
            continue
        boletim.ler_grade(bruto)  # confere o tamanho antes de gravar
        caminhos.CPTEC_SAZONAL.write_bytes(bruto)
        origem = {
            "fonte": "CPTEC/INPE, BAM-1.2 calibrado, probabilidade do tercil de chuva",
            "baixado_em": datetime.now().isoformat(timespec="seconds"),
            "emissao": [ano, mes],
            "figura": figura,
            "safra": safra,
            "janela": f"dez/{safra - 1} a fev/{safra}",
            "url": url,
        }
        origem_arquivo.write_text(json.dumps(origem, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"CPTEC: previsão de dez/{safra - 1} a fev/{safra} gravada (emissão {mes:02d}/{ano})")
        return
    print("CPTEC: previsão de dez a fev ainda não saiu (sai em meados de outubro)")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--forcar", action="store_true", help="baixa tudo de novo")
    args = parser.parse_args()

    caminhos.garantir_pastas()
    coletar_pam(args.forcar)
    centroides = coletar_centroides(args.forcar)
    coletar_malhas(args.forcar)
    coletar_clima(centroides, args.forcar)
    coletar_cptec(args.forcar)
    print("Coleta concluída.")


if __name__ == "__main__":
    main()
