"""
Questo modulo contiene funzioni di utilità per formattare dati,
come durate temporali e classifiche, per una visualizzazione pulita su Discord.
"""
import discord
import logging
import queries
import theme

def format_duration(total_seconds: float) -> str:
    """
    Converte un numero totale di secondi in una stringa formattata e leggibile
    (es. "1g 2h 30m 15s").
    """
    if total_seconds < 0:
        return "0s"
        
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{int(days)}g")
    if hours > 0:
        parts.append(f"{int(hours)}h")
    if minutes > 0:
        parts.append(f"{int(minutes)}m")
    # Mostra i secondi solo se è l'unica unità o se ci sono altre parti
    if seconds > 0 or not parts:
        parts.append(f"{int(seconds)}s")
        
    return " ".join(parts) if parts else "0s"

def get_effective_streak(activity_streak: int, last_activity_date, today) -> int:
    """
    Restituisce la striscia di attività "reale" alla data odierna.

    La streak memorizzata (activity_streak) viene ricalcolata solo quando l'utente
    compie un'attività: per un utente inattivo resta congelata sull'ultimo valore e
    quindi risulta sovrastimata. Se l'ultima attività è più vecchia di ieri la streak
    è di fatto interrotta e va mostrata come 0; se è di oggi o ieri è ancora viva.
    """
    if not last_activity_date or not activity_streak:
        return 0
    gap = (today - last_activity_date).days
    return activity_streak if gap <= 1 else 0

def format_leaderboard(rows: list[dict], formatter: callable) -> str:
    """
    Formatta una lista di righe del database in una stringa di classifica.
    Utilizza emoji per le prime tre posizioni.
    """
    if not rows:
        return theme.LEADERBOARD_EMPTY
        
    leaderboard_text = ""
    ranks = ['🥇', '🥈', '🥉']
    
    for i, row in enumerate(rows):
        rank_emoji = ranks[i] if i < len(ranks) else f"**{i+1}.**"
        level = row.get('level', 1)
        details = formatter(row)  # Funzione personalizzata per i dettagli
        display_name = row.get('nickname') or row.get('username', 'Utente Sconosciuto')
        
        leaderboard_text += f"{rank_emoji} **{display_name}** (Lvl. {level})\n> {details}\n\n"
        
    return leaderboard_text

def build_records_embed(bot) -> discord.Embed:
    """
    Costruisce l'embed "Hall of Fame" con tutti i record del server, calcolati al volo.
    Riusato sia dal comando !records sia dal report settimanale.
    """
    embed = discord.Embed(
        title=theme.RECORDS_TITLE,
        description=theme.RECORDS_TEXT,
        color=theme.COLOR_GOLD
    )

    def _add_record(name, query, value_key, formatter=None, suffix=""):
        try:
            bot.cursor.execute(query)
            row = bot.cursor.fetchone()
        except Exception as e:
            logging.error(f"Errore nel recupero del record '{name}': {e}", exc_info=True)
            row = None

        value = row[value_key] if row and row.get(value_key) is not None else 0
        if value and value > 0:
            holder = row['nickname'] or row['username']
            shown = formatter(value) if formatter else f"{value}{suffix}"
            embed.add_field(name=name, value=f"**{shown}**\n{theme.RECORDS_HOLDER.format(holder=holder)}", inline=True)
        else:
            embed.add_field(name=name, value=theme.RECORDS_NONE, inline=True)

    _add_record(theme.RECORD_DAILY_XP, queries.get_record_daily_xp_query, 'max_daily_xp', suffix=" XP")
    _add_record(theme.RECORD_LONGEST_SESSION, queries.get_record_voice_duration_query, 'duration_seconds', formatter=format_duration)
    _add_record(theme.RECORD_NIGHT, queries.get_record_night_voice_query, 'night_voice_seconds', formatter=format_duration)
    _add_record(theme.RECORD_TOTAL_VOICE, queries.get_record_total_voice_query, 'voice_seconds', formatter=format_duration)
    _add_record(theme.RECORD_MESSAGES, queries.get_record_message_count_query, 'message_count', suffix=" messaggi")
    _add_record(theme.RECORD_STREAK, queries.get_record_streak_query, 'activity_streak', formatter=lambda v: f"{v} giorni")

    if bot.KOFI_USERNAME:
        embed.add_field(name=theme.KOFI_FIELD_NAME, value=theme.kofi_link(bot.KOFI_USERNAME), inline=False)
    embed.set_footer(text=theme.FOOTER)

    return embed


async def send_report_embed(destination, title: str, user_rows: list[dict], channel_report_rows: list[dict] = None, soundboard_rows: list[dict] = None, color: int = theme.COLOR_PRIMARY, kofi_username: str = None):
    """
    Costruisce e invia un embed formattato per i report (giornalieri/settimanali).
    Migliorato con podio, statistiche totali e formattazione visiva.
    """
    try:
        embed = discord.Embed(title=f"📜 {title}", color=color)
        
        if not user_rows and not channel_report_rows and not soundboard_rows:
            embed.description = theme.REPORT_EMPTY
        else:
            # --- Statistiche Totali ---
            total_voice_time = sum(row.get('total_secs', 0) for row in user_rows)
            formatted_total_time = format_duration(total_voice_time)
            active_users_count = len([r for r in user_rows if r.get('total_secs', 0) > 0])
            
            embed.description = (
                f"{theme.REPORT_TOTAL_TIME}: `{formatted_total_time}`\n"
                f"{theme.REPORT_ACTIVE_USERS}: `{active_users_count}`\n"
                "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
            )

            # --- Sezione Attività Utenti (Top List) ---
            if user_rows:
                top_users_text = ""
                medals = ["🥇", "🥈", "🥉"]
                
                for i, row in enumerate(user_rows):
                    if row.get('total_secs', 0) > 0:
                        display_name = row.get('nickname') or row.get('username', 'N/A')
                        duration = format_duration(row['total_secs'])
                        
                        # Assegna medaglia ai primi 3, punto elenco agli altri
                        prefix = medals[i] if i < 3 else "🔹"
                        
                        # Grassetto per i nomi sul podio
                        name_fmt = f"**{display_name}**" if i < 3 else display_name
                        
                        top_users_text += f"{prefix} {name_fmt} — `{duration}`\n"
                
                if top_users_text:
                    # Se il testo è troppo lungo, lo tronchiamo o dividiamo (qui semplice troncamento per sicurezza)
                    if len(top_users_text) > 1024:
                        top_users_text = top_users_text[:1020] + "..."
                    embed.add_field(name=theme.REPORT_TOP_USERS, value=top_users_text, inline=False)

            # --- Sezione Attività Canali ---
            if channel_report_rows:
                channel_text = ""
                # Ordiniamo anche i canali per attività se non lo sono già
                sorted_channels = sorted(channel_report_rows, key=lambda x: x.get('total_activity_seconds', 0), reverse=True)
                
                for row in sorted_channels:
                    if row.get('total_activity_seconds', 0) > 0:
                        channel_name = row.get('channel_name', 'N/A')
                        duration = format_duration(row['total_activity_seconds'])
                        channel_text += f"**{channel_name}**: `{duration}`\n"
                
                if channel_text:
                    if len(channel_text) > 1024:
                        channel_text = channel_text[:1020] + "..."
                    embed.add_field(name=theme.REPORT_CHANNELS, value=channel_text, inline=False)

            # --- Sezione Soundboard ---
            if soundboard_rows:
                soundboard_text = ""
                for i, row in enumerate(soundboard_rows):
                    count = row.get('use_count', 0)
                    if count > 0:
                        name = row.get('sound_name', 'Sconosciuto')
                        prefix = ["🥇", "🥈", "🥉"][i] if i < 3 else "🔹"
                        soundboard_text += f"{prefix} **{name}** — `{count} {'volta' if count == 1 else 'volte'}`\n"
                if soundboard_text:
                    if len(soundboard_text) > 1024:
                        soundboard_text = soundboard_text[:1020] + "..."
                    embed.add_field(name=theme.REPORT_SOUNDBOARD, value=soundboard_text, inline=False)

        # Footer e Timestamp
        embed.set_footer(text=theme.REPORT_FOOTER)
        embed.timestamp = discord.utils.utcnow()

        if kofi_username:
            embed.add_field(name=theme.KOFI_FIELD_NAME, value=theme.kofi_link(kofi_username), inline=False)

        await destination.send(embed=embed)
        
    except Exception as e:
        logging.error(f"Errore durante l'invio del report embed: {e}", exc_info=True)