"""
Verificacao de versao do PJe-Calc.

O risco aqui nao e quebrar: e mentir. Um falso "esta em dia" deixa a instalacao
velha entregando numero velho por meses; um falso alarme todo mes treina quem
le a ignorar o aviso.
"""
import importlib.util
import os
import sys
import unittest
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "verificar_versao", os.path.join(RAIZ, "scripts", "verificar-versao.py"))
vv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vv)

PAGINA_PORTAL = """
<p class="rtejustify">texto antes</p>
<h3 class="rtejustify">Vers&atilde;o Atual: <strong>2.16.0</strong><br />
Dispon&iacute;vel desde: <strong>25/06/2026</strong></h3>
""".replace("&atilde;", "ã").replace("&iacute;", "í")

PAGINA_APP = 'alt="Versao">Vers&atilde;o: 2.16.0</span>'


class TestLeituraDoPortal(unittest.TestCase):
    def ler(self, html):
        with mock.patch.object(vv.urllib.request, "urlopen") as m:
            m.return_value.__enter__.return_value.read.return_value = html.encode()
            return vv.versao_do_portal()

    def test_extrai_versao_e_data(self):
        self.assertEqual(self.ler(PAGINA_PORTAL), ("2.16.0", "25/06/2026"))

    def test_portal_mudou_de_formato_falha_alto(self):
        """Sem o trecho esperado tem que estourar, nao devolver palpite."""
        with self.assertRaises(ValueError):
            self.ler("<h3>Nenhuma informacao de versao aqui</h3>")


class TestVersaoInstalada(unittest.TestCase):
    """
    A origem e conferida por igualdade, nao por `in`: "arquivo VERSAO
    (aplicacao fora do ar)" tambem contem a palavra "aplicacao", e um `in`
    aprovaria o fallback achando que era o caminho preferido.
    """

    def test_prefere_a_aplicacao_rodando(self):
        # o arquivo existe e diz outra coisa: se for lido, o teste acusa
        with mock.patch.object(vv.urllib.request, "urlopen") as m, \
             mock.patch.object(vv.os.path, "exists", return_value=True), \
             mock.patch("builtins.open", mock.mock_open(read_data="1.0.0\n")):
            m.return_value.__enter__.return_value.read.return_value = PAGINA_APP.encode("latin-1")
            versao, origem = vv.versao_instalada()
        self.assertEqual(versao, "2.16.0")
        self.assertEqual(origem, "aplicacao rodando")

    def test_cai_no_arquivo_quando_a_aplicacao_esta_fora(self):
        with mock.patch.object(vv.urllib.request, "urlopen", side_effect=OSError), \
             mock.patch.object(vv.os.path, "exists", return_value=True), \
             mock.patch("builtins.open", mock.mock_open(read_data="2.15.1\n")):
            versao, origem = vv.versao_instalada()
        self.assertEqual(versao, "2.15.1")
        self.assertTrue(origem.startswith("arquivo VERSAO"), origem)

    def test_sem_nenhuma_das_duas_devolve_vazio(self):
        with mock.patch.object(vv.urllib.request, "urlopen", side_effect=OSError), \
             mock.patch.object(vv.os.path, "exists", return_value=False):
            self.assertEqual(vv.versao_instalada(), (None, None))


class TestComparacao(unittest.TestCase):
    def rodar(self, instalada, portal):
        with mock.patch.object(vv, "versao_instalada", return_value=(instalada, "teste")), \
             mock.patch.object(vv, "versao_do_portal", return_value=(portal, "01/01/2026")):
            return vv.main()

    def test_igual_esta_em_dia(self):
        self.assertEqual(self.rodar("2.16.0", "2.16.0"), 0)

    def test_instalada_menor_avisa(self):
        self.assertEqual(self.rodar("2.15.1", "2.16.0"), 1)

    def test_salto_de_versao_maior(self):
        self.assertEqual(self.rodar("2.16.0", "3.0.0"), 1)

    def test_instalada_maior_nao_avisa(self):
        """Instalacao a frente do portal (pre-release) nao e motivo de alarme."""
        self.assertEqual(self.rodar("2.17.0", "2.16.0"), 0)

    def test_comparacao_e_numerica_nao_textual(self):
        """'2.9.0' vs '2.10.0': por texto, '9' > '1' e o aviso nunca sairia."""
        self.assertEqual(self.rodar("2.9.0", "2.10.0"), 1)

    def test_fonte_truncada_compara_o_que_da(self):
        """Se a instalada vier so como 2.16, nao pode acusar 2.16.0 de ser nova."""
        self.assertEqual(self.rodar("2.16", "2.16.0"), 0)
        self.assertEqual(self.rodar("2.16", "2.17.0"), 1)


class TestFalhas(unittest.TestCase):
    def test_versao_instalada_desconhecida_sai_2(self):
        with mock.patch.object(vv, "versao_instalada", return_value=(None, None)):
            self.assertEqual(vv.main(), 2)

    def test_portal_inacessivel_sai_2(self):
        """Nao pode sair 0: 'nao consegui verificar' nao e 'esta em dia'."""
        with mock.patch.object(vv, "versao_instalada", return_value=("2.16.0", "teste")), \
             mock.patch.object(vv, "versao_do_portal", side_effect=OSError("sem rede")):
            self.assertEqual(vv.main(), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
