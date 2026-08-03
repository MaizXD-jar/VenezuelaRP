"""
cogs/embeds_canales.py — Embeds informativos en TODOS los canales.

- /generar_embeds : publica (o actualiza) en cada canal del mapa un embed que
  explica para qué sirve el sitio y qué comandos se pueden usar ahí.
- Los canales de casas reciben un embed especial y VIVO: muestra estado real
  (libre / dueño / alquilada / okupa / casa de padres), si la puerta está
  cerrada y qué seguridad tiene, con botones para comprar o alquilar
  sincronizados con el sistema de propiedades.
- /actualizar_embed_casa : refresca el embed de una casa concreta.

Los embeds se anclan (pin) y se guarda su ID en la tabla `embeds_canales` para
poder editarlos en vez de duplicarlos cada vez.
"""
import discord
from discord.ext import commands
from discord import app_commands

from utils import db
from utils.mapa import SECTORES, get_sector_de_canal, es_canal_casa

# ── Texto por tipo de canal ──────────────────────────────────────────────────
INFO_TIPOS = {
    "calle": {
        "emoji": "🛣️", "titulo": "Calle",
        "desc": "Vía pública. Aquí se camina, se hace roleplay libre y pueden ocurrir robos o peleas.",
        "cmds": ["`/viajar` — ir a otro sitio", "`!pelear @alguien`", "`!robar @alguien`", "`/ubicacion`"],
    },
    "avenida": {
        "emoji": "🛤️", "titulo": "Avenida",
        "desc": "Gran vía de la ciudad. Mucho tránsito y presencia policial ocasional.",
        "cmds": ["`/viajar`", "`!pelear @alguien`", "`/ubicacion`"],
    },
    "barrio": {
        "emoji": "🏘️", "titulo": "Barrio",
        "desc": "Zona residencial. Aquí viven personajes y suele haber más actividad informal.",
        "cmds": ["`/viajar`", "`!casas <sector>` — ver casas de la zona", "`!ocupar_casa`"],
    },
    "mercado": {
        "emoji": "🏪", "titulo": "Mercado",
        "desc": "Compra y venta de productos. Los precios varían con la economía del servidor.",
        "cmds": ["`/comprar <item>`", "`/tienda`", "`/precios`", "`!vender <item>`"],
    },
    "comercio": {
        "emoji": "🛒", "titulo": "Comercio",
        "desc": "Local comercial legal. Todo lo que compres aquí paga IVA según su categoría.",
        "cmds": ["`/comprar <item>`", "`/tienda`", "`!impuestos` — ver tasas de IVA"],
    },
    "banco": {
        "emoji": "🏦", "titulo": "Banco",
        "desc": "Servicios financieros: cuentas, depósitos, retiros, inversiones y préstamos.",
        "cmds": ["`!depositar <monto>`", "`!retirar <monto>`", "`!banco` — ver saldo",
                 "`!invertir`", "`!banco_app` — app móvil", "`!transferir_banco @alguien <monto>`"],
    },
    "hospital": {
        "emoji": "🏥", "titulo": "Hospital",
        "desc": "Atención médica. Si estás herido, aquí se tratan las lesiones antes de que empeoren.",
        "cmds": ["`!lesiones` — ver tus heridas", "`!ir_hospital` — ingresar",
                 "`!tratar_lesion <tipo>` — curar una lesión", "`!curarse`"],
    },
    "policia": {
        "emoji": "🚔", "titulo": "Comisaría",
        "desc": "Sede policial. Los agentes gestionan arrestos, denuncias y búsquedas desde aquí.",
        "cmds": ["`!denunciar @alguien`", "`!arrestar @alguien` (policía)",
                 "`!buscados` — lista de más buscados", "`!desalojar_okupa` (policía)"],
    },
    "gobierno": {
        "emoji": "🏛️", "titulo": "Edificio de gobierno",
        "desc": "Trámites oficiales, política y administración del Estado.",
        "cmds": ["`!tesoro_nacional`", "`!impuestos`", "`!elecciones`", "`!votar`"],
    },
    "educacion": {
        "emoji": "🎓", "titulo": "Centro educativo",
        "desc": "Estudiar sube tus estadísticas y desbloquea trabajos mejor pagados.",
        "cmds": ["`!estudiar`", "`!inscribirse <carrera>`", "`!mis_estudios`"],
    },
    "trabajo": {
        "emoji": "💼", "titulo": "Lugar de trabajo",
        "desc": "Aquí se trabaja para ganar dinero legalmente.",
        "cmds": ["`!trabajar`", "`!trabajos` — ver empleos disponibles", "`!renunciar`"],
    },
    "oficina": {
        "emoji": "🏢", "titulo": "Zona de oficinas",
        "desc": "Sedes de empresas y actividad corporativa.",
        "cmds": ["`!crear_empresa <tipo> <sector> <nombre>`", "`!empresa`", "`!abrir_sucursal <sector>`"],
    },
    "transporte": {
        "emoji": "🚉", "titulo": "Transporte",
        "desc": "Punto de conexión para viajar a otros sectores de forma más rápida.",
        "cmds": ["`/viajar <destino> <método>`", "`/rutas <origen> <destino>`"],
    },
    "concesionario": {
        "emoji": "🚗", "titulo": "Concesionario",
        "desc": "Venta de vehículos. Tener coche reduce mucho los tiempos de viaje.",
        "cmds": ["`/comprar <vehiculo>`", "`!vehiculos` — ver los tuyos"],
    },
    "deporte": {
        "emoji": "⚽", "titulo": "Instalación deportiva",
        "desc": "Entrena para mejorar tus estadísticas físicas.",
        "cmds": ["`!entrenar`", "`!stats` — ver tus estadísticas"],
    },
    "recreacion": {
        "emoji": "🎰", "titulo": "Ocio y recreación",
        "desc": "Zona de entretenimiento. Algunos locales son solo para mayores de 18 en el rol.",
        "cmds": ["`!casino`", "`!tragamonedas <monto>`", "`!ruleta <monto> <apuesta>`",
                 "`!blackjack <monto>`", "`!trivia`"],
    },
    "peligro": {
        "emoji": "☠️", "titulo": "Zona peligrosa",
        "desc": "Sitio de alto riesgo. Aquí pasan cosas que en otros lados no: robos, tiroteos, negocios turbios.",
        "cmds": ["`!disparar @alguien`", "`!pelear @alguien`", "`!huir`", "`!saquear` (durante disturbios)"],
    },
    "celda": {
        "emoji": "🔒", "titulo": "Celda",
        "desc": "Estás preso. Solo puedes moverte dentro de la prisión hasta cumplir tu condena.",
        "cmds": ["`!condena` — ver tiempo restante", "`!patio`"],
    },
    "patio": {
        "emoji": "🧱", "titulo": "Patio de la prisión",
        "desc": "Zona común de la cárcel. Se puede socializar... y pelear.",
        "cmds": ["`!pelear @alguien`", "`!condena`"],
    },
    "general": {
        "emoji": "📍", "titulo": "Zona general",
        "desc": "Espacio de roleplay libre.",
        "cmds": ["`/viajar`", "`/ubicacion`", "`/perfil`"],
    },
}

COMANDOS_UNIVERSALES = "`/perfil` · `/inventario` · `/ubicacion` · `/viajar` · `!ayuda`"


def _info_para_canal(canal_nombre: str) -> dict | None:
    for sec_key, sec in SECTORES.items():
        info = sec.get("canales", {}).get(canal_nombre)
        if info:
            return {"sector": sec_key, "sector_data": sec, "canal_info": info}
    return None


def _embed_canal(canal_nombre: str, ctx_info: dict) -> discord.Embed:
    sec_key = ctx_info["sector"]
    sec = ctx_info["sector_data"]
    cinfo = ctx_info["canal_info"]
    tipo = cinfo.get("tipo", "general")
    plantilla = INFO_TIPOS.get(tipo, INFO_TIPOS["general"])

    peligro = cinfo.get("peligro", sec.get("peligro", 1))
    embed = discord.Embed(
        title=f"{cinfo.get('emoji', plantilla['emoji'])} {canal_nombre.replace('-', ' ').title()}",
        description=plantilla["desc"],
        color=discord.Color.from_rgb(46, 204, 113) if peligro <= 2 else
              (discord.Color.orange() if peligro <= 3 else discord.Color.red())
    )
    embed.add_field(name="📍 Sector", value=f"{sec.get('emoji','')} {sec.get('display', sec_key)}", inline=True)
    embed.add_field(name="🏷️ Tipo", value=plantilla["titulo"], inline=True)
    embed.add_field(name="⚠️ Peligro", value="🔺" * max(1, int(peligro)) + f" ({peligro}/5)", inline=True)
    embed.add_field(name="🎮 Qué puedes hacer aquí", value="\n".join(f"• {c}" for c in plantilla["cmds"]), inline=False)
    embed.add_field(name="🌐 Siempre disponibles", value=COMANDOS_UNIVERSALES, inline=False)
    embed.set_footer(text="Debes estar físicamente en este canal para usar sus comandos.")
    return embed


# ══════════════════════════════════════════════════════════════════════════
# Embed de casa (vivo, con botones)
# ══════════════════════════════════════════════════════════════════════════
class CasaView(discord.ui.View):
    def __init__(self, sector: str, numero: int, disponible: bool, en_alquiler: bool):
        super().__init__(timeout=None)
        self.sector = sector
        self.numero = numero
        if not disponible:
            for child in list(self.children):
                self.remove_item(child)
        elif not en_alquiler:
            for child in list(self.children):
                if getattr(child, "custom_id", "") == "casa_alquilar":
                    self.remove_item(child)

    @discord.ui.button(label="💰 Comprar", style=discord.ButtonStyle.green, custom_id="casa_comprar")
    async def comprar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"Para comprarla usa: `!comprar_casa {self.sector} {self.numero}`\n"
            f"(o el comando `/comprar_propiedad` y elige `{self.sector}:casa-{self.numero}`)",
            ephemeral=True
        )

    @discord.ui.button(label="🔑 Alquilar", style=discord.ButtonStyle.blurple, custom_id="casa_alquilar")
    async def alquilar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"Para alquilarla usa: `!alquilar_casa {self.sector} {self.numero}`",
            ephemeral=True
        )


def _embed_casa(guild: discord.Guild, sector: str, casa_id: str, casa: dict) -> tuple[discord.Embed, CasaView]:
    numero = int(casa_id.replace("casa-", "") or 0)
    sec = SECTORES.get(sector, {})

    dueño_id = casa.get("dueño")
    inquilino_id = casa.get("inquilino")
    okupa_id = casa.get("okupa")
    padres_de = casa.get("padres_de")

    disponible = not (dueño_id or inquilino_id or okupa_id or padres_de)

    if dueño_id:
        m = guild.get_member(int(dueño_id))
        estado = f"🔒 **Propiedad de {m.display_name if m else 'Desconocido'}**"
        color = discord.Color.dark_gold()
    elif padres_de:
        m = guild.get_member(int(padres_de))
        estado = f"👨‍👩‍👦 **Casa familiar** (padres de {m.display_name if m else 'un personaje'})"
        color = discord.Color.blurple()
    elif inquilino_id:
        m = guild.get_member(int(inquilino_id))
        estado = f"🔑 **Alquilada por {m.display_name if m else 'Desconocido'}**"
        color = discord.Color.teal()
    elif okupa_id:
        m = guild.get_member(int(okupa_id))
        estado = f"🚨 **Ocupada ilegalmente** por {m.display_name if m else 'un okupa'}"
        color = discord.Color.red()
    else:
        estado = "✅ **Disponible**"
        color = discord.Color.green()

    embed = discord.Embed(
        title=f"🏠 {casa_id.replace('-', ' ').title()} — {sec.get('display', sector)}",
        description=estado,
        color=color
    )

    puerta_txt = "🔓 Abierta" if casa.get("puerta_abierta") else "🔒 Cerrada"
    embed.add_field(name="🚪 Puerta", value=puerta_txt, inline=True)
    embed.add_field(name="🪑 Mobiliario", value="✅ Amoblada" if casa.get("amoblada") else "Sin muebles", inline=True)
    embed.add_field(name="⚠️ Peligro del sector", value=f"{sec.get('peligro','?')}/5", inline=True)

    seguridad = []
    if casa.get("puerta"):  seguridad.append(f"🚪 {casa['puerta']}")
    if casa.get("alarma"):  seguridad.append(f"🔔 {casa['alarma']}")
    if casa.get("camaras"): seguridad.append(f"📷 {casa['camaras']}")
    embed.add_field(name="🛡️ Seguridad instalada",
                    value="\n".join(seguridad) if seguridad else "Ninguna",
                    inline=False)

    if disponible:
        embed.add_field(name="💰 Precio de compra", value=f"${casa.get('precio', 0):,}", inline=True)
        embed.add_field(name="🔑 Alquiler", value=f"${casa.get('alquiler', 0):,}/mes", inline=True)
        embed.set_footer(text=f"!comprar_casa {sector} {numero}  |  !alquilar_casa {sector} {numero}")
    else:
        residentes = casa.get("residentes", [])
        if residentes:
            nombres = [guild.get_member(int(r)).display_name for r in residentes if guild.get_member(int(r))]
            if nombres:
                embed.add_field(name="👥 Residentes", value=", ".join(nombres), inline=False)
        embed.set_footer(text="Comandos del residente: !cerrar_puerta · !abrir_puerta · !invitar @alguien · !seguridad_casa")

    view = CasaView(sector, numero, disponible, bool(casa.get("en_alquiler")))
    return embed, view


class EmbedsCanales(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _publicar_o_editar(self, canal: discord.TextChannel, embed: discord.Embed, view=None) -> str:
        """Edita el embed existente si ya se publicó antes; si no, lo crea y lo fija."""
        registro = await db.get("embeds_canales", str(canal.id))
        if registro and registro.get("mensaje_id"):
            try:
                msg = await canal.fetch_message(int(registro["mensaje_id"]))
                await msg.edit(embed=embed, view=view)
                return "editado"
            except Exception:
                pass
        try:
            msg = await canal.send(embed=embed, view=view)
            try:
                await msg.pin(reason="Embed informativo del canal")
            except Exception:
                pass
            await db.set("embeds_canales", str(canal.id), {"mensaje_id": msg.id, "canal": canal.name})
            return "creado"
        except Exception as e:
            print(f"[WARN] embed en #{canal.name}: {e}")
            return "error"

    @app_commands.command(name="generar_embeds",
                          description="[ADMIN] Publica un embed informativo en TODOS los canales del mapa y casas")
    async def generar_embeds(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ Solo admins.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        creados = editados = errores = casas_ok = 0

        # 1) Canales normales del mapa
        for canal in guild.text_channels:
            ctx_info = _info_para_canal(canal.name)
            if not ctx_info:
                continue
            res = await self._publicar_o_editar(canal, _embed_canal(canal.name, ctx_info))
            if res == "creado": creados += 1
            elif res == "editado": editados += 1
            else: errores += 1

        # 2) Canales de casas (embed vivo con estado y botones)
        for sector_key in SECTORES:
            casas = await db.get("casas", sector_key)
            if not casas:
                continue
            for casa_id, casa in casas.items():
                canal = None
                if casa.get("canal_id"):
                    canal = guild.get_channel(casa["canal_id"])
                if not canal:
                    canal = discord.utils.get(guild.text_channels, name=casa.get("canal_nombre", casa_id))
                if not canal:
                    continue
                embed, view = _embed_casa(guild, sector_key, casa_id, casa)
                res = await self._publicar_o_editar(canal, embed, view)
                if res != "error":
                    casas_ok += 1
                else:
                    errores += 1

        await interaction.followup.send(
            f"✅ **Embeds generados**\n"
            f"🆕 Creados: {creados}\n"
            f"♻️ Actualizados: {editados}\n"
            f"🏠 Casas: {casas_ok}\n"
            f"⚠️ Errores: {errores}",
            ephemeral=True
        )

    @app_commands.command(name="actualizar_embed_casa",
                          description="[ADMIN] Refresca el embed de una casa concreta")
    @app_commands.describe(sector="Sector de la casa", numero="Número de la casa")
    async def actualizar_embed_casa(self, interaction: discord.Interaction, sector: str, numero: int):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ Solo admins.", ephemeral=True)
        sector = sector.lower().replace(" ", "-")
        casas = await db.get("casas", sector) or {}
        casa_id = f"casa-{numero}"
        casa = casas.get(casa_id)
        if not casa:
            return await interaction.response.send_message(f"❌ No existe {casa_id} en {sector}.", ephemeral=True)

        guild = interaction.guild
        canal = guild.get_channel(casa["canal_id"]) if casa.get("canal_id") else None
        if not canal:
            canal = discord.utils.get(guild.text_channels, name=casa.get("canal_nombre", casa_id))
        if not canal:
            return await interaction.response.send_message("❌ Esa casa no tiene canal creado.", ephemeral=True)

        embed, view = _embed_casa(guild, sector, casa_id, casa)
        await self._publicar_o_editar(canal, embed, view)
        await interaction.response.send_message(f"✅ Embed de {casa_id} actualizado en {canal.mention}.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(EmbedsCanales(bot))
