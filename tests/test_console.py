"""A saida do terminal, que e contrato com quem le a rodada.

Duas coisas aqui nao sao enfeite: a linha 'Pasta :', que o rodada-mensal.sh le
com sed para montar o aviso, e a recusa de pedir ENTER quando nao ha terminal —
sem isso a unidade do systemd ficaria esperando para sempre uma tecla que nao vem.
"""

import io
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pjecalc.model.indice import Indice
from pjecalc.model.tabela import Tabela
from pjecalc.view.console import Console

TR = Indice("TR", "TR", "01/1967", "12/2026", "id1", "id2", "id3")


class EntradaFalsa(io.StringIO):
    def __init__(self, com_terminal):
        super().__init__()
        self._com_terminal = com_terminal

    def isatty(self):
        return self._com_terminal


def console(com_terminal=False):
    saida = io.StringIO()
    return Console(saida=saida, entrada=EntradaFalsa(com_terminal)), saida


def tabela_com(quantidade, primeira="11/2026"):
    tabela = Tabela()
    tabela.estender([{"Mês/Ano": primeira}]
                    + [{"Mês/Ano": f"{i:02d}/2020"} for i in range(1, quantidade)])
    return tabela


class TestRelatorio(unittest.TestCase):
    def relatorio(self, tabela, pasta="/casa/output/06-11-2026"):
        tela, saida = console()
        arquivo = Path(pasta) / "indices_TR_TRT8_06-11-2026.xlsx"
        tela.relatorio([(TR, tabela, arquivo)], pasta)
        return saida.getvalue()

    def test_a_linha_da_pasta_sai_como_o_script_le(self):
        """O rodada-mensal.sh faz: sed -n 's/^ *Pasta : //p'."""
        linhas = [l for l in self.relatorio(tabela_com(3)).splitlines()
                  if l.strip().startswith("Pasta :")]
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0].split("Pasta : ")[1], "/casa/output/06-11-2026")

    def test_mostra_quantidade_arquivo_e_mes_mais_recente(self):
        texto = self.relatorio(tabela_com(3))
        self.assertIn("TR", texto)
        self.assertIn("3 registros", texto)
        self.assertIn("indices_TR_TRT8_06-11-2026.xlsx", texto)
        self.assertIn("ate 11/2026", texto)

    def test_tabela_vazia_e_anunciada_como_tal(self):
        """Zero registro nao pode sair parecendo rodada normal."""
        self.assertIn("sem dados", self.relatorio(Tabela()))


class TestIntervencaoManual(unittest.TestCase):
    def test_sem_terminal_falha_em_vez_de_esperar(self):
        tela, _ = console(com_terminal=False)
        with self.assertRaises(RuntimeError) as capturado:
            tela.intervencao("Clique em 'Pesquisar' na tela.")
        self.assertIn("Pesquisar", str(capturado.exception))

    def test_o_pedido_fica_registrado_antes_de_falhar(self):
        """Quem for ler o journal depois precisa saber qual etapa parou."""
        tela, saida = console(com_terminal=False)
        with self.assertRaises(RuntimeError):
            tela.intervencao("Selecione 'TRT 8a Região' na tela.")
        self.assertIn("TRT 8a Região", saida.getvalue())


class TestCarimbo(unittest.TestCase):
    def test_toda_linha_leva_hora_e_marcador(self):
        tela, saida = console()
        tela.ok("pronto")
        tela.erro("quebrou")
        linhas = saida.getvalue().splitlines()
        self.assertRegex(linhas[0], r"^  \[\d{2}:\d{2}:\d{2}\]\[ OK\] pronto$")
        self.assertRegex(linhas[1], r"^  \[\d{2}:\d{2}:\d{2}\]\[ERR\] quebrou$")


if __name__ == "__main__":
    unittest.main(verbosity=2)
