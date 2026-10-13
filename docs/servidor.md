# Instalação em servidor

O desenho é o mesmo da estação de trabalho — unidades de usuário do systemd, o
PJe-Calc servindo em `localhost`, a extração sem janela. O que muda são quatro
premissas que num desktop são invisíveis.

## 1. Linger: sem ele o timer deixa de existir

Unidades `--user` vivem enquanto o usuário tem sessão. Num servidor o fluxo
normal é entrar por SSH, instalar, habilitar, conferir que está armado e sair —
e é na saída que o gerenciador de usuário encerra, levando o timer junto.

Não há erro, não há log, não há rodada no dia 6. Só a planilha que não apareceu.

```bash
loginctl enable-linger "$USER"
loginctl show-user "$USER" -p Linger      # tem que dizer Linger=yes
```

O `scripts/instalar-automacao.sh` tenta habilitar sozinho e avisa se não
conseguir (alguns sistemas exigem `sudo`).

## 2. Aviso: `notify-send` não existe aqui

Num servidor não há sessão gráfica, e a notificação de desktop simplesmente não
acontece. Para que o silêncio não vire falsa tranquilidade, toda rodada **sempre**
registra o aviso em dois lugares que independem de canal:

- `~/.local/state/pjecalc-automacao/ultimo-aviso`
- o journal da unidade (`journalctl --user -u pjecalc-indices`)

Para receber o aviso em algum lugar, defina `PJECALC_AVISO_CMD`. O comando recebe
três variáveis de ambiente:

| Variável | Conteúdo |
|---|---|
| `PJECALC_AVISO_TITULO` | `Indices TRT 8: planilhas prontas` ou `...: falhou` |
| `PJECALC_AVISO_CORPO` | pasta, arquivos e eventual aviso de versão |
| `PJECALC_AVISO_URGENCIA` | `normal` ou `critical` |

Exemplos, num drop-in da unidade
(`~/.config/systemd/user/pjecalc-indices.service.d/aviso.conf`):

```ini
[Service]
# e-mail
Environment=PJECALC_AVISO_CMD=printf '%%s' "$PJECALC_AVISO_CORPO" | mail -s "$PJECALC_AVISO_TITULO" eu@exemplo.com

# ntfy
Environment=PJECALC_AVISO_CMD=curl -s -H "Title: $PJECALC_AVISO_TITULO" -d "$PJECALC_AVISO_CORPO" https://ntfy.sh/meu-topico
```

Se o comando falhar, a rodada continua e a falha do canal fica no journal — o
aviso nunca derruba a extração.

## 3. Fuso: o servidor provavelmente está em UTC

O `OnCalendar` já traz o fuso explícito:

```
OnCalendar=Mon..Fri *-*-06,07,08 11:00:00 America/Sao_Paulo
```

Sem isso, num host em UTC as "11:00" seriam 8h da manhã no Brasil. Com o fuso
fixado, a rodada cai às 11h de Belém independentemente da configuração do host.

## 4. Sem display, sem janela

O `busca_indices_rpa.py` decide sozinho: sem `DISPLAY` nem `WAYLAND_DISPLAY`, o
Firefox sobe headless. Numa estação com sessão gráfica o padrão continua sendo a
janela visível, que ajuda a depurar. `PJECALC_FF_HEADLESS=0/1` decide à força.

O **servidor** PJe-Calc nunca precisou de display: ele roda como serviço desde
que deixou de usar a UI do lançador (veja o README).

## Passo a passo

```bash
# dependências: firefox, 7z, curl, mise, python3
./scripts/instalar-pjecalc-linux.sh     # baixa, confere MD5, instala, compila
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./scripts/instalar-automacao.sh         # unidades + linger + habilita o timer
./tests/rodar.sh                        # 97 testes, sem rede
./scripts/rodada-mensal.sh --forcar     # prova real, ~6 min
```

O `--forcar` grava o marcador do mês corrente, então a próxima rodada automática
será no mês seguinte. Para deixar o mês em aberto, apague
`~/.local/state/pjecalc-automacao/ultima-rodada` depois do teste.

## Conferências depois de instalar

```bash
loginctl show-user "$USER" -p Linger                 # Linger=yes
systemctl --user is-enabled pjecalc.service          # enabled
systemctl --user list-timers pjecalc-indices.timer   # dia e hora certos
cat ~/.local/state/pjecalc-automacao/ultimo-aviso    # último resultado
```

## O que buscar quando algo der errado

```bash
journalctl --user -u pjecalc-indices -n 100   # a rodada
journalctl --user -u pjecalc -n 100           # o servidor
ls ~/Projects/pjecalc-automacao/output/*/     # as planilhas, por data
```

Numa falha, a pasta da rodada guarda as capturas de tela do momento em que
quebrou. `PJECALC_DEBUG=1` acrescenta captura e dump de DOM de cada etapa.
