# Bot Discord per la Gestione di Community

Questo è un bot per Discord multifunzione progettato per aumentare il coinvolgimento e l'interazione all'interno di un server. Include un sistema di esperienza (XP), classifiche, report di attività e altro ancora.

## ✨ Funzionalità Principali

- **Sistema di Esperienza (XP) e Livelli**: Gli utenti guadagnano punti esperienza partecipando attivamente al server:
  - Invio di messaggi
  - Tempo trascorso nei canali vocali
  - Aggiunta di reazioni ai messaggi
- **Ruoli Automatici**: Salendo di livello, gli utenti possono ottenere automaticamente ruoli speciali configurati dall'amministratore.
- **Report di Attività Vocale**:
  - **Report Automatico**: Ogni giorno, il bot pubblica un riepilogo delle sessioni vocali più lunghe delle ultime 24 ore in un canale designato.
  - **Comando `!report`**: Qualsiasi utente può generare un report aggiornato delle ultime 24 ore in qualsiasi momento.
- **Classifiche**:
  - **`!leaderboard`**: Mostra la classifica degli utenti con più punti esperienza nel server.
- **Controllo Livello**:
  - **`!level`**: Permette a ogni utente di controllare il proprio livello attuale e i punti esperienza mancanti per il prossimo livello.
- **Architettura Modulare**: Il bot è costruito con una struttura a `cogs` (estensioni di `discord.py`), che rende il codice pulito, organizzato e facile da espandere con nuove funzionalità.
- **Persistenza dei Dati**: Tutte le informazioni su utenti, livelli e attività sono salvate in un database MySQL.

## 🚀 Prerequisiti

- Python 3.8 o superiore
- Un server MySQL in esecuzione
- Un token per un bot Discord

## ⚙️ Installazione e Configurazione

1.  **Clona il repository**:

    ```bash
    git clone https://github.com/BotrugnoMarco/discord-bot.git
    cd discord-bot
    ```

2.  **Crea il file di configurazione**:
    Crea un file chiamato `.env` nella directory principale del progetto. Questo file conterrà tutte le variabili di configurazione. Puoi usare il seguente template:

    ```env
    # Token del bot Discord
    DISCORD_TOKEN="IL_TUO_TOKEN"

    # Credenziali del database MySQL
    DB_HOST="localhost"
    DB_USER="root"
    DB_PASSWORD="la_tua_password"
    DB_NAME="discord_bot"

    # ID dei canali e ruoli
    REPORT_CHANNEL_ID=123456789012345678
    WELCOME_CHANNEL_ID=123456789012345678
    LEVEL_UP_CHANNEL_ID=123456789012345678
    GUILD_ID=123456789012345678

    # Fuso orario per i report (es. Europe/Rome)
    BOT_TIMEZONE="Europe/Rome"

    # Impostazioni AFK
    AFK_CHANNEL_IDS="123456789,987654321"    # Canali AFK (il primo è quello di destinazione)
    AFK_MOVE_TIMEOUT_MINUTES=30              # Minuti dopo i quali spostare utente mutato
    AFK_EXCLUDED_USER_IDS="11111,22222"      # Utenti immuni al move AFK (separati da virgola)
    ```

3.  **Prepara il Database**:
    Esegui lo script `setup.sql` sul tuo server MySQL per creare le tabelle necessarie:

    ```sql
    -- Esempio di comando da terminale MySQL
    mysql -u root -p nome_database < setup.sql
    ```

4.  **Installa le dipendenze**:

    ```bash
    pip install -r requirements.txt
    ```

5.  **Avvia il bot**:
    ```bash
    python bot.py
    ```

## 🤖 Comandi Disponibili

- `!report`: Genera e invia nel canale corrente un report delle sessioni vocali delle ultime 24 ore.
- `!leaderboard`: Mostra la classifica dei 10 utenti con più tempo trascorso nei canali vocali.
- `!level_leaderboard`: Mostra la classifica dei 10 utenti con il livello più alto.
- `!level [utente]`: Mostra il tuo livello, XP e barra di progresso. Se menzioni un altro utente, mostra le sue statistiche.
- `!donate`: Mostra il link per supportare lo sviluppo e il mantenimento del bot.
- `!help_botrino`: Mostra un messaggio di aiuto con la lista di tutti i comandi.

---
