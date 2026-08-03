"""
cogs/viaje.py — Sistema de viaje entre canales y sectores.
- /viajar #canal — soporta mención de canal directo
- Autocomplete de destino
- Método opcional (caminar por defecto)
- FIXED: /viajar solo funciona en canales de RP
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import random
import time
from utils import db
from utils.mapa import (SECTORES, TIEMPOS_VIAJE, get_tiempo, get_sector_de_canal, get_canal_info,
                        metodos_disponibles, mejor_ruta, es_canal_casa, canal_con_sector)

ROL_POLICIA_ID  = 1359320808526450780
ROL_BOMBERO_ID  = 1359320808509538345
ROL_MEDICO_ID   = 1359320808585035789
ROL_FANB_ID     = 1382433542814040084
ROL_EJERCITO_ID = 1382433888852381828

PROTESTAS_MSGS = [
    "⚠️ **TRANCAZO:** Manifestantes en la vía. +15 minutos.",
    "⚠️ **BLOQUEO:** Barricadas en la autopista. +20 min.",
    "⚠️ **GUARIMBAS:** Hay guarimbas en tu ruta. +25 min.",
]

EVENTOS_CAMINO = [
    ("neutral", "Te cruzas con un vendedor ambulante."),
    ("neutral", "El tráfico está terrible. Normal en Venezuela."),
    ("dinero",  "¡Encontraste $5 en el suelo!"),
    ("dinero",  "Un señor te da propina por ayudarle. +$2"),
    ("malo",    "Alguien intentó robarte pero logras escapar."),
    ("malo",    "La unidad de metro se descompone. +10 min."),
]

CANALES_PRISION = {
    "celda-1","celda-2","celda-3","celda-4","celda-5",
    "celda-6","celda-7","celda-8","celda-9","celda-10",
    "celda-yare","patio-yare","oficina-director-yare",
}

viajes_activos: dict[int, dict] = {}


def _es_canal_rp(canal_nombre: str) -> bool:
    """
    Devuelve True si el canal es un canal de RP válido donde se puede usar /viajar.
    Incluye: canales del mapa, casas, celdas y canales de teléfono NO.
    """
    if not canal_nombre:
        return False
    # Canales del mapa
    for sec in SECTORES.values():
        if canal_nombre in sec.get("canales", {}):
            return True
    # Casas, celdas, patios
    if (canal_nombre.startswith("casa-") or
            canal_nombre.startswith("celda-") or
            "patio-yare" in canal_nombre or
            "oficina-director" in canal_nombre or
            "casa-abandonada" in canal_nombre):
        return True
    return False


def _es_viaje_prision(origen: str, destino: str) -> bool:
    return origen in CANALES_PRISION or destino in CANALES_PRISION


def _tiene_rol_emergencia(member: discord.Member) -> bool:
    if not member:
        return False
    ids = {r.id for r in member.roles}
    return bool(ids & {ROL_POLICIA_ID, ROL_BOMBERO_ID, ROL_MEDICO_ID, ROL_FANB_ID, ROL_EJERCITO_ID})


async def _get_destinos_choices(interaction: discord.Interaction, current: str):
    """Autocomplete: devuelve canales disponibles para viajar.

    ANTES: recorría los sectores en orden y cortaba en seco al llegar a 25, así
    que solo aparecían los canales de los primeros sectores y el resto del mapa
    era invisible en /viajar. Ahora se puntúan las coincidencias (las que
    empiezan por lo escrito van primero) y se incluyen también los canales de
    casas existentes en el servidor.
    """
    cur = (current or "").lower().strip()
    exactos, empiezan, contienen = [], [], []

    for sector_key, sec in SECTORES.items():
        emoji = sec.get("emoji", "")
        for canal_nombre in sec.get("canales", {}):
            etiqueta = f"{emoji} {canal_nombre}"[:100]
            choice = app_commands.Choice(name=etiqueta, value=canal_nombre)
            if not cur:
                contienen.append(choice)
            elif canal_nombre.lower() == cur:
                exactos.append(choice)
            elif canal_nombre.lower().startswith(cur):
                empiezan.append(choice)
            elif cur in canal_nombre.lower() or cur in sector_key.lower():
                contienen.append(choice)

    # Canales de casas del servidor (no están en SECTORES porque se renombran)
    if interaction.guild:
        for canal in interaction.guild.text_channels:
            if not canal.name.startswith("casa-"):
                continue
            if cur and cur not in canal.name.lower():
                continue
            choice = app_commands.Choice(name=f"🏠 {canal.name}"[:100], value=canal.name)
            if cur and canal.name.lower().startswith(cur):
                empiezan.append(choice)
            else:
                contienen.append(choice)

    return (exactos + empiezan + contienen)[:25]


def _parse_destino(destino: str, guild: discord.Guild = None) -> str:
    """
    Acepta:
    - #canal (mention de Discord → extrae el nombre)
    - <#12345678> (mention raw → resuelve el ID contra el servidor)
    - nombre-de-canal directamente

    ANTES devolvía None ante un `<#id>`, que es justo lo que manda Discord al
    escribir "#" en un slash command — por eso "no dejaba hacer #".
    """
    destino = (destino or "").strip()
    if destino.startswith("<#") and destino.endswith(">"):
        id_txt = destino[2:-1].strip("!&")
        if id_txt.isdigit() and guild:
            canal = guild.get_channel(int(id_txt))
            if canal:
                return canal.name
        return None
    if destino.startswith("#"):
        destino = destino[1:]
    return destino.lower().replace(" ", "-")


class ViajeView(discord.ui.View):
    def __init__(self, user_id, sector_destino, canal_destino, metodo, duracion_seg, canal_origen_nombre):
        super().__init__(timeout=duracion_seg + 60)
        self.user_id = user_id
        self.sector_destino = sector_destino
        self.canal_destino = canal_destino
        self.metodo = metodo
        self.duracion = duracion_seg
        self.canal_origen_nombre = canal_origen_nombre
        self.cancelado = False

    @discord.ui.button(label="🚫 Cancelar viaje", style=discord.ButtonStyle.red)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("No es tu viaje.", ephemeral=True)
        self.cancelado = True
        viajes_activos.pop(self.user_id, None)
        await db.update("personajes", str(self.user_id), {"en_viaje": False})
        await interaction.response.send_message("❌ Viaje cancelado.")
        self.stop()


class Viaje(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def start_tasks(self):
        if not self.check_llegadas.is_running():
            self.check_llegadas.start()

    @tasks.loop(seconds=10)
    async def check_llegadas(self):
        now = time.time()
        llegados = [uid for uid, v in list(viajes_activos.items()) if now >= v["llegada_ts"]]
        for uid in llegados:
            viaje = viajes_activos.pop(uid, None)
            if viaje:
                await self._procesar_llegada(uid, viaje)

    async def _procesar_llegada(self, user_id: int, viaje: dict):
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return
        member = guild.get_member(user_id)
        if not member:
            return

        sector = viaje["sector_destino"]
        canal_nombre = viaje["canal_destino"]
        canal_origen_nombre = viaje.get("canal_origen_nombre", "")
        sec_info = SECTORES.get(sector, {})

        update_data = {
            "ubicacion": sector,
            "canal_actual": canal_nombre,
            "en_viaje": False,
        }
        if canal_origen_nombre:
            update_data["ultimo_canal"] = canal_origen_nombre

        await db.update("personajes", str(user_id), update_data)

        from utils.permisos import actualizar_visibilidad_al_viajar
        # Canal anterior → solo lectura | Canal nuevo → lectura+escritura
        await actualizar_visibilidad_al_viajar(guild, member, canal_origen_nombre or None, canal_nombre)

        canal_discord = discord.utils.get(guild.text_channels, name=canal_nombre)
        if canal_discord:
            emoji = sec_info.get("emoji", "📍")
            display = sec_info.get("display", sector)
            canal_info = sec_info.get("canales", {}).get(canal_nombre, {})
            c_emoji = canal_info.get("emoji", "📍")
            peligro = canal_info.get("peligro", sec_info.get("peligro", 1))

            embed = discord.Embed(
                title=f"{c_emoji} Llegaste a {canal_con_sector(canal_nombre, sector)}",
                description=f"**Sector:** {emoji} {display} ({sector}) | **Método:** {viaje['metodo']}",
                color=discord.Color.green()
            )
            if peligro >= 4:
                embed.add_field(name="⚠️ ZONA PELIGROSA", value="Ten cuidado.", inline=False)

            await canal_discord.send(f"{member.mention}", embed=embed)

            if canal_nombre.startswith("casa-"):
                await self._tocar_timbre(guild, canal_discord, member, canal_nombre)

    async def _tocar_timbre(self, guild: discord.Guild, canal_casa: discord.TextChannel, visitante: discord.Member, canal_nombre: str):
        """Cuando alguien viaja a una casa, toca el timbre si hay dueño."""
        from utils.mapa import SECTORES as S
        for sector_key in S.keys():
            casas = await db.get("casas", sector_key) or {}
            for casa_id, casa in casas.items():
                if casa.get("canal_nombre") == canal_nombre:
                    dueño_id = casa.get("dueño")
                    if dueño_id:
                        dueño = guild.get_member(int(dueño_id))
                        if dueño:
                            try:
                                datos_visitante = await db.get("personajes", str(visitante.id))
                                nombre_visitante = datos_visitante.get("nombre", visitante.display_name) if datos_visitante else visitante.display_name
                                embed_timbre = discord.Embed(
                                    description=f"🔔 **{nombre_visitante}** toca a tu puerta.\n"
                                                f"Usa `!abrir_puerta` para abrir o ignóralo.",
                                    color=discord.Color.yellow()
                                )
                                await canal_casa.send(f"{dueño.mention}", embed=embed_timbre)
                            except:
                                pass
                    return

    # ── /viajar slash ─────────────────────────────────────────────────────────
    @app_commands.command(name="viajar", description="Viaja a otro canal de RP")
    @app_commands.describe(
        destino="Canal o sector de destino. Puedes usar #canal, el nombre, o escribir para buscar.",
        metodo="Método de transporte (por defecto: caminar)"
    )
    @app_commands.autocomplete(destino=_get_destinos_choices)
    @app_commands.choices(metodo=[
        app_commands.Choice(name="🚶 Caminar", value="caminar"),
        app_commands.Choice(name="🚇 Metro", value="metro"),
        app_commands.Choice(name="🚌 Autobús", value="autobus"),
        app_commands.Choice(name="🚂 Tren", value="tren"),
        app_commands.Choice(name="🚗 Coche", value="coche"),
        app_commands.Choice(name="🚲 Bicicleta", value="bicicleta"),
        app_commands.Choice(name="✈️ Avión", value="avion"),
    ])
    async def viajar_slash(self, interaction: discord.Interaction, destino: str, metodo: str = "caminar"):
        # Verificar que estamos en un canal de RP
        canal_actual_nombre = interaction.channel.name if interaction.channel else ""
        if not _es_canal_rp(canal_actual_nombre):
            return await interaction.response.send_message(
                "❌ Solo puedes usar `/viajar` desde un canal de roleplay.",
                ephemeral=True
            )

        canal_nombre = None
        if destino.startswith("<#") and destino.endswith(">"):
            try:
                canal_id = int(destino[2:-1])
                canal_obj = interaction.guild.get_channel(canal_id)
                if canal_obj:
                    canal_nombre = canal_obj.name
            except:
                pass
        if canal_nombre is None:
            canal_nombre = _parse_destino(destino, interaction.guild)
        await self._ejecutar_viaje(interaction, metodo.lower(), canal_nombre or destino)

    # ── Prefix: !viajar ──────────────────────────────────────────────────────
    @commands.command(name="viajar", aliases=["ir"])
    async def viajar_prefix(self, ctx, *args):
        """
        Uso:
        !viajar #canal
        !viajar petare-central
        !viajar coche petare-central
        Solo funciona en canales de RP.
        """
        # Verificar que estamos en un canal de RP
        canal_actual_nombre = ctx.channel.name if ctx.channel else ""
        if not _es_canal_rp(canal_actual_nombre):
            return await ctx.send(
                "❌ Solo puedes usar `!viajar` desde un canal de roleplay.",
                delete_after=10
            )

        if not args:
            return await ctx.send("❌ Uso: `!viajar #canal` o `!viajar <metodo> <destino>`")

        metodos_validos = ["caminar","metro","autobus","tren","coche","bicicleta","avion"]
        if args[0].lower() in metodos_validos and len(args) > 1:
            metodo = args[0].lower()
            destino_raw = " ".join(args[1:])
        else:
            metodo = "caminar"
            destino_raw = " ".join(args)

        canal_nombre = None
        if ctx.message.channel_mentions:
            canal_nombre = ctx.message.channel_mentions[0].name
        else:
            canal_nombre = _parse_destino(destino_raw, ctx.guild)

        await self._ejecutar_viaje(ctx, metodo, canal_nombre or destino_raw)

    async def _ejecutar_viaje(self, ctx_or_inter, metodo: str, destino: str):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        user = ctx_or_inter.user if is_slash else ctx_or_inter.author
        guild = ctx_or_inter.guild

        async def reply(content=None, embed=None, view=None, ephemeral=False):
            if is_slash:
                if not ctx_or_inter.response.is_done():
                    await ctx_or_inter.response.send_message(content=content, embed=embed, view=view, ephemeral=ephemeral)
                else:
                    await ctx_or_inter.followup.send(content=content, embed=embed, view=view)
            else:
                await ctx_or_inter.send(content=content, embed=embed, view=view)

        datos = await db.get("personajes", str(user.id))
        if not datos:
            return await reply("❌ No tienes personaje.", ephemeral=True)
        if datos.get("muerto"):
            return await reply("❌ Tu personaje está muerto.", ephemeral=True)
        if datos.get("deportado"):
            return await reply(
                "❌ Tu personaje fue deportado y no puede viajar dentro del país. "
                "Un admin puede permitirte volver con `!permitir_reingreso`.", ephemeral=True)
        if datos.get("arrestado"):
            canal_actual = datos.get("canal_actual", "")
            if not _es_viaje_prision(canal_actual, destino):
                return await reply("❌ Estás arrestado. Solo puedes moverte dentro de la prisión.", ephemeral=True)
        if datos.get("en_viaje"):
            return await reply("❌ Ya estás viajando. Espera o cancela el viaje actual.", ephemeral=True)

        metodos_validos = ["caminar","metro","autobus","tren","coche","bicicleta","avion"]
        if metodo not in metodos_validos:
            return await reply(f"❌ Método inválido. Usa: {', '.join(metodos_validos)}", ephemeral=True)

        # Validar vehículos
        if metodo == "coche":
            if not any("coche" in v.lower() or "carro" in v.lower() for v in datos.get("vehiculos", [])):
                return await reply("❌ No tienes coche.", ephemeral=True)
        if metodo == "bicicleta":
            if not any("bicicleta" in k.lower() for k in datos.get("inventario", {})):
                return await reply("❌ No tienes bicicleta.", ephemeral=True)

        canal_actual_nombre = datos.get("canal_actual", "")
        sector_origen = datos.get("ubicacion", "")

        # ── Auto-reparación de ubicación corrupta ────────────────────────────
        # El viejo /forzar_ubicacion guardaba cualquier texto como sector (incluso
        # menciones tipo "<#123456>"), dejando al personaje atascado sin poder
        # viajar a ningún lado. Si el sector guardado no existe en el mapa, se
        # deduce del canal actual; si tampoco, se manda al sector por defecto.
        if sector_origen not in SECTORES:
            sector_reparado = get_sector_de_canal(canal_actual_nombre) if canal_actual_nombre else None
            if not sector_reparado:
                mention = str(sector_origen)
                if mention.startswith("<#") and mention.endswith(">"):
                    id_txt = mention[2:-1].strip("!&")
                    canal_obj = guild.get_channel(int(id_txt)) if id_txt.isdigit() else None
                    if canal_obj:
                        sector_reparado = get_sector_de_canal(canal_obj.name)
                        if sector_reparado:
                            canal_actual_nombre = canal_obj.name
            if not sector_reparado:
                sector_reparado = "petare"
                canal_actual_nombre = canal_actual_nombre or "calle-principal-petare"
            sector_origen = sector_reparado
            await db.update("personajes", str(user.id), {
                "ubicacion": sector_origen,
                "canal_actual": canal_actual_nombre,
            })

        # Resolver destino
        sector_destino = get_sector_de_canal(destino)
        if destino in SECTORES:
            sector_destino = destino
            canales_sec = list(SECTORES[destino]["canales"].keys())
            destino = canales_sec[0] if canales_sec else destino
        elif not sector_destino:
            canal_discord = discord.utils.get(guild.text_channels, name=destino)
            if canal_discord:
                sector_destino = get_sector_de_canal(canal_discord.name)
                destino = canal_discord.name
            if not sector_destino:
                return await reply(f"❌ Canal/sector `{destino}` no encontrado en el mapa.", ephemeral=True)

        # Si el destino es una casa, el canal tiene que existir de verdad en Discord.
        # (Antes se podía iniciar un viaje hacia una casa que nunca se generó y el
        # jugador quedaba "llegando" a un canal inexistente.)
        if es_canal_casa(destino) and not discord.utils.get(guild.text_channels, name=destino):
            return await reply(
                f"❌ La casa `{destino}` no tiene canal creado en este servidor. "
                f"Un admin puede generarlas con `/iniciar_rp` o `/reorganizar_casas`.",
                ephemeral=True)

        # Calcular tiempo
        # ruta_escalas debe existir SIEMPRE: más abajo se lee sin condición, y si
        # solo se definía en la rama de sectores distintos, cualquier viaje dentro
        # del mismo sector reventaba con UnboundLocalError → la interacción nunca
        # se respondía y Discord mostraba "La aplicación no ha respondido".
        ruta_escalas = None
        if _es_viaje_prision(canal_actual_nombre, destino):
            segundos = 20
            minutos = 1
        elif sector_origen == sector_destino:
            minutos = random.randint(5, 15)
            segundos = minutos * 60
        else:
            minutos = get_tiempo(sector_origen, sector_destino, metodo)
            if minutos == 0:
                ruta_escalas = mejor_ruta(sector_origen, sector_destino)
                if not ruta_escalas or not ruta_escalas["pasos"]:
                    return await reply(f"❌ No hay ruta de `{sector_origen}` a `{sector_destino}` (ni con escalas).", ephemeral=True)
                minutos = ruta_escalas["total_minutos"]
            segundos = minutos * 60

        # Bonus emergencia
        member = guild.get_member(user.id)
        es_emergencia = metodo == "coche" and _tiene_rol_emergencia(member)
        if es_emergencia:
            segundos = int(segundos * 0.40)
            minutos = max(1, int(minutos * 0.40))

        # Verificar transporte público disponible
        # ANTES: solo se comprobaba que el SECTOR tuviera en algún lado un canal
        # de metro/tren/aeropuerto, así que podías "viajar en metro" estando en
        # una casa o una calle cualquiera del sector, sin haber pisado la
        # estación. Ahora hace falta estar FÍSICAMENTE en el canal exacto de
        # la estación correspondiente.
        KEYWORDS_ESTACION = {"metro": "metro", "tren": "tren", "avion": "aeropuerto"}
        if metodo in KEYWORDS_ESTACION:
            kw = KEYWORDS_ESTACION[metodo]
            sec_canales = SECTORES.get(sector_origen, {}).get("canales", {})
            estaciones_sector = [c for c in sec_canales if kw in c]
            if not estaciones_sector:
                nombre_metodo = {"metro": "metro", "tren": "tren", "avion": "aeropuerto"}[metodo]
                return await reply(f"❌ No hay {nombre_metodo} en **{sector_origen}**.", ephemeral=True)
            if kw not in canal_actual_nombre:
                estaciones_txt = ", ".join(f"`{e}`" for e in estaciones_sector)
                return await reply(
                    f"❌ Para viajar en {metodo} necesitas estar EN la estación, no solo en el sector.\n"
                    f"Ve primero a: {estaciones_txt} (usa `/viajar destino:<estación>` a pie).",
                    ephemeral=True
                )

        # Protesta aleatoria
        protesta = False
        if not _es_viaje_prision(canal_actual_nombre, destino) and random.random() < 0.07:
            protesta = True
            extra = random.randint(10, 25)
            minutos += extra
            segundos += extra * 60

        # Cap en 5 minutos reales
        segundos = min(segundos, 300)

        llegada_ts = time.time() + segundos
        viajes_activos[user.id] = {
            "canal_destino": destino,
            "sector_destino": sector_destino,
            "llegada_ts": llegada_ts,
            "metodo": metodo,
            "canal_origen_nombre": canal_actual_nombre,
        }
        await db.update("personajes", str(user.id), {"en_viaje": True})

        iconos = {"caminar":"🚶","metro":"🚇","autobus":"🚌","tren":"🚂","coche":"🚗","bicicleta":"🚲","avion":"✈️"}
        icono = iconos.get(metodo, "🚀")

        sec_dest_info = SECTORES.get(sector_destino, {})
        desc = (
            f"**Destino:** {sec_dest_info.get('emoji','')} `{canal_con_sector(destino, sector_destino)}`\n"
            f"**Método:** {icono} {metodo}\n"
            f"**Duración:** ~{minutos} min"
        )
        if es_emergencia:
            desc += "\n🚨 **Luces de emergencia — viaje acelerado**"

        embed = discord.Embed(title=f"{icono} Viaje iniciado", description=desc, color=discord.Color.blue())
        if ruta_escalas and ruta_escalas["pasos"]:
            iconos_metodo = {"caminar":"🚶","metro":"🚇","autobus":"🚌","tren":"🚂","coche":"🚗","bicicleta":"🚲","avion":"✈️"}
            pasos_txt = " → ".join(
                f"{iconos_metodo.get(m,'🚀')} {hasta}" for _, hasta, m, _ in ruta_escalas["pasos"]
            )
            embed.add_field(name="🗺️ Ruta con escalas", value=f"{sector_origen} → {pasos_txt}", inline=False)
        if protesta:
            embed.add_field(name="⚠️ PROTESTA", value=random.choice(PROTESTAS_MSGS), inline=False)

        if random.random() < 0.15:
            ev = random.choice(EVENTOS_CAMINO)
            embed.add_field(name="🎲 En el camino", value=ev[1], inline=False)
            if ev[0] == "dinero":
                monto = 5 if "5" in ev[1] else 2
                await db.update("personajes", str(user.id), {"dinero": round(datos.get("dinero", 0) + monto, 2)})

        embed.set_footer(text="Usa el botón para cancelar")
        view = ViajeView(user.id, sector_destino, destino, metodo, segundos, canal_actual_nombre)
        await reply(embed=embed, view=view)

    # ── /ubicacion ────────────────────────────────────────────────────────────
    @app_commands.command(name="ubicacion", description="Muestra tu ubicación actual")
    @app_commands.describe(usuario="Usuario (opcional)")
    async def ubicacion_slash(self, interaction: discord.Interaction, usuario: discord.Member = None):
        target = usuario or interaction.user
        datos = await db.get("personajes", str(target.id))
        if not datos:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        loc = datos.get("ubicacion", "?")
        canal = datos.get("canal_actual", "?")
        en_viaje = datos.get("en_viaje", False)
        status = "✈️ En viaje..." if en_viaje else f"📍 `{canal}` ({loc})"
        await interaction.response.send_message(f"**{datos['nombre']}** — {status}")

    @commands.command(name="ubicacion", aliases=["donde"])
    async def ubicacion_prefix(self, ctx, miembro: discord.Member = None):
        target = miembro or ctx.author
        datos = await db.get("personajes", str(target.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        loc = datos.get("ubicacion", "?")
        canal = datos.get("canal_actual", "?")
        en_viaje = datos.get("en_viaje", False)
        await ctx.send(f"**{datos['nombre']}** — {'✈️ En viaje...' if en_viaje else f'📍 `{canal}` ({loc})'}")

    # ── /rutas ────────────────────────────────────────────────────────────────
    @app_commands.command(name="rutas", description="Ver rutas disponibles entre dos sectores")
    @app_commands.describe(origen="Sector de origen", destino="Sector de destino")
    async def rutas_slash(self, interaction: discord.Interaction, origen: str, destino: str):
        if origen not in SECTORES:
            return await interaction.response.send_message(f"❌ Sector `{origen}` no encontrado.", ephemeral=True)
        if destino not in SECTORES:
            return await interaction.response.send_message(f"❌ Sector `{destino}` no encontrado.", ephemeral=True)
        embed = discord.Embed(title=f"🗺️ Rutas: {origen} → {destino}", color=discord.Color.blurple())
        iconos = {"caminar":"🚶","metro":"🚇","autobus":"🚌","tren":"🚂","coche":"🚗","bicicleta":"🚲","avion":"✈️"}
        rutas = []
        for m in iconos:
            t = get_tiempo(origen, destino, m)
            if t > 0:
                rutas.append(f"{iconos[m]} **{m}**: ~{t} min")

        if rutas:
            embed.add_field(name="Métodos disponibles (ruta directa)", value="\n".join(rutas), inline=False)
        else:
            ruta = mejor_ruta(origen, destino)
            if not ruta or not ruta["pasos"]:
                embed.add_field(name="Sin ruta directa", value="No existe ningún camino conocido (ni con escalas) entre estos sectores.", inline=False)
            else:
                pasos_txt = "\n".join(
                    f"{i+1}. {iconos.get(m,'🚀')} {desde} → {hasta} (~{mins} min)"
                    for i, (desde, hasta, m, mins) in enumerate(ruta["pasos"])
                )
                embed.add_field(name="Sin ruta directa — plan con escalas", value=pasos_txt, inline=False)
                embed.add_field(name="⏱️ Tiempo total estimado", value=f"~{ruta['total_minutos']} min", inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Viaje(bot))