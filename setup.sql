DROP DATABASE IF EXISTS discord_bot;
CREATE DATABASE IF NOT EXISTS discord_bot;
/* CREATE USER IF NOT EXISTS 'botuser'@'localhost' IDENTIFIED BY 'Utopia39!';
 GRANT ALL PRIVILEGES ON discord_bot.* TO 'botuser'@'localhost';
 FLUSH PRIVILEGES; */
USE discord_bot;
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    nickname VARCHAR(100) NOT NULL,
    username VARCHAR(100) NOT NULL,
    xp INT DEFAULT 0,
    level INT DEFAULT 1,
    message_count INT DEFAULT 0,
    reaction_count INT DEFAULT 0,
    voice_seconds INT DEFAULT 0,
    night_voice_seconds INT DEFAULT 0,
    video_seconds INT DEFAULT 0,
    stream_seconds INT DEFAULT 0,
    last_activity_date DATE DEFAULT NULL,
    activity_streak INT DEFAULT 0,
    daily_xp INT DEFAULT 0,
    max_daily_xp INT DEFAULT 0,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS channels (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100) NOT NULL -- Altre informazioni sul canale (es. categoria, ecc.)
);
CREATE TABLE IF NOT EXISTS voice_activity (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    join_time DATETIME NOT NULL,
    leave_time DATETIME,
    duration_seconds INT DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (channel_id) REFERENCES channels(id),
    INDEX (join_time)
);
-- Tabella per definire i badge disponibili
CREATE TABLE IF NOT EXISTS badges (
    id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    icon VARCHAR(255) NOT NULL,
    check_value INT DEFAULT NULL,
    UNIQUE(name)
);
-- Tabella per tracciare i badge ottenuti dagli utenti
CREATE TABLE IF NOT EXISTS user_badges (
    user_id BIGINT NOT NULL,
    badge_id INT NOT NULL,
    earned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, badge_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (badge_id) REFERENCES badges(id) ON DELETE CASCADE
);
-- Tabella per il tracciamento degli utilizzi della soundboard
CREATE TABLE IF NOT EXISTS soundboard_usage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    sound_id BIGINT NOT NULL,
    sound_name VARCHAR(100) NOT NULL DEFAULT 'Sconosciuto',
    used_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (channel_id) REFERENCES channels(id),
    INDEX (used_at)
);
-- Pulizia dei dati vecchi (opzionale)
-- Rimuovi le sessioni di voice_activity che non hanno leave_time e sono più vecchie di 2 giorni
-- DELETE FROM voice_activity WHERE leave_time IS NULL AND join_time < NOW() - INTERVAL 2 DAY;