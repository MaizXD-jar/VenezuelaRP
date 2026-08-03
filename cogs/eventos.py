"""
cogs/eventos.py — ⚠️ NO CARGAR ESTE COG. Versión vieja, reemplazada por
cogs/eventos_random.py (que tiene !evento, !elecciones y !clima ya mejorados).
Los 3 comandos únicos que tenía este archivo (!teleport, !protesta,
!secuestro) viven ahora en cogs/eventos_admin.py, que sí se carga en bot.py.
Se deja este archivo solo de referencia; cargarlo junto a eventos_random.py
rompe el bot por comandos duplicados.
"""
import discord
from discord.ext import commands, tasks
import random
import asyncio
import time
from utils import db
from utils.mapa import SECTORES, PELIGRO_EFECTOS

EVENTOS_PETARE_MERCADO_NEGRO = [
    ("🔫", "¡Un tiroteo inesperado estalla en el mercado negro! Todos a cubierto."),
    ("🦹", "Un carterista roba a alguien al azar en el mercado."),
    ("💊", "Se ofrece mercancía dudosa a quienes están en el mercado."),
    ("🚔", "¡La policía hace una redada! Todos los presentes son sospechosos."),
    ("💣", "Alguien lanza un petardo y causa pánico."),
    ("🔪", "Un ajuste de cuentas entre bandas interrumpe el comercio."),
    ("🧨", "Se escucha una explosión a dos calles. Pánico general."),
    ("🃏", "Un timador está estafando a transeúntes. ¿Intervienen?"),
]

EVENTOS_GENERALES = [
    ("💰", "Alguien tiró una billetera en la calle. Quien llegue primero se la lleva."),
    ("📱", "Un teléfono cae al suelo y su dueño no lo ve."),
    ("🌧️", "Comienza a llover fuerte. Los viajes tardan +10 minutos."),
    ("⚡", "Se fue la luz en toda la zona. Noche cerrada."),
    ("🛻", "Una camioneta sospechosa recorre la zona lentamente."),
    ("📢", "Un vendedor ambulante anuncia artículos a precios de liquidación."),
    ("🔊", "Se escuchan gritos de una casa. ¿Alguien investiga?"),
    ("🐕", "Un perro callejero agresivo bloquea el paso por una calle."),
    ("🎊", "Hay una fiesta improvisada en una de las casas. Se escucha música."),
    ("🚧", "Obras bloquean una calle principal. Rutas alternativas necesarias."),
]

EVENTOS_ELECCIONES = [
    ("🗳️", "Hay una marcha electoral bloqueando la autopista. +30 min viaje."),
    ("📣", "Propaganda electoral por todos lados. Ambiente tenso."),
    ("⚠️", "Guarimbas en el barrio. Zona muy peligrosa por próximas horas."),
    ("🔴", "Colectivos patrullando en motorizados. Precaución extrema."),
    ("📺", "El gobierno anuncia cadena nacional. Todos los canales de TV interrumpidos."),
]

class AdminEventoModal(discord.ui.Modal, title="Crear Evento"):
    titulo = discord.ui.TextInput(label="Título del evento")
    descripcion = discord.ui.TextInput(label="Descripción", style=discord.TextStyle.long)
    canal_nombre = discord.ui.TextInput(label="Canal donde ocurre (nombre)", placeholder="ej: mercado-negro-petare")
    duracion = discord.ui.TextInput(label="Duración (minutos, 0 = permanente)", placeholder="30")

    async def on_submit(self, interaction: discord.Interaction):
        canal_nombre = self.canal_nombre.value.lower().replace(" ", "-")
        canal = discord.utils.get(interaction.guild.text_channels, name=canal_nombre)

        try:
            dur = int(self.duracion.value)
        except:
            dur = 0

        embed = discord.Embed(
            title=f"⚡ EVENTO: {self.titulo.value}",
            description=self.descripcion.value,
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"Evento creado por Admin | Duración: {'indefinida' if dur == 0 else f'{dur} min'}")

        if canal:
            await canal.send("@here", embed=embed)
            await interaction.response.send_message(f"✅ Evento enviado a {canal.mention}", ephemeral=True)
        else:
            await interaction.response.send_message(f"✅ Evento creado (canal `{canal_nombre}` no encontrado en Discord):", ephemeral=False)
            await interaction.followup.send(embed=embed)

        if dur > 0:
            await asyncio.sleep(dur * 60)
            fin_embed = discord.Embed(
                title=f"⏰ Evento finalizado: {self.titulo.value}",
                description="El evento ha concluido.",
                color=discord.Color.grey()
            )
            if canal:
                await canal.send(embed=fin_embed)

class Eventos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.modo_elecciones = False

    def start_tasks(self):
        self.evento_aleatorio.start()

    @tasks.loop(minutes=20)
    async def evento_aleatorio(self):
        """Genera eventos aleatorios en canales peligrosos."""
        for guild in self.bot.guilds:
            for sector_key, sector in SECTORES.items():
                peligro = sector.get("peligro", 1)
                efectos = PELIGRO_EFECTOS.get(peligro, {})
                prob = efectos.get("evento_random_prob", 0.05)

                if random.random() > prob:
                    continue

                # Elegir canal del sector
                canales_sector = list(sector.get("canales", {}).keys())
                if not canales_sector:
                    continue

                canal_nombre = random.choice(canales_sector)
                canal = discord.utils.get(guild.text_channels, name=canal_nombre)
                if not canal:
                    continue

                # Elegir tipo de evento
                if "mercado-negro" in canal_nombre:
                    emoji, msg = random.choice(EVENTOS_PETARE_MERCADO_NEGRO)
                elif self.modo_elecciones and random.random() < 0.5:
                    emoji, msg = random.choice(EVENTOS_ELECCIONES)
                else:
                    emoji, msg = random.choice(EVENTOS_GENERALES)

                embed = discord.Embed(
                    description=f"{emoji} {msg}",
                    color=discord.Color.orange()
                )
                embed.set_footer(text=f"Evento en {canal_nombre}")

                # Buscar personajes en la zona y hacer ping
                personajes = await db.all("personajes")
                menciones = []
                for uid, pdata in personajes.items():
                    if pdata.get("ubicacion") == sector_key and not pdata.get("en_viaje"):
                        member = guild.get_member(int(uid))
                        if member:
                            menciones.append(member.mention)

                if menciones:
                    ping_txt = " ".join(menciones[:5])  # max 5 pings
                    await canal.send(ping_txt, embed=embed)
                else:
                    await canal.send(embed=embed)

                # Efectos del evento
                if "tiroteo" in msg.lower() or "disparo" in msg.lower():
                    for uid in menciones[:3]:  # afecta a los primeros 3
                        uid_clean = uid.replace("<@","").replace(">","").replace("!","")
                        try:
                            pdata = await db.get("personajes", uid_clean)
                            if pdata:
                                stats = pdata.get("stats", {})
                                daño = random.randint(5, 25)
                                stats["hp"] = max(0, stats.get("hp", 100) - daño)
                                await db.update("personajes", uid_clean, {"stats": stats})
                        except:
                            pass

    @commands.command(name="evento")
    async def evento_admin(self, ctx):
        """Crea un evento personalizado. (Solo admins)"""
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo admins.")
        await ctx.send_modal(AdminEventoModal())

    @commands.command(name="teleport")
    async def teleport(self, ctx, objetivo: discord.Member, *, destino: str):
        """Teleporta a un personaje a un sector/canal. (Solo admins)"""
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo admins.")

        datos = await db.get("personajes", str(objetivo.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        destino = destino.lower().replace(" ", "-")
        from utils.mapa import get_sector_de_canal
        sector = get_sector_de_canal(destino)
        if not sector:
            if destino in SECTORES:
                sector = destino
                # Primer canal del sector
                canales = list(SECTORES[destino]["canales"].keys())
                destino = canales[0] if canales else destino
            else:
                return await ctx.send(f"❌ Destino `{destino}` no encontrado.")

        await db.update("personajes", str(objetivo.id), {
            "ubicacion": sector,
            "canal_actual": destino,
            "en_viaje": False,
        })

        # Remover de viajes activos si hay
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
        except:
            pass

    @commands.command(name="elecciones")
    async def toggle_elecciones(self, ctx):
        """Activa/desactiva el modo elecciones (más protestas). (Admins)"""
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo admins.")
        self.modo_elecciones = not self.modo_elecciones
        estado = "🗳️ ACTIVADO" if self.modo_elecciones else "✅ Desactivado"
        await ctx.send(f"Modo elecciones: **{estado}**. Las protestas {'aumentarán' if self.modo_elecciones else 'volverán a la normalidad'}.")

    @commands.command(name="protesta")
    async def crear_protesta(self, ctx, *, sector: str = None):
        """Crea una protesta que afecta viajes. (Admins)"""
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo admins.")

        sector = sector or "general"
        embed = discord.Embed(
            title="⚠️ PROTESTA ACTIVA",
            description=f"Una protesta está bloqueando rutas en **{sector}**.\n"
                         f"Los viajes pueden sufrir demoras de 15-30 minutos adicionales.",
            color=discord.Color.yellow()
        )
        # Guardar protesta activa
        protestas = await db.get("eventos", "protestas") or []
        protestas.append({"sector": sector, "ts": time.time()})
        await db.set("eventos", "protestas", protestas)
        await ctx.send(embed=embed)

    @commands.command(name="clima")
    async def clima(self, ctx):
        """Estado del clima actual en Venezuela."""
        climas = [
            ("☀️", "Soleado y caluroso. Temperatura ~33°C."),
            ("🌧️", "Lluvia fuerte. Los viajes tardan +10 minutos."),
            ("⛈️", "Tormenta eléctrica. Viajes arriesgados."),
            ("🌤️", "Parcialmente nublado. Temperatura agradable ~27°C."),
            ("🌫️", "Neblina en las montañas. Visibilidad reducida."),
        ]
        emoji, desc = random.choice(climas)
        embed = discord.Embed(
            title=f"{emoji} Clima en Caracas",
            description=desc,
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

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
        except:
            pass

async def setup(bot):
    await bot.add_cog(Eventos(bot))