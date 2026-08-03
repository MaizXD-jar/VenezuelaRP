"""
cogs/mapa_ia.py — "VenezuelaMaps IA": app del teléfono que responde preguntas
de navegación en lenguaje natural, usando datos REALES del mapa (rutas
calculadas, peligro, lugares) como contexto para que la IA no invente
información. Requiere una API key gratuita de Google Gemini.

Cómo conseguir la API key (gratis):
1. Entra a https://aistudio.google.com/apikey con una cuenta de Google.
2. "Create API key" → "Create in new project" si no tienes uno.
3. Copia la key y ponla como GEMINI_API_KEY en el .env del bot.

Usa Gemini 2.5 Flash-Lite: el modelo más barato de Gemini, con tier gratuito
suficiente para un bot de RP.
"""
import os

import discord
from discord.ext import commands
import aiohttp

from utils import db
from utils.inventario import tiene_telefono
from utils.mapa import SECTORES, mejor_ruta

GEMINI_MODEL_ENV = os.getenv("GEMINI_MODEL", "").strip()

# Google va retirando modelos y bloqueando los viejos para usuarios nuevos
# (gemini-2.5-flash-lite ya no admite cuentas nuevas). Por eso se prueban varios
# en orden: si uno está deprecado o no disponible, se pasa automáticamente al
# siguiente en vez de fallar. Puedes forzar uno concreto con GEMINI_MODEL en .env.
MODELOS_GEMINI = [m for m in [
    GEMINI_MODEL_ENV,
    "gemini-3.5-flash-lite",   # el más barato y rápido (GA desde julio 2026)
    "gemini-3.1-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
] if m]


def _url_modelo(modelo: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

SYSTEM_PROMPT = (
    "Eres 'VenezuelaMaps IA', el asistente de mapas del teléfono en un servidor de "
    "roleplay de Discord ambientado en una Venezuela ficticia. Respondes SIEMPRE en "
    "español, en 2 a 4 frases, con tono de app de mapas: directo y útil, sin relleno. "
    "Usa ÚNICAMENTE los datos reales que se te dan en el CONTEXTO (rutas, tiempos, "
    "sectores, nivel de peligro, lugares). Si el contexto no tiene la respuesta, "
    "dilo claramente en vez de inventar calles, tiempos o lugares que no existen."
)


def _contexto_sector_actual(sector_key: str) -> str:
    sec = SECTORES.get(sector_key, {})
    if not sec:
        return "Ubicación actual desconocida (el personaje no tiene sector válido registrado)."
    canales = sec.get("canales", {})
    lugares = ", ".join(f"{n} ({info.get('tipo','?')})" for n, info in list(canales.items())[:12])
    return (
        f"Sector actual: {sec.get('display', sector_key)} (peligro {sec.get('peligro','?')}/5, "
        f"ciudad: {sec.get('ciudad','?')}). Lugares aquí: {lugares or 'ninguno registrado'}."
    )


def _contexto_ruta_si_se_menciona(sector_actual: str, pregunta: str) -> str:
    """Si la pregunta menciona otro sector conocido, calcula la ruta REAL (con
    escalas si hace falta) y la da como dato duro para que la IA no invente tiempos."""
    pregunta_low = pregunta.lower()
    for sector_key, sec in SECTORES.items():
        if sector_key == sector_actual:
            continue
        nombre_display = sec.get("display", sector_key).lower()
        if sector_key in pregunta_low or nombre_display in pregunta_low:
            ruta = mejor_ruta(sector_actual, sector_key)
            if not ruta:
                return f"DATO REAL: no existe ninguna ruta conocida entre {sector_actual} y {sector_key}."
            if not ruta["pasos"]:
                return f"DATO REAL: el jugador ya está en {sector_key}."
            pasos_txt = "; ".join(f"{d}→{h} en {m} (~{mi} min)" for d, h, m, mi in ruta["pasos"])
            return f"DATO REAL — ruta calculada de {sector_actual} a {sector_key}: {pasos_txt}. Tiempo total: ~{ruta['total_minutos']} min."
    return ""


class MapaIA(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="mapa_ia", aliases=["maps_ia", "google_maps"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def mapa_ia(self, ctx, *, pregunta: str):
        """Pregúntale a la IA del mapa cómo llegar a algún lugar o qué hay cerca. Requiere teléfono."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return await ctx.send(
                "❌ Esta app no está configurada en este servidor todavía. "
                "Un admin necesita poner `GEMINI_API_KEY` en el `.env` del bot "
                "(gratis en https://aistudio.google.com/apikey)."
            )

        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ No tienes personaje.")
        if not tiene_telefono(datos):
            return await ctx.send("❌ Necesitas un teléfono para abrir esta app. Cómprate uno en la tienda (`smartphone`).")

        sector_actual = datos.get("ubicacion", "")
        contexto = _contexto_sector_actual(sector_actual)
        contexto_ruta = _contexto_ruta_si_se_menciona(sector_actual, pregunta)
        if contexto_ruta:
            contexto += "\n" + contexto_ruta

        prompt = f"CONTEXTO:\n{contexto}\n\nPREGUNTA DEL JUGADOR: {pregunta}"

        data = None
        modelo_usado = None
        ultimo_error = ""
        async with ctx.typing():
            payload = {
                "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            }
            headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
            timeout = aiohttp.ClientTimeout(total=25)
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    for modelo in MODELOS_GEMINI:
                        try:
                            async with session.post(_url_modelo(modelo), json=payload, headers=headers) as resp:
                                respuesta = await resp.json()
                                if resp.status == 200:
                                    data = respuesta
                                    modelo_usado = modelo
                                    break
                                ultimo_error = respuesta.get("error", {}).get("message", str(respuesta))
                                # 404/400 suelen ser "modelo no disponible/deprecado" → probar el siguiente
                                if resp.status in (400, 404):
                                    continue
                                # 429 (sin cuota) o 403 (key inválida): no sirve reintentar con otro modelo
                                break
                        except Exception as e:
                            ultimo_error = str(e)
                            continue
            except Exception as e:
                return await ctx.send(f"❌ No se pudo conectar con la IA del mapa: {e}")

        if data is None:
            return await ctx.send(
                f"❌ La app de mapas no pudo responder con ningún modelo disponible.\n"
                f"Último error: `{ultimo_error[:300]}`\n"
                f"Si dice *quota* has agotado la cuota diaria gratuita; si dice *API key*, revisa `GEMINI_API_KEY` en el `.env`."
            )

        try:
            texto = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return await ctx.send("❌ La IA no devolvió una respuesta utilizable. Intenta reformular la pregunta.")

        embed = discord.Embed(
            title="🗺️ VenezuelaMaps IA",
            description=texto.strip()[:4000],
            color=discord.Color.teal()
        )
        embed.set_footer(text=f"📍 Ubicación: {sector_actual or '?'} | {modelo_usado}")
        await ctx.send(embed=embed)

    @mapa_ia.error
    async def mapa_ia_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Espera {error.retry_after:.0f}s antes de volver a preguntarle al mapa.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Uso: `!mapa_ia <tu pregunta>` — ej: `!mapa_ia como llego a Miami`")
        else:
            raise error


async def setup(bot):
    await bot.add_cog(MapaIA(bot))