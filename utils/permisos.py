"""
utils/permisos.py — Sistema de visibilidad de canales.

REGLA DE VISIBILIDAD:
- Solo ves el canal donde estás AHORA (lectura + escritura)
- Y el ÚLTIMO canal donde estuviste (solo lectura — ves el historial pero no puedes escribir)
- Todos los demás canales son invisibles
"""
import discord
from utils.roles import ROL_CIUDADANO


async def dar_acceso_canal(guild: discord.Guild, member: discord.Member, nombre_canal: str):
    """
    Da acceso COMPLETO (lectura + escritura) al canal actual.
    Este es el canal donde el personaje ESTÁ ahora mismo.
    """
    canal = discord.utils.get(guild.text_channels, name=nombre_canal)
    if canal:
        await canal.set_permissions(
            member,
            read_messages=True,
            send_messages=True,
            view_channel=True
        )
        return canal
    return None


async def dar_solo_lectura_canal(guild: discord.Guild, member: discord.Member, nombre_canal: str):
    """
    Deja el canal anterior como SOLO LECTURA.
    El personaje puede ver el historial de donde estuvo,
    pero NO puede enviar mensajes (ya no está físicamente ahí).
    """
    canal = discord.utils.get(guild.text_channels, name=nombre_canal)
    if canal:
        await canal.set_permissions(
            member,
            read_messages=True,
            send_messages=False,   # ← No puede escribir
            view_channel=True      # ← Sí puede ver el historial
        )
    return canal


async def revocar_acceso_canal(guild: discord.Guild, member: discord.Member, nombre_canal: str):
    """
    Revoca completamente el acceso a un canal.
    El canal desaparece de la lista del jugador.
    """
    canal = discord.utils.get(guild.text_channels, name=nombre_canal)
    if canal:
        await canal.set_permissions(member, overwrite=None)
    return canal


async def actualizar_visibilidad_al_viajar(
    guild: discord.Guild,
    member: discord.Member,
    canal_origen: str | None,
    canal_destino: str
):
    """
    Llamar cuando el personaje llega a un nuevo canal de RP.
    
    - canal_origen (donde estaba): pasa a SOLO LECTURA
    - canal_destino (donde llega): pasa a LECTURA + ESCRITURA
    
    El jugador siempre ve exactamente 2 canales:
    1. El actual → puede escribir
    2. El anterior → solo puede leer (historial)
    
    Nota: si el origen es el mismo que el destino (viaje interno), no se hace nada.
    """
    if canal_origen and canal_origen != canal_destino:
        await dar_solo_lectura_canal(guild, member, canal_origen)
    await dar_acceso_canal(guild, member, canal_destino)


async def canal_privado_base(guild: discord.Guild) -> dict:
    """Retorna los overwrites base para un canal privado (nadie lo ve por defecto)."""
    return {
        guild.default_role: discord.PermissionOverwrite(
            read_messages=False,
            view_channel=False
        ),
        guild.me: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            view_channel=True
        ),
    }


async def inicializar_acceso_personaje(guild: discord.Guild, member: discord.Member, datos: dict):
    """
    Al aceptar un personaje, da acceso solo a:
    - Su canal de casa (si tiene casa asignada)
    - Si vive con padres: el canal de la casa de los padres
    - Si no: el primer canal del barrio inicial
    
    El personaje comienza sin "último canal" (aún no ha viajado a ningún lado).
    """
    barrio = datos.get("barrio", "petare")
    casa = datos.get("casa")
    familia = datos.get("familia", {})

    canales_iniciales = []

    if casa:
        canales_iniciales.append(casa)
    elif familia.get("vive_con_padres") and familia.get("casa_padres"):
        casa_padres = familia["casa_padres"].split(":")[-1]
        canales_iniciales.append(casa_padres)
    else:
        from utils.mapa import SECTORES
        sec = SECTORES.get(barrio, {})
        canales_sec = list(sec.get("canales", {}).keys())
        if canales_sec:
            canales_iniciales.append(canales_sec[0])

    for nombre_canal in canales_iniciales:
        await dar_acceso_canal(guild, member, nombre_canal)

    if canales_iniciales:
        from utils import db
        await db.update("personajes", str(member.id), {
            "canal_actual": canales_iniciales[0],
            "ultimo_canal": None,  # Aún no ha viajado
        })

    return canales_iniciales


async def dar_acceso_al_llegar(guild: discord.Guild, member: discord.Member, canal_nombre: str):
    """Cuando un personaje llega a un nuevo canal, le da acceso completo."""
    canal = await dar_acceso_canal(guild, member, canal_nombre)
    return canal