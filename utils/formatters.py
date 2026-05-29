"""
Questo modulo contiene funzioni di utilità per formattare dati,
come durate temporali e classifiche, per una visualizzazione pulita su Discord.
"""
import discord
import logging

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

def format_leaderboard(rows: list[dict], formatter: callable) -> str:
    """
    Formatta una lista di righe del database in una stringa di classifica.
    Utilizza emoji per le prime tre posizioni.
    """
    if not rows:
        return "Nessun dato da mostrare nella classifica."
        
    leaderboard_text = ""
    ranks = ['🥇', '🥈', '🥉']
    
    for i, row in enumerate(rows):
        rank_emoji = ranks[i] if i < len(ranks) else f"**{i+1}.**"
        level = row.get('level', 1)
        details = formatter(row)  # Funzione personalizzata per i dettagli
        display_name = row.get('nickname') or row.get('username', 'Utente Sconosciuto')
        
        leaderboard_text += f"{rank_emoji} **{display_name}** (Lvl. {level})\n> {details}\n\n"
        
    return leaderboard_text

async def send_report_embed(destination, title: str, user_rows: list[dict], channel_report_rows: list[dict] = None, soundboard_rows: list[dict] = None, color: int = 0x2E8B57, kofi_username: str = None):
    """
    Costruisce e invia un embed formattato per i report (giornalieri/settimanali).
    Migliorato con podio, statistiche totali e formattazione visiva.
    """
    try:
        embed = discord.Embed(title=f"📊 {title}", color=color)
        
        if not user_rows and not channel_report_rows and not soundboard_rows:
            embed.description = "💤 Nessuna attività registrata per questo periodo."
        else:
            # --- Statistiche Totali ---
            total_voice_time = sum(row.get('total_secs', 0) for row in user_rows)
            formatted_total_time = format_duration(total_voice_time)
            active_users_count = len([r for r in user_rows if r.get('total_secs', 0) > 0])
            
            embed.description = (
                f"🕒 **Tempo Totale in Vocale**: `{formatted_total_time}`\n"
                f"👥 **Utenti Attivi**: `{active_users_count}`\n"
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
                    embed.add_field(name="🏆 Top Utenti", value=top_users_text, inline=False)

            # --- Sezione Attività Canali ---
            if channel_report_rows:
                channel_text = ""
                # Ordiniamo anche i canali per attività se non lo sono già
                sorted_channels = sorted(channel_report_rows, key=lambda x: x.get('total_activity_seconds', 0), reverse=True)
                
                for row in sorted_channels:
                    if row.get('total_activity_seconds', 0) > 0:
                        channel_name = row.get('channel_name', 'N/A')
                        duration = format_duration(row['total_activity_seconds'])
                        channel_text += f"🔊 **{channel_name}**: `{duration}`\n"
                
                if channel_text:
                    if len(channel_text) > 1024:
                        channel_text = channel_text[:1020] + "..."
                    embed.add_field(name="📡 Canali più Attivi", value=channel_text, inline=False)

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
                    embed.add_field(name="🎵 Soundboard più usata", value=soundboard_text, inline=False)

        # Footer e Timestamp
        embed.set_footer(text="Report generato automaticamente • Botrino")
        embed.timestamp = discord.utils.utcnow()

        if kofi_username:
            embed.add_field(name="☕ Supporto", value=f"[Offrimi un caffè]({f'https://ko-fi.com/{kofi_username}'})", inline=False)

        await destination.send(embed=embed)
        
    except Exception as e:
        logging.error(f"Errore durante l'invio del report embed: {e}", exc_info=True)