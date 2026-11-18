"""Tabela de indices extraida da tela: cabecalhos mais registros."""

from dataclasses import dataclass, field

from .competencia import e_competencia

COLUNAS_PADRAO = ["Mês/Ano", "Taxa do Mês(%)", "Índice Acumulado", "Criado Em"]
COLUNA_COMPETENCIA = COLUNAS_PADRAO[0]


@dataclass
class Tabela:
    colunas: list = field(default_factory=lambda: list(COLUNAS_PADRAO))
    registros: list = field(default_factory=list)
    _chaves: set = field(default_factory=set, repr=False)

    def __len__(self) -> int:
        return len(self.registros)

    def __bool__(self) -> bool:
        return bool(self.registros)

    @property
    def mais_recente(self) -> str:
        """Competencia da primeira linha — a tela entrega em ordem decrescente."""
        return self.registros[0].get(COLUNA_COMPETENCIA, "?") if self.registros else "?"

    def registro(self, valores: list) -> dict:
        """Casa os valores de uma linha com os cabecalhos, nomeando as sobras."""
        return {
            self.colunas[i] if i < len(self.colunas) else f"Col{i + 1}": valor
            for i, valor in enumerate(valores)
        }

    def estender(self, novos: list) -> int:
        """Acrescenta os registros ineditos e devolve quantos entraram.

        A paginacao do PJe-Calc repete a pagina atual quando o clique no
        'proxima' nao pega; sem deduplicar, a planilha sairia com linhas
        dobradas e o laco nunca perceberia que chegou ao fim.
        """
        antes = len(self.registros)
        for linha in novos:
            chave = str(linha)
            if chave not in self._chaves:
                self._chaves.add(chave)
                self.registros.append(linha)
        return len(self.registros) - antes

    @staticmethod
    def e_linha_de_dado(valores: list) -> bool:
        """Linha de dado comeca por uma competencia; cabecalho repetido, nao."""
        return bool(valores) and e_competencia(valores[0])
