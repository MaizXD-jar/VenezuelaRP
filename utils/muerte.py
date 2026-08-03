"""
utils/muerte.py — Procesa la muerte de un personaje: marca el estado en la DB,
publica el aviso en el canal de fallecidos y actualiza roles de Discord.

Extraído de cogs/combate.py para que también lo use utils/lesiones.py (cuando
alguien muere por no haber recibido atención médica a tiempo, en vez de morir
directamente en combate).
"""
import discord

from utils import db
from utils.roles import ROL_MUERTO, ROL_CIUDADANO

CH_MUERTOS = 1359320811420520613


async def procesar_muerte(bot, user_id: int, datos: dict, causa: str = "", guild: discord.Guild = None):
    """Marca al personaje como muerto y notifica. `guild` es opcional: si no se
    pasa, se busca entre los guilds del bot al primero donde el usuario sea miembro."""
    await db.update("personajes", str(user_id), {
        "muerto": True,
        "causa_muerte": causa or "Falleció.",
        "stats": {**datos.get("stats", {}), "hp": 0},
    })

    if guild is None:
        for g in bot.guilds:
            if g.get_member(user_id):
                guild = g
                break
    if not guild:
        return

    ch_muertos = guild.get_channel(CH_MUERTOS)
    if ch_muertos:
        embed = discord.Embed(
            title="💀 PERSONAJE FALLECIDO",
            description=f"**{datos.get('nombre', '?')}** ha muerto." + (f"\n{causa}" if causa else ""),
            color=0x000000
        )
        embed.add_field(name="Ubicación", value=datos.get("ubicacion", "?"))
        member = guild.get_member(user_id)
        if member:
            embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        await ch_muertos.send(embed=embed)

    member = guild.get_member(user_id)
    if member:
        r_c = guild.get_role(ROL_CIUDADANO)
        r_m = guild.get_role(ROL_MUERTO)
        if r_c and r_c in member.roles:
            await member.remove_roles(r_c)
        if r_m:
            await member.add_roles(r_m)
