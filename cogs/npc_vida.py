"""
cogs/npc_vida.py — Vida autónoma de los NPCs.

Cada NPC tiene una ACTIVIDAD acorde a su tipo (un policía patrulla, un criminal
trafica, un funcionario despacha...). Las actividades duran un buen rato de
tiempo real (30 min a 3 h), así que el mundo se siente vivo pero sin spam.

Cuando un NPC empieza o termina algo, la IA narra la escena en 1-2 frases con
su personalidad y su ubicación siempre visible. Los NPCs también se desplazan
entre sectores usando el mismo mapa y rutas que los jugadores, y pueden morir
de forma aleatoria (poco probable, y más si su trabajo es peligroso).
"""
import random
import time

import discord
from discord.ext import commands, tasks
from discord import app_commands

from utils import db
from utils import ia
from utils import tiempo_juego
from utils.mapa import SECTORES, mejor_ruta, canal_con_sector
from cogs.npc import npc_viajes_activos, ICONOS_METODO

# Sectores donde opera la policía venezolana (duplicado ligero de
# cogs/policia.py para no crear un import circular entre cogs).
SECTORES_VENEZUELA = {
    "petare", "las-mercedes", "distrito-capital", "23-de-enero",
    "ciudad-universitaria", "miranda", "la-alameda", "la-trinidad",
    "maracaibo", "valencia", "prision-yare"
}

HORAS_CONDENA_NPC = 6  # cuánto tiempo real pasa un NPC arrestado antes de salir

# ── Actividades por tipo de NPC ──────────────────────────────────────────────
# (nombre, descripción, duración mínima y máxima en MINUTOS REALES)
ACTIVIDADES = {
    "policia": [
        ("patrullar", "patrulla las calles buscando actividad sospechosa", 45, 120),
        ("puesto_control", "monta un punto de control y revisa documentos", 60, 150),
        ("investigar", "investiga una denuncia reciente", 90, 180),
        ("papeleo", "rellena informes en la comisaría", 30, 60),
        ("descanso", "hace una pausa para comer", 30, 45),
    ],
    "sebin": [
        ("vigilancia", "vigila discretamente a un objetivo", 90, 180),
        ("informante", "se reúne con un informante", 60, 120),
        ("archivo", "revisa expedientes clasificados", 45, 90),
    ],
    "militar": [
        ("guardia", "monta guardia en su puesto", 60, 150),
        ("ejercicio", "dirige un ejercicio de instrucción", 90, 180),
        ("inspeccion", "inspecciona el armamento de la unidad", 45, 90),
    ],
    "gobierno": [
        ("despacho", "atiende asuntos en su despacho", 60, 150),
        ("reunion", "se reúne con otros funcionarios", 45, 120),
        ("acto_publico", "participa en un acto público", 60, 120),
        ("tramites", "firma trámites y permisos", 30, 90),
    ],
    "criminal": [
        ("trapicheo", "hace negocios en una esquina del barrio", 45, 120),
        ("planificar", "planea un golpe con su gente", 60, 150),
        ("cobrar", "pasa a cobrar deudas pendientes", 45, 90),
        ("esconderse", "se mantiene fuera de la vista de la policía", 90, 180),
    ],
    "civil": [
        ("trabajar", "cumple su jornada de trabajo", 60, 180),
        ("compras", "sale a hacer compras", 30, 60),
        ("visita", "visita a un familiar", 45, 90),
        ("descanso", "descansa en casa", 60, 120),
    ],
    "presidente": [
        ("consejo_ministros", "preside un Consejo de Ministros", 60, 150),
        ("discurso", "da un discurso público, rodeado de su escolta", 45, 90),
        ("agenda_internacional", "atiende una reunión con delegados extranjeros", 60, 120),
        ("despacho_presidencial", "despacha asuntos de Estado en Miraflores", 60, 180),
    ],
    "escolta": [
        ("custodia", "custodia de cerca al funcionario que protege", 45, 150),
        ("perimetro", "revisa el perímetro de seguridad", 30, 90),
        ("escolta_vehiculo", "acompaña el convoy oficial", 30, 60),
    ],
    "abogado": [
        ("consulta", "atiende una consulta legal en su oficina", 45, 120),
        ("expediente", "revisa expedientes de sus casos", 30, 90),
        ("tribunal", "se presenta en el tribunal por una audiencia", 60, 150),
    ],
    "juez": [
        ("audiencia", "preside una audiencia en el tribunal", 60, 150),
        ("despacho_juez", "redacta una sentencia en su despacho", 45, 120),
    ],
}

# Probabilidad de muerte aleatoria por ciclo, según lo peligroso del tipo.
PROB_MUERTE = {
    "criminal":   0.010,
    "policia":    0.005,
    "militar":    0.005,
    "sebin":      0.004,
    "gobierno":   0.002,
    "civil":      0.002,
    "presidente": 0.0005,  # muy protegido: casi nunca muere de forma aleatoria
    "escolta":    0.003,
    "abogado":    0.001,
    "juez":       0.001,
}

CAUSAS_MUERTE = {
    "criminal":   ["ajuste de cuentas", "enfrentamiento con la policía", "una emboscada rival"],
    "policia":    ["un tiroteo en servicio", "un accidente durante una persecución"],
    "militar":    ["un accidente durante un ejercicio", "un incidente en su puesto"],
    "sebin":      ["una operación que salió mal"],
    "gobierno":   ["un infarto repentino", "un accidente de tráfico"],
    "civil":      ["un accidente de tráfico", "una enfermedad repentina", "un robo que acabó mal"],
    "presidente": ["un intento de golpe frustrado por su escolta", "un problema de salud repentino"],
    "escolta":    ["un enfrentamiento defendiendo a su protegido", "un accidente en un operativo"],
    "abogado":    ["un accidente de tráfico", "una amenaza de un cliente que salió mal"],
    "juez":       ["un infarto repentino", "un accidente de tráfico"],
}

PROB_VIAJE = 0.20  # probabilidad de que, al terminar, el NPC se mude de sector

SYSTEM_NPC = (
    "Narras la vida cotidiana de personajes NPC en un servidor de roleplay de "
    "Discord ambientado en una Venezuela ficticia. Escribes SIEMPRE en español, "
    "en tercera persona, 1 o 2 frases como máximo, en tono realista y sobrio.\n"
    "REGLAS: menciona SIEMPRE dónde está el personaje. Respeta su profesión y su "
    "personalidad. No inventes que interactúa con jugadores concretos. No uses "
    "comillas de diálogo largas. Nada de violencia gráfica ni contenido sexual."
)


def _tipo(npc: dict) -> str:
    t = npc.get("tipo", "civil")
    return t if t in ACTIVIDADES else "civil"


def _embed_accion(npc: dict, texto: str, color=discord.Color.greyple()) -> discord.Embed:
    """Mismo formato que /npc_accion: cursiva + autor con el nombre del NPC,
    en vez de un mensaje de texto plano suelto en el canal."""
    embed = discord.Embed(description=f"*{texto}*", color=color)
    embed.set_author(name=f"[NPC] {npc.get('nombre','?')}")
    if npc.get("imagen"):
        embed.set_thumbnail(url=npc["imagen"])
    return embed


def _embed_hablar(npc: dict, texto: str, color=discord.Color.teal()) -> discord.Embed:
    """Mismo formato que /npc_hablar: el NPC diciendo algo en primera persona."""
    embed = discord.Embed(description=texto, color=color)
    embed.set_author(name=f"{npc.get('nombre','?')} [{npc.get('trabajo','?')}]")
    if npc.get("imagen"):
        embed.set_thumbnail(url=npc["imagen"])
    return embed


def _tiene_coche(npc: dict) -> bool:
    vehiculos = npc.get("vehiculos", [])
    return any("carro" in v or "coche" in v for v in vehiculos)


async def _narrar(npc: dict, actividad_desc: str, sector: str, momento: str) -> str:
    """Pide a la IA que narre la escena. Si no hay IA, usa un texto simple."""
    sec = SECTORES.get(sector, {})
    lugar = sec.get("display", sector)
    fecha = await tiempo_juego.fecha_texto()

    fallback = f"**{npc.get('nombre','?')}** {actividad_desc} en **{lugar}**."
    if not ia.hay_ia():
        return fallback

    prompt = (
        f"Fecha en el rol: {fecha}.\n"
        f"Personaje: {npc.get('nombre','?')}, {npc.get('edad','?')} años, "
        f"profesión: {npc.get('trabajo','?')} (tipo: {npc.get('tipo','civil')}).\n"
        f"Ubicación: {lugar} ({sector}), zona con peligro {sec.get('peligro','?')}/5.\n"
        f"{'Tiene coche propio y puede usarlo si la acción implica desplazarse.' if _tiene_coche(npc) else 'No tiene coche.'}\n"
        f"Acción: {actividad_desc}.\n"
        f"Momento: {'está empezando esta actividad' if momento == 'inicio' else 'acaba de terminar esta actividad'}.\n"
        f"Narra la escena en 1-2 frases, en tercera persona, usando **negritas** de Discord "
        f"para resaltar el nombre del personaje y el lugar (formato Markdown de Discord)."
    )
    texto, _ = await ia.generar(SYSTEM_NPC, prompt, max_tokens=150, timeout_seg=20)
    return texto or fallback


class NPCVida(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def start_tasks(self):
        if not self.ciclo_npcs.is_running():
            self.ciclo_npcs.start()
        if not self.eventos_npc_npc.is_running():
            self.eventos_npc_npc.start()
        if not self.npcs_compran_casas.is_running():
            self.npcs_compran_casas.start()

    async def _canal_de_sector(self, guild: discord.Guild, sector: str):
        """Canal donde publicar lo que hace un NPC: una calle o avenida del sector."""
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

    @tasks.loop(minutes=15)
    async def ciclo_npcs(self):
        """Revisa cada 15 min: termina actividades cumplidas y empieza nuevas.
        Como cada actividad dura 30-180 min, un NPC concreto solo actúa un par de
        veces por hora — nada de spam."""
        try:
            npcs = await db.all("npcs")
        except Exception:
            return
        if not npcs:
            return

        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return

        ahora = time.time()
        for npc_id, npc in list(npcs.items()):
            if npc.get("muerto"):
                continue

            # ── ¿Está arrestado? Sale sola cuando cumple condena ────────────
            if npc.get("arrestado_npc"):
                if ahora >= npc.get("libera_ts", 0):
                    npc["arrestado_npc"] = False
                    npc["libera_ts"] = None
                    sector_salida = npc.get("ubicacion", "prision-yare")
                    await db.set("npcs", npc_id, npc)
                    canal = await self._canal_de_sector(guild, sector_salida)
                    if canal:
                        try:
                            await canal.send(embed=_embed_accion(
                                npc, f"sale de la cárcel tras cumplir su condena en **{SECTORES.get(sector_salida,{}).get('display',sector_salida)}**.",
                                color=discord.Color.green()
                            ))
                        except Exception:
                            pass
                continue  # mientras está preso (o recién liberado) no hace actividad normal este ciclo

            estado = await db.get("npc_estado", npc_id) or {}
            fin = estado.get("fin_ts", 0)

            # Sigue ocupado
            if fin and ahora < fin:
                continue

            tipo = _tipo(npc)
            sector = npc.get("ubicacion", "petare")

            # ── ¿Muere? (poco probable, solo al cambiar de actividad) ─────────
            if random.random() < PROB_MUERTE.get(tipo, 0.002):
                causa = random.choice(CAUSAS_MUERTE.get(tipo, ["causas naturales"]))
                npc["muerto"] = True
                npc["causa_muerte"] = causa
                await db.set("npcs", npc_id, npc)
                await db.set("npc_estado", npc_id, {})
                canal = await self._canal_de_sector(guild, sector)
                if canal:
                    embed = discord.Embed(
                        title="🕯️ Fallecimiento",
                        description=f"**{npc.get('nombre','?')}** ({npc.get('trabajo','?')}) "
                                    f"ha fallecido en **{SECTORES.get(sector,{}).get('display',sector)}**.\n"
                                    f"Causa: {causa}.",
                        color=0x2C2F33
                    )
                    embed.set_footer(text=await tiempo_juego.fecha_texto())
                    try:
                        await canal.send(embed=embed)
                    except Exception:
                        pass
                try:
                    from cogs.noticias_ia import registrar_evento
                    await registrar_evento("fallecimiento",
                        f"{npc.get('nombre','?')} ({npc.get('trabajo','?')}) falleció en {SECTORES.get(sector,{}).get('display',sector)}: {causa}.")
                except Exception:
                    pass
                continue

            # ── Cerrar la actividad anterior ──────────────────────────────────
            if estado.get("actividad_desc"):
                texto = await _narrar(npc, estado["actividad_desc"], sector, "fin")
                canal = await self._canal_de_sector(guild, sector)
                if canal:
                    try:
                        await canal.send(embed=_embed_accion(npc, texto))
                    except Exception:
                        pass

            # ── ¿Se muda de sector? ───────────────────────────────────────────
            # NOTA: el viaje NO es instantáneo. Se agenda en npc_viajes_activos
            # (el mismo bucle que procesa /npc_viajar, en cogs/npc.py) para que
            # el NPC tarde un tiempo real en llegar y el aviso de LLEGADA salga
            # por separado, en un momento distinto al de cualquier jugador que
            # esté viajando a la vez.
            if random.random() < PROB_VIAJE and npc_id not in npc_viajes_activos:
                destinos = [s for s in SECTORES if s != sector and SECTORES[s].get("casas_total", 0) > 0]
                if destinos:
                    nuevo = random.choice(destinos)
                    ruta = mejor_ruta(sector, nuevo)
                    if ruta and ruta["pasos"]:
                        canal_origen = await self._canal_de_sector(guild, sector)
                        canales_nuevo = list(SECTORES.get(nuevo, {}).get("canales", {}).keys())
                        canal_destino_nombre = canales_nuevo[0] if canales_nuevo else nuevo
                        metodo = ruta["pasos"][0][2] if ruta["pasos"] else "caminar"
                        minutos = max(1, round(ruta["total_minutos"] * random.uniform(0.75, 1.35)))
                        segundos = min(minutos * 60, 300)

                        npc_viajes_activos[npc_id] = {
                            "canal_destino": canal_destino_nombre,
                            "sector_destino": nuevo,
                            "llegada_ts": time.time() + segundos,
                            "metodo": metodo,
                        }
                        npc["canal_actual"] = canal_origen.name if canal_origen else npc.get("canal_actual")
                        await db.set("npcs", npc_id, npc)

                        if canal_origen:
                            icono = ICONOS_METODO.get(metodo, "🚶")
                            extra_coche = " en su coche" if (metodo == "coche" and _tiene_coche(npc)) else ""
                            try:
                                await canal_origen.send(embed=_embed_accion(
                                    npc,
                                    f"{icono} sale de **{SECTORES.get(sector,{}).get('display',sector)} ({sector})**{extra_coche} "
                                    f"rumbo a **{canal_con_sector(canal_destino_nombre, nuevo)}** (~{minutos} min).",
                                    color=discord.Color.dark_teal()
                                ))
                            except Exception:
                                pass
                        # El NPC ya no actúa aquí este ciclo: está en tránsito.
                        # La actividad nueva se le asignará cuando llegue (el
                        # ciclo siguiente lo verá con ubicación ya actualizada).
                        await db.set("npc_estado", npc_id, {})
                        continue

            # ── Empezar actividad nueva ───────────────────────────────────────
            # Evita elegir la misma actividad que acaba de terminar: si no, la
            # narración de "fin" y la de "inicio" describen básicamente lo mismo
            # y parece que la acción se ha duplicado (p.ej. "cierra un trato" y
            # justo después "vuelve a ofrecer productos en la esquina").
            actividad_anterior = estado.get("actividad")
            opciones = [a for a in ACTIVIDADES[tipo] if a[0] != actividad_anterior]
            if not opciones:
                opciones = ACTIVIDADES[tipo]
            nombre_act, desc, dur_min, dur_max = random.choice(opciones)
            duracion = random.randint(dur_min, dur_max)
            await db.set("npc_estado", npc_id, {
                "actividad": nombre_act,
                "actividad_desc": desc,
                "inicio_ts": ahora,
                "fin_ts": ahora + duracion * 60,
                "sector": sector,
            })

            texto = await _narrar(npc, desc, sector, "inicio")
            canal = await self._canal_de_sector(guild, sector)
            if canal:
                try:
                    await canal.send(embed=_embed_accion(npc, texto))
                except Exception:
                    pass

    # ══════════════════════════════════════════════════════════════════════
    # Interacciones NPC↔NPC: peleas/tiroteos entre bandas rivales, policía
    # arrestando criminales, asesinatos silenciosos, y compra de casas.
    # ══════════════════════════════════════════════════════════════════════
    async def _ping_policia(self, guild: discord.Guild, sector: str, mensaje: str):
        if sector not in SECTORES_VENEZUELA:
            return
        from bot import CH_POLICIA_AVISO, ROL_POLICIA
        ch = guild.get_channel(CH_POLICIA_AVISO)
        if not ch:
            return
        rol = guild.get_role(ROL_POLICIA)
        try:
            await ch.send(f"🚨 {rol.mention if rol else '@CPNB'} {mensaje}")
        except Exception:
            pass

    async def _narrar_evento(self, system_extra: str, prompt: str, fallback: str) -> str:
        if not ia.hay_ia():
            return fallback
        texto, _ = await ia.generar(SYSTEM_NPC + " " + system_extra, prompt, max_tokens=180, timeout_seg=20)
        return texto or fallback

    async def _tiroteo_bandas(self, guild, canal, sector, a, a_id, b, b_id):
        fallback = (f"**{a['nombre']}** ({a.get('banda','?')}) y **{b['nombre']}** ({b.get('banda','?')}) "
                    f"se cruzan en **{SECTORES.get(sector,{}).get('display',sector)}** y estalla un tiroteo entre bandas rivales.")
        texto = await self._narrar_evento(
            "Narra un tiroteo breve y tenso entre dos bandas rivales, sin gore explícito.",
            f"Banda A: {a['nombre']} ({a.get('banda')}). Banda B: {b['nombre']} ({b.get('banda')}). "
            f"Lugar: {SECTORES.get(sector,{}).get('display',sector)}. Narra el inicio del tiroteo en 2-3 frases.",
            fallback
        )
        embed = discord.Embed(title="🔫 Tiroteo entre bandas", description=texto, color=discord.Color.dark_red())
        try:
            await canal.send(embed=embed)
        except Exception:
            pass
        try:
            from cogs.noticias_ia import registrar_evento
            await registrar_evento("tiroteo_bandas",
                f"Tiroteo entre las bandas {a.get('banda','?')} y {b.get('banda','?')} en {SECTORES.get(sector,{}).get('display',sector)}.")
        except Exception:
            pass

        perdedor, perdedor_id, ganador = (a, a_id, b) if (a.get("fuerza", a.get("stats",{}).get("fuerza",5)) + random.random()*4) < \
            (b.get("fuerza", b.get("stats",{}).get("fuerza",5)) + random.random()*4) else (b, b_id, a)
        if random.random() < 0.35:
            perdedor["muerto"] = True
            perdedor["causa_muerte"] = f"tiroteo entre bandas rivales ({perdedor.get('banda','?')} vs {ganador.get('banda','?')})"
            await db.set("npcs", perdedor_id, perdedor)
            try:
                await canal.send(embed=discord.Embed(
                    description=f"💀 **{perdedor['nombre']}** cae abatido en el enfrentamiento.",
                    color=0x2C2F33
                ))
            except Exception:
                pass
        else:
            try:
                await canal.send(embed=discord.Embed(
                    description=f"🩸 **{perdedor['nombre']}** resulta herido pero logra escapar.",
                    color=discord.Color.orange()
                ))
            except Exception:
                pass
        await self._ping_policia(guild, sector, f"**Tiroteo entre bandas** reportado en {canal.mention} ({sector}).")

    async def _confrontacion_policial(self, guild, canal, sector, poli, poli_id, crim, crim_id):
        fuerza_poli = poli.get("fuerza", poli.get("stats",{}).get("fuerza",5)) + random.random()*3
        fuerza_crim = crim.get("fuerza", crim.get("stats",{}).get("fuerza",5)) + random.random()*3

        if fuerza_poli >= fuerza_crim:
            crim["arrestado_npc"] = True
            crim["libera_ts"] = time.time() + HORAS_CONDENA_NPC * 3600
            crim["ubicacion"] = "prision-yare"
            await db.set("npcs", crim_id, crim)
            fallback = f"**{poli['nombre']}** logra arrestar a **{crim['nombre']}** en **{SECTORES.get(sector,{}).get('display',sector)}**."
            texto = await self._narrar_evento(
                "Narra un arresto policial breve.",
                f"Policía: {poli['nombre']}. Sospechoso: {crim['nombre']} ({crim.get('trabajo','?')}). "
                f"Lugar: {sector}. El sospechoso termina arrestado. Narra en 2 frases.",
                fallback
            )
            embed = discord.Embed(title="🚔 Arresto", description=texto, color=discord.Color.blue())
            embed.set_footer(text=f"{crim['nombre']} saldrá en unas horas.")
        else:
            fallback = f"**{crim['nombre']}** se enfrenta a **{poli['nombre']}** y logra escapar tras un forcejeo en **{sector}**."
            texto = await self._narrar_evento(
                "Narra un forcejeo/tiroteo breve donde el sospechoso escapa.",
                f"Policía: {poli['nombre']}. Sospechoso: {crim['nombre']}. Lugar: {sector}. "
                f"El sospechoso escapa, puede haber disparos. Narra en 2-3 frases.",
                fallback
            )
            embed = discord.Embed(title="🚨 Confrontación con la policía", description=texto, color=discord.Color.dark_orange())
            if random.random() < 0.25:
                poli["muerto"] = True
                poli["causa_muerte"] = f"un tiroteo contra {crim['nombre']}"
                await db.set("npcs", poli_id, poli)
                embed.add_field(name="💀 Baja", value=f"**{poli['nombre']}** no sobrevivió al enfrentamiento.", inline=False)
        try:
            await canal.send(embed=embed)
        except Exception:
            pass
        await self._ping_policia(guild, sector, f"**Confrontación policía/criminal** en {canal.mention} ({sector}).")
        try:
            from cogs.noticias_ia import registrar_evento
            resultado = "arrestado" if crim.get("arrestado_npc") else "escapó"
            await registrar_evento("confrontacion_policial",
                f"La policía se enfrentó a {crim['nombre']} en {SECTORES.get(sector,{}).get('display',sector)}; el sospechoso {resultado}.")
        except Exception:
            pass

    async def _asesinato_silencioso(self, canal, sector, atacante, victima_id, victima):
        fallback = f"Encuentran a **{victima['nombre']}** muerto/a en **{SECTORES.get(sector,{}).get('display',sector)}**. No hubo disparos ni testigos."
        texto = await self._narrar_evento(
            "Narra el HALLAZGO de un asesinato sigiloso (sin tiroteo, sin detalles gráficos), no quién lo hizo.",
            f"Víctima: {victima['nombre']} ({victima.get('trabajo','?')}). Lugar: {sector}. "
            f"Fue un asesinato silencioso, sin arma de fuego. Narra el hallazgo en 2 frases, sin revelar al asesino.",
            fallback
        )
        victima["muerto"] = True
        victima["causa_muerte"] = "asesinato (sin tiroteo)"
        await db.set("npcs", victima_id, victima)
        try:
            await canal.send(embed=discord.Embed(title="🔪 Hallazgo macabro", description=texto, color=0x2C2F33))
        except Exception:
            pass
        try:
            from cogs.noticias_ia import registrar_evento
            await registrar_evento("asesinato",
                f"Hallan muerto a {victima['nombre']} ({victima.get('trabajo','?')}) en {SECTORES.get(sector,{}).get('display',sector)}; no hubo tiroteo.")
        except Exception:
            pass

    @tasks.loop(minutes=20)
    async def eventos_npc_npc(self):
        """Interacciones entre NPCs: bandas rivales a tiros, policía arrestando
        criminales, asesinatos silenciosos. Un evento como mucho por sector
        y ciclo, para no saturar los canales."""
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return
        npcs = await db.all("npcs")
        vivos = {nid: n for nid, n in npcs.items() if not n.get("muerto") and not n.get("arrestado_npc")}

        por_sector: dict[str, list] = {}
        for nid, n in vivos.items():
            por_sector.setdefault(n.get("ubicacion", ""), []).append((nid, n))

        for sector, lista in por_sector.items():
            if len(lista) < 2 or not sector:
                continue
            canal = await self._canal_de_sector(guild, sector)
            if not canal:
                continue

            criminales = [(nid, n) for nid, n in lista if n.get("tipo") == "criminal"]
            policias = [(nid, n) for nid, n in lista if n.get("tipo") == "policia"]

            # 1) Bandas rivales
            bandas = {}
            for nid, n in criminales:
                bandas.setdefault(n.get("banda", nid), []).append((nid, n))
            if len(bandas) >= 2 and random.random() < 0.06:
                dos_bandas = random.sample(list(bandas.values()), 2)
                a_id, a = random.choice(dos_bandas[0])
                b_id, b = random.choice(dos_bandas[1])
                await self._tiroteo_bandas(guild, canal, sector, a, a_id, b, b_id)
                continue

            # 2) Policía vs criminal (solo en Venezuela)
            if policias and criminales and sector in SECTORES_VENEZUELA and random.random() < 0.05:
                poli_id, poli = random.choice(policias)
                crim_id, crim = random.choice(criminales)
                await self._confrontacion_policial(guild, canal, sector, poli, poli_id, crim, crim_id)
                continue

            # 3) Asesinato silencioso entre criminales (o hacia un civil)
            objetivos = criminales + [(nid, n) for nid, n in lista if n.get("tipo") == "civil"]
            if len(criminales) >= 1 and len(objetivos) >= 2 and random.random() < 0.015:
                atacante_id, atacante = random.choice(criminales)
                posibles_victimas = [(nid, n) for nid, n in objetivos if nid != atacante_id]
                if posibles_victimas:
                    victima_id, victima = random.choice(posibles_victimas)
                    await self._asesinato_silencioso(canal, sector, atacante, victima_id, victima)
                    continue

    # ══════════════════════════════════════════════════════════════════════
    # NPCs comprando casas: usan su propio dinero, igual que un jugador.
    # ══════════════════════════════════════════════════════════════════════
    @tasks.loop(hours=1)
    async def npcs_compran_casas(self):
        from cogs.propiedades import _inicializar_casas_sector, _resolver_canal_casa, refrescar_embed_casa, PRECIOS_CASA

        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return
        npcs = await db.all("npcs")
        for npc_id, npc in list(npcs.items()):
            if npc.get("muerto") or npc.get("arrestado_npc") or npc.get("protege_a"):
                continue
            if npc.get("casas"):
                continue  # ya tiene casa
            if npc.get("tipo") not in ("civil", "gobierno", "criminal", "policia", "abogado"):
                continue
            if random.random() >= 0.02:
                continue

            sector = npc.get("ubicacion", "")
            if sector not in SECTORES or SECTORES[sector].get("casas_total", 0) <= 0:
                continue

            casas = await _inicializar_casas_sector(sector)
            libres = [(cid, c) for cid, c in casas.items()
                      if not c.get("dueño") and not c.get("inquilino") and not c.get("okupa") and not c.get("padres_de")]
            if not libres:
                continue
            casa_id, casa = random.choice(libres)
            precio = casa.get("precio", PRECIOS_CASA.get(2, 5000))
            if npc.get("dinero", 0) < precio:
                continue

            numero = int(casa_id.replace("casa-", ""))
            canal = _resolver_canal_casa(guild, sector, numero, casa)

            casa["dueño"] = npc_id
            casa["estado"] = "ocupada"
            casa["en_venta"] = False
            casa["puerta"] = "puerta_madera"
            casas[casa_id] = casa
            await db.set("casas", sector, casas)

            npc["dinero"] = round(npc.get("dinero", 0) - precio, 2)
            npc["casas"] = [f"{sector}:{casa_id}"]
            await db.set("npcs", npc_id, npc)

            if canal:
                try:
                    await canal.edit(topic=f"🏠 Casa de {npc['nombre']} (NPC) en {sector}")
                    # Igual que cuando compra un jugador: en cuanto la casa tiene
                    # dueño, deja de ser visible para todo el mundo. Antes, al
                    # comprarla un NPC, el canal se quedaba público (@everyone
                    # seguía viéndolo) porque solo se cambiaba el topic.
                    await canal.set_permissions(guild.default_role, read_messages=False, view_channel=False)
                except Exception:
                    pass
                casa["canal_id"] = canal.id
                casas[casa_id] = casa
                await db.set("casas", sector, casas)
                try:
                    await canal.send(embed=discord.Embed(
                        description=f"🏠 **{npc['nombre']}** compró esta casa por ${precio:,.0f}.",
                        color=discord.Color.green()
                    ))
                except Exception:
                    pass
            await refrescar_embed_casa(guild, sector, casa_id, casa)

            canal_anuncio = await self._canal_de_sector(guild, sector)
            if canal_anuncio:
                try:
                    await canal_anuncio.send(embed=_embed_accion(
                        npc, f"compra **{casa_id}** en **{SECTORES.get(sector,{}).get('display',sector)}** por ${precio:,.0f}.",
                        color=discord.Color.gold()
                    ))
                except Exception:
                    pass

    # ── /npc_actividad ───────────────────────────────────────────────────────
    @app_commands.command(name="npc_actividad", description="Mira qué está haciendo un NPC ahora mismo")
    @app_commands.describe(nombre="Nombre del NPC")
    async def npc_actividad(self, interaction: discord.Interaction, nombre: str):
        npcs = await db.all("npcs")
        encontrado = None
        for npc_id, npc in npcs.items():
            if nombre.lower() in npc.get("nombre", "").lower():
                encontrado = (npc_id, npc)
                break
        if not encontrado:
            return await interaction.response.send_message(f"❌ No encontré ningún NPC llamado `{nombre}`.", ephemeral=True)

        npc_id, npc = encontrado
        if npc.get("muerto"):
            return await interaction.response.send_message(
                f"🕯️ **{npc['nombre']}** falleció. Causa: {npc.get('causa_muerte','desconocida')}.")

        estado = await db.get("npc_estado", npc_id) or {}
        sector = npc.get("ubicacion", "?")
        embed = discord.Embed(title=f"👤 {npc.get('nombre','?')}", color=discord.Color.blurple())
        embed.add_field(name="💼 Ocupación", value=npc.get("trabajo", "?"), inline=True)
        embed.add_field(name="📍 Dónde está", value=SECTORES.get(sector, {}).get("display", sector), inline=True)
        if estado.get("actividad_desc"):
            restante = max(0, (estado.get("fin_ts", 0) - time.time()) / 60)
            embed.add_field(name="🎬 Ahora mismo",
                            value=f"{estado['actividad_desc'].capitalize()}\n"
                                  f"Termina en ~{restante:.0f} min", inline=False)
        else:
            embed.add_field(name="🎬 Ahora mismo", value="Sin actividad asignada todavía.", inline=False)
        embed.set_footer(text=await tiempo_juego.fecha_texto())
        await interaction.response.send_message(embed=embed)

    # ── /npcs_activos ────────────────────────────────────────────────────────
    @app_commands.command(name="npcs_activos", description="Lista qué están haciendo todos los NPCs")
    async def npcs_activos(self, interaction: discord.Interaction):
        await interaction.response.defer()
        npcs = await db.all("npcs")
        vivos = {k: v for k, v in npcs.items() if not v.get("muerto")}
        if not vivos:
            return await interaction.followup.send("No hay NPCs vivos registrados.")

        embed = discord.Embed(title="👥 NPCs activos", color=discord.Color.blurple())
        embed.set_footer(text=await tiempo_juego.fecha_texto())
        lineas = []
        for npc_id, npc in list(vivos.items())[:25]:
            estado = await db.get("npc_estado", npc_id) or {}
            sector = SECTORES.get(npc.get("ubicacion", ""), {}).get("display", npc.get("ubicacion", "?"))
            act = estado.get("actividad_desc", "sin actividad")
            lineas.append(f"**{npc.get('nombre','?')}** — {act} · 📍{sector}")
        embed.description = "\n".join(lineas)
        muertos = len(npcs) - len(vivos)
        if muertos:
            embed.add_field(name="🕯️ Fallecidos", value=str(muertos), inline=True)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(NPCVida(bot))
