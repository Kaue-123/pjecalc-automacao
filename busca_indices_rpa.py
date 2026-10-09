"""
=============================================================================
SCRIPT 2 — Extração de Índices TR e IPCA-E do PJe-Calc Cidadão (TRT 8)
=============================================================================

FLUXO CORRETO (baseado na interface real do PJe-Calc):
  1. Home → menu Tabelas → "Atualização de Tabelas e Índices" → TRT 8 → Atualizar
  2. Home → menu Tabelas → "Correção Monetária" → filtrar datas → extrair TR
  3. Home → menu Tabelas → "Correção Monetária" → filtrar datas → extrair IPCA-E

DATAS BUSCADAS (calculadas na hora de rodar):
  - TR    : de 01/1967 ate o MES SEGUINTE ao da execucao
  - IPCA-E: de 01/1992 ate o MES CORRENTE

  Pedir um mes a frente e de proposito: o PJe-Calc nao reclama de um mes que
  ainda nao existe, so entrega ate onde tem. Assim a planilha sai sempre
  completa, sem depender do dia em que o TRT publicou o indice.
  Para uma rodada fora do padrao, use PJECALC_TR_ATE / PJECALC_IPCAE_ATE
  (formato MM/AAAA).

PRE-REQUISITOS:
  pip install -r requirements.txt

ANTES DE RODAR:
  1. Suba o PJe-Calc e aguarde ele responder:
       Linux   : ~/.local/share/pjecalc/pjecalc.sh start
       Windows : iniciarPJeCalc.bat
  2. Feche o navegador que o PJe-Calc abriu automaticamente (so no Windows;
     o lancador do Linux nao abre navegador nenhum)
  3. Execute: python busca_indices_rpa.py
=============================================================================
"""

import time, sys, os
from datetime import datetime
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, WebDriverException, StaleElementReferenceException,
)

# ─────────────────────────────────────────────
# CONFIGURACOES
# ─────────────────────────────────────────────
PORTA      = 9257
NAVEGADOR  = "firefox"    # "firefox" ou "chrome"
TIMEOUT    = 20

# Datas de consulta para cada índice
# Formato dos campos na tela: MM/AAAA  (ex: "06/2026")
# tab_texto: texto EXATO da aba na tela indices-gerais.jsf

def _mes_ano(ano, mes):
    """Normaliza (ano, mes) com mes fora de 1..12 e devolve 'MM/AAAA'."""
    ano += (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    return f"{mes:02d}/{ano}"

HOJE_DT = datetime.now()

# O TRT publica a TR do mes corrente por volta do dia 8 e a IPCA-E do mes
# anterior por volta do dia 2. Pedir TR um mes a frente e IPCA-E no mes corrente
# cobre os dois calendarios sem precisar saber em que dia a rodada caiu.
TR_ATE    = os.environ.get("PJECALC_TR_ATE")    or _mes_ano(HOJE_DT.year, HOJE_DT.month + 1)
IPCAE_ATE = os.environ.get("PJECALC_IPCAE_ATE") or _mes_ano(HOJE_DT.year, HOJE_DT.month)

CONFIG_INDICES = {
    "TR": {
        "tab_texto":  "TR",          # texto exato da aba (case-sensitive)
        "tabela_de":  TR_ATE,        # campo "Tabela de*"  (último mês desejado)
        "a_partir":   "01/1967",     # campo "A partir de" (mês inicial)
        "termos_selecao": ["TR"],    # fallback se aba não for encontrada por texto exato
        # IDs JSF conferidos no DOM da 2.16.0. Note a inconsistencia do PJe-Calc:
        # a aba TR carrega "Indice" no meio do id, a IPCA-E nao.
        "id_tabela_de": "formulario:mesAnoConsultaIndiceTRInputDate",
        "id_a_partir":  "formulario:aPartirDeIndiceTRInputDate",
        "id_pesquisar": "formulario:cmdVisualizarIndiceTR",
    },
    "IPCAE": {
        "tab_texto":  "IPCA-E",      # texto exato da aba
        "tabela_de":  IPCAE_ATE,     # campo "Tabela de*"
        "a_partir":   "01/1992",     # campo "A partir de"
        "termos_selecao": ["IPCA-E"],
        "id_tabela_de": "formulario:mesAnoConsultaIPCAEInputDate",
        "id_a_partir":  "formulario:aPartirDeIPCAEInputDate",
        "id_pesquisar": "formulario:cmdVisualizarIPCAE",
    },
}

# Cada rodada tem a sua pasta, nomeada pela data com hifens. O perfil do Firefox
# fica na raiz de output/ porque e reaproveitado entre rodadas.
DATA_RODADA  = HOJE_DT.strftime("%d-%m-%Y")
OUTPUT_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
PASTA_RODADA = os.path.join(OUTPUT_DIR, DATA_RODADA)
ARQ_TR       = os.path.join(PASTA_RODADA, f"indices_TR_TRT8_{DATA_RODADA}.xlsx")
ARQ_IPCAE    = os.path.join(PASTA_RODADA, f"indices_IPCAE_TRT8_{DATA_RODADA}.xlsx")

# Screenshot e dump de DOM a cada etapa so com PJECALC_DEBUG=1. Sem isso, a
# pasta da rodada fica so com as duas planilhas — mas as capturas de FALHA
# continuam saindo sempre, que e o unico momento em que alguem vai olhar.
DEBUG = os.environ.get("PJECALC_DEBUG") == "1"
# ─────────────────────────────────────────────

HOME = f"http://localhost:{PORTA}/pjecalc/pages/principal.jsf"


# ═══════════════════════════════════════════════════════════════
# UTILITÁRIOS
# ═══════════════════════════════════════════════════════════════

def log(msg, t="   "): print(f"  [{datetime.now().strftime('%H:%M:%S')}][{t}] {msg}")
def ok(m):   log(m, " OK")
def warn(m): log(m, "AVS")
def err(m):  log(m, "ERR")
def step(m): log(m, "-->")

def shot(driver, nome, erro=False):
    """
    Captura a tela na pasta da rodada.

    Nas etapas que deram certo isso so acontece com PJECALC_DEBUG=1 — numa
    rodada mensal desacompanhada ninguem vai abrir 18 imagens de coisa que
    funcionou. Quando `erro` e True a captura sai sempre: e o unico registro
    visual do que a tela mostrava na hora em que quebrou.
    """
    if not (DEBUG or erro):
        return
    try:
        os.makedirs(PASTA_RODADA, exist_ok=True)
        p = os.path.join(PASTA_RODADA, f"debug_{nome}.png")
        driver.save_screenshot(p)
        log(f"Screenshot: debug_{nome}.png", "DBG")
    except Exception:
        pass

def src(driver):
    try: return driver.page_source.lower()
    except: return ""

def tem_erro_interno(driver):
    s = src(driver)
    return "erro interno" in s or "ocorreu um erro inesperado" in s

def clicar(driver, el):
    try: el.click()
    except: driver.execute_script("arguments[0].click();", el)

def sessao_viva(driver):
    """
    Verifica se a janela do Firefox ainda existe.
    O PJe-Calc 2.16 é uma SPA JSF: se o usuario fechar a janela controlada pelo
    Selenium, toda chamada seguinte estoura InvalidSessionIdException.
    """
    try:
        _ = driver.title
        return True
    except Exception:
        return False

def exigir_sessao(driver):
    if not sessao_viva(driver):
        err("A janela do Firefox controlada pelo script foi fechada.")
        err("NAO feche essa janela — o script precisa dela ate o fim.")
        raise SystemExit(1)

def voltar_home(driver):
    """
    Volta para a tela inicial CLICANDO no menu, nao via driver.get().

    O PJe-Calc 2.16 mantem todo o estado (tabela carregada, aba do indice,
    filtros) no lado do servidor amarrado ao jsessionid. Um driver.get()
    recarrega principal.jsf e descarta esse estado.
    """
    exigir_sessao(driver)
    if not clicar_menu_id(driver, "li_tela_inicial"):
        driver.get(HOME)
    time.sleep(2)


def dump_dom(driver, nome, erro=False):
    """Salva o HTML da tela atual na pasta da rodada, para inspecao dos seletores."""
    if not (DEBUG or erro):
        return
    try:
        os.makedirs(PASTA_RODADA, exist_ok=True)
        p = os.path.join(PASTA_RODADA, f"dom_{nome}.html")
        with open(p, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        log(f"DOM salvo: dom_{nome}.html", "DBG")
    except Exception:
        pass

def pausar(driver, msg):
    shot(driver, "pausa_manual")
    warn(msg)
    if not sys.stdin.isatty():
        raise RuntimeError(f"Etapa manual necessaria em execucao nao-interativa: {msg}")
    input("  >> Pressione ENTER para continuar... ")


# ═══════════════════════════════════════════════════════════════
# DRIVER
# ═══════════════════════════════════════════════════════════════

def criar_driver():
    step(f"Iniciando {NAVEGADOR.upper()}...")
    if NAVEGADOR.lower() == "firefox":
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.firefox.options import Options
        from webdriver_manager.firefox import GeckoDriverManager
        options = Options()
        # No Linux o Firefox esta no PATH e o Selenium o localiza sozinho; so o
        # Windows precisa do caminho explicito.
        if sys.platform.startswith("win"):
            options.binary_location = r"C:\Program Files\Mozilla Firefox\firefox.exe"
        # Perfil dedicado + -no-remote: força uma instância isolada e impede
        # que o Firefox "grude" numa janela já aberta (o que faz o processo
        # encerrar com status 0 e o geckodriver perder a sessão).
        perfil_dir = os.path.join(OUTPUT_DIR, "_ff_profile")
        os.makedirs(perfil_dir, exist_ok=True)
        options.add_argument("-no-remote")
        options.add_argument("-profile")
        options.add_argument(perfil_dir)
        # PJECALC_FF_HEADLESS=1 roda sem janela, para nao tomar o foco de quem
        # esta usando a maquina. O Firefox headless desenha normalmente (as
        # capturas de tela continuam saindo); o que some e a janela no monitor.
        if os.environ.get("PJECALC_FF_HEADLESS") == "1":
            options.add_argument("-headless")
        drv = webdriver.Firefox(service=Service(GeckoDriverManager().install()), options=options)
    else:
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
        drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=Options())
    drv.set_window_size(1366, 900)
    ok("Driver pronto.")
    return drv


# ═══════════════════════════════════════════════════════════════
# MENU LATERAL — FUNÇÕES BASE
# ═══════════════════════════════════════════════════════════════

# IDs estaveis do menu lateral em principal.jsf (PJe-Calc 2.16.0).
# Confirmados no HTML: <li id="li_tabelas_indices_gerais"><a onclick="A4J.AJAX.Submit(...)">
# Sao MUITO mais confiaveis que casar texto acentuado ("Correção Monetária"),
# que quebra com entidades HTML (&ccedil;) e espacos nao-quebraveis.
MENU_IDS = {
    "tela_inicial":       "li_tela_inicial",
    "correcao_monetaria": "li_tabelas_indices_gerais",   # "Correção Monetária"
    "atualizacao":        "li_tabelas_sincronizar",       # "Atualização de Tabelas e Índices"
}


def clicar_menu_id(driver, li_id):
    """
    Dispara o item de menu pelo id do <li>, clicando no <a> interno.

    Funciona mesmo com o submenu COLAPSADO: o <a> carrega o handler
    A4J.AJAX.Submit no onclick, e element.click() via JS dispara esse handler
    independentemente de o elemento estar com display:none. Isso remove a
    dependencia de expandir o menu antes de navegar.
    """
    exigir_sessao(driver)
    r = driver.execute_script("""
        var li = document.getElementById(arguments[0]);
        if (!li) return 'SEM_LI';
        var a = li.querySelector('a');
        if (!a) return 'SEM_A';
        var txt = (a.innerText || a.textContent || '').trim();
        a.click();
        return 'OK:' + txt;
    """, li_id)

    if isinstance(r, str) and r.startswith("OK:"):
        time.sleep(2.5)
        if tem_erro_interno(driver):
            warn(f"Erro interno apos acionar '{li_id}'.")
            shot(driver, f"erro_menu_{li_id}", erro=True)
            return False
        ok(f"Menu acionado: '{r[3:]}' ({li_id})")
        return True

    warn(f"Item de menu '{li_id}' nao encontrado no DOM ({r}).")
    return False


def expandir_tabelas(driver):
    """
    Clica em 'Tabelas' no menu lateral esquerdo para expandir o submenu.

    Puramente cosmetico: serve para os screenshots de debug mostrarem o menu
    aberto. A navegacao real usa clicar_menu_id(), que nao precisa disso.
    """
    # Verifica se já está expandido (subitens REALMENTE visíveis)
    if _submenu_tabelas_aberto(driver):
        ok("Submenu Tabelas ja aberto.")
        return True

    # Clica no <li class="header"> cujo texto e "Tabelas"
    r = driver.execute_script("""
        var lis = document.querySelectorAll('li.header, li[class^="header"]');
        for (var i = 0; i < lis.length; i++) {
            var t = (lis[i].innerText || '').trim();
            if (t === 'Tabelas') { lis[i].click(); return 'ok'; }
        }
        return null;
    """)
    if r:
        time.sleep(1.2)
        if _submenu_tabelas_aberto(driver):
            ok("Menu Tabelas expandido.")
            return True

    # Nao expandiu — irrelevante para a navegacao, apenas registra.
    warn("Nao consegui expandir 'Tabelas' visualmente (navegacao segue por ID).")
    return True

def _submenu_tabelas_aberto(driver):
    """
    Verifica se o submenu de Tabelas está de fato VISÍVEL.

    ATENCAO: nao usar page_source aqui. O PJe-Calc renderiza TODOS os itens do
    submenu no HTML e apenas esconde o container com
    <li class="menu-item" style="display:none;">. Checar texto no page_source
    retorna True mesmo colapsado — foi exatamente esse o bug que fazia o script
    anunciar "Submenu Tabelas ja aberto" e em seguida falhar todos os cliques.
    Testamos visibilidade real via offsetParent.
    """
    try:
        return bool(driver.execute_script("""
            var li = document.getElementById('li_tabelas_indices_gerais');
            return !!(li && li.offsetParent !== null);
        """))
    except Exception:
        return False


def clicar_subitem(driver, texto_exato):
    """
    Clica em um subitem do menu por texto exato.
    O submenu de Tabelas deve estar expandido antes de chamar esta função.
    """
    # Tenta link com texto exato
    for xp in [
        f"//a[normalize-space(text())='{texto_exato}']",
        f"//span[normalize-space(text())='{texto_exato}']",
        f"//li[normalize-space(.)='{texto_exato}']//a",
        f"//*[normalize-space(text())='{texto_exato}']",
    ]:
        try:
            els = driver.find_elements(By.XPATH, xp)
            for el in els:
                if el.is_displayed():
                    clicar(driver, el)
                    time.sleep(2)
                    if not tem_erro_interno(driver):
                        ok(f"Subitem clicado: '{texto_exato}'")
                        return True
                    else:
                        warn(f"Erro interno após clicar em '{texto_exato}'. Indo ao home...")
                        voltar_home(driver)
                        return False
        except Exception:
            continue

    # Fallback JS com texto parcial (case-insensitive)
    script = f"""
        var alvo = '{texto_exato.lower()}';
        var els = document.querySelectorAll('a, span, li, td');
        for (var i = 0; i < els.length; i++) {{
            var el = els[i];
            if (!el.offsetParent) continue;
            var txt = (el.innerText || '').trim().toLowerCase();
            if (txt === alvo || txt.indexOf(alvo) !== -1) {{
                var rect = el.getBoundingClientRect();
                if (rect.left < 400) {{ el.click(); return txt; }}
            }}
        }}
        return null;
    """
    r = driver.execute_script(script)
    if r:
        time.sleep(2)
        if not tem_erro_interno(driver):
            ok(f"Subitem clicado via JS: '{r}'")
            return True
        voltar_home(driver)

    return False


# ═══════════════════════════════════════════════════════════════
# ETAPA 1 — ATUALIZAÇÃO DE TABELAS TRT 8
# ═══════════════════════════════════════════════════════════════

def atualizar_tabelas_trt8(driver):
    step("ETAPA 1/4  Atualizacao de Tabelas TRT 8")

    voltar_home(driver)
    expandir_tabelas(driver)

    if not clicar_menu_id(driver, MENU_IDS["atualizacao"]):
        if not clicar_subitem(driver, "Atualização de Tabelas e Índices"):
            pausar(driver, "Clique em 'Atualização de Tabelas e Índices' no submenu e pressione ENTER.")

    time.sleep(2)
    shot(driver, "tela_atualizacao")
    dump_dom(driver, "tela_atualizacao")

    # Verifica se o alerta de "já atualizado" está presente
    s = src(driver)
    if "mais recentes disponíveis" in s or "j\xe1 possui" in s or "ja possui" in s:
        ok("Tabelas já estão atualizadas (alerta confirmado).")
        return True

    # Seleciona TRT 8
    _selecionar_trt8(driver)
    time.sleep(1)

    # Clica em Atualizar Online
    if not _clicar_atualizar_online(driver):
        pausar(driver, "Clique em 'Atualizar Online' e aguarde concluir, depois pressione ENTER.")
        return True

    # Aguarda conclusão — detecta tanto a mensagem de sucesso quanto o alerta de "já atualizado"
    log("Aguardando atualizacao...", "   ")
    for _ in range(60):  # até 4 minutos
        time.sleep(4)
        print(".", end="", flush=True)
        s = src(driver)
        if tem_erro_interno(driver):
            print()
            warn("Erro interno durante atualizacao.")
            shot(driver, "erro_atualizacao", erro=True)
            voltar_home(driver)
            return False
        termos_ok = [
            "sucesso", "atualizado", "conclu", "finaliz",
            "mais recentes disponíveis", "ja possui", "j\xe1 possui",
            "recentes dispon",
        ]
        if any(t in s for t in termos_ok):
            print()
            ok("Atualizacao concluida!")
            return True
    print()
    warn("Timeout. Continuando assim mesmo...")
    return True

def _selecionar_trt8(driver):
    for sel_el in driver.find_elements(By.TAG_NAME, "select"):
        try:
            sel = Select(sel_el)
            for opt in sel.options:
                t = opt.text.lower()
                if ("8" in t and "trt" in t) or "par" in t or "amap" in t:
                    sel.select_by_visible_text(opt.text)
                    ok(f"TRT selecionado: '{opt.text}'")
                    return True
            # Log de diagnóstico se não encontrou TRT 8
            todas = [o.text for o in sel.options if o.text.strip()]
            if todas:
                warn(f"Opcoes no select: {todas}")
        except Exception:
            continue

    shot(driver, "selecao_trt_falhou", erro=True)
    pausar(driver, "Selecione 'TRT 8a Região' manualmente e pressione ENTER.")
    return True

def _clicar_atualizar_online(driver):
    for xp in [
        "//input[contains(translate(@value,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'atualiz')]",
        "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'atualiz')]",
        "//a[contains(@class,'btn') and contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'atualiz')]",
        "//input[@type='submit']",
        "//button[@type='submit']",
    ]:
        try:
            for el in driver.find_elements(By.XPATH, xp):
                if el.is_displayed() and el.is_enabled():
                    txt = (el.get_attribute("value") or el.text or "").strip()
                    clicar(driver, el)
                    ok(f"Botao clicado: '{txt}'")
                    return True
        except Exception:
            continue
    return False


# ═══════════════════════════════════════════════════════════════
# ETAPA 2/3 — EXTRAIR ÍNDICE DA TELA DE CORREÇÃO MONETÁRIA
# ═══════════════════════════════════════════════════════════════

def extrair_indice_correcao_monetaria(driver, nome_indice, config):
    """
    Navega para Tabelas > Correção Monetária (indices-gerais.jsf),
    clica na aba do índice, preenche os campos de data e extrai a tabela.

    Estrutura real da tela (confirmada na interface):
      - Abas horizontais no topo do conteúdo: "TR", "IPCA-E", "IPCA", etc.
      - Campos de filtro: "Tabela de*" (MM/AAAA) e "A partir de" (MM/AAAA)
      - Botão: "Pesquisar"
      - Tabela de resultados: Mês/Ano | Taxa do Mês(%) | Índice Acumulado | Criado Em
    """
    step(f"Extracao de {nome_indice} via Correcao Monetaria")

    # ── Abre Correção Monetária ───────────────────────────────
    voltar_home(driver)
    time.sleep(1)
    expandir_tabelas(driver)
    time.sleep(1)

    if not clicar_menu_id(driver, MENU_IDS["correcao_monetaria"]):
        if not clicar_subitem(driver, "Correção Monetária"):
            shot(driver, f"correcao_monetaria_falhou_{nome_indice}", erro=True)
            pausar(driver, "Clique em 'Correção Monetária' no submenu e pressione ENTER.")

    time.sleep(2)

    if tem_erro_interno(driver):
        err(f"Erro interno ao abrir Correcao Monetaria.")
        return [], []

    shot(driver, f"01_correcao_aberta_{nome_indice}")
    # Dump do DOM: os seletores da tela de indices ainda nao foram validados
    # na versao 2.16.0 (abas, campos de data, paginacao do modal).
    dump_dom(driver, f"correcao_monetaria_{nome_indice}")

    # ── Clica na aba do índice ────────────────────────────────
    tab_texto = config["tab_texto"]   # ex: "TR" ou "IPCA-E"
    if not _clicar_aba_indice(driver, tab_texto):
        shot(driver, f"02_aba_{nome_indice}_falhou", erro=True)
        warn(f"Aba '{tab_texto}' nao clicada automaticamente.")
        warn(f"Clique na aba '{tab_texto}' na faixa de abas no topo da tabela.")
        pausar(driver, f"Clique na aba '{tab_texto}' e pressione ENTER.")

    time.sleep(1.5)
    shot(driver, f"03_aba_{nome_indice}_selecionada")

    # ── Preenche datas e pesquisa ────────────────────────────
    print()
    _preencher_campos_data(driver, config)
    shot(driver, f"04_datas_preenchidas_{nome_indice}")

    time.sleep(1)
    if not _clicar_pesquisar(driver, config.get("id_pesquisar")):
        shot(driver, f"05_pesquisar_falhou_{nome_indice}", erro=True)
        pausar(driver, "Clique em 'Pesquisar' na tela e pressione ENTER.")

    time.sleep(2.5)
    shot(driver, f"06_resultados_{nome_indice}")

    if tem_erro_interno(driver):
        err(f"Erro interno após pesquisa.")
        return [], []

    if not _tem_tabela_dados(driver):
        shot(driver, f"07_sem_dados_{nome_indice}", erro=True)
        warn("Tabela de resultados nao detectada.")
        pausar(driver, "A tabela de resultados deve estar visivel. Pressione ENTER.")

    return extrair_tabela_completa(driver, nome_indice)


def _clicar_aba_indice(driver, texto_aba):
    """
    Clica na aba do índice na tela indices-gerais.jsf.

    Estrutura real: a linha de abas contém células como
    "TR", "UFIR", "IGP-M", "INPC", "IPCA", "IPCA-E", etc.
    Usamos XPath que identifica especificamente a linha de abas de índices.
    """
    log(f"  Clicando na aba '{texto_aba}'...", "   ")

    # ── Estratégia 1: Linha de abas identificada pelos vizinhos "TR" e "UFIR" ──
    # Esta é a abordagem mais confiável porque identifica a linha exata de abas.
    xpaths_precisos = [
        # Linha que contém tanto "TR" quanto "UFIR" (confirma que é a linha de abas)
        f"//tr[.//td[normalize-space(text())='TR'] and .//td[normalize-space(text())='UFIR']]"
        f"//td[normalize-space(text())='{texto_aba}']",
        # Linha que contém "IPCA-E" e "IPCA" (confirma linha de abas)
        f"//tr[.//td[normalize-space(text())='IPCA-E'] and .//td[normalize-space(text())='IPCA']]"
        f"//td[normalize-space(text())='{texto_aba}']",
        # Qualquer td com texto exato que esteja numa linha com outras abas conhecidas
        f"//td[normalize-space(text())='{texto_aba}' and "
        f"ancestor::tr[.//td[normalize-space(text())='UFIR'] or .//td[normalize-space(text())='JAM']]]",
    ]
    for xp in xpaths_precisos:
        try:
            els = driver.find_elements(By.XPATH, xp)
            for el in els:
                if el.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    time.sleep(0.3)
                    clicar(driver, el)
                    ok(f"Aba '{texto_aba}' clicada via XPath preciso.")
                    return True
        except Exception:
            continue

    # ── Estratégia 2: JavaScript — encontra td com texto EXATO fora do sidebar ──
    # Coleta TODOS os tds visíveis com o texto exato e tenta cada um.
    script = """
        var alvo = arguments[0];
        var tds = document.querySelectorAll('td, th');
        var candidatos = [];
        for (var i = 0; i < tds.length; i++) {
            var el = tds[i];
            if (!el.offsetParent) continue;
            // Texto EXATO (innerText pode ter \n, então trim)
            var txt = (el.innerText || el.textContent || '').replace(/\\s+/g,' ').trim();
            if (txt !== alvo) continue;
            var rect = el.getBoundingClientRect();
            if (rect.left < 230) continue;  // ignora sidebar
            if (rect.width < 5) continue;
            candidatos.push({el: el, x: rect.left, y: rect.top});
        }
        // Ordena por posição (mais à esquerda primeiro, excluindo sidebar)
        candidatos.sort(function(a,b){ return a.x - b.x; });
        if (candidatos.length > 0) {
            candidatos[0].el.scrollIntoView({block:'center'});
            candidatos[0].el.click();
            return 'js:' + alvo + '@' + Math.round(candidatos[0].x) + ',' + Math.round(candidatos[0].y)
                   + ' (total=' + candidatos.length + ')';
        }
        // Debug: lista todos tds com texto similar para diagnóstico
        var similares = [];
        for (var j = 0; j < tds.length; j++) {
            var t = (tds[j].innerText||'').replace(/\\s+/g,' ').trim();
            if (t.toUpperCase().indexOf(alvo.toUpperCase()) !== -1 && t.length < 20) {
                var r = tds[j].getBoundingClientRect();
                similares.push(t + '@x=' + Math.round(r.left));
            }
        }
        return 'NAO_ENCONTRADO|similares:' + similares.join(';');
    """
    r = driver.execute_script(script, texto_aba)
    if r and not r.startswith("NAO_ENCONTRADO"):
        ok(f"Aba '{texto_aba}' clicada via JS: {r}")
        return True
    if r:
        warn(f"Aba '{texto_aba}' nao encontrada. Diagnostico: {r}")

    # ── Estratégia 3: ActionChains — rola o scroll horizontal das abas e tenta ──
    try:
        # As abas podem estar fora da área visível — scrolla para encontrá-las
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        for xp in [
            f"//td[normalize-space(.)='{texto_aba}']",
            f"//th[normalize-space(.)='{texto_aba}']",
        ]:
            els = driver.find_elements(By.XPATH, xp)
            for el in els:
                try:
                    driver.execute_script("arguments[0].scrollIntoView(true);", el)
                    time.sleep(0.3)
                    from selenium.webdriver.common.action_chains import ActionChains
                    ActionChains(driver).move_to_element(el).click().perform()
                    ok(f"Aba '{texto_aba}' clicada via ActionChains.")
                    return True
                except Exception:
                    continue
    except Exception:
        pass

    return False


def _preencher_campos_data(driver, config):
    """
    Preenche os campos "Tabela de *" e "A partir de" na seção Consulta.

    O caminho bom é pelo id JSF (config["id_tabela_de"] / ["id_a_partir"]).
    As heuristicas por rótulo e por posição ficam só como rede de segurança
    para quando o PJe-Calc renomear os ids numa versão nova.

    PROBLEMA CONHECIDO: entre os dois inputs há um botão de calendário (📅).
    Pressionar TAB move o foco para esse botão, abre o calendário e buga o
    preenchimento. SOLUÇÃO: usar JS blur() em vez de TAB, e encontrar cada
    input navegando de TD em TD (não pela linha inteira).
    """
    tabela_de = config["tabela_de"]
    a_partir  = config["a_partir"]
    log(f"  Preenchendo: Tabela de={tabela_de} | A partir de={a_partir}", "   ")

    def escrever_sem_tab(campo, valor):
        """
        Preenche o campo sem pressionar TAB para não ativar o botão do calendário.
        Usa focus() → clear → send_keys → blur() via JS.
        """
        try:
            # Garante que o campo está visível e clicável
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", campo)
            driver.execute_script("arguments[0].focus();", campo)
            time.sleep(0.15)

            # Limpa o campo
            driver.execute_script("arguments[0].value = '';", campo)
            campo.send_keys(valor)
            time.sleep(0.15)

            # Dispara eventos de validação JSF SEM pressionar TAB
            # (TAB moveria o foco para o botão do calendário ao lado)
            driver.execute_script("""
                var el = arguments[0];
                el.dispatchEvent(new Event('input',  {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
                el.dispatchEvent(new Event('blur',   {bubbles: true}));
            """, campo)
            time.sleep(0.2)

            # NAO mandar ESCAPE aqui. O calendario do RichFaces trata ESC como
            # "cancelar" e LIMPA o input — era isso que zerava o campo recem
            # preenchido e fazia esta funcao devolver False. O blur() acima ja
            # fecha o calendario.

            val_atual = driver.execute_script("return arguments[0].value;", campo)
            return valor in (val_atual or "")
        except Exception as e:
            warn(f"    Erro ao escrever '{valor}': {e}")
            return False

    def encontrar_input_por_td_rotulo(rotulo_texto):
        """
        Encontra o <input> que está no <td> SEGUINTE ao <td> que contém o rótulo.
        Isso evita confundir os dois inputs que ficam na mesma <tr>.

        Estrutura da tela:
          <tr>
            <td>Tabela de *</td>  <td><input/><button>📅</button></td>
            <td>A partir de</td>  <td><input/><button>📅</button></td>
            <td><input type=submit value="Pesquisar"/></td>
          </tr>
        """
        script = """
            var rotulo = arguments[0].toLowerCase().trim();
            var cells = Array.from(document.querySelectorAll('td, th, label, span'));
            for (var i = 0; i < cells.length; i++) {
                var cel = cells[i];
                if (!cel.offsetParent) continue;
                var txt = (cel.innerText || cel.textContent || '').trim().toLowerCase();
                // Verifica se é a célula do rótulo (texto curto que contém o rótulo)
                if (txt.indexOf(rotulo) === -1 || txt.length > 60) continue;
                // Caso 1: input na célula irmã seguinte
                var prox = cel.nextElementSibling;
                while (prox) {
                    var inp = prox.querySelector(
                        'input[type=text], input[type=month], input:not([type]):not([type=hidden])'
                    );
                    if (inp && inp.offsetParent && !inp.disabled && !inp.readOnly) {
                        return inp;
                    }
                    // Para na próxima célula que tem input
                    if (prox.querySelectorAll('input').length > 0) break;
                    prox = prox.nextElementSibling;
                }
                // Caso 2: input dentro da própria célula (ex: label wrap)
                var inp2 = cel.querySelector(
                    'input[type=text], input[type=month], input:not([type]):not([type=hidden])'
                );
                if (inp2 && inp2.offsetParent) return inp2;
            }
            return null;
        """
        return driver.execute_script(script, rotulo_texto)

    def por_id(id_jsf):
        """Localiza pelo id JSF (getElementById, que aceita o ':' do JSF sem escape)."""
        if not id_jsf:
            return None
        try:
            return driver.execute_script(
                "return document.getElementById(arguments[0]);", id_jsf)
        except Exception:
            return None

    # ── Preenche "Tabela de *" ────────────────────────────────
    sucesso_1 = False
    campo_tabela = por_id(config.get("id_tabela_de"))
    if campo_tabela and escrever_sem_tab(campo_tabela, tabela_de):
        sucesso_1 = True
        ok(f"  'Tabela de*' = '{tabela_de}' (por id)")
    if not sucesso_1:
        campo_tabela = encontrar_input_por_td_rotulo("Tabela de")
        if campo_tabela:
            sucesso_1 = escrever_sem_tab(campo_tabela, tabela_de)
            if sucesso_1:
                ok(f"  'Tabela de*' = '{tabela_de}' (por rótulo)")
    if not sucesso_1:
        warn(f"  Campo 'Tabela de*' nao encontrado por id nem por rótulo.")

    # ── Preenche "A partir de" ────────────────────────────────
    sucesso_2 = False
    campo_apartir = por_id(config.get("id_a_partir"))
    if campo_apartir and escrever_sem_tab(campo_apartir, a_partir):
        sucesso_2 = True
        ok(f"  'A partir de' = '{a_partir}' (por id)")
    if not sucesso_2:
        campo_apartir = encontrar_input_por_td_rotulo("A partir de")
        if campo_apartir:
            sucesso_2 = escrever_sem_tab(campo_apartir, a_partir)
            if sucesso_2:
                ok(f"  'A partir de' = '{a_partir}' (por rótulo)")
    if not sucesso_2:
        warn(f"  Campo 'A partir de' nao encontrado por id nem por rótulo.")

    # ── Fallback: posição na tela (1º e 2º inputs do conteúdo) ───────
    if not sucesso_1 or not sucesso_2:
        campos_vis = [
            inp for inp in driver.find_elements(By.TAG_NAME, "input")
            if inp.is_displayed() and inp.is_enabled()
            and inp.get_attribute("type") not in
                ("hidden", "submit", "button", "checkbox", "radio", "image")
        ]
        # Nao filtrar por posicao: na tela de indices o painel de consulta fica
        # com left negativo (fora da viewport) e o filtro antigo (left > 230)
        # descartava justamente os dois campos que interessam.
        if not sucesso_1 and len(campos_vis) >= 1:
            sucesso_1 = escrever_sem_tab(campos_vis[0], tabela_de)
            if sucesso_1:
                ok(f"  'Tabela de*' = '{tabela_de}' (por posição[0])")
        if not sucesso_2 and len(campos_vis) >= 2:
            sucesso_2 = escrever_sem_tab(campos_vis[1], a_partir)
            if sucesso_2:
                ok(f"  'A partir de' = '{a_partir}' (por posição[1])")

    if not sucesso_1 or not sucesso_2:
        shot(driver, "datas_nao_preenchidas", erro=True)
        warn(f"  Preencha manualmente: 'Tabela de*' = {tabela_de} | 'A partir de' = {a_partir}")
        pausar(driver, "Preencha os campos de data e pressione ENTER.")

    return sucesso_1 or sucesso_2

def _clicar_pesquisar(driver, id_botao=None):
    # O botao da tela de indices e um <a> do RichFaces (A4J.AJAX.Submit), nao um
    # <input type=submit> — por isso o id explicito vem primeiro.
    if id_botao:
        try:
            el = driver.execute_script(
                "return document.getElementById(arguments[0]);", id_botao)
            if el:
                clicar(driver, el)
                ok(f"Botao 'Pesquisar' clicado (id {id_botao})")
                return True
        except Exception:
            pass

    termos = ["pesquisar", "consultar", "buscar", "pesquisa", "filtrar", "ok"]
    for termo in termos:
        for xp in [
            f"//input[contains(translate(@value,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'{termo}')]",
            f"//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'{termo}')]",
            f"//a[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'{termo}') and not(contains(@class,'menu'))]",
        ]:
            try:
                for el in driver.find_elements(By.XPATH, xp):
                    if el.is_displayed() and el.is_enabled():
                        clicar(driver, el)
                        ok(f"Botao pesquisar clicado: '{termo}'")
                        return True
            except Exception:
                continue
    # Último recurso: submit do form
    try:
        forms = driver.find_elements(By.TAG_NAME, "form")
        if forms:
            driver.execute_script("arguments[0].submit();", forms[0])
            ok("Form submetido via JS.")
            return True
    except Exception:
        pass
    return False

def _tem_tabela_dados(driver):
    if tem_erro_interno(driver): return False
    try:
        for t in driver.find_elements(By.TAG_NAME, "table"):
            linhas = t.find_elements(By.TAG_NAME, "tr")
            if len(linhas) >= 3:
                txt = t.text
                if sum(1 for c in txt if c.isdigit()) > 10:
                    return True
    except Exception:
        pass
    return False


# ═══════════════════════════════════════════════════════════════
# EXTRAÇÃO COM PAGINAÇÃO COMPLETA
# ═══════════════════════════════════════════════════════════════

def _modal_visivel(driver):
    """
    Detecta se o modal RichFaces (rich:modalPanel) está visível na tela.
    Retorna o elemento do modal ou None.
    """
    xps = [
        "//div[contains(@class,'rich-mpnl') and not(contains(@style,'display: none')) and not(contains(@style,'display:none'))]",
        "//div[contains(@class,'rich-mpnl-body')]/..",
        "//div[contains(@id,'Modal') or contains(@id,'modal') or contains(@id,'Popup') or contains(@id,'popup')]"
        "[not(contains(@style,'display: none'))]",
    ]
    for xp in xps:
        try:
            els = driver.find_elements(By.XPATH, xp)
            for el in els:
                if el.is_displayed():
                    return el
        except Exception:
            continue
    # Fallback: verifica via JS
    r = driver.execute_script("""
        var sels = ['div.rich-mpnl', 'div[class*="rich-mpnl"]', 'div[class*="modalPanel"]'];
        for (var s = 0; s < sels.length; s++) {
            var el = document.querySelector(sels[s]);
            if (el && el.offsetWidth > 0 && el.offsetHeight > 0) {
                var style = window.getComputedStyle(el);
                if (style.display !== 'none' && style.visibility !== 'hidden') return sels[s];
            }
        }
        return null;
    """)
    return r  # retorna string do seletor CSS, não elemento (aceitável como truthy)


def _cabecalhos_modal(driver):
    """Extrai cabeçalhos de dentro do modal RichFaces."""
    xps = [
        "//div[contains(@class,'rich-mpnl')]//table//th",
        "//div[contains(@class,'rich-mpnl')]//table//thead//td",
        "//div[contains(@class,'rich-mpnl-body')]//th",
        # Cabeçalho de tabela dentro de qualquer elemento modal/popup visível
        "//div[@style[contains(.,'z-index') or contains(.,'position: absolute')]]"
        "//table//th[normalize-space(.)!='']",
    ]
    for xp in xps:
        try:
            ths = driver.find_elements(By.XPATH, xp)
            cabs = [t.text.strip() for t in ths if t.text.strip()]
            if cabs:
                ok(f"  Cabecalhos do modal: {cabs}")
                return cabs
        except Exception:
            continue
    return []


def _linhas_modal(driver, cabecalhos):
    """
    Extrai APENAS as linhas de DADOS da tabela dentro do modal RichFaces.
    - Nunca toca na tabela do fundo da página
    - Filtra linhas de cabeçalho repetido (onde a primeira coluna não é MM/AAAA)
    """
    import re
    # Padrão de competência: MM/AAAA  (ex: 05/2026, 01/1967)
    RE_COMPETENCIA = re.compile(r'^\d{2}/\d{4}$')

    def e_linha_dado(vals):
        """Retorna True somente se a linha parece ser um dado real (não cabeçalho)."""
        if not any(v for v in vals): return False
        # A primeira coluna deve ser uma competência MM/AAAA
        primeiro = vals[0].strip() if vals else ""
        if not RE_COMPETENCIA.match(primeiro): return False
        return True

    # ── Extração via JavaScript (mais confiável para modal) ──────────
    script = """
        var modal = document.querySelector(
            'div.rich-mpnl, div[class*="rich-mpnl"], div[class*="modalPanel"]'
        );
        if (!modal || modal.offsetWidth === 0) return null;
        var tbody = modal.querySelector('table tbody');
        if (!tbody) return null;
        var rows = tbody.querySelectorAll('tr');
        var result = [];
        for (var i = 0; i < rows.length; i++) {
            var tds = rows[i].querySelectorAll('td');
            var vals = [];
            for (var j = 0; j < tds.length; j++) {
                vals.push((tds[j].innerText || '').trim());
            }
            if (vals.length > 0) result.push(vals);
        }
        return result;
    """
    resultado_js = driver.execute_script(script)
    if resultado_js:
        linhas = []
        for vals in resultado_js:
            if not e_linha_dado(vals): continue   # pula cabeçalhos repetidos
            reg = {cabecalhos[i] if i < len(cabecalhos) else f"Col{i+1}": v
                   for i, v in enumerate(vals)}
            linhas.append(reg)
        return linhas

    # ── Fallback XPath ────────────────────────────────────────────────
    for xp in [
        "//div[contains(@class,'rich-mpnl-body')]//table//tbody//tr",
        "//div[contains(@class,'rich-mpnl')]//table//tbody//tr",
    ]:
        try:
            trs = driver.find_elements(By.XPATH, xp)
            if not trs: continue
            linhas = []
            for tr in trs:
                try:
                    tds = tr.find_elements(By.TAG_NAME, "td")
                    vals = [td.text.strip() for td in tds]
                    if not e_linha_dado(vals): continue
                    reg = {cabecalhos[i] if i < len(cabecalhos) else f"Col{i+1}": v
                           for i, v in enumerate(vals)}
                    linhas.append(reg)
                except (StaleElementReferenceException, Exception):
                    continue
            if linhas: return linhas
        except Exception:
            continue
    return []


def _proxima_pagina_modal(driver):
    """
    Clica no botão de PRÓXIMA PÁGINA (▶) do modal — NÃO no de última página (▶|).

    Estrutura do datascroller RichFaces:
      [|◀]  [◀]  [1] [2] ... [12]  [▶]  [▶|]
       btn   btn  pages...         btn   btn
                                    ↑ queremos este (last()-1)
                                          ↑ NÃO este (last())
    """
    xps = [
        # RichFaces: penúltimo botão de navegação dentro do modal
        "//div[contains(@class,'rich-mpnl')]"
        "//td[contains(@class,'rich-datascr-button') and not(contains(@class,'dis'))][last()-1]",

        "//div[contains(@class,'rich-mpnl')]"
        "//td[contains(@class,'rich-datascr-button')][last()-1]//a",

        # Fallback: ícone de seta simples ">" (próxima) vs ">>" (última)
        "//div[contains(@class,'rich-mpnl')]"
        "//a[contains(@class,'next') and not(contains(@class,'last')) "
        "    and not(contains(@class,'dis'))]",
    ]
    for xp in xps:
        try:
            els = driver.find_elements(By.XPATH, xp)
            for el in els:
                if not el.is_displayed() or not el.is_enabled(): continue
                cls = (el.get_attribute("class") or "").lower()
                if "disabled" in cls or "inativ" in cls: continue
                return el
        except Exception:
            continue

    # Fallback JS — penúltimo botão de datascroller dentro do modal
    el_js = driver.execute_script("""
        var modal = document.querySelector('div.rich-mpnl, div[class*="rich-mpnl"]');
        if (!modal) return null;
        // Pega todos os td de navegação (rich-datascr-button)
        var btns = Array.from(
            modal.querySelectorAll('td[class*="rich-datascr-button"], td[class*="rich-datascr-btn"]')
        ).filter(function(b){ return b.offsetParent !== null; });
        // Penúltimo = próxima página (último = última página)
        var idx = btns.length - 2;
        if (idx < 0) return null;
        var btn = btns[idx];
        var cls = (btn.className || '').toLowerCase();
        if (cls.indexOf('dis') !== -1) return null;   // desabilitado = já na última página
        var a = btn.querySelector('a');
        return a || btn;
    """)
    return el_js if el_js else None


def extrair_tabela_completa(driver, nome):
    """
    Extrai TODOS os registros da tabela de índices do PJe-Calc.
    Prioriza extração do modal popup (RichFaces modalPanel).
    Navega por TODAS as páginas do modal até esgotar os dados.
    """
    todos, cabecalhos = [], []
    pagina, sem_novos = 1, 0
    max_paginas = 200  # segurança

    # Detecta se há modal aberto
    modal = _modal_visivel(driver)
    usar_modal = bool(modal)
    if usar_modal:
        ok(f"  Modal detectado. Extração focada no modal.")
    else:
        warn(f"  Modal NAO detectado. Extração da tabela da página.")

    while pagina <= max_paginas:
        time.sleep(1.2)

        if tem_erro_interno(driver):
            err(f"Erro interno na pagina {pagina}.")
            shot(driver, f"erro_pag_{nome}_{pagina:03d}", erro=True)
            break

        # Cabeçalhos (apenas na primeira página)
        if pagina == 1:
            cabecalhos = _cabecalhos_modal(driver) if usar_modal else _cabecalhos_pagina(driver)
            log(f"  Cabecalhos ({nome}): {cabecalhos}", "   ")
            if not cabecalhos:
                warn("  Cabecalhos nao encontrados. Usando nomes genericos.")
                cabecalhos = ["Mês/Ano", "Taxa do Mês(%)", "Índice Acumulado", "Criado Em"]

        # Linhas desta página
        novas = _linhas_modal(driver, cabecalhos) if usar_modal else _linhas_pagina(driver, cabecalhos)

        # Deduplicação
        chaves = {str(r) for r in todos}
        adicionadas = 0
        for linha in novas:
            k = str(linha)
            if k not in chaves:
                todos.append(linha)
                chaves.add(k)
                adicionadas += 1

        log(f"  Pag {pagina:3d}: +{adicionadas:3d} novos | total: {len(todos):5d}", "   ")

        if adicionadas == 0:
            sem_novos += 1
            if sem_novos >= 2:
                ok(f"  Fim: {len(todos)} registros em {pagina} pagina(s).")
                break
        else:
            sem_novos = 0

        # Próxima página
        prox = _proxima_pagina_modal(driver) if usar_modal else _botao_proxima_pagina(driver)
        if not prox:
            ok(f"  Ultima pagina ({pagina}). {len(todos)} registros no total.")
            break
        try:
            clicar(driver, prox)
            pagina += 1
        except (StaleElementReferenceException, Exception) as e:
            warn(f"  Erro ao paginar (pag {pagina}): {e}")
            break

    return todos, cabecalhos


def _cabecalhos_pagina(driver):
    """Extrai cabeçalhos da tabela na página (fora do modal)."""
    for xp in ["//table[.//tbody//tr]//th", "//th[@scope='col']", "//table[.//tbody//tr]//thead//td"]:
        try:
            ths = driver.find_elements(By.XPATH, xp)
            cabs = [t.text.strip() for t in ths if t.text.strip()]
            if cabs: return cabs
        except Exception:
            continue
    return []


def _linhas_pagina(driver, cabecalhos):
    """Extrai linhas da tabela da página (fora do modal)."""
    for xp in [
        "//table[contains(@class,'rich-table')]//tbody//tr",
        "//table[@role='grid']//tbody//tr",
        "(//table[count(.//tbody//tr)>1])[1]//tbody//tr",
    ]:
        try:
            trs = driver.find_elements(By.XPATH, xp)
            if not trs: continue
            linhas = []
            for tr in trs:
                try:
                    tds = tr.find_elements(By.TAG_NAME, "td")
                    vals = [td.text.strip() for td in tds]
                    if not any(vals): continue
                    if not any(any(c.isdigit() for c in v) for v in vals if v): continue
                    reg = {cabecalhos[i] if i < len(cabecalhos) else f"Col{i+1}": v
                           for i, v in enumerate(vals)}
                    linhas.append(reg)
                except Exception: continue
            if linhas: return linhas
        except Exception: continue
    return []


def _botao_proxima_pagina(driver):
    """Botão próxima página genérico (fora do modal)."""
    for xp in [
        "//td[contains(@class,'rich-datascr-button') and not(contains(@class,'dis'))][last()]//a",
        "//a[contains(@class,'ui-paginator-next') and not(contains(@class,'disabled'))]",
        "//a[normalize-space(text())='>' or normalize-space(text())='»']",
    ]:
        try:
            for el in driver.find_elements(By.XPATH, xp):
                if not el.is_displayed() or not el.is_enabled(): continue
                cls = (el.get_attribute("class") or "").lower()
                if "disabled" not in cls and "inativ" not in cls: return el
        except Exception: continue
    return None


# ═══════════════════════════════════════════════════════════════
# SALVAR EXCEL
# ═══════════════════════════════════════════════════════════════

def salvar_excel(registros, cabecalhos, nome, arquivo):
    if not registros:
        warn(f"Sem dados para salvar ({nome}).")
        return False
    df = pd.DataFrame(registros)
    cols = [c for c in cabecalhos if c in df.columns]
    df = df[cols + [c for c in df.columns if c not in cols]]
    os.makedirs(os.path.dirname(arquivo), exist_ok=True)

    with pd.ExcelWriter(arquivo, engine="openpyxl") as w:
        df.to_excel(w, sheet_name=nome[:31], index=False)
        ws = w.sheets[nome[:31]]
        from openpyxl.styles import PatternFill, Font, Alignment
        hf = PatternFill("solid", fgColor="1F3864"); hft = Font(bold=True, color="FFFFFF")
        af = PatternFill("solid", fgColor="DCE6F1")
        for c in ws[1]: c.fill = hf; c.font = hft; c.alignment = Alignment(horizontal="center")
        for i, row in enumerate(ws.iter_rows(min_row=2), 2):
            if i % 2 == 0:
                for c in row: c.fill = af
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(
                max(len(str(c.value or "")) for c in col) + 4, 30)
    ok(f"Salvo ({len(df)} registros): {arquivo}")
    return True


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print("\n" + "="*62)
    print("  PJe-Calc — Extracao Indices TRT 8 (TR e IPCA-E)")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("="*62)
    os.makedirs(PASTA_RODADA, exist_ok=True)
    driver = None

    try:
        driver = criar_driver()
        driver.get(HOME)
        time.sleep(3)

        print()
        warn("O script abriu uma janela DEDICADA do Firefox (perfil isolado).")
        warn("Todas as acoes manuais pedidas devem ser feitas NESSA janela.")
        warn("Se voce mexer em outra janela do Firefox, o script nao enxerga.")
        warn("NAO feche essa janela ate o script terminar.")
        print()

        if tem_erro_interno(driver):
            err("PJe-Calc respondeu com erro na home. Verifique se está rodando.")
            sys.exit(1)
        ok("PJe-Calc acessivel.")

        # ── Atualiza tabelas TRT 8 ────────────────────────────
        print()
        atualizar_tabelas_trt8(driver)
        time.sleep(2)

        # ── Extrai TR ─────────────────────────────────────────
        print()
        step("ETAPA 2/4  Extracao TR  (aba 'TR', a partir de 01/1967)")
        r_tr, c_tr = extrair_indice_correcao_monetaria(driver, "TR", CONFIG_INDICES["TR"])

        # ── Extrai IPCA-E ─────────────────────────────────────
        print()
        step("ETAPA 3/4  Extracao IPCA-E  (aba 'IPCA-E', a partir de 01/1992)")
        r_ie, c_ie = extrair_indice_correcao_monetaria(driver, "IPCAE", CONFIG_INDICES["IPCAE"])

        # ── Salva ─────────────────────────────────────────────
        print()
        step("ETAPA 4/4  Salvando arquivos")
        salvar_excel(r_tr, c_tr, "TR",    ARQ_TR)
        salvar_excel(r_ie, c_ie, "IPCAE", ARQ_IPCAE)

        print()
        print("="*62)
        print("  CONCLUIDO")
        print(f"  TR    : {len(r_tr):5d} registros  -> {os.path.basename(ARQ_TR)}")
        print(f"  IPCAE : {len(r_ie):5d} registros  -> {os.path.basename(ARQ_IPCAE)}")
        if r_tr: print(f"  Mes mais recente TR    : {r_tr[0].get('Mês/Ano', '?')}")
        if r_ie: print(f"  Mes mais recente IPCAE : {r_ie[0].get('Mês/Ano', '?')}")
        print(f"  Pasta : {PASTA_RODADA}")
        print("="*62)
        time.sleep(3)

    except KeyboardInterrupt:
        warn("Interrompido.")
    except SystemExit:
        raise
    except Exception as e:
        from selenium.common.exceptions import InvalidSessionIdException
        if isinstance(e, InvalidSessionIdException) or "without establishing a connection" in str(e):
            err("A janela do Firefox controlada pelo script foi fechada durante a execucao.")
            err("Os dados extraidos ate aqui foram perdidos.")
            err("Rode de novo e NAO feche a janela que o script abre.")
        else:
            err(f"Erro inesperado: {e}")
            if driver and sessao_viva(driver): shot(driver, "erro_fatal", erro=True)
            import traceback; traceback.print_exc()
    finally:
        if driver:
            try: driver.quit()
            except Exception: pass
            log("Navegador encerrado.", "   ")

if __name__ == "__main__":
    main()