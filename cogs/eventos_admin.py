"""
cogs/eventos_admin.py — Herramientas de admin para eventos manuales + sistema
de disturbios (antes solo había un !protesta cosmético que no afectaba nada
más que un mensaje; ahora un disturbio es un estado real y consultable que
habilita saqueo con riesgo real de arresto o lesión).

Nota: cogs/eventos.py quedó como versión vieja/abandonada de
cogs/eventos_random.py (comparten los comandos !evento, !elecciones y !clima
casi idénticos). Por eso nunca se cargó en bot.py — cargarlo tal cual habría
roto el bot por comandos duplicados. Este cog rescata los 3 comandos que SÍ
eran únicos y útiles de eventos.py: !teleport, !protesta y !secuestro.
"""
import random
import time

import discord
from discord.ext import commands, tasks

from utils import db
from utils import lesiones as lesiones_mod
from utils.mapa import SECTORES, get_sector_de_canal

DURACION_DEFAULT_MIN = 30
BOTIN_SAQUEO = ["televisor", "ropa", "electrodomestico", "comida_enlatada", "medicinas", "herramientas", "celular"]
COOLDOWN_SAQUEO_SEG = 300  # 5 minutos entre saqueos por persona


class EventosAdmin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._ultimo_saqueo: dict[int, float] = {}

    def start_tasks(self):
        if not self.expirar_disturbios.is_running():
            self.expirar_disturbios.start()

    @tasks.loop(minutes=5)
    async def expirar_disturbios(self):
        disturbios = await db.all("disturbios")
        ahora = time.time()
        for sector_key, d in disturbios.items():
            if d.get("activo") and ahora >= d.get("expira_ts", 0):
                d["activo"] = False
                await db.set("disturbios", sector_key, d)

    @commands.command(name="teleport")
    async def teleport(self, ctx, objetivo: discord.Member, *, destino: str):
        """Teleporta a un personaje a un sector/canal. (Solo admins)"""
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo admins.")

        datos = await db.get("personajes", str(objetivo.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        destino = destino.lower().replace(" ", "-")
        sector = get_sector_de_canal(destino)
        if not sector:
            if destino in SECTORES:
                sector = destino
                canales = list(SECTORES[destino]["canales"].keys())
                destino = canales[0] if canales else destino
            else:
                return await ctx.send(f"❌ Destino `{destino}` no encontrado.")

        await db.update("personajes", str(objetivo.id), {
            "ubicacion": sector,
            "canal_actual": destino,
            "en_viaje": False,
        })

        from cogs.viaje import viajes_activos
        viajes_activos.pop(objetivo.id, None)

        canal_discord = discord.utils.get(ctx.guild.text_channels, name=destino)
        if canal_discord:
            await canal_discord.send(
                f"✨ {objetivo.mention} ha sido teleportado aquí por un admin."
            )

        await ctx.send(f"✅ {datos['nombre']} teleportado a `{destino}` ({sector}).")
        try:
            await objetivo.send(f"✨ Un admin te teleportó a **{destino}** ({sector}).")
        except Exception:
            pass

    @commands.command(name="protesta")
    async def crear_protesta(self, ctx, *, sector: str = None):
        """Crea una protesta que afecta viajes. (Admins) — alias corto de !disturbio."""
        await self._iniciar_disturbio(ctx, sector or "general", DURACION_DEFAULT_MIN)

    @commands.command(name="disturbio")
    async def disturbio(self, ctx, sector: str = None, minutos: int = DURACION_DEFAULT_MIN):
        """[ADMIN] Inicia un disturbio real en un sector: sube el riesgo de robo/tiroteo
        y habilita !saquear ahí durante `minutos` (default 30)."""
        if not sector:
            return await ctx.send("❌ Uso: `!disturbio <sector> [minutos]`")
        await self._iniciar_disturbio(ctx, sector, minutos)

    async def _iniciar_disturbio(self, ctx, sector: str, minutos: int):
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo admins.")
        sector = sector.lower().replace(" ", "-")
        if sector not in SECTORES:
            return await ctx.send(f"❌ Sector `{sector}` no encontrado.")

        ahora = time.time()
        await db.set("disturbios", sector, {
            "activo": True,
            "inicio_ts": ahora,
            "expira_ts": ahora + minutos * 60,
            "iniciado_por": str(ctx.author.id),
        })

        embed = discord.Embed(
            title="🔥 ¡DISTURBIO EN CURSO!",
            description=(
                f"Hay disturbios activos en **{sector}** durante los próximos **{minutos} minutos**.\n"
                f"Los viajes ahí sufren demoras y el riesgo de robo/tiroteo sube.\n"
                f"Mientras dure, cualquiera en el sector puede usar `!saquear` — con riesgo real de arresto o salir herido."
            ),
            color=discord.Color.dark_orange()
        )
        await ctx.send(embed=embed)

    @commands.command(name="disturbios_activos", aliases=["disturbios"])
    async def disturbios_activos(self, ctx):
        """Lista los sectores con disturbios activos ahora mismo."""
        todos = await db.all("disturbios")
        ahora = time.time()
        activos = [(s, d) for s, d in todos.items() if d.get("activo") and ahora < d.get("expira_ts", 0)]
        if not activos:
            return await ctx.send("✅ No hay disturbios activos en este momento.")

        embed = discord.Embed(title="🔥 Disturbios activos", color=discord.Color.dark_orange())
        for sector_key, d in activos:
            restante_min = int((d["expira_ts"] - ahora) / 60)
            embed.add_field(name=sector_key, value=f"~{restante_min} min restantes", inline=True)
        await ctx.send(embed=embed)

    # ── !saquear ─────────────────────────────────────────────────────────────
    @commands.command(name="saquear")
    async def saquear(self, ctx):
        """Saquea durante un disturbio activo en tu sector actual. Riesgo real
        de arresto o de salir herido — no es gratis."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        if datos.get("muerto"):
            return await ctx.send("❌ Tu personaje está muerto.")

        canal_actual = datos.get("canal_actual", "")
        sector = get_sector_de_canal(canal_actual) or datos.get("ubicacion", "")
        disturbio = await db.get("disturbios", sector)
        ahora = time.time()
        if not disturbio or not disturbio.get("activo") or ahora >= disturbio.get("expira_ts", 0):
            return await ctx.send(f"❌ No hay ningún disturbio activo en `{sector}` ahora mismo.")

        ultimo = self._ultimo_saqueo.get(ctx.author.id, 0)
        restante = COOLDOWN_SAQUEO_SEG - (ahora - ultimo)
        if restante > 0:
            return await ctx.send(f"⏳ Espera {int(restante)}s antes de volver a saquear.")
        self._ultimo_saqueo[ctx.author.id] = ahora

        peligro = SECTORES.get(sector, {}).get("peligro", 3)
        agilidad = datos.get("stats", {}).get("agilidad", 5)

        prob_arresto = max(0.10, 0.35 - agilidad * 0.02)
        prob_lesion = max(0.05, 0.20 - agilidad * 0.01)

        if random.random() < prob_arresto:
            from bot import CH_POLICIA_AVISO, ROL_POLICIA
            ch_pol = ctx.guild.get_channel(CH_POLICIA_AVISO)
            if ch_pol:
                rol_pol = ctx.guild.get_role(ROL_POLICIA)
                ping = rol_pol.mention if rol_pol else "@CPNB"
                await ch_pol.send(f"🚨 {ping} **{datos['nombre']}** fue sorprendido/a saqueando en el disturbio de **{sector}**.")
            return await ctx.send(embed=discord.Embed(
                title="🚨 ¡Te agarraron saqueando!",
                description="La policía te sorprendió en pleno saqueo. Espera a que un oficial te procese (`!arrestar`).",
                color=discord.Color.red()
            ))

        if random.random() < prob_lesion:
            await lesiones_mod.agregar_lesion(ctx.author.id, "contusion")
            return await ctx.send(embed=discord.Embed(
                title="🤕 Saqueo caótico",
                description="En medio del caos te empujan y te lastimas. Ganaste algo, pero saliste con una contusión leve (`!lesiones`).",
                color=discord.Color.orange()
            ))

        botin = random.sample(BOTIN_SAQUEO, k=random.randint(1, 2))
        valor = round(random.uniform(15, 90), 2)
        inv = datos.get("inventario", {})
        for b in botin:
            inv[b] = inv.get(b, 0) + 1
        await db.update("personajes", str(ctx.author.id), {
            "inventario": inv,
            "dinero": round(datos.get("dinero", 0) + valor, 2),
        })

        await ctx.send(embed=discord.Embed(
            title="✅ ¡Saqueo exitoso!",
            description=f"Te llevaste: {', '.join(botin)}\n💵 +${valor:,.2f}",
            color=discord.Color.green()
        ))

    @commands.command(name="secuestro")
    async def reportar_secuestro(self, ctx, victima: discord.Member, *, descripcion: str = ""):
        """Reporta un secuestro en el RP. (Admins/sistema)"""
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo admins pueden iniciar un secuestro en el RP.")

        datos = await db.get("personajes", str(victima.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        await db.update("personajes", str(victima.id), {
            "secuestrado": True,
            "en_viaje": False,
        })

        embed = discord.Embed(
            title="⚠️ SECUESTRO",
            description=f"**{datos['nombre']}** ha sido secuestrado/a.\n{descripcion}",
            color=discord.Color.dark_red()
        )
        await ctx.send(embed=embed)
        try:
            await victima.send(f"⚠️ Tu personaje **{datos['nombre']}** ha sido secuestrado. Espera instrucciones del admin.")
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(EventosAdmin(bot))
