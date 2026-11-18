"""Datas, configuracao e nomes de arquivo da rodada.

A regra de negocio e: TR no mes seguinte ao da execucao, IPCA-E no corrente.
Errar isso nao quebra nada visivelmente — a planilha so sai com um mes a menos,
que e exatamente o tipo de falha que passa despercebida por meses.
"""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pjecalc.config import Configuracao
from pjecalc.model.competencia import e_competencia, mes_ano
from pjecalc.model.indice import catalogo


def configurar(agora=None, **env):
    """Configuracao a partir de um ambiente controlado, sem tocar no real."""
    return Configuracao.do_ambiente(env=env, agora=agora)


def indices(config):
    return {indice.nome: indice for indice in catalogo(config)}


class TestMesAno(unittest.TestCase):
    def test_mes_normal(self):
        self.assertEqual(mes_ano(2026, 10), "10/2026")

    def test_virada_de_ano(self):
        """Dezembro + 1 tem que virar janeiro do ano seguinte, nao '13/2026'."""
        self.assertEqual(mes_ano(2026, 13), "01/2027")

    def test_dois_meses_adiante_da_virada(self):
        self.assertEqual(mes_ano(2026, 14), "02/2027")

    def test_sempre_com_dois_digitos(self):
        self.assertEqual(mes_ano(2027, 1), "01/2027")

    def test_reconhece_competencia(self):
        self.assertTrue(e_competencia("01/1967"))
        self.assertTrue(e_competencia("  11/2026 "))

    def test_recusa_o_que_nao_e_competencia(self):
        for texto in ("Mês/Ano", "1/2026", "11/26", "", "0,1234"):
            self.assertFalse(e_competencia(texto), texto)


class TestIndices(unittest.TestCase):
    def test_tr_e_o_mes_seguinte_ipcae_o_corrente(self):
        config = configurar(agora=datetime(2026, 11, 6))
        self.assertEqual(indices(config)["TR"].ate, "12/2026")
        self.assertEqual(indices(config)["IPCAE"].ate, "11/2026")

    def test_em_dezembro_a_tr_pede_janeiro_do_ano_seguinte(self):
        config = configurar(agora=datetime(2026, 12, 6))
        self.assertEqual(indices(config)["TR"].ate, "01/2027")
        self.assertEqual(indices(config)["IPCAE"].ate, "12/2026")

    def test_acompanha_o_relogio_quando_ninguem_manda(self):
        hoje = datetime.now()
        config = configurar()
        self.assertEqual(indices(config)["IPCAE"].ate, f"{hoje.month:02d}/{hoje.year}")
        self.assertEqual(indices(config)["TR"].ate, mes_ano(hoje.year, hoje.month + 1))

    def test_inicio_das_series_nao_muda(self):
        config = configurar()
        self.assertEqual(indices(config)["TR"].a_partir, "01/1967")
        self.assertEqual(indices(config)["IPCAE"].a_partir, "01/1992")

    def test_env_sobrescreve(self):
        config = configurar(PJECALC_TR_ATE="03/2027", PJECALC_IPCAE_ATE="02/2027")
        self.assertEqual(indices(config)["TR"].ate, "03/2027")
        self.assertEqual(indices(config)["IPCAE"].ate, "02/2027")

    def test_ids_jsf_sao_diferentes_entre_as_abas(self):
        """O PJe-Calc poe 'Indice' no id da TR e nao poe no da IPCA-E; copiar um
        do outro faz o preenchimento cair no fallback sem ninguem notar."""
        tr, ipcae = indices(configurar())["TR"], indices(configurar())["IPCAE"]
        self.assertIn("IndiceTR", tr.id_ate)
        self.assertNotIn("Indice", ipcae.id_ate)
        self.assertNotEqual(tr.id_pesquisar, ipcae.id_pesquisar)


class TestSaida(unittest.TestCase):
    def setUp(self):
        self.config = configurar(agora=datetime(2027, 1, 6))

    def test_pasta_tem_a_data_com_hifens(self):
        self.assertEqual(self.config.data_rodada, "06-01-2027")
        self.assertEqual(self.config.pasta_rodada.name, "06-01-2027")

    def test_planilhas_ficam_dentro_da_pasta_da_rodada(self):
        for indice in catalogo(self.config):
            arquivo = self.config.planilha(indice)
            self.assertEqual(arquivo.parent, self.config.pasta_rodada)
            self.assertIn(self.config.data_rodada, arquivo.name)
            self.assertTrue(arquivo.name.endswith(".xlsx"))

    def test_cada_indice_tem_o_seu_arquivo(self):
        nomes = {self.config.planilha(i).name for i in catalogo(self.config)}
        self.assertEqual(len(nomes), len(catalogo(self.config)))

    def test_perfil_do_firefox_fica_fora_da_pasta_da_rodada(self):
        """Se o perfil entrasse na pasta da rodada, cada mes baixaria tudo de novo."""
        self.assertEqual(self.config.perfil_firefox.parent, self.config.saida)
        self.assertNotEqual(self.config.perfil_firefox.parent, self.config.pasta_rodada)


class TestDebug(unittest.TestCase):
    def test_desligado_por_padrao(self):
        self.assertFalse(configurar().debug)

    def test_ligado_pela_env(self):
        self.assertTrue(configurar(PJECALC_DEBUG="1").debug)


class TestJanelaDoNavegador(unittest.TestCase):
    """Num servidor nao ha display: o padrao tem que ser sem janela."""

    def test_sem_display_roda_sem_janela(self):
        self.assertTrue(configurar().sem_janela)

    def test_com_display_mantem_a_janela(self):
        self.assertFalse(configurar(DISPLAY=":0").sem_janela)

    def test_com_wayland_mantem_a_janela(self):
        self.assertFalse(configurar(WAYLAND_DISPLAY="wayland-1").sem_janela)

    def test_env_vence_o_padrao(self):
        self.assertTrue(configurar(DISPLAY=":0", PJECALC_FF_HEADLESS="1").sem_janela)
        self.assertFalse(configurar(PJECALC_FF_HEADLESS="0").sem_janela)


class TestPorta(unittest.TestCase):
    def test_padrao(self):
        config = configurar()
        self.assertEqual(config.porta, 9257)
        self.assertIn("9257", config.home)

    def test_env_sobrescreve(self):
        self.assertEqual(configurar(PJECALC_PORTA="8080").porta, 8080)
        self.assertIn("8080", configurar(PJECALC_PORTA="8080").home)


if __name__ == "__main__":
    unittest.main(verbosity=2)
