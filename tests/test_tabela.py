"""A tabela de indices: deduplicacao, cabecalhos e o que e linha de dado.

Essa logica vivia no meio do laco de paginacao e nunca foi testada. Ela decide
duas coisas caras: se a planilha sai com linhas repetidas e se o laco percebe
que chegou ao fim da paginacao.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pjecalc.model.tabela import COLUNAS_PADRAO, Tabela

CABECALHO = ["Mês/Ano", "Taxa do Mês(%)", "Índice Acumulado", "Criado Em"]
LINHA_TR = ["11/2026", "0,0000", "1,0000000", "04/11/2026"]
LINHA_ANTERIOR = ["10/2026", "0,0000", "1,0000000", "08/10/2026"]


def tabela_com(*linhas):
    tabela = Tabela(colunas=list(CABECALHO))
    tabela.estender([tabela.registro(linha) for linha in linhas])
    return tabela


class TestLinhaDeDado(unittest.TestCase):
    def test_linha_que_comeca_por_competencia(self):
        self.assertTrue(Tabela.e_linha_de_dado(LINHA_TR))

    def test_cabecalho_repetido_no_meio_da_paginacao(self):
        """O modal reimprime o cabecalho a cada pagina; ele nao vira linha."""
        self.assertFalse(Tabela.e_linha_de_dado(CABECALHO))

    def test_linha_vazia(self):
        self.assertFalse(Tabela.e_linha_de_dado([]))
        self.assertFalse(Tabela.e_linha_de_dado(["", "", ""]))

    def test_rodape_da_paginacao(self):
        self.assertFalse(Tabela.e_linha_de_dado(["1 2 3 4 5", "", ""]))


class TestRegistro(unittest.TestCase):
    def setUp(self):
        self.tabela = Tabela(colunas=list(CABECALHO))

    def test_casa_valores_com_cabecalhos(self):
        registro = self.tabela.registro(LINHA_TR)
        self.assertEqual(registro["Mês/Ano"], "11/2026")
        self.assertEqual(registro["Criado Em"], "04/11/2026")

    def test_coluna_a_mais_ganha_nome_generico(self):
        """Versao nova do PJe-Calc pode acrescentar coluna: nao pode perder dado."""
        self.assertEqual(self.tabela.registro(LINHA_TR + ["sobra"])["Col5"], "sobra")

    def test_coluna_a_menos_nao_estoura(self):
        self.assertEqual(self.tabela.registro(["11/2026"]), {"Mês/Ano": "11/2026"})


class TestDeduplicacao(unittest.TestCase):
    def test_conta_so_os_ineditos(self):
        tabela = tabela_com(LINHA_TR)
        novos = tabela.estender(
            [tabela.registro(LINHA_TR), tabela.registro(LINHA_ANTERIOR)])
        self.assertEqual(novos, 1)
        self.assertEqual(len(tabela), 2)

    def test_pagina_repetida_nao_entra_de_novo(self):
        """Quando o clique em 'proxima' nao pega, a pagina inteira volta — e e o
        zero devolvido aqui que faz o laco de paginacao parar."""
        tabela = tabela_com(LINHA_TR, LINHA_ANTERIOR)
        repetida = [tabela.registro(LINHA_TR), tabela.registro(LINHA_ANTERIOR)]
        self.assertEqual(tabela.estender(repetida), 0)
        self.assertEqual(len(tabela), 2)

    def test_preserva_a_ordem_de_chegada(self):
        """A tela entrega do mes mais novo para o mais velho; a planilha mantem."""
        tabela = tabela_com(LINHA_TR, LINHA_ANTERIOR)
        self.assertEqual([r["Mês/Ano"] for r in tabela.registros],
                         ["11/2026", "10/2026"])

    def test_linhas_iguais_em_competencias_diferentes_entram_as_duas(self):
        taxa_igual = ["09/2026", "0,0000", "1,0000000", "08/09/2026"]
        tabela = tabela_com(LINHA_TR, taxa_igual)
        self.assertEqual(len(tabela), 2)


class TestEstadoDaTabela(unittest.TestCase):
    def test_tabela_vazia_e_falsa(self):
        self.assertFalse(Tabela())
        self.assertEqual(len(Tabela()), 0)

    def test_mais_recente_e_a_primeira_linha(self):
        self.assertEqual(tabela_com(LINHA_TR, LINHA_ANTERIOR).mais_recente, "11/2026")

    def test_mais_recente_sem_dados_nao_estoura(self):
        self.assertEqual(Tabela().mais_recente, "?")

    def test_colunas_padrao_quando_a_tela_nao_entrega_cabecalho(self):
        self.assertEqual(Tabela().colunas, COLUNAS_PADRAO)

    def test_colunas_padrao_nao_sao_compartilhadas_entre_tabelas(self):
        """Lista mutavel como padrao faria uma tabela sujar a outra."""
        primeira = Tabela()
        primeira.colunas.append("Extra")
        self.assertNotIn("Extra", Tabela().colunas)


if __name__ == "__main__":
    unittest.main(verbosity=2)
