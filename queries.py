"""
Questo file contiene tutte le query SQL utilizzate dal bot,
organizzate per funzionalità per una facile manutenzione.
"""

# --- REPORT QUERY ---

# Query generica per i report. Seleziona le sessioni in un dato intervallo di tempo.
report_query = """
    SELECT 
        va.user_id,
        u.nickname,
        u.username,
        u.level,
        c.id AS channel_id,
        c.name AS channel_name,
        va.join_time,
        va.leave_time,
        va.duration_seconds
    FROM voice_activity va
        JOIN users u ON va.user_id = u.id
        JOIN channels c ON va.channel_id = c.id
    WHERE va.join_time < %s 
      AND va.leave_time IS NOT NULL
      AND va.leave_time > %s;
"""


# --- LEADERBOARD QUERIES ---

# Query per la classifica basata sul tempo totale in vocale (sessioni concluse).
leaderboard_query = """
    SELECT u.id AS user_id, u.username, u.nickname, u.level, SUM(va.duration_seconds) AS total_secs
    FROM voice_activity va
    JOIN users u ON va.user_id = u.id
    WHERE va.leave_time IS NOT NULL
    GROUP BY u.id, u.username, u.nickname, u.level
    ORDER BY total_secs DESC
"""

# Query per la classifica basata sul livello e l'XP.
level_leaderboard_query = """
    SELECT user_id, username, nickname, level, xp
    FROM users
    ORDER BY level DESC, xp DESC
    LIMIT 10;
"""

# --- Query per i Badge ---

# Query per ottenere i badge di un utente
get_user_badges_query = """
SELECT b.name, b.description, b.icon
FROM user_badges ub
JOIN badges b ON ub.badge_id = b.id
WHERE ub.user_id = %s;
"""

# Query per ottenere tutti i badge e i loro requisiti
get_all_badges_query = "SELECT id, name, description, icon, check_value FROM badges"

# Query per aggiungere un badge a un utente
add_badge_to_user_query = """
INSERT IGNORE INTO user_badges (user_id, badge_id)
VALUES (%s, %s);
"""

# Query per inserire un nuovo tipo di badge (usata per il setup iniziale)
insert_badge_query = """
INSERT INTO badges (id, name, description, icon, check_value)
VALUES (%s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description), icon=VALUES(icon), check_value=VALUES(check_value);
"""

# --- VOICE ACTIVITY QUERIES ---

# Inserisce una nuova riga quando un utente inizia una sessione vocale.
insert_voice_activity_query = """
    INSERT INTO voice_activity (user_id, channel_id, join_time)
    VALUES (%s, %s, %s)
"""

# Aggiorna una sessione vocale al termine, impostando l'orario di uscita e la durata.
update_voice_activity_query = """
    UPDATE voice_activity
    SET leave_time = %s, duration_seconds = %s
    WHERE user_id = %s AND leave_time IS NULL
"""

# Aggiorna il canale di una sessione vocale attiva (per spostamenti).
update_voice_activity_channel_query = """
    UPDATE voice_activity
    SET channel_id = %s
    WHERE user_id = %s AND leave_time IS NULL
"""


# --- XP AND LEVEL QUERIES ---

# Recupera l'XP e il livello attuali di un utente, più tutte le statistiche per i badge.
get_user_xp_query = """
    SELECT xp, level, message_count, reaction_count, voice_seconds, night_voice_seconds, video_seconds, stream_seconds, last_activity_date, activity_streak, daily_xp, max_daily_xp
    FROM users WHERE id = %s
"""

# Aggiorna l'XP e il livello di un utente.
update_user_xp_level_query = """
    UPDATE users SET xp = %s, level = %s WHERE id = %s
"""

# Aggiorna l'XP giornaliero e il record personale
update_daily_xp_query = """
    UPDATE users SET daily_xp = %s, max_daily_xp = %s WHERE id = %s
"""

# Ottieni il record assoluto di XP giornalieri nel server
get_server_max_daily_xp_query = "SELECT MAX(max_daily_xp) as max_xp FROM users"

# Ottieni il detentore del record di XP giornalieri
get_record_daily_xp_query = """
    SELECT id, username, nickname, max_daily_xp 
    FROM users 
    ORDER BY max_daily_xp DESC 
    LIMIT 1
"""

# Ottieni il record assoluto di durata sessione vocale
get_server_max_voice_duration_query = "SELECT MAX(duration_seconds) as max_duration FROM voice_activity"

# Ottieni il detentore del record di durata sessione vocale
get_record_voice_duration_query = """
    SELECT u.id, u.username, u.nickname, va.duration_seconds 
    FROM voice_activity va 
    JOIN users u ON va.user_id = u.id 
    ORDER BY va.duration_seconds DESC 
    LIMIT 1
"""

# Conta il numero totale di utenti
get_user_count_query = "SELECT COUNT(*) as count FROM users"

# Ottieni gli ID dei primi N utenti registrati (ordinati per data di inserimento nel DB)
get_first_users_query = "SELECT id FROM users ORDER BY first_seen ASC, id ASC LIMIT %s"

# Verifica se un utente ha una sessione vocale di almeno X secondi
check_user_voice_record_query = "SELECT 1 FROM voice_activity WHERE user_id = %s AND duration_seconds >= %s LIMIT 1"

# Incrementa il conteggio dei messaggi di un utente.
increment_message_count_query = """
    UPDATE users SET message_count = message_count + 1 WHERE id = %s
"""

# Aggiorna il tempo totale in vocale notturno.
update_night_voice_seconds_query = """
    UPDATE users SET night_voice_seconds = night_voice_seconds + %s WHERE id = %s
"""

# Incrementa il conteggio delle reazioni di un utente.
increment_reaction_count_query = """
    UPDATE users SET reaction_count = reaction_count + 1 WHERE id = %s
"""

# Aggiorna il tempo totale in vocale.
update_voice_seconds_query = """
    UPDATE users SET voice_seconds = voice_seconds + %s WHERE id = %s
"""

# Aggiorna il tempo totale in video (cam).
update_video_seconds_query = """
    UPDATE users SET video_seconds = video_seconds + %s WHERE id = %s
"""

# Aggiorna il tempo totale in stream (Go Live).
update_stream_seconds_query = """
    UPDATE users SET stream_seconds = stream_seconds + %s WHERE id = %s
"""

# Aggiorna la striscia di attività.
update_streak_query = """
    UPDATE users SET last_activity_date = %s, activity_streak = %s WHERE id = %s
"""


# --- USER AND CHANNEL MANAGEMENT QUERIES ---

# Inserisce un nuovo utente se non è già presente nel database.
insert_user_query = "INSERT IGNORE INTO users (id, username, nickname) VALUES (%s, %s, %s)"

# Aggiorna il nome utente e il nickname di un utente.
update_user_names_query = """
    UPDATE users SET username = %s, nickname = %s WHERE id = %s
"""

# Inserisce un nuovo canale se non è già presente, oppure aggiorna il nome se esiste.
insert_channel_query = """
    INSERT INTO channels (id, name) VALUES (%s, %s)
    ON DUPLICATE KEY UPDATE name = VALUES(name)
"""


# --- UTILITY QUERIES ---

# Query leggera per mantenere attiva la connessione al database.
keep_alive_query = "SELECT 1"

