import discord
from discord.ext import commands
from discord import app_commands
import json
import random
from utils import db
from utils.mapa import SECTORES, get_sector_de_canal


async def _autocomplete_ubicacion(interaction: discord.Interaction, current: str):
    """Autocompletado de destinos para /forzar_ubicacion: sectores, canales del
    mapa y canales de casas existentes en el servidor."""
    cur = (current or "").lower().strip()
    empiezan, contienen = [], []

    for sector_key, sec in SECTORES.items():
        etiqueta = f"📍 {sector_key} (sector)"[:100]
        ch = app_commands.Choice(name=etiqueta, value=sector_key)
        if not cur or sector_key.lower().startswith(cur):
            empiezan.append(ch)
        elif cur in sector_key.lower():
            contienen.append(ch)

        for canal_nombre in sec.get("canales", {}):
            ch2 = app_commands.Choice(name=f"{sec.get('emoji','')} {canal_nombre}"[:100], value=canal_nombre)
            if not cur:
                contienen.append(ch2)
            elif canal_nombre.lower().startswith(cur):
                empiezan.append(ch2)
            elif cur in canal_nombre.lower():
                contienen.append(ch2)

    if interaction.guild:
        for canal in interaction.guild.text_channels:
            if not canal.name.startswith("casa-"):
                continue
            if cur and cur not in canal.name.lower():
                continue
            contienen.append(app_commands.Choice(name=f"🏠 {canal.name}"[:100], value=canal.name))

    return (empiezan + contienen)[:25]


# ── IDs ───────────────────────────────────────────────────────────────────────
CH_PERSONAJES_ACEPTADOS = 1359320812003393567
CH_MUERTOS              = 1359320811420520613
CH_MAS_BUSCADOS         = 1369438636260724856
CH_POLICIA_AVISO        = 1359320808526450780
ROL_PERSONAJE           = 1369362859188027543

ROLES_SALARIO = {
    "minimo":     1359320808572321909,
    "bajo":       1369552405435514951,
    "medio_bajo": 1369553098338734120,
    "medio":      1359320808572321910,
    "medio_alto": 1369553333643378739,
    "alto":       1359320808572321911,
    "muy_alto":   1369553498974326876,
    "extranjero": 1359320808593559663,
}


def es_admin():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)


async def _quitar_rol_safe(member: discord.Member, rol: discord.Role | None):
    """Quita un rol ignorando errores de permisos."""
    if rol and rol in member.roles:
        try:
            await member.remove_roles(rol)
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"[WARN] No se pudo quitar rol {rol.name} de {member}: {e}")


async def _dar_rol_safe(member: discord.Member, rol: discord.Role | None):
    """Da un rol ignorando errores de permisos."""
    if rol and rol not in member.roles:
        try:
            await member.add_roles(rol)
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"[WARN] No se pudo dar rol {rol.name} a {member}: {e}")


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="resetear_personaje", description="[ADMIN] Borra el personaje de un usuario")
    @es_admin()
    async def resetear_personaje(self, interaction: discord.Interaction, usuario: discord.Member):
        await db.delete("personajes", str(usuario.id))

        # Quitar todos los roles relacionados con RP
        from utils.roles import TODOS_ROLES_RP
        roles_a_quitar = []
        for rid in TODOS_ROLES_RP:
            r = interaction.guild.get_role(rid)
            if r and r in usuario.roles:
                roles_a_quitar.append(r)

        if roles_a_quitar:
            try:
                await usuario.remove_roles(*roles_a_quitar, reason="Reseteo de personaje")
            except discord.Forbidden:
                # Quitar uno a uno si falla en masa
                for r in roles_a_quitar:
                    await _quitar_rol_safe(usuario, r)

        await interaction.response.send_message(
            f"✅ Personaje de {usuario.mention} eliminado. "
            f"({len(roles_a_quitar)} roles quitados)",
            ephemeral=True
        )

    @app_commands.command(name="dar_dinero", description="[ADMIN] Da dinero a un jugador")
    @es_admin()
    @app_commands.describe(usuario="Jugador", cantidad="Cantidad en $")
    async def dar_dinero(self, interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
        p = await db.get("personajes", str(usuario.id))
        if not p:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        p["dinero"] = p.get("dinero", 0) + cantidad
        await db.set("personajes", str(usuario.id), p)
        await interaction.response.send_message(
            f"💵 +${cantidad:,} entregados a {usuario.mention}. Saldo: ${p['dinero']:,}", ephemeral=True
        )

    @app_commands.command(name="quitar_dinero", description="[ADMIN] Quita dinero a un jugador")
    @es_admin()
    async def quitar_dinero(self, interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
        p = await db.get("personajes", str(usuario.id))
        if not p:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        p["dinero"] = max(0, p.get("dinero", 0) - cantidad)
        await db.set("personajes", str(usuario.id), p)
        await interaction.response.send_message(
            f"💸 -${cantidad:,} de {usuario.mention}. Saldo: ${p['dinero']:,}", ephemeral=True
        )

    @app_commands.command(name="modificar_stat", description="[ADMIN] Modifica una estadística de un jugador")
    @es_admin()
    @app_commands.describe(usuario="Jugador", stat="Stat a modificar", valor="Nuevo valor")
    async def modificar_stat(self, interaction: discord.Interaction, usuario: discord.Member, stat: str, valor: int):
        stats_validos = ["fuerza", "agilidad", "inteligencia", "tecnica", "carisma", "resistencia"]
        if stat not in stats_validos:
            return await interaction.response.send_message(f"❌ Stats válidos: {', '.join(stats_validos)}", ephemeral=True)
        p = await db.get("personajes", str(usuario.id))
        if not p:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        p["stats"][stat] = max(1, min(100, valor))
        await db.set("personajes", str(usuario.id), p)
        await interaction.response.send_message(f"✅ {stat.capitalize()} de **{p['nombre']}** → {valor}", ephemeral=True)

    @app_commands.command(name="dar_item", description="[ADMIN] Da un ítem al inventario de un jugador")
    @es_admin()
    @app_commands.describe(usuario="Jugador", item="Nombre del ítem", cantidad="Cantidad")
    async def dar_item(self, interaction: discord.Interaction, usuario: discord.Member, item: str, cantidad: int = 1):
        p = await db.get("personajes", str(usuario.id))
        if not p:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        if "inventario" not in p:
            p["inventario"] = {}
        p["inventario"][item] = p["inventario"].get(item, 0) + cantidad
        await db.set("personajes", str(usuario.id), p)
        await interaction.response.send_message(f"🎒 {cantidad}x **{item}** entregado(s) a {usuario.mention}.", ephemeral=True)

    @app_commands.command(name="quitar_item", description="[ADMIN] Quita un ítem del inventario de un jugador")
    @es_admin()
    async def quitar_item(self, interaction: discord.Interaction, usuario: discord.Member, item: str, cantidad: int = 1):
        p = await db.get("personajes", str(usuario.id))
        if not p:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        inv = p.get("inventario", {})
        if item not in inv:
            return await interaction.response.send_message(f"❌ No tiene **{item}**.", ephemeral=True)
        inv[item] = max(0, inv[item] - cantidad)
        if inv[item] == 0:
            del inv[item]
        p["inventario"] = inv
        await db.set("personajes", str(usuario.id), p)
        await interaction.response.send_message(f"🗑️ {cantidad}x **{item}** quitado(s) de {usuario.mention}.", ephemeral=True)

    @app_commands.command(name="matar_personaje", description="[ADMIN] Mata a un personaje (PK)")
    @es_admin()
    @app_commands.describe(usuario="Jugador", razon="Motivo de la muerte")
    async def matar_personaje(self, interaction: discord.Interaction, usuario: discord.Member, razon: str = "Muerte en el roleplay"):
        p = await db.get("personajes", str(usuario.id))
        if not p:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        canal_muertos = interaction.guild.get_channel(CH_MUERTOS)
        if canal_muertos:
            embed = discord.Embed(title="💀 PERSONAJE FALLECIDO", description=f"**{p['nombre']}** ha muerto.", color=0x000000)
            embed.add_field(name="Causa", value=razon)
            embed.add_field(name="Jugador", value=usuario.mention)
            embed.add_field(name="Edad", value=f"{p.get('edad', '?')} años")
            embed.add_field(name="Trabajo", value=p.get("trabajo", "Sin trabajo"))
            embed.set_footer(text="Que descanse en paz... o no.")
            await canal_muertos.send(embed=embed)
        p["muerto"] = True
        p["causa_muerte"] = razon
        await db.set("personajes", str(usuario.id), p)
        rol_p = interaction.guild.get_role(ROL_PERSONAJE)
        await _quitar_rol_safe(usuario, rol_p)
        await interaction.response.send_message(f"💀 **{p['nombre']}** ha sido marcado como muerto.", ephemeral=True)

    @app_commands.command(name="revivir", description="[ADMIN] Revive a un personaje")
    @es_admin()
    async def revivir(self, interaction: discord.Interaction, usuario: discord.Member):
        p = await db.get("personajes", str(usuario.id))
        if not p:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        p["muerto"] = False
        p["hp"] = 100
        p.pop("causa_muerte", None)
        await db.set("personajes", str(usuario.id), p)
        rol_p = interaction.guild.get_role(ROL_PERSONAJE)
        await _dar_rol_safe(usuario, rol_p)
        await interaction.response.send_message(f"✅ {usuario.mention} ha sido revivido.", ephemeral=True)

    @app_commands.command(name="info_jugador", description="[ADMIN] Ve toda la info de un jugador")
    @es_admin()
    async def info_jugador(self, interaction: discord.Interaction, usuario: discord.Member):
        p = await db.get("personajes", str(usuario.id))
        if not p:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        embed = discord.Embed(title=f"🗂️ Admin Info — {p['nombre']}", color=0xFF6600)
        embed.add_field(name="👤 Jugador", value=usuario.mention)
        embed.add_field(name="💰 Dinero", value=f"${p.get('dinero', 0):,}")
        embed.add_field(name="❤️ HP", value=f"{p.get('hp', 100)}/100")
        embed.add_field(name="📍 Ubicación", value=p.get("ubicacion", "Desconocida"))
        embed.add_field(name="💼 Trabajo", value=p.get("trabajo", "Ninguno"))
        embed.add_field(name="🏠 Casa", value=p.get("casa", "Sin casa"))
        embed.add_field(name="⚖️ Estado", value="💀 Muerto" if p.get("muerto") else "✅ Vivo")
        stats = p.get("stats", {})
        stats_txt = "\n".join(f"• {k.capitalize()}: {v}" for k, v in stats.items())
        embed.add_field(name="📊 Stats", value=stats_txt or "Sin stats", inline=False)
        inv = p.get("inventario", {})
        inv_txt = ", ".join(f"{v}x {k}" for k, v in inv.items()) if inv else "Vacío"
        embed.add_field(name="🎒 Inventario", value=inv_txt[:500], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="listar_personajes", description="[ADMIN] Lista todos los personajes activos")
    @es_admin()
    async def listar_personajes(self, interaction: discord.Interaction):
        todos = await db.all("personajes")
        if not todos:
            return await interaction.response.send_message("No hay personajes.", ephemeral=True)
        lines = []
        for uid, p in todos.items():
            estado = "💀" if p.get("muerto") else "✅"
            member = interaction.guild.get_member(int(uid))
            nombre_discord = member.display_name if member else f"ID:{uid}"
            lines.append(f"{estado} **{p['nombre']}** ({nombre_discord}) — ${p.get('dinero', 0):,} — {p.get('ubicacion', '?')}")
        chunks = [lines[i:i + 20] for i in range(0, len(lines), 20)]
        embed = discord.Embed(
            title=f"👥 Personajes ({len(todos)} total)",
            description="\n".join(chunks[0]),
            color=0x3498DB
        )
        if len(chunks) > 1:
            embed.set_footer(text=f"Página 1/{len(chunks)}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="forzar_ubicacion", description="[ADMIN] Fuerza la ubicación de un jugador")
    @es_admin()
    @app_commands.describe(usuario="Jugador a mover", ubicacion="Canal o sector destino (usa el autocompletado)")
    @app_commands.autocomplete(ubicacion=_autocomplete_ubicacion)
    async def forzar_ubicacion(self, interaction: discord.Interaction, usuario: discord.Member, ubicacion: str):
        """ANTES: guardaba el texto tal cual en 'ubicacion' sin validar nada y NUNCA
        tocaba 'canal_actual'. Si el admin escribía "#casa-8-..." Discord mandaba
        "<#123456>", que quedaba guardado como si fuera un sector — y a partir de
        ahí el jugador no podía viajar a ningún lado ("no hay ruta de <#...> a
        petare"). Ahora se resuelve y valida el destino, y se actualizan ambos
        campos de forma coherente."""
        p = await db.get("personajes", str(usuario.id))
        if not p:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)

        destino = (ubicacion or "").strip()

        # Resolver menciones de canal <#id> o #nombre
        if destino.startswith("<#") and destino.endswith(">"):
            id_txt = destino[2:-1].strip("!&")
            canal_obj = interaction.guild.get_channel(int(id_txt)) if id_txt.isdigit() else None
            if not canal_obj:
                return await interaction.response.send_message(
                    "❌ No pude resolver ese canal. Usa el autocompletado.", ephemeral=True)
            destino = canal_obj.name
        elif destino.startswith("#"):
            destino = destino[1:]
        destino = destino.lower().replace(" ", "-")

        # ¿Es un sector? → lo mandamos a su primer canal
        if destino in SECTORES:
            sector = destino
            canales = list(SECTORES[sector]["canales"].keys())
            canal_final = canales[0] if canales else None
        else:
            sector = get_sector_de_canal(destino)
            if not sector:
                # Último intento: ¿existe un canal con ese nombre en el servidor?
                canal_obj = discord.utils.get(interaction.guild.text_channels, name=destino)
                if canal_obj:
                    sector = get_sector_de_canal(canal_obj.name)
                if not sector:
                    return await interaction.response.send_message(
                        f"❌ `{destino}` no es un canal ni un sector válido del mapa. Usa el autocompletado.",
                        ephemeral=True)
            canal_final = destino

        p["ubicacion"] = sector
        p["canal_actual"] = canal_final
        p["en_viaje"] = False
        await db.set("personajes", str(usuario.id), p)

        # Cancelar cualquier viaje en curso para que no lo sobreescriba al llegar
        try:
            from cogs.viaje import viajes_activos
            viajes_activos.pop(usuario.id, None)
        except Exception:
            pass

        await interaction.response.send_message(
            f"📍 {usuario.mention} movido a **{canal_final or sector}** (sector: `{sector}`).", ephemeral=True)

    @app_commands.command(name="anuncio", description="[ADMIN] Envía un anuncio del servidor")
    @es_admin()
    @app_commands.describe(canal="Canal donde enviar", titulo="Título", mensaje="Mensaje")
    async def anuncio(self, interaction: discord.Interaction, canal: discord.TextChannel, titulo: str, mensaje: str):
        embed = discord.Embed(title=f"📢 {titulo}", description=mensaje, color=0xF39C12)
        embed.set_footer(text=f"Enviado por {interaction.user.display_name}")
        await canal.send(embed=embed)
        await interaction.response.send_message(f"✅ Anuncio enviado a {canal.mention}.", ephemeral=True)

    @app_commands.command(name="estadisticas_servidor", description="[ADMIN] Estadísticas generales del servidor RP")
    @es_admin()
    async def estadisticas_servidor(self, interaction: discord.Interaction):
        personajes = await db.all("personajes") or {}
        npcs = await db.all("npcs") or {}
        casas = await db.all("casas") or {}
        cuentas = await db.all("cuentas_banco") or {}
        vivos = sum(1 for p in personajes.values() if not p.get("muerto"))
        muertos = len(personajes) - vivos
        dinero_total = sum(p.get("dinero", 0) for p in personajes.values())
        dinero_bancos = sum(c.get("saldo", 0) for c in cuentas.values())
        casas_ocupadas = 0
        for sector_casas in casas.values():
            if isinstance(sector_casas, dict):
                casas_ocupadas += sum(1 for c in sector_casas.values() if c.get("dueno"))
        embed = discord.Embed(title="📊 Estadísticas del Servidor", color=0x2ECC71)
        embed.add_field(name="👥 Personajes", value=f"Total: {len(personajes)}\n✅ Vivos: {vivos}\n💀 Muertos: {muertos}")
        embed.add_field(name="🤖 NPCs", value=str(len(npcs)))
        embed.add_field(name="🏠 Casas ocupadas", value=str(casas_ocupadas))
        embed.add_field(name="💵 Dinero en circulación", value=f"${dinero_total:,}")
        embed.add_field(name="🏦 En bancos", value=f"${dinero_bancos:,}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="purgar_datos", description="[ADMIN] ⚠️ Elimina TODOS los datos de una tabla")
    @es_admin()
    @app_commands.describe(tabla="Escribe 'CONFIRMAR_' delante del nombre (ej: CONFIRMAR_personajes)")
    async def purgar_datos(self, interaction: discord.Interaction, tabla: str):
        if not tabla.startswith("CONFIRMAR_"):
            return await interaction.response.send_message(
                "⚠️ Debes escribir `CONFIRMAR_` delante del nombre.\nEj: `CONFIRMAR_personajes`", ephemeral=True
            )
        tabla_real = tabla.replace("CONFIRMAR_", "")
        import os
        path = f"./data/{tabla_real}.json"
        if os.path.exists(path):
            with open(path, "w") as f:
                json.dump({}, f)
            await interaction.response.send_message(f"🗑️ Tabla `{tabla_real}` purgada.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ No existe la tabla `{tabla_real}`.", ephemeral=True)

    @app_commands.command(name="asignar_rol_salario", description="[ADMIN] Asigna el rol de salario a un usuario")
    @es_admin()
    @app_commands.describe(usuario="Jugador", nivel="Nivel de salario")
    @app_commands.choices(nivel=[
        app_commands.Choice(name="Mínimo", value="minimo"),
        app_commands.Choice(name="Bajo", value="bajo"),
        app_commands.Choice(name="Medio-Bajo", value="medio_bajo"),
        app_commands.Choice(name="Medio", value="medio"),
        app_commands.Choice(name="Medio-Alto", value="medio_alto"),
        app_commands.Choice(name="Alto", value="alto"),
        app_commands.Choice(name="Muy Alto", value="muy_alto"),
        app_commands.Choice(name="Extranjero", value="extranjero"),
    ])
    async def asignar_rol_salario(self, interaction: discord.Interaction, usuario: discord.Member, nivel: str):
        for rid in ROLES_SALARIO.values():
            r = interaction.guild.get_role(rid)
            await _quitar_rol_safe(usuario, r)
        nuevo_rol = interaction.guild.get_role(ROLES_SALARIO[nivel])
        if nuevo_rol:
            await _dar_rol_safe(usuario, nuevo_rol)
            await interaction.response.send_message(f"✅ {usuario.mention} → rol de salario **{nivel}** asignado.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No se encontró el rol.", ephemeral=True)

    @app_commands.command(name="buscar_personaje", description="[ADMIN] Busca un personaje por nombre")
    @es_admin()
    @app_commands.describe(nombre="Nombre del personaje (parcial)")
    async def buscar_personaje(self, interaction: discord.Interaction, nombre: str):
        todos = await db.all("personajes") or {}
        encontrados = [(uid, p) for uid, p in todos.items() if nombre.lower() in p.get("nombre", "").lower()]
        if not encontrados:
            return await interaction.response.send_message(f"❌ No se encontró ningún personaje con '{nombre}'.", ephemeral=True)
        lines = []
        for uid, p in encontrados[:10]:
            member = interaction.guild.get_member(int(uid))
            tag = member.mention if member else f"ID:{uid}"
            estado = "💀" if p.get("muerto") else "✅"
            lines.append(f"{estado} **{p['nombre']}** → {tag} | ${p.get('dinero', 0):,} | {p.get('ubicacion', '?')}")
        embed = discord.Embed(title=f"🔍 Resultados para '{nombre}'", description="\n".join(lines), color=0x9B59B6)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setup_celdas", description="[ADMIN] Crea los canales de celdas en la prisión de Yare")
    @es_admin()
    @app_commands.describe(cantidad="Número de celdas (default 10)")
    async def setup_celdas(self, interaction: discord.Interaction, cantidad: int = 10):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        cat = discord.utils.get(guild.categories, name="PRISION-YARE")
        if not cat:
            cat = await guild.create_category("PRISION-YARE")

        creados = 0
        canales_base = [
            ("celda-yare", "Celda general de Yare"),
            ("patio-yare", "Patio de la cárcel de Yare"),
            ("oficina-director-yare", "Oficina del Director"),
        ]
        for nombre, desc in canales_base:
            if not discord.utils.get(cat.channels, name=nombre):
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False, view_channel=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, view_channel=True),
                }
                await guild.create_text_channel(name=nombre, category=cat, topic=desc, overwrites=overwrites)
                creados += 1

        for i in range(1, cantidad + 1):
            nombre = f"celda-{i}"
            if not discord.utils.get(cat.channels, name=nombre):
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False, view_channel=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, view_channel=True),
                }
                await guild.create_text_channel(
                    name=nombre,
                    category=cat,
                    topic=f"Celda {i} — Prisión de Yare",
                    overwrites=overwrites
                )
                creados += 1

        await interaction.followup.send(f"⛓️ Prisión de Yare lista. {creados} canales creados.", ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Solo administradores pueden usar este comando.", ephemeral=True)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))