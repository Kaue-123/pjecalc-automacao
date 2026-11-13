#!/usr/bin/env bash
# PJe-Calc Cidadao 2.16.0 — lancador para Linux
# O bundle oficial do TRT8 so traz .bat + JRE Windows, mas a aplicacao e Java puro
# (Tomcat 7 embarcado + H2). Aqui usamos um JDK 8 do mise no lugar do JRE embutido.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JAVA_HOME_8="${PJECALC_JAVA_HOME:-$HOME/.local/share/mise/installs/java/temurin-8.0.504+1}"
JAVA="$JAVA_HOME_8/bin/java"
JAVAC="$JAVA_HOME_8/bin/javac"
PIDFILE="$APP_DIR/.pjecalc.pid"
# Sobe so o Tomcat, sem a UI do Lancador oficial — ver PjeCalcServico.java.
CLASSES_SERVICO="$APP_DIR/bin/servico"
FONTE_SERVICO="$APP_DIR/bin/servico/PjeCalcServico.java"
# Parametros que vieram do iniciarPjeCalc.bat do instalador oficial. O
# instalar-pjecalc-linux.sh extrai do .bat e grava aqui; nao ficam versionados.
ENVFILE="$APP_DIR/pjecalc.env"
[ -f "$ENVFILE" ] && . "$ENVFILE"
: "${PJECALC_TOKEN_SERVICOS:?faltando pjecalc.env — rode scripts/instalar-pjecalc-linux.sh}"
: "${PJECALC_SEGURANCA_CONTEXTO:=https://pje.trtXX.jus.br/pje-seguranca}"
LOGFILE="$APP_DIR/pjecalc.log"
# Dono do endereco: quem precisa dele pergunta com `pjecalc.sh url`.
PORTA="${PJECALC_PORTA:-9257}"
URL="http://localhost:$PORTA/pjecalc/pages/principal.jsf"
ARGS_JVM=(
  -Djava.awt.headless=true
  -Duser.timezone=GMT-3
  -Dfile.encoding=ISO-8859-1
  -Dseguranca.pjecalc.tokenServicos="$PJECALC_TOKEN_SERVICOS"
  -Dseguranca.pjekz.servico.contexto="$PJECALC_SEGURANCA_CONTEXTO"
  -Xms1024m -Xmx2048m -XX:MaxPermSize=512m
  -cp "bin/pjecalc.jar:$CLASSES_SERVICO" PjeCalcServico
)

# Java 8 e obrigatorio: em Java 21 o JBoss Seam/Drools quebra no encapsulamento
# de modulos (InaccessibleObjectException), mesmo com --add-opens.
[ -x "$JAVA" ] || { echo "Java 8 nao encontrado em $JAVA_HOME_8"; \
  echo "Instale com: mise install java@temurin-8.0.504+1"; exit 1; }

# Sob systemd nao ha pidfile: o modo foreground de proposito nao escreve um.
# Olhar so o pid faria o `status` dizer "parado" com o servico no ar, e o `start`
# tentar subir uma segunda JVM para brigar pela porta e pelo banco H2.
sob_systemd() { systemctl --user is-active --quiet pjecalc.service 2>/dev/null; }

rodando() {
  sob_systemd && return 0
  [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

quem_controla() {
  if sob_systemd; then echo "systemd"; else echo "pid $(cat "$PIDFILE" 2>/dev/null)"; fi
}

start() {
  if rodando; then echo "Ja esta rodando ($(quem_controla)). URL: $URL"; return 0; fi
  cd "$APP_DIR"
  [ -f "$CLASSES_SERVICO/PjeCalcServico.class" ] || compilar_servico
  # setsid: solta o processo numa sessao propria, para ele nao morrer junto com
  # o terminal (ou com a limpeza de jobs de quem chamou o script).
  setsid nohup "$JAVA" "${ARGS_JVM[@]}" > "$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"
  echo -n "Subindo PJe-Calc"
  if esperar; then
    echo " OK"; echo "URL: $URL"; echo "Log: $LOGFILE"; return 0
  fi
  echo " FALHOU"; tail -20 "$LOGFILE"; return 1
}

# O Tomcat leva uns 10 s para publicar /pjecalc depois que o processo sobe.
esperar() {
  for _ in $(seq 1 "${PJECALC_TENTATIVAS:-90}"); do
    curl -sf -o /dev/null --max-time 5 "$URL" && return 0
    echo -n "."; sleep 2
  done
  return 1
}

compilar_servico() {
  [ -f "$FONTE_SERVICO" ] || { echo "Falta $FONTE_SERVICO — rode scripts/instalar-pjecalc-linux.sh"; exit 1; }
  [ -x "$JAVAC" ] || { echo "javac nao encontrado em $JAVA_HOME_8 (precisa do JDK, nao do JRE)"; exit 1; }
  "$JAVAC" -encoding UTF-8 -cp "$APP_DIR/bin/pjecalc.jar" -d "$CLASSES_SERVICO" "$FONTE_SERVICO"
}

stop() {
  if sob_systemd; then
    echo "Sob systemd — parando a unidade."
    systemctl --user stop pjecalc.service
    return 0
  fi
  if ! rodando; then echo "Nao esta rodando."; rm -f "$PIDFILE"; return 0; fi
  kill "$(cat "$PIDFILE")"
  for _ in $(seq 1 20); do rodando || break; sleep 1; done
  rodando && kill -9 "$(cat "$PIDFILE")" 2>/dev/null || true
  rm -f "$PIDFILE"; echo "Parado."
}

# Sem setsid e sem pidfile: o systemd precisa do java como processo principal.
foreground() {
  cd "$APP_DIR"
  [ -f "$CLASSES_SERVICO/PjeCalcServico.class" ] || compilar_servico
  exec "$JAVA" "${ARGS_JVM[@]}"
}

case "${1:-start}" in
  start)   start ;;
  foreground) foreground ;;
  stop)    stop ;;
  restart) stop; start ;;
  status)  if rodando; then echo "rodando ($(quem_controla)) — $URL"; else echo "parado"; fi ;;
  abrir)   start && xdg-open "$URL" >/dev/null 2>&1 & ;;
  url)     echo "$URL" ;;
  esperar) esperar && echo "no ar" || { echo "sem resposta em $URL"; exit 1; } ;;
  compilar) compilar_servico ;;
  *) echo "uso: $0 {start|stop|restart|status|abrir|foreground|url|esperar|compilar}"; exit 1 ;;
esac
