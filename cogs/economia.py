"""
cogs/economia.py — Sistema económico: dinero, tienda con ubicaciones específicas,
préstamos, precios dinámicos, crafteo de objetos.
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import asyncio
from utils import db
from utils import impuestos

CH_PRECIOS = 1359320811420520609

# ── UBICACIONES DE COMPRA ─────────────────────────────────────────────────────
# "cualquiera" = se puede comprar en cualquier canal
# Lista de keywords: si el canal_actual contiene alguna de ellas, se puede comprar

TIENDA_ITEMS = {
    # ── COMIDA ────────────────────────────────────────────────────────────────
    "arepa":               {"precio": 1.5,    "categoria": "comida",  "descripcion": "+5 HP",   "ubicaciones": ["restaurante","tasca","bodega","cantina","parador","comida","pollos","cafe","puesto"]},
    "perro_caliente":      {"precio": 2.0,    "categoria": "comida",  "descripcion": "+5 HP",   "ubicaciones": ["restaurante","tasca","bodega","cantina","comida","pollos","puesto"]},
    "empanada":            {"precio": 1.0,    "categoria": "comida",  "descripcion": "+5 HP",   "ubicaciones": ["restaurante","tasca","bodega","cantina","comida","parador","puesto"]},
    "pabellon_criollo":    {"precio": 4.0,    "categoria": "comida",  "descripcion": "+15 HP",  "ubicaciones": ["restaurante","tasca","comida","cantina"]},
    "hallaca":             {"precio": 3.0,    "categoria": "comida",  "descripcion": "+10 HP",  "ubicaciones": ["restaurante","tasca","comida","bodega","mercado"]},
    "tequeño":             {"precio": 0.5,    "categoria": "comida",  "descripcion": "+3 HP",   "ubicaciones": ["restaurante","tasca","bodega","cantina","cafe","parador","puesto"]},
    "agua_botella":        {"precio": 0.5,    "categoria": "comida",  "descripcion": "+2 HP",   "ubicaciones": ["cualquiera"]},
    "refresco":            {"precio": 1.0,    "categoria": "comida",  "descripcion": "+2 HP",   "ubicaciones": ["restaurante","tasca","bodega","cantina","cafe","mercado","supermercado","automercado"]},
    "cafe_negro":          {"precio": 0.5,    "categoria": "comida",  "descripcion": "+1 HP",   "ubicaciones": ["cafe","tasca","restaurante","cantina","bodega"]},
    "malta":               {"precio": 0.8,    "categoria": "comida",  "descripcion": "+3 HP",   "ubicaciones": ["bodega","tasca","restaurante","mercado","supermercado","automercado"]},
    "ron_cacique":         {"precio": 5.0,    "categoria": "comida",  "descripcion": "Bebida/trueque", "ubicaciones": ["tasca","bodega","mercado","supermercado","automercado","licor"]},
    "cerveza_polar":       {"precio": 1.5,    "categoria": "comida",  "descripcion": "+2 HP",   "ubicaciones": ["tasca","bodega","restaurante","mercado","supermercado","automercado"]},
    "pollo_completo":      {"precio": 8.0,    "categoria": "comida",  "descripcion": "+20 HP",  "ubicaciones": ["restaurante","pollos","tasca","supermercado","automercado","mercado"]},
    "bolsa_arroz":         {"precio": 3.0,    "categoria": "comida",  "descripcion": "Alimento hogar", "ubicaciones": ["bodega","mercado","supermercado","automercado"]},
    "bolsa_caraotas":      {"precio": 2.0,    "categoria": "comida",  "descripcion": "Alimento hogar", "ubicaciones": ["bodega","mercado","supermercado","automercado"]},

    # ── MEDICINA ──────────────────────────────────────────────────────────────
    "ibuprofeno":          {"precio": 3.0,    "categoria": "medicina","descripcion": "Analgésico", "ubicaciones": ["farmacia","farmatodo","clinica","hospital","drogueria"]},
    "vendaje":             {"precio": 2.0,    "categoria": "medicina","descripcion": "+20 HP",  "ubicaciones": ["farmacia","farmatodo","clinica","hospital","drogueria","mercado"]},
    "kit_medico":          {"precio": 15.0,   "categoria": "medicina","descripcion": "+50 HP",  "ubicaciones": ["farmacia","farmatodo","clinica","hospital"]},
    "suero_oral":          {"precio": 1.5,    "categoria": "medicina","descripcion": "+10 HP",  "ubicaciones": ["farmacia","farmatodo","clinica","hospital","drogueria","bodega"]},
    "antibioticos":        {"precio": 12.0,   "categoria": "medicina","descripcion": "+15 HP",  "ubicaciones": ["farmacia","farmatodo","clinica","hospital"]},
    "morfina":             {"precio": 40.0,   "categoria": "medicina","descripcion": "+35 HP",  "ubicaciones": ["hospital","clinica","emergencia"]},
    "jeringa":             {"precio": 0.5,    "categoria": "medicina","descripcion": "Jeringa",  "ubicaciones": ["farmacia","farmatodo","hospital","clinica"]},
    "desfibrilador":       {"precio": 200.0,  "categoria": "medicina","descripcion": "Emergencias", "ubicaciones": ["hospital","clinica","emergencia"]},
    "sangre_tipo_o":       {"precio": 80.0,   "categoria": "medicina","descripcion": "+60 HP",  "ubicaciones": ["hospital","clinica","emergencia"]},
    "gasa_esteril":        {"precio": 1.5,    "categoria": "medicina","descripcion": "+12 HP",  "ubicaciones": ["farmacia","farmatodo","hospital","clinica","drogueria"]},
    "agua_oxigenada":      {"precio": 1.0,    "categoria": "medicina","descripcion": "+8 HP",   "ubicaciones": ["farmacia","farmatodo","clinica","drogueria","bodega"]},
    "torniquete":          {"precio": 5.0,    "categoria": "medicina","descripcion": "+25 HP",  "ubicaciones": ["farmacia","farmatodo","hospital","clinica"]},
    "botiquin_hogar":      {"precio": 18.0,   "categoria": "medicina","descripcion": "+30 HP",  "ubicaciones": ["farmacia","farmatodo","supermercado","automercado"]},

    # ── HERRAMIENTAS ──────────────────────────────────────────────────────────
    "linterna":            {"precio": 5.0,    "categoria": "herramienta","descripcion": "Apagones", "ubicaciones": ["ferreteria","supermercado","automercado","tienda","bodega"]},
    "candado":             {"precio": 4.0,    "categoria": "herramienta","descripcion": "Seguridad", "ubicaciones": ["ferreteria","supermercado","automercado","tienda"]},
    "llave_inglesa":       {"precio": 8.0,    "categoria": "herramienta","descripcion": "Herramienta/arma", "ubicaciones": ["ferreteria","taller","garage"]},
    "palanca":             {"precio": 12.0,   "categoria": "herramienta","descripcion": "Abre puertas", "ubicaciones": ["ferreteria","taller","garage"]},
    "maletin_herramientas":{"precio": 35.0,   "categoria": "herramienta","descripcion": "Set completo", "ubicaciones": ["ferreteria","taller"]},
    "taladro":             {"precio": 50.0,   "categoria": "herramienta","descripcion": "Construcción", "ubicaciones": ["ferreteria"]},
    "generador_electrico": {"precio": 300.0,  "categoria": "herramienta","descripcion": "Electricidad", "ubicaciones": ["ferreteria","zona_industrial","taller"]},
    "bidan_gasolina":      {"precio": 15.0,   "categoria": "herramienta","descripcion": "10L gasolina", "ubicaciones": ["gasolinera","pdvsa","bomba"]},
    "hacha_lena":          {"precio": 20.0,   "categoria": "herramienta","descripcion": "Leña/arma", "ubicaciones": ["ferreteria","mercado"]},

    # ── ROPA Y EQUIPO ─────────────────────────────────────────────────────────
    "mochila":             {"precio": 12.0,   "categoria": "ropa",   "descripcion": "+5 slots",  "ubicaciones": ["tienda","supermercado","automercado","mercado","cc","mall"]},
    "casco":               {"precio": 15.0,   "categoria": "ropa",   "descripcion": "Protección", "ubicaciones": ["tienda","ferreteria","concesionario","mercado"]},
    "ropa_basica":         {"precio": 5.0,    "categoria": "ropa",   "descripcion": "Ropa diaria","ubicaciones": ["tienda","mercado","bodega","cc","mall","supermercado","automercado"]},
    "ropa_formal":         {"precio": 30.0,   "categoria": "ropa",   "descripcion": "+5 carisma", "ubicaciones": ["tienda","cc","mall"]},
    "ropa_tactica":        {"precio": 80.0,   "categoria": "ropa",   "descripcion": "Sigilo nocturno", "ubicaciones": ["tienda","mercado_negro"]},
    "chaleco_trabajo":     {"precio": 10.0,   "categoria": "ropa",   "descripcion": "Para obras", "ubicaciones": ["ferreteria","tienda","zona_industrial"]},
    "botas_militares":     {"precio": 45.0,   "categoria": "ropa",   "descripcion": "+2 resistencia","ubicaciones": ["tienda","ferreteria","cc","mall"]},
    "gorra":               {"precio": 3.0,    "categoria": "ropa",   "descripcion": "Sol y estilo","ubicaciones": ["tienda","bodega","mercado","cc","mall","supermercado"]},
    "impermeable":         {"precio": 18.0,   "categoria": "ropa",   "descripcion": "Para lluvia", "ubicaciones": ["tienda","supermercado","automercado","cc","mall"]},

    # ── TECNOLOGÍA ────────────────────────────────────────────────────────────
    "telefono_basico":     {"precio": 25.0,   "categoria": "tech",   "descripcion": "Llamadas/SMS","ubicaciones": ["tienda","cc","mall","supermercado","automercado","mercado"]},
    "smartphone":          {"precio": 120.0,  "categoria": "tech",   "descripcion": "Apps y redes","ubicaciones": ["tienda","cc","mall","tech"]},
    "smartphone_premium":  {"precio": 400.0,  "categoria": "tech",   "descripcion": "+hackeo",    "ubicaciones": ["tienda","cc","mall","tech"]},
    "walkie_talkie":       {"precio": 30.0,   "categoria": "tech",   "descripcion": "Sin teléfono","ubicaciones": ["tienda","ferreteria","mercado","tech"]},
    "radio_portatil":      {"precio": 20.0,   "categoria": "tech",   "descripcion": "Frecuencias policiales","ubicaciones": ["tienda","ferreteria","tech"]},
    "camara_vigilancia":   {"precio": 80.0,   "categoria": "tech",   "descripcion": "Vigilancia", "ubicaciones": ["tienda","ferreteria","tech","cc"]},
    "television":          {"precio": 60.0,   "categoria": "tech",   "descripcion": "Noticias",   "ubicaciones": ["tienda","supermercado","automercado","cc","mall","tech"]},
    "tablet":              {"precio": 80.0,   "categoria": "tech",   "descripcion": "Internet",   "ubicaciones": ["tienda","cc","mall","tech"]},
    "pendrive_encriptado": {"precio": 15.0,   "categoria": "tech",   "descripcion": "Info segura","ubicaciones": ["tienda","tech","cc"]},
    "disco_duro_externo":  {"precio": 50.0,   "categoria": "tech",   "descripcion": "Almacenamiento","ubicaciones": ["tienda","tech","cc","mall"]},

    # ── VEHÍCULOS ─────────────────────────────────────────────────────────────
    "bicicleta":           {"precio": 80.0,   "categoria": "vehiculo","descripcion": "Transporte", "ubicaciones": ["concesionario","tienda","mercado","bodega"]},
    "moto_basica":         {"precio": 600.0,  "categoria": "vehiculo","descripcion": "Rápida en ciudad","ubicaciones": ["concesionario"]},
    "carro_basico":        {"precio": 2500.0, "categoria": "vehiculo","descripcion": "Carro económico","ubicaciones": ["concesionario","rent"]},
    "carro_mediano":       {"precio": 8000.0, "categoria": "vehiculo","descripcion": "Confiable",  "ubicaciones": ["concesionario"]},
    "carro_lujoso":        {"precio": 25000.0,"categoria": "vehiculo","descripcion": "+carisma",   "ubicaciones": ["concesionario"]},
    "camioneta_4x4":       {"precio": 35000.0,"categoria": "vehiculo","descripcion": "Todo terreno","ubicaciones": ["concesionario"]},

    # ── DOCUMENTOS ────────────────────────────────────────────────────────────
    "cedula_venezolana":   {"precio": 10.0,   "categoria": "documento","descripcion": "ID Venezuela","ubicaciones": ["registro","notaria","saren"]},
    "pasaporte":           {"precio": 50.0,   "categoria": "documento","descripcion": "Viajes internacionales","ubicaciones": ["registro","notaria","saime"]},
    "licencia_conducir":   {"precio": 20.0,   "categoria": "documento","descripcion": "Para taxista","ubicaciones": ["registro","notaria","intt"]},
    "permiso_porte_armas": {"precio": 150.0,  "categoria": "documento","descripcion": "Porte legal","ubicaciones": ["comisaria","policia","cpnb","cicpc"]},
    "carnet_prensa":       {"precio": 30.0,   "categoria": "documento","descripcion": "Acceso restringido","ubicaciones": ["registro","notaria","cnp"]},

    # ── HOGAR ─────────────────────────────────────────────────────────────────
    "colchon":             {"precio": 25.0,   "categoria": "hogar",  "descripcion": "+HP al descansar","ubicaciones": ["tienda","mercado","supermercado","automercado","cc","mall"]},
    "nevera_pequena":      {"precio": 80.0,   "categoria": "hogar",  "descripcion": "Conserva comida","ubicaciones": ["tienda","supermercado","automercado","cc","mall"]},
    "cocina_gas":          {"precio": 60.0,   "categoria": "hogar",  "descripcion": "Para cocinar","ubicaciones": ["tienda","supermercado","automercado","ferreteria","cc","mall"]},
    "bombonas_gas":        {"precio": 5.0,    "categoria": "hogar",  "descripcion": "Gas doméstico","ubicaciones": ["gasolinera","pdvsa","bodega","tienda"]},
    "ventilador":          {"precio": 15.0,   "categoria": "hogar",  "descripcion": "Calor venezolano","ubicaciones": ["tienda","supermercado","automercado","cc","mall"]},
    "candado_reforzado":   {"precio": 20.0,   "categoria": "hogar",  "descripcion": "-50% robo","ubicaciones": ["ferreteria","supermercado","automercado","tienda"]},

    # ── ARMAS LEGALES ─────────────────────────────────────────────────────────
    "cuchillo_cocina":     {"precio": 5.0,    "categoria": "arma",   "descripcion": "+10 daño melee","ubicaciones": ["bodega","supermercado","automercado","mercado","tienda","cualquiera"]},
    "cuchillo":            {"precio": 8.0,    "categoria": "arma",   "descripcion": "+15 daño melee","ubicaciones": ["bodega","mercado","ferreteria","tienda"]},
    "bate_baseball":       {"precio": 30.0,   "categoria": "arma",   "descripcion": "+25 daño melee","ubicaciones": ["tienda","mercado","bodega","ferreteria"]},
    "bate_metal":          {"precio": 45.0,   "categoria": "arma",   "descripcion": "+30 daño melee","ubicaciones": ["tienda","ferreteria"]},
    "machete":             {"precio": 25.0,   "categoria": "arma",   "descripcion": "+35 daño",      "ubicaciones": ["ferreteria","mercado","bodega","tienda"]},
    "hacha":               {"precio": 40.0,   "categoria": "arma",   "descripcion": "+40 daño",      "ubicaciones": ["ferreteria","mercado","tienda"]},
    "llave_inglesa":       {"precio": 8.0,    "categoria": "herramienta","descripcion": "Herramienta/arma","ubicaciones": ["ferreteria","taller","garage"]},

    # ── MISCELÁNEOS ───────────────────────────────────────────────────────────
    "cigarro":             {"precio": 0.5,    "categoria": "misc",   "descripcion": "Trueque en prisión","ubicaciones": ["bodega","tasca","mercado","tienda","cualquiera"]},
    "encendedor":          {"precio": 0.5,    "categoria": "misc",   "descripcion": "Múltiples usos","ubicaciones": ["bodega","tasca","mercado","tienda","cualquiera"]},
    "cuerda":              {"precio": 3.0,    "categoria": "misc",   "descripcion": "10m de cuerda","ubicaciones": ["ferreteria","mercado","bodega","tienda"]},
    "spray_pintura":       {"precio": 2.0,    "categoria": "misc",   "descripcion": "Grafitis/territorio","ubicaciones": ["ferreteria","tienda","mercado"]},
    "binoculares":         {"precio": 25.0,   "categoria": "misc",   "descripcion": "Vigilar desde lejos","ubicaciones": ["tienda","ferreteria","cc","mall"]},
    "maletin_diplomatico": {"precio": 80.0,   "categoria": "misc",   "descripcion": "Transporte discreto","ubicaciones": ["tienda","cc","mall"]},
    "mapa_caracas":        {"precio": 2.0,    "categoria": "misc",   "descripcion": "+orientación","ubicaciones": ["bodega","tienda","mercado","cualquiera"]},
    "bolsa_basura":        {"precio": 0.3,    "categoria": "misc",   "descripcion": "Ocultar cosas","ubicaciones": ["bodega","supermercado","automercado","mercado","cualquiera"]},
}

precios_actuales = {k: v["precio"] for k, v in TIENDA_ITEMS.items()}

# ── RECETAS DE CRAFTEO ────────────────────────────────────────────────────────
RECETAS = {
    "punial_improvisado": {
        "ingredientes": {"cuerda": 1, "encendedor": 1},
        "descripcion": "Punzón artesanal improvisado. +15 daño melee.",
        "probabilidad": 0.80,
        "requiere_canal": None,  # cualquier sitio
    },
    "bomba_molotov": {
        "ingredientes": {"bidan_gasolina": 1, "trapo_viejo": 1, "encendedor": 1},
        "descripcion": "⚠️ Bomba molotov. Explosivo artesanal.",
        "probabilidad": 0.65,
        "requiere_canal": None,
    },
    "botiquin_improvisado": {
        "ingredientes": {"vendaje": 2, "agua_oxigenada": 1},
        "descripcion": "Botiquín improvisado. +20 HP.",
        "probabilidad": 0.90,
        "requiere_canal": None,
    },
    "escudo_improvisado": {
        "ingredientes": {"mochila": 1, "ropa_tactica": 1},
        "descripcion": "Escudo improvisado. Reduce daño 15%.",
        "probabilidad": 0.60,
        "requiere_canal": ["taller","garage","ferreteria"],
    },
    "lanza_casero": {
        "ingredientes": {"palo": 1, "cuchillo": 1, "cuerda": 1},
        "descripcion": "Lanza artesanal. +20 daño melee.",
        "probabilidad": 0.70,
        "requiere_canal": None,
    },
    "radio_improvisada": {
        "ingredientes": {"walkie_talkie": 1, "pendrive_encriptado": 1},
        "descripcion": "Radio encriptada artesanal para comunicaciones seguras.",
        "probabilidad": 0.55,
        "requiere_canal": ["taller","laboratorio","tech"],
    },
}

# ── OBJETOS QUE SE PUEDEN ENCONTRAR EN ZONAS RANDOM ──────────────────────────
OBJETOS_RANDOM_POR_ZONA = {
    "peligro": ["punial_improvisado", "navaja", "cuchillo", "cuerda", "cigarro"],
    "barrio":  ["cigarro", "encendedor", "cuerda", "bate_baseball", "ropa_basica", "vendaje"],
    "mercado": ["cuchillo_cocina", "ropa_basica", "bolsa_arroz", "bolsa_basura", "agua_botella"],
    "general": ["agua_botella", "cigarro", "encendedor", "mapa_caracas", "refresco"],
    "monte":   ["cuerda", "hacha_lena", "llave_inglesa", "punial_improvisado"],
}

# Efectos de uso de objetos
EFECTOS_USO = {
    "vendaje":           {"hp": 20, "msg": "🩹 Usaste un vendaje. +20 HP."},
    "kit_medico":        {"hp": 50, "msg": "🏥 Usaste kit médico. +50 HP."},
    "suero_oral":        {"hp": 10, "msg": "💧 Tomaste suero oral. +10 HP."},
    "antibioticos":      {"hp": 15, "msg": "💊 Tomaste antibióticos. +15 HP."},
    "morfina":           {"hp": 35, "msg": "💉 Morfina administrada. +35 HP. ⚠️ Controlada."},
    "sangre_tipo_o":     {"hp": 60, "msg": "🩸 Transfusión realizada. +60 HP."},
    "gasa_esteril":      {"hp": 12, "msg": "🩺 Gasa estéril aplicada. +12 HP."},
    "agua_oxigenada":    {"hp": 8,  "msg": "🫧 Herida desinfectada. +8 HP."},
    "torniquete":        {"hp": 25, "msg": "🩹 Torniquete aplicado. +25 HP."},
    "botiquin_hogar":    {"hp": 30, "msg": "🏥 Botiquín del hogar. +30 HP."},
    "botiquin_improvisado": {"hp": 20, "msg": "🩹 Botiquín improvisado. +20 HP."},
    "arepa":             {"hp": 5,  "msg": "🫓 Comiste una arepa. +5 HP."},
    "empanada":          {"hp": 5,  "msg": "🥟 Comiste una empanada. +5 HP."},
    "perro_caliente":    {"hp": 5,  "msg": "🌭 Comiste un perro caliente. +5 HP."},
    "pabellon_criollo":  {"hp": 15, "msg": "🍽️ Comiste pabellón criollo. +15 HP."},
    "hallaca":           {"hp": 10, "msg": "🫔 Comiste una hallaca. +10 HP."},
    "pollo_completo":    {"hp": 20, "msg": "🍗 Te comiste el pollo. +20 HP."},
    "tequeño":           {"hp": 3,  "msg": "🧀 Comiste un tequeño. +3 HP."},
    "agua_botella":      {"hp": 2,  "msg": "💧 Tomaste agua. +2 HP."},
    "refresco":          {"hp": 2,  "msg": "🥤 Tomaste un refresco. +2 HP."},
    "malta":             {"hp": 3,  "msg": "🍺 Tomaste una malta. +3 HP."},
}


def _verificar_ubicacion(canal_actual: str, ubicaciones: list) -> bool:
    """Verifica si el canal actual permite comprar el item."""
    if "cualquiera" in ubicaciones:
        return True
    return any(u in canal_actual for u in ubicaciones)


def _desc_ubicaciones(ubicaciones: list) -> str:
    if "cualquiera" in ubicaciones:
        return "En cualquier lugar"
    return ", ".join(f"`{u}`" for u in ubicaciones[:4])


class Economia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def start_tasks(self):
        if not self.fluctuacion_precios.is_running():
            self.fluctuacion_precios.start()

    @tasks.loop(hours=1)
    async def fluctuacion_precios(self):
        for item in precios_actuales:
            base = TIENDA_ITEMS[item]["precio"]
            factor = random.uniform(0.95, 1.08)
            precios_actuales[item] = round(precios_actuales[item] * factor, 2)
            precios_actuales[item] = max(base * 0.5, min(base * 3, precios_actuales[item]))

    # ── /tienda ───────────────────────────────────────────────────────────────
    @app_commands.command(name="tienda", description="Muestra los artículos disponibles en la tienda del lugar actual")
    @app_commands.describe(categoria="Categoría: comida, medicina, herramienta, ropa, tech, vehiculo, documento, hogar, misc, arma")
    async def tienda_slash(self, interaction: discord.Interaction, categoria: str = None):
        await self._mostrar_tienda(interaction, categoria)

    @commands.command(name="tienda")
    async def tienda_prefix(self, ctx, categoria: str = None):
        await self._mostrar_tienda(ctx, categoria)

    async def _mostrar_tienda(self, ctx_or_inter, categoria: str = None):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        user = ctx_or_inter.user if is_slash else ctx_or_inter.author

        datos = await db.get("personajes", str(user.id))
        canal_actual = datos.get("canal_actual", "") if datos else ""

        # Filtrar items disponibles en la ubicación actual
        items_disponibles = []
        for nombre, info in TIENDA_ITEMS.items():
            if categoria and info["categoria"] != categoria.lower():
                continue
            if _verificar_ubicacion(canal_actual, info.get("ubicaciones", ["cualquiera"])):
                items_disponibles.append((nombre, info))

        if not items_disponibles:
            msg = (f"❌ No hay artículos disponibles aquí"
                   + (f" en la categoría `{categoria}`" if categoria else "")
                   + f".\nEstás en: `{canal_actual or 'ninguno'}`\n"
                   + "Muévete a un mercado, farmacia, ferretería, etc.")
            if is_slash:
                return await ctx_or_inter.response.send_message(msg, ephemeral=True)
            return await ctx_or_inter.send(msg)

        embed = discord.Embed(
            title=f"🛒 Tienda — {canal_actual or 'General'}",
            description="Usa `/comprar <item>` para comprar.\nSolo ves lo que está disponible aquí.",
            color=discord.Color.gold()
        )
        categorias_usadas = {}
        for nombre, info in items_disponibles:
            cat = info["categoria"]
            precio = precios_actuales.get(nombre, info["precio"])
            categorias_usadas.setdefault(cat, []).append(f"`{nombre}` — ${precio:.2f}")

        cat_emojis = {
            "comida": "🍽️", "medicina": "💊", "herramienta": "🔧",
            "arma": "🗡️", "tech": "📱", "vehiculo": "🚲",
            "documento": "📄", "ropa": "👕", "hogar": "🏠", "misc": "🎒"
        }
        for cat, lista in categorias_usadas.items():
            embed.add_field(
                name=f"{cat_emojis.get(cat,'•')} {cat.title()} ({len(lista)})",
                value="\n".join(lista[:8]) + (f"\n_...y {len(lista)-8} más_" if len(lista) > 8 else ""),
                inline=True
            )
        embed.set_footer(text=f"📍 {canal_actual} | /tienda <categoria> para filtrar")
        if is_slash:
            await ctx_or_inter.response.send_message(embed=embed)
        else:
            await ctx_or_inter.send(embed=embed)

    # ── /comprar ──────────────────────────────────────────────────────────────
    @app_commands.command(name="comprar", description="Compra un artículo (debes estar en el lugar correcto)")
    @app_commands.describe(item="Nombre del item a comprar")
    async def comprar_slash(self, interaction: discord.Interaction, item: str):
        await self._comprar(interaction, item.lower().replace(" ", "_"))

    @commands.command(name="comprar")
    async def comprar_prefix(self, ctx, *, item: str):
        await self._comprar(ctx, item.lower().replace(" ", "_"))

    async def _comprar(self, ctx_or_inter, item: str):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        user = ctx_or_inter.user if is_slash else ctx_or_inter.author

        async def reply(msg, embed=None, ephemeral=False):
            if is_slash:
                await ctx_or_inter.response.send_message(msg, embed=embed, ephemeral=ephemeral)
            else:
                await ctx_or_inter.send(msg, embed=embed)

        if item not in TIENDA_ITEMS:
            return await reply(
                f"❌ Item `{item}` no existe. Usa `/tienda` para ver lo disponible aquí.",
                ephemeral=True
            )

        datos = await db.get("personajes", str(user.id))
        if not datos:
            return await reply("❌ No tienes personaje.", ephemeral=True)

        canal_actual = datos.get("canal_actual", "")
        ubicaciones = TIENDA_ITEMS[item].get("ubicaciones", ["cualquiera"])

        if not _verificar_ubicacion(canal_actual, ubicaciones):
            return await reply(
                f"❌ No puedes comprar **{item}** aquí.\n"
                f"📍 Disponible en: {_desc_ubicaciones(ubicaciones)}\n"
                f"Usa `/viajar` para llegar al lugar correcto.",
                ephemeral=True
            )

        precio = precios_actuales.get(item, TIENDA_ITEMS[item]["precio"])
        cat = TIENDA_ITEMS[item]["categoria"]
        tasa_iva = impuestos.tasa_iva(cat)
        monto_iva = round(precio * tasa_iva, 2)
        precio_total = round(precio + monto_iva, 2)

        dinero = datos.get("dinero", 0)
        if dinero < precio_total:
            return await reply(
                f"❌ Necesitas ${precio_total:,.2f} (${precio:,.2f} + ${monto_iva:,.2f} de IVA), "
                f"tienes ${dinero:,.2f}.", ephemeral=True
            )

        if cat == "vehiculo":
            vehiculos = datos.get("vehiculos", [])
            vehiculos.append(item)
            await db.update("personajes", str(user.id), {"vehiculos": vehiculos, "dinero": round(dinero - precio_total, 2)})
        else:
            inv = datos.get("inventario", {})
            inv[item] = inv.get(item, 0) + 1
            await db.update("personajes", str(user.id), {"inventario": inv, "dinero": round(dinero - precio_total, 2)})

        if monto_iva > 0:
            await impuestos.recaudar(monto_iva, concepto=f"iva_{cat}")

        embed = discord.Embed(
            title="✅ Compra realizada",
            description=f"Compraste **{item.replace('_', ' ')}**",
            color=discord.Color.green()
        )
        embed.add_field(name="📦 Descripción", value=TIENDA_ITEMS[item]["descripcion"])
        embed.add_field(name="Precio base", value=f"${precio:,.2f}", inline=True)
        embed.add_field(name=f"IVA ({tasa_iva*100:.0f}% · {cat})", value=f"${monto_iva:,.2f}", inline=True)
        embed.add_field(name="💵 Total pagado", value=f"${precio_total:,.2f}", inline=True)
        embed.add_field(name="Saldo restante", value=f"${dinero - precio_total:,.2f}", inline=False)
        await reply("", embed=embed)

    # ── /vender ───────────────────────────────────────────────────────────────
    @app_commands.command(name="vender", description="Vende un artículo de tu inventario (50% del precio)")
    @app_commands.describe(item="Item a vender")
    async def vender_slash(self, interaction: discord.Interaction, item: str):
        await self._vender(interaction, item.lower().replace(" ", "_"))

    @commands.command(name="vender")
    async def vender_prefix(self, ctx, *, item: str):
        await self._vender(ctx, item.lower().replace(" ", "_"))

    async def _vender(self, ctx_or_inter, item: str):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        user = ctx_or_inter.user if is_slash else ctx_or_inter.author

        async def reply(msg, ephemeral=False):
            if is_slash:
                await ctx_or_inter.response.send_message(msg, ephemeral=ephemeral)
            else:
                await ctx_or_inter.send(msg)

        datos = await db.get("personajes", str(user.id))
        if not datos:
            return await reply("❌ Sin personaje.", ephemeral=True)

        inv = datos.get("inventario", {})
        vehiculos = datos.get("vehiculos", [])
        if item not in inv and item not in vehiculos:
            return await reply(f"❌ No tienes `{item}` en tu inventario.", ephemeral=True)

        precio_base = precios_actuales.get(item, TIENDA_ITEMS.get(item, {}).get("precio", 5))
        precio_venta = round(precio_base * 0.5, 2)
        dinero = datos.get("dinero", 0)

        if item in inv:
            inv[item] -= 1
            if inv[item] <= 0:
                del inv[item]
            await db.update("personajes", str(user.id), {"inventario": inv, "dinero": round(dinero + precio_venta, 2)})
        else:
            vehiculos.remove(item)
            await db.update("personajes", str(user.id), {"vehiculos": vehiculos, "dinero": round(dinero + precio_venta, 2)})

        await reply(f"💰 Vendiste **{item.replace('_', ' ')}** por **${precio_venta:.2f}**. Saldo: ${dinero + precio_venta:.2f}")

    # ── /usar ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="usar", description="Usa un objeto del inventario")
    @app_commands.describe(item="Item a usar")
    async def usar_slash(self, interaction: discord.Interaction, item: str):
        await self._usar(interaction, item.lower().replace(" ", "_"))

    @commands.command(name="usar")
    async def usar_prefix(self, ctx, *, item: str):
        await self._usar(ctx, item.lower().replace(" ", "_"))

    async def _usar(self, ctx_or_inter, item: str):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        user = ctx_or_inter.user if is_slash else ctx_or_inter.author

        async def reply(msg, ephemeral=False):
            if is_slash:
                await ctx_or_inter.response.send_message(msg, ephemeral=ephemeral)
            else:
                await ctx_or_inter.send(msg)

        datos = await db.get("personajes", str(user.id))
        if not datos:
            return await reply("❌ Sin personaje.", ephemeral=True)

        inv = datos.get("inventario", {})
        if item not in inv or inv[item] <= 0:
            return await reply(f"❌ No tienes `{item}`.", ephemeral=True)

        stats = datos.get("stats", {})
        hp = stats.get("hp", 100)
        hp_max = stats.get("hp_max", 100)

        efecto = EFECTOS_USO.get(item)
        if efecto:
            hp_nuevo = min(hp_max, hp + efecto["hp"])
            stats["hp"] = hp_nuevo
            mensaje = efecto["msg"] + f" HP: {hp_nuevo}/{hp_max}"
        else:
            return await reply(f"ℹ️ `{item.replace('_', ' ')}` no se usa directamente — es parte de tu equipo.")

        inv[item] -= 1
        if inv[item] <= 0:
            del inv[item]
        await db.update("personajes", str(user.id), {"inventario": inv, "stats": stats})
        await reply(mensaje)

    # ── /craftear ─────────────────────────────────────────────────────────────
    @app_commands.command(name="craftear", description="Fabrica un objeto con materiales de tu inventario")
    @app_commands.describe(item="Nombre del objeto a fabricar")
    async def craftear_slash(self, interaction: discord.Interaction, item: str):
        await self._craftear(interaction, item.lower().replace(" ", "_"))

    @commands.command(name="craftear", aliases=["fabricar", "craft"])
    async def craftear_prefix(self, ctx, *, item: str):
        await self._craftear(ctx, item.lower().replace(" ", "_"))

    async def _craftear(self, ctx_or_inter, item: str):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        user = ctx_or_inter.user if is_slash else ctx_or_inter.author

        async def reply(msg, embed=None, ephemeral=False):
            if is_slash:
                await ctx_or_inter.response.send_message(msg, embed=embed, ephemeral=ephemeral)
            else:
                await ctx_or_inter.send(msg, embed=embed)

        if item not in RECETAS:
            items_txt = ", ".join(f"`{k}`" for k in RECETAS.keys())
            return await reply(f"❌ No existe receta para `{item}`.\nPuedes craftear: {items_txt}", ephemeral=True)

        datos = await db.get("personajes", str(user.id))
        if not datos:
            return await reply("❌ Sin personaje.", ephemeral=True)

        receta = RECETAS[item]
        inv = datos.get("inventario", {})
        canal_actual = datos.get("canal_actual", "")

        # Verificar ubicación
        req_canal = receta.get("requiere_canal")
        if req_canal:
            if not any(c in canal_actual for c in req_canal):
                return await reply(
                    f"❌ Para fabricar **{item}** debes estar en: {', '.join(f'`{c}`' for c in req_canal)}",
                    ephemeral=True
                )

        # Verificar ingredientes
        ingredientes = receta["ingredientes"]
        faltantes = []
        for mat, cantidad in ingredientes.items():
            if inv.get(mat, 0) < cantidad:
                faltantes.append(f"{cantidad}x `{mat}` (tienes {inv.get(mat, 0)})")

        if faltantes:
            return await reply(
                f"❌ Te faltan materiales para fabricar **{item}**:\n" + "\n".join(faltantes),
                ephemeral=True
            )

        # Intentar craftear
        prob = receta.get("probabilidad", 0.80)
        if random.random() > prob:
            # Fallo: consumir materiales igualmente
            for mat, cantidad in ingredientes.items():
                inv[mat] = max(0, inv.get(mat, 0) - cantidad)
                if inv[mat] == 0:
                    del inv[mat]
            await db.update("personajes", str(user.id), {"inventario": inv})
            return await reply(f"💥 El crafteo de **{item}** falló y los materiales se perdieron. (Prob. éxito: {int(prob*100)}%)")

        # Éxito
        for mat, cantidad in ingredientes.items():
            inv[mat] = max(0, inv.get(mat, 0) - cantidad)
            if inv[mat] == 0:
                del inv[mat]
        inv[item] = inv.get(item, 0) + 1
        await db.update("personajes", str(user.id), {"inventario": inv})

        embed = discord.Embed(
            title=f"🔨 ¡{item.replace('_',' ').title()} fabricado!",
            description=receta["descripcion"],
            color=discord.Color.green()
        )
        embed.add_field(name="Materiales usados", value="\n".join(f"• {v}x {k}" for k, v in ingredientes.items()))
        embed.set_footer(text=f"Éxito: {int(prob*100)}% | Canal: {canal_actual}")
        await reply("", embed=embed)

    # ── /recetas ──────────────────────────────────────────────────────────────
    @app_commands.command(name="recetas", description="Muestra todos los objetos que puedes craftear")
    async def recetas_slash(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🔨 Recetas de Crafteo", color=discord.Color.orange())
        for nombre, receta in RECETAS.items():
            mats = ", ".join(f"{v}x {k}" for k, v in receta["ingredientes"].items())
            lugar = "Cualquier lugar" if not receta.get("requiere_canal") else ", ".join(receta["requiere_canal"])
            embed.add_field(
                name=f"`{nombre}` — {int(receta['probabilidad']*100)}% éxito",
                value=f"**Materiales:** {mats}\n**Lugar:** {lugar}\n_{receta['descripcion']}_",
                inline=False
            )
        embed.set_footer(text="Usa /craftear <nombre> para fabricar")
        await interaction.response.send_message(embed=embed)

    # ── /prestamo ─────────────────────────────────────────────────────────────
    @app_commands.command(name="prestamo", description="Solicita un préstamo con 15% de interés (en banco)")
    @app_commands.describe(monto="Monto a solicitar (máx $5000)")
    async def prestamo_slash(self, interaction: discord.Interaction, monto: float):
        await self._prestamo(interaction, monto)

    @commands.command(name="prestamo")
    async def prestamo_prefix(self, ctx, monto: float):
        await self._prestamo(ctx, monto)

    async def _prestamo(self, ctx_or_inter, monto: float):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        user = ctx_or_inter.user if is_slash else ctx_or_inter.author

        async def reply(msg, embed=None, ephemeral=False):
            if is_slash:
                await ctx_or_inter.response.send_message(msg, embed=embed, ephemeral=ephemeral)
            else:
                await ctx_or_inter.send(msg, embed=embed)

        datos = await db.get("personajes", str(user.id))
        if not datos:
            return await reply("❌ Sin personaje.", ephemeral=True)
        canal_actual = datos.get("canal_actual", "")
        if "banco" not in canal_actual and "prestamista" not in canal_actual:
            return await reply("❌ Debes estar en un banco para solicitar préstamo.", ephemeral=True)
        if monto <= 0 or monto > 5000:
            return await reply("❌ Monto inválido. Entre $1 y $5000.", ephemeral=True)
        deuda_actual = datos.get("deudas", 0)
        if deuda_actual > 1000:
            return await reply("❌ Ya tienes demasiada deuda. Págala primero.", ephemeral=True)

        interes = round(monto * 0.15, 2)
        total_deuda = round(monto + interes, 2)
        dinero_nuevo = datos.get("dinero", 0) + monto
        await db.update("personajes", str(user.id), {
            "dinero": round(dinero_nuevo, 2),
            "deudas": round(deuda_actual + total_deuda, 2)
        })
        embed = discord.Embed(title="🏦 Préstamo aprobado", color=discord.Color.green())
        embed.add_field(name="Monto recibido", value=f"${monto:.2f}", inline=True)
        embed.add_field(name="Interés (15%)", value=f"${interes:.2f}", inline=True)
        embed.add_field(name="Total a pagar", value=f"${total_deuda:.2f}", inline=True)
        embed.add_field(name="Aviso", value="⚠️ Si no pagas, habrá consecuencias en el RP.", inline=False)
        await reply("", embed=embed)

    # ── /pagar_deuda ──────────────────────────────────────────────────────────
    @app_commands.command(name="pagar_deuda", description="Paga parte o toda tu deuda")
    @app_commands.describe(monto="Cantidad a pagar")
    async def pagar_deuda_slash(self, interaction: discord.Interaction, monto: float):
        await self._pagar_deuda(interaction, monto)

    @commands.command(name="pagar_deuda")
    async def pagar_deuda_prefix(self, ctx, monto: float):
        await self._pagar_deuda(ctx, monto)

    async def _pagar_deuda(self, ctx_or_inter, monto: float):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        user = ctx_or_inter.user if is_slash else ctx_or_inter.author

        async def reply(msg, ephemeral=False):
            if is_slash:
                await ctx_or_inter.response.send_message(msg, ephemeral=ephemeral)
            else:
                await ctx_or_inter.send(msg)

        datos = await db.get("personajes", str(user.id))
        if not datos:
            return await reply("❌ Sin personaje.", ephemeral=True)
        deuda = datos.get("deudas", 0)
        if deuda <= 0:
            return await reply("✅ No tienes deudas.")
        dinero = datos.get("dinero", 0)
        if monto > dinero:
            return await reply(f"❌ No tienes ${monto:.2f}. Tienes ${dinero:.2f}.", ephemeral=True)
        monto = min(monto, deuda)
        await db.update("personajes", str(user.id), {
            "dinero": round(dinero - monto, 2),
            "deudas": round(deuda - monto, 2)
        })
        await reply(f"✅ Pagaste ${monto:.2f} de deuda. Deuda restante: ${deuda - monto:.2f}")

    # ── /transferir ───────────────────────────────────────────────────────────
    @app_commands.command(name="transferir", description="Transfiere dinero a otro personaje")
    @app_commands.describe(destinatario="Usuario al que transferir", monto="Cantidad a transferir")
    async def transferir_slash(self, interaction: discord.Interaction, destinatario: discord.Member, monto: float):
        await self._transferir(interaction, destinatario, monto)

    @commands.command(name="transferir")
    async def transferir_prefix(self, ctx, destinatario: discord.Member, monto: float):
        await self._transferir(ctx, destinatario, monto)

    async def _transferir(self, ctx_or_inter, destinatario: discord.Member, monto: float):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        user = ctx_or_inter.user if is_slash else ctx_or_inter.author

        async def reply(msg, ephemeral=False):
            if is_slash:
                await ctx_or_inter.response.send_message(msg, ephemeral=ephemeral)
            else:
                await ctx_or_inter.send(msg)

        if user.id == destinatario.id:
            return await reply("❌ No puedes transferirte a ti mismo.", ephemeral=True)
        datos_from = await db.get("personajes", str(user.id))
        datos_to = await db.get("personajes", str(destinatario.id))
        if not datos_from:
            return await reply("❌ No tienes personaje.", ephemeral=True)
        if not datos_to:
            return await reply(f"❌ {destinatario.display_name} no tiene personaje.", ephemeral=True)
        if monto <= 0:
            return await reply("❌ Monto inválido.", ephemeral=True)
        dinero_from = datos_from.get("dinero", 0)
        if dinero_from < monto:
            return await reply(f"❌ No tienes suficiente. Tienes ${dinero_from:.2f}.", ephemeral=True)

        await db.update("personajes", str(user.id), {"dinero": round(dinero_from - monto, 2)})
        await db.update("personajes", str(destinatario.id), {"dinero": round(datos_to.get("dinero", 0) + monto, 2)})
        await reply(f"✅ Transferiste **${monto:.2f}** a **{datos_to['nombre']}**.")
        try:
            await destinatario.send(f"💵 Recibiste **${monto:.2f}** de **{datos_from['nombre']}**.")
        except:
            pass

    # ── /impuestos ────────────────────────────────────────────────────────────
    @app_commands.command(name="impuestos", description="Muestra las tasas de IVA por categoría")
    async def impuestos_slash(self, interaction: discord.Interaction):
        await self._mostrar_impuestos(interaction)

    @commands.command(name="impuestos")
    async def impuestos_prefix(self, ctx):
        await self._mostrar_impuestos(ctx)

    async def _mostrar_impuestos(self, ctx_or_inter):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        embed = discord.Embed(
            title="🧾 IVA por categoría",
            description="Se cobra automáticamente al usar `/comprar`. Va directo al tesoro nacional.",
            color=discord.Color.dark_teal()
        )
        for cat, tasa in sorted(impuestos.IVA_CATEGORIA.items(), key=lambda x: -x[1]):
            embed.add_field(name=cat.title(), value=f"{tasa*100:.0f}%", inline=True)
        embed.set_footer(text=f"Categorías no listadas: {impuestos.IVA_DEFAULT*100:.0f}% (tasa por defecto)")
        if is_slash:
            await ctx_or_inter.response.send_message(embed=embed)
        else:
            await ctx_or_inter.send(embed=embed)

    # ── /tesoro_nacional ──────────────────────────────────────────────────────
    @commands.command(name="tesoro_nacional", aliases=["tesoro"])
    async def tesoro_nacional(self, ctx):
        estado = await impuestos.obtener_tesoro()
        embed = discord.Embed(
            title="🏛️ Tesoro Nacional de Venezuela",
            description="Acumulado de TODOS los impuestos cobrados en el servidor (IVA, corporativo, dividendos).",
            color=discord.Color.dark_gold()
        )
        embed.add_field(name="💰 Total acumulado", value=f"${estado.get('total', 0):,.2f}", inline=False)
        por_concepto = estado.get("por_concepto", {})
        if por_concepto:
            desglose = "\n".join(f"`{k}`: ${v:,.2f}" for k, v in sorted(por_concepto.items(), key=lambda x: -x[1])[:10])
            embed.add_field(name="📊 Desglose por concepto", value=desglose, inline=False)
        await ctx.send(embed=embed)

    # ── /precios ──────────────────────────────────────────────────────────────
    @app_commands.command(name="precios", description="Muestra los precios actuales del mercado")
    async def precios_slash(self, interaction: discord.Interaction):
        await self._mostrar_precios(interaction)

    @commands.command(name="precios")
    async def precios_prefix(self, ctx):
        await self._mostrar_precios(ctx)

    async def _mostrar_precios(self, ctx_or_inter):
        is_slash = isinstance(ctx_or_inter, discord.Interaction)
        embed = discord.Embed(
            title="📊 Precios del Mercado",
            description="Precios fluctúan con la inflación venezolana 🇻🇪\nMuestra los más importantes.",
            color=discord.Color.gold()
        )
        items_importantes = ["arepa", "agua_botella", "vendaje", "kit_medico", "telefono_basico",
                              "smartphone", "bicicleta", "carro_basico", "cuchillo", "linterna",
                              "generador_electrico", "bidan_gasolina", "cedula_venezolana",
                              "pasaporte", "ron_cacique"]
        for item in items_importantes:
            if item not in precios_actuales:
                continue
            precio = precios_actuales[item]
            base = TIENDA_ITEMS[item]["precio"]
            variacion = round(((precio - base) / base) * 100, 1)
            signo = "📈" if variacion > 0 else "📉" if variacion < 0 else "➡️"
            embed.add_field(name=item.replace("_", " ").title(), value=f"${precio:.2f} {signo} {variacion:+.1f}%", inline=True)
        embed.set_footer(text="Precios se actualizan cada hora. Usa /tienda para ver todos.")
        if is_slash:
            await ctx_or_inter.response.send_message(embed=embed)
        else:
            await ctx_or_inter.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Economia(bot))