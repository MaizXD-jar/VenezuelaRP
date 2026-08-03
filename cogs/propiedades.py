"""
cogs/propiedades.py — Sistema de propiedades completo.
- Al comprar/alquilar: se RENOMBRA el canal casa-N existente, NO se crea uno nuevo.
- Casas con seguridad (alarmas, cámaras, puertas por niveles)
- Sistema de puertas: abrir/cerrar, invitar jugadores
- Robo y okupa con tiempo según seguridad
- Historial de mensajes SOLO visible para dueño e invitados
- Compra de seguridad para el hogar
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import random
import re
import time
from utils import db
from utils.mapa import SECTORES

PRECIOS_CASA = {
    1: 15000, 2: 8000, 3: 3000, 4: 800, 5: 200,
}
ALQUILER_MENSUAL = {nivel: precio // 10 for nivel, precio in PRECIOS_CASA.items()}

# ── SISTEMA DE SEGURIDAD ──────────────────────────────────────────────────────
PUERTAS = {
    "puerta_madera":    {"nivel": 1, "precio": 50,   "resistencia": 1, "descripcion": "Puerta de madera básica."},
    "puerta_metalica":  {"nivel": 2, "precio": 150,  "resistencia": 2, "descripcion": "Puerta metálica reforzada."},
    "puerta_blindada":  {"nivel": 3, "precio": 400,  "resistencia": 3, "descripcion": "Puerta blindada. Difícil de forzar."},
    "puerta_seguridad": {"nivel": 4, "precio": 900,  "resistencia": 4, "descripcion": "Puerta de seguridad profesional."},
    "bunker_door":      {"nivel": 5, "precio": 2500, "resistencia": 5, "descripcion": "Puerta de búnker. Prácticamente infranqueable."},
}

ALARMAS = {
    "alarma_basica":        {"nivel": 1, "precio": 80,   "prob_alerta": 0.40, "descripcion": "Alarma simple. 40% de alertar."},
    "alarma_sonora":        {"nivel": 2, "precio": 200,  "prob_alerta": 0.60, "descripcion": "Alarma sonora. Avisa a vecinos."},
    "alarma_silenciosa":    {"nivel": 3, "precio": 500,  "prob_alerta": 0.75, "descripcion": "Alarma silenciosa. Avisa directo a policía."},
    "alarma_smart":         {"nivel": 4, "precio": 1000, "prob_alerta": 0.90, "descripcion": "Sistema inteligente. Notificación al móvil."},
    "sistema_seguridad_max":{"nivel": 5, "precio": 3000, "prob_alerta": 0.98, "descripcion": "Sistema máximo. Casi imposible evitarla."},
}

CAMARAS = {
    "camara_basica":   {"nivel": 1, "precio": 60,   "descripcion": "Cámara analógica simple."},
    "camara_hd":       {"nivel": 2, "precio": 200,  "descripcion": "Cámara HD. Imagen clara."},
    "camara_360":      {"nivel": 3, "precio": 450,  "descripcion": "Cámara 360°. Sin puntos ciegos."},
    "camara_nocturna": {"nivel": 4, "precio": 800,  "descripcion": "Visión nocturna. Funciona en la oscuridad."},
    "sistema_cctv":    {"nivel": 5, "precio": 2000, "descripcion": "Sistema CCTV profesional. Grabación 24/7."},
}

# Herramienta necesaria para forzar entradas
HERRAMIENTAS_OKUPA = ["ganzua", "hacha", "palanca", "maletin_herramientas"]

# Tiempo base en segundos para forzar una puerta (nivel 1-5)
TIEMPO_FORZAR_PUERTA = {1: 30, 2: 90, 3: 240, 4: 600, 5: 1800}


def _slug(texto: str, max_len: int = 15) -> str:
    t = texto.lower()
    for src, dst in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n")]:
        t = t.replace(src, dst)
    t = re.sub(r'[^a-z0-9\-]', '-', t)
    t = re.sub(r'-+', '-', t).strip('-')
    return t[:max_len]


def _nombre_canal_casa(num: int, sector: str, nombre_personaje: str = None) -> str:
    """Genera el nombre del canal de la casa."""
    sector_slug = _slug(sector, 12)
    if nombre_personaje:
        nombre_slug = _slug(nombre_personaje.replace(" ", ""), 10)
        return f"casa-{num}-{sector_slug}-{nombre_slug}"
    return f"casa-{num}-{sector_slug}"


def _calcular_tiempo_robo(casa: dict) -> int:
    puerta_nivel = PUERTAS.get(casa.get("puerta", ""), {}).get("nivel", 0)
    alarma_nivel = ALARMAS.get(casa.get("alarma", ""), {}).get("nivel", 0)
    camaras_nivel = CAMARAS.get(casa.get("camaras", ""), {}).get("nivel", 0)
    tiempo_base = 30
    tiempo_puerta = TIEMPO_FORZAR_PUERTA.get(puerta_nivel, 0) if puerta_nivel else 0
    tiempo_alarma = alarma_nivel * 30
    tiempo_camaras = camaras_nivel * 20
    return tiempo_base + tiempo_puerta + tiempo_alarma + tiempo_camaras


def _prob_alerta_policia(casa: dict, tiene_armas_dueño: bool = False) -> float:
    alarma = ALARMAS.get(casa.get("alarma", ""), {})
    prob_base = alarma.get("prob_alerta", 0.20)
    if tiene_armas_dueño:
        prob_base = min(0.99, prob_base + 0.30)
    return prob_base


async def _inicializar_casas_sector(sector_key: str):
    sector = SECTORES.get(sector_key, {})
    n_casas = sector.get("casas_total", 20)
    peligro = sector.get("peligro", 2)
    casas_sector = await db.get("casas", sector_key) or {}
    for i in range(1, n_casas + 1):
        casa_id = f"casa-{i}"
        if casa_id not in casas_sector:
            casas_sector[casa_id] = {
                "id": casa_id, "sector": sector_key,
                "dueño": None, "inquilino": None, "okupa": None,
                "precio": PRECIOS_CASA.get(peligro, 5000),
                "alquiler": ALQUILER_MENSUAL.get(peligro, 500),
                "en_venta": True, "en_alquiler": True,
                "amoblada": random.choice([True, False]),
                "estado": "disponible",
                "puerta_abierta": False,
                "puerta": None,
                "alarma": None,
                "camaras": None,
                "invitados": [],
                "canal_id": None,
                "canal_nombre": f"casa-{i}",  # nombre base sin propietario
            }
    await db.set("casas", sector_key, casas_sector)
    return casas_sector


async def _get_casas_choices(interaction: discord.Interaction, current: str):
    choices = []
    for sector_key in SECTORES:
        casas = await db.get("casas", sector_key) or {}
        for casa_id, casa in casas.items():
            if not casa.get("dueño") and not casa.get("okupa"):
                nombre = f"{sector_key}: {casa_id}"
                if current.lower() in nombre.lower():
                    value = f"{sector_key}:{casa_id}"
                    choices.append(app_commands.Choice(name=nombre[:100], value=value))
        if len(choices) >= 25:
            break
    return choices[:25]


def _resolver_canal_casa(guild: discord.Guild, sector: str, numero: int, casa: dict) -> discord.TextChannel | None:
    """Encuentra el canal de Discord de una casa de forma segura.

    ANTES: se buscaba con discord.utils.get(guild.text_channels, name=f"casa-{numero}"),
    lo cual devuelve el PRIMER canal de ese nombre en TODO el servidor. Como cada
    sector reutiliza los mismos nombres (casa-1, casa-2, ...), comprar/alquilar la
    casa-5 de "las-mercedes" podía terminar renombrando la casa-5 de "petare" si
    esa se creó primero. Ahora se prioriza el canal_id guardado en la DB, y si no
    existe, se busca SIEMPRE dentro de la categoría del sector (nunca en todo el
    guild a ciegas).
    """
    canal_id = casa.get("canal_id")
    if canal_id:
        canal = guild.get_channel(canal_id)
        if canal:
            return canal

    nombre_casa = f"casa-{numero}"
    # 1) Categoría dedicada de casas (creada por /iniciar_rp desde esta actualización)
    cat_casas = discord.utils.get(guild.categories, name=f"🏠 CASAS - {sector.upper()}")
    if cat_casas:
        canal = discord.utils.get(cat_casas.channels, name=nombre_casa)
        if canal:
            return canal

    # 2) Compatibilidad con servidores viejos: casas mezcladas en la categoría del sector
    cat_sector = discord.utils.get(guild.categories, name=sector.upper())
    if cat_sector:
        canal = discord.utils.get(cat_sector.channels, name=nombre_casa)
        if canal:
            return canal

    return None


def _es_canal_de_mi_casa(canal_nombre: str, datos: dict) -> bool:
    """Verifica que el personaje esté en el canal de SU propia casa."""
    mis_casas = datos.get("casas", [])
    canal_actual = datos.get("canal_actual", "")
    if canal_actual != canal_nombre:
        return False
    # Verificar que ese canal pertenece a una de sus casas
    return canal_nombre.startswith("casa-")


class Propiedades(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._robos_en_progreso = {}

    def start_tasks(self):
        if not self.revisar_okupas.is_running():
            self.revisar_okupas.start()

    @tasks.loop(hours=2)
    async def revisar_okupas(self):
        """Ocupar una casa ya no es gratis ni permanente: cada cierto tiempo hay
        riesgo de que la policía haga una redada y desaloje al okupa. Sectores
        más seguros (menos peligro) tienen más presencia policial."""
        for sector_key in SECTORES:
            casas = await db.get("casas", sector_key)
            if not casas:
                continue
            cambiado = False
            for casa_id, casa in casas.items():
                if not casa.get("okupa"):
                    continue
                peligro = SECTORES.get(sector_key, {}).get("peligro", 3)
                prob_redada = max(0.05, 0.35 - peligro * 0.05)
                if casa.get("alarma"):
                    prob_redada += 0.10

                if random.random() >= prob_redada:
                    continue

                okupa_id = casa["okupa"]
                casa["okupa"] = None
                casa["estado"] = "disponible"
                casa["invitados"] = []
                casas[casa_id] = casa
                cambiado = True

                canal_id = casa.get("canal_id")
                for guild in self.bot.guilds:
                    member = guild.get_member(int(okupa_id))
                    if not member:
                        continue
                    try:
                        await member.send(
                            f"🚨 La CPNB hizo una redada y te desalojó de **{casa_id}** en **{sector_key}**. "
                            f"Ya no es tu vivienda."
                        )
                    except Exception:
                        pass
                    canal = guild.get_channel(canal_id) if canal_id else None
                    if canal:
                        try:
                            await canal.set_permissions(member, overwrite=None)
                        except Exception:
                            pass
                    break
            if cambiado:
                await db.set("casas", sector_key, casas)

    # ── !casas ────────────────────────────────────────────────────────────────
    @commands.command(name="casas")
    async def listar_casas(self, ctx, sector: str = None):
        datos_per = await db.get("personajes", str(ctx.author.id))
        if not datos_per:
            return await ctx.send("❌ Sin personaje.")
        sector = sector or datos_per.get("ubicacion", "petare")
        sector = sector.lower().replace(" ", "-")
        if sector not in SECTORES:
            return await ctx.send(f"❌ Sector `{sector}` no encontrado.")
        casas = await _inicializar_casas_sector(sector)
        sec_info = SECTORES[sector]
        peligro = sec_info.get("peligro", 2)
        embed = discord.Embed(
            title=f"🏠 Casas en {sec_info.get('display', sector)}",
            description=(
                f"Nivel peligro: {'⚠️'*peligro}\n"
                f"Compra: ${PRECIOS_CASA.get(peligro,5000):,} | Alquiler: ${ALQUILER_MENSUAL.get(peligro,500):,}/mes"
            ),
            color=discord.Color.blue()
        )
        for casa_id, casa in list(casas.items())[:20]:
            if casa["dueño"]:
                m = ctx.guild.get_member(int(casa["dueño"])) if casa["dueño"] else None
                dueño_nombre = m.display_name if m else "Desconocido"
                seg = ""
                if casa.get("puerta"): seg += "🚪"
                if casa.get("alarma"): seg += "🔔"
                if casa.get("camaras"): seg += "📷"
                puerta_txt = "🔓 Abierta" if casa.get("puerta_abierta") else "🔒 Cerrada"
                estado_txt = f"🔒 Dueño: {dueño_nombre} | {puerta_txt} {seg}"
                if casa.get("inquilino"):
                    estado_txt += " | 🏠 Alquilada"
            elif casa.get("okupa"):
                estado_txt = "🚨 Okupa"
            else:
                amob = "✅ Amoblada" if casa.get("amoblada") else "🪑 Sin muebles"
                estado_txt = f"✅ Disponible | {amob}"
            embed.add_field(name=f"🏠 {casa_id}", value=f"{estado_txt}\n`{casa.get('canal_nombre', casa_id)}`", inline=True)
        embed.set_footer(text="!comprar_casa <sector> <num> | !alquilar_casa <sector> <num>")
        await ctx.send(embed=embed)

    # ── /comprar_propiedad ─────────────────────────────────────────────────────
    @app_commands.command(name="comprar_propiedad", description="Compra una casa disponible")
    @app_commands.describe(propiedad="Formato: sector:casa-N (usa el autocompletado)")
    @app_commands.autocomplete(propiedad=_get_casas_choices)
    async def comprar_propiedad_slash(self, interaction: discord.Interaction, propiedad: str):
        await interaction.response.defer(ephemeral=True)
        partes = propiedad.split(":")
        if len(partes) != 2:
            return await interaction.followup.send("❌ Formato inválido. Usa el autocompletado.", ephemeral=True)
        sector, casa_id = partes[0], partes[1]
        num = int(casa_id.replace("casa-", ""))
        await self._comprar_casa_logica(interaction, sector, num, followup=True)

    @commands.command(name="comprar_casa")
    async def comprar_casa(self, ctx, sector: str, numero: int):
        await self._comprar_casa_logica(ctx, sector.lower().replace(" ", "-"), numero)

    async def _comprar_casa_logica(self, ctx_or_inter, sector: str, numero: int, followup: bool = False):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        user = ctx_or_inter.user if is_slash else ctx_or_inter.author

        async def reply(msg, embed=None, ephemeral=False):
            if is_slash:
                if followup:
                    await ctx_or_inter.followup.send(msg, embed=embed, ephemeral=ephemeral)
                else:
                    await ctx_or_inter.response.send_message(msg, embed=embed, ephemeral=ephemeral)
            else:
                await ctx_or_inter.send(msg, embed=embed)

        datos = await db.get("personajes", str(user.id))
        if not datos:
            return await reply("❌ Sin personaje.", ephemeral=True)
        if sector not in SECTORES:
            return await reply(f"❌ Sector `{sector}` no encontrado.", ephemeral=True)

        casas = await _inicializar_casas_sector(sector)
        casa_id = f"casa-{numero}"
        if casa_id not in casas:
            return await reply(f"❌ Casa {numero} no existe en {sector}.", ephemeral=True)
        casa = casas[casa_id]
        if casa["dueño"]:
            return await reply(f"❌ Casa {numero} ya tiene dueño.", ephemeral=True)

        precio = casa["precio"]
        dinero = datos.get("dinero", 0)
        if dinero < precio:
            return await reply(f"❌ Necesitas ${precio:,}, tienes ${dinero:,.2f}.", ephemeral=True)

        nombre_personaje = datos.get("nombre", "")
        # Nuevo nombre del canal: renombrar el existente casa-N
        nuevo_canal_nombre = _nombre_canal_casa(numero, sector, nombre_personaje)

        guild = ctx_or_inter.guild
        # Buscar el canal existente casa-N, siempre escopado al sector correcto
        canal = _resolver_canal_casa(guild, sector, numero, casa)

        # Actualizar DB
        casa["dueño"] = str(user.id)
        casa["estado"] = "ocupada"
        casa["en_venta"] = False
        casa["canal_nombre"] = nuevo_canal_nombre
        casa["puerta"] = "puerta_madera"
        casas[casa_id] = casa
        await db.set("casas", sector, casas)

        mis_casas = datos.get("casas", [])
        mis_casas.append(f"{sector}:{casa_id}")
        await db.update("personajes", str(user.id), {
            "dinero": round(dinero - precio, 2),
            "casas": mis_casas,
        })

        # Renombrar el canal existente y configurar permisos
        if canal:
            try:
                await canal.edit(
                    name=nuevo_canal_nombre,
                    topic=f"🏠 Casa de {nombre_personaje} en {sector} | !abrir_puerta · !cerrar_puerta · !invitar · !tienda_seguridad"
                )
                member = guild.get_member(user.id)
                if member:
                    # Solo el dueño ve el canal
                    await canal.set_permissions(member, read_messages=True, send_messages=True, view_channel=True)
                    # Quitar acceso al rol por defecto si no lo tiene ya
                    await canal.set_permissions(guild.default_role, read_messages=False, view_channel=False)
                casa["canal_id"] = canal.id
                casas[casa_id] = casa
                await db.set("casas", sector, casas)

                # Enviar embed de bienvenida en la casa
                embed_bienvenida = discord.Embed(
                    title="🏠 ¡Bienvenido a tu nueva casa!",
                    description=(
                        f"**{nombre_personaje}** acaba de comprar esta propiedad en **{sector}**.\n\n"
                        f"**Comandos disponibles (solo aquí):**\n"
                        f"• `!abrir_puerta` / `!cerrar_puerta` — controla el acceso\n"
                        f"• `!invitar @usuario` — invita a alguien\n"
                        f"• `!expulsar @usuario` — echa a un invitado\n"
                        f"• `!instalar_seguridad <tipo>` — mejora la seguridad\n"
                        f"• `!tienda_seguridad` — ver opciones de seguridad\n"
                        f"• `!seguridad_casa` — ver estado actual\n"
                        f"• `!craftear_droga <receta>` — fabricar en casa (si aplica)"
                    ),
                    color=discord.Color.green()
                )
                embed_bienvenida.add_field(name="🚪 Puerta instalada", value="Puerta de madera básica (Nivel 1)", inline=True)
                embed_bienvenida.add_field(name="💵 Pagado", value=f"${precio:,}", inline=True)
                embed_bienvenida.set_footer(text="¡Cuida tu hogar!")
                await canal.send(f"{member.mention if member else ''}", embed=embed_bienvenida)

            except Exception as e:
                print(f"[WARN] No se pudo renombrar/configurar canal casa: {e}")

        embed = discord.Embed(
            title="🏠 ¡Casa comprada!",
            description=f"**{nombre_personaje}** es ahora dueño/a de **{casa_id}** en **{sector}**.",
            color=discord.Color.green()
        )
        embed.add_field(name="Precio", value=f"${precio:,}", inline=True)
        embed.add_field(name="Saldo restante", value=f"${dinero-precio:,.2f}", inline=True)
        embed.add_field(name="Canal", value=f"`{nuevo_canal_nombre}`", inline=True)
        embed.set_footer(text="El canal casa-N ha sido renombrado con tu nombre.")
        await reply("", embed=embed)

    # ── !alquilar_casa ─────────────────────────────────────────────────────────
    @commands.command(name="alquilar_casa")
    async def alquilar_casa(self, ctx, sector: str, numero: int):
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        sector = sector.lower().replace(" ", "-")
        casas = await _inicializar_casas_sector(sector)
        casa_id = f"casa-{numero}"
        if casa_id not in casas:
            return await ctx.send(f"❌ Casa {numero} no existe.")
        casa = casas[casa_id]
        if casa["inquilino"]:
            return await ctx.send("❌ Casa ya tiene inquilino.")
        if not casa["en_alquiler"] and not casa["en_venta"]:
            return await ctx.send("❌ Casa no disponible.")
        alquiler = casa["alquiler"]
        dinero = datos.get("dinero", 0)
        if dinero < alquiler:
            return await ctx.send(f"❌ Necesitas ${alquiler:,}. Tienes ${dinero:,.2f}.")

        nombre_personaje = datos.get("nombre", "")
        nuevo_canal_nombre = _nombre_canal_casa(numero, sector, nombre_personaje)

        casa["inquilino"] = str(ctx.author.id)
        casa["canal_nombre"] = nuevo_canal_nombre
        casas[casa_id] = casa
        await db.set("casas", sector, casas)

        mis_casas = datos.get("casas", [])
        mis_casas.append(f"{sector}:{casa_id}:alquiler")
        await db.update("personajes", str(ctx.author.id), {
            "dinero": round(dinero - alquiler, 2),
            "casas": mis_casas
        })

        guild = ctx.guild
        # Buscar canal existente casa-N, siempre escopado al sector correcto
        canal = _resolver_canal_casa(guild, sector, numero, casa)

        if canal:
            try:
                await canal.edit(
                    name=nuevo_canal_nombre,
                    topic=f"🏠 Alquilada por {nombre_personaje} en {sector} | !abrir_puerta · !cerrar_puerta · !invitar"
                )
                await canal.set_permissions(ctx.author, read_messages=True, send_messages=True, view_channel=True)
                await canal.set_permissions(guild.default_role, read_messages=False, view_channel=False)
                casa["canal_id"] = canal.id
                casas[casa_id] = casa
                await db.set("casas", sector, casas)

                embed_bienvenida = discord.Embed(
                    title="🏠 ¡Bienvenido a tu casa alquilada!",
                    description=(
                        f"**{nombre_personaje}** alquila esta propiedad en **{sector}**.\n\n"
                        f"• `!abrir_puerta` / `!cerrar_puerta` — controla el acceso\n"
                        f"• `!invitar @usuario` — invita a alguien\n"
                        f"• `!instalar_seguridad <tipo>` — mejora la seguridad"
                    ),
                    color=discord.Color.blurple()
                )
                embed_bienvenida.add_field(name="💵 Alquiler pagado", value=f"${alquiler:,}/mes", inline=True)
                await canal.send(f"{ctx.author.mention}", embed=embed_bienvenida)
            except Exception as e:
                print(f"[WARN] Canal alquiler: {e}")

        await ctx.send(f"🏠 Alquilaste **{casa_id}** en **{sector}** por ${alquiler:,}/mes. Canal: `{nuevo_canal_nombre}`")

    # ── !abrir_puerta / !cerrar_puerta ─────────────────────────────────────────
    @commands.command(name="abrir_puerta")
    async def abrir_puerta(self, ctx):
        """Abre la puerta de tu casa. Solo funciona DENTRO del canal de tu casa."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        canal_actual = datos.get("canal_actual", "")
        # Verificar que el canal actual ES el canal de una de sus casas
        casa_data = await self._get_casa_de_canal(canal_actual)
        if not casa_data:
            return await ctx.send("❌ Este comando solo funciona dentro del canal de tu casa.")

        sector, casa_id, casa, casas = casa_data
        if casa.get("dueño") != str(ctx.author.id) and casa.get("inquilino") != str(ctx.author.id):
            return await ctx.send("❌ No eres el dueño ni inquilino de esta casa.")

        # Verificar que el mensaje se envía desde el canal correcto
        if ctx.channel.name != canal_actual:
            return await ctx.send(f"❌ Debes estar en el canal `{canal_actual}` para controlar tu puerta.")

        casa["puerta_abierta"] = True
        casas[casa_id] = casa
        await db.set("casas", sector, casas)

        embed = discord.Embed(
            description=(
                "🔓 **La puerta está abierta.**\n"
                "Cualquiera que viaje a esta dirección podrá entrar.\n"
                "Usa `!cerrar_puerta` para cerrarla."
            ),
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="cerrar_puerta")
    async def cerrar_puerta(self, ctx):
        """Cierra la puerta de tu casa. Solo funciona DENTRO del canal de tu casa."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        canal_actual = datos.get("canal_actual", "")
        if ctx.channel.name != canal_actual:
            return await ctx.send(f"❌ Debes estar dentro del canal de tu casa para hacer esto.")

        casa_data = await self._get_casa_de_canal(canal_actual)
        if not casa_data:
            return await ctx.send("❌ Este comando solo funciona dentro del canal de tu casa.")

        sector, casa_id, casa, casas = casa_data
        if casa.get("dueño") != str(ctx.author.id) and casa.get("inquilino") != str(ctx.author.id):
            return await ctx.send("❌ No eres el dueño ni inquilino de esta casa.")

        casa["puerta_abierta"] = False
        casas[casa_id] = casa
        await db.set("casas", sector, casas)

        embed = discord.Embed(
            description="🔒 **Puerta cerrada.** Solo los invitados y el dueño pueden entrar.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    # ── !invitar ───────────────────────────────────────────────────────────────
    @commands.command(name="invitar")
    async def invitar(self, ctx, objetivo: discord.Member):
        """Invita a alguien. Solo funciona DENTRO del canal de tu casa."""
        datos_dueno = await db.get("personajes", str(ctx.author.id))
        datos_obj = await db.get("personajes", str(objetivo.id))
        if not datos_dueno:
            return await ctx.send("❌ Sin personaje.")
        if not datos_obj:
            return await ctx.send(f"❌ {objetivo.display_name} no tiene personaje.")

        canal_actual = datos_dueno.get("canal_actual", "")
        if ctx.channel.name != canal_actual:
            return await ctx.send("❌ Debes estar dentro del canal de tu casa para invitar.")

        casa_data = await self._get_casa_de_canal(canal_actual)
        if not casa_data:
            return await ctx.send("❌ Este comando solo funciona dentro del canal de tu casa.")

        sector, casa_id, casa, casas = casa_data
        if casa.get("dueño") != str(ctx.author.id) and casa.get("inquilino") != str(ctx.author.id):
            return await ctx.send("❌ No eres el dueño ni inquilino de esta casa.")

        invitados = casa.get("invitados", [])
        if str(objetivo.id) not in invitados:
            invitados.append(str(objetivo.id))
        casa["invitados"] = invitados
        casas[casa_id] = casa
        await db.set("casas", sector, casas)

        canal_id = casa.get("canal_id")
        canal = ctx.guild.get_channel(canal_id) if canal_id else ctx.channel
        if canal:
            await canal.set_permissions(objetivo, read_messages=True, send_messages=True, view_channel=True)

        await ctx.send(
            embed=discord.Embed(
                description=f"🏠 **{datos_obj['nombre']}** fue invitado/a. Ahora puede ver el historial y escribir aquí.",
                color=discord.Color.green()
            )
        )
        try:
            await objetivo.send(
                f"🏠 **{datos_dueno['nombre']}** te invitó a su casa.\n"
                f"Canal: `{casa.get('canal_nombre', canal_actual)}`"
            )
        except:
            pass

    # ── !expulsar ──────────────────────────────────────────────────────────────
    @commands.command(name="expulsar")
    async def expulsar(self, ctx, objetivo: discord.Member):
        """Expulsa a un invitado. Solo funciona DENTRO del canal de tu casa."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        canal_actual = datos.get("canal_actual", "")
        if ctx.channel.name != canal_actual:
            return await ctx.send("❌ Debes estar dentro del canal de tu casa.")

        casa_data = await self._get_casa_de_canal(canal_actual)
        if not casa_data:
            return await ctx.send("❌ Este comando solo funciona dentro del canal de tu casa.")

        sector, casa_id, casa, casas = casa_data
        if casa.get("dueño") != str(ctx.author.id):
            return await ctx.send("❌ Solo el dueño puede expulsar invitados.")

        invitados = casa.get("invitados", [])
        if str(objetivo.id) in invitados:
            invitados.remove(str(objetivo.id))
        casa["invitados"] = invitados
        casas[casa_id] = casa
        await db.set("casas", sector, casas)

        canal_id = casa.get("canal_id")
        canal = ctx.guild.get_channel(canal_id) if canal_id else ctx.channel
        if canal:
            await canal.set_permissions(objetivo, overwrite=None)

        await ctx.send(f"👋 {objetivo.display_name} fue expulsado/a de la casa.")

    # ── !instalar_seguridad ────────────────────────────────────────────────────
    @commands.command(name="instalar_seguridad")
    async def instalar_seguridad(self, ctx, tipo: str):
        """Instala seguridad en tu casa. Solo funciona DENTRO del canal de tu casa."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        canal_actual = datos.get("canal_actual", "")
        if ctx.channel.name != canal_actual:
            return await ctx.send("❌ Debes estar dentro del canal de tu casa para instalar seguridad.")

        casa_data = await self._get_casa_de_canal(canal_actual)
        if not casa_data:
            return await ctx.send("❌ Este comando solo funciona dentro del canal de tu casa.")

        sector, casa_id, casa, casas = casa_data
        if casa.get("dueño") != str(ctx.author.id):
            return await ctx.send("❌ Solo el dueño puede instalar seguridad.")

        tipo = tipo.lower().replace(" ", "_")
        item = None
        categoria = None
        for nombre, data in PUERTAS.items():
            if nombre == tipo:
                item = data
                categoria = "puerta"
                break
        if not item:
            for nombre, data in ALARMAS.items():
                if nombre == tipo:
                    item = data
                    categoria = "alarma"
                    break
        if not item:
            for nombre, data in CAMARAS.items():
                if nombre == tipo:
                    item = data
                    categoria = "camaras"
                    break

        if not item:
            return await ctx.send(f"❌ `{tipo}` no encontrado. Usa `!tienda_seguridad` para ver opciones.")

        precio = item["precio"]
        dinero = datos.get("dinero", 0)
        if dinero < precio:
            return await ctx.send(f"❌ Necesitas ${precio:,}. Tienes ${dinero:.2f}.")

        await db.update("personajes", str(ctx.author.id), {"dinero": round(dinero - precio, 2)})
        casa[categoria] = tipo
        casas[casa_id] = casa
        await db.set("casas", sector, casas)

        nivel = item.get("nivel", "?")
        await ctx.send(
            embed=discord.Embed(
                title=f"🔒 Seguridad instalada: {tipo.replace('_', ' ').title()}",
                description=f"Nivel {nivel}/5 | {item['descripcion']}\nCosto: ${precio:,}",
                color=discord.Color.green()
            )
        )

    @commands.command(name="tienda_seguridad")
    async def tienda_seguridad(self, ctx):
        """Muestra todas las opciones de seguridad."""
        embed = discord.Embed(
            title="🔒 Tienda de Seguridad para el Hogar",
            description="Instala con `!instalar_seguridad <nombre>` **estando dentro de tu casa**.",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="🚪 Puertas",
            value="\n".join(
                f"`{k}` Nv.{v['nivel']} — ${v['precio']:,} — {v['descripcion']}"
                for k, v in PUERTAS.items()
            ),
            inline=False
        )
        embed.add_field(
            name="🔔 Alarmas",
            value="\n".join(
                f"`{k}` Nv.{v['nivel']} — ${v['precio']:,} — {v['descripcion']}"
                for k, v in ALARMAS.items()
            ),
            inline=False
        )
        embed.add_field(
            name="📷 Cámaras",
            value="\n".join(
                f"`{k}` Nv.{v['nivel']} — ${v['precio']:,} — {v['descripcion']}"
                for k, v in CAMARAS.items()
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    # ── !ocupar_casa ───────────────────────────────────────────────────────────
    @commands.command(name="ocupar_casa")
    async def ocupar_casa(self, ctx, sector: str, numero: int):
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        sector = sector.lower().replace(" ", "-")
        casas = await _inicializar_casas_sector(sector)
        casa_id = f"casa-{numero}"
        if casa_id not in casas:
            return await ctx.send("❌ Casa no existe.")
        casa = casas[casa_id]
        if casa["dueño"] or casa["okupa"] or casa["inquilino"]:
            return await ctx.send("❌ Casa tiene alguien. No puedes ocuparla.")

        puerta_abierta = casa.get("puerta_abierta", False)
        inv = datos.get("inventario", {})
        if not puerta_abierta:
            tiene_herramienta = any(h in inv for h in HERRAMIENTAS_OKUPA)
            if not tiene_herramienta:
                herramientas_txt = ", ".join(f"`{h}`" for h in HERRAMIENTAS_OKUPA)
                return await ctx.send(
                    f"❌ Necesitas una herramienta: {herramientas_txt}\n"
                    f"O espera a que el dueño deje la puerta abierta."
                )

        tiempo_segundos = _calcular_tiempo_robo(casa) if not puerta_abierta else 5
        await ctx.send(
            embed=discord.Embed(
                description=(
                    f"🔨 **Intentando entrar a {casa_id} en {sector}...**\n"
                    f"Tiempo estimado: {tiempo_segundos}s\n"
                    f"{'🔓 Puerta abierta.' if puerta_abierta else '🔒 Forzando cerradura...'}"
                ),
                color=discord.Color.orange()
            )
        )
        await asyncio.sleep(min(tiempo_segundos, 60))

        prob_alerta = _prob_alerta_policia(casa)
        if not puerta_abierta and random.random() < prob_alerta:
            from bot import CH_POLICIA_AVISO, ROL_POLICIA
            ch_pol = ctx.guild.get_channel(CH_POLICIA_AVISO)
            rol_pol = ctx.guild.get_role(ROL_POLICIA)
            if ch_pol:
                ping = rol_pol.mention if rol_pol else "@Admins"
                await ch_pol.send(f"🚨 {ping} Intento de okupa: **{datos['nombre']}** en {casa_id}, {sector}.")
            return await ctx.send(embed=discord.Embed(
                description="🚨 **¡La alarma se activó!** La CPNB fue notificada.",
                color=discord.Color.red()
            ))

        casa["okupa"] = str(ctx.author.id)
        casa["estado"] = "okupa"
        casa["invitados"] = [str(ctx.author.id)]
        casas[casa_id] = casa
        await db.set("casas", sector, casas)

        canal_id = casa.get("canal_id")
        canal = ctx.guild.get_channel(canal_id) if canal_id else None
        if not canal:
            canal = discord.utils.get(ctx.guild.text_channels, name=casa.get("canal_nombre", ""))
        if canal:
            try:
                await canal.set_permissions(ctx.author, read_messages=True, send_messages=True, view_channel=True)
            except:
                pass

        await ctx.send(embed=discord.Embed(
            title="⚠️ OCUPACIÓN EXITOSA",
            description=f"**{datos['nombre']}** está okupando **{casa_id}** en **{sector}**. Esto es ilegal.",
            color=discord.Color.yellow()
        ))

    # ── !desalojar_okupa ─────────────────────────────────────────────────────
    @commands.command(name="desalojar_okupa")
    async def desalojar_okupa(self, ctx, sector: str, numero: int):
        """[POLICÍA] Desaloja manualmente a un okupa de una casa."""
        from bot import ROL_POLICIA
        rol_pol = ctx.guild.get_role(ROL_POLICIA)
        if not (rol_pol and rol_pol in ctx.author.roles) and not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo la policía puede desalojar okupas.")

        sector = sector.lower().replace(" ", "-")
        casas = await db.get("casas", sector) or {}
        casa_id = f"casa-{numero}"
        casa = casas.get(casa_id)
        if not casa or not casa.get("okupa"):
            return await ctx.send(f"❌ No hay ningún okupa en {casa_id} de {sector}.")

        okupa_id = casa["okupa"]
        casa["okupa"] = None
        casa["estado"] = "disponible"
        casa["invitados"] = []
        casas[casa_id] = casa
        await db.set("casas", sector, casas)

        canal_id = casa.get("canal_id")
        canal = ctx.guild.get_channel(canal_id) if canal_id else None
        member = ctx.guild.get_member(int(okupa_id))
        if canal and member:
            try:
                await canal.set_permissions(member, overwrite=None)
            except Exception:
                pass
        if member:
            try:
                await member.send(f"🚨 La policía te desalojó de **{casa_id}** en **{sector}**.")
            except Exception:
                pass

        await ctx.send(f"✅ Okupa desalojado de **{casa_id}** en **{sector}**.")

    # ── !robar_casa ────────────────────────────────────────────────────────────
    @commands.command(name="robar_casa")
    async def robar_casa(self, ctx, sector: str, numero: int):
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        if ctx.author.id in self._robos_en_progreso:
            return await ctx.send("❌ Ya tienes un robo en progreso.")

        sector = sector.lower().replace(" ", "-")
        casas = await _inicializar_casas_sector(sector)
        casa_id = f"casa-{numero}"
        if casa_id not in casas:
            return await ctx.send("❌ Casa no existe.")
        casa = casas[casa_id]
        if not casa["dueño"]:
            return await ctx.send("❌ Sin dueño. Puedes okuparla con `!ocupar_casa`.")

        puerta_abierta = casa.get("puerta_abierta", False)
        inv = datos.get("inventario", {})
        if not puerta_abierta:
            tiene_herramienta = any(h in inv for h in HERRAMIENTAS_OKUPA)
            if not tiene_herramienta:
                return await ctx.send(f"❌ La puerta está cerrada. Necesitas: {', '.join(f'`{h}`' for h in HERRAMIENTAS_OKUPA)}")

        tiempo_segundos = _calcular_tiempo_robo(casa) if not puerta_abierta else 10
        await ctx.send(embed=discord.Embed(
            description=(
                f"🕵️ **Accediendo a {casa_id} en {sector}...**\n"
                f"Tiempo: {tiempo_segundos}s\n"
                f"{'🔓 Puerta abierta.' if puerta_abierta else '🔒 Forzando cerradura...'}"
            ),
            color=discord.Color.orange()
        ))

        self._robos_en_progreso[ctx.author.id] = {"sector": sector, "casa_id": casa_id}
        await asyncio.sleep(min(tiempo_segundos, 60))
        del self._robos_en_progreso[ctx.author.id]

        casas = await db.get("casas", sector) or {}
        casa = casas.get(casa_id, casa)

        agilidad = datos.get("stats", {}).get("agilidad", 5)
        tecnica = datos.get("stats", {}).get("tecnica", 3)
        puerta_nivel = PUERTAS.get(casa.get("puerta", ""), {}).get("nivel", 0)
        prob_exito = max(0.05, (agilidad + tecnica) / 30 - puerta_nivel * 0.08)
        prob_alerta = _prob_alerta_policia(casa)

        if random.random() < prob_alerta:
            from bot import CH_POLICIA_AVISO, ROL_POLICIA
            ch_pol = ctx.guild.get_channel(CH_POLICIA_AVISO)
            rol_pol = ctx.guild.get_role(ROL_POLICIA)
            if ch_pol:
                ping = rol_pol.mention if rol_pol else "@Admins"
                await ch_pol.send(f"🚨 {ping} Robo detectado: **{datos['nombre']}** en {casa_id}, {sector}.")
            dueño_id = int(casa["dueño"])
            dueño_member = ctx.guild.get_member(dueño_id)
            if dueño_member:
                try:
                    await dueño_member.send(f"🚨 ¡Alguien intenta robar tu casa **{casa_id}** en **{sector}**! La alarma notificó a la CPNB.")
                except:
                    pass
            return await ctx.send("🚨 **¡La alarma se activó!** La CPNB fue notificada.")

        if random.random() > prob_exito:
            return await ctx.send("❌ Robo fallido. La seguridad era demasiado alta.")

        botin = random.sample(["televisor", "laptop", "joyería", "dinero en efectivo", "electrodoméstico", "ropa"], k=random.randint(1, 3))
        valor = random.uniform(20, 200)
        inv_nuevo = datos.get("inventario", {})
        for b in botin[:2]:
            inv_nuevo[b] = inv_nuevo.get(b, 0) + 1
        await db.update("personajes", str(ctx.author.id), {
            "inventario": inv_nuevo,
            "dinero": round(datos.get("dinero", 0) + valor, 2)
        })

        dueño_id = int(casa["dueño"])
        dueño_member = ctx.guild.get_member(dueño_id)
        if dueño_member:
            try:
                await dueño_member.send(f"🚨 ¡Tu casa fue robada! **{casa_id}** en **{sector}**. Robaron: {', '.join(botin)}")
            except:
                pass

        await ctx.send(f"✅ **¡Robo exitoso!** Robaste: {', '.join(botin)}. +${valor:.2f}")

    # ── Helpers ───────────────────────────────────────────────────────────────
    async def _get_casa_de_canal(self, canal_nombre: str):
        """Devuelve (sector, casa_id, casa, casas) del canal o None."""
        for sector_key in SECTORES:
            casas = await db.get("casas", sector_key)
            if not casas:
                continue
            for casa_id, casa in casas.items():
                nombre_canal = casa.get("canal_nombre", "")
                canal_id = casa.get("canal_id")
                if nombre_canal == canal_nombre or casa_id == canal_nombre:
                    return sector_key, casa_id, casa, casas
        return None

    @commands.command(name="mi_casa")
    async def mi_casa(self, ctx):
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        mis_casas = datos.get("casas", [])
        if not mis_casas:
            return await ctx.send("🏠 No tienes propiedades.")
        embed = discord.Embed(title=f"🏠 Propiedades de {datos['nombre']}", color=discord.Color.blue())
        for casa_str in mis_casas:
            partes = casa_str.split(":")
            tipo = "Alquiler" if len(partes) > 2 and partes[2] == "alquiler" else "Propiedad propia"
            sector_c = partes[0] if len(partes) > 0 else "?"
            casa_c = partes[1] if len(partes) > 1 else "?"
            casas_sector = await db.get("casas", sector_c) or {}
            casa = casas_sector.get(casa_c, {})
            seg_txt = ""
            if casa.get("puerta"): seg_txt += f"🚪 {casa['puerta'].replace('_', ' ').title()}"
            if casa.get("alarma"): seg_txt += f" | 🔔 {casa['alarma'].replace('_', ' ').title()}"
            if casa.get("camaras"): seg_txt += f" | 📷 {casa['camaras'].replace('_', ' ').title()}"
            estado_puerta = "🔓 Abierta" if casa.get("puerta_abierta") else "🔒 Cerrada"
            embed.add_field(
                name=f"🏠 {casa_c} en {sector_c}",
                value=f"{tipo} | {estado_puerta}\n{seg_txt or 'Sin seguridad adicional'}\nCanal: `{casa.get('canal_nombre', casa_c)}`",
                inline=False
            )
        embed.set_footer(text="Usa los comandos dentro del canal de tu casa")
        await ctx.send(embed=embed)

    @commands.command(name="seguridad_casa")
    async def seguridad_casa(self, ctx):
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        canal_actual = datos.get("canal_actual", "")
        if ctx.channel.name != canal_actual:
            return await ctx.send("❌ Debes estar dentro del canal de tu casa.")
        casa_data = await self._get_casa_de_canal(canal_actual)
        if not casa_data:
            return await ctx.send("❌ No estás en el canal de tu casa.")
        sector, casa_id, casa, _ = casa_data

        embed = discord.Embed(title=f"🔒 Seguridad de {casa_id}", color=discord.Color.gold())
        puerta = PUERTAS.get(casa.get("puerta", ""), None)
        alarma = ALARMAS.get(casa.get("alarma", ""), None)
        camaras = CAMARAS.get(casa.get("camaras", ""), None)
        embed.add_field(name="🚪 Puerta",
                        value=f"Nivel {puerta['nivel']}/5 — {puerta['descripcion']}" if puerta else "Sin puerta especial", inline=False)
        embed.add_field(name="🔔 Alarma",
                        value=f"Nivel {alarma['nivel']}/5 — {alarma['descripcion']}" if alarma else "Sin alarma", inline=False)
        embed.add_field(name="📷 Cámaras",
                        value=f"Nivel {camaras['nivel']}/5 — {camaras['descripcion']}" if camaras else "Sin cámaras", inline=False)
        tiempo_robo = _calcular_tiempo_robo(casa)
        prob_alerta = _prob_alerta_policia(casa)
        embed.add_field(name="⏱️ Tiempo para robar", value=f"{tiempo_robo}s", inline=True)
        embed.add_field(name="🚨 Prob. alerta policía", value=f"{int(prob_alerta*100)}%", inline=True)
        estado_puerta = "🔓 Abierta" if casa.get("puerta_abierta") else "🔒 Cerrada"
        embed.add_field(name="Estado puerta", value=estado_puerta, inline=True)
        invitados = casa.get("invitados", [])
        embed.add_field(name="👥 Invitados activos", value=str(len(invitados)), inline=True)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Propiedades(bot))