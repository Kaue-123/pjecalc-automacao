"""Gravacao das tabelas extraidas em .xlsx."""

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill

AZUL_CABECALHO = "1F3864"
AZUL_ZEBRA = "DCE6F1"
LARGURA_MAXIMA = 30
FOLGA_COLUNA = 4
MAX_NOME_ABA = 31


class RepositorioPlanilha:
    def __init__(self, console):
        self._console = console

    def salvar(self, tabela, nome_aba, arquivo) -> bool:
        if not tabela:
            self._console.aviso(f"Sem dados para salvar ({nome_aba}).")
            return False

        planilha = pd.DataFrame(tabela.registros)
        conhecidas = [c for c in tabela.colunas if c in planilha.columns]
        sobras = [c for c in planilha.columns if c not in conhecidas]
        planilha = planilha[conhecidas + sobras]

        arquivo.parent.mkdir(parents=True, exist_ok=True)
        aba = nome_aba[:MAX_NOME_ABA]
        with pd.ExcelWriter(arquivo, engine="openpyxl") as escritor:
            planilha.to_excel(escritor, sheet_name=aba, index=False)
            self._formatar(escritor.sheets[aba])

        self._console.ok(f"Salvo ({len(planilha)} registros): {arquivo}")
        return True

    @staticmethod
    def _formatar(folha):
        fundo = PatternFill("solid", fgColor=AZUL_CABECALHO)
        fonte = Font(bold=True, color="FFFFFF")
        for celula in folha[1]:
            celula.fill = fundo
            celula.font = fonte
            celula.alignment = Alignment(horizontal="center")

        zebra = PatternFill("solid", fgColor=AZUL_ZEBRA)
        for numero, linha in enumerate(folha.iter_rows(min_row=2), start=2):
            if numero % 2 == 0:
                for celula in linha:
                    celula.fill = zebra

        for coluna in folha.columns:
            maior = max(len(str(celula.value or "")) for celula in coluna)
            folha.column_dimensions[coluna[0].column_letter].width = min(
                maior + FOLGA_COLUNA, LARGURA_MAXIMA)
