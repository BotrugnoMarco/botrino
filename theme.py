"""
Tema del server: tutti i testi, i nomi e i colori che gli utenti vedono.

Botrino è l'Automa del Thermopolium, un bancone di Pompei dove ci si ritrova
per giocare, studiare e guardare le partite. Per cambiare identità al server
basta modificare questo file: il resto del codice legge da qui.
"""
import random

# --- Identità ---
SERVER_NAME = "Thermopolium"
BOT_TITLE = "l'Automa del Thermopolium"
FOOTER = "Botrino, l'Automa del Thermopolium 🍷"

# --- Colori (palette pompeiana) ---
# Il colore principale si può ancora sovrascrivere con PRIMARY_COLOR nel .env.
COLOR_PRIMARY = 0xB23A2F   # rosso pompeiano
COLOR_GOLD = 0xE2B24C      # foglia d'oro: traguardi, livelli, albo d'onore

# Barra di avanzamento di livello e profilo
PROGRESS_FULL = "🟥"
PROGRESS_EMPTY = "⬛"


def progress_bar(progress: float, length: int) -> str:
    filled = int(max(0.0, min(progress, 1.0)) * length)
    return PROGRESS_FULL * filled + PROGRESS_EMPTY * (length - filled)


# --- Gradi (ruoli per livello, in ordine crescente) ---
# Servono solo per i testi: i ruoli veri sono collegati ai livelli con LEVEL_ROLES nel .env.
RANKS = ["🧳 Forestiero", "🥾 Viandante", "🍷 Cliente", "🏺 Cittadino", "🛡️ Patrono", "📜 Senatore", "⚡ Divo"]

# --- Badge ---
# Formato: (id, nome, descrizione, icona, valore_controllo)
# Gli ID e i valori di controllo non vanno cambiati: sono quelli salvati nel database.
# All'avvio nome, descrizione e icona vengono aggiornati da soli (upsert per ID).
BADGES = [
    # Attività
    (1, 'Voce del Foro', 'Lascia 100 messaggi sui muri del Thermopolium.', '💬', 100),
    (2, 'Sempre al Bancone', 'Passa 50 ore in totale nelle sale vocali.', '🪑', 50 * 3600),
    (3, 'Nottambulo', 'Passa 10 ore in vocale tra mezzanotte e le 05:00.', '🦉', 10 * 3600),
    (4, 'Alla Salute!', 'Alza la coppa 50 volte: assegna 50 reazioni ai messaggi.', '🍷', 50),
    # Traguardi
    (5, "Corona d'Alloro", 'Raggiungi il livello 25.', '🌿', 25),
    (6, 'Fondatore', 'Tra i primi 10 ospiti ad aver conosciuto l\'Automa.', '🗝️', 10),
    (7, 'Mecenate', 'Ha offerto una calda all\'Automa con una donazione.', '🪙', None),  # Manuale
    # Record e strisce
    (8, 'Clessidra', 'Detiene la sessione vocale ininterrotta più lunga del server.', '⏳', None),  # Record
    (9, 'Veni Vidi Vici', 'Detiene il record di XP guadagnati in un solo giorno.', '⚡', None),  # Record
    (10, 'Legionario', 'Marcia ogni giorno: 7 giorni di fila con XP guadagnati.', '🛡️', 7),
    (11, 'Un Anno a Pompei', 'Ospite del Thermopolium da almeno un anno.', '🦅', 365),  # Giorni
    (12, 'Ritratto', 'Mostra il volto: 5 ore in totale con la webcam accesa.', '🖼️', 5 * 3600),
    (13, 'In Scena', 'Va in scena: 10 ore in totale di streaming (Go Live).', '🎭', 10 * 3600),
    # Livelli superiori
    (14, 'Vigile Notturno', 'Fa la ronda come i vigiles: 50 ore in vocale tra mezzanotte e le 05:00.', '🕯️', 50 * 3600),
    (15, 'Cicerone', 'Lascia 1000 messaggi sui muri del Thermopolium.', '📜', 1000),
    (16, 'Trionfo', 'Raggiungi il livello 50.', '🏛️', 50),
    (17, 'Fuoco di Vesta', 'Come il fuoco sacro, non si spegne mai: 30 giorni di fila con XP guadagnati.', '🔥', 30),
]


def badge(badge_id: int):
    """Restituisce la tupla del badge con quell'ID, o None."""
    return next((b for b in BADGES if b[0] == badge_id), None)


BADGE_DM_TITLE = "🏅 Un nuovo traguardo!"
BADGE_DM_TEXT = "L'Oste ha inciso il tuo nome sulla parete del Thermopolium: hai ottenuto **{name}**!"
NO_BADGES = "Nessun traguardo ancora inciso sulla parete."
NO_BADGES_USER = "{name} non ha ancora nessun traguardo inciso sulla parete."

# --- Benvenuto ---
WELCOME_TITLE = "🏛️ Salve, {name}!"
WELCOME_TEXT = (
    "Un nuovo forestiero entra al **Thermopolium**. {mention}, l'Automa ti versa una "
    "calda fumante e ti fa posto al Triclinio. 🍷"
)
WELCOME_FOOTER = "Sei il {count}° ospite del Thermopolium"

# --- Passaggio di livello ---
LEVEL_UP_LINES = [
    "🎉 {mention} sale al livello **{level}**! L'Automa versa una calda in suo onore. 🍷",
    "🏛️ Il Senato prende nota: {mention} ha raggiunto il livello **{level}**!",
    "🌿 Una nuova foglia d'alloro per {mention}: livello **{level}**!",
    "⚙️ *Clank, clank.* L'Automa annuncia che {mention} è al livello **{level}**!",
]


def level_up_message(mention: str, level: int) -> str:
    return random.choice(LEVEL_UP_LINES).format(mention=mention, level=level)


# --- Supporto (Ko-fi) ---
def kofi_url(username: str) -> str:
    return f"https://ko-fi.com/{username}"


KOFI_FIELD_NAME = "🪙 Mecenati"
KOFI_LINK_TEXT = "Offri una calda all'Automa"


def kofi_link(username: str) -> str:
    return f"[🪙 {KOFI_LINK_TEXT}]({kofi_url(username)})"


DONATE_TITLE = "🪙 Offri una calda all'Automa"
DONATE_TEXT = (
    "Botrino gira a olio, ingranaggi e qualche moneta. Se ti piace averlo al bancone, "
    "puoi offrirgli una calda su Ko-fi: ogni contributo tiene acceso il fuoco del Thermopolium.\n\n"
    "Chi dona riceve il traguardo 🪙 **Mecenate**."
)
DONATE_FOOTER = "Grazie, mecenate!"

# --- Report vocali ---
REPORT_DAILY_TITLE = "Acta Diurna: le ultime 24 ore"
REPORT_WEEKLY_TITLE = "Il registro della settimana"
REPORT_EMPTY = "💤 Il bancone è rimasto vuoto: nessuna attività in questo periodo."
REPORT_TOTAL_TIME = "🕒 **Ore passate ai tavoli**"
REPORT_ACTIVE_USERS = "👥 **Ospiti presenti**"
REPORT_TOP_USERS = "🏆 I più assidui"
REPORT_CHANNELS = "🏺 Le sale più frequentate"
REPORT_SOUNDBOARD = "🎵 I suoni più richiesti"
REPORT_FOOTER = "Registro compilato dall'Automa • Thermopolium"

# --- Classifiche ---
LEADERBOARD_VOICE_TITLE = "🏆 I più assidui del Thermopolium (tempo in vocale)"
LEADERBOARD_LEVEL_TITLE = "🏆 Le stelle del Thermopolium (livelli)"
LEADERBOARD_EMPTY = "Il bancone è ancora vuoto: nessun dato da mostrare."

# --- Albo d'onore (record) ---
RECORDS_TITLE = "🏛️ L'Albo d'Onore del Thermopolium"
RECORDS_TEXT = "I primati incisi sulla parete, in attesa di qualcuno che li batta."
RECORDS_NONE = "Ancora nessuna incisione."
RECORDS_HOLDER = "Inciso da: **{holder}**"
RECORD_DAILY_XP = "⚡ Veni Vidi Vici"          # più XP in un giorno
RECORD_LONGEST_SESSION = "⏳ La Clessidra"      # sessione vocale più lunga
RECORD_NIGHT = "🦉 Vigile della Notte"          # più tempo notturno
RECORD_TOTAL_VOICE = "🛋️ Padrone del Triclinio"  # più tempo in vocale
RECORD_MESSAGES = "📜 Il Cicerone"              # più messaggi
RECORD_STREAK = "🔥 Fuoco di Vesta"             # striscia più lunga

# --- Profilo e livello ---
PROFILE_TITLE = "📜 La tavoletta di {name}"
LEVEL_TITLE = "🏛️ Livello di {name}"
PROFILE_JOINED = "Ospite dal {date}"

# --- Aiuto ---
HELP_TITLE = "⚙️ I comandi dell'Automa"
HELP_TEXT = "Tira la leva giusta e l'Automa risponde:"

# --- Stato del bot su Discord ---
PRESENCE = "Serve calde al bancone 🍷"
