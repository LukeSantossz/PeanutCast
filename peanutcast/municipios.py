"""Lista de municípios da Alta Paulista atendidos pelo PeanutCast.

Fechada na dependência 1 da Semana 1: os 24 municípios das microrregiões de
Marília, Tupã e Adamantina com rendimento de amendoim publicado no
IBGE/SIDRA-PAM. Bastos saiu, porque o IBGE não registra amendoim lá desde 2007.

A lista fica escrita aqui, e não é lida do dataset, porque é ela que diz à
coleta o que baixar. O dataset é consequência dela, não o contrário.
"""

# Código IBGE de 7 dígitos como chave, nunca o nome: a acentuação varia entre
# fontes (o IBGE escreve "Pompéia", com acento) e a junção quebraria em silêncio.
MUNICIPIOS = {
    3500105: "Adamantina",
    3503356: "Arco-Íris",
    3514700: "Echaporã",
    3515806: "Flora Rica",
    3516002: "Flórida Paulista",
    3516705: "Garça",
    3519006: "Herculândia",
    3519204: "Iacri",
    3527405: "Lucélia",
    3527801: "Lupércio",
    3528908: "Mariápolis",
    3529005: "Marília",
    3533700: "Ocauçu",
    3534104: "Oriente",
    3534500: "Oscar Bressane",
    3534906: "Pacaembu",
    3536000: "Parapuã",
    3540002: "Pompéia",
    3542008: "Quintana",
    3543808: "Rinópolis",
    3544707: "Sagres",
    3545100: "Salmourão",
    3555000: "Tupã",
    3556602: "Vera Cruz",
}

NOMES = sorted(MUNICIPIOS.values())
