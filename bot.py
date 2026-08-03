import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from pathlib import Path
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # opcional: si no está python-dotenv, igual funciona con variables de entorno del sistema

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError(
        "Falta la variable de entorno DISCORD_TOKEN. "
        "Copia .env.example a .env y pon tu token ahí (nunca lo escribas en el código)."
    )

# ── Channel IDs ───────────────────────────────────────────────────────────────
CH_CREAR_DOC       = 1484797041560260688  # ← Canal principal actualizado
CH_CREAR_DOC_OLD   = 1369366721550614700  # ← Canal viejo (compatibilidad)
CH_DOCUMENTACIONES = 1421513030851629056
CH_PERSONAJES_OK   = 1359320812003393567
CH_DROGAS          = 1359320811420520614
CH_ROBOS           = 1359412448976965713
CH_PRECIOS         = 1359320811420520609
CH_COMPRAR_VEHIC   = 1369438606694944799
CH_MUERTOS         = 1359320811420520613
CH_MAS_BUSCADOS    = 1369438636260724856
CH_INFO_TRABAJOS   = 1369365887156617428
CH_POLICIA_AVISO   = 1359320808526450780
CH_NOTICIAS_VZ1    = 1382156099473379458
CH_NOTICIAS_VZ2    = 1382156210576425040
CH_NOTICIAS_INT    = 1382156276016087110
CH_CONSTITUCION    = 1484642756927164529
CH_INFO_EDUCACION  = 1359364736822804571

# ── Role IDs ──────────────────────────────────────────────────────────────────
ROL_PERSONAJE_OK   = 1369362859188027543
ROL_POLICIA        = 1359320808526450780

ROL_SALARIO = {
    "minimo":     1359320808572321909,
    "bajo":       1369552405435514951,
    "medio_bajo": 1369553098338734120,
    "medio":      1359320808572321910,
    "medio_alto": 1369553333643378739,
    "alto":       1359320808572321911,
    "muy_alto":   1369553498974326876,
    "extranjero": 1359320808593559663,
}

CONSTITUCION_EMBEDS = [
    {
        "title": "📜 Constitución de la República Bolivariana de Venezuela (1999)",
        "description": (
            "Aprobada el **15-12-1999**. **350 artículos**.\n\n"
            "*El pueblo de Venezuela, en ejercicio de sus poderes creadores e invocando "
            "la protección de Dios, el ejemplo histórico de nuestro Libertador Simón Bolívar...*"
        ),
        "color": 0xCF1020,
        "fields": [
            ("🏛️ Título I — Principios Fundamentales",
             "• **Art. 1** — Estado democrático y social de Derecho y de Justicia.\n"
             "• **Art. 2** — Valores superiores: vida, libertad, justicia, igualdad.\n"
             "• **Art. 7** — La Constitución es la norma suprema.\n"
             "• **Art. 9** — Idioma oficial: castellano."),
        ]
    },
    {
        "title": "📜 Derechos Humanos y Garantías",
        "description": "",
        "color": 0xCF1020,
        "fields": [
            ("⚖️ Derechos Civiles",
             "• **Art. 44** — La libertad personal es inviolable. Sin orden judicial no hay arresto.\n"
             "• **Art. 46** — Derecho a integridad física, psíquica y moral.\n"
             "• **Art. 49** — Debido proceso. Presunción de inocencia."),
            ("🏥 Derechos Sociales",
             "• **Art. 83** — La salud es un derecho social fundamental.\n"
             "• **Art. 87** — Toda persona tiene derecho al trabajo.\n"
             "• **Art. 91** — Salario suficiente para vivir con dignidad.\n"
             "• **Art. 102** — La educación es un derecho humano. Educación pública gratuita."),
        ]
    },
    {
        "title": "📜 Poder Público — Las 5 Ramas",
        "description": "",
        "color": 0x002B7F,
        "fields": [
            ("🏛️ División del Poder",
             "• **Legislativo** — Asamblea Nacional\n"
             "• **Ejecutivo** — Presidencia, Vicepresidencia, Ministros\n"
             "• **Judicial** — Tribunal Supremo de Justicia\n"
             "• **Ciudadano** — Defensoría, Fiscalía, Contraloría\n"
             "• **Electoral** — CNE\n\n*Venezuela tiene 5 poderes públicos.*"),
            ("👨‍💼 La Presidencia",
             "• **Art. 230** — Período: **6 años**. Reelección inmediata una sola vez.\n"
             "• **Art. 233** — Revocatoria a mitad de mandato.\n"
             "• **Art. 236** — Comandar FANB, relaciones exteriores, decretos-leyes."),
        ]
    },
    {
        "title": "📜 FANB, Economía y Disposiciones Finales",
        "description": "",
        "color": 0x002B7F,
        "fields": [
            ("🪖 Fuerza Armada Nacional Bolivariana",
             "• **Art. 328** — Institución profesional, sin militancia política.\n"
             "• **Art. 332** — El Ejecutivo organiza la CPNB."),
            ("💰 Sistema Socioeconómico",
             "• **Art. 299** — Justicia social, democracia, libre competencia.\n"
             "• **Art. 302** — El Estado se reserva la industria petrolera.\n"
             "• **Art. 318** — El BCV con autonomía de política monetaria."),
            ("🗳️ Derechos Políticos y Art. 350",
             "• **Art. 72** — Todos los cargos de elección popular son revocables.\n"
             "• **Art. 350** — El pueblo desconocerá cualquier régimen que contraríe los valores democráticos.\n\n"
             "*📌 Vigente desde 30-12-1999*"),
        ]
    },
]


async def publicar_constitucion(bot):
    for guild in bot.guilds:
        canal = guild.get_channel(CH_CONSTITUCION)
        if not canal:
            continue
        try:
            mensajes = [m async for m in canal.history(limit=5)]
            if mensajes:
                return
        except Exception:
            return
        for emb_data in CONSTITUCION_EMBEDS:
            embed = discord.Embed(
                title=emb_data["title"],
                description=emb_data.get("description", ""),
                color=emb_data["color"]
            )
            for name, value in emb_data.get("fields", []):
                embed.add_field(name=name, value=value, inline=False)
            try:
                await canal.send(embed=embed)
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"[WARN] Constitución: {e}")
        print("[STARTUP] Constitución publicada.")


async def publicar_embed_crear_doc(canal: discord.TextChannel):
    embed = discord.Embed(
        title="📋 Crear Personaje — Venezuela RP",
        description=(
            "¡Bienvenido al servidor de **Roleplay Venezuela**!\n\n"
            "Para comenzar necesitas crear tu personaje.\n\n"
            "**📌 Pasos:**\n"
            "1️⃣ Usa `/crear_personaje` en este canal\n"
            "2️⃣ Rellena el formulario\n"
            "3️⃣ Un admin aprobará tu ficha\n"
            "4️⃣ Aparecerás automáticamente en el mundo\n\n"
            "**🤖 Al ser aceptado:**\n"
            "• Tus padres serán creados como NPCs del servidor\n"
            "• Para crear los NPCs de policías, criminales y autoridades un admin puede usar `/crear_npcs_ejemplo`\n\n"
            "**👁️ Sistema de visibilidad:**\n"
            "• Solo ves el canal donde estás **ahora mismo**\n"
            "• Y el último canal donde estuviste *(solo lectura — no puedes escribir)*\n"
            "• Usa `/viajar #canal` para moverte por el mapa\n\n"
            "**📚 Comandos al empezar:**\n"
            "`/ayuda_rp` · `/perfil` · `/stats` · `/inventario`"
        ),
        color=0x2ECC71
    )
    embed.set_footer(text="Venezuela RP • ¡Que empiece el roleplay!")
    await canal.send(embed=embed)


async def publicar_embed_educacion(canal: discord.TextChannel):
    embed = discord.Embed(
        title="🎓 Sistema de Educación — Venezuela RP",
        description=(
            "El sistema educativo permite mejorar **stats**, cambiar el **nivel educativo** "
            "y desbloquear **trabajos mejor pagados**. Todo funciona en tiempo real."
        ),
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="📚 Niveles Educativos",
        value="```\nNinguno → Primaria → Secundaria → Universitario → Graduado\n```",
        inline=False
    )
    embed.add_field(
        name="🏫 Cursos (selección)",
        value=(
            "**Básicos:** `primaria` (gratis) · `bachillerato` ($50)\n"
            "**Técnicos:** `tecnico_mecanica` · `tecnico_cocina` · `autodefensa` · `educacion_fisica`\n"
            "**Universitarios:** `informatica` · `derecho` · `medicina` · `quimica` · `periodismo` · `administracion`"
        ),
        inline=False
    )
    embed.add_field(
        name="📊 Sistema de Notas (cada 3 días)",
        value=(
            "• **10** — Excelente: bonus extra de stats\n"
            "• **7-9** — Aprobado: progresas normalmente\n"
            "• **5-6** — Regular: progreso lento\n"
            "• **<5** — Reprobado: pierdes 25% del progreso\n\n"
            "Las notas dependen de tu **inteligencia** y **asistencia** (estar en el canal correcto)."
        ),
        inline=False
    )
    embed.add_field(
        name="🎓 Becas",
        value=(
            "Si tienes promedio ≥ 8 y poco dinero (< $200), usa `/beca` para "
            "solicitar una beca que cubre el **50% del costo** del siguiente curso."
        ),
        inline=False
    )
    embed.add_field(
        name="📋 Comandos",
        value=(
            "`/cursos` · `/estudiar <curso>` · `/mi_estudio`\n"
            "`/cancelar_estudio` · `/certificados` · `/examen <nivel>` · `/beca`"
        ),
        inline=False
    )
    embed.set_footer(text="Venezuela RP • La educación abre puertas")
    await canal.send(embed=embed)


async def limpiar_canal_crear_doc(bot):
    for guild in bot.guilds:
        for ch_id in [CH_CREAR_DOC, CH_CREAR_DOC_OLD]:
            canal = guild.get_channel(ch_id)
            if not canal:
                continue
            try:
                async for mensaje in canal.history(limit=100):
                    if mensaje.author.bot and mensaje.embeds:
                        continue
                    try:
                        await mensaje.delete()
                        await asyncio.sleep(0.3)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[WARN] Limpieza canal: {e}")
    print("[STARTUP] Canales limpiados.")


intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


async def load_cogs():
    cogs = [
        "cogs.personajes", "cogs.viaje", "cogs.economia", "cogs.combate",
        "cogs.npc", "cogs.policia", "cogs.telefono", "cogs.eventos_random",
        "cogs.eventos_admin",  # !teleport, !protesta, !secuestro (rescatados de eventos.py, que estaba duplicado/muerto)
        "cogs.propiedades", "cogs.trabajos", "cogs.banco", "cogs.admin",
        "cogs.roleplay", "cogs.ciudad", "cogs.tecnologia", "cogs.politica",
        "cogs.setup_rp", "cogs.mercado_negro", "cogs.educacion", "cogs.casino", "cogs.empresas",
        "cogs.hospital", "cogs.mapa_ia", "cogs.minijuegos",
    ]
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"[OK] {cog}")
        except Exception as e:
            print(f"[ERR] {cog}: {e}")


@bot.event
async def on_ready():
    print(f"Bot listo: {bot.user} ({bot.user.id})")
    await bot.tree.sync()
    print("[OK] Slash commands sincronizados")

    for cog in bot.cogs.values():
        if hasattr(cog, "start_tasks"):
            cog.start_tasks()

    await limpiar_canal_crear_doc(bot)
    await publicar_constitucion(bot)

    # ── Crear NPCs de ejemplo si no existen ──────────────────────────────────
    for guild in bot.guilds:
        npc_cog = bot.cogs.get("NPC")
        if npc_cog and hasattr(npc_cog, "crear_npcs_ejemplo"):
            from utils import db
            npcs_existentes = await db.all("npcs")
            if not npcs_existentes:
                print("[STARTUP] Creando NPCs de ejemplo...")
                from cogs.npc import NPCS_EJEMPLO
                import random
                creados = 0
                for npc_template in NPCS_EJEMPLO:
                    nombre = npc_template["nombre"]
                    npc_id = nombre.lower().replace(" ", "_").replace("'", "").replace("(", "").replace(")", "")[:30]
                    existente = await db.get("npcs", npc_id)
                    if existente:
                        continue
                    fuerza = npc_template["fuerza"]
                    npc_data = {
                        "nombre": nombre,
                        "edad": npc_template["edad"],
                        "trabajo": npc_template["trabajo"],
                        "dinero": npc_template["dinero"],
                        "tipo": npc_template.get("tipo", "civil"),
                        "stats": {
                            "hp": 100, "hp_max": 100,
                            "fuerza": fuerza,
                            "agilidad": random.randint(4, 9),
                            "resistencia": random.randint(4, 8),
                            "tecnica": random.randint(3, 9),
                            "inteligencia": random.randint(5, 12),
                        },
                        "inventario": {},
                        "ubicacion": npc_template["ubicacion"],
                        "canal_actual": None,
                        "vivo": True,
                        "imagen": None,
                        "creado_automaticamente": True,
                    }
                    if npc_template.get("tipo") == "policia":
                        npc_data["inventario"]["glock_17"] = 1
                        npc_data["inventario"]["esposas"] = 1
                    elif npc_template.get("tipo") == "criminal":
                        npc_data["inventario"]["ak47" if fuerza >= 9 else "glock_17"] = 1
                    elif npc_template.get("tipo") in ("sebin", "militar"):
                        npc_data["inventario"]["m4_carbine"] = 1
                        npc_data["inventario"]["chaleco_antibalas"] = 1
                    await db.set("npcs", npc_id, npc_data)
                    creados += 1
                print(f"[STARTUP] {creados} NPCs de ejemplo creados.")
            else:
                print(f"[STARTUP] NPCs ya existen ({len(npcs_existentes)}), omitiendo creación.")

    for guild in bot.guilds:
        for ch_id, fn in [(CH_CREAR_DOC, publicar_embed_crear_doc),
                          (CH_CREAR_DOC_OLD, publicar_embed_crear_doc),
                          (CH_INFO_EDUCACION, publicar_embed_educacion)]:
            canal = guild.get_channel(ch_id)
            if canal:
                try:
                    msgs = [m async for m in canal.history(limit=3)]
                    embed_msgs = [m for m in msgs if m.embeds]
                    if not embed_msgs:
                        await fn(canal)
                except Exception:
                    pass


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Falta argumento: `{error.param.name}`")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ No tienes permisos para esto.")
    else:
        await ctx.send(f"❌ Error: {error}")


@bot.command(name="reenviar_embed")
@commands.has_permissions(administrator=True)
async def reenviar_embed(ctx, tipo: str = "crear_doc"):
    """[ADMIN] Reenvía un embed al canal correspondiente.
    Tipos: crear_doc | educacion | constitucion"""
    tipo = tipo.lower().replace("ó", "o").replace("á", "a")
    if tipo in ("crear_doc", "bienvenida", "personaje"):
        canal = ctx.guild.get_channel(CH_CREAR_DOC)
        if canal:
            await publicar_embed_crear_doc(canal)
            await ctx.send(f"✅ Embed de bienvenida reenviado a {canal.mention}.", delete_after=5)
        else:
            await ctx.send("❌ Canal no encontrado.")
    elif tipo in ("educacion", "estudio"):
        canal = ctx.guild.get_channel(CH_INFO_EDUCACION)
        if canal:
            await publicar_embed_educacion(canal)
            await ctx.send(f"✅ Embed de educación reenviado a {canal.mention}.", delete_after=5)
        else:
            await ctx.send("❌ Canal no encontrado.")
    elif tipo in ("constitucion"):
        canal = ctx.guild.get_channel(CH_CONSTITUCION)
        if canal:
            for emb_data in CONSTITUCION_EMBEDS:
                embed = discord.Embed(
                    title=emb_data["title"],
                    description=emb_data.get("description", ""),
                    color=emb_data["color"]
                )
                for name, value in emb_data.get("fields", []):
                    embed.add_field(name=name, value=value, inline=False)
                await canal.send(embed=embed)
                await asyncio.sleep(0.5)
            await ctx.send(f"✅ Constitución reenviada a {canal.mention}.", delete_after=5)
        else:
            await ctx.send("❌ Canal no encontrado.")
    else:
        await ctx.send(
            "Usa: `!reenviar_embed <tipo>`\n"
            "Tipos: `crear_doc` | `educacion` | `constitucion`"
        )


async def main():
    Path("data").mkdir(exist_ok=True)
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())