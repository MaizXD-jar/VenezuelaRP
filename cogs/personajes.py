"""
cogs/personajes.py — Creación y gestión de personajes.
Al aceptar un personaje, se crean automáticamente los padres/madres como NPCs.
FIXED: género de padres, apellido del padre = apellido del personaje.
FIXED: spawn automático al aceptar (casa padres o calle barrio), sin /viajar en DM.
FIXED: CH_CREAR_DOC actualizado al nuevo canal 1484797041560260688.
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import asyncio
import time
from utils import db
from utils.roles import (ROLES_SALARIO, ROL_CIUDADANO, ROL_HOMBRE, ROL_MUJER,
                          ROL_MUERTO, ROL_CRIMINAL, ROL_PRISIONERO,
                          ROL_PRIMARIA, ROL_SECUNDARIA, ROL_UNIVERSITARIO, ROL_GRADUADO,
                          ROL_ESTUDIANTE, ROL_MANTENIDO, ROL_EXTRANJERO, ROL_INDOCUMENTADO)
from utils.mapa import SECTORES

CH_CREAR_DOC       = 1484797041560260688  # ← Canal principal actualizado
CH_CREAR_DOC_OLD   = 1369366721550614700  # ← Canal viejo (compatibilidad)
CH_DOCUMENTACIONES = 1421513030851629056
CH_PERSONAJES_OK   = 1359320812003393567
CH_MUERTOS         = 1359320811420520613

CH_NOTICIAS_IDS = [1382156099473379458, 1382156210576425040, 1382156276016087110]

CANALES_SISTEMA = {
    CH_CREAR_DOC, CH_CREAR_DOC_OLD, CH_DOCUMENTACIONES, CH_PERSONAJES_OK,
    1359320811420520614, 1359412448976965713, 1359320811420520609,
    1369438606694944799, CH_MUERTOS, 1369438636260724856,
    1369365887156617428, 1359320808526450780,
    1382156099473379458, 1382156210576425040, 1382156276016087110,
}

BARRIOS_POR_ESTATUS = {
    "muy_pobre":  ["petare", "23-de-enero"],
    "pobre":      ["petare", "23-de-enero", "la-alameda"],
    "medio_bajo": ["la-alameda", "ciudad-universitaria"],
    "medio":      ["miranda", "ciudad-universitaria"],
    "medio_alto": ["miranda", "las-mercedes"],
    "rico":       ["las-mercedes", "la-trinidad"],
    "muy_rico":   ["la-trinidad", "las-mercedes"],
}

ESTATUS_SOCIAL = ["muy_pobre", "pobre", "medio_bajo", "medio", "medio_alto", "rico", "muy_rico"]

ESTUDIOS_POR_ESTATUS = {
    "muy_pobre":  ["ninguno", "primaria"],
    "pobre":      ["primaria", "secundaria"],
    "medio_bajo": ["secundaria", "secundaria"],
    "medio":      ["secundaria", "universitario"],
    "medio_alto": ["universitario", "universitario"],
    "rico":       ["universitario", "graduado"],
    "muy_rico":   ["graduado", "graduado"],
}

NOMBRES_MASCULINOS = [
    "Luis", "Carlos", "José", "Miguel", "Jesús", "Jorge", "Roberto", "Ramón",
    "Simón", "Ricardo", "Pedro", "Fernando", "Alejandro", "Diego", "Juan",
    "Antonio", "Rodrigo", "Manuel", "Rafael", "Eduardo", "Víctor", "Héctor"
]
NOMBRES_FEMENINOS = [
    "María", "Ana", "Carmen", "Laura", "Sofía", "Isabella", "Valentina", "Adriana",
    "Keila", "Yolanda", "Rosa", "Elena", "Gloria", "Patricia", "Luisa", "Teresa",
    "Gabriela", "Daniela", "Mónica", "Verónica", "Beatriz", "Ángela"
]
APELLIDOS = [
    "González", "Rodríguez", "Pérez", "García", "López", "Martínez", "Hernández",
    "Díaz", "Torres", "Ramírez", "Sánchez", "Flores", "Morales", "Jiménez", "Castro",
    "Gutiérrez", "Álvarez", "Medina", "Vargas", "Rojas", "Blanco", "Reyes", "Toledo",
    "Bravo", "Rivas", "Contreras", "Mendoza", "Suárez", "Figueroa", "Herrera"
]

TRABAJOS_PADRES_HOMBRE = [
    "Obrero", "Taxista", "Mecánico", "Vigilante", "Comerciante",
    "Carpintero", "Plomero", "Electricista", "Desempleado", "Vendedor"
]
TRABAJOS_PADRES_MUJER = [
    "Vendedora ambulante", "Bodeguera", "Enfermera", "Maestra",
    "Cocinera", "Costurera", "Ama de casa", "Limpiadora", "Peluquera"
]

_webhook_cache: dict[int, discord.Webhook] = {}


async def _get_webhook(canal: discord.TextChannel) -> discord.Webhook | None:
    if canal.id in _webhook_cache:
        return _webhook_cache[canal.id]
    try:
        webhooks = await canal.webhooks()
        wh = next((w for w in webhooks if w.name == "VenezuelaRP_Chars"), None)
        if not wh:
            wh = await canal.create_webhook(name="VenezuelaRP_Chars")
        _webhook_cache[canal.id] = wh
        return wh
    except Exception:
        return None


async def _crear_npc_padre(datos_personaje: dict, tipo: str, parent_data: dict):
    nombre = parent_data.get("nombre", "")
    if not nombre:
        return
    npc_id = nombre.lower().replace(" ", "_").replace(".", "").replace(",", "")[:30]
    existente = await db.get("npcs", npc_id)
    if existente:
        return
    trabajo = parent_data.get("trabajo", "Desempleado")
    edad_hijo = datos_personaje.get("edad", 20)
    edad_padre = min(edad_hijo + random.randint(22, 40), 85)
    npc_data = {
        "nombre": nombre,
        "edad": edad_padre,
        "trabajo": trabajo,
        "dinero": round(random.uniform(5, 300), 2),
        "genero": "hombre" if tipo == "padre" else "mujer",
        "stats": {
            "hp": 100, "hp_max": 100,
            "fuerza": random.randint(2, 7),
            "agilidad": max(1, random.randint(2, 7) - (edad_padre - 40) // 15),
            "resistencia": random.randint(3, 8),
            "tecnica": random.randint(2, 8),
            "inteligencia": random.randint(4, 12),
        },
        "inventario": {},
        "ubicacion": datos_personaje.get("barrio", "petare"),
        "canal_actual": None,
        "vivo": parent_data.get("vivo", True),
        "imagen": None,
        "creado_automaticamente": True,
        "tipo_familiar": tipo,
        "es_padre_de": datos_personaje.get("nombre", "?"),
        "hijo_user_id": datos_personaje.get("user_id"),
    }
    await db.set("npcs", npc_id, npc_data)
    print(f"[NPC] Creado: {nombre} ({tipo} de {datos_personaje.get('nombre', '?')})")


async def _spawn_personaje(guild: discord.Guild, member: discord.Member, datos: dict) -> str:
    from utils.permisos import dar_acceso_canal, canal_privado_base

    barrio = datos.get("barrio", "petare")
    familia = datos.get("familia", {})
    nombre = datos.get("nombre", "?")
    canal_spawn_nombre = None

    if familia.get("vive_con_padres") and familia.get("casa_padres"):
        casa_padres_str = familia["casa_padres"]
        partes = casa_padres_str.split(":")
        if len(partes) == 2:
            sector_padres, casa_id_padres = partes
            num_casa = casa_id_padres.replace("casa-", "")
            sector_slug = sector_padres.replace(" ", "-")[:12]
            nombre_canal_casa = f"casa-{num_casa}-{sector_slug}-padres"

            canal_discord = discord.utils.get(guild.text_channels, name=nombre_canal_casa)
            if not canal_discord:
                cat = discord.utils.get(guild.categories, name=sector_padres.upper())
                if not cat:
                    try:
                        cat = await guild.create_category(sector_padres.upper())
                    except Exception as e:
                        print(f"[WARN] No se pudo crear categoría {sector_padres}: {e}")
                if cat:
                    try:
                        overwrites = await canal_privado_base(guild)
                        canal_discord = await guild.create_text_channel(
                            name=nombre_canal_casa,
                            category=cat,
                            topic=f"Casa de los padres de {nombre} en {sector_padres}",
                            overwrites=overwrites
                        )
                    except Exception as e:
                        print(f"[WARN] No se pudo crear canal casa padres: {e}")

            if canal_discord:
                canal_spawn_nombre = canal_discord.name
                await dar_acceso_canal(guild, member, canal_spawn_nombre)
                await db.update("personajes", str(member.id), {
                    "canal_actual": canal_spawn_nombre,
                    "ubicacion": sector_padres,
                    "ultimo_canal": None,
                })
                embed_spawn = discord.Embed(
                    description=f"🏠 **{nombre}** aparece en la casa de sus padres.",
                    color=discord.Color.green()
                )
                await canal_discord.send(f"{member.mention}", embed=embed_spawn)

    if not canal_spawn_nombre:
        sec = SECTORES.get(barrio, {})
        canales_sec = list(sec.get("canales", {}).keys())
        if canales_sec:
            canal_spawn_nombre = canales_sec[0]
            await dar_acceso_canal(guild, member, canal_spawn_nombre)
            await db.update("personajes", str(member.id), {
                "canal_actual": canal_spawn_nombre,
                "ubicacion": barrio,
                "ultimo_canal": None,
            })
            canal_discord = discord.utils.get(guild.text_channels, name=canal_spawn_nombre)
            if canal_discord:
                embed_spawn = discord.Embed(
                    description=f"🏙️ **{nombre}** aparece en **{barrio}**.",
                    color=discord.Color.blurple()
                )
                await canal_discord.send(f"{member.mention}", embed=embed_spawn)
        else:
            canal_spawn_nombre = barrio

    return canal_spawn_nombre


def _asignar_trabajo_automatico(edad: int, estatus: str, estudios: str, barrio: str) -> tuple:
    if edad < 16:
        return "desempleado", "Estudiante"
    if edad < 18:
        if estudios in ("universitario", "secundaria"):
            return "desempleado", "Estudiante"
        return random.choice([("vendedor_ambulante", "Vendedor Ambulante"), ("desempleado", "Desempleado")])
    if estatus in ("muy_pobre", "pobre"):
        if estudios in ("ninguno", "primaria"):
            return random.choice([("vendedor_ambulante", "Vendedor Ambulante"), ("obrero", "Obrero"),
                                   ("desempleado", "Desempleado"), ("desempleado", "Desempleado")])
        if estudios == "secundaria":
            opciones = [("vendedor_ambulante", "Vendedor Ambulante"), ("obrero", "Obrero"),
                        ("comerciante", "Comerciante"), ("desempleado", "Desempleado")]
            if edad >= 18:
                opciones.append(("taxista", "Taxista"))
            return random.choice(opciones)
    if estatus == "medio_bajo":
        if estudios in ("ninguno", "primaria", "secundaria"):
            opciones = [("comerciante", "Comerciante"), ("obrero", "Obrero"),
                        ("mecanico", "Mecánico"), ("vendedor_ambulante", "Vendedor Ambulante")]
            if edad >= 18:
                opciones.append(("taxista", "Taxista"))
            return random.choice(opciones)
        if estudios in ("universitario", "graduado"):
            if edad < 23:
                return ("desempleado", "Recién graduado / Desempleado")
            return random.choice([("profesor", "Profesor/a"), ("enfermero", "Enfermero/a"), ("comerciante", "Comerciante")])
    if estatus == "medio":
        if estudios == "secundaria":
            return random.choice([("comerciante", "Comerciante"), ("mecanico", "Mecánico"),
                                   ("taxista", "Taxista"), ("enfermero", "Enfermero/a")])
        if estudios in ("universitario", "graduado"):
            opciones = [("enfermero", "Enfermero/a"), ("profesor", "Profesor/a"), ("periodista", "Periodista")]
            if edad >= 24:
                opciones.append(("abogado", "Abogado/a"))
            if edad >= 26:
                opciones.append(("medico", "Médico/a"))
            return random.choice(opciones)
        return ("comerciante", "Comerciante")
    if estatus == "medio_alto":
        if estudios in ("universitario", "graduado"):
            opciones = [("periodista", "Periodista"), ("enfermero", "Enfermero/a")]
            if edad >= 24:
                opciones.append(("abogado", "Abogado/a"))
            if edad >= 26:
                opciones.append(("medico", "Médico/a"))
            if edad >= 21:
                opciones.append(("empresario", "Empresario/a"))
            return random.choice(opciones)
        return ("comerciante", "Comerciante")
    if estatus in ("rico", "muy_rico"):
        if estudios in ("universitario", "graduado"):
            opciones = []
            if edad >= 24:
                opciones.append(("abogado", "Abogado/a"))
            if edad >= 26:
                opciones.append(("medico", "Médico/a"))
            if edad >= 21:
                opciones += [("empresario", "Empresario/a"), ("empresario", "Empresario/a")]
            if opciones:
                return random.choice(opciones)
        return ("empresario", "Empresario/a")
    return ("desempleado", "Desempleado")


def _extraer_apellido(nombre_completo: str) -> str:
    partes = nombre_completo.strip().split()
    if len(partes) >= 2:
        return partes[-1]
    return random.choice(APELLIDOS)


def _generar_familia(edad: int, estatus: str, barrio: str, apellido_personaje: str = None) -> dict:
    apellido_padre = apellido_personaje or random.choice(APELLIDOS)
    apellido_madre = random.choice(APELLIDOS)
    padre_info = {
        "nombre": random.choice(NOMBRES_MASCULINOS) + " " + apellido_padre,
        "trabajo": random.choice(TRABAJOS_PADRES_HOMBRE),
        "vivo": True
    }
    madre_info = {
        "nombre": random.choice(NOMBRES_FEMENINOS) + " " + apellido_madre,
        "trabajo": random.choice(TRABAJOS_PADRES_MUJER),
        "vivo": True
    }
    if edad < 18:
        return {
            "padre": padre_info, "madre": madre_info,
            "vive_con_padres": True,
            "casa_padres": f"{barrio}:casa-{random.randint(1, 15)}",
        }
    elif edad < 25:
        fam = {}
        if random.random() < 0.7:
            fam["padre"] = padre_info
            fam["madre"] = madre_info
        fam["vive_con_padres"] = random.random() < 0.3
        if fam.get("vive_con_padres"):
            fam["casa_padres"] = f"{barrio}:casa-{random.randint(1, 15)}"
        return fam
    else:
        fam = {"vive_con_padres": False}
        if random.random() < 0.6:
            padre_mayor = dict(padre_info)
            padre_mayor["vivo"] = random.random() > 0.2
            madre_mayor = dict(madre_info)
            madre_mayor["vivo"] = random.random() > 0.15
            fam["padre"] = padre_mayor
            fam["madre"] = madre_mayor
        if random.random() < 0.4:
            fam["pareja"] = random.choice(NOMBRES_FEMENINOS if random.random() < 0.5 else NOMBRES_MASCULINOS) + " " + random.choice(APELLIDOS)
        if random.random() < 0.3:
            fam["hijos"] = random.randint(1, 3)
        return fam


def _generar_stats(edad: int, estatus: str, estudios: str) -> dict:
    base = 5 + (edad - 16) // 5 if edad >= 16 else 3
    bi = 2 if estudios in ("universitario", "graduado") else 0
    return {
        "fuerza":       random.randint(3, max(4, base)),
        "agilidad":     random.randint(3, max(4, base)),
        "resistencia":  random.randint(3, max(4, base)),
        "inteligencia": random.randint(3 + bi, max(5, base + bi)),
        "carisma":      random.randint(3, max(4, base)),
        "tecnica":      random.randint(1, max(4, base - 1)),
        "hp": 100, "hp_max": 100,
    }


def _dinero_inicial(estatus: str) -> float:
    tabla = {"muy_pobre": 5, "pobre": 20, "medio_bajo": 80, "medio": 200,
             "medio_alto": 500, "rico": 1500, "muy_rico": 5000}
    return round(tabla.get(estatus, 50) * random.uniform(0.8, 1.2), 2)


def _embed_personaje(datos: dict, user: discord.Member, aceptado: bool = False) -> discord.Embed:
    color = discord.Color.green() if aceptado else discord.Color.orange()
    embed = discord.Embed(
        title=f"{'✅ ' if aceptado else '📋 '}Personaje: {datos.get('nombre', '?')}",
        color=color
    )
    embed.set_author(name=str(user), icon_url=user.display_avatar.url)
    imagen = datos.get("imagen_url")
    if imagen:
        embed.set_thumbnail(url=imagen)
    embed.add_field(name="Nombre", value=datos.get("nombre", "?"), inline=True)
    embed.add_field(name="Edad", value=str(datos.get("edad", "?")), inline=True)
    embed.add_field(name="Género", value=datos.get("genero", "?"), inline=True)
    embed.add_field(name="Estatus", value=datos.get("estatus_social", "?").replace("_", " ").title(), inline=True)
    embed.add_field(name="Estudios", value=datos.get("estudios", "ninguno").title(), inline=True)
    embed.add_field(name="Trabajo", value=datos.get("trabajo_display", "Desempleado"), inline=True)
    embed.add_field(name="Barrio", value=datos.get("barrio", "?"), inline=True)
    fam = datos.get("familia", {})
    if fam.get("padre"):
        vivo = "✅" if fam["padre"].get("vivo", True) else "💀"
        embed.add_field(name="👨 Padre", value=f"{vivo} {fam['padre']['nombre']}", inline=True)
    if fam.get("madre"):
        vivo = "✅" if fam["madre"].get("vivo", True) else "💀"
        embed.add_field(name="👩 Madre", value=f"{vivo} {fam['madre']['nombre']}", inline=True)
    embed.add_field(name="Historia", value=datos.get("backstory", "Sin historia")[:300], inline=False)
    stats = datos.get("stats", {})
    if stats:
        st = "  ".join(f"**{k[:3].upper()}** {v}" for k, v in stats.items() if k not in ("hp", "hp_max"))
        embed.add_field(name="📊 Stats", value=st or "—", inline=False)
    return embed


# ── VIEWS ─────────────────────────────────────────────────────────────────────

class PersonajeCrearView(discord.ui.View):
    def __init__(self, user_id, datos):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.datos = datos

    @discord.ui.button(label="✅ Confirmar y enviar", style=discord.ButtonStyle.green)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("No es tu formulario.", ephemeral=True)
        await interaction.response.send_message(
            "✅ Solicitud enviada. Los admins revisarán tu personaje pronto.", ephemeral=True
        )
        ch = interaction.guild.get_channel(CH_DOCUMENTACIONES)
        if ch:
            embed = _embed_personaje(self.datos, interaction.user)
            embed.set_footer(text=f"UserID: {self.user_id}")
            view = AdminAceptarView(self.user_id, self.datos)
            await ch.send(embed=embed, view=view)
        self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.red)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("No es tu formulario.", ephemeral=True)
        await interaction.response.send_message("Cancelado.", ephemeral=True)
        self.stop()


class AdminAceptarView(discord.ui.View):
    def __init__(self, user_id, datos):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.datos = datos

    @discord.ui.button(label="✅ Aceptar Personaje", style=discord.ButtonStyle.green, custom_id="admin_aceptar_v6")
    async def aceptar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ Solo admins.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        member = guild.get_member(self.user_id)
        if not member:
            return await interaction.followup.send("❌ El usuario ya no está en el servidor.", ephemeral=True)

        self.datos["creado_ts"] = time.time()
        await db.set("personajes", str(self.user_id), self.datos)

        async def add_role_safe(role_id):
            try:
                r = guild.get_role(role_id)
                if r and r not in member.roles:
                    await member.add_roles(r)
            except Exception as e:
                print(f"[WARN] No se pudo añadir rol {role_id}: {e}")

        await add_role_safe(ROL_CIUDADANO)

        genero = self.datos.get("genero", "").lower()
        if "mujer" in genero or genero == "f":
            await add_role_safe(ROL_MUJER)
        else:
            await add_role_safe(ROL_HOMBRE)

        estudios = self.datos.get("estudios", "ninguno")
        er = {"primaria": ROL_PRIMARIA, "secundaria": ROL_SECUNDARIA,
              "universitario": ROL_UNIVERSITARIO, "graduado": ROL_GRADUADO}
        if estudios in er:
            await add_role_safe(er[estudios])
            if estudios in ("universitario", "graduado"):
                await add_role_safe(ROL_ESTUDIANTE)

        trabajo_key = self.datos.get("trabajo_actual", "desempleado")
        try:
            from cogs.trabajos import TRABAJOS
            job = TRABAJOS.get(trabajo_key, {})
            nivel_sal = job.get("nivel")
        except:
            nivel_sal = None

        if not nivel_sal:
            sal_map = {"muy_pobre": "minimo", "pobre": "bajo", "medio_bajo": "medio_bajo",
                       "medio": "medio", "medio_alto": "medio_alto", "rico": "alto", "muy_rico": "muy_alto"}
            nivel_sal = sal_map.get(self.datos.get("estatus_social", "medio"), "medio")

        sal_id = ROLES_SALARIO.get(nivel_sal)
        if sal_id:
            await add_role_safe(sal_id)

        try:
            ch_ok = guild.get_channel(CH_PERSONAJES_OK)
            if ch_ok:
                embed = _embed_personaje(self.datos, member, aceptado=True)
                await ch_ok.send(embed=embed)
        except Exception as e:
            print(f"[WARN] Error enviando a canal OK: {e}")

        familia = self.datos.get("familia", {})
        padre = familia.get("padre")
        madre = familia.get("madre")
        if padre and padre.get("nombre"):
            await _crear_npc_padre(self.datos, "padre", padre)
        if madre and madre.get("nombre"):
            await _crear_npc_padre(self.datos, "madre", madre)

        canal_spawn_nombre = await _spawn_personaje(guild, member, self.datos)

        try:
            await interaction.message.edit(
                content=f"✅ **ACEPTADO** por {interaction.user.mention}", view=None
            )
        except:
            pass

        await interaction.followup.send(
            f"✅ Personaje **{self.datos.get('nombre', '?')}** de {member.mention} aceptado.\n"
            f"📍 Spawneado en: `{canal_spawn_nombre}`\n"
            f"NPCs de padres creados automáticamente.",
            ephemeral=True
        )

        nombre = self.datos.get("nombre", "?")
        barrio = self.datos.get("barrio", "?")
        trabajo_display = self.datos.get("trabajo_display", "Desempleado")
        fam = self.datos.get("familia", {})
        padre_txt = f"\n👨 Padre: **{fam['padre']['nombre']}**" if fam.get("padre") else ""
        madre_txt = f"\n👩 Madre: **{fam['madre']['nombre']}**" if fam.get("madre") else ""

        if fam.get("vive_con_padres"):
            where_txt = f"en la casa de tus padres en **{barrio}**"
        else:
            where_txt = f"en la calle de **{barrio}**"

        try:
            await member.send(
                f"🎮 **¡Tu personaje fue aceptado!**\n\n"
                f"👤 **{nombre}**\n"
                f"📍 Has aparecido {where_txt}\n"
                f"💼 Trabajo: **{trabajo_display}**"
                f"{padre_txt}{madre_txt}\n\n"
                f"**Comandos útiles:**\n"
                f"• `/perfil` — ver tu ficha\n"
                f"• `/ayuda_rp` — ver todos los comandos\n\n"
                f"*Escribe en los canales de RP y tus mensajes aparecerán con tu personaje.*"
            )
        except:
            pass

    @discord.ui.button(label="❌ Rechazar", style=discord.ButtonStyle.red, custom_id="admin_rechazar_v6")
    async def rechazar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ Solo admins.", ephemeral=True)
        await interaction.response.send_modal(RechazarModal(self.user_id))
        try:
            await interaction.message.edit(
                content=f"❌ **RECHAZADO** por {interaction.user.mention}", view=None
            )
        except:
            pass


class RechazarModal(discord.ui.Modal, title="Razón del rechazo"):
    razon = discord.ui.TextInput(label="Razón del rechazo", style=discord.TextStyle.long, max_length=500)

    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(self.user_id)
        if member:
            try:
                await member.send(
                    f"❌ **Tu personaje fue rechazado.**\n"
                    f"Razón: {self.razon.value}\n\n"
                    f"Puedes intentarlo de nuevo en <#{CH_CREAR_DOC}>."
                )
            except:
                pass
        await interaction.response.send_message("✅ Rechazo notificado.", ephemeral=True)


class PersonajesModal(discord.ui.Modal, title="Crear Personaje — Venezuela RP"):
    nombre     = discord.ui.TextInput(label="Nombre completo del personaje", max_length=50)
    edad       = discord.ui.TextInput(label="Edad (mínimo 10 años)", max_length=3)
    genero     = discord.ui.TextInput(label="Género (hombre / mujer / otro)", max_length=20)
    backstory  = discord.ui.TextInput(label="Historia del personaje", style=discord.TextStyle.long, max_length=600)
    imagen_url = discord.ui.TextInput(
        label="URL de foto del personaje (opcional)",
        placeholder="https://i.imgur.com/tu-imagen.jpg",
        required=False, max_length=300
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            edad_int = int(self.edad.value.strip())
        except:
            return await interaction.response.send_message("❌ Edad inválida.", ephemeral=True)
        if edad_int < 10 or edad_int > 99:
            return await interaction.response.send_message("❌ La edad debe estar entre 10 y 99 años.", ephemeral=True)

        img = self.imagen_url.value.strip() if self.imagen_url.value else None
        if img and not (img.startswith("http://") or img.startswith("https://")):
            img = None

        estatus = random.choice(ESTATUS_SOCIAL)
        barrio = random.choice(BARRIOS_POR_ESTATUS.get(estatus, ["miranda"]))
        estudios = random.choice(ESTUDIOS_POR_ESTATUS.get(estatus, ["ninguno"]))

        if edad_int < 18 and estudios in ("universitario", "graduado"):
            estudios = "secundaria" if edad_int >= 15 else "primaria"
        if edad_int < 12:
            estudios = "ninguno"

        genero_str = self.genero.value.strip().lower()
        apellido = _extraer_apellido(self.nombre.value.strip())
        familia = _generar_familia(edad_int, estatus, barrio, apellido_personaje=apellido)
        stats = _generar_stats(edad_int, estatus, estudios)
        trabajo_key, trabajo_display = _asignar_trabajo_automatico(edad_int, estatus, estudios, barrio)

        datos = {
            "user_id": interaction.user.id,
            "nombre": self.nombre.value.strip(),
            "edad": edad_int,
            "genero": genero_str,
            "estatus_social": estatus,
            "estudios": estudios,
            "trabajo_actual": trabajo_key,
            "trabajo_display": trabajo_display,
            "backstory": self.backstory.value.strip(),
            "barrio": barrio,
            "familia": familia,
            "stats": stats,
            "dinero": _dinero_inicial(estatus),
            "inventario": {},
            "vehiculos": [],
            "ubicacion": barrio,
            "canal_actual": None,
            "ultimo_canal": None,
            "en_viaje": False,
            "casa": None,
            "muerto": False,
            "arrestado": False,
            "nivel_busqueda": 0,
            "deudas": 0,
            "telefono": None,
            "creado_ts": time.time(),
            "ultimo_cumple_ts": time.time(),
            "imagen_url": img,
        }

        embed = _embed_personaje(datos, interaction.user)
        embed.add_field(
            name="💼 Trabajo asignado",
            value=f"**{trabajo_display}**\n*Asignado automáticamente*",
            inline=False
        )

        fam = datos.get("familia", {})
        if fam.get("padre") or fam.get("madre"):
            fam_txt = ""
            if fam.get("padre"):
                fam_txt += f"👨 **{fam['padre']['nombre']}** — {fam['padre']['trabajo']}\n"
            if fam.get("madre"):
                fam_txt += f"👩 **{fam['madre']['nombre']}** — {fam['madre']['trabajo']}\n"
            if fam.get("vive_con_padres"):
                fam_txt += "🏠 Vives con tus padres"
            embed.add_field(name="👨‍👩‍👧 Familia (NPCs automáticos)", value=fam_txt.strip(), inline=False)

        embed.set_footer(text="Revisa tu personaje y confirma para enviarlo a revisión.")
        view = PersonajeCrearView(interaction.user.id, datos)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class AbrirModalView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id

    @discord.ui.button(label="📋 Abrir formulario de personaje", style=discord.ButtonStyle.blurple)
    async def abrir(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("No es tu formulario.", ephemeral=True)
        await interaction.response.send_modal(PersonajesModal())


# ── COG ───────────────────────────────────────────────────────────────────────

class Personajes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def start_tasks(self):
        if not self.envejecimiento_loop.is_running():
            self.envejecimiento_loop.start()

    @tasks.loop(hours=6)
    async def envejecimiento_loop(self):
        personajes = await db.all("personajes")
        now = time.time()
        CICLO = 60 * 3600
        for uid, datos in personajes.items():
            if datos.get("muerto"):
                continue
            ultimo = datos.get("ultimo_cumple_ts", datos.get("creado_ts", now))
            if now - ultimo < CICLO:
                continue
            nueva_edad = datos.get("edad", 20) + 1
            await db.update("personajes", uid, {"edad": nueva_edad, "ultimo_cumple_ts": now})
            guild = self.bot.guilds[0] if self.bot.guilds else None
            if guild:
                member = guild.get_member(int(uid))
                if member:
                    try:
                        await member.send(f"🎂 ¡**{datos['nombre']}** cumple **{nueva_edad} años**!")
                    except:
                        pass
            if nueva_edad >= 90 and random.random() < (nueva_edad - 89) * 0.15:
                await db.update("personajes", uid, {
                    "muerto": True,
                    "causa_muerte": f"Falleció de vejez a los {nueva_edad} años."
                })

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return
        if message.content and message.content[0] in ("!", "/", "?", "."):
            return
        if message.channel.id in CANALES_SISTEMA:
            return
        if not isinstance(message.channel, discord.TextChannel):
            return

        canal_nombre = message.channel.name
        es_rp = False
        for sec in SECTORES.values():
            if canal_nombre in sec.get("canales", {}):
                es_rp = True
                break
        if not es_rp and (
            canal_nombre.startswith("casa-") or
            canal_nombre.startswith("celda-") or
            "patio-yare" in canal_nombre or
            "oficina-director" in canal_nombre or
            "casa-abandonada" in canal_nombre or
            canal_nombre.startswith("casas-abandonadas")
        ):
            es_rp = True

        if "tel-" in canal_nombre:
            return
        if not es_rp:
            return

        datos = await db.get("personajes", str(message.author.id))
        if not datos or datos.get("muerto"):
            return

        if not message.channel.permissions_for(message.guild.me).manage_webhooks:
            return

        nombre_personaje = datos.get("nombre", message.author.display_name)
        imagen = datos.get("imagen_url") or message.author.display_avatar.url

        try:
            webhook = await _get_webhook(message.channel)
            if not webhook:
                return
            await message.delete()
            files = []
            for att in message.attachments:
                try:
                    files.append(await att.to_file())
                except:
                    pass
            content = message.content or None
            await webhook.send(
                content=content,
                username=nombre_personaje,
                avatar_url=imagen,
                files=files if files else discord.utils.MISSING,
                allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
            )
        except discord.Forbidden:
            pass
        except discord.NotFound:
            _webhook_cache.pop(message.channel.id, None)
        except Exception as e:
            print(f"[WARN] on_message webhook: {e}")

    @app_commands.command(name="crear_personaje", description="Crea tu personaje para Venezuela RP")
    async def crear_personaje_slash(self, interaction: discord.Interaction):
        if interaction.channel_id not in (CH_CREAR_DOC, CH_CREAR_DOC_OLD):
            return await interaction.response.send_message(
                f"❌ Usa este comando en <#{CH_CREAR_DOC}>.", ephemeral=True
            )
        existente = await db.get("personajes", str(interaction.user.id))
        if existente and not existente.get("muerto"):
            return await interaction.response.send_message(
                "❌ Ya tienes un personaje activo. Usa `/perfil` para verlo.", ephemeral=True
            )
        await interaction.response.send_modal(PersonajesModal())

    @app_commands.command(name="perfil", description="Muestra el perfil de tu personaje")
    @app_commands.describe(usuario="Usuario (opcional)")
    async def perfil(self, interaction: discord.Interaction, usuario: discord.Member = None):
        target = usuario or interaction.user
        datos = await db.get("personajes", str(target.id))
        if not datos:
            return await interaction.response.send_message(f"❌ {target.display_name} no tiene personaje.", ephemeral=True)
        embed = _embed_personaje(datos, target, aceptado=True)
        embed.add_field(name="💵 Dinero", value=f"${datos.get('dinero', 0):.2f}", inline=True)
        embed.add_field(name="📍 Ubicación", value=datos.get("ubicacion", "?"), inline=True)
        hp = datos.get("stats", {}).get("hp", 100)
        hp_max = datos.get("stats", {}).get("hp_max", 100)
        barra = "█" * int((hp / hp_max) * 10) + "░" * (10 - int((hp / hp_max) * 10))
        embed.add_field(name="❤️ HP", value=f"`{barra}` {hp}/{hp_max}", inline=False)
        telefono = datos.get("telefono")
        if telefono:
            embed.add_field(name="📱 Teléfono", value=telefono, inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="stats", description="Muestra las estadísticas del personaje")
    @app_commands.describe(usuario="Usuario (opcional)")
    async def stats(self, interaction: discord.Interaction, usuario: discord.Member = None):
        target = usuario or interaction.user
        datos = await db.get("personajes", str(target.id))
        if not datos:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        s = datos.get("stats", {})
        hp = s.get("hp", 100)
        hm = s.get("hp_max", 100)
        barra = "█" * int((hp / hm) * 10) + "░" * (10 - int((hp / hm) * 10))
        embed = discord.Embed(title=f"📊 Stats de {datos['nombre']}", color=discord.Color.blue())
        embed.add_field(name="❤️ HP", value=f"`{barra}` {hp}/{hm}", inline=False)
        for k, v in s.items():
            if k not in ("hp", "hp_max"):
                embed.add_field(name=k.title(), value=str(v), inline=True)
        embed.add_field(name="📚 Estudios", value=datos.get("estudios", "ninguno").title(), inline=True)
        embed.add_field(name="🎂 Edad", value=str(datos.get("edad", "?")), inline=True)
        embed.add_field(name="💼 Trabajo", value=datos.get("trabajo_display", "Desempleado"), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="inventario", description="Muestra tu inventario")
    async def inventario(self, interaction: discord.Interaction):
        datos = await db.get("personajes", str(interaction.user.id))
        if not datos:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        inv = datos.get("inventario", {})
        embed = discord.Embed(title=f"🎒 Inventario de {datos['nombre']}", color=discord.Color.gold())
        embed.add_field(name="💵 Dinero en efectivo", value=f"${datos.get('dinero', 0):.2f}", inline=False)
        if datos.get("deudas", 0) > 0:
            embed.add_field(name="💸 Deudas", value=f"${datos.get('deudas', 0):.2f}", inline=False)
        embed.add_field(name="Objetos", value="\n".join(f"• {v}x {k}" for k, v in inv.items()) or "Vacío.", inline=False)
        if datos.get("vehiculos"):
            embed.add_field(name="🚗 Vehículos", value=", ".join(datos["vehiculos"]), inline=False)
        tel = datos.get("telefono")
        if tel:
            embed.add_field(name="📱 Teléfono", value=tel, inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="familia", description="Muestra la familia de tu personaje")
    async def ver_familia(self, interaction: discord.Interaction):
        datos = await db.get("personajes", str(interaction.user.id))
        if not datos:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        fam = datos.get("familia", {})
        embed = discord.Embed(title=f"👨‍👩‍👧‍👦 Familia de {datos['nombre']}", color=0xF39C12)
        if fam.get("padre"):
            vivo_txt = "✅ Vivo" if fam["padre"].get("vivo", True) else "💀 Fallecido"
            embed.add_field(name="👨 Padre", value=f"{fam['padre']['nombre']}\n{fam['padre']['trabajo']} | {vivo_txt}", inline=True)
        if fam.get("madre"):
            vivo_txt = "✅ Viva" if fam["madre"].get("vivo", True) else "💀 Fallecida"
            embed.add_field(name="👩 Madre", value=f"{fam['madre']['nombre']}\n{fam['madre']['trabajo']} | {vivo_txt}", inline=True)
        if fam.get("vive_con_padres"):
            embed.add_field(name="🏠", value="Vive con sus padres", inline=True)
        if fam.get("pareja"):
            embed.add_field(name="💑 Pareja", value=fam["pareja"], inline=True)
        if fam.get("hijos"):
            embed.add_field(name="👶 Hijos", value=str(fam["hijos"]), inline=True)
        if not fam:
            embed.description = "Sin datos de familia registrados."
        embed.set_footer(text="Usa /npc_info <nombre> para ver detalles del NPC")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="cambiar_imagen", description="Cambia la foto de tu personaje")
    @app_commands.describe(url="URL de la nueva imagen")
    async def cambiar_imagen(self, interaction: discord.Interaction, url: str):
        datos = await db.get("personajes", str(interaction.user.id))
        if not datos:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        if not (url.startswith("http://") or url.startswith("https://")):
            return await interaction.response.send_message("❌ URL inválida.", ephemeral=True)
        await db.update("personajes", str(interaction.user.id), {"imagen_url": url})
        embed = discord.Embed(title="✅ Imagen actualizada", color=discord.Color.green())
        embed.set_thumbnail(url=url)
        embed.description = f"La foto de **{datos['nombre']}** fue actualizada."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        _webhook_cache.clear()

    @commands.command(name="crearPersonaje", aliases=["cp"])
    async def crear_personaje_prefix(self, ctx):
        if ctx.channel.id not in (CH_CREAR_DOC, CH_CREAR_DOC_OLD):
            return await ctx.send(f"❌ Ve a <#{CH_CREAR_DOC}>.", delete_after=5)
        existente = await db.get("personajes", str(ctx.author.id))
        if existente and not existente.get("muerto"):
            return await ctx.send("❌ Ya tienes un personaje activo.", delete_after=5)
        view = AbrirModalView(ctx.author.id)
        await ctx.send("📋 Haz clic para crear tu personaje:", view=view, delete_after=120)


async def setup(bot):
    await bot.add_cog(Personajes(bot))