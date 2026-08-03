"""
cogs/telefono.py — Sistema de teléfono: canales privados de comunicación
entre personajes, "llamadas" simuladas, mensajes de texto.
"""
import discord
from discord.ext import commands
import asyncio
import random
import re
from utils import db

# Formato del canal privado: 📱tel-{nombre1}-{nombre2}
# Guardamos activos: {frozenset(id1, id2): channel_id}
conversaciones_activas: dict[frozenset, int] = {}
llamadas_activas: dict[int, int] = {}  # caller_id: called_id

# ── Números de emergencia ─────────────────────────────────────────────────────
# Marcar cualquiera de estos números despacha una llamada automática a
# emergencias (policía/bomberos/médicos), sin necesidad de que exista un
# personaje "dueño" de ese número.
NUMEROS_EMERGENCIA = {"911", "112", "0800"}


def _normalizar_numero(texto: str) -> str:
    """Deja solo dígitos y guiones para poder comparar números de teléfono
    escritos de formas distintas (con o sin guion, con o sin espacios)."""
    return re.sub(r"[^0-9]", "", texto or "")


async def _buscar_personaje_por_numero(numero: str):
    """Busca en TODOS los personajes registrados uno cuyo teléfono coincida.
    Devuelve (user_id, datos) o (None, None) si no existe."""
    objetivo = _normalizar_numero(numero)
    if not objetivo:
        return None, None
    todos = await db.all("personajes")
    for uid, datos in todos.items():
        tel = _normalizar_numero(datos.get("telefono", ""))
        if tel and tel == objetivo:
            return int(uid), datos
    return None, None


async def _resolver_destino_llamada(ctx, numero_o_mencion: str):
    """Resuelve a quién se está llamando/mensajeando a partir de lo que el
    jugador escribió: puede ser una @mención de Discord, un número de
    teléfono marcado a mano, uno de los números de emergencia, o directamente
    su PROPIO número (se puede llamar a uno mismo).

    Devuelve una tupla (modo, valor):
    - ("emergencia", None)                     -> marcó 911/112/0800
    - ("miembro", discord.Member)               -> objetivo válido (puede ser el propio autor)
    - ("error", "mensaje de error para mostrar")
    Solo se puede llamar/mensajear a PERSONAS con personaje registrado — nunca
    a un número que no pertenezca a nadie ni a un NPC.
    """
    texto = (numero_o_mencion or "").strip()
    limpio = _normalizar_numero(texto)

    if limpio in NUMEROS_EMERGENCIA or texto in NUMEROS_EMERGENCIA:
        return "emergencia", None

    # ¿Es una @mención de Discord?
    match = re.match(r"^<@!?(\d+)>$", texto)
    if match:
        member = ctx.guild.get_member(int(match.group(1)))
        if not member:
            return "error", "❌ No encuentro a ese usuario en el servidor."
        return "miembro", member

    # ¿Escribió directamente un número de teléfono? (el suyo propio incluido)
    if limpio and len(limpio) >= 6:
        uid, datos_obj = await _buscar_personaje_por_numero(limpio)
        if not uid:
            return "error", f"❌ El número `{texto}` no está registrado a ningún personaje."
        member = ctx.guild.get_member(uid)
        if not member:
            return "error", "❌ Ese número pertenece a alguien que ya no está en el servidor."
        return "miembro", member

    return "error", ("❌ Marca un número de teléfono (el tuyo, el de otro personaje, o 911/112/0800), "
                     "o menciona a alguien con @usuario.")

class LlamadaView(discord.ui.View):
    def __init__(self, llamante_id: int, receptor_id: int, canal_id: int, datos_ll: dict, datos_rx: dict):
        super().__init__(timeout=60)
        self.llamante_id = llamante_id
        self.receptor_id = receptor_id
        self.canal_id = canal_id
        self.datos_ll = datos_ll
        self.datos_rx = datos_rx

    @discord.ui.button(label="📞 Contestar", style=discord.ButtonStyle.green)
    async def contestar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.receptor_id:
            return await interaction.response.send_message("No es tu llamada.", ephemeral=True)

        llamadas_activas[self.llamante_id] = self.receptor_id
        llamadas_activas[self.receptor_id] = self.llamante_id

        canal = interaction.guild.get_channel(self.canal_id)
        if canal:
            embed = discord.Embed(
                title="📞 Llamada conectada",
                description=f"**{self.datos_ll['nombre']}** y **{self.datos_rx['nombre']}** están en llamada.\n"
                             f"Escribe aquí para hablar. Usa `/colgar` para terminar.",
                color=discord.Color.green()
            )
            await canal.send(embed=embed)
        await interaction.response.send_message("✅ Llamada conectada.", ephemeral=True)
        await interaction.message.edit(view=None)
        self.stop()

    @discord.ui.button(label="🔴 Rechazar", style=discord.ButtonStyle.red)
    async def rechazar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.receptor_id:
            return await interaction.response.send_message("No es tu llamada.", ephemeral=True)

        canal = interaction.guild.get_channel(self.canal_id)
        if canal:
            await canal.send("📵 Llamada rechazada.")
        await interaction.response.send_message("Llamada rechazada.", ephemeral=True)
        await interaction.message.edit(view=None)
        self.stop()

class Telefono(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _obtener_o_crear_canal(self, guild: discord.Guild, user1_id: int, user2_id: int,
                                     datos1: dict, datos2: dict) -> discord.TextChannel:
        """Obtiene o crea el canal privado entre dos personajes."""
        key = frozenset([user1_id, user2_id])
        if key in conversaciones_activas:
            canal = guild.get_channel(conversaciones_activas[key])
            if canal:
                return canal

        # Buscar categoría de teléfonos
        categoria = discord.utils.get(guild.categories, name="📱 Teléfonos")
        if not categoria:
            categoria = await guild.create_category("📱 Teléfonos")

        # Nombre del canal
        n1 = datos1.get("nombre","?").lower().replace(" ","-")[:10]
        n2 = datos2.get("nombre","?").lower().replace(" ","-")[:10]
        nombre_canal = f"📱tel-{n1}-{n2}"

        # Permisos: solo los 2 usuarios y admins
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        m1 = guild.get_member(user1_id)
        m2 = guild.get_member(user2_id)
        if m1:
            overwrites[m1] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        if m2:
            overwrites[m2] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        canal = await guild.create_text_channel(
            nombre_canal,
            category=categoria,
            overwrites=overwrites,
            topic=f"Canal privado entre {datos1.get('nombre','?')} y {datos2.get('nombre','?')}"
        )

        conversaciones_activas[key] = canal.id

        # Mensaje de bienvenida
        embed = discord.Embed(
            title="📱 Canal de comunicación privado",
            description=f"**{datos1.get('nombre','?')}** ↔️ **{datos2.get('nombre','?')}**\n"
                         f"Solo ustedes pueden ver este canal.\n"
                         f"Usa `/mensaje <texto>` o escribe directamente aquí.\n"
                         f"Usa `/cerrar_chat` para eliminar este canal.",
            color=discord.Color.blurple()
        )
        await canal.send(embed=embed)
        return canal

    @commands.command(name="llamar")
    async def llamar(self, ctx, *, numero: str):
        """Llama por teléfono. Acepta @mención, un número de teléfono marcado
        a mano (el tuyo propio incluido), o 911/112/0800 para emergencias.
        Uso: !llamar 0412-1234567  |  !llamar @alguien  |  !llamar 911"""
        datos_self = await db.get("personajes", str(ctx.author.id))
        if not datos_self:
            return await ctx.send("❌ No tienes personaje.")

        inv_self = datos_self.get("inventario", [])
        if not any("telefono" in i or "smartphone" in i for i in inv_self):
            return await ctx.send("❌ No tienes teléfono. Compra uno en la tienda.")

        modo, valor = await _resolver_destino_llamada(ctx, numero)

        if modo == "error":
            return await ctx.send(valor)

        if modo == "emergencia":
            return await self._llamada_emergencia(ctx, datos_self, numero.strip())

        objetivo = valor  # discord.Member (puede ser el propio ctx.author)

        if objetivo.id == ctx.author.id:
            # Llamarse a uno mismo: no tiene sentido crear un chat de 2 con la
            # misma persona, pero SÍ debe estar permitido (el jugador lo pidió
            # explícitamente) — se resuelve como un momento de rol suelto.
            await asyncio.sleep(1)
            return await ctx.send(embed=discord.Embed(
                description=f"📱 **{datos_self['nombre']}** se marca a sí mismo... suena el propio teléfono en su bolsillo. "
                            f"*(Te llamaste a ti mismo — nadie más contesta del otro lado.)*",
                color=discord.Color.blurple()
            ))

        datos_obj = await db.get("personajes", str(objetivo.id))
        if not datos_obj:
            return await ctx.send(f"❌ {objetivo.display_name} no tiene personaje.")

        inv_obj = datos_obj.get("inventario", [])
        tiene_tel_obj = any("telefono" in i or "smartphone" in i for i in inv_obj)
        if not tiene_tel_obj:
            return await ctx.send(f"❌ {datos_obj['nombre']} no tiene teléfono.")

        # Crear/obtener canal privado
        canal = await self._obtener_o_crear_canal(
            ctx.guild, ctx.author.id, objetivo.id, datos_self, datos_obj
        )

        # Notificar al receptor
        embed = discord.Embed(
            title="📞 Llamada entrante",
            description=f"**{datos_self['nombre']}** te está llamando.\n"
                         f"📱 {datos_self.get('telefono','???')}",
            color=discord.Color.green()
        )
        view = LlamadaView(ctx.author.id, objetivo.id, canal.id, datos_self, datos_obj)

        try:
            await objetivo.send(embed=embed, view=view)
        except:
            # Si no puede DM, pinga en el canal privado
            await canal.send(f"{objetivo.mention}", embed=embed, view=view)

        # Indicar en el canal de llamada
        await canal.send(f"📞 *{datos_self['nombre']} está llamando a {datos_obj['nombre']}...*")
        await ctx.send(f"📞 Llamando a **{datos_obj['nombre']}**... Canal: {canal.mention}", delete_after=10)

    async def _llamada_emergencia(self, ctx, datos_self: dict, numero_marcado: str):
        """911/112/0800: despacha automáticamente a la CPNB/bomberos/médicos
        con la ubicación real del personaje que llama."""
        from bot import CH_POLICIA_AVISO, ROL_POLICIA
        ROL_BOMBERO_ID = 1359320808509538345
        ROL_MEDICO_ID = 1359320808585035789

        sector = datos_self.get("ubicacion", "?")
        canal_actual = datos_self.get("canal_actual", "?")
        nombre = datos_self.get("nombre", ctx.author.display_name)

        embed_confirm = discord.Embed(
            title="🚨 Llamada de emergencia realizada",
            description=(
                f"Marcaste **{numero_marcado}**. Un operador toma tu reporte:\n"
                f"> *\"Emergencias, ¿cuál es tu ubicación?\"*\n\n"
                f"📍 Reportaste estar en **{canal_actual}** ({sector}).\n"
                f"Unidades han sido notificadas."
            ),
            color=discord.Color.red()
        )
        await ctx.send(embed=embed_confirm)

        ch = ctx.guild.get_channel(CH_POLICIA_AVISO)
        if not ch:
            return
        rol_pol = ctx.guild.get_role(ROL_POLICIA)
        rol_bombero = ctx.guild.get_role(ROL_BOMBERO_ID)
        rol_medico = ctx.guild.get_role(ROL_MEDICO_ID)
        pings = " ".join(r.mention for r in (rol_pol, rol_bombero, rol_medico) if r) or "@Emergencias"
        try:
            await ch.send(
                f"🚨 {pings} **LLAMADA A {numero_marcado} — EMERGENCIA REPORTADA**\n"
                f"**Quién llama:** {nombre} ({ctx.author.mention})\n"
                f"**Ubicación reportada:** `{canal_actual}` ({sector})"
            )
        except Exception:
            pass

    @commands.command(name="sms", aliases=["mensaje"])
    async def sms(self, ctx, objetivo: discord.Member, *, mensaje: str):
        """Envía un SMS a otro personaje."""
        datos_self = await db.get("personajes", str(ctx.author.id))
        datos_obj = await db.get("personajes", str(objetivo.id))

        if not datos_self:
            return await ctx.send("❌ No tienes personaje.")
        if not datos_obj:
            return await ctx.send(f"❌ {objetivo.display_name} no tiene personaje.")

        inv_self = datos_self.get("inventario", [])
        if not any("telefono" in i or "smartphone" in i for i in inv_self):
            return await ctx.send("❌ No tienes teléfono.")

        canal = await self._obtener_o_crear_canal(
            ctx.guild, ctx.author.id, objetivo.id, datos_self, datos_obj
        )

        embed = discord.Embed(
            description=mensaje,
            color=discord.Color.blurple()
        )
        tel = await asegurar_numero(ctx.author.id, datos_self)
        embed.set_author(name=f"💬 SMS de {datos_self['nombre']} ({tel})")
        embed.set_footer(text="Responde en este canal.")

        await canal.send(f"{objetivo.mention}", embed=embed)
        await ctx.send(f"✉️ SMS enviado a **{datos_obj['nombre']}**. Canal: {canal.mention}", delete_after=8)

        # Eliminar mensaje original del canal público
        try:
            await ctx.message.delete()
        except:
            pass

    @commands.command(name="colgar")
    async def colgar(self, ctx):
        """Cuelga la llamada activa."""
        if ctx.author.id not in llamadas_activas:
            return await ctx.send("❌ No tienes llamada activa.", delete_after=5)

        otro_id = llamadas_activas.pop(ctx.author.id)
        llamadas_activas.pop(otro_id, None)

        datos = await db.get("personajes", str(ctx.author.id))
        nombre = datos.get("nombre","?") if datos else ctx.author.display_name
        await ctx.send(f"📵 **{nombre}** colgó la llamada.")

    @commands.command(name="cerrar_chat")
    async def cerrar_chat(self, ctx, objetivo: discord.Member = None):
        """Cierra/elimina el canal de comunicación privado."""
        if objetivo:
            key = frozenset([ctx.author.id, objetivo.id])
        else:
            # Buscar si el canal actual es un chat privado
            key = None
            for k, cid in conversaciones_activas.items():
                if cid == ctx.channel.id and ctx.author.id in k:
                    key = k
                    break

        if not key or key not in conversaciones_activas:
            return await ctx.send("❌ No se encontró canal activo.", delete_after=5)

        canal_id = conversaciones_activas.pop(key)
        canal = ctx.guild.get_channel(canal_id)
        if canal:
            await canal.send("🔴 *Chat cerrado. Este canal se eliminará en 5 segundos.*")
            await asyncio.sleep(5)
            await canal.delete(reason="Chat telefónico cerrado")
        await ctx.send("✅ Canal cerrado.", delete_after=5)

    @commands.command(name="mi_numero")
    async def mi_numero(self, ctx):
        """Muestra tu número de teléfono."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        inv = datos.get("inventario", {})
        if not any("telefono" in i or "smartphone" in i for i in inv):
            return await ctx.send("❌ No tienes ningún teléfono. Cómprate uno en la tienda (`telefono_basico` o `smartphone`).")

        tel = await asegurar_numero(ctx.author.id, datos)
        await ctx.send(
            f"📱 Tu número: **{tel}**\n"
            f"Comparte este número para que te llamen con `!llamar` o te escriban con `!sms`.",
            delete_after=30
        )


async def asegurar_numero(user_id, datos: dict = None) -> str:
    """Devuelve el número del personaje, generando uno único si aún no tiene.

    ANTES: cogs/personajes.py guardaba "telefono": None al crear el personaje y
    NADA lo rellenaba nunca — ni siquiera comprar un teléfono en la tienda — así
    que !mi_numero mostraba siempre "None" y era imposible que te llamaran.
    """
    if datos is None:
        datos = await db.get("personajes", str(user_id)) or {}
    tel = datos.get("telefono")
    if tel:
        return tel

    existentes = {p.get("telefono") for p in (await db.all("personajes")).values() if p.get("telefono")}
    for _ in range(200):
        nuevo = f"0{random.choice(['412','414','416','424','426'])}-{random.randint(1000000, 9999999)}"
        if nuevo not in existentes:
            await db.update("personajes", str(user_id), {"telefono": nuevo})
            return nuevo
    return "0000-0000000"

async def setup(bot):
    await bot.add_cog(Telefono(bot))