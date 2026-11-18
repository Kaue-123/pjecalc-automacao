"""Competencia: o mes de referencia de um indice, no formato MM/AAAA."""

import re

PADRAO = re.compile(r"^\d{2}/\d{4}$")


def mes_ano(ano: int, mes: int) -> str:
    """Formata (ano, mes) como 'MM/AAAA', normalizando mes fora de 1..12."""
    ano += (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    return f"{mes:02d}/{ano}"


def e_competencia(texto: str) -> bool:
    return bool(PADRAO.match((texto or "").strip()))
