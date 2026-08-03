"""
cogs/setup_rp.py — Comando /iniciar_rp para configurar todo el servidor de una vez.
Crea canales, los hace privados, envía embeds informativos.
Sistema de visibilidad: los jugadores solo ven canales donde han estado.
"""
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from utils import db
from utils.permisos import dar_acceso_canal, canal_privado_base

# ── IDs de canales informativos ───────────────────────────────────────────────
CH_CREAR_DOC       = 1369366721550614700
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

# Canales informativos que DEBEN ser públicos (todos los pueden ver)
CANALES_PUBLICOS_IDS = [
    CH_CREAR_DOC, CH_DOCUMENTACIONES, CH_PERSONAJES_OK,
    CH_DROGAS, CH_ROBOS, CH_PRECIOS, CH_COMPRAR_VEHIC,
    CH_MUERTOS, CH_MAS_BUSCADOS, CH_INFO_TRABAJOS,
    CH_NOTICIAS_VZ1, CH_NOTICIAS_VZ2, CH_NOTICIAS_INT,
]

# ── MAPA DE SECTORES PARA CREAR ───────────────────────────────────────────────
from utils.mapa import SECTORES

# Canales adicionales por sector que no están en mapa pero se deben crear
CANALES_EXTRA = {
    "petare": [
        ("🏚️", "calle-petare",          "Calle principal de Petare",              "general"),
        ("🛒", "mercado-negro-petare",   "Mercado negro — zona peligrosa",         "peligro"),
        ("🏥", "ambulatorio-petare",     "Ambulatorio básico",                     "servicio"),
        ("🚔", "comisaria-petare",       "Comisaría CPNB Petare",                  "servicio"),
        ("🔧", "taller-petare",          "Taller mecánico",                        "comercio"),
        ("🏪", "bodega-petare",          "Bodega local",                           "comercio"),
        ("⛪", "iglesia-petare",         "Iglesia del barrio",                     "general"),
        ("🏫", "escuela-petare",         "Escuela primaria",                       "servicio"),
        ("🍺", "tasca-el-tigre",         "Bar popular",                            "comercio"),
        ("🌿", "campo-pelota-petare",    "Campo de béisbol improvisado",           "general"),
        ("🚌", "parada-bus-petare",      "Parada de autobuses",                    "transporte"),
        ("🚇", "metro-petare",           "Estación Metro Petare",                  "transporte"),
    ],
    "las-mercedes": [
        ("🏙️", "av-las-mercedes",        "Avenida Las Mercedes",                   "general"),
        ("🏦", "banco-mercantil",         "Banco Mercantil Las Mercedes",           "comercio"),
        ("🍽️", "restaurante-la-estancia","Restaurante de lujo",                    "comercio"),
        ("🏋️", "gym-elite-fitness",      "Gimnasio de alto nivel",                 "servicio"),
        ("🛍️", "centro-comercial-sambil","Centro Comercial Sambil",                "comercio"),
        ("🚗", "concesionario-toyota",   "Concesionario de vehículos",             "comercio"),
        ("☕", "cafe-arte",              "Café artístico",                         "comercio"),
        ("💊", "farmacia-farmatodo",     "Farmacia Farmatodo",                     "servicio"),
        ("🏨", "hotel-eurobuilding",     "Hotel de lujo",                          "servicio"),
        ("🎭", "teatro-las-mercedes",    "Teatro",                                 "general"),
        ("🚌", "parada-bus-mercedes",    "Parada de autobuses",                    "transporte"),
    ],
    "distrito-capital": [
        ("🏛️", "palacio-miraflores",     "Palacio de Gobierno",                    "general"),
        ("🏦", "banco-central-venezuela","Banco Central de Venezuela",             "comercio"),
        ("⚖️", "tribunal-supremo",       "Tribunal Supremo",                       "servicio"),
        ("🚔", "comisaria-cicpc",        "Sede CICPC",                             "servicio"),
        ("🚔", "comisaria-cpnb-capital", "CPNB Distrito Capital",                  "servicio"),
        ("📋", "registro-civil",         "Registro Civil",                         "servicio"),
        ("🌳", "parque-los-caobos",      "Parque Los Caobos",                      "general"),
        ("🎨", "museo-bellas-artes",     "Museo de Bellas Artes",                  "general"),
        ("🕍", "capitolio-nacional",     "Capitolio Nacional",                     "general"),
        ("🚇", "metro-capitolio",        "Metro Capitolio",                        "transporte"),
        ("🏥", "hospital-vargas",        "Hospital Vargas",                        "servicio"),
        ("🏬", "cc-el-recreo",           "C.C. El Recreo",                         "comercio"),
        ("🚗", "concesionario-capital",  "Concesionario vehículos Capital",        "comercio"),
        ("🔒", "sebin-hq",               "Sede SEBIN — Acceso restringido",        "servicio"),
        ("🪖", "cuartel-militar-capital","Cuartel Militar",                        "servicio"),
    ],
    "23-de-enero": [
        ("🏢", "bloques-23-enero",       "Bloques residenciales",                  "general"),
        ("🛒", "mercado-23-enero",       "Mercado popular",                        "comercio"),
        ("🏫", "liceo-aplicacion",       "Liceo de Aplicación",                    "servicio"),
        ("⛽", "gasolinera-pdvsa-23",    "Gasolinera PDVSA",                       "transporte"),
        ("🏥", "ambulatorio-23",         "Ambulatorio urbano",                     "servicio"),
        ("🎳", "cancha-multiusos-23",    "Cancha deportiva",                       "general"),
        ("🍗", "pollos-hermanos-23",     "Local de comida",                        "comercio"),
        ("🔧", "taller-23",              "Taller mecánico",                        "comercio"),
        ("🚌", "terminal-23-enero",      "Terminal de autobuses",                  "transporte"),
        ("🌃", "paseo-23-enero",         "Paseo nocturno — peligroso",             "peligro"),
        ("⚠️", "colectivos-zona-23",     "Zona de colectivos",                     "peligro"),
    ],
    "ciudad-universitaria": [
        ("🎓", "ucv-campus",             "Campus UCV",                             "servicio"),
        ("📚", "biblioteca-ucv",         "Biblioteca Central UCV",                 "servicio"),
        ("🏟️", "estadio-ucv",            "Estadio universitario",                  "general"),
        ("☕", "cantina-ucv",            "Cantina UCV",                            "comercio"),
        ("🔬", "laboratorio-ucv",        "Laboratorios UCV",                       "servicio"),
        ("🚇", "metro-ciudad-univ",      "Metro Ciudad Universitaria",             "transporte"),
        ("🌿", "jardines-botanicos",     "Jardín Botánico",                        "general"),
        ("🏠", "residencias-ucv",        "Residencias estudiantiles",              "general"),
        ("🎭", "aula-magna",             "Aula Magna",                             "general"),
        ("🍕", "pizzeria-ucv",           "Pizzería zona estudiantil",              "comercio"),
    ],
    "miranda": [
        ("🏡", "los-palos-grandes",      "Los Palos Grandes",                      "barrio"),
        ("🏙️", "chacao",                "Chacao",                                 "general"),
        ("🏬", "cc-sambil-chacao",       "C.C. Sambil Chacao",                     "comercio"),
        ("🚔", "policia-miranda",        "CPNB Miranda",                           "servicio"),
        ("🏥", "hospital-de-clinicas",   "Hospital de Clínicas",                   "servicio"),
        ("🚇", "metro-chacao",           "Metro Chacao",                           "transporte"),
        ("🚂", "estacion-tren-miranda",  "Estación Tren Miranda",                  "transporte"),
        ("🏘️", "guarenas-centro",        "Centro de Guarenas",                     "general"),
        ("🏬", "cc-buenaventura",        "C.C. Buenaventura",                      "comercio"),
        ("🌳", "parque-la-llovizna",     "Parque La Llovizna",                     "general"),
    ],
    "la-alameda": [
        ("🏘️", "residencias-alameda",    "Residencias La Alameda",                 "general"),
        ("🏞️", "plaza-alameda",          "Plaza La Alameda",                       "general"),
        ("🏪", "bodega-alameda",         "Bodega La Alameda",                      "comercio"),
        ("🚌", "parada-bus-alameda",     "Parada de autobuses",                    "transporte"),
        ("🏋️", "gym-popular-alameda",    "Gimnasio popular",                       "servicio"),
        ("🔧", "ferreteria-gonzalez",    "Ferretería González",                    "comercio"),
        ("🍽️", "restaurante-criollo",    "Restaurante criollo",                    "comercio"),
        ("🏥", "clinica-alameda",        "Clínica privada",                        "servicio"),
    ],
    "la-trinidad": [
        ("🏡", "residencias-trinidad",   "Residencias La Trinidad",                "barrio"),
        ("💪", "gym-trinidad",           "Gym La Trinidad",                        "servicio"),
        ("🍽️", "restaurante-trinidad",   "Restaurante gourmet",                    "comercio"),
        ("🚌", "parada-bus-trinidad",    "Parada de autobuses",                    "transporte"),
        ("🏦", "banesco-trinidad",       "Banco Banesco Trinidad",                 "comercio"),
        ("🚗", "rent-a-car-trinidad",    "Rent a Car Trinidad",                    "comercio"),
        ("🏊", "country-club-trinidad",  "Country Club",                           "general"),
        ("🎯", "campo-tiro-trinidad",    "Campo de tiro",                          "general"),
    ],
    "maracaibo": [
        ("🏙️", "centro-maracaibo",       "Centro de Maracaibo",                    "general"),
        ("🌊", "lago-maracaibo",         "Lago de Maracaibo",                      "general"),
        ("🛒", "mercado-las-pulgas",     "Mercado Las Pulgas",                     "comercio"),
        ("🚌", "terminal-maracaibo",     "Terminal Maracaibo",                     "transporte"),
        ("🏥", "hospital-maracaibo",     "Hospital Maracaibo",                     "servicio"),
        ("✈️", "aeropuerto-maracaibo",   "Aeropuerto La Chinita",                  "transporte"),
        ("🏦", "banco-occidental",       "Banco Occidental",                       "comercio"),
        ("🎭", "teatro-baralt",          "Teatro Baralt",                          "general"),
        ("🏫", "universidad-zulia",      "Universidad del Zulia",                  "servicio"),
    ],
    "valencia": [
        ("🏙️", "centro-valencia",        "Centro de Valencia",                     "general"),
        ("🏭", "zona-industrial-val",    "Zona Industrial Valencia",               "comercio"),
        ("🏬", "cc-valencia",            "C.C. Valencia",                          "comercio"),
        ("🏥", "hospital-carabobo",      "Hospital Carabobo",                      "servicio"),
        ("🏫", "universidad-carabobo",   "Universidad de Carabobo",                "servicio"),
        ("✈️", "aeropuerto-valencia",    "Aeropuerto Arturo Michelena",            "transporte"),
        ("🚌", "terminal-valencia",      "Terminal de pasajeros",                  "transporte"),
        ("🔫", "barrio-la-isabelica",    "Barrio La Isabelica — zona roja",        "peligro"),
    ],
    "medellin": [
        ("🏙️", "el-poblado",             "El Poblado",                             "general"),
        ("🚇", "metro-medellin",         "Metro Medellín",                         "transporte"),
        ("✈️", "aeropuerto-rionegro",    "Aeropuerto Rionegro",                    "transporte"),
        ("🛒", "mercado-medellin",       "Mercado Medellín",                       "comercio"),
        ("🏦", "bancolombia-medellin",   "Bancolombia",                            "comercio"),
        ("🔫", "comuna-13",              "Comuna 13",                              "peligro"),
        ("🏥", "clinica-medellin",       "Clínica Las Vegas",                      "servicio"),
    ],
    "bogota": [
        ("🏛️", "plaza-bolivar-bogota",   "Plaza Bolívar Bogotá",                  "general"),
        ("✈️", "aeropuerto-bogota",      "Aeropuerto El Dorado",                   "transporte"),
        ("🚌", "transmilenio",           "TransMilenio",                           "transporte"),
        ("🏦", "banco-republica",        "Banco de la República",                  "comercio"),
        ("🔫", "bronx-bogota",           "El Bronx",                               "peligro"),
        ("🏥", "hospital-bogota",        "Hospital Bogotá",                        "servicio"),
    ],
    "miami": [
        ("🏖️", "south-beach",            "South Beach",                            "general"),
        ("✈️", "aeropuerto-miami",       "Miami International Airport",            "transporte"),
        ("🏦", "bank-of-america-miami",  "Bank of America Miami",                  "comercio"),
        ("🛒", "mall-of-miami",          "Mall of Miami",                          "comercio"),
        ("🍽️", "versailles-restaurant",  "Restaurante Versailles",                 "comercio"),
        ("🏥", "jackson-memorial",       "Jackson Memorial Hospital",              "servicio"),
        ("🌴", "wynwood-arts",           "Wynwood Arts District",                  "general"),
        ("🚗", "car-dealership-miami",   "Concesionario Miami",                    "comercio"),
        ("🏨", "fontainebleau-miami",    "Hotel Fontainebleau",                    "servicio"),
        ("🎰", "casino-fontainebleau-miami", "Casino del Hotel Fontainebleau — 18+ en el rol", "recreacion"),
    ],
    # ── PRISIÓN ──────────────────────────────────────────────────────────────
    "prision": [
        ("⛓️", "celda-yare",             "Celda de la Cárcel de Yare",             "general"),
        ("🏛️", "patio-yare",             "Patio de la cárcel",                     "general"),
        ("🚔", "oficina-director-yare",  "Oficina del Director",                   "servicio"),
    ],
}


def es_admin():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)


class SetupRP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── /iniciar_rp ────────────────────────────────────────────────────────────
    @app_commands.command(name="iniciar_rp", description="[ADMIN] ⚙️ Configura TODO el servidor de roleplay de una vez")
    @es_admin()
    async def iniciar_rp(self, interaction: discord.Interaction):
        """Setup completo: crea categorías, canales, hace públicos los informativos, envía embeds."""
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        log = []
        errores = []

        # ── 1. Hacer canales informativos públicos ────────────────────────────
        for ch_id in CANALES_PUBLICOS_IDS:
            ch = guild.get_channel(ch_id)
            if ch:
                try:
                    await ch.set_permissions(guild.default_role, read_messages=True, view_channel=True, send_messages=False)
                    log.append(f"✅ Canal público: #{ch.name}")
                except Exception as e:
                    errores.append(f"Canal {ch_id}: {e}")

        # ── 2. Crear separadores de ciudad ────────────────────────────────────
        separadores = [
            ("━━━━━ 🇻🇪 CARACAS ━━━━━",  ["petare","las-mercedes","distrito-capital","23-de-enero","ciudad-universitaria","miranda","la-alameda","la-trinidad"]),
            ("━━━━━ 🏭 OTRAS VZ ━━━━━",   ["maracaibo","valencia"]),
            ("━━━━━ 🌍 INTERNACIONAL ━━━━━", ["medellin","bogota","miami"]),
            ("━━━━━ ⛓️ PRISIÓN ━━━━━",    ["prision"]),
        ]

        for sep_nombre, sectores_grupo in separadores:
            # Crear/verificar categoría separadora (solo visual)
            for sector in sectores_grupo:
                canales_data = CANALES_EXTRA.get(sector, [])
                if not canales_data:
                    continue

                # Buscar o crear categoría del sector
                nombre_cat = sector.upper()
                cat = discord.utils.get(guild.categories, name=nombre_cat)
                if not cat:
                    try:
                        cat = await guild.create_category(nombre_cat)
                        log.append(f"📁 Categoría: {nombre_cat}")
                    except Exception as e:
                        errores.append(f"Cat {nombre_cat}: {e}")
                        continue

                # Crear canales del sector
                for emoji, nombre_canal, descripcion, tipo in canales_data:
                    canal_existente = discord.utils.get(cat.channels, name=nombre_canal)
                    if canal_existente:
                        continue
                    try:
                        overwrites = await canal_privado_base(guild)
                        await guild.create_text_channel(
                            name=nombre_canal,
                            category=cat,
                            topic=descripcion,
                            overwrites=overwrites
                        )
                    except Exception as e:
                        errores.append(f"{nombre_canal}: {e}")

                # Crear casas — en su PROPIA categoría dedicada, separada de los
                # canales de contenido del sector. Antes se creaban todas
                # mezcladas dentro de la misma categoría que petare/las-mercedes/
                # etc., por lo que quedaban enterradas entre canales normales y
                # además usaba n_casas=20 fijo para TODOS los sectores en vez del
                # casas_total real de cada uno (algunos sectores tienen 8, 10 o 15).
                n_casas = SECTORES.get(sector, {}).get("casas_total", 0)
                if n_casas > 0:
                    nombre_cat_casas = f"🏠 CASAS - {sector.upper()}"
                    cat_casas = discord.utils.get(guild.categories, name=nombre_cat_casas)
                    if not cat_casas:
                        try:
                            cat_casas = await guild.create_category(nombre_cat_casas)
                            log.append(f"📁 Categoría de casas: {nombre_cat_casas}")
                        except Exception as e:
                            errores.append(f"Cat casas {nombre_cat_casas}: {e}")
                            cat_casas = None

                    if cat_casas:
                        # Traer (o inicializar) las casas de este sector en la DB
                        # para poder guardar canal_id apenas se crea el canal.
                        from cogs.propiedades import _inicializar_casas_sector
                        casas_db = await _inicializar_casas_sector(sector)

                        for i in range(1, n_casas + 1):
                            nombre_casa = f"casa-{i}"
                            casa_id = f"casa-{i}"
                            canal_casa = discord.utils.get(cat_casas.channels, name=nombre_casa)
                            if not canal_casa:
                                try:
                                    overwrites = await canal_privado_base(guild)
                                    canal_casa = await guild.create_text_channel(
                                        name=nombre_casa,
                                        category=cat_casas,
                                        topic=f"Casa {i} en {sector} — disponible",
                                        overwrites=overwrites
                                    )
                                except Exception as e:
                                    errores.append(f"{nombre_casa} ({sector}): {e}")
                                    continue

                            # Guardar el canal_id real ya, en vez de esperar a
                            # que alguien la compre (así nunca hay que adivinar
                            # el canal por nombre entre sectores distintos).
                            entrada = casas_db.get(casa_id)
                            if entrada and not entrada.get("canal_id"):
                                entrada["canal_id"] = canal_casa.id
                                casas_db[casa_id] = entrada
                        await db.set("casas", sector, casas_db)

        # ── 3. Categoría especial TELÉFONOS ───────────────────────────────────
        cat_tel = discord.utils.get(guild.categories, name="📱 TELÉFONOS")
        if not cat_tel:
            try:
                overwrites_cat = {guild.default_role: discord.PermissionOverwrite(read_messages=False)}
                await guild.create_category("📱 TELÉFONOS", overwrites=overwrites_cat)
                log.append("📱 Categoría TELÉFONOS creada")
            except Exception as e:
                errores.append(f"Teléfonos cat: {e}")

        # ── 4. Enviar embeds informativos ─────────────────────────────────────
        await self._enviar_embeds_info(guild)

        # ── 5. Canal de creación de personajes ───────────────────────────────
        ch_crear = guild.get_channel(CH_CREAR_DOC)
        if ch_crear:
            try:
                await ch_crear.set_permissions(guild.default_role, read_messages=True, view_channel=True, send_messages=True)
                embed_crear = discord.Embed(
                    title="📋 Crear Personaje — Venezuela RP",
                    description=(
                        "¡Bienvenido al servidor de Roleplay Venezuela!\n\n"
                        "Para comenzar a jugar necesitas crear tu personaje.\n\n"
                        "**Pasos:**\n"
                        "1️⃣ Escribe `/crearPersonaje` en este canal\n"
                        "2️⃣ Rellena el formulario\n"
                        "3️⃣ Un admin aprobará tu personaje\n"
                        "4️⃣ Al ser aprobado, recibirás acceso a los canales\n\n"
                        "**Nota:** Solo puedes ver los canales donde has estado. "
                        "Al empezar, verás tu casa (o la calle si no tienes)."
                    ),
                    color=0x2ECC71
                )
                embed_crear.set_footer(text="Venezuela RP • Usa /ayuda_rp para ver comandos")
                await ch_crear.send(embed=embed_crear)
                log.append("✅ Embed bienvenida enviado")
            except Exception as e:
                errores.append(f"Canal crear: {e}")

        # ── Resumen ───────────────────────────────────────────────────────────
        resumen = f"🏙️ **Setup completado**\n"
        resumen += f"✅ {len(log)} acciones exitosas\n"
        if errores:
            resumen += f"⚠️ {len(errores)} errores: {'; '.join(errores[:5])}"

        await interaction.followup.send(resumen, ephemeral=True)

    # ── /reorganizar_casas ───────────────────────────────────────────────────
    @app_commands.command(
        name="reorganizar_casas",
        description="[ADMIN] 🏠 Mueve los canales de casas existentes a su propia categoría (arregla el desorden viejo)"
    )
    @es_admin()
    async def reorganizar_casas(self, interaction: discord.Interaction):
        """Para servidores que ya corrieron /iniciar_rp antes de esta actualización:
        las casas quedaron mezcladas dentro de la categoría de contenido de cada
        sector. Este comando las mueve a una categoría propia "🏠 CASAS - SECTOR"
        y guarda el canal_id real en la base de datos para cada una, sin borrar
        ni recrear nada (los dueños/inquilinos actuales no se pierden)."""
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        from cogs.propiedades import _inicializar_casas_sector

        movidos = 0
        creados_cat = 0
        no_encontrados = []

        for sector_key, sector_data in SECTORES.items():
            n_casas = sector_data.get("casas_total", 0)
            if n_casas <= 0:
                continue

            nombre_cat_casas = f"🏠 CASAS - {sector_key.upper()}"
            cat_casas = discord.utils.get(guild.categories, name=nombre_cat_casas)
            if not cat_casas:
                try:
                    cat_casas = await guild.create_category(nombre_cat_casas)
                    creados_cat += 1
                except Exception:
                    continue

            casas_db = await _inicializar_casas_sector(sector_key)
            cat_sector_vieja = discord.utils.get(guild.categories, name=sector_key.upper())

            for i in range(1, n_casas + 1):
                casa_id = f"casa-{i}"
                casa = casas_db.get(casa_id, {})
                canal = None

                canal_id = casa.get("canal_id")
                if canal_id:
                    canal = guild.get_channel(canal_id)

                if not canal and cat_sector_vieja:
                    nombre_buscado = casa.get("canal_nombre", casa_id)
                    canal = discord.utils.get(cat_sector_vieja.channels, name=nombre_buscado)
                    if not canal:
                        # también puede haber quedado con su nombre base sin comprar aún
                        canal = discord.utils.get(cat_sector_vieja.channels, name=casa_id)

                if not canal:
                    no_encontrados.append(f"{sector_key}:{casa_id}")
                    continue

                if canal.category_id != cat_casas.id:
                    try:
                        await canal.edit(category=cat_casas, sync_permissions=False)
                        movidos += 1
                    except Exception:
                        pass

                if not casa.get("canal_id"):
                    casa["canal_id"] = canal.id
                    casas_db[casa_id] = casa

            await db.set("casas", sector_key, casas_db)

        resumen = (
            f"🏠 **Reorganización de casas completada**\n"
            f"📁 Categorías nuevas creadas: {creados_cat}\n"
            f"📦 Canales movidos a su categoría de casas: {movidos}\n"
        )
        if no_encontrados:
            resumen += f"⚠️ No se encontraron {len(no_encontrados)} canales (puede que nunca se hayan creado): " \
                       f"{', '.join(no_encontrados[:10])}" + (", ..." if len(no_encontrados) > 10 else "")

        await interaction.followup.send(resumen, ephemeral=True)

    async def _enviar_embeds_info(self, guild: discord.Guild):
        """Envía embeds informativos a todos los canales de información."""
        
        # Info drogas
        ch = guild.get_channel(CH_DROGAS)
        if ch:
            try:
                embed = discord.Embed(title="💊 El Negocio — Guía RP", color=0x2ECC71)
                embed.description = (
                    "**⚠️ FICCIÓN — Todo es roleplay ficticio. No refleja la realidad.**\n\n"
                    "El mercado negro opera desde **Petare**.\n\n"
                    "**Productos (RP):**\n"
                    "```\n🟢 Verde    — Bajo riesgo, baja ganancia\n"
                    "🔵 Azul     — Riesgo medio\n"
                    "🔴 Rojo     — Alto riesgo, alta ganancia\n"
                    "⚫ Negro    — Máximo riesgo\n```\n"
                    "**Proceso:**\n"
                    "1. Ve al `mercado-negro-petare`\n"
                    "2. Negocia por teléfono `/llamar`\n"
                    "3. Entrega en el canal acordado\n\n"
                    "**Bonus:** Si tienes estudios de **Química**, fabricas más eficientemente.\n"
                    "_Inspirado en Breaking Bad. Solo roleplay._"
                )
                await ch.send(embed=embed)
            except: pass

        # Info robos
        ch = guild.get_channel(CH_ROBOS)
        if ch:
            try:
                embed = discord.Embed(title="🔫 Manual del Ladrón — Venezuela RP", color=0xE74C3C)
                embed.description = (
                    "**Robar a una persona:**\n"
                    "• `/robar @usuario` — mismo canal\n"
                    "• Depende: Agilidad + Técnica vs sus stats\n"
                    "• Si fallas → puede disparar o llamar policía\n\n"
                    "**Robar una casa:**\n"
                    "• `/robar_casa <sector> <numero>` en el canal de la casa\n"
                    "• 30% chance de que llegue la CPNB\n\n"
                    "**Tiroteo:**\n"
                    "• `/disparar @usuario` — inicia tiroteo\n"
                    "• Hay fuego cruzado si hay inocentes cerca\n"
                    "• Puedes intentar huir con el botón que aparece\n\n"
                    "**Consecuencias:**\n"
                    "• Arrestado → Prisión de Yare\n"
                    "• Muy buscado → Canal #más-buscados\n"
                    "• Muerto → Canal #personajes-muertos"
                )
                await ch.send(embed=embed)
            except: pass

        # Info precios
        ch = guild.get_channel(CH_PRECIOS)
        if ch:
            try:
                embed = discord.Embed(title="💹 Economía Venezuela RP", color=0xF39C12)
                embed.description = (
                    "**Moneda:** Dólares americanos ($)\n"
                    "Los precios fluctúan con inflación cada hora.\n\n"
                    "**Salarios base/hora:**\n"
                    "```\n"
                    "💰 Mínimo:    $0.50\n"
                    "💰 Bajo:      $1.50\n"
                    "💰 Med-Bajo:  $4.00\n"
                    "💰 Medio:     $8.00\n"
                    "💰 Med-Alto:  $15.00\n"
                    "💰 Alto:      $30.00\n"
                    "💰 Muy Alto:  $60.00\n"
                    "💰 Extranjero:$120.00\n```\n"
                    "Los salarios se pagan automáticamente cada 6 horas.\n"
                    "Usa `/precios` para ver precios actuales."
                )
                await ch.send(embed=embed)
            except: pass

        # Info vehículos
        ch = guild.get_channel(CH_COMPRAR_VEHIC)
        if ch:
            try:
                embed = discord.Embed(title="🚗 Vehículos y Transporte", color=0x3498DB)
                embed.description = (
                    "**Métodos de viaje:**\n"
                    "```\n"
                    "/viajar caminar <destino>   — Siempre. Lento.\n"
                    "/viajar bicicleta <destino> — Necesitas bicicleta\n"
                    "/viajar coche <destino>     — Necesitas coche\n"
                    "/viajar metro <destino>     — En estación metro\n"
                    "/viajar autobus <destino>   — En parada/terminal\n"
                    "/viajar avion <destino>     — Solo aeropuertos\n```\n"
                    "**Precios:**\n"
                    "```\n"
                    "🚲 Bicicleta:   $50\n"
                    "🚗 Carro básico: $2,500\n"
                    "🚗 Carro lujoso: $25,000\n"
                    "🚐 4x4:          $35,000\n```\n"
                    "**⚠️ Ir caminando a otras ciudades/países:**\n"
                    "Probabilidad de muerte/secuestro extremadamente alta."
                )
                await ch.send(embed=embed)
            except: pass

        # Info trabajos
        ch = guild.get_channel(CH_INFO_TRABAJOS)
        if ch:
            try:
                embed = discord.Embed(title="💼 Guía de Empleos", color=0x27AE60)
                embed.description = (
                    "**Requisitos:**\n"
                    "• Personaje aprobado\n"
                    "• Edad mínima según trabajo (mínimo 16 para trabajar)\n"
                    "• Estudios requeridos para algunos puestos\n\n"
                    "**Comando:** `/solicitar_trabajo <nombre>`\n"
                    "**Ver lista:** `/trabajos`\n\n"
                    "**Estudios y bonuses:**\n"
                    "• Química universitaria → Más eficiencia en RP químico\n"
                    "• Informática → Mejor hackeo\n"
                    "• Graduado → +15% salario\n\n"
                    "**Salarios** se pagan automáticamente cada 6h."
                )
                await ch.send(embed=embed)
            except: pass

    # ── /dar_acceso_personaje ─────────────────────────────────────────────────
    @app_commands.command(name="dar_acceso_personaje", description="[ADMIN] Da acceso inicial de canales a un personaje recién aprobado")
    @es_admin()
    async def dar_acceso_personaje(self, interaction: discord.Interaction, usuario: discord.Member):
        """Asigna visibilidad inicial al personaje según su situación (casa o calle)."""
        datos = await db.get("personajes", str(usuario.id))
        if not datos:
            return await interaction.response.send_message("❌ Sin personaje.", ephemeral=True)

        from utils.permisos import inicializar_acceso_personaje
        canales_dados = await inicializar_acceso_personaje(interaction.guild, usuario, datos)

        embed = discord.Embed(title="✅ Acceso inicial configurado", color=0x2ECC71)
        embed.add_field(name="Jugador", value=usuario.mention)
        embed.add_field(name="Barrio inicial", value=datos.get("barrio","?"))
        embed.add_field(name="Canales visibles", value="\n".join(f"#{c}" for c in canales_dados) or "Ninguno")
        embed.set_footer(text="El jugador solo verá canales adicionales al viajar a ellos.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Notificar al jugador
        nombre = datos.get("nombre","?")
        barrio = datos.get("barrio","?")
        familia = datos.get("familia",{})

        try:
            if familia.get("vive_con_padres"):
                msg_inicio = (
                    f"🎮 **¡Tu personaje {nombre} está listo!**\n\n"
                    f"Vives con tus padres en **{barrio}**.\n"
                    f"Solo puedes ver los canales donde has estado.\n"
                    f"Usa `/viajar` para explorar nuevos lugares.\n"
                    f"Usa `/ayuda_rp` para ver todos los comandos disponibles."
                )
            else:
                msg_inicio = (
                    f"🎮 **¡Tu personaje {nombre} está listo!**\n\n"
                    f"Estás en **{barrio}**.\n"
                    f"Solo puedes ver los canales donde has estado.\n"
                    f"Usa `/viajar` para explorar. Usa `/casas` para buscar donde vivir.\n"
                    f"Usa `/ayuda_rp` para ver todos los comandos."
                )
            await usuario.send(msg_inicio)
        except: pass

    # ── /setup_prision ────────────────────────────────────────────────────────
    @app_commands.command(name="setup_prision", description="[ADMIN] Crea los canales de la prisión de Yare")
    @es_admin()
    async def setup_prision(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        cat = discord.utils.get(guild.categories, name="PRISION")
        if not cat:
            cat = await guild.create_category("PRISION")

        canales_prision = CANALES_EXTRA.get("prision", [])
        creados = 0
        for emoji, nombre, desc, tipo in canales_prision:
            if not discord.utils.get(cat.channels, name=nombre):
                overwrites = await canal_privado_base(guild)
                await guild.create_text_channel(name=nombre, category=cat, topic=desc, overwrites=overwrites)
                creados += 1

        await interaction.followup.send(f"⛓️ Prisión de Yare configurada. {creados} canales creados.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(SetupRP(bot))