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

### Sem janela: o modo serviço

O `Lancador` que é o `Main-Class` do jar faz três coisas: prepara as variáveis e
o banco, sobe o Tomcat e só então abre uma interface. A interface é um ícone na
bandeja do sistema quando há bandeja; quando não há — no Wayland, por exemplo —
ele cai numa `JFrame` com dois botões, "Abrir o PjeCalc" e "Sair", que fica
parada na tela sem servir para nada em uso automatizado.

Daí `scripts/servico/PjeCalcServico.java`: repete as duas primeiras etapas,
chamando por reflexão os métodos privados do `Lancador`, e para antes da
terceira.

O que a janela fazia de útil era **segurar a JVM viva** — as threads do Tomcat
embarcado são daemon, quem não deixava o processo morrer era a thread de eventos
do AWT. No lugar dela, a `main` fica bloqueada até chegar um `SIGTERM`.

Sem AWT, `-Djava.awt.headless=true` deixa de ser problema: ninguém mais chama
`SplashScreen.getSplashScreen()`, que era o que estourava `HeadlessException` no
Java 8 e derrubava o processo antes do Tomcat subir. O servidor roda sem display
nenhum. Quem ainda precisa de display é o Firefox da automação.

## Uso

```bash
# 1. sobe o PJe-Calc (deixe rodando)
~/.local/share/pjecalc/pjecalc.sh start

# 2. ambiente Python
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 3. extração
.venv/bin/python -m pjecalc
```

Cada rodada tem a sua pasta, nomeada pela data:

```
output/09-10-2026/
├── indices_TR_TRT8_09-10-2026.xlsx
└── indices_IPCAE_TRT8_09-10-2026.xlsx
```

As datas consultadas são calculadas na hora de rodar: **TR até o mês seguinte,
IPCA-E até o mês corrente**, as duas a partir de 01/1967 e 01/1992. Pedir um mês
à frente é de propósito — o PJe-Calc não reclama de um mês que ainda não existe,
só entrega até onde tem, e aí a planilha sai completa independentemente do dia
em que o TRT publicou o índice. Para uma rodada fora do padrão:

```bash
PJECALC_TR_ATE=03/2027 PJECALC_IPCAE_ATE=02/2027 .venv/bin/python -m pjecalc
```

Numa rodada normal a pasta fica só com as duas planilhas. `PJECALC_DEBUG=1`
acrescenta screenshot e dump de DOM a cada etapa, úteis quando o PJe-Calc muda
de layout e algum seletor quebra; as capturas de **falha** saem sempre.

### Deixando o servidor de pé sozinho

Para não ter de subir o PJe-Calc a cada vez, há uma unidade de usuário do
systemd — de usuário, não de sistema, porque o banco H2 fica no `$HOME` e o
servidor só atende em `localhost`:

```bash
cp scripts/pjecalc.service ~/.config/systemd/user/
systemctl --user enable --now pjecalc   # sobe agora e a cada login
systemctl --user status pjecalc
journalctl --user -u pjecalc -f
```

Ela chama `pjecalc.sh foreground`, que roda o java como processo principal da
unidade, sem `setsid` nem arquivo de pid. Com a unidade no ar, não use
`pjecalc.sh start`/`stop` — os dois controles brigam pelo mesmo processo.

## Rodada mensal automática

A extração inteira — subir o servidor, conferir a versão do PJe-Calc, extrair e
avisar — roda sozinha uma vez por mês:

```bash
./scripts/instalar-automacao.sh
```

Ele escreve as unidades em `~/.config/systemd/user/` com o caminho real do
repositório e habilita o timer. Rode de novo se mover o repositório de lugar.

**Quando roda:** dia 6 às 11h; se cair no fim de semana, na segunda seguinte.

O systemd não conhece dia útil, então o timer dispara nos dias 6, 7 e 8 e um
marcador em `~/.local/state/pjecalc-automacao/` descarta as sobras. O
`pjecalc-indices.timer` tem os casos comentados. Feriado não entra na conta; com
a máquina desligada na hora, `Persistent=true` recupera no próximo boot.

Para rodar na mão, fora da agenda:

```bash
systemctl --user start pjecalc-indices     # respeita o marcador do mês
./scripts/rodada-mensal.sh --forcar        # ignora o marcador
```

### Versão do PJe-Calc

Versão nova muda tabela e regra de cálculo, e a instalação antiga continua
entregando número velho sem reclamar — por isso toda rodada confere:

```bash
python3 scripts/verificar-versao.py
# 0 = em dia | 1 = há versão nova | 2 = não deu para verificar
```

A versão instalada vem da própria aplicação rodando, que diz o que está no ar
agora; o arquivo `VERSAO` gravado pelo instalador é só a rede de segurança para
quando o servidor estiver fora do ar.

Do lado do TRT, **duas fontes são cruzadas**: o texto "Versão Atual" do portal e
o nome do instalador publicado na página de instalação. A segunda existe porque
o tribunal precisa trocar o arquivo para a versão nova ficar baixável — então
ela pega o caso de publicarem a versão e esquecerem de mexer no texto. Se as
duas discordarem, vale a maior e a divergência é reportada; se só uma responder,
a conferência segue com ela e diz isso. O aviso entra na notificação do fim da
rodada.

Instalar continua sendo passo seu, porque o instalador tem que ser conferido
contra o MD5 publicado pelo tribunal: atualize `VERSAO` e `MD5_ESPERADO` em
`scripts/instalar-pjecalc-linux.sh` e rode-o.

A extração roda de ponta a ponta sem intervenção. Se alguma etapa cair num
fallback que exige mão humana, o script só pede ENTER quando há terminal
interativo; sem TTY ele falha dizendo qual etapa não foi automatizada, em vez de
travar esperando uma tecla que não vem.

A extração sai com **0 só quando as duas planilhas foram gravadas**; qualquer
outro desfecho sai com 1. Quem chama olha o código de saída, e um sucesso falso
aqui vira mês sem índice sem ninguém notar.

### Seletores da tela de índices

Os campos de data são `rich-calendar-input` do RichFaces e o "Pesquisar" é um
`<a>` com `A4J.AJAX.Submit`, não um `input[type=submit]`. Os ids estão em
`pjecalc/model/indice.py`, e mudam entre as abas — repare que a TR carrega
`Indice` no meio do id e a IPCA-E não:

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

Para instalar num servidor — onde não há sessão gráfica e o fuso costuma ser
UTC — veja [`docs/servidor.md`](docs/servidor.md).

## Arquitetura

O código está separado em camadas, no formato MVC: o domínio não conhece o
Selenium, a saída no terminal mora num lugar só e o controlador é quem conhece
a ordem das etapas.

```
pjecalc/
├── config.py                  configuração da rodada, lida do ambiente
├── model/                     domínio puro — nada de Selenium aqui
│   ├── competencia.py         MM/AAAA e a virada de ano
│   ├── indice.py              TR e IPCA-E: intervalo e ids JSF
│   └── tabela.py              registros extraídos, deduplicação, cabeçalhos
├── view/
│   └── console.py             tudo que é escrito para quem lê a rodada
├── controller/
│   └── extracao.py            a ordem das etapas e o código de saída
└── infra/                     adaptadores para o mundo
    ├── navegador.py           o driver, a sessão e as capturas de evidência
    ├── planilha.py            gravação do .xlsx
    └── paginas/               um objeto por tela do PJe-Calc
        ├── menu.py            menu lateral de principal.jsf
        ├── atualizacao.py     "Atualização de Tabelas e Índices"
        ├── correcao_monetaria.py   abas, filtros de data e "Pesquisar"
        └── grade.py           leitura paginada do modal ou da tabela da página
```

A divisão não é enfeite: as regras que custaram caro — qual mês pedir, o que é
linha de dado e o que é cabeçalho repetido, quando a paginação acabou — saíram
do meio do laço do Selenium e viraram código testável sem navegador. O que
**precisa** de navegador ficou em `infra/paginas`, um objeto por tela, cada um
com os seletores e as armadilhas daquela tela ao lado do código que as evita.

As duas grades de resultado (o modal do RichFaces e a tabela desenhada na
página) expõem a mesma interface — cabeçalhos, linhas, próxima página — e o
laço de paginação é escrito uma vez só, sem saber em qual das duas está.

## Testes

```bash
./tests/rodar.sh
```

139 testes, sem rede e sem subir o PJe-Calc — tudo que toca o mundo (`curl`,
`systemctl`, `notify-send`, o lançador, a extração) está substituído por dublê.

| Arquivo | Cobre |
|---|---|
| `tests/test_datas.py` | TR no mês seguinte, IPCA-E no corrente, virada de ano, nomes e pastas de saída |
| `tests/test_tabela.py` | deduplicação da paginação, cabeçalho repetido, coluna a mais, ordem das linhas |
| `tests/test_console.py` | a linha `Pasta :` que o shell lê, e a recusa de pedir ENTER sem terminal |
| `tests/test_verificar_versao.py` | leitura do portal, ordem das fontes, comparação numérica, os três códigos de saída |
| `tests/test_timer.py` | todo mês tem rodada no dia 6 ou no primeiro dia útil seguinte, por 24 meses |
| `tests/test_lancador.sh` | `url`, `esperar`, `status`, recusa sem `pjecalc.env` |
| `tests/test_rodada_mensal.sh` | marcador, `--forcar`, falhas, captura da pasta, aviso de versão |

A extração em si (Selenium contra o PJe-Calc) não cabe nesse formato. Essa se
verifica rodando de verdade:

```bash
./scripts/rodada-mensal.sh --forcar
```

### Os testes são testados

A suíte foi validada por mutação: quebra-se o código de propósito e confere-se
que ela acusa. As nove mutações da primeira rodada estão listadas no commit que
introduziu os testes — duas passaram de primeira e revelaram buracos reais (um
mês sem disparo nenhum não era conferido, e uma asserção com `in` aceitava o
fallback no lugar do caminho preferido). As oito da separação em camadas estão
no commit que a fez, e cobrem o que saiu do laço do Selenium: deduplicação,
reconhecimento de competência, virada de ano, a linha que o shell lê.

Ao mexer na lógica de decisão, repita: quebre, rode, veja falhar.

## Configuração

Tudo que muda entre uma rodada e outra vem do ambiente e é lido num lugar só,
`pjecalc/config.py`. O que é da tela — intervalo de datas e ids JSF de cada
índice — está em `pjecalc/model/indice.py`.

| Variável | Para quê |
|---|---|
| `PJECALC_TR_ATE` / `PJECALC_IPCAE_ATE` | `MM/AAAA` final, no lugar do calculado |
| `PJECALC_FF_HEADLESS` | `1` força Firefox sem janela, `0` força com; sem a variável, decide pelo `DISPLAY` |
| `PJECALC_AVISO_CMD` | comando que recebe o aviso do fim da rodada (servidor) |
| `PJECALC_DEBUG=1` | screenshot e dump de DOM a cada etapa |
| `PJECALC_HOME` | instalação do PJe-Calc (padrão `~/.local/share/pjecalc`) |

## Comandos do lançador

```
pjecalc.sh start | stop | restart | status | abrir | foreground | url | esperar | compilar
```

## Requisitos

- Firefox, `7z`, `curl`, [`mise`](https://mise.jdx.dev)
- Python 3.10+
- ~600 MB livres (103 MB depois de tirar as partes Windows)
