"""
Datas e nomes de arquivo do busca_indices_rpa.

A regra de negocio e: TR no mes seguinte ao da execucao, IPCA-E no corrente.
Errar isso nao quebra nada visivelmente — a planilha so sai com um mes a menos,
que e exatamente o tipo de falha que passa despercebida por meses.
"""
import importlib
import os
import re
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def recarregar(**env):
    """Recarrega o modulo com o ambiente dado, isolando as variaveis."""
    anterior = {}
    for k in ("PJECALC_TR_ATE", "PJECALC_IPCAE_ATE", "PJECALC_PORTA", "PJECALC_DEBUG"):
        anterior[k] = os.environ.pop(k, None)
    os.environ.update({k: v for k, v in env.items() if v is not None})
    try:
        import busca_indices_rpa
        return importlib.reload(busca_indices_rpa)
    finally:
        for k, v in anterior.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v


class TestMesAno(unittest.TestCase):
    def setUp(self):
        self.mod = recarregar()

    def test_mes_normal(self):
        self.assertEqual(self.mod._mes_ano(2026, 10), "10/2026")

    def test_virada_de_ano(self):
        """Dezembro + 1 tem que virar janeiro do ano seguinte, nao '13/2026'."""
        self.assertEqual(self.mod._mes_ano(2026, 13), "01/2027")

    def test_dois_meses_adiante_da_virada(self):
        self.assertEqual(self.mod._mes_ano(2026, 14), "02/2027")

    def test_sempre_com_dois_digitos(self):
        self.assertEqual(self.mod._mes_ano(2027, 1), "01/2027")


class TestConfigIndices(unittest.TestCase):
    def test_tr_e_o_mes_seguinte_ipcae_o_corrente(self):
        mod = recarregar()
        hoje = datetime.now()
        self.assertEqual(mod.CONFIG_INDICES["IPCAE"]["tabela_de"],
                         f"{hoje.month:02d}/{hoje.year}")
        self.assertEqual(mod.CONFIG_INDICES["TR"]["tabela_de"],
                         mod._mes_ano(hoje.year, hoje.month + 1))

    def test_inicio_das_series_nao_muda(self):
        mod = recarregar()
        self.assertEqual(mod.CONFIG_INDICES["TR"]["a_partir"], "01/1967")
        self.assertEqual(mod.CONFIG_INDICES["IPCAE"]["a_partir"], "01/1992")

    def test_env_sobrescreve(self):
        mod = recarregar(PJECALC_TR_ATE="03/2027", PJECALC_IPCAE_ATE="02/2027")
        self.assertEqual(mod.CONFIG_INDICES["TR"]["tabela_de"], "03/2027")
        self.assertEqual(mod.CONFIG_INDICES["IPCAE"]["tabela_de"], "02/2027")


class TestSaida(unittest.TestCase):
    def setUp(self):
        self.mod = recarregar()

    def test_pasta_tem_a_data_com_hifens(self):
        self.assertRegex(self.mod.DATA_RODADA, r"^\d{2}-\d{2}-\d{4}$")
        self.assertTrue(self.mod.PASTA_RODADA.endswith(self.mod.DATA_RODADA))

    def test_planilhas_ficam_dentro_da_pasta_da_rodada(self):
        for arq in (self.mod.ARQ_TR, self.mod.ARQ_IPCAE):
            self.assertEqual(os.path.dirname(arq), self.mod.PASTA_RODADA)
            self.assertIn(self.mod.DATA_RODADA, os.path.basename(arq))

    def test_perfil_do_firefox_fica_fora_da_pasta_da_rodada(self):
        """Se o perfil entrasse na pasta da rodada, cada mes baixaria tudo de novo."""
        self.assertEqual(os.path.dirname(self.mod.PASTA_RODADA), self.mod.OUTPUT_DIR)


class TestDebug(unittest.TestCase):
    def test_desligado_por_padrao(self):
        self.assertFalse(recarregar().DEBUG)

    def test_ligado_pela_env(self):
        self.assertTrue(recarregar(PJECALC_DEBUG="1").DEBUG)


class TestPorta(unittest.TestCase):
    def test_padrao(self):
        mod = recarregar()
        self.assertEqual(mod.PORTA, 9257)
        self.assertIn("9257", mod.HOME)

    def test_env_sobrescreve(self):
        self.assertEqual(recarregar(PJECALC_PORTA="8080").PORTA, 8080)


if __name__ == "__main__":
    unittest.main(verbosity=2)
