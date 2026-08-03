"""
cogs/mapa_ia.py — "VenezuelaMaps IA": asistente de mapas del teléfono.

Responde en lenguaje natural usando datos REALES del mapa como contexto:
rutas calculadas con el pathfinder, sectores, niveles de peligro, lugares,
y también las CASAS (que no están en el mapa estático porque sus canales se
renombran al comprarlas — antes la IA decía "no tengo registrada casa-1 de
petare" justamente por eso).

Es un comando slash y responde en privado (ephemeral): estás mirando tu móvil.
"""
import discord
from discord.ext import commands
from discord import app_commands

from utils import db
from utils import ia
from utils.inventario import tiene_telefono
from utils.mapa import (SECTORES, TIEMPOS_VIAJE, mejor_ruta, get_tiempo,
                        metodos_disponibles, get_sector_de_canal)

SYSTEM_PROMPT = (
    "Eres 'VenezuelaMaps IA', el asistente de mapas del teléfono en un servidor de "
    "roleplay de Discord ambientado en una Venezuela ficticia. Respondes SIEMPRE en "
    "español, en 2 a 5 frases, con tono de app de mapas: directo y útil, sin relleno.\n\n"
    "REGLAS IMPORTANTES (sobre todo con los NÚMEROS):\n"
    "- Usa ÚNICAMENTE los datos del CONTEXTO. No inventes calles, tiempos, lugares ni casas.\n"
    "- Si el contexto trae una ruta calculada con minutos ('~N min' o 'Total ~N min'), "
    "COPIA ese número EXACTO, tal cual aparece. NO lo redondees, NO lo aproximes, NO "
    "sumes ni restes minutos por tu cuenta, y NO inventes otro tiempo si el contexto no "
    "lo trae — en ese caso di que no tienes ese dato en vez de adivinar.\n"
    "- Si hay varios métodos de transporte con tiempos distintos en el CONTEXTO, cita el "
    "de cada método por separado, con su número exacto.\n"
    "- Menciona el comando concreto que debe usar el jugador, por ejemplo: "
    "`/viajar destino:<canal> metodo:<metodo>`.\n"
    "- Si el destino es una casa privada, avisa de que necesita permiso del dueño o "
    "que la puerta puede estar cerrada.\n"
    "- Si el contexto no tiene la respuesta, dilo claramente y sugiere qué preguntar."
)


def _ctx_sector_actual(sector_key: str, canal_actual: str) -> str:
    sec = SECTORES.get(sector_key, {})
    if not sec:
        return f"Ubicación actual desconocida (sector '{sector_key}' no válido)."
    canales = sec.get("canales", {})
    lugares = "; ".join(f"{n} [{i.get('tipo','?')}]" for n, i in canales.items())
    metodos = ", ".join(metodos_disponibles(sector_key))
    return (
        f"UBICACIÓN ACTUAL DEL JUGADOR: canal '{canal_actual}', "
        f"sector '{sec.get('display', sector_key)}' ({sector_key}), "
        f"ciudad {sec.get('ciudad','?')}, peligro {sec.get('peligro','?')}/5.\n"
        f"Lugares en este sector: {lugares}.\n"
        f"Transportes disponibles desde aquí: {metodos}."
    )


async def _ctx_casas(guild: discord.Guild, sectores_relevantes: list[str]) -> str:
    """Las casas NO están en SECTORES, hay que sacarlas de la base de datos."""
    lineas = []
    for sector_key in sectores_relevantes:
        casas = await db.get("casas", sector_key)
        if not casas:
            continue
        resumen = []
        for casa_id, casa in casas.items():
            canal_nombre = casa.get("canal_nombre", casa_id)
            existe = bool(
                (casa.get("canal_id") and guild.get_channel(casa["canal_id"]))
                or discord.utils.get(guild.text_channels, name=canal_nombre)
            )
            if not existe:
                continue
            if casa.get("dueño"):
                estado = "con dueño (privada)"
            elif casa.get("padres_de"):
                estado = "casa familiar habitada"
            elif casa.get("inquilino"):
                estado = "alquilada"
            elif casa.get("okupa"):
                estado = "ocupada por okupas"
            else:
                estado = f"DISPONIBLE, precio ${casa.get('precio',0):,}"
            puerta = "puerta cerrada" if not casa.get("puerta_abierta") else "puerta abierta"
            resumen.append(f"{casa_id} (canal '{canal_nombre}', {estado}, {puerta})")
        if resumen:
            lineas.append(f"CASAS EN {sector_key}: " + "; ".join(resumen))
    return "\n".join(lineas)


def _ctx_rutas_desde(sector_actual: str) -> str:
    """Todas las rutas directas que salen del sector actual."""
    salidas = []
    for (a, b), metodos in TIEMPOS_VIAJE.items():
        otro = None
        if a == sector_actual:
            otro = b
        elif b == sector_actual:
            otro = a
        if otro:
            detalle = ", ".join(f"{m} {t}min" for m, t in metodos.items())
            salidas.append(f"{otro} ({detalle})")
    if not salidas:
        return ""
    return f"RUTAS DIRECTAS DESDE {sector_actual}: " + "; ".join(salidas)


def _ctx_ruta_a_destino(sector_actual: str, pregunta: str, guild: discord.Guild) -> tuple[str, list[str]]:
    """Detecta destinos mencionados (sector, canal o casa) y calcula la ruta real.
    Devuelve (texto_contexto, sectores_relevantes)."""
    p = pregunta.lower()
    partes = []
    relevantes = {sector_actual}

    # ¿Menciona un canal de casa concreto? (ej "casa-1 de petare", "casa-17-petare-maiz")
    for canal in guild.text_channels:
        if not canal.name.startswith("casa-"):
            continue
        base = canal.name.split("-")[0] + "-" + (canal.name.split("-")[1] if len(canal.name.split("-")) > 1 else "")
        if canal.name.lower() in p or (base in p and get_sector_de_canal(canal.name) and
                                        (get_sector_de_canal(canal.name) in p or sector_actual == get_sector_de_canal(canal.name))):
            sec_casa = get_sector_de_canal(canal.name)
            if not sec_casa:
                continue
            relevantes.add(sec_casa)
            if sec_casa == sector_actual:
                partes.append(
                    f"DATO REAL: la casa '{canal.name}' está en el MISMO sector donde ya se "
                    f"encuentra el jugador ({sector_actual}). Un viaje dentro del mismo sector "
                    f"tarda entre 5 y 15 minutos. Comando: /viajar destino:{canal.name} metodo:caminar"
                )
            else:
                ruta = mejor_ruta(sector_actual, sec_casa)
                if ruta and ruta["pasos"]:
                    pasos = "; ".join(f"{d}→{h} en {m} (~{mi} min)" for d, h, m, mi in ruta["pasos"])
                    partes.append(
                        f"DATO REAL: ruta hasta la casa '{canal.name}' (sector {sec_casa}): {pasos}. "
                        f"Total ~{ruta['total_minutos']} min. Comando: /viajar destino:{canal.name}"
                    )

    # ¿Menciona otro sector o canal normal?
    for sector_key, sec in SECTORES.items():
        if sector_key == sector_actual:
            continue
        nombre_display = sec.get("display", sector_key).lower()
        canales = sec.get("canales", {})
        canal_mencionado = next((c for c in canales if c in p), None)
        if sector_key in p or nombre_display in p or canal_mencionado:
            relevantes.add(sector_key)
            ruta = mejor_ruta(sector_actual, sector_key)
            destino_canal = canal_mencionado or (list(canales)[0] if canales else sector_key)
            if not ruta:
                partes.append(f"DATO REAL: no existe ninguna ruta conocida de {sector_actual} a {sector_key}.")
            elif not ruta["pasos"]:
                partes.append(f"DATO REAL: el jugador ya está en {sector_key}.")
            else:
                pasos = "; ".join(f"{d}→{h} en {m} (~{mi} min)" for d, h, m, mi in ruta["pasos"])
                directo = [f"{m}: {get_tiempo(sector_actual, sector_key, m)} min"
                           for m in ("caminar", "metro", "autobus", "coche", "tren", "avion")
                           if get_tiempo(sector_actual, sector_key, m) > 0]
                extra = f" Opciones directas: {', '.join(directo)}." if directo else ""
                partes.append(
                    f"DATO REAL: ruta de {sector_actual} a {sector_key}: {pasos}. "
                    f"Total ~{ruta['total_minutos']} min.{extra} "
                    f"Comando: /viajar destino:{destino_canal}"
                )

    return "\n".join(partes), list(relevantes)


class MapaIA(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mapa_ia", description="📱 Pregunta a la IA del mapa cómo llegar a un sitio (privado)")
    @app_commands.describe(pregunta="Ej: cómo llego a casa-1 de petare y cuánto tardo")
    @app_commands.checks.cooldown(1, 10)
    async def mapa_ia(self, interaction: discord.Interaction, pregunta: str):
        await interaction.response.defer(ephemeral=True)

        if not ia.hay_ia():
            return await interaction.followup.send(
                "❌ Esta app no está configurada. Un admin debe añadir `GROQ_API_KEY` "
                "(gratis en https://console.groq.com/keys) o `GEMINI_API_KEY` al `.env`.",
                ephemeral=True)

        datos = await db.get("personajes", str(interaction.user.id))
        if not datos:
            return await interaction.followup.send("❌ No tienes personaje.", ephemeral=True)
        if not tiene_telefono(datos):
            return await interaction.followup.send(
                "❌ Necesitas un teléfono para abrir esta app. Cómprate uno en la tienda "
                "(`telefono_basico` o `smartphone`).", ephemeral=True)

        sector_actual = datos.get("ubicacion", "")
        canal_actual = datos.get("canal_actual", "")

        ctx_ruta, relevantes = _ctx_ruta_a_destino(sector_actual, pregunta, interaction.guild)
        ctx_casas = await _ctx_casas(interaction.guild, relevantes)

        bloques = [
            _ctx_sector_actual(sector_actual, canal_actual),
            _ctx_rutas_desde(sector_actual),
            ctx_casas,
            ctx_ruta,
        ]
        contexto = "\n\n".join(b for b in bloques if b)
        prompt = f"CONTEXTO DEL MAPA:\n{contexto}\n\nPREGUNTA DEL JUGADOR: {pregunta}"

        texto, info = await ia.generar(SYSTEM_PROMPT, prompt, max_tokens=400)
        if not texto:
            return await interaction.followup.send(
                f"❌ La app de mapas no pudo responder.\nDetalle: `{info[:400]}`", ephemeral=True)

        embed = discord.Embed(title="🗺️ VenezuelaMaps IA", description=texto[:4000], color=discord.Color.teal())
        # Salvaguarda: la IA a veces redondea o inventa tiempos al narrar. Se
        # añaden aquí, TAL CUAL calculados (sin pasar por la IA), los datos
        # reales de ruta que se le dieron de contexto, para que el jugador
        # siempre tenga el número correcto a la vista aunque el texto de
        # arriba se equivoque.
        if ctx_ruta:
            embed.add_field(name="📊 Datos exactos (sin IA)", value=ctx_ruta[:1024], inline=False)
        embed.set_footer(text=f"📍 {canal_actual or sector_actual or '?'} | {info}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @mapa_ia.error
    async def mapa_ia_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CommandOnCooldown):
            msg = f"⏳ Espera {error.retry_after:.0f}s antes de volver a preguntar."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        else:
            raise error


async def setup(bot):
    await bot.add_cog(MapaIA(bot))
