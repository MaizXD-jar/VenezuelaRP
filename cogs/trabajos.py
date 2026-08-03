"""
cogs/trabajos.py — Sistema de trabajos: empleos, salarios, turnos.
FIXED: solicitar_trabajo requiere estar en la ubicación correcta.
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import asyncio
import time
from utils import db
from bot import CH_INFO_TRABAJOS, ROL_SALARIO

TRABAJOS = {
    "desempleado": {
        "display": "Desempleado",
        "salario_hora": 0,
        "nivel": "minimo",
        "min_edad": 0,
        "descripcion": "Sin empleo formal.",
        "canales_trabajo": ["cualquiera"],
        "canales_solicitud": ["cualquiera"],
        "turno": 0,
    },
    "vendedor_ambulante": {
        "display": "Vendedor Ambulante",
        "salario_hora": 1.5,
        "nivel": "minimo",
        "min_edad": 16,
        "descripcion": "Vende en la calle. Sin requisitos formales.",
        "canales_trabajo": ["calle", "mercado", "plaza", "bodega", "parada"],
        "canales_solicitud": ["calle", "mercado", "plaza", "bodega"],
        "turno": 8,
    },
    "obrero": {
        "display": "Obrero",
        "salario_hora": 2.5,
        "nivel": "bajo",
        "min_edad": 18,
        "descripcion": "Trabajo de construcción u obra.",
        "canales_trabajo": ["zona_industrial", "construccion", "obra", "taller"],
        "canales_solicitud": ["zona_industrial", "construccion", "taller"],
        "turno": 8,
    },
    "taxista": {
        "display": "Taxista",
        "salario_hora": 4.0,
        "nivel": "bajo",
        "min_edad": 18,
        "descripcion": "Transporta personas. Requiere coche.",
        "canales_trabajo": ["calle", "av", "autopista", "parada", "terminal"],
        "canales_solicitud": ["terminal", "parada"],
        "turno": 10,
        "requiere_vehiculo": "coche",
    },
    "mecanico": {
        "display": "Mecánico",
        "salario_hora": 5.0,
        "nivel": "medio_bajo",
        "min_edad": 18,
        "descripcion": "Repara vehículos en taller.",
        "canales_trabajo": ["taller", "mecanico", "garage", "ferreteria"],
        "canales_solicitud": ["taller", "mecanico", "garage"],
        "turno": 8,
    },
    "comerciante": {
        "display": "Comerciante",
        "salario_hora": 6.0,
        "nivel": "medio_bajo",
        "min_edad": 16,
        "descripcion": "Administra un pequeño negocio.",
        "canales_trabajo": ["tienda", "bodega", "comercio", "mercado", "supermercado", "automercado"],
        "canales_solicitud": ["tienda", "bodega", "comercio", "mercado"],
        "turno": 10,
    },
    "enfermero": {
        "display": "Enfermero/a",
        "salario_hora": 5.0,
        "nivel": "medio",
        "min_edad": 20,
        "descripcion": "Trabaja en hospital o clínica.",
        "canales_trabajo": ["hospital", "clinica", "emergencia", "ambulatorio"],
        "canales_solicitud": ["hospital", "clinica", "ambulatorio"],
        "turno": 12,
    },
    "policia_rp": {
        "display": "Policía CPNB",
        "salario_hora": 6.0,
        "nivel": "medio",
        "min_edad": 18,
        "descripcion": "Mantiene el orden. Solo asignado por admins.",
        "canales_trabajo": ["comisaria", "policia", "cpnb"],
        "canales_solicitud": ["comisaria", "policia"],
        "turno": 12,
        "requiere_admin": True,
    },
    "profesor": {
        "display": "Profesor/a",
        "salario_hora": 4.0,
        "nivel": "medio_bajo",
        "min_edad": 22,
        "descripcion": "Enseña en escuela o universidad.",
        "canales_trabajo": ["escuela", "colegio", "ucv", "universidad", "liceo", "biblioteca"],
        "canales_solicitud": ["escuela", "colegio", "ucv", "universidad", "liceo"],
        "turno": 8,
    },
    "periodista": {
        "display": "Periodista",
        "salario_hora": 7.0,
        "nivel": "medio",
        "min_edad": 20,
        "descripcion": "Reporta noticias. Puede investigar crímenes.",
        "canales_trabajo": ["redaccion", "prensa", "radio", "tv", "cualquiera"],
        "canales_solicitud": ["cualquiera"],
        "turno": 8,
    },
    "abogado": {
        "display": "Abogado/a",
        "salario_hora": 15.0,
        "nivel": "medio_alto",
        "min_edad": 24,
        "descripcion": "Defiende o acusa en tribunal.",
        "canales_trabajo": ["tribunal", "juzgado", "bufete", "registro"],
        "canales_solicitud": ["tribunal", "juzgado", "registro"],
        "turno": 8,
    },
    "medico": {
        "display": "Médico/a",
        "salario_hora": 20.0,
        "nivel": "alto",
        "min_edad": 26,
        "descripcion": "Trata pacientes en hospital.",
        "canales_trabajo": ["hospital", "clinica", "emergencia"],
        "canales_solicitud": ["hospital", "clinica"],
        "turno": 12,
    },
    "empresario": {
        "display": "Empresario/a",
        "salario_hora": 30.0,
        "nivel": "muy_alto",
        "min_edad": 21,
        "descripcion": "Dirige empresa. Requiere $5,000 de capital.",
        "canales_trabajo": ["oficina", "empresa", "corporativo", "cualquiera"],
        "canales_solicitud": ["cualquiera"],
        "turno": 8,
        "requiere_capital": 5000,
    },
    "contrabandista": {
        "display": "Contrabandista",
        "salario_hora": 25.0,
        "nivel": "alto",
        "min_edad": 18,
        "descripcion": "Trabaja en el mercado negro. Muy ilegal.",
        "canales_trabajo": ["mercado-negro", "mercado_negro", "almacen", "frontera"],
        "canales_solicitud": ["mercado-negro", "mercado_negro"],
        "turno": 6,
        "ilegal": True,
    },
    "sicario": {
        "display": "Sicario",
        "salario_hora": 50.0,
        "nivel": "muy_alto",
        "min_edad": 18,
        "descripcion": "Trabajo ilegal de alta peligrosidad. Solo por admin.",
        "canales_trabajo": ["cualquiera"],
        "canales_solicitud": ["cualquiera"],
        "turno": 4,
        "ilegal": True,
        "requiere_admin": True,
    },
    "mesonero": {
        "display": "Mesonero/a",
        "salario_hora": 3.0,
        "nivel": "minimo",
        "min_edad": 16,
        "descripcion": "Atiende mesas en restaurantes.",
        "canales_trabajo": ["restaurante", "tasca", "cafe", "cantina"],
        "canales_solicitud": ["restaurante", "tasca", "cafe", "cantina"],
        "turno": 8,
    },
    "guarda_prision": {
        "display": "Guardia de Prisión",
        "salario_hora": 5.5,
        "nivel": "medio",
        "min_edad": 20,
        "descripcion": "Vigila la Prisión de Yare. Solo asignado por admins.",
        "canales_trabajo": ["celda", "patio-yare", "oficina-director-yare"],
        "canales_solicitud": ["oficina-director-yare"],
        "turno": 12,
        "requiere_admin": True,
    },
    "farmaceutico": {
        "display": "Farmacéutico/a",
        "salario_hora": 10.0,
        "nivel": "medio_alto",
        "min_edad": 22,
        "descripcion": "Despacha medicamentos en farmacia.",
        "canales_trabajo": ["farmacia", "farmatodo", "clinica"],
        "canales_solicitud": ["farmacia", "farmatodo"],
        "turno": 8,
    },
    "cocinero": {
        "display": "Cocinero/a",
        "salario_hora": 4.5,
        "nivel": "bajo",
        "min_edad": 16,
        "descripcion": "Cocina en restaurante o negocio de comida.",
        "canales_trabajo": ["restaurante", "tasca", "cafe", "cantina", "pollos"],
        "canales_solicitud": ["restaurante", "tasca", "cafe", "cantina"],
        "turno": 8,
    },
    "guardia_seguridad": {
        "display": "Guardia de Seguridad",
        "salario_hora": 4.0,
        "nivel": "bajo",
        "min_edad": 18,
        "descripcion": "Vigila edificios y locales comerciales.",
        "canales_trabajo": ["banco", "cc", "comercial", "hotel", "edificio"],
        "canales_solicitud": ["banco", "cc", "hotel"],
        "turno": 12,
    },
}


class Trabajos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def start_tasks(self):
        if not self.pagar_salarios.is_running():
            self.pagar_salarios.start()

    @tasks.loop(hours=6)
    async def pagar_salarios(self):
        personajes = await db.all("personajes")
        for uid, datos in personajes.items():
            if datos.get("muerto") or datos.get("arrestado"):
                continue
            trabajo = datos.get("trabajo_actual", "desempleado")
            if not trabajo or trabajo == "desempleado":
                continue
            job_info = TRABAJOS.get(trabajo.lower().replace(" ", "_"))
            if not job_info or job_info.get("salario_hora", 0) <= 0:
                continue
            salario = round(job_info["salario_hora"] * 6, 2)
            nuevo_dinero = round(datos.get("dinero", 0) + salario, 2)
            await db.update("personajes", uid, {"dinero": nuevo_dinero})

    # ── /trabajos ─────────────────────────────────────────────────────────────

    @app_commands.command(name="trabajos", description="Lista todos los trabajos disponibles")
    async def trabajos_slash(self, interaction: discord.Interaction):
        await self._mostrar_trabajos(interaction)

    @commands.command(name="trabajos")
    async def trabajos_prefix(self, ctx):
        await self._mostrar_trabajos(ctx)

    async def _mostrar_trabajos(self, ctx_or_inter):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        embed = discord.Embed(
            title="💼 Trabajos Disponibles — Venezuela RP",
            description=f"Usa `/solicitar_trabajo <nombre>` **estando en el lugar correcto**.\nInfo completa en <#{CH_INFO_TRABAJOS}>",
            color=discord.Color.gold()
        )
        legales = {k: v for k, v in TRABAJOS.items() if not v.get("ilegal") and k != "desempleado"}
        ilegales = {k: v for k, v in TRABAJOS.items() if v.get("ilegal")}

        for key, job in legales.items():
            tags = ""
            if job.get("requiere_admin"): tags += " 🔒"
            if job.get("requiere_vehiculo"): tags += " 🚗"
            if job.get("requiere_capital"): tags += " 💰"
            canales_s = job.get("canales_solicitud", ["?"])
            lugar = "Cualquier lugar" if "cualquiera" in canales_s else f"En: {', '.join(canales_s[:2])}"
            embed.add_field(
                name=f"{job['display']}{tags}",
                value=f"${job['salario_hora']:.1f}/h | +{job['min_edad']}años\n📍 {lugar}",
                inline=True
            )

        if ilegales:
            embed.add_field(name="─────────────", value="**⚠️ ILEGALES:**", inline=False)
            for key, job in ilegales.items():
                tags = " 🔒" if job.get("requiere_admin") else ""
                embed.add_field(
                    name=f"⚠️ {job['display']}{tags}",
                    value=f"${job['salario_hora']:.1f}/h | {job['descripcion'][:50]}",
                    inline=True
                )

        if is_slash:
            await ctx_or_inter.response.send_message(embed=embed)
        else:
            await ctx_or_inter.send(embed=embed)

    # ── /solicitar_trabajo ────────────────────────────────────────────────────

    @app_commands.command(name="solicitar_trabajo", description="Solicita un trabajo (debes estar en el lugar)")
    @app_commands.describe(nombre_trabajo="Nombre del trabajo (ej: comerciante, medico, taxista)")
    async def solicitar_trabajo_slash(self, interaction: discord.Interaction, nombre_trabajo: str):
        await self._solicitar(interaction, nombre_trabajo)

    @commands.command(name="solicitar_trabajo", aliases=["trabajo"])
    async def solicitar_trabajo_prefix(self, ctx, *, nombre_trabajo: str):
        await self._solicitar(ctx, nombre_trabajo)

    async def _solicitar(self, ctx_or_inter, nombre_trabajo: str):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        user = ctx_or_inter.user if is_slash else ctx_or_inter.author

        async def reply(msg, embed=None, view=None, ephemeral=False):
            if is_slash:
                if not ctx_or_inter.response.is_done():
                    await ctx_or_inter.response.send_message(msg, embed=embed, view=view, ephemeral=ephemeral)
                else:
                    await ctx_or_inter.followup.send(msg, embed=embed, view=view)
            else:
                await ctx_or_inter.send(msg, embed=embed, view=view)

        datos = await db.get("personajes", str(user.id))
        if not datos:
            return await reply("❌ Sin personaje.", ephemeral=True)

        job_key = nombre_trabajo.lower().replace(" ", "_").replace("-", "_")
        if job_key not in TRABAJOS:
            for k, v in TRABAJOS.items():
                if nombre_trabajo.lower() in v["display"].lower():
                    job_key = k
                    break
            else:
                return await reply(f"❌ Trabajo `{nombre_trabajo}` no encontrado. Usa `/trabajos`.", ephemeral=True)

        job = TRABAJOS[job_key]
        edad = datos.get("edad", 0)

        if job_key == "desempleado":
            return await self._asignar_trabajo(ctx_or_inter, job_key, job, datos)

        if edad < job["min_edad"]:
            return await reply(f"❌ Necesitas {job['min_edad']} años. Tienes {edad}.", ephemeral=True)
        if edad < 16:
            return await reply("❌ Necesitas mínimo 16 años para trabajar.", ephemeral=True)

        # ── VERIFICAR UBICACIÓN ───────────────────────────────────────────────
        canales_solicitud = job.get("canales_solicitud", ["cualquiera"])
        if "cualquiera" not in canales_solicitud:
            canal_actual = datos.get("canal_actual", "")
            en_lugar = any(c in canal_actual for c in canales_solicitud)
            if not en_lugar:
                lugares_txt = ", ".join(f"`{c}`" for c in canales_solicitud[:4])
                return await reply(
                    f"❌ Para solicitar **{job['display']}** debes estar en el lugar de trabajo.\n"
                    f"📍 Canales válidos: {lugares_txt}\n"
                    f"Usa `/viajar` para desplazarte.",
                    ephemeral=True
                )

        if job.get("requiere_vehiculo"):
            vehiculos = datos.get("vehiculos", [])
            if not any(job["requiere_vehiculo"] in v.lower() for v in vehiculos):
                return await reply(f"❌ Necesitas un {job['requiere_vehiculo']} para este trabajo.", ephemeral=True)

        if job.get("requiere_capital"):
            if datos.get("dinero", 0) < job["requiere_capital"]:
                return await reply(f"❌ Necesitas ${job['requiere_capital']:,} de capital inicial.", ephemeral=True)

        if job.get("requiere_admin"):
            return await reply(f"❌ **{job['display']}** solo puede ser asignado por un admin.", ephemeral=True)

        if job.get("ilegal"):
            embed = discord.Embed(
                title="⚠️ Trabajo Ilegal",
                description=f"**{job['display']}** es ilegal. Si la policía te atrapa, serás arrestado.\n\n¿Confirmas?",
                color=discord.Color.red()
            )
            view = ConfirmarTrabajoIlegalView(user.id, job_key, job, datos)
            return await reply("", embed=embed, view=view)

        await self._asignar_trabajo(ctx_or_inter, job_key, job, datos)

    async def _asignar_trabajo(self, ctx_or_inter, job_key: str, job: dict, datos: dict):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        user = ctx_or_inter.user if is_slash else ctx_or_inter.author
        guild = ctx_or_inter.guild

        member = guild.get_member(user.id)
        if member:
            for rol_id in ROL_SALARIO.values():
                r = guild.get_role(rol_id)
                if r and r in member.roles:
                    try:
                        await member.remove_roles(r)
                    except discord.Forbidden:
                        pass

            if job.get("salario_hora", 0) > 0:
                nivel = job.get("nivel", "minimo")
                sal_id = ROL_SALARIO.get(nivel)
                if sal_id:
                    r = guild.get_role(sal_id)
                    if r:
                        try:
                            await member.add_roles(r)
                        except discord.Forbidden:
                            pass

        await db.update("personajes", str(user.id), {
            "trabajo_actual": job_key,
            "trabajo_display": job["display"],
        })

        embed = discord.Embed(
            title=f"✅ Trabajo: {job['display']}",
            description=job["descripcion"],
            color=discord.Color.green()
        )
        if job.get("salario_hora", 0) > 0:
            embed.add_field(name="💰 Salario", value=f"${job['salario_hora']:.2f}/hora", inline=True)
            embed.add_field(name="⏰ Turno", value=f"{job.get('turno', 8)} horas", inline=True)
            embed.add_field(name="📅 Pago automático", value="Cada 6 horas", inline=True)
        else:
            embed.description = "Estás desempleado. Usa `/trabajos` para buscar empleo."

        if is_slash:
            if not ctx_or_inter.response.is_done():
                await ctx_or_inter.response.send_message(embed=embed)
            else:
                await ctx_or_inter.followup.send(embed=embed)
        else:
            await ctx_or_inter.send(embed=embed)

    # ── /renunciar ────────────────────────────────────────────────────────────

    @app_commands.command(name="renunciar", description="Renuncia a tu trabajo actual")
    async def renunciar_slash(self, interaction: discord.Interaction):
        await self._renunciar(interaction)

    @commands.command(name="renunciar")
    async def renunciar_prefix(self, ctx):
        await self._renunciar(ctx)

    async def _renunciar(self, ctx_or_inter):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        user = ctx_or_inter.user if is_slash else ctx_or_inter.author

        async def reply(msg):
            if is_slash:
                await ctx_or_inter.response.send_message(msg)
            else:
                await ctx_or_inter.send(msg)

        datos = await db.get("personajes", str(user.id))
        if not datos:
            return await reply("❌ Sin personaje.")

        trabajo_actual = datos.get("trabajo_actual", "desempleado")
        if trabajo_actual == "desempleado":
            return await reply("❌ No tienes trabajo actualmente.")

        trabajo_display = datos.get("trabajo_display", trabajo_actual)
        guild = ctx_or_inter.guild
        member = guild.get_member(user.id)
        if member:
            for rol_id in ROL_SALARIO.values():
                r = guild.get_role(rol_id)
                if r and r in member.roles:
                    try:
                        await member.remove_roles(r)
                    except discord.Forbidden:
                        pass

        await db.update("personajes", str(user.id), {
            "trabajo_actual": "desempleado",
            "trabajo_display": "Desempleado",
        })
        await reply(f"✅ Renunciaste a **{trabajo_display}**. Ahora estás desempleado/a.")

    # ── /trabajar ─────────────────────────────────────────────────────────────

    @app_commands.command(name="trabajar", description="Registra una hora de trabajo manual")
    async def trabajar_slash(self, interaction: discord.Interaction):
        await self._trabajar(interaction)

    @commands.command(name="trabajar")
    async def trabajar_prefix(self, ctx):
        await self._trabajar(ctx)

    async def _trabajar(self, ctx_or_inter):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        user = ctx_or_inter.user if is_slash else ctx_or_inter.author

        async def reply(msg, embed=None):
            if is_slash:
                await ctx_or_inter.response.send_message(msg, embed=embed)
            else:
                await ctx_or_inter.send(msg, embed=embed)

        datos = await db.get("personajes", str(user.id))
        if not datos:
            return await reply("❌ Sin personaje.")

        trabajo = datos.get("trabajo_actual", "desempleado")
        if trabajo == "desempleado":
            return await reply("❌ No tienes trabajo. Usa `/trabajos` para ver opciones.")

        job_info = TRABAJOS.get(trabajo)
        if not job_info or job_info.get("salario_hora", 0) <= 0:
            return await reply("❌ Trabajo no reconocido o sin salario.")

        canal_actual = datos.get("canal_actual", "")
        canales_validos = job_info.get("canales_trabajo", [])
        en_lugar = any(c in canal_actual for c in canales_validos) or "cualquiera" in canales_validos

        if not en_lugar:
            return await reply(
                f"❌ Debes estar en tu lugar de trabajo para cobrar horas como **{job_info['display']}**.\n"
                f"Canales válidos: {', '.join(canales_validos[:4])}"
            )

        ganancia = round(job_info["salario_hora"], 2)
        dinero = datos.get("dinero", 0)
        await db.update("personajes", str(user.id), {"dinero": round(dinero + ganancia, 2)})

        embed = discord.Embed(title=f"💼 {job_info['display']}", color=discord.Color.green())
        embed.add_field(name="⏱️ Horas trabajadas", value="1 hora", inline=True)
        embed.add_field(name="💵 Ganancia", value=f"+${ganancia:.2f}", inline=True)
        embed.add_field(name="💰 Saldo total", value=f"${dinero + ganancia:.2f}", inline=True)
        await reply("", embed=embed)

    # ── /asignar_trabajo (admin) ──────────────────────────────────────────────

    @app_commands.command(name="asignar_trabajo", description="[ADMIN] Asigna un trabajo a un personaje")
    @app_commands.describe(usuario="Jugador", nombre_trabajo="Trabajo a asignar")
    async def asignar_trabajo_admin(self, interaction: discord.Interaction, usuario: discord.Member, nombre_trabajo: str):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ Solo admins.", ephemeral=True)

        datos = await db.get("personajes", str(usuario.id))
        if not datos:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)

        job_key = nombre_trabajo.lower().replace(" ", "_")
        if job_key not in TRABAJOS:
            return await interaction.response.send_message(f"❌ Trabajo `{nombre_trabajo}` no encontrado.", ephemeral=True)

        job = TRABAJOS[job_key]
        await self._asignar_trabajo(interaction, job_key, job, datos)


class ConfirmarTrabajoIlegalView(discord.ui.View):
    def __init__(self, user_id, job_key, job, datos):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.job_key = job_key
        self.job = job
        self.datos = datos

    @discord.ui.button(label="✅ Confirmar (ilegal)", style=discord.ButtonStyle.red)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("No es tu decisión.", ephemeral=True)

        await db.update("personajes", str(self.user_id), {
            "trabajo_actual": self.job_key,
            "trabajo_display": self.job["display"],
        })

        guild = interaction.guild
        member = guild.get_member(self.user_id)
        if member:
            nivel = self.job.get("nivel", "minimo")
            sal_id = ROL_SALARIO.get(nivel)
            if sal_id:
                r = guild.get_role(sal_id)
                if r:
                    try:
                        await member.add_roles(r)
                    except discord.Forbidden:
                        pass

        await interaction.response.send_message(
            f"⚠️ Ahora eres **{self.job['display']}**. Ten cuidado con la policía."
        )
        self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Cancelado.", ephemeral=True)
        self.stop()


async def setup(bot):
    await bot.add_cog(Trabajos(bot))