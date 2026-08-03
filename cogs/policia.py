"""
cogs/policia.py — Sistema policial: arrestos, multas, más buscados, prisión.
La policía venezolana (CPNB) solo actúa en Venezuela.
En Colombia y Miami tiene su propia fuerza local (sin ping a Venezuela).
"""
import discord
from discord.ext import commands, tasks
import asyncio
import random
from utils import db
from utils.mapa import SECTORES
from bot import CH_MAS_BUSCADOS, CH_POLICIA_AVISO, ROL_POLICIA

# Objetos que un control policial aleatorio puede encontrar encima del personaje.
ARMAS_ILEGALES_SIN_PERMISO = {
    "glock_17", "beretta_92", "colt_m1911", "desert_eagle", "sw_model_29",
    "mp5", "uzi", "ak47", "m4_carbine", "remington_870", "navaja",
    "cuchillo_militar", "punio_americano", "daga",
}
DROGAS_KEYS = {"marihuana", "cocaina", "crack", "heroina", "pastillas"}

# Sectores donde opera la policía venezolana
SECTORES_VENEZUELA = {
    "petare", "las-mercedes", "distrito-capital", "23-de-enero",
    "ciudad-universitaria", "miranda", "la-alameda", "la-trinidad",
    "maracaibo", "valencia", "prision-yare"
}

# Sectores internacionales y su "policía local" (solo RP narrativo)
POLICIA_LOCAL_INTERNACIONAL = {
    "medellin": "🇨🇴 Policía Nacional de Colombia",
    "bogota":   "🇨🇴 Policía Nacional de Colombia",
    "miami":    "🇺🇸 Miami-Dade Police Department",
}


def _es_sector_venezolano(sector: str) -> bool:
    return sector in SECTORES_VENEZUELA


async def _notificar_policia_venezolana(guild, canal, mensaje: str, sector: str = ""):
    """Solo notifica a la CPNB si el evento ocurre en Venezuela."""
    if sector and not _es_sector_venezolano(sector):
        return  # No concierne a Venezuela

    ch_pol = guild.get_channel(CH_POLICIA_AVISO)
    if ch_pol:
        rol_pol = guild.get_role(ROL_POLICIA)
        ping = rol_pol.mention if rol_pol else "@CPNB"
        await ch_pol.send(f"🚨 {ping} **INCIDENTE:** {mensaje}\n📍 {canal.mention if canal else '?'}")


async def _notificar_policia_local(canal: discord.TextChannel, sector: str, descripcion: str):
    """Genera un mensaje narrativo de policía local en sectores internacionales."""
    policia_nombre = POLICIA_LOCAL_INTERNACIONAL.get(sector)
    if not policia_nombre:
        return

    embed = discord.Embed(
        title=f"🚔 {policia_nombre} — Respuesta en la zona",
        description=descripcion,
        color=0x1a3a6e
    )
    embed.set_footer(text=f"Policía local — esto no concierne a la CPNB venezolana")
    if canal:
        await canal.send(embed=embed)


class ConfirmarArrestoView(discord.ui.View):
    def __init__(self, objetivo_id: int, razon: str, admin_id: int, sector: str = ""):
        super().__init__(timeout=300)
        self.objetivo_id = objetivo_id
        self.razon = razon
        self.admin_id = admin_id
        self.sector = sector

    @discord.ui.button(label="✅ Confirmar Arresto", style=discord.ButtonStyle.red)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("Solo admins.", ephemeral=True)

        member = interaction.guild.get_member(self.objetivo_id)
        datos = await db.get("personajes", str(self.objetivo_id))

        if not datos:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)

        await db.update("personajes", str(self.objetivo_id), {
            "arrestado": True,
            "ubicacion": "prision-yare",
            "canal_actual": "celda-yare",
            "en_viaje": False,
        })

        arrestos = await db.get("arrestos", str(self.objetivo_id)) or []
        arrestos.append({"razon": self.razon, "admin": interaction.user.id, "sector": self.sector})
        await db.set("arrestos", str(self.objetivo_id), arrestos)

        embed = discord.Embed(
            title="🚔 ARRESTADO",
            description=f"**{datos.get('nombre', '?')}** ha sido arrestado.",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="Razón", value=self.razon, inline=False)
        embed.add_field(name="Destino", value="⛓️ Prisión de Yare", inline=True)
        embed.add_field(name="Admin", value=interaction.user.mention, inline=True)

        await interaction.response.send_message(embed=embed)
        await interaction.message.edit(view=None)

        if member:
            try:
                await member.send(
                    f"🚔 Tu personaje **{datos['nombre']}** ha sido arrestado.\n"
                    f"Razón: {self.razon}\nUsa `/libertad` cuando un admin te libere."
                )
            except:
                pass
        self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Arresto cancelado.", ephemeral=True)
        await interaction.message.edit(view=None)
        self.stop()


class Policia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def start_tasks(self):
        if not self.controles_random.is_running():
            self.controles_random.start()

    @tasks.loop(hours=4)
    async def controles_random(self):
        """Controles policiales aleatorios: la CPNB puede detenerte al azar,
        sobre todo si llevas encima drogas o un arma sin permiso. Solo aplica
        en sectores donde opera la policía venezolana."""
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return

        personajes = await db.all("personajes")
        for uid, datos in personajes.items():
            if datos.get("muerto") or datos.get("arrestado") or datos.get("en_viaje") or datos.get("deportado"):
                continue
            sector = datos.get("ubicacion", "")
            if not _es_sector_venezolano(sector):
                continue

            inv = datos.get("inventario", {})
            lleva_drogas = any(k in inv for k in DROGAS_KEYS)
            armas_sin_permiso = [k for k in inv if k in ARMAS_ILEGALES_SIN_PERMISO]
            tiene_permiso = "permiso_porte_armas" in inv
            lleva_arma_ilegal = bool(armas_sin_permiso) and not tiene_permiso
            es_ilegal_migratorio = bool(datos.get("inmigrante_ilegal"))

            prob_control = (0.015 + (0.10 if lleva_drogas else 0) + (0.10 if lleva_arma_ilegal else 0)
                            + (0.06 if es_ilegal_migratorio else 0))
            if random.random() >= prob_control:
                continue

            member = guild.get_member(int(uid))
            if not member:
                continue

            if es_ilegal_migratorio and random.random() < 0.5 and not (lleva_drogas or lleva_arma_ilegal):
                # Verificación migratoria: puede terminar en deportación directa.
                pais = datos.get("pais_origen", "su país de origen")
                await db.update("personajes", uid, {
                    "deportado": True, "ubicacion": "deportado", "canal_actual": None,
                })
                ch_pol = guild.get_channel(CH_POLICIA_AVISO)
                if ch_pol:
                    try:
                        await ch_pol.send(embed=discord.Embed(
                            title="✈️ DEPORTACIÓN AUTOMÁTICA (control migratorio aleatorio)",
                            description=f"**{datos.get('nombre','?')}** fue deportado/a a **{pais}** tras un control en **{sector}**.",
                            color=discord.Color.dark_red()
                        ))
                    except Exception:
                        pass
                try:
                    await member.send(
                        f"🛂 Un control migratorio te detectó sin papeles en regla en **{sector}** "
                        f"y fuiste deportado a **{pais}**. Un admin puede permitirte volver con `!permitir_reingreso`."
                    )
                except Exception:
                    pass
                continue

            if not (lleva_drogas or lleva_arma_ilegal):
                # Control de rutina sin hallazgos: solo ambientación, sin consecuencia.
                canal = discord.utils.get(guild.text_channels, name=datos.get("canal_actual", ""))
                if canal:
                    try:
                        await canal.send(embed=discord.Embed(
                            description=f"🚔 La CPNB detiene un momento a **{datos.get('nombre','?')}** para "
                                        f"revisar documentos... todo en orden, puede seguir.",
                            color=discord.Color.blurple()
                        ))
                    except Exception:
                        pass
                continue

            # Hallazgo ilegal: detención automática.
            razon_partes = []
            if lleva_drogas:
                razon_partes.append("posesión de drogas")
            if lleva_arma_ilegal:
                razon_partes.append("porte ilegal de arma de fuego sin permiso")
            razon = "Control policial aleatorio: " + " y ".join(razon_partes) + "."

            await db.update("personajes", uid, {
                "arrestado": True,
                "ubicacion": "prision-yare",
                "canal_actual": "celda-yare",
                "en_viaje": False,
            })
            arrestos = await db.get("arrestos", uid) or []
            arrestos.append({"razon": razon, "admin": "sistema", "sector": sector})
            await db.set("arrestos", uid, arrestos)

            ch_pol = guild.get_channel(CH_POLICIA_AVISO)
            if ch_pol:
                try:
                    await ch_pol.send(embed=discord.Embed(
                        title="🚔 DETENCIÓN AUTOMÁTICA (control aleatorio)",
                        description=f"**{datos.get('nombre','?')}** fue detenido/a en **{sector}**.\n{razon}",
                        color=discord.Color.dark_red()
                    ))
                except Exception:
                    pass
            try:
                await member.send(
                    f"🚔 Un control policial aleatorio te detuvo en **{sector}**.\n"
                    f"Razón: {razon}\nUsa `!hablar_abogado` para pedir asistencia legal."
                )
            except Exception:
                pass
            try:
                from cogs.noticias_ia import registrar_evento
                await registrar_evento("detencion", f"Detención policial en {sector}: {razon}.")
            except Exception:
                pass

    @commands.command(name="arrestar")
    async def arrestar(self, ctx, objetivo: discord.Member, *, razon: str = "Sin razón especificada"):
        """Inicia proceso de arresto."""
        datos_pol = await db.get("personajes", str(ctx.author.id))
        datos_obj = await db.get("personajes", str(objetivo.id))

        if not datos_obj:
            return await ctx.send("❌ Ese usuario no tiene personaje.")

        sector_objetivo = datos_obj.get("ubicacion", "")

        # Si está en sector internacional, la policía local maneja el asunto
        if sector_objetivo in POLICIA_LOCAL_INTERNACIONAL:
            canal_actual = datos_obj.get("canal_actual", "")
            canal = discord.utils.get(ctx.guild.text_channels, name=canal_actual)
            await _notificar_policia_local(
                canal, sector_objetivo,
                f"**{datos_obj.get('nombre', '?')}** fue detenido/a. Razón: {razon}"
            )
            await ctx.send(
                f"📋 **{datos_obj.get('nombre', '?')}** está en **{sector_objetivo}** (internacional).\n"
                f"La {POLICIA_LOCAL_INTERNACIONAL[sector_objetivo]} ha sido notificada.\n"
                f"La CPNB venezolana no tiene jurisdicción aquí.",
                delete_after=15
            )
            # Aun así se procesa el arresto para el RP
            view = ConfirmarArrestoView(objetivo.id, razon, ctx.author.id, sector_objetivo)
            await ctx.send(embed=discord.Embed(
                title="🚔 Solicitud de Arresto (Internacional)",
                description=f"**Objetivo:** {objetivo.mention} ({datos_obj.get('nombre', '?')})\n"
                            f"**Razón:** {razon}\n"
                            f"**Sector:** {sector_objetivo} (policía local actúa)",
                color=discord.Color.blue()
            ), view=view)
            return

        # Venezuela — proceso normal
        ch_pol = ctx.guild.get_channel(CH_POLICIA_AVISO)
        rol_pol = ctx.guild.get_role(ROL_POLICIA)

        embed = discord.Embed(
            title="🚨 Solicitud de Arresto",
            description=f"**Solicitado por:** {ctx.author.mention} ({datos_pol['nombre'] if datos_pol else ctx.author.display_name})\n"
                        f"**Objetivo:** {objetivo.mention} ({datos_obj.get('nombre', '?')})\n"
                        f"**Razón:** {razon}\n"
                        f"**Canal:** {ctx.channel.mention}",
            color=discord.Color.red()
        )
        view = ConfirmarArrestoView(objetivo.id, razon, ctx.author.id, sector_objetivo)
        ping = rol_pol.mention if rol_pol else "@Admins"

        if ch_pol:
            await ch_pol.send(f"🚨 {ping}", embed=embed, view=view)
            await ctx.send("📨 Solicitud de arresto enviada. Un admin debe confirmar.", delete_after=10)
        else:
            await ctx.send(embed=embed, view=view)

    @commands.command(name="liberar")
    async def liberar(self, ctx, objetivo: discord.Member, *, razon: str = "Cumplió condena"):
        """Libera a un personaje de prisión. (Solo admins)"""
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo admins.")

        datos = await db.get("personajes", str(objetivo.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        if not datos.get("arrestado", False):
            return await ctx.send("❌ Ese personaje no está arrestado.")

        barrio_origen = datos.get("barrio", "distrito-capital")
        await db.update("personajes", str(objetivo.id), {
            "arrestado": False,
            "ubicacion": barrio_origen,
            "canal_actual": None,
        })

        await ctx.send(f"✅ **{datos['nombre']}** ha sido liberado. Razón: {razon}")
        try:
            await objetivo.send(f"🔓 Tu personaje **{datos['nombre']}** ha sido liberado. Razón: {razon}")
        except:
            pass

    @commands.command(name="masbuscado")
    async def mas_buscado(self, ctx, objetivo: discord.Member, recompensa: float, *, descripcion: str):
        """Añade un personaje a la lista de más buscados. (Admins)"""
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo admins.")

        datos = await db.get("personajes", str(objetivo.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        # Si está en internacional, la lista de buscados igual aplica
        sector = datos.get("ubicacion", "")
        if sector in POLICIA_LOCAL_INTERNACIONAL:
            await ctx.send(f"⚠️ Nota: **{datos['nombre']}** está actualmente en {sector} (internacional). "
                           f"Se añade a la lista venezolana pero la captura debe coordinarse con autoridades locales.")

        await db.update("personajes", str(objetivo.id), {"mas_buscado": True, "recompensa": recompensa})

        ch = ctx.guild.get_channel(CH_MAS_BUSCADOS)
        if ch:
            embed = discord.Embed(
                title=f"🔴 MÁS BUSCADO: {datos['nombre']}",
                description=descripcion,
                color=discord.Color.dark_red()
            )
            embed.add_field(name="💰 Recompensa", value=f"${recompensa:.2f}", inline=True)
            embed.add_field(name="Último avistamiento", value=datos.get("ubicacion", "?"), inline=True)
            embed.set_footer(text=f"UserID: {objetivo.id}")
            await ch.send(embed=embed)
            await ctx.send(f"✅ {datos['nombre']} añadido a lista de más buscados.")
        else:
            await ctx.send("✅ Actualizado (canal de más buscados no configurado).")

    @commands.command(name="multar")
    async def multar(self, ctx, objetivo: discord.Member, monto: float, *, razon: str = "Infracción"):
        """Multa a un personaje. (Admins/Policía)"""
        if not ctx.author.guild_permissions.manage_roles:
            return await ctx.send("❌ No tienes permisos.")

        datos = await db.get("personajes", str(objetivo.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        sector = datos.get("ubicacion", "")
        if sector in POLICIA_LOCAL_INTERNACIONAL:
            await ctx.send(
                f"⚠️ **{datos['nombre']}** está en {sector}. En su territorio aplica la ley local.\n"
                f"Para multas internacionales, coordina con las autoridades del país. Se registra de todas formas."
            )

        dinero = datos.get("dinero", 0)
        if dinero < monto:
            await db.update("personajes", str(objetivo.id), {"deudas": datos.get("deudas", 0) + monto})
            await ctx.send(f"⚠️ {datos['nombre']} no tiene fondos. La multa (${monto:.2f}) se añade a su deuda.")
        else:
            await db.update("personajes", str(objetivo.id), {"dinero": round(dinero - monto, 2)})
            await ctx.send(f"💸 {datos['nombre']} multado por ${monto:.2f}. Razón: {razon}")

        try:
            await objetivo.send(f"🚔 Fuiste multado **${monto:.2f}**. Razón: {razon}")
        except:
            pass

    @commands.command(name="registros")
    async def registros(self, ctx, objetivo: discord.Member = None):
        """Muestra el historial de arrestos de un personaje."""
        target = objetivo or ctx.author
        datos = await db.get("personajes", str(target.id))
        arrestos = await db.get("arrestos", str(target.id)) or []

        embed = discord.Embed(
            title=f"📋 Registros: {datos['nombre'] if datos else target.display_name}",
            color=discord.Color.dark_grey()
        )
        if not arrestos:
            embed.description = "Sin antecedentes."
        else:
            for i, a in enumerate(arrestos[-5:], 1):
                sector_txt = f" (en {a['sector']})" if a.get("sector") else ""
                embed.add_field(name=f"Arresto #{i}", value=a.get("razon", "?") + sector_txt, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="presos")
    async def presos(self, ctx):
        """Lista de personajes actualmente en prisión."""
        if not ctx.author.guild_permissions.manage_roles:
            return await ctx.send("❌ Solo policía o admins.")
        personajes = await db.all("personajes")
        arrestados = [(uid, d) for uid, d in personajes.items() if d.get("arrestado")]

        if not arrestados:
            return await ctx.send("✅ No hay nadie en prisión actualmente.")

        embed = discord.Embed(title="⛓️ Presos Actuales", color=discord.Color.dark_grey())
        for uid, d in arrestados[:15]:
            embed.add_field(name=d.get("nombre", "?"), value=f"📍 {d.get('ubicacion', '?')}", inline=True)
        await ctx.send(embed=embed)

    # ── !deportar / !permitir_reingreso ─────────────────────────────────────────
    @commands.command(name="deportar")
    async def deportar(self, ctx, objetivo: discord.Member, *, razon: str = "Estatus migratorio irregular"):
        """[ADMIN] Deporta a un personaje de vuelta a su país de origen."""
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo admins.")
        datos = await db.get("personajes", str(objetivo.id))
        if not datos:
            return await ctx.send("❌ Ese usuario no tiene personaje.")

        pais = datos.get("pais_origen", "su país de origen")
        await db.update("personajes", str(objetivo.id), {
            "deportado": True,
            "arrestado": False,
            "en_viaje": False,
            "ubicacion": "deportado",
            "canal_actual": None,
        })
        await ctx.send(embed=discord.Embed(
            title="✈️ DEPORTACIÓN",
            description=f"**{datos.get('nombre','?')}** fue deportado/a de vuelta a **{pais}**.\nRazón: {razon}",
            color=discord.Color.dark_red()
        ))
        try:
            await objetivo.send(
                f"✈️ Tu personaje **{datos.get('nombre','?')}** fue deportado a **{pais}**.\n"
                f"Razón: {razon}\nUn admin puede permitirte volver a entrar con `!permitir_reingreso`."
            )
        except Exception:
            pass
        try:
            from cogs.noticias_ia import registrar_evento
            await registrar_evento("deportacion", f"{datos.get('nombre','?')} fue deportado a {pais}. Razón: {razon}.")
        except Exception:
            pass

    @commands.command(name="permitir_reingreso")
    async def permitir_reingreso(self, ctx, objetivo: discord.Member):
        """[ADMIN] Permite que un personaje deportado vuelva a entrar al país."""
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo admins.")
        datos = await db.get("personajes", str(objetivo.id))
        if not datos or not datos.get("deportado"):
            return await ctx.send("❌ Ese personaje no está deportado.")
        barrio_origen = datos.get("barrio", "distrito-capital")
        await db.update("personajes", str(objetivo.id), {"deportado": False, "ubicacion": barrio_origen})
        await ctx.send(f"✅ **{datos.get('nombre','?')}** puede volver a entrar al país.")

    @commands.command(name="entorno")
    async def entorno(self, ctx, *, descripcion: str):
        """Describe el entorno (avisa a la policía venezolana si hay peligro EN Venezuela)."""
        embed = discord.Embed(
            description=f"*{descripcion}*",
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"[Entorno] {ctx.channel.name}")
        await ctx.send(embed=embed)

        palabras_peligro = ["disparo", "tiroteo", "muerto", "sangre", "robo", "pelea", "explosión", "bomba", "secuestro"]
        if any(p in descripcion.lower() for p in palabras_peligro):
            # Verificar sector del autor
            datos = await db.get("personajes", str(ctx.author.id))
            sector = datos.get("ubicacion", "") if datos else ""

            if _es_sector_venezolano(sector):
                # Alerta CPNB venezolana
                ch_pol = ctx.guild.get_channel(CH_POLICIA_AVISO)
                rol_pol = ctx.guild.get_role(ROL_POLICIA)
                if ch_pol:
                    ping = rol_pol.mention if rol_pol else "@Admins"
                    await ch_pol.send(
                        f"🚨 {ping} Situación reportada en {ctx.channel.mention} ({sector}):\n> {descripcion}"
                    )
            elif sector in POLICIA_LOCAL_INTERNACIONAL:
                # Policía local del país extranjero
                await _notificar_policia_local(
                    ctx.channel, sector,
                    f"Incidente reportado: {descripcion[:200]}"
                )


async def setup(bot):
    await bot.add_cog(Policia(bot))