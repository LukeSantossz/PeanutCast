"""Previsão sazonal do CPTEC: qual emissão vale, como ler a grade e o tercil."""
import math
from datetime import date

import numpy as np
import pytest

from peanutcast import boletim


def test_so_setembro_e_outubro_cobrem_dez_a_fev():
    assert boletim.figura_djf(2026, 9) == (2, 2027)
    assert boletim.figura_djf(2026, 10) == (1, 2027)
    for mes in (1, 2, 3, 6, 8, 11, 12):
        assert boletim.figura_djf(2026, mes) is None


@pytest.mark.parametrize("hoje", [date(2026, 7, 20), date(2026, 11, 4), date(2027, 1, 15), date(2027, 2, 28)])
def test_candidatos_sao_outubro_e_setembro_da_safra_que_nao_acabou(hoje):
    assert boletim.candidatos(hoje) == [(2026, 10), (2026, 9)]


def test_em_marco_a_safra_alvo_vira():
    assert boletim.safra_alvo(date(2027, 3, 1)) == 2028
    assert boletim.candidatos(date(2027, 3, 1)) == [(2027, 10), (2027, 9)]


def test_previsao_de_safra_passada_nao_vale():
    assert boletim.vigente({"safra": 2027}, date(2026, 11, 4))
    assert not boletim.vigente({"safra": 2027}, date(2027, 3, 2))


def test_latitudes_gaussianas_do_sul_para_o_norte():
    lat = boletim.latitudes()
    assert len(lat) == boletim.NLAT == 192
    assert lat[0] == pytest.approx(-89.28423, abs=1e-5)
    assert lat[-1] == pytest.approx(89.28423, abs=1e-5)
    # Valores do pacote cptec-sazonal em torno do equador.
    assert lat[95] == pytest.approx(-0.46753, abs=1e-5)
    assert lat[96] == pytest.approx(0.46753, abs=1e-5)
    assert lat[94] == pytest.approx(-1.40259, abs=1e-5)


def test_ler_grade_troca_ausente_por_nan():
    bruto = np.zeros((192, 384), dtype="<f4")
    bruto[0, 0] = -9.99e8
    bruto[1, 1] = 0.4
    grade = boletim.ler_grade(bruto.tobytes())
    assert grade.shape == (192, 384)
    assert math.isnan(grade[0, 0])
    assert grade[1, 1] == pytest.approx(0.4)


def test_ler_grade_recusa_tamanho_errado():
    with pytest.raises(ValueError):
        boletim.ler_grade(b"\0" * 100)


def test_tercil():
    assert boletim.tercil(-0.45) == ("Seco", 0.45)
    assert boletim.tercil(0.42) == ("Chuvoso", 0.42)
    assert boletim.tercil(0.0) == ("Normal", None)
    assert boletim.tercil(float("nan")) is None


def test_cada_municipio_le_a_celula_mais_proxima():
    lat, lon = boletim.latitudes(), boletim.longitudes()
    grade = np.zeros((192, 384), dtype="f4")
    # Marília fica perto de (-22.2, -49.9): célula de -22.0 e 310.3125 (= -49.6875).
    i = int(np.argmin(abs(lat - -22.2)))
    j = int(np.argmin(abs(lon - (360 - 49.9))))
    grade[i, j] = -0.5
    grade[i, j + 1] = 0.6
    leitura = boletim.por_municipio(grade, {1: (-49.9, -22.2), 2: (lon[j + 1] - 360, lat[i])})
    assert leitura == {1: ("Seco", 0.5), 2: ("Chuvoso", pytest.approx(0.6))}


def test_cenario_da_regiao_e_a_maioria_e_empate_e_normal():
    assert boletim.cenario_regiao(["Chuvoso", "Chuvoso", "Seco"]) == "Chuvoso"
    assert boletim.cenario_regiao(["Chuvoso", "Seco"]) == "Normal"
    assert boletim.cenario_regiao(["Seco", "Seco", "Normal", "Normal", "Chuvoso"]) == "Normal"
    assert boletim.cenario_regiao([]) is None


def test_resumo_para_o_painel():
    lat, lon = boletim.latitudes(), boletim.longitudes()
    grade = np.full((192, 384), 0.45, dtype="f4")
    origem = {"emissao": [2026, 9], "figura": 2, "safra": 2027}
    r = boletim.resumo(grade, origem, {3500105: (lon[300] - 360, lat[70]), 3500204: (lon[301] - 360, lat[70])})
    assert r["cenario"] == "Chuvoso"
    assert r["safra"] == 2027
    assert r["janela"] == "dez/2026 a fev/2027"
    assert r["emissao"] == "set/2026"
    assert r["municipios"]["3500105"] == {"cen": "Chuvoso", "prob": pytest.approx(0.45)}
