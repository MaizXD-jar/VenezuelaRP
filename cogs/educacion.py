"""
cogs/educacion.py — Sistema de educación completo.
- Cursos con duración real
- Educación física como asignatura
- Notas cada 3 días (basadas en inteligencia y asistencia)
- Si repruebas pierdes progreso; si tienes nota alta desbloqueas bonus extra
- /beca — solicita beca si tienes buenas notas y poco dinero
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import time
import random
from utils import db

TRES_DIAS_SEG = 3 * 24 * 3600  # 3 días en segundos

CURSOS = {
    "primaria": {
        "display": "Educación Primaria",
        "descripcion": "Educación básica. Necesaria para continuar estudiando.",
        "duracion_horas": 24,
        "costo": 0.0,
        "requisito_estudios": None,
        "resultado_estudios": "primaria",
        "bonuses": {"inteligencia": 1},
        "canales_validos": ["escuela", "liceo", "colegio", "ucv", "universidad"],
        "nivel_min_edad": 6,
        "emoji": "📚",
    },
    "bachillerato": {
        "display": "Bachillerato",
        "descripcion": "Obtén tu título de bachiller. Necesario para trabajos de nivel medio.",
        "duracion_horas": 48,
        "costo": 50.0,
        "requisito_estudios": None,
        "resultado_estudios": "secundaria",
        "bonuses": {"inteligencia": 2, "carisma": 1},
        "canales_validos": ["liceo", "escuela", "colegio", "ucv", "universidad"],
        "nivel_min_edad": 12,
        "emoji": "🏫",
    },
    "educacion_fisica": {
        "display": "Educación Física",
        "descripcion": "Mejora tu condición física, fuerza y agilidad. Clases en el gimnasio.",
        "duracion_horas": 72,
        "costo": 200.0,
        "requisito_estudios": None,
        "resultado_estudios": None,
        "bonuses": {"fuerza": 2, "agilidad": 3, "resistencia": 3},
        "canales_validos": ["gym", "crossfit", "muay", "boxeo", "deporte", "cancha", "campo", "estadio"],
        "nivel_min_edad": 10,
        "emoji": "🏃",
    },
    "tecnico_mecanica": {
        "display": "Técnico en Mecánica",
        "descripcion": "Curso técnico de mecánica. Bono en trabajos de taller.",
        "duracion_horas": 24,
        "costo": 80.0,
        "requisito_estudios": "primaria",
        "resultado_estudios": None,
        "bonuses": {"tecnica": 3, "fuerza": 1},
        "bonus_trabajo": "mecanico",
        "canales_validos": ["taller", "garage", "mecanico", "ferreteria"],
        "nivel_min_edad": 16,
        "emoji": "🔧",
    },
    "tecnico_cocina": {
        "display": "Curso de Cocina",
        "descripcion": "Aprende cocina venezolana. Bono como cocinero.",
        "duracion_horas": 12,
        "costo": 30.0,
        "requisito_estudios": None,
        "resultado_estudios": None,
        "bonuses": {"carisma": 1, "tecnica": 2},
        "bonus_trabajo": "cocinero",
        "canales_validos": ["restaurante", "tasca", "cantina", "cafe"],
        "nivel_min_edad": 14,
        "emoji": "👨‍🍳",
    },
    "autodefensa": {
        "display": "Curso de Autodefensa",
        "descripcion": "Entrenamiento básico de combate cuerpo a cuerpo.",
        "duracion_horas": 24,
        "costo": 60.0,
        "requisito_estudios": None,
        "resultado_estudios": None,
        "bonuses": {"fuerza": 3, "agilidad": 3, "resistencia": 2},
        "canales_validos": ["gym", "crossfit", "muay", "boxeo", "deporte", "cancha", "campo"],
        "nivel_min_edad": 14,
        "emoji": "🥊",
    },
    "informatica": {
        "display": "Carrera de Informática",
        "descripcion": "Carrera universitaria en TI. Bono masivo en hackeo y tecnología.",
        "duracion_horas": 168,
        "costo": 500.0,
        "requisito_estudios": "secundaria",
        "resultado_estudios": "universitario",
        "bonuses": {"inteligencia": 5, "tecnica": 4},
        "bonus_trabajo": "informatico",
        "canales_validos": ["ucv", "universidad", "laboratorio", "biblioteca"],
        "nivel_min_edad": 17,
        "emoji": "💻",
    },
    "derecho": {
        "display": "Carrera de Derecho",
        "descripcion": "Abogacía. Necesario para ejercer como abogado.",
        "duracion_horas": 200,
        "costo": 800.0,
        "requisito_estudios": "secundaria",
        "resultado_estudios": "universitario",
        "bonuses": {"inteligencia": 4, "carisma": 5},
        "bonus_trabajo": "abogado",
        "canales_validos": ["ucv", "universidad", "tribunal", "biblioteca"],
        "nivel_min_edad": 17,
        "emoji": "⚖️",
    },
    "medicina": {
        "display": "Carrera de Medicina",
        "descripcion": "La carrera más larga. Necesaria para ejercer como médico.",
        "duracion_horas": 336,
        "costo": 1200.0,
        "requisito_estudios": "secundaria",
        "resultado_estudios": "graduado",
        "bonuses": {"inteligencia": 6, "tecnica": 5, "resistencia": 2},
        "bonus_trabajo": "medico",
        "canales_validos": ["ucv", "universidad", "hospital", "clinica", "laboratorio"],
        "nivel_min_edad": 17,
        "emoji": "🏥",
    },
    "quimica": {
        "display": "Carrera de Química",
        "descripcion": "Bono en fabricación de sustancias. Útil para farmacia y... otras cosas.",
        "duracion_horas": 144,
        "costo": 600.0,
        "requisito_estudios": "secundaria",
        "resultado_estudios": "universitario",
        "bonuses": {"inteligencia": 5, "tecnica": 4},
        "bonus_trabajo": "quimico",
        "canales_validos": ["ucv", "universidad", "laboratorio", "biblioteca"],
        "nivel_min_edad": 17,
        "emoji": "🧪",
    },
    "periodismo": {
        "display": "Carrera de Periodismo",
        "descripcion": "Comunicación social. Acceso a zonas restringidas con carnet de prensa.",
        "duracion_horas": 120,
        "costo": 400.0,
        "requisito_estudios": "secundaria",
        "resultado_estudios": "universitario",
        "bonuses": {"carisma": 5, "inteligencia": 3},
        "bonus_trabajo": "periodista",
        "canales_validos": ["ucv", "universidad", "aula", "biblioteca"],
        "nivel_min_edad": 17,
        "emoji": "📰",
    },
    "administracion": {
        "display": "Administración de Empresas",
        "descripcion": "Economía y negocios. Bono como empresario.",
        "duracion_horas": 120,
        "costo": 450.0,
        "requisito_estudios": "secundaria",
        "resultado_estudios": "universitario",
        "bonuses": {"inteligencia": 3, "carisma": 3, "tecnica": 2},
        "bonus_trabajo": "empresario",
        "canales_validos": ["ucv", "universidad", "aula", "biblioteca"],
        "nivel_min_edad": 17,
        "emoji": "📊",
    },
}


def _requisito_ok(datos: dict, curso: dict) -> tuple:
    edad = datos.get("edad", 0)
    estudios = datos.get("estudios", "ninguno")
    min_edad = curso.get("nivel_min_edad", 0)
    req_estudios = curso.get("requisito_estudios")
    ORDEN = ["ninguno", "primaria", "secundaria", "universitario", "graduado"]
    if edad < min_edad:
        return False, f"Necesitas al menos {min_edad} años (tienes {edad})."
    if req_estudios:
        idx_req = ORDEN.index(req_estudios) if req_estudios in ORDEN else 0
        idx_actual = ORDEN.index(estudios) if estudios in ORDEN else 0
        if idx_actual < idx_req:
            return False, f"Necesitas tener estudios de **{req_estudios}** primero (tienes: {estudios})."
    return True, ""


def _calcular_nota(datos: dict, curso_key: str) -> int:
    """
    Calcula una nota (1-10) basada en inteligencia del personaje y el curso.
    La asistencia se simula con si el personaje está en el canal correcto (canal_actual).
    """
    inteligencia = datos.get("stats", {}).get("inteligencia", 5)
    # Base de nota según inteligencia
    base_nota = 3 + int(inteligencia * 0.6)  # entre 3 y 9 con int 1-10
    base_nota = min(9, max(3, base_nota))
    # Variación aleatoria ±2
    nota = base_nota + random.randint(-2, 2)
    nota = max(1, min(10, nota))
    # Bonus educacion fisica si tiene fuerza alta
    if curso_key == "educacion_fisica":
        fuerza = datos.get("stats", {}).get("fuerza", 5)
        if fuerza >= 8:
            nota = min(10, nota + 1)
    return nota


class Educacion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def start_tasks(self):
        if not self.check_estudios_terminados.is_running():
            self.check_estudios_terminados.start()
        if not self.check_notas_periodo.is_running():
            self.check_notas_periodo.start()

    # ── Task: Verificar cursos terminados ──────────────────────────────────────
    @tasks.loop(minutes=10)
    async def check_estudios_terminados(self):
        personajes = await db.all("personajes")
        now = time.time()
        for uid, datos in personajes.items():
            estudio = datos.get("estudio_activo")
            if not estudio:
                continue
            if now < estudio.get("termina_ts", float("inf")):
                continue
            await self._completar_curso(uid, datos, estudio)

    async def _completar_curso(self, uid: str, datos: dict, estudio: dict):
        nombre_curso = estudio["curso"]
        curso = CURSOS.get(nombre_curso)
        if not curso:
            await db.update("personajes", uid, {"estudio_activo": None})
            return
        # Verificar nota final promedio
        notas = estudio.get("notas", [])
        promedio = sum(notas) / len(notas) if notas else 6
        if promedio < 5:
            # Reprobó — no obtiene el certificado, pierde el dinero
            await db.update("personajes", uid, {"estudio_activo": None})
            guild = self.bot.guilds[0] if self.bot.guilds else None
            if guild:
                member = guild.get_member(int(uid))
                if member:
                    try:
                        embed = discord.Embed(
                            title=f"❌ Reprobaste: {curso['display']}",
                            description=f"Tu promedio fue **{promedio:.1f}/10**. No obtuviste el certificado.",
                            color=discord.Color.red()
                        )
                        embed.set_footer(text="Puedes volver a inscribirte con /estudiar")
                        await member.send(embed=embed)
                    except:
                        pass
            return

        stats = datos.get("stats", {})
        # Bonus extra si nota >= 9
        bonuses = curso.get("bonuses", {})
        if promedio >= 9:
            bonuses = {k: v + 1 for k, v in bonuses.items()}

        for stat, valor in bonuses.items():
            stats[stat] = stats.get(stat, 5) + valor

        update = {"stats": stats, "estudio_activo": None}
        if curso.get("resultado_estudios"):
            update["estudios"] = curso["resultado_estudios"]
        certs = datos.get("certificados", [])
        if nombre_curso not in certs:
            certs.append(nombre_curso)
        update["certificados"] = certs
        if curso.get("bonus_trabajo"):
            bt = datos.get("bonuses_trabajo", [])
            if curso["bonus_trabajo"] not in bt:
                bt.append(curso["bonus_trabajo"])
            update["bonuses_trabajo"] = bt
        await db.update("personajes", uid, update)

        guild = self.bot.guilds[0] if self.bot.guilds else None
        if guild:
            member = guild.get_member(int(uid))
            if member:
                try:
                    embed = discord.Embed(
                        title=f"🎓 ¡Curso completado: {curso['display']}!",
                        description=f"Promedio final: **{promedio:.1f}/10**",
                        color=discord.Color.gold()
                    )
                    bonuses_txt = "\n".join(f"• +{v} {k.title()}" for k, v in bonuses.items())
                    if bonuses_txt:
                        embed.add_field(name="📈 Stats mejorados", value=bonuses_txt)
                    if curso.get("resultado_estudios"):
                        embed.add_field(name="🎓 Nivel educativo", value=f"Ahora tienes: **{curso['resultado_estudios']}**")
                    if promedio >= 9:
                        embed.add_field(name="⭐ Excelencia", value="¡Bonus adicional por nota sobresaliente!", inline=False)
                    embed.set_footer(text="Usa /certificados para ver tus títulos")
                    await member.send(embed=embed)
                except:
                    pass

    # ── Task: Evaluar notas cada 3 días ───────────────────────────────────────
    @tasks.loop(hours=1)
    async def check_notas_periodo(self):
        """Cada hora revisa si han pasado 3 días del último período de notas."""
        personajes = await db.all("personajes")
        now = time.time()
        for uid, datos in personajes.items():
            estudio = datos.get("estudio_activo")
            if not estudio:
                continue
            ultimo_periodo = estudio.get("ultimo_periodo_ts", estudio.get("inicio_ts", now))
            if now - ultimo_periodo < TRES_DIAS_SEG:
                continue
            await self._evaluar_periodo(uid, datos, estudio, now)

    async def _evaluar_periodo(self, uid: str, datos: dict, estudio: dict, now: float):
        """Evalúa el rendimiento del período y asigna nota."""
        nombre_curso = estudio["curso"]
        curso = CURSOS.get(nombre_curso, {})
        nota = _calcular_nota(datos, nombre_curso)
        notas = estudio.get("notas", [])
        notas.append(nota)
        promedio_actual = sum(notas) / len(notas)

        # Actualizar el estudio
        nuevo_estudio = dict(estudio)
        nuevo_estudio["notas"] = notas
        nuevo_estudio["ultimo_periodo_ts"] = now
        await db.update("personajes", uid, {"estudio_activo": nuevo_estudio})

        # Penalización si reprueba el período
        if nota < 5:
            # Pierde 25% del progreso (aumenta el tiempo restante)
            termina_ts = estudio.get("termina_ts", now)
            duracion_original = CURSOS.get(nombre_curso, {}).get("duracion_horas", 24) * 3600
            nuevo_termina = termina_ts + duracion_original * 0.25
            nuevo_estudio["termina_ts"] = nuevo_termina
            await db.update("personajes", uid, {"estudio_activo": nuevo_estudio})

        # Notificar al jugador
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if guild:
            member = guild.get_member(int(uid))
            if member:
                try:
                    if nota >= 9:
                        emoji = "⭐"
                        msg = "¡Excelente rendimiento!"
                    elif nota >= 7:
                        emoji = "✅"
                        msg = "Buen rendimiento. Sigue así."
                    elif nota >= 5:
                        emoji = "⚠️"
                        msg = "Rendimiento justo. Esfuérzate más."
                    else:
                        emoji = "❌"
                        msg = "Reprobaste este período. Perdiste 25% del progreso."

                    embed = discord.Embed(
                        title=f"{emoji} Nota del período — {curso.get('display', nombre_curso)}",
                        description=(
                            f"**Nota:** {nota}/10\n"
                            f"**Promedio acumulado:** {promedio_actual:.1f}/10\n"
                            f"{msg}"
                        ),
                        color=discord.Color.green() if nota >= 7 else (discord.Color.yellow() if nota >= 5 else discord.Color.red())
                    )
                    if nota >= 8 and datos.get("dinero", 0) < 200:
                        embed.add_field(name="💡 Beca disponible", value="Tienes buenas notas y poco dinero. Usa `/beca` para solicitar una beca.", inline=False)
                    await member.send(embed=embed)
                except:
                    pass

    # ── /cursos ───────────────────────────────────────────────────────────────
    @app_commands.command(name="cursos", description="Lista todos los cursos educativos disponibles")
    async def cursos_slash(self, interaction: discord.Interaction):
        datos = await db.get("personajes", str(interaction.user.id))
        canal_actual = datos.get("canal_actual", "") if datos else ""
        embed = discord.Embed(
            title="🎓 Cursos Disponibles — Venezuela RP",
            description="Usa `/estudiar <curso>` estando en el lugar correcto.",
            color=discord.Color.blurple()
        )
        for key, curso in CURSOS.items():
            disponible = any(c in canal_actual for c in curso["canales_validos"]) if canal_actual else False
            disp_txt = "✅ Aquí" if disponible else f"📍 {', '.join(curso['canales_validos'][:2])}"
            if datos:
                ok, razon = _requisito_ok(datos, curso)
                req_txt = "✅ Puedes inscribirte" if ok else f"❌ {razon[:50]}"
            else:
                req_txt = "Sin personaje"
            embed.add_field(
                name=f"{curso['emoji']} {curso['display']} — ${curso['costo']:.0f}",
                value=f"⏱️ {curso['duracion_horas']}h | {disp_txt}\n{req_txt}\n_{curso['descripcion'][:55]}_",
                inline=False
            )
        embed.set_footer(text="📊 Notas cada 3 días | /beca para solicitar beca si tienes buenas notas")
        await interaction.response.send_message(embed=embed)

    # ── /estudiar ─────────────────────────────────────────────────────────────
    @app_commands.command(name="estudiar", description="Inscríbete en un curso educativo")
    @app_commands.describe(curso="Nombre del curso")
    async def estudiar_slash(self, interaction: discord.Interaction, curso: str):
        await self._estudiar(interaction, curso.lower().replace(" ", "_"))

    @commands.command(name="estudiar")
    async def estudiar_prefix(self, ctx, *, curso: str):
        await self._estudiar(ctx, curso.lower().replace(" ", "_"))

    async def _estudiar(self, ctx_or_inter, curso_key: str):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        user = ctx_or_inter.user if is_slash else ctx_or_inter.author

        async def reply(msg, embed=None, ephemeral=False):
            if is_slash:
                await ctx_or_inter.response.send_message(msg, embed=embed, ephemeral=ephemeral)
            else:
                await ctx_or_inter.send(msg, embed=embed)

        if curso_key not in CURSOS:
            return await reply(f"❌ Curso no encontrado. Usa `/cursos`.", ephemeral=True)

        datos = await db.get("personajes", str(user.id))
        if not datos:
            return await reply("❌ Sin personaje.", ephemeral=True)
        if datos.get("estudio_activo"):
            c_actual = datos["estudio_activo"]["curso"]
            t_ts = datos["estudio_activo"]["termina_ts"]
            rh = max(0, int((t_ts - time.time()) / 3600))
            return await reply(f"❌ Ya estudias **{CURSOS.get(c_actual,{}).get('display', c_actual)}**. Quedan ~{rh}h.", ephemeral=True)

        curso = CURSOS[curso_key]
        canal_actual = datos.get("canal_actual", "")
        if not any(c in canal_actual for c in curso["canales_validos"]):
            return await reply(
                f"❌ Para **{curso['display']}** debes estar en: {', '.join(f'`{c}`' for c in curso['canales_validos'][:3])}",
                ephemeral=True
            )

        ok, razon = _requisito_ok(datos, curso)
        if not ok:
            return await reply(f"❌ {razon}", ephemeral=True)

        if curso_key in datos.get("certificados", []):
            return await reply(f"✅ Ya tienes el certificado de **{curso['display']}**.", ephemeral=True)

        costo = curso["costo"]
        dinero = datos.get("dinero", 0)

        # Aplicar beca si tiene
        beca = datos.get("beca_activa")
        descuento = 0
        if beca and beca.get("activa") and costo > 0:
            descuento = round(costo * 0.5, 2)
            costo = round(costo - descuento, 2)

        if datos.get("edad", 18) < 18:
            costo = 0  # Menores no pagan
        elif dinero < costo and costo > 0:
            return await reply(f"❌ Necesitas ${costo:.2f}. Tienes ${dinero:.2f}.\n💡 ¿Tienes buenas notas y poco dinero? Usa `/beca`.", ephemeral=True)

        termina_ts = time.time() + curso["duracion_horas"] * 3600
        await db.update("personajes", str(user.id), {
            "estudio_activo": {
                "curso": curso_key,
                "inicio_ts": time.time(),
                "termina_ts": termina_ts,
                "ultimo_periodo_ts": time.time(),
                "notas": [],
            },
            "dinero": round(dinero - costo, 2) if costo > 0 else dinero,
            "beca_activa": None,  # consumir beca
        })

        embed = discord.Embed(
            title=f"{curso['emoji']} ¡Inscrito en {curso['display']}!",
            description=curso["descripcion"],
            color=discord.Color.blurple()
        )
        embed.add_field(name="⏱️ Duración", value=f"{curso['duracion_horas']}h")
        embed.add_field(name="💰 Costo", value=f"${costo:.2f}" if costo > 0 else "Gratis")
        if descuento > 0:
            embed.add_field(name="🎓 Beca aplicada", value=f"-${descuento:.2f}", inline=True)
        embed.add_field(name="📊 Sistema de notas", value="Cada 3 días recibirás una calificación por DM.", inline=False)
        bonuses_txt = "\n".join(f"• +{v} {k.title()}" for k, v in curso.get("bonuses", {}).items())
        if bonuses_txt:
            embed.add_field(name="📈 Al terminar recibirás", value=bonuses_txt)
        if curso.get("resultado_estudios"):
            embed.add_field(name="🎓 Nivel educativo", value=f"Obtendrás: **{curso['resultado_estudios']}**")
        embed.set_footer(text="Serás notificado de tus notas cada 3 días y cuando termines.")
        await reply("", embed=embed)

    # ── /mi_estudio ───────────────────────────────────────────────────────────
    @app_commands.command(name="mi_estudio", description="Muestra tu progreso de estudio actual")
    async def mi_estudio_slash(self, interaction: discord.Interaction):
        datos = await db.get("personajes", str(interaction.user.id))
        if not datos:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        estudio = datos.get("estudio_activo")
        if not estudio:
            return await interaction.response.send_message("📚 No estás estudiando. Usa `/cursos`.", ephemeral=True)
        curso_key = estudio["curso"]
        curso = CURSOS.get(curso_key, {})
        now = time.time()
        total_seg = estudio.get("termina_ts", now) - estudio.get("inicio_ts", now)
        transcurrido = now - estudio.get("inicio_ts", now)
        progreso = min(100, int((transcurrido / max(1, total_seg)) * 100))
        rh = max(0, int((estudio.get("termina_ts", now) - now) / 3600))
        rm = max(0, int(((estudio.get("termina_ts", now) - now) % 3600) / 60))
        barra = "█" * (progreso // 10) + "░" * (10 - progreso // 10)
        notas = estudio.get("notas", [])
        promedio = sum(notas) / len(notas) if notas else None
        embed = discord.Embed(
            title=f"📚 Estudiando: {curso.get('display', curso_key)}",
            description=curso.get("descripcion", ""),
            color=discord.Color.blurple()
        )
        embed.add_field(name="📊 Progreso", value=f"`{barra}` {progreso}%", inline=False)
        embed.add_field(name="⏱️ Tiempo restante", value=f"{rh}h {rm}min")
        if notas:
            notas_txt = " · ".join(f"{n}/10" for n in notas[-5:])
            embed.add_field(name=f"📝 Últimas notas", value=f"{notas_txt}\nPromedio: **{promedio:.1f}**")
        embed.set_footer(text="Las notas se evalúan cada 3 días | /cancelar_estudio para abandonar")
        await interaction.response.send_message(embed=embed)

    # ── /cancelar_estudio ─────────────────────────────────────────────────────
    @app_commands.command(name="cancelar_estudio", description="Cancela el curso actual (pierdes el dinero)")
    async def cancelar_estudio_slash(self, interaction: discord.Interaction):
        datos = await db.get("personajes", str(interaction.user.id))
        if not datos or not datos.get("estudio_activo"):
            return await interaction.response.send_message("❌ No estás estudiando nada.", ephemeral=True)
        curso_key = datos["estudio_activo"]["curso"]
        await db.update("personajes", str(interaction.user.id), {"estudio_activo": None})
        curso = CURSOS.get(curso_key, {})
        await interaction.response.send_message(
            f"❌ Abandonaste **{curso.get('display', curso_key)}**. El dinero no se devuelve."
        )

    # ── /certificados ─────────────────────────────────────────────────────────
    @app_commands.command(name="certificados", description="Muestra tus certificados y títulos")
    @app_commands.describe(usuario="Usuario (opcional)")
    async def certificados_slash(self, interaction: discord.Interaction, usuario: discord.Member = None):
        target = usuario or interaction.user
        datos = await db.get("personajes", str(target.id))
        if not datos:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        certs = datos.get("certificados", [])
        embed = discord.Embed(title=f"🎓 Certificados de {datos['nombre']}", color=discord.Color.gold())
        embed.add_field(name="📚 Nivel educativo", value=datos.get("estudios", "ninguno").title(), inline=True)
        if certs:
            certs_txt = "\n".join(
                f"{CURSOS.get(c, {}).get('emoji', '📜')} **{CURSOS.get(c, {}).get('display', c)}**"
                for c in certs
            )
            embed.add_field(name="🏆 Certificados", value=certs_txt, inline=False)
        else:
            embed.add_field(name="🏆 Certificados", value="Ninguno aún.", inline=False)
        bonuses = datos.get("bonuses_trabajo", [])
        if bonuses:
            embed.add_field(name="💼 Bonus de trabajo", value=", ".join(bonuses), inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /examen ───────────────────────────────────────────────────────────────
    @app_commands.command(name="examen", description="Examen express para avanzar de nivel (sin curso, más rápido pero arriesgado)")
    @app_commands.describe(nivel="Nivel: primaria, secundaria, universitario")
    async def examen_slash(self, interaction: discord.Interaction, nivel: str):
        datos = await db.get("personajes", str(interaction.user.id))
        if not datos:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        niveles_validos = ["primaria", "secundaria", "universitario"]
        if nivel not in niveles_validos:
            return await interaction.response.send_message(f"❌ Nivel no válido. Opciones: {', '.join(niveles_validos)}", ephemeral=True)
        canal_actual = datos.get("canal_actual", "")
        canales_examen = ["escuela", "liceo", "ucv", "universidad", "colegio"]
        if not any(c in canal_actual for c in canales_examen):
            return await interaction.response.send_message(
                "❌ Debes estar en un centro educativo para presentar examen.", ephemeral=True
            )
        COSTOS = {"primaria": 20, "secundaria": 80, "universitario": 300}
        ORDEN = ["ninguno", "primaria", "secundaria", "universitario", "graduado"]
        idx_actual = ORDEN.index(datos.get("estudios", "ninguno"))
        idx_nuevo = ORDEN.index(nivel)
        if idx_nuevo <= idx_actual:
            return await interaction.response.send_message(f"❌ Ya tienes estudios de nivel **{datos.get('estudios')}** o superior.", ephemeral=True)
        if idx_nuevo > idx_actual + 1:
            return await interaction.response.send_message(f"❌ Presenta los exámenes en orden.", ephemeral=True)
        costo = COSTOS[nivel]
        dinero = datos.get("dinero", 0)
        if dinero < costo:
            return await interaction.response.send_message(f"❌ El examen cuesta **${costo}**. Tienes ${dinero:.2f}.", ephemeral=True)
        inteligencia = datos.get("stats", {}).get("inteligencia", 5)
        prob_aprobar = min(0.85, (inteligencia / 15) + 0.30)
        await db.update("personajes", str(interaction.user.id), {"dinero": round(dinero - costo, 2)})
        if random.random() < prob_aprobar:
            await db.update("personajes", str(interaction.user.id), {"estudios": nivel})
            await interaction.response.send_message(
                f"✅ **¡Aprobaste el examen de {nivel}!** Ahora tienes estudios de **{nivel}**.\n"
                f"Costo: ${costo} | Probabilidad de éxito era: {int(prob_aprobar*100)}%"
            )
        else:
            await interaction.response.send_message(
                f"❌ **Reprobaste el examen de {nivel}.** Perdiste ${costo}.\n"
                f"Intenta de nuevo o usa `/estudiar` para hacerlo con más garantías."
            )

    # ── /beca ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="beca", description="Solicita una beca estudiantil (buenas notas + poco dinero)")
    async def beca_slash(self, interaction: discord.Interaction):
        datos = await db.get("personajes", str(interaction.user.id))
        if not datos:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)

        # Verificar si ya tiene beca
        if datos.get("beca_activa", {}).get("activa"):
            return await interaction.response.send_message(
                "ℹ️ Ya tienes una beca activa. Se aplicará en tu próxima inscripción.", ephemeral=True
            )

        # Verificar dinero
        dinero = datos.get("dinero", 0)
        familia = datos.get("familia", {})
        dinero_familia = 0
        if familia.get("padre", {}).get("vivo"):
            dinero_familia += random.randint(50, 300)
        if familia.get("madre", {}).get("vivo"):
            dinero_familia += random.randint(30, 200)

        if dinero > 200 or dinero_familia > 400:
            return await interaction.response.send_message(
                f"❌ No cumples el criterio económico para la beca.\n"
                f"Tu efectivo: ${dinero:.2f} | Situación familiar estimada: ${dinero_familia}\n"
                f"La beca es para estudiantes con **menos de $200** y familia de bajos recursos.",
                ephemeral=True
            )

        # Verificar notas
        estudio = datos.get("estudio_activo")
        if estudio:
            notas = estudio.get("notas", [])
            promedio = sum(notas) / len(notas) if notas else 0
            if promedio < 8 and notas:
                return await interaction.response.send_message(
                    f"❌ No cumples el criterio académico. Tu promedio es **{promedio:.1f}/10**.\n"
                    f"Necesitas promedio ≥ 8 para solicitar beca.",
                    ephemeral=True
                )

        # Aprobar beca
        await db.update("personajes", str(interaction.user.id), {
            "beca_activa": {
                "activa": True,
                "descuento": 0.5,
                "ts": time.time(),
            }
        })
        embed = discord.Embed(
            title="🎓 ¡Beca aprobada!",
            description=(
                "Tu solicitud de beca ha sido **aprobada**.\n\n"
                "Recibirás un **50% de descuento** en tu próxima inscripción a un curso.\n"
                "La beca se aplica automáticamente cuando uses `/estudiar`."
            ),
            color=discord.Color.gold()
        )
        embed.add_field(name="💵 Tu efectivo", value=f"${dinero:.2f}")
        embed.add_field(name="🎁 Descuento", value="50% del costo del curso")
        embed.set_footer(text="La beca caduca si no la usas en tu próxima inscripción.")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Educacion(bot))