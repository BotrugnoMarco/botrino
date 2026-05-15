"""
Questo modulo contiene le funzioni di utilità per il calcolo dell'XP
necessario per i passaggi di livello, implementando una curva di progressione non lineare.
"""

def get_multiplier_for_level(level: int) -> float:
    """
    Restituisce un moltiplicatore basato sul livello attuale dell'utente.
    La curva di difficoltà aumenta più rapidamente ai livelli bassi e poi si appiattisce.
    """
    if 1 <= level <= 10:
        return 1.22  # Aumento rapido all'inizio
    elif 11 <= level <= 20:
        return 1.16
    elif 21 <= level <= 30:
        return 1.11
    else:
        # Dal livello 31 in poi, il moltiplicatore si stabilizza per ammorbidire la curva
        return 1.03

def calculate_xp_for_level_up(current_level: int, base_xp: int) -> int:
    """
    Calcola la quantità totale di XP necessaria per passare dal livello `current_level`
    al livello `current_level + 1`.
    
    La formula è iterativa: l'XP per il livello successivo dipende da quello precedente,
    applicando un moltiplicatore che decresce con l'aumentare del livello.
    """
    if current_level == 0:
        return base_xp
    
    # Calcolo iterativo per determinare l'XP necessario per il livello successivo
    xp_needed = float(base_xp)
    for i in range(1, current_level + 1):
        multiplier = get_multiplier_for_level(i)
        xp_needed *= multiplier
        
    return int(xp_needed)
