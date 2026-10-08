# PJe-Calc — Extração de índices TR e IPCA-E (TRT 8)

Automação Selenium que extrai as tabelas de correção monetária (**TR** e **IPCA-E**)
do **PJe-Calc Cidadão** do TRT da 8ª Região e grava cada uma em um `.xlsx`.

O PJe-Calc Cidadão roda localmente como um servidor HTTP em `localhost:9257`; o
script dirige um Firefox contra essa interface, atualiza as tabelas do TRT 8
online e raspa os resultados.

## Rodando no Linux

O TRT8 só homologa o PJe-Calc para Windows e distribui apenas um `.exe`. Mas esse
instalador é um ZIP auto-extraível, e a aplicação dentro dele é **Java puro**:
Tomcat 7 embarcado + banco H2, sem nenhuma biblioteca nativa fora do JRE que vem
junto. O próprio lançador (`br.jus.trt8.pjecalcsa.container.Lancador`) já tem o
ramo de Linux — procura `navegador/linux/Firefox-45.0.1-x86_64.AppImage`. O
suporte existe no código; o tribunal só não empacota.

Então dá para rodar nativo, trocando o JRE do Windows por um JDK 8 local:

```bash
./scripts/instalar-pjecalc-linux.sh
```

O script baixa o instalador oficial, **confere o MD5 publicado pelo TRT8**,
extrai, descarta as partes Windows (JRE e Firefox Portable, 167 MB que não rodam
aqui), instala o Temurin 8 via `mise` e deixa um lançador pronto.

Os dois parâmetros que o `iniciarPjeCalc.bat` passa para a JVM
(`seguranca.pjecalc.tokenServicos` e `seguranca.pjekz.servico.contexto`) são
extraídos do próprio `.bat` para um `pjecalc.env` ao lado do lançador. São
constantes iguais em todo instalador oficial, não credenciais suas — mas ficam
fora do versionamento de qualquer jeito.

### Java 8 é obrigatório

Não troque por um JDK mais novo. Em Java 17/21 o JBoss Seam e o Drools que a
aplicação usa esbarram no encapsulamento de módulos
(`InaccessibleObjectException`) e o contexto `/pjecalc` não sobe — testado, e
`--add-opens` só empurra o erro do Seam para o Drools.

### Display

O lançador precisa de um display (XWayland serve). Com
`-Djava.awt.headless=true` o Java 8 estoura `HeadlessException` em
`SplashScreen.getSplashScreen()` e morre antes do Tomcat subir.

No log aparece um `IllegalStateException: no splash screen available` na thread
`main`. É inofensivo: dispara **depois** do Tomcat já estar servindo, e a JVM
segue viva pelas threads não-daemon do Tomcat.

## Uso

```bash
# 1. sobe o PJe-Calc (deixe rodando)
~/.local/share/pjecalc/pjecalc.sh start

# 2. ambiente Python
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 3. extração
.venv/bin/python busca_indices_rpa.py
```

Saída em `output/`:

- `indices_TR_TRT8_<DDMMAAAA>.xlsx`
- `indices_IPCAE_TRT8_<DDMMAAAA>.xlsx`

Mais screenshots e dumps de DOM a cada etapa, úteis quando o PJe-Calc muda de
layout e algum seletor quebra.

A extração roda de ponta a ponta sem intervenção. Se alguma etapa cair num
fallback que exige mão humana, o script só pede ENTER quando há terminal
interativo; sem TTY ele falha dizendo qual etapa não foi automatizada, em vez de
travar esperando uma tecla que não vem.

### Seletores da tela de índices

Os campos de data são `rich-calendar-input` do RichFaces e o "Pesquisar" é um
`<a>` com `A4J.AJAX.Submit`, não um `input[type=submit]`. Os ids estão em
`CONFIG_INDICES`, e mudam entre as abas — repare que a TR carrega `Indice` no
meio do id e a IPCA-E não:

| | TR | IPCA-E |
|---|---|---|
| Tabela de * | `formulario:mesAnoConsultaIndiceTRInputDate` | `formulario:mesAnoConsultaIPCAEInputDate` |
| A partir de | `formulario:aPartirDeIndiceTRInputDate` | `formulario:aPartirDeIPCAEInputDate` |
| Pesquisar | `formulario:cmdVisualizarIndiceTR` | `formulario:cmdVisualizarIPCAE` |

Se uma versão nova do PJe-Calc renomear esses ids, o script ainda tenta por
rótulo e por posição antes de desistir — e os dumps em `output/dom_*.html` são o
caminho para descobrir os ids novos.

O script abre uma **janela dedicada do Firefox**, com perfil isolado e
`-no-remote`. Não a feche enquanto estiver rodando — sem isso o Firefox gruda
numa janela já aberta, encerra com status 0 e o geckodriver perde a sessão.

## Configuração

No topo de `busca_indices_rpa.py`:

| Constante | Para quê |
|---|---|
| `PORTA` | porta do PJe-Calc (padrão `9257`, definida em `tomcat/conf/server.xml`) |
| `NAVEGADOR` | `"firefox"` ou `"chrome"` |
| `CONFIG_INDICES` | intervalo de datas e ids JSF de cada índice |

Atualize `tabela_de` em `CONFIG_INDICES` para o mês mais recente que quiser
puxar — o padrão é TR até `06/2026` e IPCA-E até `05/2026`.

## Comandos do lançador

```
pjecalc.sh start | stop | restart | status | abrir
```

## Requisitos

- Firefox, `7z`, `curl`, [`mise`](https://mise.jdx.dev)
- Python 3.10+
- ~600 MB livres (103 MB depois de tirar as partes Windows)
