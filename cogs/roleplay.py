"""
cogs/roleplay.py — Comandos narrativos de RP: /me, /do, /entorno, /narrar.
"""
import discord
from discord.ext import commands
from discord import app_commands
from utils import db


class Roleplay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="me")
    async def me_action(self, ctx, *, accion: str):
        """Describe una acción de tu personaje."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje. Usa `/crear_personaje`.")
        if not datos.get("vivo", True):
            return await ctx.send("❌ Tu personaje está muerto.")
        nombre = datos.get("nombre", ctx.author.display_name)
        try:
            await ctx.message.delete()
        except:
            pass
        embed = discord.Embed(
            description=f"*{nombre} {accion}*",
            color=discord.Color.from_rgb(138, 138, 138)
        )
        embed.set_author(name=nombre, icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="do")
    async def do_action(self, ctx, *, descripcion: str):
        """Describe algo que ocurre en el entorno."""
        datos = await db.get("personajes", str(ctx.author.id))
        nombre = datos.get("nombre", ctx.author.display_name) if datos else ctx.author.display_name
        try:
            await ctx.message.delete()
        except:
            pass
        embed = discord.Embed(
            description=f"*{descripcion}*",
            color=discord.Color.from_rgb(80, 80, 120)
        )
        embed.set_footer(text=f"[DO por {nombre}]")
        await ctx.send(embed=embed)

    @commands.command(name="narrar")
    async def narrar(self, ctx, *, texto: str):
        """Narración de admin/GM."""
        if not ctx.author.guild_permissions.manage_messages:
            return await ctx.send("❌ Solo narradores y admins.", delete_after=5)
        try:
            await ctx.message.delete()
        except:
            pass
        embed = discord.Embed(
            description=f"📖 *{texto}*",
            color=discord.Color.from_rgb(255, 200, 50)
        )
        embed.set_footer(text="— Narrador")
        await ctx.send(embed=embed)

    @commands.command(name="susurrar")
    async def susurrar(self, ctx, objetivo: discord.Member, *, mensaje: str):
        """Susurra a alguien."""
        datos_self = await db.get("personajes", str(ctx.author.id))
        datos_obj = await db.get("personajes", str(objetivo.id))
        if not datos_self:
            return await ctx.send("❌ Sin personaje.")
        nombre_self = datos_self.get("nombre", "?")
        nombre_obj = datos_obj.get("nombre", objetivo.display_name) if datos_obj else objetivo.display_name
        try:
            await ctx.message.delete()
        except:
            pass
        embed = discord.Embed(
            description=f"*{nombre_self} susurra a {nombre_obj}: \"{mensaje}\"*",
            color=discord.Color.from_rgb(60, 60, 60)
        )
        embed.set_footer(text="[susurro]")
        await ctx.send(embed=embed)

    @commands.command(name="grito")
    async def gritar(self, ctx, *, mensaje: str):
        """Tu personaje grita algo."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        nombre = datos.get("nombre", "?")
        try:
            await ctx.message.delete()
        except:
            pass
        embed = discord.Embed(
            description=f"# 📢 {nombre.upper()} GRITA: **\"{mensaje.upper()}\"**",
            color=discord.Color.from_rgb(255, 50, 50)
        )
        embed.set_footer(text="[GRITO — audible en canales cercanos]")
        await ctx.send(embed=embed)

    @commands.command(name="pensar")
    async def pensar(self, ctx, *, pensamiento: str):
        """Pensamiento interno del personaje."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        nombre = datos.get("nombre", "?")
        try:
            await ctx.message.delete()
        except:
            pass
        embed = discord.Embed(
            description=f"💭 *{nombre} piensa: '{pensamiento}'*",
            color=discord.Color.from_rgb(100, 100, 200)
        )
        await ctx.send(embed=embed)

    @commands.command(name="estado")
    async def estado_personaje(self, ctx, *, estado: str):
        """Muestra el estado físico/emocional del personaje."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        nombre = datos.get("nombre", "?")
        hp = datos.get("stats", {}).get("hp", 100)
        hp_max = datos.get("stats", {}).get("hp_max", 100)
        await db.update("personajes", str(ctx.author.id), {"estado_rp": estado})
        embed = discord.Embed(
            description=f"**{nombre}** — {estado}",
            color=discord.Color.blurple()
        )
        barra = "█" * int((hp / hp_max) * 10) + "░" * (10 - int((hp / hp_max) * 10))
        embed.set_footer(text=f"HP: {barra} {hp}/{hp_max}")
        await ctx.send(embed=embed)

    @commands.command(name="oc")
    async def out_of_character(self, ctx, *, mensaje: str):
        """Mensaje fuera de personaje (OOC)."""
        try:
            await ctx.message.delete()
        except:
            pass
        await ctx.send(f"💬 **[OOC] {ctx.author.display_name}:** {mensaje}")

    # ── /ayuda_rp ─────────────────────────────────────────────────────────────
    @app_commands.command(name="ayuda_rp", description="Muestra todos los comandos de roleplay disponibles")
    async def ayuda_rp_slash(self, interaction: discord.Interaction):
        embed = self._build_ayuda_embed()
        await interaction.response.send_message(embed=embed)

    @commands.command(name="ayuda_rp", aliases=["comandos_rp", "ayuda", "help_rp"])
    async def ayuda_rp_prefix(self, ctx):
        embed = self._build_ayuda_embed()
        await ctx.send(embed=embed)

    def _build_ayuda_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="📖 Comandos de Roleplay — Venezuela RP",
            description="Guía rápida. Usa `/` para slash commands o `!` para prefix.",
            color=discord.Color.gold()
        )
        campos = [
            ("🎭 Acciones RP",
             "`!me <acción>` — tu personaje hace algo\n"
             "`!do <desc>` — describe el entorno\n"
             "`!susurrar @user <msg>` — susurro\n"
             "`!grito <msg>` — gritar en voz alta\n"
             "`!pensar <texto>` — pensamiento interno\n"
             "`!oc <msg>` — fuera de personaje"),

            ("📍 Moverse",
             "`/viajar <método> <destino>`\n"
             "Métodos: caminar, metro, autobus, tren, coche, bicicleta, avion\n"
             "`/ubicacion` — ver dónde estás\n"
             "`/rutas <origen> <destino>` — ver tiempos"),

            ("👤 Personaje",
             "`/perfil` — ver tu ficha\n"
             "`/stats` — estadísticas\n"
             "`/inventario` — ver objetos\n"
             "`/familia` — ver familia\n"
             "`/cambiar_imagen <url>` — cambiar foto"),

            ("💰 Economía",
             "`/tienda [categoria]` — ver artículos del lugar actual\n"
             "`/comprar <item>` — comprar (debes estar en el sitio)\n"
             "`/vender <item>` — vender al 50%\n"
             "`/usar <item>` — usar objeto\n"
             "`/craftear <item>` — fabricar con materiales\n"
             "`/recetas` — ver objetos fabricables\n"
             "`/transferir @user <$>` — enviar dinero\n"
             "`/precios` — precios del mercado"),

            ("🔫 Armas y Combate",
             "**Legales** (en ferreterías/tiendas):\n"
             "`cuchillo`, `bate_baseball`, `machete`, `hacha`...\n"
             "**Ilegales** (solo Mercado Negro de Petare):\n"
             "`!comprar_arma_negra <nombre>`\n"
             "**Crafteo:**\n"
             "`/craftear punial_improvisado` — cuerda+encendedor\n"
             "**Uso:** Las armas se usan automáticamente en combate."),

            ("⚔️ Combate",
             "`!pelear @usuario` — pelea cuerpo a cuerpo\n"
             "`!disparar @usuario` — tiroteo (necesitas arma de fuego)\n"
             "`!entrenar <stat>` — mejorar stats (en gym)\n"
             "`!curarse [item]` — curarte a ti mismo\n"
             "`!curar @usuario [item]` — curar a alguien\n"
             "`!items_curacion` — ver ítems de curación"),

            ("🏦 Banco",
             "`!depositar <monto>` — en banco\n"
             "`!retirar <monto>` — retirar efectivo\n"
             "`!saldo_banco` — ver saldo\n"
             "`!invertir <tipo> <monto>`\n"
             "`/prestamo <monto>` — pedir préstamo (en banco)\n"
             "`/pagar_deuda <monto>`"),

            ("🏠 Propiedades",
             "`!casas [sector]` — ver casas\n"
             "`!comprar_casa <sector> <n>`\n"
             "`!alquilar_casa <sector> <n>`\n"
             "`!mi_casa` — tus propiedades"),

            ("📱 Teléfono",
             "`!llamar @usuario` — llamar\n"
             "`!sms @usuario <msg>` — SMS\n"
             "`!colgar` — colgar llamada\n"
             "`!mi_numero` — ver tu número"),

            ("💼 Trabajo",
             "`/trabajos` — ver empleos\n"
             "`/solicitar_trabajo <nombre>`\n"
             "`/trabajar` — cobrar hora manual\n"
             "`/renunciar` — dejar trabajo"),

            ("🎓 Educación",
             "`/cursos` — ver cursos disponibles\n"
             "`/estudiar <curso>` — inscribirte (debes estar ahí)\n"
             "`/mi_estudio` — progreso de estudio\n"
             "`/cancelar_estudio` — abandonar curso\n"
             "`/certificados` — tus títulos\n"
             "`/examen <nivel>` — examen express (arriesgado)"),

            ("🌐 Tecnología",
             "`!contratar_internet <plan>`\n"
             "`!vpn [tipo]` — comprar VPN\n"
             "`!comprar_pc [tipo]`\n"
             "`!twitter <tweet>` — postear (requiere VPN)\n"
             "`!hackear @user <tipo>`"),

            ("🚔 Policía / Crimen",
             "`!arrestar @user <razon>`\n"
             "`!entorno <descripcion>`\n"
             "`!registros [@user]`\n"
             "`!robar_casa <sector> <n>`\n"
             "`/mercadonegro` — catálogo ilegal\n"
             "`!comprar_droga <tipo> <cant>`\n"
             "`!vender_droga <tipo> <cant>`\n"
             "`/nivel_busqueda` — ver nivel búsqueda"),
        ]
        for nombre, valor in campos:
            embed.add_field(name=nombre, value=valor, inline=True)
        embed.set_footer(text="Venezuela RP • /crear_personaje para empezar • /cursos para educación")
        return embed


async def setup(bot):
    await bot.add_cog(Roleplay(bot))