#!/bin/bash
# Gestione bot Discord (start, stop, restart, status, logs, update) con variabili da .env

# Cartella e percorso assoluto di questo script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SELF="$SCRIPT_DIR/$(basename "$0")"

# Carico le variabili da .env (nella stessa cartella dello script)
set -a
source "$SCRIPT_DIR/.env"
set +a

BOT_DIR="${BOT_DIR:-$SCRIPT_DIR}"
BOT_SCRIPT="${BOT_SCRIPT:-bot.py}"
LOG_FILE="$BOT_DIR/logs/bot.log"

send_discord() {
    [ -z "$WEBHOOK_URL" ] && return
    # Costruisce il JSON con python3 per gestire virgolette e a capo nel messaggio
    PAYLOAD=$(python3 -c 'import json, sys; print(json.dumps({"content": sys.argv[1]}))' "$1")
    curl -H "Content-Type: application/json" -X POST -d "$PAYLOAD" "$WEBHOOK_URL" > /dev/null 2>&1
}

cd "$BOT_DIR" || exit 1
mkdir -p "$BOT_DIR/logs"

# Funzione per aggiornare il codice da Git
update_code() {
    echo "Aggiornamento del codice da Git..."

    # Ferma il bot prima di aggiornare
    "$SELF" stop

    # Svuota il file di log prima di aggiornare
    : > "$LOG_FILE"
    echo "File di log svuotato."

    # Esegue il pull del codice dal repository Git e cattura l'output
    GIT_OUTPUT=$(git pull origin main 2>&1)
    GIT_PULL_RESULT=$?
    echo "$GIT_OUTPUT"

    if [ $GIT_PULL_RESULT -eq 0 ]; then
        echo "🆕 Codice aggiornato con successo."
        send_discord "🆕 Il codice del bot è stato **aggiornato** da Git."

        # Installa/aggiorna le dipendenze
        echo "Installazione/aggiornamento delle dipendenze..."
        source "$VENV"  # Attiva l'ambiente virtuale
        pip install -r requirements.txt
        deactivate # Disattiva l'ambiente virtuale

        # Riavvia il bot dopo l'aggiornamento
        "$SELF" start
    else
        echo "❌ Errore durante l'aggiornamento del codice."
        send_discord "❌ Errore durante l'aggiornamento del codice da Git. Errore: $GIT_OUTPUT"
    fi
}

case "$1" in
    start)
        if pgrep -f "python3 $BOT_SCRIPT" > /dev/null
        then
            echo "⚠️  Il bot è già in esecuzione!"
        else
            echo "✅ Avvio del bot..."
            source "$VENV"
            # In append: bot.py scrive nello stesso file tramite logging
            nohup python3 "$BOT_SCRIPT" >> "$LOG_FILE" 2>&1 &
            echo "Bot avviato (log in $LOG_FILE)"
            send_discord "✅ Il bot è stato **avviato** sul server."
        fi
        ;;
    stop)
        if pgrep -f "python3 $BOT_SCRIPT" > /dev/null
        then
            echo "🛑 Arresto del bot..."
            pkill -f "python3 $BOT_SCRIPT"
            # Attende la chiusura pulita (salvataggio delle sessioni vocali), max 15 secondi
            for _ in $(seq 1 15); do
                pgrep -f "python3 $BOT_SCRIPT" > /dev/null || break
                sleep 1
            done
            echo "Bot fermato."
            send_discord "🛑 Il bot è stato **fermato** manualmente."
        else
            echo "⚠️  Il bot non è in esecuzione."
        fi
        ;;
    restart)
        "$SELF" stop
        sleep 2
        "$SELF" start
        send_discord "🔄 Il bot è stato **riavviato**."
        ;;
    status)
        if PID=$(pgrep -f "python3 $BOT_SCRIPT")
        then
            START_TIME=$(ps -o etime= -p "$PID")
            echo "✅ Il bot è in esecuzione (PID: $PID) da $START_TIME."
        else
            echo "❌ Il bot non è attivo."
        fi
        ;;
    logs)
        tail -f "$LOG_FILE"
        ;;
    update)
        update_code
        ;;
    *)
        echo "Uso: $0 {start|stop|restart|status|logs|update}"
        exit 1
        ;;
esac

exit 0
