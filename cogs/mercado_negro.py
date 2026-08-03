"""
cogs/mercado_negro.py — Sistema del Mercado Negro.
Drogas con pureza, crafteo de drogas, armas ilegales, venta a NPCs.
El crafteo de drogas requiere una casa y materiales.
"""
import discord
from discord.ext import commands
from discord import app_commands
import random
import time
from utils import db
from utils import lesiones as lesiones_mod

# ── DROGAS CON PUREZA ─────────────────────────────────────────────────────────
DROGAS = {
    "marihuana": {
        "display": "🟢 Producto Verde (Marihuana)",
        "precio_compra": 5.0,
        "precio_venta_mercado": 12.0,
        "riesgo": "bajo",
        "descripcion": "Bajo riesgo, baja ganancia.",
        "pureza_base": (60, 80),   # rango de pureza al comprar
    },
    "cocaina": {
        "display": "🔵 Producto Azul (Cocaína)",
        "precio_compra": 20.0,
        "precio_venta_mercado": 50.0,
        "riesgo": "medio",
        "descripcion": "Riesgo medio, ganancia media.",
        "pureza_base": (50, 75),
    },
    "crack": {
        "display": "🔴 Producto Rojo (Crack)",
        "precio_compra": 35.0,
        "precio_venta_mercado": 80.0,
        "riesgo": "alto",
        "descripcion": "Alto riesgo, alta ganancia.",
        "pureza_base": (40, 70),
    },
    "heroina": {
        "display": "⚫ Producto Negro (Heroína)",
        "precio_compra": 80.0,
        "precio_venta_mercado": 200.0,
        "riesgo": "extremo",
        "descripcion": "Máximo riesgo, máxima ganancia.",
        "pureza_base": (35, 65),
    },
    "pastillas": {
        "display": "💊 Pastillas (Benzodiacepinas)",
        "precio_compra": 10.0,
        "precio_venta_mercado": 25.0,
        "riesgo": "medio",
        "descripcion": "Prescripción sin receta.",
        "pureza_base": (70, 90),
    },
}

# ── RECETAS DE CRAFTEO DE DROGAS ──────────────────────────────────────────────
# La pureza resultante depende de la química del personaje
RECETAS_DROGAS = {
    "marihuana_casera": {
        "display": "🟢 Marihuana (cultivada)",
        "tipo_droga": "marihuana",
        "ingredientes": {
            "semillas": 3,
            "tierra_fertil": 2,
            "agua_botella": 2,
        },
        "cantidad_produce": 3,
        "pureza_min": 65,
        "pureza_max": 90,
        "pureza_quimica_bonus": 10,  # bonus si tiene estudios de quimica
        "duracion_horas": 72,       # tarda 72h en cultivar
        "requiere_casa": True,
        "descripcion": "Cultivo casero de marihuana. Alta pureza si sabes lo que haces.",
    },
    "cocaina_refinada": {
        "display": "🔵 Cocaína Refinada",
        "tipo_droga": "cocaina",
        "ingredientes": {
            "cocaina": 2,
            "acetona": 1,
            "bicarbonato": 1,
        },
        "cantidad_produce": 2,
        "pureza_min": 70,
        "pureza_max": 95,
        "pureza_quimica_bonus": 15,
        "duracion_horas": 12,
        "requiere_casa": True,
        "descripcion": "Purificación de cocaína. Necesitas cocaína del mercado y productos químicos.",
    },
    "crack_casero": {
        "display": "🔴 Crack (artesanal)",
        "tipo_droga": "crack",
        "ingredientes": {
            "cocaina": 1,
            "bicarbonato": 1,
            "encendedor": 1,
        },
        "cantidad_produce": 2,
        "pureza_min": 55,
        "pureza_max": 80,
        "pureza_quimica_bonus": 10,
        "duracion_horas": 6,
        "requiere_casa": True,
        "descripcion": "Procesamiento básico de crack. Rápido pero menos puro.",
    },
    "pastillas_falsas": {
        "display": "💊 Pastillas (falsificadas)",
        "tipo_droga": "pastillas",
        "ingredientes": {
            "harina": 2,
            "ibuprofeno": 3,
            "jeringa": 1,
        },
        "cantidad_produce": 5,
        "pureza_min": 30,
        "pureza_max": 60,
        "pureza_quimica_bonus": 20,
        "duracion_horas": 8,
        "requiere_casa": True,
        "descripcion": "Pastillas falsificadas. Baja pureza sin conocimientos de química.",
    },
    "heroina_sintetica": {
        "display": "⚫ Heroína Sintética",
        "tipo_droga": "heroina",
        "ingredientes": {
            "morfina": 2,
            "acetona": 2,
            "jeringa": 2,
        },
        "cantidad_produce": 1,
        "pureza_min": 60,
        "pureza_max": 92,
        "pureza_quimica_bonus": 20,
        "duracion_horas": 24,
        "requiere_casa": True,
        "descripcion": "Síntesis de heroína. Muy peligroso. Requiere conocimientos avanzados.",
    },
}

# Materiales que se pueden comprar en tiendas (para craftear drogas)
MATERIALES_CRAFTEO = {
    "semillas":       {"precio": 5.0,  "ubicaciones": ["mercado", "bodega", "tienda"]},
    "tierra_fertil":  {"precio": 3.0,  "ubicaciones": ["ferreteria", "mercado", "tienda"]},
    "acetona":        {"precio": 8.0,  "ubicaciones": ["ferreteria", "quimica", "laboratorio"]},
    "bicarbonato":    {"precio": 1.0,  "ubicaciones": ["bodega", "supermercado", "mercado", "cualquiera"]},
    "harina":         {"precio": 1.5,  "ubicaciones": ["bodega", "supermercado", "mercado", "cualquiera"]},
}

# ── ARMAS ILEGALES ────────────────────────────────────────────────────────────
ARMAS_ILEGALES_MN = {
    "glock_17":        {"daño": 38, "precio": 450,  "descripcion": "Glock 17 — la más común."},
    "beretta_92":      {"daño": 36, "precio": 500,  "descripcion": "Beretta 92. Clásica italiana."},
    "colt_m1911":      {"daño": 45, "precio": 700,  "descripcion": "Colt M1911. Mucho daño."},
    "desert_eagle":    {"daño": 65, "precio": 1500, "descripcion": "Desert Eagle. Monstruosa."},
    "sw_model_29":     {"daño": 60, "precio": 900,  "descripcion": "S&W Model 29. El Dirty Harry."},
    "mp5":             {"daño": 42, "precio": 2500, "descripcion": "HK MP5. Fuerzas especiales."},
    "uzi":             {"daño": 38, "precio": 1800, "descripcion": "Uzi israelí. Cadencia alta."},
    "ak47":            {"daño": 58, "precio": 3000, "descripcion": "AK-47. El más conocido."},
    "m4_carbine":      {"daño": 55, "precio": 3500, "descripcion": "M4 Carbine. Versátil."},
    "remington_870":   {"daño": 70, "precio": 1200, "descripcion": "Remington 870. Devastadora."},
    "navaja":          {"daño": 12, "precio": 15,   "descripcion": "Navaja de bolsillo."},
    "cuchillo_militar":{"daño": 22, "precio": 80,   "descripcion": "Cuchillo militar."},
    "punio_americano": {"daño": 18, "precio": 25,   "descripcion": "Puños americanos."},
    "daga":            {"daño": 28, "precio": 60,   "descripcion": "Daga de doble filo."},
    "chaleco_antibalas":{"defensa": 30, "precio": 300, "descripcion": "Reduce daño de bala 30%."},
}

CH_POLICIA_AVISO = 1359320808526450780
ROL_POLICIA      = 1359320808526450780


def _es_mercado_negro(canal_nombre: str) -> bool:
    return "mercado-negro" in canal_nombre or "mercado_negro" in canal_nombre


def _calcular_pureza(droga_key: str, receta: dict, datos: dict) -> int:
    """Calcula la pureza resultante según los skills del personaje."""
    pmin = receta["pureza_min"]
    pmax = receta["pureza_max"]
    # Base aleatoria
    pureza = random.randint(pmin, pmax)
    # Bonus si tiene estudios de química
    certs = datos.get("certificados", [])
    bonuses = datos.get("bonuses_trabajo", [])
    if "quimica" in certs or "quimico" in bonuses:
        pureza = min(99, pureza + receta.get("pureza_quimica_bonus", 0))
    # Bonus por stat inteligencia
    inteligencia = datos.get("stats", {}).get("inteligencia", 5)
    if inteligencia >= 10:
        pureza = min(99, pureza + 5)
    return pureza


def _precio_por_pureza(droga: dict, pureza: int, cantidad: int) -> float:
    """El precio de venta varía según la pureza."""
    precio_base = droga["precio_venta_mercado"]
    multiplicador = 0.5 + (pureza / 100)  # 50% a 150% según pureza
    return round(precio_base * multiplicador * cantidad, 2)


class MercadoNegro(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── /mercadonegro ──────────────────────────────────────────────────────────
    @app_commands.command(name="mercadonegro", description="Ver catálogo del mercado negro (solo en el mercado)")
    async def mercado_negro_slash(self, interaction: discord.Interaction):
        datos = await db.get("personajes", str(interaction.user.id))
        if not datos:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)

        canal_nombre = interaction.channel.name if interaction.channel else ""
        if not _es_mercado_negro(canal_nombre):
            return await interaction.response.send_message(
                "❌ Solo puedes consultar esto **en el mercado negro**.\n"
                "Viaja a `mercado-negro-petare`.", ephemeral=True
            )

        embed = discord.Embed(
            title="🖤 Mercado Negro — Catálogo Completo",
            description="**⚠️ SOLO ROLEPLAY FICTICIO**\nCuídate de la CPNB. Informantes en todos lados.",
            color=0x1a1a1a
        )

        embed.add_field(name="━━━ 💊 DROGAS ━━━", value="\u200b", inline=False)
        for key, d in DROGAS.items():
            pureza_txt = f"Pureza: {d['pureza_base'][0]}-{d['pureza_base'][1]}%"
            embed.add_field(
                name=d["display"],
                value=(
                    f"Compra: **${d['precio_compra']:.2f}** | Venta: **${d['precio_venta_mercado']:.2f}**\n"
                    f"Riesgo: `{d['riesgo'].upper()}` | {pureza_txt}\n"
                    f"_{d['descripcion']}_"
                ),
                inline=False
            )

        embed.add_field(name="━━━ 🧪 CRAFTEO DE DROGAS ━━━",
                        value="Usa `!recetas_drogas` para ver qué puedes fabricar en tu casa.", inline=False)

        embed.add_field(name="━━━ 🔫 ARMAS ILEGALES ━━━",
                        value="Solo aquí. Arrestado si la policía te registra.", inline=False)
        for nombre, info in list(ARMAS_ILEGALES_MN.items())[:8]:
            if "daño" in info:
                embed.add_field(name=f"`{nombre}` — ${info['precio']:,}",
                                value=f"💥 {info['daño']} dmg | {info['descripcion'][:40]}", inline=True)
            else:
                embed.add_field(name=f"`{nombre}` — ${info['precio']:,}",
                                value=f"🛡️ {info['defensa']}% def | {info['descripcion'][:40]}", inline=True)

        embed.add_field(
            name="📋 Comandos",
            value=(
                "`!comprar_droga <tipo> <cant>` | `!vender_droga <tipo> <cant>`\n"
                "`!vender_npc <npc> <tipo> <cant>` | `!comprar_arma_negra <nombre>`\n"
                "`!recetas_drogas` | `!craftear_droga <receta>`"
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed)

    @commands.command(name="mercadonegro")
    async def mercado_negro_prefix(self, ctx):
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        if not _es_mercado_negro(ctx.channel.name):
            return await ctx.send("❌ Solo en el mercado negro. Viaja a `mercado-negro-petare`.")
        embed = discord.Embed(title="🖤 Mercado Negro", description="⚠️ Solo roleplay ficticio.", color=0x1a1a1a)
        for key, d in DROGAS.items():
            embed.add_field(
                name=d["display"],
                value=f"Compra: ${d['precio_compra']:.2f} | Venta: ${d['precio_venta_mercado']:.2f} | Pureza: {d['pureza_base'][0]}-{d['pureza_base'][1]}%",
                inline=False
            )
        embed.set_footer(text="!comprar_droga | !vender_droga | !recetas_drogas | !craftear_droga | !comprar_arma_negra")
        await ctx.send(embed=embed)

    # ── !comprar_droga ─────────────────────────────────────────────────────────
    @commands.command(name="comprar_droga")
    async def comprar_droga(self, ctx, tipo: str, cantidad: int = 1):
        if not _es_mercado_negro(ctx.channel.name):
            return await ctx.send("❌ Solo en el mercado negro.")
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        tipo = tipo.lower()
        if tipo not in DROGAS:
            return await ctx.send(f"❌ Tipo no válido. Disponibles: {', '.join(DROGAS.keys())}")

        droga = DROGAS[tipo]
        costo = round(droga["precio_compra"] * cantidad, 2)
        dinero = datos.get("dinero", 0)
        if dinero < costo:
            return await ctx.send(f"❌ Necesitas ${costo:.2f}. Tienes ${dinero:.2f}.")

        # Calcular pureza aleatoria
        pmin, pmax = droga["pureza_base"]
        pureza = random.randint(pmin, pmax)

        inv = datos.get("inventario", {})
        # Guardar droga con su pureza (formato: "tipo_pureza%")
        key_inv = f"{tipo}_{pureza}pct"
        inv[key_inv] = inv.get(key_inv, 0) + cantidad
        # También guardar registro simple para compatibilidad
        inv[tipo] = inv.get(tipo, 0) + cantidad

        await db.update("personajes", str(ctx.author.id), {
            "inventario": inv,
            "dinero": round(dinero - costo, 2)
        })

        try:
            await ctx.message.delete()
        except:
            pass

        if random.random() < 0.15:
            ch_pol = ctx.guild.get_channel(CH_POLICIA_AVISO)
            rol_pol = ctx.guild.get_role(ROL_POLICIA)
            if ch_pol:
                ping = rol_pol.mention if rol_pol else "@CPNB"
                await ch_pol.send(f"🚨 {ping} Movimiento sospechoso en {ctx.channel.mention}.")

        await ctx.send(
            f"🤝 **{cantidad}x {tipo}** por **${costo:.2f}** | Pureza: **{pureza}%**\n"
            f"⚠️ Riesgo: `{droga['riesgo'].upper()}`",
            delete_after=25
        )

    # ── !vender_droga ─────────────────────────────────────────────────────────
    @commands.command(name="vender_droga")
    async def vender_droga(self, ctx, tipo: str, cantidad: int = 1):
        if not _es_mercado_negro(ctx.channel.name):
            return await ctx.send("❌ Solo en el mercado negro.")
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        tipo = tipo.lower()
        if tipo not in DROGAS:
            return await ctx.send(f"❌ No conocemos ese producto.")

        inv = datos.get("inventario", {})
        if inv.get(tipo, 0) < cantidad:
            return await ctx.send(f"❌ Solo tienes {inv.get(tipo, 0)}x {tipo}.")

        droga = DROGAS[tipo]

        # Buscar la pureza más alta en el inventario para esa droga
        mejor_pureza = 50
        for key in inv:
            if key.startswith(f"{tipo}_") and key.endswith("pct"):
                try:
                    p = int(key.split("_")[1].replace("pct", ""))
                    if p > mejor_pureza:
                        mejor_pureza = p
                except:
                    pass

        precio_real = _precio_por_pureza(droga, mejor_pureza, cantidad)
        precio_real = round(precio_real * random.uniform(0.85, 1.15), 2)

        inv[tipo] -= cantidad
        if inv[tipo] <= 0:
            del inv[tipo]

        await db.update("personajes", str(ctx.author.id), {
            "inventario": inv,
            "dinero": round(datos.get("dinero", 0) + precio_real, 2)
        })

        try:
            await ctx.message.delete()
        except:
            pass

        await ctx.send(
            f"💰 Vendiste **{cantidad}x {tipo}** (pureza ~{mejor_pureza}%) por **${precio_real:.2f}**.",
            delete_after=25
        )

    # ── !recetas_drogas ────────────────────────────────────────────────────────
    @commands.command(name="recetas_drogas", aliases=["r_drogas"])
    async def recetas_drogas(self, ctx):
        """Muestra las recetas de crafteo de drogas."""
        datos = await db.get("personajes", str(ctx.author.id))
        tiene_quimica = False
        if datos:
            certs = datos.get("certificados", [])
            bonuses = datos.get("bonuses_trabajo", [])
            tiene_quimica = "quimica" in certs or "quimico" in bonuses

        embed = discord.Embed(
            title="🧪 Recetas de Drogas",
            description=(
                "Puedes fabricar drogas **en tu casa** con los materiales correctos.\n"
                f"{'✅ Tienes estudios de Química: +pureza' if tiene_quimica else '⚠️ Sin estudios de Química: pureza reducida'}"
            ),
            color=0x1a1a1a
        )

        for key, receta in RECETAS_DROGAS.items():
            mats = "\n".join(f"• {v}x `{k}`" for k, v in receta["ingredientes"].items())
            pureza_txt = f"{receta['pureza_min']}-{receta['pureza_max']}%"
            if tiene_quimica:
                pureza_txt += f" (+{receta['pureza_quimica_bonus']}% bonus)"
            embed.add_field(
                name=f"`{key}` — {receta['display']}",
                value=(
                    f"**Materiales:**\n{mats}\n"
                    f"**Produce:** {receta['cantidad_produce']}x {receta['tipo_droga']}\n"
                    f"**Pureza:** {pureza_txt}\n"
                    f"**Tiempo:** {receta['duracion_horas']}h\n"
                    f"_{receta['descripcion']}_"
                ),
                inline=False
            )

        embed.set_footer(text="!craftear_droga <nombre_receta> — Iniciar fabricación (requiere estar en tu casa)")
        await ctx.send(embed=embed)

    # ── !consumir_droga ────────────────────────────────────────────────────────
    OVERDOSE_TABLA = {
        "bajo":    {"prob": 0.03, "lesion": "sobredosis_leve"},
        "medio":   {"prob": 0.08, "lesion": "sobredosis_leve"},
        "alto":    {"prob": 0.15, "lesion": "sobredosis_grave"},
        "extremo": {"prob": 0.25, "lesion": "sobredosis_grave"},
    }

    @commands.command(name="consumir_droga", aliases=["usar_droga"])
    async def consumir_droga(self, ctx, tipo: str):
        """Consume una droga de tu inventario. Es ficción de roleplay — mientras más
        fuerte/pura, más riesgo real de sobredosis (requiere hospital)."""
        tipo = tipo.lower()
        if tipo not in DROGAS:
            return await ctx.send(f"❌ Tipo no válido. Disponibles: {', '.join(DROGAS.keys())}")

        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        inv = datos.get("inventario", {})
        if inv.get(tipo, 0) <= 0:
            return await ctx.send(f"❌ No tienes **{tipo}** en tu inventario.")

        # Buscar la variante con pureza más alta que tengas, para escalar el riesgo
        pureza = 50
        for key in inv:
            if key.startswith(f"{tipo}_") and key.endswith("pct") and inv[key] > 0:
                try:
                    pureza = max(pureza, int(key.split("_")[1].replace("pct", "")))
                except ValueError:
                    pass

        droga = DROGAS[tipo]
        riesgo = droga["riesgo"]
        tabla = self.OVERDOSE_TABLA.get(riesgo, self.OVERDOSE_TABLA["medio"])
        factor_pureza = 0.5 + (pureza / 100)
        prob_sobredosis = min(0.60, tabla["prob"] * factor_pureza)

        inv[tipo] -= 1
        if inv[tipo] <= 0:
            del inv[tipo]
        await db.update("personajes", str(ctx.author.id), {"inventario": inv})

        if random.random() < prob_sobredosis:
            await lesiones_mod.agregar_lesion(ctx.author.id, tabla["lesion"])
            info_lesion = lesiones_mod.LESIONES_TIPOS[tabla["lesion"]]
            embed = discord.Embed(
                title="🚨 ¡SOBREDOSIS!",
                description=(
                    f"**{datos['nombre']}** consumió **{tipo}** (pureza {pureza}%) y tuvo una reacción grave.\n"
                    f"Sufre: **{info_lesion['display']}**. Ve a un hospital (`!ir_hospital`) o trátala con `!tratar_lesion {tabla['lesion']}`."
                ),
                color=discord.Color.dark_red()
            )
            if info_lesion.get("riesgo_muerte_sin_tratar"):
                embed.add_field(name="⚠️ Riesgo real", value="Si no se atiende a tiempo, puede morir.", inline=False)
            return await ctx.send(embed=embed)

        stats = datos.get("stats", {})
        hp = stats.get("hp", 100)
        hp_max = stats.get("hp_max", 100)
        alivio = {"bajo": 5, "medio": 10, "alto": 15, "extremo": 20}.get(riesgo, 5)
        hp_nuevo = min(hp_max, hp + alivio)
        stats["hp"] = hp_nuevo
        await db.update("personajes", str(ctx.author.id), {"stats": stats})

        await ctx.send(embed=discord.Embed(
            title=f"💨 {datos['nombre']} consume {tipo}",
            description=f"Sensación intensa, sin complicaciones esta vez. HP: {hp} → {hp_nuevo}/{hp_max}",
            color=discord.Color.dark_grey()
        ))

    # ── !craftear_droga ────────────────────────────────────────────────────────
    @commands.command(name="craftear_droga", aliases=["fabricar_droga"])
    async def craftear_droga(self, ctx, *, nombre_receta: str):
        """Fabrica drogas en tu casa. Requiere estar en el canal de tu casa."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        nombre_receta = nombre_receta.lower().replace(" ", "_")
        if nombre_receta not in RECETAS_DROGAS:
            recetas_txt = ", ".join(f"`{k}`" for k in RECETAS_DROGAS.keys())
            return await ctx.send(f"❌ Receta no encontrada. Disponibles: {recetas_txt}\nUsa `!recetas_drogas` para ver detalles.")

        receta = RECETAS_DROGAS[nombre_receta]

        # Verificar que está en su casa
        canal_actual = datos.get("canal_actual", "")
        mis_casas = datos.get("casas", [])

        en_casa_propia = False
        for casa_str in mis_casas:
            partes = casa_str.split(":")
            if len(partes) >= 2:
                sector = partes[0]
                casa_id = partes[1]
                # El nombre del canal puede ser casa-1-sector-nombre o similar
                if canal_actual.startswith("casa") and sector in canal_actual:
                    en_casa_propia = True
                    break
                if casa_id in canal_actual:
                    en_casa_propia = True
                    break

        if receta.get("requiere_casa") and not en_casa_propia:
            return await ctx.send(
                "❌ Para fabricar drogas necesitas estar **en el canal de tu propia casa**.\n"
                "Usa `/mi_casa` para ver tus propiedades y viaja a ella con `/viajar`."
            )

        # Verificar materiales
        inv = datos.get("inventario", {})
        ingredientes = receta["ingredientes"]
        faltantes = []
        for mat, cant in ingredientes.items():
            if inv.get(mat, 0) < cant:
                faltantes.append(f"{cant}x `{mat}` (tienes {inv.get(mat, 0)})")

        if faltantes:
            return await ctx.send(
                f"❌ Te faltan materiales:\n" + "\n".join(faltantes) +
                f"\n\nCompra materiales en mercados, ferreterías o farmacias."
            )

        # Verificar que no tiene ya un proceso activo
        crafteo_activo = datos.get("crafteo_droga_activo")
        if crafteo_activo and crafteo_activo.get("termina_ts", 0) > time.time():
            restante = int((crafteo_activo["termina_ts"] - time.time()) / 3600)
            return await ctx.send(f"❌ Ya tienes una fabricación en curso. Termina en {restante}h.")

        # Consumir materiales
        for mat, cant in ingredientes.items():
            inv[mat] -= cant
            if inv[mat] <= 0:
                del inv[mat]

        termina_ts = time.time() + receta["duracion_horas"] * 3600

        await db.update("personajes", str(ctx.author.id), {
            "inventario": inv,
            "crafteo_droga_activo": {
                "receta": nombre_receta,
                "inicio_ts": time.time(),
                "termina_ts": termina_ts,
                "canal": canal_actual,
            }
        })

        # Calcular pureza que obtendrá
        pureza_estimada = _calcular_pureza(nombre_receta, receta, datos)

        embed = discord.Embed(
            title=f"🧪 Fabricación iniciada: {receta['display']}",
            description=receta["descripcion"],
            color=0x9B59B6
        )
        embed.add_field(name="⏱️ Duración", value=f"{receta['duracion_horas']} horas")
        embed.add_field(name="📦 Producirá", value=f"{receta['cantidad_produce']}x {receta['tipo_droga']}")
        embed.add_field(name="✨ Pureza estimada", value=f"~{pureza_estimada}%")
        embed.set_footer(text="Serás notificado cuando esté listo. No salgas de casa o se cancela.")
        await ctx.send(embed=embed)

        try:
            await ctx.message.delete()
        except:
            pass

    # ── Task: resolver crafteos de drogas ─────────────────────────────────────
    def start_tasks(self):
        if not self._check_crafteos.is_running():
            self._check_crafteos.start()

    from discord.ext import tasks

    @tasks.loop(minutes=5)
    async def _check_crafteos(self):
        """Resuelve crafteos de drogas completados."""
        personajes = await db.all("personajes")
        now = time.time()

        for uid, datos in personajes.items():
            crafteo = datos.get("crafteo_droga_activo")
            if not crafteo:
                continue
            if now < crafteo.get("termina_ts", float("inf")):
                continue

            # Terminó
            nombre_receta = crafteo["receta"]
            receta = RECETAS_DROGAS.get(nombre_receta)
            if not receta:
                await db.update("personajes", uid, {"crafteo_droga_activo": None})
                continue

            # Verificar que sigue en su casa (si salió, pierde el progreso)
            canal_actual = datos.get("canal_actual", "")
            canal_original = crafteo.get("canal", "")
            
            if canal_actual != canal_original:
                await db.update("personajes", uid, {"crafteo_droga_activo": None})
                guild = self.bot.guilds[0] if self.bot.guilds else None
                if guild:
                    member = guild.get_member(int(uid))
                    if member:
                        try:
                            await member.send(
                                f"💥 **Fabricación arruinada**: Saliste de tu casa durante el proceso. "
                                f"Los materiales se perdieron."
                            )
                        except:
                            pass
                continue

            # Calcular pureza y agregar al inventario
            pureza = _calcular_pureza(nombre_receta, receta, datos)
            tipo_droga = receta["tipo_droga"]
            cantidad = receta["cantidad_produce"]

            inv = datos.get("inventario", {})
            key_inv = f"{tipo_droga}_{pureza}pct"
            inv[key_inv] = inv.get(key_inv, 0) + cantidad
            inv[tipo_droga] = inv.get(tipo_droga, 0) + cantidad

            await db.update("personajes", uid, {
                "inventario": inv,
                "crafteo_droga_activo": None,
            })

            guild = self.bot.guilds[0] if self.bot.guilds else None
            if guild:
                member = guild.get_member(int(uid))
                if member:
                    try:
                        embed = discord.Embed(
                            title=f"🧪 ¡Fabricación completada!",
                            description=f"**{receta['display']}** listo.",
                            color=0x2ECC71
                        )
                        embed.add_field(name="📦 Obtenido", value=f"{cantidad}x `{tipo_droga}`")
                        embed.add_field(name="✨ Pureza", value=f"**{pureza}%**")
                        droga = DROGAS.get(tipo_droga, {})
                        precio_est = _precio_por_pureza(droga, pureza, cantidad) if droga else 0
                        embed.add_field(name="💰 Valor estimado", value=f"~${precio_est:.2f}")
                        await member.send(embed=embed)
                    except:
                        pass

    # ── !vender_npc ────────────────────────────────────────────────────────────
    @commands.command(name="vender_npc")
    async def vender_npc(self, ctx, nombre_npc: str, tipo: str, cantidad: int = 1):
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        tipo = tipo.lower()
        if tipo not in DROGAS:
            return await ctx.send("❌ Producto no válido.")
        inv = datos.get("inventario", {})
        if inv.get(tipo, 0) < cantidad:
            return await ctx.send(f"❌ Solo tienes {inv.get(tipo, 0)}x {tipo}.")

        npc_id = nombre_npc.lower().replace(" ", "_")
        npc = await db.get("npcs", npc_id)
        if not npc:
            todos = await db.all("npcs")
            npc = next((v for v in todos.values() if nombre_npc.lower() in v.get("nombre", "").lower()), None)
        if not npc:
            return await ctx.send(f"❌ NPC `{nombre_npc}` no encontrado. Usa `!npc lista`.")
        if npc.get("ubicacion") != datos.get("ubicacion"):
            return await ctx.send(f"❌ **{npc['nombre']}** no está en tu zona actual.")

        if random.random() < 0.08:
            ch_pol = ctx.guild.get_channel(CH_POLICIA_AVISO)
            rol_pol = ctx.guild.get_role(ROL_POLICIA)
            if ch_pol:
                ping = rol_pol.mention if rol_pol else "@CPNB"
                await ch_pol.send(
                    f"🚨 {ping} **OPERACIÓN ENCUBIERTA**: **{datos['nombre']}** intentó vender "
                    f"`{tipo}` al agente **{npc['nombre']}**. Canal: {ctx.channel.mention}"
                )
            return await ctx.send(f"🚔 **¡ERA UNA TRAMPA!** {npc['nombre']} era agente encubierto.")

        droga = DROGAS[tipo]
        mejor_pureza = 50
        for key in inv:
            if key.startswith(f"{tipo}_") and key.endswith("pct"):
                try:
                    p = int(key.split("_")[1].replace("pct", ""))
                    if p > mejor_pureza:
                        mejor_pureza = p
                except:
                    pass
        ganancia = _precio_por_pureza(droga, mejor_pureza, cantidad)
        ganancia = round(ganancia * random.uniform(1.1, 1.5), 2)

        inv[tipo] -= cantidad
        if inv[tipo] <= 0:
            del inv[tipo]
        await db.update("personajes", str(ctx.author.id), {
            "inventario": inv,
            "dinero": round(datos.get("dinero", 0) + ganancia, 2)
        })

        embed = discord.Embed(
            title="🤝 Venta a NPC exitosa",
            description=f"**{npc['nombre']}** compró **{cantidad}x {tipo}** (pureza ~{mejor_pureza}%) por **${ganancia:.2f}**.",
            color=0x2ECC71
        )
        embed.set_footer(text="Transacción discreta.")
        await ctx.send(embed=embed, delete_after=60)
        try:
            await ctx.message.delete()
        except:
            pass

    # ── !comprar_arma_negra ────────────────────────────────────────────────────
    @commands.command(name="comprar_arma_negra", aliases=["arma_ilegal"])
    async def comprar_arma_negra(self, ctx, *, nombre: str):
        if not _es_mercado_negro(ctx.channel.name):
            return await ctx.send("❌ Las armas ilegales solo se consiguen en el **mercado negro** de Petare.")
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        nombre = nombre.lower().replace(" ", "_")
        info = ARMAS_ILEGALES_MN.get(nombre)
        if not info:
            armas_txt = ", ".join(f"`{k}`" for k in ARMAS_ILEGALES_MN.keys())
            return await ctx.send(f"❌ No disponible. Armas ilegales: {armas_txt}")
        precio = info["precio"]
        dinero = datos.get("dinero", 0)
        if dinero < precio:
            return await ctx.send(f"❌ Necesitas ${precio:,}. Tienes ${dinero:.2f}.")
        inv = datos.get("inventario", {})
        inv[nombre] = inv.get(nombre, 0) + 1
        await db.update("personajes", str(ctx.author.id), {
            "inventario": inv,
            "dinero": round(dinero - precio, 2)
        })
        try:
            await ctx.message.delete()
        except:
            pass
        await ctx.send(
            f"🔫 **{nombre.replace('_', ' ').title()}** adquirida por **${precio:,}**.\n"
            f"⚠️ Posesión ilegal. Si la CPNB te registra, te arrestan.",
            delete_after=30
        )

    # ── /armas ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="armas", description="Muestra dónde conseguir cada tipo de arma")
    async def armas_slash(self, interaction: discord.Interaction):
        datos = await db.get("personajes", str(interaction.user.id))
        canal_actual = datos.get("canal_actual", "") if datos else ""
        en_mercado = _es_mercado_negro(canal_actual)
        embed = discord.Embed(title="🔫 Armas Disponibles", color=0x8B0000)
        embed.add_field(
            name="✅ Armas Legales (ferreterías/tiendas)",
            value=("`cuchillo_cocina` $5 | `cuchillo` $8 | `bate_baseball` $30\n"
                   "`bate_metal` $45 | `machete` $25 | `hacha` $40\n"
                   "Usa `/comprar <item>` en el sitio correcto."),
            inline=False
        )
        embed.add_field(
            name="🔨 Crafteable",
            value=("`punial_improvisado` — cuerda+encendedor (80%)\n"
                   "`lanza_casero` — palo+cuchillo+cuerda (70%)\n"
                   "Usa `/craftear <item>`"),
            inline=False
        )
        if en_mercado:
            embed.add_field(
                name="🖤 Ilegales (mercado negro — estás aquí)",
                value="Pistoletazos, rifles, SMGs...\n`!comprar_arma_negra <nombre>` o `/mercadonegro`",
                inline=False
            )
        else:
            embed.add_field(
                name="🖤 Armas Ilegales",
                value="Solo en **mercado-negro-petare**.\n`/viajar mercado-negro-petare`",
                inline=False
            )
        embed.set_footer(text=f"📍 {canal_actual or 'desconocida'}")
        await interaction.response.send_message(embed=embed)

    # ── /mi_fabricacion ────────────────────────────────────────────────────────
    @app_commands.command(name="mi_fabricacion", description="Ver el estado de tu fabricación de drogas actual")
    async def mi_fabricacion(self, interaction: discord.Interaction):
        datos = await db.get("personajes", str(interaction.user.id))
        if not datos:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)
        crafteo = datos.get("crafteo_droga_activo")
        if not crafteo:
            return await interaction.response.send_message(
                "🧪 No tienes ninguna fabricación en curso. Usa `!craftear_droga <receta>`.",
                ephemeral=True
            )
        receta = RECETAS_DROGAS.get(crafteo["receta"], {})
        now = time.time()
        termina_ts = crafteo.get("termina_ts", now)
        restante_h = max(0, int((termina_ts - now) / 3600))
        restante_min = max(0, int(((termina_ts - now) % 3600) / 60))
        total_seg = termina_ts - crafteo.get("inicio_ts", termina_ts - 1)
        transcurrido = now - crafteo.get("inicio_ts", now)
        progreso = min(100, int((transcurrido / max(1, total_seg)) * 100))
        barra = "█" * (progreso // 10) + "░" * (10 - progreso // 10)
        embed = discord.Embed(
            title=f"🧪 Fabricando: {receta.get('display', crafteo['receta'])}",
            color=0x9B59B6
        )
        embed.add_field(name="📊 Progreso", value=f"`{barra}` {progreso}%", inline=False)
        embed.add_field(name="⏱️ Tiempo restante", value=f"{restante_h}h {restante_min}min")
        embed.add_field(name="📍 En canal", value=f"`{crafteo.get('canal','?')}`")
        embed.set_footer(text="⚠️ Si sales de tu casa, se cancela la fabricación.")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(MercadoNegro(bot))