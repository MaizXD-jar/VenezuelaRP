"""
utils/canal_fijo.py — Redirección de canales para el servidor de pruebas.

En el servidor SERVIDOR_CANAL_FIJO_ID, CUALQUIER canal fijo del bot (avisos de
policía, noticias, creación de personaje, etc.) debe resolver siempre al mismo
canal de prueba, sin importar qué ID esté hardcodeado en el código.

bot.py usa esto para parchear discord.Guild.get_channel globalmente. Los
lugares que comparan IDs de canal directamente (en vez de usar get_channel)
deben llamar a id_efectivo() explícitamente — ver cogs/personajes.py.
"""

SERVIDOR_CANAL_FIJO_ID = 1511638671332343920
CANAL_FIJO_ID = 1511638672599158796


def es_servidor_fijo(guild_id: int) -> bool:
    return guild_id == SERVIDOR_CANAL_FIJO_ID


def id_efectivo(guild_id: int, id_original: int) -> int:
    """Devuelve el ID de canal que realmente se debe usar según el servidor."""
    if es_servidor_fijo(guild_id):
        return CANAL_FIJO_ID
    return id_original
