"""
cogs/telefono.py — Sistema de teléfono: canales privados de comunicación
entre personajes, "llamadas" simuladas, mensajes de texto.
"""
import discord
from discord.ext import commands
import asyncio
import random
from utils import db

# Formato del canal privado: 📱tel-{nombre1}-{nombre2}
# Guardamos activos: {frozenset(id1, id2): channel_id}
conversaciones_activas: dict[frozenset, int] = {}
llamadas_activas: dict[int, int] = {}  # caller_id: called_id

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
    async def llamar(self, ctx, objetivo: discord.Member):
        """Llama a otro personaje por teléfono."""
        datos_self = await db.get("personajes", str(ctx.author.id))
        datos_obj = await db.get("personajes", str(objetivo.id))

        if not datos_self:
            return await ctx.send("❌ No tienes personaje.")
        if not datos_obj:
            return await ctx.send(f"❌ {objetivo.display_name} no tiene personaje.")

        # Verificar que tengan teléfono
        inv_self = datos_self.get("inventario", [])
        inv_obj = datos_obj.get("inventario", [])
        tiene_tel_self = any("telefono" in i or "smartphone" in i for i in inv_self)
        tiene_tel_obj = any("telefono" in i or "smartphone" in i for i in inv_obj)

        if not tiene_tel_self:
            return await ctx.send("❌ No tienes teléfono. Compra uno en la tienda.")
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