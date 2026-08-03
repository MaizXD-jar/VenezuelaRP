"""
cogs/npc.py — Sistema de NPCs: creación, control, acciones.
Con autocomplete en /npc_usar y generación de NPCs de ejemplo.
"""
import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from utils import db

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
    # CRIMEN ORGANIZADO
    {"nombre": "Nelson Domingo", "edad": 48, "trabajo": "Jefe de la Banda", "dinero": 50000.0,
     "fuerza": 9, "ubicacion": "petare", "tipo": "criminal"},
    {"nombre": "Marisol Domingo", "edad": 36, "trabajo": "Distribuidora Mayor", "dinero": 25000.0,
     "fuerza": 6, "ubicacion": "petare", "tipo": "criminal"},
    {"nombre": "Kevin", "edad": 29, "trabajo": "Sicario", "dinero": 3000.0,
     "fuerza": 10, "ubicacion": "petare", "tipo": "criminal"},
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
     "fuerza": 8, "ubicacion": "medellin", "tipo": "criminal"},
    {"nombre": "Agent Smith (DEA)", "edad": 38, "trabajo": "Agente DEA", "dinero": 5000.0,
     "fuerza": 8, "ubicacion": "miami", "tipo": "policia"},
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


class NPC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.npc_activo: dict[int, str] = {}  # admin_id: npc_id activo

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
        npc_id = nombre.lower().replace(" ", "_")
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

    # ── on_message: intercept mensajes del admin como NPC ─────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
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

    # ── /crear_npcs_ejemplo ────────────────────────────────────────────────────
    @app_commands.command(name="crear_npcs_ejemplo", description="[ADMIN] Crea 20 NPCs de ejemplo (policías, criminales, autoridades)")
    async def crear_npcs_ejemplo(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Solo administradores.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
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
            # Dar armas a policías y criminales
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

        await interaction.followup.send(
            f"✅ {creados} NPCs de ejemplo creados.\n"
            f"Incluye: policías CPNB, SEBIN, militares FANB, gobierno, criminales y sociedad civil.",
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