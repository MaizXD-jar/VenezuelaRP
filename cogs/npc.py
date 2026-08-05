"""
cogs/npc.py — Sistema de NPCs: creación, control, acciones.
Con autocomplete en /npc_usar y generación de NPCs de ejemplo.

Comandos de rol como NPC (todos [ADMIN]):
  /npc_usar   — te "posees" al NPC, tus mensajes normales salen como él
  /npc_hablar — el NPC dice algo puntual sin necesidad de tenerlo activo
  /npc_accion — el NPC hace una acción (*en cursiva*)
  /npc_viajar — el NPC viaja de verdad por el mapa (con su propio tiempo real,
                independiente de los viajes de los jugadores) y avisa por
                separado cuando SALE de su canal de origen y cuando LLEGA al
                canal de destino, igual que /viajar pero para NPCs.
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import asyncio
import time
import unicodedata
from utils import db
from utils import ia
from utils.mapa import SECTORES, get_tiempo, get_sector_de_canal, mejor_ruta, es_canal_casa, canal_con_sector

# Sistema de "responder" (reply de Discord) a un NPC/policía para hablarle
# directamente, como si estuvieras delante de él en el canal.
SYSTEM_NPC_CHAT = (
    "Interpretas a un personaje NPC en un servidor de roleplay de Discord "
    "ambientado en una Venezuela ficticia. Un jugador te acaba de responder "
    "(reply de Discord) a algo que dijiste o hiciste, así que te está "
    "hablando directamente. Responde SIEMPRE en español, en PRIMERA persona, "
    "en 1-3 frases, con la personalidad y el tono que corresponde a tu "
    "profesión (policía, criminal, funcionario, civil...). No repitas tu "
    "nombre. No inventes que el jugador dijo algo que no dijo. Nada de "
    "contenido sexual ni violencia gráfica explícita."
)


def _nombre_npc_de_embed(embed: discord.Embed) -> str | None:
    """Extrae el nombre del NPC del autor de un embed de acción/diálogo suyo.
    Soporta los formatos "[NPC] Nombre" (acciones) y "Nombre [Trabajo]"
    (diálogo/npc_hablar/npc_usar)."""
    if not embed.author or not embed.author.name:
        return None
    nombre = embed.author.name.strip()
    if nombre.startswith("[NPC] "):
        return nombre[len("[NPC] "):].strip() or None
    if "[" in nombre:
        return nombre.split("[")[0].strip() or None
    return nombre or None


def slug_npc(nombre: str, max_len: int = 30) -> str:
    """ID estable para un NPC a partir de su nombre.

    ANTES: se hacía nombre.lower().replace(" ", "_") sin quitar tildes/ñ, así
    que "Comisario Rafael Méndez" generaba el id "comisario_rafael_méndez"
    (con é literal). Esto rompía comparaciones y comandos escritos sin tilde,
    y hacía frágiles referencias cruzadas como "protege_a". Ahora se
    normalizan los acentos igual que en utils/propiedades._slug.
    """
    t = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    t = t.lower().replace(" ", "_")
    for ch in "'()":
        t = t.replace(ch, "")
    return t[:max_len]

METODOS_VIAJE = ["caminar", "metro", "autobus", "tren", "coche", "bicicleta", "avion"]
ICONOS_METODO = {"caminar": "🚶", "metro": "🚇", "autobus": "🚌", "tren": "🚂",
                 "coche": "🚗", "bicicleta": "🚲", "avion": "✈️"}

# Viajes de NPC en curso: npc_id -> dict(...). Deliberadamente SEPARADO del
# diccionario de viajes de jugadores (cogs/viaje.py) para que un NPC y un
# jugador que salgan a la misma hora lleguen en momentos distintos: cada uno
# tiene su propio cálculo de duración (con su propio "ruido" aleatorio) y su
# propio bucle de comprobación.
npc_viajes_activos: dict[str, dict] = {}

# ── 20 NPCs DE EJEMPLO (policías, autoridades, figuras importantes) ───────────
NPCS_EJEMPLO = [
    # POLICÍA CPNB
    {"nombre": "Comisario Rafael Méndez", "edad": 52, "trabajo": "Comisario CPNB", "dinero": 1200.0,
     "fuerza": 8, "ubicacion": "distrito-capital", "tipo": "policia"},
    {"nombre": "Sargento Yolanda Torres", "edad": 38, "trabajo": "Sargento CPNB", "dinero": 600.0,
     "fuerza": 7, "ubicacion": "petare", "tipo": "policia"},
    {"nombre": "Agente Carlos Blanco", "edad": 28, "trabajo": "Agente CPNB", "dinero": 300.0,
     "fuerza": 6, "ubicacion": "petare", "tipo": "policia"},
    {"nombre": "Inspector Gloria Ramírez", "edad": 44, "trabajo": "Inspectora CPNB", "dinero": 800.0,
     "fuerza": 7, "ubicacion": "las-mercedes", "tipo": "policia"},
    {"nombre": "Oficial Pedro Gutiérrez", "edad": 32, "trabajo": "Oficial CPNB", "dinero": 450.0,
     "fuerza": 6, "ubicacion": "miranda", "tipo": "policia"},
    # SEBIN / INTELIGENCIA
    {"nombre": "Director Hernán Salazar", "edad": 58, "trabajo": "Director SEBIN", "dinero": 5000.0,
     "fuerza": 9, "ubicacion": "distrito-capital", "tipo": "sebin"},
    {"nombre": "Agente Encubierto 'La Sombra'", "edad": 35, "trabajo": "Agente Encubierto SEBIN", "dinero": 2000.0,
     "fuerza": 8, "ubicacion": "petare", "tipo": "sebin"},
    # EJÉRCITO FANB
    {"nombre": "General Simón Álvarez", "edad": 62, "trabajo": "General FANB", "dinero": 8000.0,
     "fuerza": 10, "ubicacion": "distrito-capital", "tipo": "militar"},
    {"nombre": "Teniente Rodrigo Vargas", "edad": 30, "trabajo": "Teniente FANB", "dinero": 700.0,
     "fuerza": 9, "ubicacion": "23-de-enero", "tipo": "militar"},
    # GOBIERNO
    {"nombre": "Ministra Luisa Contreras", "edad": 49, "trabajo": "Ministra del Interior", "dinero": 15000.0,
     "fuerza": 5, "ubicacion": "distrito-capital", "tipo": "gobierno"},
    {"nombre": "Alcalde José Figueroa", "edad": 55, "trabajo": "Alcalde de Caracas", "dinero": 20000.0,
     "fuerza": 4, "ubicacion": "distrito-capital", "tipo": "gobierno"},
    # PRESIDENCIA Y ALTOS CARGOS (protegidos por escoltas del FANB, ver abajo)
    {"nombre": "Presidente Ramón Ibáñez Duarte", "edad": 61, "trabajo": "Presidente de la República", "dinero": 500000.0,
     "fuerza": 3, "ubicacion": "distrito-capital", "tipo": "presidente"},
    {"nombre": "Vicepresidenta Carmen Aguirre", "edad": 54, "trabajo": "Vicepresidenta Ejecutiva", "dinero": 180000.0,
     "fuerza": 3, "ubicacion": "distrito-capital", "tipo": "gobierno"},
    {"nombre": "Ministro Álvaro Bastidas", "edad": 57, "trabajo": "Ministro de Defensa", "dinero": 90000.0,
     "fuerza": 4, "ubicacion": "distrito-capital", "tipo": "gobierno"},
    # ESCOLTA PRESIDENCIAL (FANB) — "protege_a" apunta al npc_id que custodian
    {"nombre": "Capitán Escolta Freddy Rondón", "edad": 39, "trabajo": "Jefe de Escolta Presidencial (FANB)",
     "dinero": 2500.0, "fuerza": 9, "ubicacion": "distrito-capital", "tipo": "escolta",
     "protege_a": "presidente_ramon_ibanez_duarte"},
    {"nombre": "Sargento Escolta Wilmer Peña", "edad": 33, "trabajo": "Escolta Presidencial (FANB)",
     "dinero": 1200.0, "fuerza": 8, "ubicacion": "distrito-capital", "tipo": "escolta",
     "protege_a": "presidente_ramon_ibanez_duarte"},
    {"nombre": "Sargento Escolta Ana Beltrán", "edad": 31, "trabajo": "Escolta Presidencial (FANB)",
     "dinero": 1200.0, "fuerza": 8, "ubicacion": "distrito-capital", "tipo": "escolta",
     "protege_a": "presidente_ramon_ibanez_duarte"},
    # CRIMEN ORGANIZADO — "banda" marca la facción: bandas distintas en el
    # mismo sector pueden acabar a tiros (ver npc_vida.py, eventos_npc_npc).
    {"nombre": "Nelson Domingo", "edad": 48, "trabajo": "Jefe de la Banda", "dinero": 50000.0,
     "fuerza": 9, "ubicacion": "petare", "tipo": "criminal", "banda": "tren_de_petare", "vehiculos": ["carro_lujoso"]},
    {"nombre": "Marisol Domingo", "edad": 36, "trabajo": "Distribuidora Mayor", "dinero": 25000.0,
     "fuerza": 6, "ubicacion": "petare", "tipo": "criminal", "banda": "tren_de_petare"},
    {"nombre": "Kevin", "edad": 29, "trabajo": "Sicario", "dinero": 3000.0,
     "fuerza": 10, "ubicacion": "petare", "tipo": "criminal", "banda": "tren_de_petare", "vehiculos": ["moto_basica"]},
    {"nombre": "Wilson Paredes", "edad": 44, "trabajo": "Jefe de Banda Rival", "dinero": 40000.0,
     "fuerza": 9, "ubicacion": "23-de-enero", "tipo": "criminal", "banda": "colectivo_23", "vehiculos": ["carro_mediano"]},
    {"nombre": "Estefany Lugo", "edad": 27, "trabajo": "Sicaria", "dinero": 4000.0,
     "fuerza": 9, "ubicacion": "23-de-enero", "tipo": "criminal", "banda": "colectivo_23", "vehiculos": ["moto_basica"]},
    # SOCIEDAD CIVIL
    {"nombre": "Dr. Marcos Herrera", "edad": 45, "trabajo": "Médico Jefe Hospital Vargas", "dinero": 3000.0,
     "fuerza": 3, "ubicacion": "distrito-capital", "tipo": "civil"},
    {"nombre": "Periodista Ana Flores", "edad": 33, "trabajo": "Periodista de Investigación", "dinero": 800.0,
     "fuerza": 3, "ubicacion": "miranda", "tipo": "civil"},
    {"nombre": "Don Eduardo el Bodeguero", "edad": 60, "trabajo": "Bodeguero", "dinero": 500.0,
     "fuerza": 4, "ubicacion": "petare", "tipo": "civil"},
    {"nombre": "Padre Miguel Ángel", "edad": 55, "trabajo": "Sacerdote", "dinero": 200.0,
     "fuerza": 2, "ubicacion": "petare", "tipo": "civil"},
    # INTERNACIONAL
    {"nombre": "Diego Escobar (Colombiano)", "edad": 40, "trabajo": "Traficante Internacional", "dinero": 100000.0,
     "fuerza": 8, "ubicacion": "medellin", "tipo": "criminal", "banda": "cartel_medellin", "vehiculos": ["carro_lujoso"]},
    {"nombre": "Agent Smith (DEA)", "edad": 38, "trabajo": "Agente DEA", "dinero": 5000.0,
     "fuerza": 8, "ubicacion": "miami", "tipo": "policia"},
    # ABOGADOS (de oficio, gratis, y privados, de pago — ver cogs/justicia.py)
    {"nombre": "Defensora Pública Marisela Ortiz", "edad": 41, "trabajo": "Defensora Pública de Oficio", "dinero": 800.0,
     "fuerza": 2, "ubicacion": "distrito-capital", "tipo": "abogado", "categoria": "publico", "tarifa": 0, "nivel": 4},
    {"nombre": "Defensor Público Jesús Rangel", "edad": 46, "trabajo": "Defensor Público de Oficio", "dinero": 800.0,
     "fuerza": 2, "ubicacion": "distrito-capital", "tipo": "abogado", "categoria": "publico", "tarifa": 0, "nivel": 4},
    {"nombre": "Dra. Valentina Roa", "edad": 37, "trabajo": "Abogada Penalista Privada", "dinero": 40000.0,
     "fuerza": 2, "ubicacion": "las-mercedes", "tipo": "abogado", "categoria": "privado", "tarifa": 500, "nivel": 7},
    {"nombre": "Dr. Ignacio Salcedo", "edad": 52, "trabajo": "Abogado Penalista Privado (élite)", "dinero": 150000.0,
     "fuerza": 2, "ubicacion": "las-mercedes", "tipo": "abogado", "categoria": "privado", "tarifa": 2000, "nivel": 9},
    {"nombre": "Juez Horacio Fermín", "edad": 60, "trabajo": "Juez del Tribunal Supremo", "dinero": 25000.0,
     "fuerza": 1, "ubicacion": "distrito-capital", "tipo": "juez", "nivel": 8},
]


async def _get_npcs_choices(interaction: discord.Interaction, current: str):
    """Autocomplete para NPCs."""
    todos = await db.all("npcs")
    choices = []
    for npc_id, data in todos.items():
        nombre = data.get("nombre", npc_id)
        if current.lower() in nombre.lower() or current.lower() in npc_id.lower():
            choices.append(app_commands.Choice(name=nombre[:100], value=npc_id))
        if len(choices) >= 25:
            break
    return choices


async def _get_destinos_choices_npc(interaction: discord.Interaction, current: str):
    """Autocomplete de destinos para /npc_viajar (canales del mapa + casas)."""
    cur = (current or "").lower().strip()
    resultados = []
    for sector_key, sec in SECTORES.items():
        emoji = sec.get("emoji", "")
        for canal_nombre in sec.get("canales", {}):
            if cur and cur not in canal_nombre.lower() and cur not in sector_key.lower():
                continue
            resultados.append(app_commands.Choice(name=f"{emoji} {canal_nombre}"[:100], value=canal_nombre))
    if interaction.guild:
        for canal in interaction.guild.text_channels:
            if not canal.name.startswith("casa-"):
                continue
            if cur and cur not in canal.name.lower():
                continue
            resultados.append(app_commands.Choice(name=f"🏠 {canal.name}"[:100], value=canal.name))
    return resultados[:25]


def _canal_de_sector_sync(guild: discord.Guild, sector: str):
    """Devuelve un canal público real donde narrar la vida del sector (calle,
    avenida, barrio...). Se usa para publicar salidas/llegadas de NPCs cuando
    no tienen un canal_actual concreto asignado."""
    sec = SECTORES.get(sector, {})
    candidatos = [n for n, i in sec.get("canales", {}).items()
                  if i.get("tipo") in ("calle", "avenida", "general", "barrio")]
    for nombre in candidatos:
        canal = discord.utils.get(guild.text_channels, name=nombre)
        if canal:
            return canal
    for nombre in sec.get("canales", {}):
        canal = discord.utils.get(guild.text_channels, name=nombre)
        if canal:
            return canal
    return None


class NPC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.npc_activo: dict[int, str] = {}  # admin_id: npc_id activo

    def start_tasks(self):
        if not self.check_llegadas_npc.is_running():
            self.check_llegadas_npc.start()

    @tasks.loop(seconds=15)
    async def check_llegadas_npc(self):
        """Bucle independiente del de jugadores (cogs/viaje.py): revisa cada
        15s si algún NPC en viaje ya debería haber llegado a su destino."""
        now = time.time()
        llegados = [nid for nid, v in list(npc_viajes_activos.items()) if now >= v["llegada_ts"]]
        for npc_id in llegados:
            viaje = npc_viajes_activos.pop(npc_id, None)
            if viaje:
                await self._procesar_llegada_npc(npc_id, viaje)

    async def _procesar_llegada_npc(self, npc_id: str, viaje: dict):
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return
        data = await db.get("npcs", npc_id)
        if not data:
            return

        sector_destino = viaje["sector_destino"]
        canal_destino_nombre = viaje["canal_destino"]
        sec_info = SECTORES.get(sector_destino, {})

        await db.update("npcs", npc_id, {
            "ubicacion": sector_destino,
            "canal_actual": canal_destino_nombre,
        })

        canal_discord = discord.utils.get(guild.text_channels, name=canal_destino_nombre)
        if not canal_discord:
            return

        canal_info = sec_info.get("canales", {}).get(canal_destino_nombre, {})
        c_emoji = canal_info.get("emoji", "📍")
        display = sec_info.get("display", sector_destino)
        peligro = canal_info.get("peligro", sec_info.get("peligro", 1))
        icono_metodo = ICONOS_METODO.get(viaje["metodo"], "🚀")

        embed = discord.Embed(
            title=f"{c_emoji} [NPC] {data.get('nombre','?')} llegó a {canal_con_sector(canal_destino_nombre, sector_destino)}",
            description=f"**Sector:** {sec_info.get('emoji','')} {display} ({sector_destino}) | "
                        f"**Método:** {icono_metodo} {viaje['metodo']}",
            color=discord.Color.dark_teal()
        )
        if peligro >= 4:
            embed.add_field(name="⚠️ ZONA PELIGROSA", value="Ten cuidado.", inline=False)
        try:
            await canal_discord.send(embed=embed)
        except Exception:
            pass

    def _es_admin(self, ctx_or_member) -> bool:
        if isinstance(ctx_or_member, commands.Context):
            return ctx_or_member.author.guild_permissions.manage_guild or ctx_or_member.author.guild_permissions.administrator
        return ctx_or_member.guild_permissions.manage_guild or ctx_or_member.guild_permissions.administrator

    # ── Gestión de NPCs (prefix) ───────────────────────────────────────────────
    @commands.command(name="npc")
    async def npc_cmd(self, ctx, subcomando: str, *args):
        """Gestión de NPCs. Sub: crear, lista, info, borrar"""
        if subcomando == "crear":
            await self._npc_crear(ctx, args)
        elif subcomando == "lista":
            await self._npc_lista(ctx)
        elif subcomando == "info":
            await self._npc_info_prefix(ctx, args)
        elif subcomando == "borrar":
            await self._npc_borrar(ctx, args)
        else:
            await ctx.send("❌ Subcomandos: `crear`, `lista`, `info`, `borrar`")

    async def _npc_crear(self, ctx, args):
        if not self._es_admin(ctx):
            return await ctx.send("❌ Solo admins pueden crear NPCs.")
        if len(args) < 5:
            return await ctx.send("❌ Uso: `!npc crear <nombre> <edad> <trabajo> <dinero> <fuerza>`")
        nombre = args[0]
        try:
            edad = int(args[1])
            dinero = float(args[3])
            fuerza = int(args[4])
        except:
            return await ctx.send("❌ Edad, dinero y fuerza deben ser números.")
        trabajo = args[2]
        npc_id = slug_npc(nombre)
        existente = await db.get("npcs", npc_id)
        if existente:
            return await ctx.send(f"❌ Ya existe un NPC llamado `{nombre}`.")
        npc_data = {
            "nombre": nombre, "edad": edad, "trabajo": trabajo, "dinero": dinero,
            "stats": {
                "hp": 100, "hp_max": 100, "fuerza": fuerza,
                "agilidad": random.randint(3, 10), "resistencia": random.randint(3, 10),
                "tecnica": random.randint(1, 8), "inteligencia": random.randint(3, 12),
            },
            "inventario": {}, "ubicacion": "distrito-capital",
            "vivo": True, "imagen": None, "creado_por": ctx.author.id,
        }
        await db.set("npcs", npc_id, npc_data)
        embed = discord.Embed(title=f"✅ NPC Creado: {nombre}", color=discord.Color.teal())
        embed.add_field(name="Edad", value=str(edad), inline=True)
        embed.add_field(name="Trabajo", value=trabajo, inline=True)
        embed.add_field(name="Dinero", value=f"${dinero:.2f}", inline=True)
        embed.set_footer(text=f"ID: {npc_id} | Usa /npc_usar {nombre}")
        await ctx.send(embed=embed)

    async def _npc_lista(self, ctx):
        npcs = await db.all("npcs")
        if not npcs:
            return await ctx.send("No hay NPCs creados.")
        embed = discord.Embed(title="🤖 Lista de NPCs", color=discord.Color.teal())
        for npc_id, data in list(npcs.items())[:20]:
            hp = data["stats"]["hp"]
            hp_max = data["stats"]["hp_max"]
            status = "✅ Vivo" if data.get("vivo") else "💀 Muerto"
            embed.add_field(
                name=f"{data['nombre']} ({data['trabajo']})",
                value=f"{status} | HP: {hp}/{hp_max} | 📍 {data.get('ubicacion', '?')}",
                inline=False
            )
        await ctx.send(embed=embed)

    async def _npc_info_prefix(self, ctx, args):
        if not args:
            return await ctx.send("❌ Uso: `!npc info <nombre>`")
        npc_id = "_".join(args).lower().replace(" ", "_")
        data = await db.get("npcs", npc_id)
        if not data:
            todos = await db.all("npcs")
            data = next((v for v in todos.values() if "_".join(args).lower() in v.get("nombre", "").lower()), None)
        if not data:
            return await ctx.send(f"❌ NPC `{' '.join(args)}` no encontrado.")
        await ctx.send(embed=self._build_npc_embed(data))

    async def _npc_borrar(self, ctx, args):
        if not self._es_admin(ctx):
            return await ctx.send("❌ Solo admins.")
        if not args:
            return await ctx.send("❌ Uso: `!npc borrar <nombre>`")
        npc_id = args[0].lower().replace(" ", "_")
        await db.delete("npcs", npc_id)
        await ctx.send(f"✅ NPC `{args[0]}` eliminado.")

    def _build_npc_embed(self, data: dict) -> discord.Embed:
        embed = discord.Embed(title=f"🤖 NPC: {data['nombre']}", color=discord.Color.teal())
        embed.add_field(name="Edad", value=str(data.get("edad", "?")), inline=True)
        embed.add_field(name="Trabajo", value=data.get("trabajo", "?"), inline=True)
        embed.add_field(name="Dinero", value=f"${data.get('dinero', 0):.2f}", inline=True)
        embed.add_field(name="Ubicación", value=data.get("ubicacion", "?"), inline=True)
        embed.add_field(name="Estado", value="✅ Vivo" if data.get("vivo", True) else "💀 Muerto", inline=True)
        if data.get("tipo_familiar"):
            embed.add_field(name="Rol Familiar", value=f"{data['tipo_familiar'].title()} de {data.get('es_padre_de','?')}", inline=True)
        stats = data.get("stats", {})
        stats_txt = "\n".join([f"**{k.title()}**: {v}" for k, v in stats.items()])
        embed.add_field(name="📊 Stats", value=stats_txt or "—", inline=False)
        inv = data.get("inventario", {})
        if inv:
            embed.add_field(name="🎒 Inventario", value=", ".join(f"{v}x {k}" for k, v in inv.items())[:200], inline=False)
        if data.get("imagen"):
            embed.set_thumbnail(url=data["imagen"])
        embed.set_footer(text=f"ID: {data['nombre'].lower().replace(' ', '_')}")
        return embed

    # ── /npc_info ─────────────────────────────────────────────────────────────
    @app_commands.command(name="npc_info", description="Muestra información de un NPC")
    @app_commands.describe(nombre="Nombre del NPC")
    @app_commands.autocomplete(nombre=_get_npcs_choices)
    async def npc_info_slash(self, interaction: discord.Interaction, nombre: str):
        data = await db.get("npcs", nombre)
        if not data:
            todos = await db.all("npcs")
            data = next((v for v in todos.values() if nombre.lower() in v.get("nombre", "").lower()), None)
        if not data:
            return await interaction.response.send_message(f"❌ NPC `{nombre}` no encontrado.", ephemeral=True)
        await interaction.response.send_message(embed=self._build_npc_embed(data))

    # ── /npc_usar — con autocomplete ──────────────────────────────────────────
    @app_commands.command(name="npc_usar", description="[ADMIN] Empieza a hablar como un NPC. Se activa automáticamente.")
    @app_commands.describe(nombre="Nombre del NPC a controlar")
    @app_commands.autocomplete(nombre=_get_npcs_choices)
    async def npc_usar_slash(self, interaction: discord.Interaction, nombre: str):
        if not self._es_admin(interaction.user):
            return await interaction.response.send_message("❌ Solo admins.", ephemeral=True)

        # Buscar por ID o nombre
        data = await db.get("npcs", nombre)
        if not data:
            todos = await db.all("npcs")
            for npc_id, npc_data in todos.items():
                if nombre.lower() in npc_data.get("nombre", "").lower():
                    nombre = npc_id
                    data = npc_data
                    break

        if not data:
            return await interaction.response.send_message(f"❌ NPC `{nombre}` no encontrado.", ephemeral=True)

        self.npc_activo[interaction.user.id] = nombre
        await interaction.response.send_message(
            f"✅ Ahora hablas como **{data['nombre']}** ({data['trabajo']}).\n"
            f"Escribe normalmente y tus mensajes saldrán como el NPC.\n"
            f"Usa `/npc_desusar` cuando quieras salir del personaje.",
            ephemeral=True
        )

    # ── /npc_desusar ──────────────────────────────────────────────────────────
    @app_commands.command(name="npc_desusar", description="[ADMIN] Deja de hablar como el NPC activo")
    async def npc_desusar_slash(self, interaction: discord.Interaction):
        if interaction.user.id in self.npc_activo:
            npc_id = self.npc_activo.pop(interaction.user.id)
            data = await db.get("npcs", npc_id)
            nombre = data.get("nombre", npc_id) if data else npc_id
            await interaction.response.send_message(f"✅ Dejaste de controlar a **{nombre}**.", ephemeral=True)
        else:
            await interaction.response.send_message("ℹ️ No tienes ningún NPC activo.", ephemeral=True)

    async def _intentar_responder_npc(self, message: discord.Message) -> bool:
        """Si el jugador usa "Responder" (reply de Discord) sobre un mensaje de
        un NPC (acción, diálogo, o un policía patrullando), lo trata como si
        le estuviera hablando directamente: el NPC contesta en personaje,
        siempre que siga vivo y siga estando en ese mismo sector/canal.
        Devuelve True si se manejó la respuesta (para no seguir procesando el
        mensaje de ninguna otra forma)."""
        if not message.reference:
            return False
        ref = message.reference.resolved
        if ref is None:
            try:
                ref = await message.channel.fetch_message(message.reference.message_id)
            except Exception:
                return False
        if not ref or not ref.author.bot or ref.author.id != self.bot.user.id or not ref.embeds:
            return False

        nombre_npc = _nombre_npc_de_embed(ref.embeds[0])
        if not nombre_npc:
            return False

        npcs = await db.all("npcs")
        npc_id = None
        npc = None
        nombre_lower = nombre_npc.lower()
        for nid, n in npcs.items():
            if n.get("nombre", "").lower() == nombre_lower:
                npc_id, npc = nid, n
                break
        if not npc:
            for nid, n in npcs.items():
                if nombre_lower in n.get("nombre", "").lower():
                    npc_id, npc = nid, n
                    break
        if not npc or npc.get("muerto") or npc.get("arrestado_npc"):
            return False

        # El NPC tiene que seguir "aquí": mismo sector que el canal donde
        # respondiste (y no estar en tránsito hacia otro sitio).
        sector_canal = get_sector_de_canal(message.channel.name)
        if not sector_canal or npc.get("ubicacion") != sector_canal:
            return False
        if npc_id in npc_viajes_activos:
            return False

        fallback = f"*{npc['nombre']} te mira, pero no dice nada por ahora.*"
        texto = fallback
        if ia.hay_ia():
            prompt = (
                f"Personaje: {npc['nombre']}, {npc.get('edad','?')} años, "
                f"profesión: {npc.get('trabajo','?')} (tipo: {npc.get('tipo','civil')}).\n"
                f"Un jugador te responde/habla: \"{message.content}\"\n"
                f"Responde en personaje, en primera persona, 1-3 frases."
            )
            texto_ia, _ = await ia.generar(SYSTEM_NPC_CHAT, prompt, max_tokens=150, timeout_seg=20)
            texto = texto_ia or fallback

        embed = discord.Embed(description=texto, color=discord.Color.teal())
        if npc.get("imagen"):
            embed.set_author(name=f"{npc['nombre']} [{npc.get('trabajo','?')}]", icon_url=npc["imagen"])
        else:
            embed.set_author(name=f"{npc['nombre']} [{npc.get('trabajo','?')}]")
        try:
            await message.reply(embed=embed, mention_author=False)
        except Exception:
            await message.channel.send(embed=embed)
        return True

    # ── on_message: intercept mensajes del admin como NPC ─────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return

        # "Responder" (reply de Discord) a un NPC/policía = hablarle directamente.
        if message.reference and not (message.content.startswith("!") or message.content.startswith("/")):
            manejado = await self._intentar_responder_npc(message)
            if manejado:
                return

        if message.author.id not in self.npc_activo:
            return
        if message.content.startswith("!") or message.content.startswith("/"):
            return

        npc_id = self.npc_activo[message.author.id]
        data = await db.get("npcs", npc_id)
        if not data:
            return

        try:
            await message.delete()
        except:
            pass

        embed = discord.Embed(description=message.content, color=discord.Color.teal())
        if data.get("imagen"):
            embed.set_author(name=f"{data['nombre']} [{data['trabajo']}]", icon_url=data["imagen"])
        else:
            embed.set_author(name=f"{data['nombre']} [{data['trabajo']}]")
        await message.channel.send(embed=embed)

    # ── /npc_hablar (alternativa slash) ──────────────────────────────────────
    @app_commands.command(name="npc_hablar", description="[ADMIN] El NPC dice algo específico")
    @app_commands.describe(texto="Lo que dirá el NPC")
    async def npc_hablar_slash(self, interaction: discord.Interaction, texto: str):
        if not self._es_admin(interaction.user):
            return await interaction.response.send_message("❌ Solo admins.", ephemeral=True)
        npc_id = self.npc_activo.get(interaction.user.id)
        if not npc_id:
            return await interaction.response.send_message(
                "❌ No tienes NPC activo. Usa `/npc_usar <nombre>` primero.", ephemeral=True
            )
        data = await db.get("npcs", npc_id)
        if not data:
            return await interaction.response.send_message("❌ NPC no encontrado.", ephemeral=True)
        embed = discord.Embed(description=texto, color=discord.Color.teal())
        if data.get("imagen"):
            embed.set_author(name=f"{data['nombre']} [{data['trabajo']}]", icon_url=data["imagen"])
        else:
            embed.set_author(name=f"{data['nombre']} [{data['trabajo']}]")
        await interaction.response.send_message(embed=embed)

    # ── /npc_accion ───────────────────────────────────────────────────────────
    @app_commands.command(name="npc_accion", description="[ADMIN] El NPC hace una acción (*en cursiva*)")
    @app_commands.describe(nombre="Nombre del NPC", accion="Descripción de la acción")
    @app_commands.autocomplete(nombre=_get_npcs_choices)
    async def npc_accion_slash(self, interaction: discord.Interaction, nombre: str, accion: str):
        if not self._es_admin(interaction.user):
            return await interaction.response.send_message("❌ Solo admins.", ephemeral=True)
        data = await db.get("npcs", nombre)
        if not data:
            todos = await db.all("npcs")
            data = next((v for v in todos.values() if nombre.lower() in v.get("nombre", "").lower()), None)
        if not data:
            return await interaction.response.send_message(f"❌ NPC `{nombre}` no encontrado.", ephemeral=True)
        embed = discord.Embed(description=f"*{accion}*", color=discord.Color.greyple())
        embed.set_author(name=f"[NPC] {data['nombre']}")
        await interaction.response.send_message(embed=embed)

    # ── /npc_viajar ───────────────────────────────────────────────────────────
    @app_commands.command(name="npc_viajar", description="[ADMIN] Envía a un NPC de viaje real por el mapa")
    @app_commands.describe(nombre="NPC que viaja", destino="Canal/sector de destino", metodo="Método de transporte")
    @app_commands.autocomplete(nombre=_get_npcs_choices, destino=_get_destinos_choices_npc)
    @app_commands.choices(metodo=[app_commands.Choice(name=f"{ICONOS_METODO[m]} {m}", value=m) for m in METODOS_VIAJE])
    async def npc_viajar_slash(self, interaction: discord.Interaction, nombre: str, destino: str, metodo: str = "caminar"):
        if not self._es_admin(interaction.user):
            return await interaction.response.send_message("❌ Solo admins.", ephemeral=True)

        npc_id = nombre
        data = await db.get("npcs", npc_id)
        if not data:
            todos = await db.all("npcs")
            for nid, ndata in todos.items():
                if nombre.lower() in ndata.get("nombre", "").lower():
                    npc_id, data = nid, ndata
                    break
        if not data:
            return await interaction.response.send_message(f"❌ NPC `{nombre}` no encontrado.", ephemeral=True)
        if data.get("muerto"):
            return await interaction.response.send_message(f"❌ **{data['nombre']}** está fallecido.", ephemeral=True)
        if npc_id in npc_viajes_activos:
            return await interaction.response.send_message(f"❌ **{data['nombre']}** ya está de viaje.", ephemeral=True)

        guild = interaction.guild
        destino = destino.strip().lower().replace(" ", "-")

        sector_destino = get_sector_de_canal(destino)
        if destino in SECTORES:
            sector_destino = destino
            canales_sec = list(SECTORES[destino]["canales"].keys())
            destino = canales_sec[0] if canales_sec else destino
        elif not sector_destino:
            canal_obj = discord.utils.get(guild.text_channels, name=destino)
            if canal_obj:
                sector_destino = get_sector_de_canal(canal_obj.name)
                destino = canal_obj.name
        if not sector_destino:
            return await interaction.response.send_message(f"❌ Canal/sector `{destino}` no encontrado en el mapa.", ephemeral=True)
        if es_canal_casa(destino) and not discord.utils.get(guild.text_channels, name=destino):
            return await interaction.response.send_message(f"❌ La casa `{destino}` no tiene canal creado en este servidor.", ephemeral=True)

        sector_origen = data.get("ubicacion", "petare")
        if sector_origen not in SECTORES:
            sector_origen = "petare"
        canal_origen_nombre = data.get("canal_actual")
        canal_origen = None
        if canal_origen_nombre:
            canal_origen = discord.utils.get(guild.text_channels, name=canal_origen_nombre)
        if not canal_origen:
            canal_origen = _canal_de_sector_sync(guild, sector_origen)
            canal_origen_nombre = canal_origen.name if canal_origen else canal_origen_nombre

        # Duración: mismo mapa/rutas que /viajar, pero con su PROPIO ruido
        # aleatorio, así que un NPC y un jugador que salgan juntos NO llegan
        # a la vez — cada viaje tiene su propio reloj.
        ruta_escalas = None
        if sector_origen == sector_destino:
            minutos = random.randint(4, 14)
        else:
            minutos = get_tiempo(sector_origen, sector_destino, metodo)
            if minutos == 0:
                ruta_escalas = mejor_ruta(sector_origen, sector_destino)
                if not ruta_escalas or not ruta_escalas["pasos"]:
                    return await interaction.response.send_message(
                        f"❌ No hay ruta de `{sector_origen}` a `{sector_destino}` (ni con escalas).", ephemeral=True)
                minutos = ruta_escalas["total_minutos"]
        minutos = max(1, round(minutos * random.uniform(0.75, 1.35)))
        segundos = min(minutos * 60, 300)

        llegada_ts = time.time() + segundos
        npc_viajes_activos[npc_id] = {
            "canal_destino": destino,
            "sector_destino": sector_destino,
            "llegada_ts": llegada_ts,
            "metodo": metodo,
        }
        await db.update("npcs", npc_id, {"ubicacion": sector_origen, "canal_actual": canal_origen_nombre})

        icono = ICONOS_METODO.get(metodo, "🚀")
        sec_origen_info = SECTORES.get(sector_origen, {})
        sec_destino_info = SECTORES.get(sector_destino, {})

        # Aviso de SALIDA en el canal de origen (independiente del de llegada)
        if canal_origen:
            embed_salida = discord.Embed(
                description=f"*🚶 **{data['nombre']}** sale de "
                            f"**{sec_origen_info.get('display', sector_origen)} ({sector_origen})** "
                            f"rumbo a **{canal_con_sector(destino, sector_destino)}** "
                            f"— {icono} {metodo}, ~{minutos} min.*",
                color=discord.Color.dark_teal()
            )
            try:
                await canal_origen.send(embed=embed_salida)
            except Exception:
                pass

        # ── Escolta: si el NPC es un protegido (presidente, ministros...),
        # sus escoltas del FANB viajan CON él, al mismo destino. No van
        # exactamente al mismo segundo (cada uno con su pequeño margen), pero
        # nunca lo dejan solo llegando a un sitio peligroso.
        escoltas_movidas = []
        todos_npcs = await db.all("npcs")
        for eid, edata in todos_npcs.items():
            if edata.get("protege_a") == npc_id and not edata.get("muerto") and eid not in npc_viajes_activos:
                seg_escolta = min(300, max(10, segundos + random.randint(-15, 30)))
                npc_viajes_activos[eid] = {
                    "canal_destino": destino,
                    "sector_destino": sector_destino,
                    "llegada_ts": time.time() + seg_escolta,
                    "metodo": metodo,
                }
                await db.update("npcs", eid, {"ubicacion": sector_origen, "canal_actual": canal_origen_nombre})
                escoltas_movidas.append(edata.get("nombre", eid))

        desc = (
            f"**NPC:** {data['nombre']}\n"
            f"**Destino:** {sec_destino_info.get('emoji','')} `{canal_con_sector(destino, sector_destino)}`\n"
            f"**Método:** {icono} {metodo}\n"
            f"**Duración estimada:** ~{minutos} min (real, con su propio bucle — no llega a la vez que un jugador)"
        )
        embed = discord.Embed(title=f"{icono} Viaje de NPC iniciado", description=desc, color=discord.Color.blue())
        if ruta_escalas and ruta_escalas["pasos"]:
            pasos_txt = " → ".join(f"{ICONOS_METODO.get(m,'🚀')} {hasta}" for _, hasta, m, _ in ruta_escalas["pasos"])
            embed.add_field(name="🗺️ Ruta con escalas", value=f"{sector_origen} → {pasos_txt}", inline=False)
        if escoltas_movidas:
            embed.add_field(name="🪖 Escolta acompañando", value=", ".join(escoltas_movidas), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /crear_npcs_ejemplo ────────────────────────────────────────────────────
    @app_commands.command(name="crear_npcs_ejemplo", description="[ADMIN] Crea 20 NPCs de ejemplo (policías, criminales, autoridades)")
    async def crear_npcs_ejemplo(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Solo administradores.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        creados = 0
        for npc_template in NPCS_EJEMPLO:
            nombre = npc_template["nombre"]
            npc_id = slug_npc(nombre)
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
            if npc_template.get("protege_a"):
                npc_data["protege_a"] = npc_template["protege_a"]
            for campo in ("categoria", "tarifa", "nivel", "banda", "vehiculos"):
                if campo in npc_template:
                    npc_data[campo] = npc_template[campo]
            # Dar armas a policías, criminales, escoltas y militares
            if npc_template.get("tipo") == "policia":
                npc_data["inventario"]["glock_17"] = 1
                npc_data["inventario"]["esposas"] = 1
            elif npc_template.get("tipo") == "criminal":
                npc_data["inventario"]["ak47" if fuerza >= 9 else "glock_17"] = 1
            elif npc_template.get("tipo") in ("sebin", "militar"):
                npc_data["inventario"]["m4_carbine"] = 1
                npc_data["inventario"]["chaleco_antibalas"] = 1
            elif npc_template.get("tipo") == "escolta":
                npc_data["inventario"]["m4_carbine"] = 1
                npc_data["inventario"]["chaleco_antibalas"] = 1
                npc_data["inventario"]["radio_portatil"] = 1
            await db.set("npcs", npc_id, npc_data)
            creados += 1

        await interaction.followup.send(
            f"✅ {creados} NPCs de ejemplo creados.\n"
            f"Incluye: policías CPNB, SEBIN, militares FANB, gobierno (con Presidente y "
            f"Vicepresidenta), escolta presidencial del FANB, criminales y sociedad civil.",
            ephemeral=True
        )

    # ── Prefix aliases ────────────────────────────────────────────────────────
    @commands.command(name="npcusar")
    async def npcusar(self, ctx, *, nombre: str):
        if not self._es_admin(ctx):
            return await ctx.send("❌ Solo admins.")
        npc_id = nombre.lower().replace(" ", "_")
        data = await db.get("npcs", npc_id)
        if not data:
            todos = await db.all("npcs")
            for k, v in todos.items():
                if nombre.lower() in v.get("nombre", "").lower():
                    npc_id = k
                    data = v
                    break
        if not data:
            return await ctx.send(f"❌ NPC `{nombre}` no encontrado.")
        self.npc_activo[ctx.author.id] = npc_id
        await ctx.send(f"✅ Ahora hablas como **{data['nombre']}**. Escribe normalmente. `!npcdesactivar` para salir.", delete_after=10)

    @commands.command(name="npcdesactivar")
    async def npcdesactivar(self, ctx):
        if ctx.author.id in self.npc_activo:
            npc_id = self.npc_activo.pop(ctx.author.id)
            await ctx.send(f"✅ Saliste del control de `{npc_id}`.", delete_after=5)
        else:
            await ctx.send("No tienes NPC activo.", delete_after=5)

    @commands.command(name="npcimagen")
    async def npcimagen(self, ctx, nombre: str, url: str):
        if not self._es_admin(ctx):
            return await ctx.send("❌ Solo admins.")
        npc_id = nombre.lower().replace(" ", "_")
        data = await db.get("npcs", npc_id)
        if not data:
            return await ctx.send(f"❌ NPC `{nombre}` no encontrado.")
        await db.update("npcs", npc_id, {"imagen": url})
        await ctx.send(f"✅ Imagen de **{nombre}** actualizada.")

    @commands.command(name="npcmover")
    async def npcmover(self, ctx, nombre: str, *, sector: str):
        if not self._es_admin(ctx):
            return await ctx.send("❌ Solo admins.")
        npc_id = nombre.lower().replace(" ", "_")
        data = await db.get("npcs", npc_id)
        if not data:
            return await ctx.send(f"❌ NPC `{nombre}` no encontrado.")
        await db.update("npcs", npc_id, {"ubicacion": sector.lower()})
        await ctx.send(f"✅ **{nombre}** movido a `{sector}`.")

    @commands.command(name="npcaccion")
    async def npcaccion(self, ctx, nombre: str, *, accion: str):
        if not self._es_admin(ctx):
            return await ctx.send("❌ Solo admins.")
        npc_id = nombre.lower().replace(" ", "_")
        data = await db.get("npcs", npc_id)
        if not data:
            return await ctx.send(f"❌ NPC `{nombre}` no encontrado.")
        try:
            await ctx.message.delete()
        except:
            pass
        embed = discord.Embed(description=f"*{accion}*", color=discord.Color.greyple())
        embed.set_author(name=f"[NPC] {data['nombre']}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(NPC(bot))