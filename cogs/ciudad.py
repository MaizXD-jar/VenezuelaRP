"""
cogs/ciudad.py — Creación de canales y embeds informativos para todos los canales útiles.
Comando /setup_embeds_canales para poblar cada canal con su embed correspondiente.
"""
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from utils.mapa import SECTORES

# ─────────────────────────────────────────────────────────────────────────────
# MAPA DE CANALES → FUNCIÓN DE EMBED
# Cada entrada: (lista de keywords del nombre de canal) → función que genera embed
# ─────────────────────────────────────────────────────────────────────────────

def _embed_hospital(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🏥 Hospital / Clínica",
        description=(
            "Bienvenido al centro médico. Aquí puedes recibir atención de emergencia y curación.\n\n"
            "**Servicios disponibles:**\n"
            "• `!curarse [item]` — cúrate a ti mismo con ítems médicos\n"
            "• `!curar @usuario [item]` — cura a otra persona\n"
            "• Bonus: los ítems `morfina`, `kit_medico` y `sangre_tipo_o` tienen **+30% eficacia** aquí\n"
            "• `/comprar morfina` `/comprar kit_medico` `/comprar sangre_tipo_o`\n\n"
            "**RP:** Si juegas como médico o enfermero, aquí es tu lugar de trabajo.\n"
            "Usa `/solicitar_trabajo medico` o `enfermero` en este canal.\n\n"
            "**Estudias medicina?** Este canal cuenta como válido para `/estudiar medicina`."
        ),
        color=0xE74C3C
    )
    embed.add_field(
        name="🩺 Ítems que puedes comprar aquí",
        value="`morfina` $40 | `kit_medico` $15 | `sangre_tipo_o` $80 | `desfibrilador` $200\n`gasa_esteril` $1.50 | `antibioticos` $12 | `vendaje` $2 | `torniquete` $5",
        inline=False
    )
    embed.add_field(
        name="💼 Trabajos disponibles aquí",
        value="`/solicitar_trabajo medico` | `/solicitar_trabajo enfermero`",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_escuela(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🏫 Centro Educativo",
        description=(
            "Este es un centro de educación. Aquí puedes estudiar, inscribirte en cursos y presentar exámenes.\n\n"
            "**Cursos disponibles en este canal:**\n"
            "• `/estudiar primaria` — gratis\n"
            "• `/estudiar bachillerato` — $50\n"
            "• `/examen primaria` / `/examen secundaria` — examen express (arriesgado)\n\n"
            "**Sistema de notas:** Cada 3 días recibes una calificación por DM.\n"
            "Si repruebas (nota < 5) pierdes el 25% del progreso. Si sacas 10 obtienes bonus extra.\n\n"
            "¿Tienes buenas notas y poco dinero? Usa `/beca` para solicitar una beca del 50%."
        ),
        color=0x3498DB
    )
    embed.add_field(
        name="📚 Comandos de educación",
        value="`/cursos` · `/estudiar <curso>` · `/mi_estudio` · `/cancelar_estudio` · `/certificados` · `/examen <nivel>` · `/beca`",
        inline=False
    )
    embed.add_field(
        name="🎓 ¿Por qué estudiar?",
        value="Los estudios desbloquean trabajos mejor pagados y mejoran tus stats permanentemente.",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_universidad(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🎓 Universidad",
        description=(
            "Bienvenido a la universidad. Aquí puedes estudiar carreras universitarias de alto nivel.\n\n"
            "**Carreras disponibles:**"
        ),
        color=0x9B59B6
    )
    carreras = [
        ("💻 Informática", "$500 | 168h | +5 int +4 tec | Bono: hackeo"),
        ("⚖️ Derecho", "$800 | 200h | +4 int +5 car | Bono: abogado"),
        ("🏥 Medicina", "$1,200 | 336h | +6 int +5 tec | Bono: médico"),
        ("🧪 Química", "$600 | 144h | +5 int +4 tec | Bono: fabricación drogas mejorada"),
        ("📰 Periodismo", "$400 | 120h | +5 car +3 int | Bono: periodista"),
        ("📊 Administración", "$450 | 120h | +3 int +3 car +2 tec | Bono: empresario"),
    ]
    for nombre, info in carreras:
        embed.add_field(name=nombre, value=info, inline=True)
    embed.add_field(
        name="📋 Comandos",
        value="`/estudiar <carrera>` · `/mi_estudio` · `/certificados` · `/examen universitario` · `/beca`",
        inline=False
    )
    embed.add_field(
        name="⚠️ Requisito",
        value="Debes tener estudios de **secundaria** para inscribirte en carreras universitarias.",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP — Requisito: Bachillerato")
    return embed


def _embed_banco(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🏦 Banco",
        description=(
            "Bienvenido al banco. Gestiona tus finanzas, invierte y solicita préstamos.\n\n"
            "**Servicios:**\n"
            "• Depósitos y retiros de efectivo\n"
            "• Inversiones en petróleo, crypto, inmuebles, bonos\n"
            "• Préstamos con 15% de interés\n"
            "• Intereses diarios sobre tu saldo"
        ),
        color=0xF39C12
    )
    embed.add_field(
        name="💳 Comandos bancarios",
        value=(
            "`!depositar <monto>` — deposita efectivo\n"
            "`!retirar <monto>` — retira a efectivo\n"
            "`!saldo_banco` — ver saldo\n"
            "`!historial_banco` — últimas transacciones\n"
            "`/prestamo <monto>` — pedir préstamo (máx $5,000)\n"
            "`/pagar_deuda <monto>` — pagar deuda\n"
            "`!invertir <tipo> <monto>` — invertir"
        ),
        inline=False
    )
    embed.add_field(
        name="📈 Tipos de inversión",
        value=(
            "`petroleo` — bajo riesgo, 5-15% en 48h\n"
            "`inmuebles` — bajo riesgo, 3-8% en 72h\n"
            "`bonos` — bajo riesgo, 2-6% en 96h\n"
            "`crypto` — alto riesgo, -40% a +150% en 24h\n"
            "`mercado_negro` — extremo, -80% a +300% en 12h"
        ),
        inline=False
    )
    embed.add_field(
        name="💼 Trabajo disponible",
        value="`/solicitar_trabajo guardia_seguridad`",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_gym(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="💪 Gimnasio / Centro Deportivo",
        description=(
            "Entrena aquí para mejorar tus estadísticas físicas de forma permanente.\n\n"
            "**Estadísticas que puedes mejorar:**\n"
            "• `fuerza` — daño en combate\n"
            "• `agilidad` — esquivar golpes y escapar\n"
            "• `resistencia` — HP máximo (+5 HP por nivel)\n"
            "• `tecnica` — precisión en combate\n"
            "• `inteligencia` — hackeo y educación\n"
            "• `carisma` — negociación y trabajos sociales"
        ),
        color=0xE67E22
    )
    embed.add_field(
        name="🏋️ Comandos",
        value=(
            "`!entrenar <stat>` — cuesta $5 por sesión\n"
            "`/estudiar educacion_fisica` — curso completo $200 (fuerza +2, agilidad +3, resistencia +3)\n"
            "`/estudiar autodefensa` — $60 (fuerza +3, agilidad +3, resistencia +2)"
        ),
        inline=False
    )
    embed.add_field(
        name="🥊 Artes marciales",
        value=(
            "• `educacion_fisica` → 72h, mejora stats físicas\n"
            "• `autodefensa` → 24h, combate cuerpo a cuerpo\n"
            "Ambos válidos en canales de gym, crossfit, muay thai, boxeo."
        ),
        inline=False
    )
    embed.add_field(
        name="💼 Trabajo disponible",
        value="`/solicitar_trabajo` (mesonero si hay café en el gym)",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Límite de stats: 30 | Venezuela RP")
    return embed


def _embed_farmacia(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="💊 Farmacia",
        description=(
            "Compra medicamentos y artículos de salud.\n\n"
            "**Cómo usar ítems de curación:**\n"
            "• `!curarse [item]` — úsalo contigo mismo\n"
            "• `!curar @usuario [item]` — cura a otra persona"
        ),
        color=0x2ECC71
    )
    embed.add_field(
        name="🩺 Ítems disponibles",
        value=(
            "`vendaje` $2 (+20 HP)\n"
            "`suero_oral` $1.50 (+10 HP)\n"
            "`antibioticos` $12 (+15 HP)\n"
            "`kit_medico` $15 (+50 HP)\n"
            "`gasa_esteril` $1.50 (+12 HP)\n"
            "`agua_oxigenada` $1 (+8 HP)\n"
            "`torniquete` $5 (+25 HP)\n"
            "`botiquin_hogar` $18 (+30 HP)\n"
            "`jeringa` $0.50"
        ),
        inline=True
    )
    embed.add_field(
        name="💼 Trabajo disponible",
        value="`/solicitar_trabajo farmaceutico` (requiere estudios universitarios)",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_concesionario(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🚗 Concesionario / Venta de Vehículos",
        description=(
            "Compra vehículos para moverte más rápido por el mapa.\n\n"
            "**Métodos de viaje desbloqueados por vehículo:**\n"
            "• `bicicleta` → `/viajar bicicleta <destino>`\n"
            "• `carro_basico` / `carro_mediano` / `carro_lujoso` → `/viajar coche <destino>`\n"
            "• Los coches reducen el tiempo de viaje hasta **70%**\n"
            "• Coches de emergencia (policía, médico) viajan al **40%** del tiempo normal"
        ),
        color=0x3498DB
    )
    embed.add_field(
        name="🚘 Vehículos disponibles",
        value=(
            "`bicicleta` — $80\n"
            "`moto_basica` — $600\n"
            "`carro_basico` — $2,500\n"
            "`carro_mediano` — $8,000\n"
            "`carro_lujoso` — $25,000\n"
            "`camioneta_4x4` — $35,000"
        ),
        inline=True
    )
    embed.add_field(
        name="📋 Cómo comprar",
        value=(
            "1. Ve al concesionario más cercano con `/viajar`\n"
            "2. Usa `/comprar <nombre_vehiculo>`\n"
            "3. Verás el vehículo en `/inventario` sección vehículos\n"
            "4. Ya puedes usar `/viajar coche <destino>`"
        ),
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_mercado_negro(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🖤 Mercado Negro",
        description=(
            "**⚠️ ZONA DE ALTA PELIGROSIDAD — SOLO ROLEPLAY FICTICIO**\n\n"
            "Aquí se comercian productos ilegales. La CPNB tiene informantes.\n"
            "Un movimiento sospechoso y la policía sabrá que estás aquí."
        ),
        color=0x1a1a1a
    )
    embed.add_field(
        name="💊 Drogas disponibles",
        value=(
            "`marihuana` $5 c/u | Pureza 60-80% | Riesgo: bajo\n"
            "`pastillas` $10 c/u | Pureza 70-90% | Riesgo: medio\n"
            "`cocaina` $20 c/u | Pureza 50-75% | Riesgo: medio\n"
            "`crack` $35 c/u | Pureza 40-70% | Riesgo: alto\n"
            "`heroina` $80 c/u | Pureza 35-65% | Riesgo: extremo"
        ),
        inline=False
    )
    embed.add_field(
        name="🔫 Armas ilegales (selección)",
        value=(
            "`navaja` $15 | `glock_17` $450 | `beretta_92` $500\n"
            "`ak47` $3,000 | `m4_carbine` $3,500 | `uzi` $1,800\n"
            "`chaleco_antibalas` $300 — 30% reducción de daño"
        ),
        inline=False
    )
    embed.add_field(
        name="📋 Comandos",
        value=(
            "`/mercadonegro` — ver catálogo completo\n"
            "`!comprar_droga <tipo> <cant>` — comprar drogas\n"
            "`!vender_droga <tipo> <cant>` — vender drogas\n"
            "`!comprar_arma_negra <nombre>` — comprar arma\n"
            "`!recetas_drogas` — ver cómo fabricar en casa\n"
            "`!craftear_droga <receta>` — fabricar (requiere tu casa)"
        ),
        inline=False
    )
    embed.add_field(
        name="🧪 ¿Tienes estudios de Química?",
        value="Si completaste la carrera de Química en la universidad, fabricas drogas con **mayor pureza** y las vendes más caro.",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | ⚠️ 15% de chance de alerta policial por transacción")
    return embed


def _embed_comisaria(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🚔 Comisaría / Sede Policial",
        description=(
            "Sede de la Cuerpo de Policía Nacional Bolivariana (CPNB).\n\n"
            "**Funciones:**\n"
            "• Aquí trabajan los jugadores con rol de Policía\n"
            "• Los admins procesan arrestos desde aquí\n"
            "• Puedes solicitar trabajo de policía aquí (solo por admin)\n"
            "• Registro civil y expedición de permisos de porte de armas"
        ),
        color=0x1a3a6e
    )
    embed.add_field(
        name="📋 Documentos que se tramitan aquí",
        value=(
            "`/comprar permiso_porte_armas` — $150 (porte legal de armas)\n"
            "`/comprar cedula_venezolana` — $10\n"
            "`/comprar licencia_conducir` — $20"
        ),
        inline=False
    )
    embed.add_field(
        name="👮 Trabajo policial",
        value=(
            "El trabajo de `policia_rp` solo puede ser asignado por un admin.\n"
            "Salario: $6/hora | Turno: 12h\n"
            "Puedes usar `!arrestar`, `!multar`, `!entorno` y el canal de aviso policial."
        ),
        inline=False
    )
    embed.add_field(
        name="⚖️ Comandos útiles",
        value="`!registros [@usuario]` — ver antecedentes | `!presos` — lista de presos",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_restaurante(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🍽️ Restaurante / Tasca / Café",
        description=(
            "Come algo para recuperar HP y socializar.\n\n"
            "**¿Cómo funciona comer?**\n"
            "1. Compra comida con `/comprar <item>`\n"
            "2. Úsala con `/usar <item>` para recuperar HP"
        ),
        color=0xE74C3C
    )
    embed.add_field(
        name="🍴 Comida disponible aquí",
        value=(
            "`arepa` $1.50 (+5 HP)\n"
            "`perro_caliente` $2 (+5 HP)\n"
            "`empanada` $1 (+5 HP)\n"
            "`pabellon_criollo` $4 (+15 HP)\n"
            "`hallaca` $3 (+10 HP)\n"
            "`pollo_completo` $8 (+20 HP)\n"
            "`tequeño` $0.50 (+3 HP)\n"
            "`refresco` $1 | `cafe_negro` $0.50 | `malta` $0.80 | `cerveza_polar` $1.50"
        ),
        inline=False
    )
    embed.add_field(
        name="💼 Trabajos disponibles aquí",
        value="`/solicitar_trabajo mesonero` · `/solicitar_trabajo cocinero`",
        inline=False
    )
    embed.add_field(
        name="🎓 Estudios disponibles aquí",
        value="`/estudiar tecnico_cocina` — $30 | 12h | +1 car +2 tec",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_supermercado(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🛒 Supermercado / Bodega / Mercado",
        description=(
            "Compra artículos de primera necesidad, comida, medicina básica y hogar.\n\n"
            "Usa `/tienda` para ver todos los artículos disponibles **en tu ubicación actual**."
        ),
        color=0x27AE60
    )
    embed.add_field(
        name="🛍️ Categorías disponibles",
        value=(
            "**Comida:** arepas, agua, refrescos, arroz, caraotas, malta...\n"
            "**Medicina básica:** vendaje, suero_oral, agua_oxigenada, botiquin_hogar\n"
            "**Hogar:** colchon, nevera_pequena, ventilador, candado_reforzado\n"
            "**Ropa:** ropa_basica, gorra, impermeable, mochila\n"
            "**Tecnología:** television, telefono_basico"
        ),
        inline=False
    )
    embed.add_field(
        name="📋 Comandos",
        value=(
            "`/tienda` — ver artículos disponibles aquí\n"
            "`/tienda comida` — filtrar por categoría\n"
            "`/comprar <item>` — comprar\n"
            "`/vender <item>` — vender al 50% del precio\n"
            "`/precios` — ver fluctuación del mercado"
        ),
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Precios fluctúan con la inflación venezolana | Venezuela RP")
    return embed


def _embed_ferreteria(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🔧 Ferretería / Taller",
        description=(
            "Compra herramientas, armas legales y materiales de construcción.\n"
            "También puedes trabajar como mecánico aquí."
        ),
        color=0x95A5A6
    )
    embed.add_field(
        name="🛠️ Artículos disponibles",
        value=(
            "**Herramientas:** `linterna` $5 · `candado` $4 · `llave_inglesa` $8 · `palanca` $12\n"
            "`maletin_herramientas` $35 · `taladro` $50 · `generador_electrico` $300\n"
            "`hacha_lena` $20 · `cuerda` $3 · `spray_pintura` $2\n"
            "**Armas legales:** `machete` $25 · `hacha` $40 · `bate_metal` $45\n"
            "**Para casas:** `candado_reforzado` $20 · `camara_vigilancia` $80"
        ),
        inline=False
    )
    embed.add_field(
        name="🔨 Crafteo disponible aquí",
        value=(
            "`/craftear escudo_improvisado` — mochila + ropa_tactica\n"
            "`/craftear radio_improvisada` — walkie_talkie + pendrive"
        ),
        inline=False
    )
    embed.add_field(
        name="💼 Trabajo disponible",
        value="`/solicitar_trabajo mecanico` — $5/hora | Turno 8h",
        inline=False
    )
    embed.add_field(
        name="🎓 Estudios",
        value="`/estudiar tecnico_mecanica` — $80 | 24h | +3 tec +1 fue",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_cc(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🏬 Centro Comercial",
        description=(
            "El centro comercial más grande de la zona.\n"
            "Aquí encuentras tecnología, ropa, vehículos y más.\n\n"
            "Usa `/tienda` para ver todo lo disponible aquí."
        ),
        color=0x3498DB
    )
    embed.add_field(
        name="🛍️ Tiendas disponibles",
        value=(
            "**Tecnología:** smartphone, smartphone_premium, tablet, television, camara_vigilancia\n"
            "**Ropa:** ropa_formal (+5 carisma), botas_militares, impermeable, gorra, mochila\n"
            "**Vehículos:** visita el concesionario en el CC\n"
            "**Hogar:** nevera_pequena, cocina_gas, ventilador, colchon"
        ),
        inline=False
    )
    embed.add_field(
        name="📋 Comandos",
        value="`/tienda` · `/comprar <item>` · `/vender <item>` · `/precios`",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_aeropuerto(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="✈️ Aeropuerto",
        description=(
            "Desde aquí puedes viajar a otras ciudades y países por avión.\n\n"
            "**Destinos disponibles en avión:**\n"
            "• Caracas ↔ Maracaibo (~1h)\n"
            "• Caracas ↔ Valencia (~50min)\n"
            "• Caracas ↔ Medellín (~1.5h)\n"
            "• Caracas ↔ Bogotá (~1.7h)\n"
            "• Caracas ↔ Miami (~3.5h)\n"
            "• Miami ↔ Bogotá (~3h)"
        ),
        color=0x85C1E9
    )
    embed.add_field(
        name="✈️ Cómo viajar en avión",
        value=(
            "`/viajar avion <destino>` — debes estar en un aeropuerto\n"
            "Ejemplo: `/viajar avion miami`\n"
            "También puedes especificar el canal: `/viajar avion aeropuerto-miami`"
        ),
        inline=False
    )
    embed.add_field(
        name="⚠️ Nota sobre viajes internacionales",
        value=(
            "Al llegar a otro país la policía venezolana **no tiene jurisdicción**.\n"
            "Cada país tiene su propia fuerza policial local."
        ),
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_terminal(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🚌 Terminal de Autobuses",
        description=(
            "Desde aquí puedes tomar autobuses interurbanos e interprovinciales.\n\n"
            "**Rutas disponibles:**\n"
            "• Caracas ↔ Valencia (~3h)\n"
            "• Caracas ↔ Maracaibo (~10h)\n"
            "• Caracas ↔ Medellín, Colombia (~24h)\n\n"
            "El autobús es más lento que el coche pero no requiere vehículo."
        ),
        color=0xF39C12
    )
    embed.add_field(
        name="🚌 Cómo tomar autobús",
        value=(
            "`/viajar autobus <destino>` — debes estar en terminal o parada\n"
            "También puedes usar `/viajar autobus` desde paradas de bus."
        ),
        inline=False
    )
    embed.add_field(
        name="💼 Trabajo disponible",
        value="`/solicitar_trabajo taxista` — $4/hora (requiere coche propio)",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_metro(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🚇 Estación de Metro",
        description=(
            "El metro de Caracas conecta los sectores de la ciudad de forma rápida y económica.\n\n"
            "**Líneas disponibles:**\n"
            "• Petare ↔ Distrito Capital ↔ 23 de Enero\n"
            "• Conexiones a: Miranda, Ciudad Universitaria"
        ),
        color=0x1ABC9C
    )
    embed.add_field(
        name="🚇 Cómo usar el metro",
        value=(
            "`/viajar metro <destino>` — más rápido que caminar\n"
            "Solo funciona entre estaciones de metro conectadas.\n"
            "No requiere vehículo propio."
        ),
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_tren(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🚂 Estación de Tren",
        description=(
            "El tren conecta Caracas con ciudades más distantes como Valencia.\n\n"
            "**Ruta principal:** Caracas → Valencia (~2h)"
        ),
        color=0x7F8C8D
    )
    embed.add_field(
        name="🚂 Cómo usar el tren",
        value="`/viajar tren <destino>` — solo desde estaciones de tren.",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_registro_civil(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="📋 Registro Civil / Notaría",
        description=(
            "Aquí puedes tramitar documentos oficiales de identidad.\n\n"
            "**Sin documentos estás en situación de indocumentado.**\n"
            "La policía puede arrestarte si no tienes cédula."
        ),
        color=0x8E44AD
    )
    embed.add_field(
        name="📄 Documentos disponibles",
        value=(
            "`/comprar cedula_venezolana` — $10 (ID Venezuela)\n"
            "`/comprar pasaporte` — $50 (viajes internacionales)\n"
            "`/comprar licencia_conducir` — $20 (para taxistas)\n"
            "`/comprar carnet_prensa` — $30 (acceso a zonas restringidas)"
        ),
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_gasolinera(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="⛽ Gasolinera PDVSA",
        description=(
            "Estación de gasolina venezolana.\n"
            "La gasolina es subvencionada por el estado, pero a veces escasea."
        ),
        color=0xF39C12
    )
    embed.add_field(
        name="⛽ Artículos disponibles",
        value=(
            "`/comprar bidan_gasolina` — $15 (10L de gasolina)\n"
            "`/comprar bombonas_gas` — $5 (gas doméstico)\n\n"
            "El bidán de gasolina es necesario para craftear ciertos objetos."
        ),
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_bodega(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🏪 Bodega",
        description=(
            "La bodega del barrio. Compra artículos básicos de primera necesidad."
        ),
        color=0x27AE60
    )
    embed.add_field(
        name="🛒 Disponible aquí",
        value=(
            "**Comida:** arepas, empanadas, tequeños, agua, refresco, malta, cerveza_polar\n"
            "**Básicos:** cigarro $0.50, encendedor $0.50, mapa_caracas $2\n"
            "**Herramientas:** cuchillo_cocina $5, cuerda $3\n"
            "**Medicina básica:** agua_oxigenada $1, suero_oral $1.50"
        ),
        inline=False
    )
    embed.add_field(
        name="📋 Comandos",
        value="`/tienda` · `/comprar <item>` · `/vender <item>`",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_taller(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🔧 Taller Mecánico / Garage",
        description=(
            "Trabaja como mecánico o fabrica objetos especiales."
        ),
        color=0x7F8C8D
    )
    embed.add_field(
        name="🔨 Crafteo disponible AQUÍ",
        value=(
            "`/craftear escudo_improvisado` — mochila + ropa_tactica (60%)\n"
            "`/craftear radio_improvisada` — walkie_talkie + pendrive (55%)"
        ),
        inline=False
    )
    embed.add_field(
        name="💼 Trabajo",
        value="`/solicitar_trabajo mecanico` — $5/hora | Turno 8h",
        inline=False
    )
    embed.add_field(
        name="🎓 Estudios",
        value="`/estudiar tecnico_mecanica` — requiere estar aquí",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_tribunal(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="⚖️ Tribunal / Juzgado",
        description=(
            "Sede del poder judicial venezolano.\n\n"
            "Los abogados trabajan aquí. También se tramitan documentos legales."
        ),
        color=0x2C3E50
    )
    embed.add_field(
        name="📄 Documentos disponibles",
        value="`/comprar carnet_prensa` $30 · `/comprar cedula_venezolana` $10",
        inline=False
    )
    embed.add_field(
        name="💼 Trabajo",
        value="`/solicitar_trabajo abogado` — $15/hora | Requiere carrera de Derecho",
        inline=False
    )
    embed.add_field(
        name="🎓 Estudios",
        value="`/estudiar derecho` — válido en este canal",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_iglesia(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="⛪ Iglesia",
        description=(
            "Lugar de paz y reflexión. Los personajes pueden venir a 'descasar'.\n\n"
            "**Función especial:** Si tu HP es menor a 30 y llevas 10 minutos aquí,\n"
            "recibirás +5 HP de recuperación pasiva cada cierto tiempo.\n\n"
            "El sacerdote local es un NPC disponible para interacción.\n"
            "Úsalo con `/npc_info Padre Miguel Angel`."
        ),
        color=0xF5CBA7
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_zona_industrial(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🏭 Zona Industrial",
        description=(
            "Área de trabajo y manufactura industrial.\n\n"
            "Aquí trabajan obreros, mecánicos y se pueden comprar materiales."
        ),
        color=0x7F8C8D
    )
    embed.add_field(
        name="🏗️ Artículos disponibles",
        value=(
            "`/comprar generador_electrico` — $300\n"
            "`/comprar taladro` — $50\n"
            "`/comprar maletin_herramientas` — $35"
        ),
        inline=False
    )
    embed.add_field(
        name="💼 Trabajos aquí",
        value="`/solicitar_trabajo obrero` — $2.50/hora | `/solicitar_trabajo mecanico`",
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_hotel(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🏨 Hotel",
        description=(
            "Alojamiento temporal para viajeros.\n\n"
            "Los personajes sin casa pueden 'descansar' aquí temporalmente.\n"
            "Es un punto de encuentro neutral y seguro."
        ),
        color=0xD4AC0D
    )
    embed.add_field(
        name="🛏️ Servicios",
        value=(
            "• Zona segura: eventos negativos tienen -50% de probabilidad aquí\n"
            "• Punto de encuentro: cualquiera puede estar aquí sin restricciones\n"
            "• Disponible para transacciones discretas en el RP"
        ),
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_plaza(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🌳 Plaza / Parque",
        description=(
            "Espacio público abierto. Zona de socialización y eventos.\n\n"
            "• Cualquiera puede estar aquí sin restricciones\n"
            "• Lugar ideal para encuentros de RP\n"
            "• Los eventos políticos y manifestaciones suelen ocurrir aquí"
        ),
        color=0x2ECC71
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_gobierno(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🏛️ Edificio de Gobierno",
        description=(
            "Sede del poder ejecutivo o legislativo.\n\n"
            "**Actividades políticas:**\n"
            "• `!postularse <cargo> <partido>` — postularte a elecciones\n"
            "• `!candidatos` — ver candidatos actuales\n"
            "• `!nivel_busqueda` — ver tu nivel de búsqueda\n\n"
            "**Partidos disponibles:** `psuv` · `mud` · `vente` · `pj` · `independiente`\n"
            "**Cargos:** `concejal` · `alcalde` · `gobernador` · `diputado` · `presidente`"
        ),
        color=0xCF1020
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP — ⚠️ Las acciones políticas escalan tu nivel de búsqueda")
    return embed


def _embed_prisión(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="⛓️ Prisión de Yare",
        description=(
            "Estás dentro de la Prisión de Yare.\n\n"
            "**Estado:** ARRESTADO\n"
            "No puedes salir hasta que un admin te libere con `!liberar`.\n\n"
            "**Mientras estás aquí:**\n"
            "• Puedes hablar con otros presos\n"
            "• Puedes hacer tratos con `cigarro` como moneda de cambio\n"
            "• El patio permite actividad física: `!entrenar` (sin costo)\n"
            "• Un guardia puede trasladarte a otra celda"
        ),
        color=0x2C3E50
    )
    embed.add_field(
        name="⚖️ ¿Cómo salir?",
        value=(
            "Solo un admin puede liberarte con `!liberar @usuario`.\n"
            "Habla con la policía en el RP para negociar tu liberación."
        ),
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Prisión de Yare — Venezuela RP")
    return embed


def _embed_laboratorio(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🔬 Laboratorio",
        description=(
            "Laboratorio científico. Estudia ciencias y fabrica objetos avanzados."
        ),
        color=0x1ABC9C
    )
    embed.add_field(
        name="🧪 Crafteo disponible aquí",
        value="`/craftear radio_improvisada` — walkie_talkie + pendrive (55%)",
        inline=False
    )
    embed.add_field(
        name="🎓 Estudios válidos aquí",
        value=(
            "`/estudiar informatica` · `/estudiar quimica` · `/estudiar medicina`\n"
            "*(también válidos en la universidad)*"
        ),
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_biblioteca(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="📚 Biblioteca",
        description=(
            "Lugar de estudio e investigación."
        ),
        color=0x8E44AD
    )
    embed.add_field(
        name="🎓 Estudios válidos aquí",
        value=(
            "`/estudiar derecho` · `/estudiar periodismo`\n"
            "`/estudiar administracion` · `/estudiar informatica`"
        ),
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_campo_deportivo(canal_nombre: str) -> discord.Embed:
    embed = discord.Embed(
        title="🏟️ Campo / Cancha Deportiva",
        description=(
            "Área deportiva al aire libre. Entrena o juega béisbol."
        ),
        color=0x27AE60
    )
    embed.add_field(
        name="🏋️ Comandos",
        value=(
            "`!entrenar <stat>` — cuesta $5 (fuerza, agilidad, resistencia)\n"
            "`/estudiar educacion_fisica` — $200 | 72h\n"
            "`/estudiar autodefensa` — $60 | 24h"
        ),
        inline=False
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP")
    return embed


def _embed_default_barrio(canal_nombre: str) -> discord.Embed:
    """Embed genérico para calles y barrios sin función específica."""
    embed = discord.Embed(
        title=f"📍 {canal_nombre.replace('-', ' ').title()}",
        description=(
            "Zona del barrio. Aquí puedes interactuar con otros personajes en el RP.\n\n"
            "**Comandos de roleplay:**\n"
            "`!me <acción>` · `!do <descripción>` · `!entorno <descripción>`\n"
            "`!susurrar @usuario <msg>` · `!grito <msg>` · `!oc <msg fuera del personaje>`\n\n"
            "Usa `/viajar <destino>` para moverte a otro canal."
        ),
        color=0x95A5A6
    )
    embed.set_footer(text=f"📍 {canal_nombre} | Venezuela RP — /ayuda_rp para ver todos los comandos")
    return embed


# ── MAPA DE KEYWORDS → FUNCIÓN DE EMBED ─────────────────────────────────────
# Se evalúan en orden, primer match gana
EMBED_MAP = [
    # Prioridad alta — canales muy específicos
    (["mercado-negro", "mercado_negro"],                           _embed_mercado_negro),
    (["prision", "yare", "celda", "patio-yare"],                  _embed_prisión),
    (["aeropuerto"],                                               _embed_aeropuerto),
    (["metro"],                                                    _embed_metro),
    (["tren", "estacion-tren"],                                    _embed_tren),
    (["terminal", "parada-bus", "parada-autobus", "transmilenio"], _embed_terminal),
    (["banco", "banesco", "mercantil", "provincial", "occidental",
      "bancolombia", "banco-central", "bank-of-america"],          _embed_banco),
    (["hospital", "clinica", "emergencia", "jackson"],             _embed_hospital),
    (["farmacia", "farmatodo", "drogueria"],                       _embed_farmacia),
    (["ucv", "universidad", "univ"],                               _embed_universidad),
    (["escuela", "liceo", "colegio", "aplicacion"],                _embed_escuela),
    (["biblioteca"],                                               _embed_biblioteca),
    (["laboratorio"],                                              _embed_laboratorio),
    (["gym", "crossfit", "boxeo", "muay", "fitness", "crossfit",
      "country-club", "estadio-ucv"],                              _embed_gym),
    (["cancha", "campo-pelota", "campo-deporte", "estadio", "campo-beisbol"], _embed_campo_deportivo),
    (["concesionario", "rent-a-car", "car-dealership", "dealership"], _embed_concesionario),
    (["ferreteria", "taller", "garage", "mecanico"],               _embed_ferreteria),
    (["comisaria", "policia", "cpnb", "cicpc", "sebin"],           _embed_comisaria),
    (["tribunal", "juzgado", "bufete"],                            _embed_tribunal),
    (["registro", "notaria", "saren", "saime"],                    _embed_registro_civil),
    (["sambil", "cc-", "centro-comercial", "mall", "recreo",
      "buenaventura", "oviedo", "andino", "tamanaco"],             _embed_cc),
    (["supermercado", "automercado", "las-pulgas", "san-alejo"],   _embed_supermercado),
    (["restaurante", "la-estancia", "versailles", "comida",
      "pollos", "criollo", "gourmet", "cantina"],                  _embed_restaurante),
    (["tasca", "cafe", "juan-valdez", "starbucks", "cerveceria"],  _embed_restaurante),
    (["bodega", "dona-carmen"],                                    _embed_bodega),
    (["gasolinera", "pdvsa", "bomba"],                             _embed_gasolinera),
    (["hotel", "eurobuilding", "fontainebleau"],                   _embed_hotel),
    (["palacio", "miraflores", "capitolio", "gobierno"],           _embed_gobierno),
    (["iglesia", "parroquia"],                                     _embed_iglesia),
    (["zona-industrial", "industrial"],                            _embed_zona_industrial),
    (["parque", "plaza", "caobos", "llovizna", "botanical",
      "paseo", "wynwood", "arvi"],                                  _embed_plaza),
]


def _get_embed_for_canal(canal_nombre: str) -> discord.Embed | None:
    """Devuelve el embed adecuado para un canal según su nombre, o None si no hay match específico."""
    nombre_lower = canal_nombre.lower()
    for keywords, fn in EMBED_MAP:
        if any(kw in nombre_lower for kw in keywords):
            return fn(canal_nombre)
    # Canales de casa → sin embed informativo (el embed se envía al comprar)
    if nombre_lower.startswith("casa-"):
        return None
    # Canales de barrio/calle genéricos
    if any(x in nombre_lower for x in ["barrio", "calle", "av-", "residencia", "bloque",
                                        "sector", "zona", "poblado", "havana", "doral",
                                        "comunidad", "callejon", "monte"]):
        return _embed_default_barrio(canal_nombre)
    return None


def es_admin():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)


class Ciudad(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── /setup_embeds_canales ──────────────────────────────────────────────────
    @app_commands.command(
        name="setup_embeds_canales",
        description="[ADMIN] Envía embeds informativos a todos los canales útiles del servidor"
    )
    @es_admin()
    async def setup_embeds_canales(self, interaction: discord.Interaction):
        """
        Recorre TODOS los canales de texto del servidor y envía el embed
        correspondiente si el canal está vacío o solo tiene embeds del bot.
        """
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        procesados = 0
        enviados = 0
        errores = []

        for canal in guild.text_channels:
            # Saltar canales del sistema (informativos especiales)
            canales_sistema_ids = {
                1484797041560260688, 1369366721550614700, 1421513030851629056,
                1359320812003393567, 1359320811420520614, 1359412448976965713,
                1359320811420520609, 1369438606694944799, 1359320811420520613,
                1369438636260724856, 1369365887156617428, 1359320808526450780,
                1382156099473379458, 1382156210576425040, 1382156276016087110,
                1484642756927164529, 1359364736822804571,
            }
            if canal.id in canales_sistema_ids:
                continue
            # Saltar canales de teléfonos y documentaciones
            if canal.name.startswith("📱") or "tel-" in canal.name:
                continue

            procesados += 1
            embed = _get_embed_for_canal(canal.name)
            if not embed:
                continue

            # Verificar si ya tiene un embed informativo del bot
            try:
                mensajes_recientes = [m async for m in canal.history(limit=5)]
                ya_tiene_embed = any(
                    m.author.id == guild.me.id and m.embeds
                    for m in mensajes_recientes
                )
                if ya_tiene_embed:
                    continue

                await canal.send(embed=embed)
                enviados += 1
                await asyncio.sleep(0.4)  # Rate limit gentil
            except discord.Forbidden:
                errores.append(f"Sin permisos: #{canal.name}")
            except Exception as e:
                errores.append(f"#{canal.name}: {str(e)[:50]}")

        resumen = (
            f"✅ **Setup de embeds completado**\n"
            f"📋 Canales procesados: {procesados}\n"
            f"📨 Embeds enviados: {enviados}\n"
        )
        if errores:
            resumen += f"⚠️ Errores ({len(errores)}): {', '.join(errores[:8])}"

        await interaction.followup.send(resumen, ephemeral=True)

    # ── /setup_embeds_sector ───────────────────────────────────────────────────
    @app_commands.command(
        name="setup_embeds_sector",
        description="[ADMIN] Envía embeds solo a los canales de un sector específico"
    )
    @es_admin()
    @app_commands.describe(sector="Nombre del sector (ej: petare, las-mercedes)")
    async def setup_embeds_sector(self, interaction: discord.Interaction, sector: str):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        sector = sector.lower().replace(" ", "-")

        # Buscar categoría del sector
        cat = discord.utils.get(guild.categories, name=sector.upper())
        if not cat:
            return await interaction.followup.send(
                f"❌ No encontré la categoría `{sector.upper()}`. ¿Existe el sector?",
                ephemeral=True
            )

        enviados = 0
        errores = []
        for canal in cat.channels:
            if not isinstance(canal, discord.TextChannel):
                continue
            if canal.name.startswith("casa-"):
                continue

            embed = _get_embed_for_canal(canal.name)
            if not embed:
                continue

            try:
                mensajes_recientes = [m async for m in canal.history(limit=3)]
                ya_tiene_embed = any(
                    m.author.id == guild.me.id and m.embeds
                    for m in mensajes_recientes
                )
                if ya_tiene_embed:
                    continue
                await canal.send(embed=embed)
                enviados += 1
                await asyncio.sleep(0.3)
            except discord.Forbidden:
                errores.append(f"Sin permisos: #{canal.name}")
            except Exception as e:
                errores.append(f"#{canal.name}: {str(e)[:40]}")

        msg = f"✅ Sector **{sector.upper()}**: {enviados} embeds enviados."
        if errores:
            msg += f"\n⚠️ Errores: {', '.join(errores[:5])}"
        await interaction.followup.send(msg, ephemeral=True)

    # ── /reenviar_embed_canal ─────────────────────────────────────────────────
    @app_commands.command(
        name="reenviar_embed_canal",
        description="[ADMIN] Reenvía el embed informativo a un canal específico"
    )
    @es_admin()
    @app_commands.describe(canal="Canal al que enviar el embed")
    async def reenviar_embed_canal(self, interaction: discord.Interaction, canal: discord.TextChannel):
        embed = _get_embed_for_canal(canal.name)
        if not embed:
            return await interaction.response.send_message(
                f"❌ No hay embed definido para `{canal.name}`.",
                ephemeral=True
            )
        await canal.send(embed=embed)
        await interaction.response.send_message(
            f"✅ Embed enviado a {canal.mention}.", ephemeral=True
        )

    # ── /crear_sector ──────────────────────────────────────────────────────────
    @app_commands.command(name="crear_sector", description="[ADMIN] Crea todos los canales de un sector")
    @es_admin()
    @app_commands.describe(sector="Nombre del sector (ej: petare)")
    async def crear_sector(self, interaction: discord.Interaction, sector: str):
        sector = sector.lower().replace(" ", "-")
        if sector not in SECTORES:
            return await interaction.response.send_message(
                f"❌ Sector no encontrado. Sectores: {', '.join(SECTORES.keys())}",
                ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        sec_info = SECTORES[sector]

        categoria = discord.utils.get(guild.categories, name=sector.upper())
        if not categoria:
            categoria = await guild.create_category(sector.upper())

        creados = []
        existentes = []

        # Canales del mapa
        for canal_nombre in sec_info.get("canales", {}).keys():
            canal_existente = discord.utils.get(categoria.channels, name=canal_nombre)
            if canal_existente:
                existentes.append(canal_nombre)
                continue
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            await guild.create_text_channel(name=canal_nombre, category=categoria, overwrites=overwrites)
            creados.append(canal_nombre)

        # Casas
        n_casas = sec_info.get("casas_total", 20)
        for i in range(1, n_casas + 1):
            nombre = f"casa-{i}"
            if not discord.utils.get(categoria.channels, name=nombre):
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                }
                await guild.create_text_channel(
                    name=nombre, category=categoria,
                    topic=f"Casa {i} en {sector} — disponible",
                    overwrites=overwrites
                )
                creados.append(nombre)

        msg = f"✅ Sector **{sector.upper()}** configurado.\n"
        msg += f"📋 Creados: {len(creados)} | Ya existían: {len(existentes)}"
        await interaction.followup.send(msg, ephemeral=True)

    # ── /crear_todos_sectores ──────────────────────────────────────────────────
    @app_commands.command(name="crear_todos_sectores", description="[ADMIN] ⚠️ Crea TODOS los sectores y canales")
    @es_admin()
    async def crear_todos_sectores(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        total_creados = 0
        errores = []

        for sector, sec_info in SECTORES.items():
            try:
                categoria = discord.utils.get(guild.categories, name=sector.upper())
                if not categoria:
                    categoria = await guild.create_category(sector.upper())

                for canal_nombre in sec_info.get("canales", {}).keys():
                    if discord.utils.get(categoria.channels, name=canal_nombre):
                        continue
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                    }
                    await guild.create_text_channel(name=canal_nombre, category=categoria, overwrites=overwrites)
                    total_creados += 1

                n_casas = sec_info.get("casas_total", 20)
                for i in range(1, n_casas + 1):
                    nombre = f"casa-{i}"
                    if not discord.utils.get(categoria.channels, name=nombre):
                        overwrites = {
                            guild.default_role: discord.PermissionOverwrite(read_messages=False),
                            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                        }
                        await guild.create_text_channel(
                            name=nombre, category=categoria,
                            topic=f"Casa {i} en {sector} — disponible",
                            overwrites=overwrites
                        )
                        total_creados += 1
            except Exception as e:
                errores.append(f"{sector}: {e}")

        msg = f"🏙️ **Setup completo** — {total_creados} canales creados"
        if errores:
            msg += f"\n⚠️ Errores: {', '.join(errores[:5])}"
        await interaction.followup.send(msg, ephemeral=True)

    # ── /dar_acceso_canal ──────────────────────────────────────────────────────
    @app_commands.command(name="dar_acceso_canal", description="[ADMIN] Da acceso a un canal privado a un jugador")
    @es_admin()
    async def dar_acceso_canal(self, interaction: discord.Interaction, canal: discord.TextChannel, usuario: discord.Member):
        await canal.set_permissions(usuario, read_messages=True, send_messages=True)
        await interaction.response.send_message(
            f"✅ {usuario.mention} tiene acceso a {canal.mention}.", ephemeral=True
        )

    # ── /quitar_acceso_canal ───────────────────────────────────────────────────
    @app_commands.command(name="quitar_acceso_canal", description="[ADMIN] Quita acceso de un jugador a un canal")
    @es_admin()
    async def quitar_acceso_canal(self, interaction: discord.Interaction, canal: discord.TextChannel, usuario: discord.Member):
        await canal.set_permissions(usuario, overwrite=None)
        await interaction.response.send_message(
            f"✅ Acceso de {usuario.mention} a {canal.mention} revocado.", ephemeral=True
        )

    # ── Error handler ──────────────────────────────────────────────────────────
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Solo administradores.", ephemeral=True)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Ciudad(bot))