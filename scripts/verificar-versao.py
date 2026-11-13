#!/usr/bin/env python3
"""
Compara a versao do PJe-Calc Cidadao instalada com a anunciada pelo TRT 8.

Quando o tribunal publica uma versao nova, as tabelas e regras de calculo
mudam junto — e a instalacao antiga continua rodando e entregando numero
velho, sem reclamar de nada. Por isso a conferencia entra na rodada mensal,
em vez de depender de alguem lembrar de olhar o portal.

Baixar e instalar continua sendo passo manual: o instalador precisa ser
conferido contra o MD5 que o TRT publica.

Duas fontes do TRT sao cruzadas: o texto "Versao Atual" do portal e o nome do
instalador publicado na pagina de instalacao. A segunda cobre o caso de
publicarem a versao nova e esquecerem de mexer no texto.

Saida: 0 = em dia | 1 = ha versao nova | 2 = nao foi possivel verificar
"""

import os
import re
import sys
import urllib.request

PORTAL = "https://www.trt8.jus.br/pjecalc-cidadao"
# Segunda fonte: a pagina de instalacao, que lista o instalador baixavel. O TRT
# precisa trocar esse arquivo para a versao nova existir de fato, entao ela
# cobre o caso de alguem publicar a versao e esquecer de mexer no "Versao Atual".
PAGINA_INSTALACAO = PORTAL + "/instalando-o-pje-calc-cidadao"
PJECALC_HOME = os.environ.get("PJECALC_HOME", os.path.expanduser("~/.local/share/pjecalc"))
# O lancador exporta PJECALC_URL; o default so serve para rodar na mao.
URL_APP = os.environ.get("PJECALC_URL", "http://localhost:9257/pjecalc/pages/principal.jsf")
TIMEOUT = 30


def versao_instalada():
    """
    Pergunta primeiro a aplicacao rodando: ela diz o que esta no ar agora.

    O arquivo VERSAO e rede de segurança para quando o servidor esta fora do ar
    — ele guarda o que o instalador baixou um dia, e fica congelado se alguem
    atualizar o PJe-Calc por fora.
    """
    try:
        with urllib.request.urlopen(URL_APP, timeout=10) as r:
            html = r.read().decode("latin-1", errors="replace")
        m = re.search(r"Vers[ãa]o:?\s*([\d.]+)", html.replace("&atilde;", "ã"))
        if m:
            return m.group(1), "aplicacao rodando"
    except Exception:
        pass

    arq = os.path.join(PJECALC_HOME, "VERSAO")
    if os.path.exists(arq):
        with open(arq) as f:
            v = f.read().strip()
        if v:
            return v, "arquivo VERSAO (aplicacao fora do ar)"
    return None, None


def _baixar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "pjecalc-automacao"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", errors="replace")


def versao_do_portal():
    """O <h3> 'Versao Atual' da pagina principal. Devolve (versao, data)."""
    m = re.search(
        r"Vers[ãa]o Atual:\s*<strong>\s*([\d.]+)\s*</strong>.*?"
        r"Dispon[íi]vel desde:\s*<strong>\s*([\d/]+)\s*</strong>",
        _baixar(PORTAL), re.S | re.I)
    if not m:
        raise ValueError("o portal mudou de formato: nao achei 'Versão Atual'")
    return m.group(1), m.group(2)


def versao_do_instalador():
    """A maior versao entre os instaladores listados para download."""
    achados = re.findall(r"pjecalc-([\d.]+)-instalador-x\d+\.exe",
                         _baixar(PAGINA_INSTALACAO))
    if not achados:
        raise ValueError("nao achei nenhum instalador listado na pagina de instalacao")
    return max(achados, key=como_tupla)


def como_tupla(v):
    return tuple(int(x) for x in v.split(".") if x.isdigit())


def main():
    instalada, origem = versao_instalada()
    if not instalada:
        print("[ERR] Nao consegui descobrir a versao instalada.")
        print(f"      Procurei em {URL_APP} e em {PJECALC_HOME}/VERSAO.")
        return 2

    # Duas fontes independentes: o texto que o TRT escreve e o arquivo que ele
    # publica. Se so uma responder, segue com ela; se discordarem, vale a maior,
    # porque a versao nova existir em qualquer uma das duas ja e motivo de aviso.
    portal = desde = instalador = None
    falhas = []
    try:
        portal, desde = versao_do_portal()
        print(f"[   ] No portal   : {portal}  (disponivel desde {desde})")
    except Exception as e:
        falhas.append(f"portal: {e}")
    try:
        instalador = versao_do_instalador()
        print(f"[   ] Instalador  : {instalador}")
    except Exception as e:
        falhas.append(f"pagina de instalacao: {e}")

    for f in falhas:
        print(f"[AVS] Fonte indisponivel — {f}")

    publicadas = [v for v in (portal, instalador) if v]
    if not publicadas:
        print("[ERR] Nenhuma das duas fontes do TRT 8 respondeu.")
        return 2

    if portal and instalador and portal != instalador:
        print(f"[AVS] As duas fontes do TRT discordam: portal diz {portal}, "
              f"instalador publicado e {instalador}.")

    publicada = max(publicadas, key=como_tupla)
    print(f"[   ] Instalada   : {instalada}  ({origem})")

    # Se uma das fontes vier sem o terceiro numero, compara-se o que da.
    a, b = como_tupla(instalada), como_tupla(publicada)
    if len(a) < len(b):
        b = b[:len(a)]

    if b > a:
        desde_txt = f", desde {desde}" if desde and publicada == portal else ""
        print(f"[AVS] Versao nova do PJe-Calc Cidadao: {publicada}{desde_txt}.")
        print( "      Atualize com scripts/instalar-pjecalc-linux.sh, ajustando")
        print( "      VERSAO e MD5_ESPERADO com os valores publicados pelo TRT 8.")
        return 1

    if falhas:
        print("[ OK] PJe-Calc esta na versao atual (com uma fonte indisponivel).")
    else:
        print("[ OK] PJe-Calc esta na versao atual.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
