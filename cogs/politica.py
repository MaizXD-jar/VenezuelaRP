"""
cogs/politica.py — Elecciones, candidaturas, revoluciones, persecución del ejército,
FBI División Venezuela, CIA, fuga del país.
"""
import discord
from discord.ext import commands, tasks
import random
import asyncio
import time
from utils import db
from utils.roles import ROL_CRIMINAL, ROL_FANB, ROL_EJERCITO, ROL_SEBIN

CH_NOTICIAS_VZ1 = 1382156099473379458
CH_NOTICIAS_VZ2 = 1382156210576425040
CH_NOTICIAS_INT = 1382156276016087110
CH_MAS_BUSCADOS = 1369438636260724856
CH_POLICIA_AVISO = 1359320808526450780

# ── PARTIDOS POLÍTICOS ────────────────────────────────────────────────────────
PARTIDOS = {
    "psuv":   {"display": "PSUV (Socialismo Bolivariano)", "ideologia": "Socialismo"},
    "mud":    {"display": "MUD (Mesa de Unidad Democrática)", "ideologia": "Democracia liberal"},
    "vente":  {"display": "Vente Venezuela", "ideologia": "Conservadurismo liberal"},
    "pj":     {"display": "Primero Justicia", "ideologia": "Social-democracia"},
    "independiente": {"display": "Candidato Independiente", "ideologia": "Populismo"},
}

# ── CARGOS ────────────────────────────────────────────────────────────────────
CARGOS = {
    "concejal":   {"display": "Concejal Municipal", "min_edad": 21, "ingreso_min": 500,   "salario": 400},
    "alcalde":    {"display": "Alcalde",             "min_edad": 25, "ingreso_min": 2000,  "salario": 800},
    "gobernador": {"display": "Gobernador",          "min_edad": 30, "ingreso_min": 5000,  "salario": 1500},
    "diputado":   {"display": "Diputado Nacional",   "min_edad": 25, "ingreso_min": 3000,  "salario": 1200},
    "presidente": {"display": "Presidente de Venezuela", "min_edad": 30, "ingreso_min": 10000, "salario": 5000},
}

# ── NIVELES DE BÚSQUEDA (escalada) ───────────────────────────────────────────
NIVEL_BUSQUEDA = {
    1: "🟡 Buscado por policía",
    2: "🟠 Buscado por SEBIN",
    3: "🔴 Perseguido por el Ejército",
    4: "🔴🔴 FBI División Venezuela activado",
    5: "☠️ CIA / Ejército USA involucrado — NIVEL MÁXIMO",
}


class Politica(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.elecciones_activas = False
        self.candidatos = {}  # user_id: {cargo, partido, votos}
        self.fecha_eleccion = None

    # ── /postularse ───────────────────────────────────────────────────────────
    @commands.command(name="postularse")
    async def postularse(self, ctx, cargo: str, partido: str = "independiente"):
        """Postúlate a un cargo político. /postularse <cargo> <partido>"""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        cargo = cargo.lower()
        partido = partido.lower()

        if cargo not in CARGOS:
            cargos_txt = ", ".join(CARGOS.keys())
            return await ctx.send(f"❌ Cargo inválido. Opciones: `{cargos_txt}`")

        if partido not in PARTIDOS:
            partidos_txt = ", ".join(PARTIDOS.keys())
            return await ctx.send(f"❌ Partido inválido. Opciones: `{partidos_txt}`")

        info_cargo = CARGOS[cargo]
        edad = datos.get("edad", 0)
        dinero = datos.get("dinero", 0)

        if edad < info_cargo["min_edad"]:
            return await ctx.send(f"❌ Necesitas {info_cargo['min_edad']} años para este cargo (tienes {edad}).")
        if dinero < info_cargo["ingreso_min"]:
            return await ctx.send(f"❌ Necesitas ${info_cargo['ingreso_min']:,} para financiar la campaña (tienes ${dinero:.2f}).")

        # Registrar candidatura
        self.candidatos[str(ctx.author.id)] = {
            "cargo": cargo,
            "partido": partido,
            "nombre": datos.get("nombre", "?"),
            "votos": 0,
            "activo": True,
        }

        # Coste de campaña
        costo_campania = info_cargo["ingreso_min"] * 0.10
        await db.update("personajes", str(ctx.author.id), {
            "candidato": True,
            "cargo_postulado": cargo,
            "partido": partido,
            "dinero": round(dinero - costo_campania, 2),
        })

        embed = discord.Embed(
            title="🗳️ ¡Candidatura registrada!",
            description=f"**{datos['nombre']}** se postula a **{info_cargo['display']}**",
            color=0x3498DB
        )
        embed.add_field(name="Partido", value=PARTIDOS[partido]["display"])
        embed.add_field(name="Costo campaña", value=f"${costo_campania:.2f}")
        embed.add_field(name="Salario si ganas", value=f"${info_cargo['salario']:.2f}/semana")

        # Anunciar en canal de noticias
        ch = ctx.guild.get_channel(CH_NOTICIAS_VZ1)
        if ch:
            await ch.send(embed=embed)
        await ctx.send(embed=embed)

    # ── /votar ────────────────────────────────────────────────────────────────
    @commands.command(name="votar_antiguo")
    async def votar(self, ctx, candidato: discord.Member):
        """OBSOLETO: el sistema de elecciones vive ahora en cogs/elecciones.py,
        que es automático (cada 4 semanas del rol) y persiste en base de datos.
        Este guardaba los candidatos en memoria y se perdían al reiniciar el bot.
        Usa /votar."""
        await ctx.send("ℹ️ Este comando quedó obsoleto. Usa `/votar` — las elecciones ahora "
                       "son automáticas cada 4 semanas del rol. Mira `/estado_elecciones`.")
        if not self.elecciones_activas:
            return

        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        if datos.get("ya_voto"):
            return await ctx.send("❌ Ya votaste en estas elecciones.")

        cand_id = str(candidato.id)
        if cand_id not in self.candidatos:
            return await ctx.send("❌ Ese personaje no es candidato.")

        self.candidatos[cand_id]["votos"] += 1
        await db.update("personajes", str(ctx.author.id), {"ya_voto": True})
        await ctx.send(f"✅ Votaste por **{self.candidatos[cand_id]['nombre']}**.", delete_after=10)

    # ── /iniciar_elecciones (admin) ────────────────────────────────────────────
    @commands.command(name="iniciar_elecciones")
    async def iniciar_elecciones(self, ctx, duracion_minutos: int = 60):
        """[ADMIN] Inicia período electoral."""
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo admins.")

        self.elecciones_activas = True
        self.fecha_eleccion = time.time() + duracion_minutos * 60

        # Resetear votos
        personajes = await db.all("personajes")
        for uid in personajes:
            await db.update("personajes", uid, {"ya_voto": False})

        embed = discord.Embed(
            title="🗳️ ¡ELECCIONES INICIADAS!",
            description=f"El proceso electoral ha comenzado. Duración: **{duracion_minutos} minutos**.\n"
                         f"Usa `/votar @candidato` para votar.\n"
                         f"Candidatos registrados: {len(self.candidatos)}",
            color=0xFFD700
        )
        if self.candidatos:
            cands_txt = "\n".join(
                f"• **{v['nombre']}** ({CARGOS.get(v['cargo'],{}).get('display','?')}) — {PARTIDOS.get(v['partido'],{}).get('display','?')}"
                for v in self.candidatos.values()
            )
            embed.add_field(name="Candidatos", value=cands_txt[:1000], inline=False)

        for ch_id in [CH_NOTICIAS_VZ1, CH_NOTICIAS_VZ2]:
            ch = ctx.guild.get_channel(ch_id)
            if ch:
                await ch.send("@here", embed=embed)

        await ctx.send(f"✅ Elecciones iniciadas por {duracion_minutos} min.")
        await asyncio.sleep(duracion_minutos * 60)
        await self._cerrar_elecciones(ctx.guild)

    async def _cerrar_elecciones(self, guild):
        """Cierra las elecciones y anuncia ganadores."""
        self.elecciones_activas = False
        if not self.candidatos:
            return

        # Encontrar ganadores por cargo
        por_cargo = {}
        for uid, cand in self.candidatos.items():
            cargo = cand["cargo"]
            if cargo not in por_cargo or cand["votos"] > por_cargo[cargo]["votos"]:
                por_cargo[cargo] = {**cand, "uid": uid}

        embed = discord.Embed(
            title="📊 RESULTADOS ELECTORALES",
            description="Las urnas han cerrado. Los venezolanos han hablado.",
            color=0xFFD700
        )
        for cargo, ganador in por_cargo.items():
            info_cargo = CARGOS.get(cargo, {})
            embed.add_field(
                name=f"🏆 {info_cargo.get('display','?')}",
                value=f"**{ganador['nombre']}** — {ganador['votos']} votos",
                inline=False
            )
            # Asignar salario al ganador
            member = guild.get_member(int(ganador["uid"]))
            if member:
                await db.update("personajes", ganador["uid"], {
                    "cargo_politico": cargo,
                    "salario_politico": info_cargo.get("salario", 0),
                })
                try:
                    await member.send(f"🏆 ¡Ganaste las elecciones como **{info_cargo.get('display','?')}**!")
                except:
                    pass

        ch = guild.get_channel(CH_NOTICIAS_VZ1)
        if ch:
            await ch.send("@here", embed=embed)

        # Limpiar
        self.candidatos.clear()

    # ── /revolucion ───────────────────────────────────────────────────────────
    @commands.command(name="iniciar_revolucion")
    async def iniciar_revolucion(self, ctx, *, manifiesto: str):
        """Declara una revolución. El gobierno responderá. (Alta peligrosidad)"""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        if datos.get("edad", 0) < 18:
            return await ctx.send("❌ Debes tener 18 años para liderar una revolución.")

        nombre = datos.get("nombre", "?")

        # Subir nivel de búsqueda masivamente
        nivel = datos.get("nivel_busqueda", 0) + 3
        nivel = min(5, nivel)

        await db.update("personajes", str(ctx.author.id), {
            "nivel_busqueda": nivel,
            "revolucionario": True,
        })

        embed = discord.Embed(
            title="🔥 ¡REVOLUCIÓN DECLARADA!",
            description=f"**{nombre}** ha declarado la revolución:\n\n*{manifiesto[:500]}*",
            color=0x8B0000
        )
        embed.add_field(name="Estado", value=NIVEL_BUSQUEDA.get(nivel, "?"))

        # Publicar en noticias
        for ch_id in [CH_NOTICIAS_VZ1, CH_NOTICIAS_VZ2, CH_NOTICIAS_INT]:
            ch = ctx.guild.get_channel(ch_id)
            if ch:
                await ch.send("@here", embed=embed)

        await ctx.send(embed=embed)
        await self._escalar_persecucion(ctx.guild, ctx.author, datos, nivel)

    # ── /nivel_busqueda ───────────────────────────────────────────────────────
    @commands.command(name="nivel_busqueda")
    async def ver_nivel_busqueda(self, ctx, usuario: discord.Member = None):
        """Ve el nivel de búsqueda de un personaje."""
        target = usuario or ctx.author
        datos = await db.get("personajes", str(target.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        nivel = datos.get("nivel_busqueda", 0)
        embed = discord.Embed(
            title=f"🔎 Nivel de búsqueda: {datos.get('nombre','?')}",
            description=NIVEL_BUSQUEDA.get(nivel, "✅ Sin búsqueda activa"),
            color=0xE74C3C if nivel > 0 else 0x2ECC71
        )
        embed.add_field(name="Nivel", value=str(nivel))
        if nivel == 0:
            embed.description = "✅ Sin búsqueda activa. Eres libre."
        await ctx.send(embed=embed)

    async def _escalar_persecucion(self, guild, member, datos, nivel):
        """Escala la persecución según el nivel."""
        nombre = datos.get("nombre", "?")
        ch_pol = guild.get_channel(CH_POLICIA_AVISO)
        ch_buscados = guild.get_channel(CH_MAS_BUSCADOS)

        if nivel >= 1 and ch_pol:
            embed = discord.Embed(
                title=f"🚨 Nivel {nivel} — {NIVEL_BUSQUEDA[nivel]}",
                description=f"**{nombre}** ({member.mention}) está siendo buscado. Nivel {nivel}.",
                color=0xE74C3C
            )
            await ch_pol.send(f"<@&{ROL_SEBIN}>", embed=embed)

        if nivel >= 2 and ch_buscados:
            embed = discord.Embed(
                title=f"🔴 BUSCADO NIVEL {nivel}: {nombre}",
                description=NIVEL_BUSQUEDA[nivel],
                color=0x8B0000
            )
            await ch_buscados.send(embed=embed)

        if nivel >= 3:
            # Ejército en acción
            embed = discord.Embed(
                title="🪖 EJÉRCITO BOLIVARIANO MOVILIZADO",
                description=f"El Ejército Bolivariano ha sido desplegado para capturar a **{nombre}**.",
                color=0x2E4057
            )
            for ch_id in [CH_NOTICIAS_VZ1, CH_NOTICIAS_VZ2]:
                ch = guild.get_channel(ch_id)
                if ch:
                    await ch.send(embed=embed)

        if nivel >= 4:
            embed = discord.Embed(
                title="🇺🇸 FBI — DIVISIÓN VENEZUELA ACTIVADA",
                description=f"Fuentes indican que el FBI ha activado su **División Venezuela** para rastrear a **{nombre}**.",
                color=0x003087
            )
            ch_int = guild.get_channel(CH_NOTICIAS_INT)
            if ch_int:
                await ch_int.send("@here", embed=embed)

        if nivel >= 5:
            embed = discord.Embed(
                title="☠️ OPERACIÓN MÁXIMA — CIA / EJÉRCITO EEUU",
                description=f"Fuentes de inteligencia confirman que la CIA y el Ejército de EEUU tienen activa una operación para neutralizar a **{nombre}**.\nEstatus: EXTREMADAMENTE PELIGROSO.",
                color=0x000000
            )
            for ch_id in [CH_NOTICIAS_VZ1, CH_NOTICIAS_VZ2, CH_NOTICIAS_INT]:
                ch = guild.get_channel(ch_id)
                if ch:
                    await ch.send("@here", embed=embed)

    # ── /escalar_busqueda (admin) ─────────────────────────────────────────────
    @commands.command(name="escalar_busqueda")
    async def escalar_busqueda(self, ctx, objetivo: discord.Member, nivel: int):
        """[ADMIN] Escala el nivel de búsqueda de un personaje (1-5)."""
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo admins.")
        datos = await db.get("personajes", str(objetivo.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        nivel = max(0, min(5, nivel))
        await db.update("personajes", str(objetivo.id), {"nivel_busqueda": nivel})
        await ctx.send(f"✅ Nivel de búsqueda de **{datos['nombre']}** → {nivel} ({NIVEL_BUSQUEDA.get(nivel,'Ninguno')})")
        if nivel > 0:
            await self._escalar_persecucion(ctx.guild, objetivo, datos, nivel)

    # ── /fugarse ──────────────────────────────────────────────────────────────
    @commands.command(name="fugarse")
    async def fugarse(self, ctx, destino: str = "colombia"):
        """Intenta fugarse ilegalmente a Colombia o Brasil. Alto riesgo."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        destinos_ilegales = {
            "colombia": {"tiempo_min": 120, "prob_exito": 0.55, "prob_muerte": 0.20, "prob_arresto": 0.25},
            "brasil":   {"tiempo_min": 180, "prob_exito": 0.45, "prob_muerte": 0.25, "prob_arresto": 0.30},
        }

        if destino.lower() not in destinos_ilegales:
            return await ctx.send(f"❌ Destino no válido. Puedes intentar: `colombia` o `brasil`.")

        info = destinos_ilegales[destino.lower()]
        nombre = datos.get("nombre", "?")

        embed = discord.Embed(
            title="🌿 Fuga ilegal en progreso...",
            description=f"**{nombre}** intenta cruzar ilegalmente la frontera hacia **{destino.title()}**.\n"
                         f"Tiempo estimado: {info['tiempo_min']} minutos.\n"
                         f"⚠️ Probabilidad de éxito: {int(info['prob_exito']*100)}%\n"
                         f"💀 Probabilidad de muerte: {int(info['prob_muerte']*100)}%\n"
                         f"🚔 Probabilidad de arresto: {int(info['prob_arresto']*100)}%",
            color=0x27AE60
        )
        await ctx.send(embed=embed)
        await db.update("personajes", str(ctx.author.id), {"en_viaje": True})
        await asyncio.sleep(min(info["tiempo_min"] * 60, 180))  # Max 3 min real para demo

        # Determinar resultado
        roll = random.random()
        if roll < info["prob_muerte"]:
            # Muerto
            from bot import CH_MUERTOS
            await db.update("personajes", str(ctx.author.id), {
                "muerto": True, "causa_muerte": f"Murió intentando cruzar la frontera a {destino}",
                "en_viaje": False,
            })
            ch_muertos = ctx.guild.get_channel(CH_MUERTOS)
            if ch_muertos:
                em = discord.Embed(title="💀 PERSONAJE FALLECIDO",
                                   description=f"**{nombre}** murió intentando cruzar la frontera a {destino.title()} ilegalmente.",
                                   color=0x000000)
                await ch_muertos.send(em)
            await ctx.send(f"💀 {ctx.author.mention} — **{nombre}** murió en el intento. La selva/frontera no perdonó.")

        elif roll < info["prob_muerte"] + info["prob_arresto"]:
            # Arrestado
            await db.update("personajes", str(ctx.author.id), {
                "arrestado": True, "ubicacion": "prision-yare", "en_viaje": False,
            })
            await ctx.send(f"🚔 {ctx.author.mention} — **{nombre}** fue detenido/a en la frontera y enviado/a a prisión.")

        else:
            # Éxito
            sector_destino = "medellin" if destino == "colombia" else "bogota"
            await db.update("personajes", str(ctx.author.id), {
                "ubicacion": sector_destino, "canal_actual": sector_destino, "en_viaje": False,
                "nivel_busqueda": max(0, datos.get("nivel_busqueda", 0) - 1),
            })
            await ctx.send(
                f"✅ {ctx.author.mention} — **{nombre}** cruzó exitosamente a **{destino.title()}**.\n"
                f"Nueva ubicación: {sector_destino}"
            )
            # Noticia internacional
            ch_int = ctx.guild.get_channel(CH_NOTICIAS_INT)
            if ch_int:
                await ch_int.send(f"🌍 **Noticia:** Un venezolano conocido como **{nombre}** cruzó ilegalmente la frontera hacia {destino.title()}.")

    # ── /candidatos ───────────────────────────────────────────────────────────
    @commands.command(name="candidatos")
    async def ver_candidatos(self, ctx):
        if not self.candidatos:
            return await ctx.send("No hay candidatos registrados actualmente.")
        embed = discord.Embed(title="🗳️ Candidatos Registrados", color=0x3498DB)
        for uid, cand in self.candidatos.items():
            embed.add_field(
                name=f"{cand['nombre']}",
                value=f"Cargo: {CARGOS.get(cand['cargo'],{}).get('display','?')} | Partido: {PARTIDOS.get(cand['partido'],{}).get('display','?')} | Votos: {cand['votos']}",
                inline=False
            )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Politica(bot))