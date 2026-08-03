"""
cogs/noticias_ia.py — Noticiero del RP generado con IA.

Publica noticias en los canales de noticias asignados, ancladas al calendario
del rol (utils/tiempo_juego.py, que arranca el 4 de enero de 2022 y avanza).

Las noticias mezclan:
  • Lo que REALMENTE está pasando en el servidor (tiroteos, disturbios, casas
    compradas, empresas fundadas, muertes de NPCs, elecciones...).
  • Contexto histórico real de esa fecha de 2022, pero solo como telón de fondo
    y en términos factuales y generales.

NOTA SOBRE PERSONAS REALES: el noticiero NO pone declaraciones inventadas en
boca de políticos reales ni fabrica escándalos sobre personas que existen. Los
titulares nacionales que involucran política usan los cargos y candidatos
FICTICIOS del servidor (ver cogs/elecciones.py). Los sucesos históricos reales
se mencionan como hechos, sin citas inventadas.
"""
import random
import time

import discord
from discord.ext import commands, tasks
from discord import app_commands

from utils import db
from utils import ia
from utils import tiempo_juego
from utils.mapa import SECTORES

MAX_EVENTOS_LOG = 60
VENTANA_EVENTOS_HORAS = 14  # solo se cuentan como "noticia fresca" los hechos de las últimas N horas


async def registrar_evento(tipo: str, texto: str):
    """Cualquier cog puede llamar a esto para anotar algo que acaba de pasar
    de verdad (tiroteo, arresto, incendio, extorsión, veredicto...). El
    noticiero usa ESTOS hechos recientes en vez de una foto fija del estado
    del servidor, que es lo que hacía que las noticias sonaran repetidas
    ciclo tras ciclo aunque no hubiera pasado nada nuevo."""
    try:
        log = await db.get("estado", "eventos_noticiables") or []
        log.append({"ts": time.time(), "tipo": tipo, "texto": texto})
        log = log[-MAX_EVENTOS_LOG:]
        await db.set("estado", "eventos_noticiables", log)
    except Exception:
        pass


async def _eventos_recientes(horas: float = VENTANA_EVENTOS_HORAS) -> list[str]:
    log = await db.get("estado", "eventos_noticiables") or []
    limite = time.time() - horas * 3600
    return [e["texto"] for e in log if e.get("ts", 0) >= limite]

CH_NOTICIAS_VZ1 = 1382156099473379458
CH_NOTICIAS_VZ2 = 1382156210576425040
CH_NOTICIAS_INT = 1382156276016087110

MEDIOS_NACIONALES = ["El Nacional RP", "Últimas Noticias RP", "Radio Caracas RP", "VenePrensa"]
MEDIOS_INTERNACIONALES = ["Agencia Global RP", "Corresponsalía Internacional RP"]

# Contexto histórico REAL y factual de 2022, por mes. Se usa como telón de fondo
# para que las noticias internacionales encajen con la época del rol.
CONTEXTO_2022 = {
    1: "Enero 2022: ómicron dispara los contagios de COVID-19 en el mundo; erupción del volcán submarino de Tonga; tensión creciente en la frontera entre Rusia y Ucrania.",
    2: "Febrero 2022: comienza la invasión rusa de Ucrania (24 de febrero); Juegos Olímpicos de Invierno de Pekín; sanciones económicas masivas a Rusia.",
    3: "Marzo 2022: la guerra en Ucrania provoca una crisis energética y alimentaria global; el precio del petróleo se dispara por encima de los 100 dólares.",
    4: "Abril 2022: inflación récord en Europa y Estados Unidos; continúan los combates en el este de Ucrania; elecciones presidenciales en Francia.",
    5: "Mayo 2022: crisis mundial de alimentos por el bloqueo de los puertos ucranianos; brote de viruela del mono en varios países.",
    6: "Junio 2022: los bancos centrales suben tipos de interés de forma agresiva contra la inflación; crisis energética en Europa.",
    7: "Julio 2022: ola de calor extremo e incendios en Europa; dimite Boris Johnson como primer ministro británico; inflación en máximos de décadas.",
    8: "Agosto 2022: sequía histórica en Europa y China; tensión en Taiwán tras visitas diplomáticas; los precios del gas siguen disparados.",
    9: "Septiembre 2022: fallece la reina Isabel II; sabotaje de los gasoductos Nord Stream; protestas masivas en Irán.",
    10: "Octubre 2022: crisis política en Reino Unido; contraofensiva ucraniana; los mercados globales siguen volátiles.",
    11: "Noviembre 2022: cumbre climática COP27 en Egipto; Mundial de Fútbol de Catar; caída de la plataforma de criptomonedas FTX.",
    12: "Diciembre 2022: Argentina gana el Mundial de Catar; olas de frío extremo en Norteamérica; el mundo cierra un año marcado por la inflación.",
}

SYSTEM_NOTICIAS = (
    "Eres el redactor de un noticiero ficticio para un servidor de roleplay de Discord "
    "ambientado en una Venezuela FICTICIA del año 2022. Escribes SIEMPRE en español.\n\n"
    "FORMATO: devuelve entre 2 y 3 noticias. Cada una en este formato exacto, sin numerar:\n"
    "TITULAR: <titular en mayúscula inicial, máximo 12 palabras>\n"
    "CUERPO: <2 o 3 frases de desarrollo>\n"
    "---\n\n"
    "REGLAS ESTRICTAS:\n"
    "- Las noticias LOCALES deben basarse en los HECHOS DEL SERVIDOR que se te dan. "
    "No inventes sucesos locales que no aparezcan ahí.\n"
    "- Para política nacional usa SOLO los cargos y nombres ficticios del servidor "
    "que aparezcan en el contexto. NUNCA menciones ni cites a políticos reales.\n"
    "- Para noticias internacionales, apóyate en el contexto histórico factual dado, "
    "sin inventar declaraciones ni atribuir frases a personas reales.\n"
    "- Tono periodístico sobrio. Nada de violencia gráfica ni contenido sexual.\n"
    "- No uses emojis."
)


async def _hechos_del_servidor(guild: discord.Guild) -> str:
    """Reúne lo que ha pasado de verdad en el servidor para alimentar las noticias.

    ANTES esto era solo una "foto fija" del estado (cuántas casas ocupadas,
    cuántas empresas hay...) y esos datos casi nunca cambian de un ciclo a
    otro, así que la IA acababa escribiendo prácticamente la misma noticia
    una y otra vez. Ahora se prioriza el LOG de hechos recientes (tiroteos,
    arrestos, incendios, extorsiones, veredictos...) que van registrando los
    demás cogs con registrar_evento(), y el estado general queda como
    contexto secundario."""
    hechos = []

    recientes = await _eventos_recientes()
    if recientes:
        hechos.append("HECHOS RECIENTES (úsalos con prioridad, son lo más nuevo):")
        hechos.extend(recientes[-10:])

    # Disturbios activos
    import time as _t
    disturbios = await db.all("disturbios")
    activos = [s for s, d in disturbios.items() if d.get("activo") and _t.time() < d.get("expira_ts", 0)]
    if activos:
        hechos.append(f"Hay disturbios activos en: {', '.join(activos)}.")

    # Personajes fallecidos recientemente
    personajes = await db.all("personajes")
    muertos = [p.get("nombre", "?") for p in personajes.values() if p.get("muerto")]
    if muertos:
        hechos.append(f"Personas fallecidas recientemente en la ciudad: {', '.join(muertos[:4])}.")

    # NPCs fallecidos
    npcs = await db.all("npcs")
    npcs_muertos = [(n.get("nombre", "?"), n.get("trabajo", "?"), n.get("causa_muerte", "?"))
                    for n in npcs.values() if n.get("muerto")]
    if npcs_muertos:
        detalle = "; ".join(f"{n} ({t}) por {c}" for n, t, c in npcs_muertos[:3])
        hechos.append(f"Fallecimientos notables: {detalle}.")

    # Empresas
    empresas = await db.all("empresas")
    if empresas:
        nombres = [f"{e.get('nombre','?')} ({e.get('tipo','?')}, en {e.get('sector','?')})"
                   for e in list(empresas.values())[:3]]
        hechos.append(f"Empresas operando en el país: {', '.join(nombres)}.")

    # Economía / tesoro
    tesoro = await db.get("estado", "tesoro_nacional")
    if tesoro and tesoro.get("total"):
        hechos.append(f"La recaudación acumulada del Estado asciende a ${tesoro['total']:,.0f}.")

    # Casas y mercado inmobiliario
    total_casas = ocupadas = 0
    for sector_key in SECTORES:
        casas = await db.get("casas", sector_key)
        if not casas:
            continue
        total_casas += len(casas)
        ocupadas += sum(1 for c in casas.values() if c.get("dueño") or c.get("inquilino"))
    if total_casas:
        hechos.append(f"Mercado inmobiliario: {ocupadas} de {total_casas} viviendas registradas están ocupadas.")

    # Política ficticia del servidor
    gobierno = await db.get("estado", "gobierno_actual")
    if gobierno:
        hechos.append(
            f"Gobierno actual (ficticio): presidente {gobierno.get('presidente','?')} "
            f"del partido {gobierno.get('partido','?')}, en el cargo desde la semana "
            f"{gobierno.get('desde_semana','?')} del rol."
        )

    return "\n".join(f"- {h}" for h in hechos) if hechos else "- Sin sucesos destacados registrados esta jornada."


def _parsear_noticias(texto: str) -> list[tuple[str, str]]:
    noticias = []
    for bloque in texto.split("---"):
        titular = cuerpo = None
        for linea in bloque.strip().splitlines():
            l = linea.strip()
            if l.upper().startswith("TITULAR:"):
                titular = l.split(":", 1)[1].strip()
            elif l.upper().startswith("CUERPO:"):
                cuerpo = l.split(":", 1)[1].strip()
            elif cuerpo is not None and l:
                cuerpo += " " + l
        if titular:
            noticias.append((titular, cuerpo or ""))
    return noticias


class NoticiasIA(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def start_tasks(self):
        if not self.ciclo_noticias.is_running():
            self.ciclo_noticias.start()

    @tasks.loop(hours=3)
    async def ciclo_noticias(self):
        await self._publicar(self.bot.guilds[0] if self.bot.guilds else None)

    async def _publicar(self, guild: discord.Guild, forzar_ambito: str = None) -> str:
        if not guild:
            return "sin servidor"
        if not ia.hay_ia():
            return "sin IA configurada"

        fecha = await tiempo_juego.fecha_actual()
        fecha_txt = tiempo_juego.formatear(fecha)
        ambito = forzar_ambito or random.choice(["nacional", "nacional", "internacional"])

        # Titulares recientes (de cualquier ámbito) para pedirle a la IA que
        # NO los repita — esto es lo que más ayuda contra "las noticias son
        # siempre las mismas".
        titulares_previos = await db.get("estado", "titulares_recientes") or []
        titulares_txt = "; ".join(t["titular"] for t in titulares_previos[-12:]) or "(ninguno todavía)"

        if ambito == "internacional":
            contexto_hist = CONTEXTO_2022.get(fecha.month, "")
            # Partimos el contexto del mes en fragmentos y elegimos un ángulo
            # distinto cada vez, para no repetir siempre el mismo resumen.
            fragmentos = [f.strip() for f in contexto_hist.split(";") if f.strip()]
            fragmento_elegido = random.choice(fragmentos) if fragmentos else contexto_hist
            angulo = random.choice(["economía y mercados", "conflicto y geopolítica", "sociedad y cultura",
                                     "ciencia, clima o salud pública", "diplomacia internacional"])
            prompt = (
                f"Fecha en el rol: {fecha_txt}.\n"
                f"CONTEXTO HISTÓRICO REAL DE LA ÉPOCA (factual, úsalo como telón de fondo):\n{contexto_hist}\n\n"
                f"Enfócate esta vez en este fragmento concreto: \"{fragmento_elegido}\"\n"
                f"Ángulo pedido para esta edición: {angulo}.\n"
                f"TITULARES YA PUBLICADOS RECIENTEMENTE (no los repitas ni escribas algo casi igual): {titulares_txt}\n\n"
                f"Escribe 2 noticias INTERNACIONALES coherentes con esa fecha, ese fragmento y ese ángulo. "
                f"No inventes declaraciones de personas reales; limítate a hechos generales."
            )
            canales = [CH_NOTICIAS_INT]
            medio = random.choice(MEDIOS_INTERNACIONALES)
            color = discord.Color.dark_blue()
        else:
            hechos = await _hechos_del_servidor(guild)
            contexto_hist = CONTEXTO_2022.get(fecha.month, "")
            prompt = (
                f"Fecha en el rol: {fecha_txt}.\n\n"
                f"HECHOS REALES OCURRIDOS EN EL SERVIDOR (básate en esto, priorizando los HECHOS RECIENTES "
                f"si los hay — son lo más nuevo; si no hay hechos recientes, usa el resto como contexto "
                f"y escribe algo de color/análisis en vez de repetir la misma foto fija):\n{hechos}\n\n"
                f"CONTEXTO ECONÓMICO GLOBAL DE LA ÉPOCA (solo como telón de fondo):\n{contexto_hist}\n\n"
                f"TITULARES YA PUBLICADOS RECIENTEMENTE (no los repitas ni escribas algo casi igual): {titulares_txt}\n\n"
                f"Escribe 3 noticias NACIONALES de esta Venezuela ficticia basadas en los hechos del servidor. "
                f"Usa únicamente cargos y nombres ficticios; no menciones políticos reales."
            )
            canales = [random.choice([CH_NOTICIAS_VZ1, CH_NOTICIAS_VZ2])]
            medio = random.choice(MEDIOS_NACIONALES)
            color = discord.Color.dark_gold()

        texto, info = await ia.generar(SYSTEM_NOTICIAS, prompt, max_tokens=700, timeout_seg=30)
        if not texto:
            return f"error de IA: {info}"

        noticias = _parsear_noticias(texto)
        if not noticias:
            noticias = [("Boletín informativo", texto[:900])]

        enviadas = 0
        for ch_id in canales:
            canal = guild.get_channel(ch_id)
            if not canal:
                continue
            for titular, cuerpo in noticias[:3]:
                embed = discord.Embed(
                    title=f"📰 {titular[:250]}",
                    description=cuerpo[:1500],
                    color=color
                )
                embed.set_author(name=medio)
                embed.set_footer(text=f"{fecha_txt} · {'Internacional' if ambito=='internacional' else 'Nacional'}")
                try:
                    await canal.send(embed=embed)
                    enviadas += 1
                    titulares_previos.append({"titular": titular, "ts": time.time()})
                except Exception as e:
                    print(f"[WARN] noticia: {e}")

        # Guardar solo los titulares de las últimas ~48h para no acumular basura.
        limite = time.time() - 48 * 3600
        titulares_previos = [t for t in titulares_previos if t.get("ts", 0) >= limite][-30:]
        await db.set("estado", "titulares_recientes", titulares_previos)

        await db.set("estado", "ultima_noticia", {"fecha_rp": fecha_txt, "ambito": ambito, "n": enviadas})
        return f"{enviadas} noticias publicadas ({ambito}) vía {info}"

    # ── /noticias_ahora ──────────────────────────────────────────────────────
    @app_commands.command(name="noticias_ahora", description="[ADMIN] Genera y publica un boletín de noticias ya")
    @app_commands.describe(ambito="Tipo de noticias a generar")
    @app_commands.choices(ambito=[
        app_commands.Choice(name="Nacional", value="nacional"),
        app_commands.Choice(name="Internacional", value="internacional"),
    ])
    async def noticias_ahora(self, interaction: discord.Interaction, ambito: str = None):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ Solo admins.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        resultado = await self._publicar(interaction.guild, forzar_ambito=ambito)
        await interaction.followup.send(f"📰 {resultado}", ephemeral=True)

    # ── /fecha_rp ────────────────────────────────────────────────────────────
    @app_commands.command(name="fecha_rp", description="Muestra la fecha actual dentro del roleplay")
    async def fecha_rp(self, interaction: discord.Interaction):
        fecha = await tiempo_juego.fecha_actual()
        dias = await tiempo_juego.dias_transcurridos()
        semanas = await tiempo_juego.semanas_transcurridas()
        embed = discord.Embed(
            title="📅 Fecha en el roleplay",
            description=f"**{tiempo_juego.formatear(fecha)}**",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Días transcurridos", value=str(dias), inline=True)
        embed.add_field(name="Semanas", value=str(semanas), inline=True)
        embed.add_field(name="Ritmo", value=f"1 día del rol = {tiempo_juego.HORAS_REALES_POR_DIA_JUEGO}h reales", inline=True)
        embed.set_footer(text="El rol comenzó el 4 de enero de 2022")
        await interaction.response.send_message(embed=embed)

    # ── /adelantar_tiempo ────────────────────────────────────────────────────
    @app_commands.command(name="adelantar_tiempo", description="[ADMIN] Adelanta el reloj del rol")
    @app_commands.describe(dias="Días del rol a adelantar (puede ser negativo)")
    async def adelantar_tiempo(self, interaction: discord.Interaction, dias: float):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ Solo admins.", ephemeral=True)
        await tiempo_juego.adelantar_dias(dias)
        await interaction.response.send_message(
            f"⏩ Reloj del rol movido {dias:+.1f} días. Ahora es **{await tiempo_juego.fecha_texto()}**.",
            ephemeral=True)


async def setup(bot):
    await bot.add_cog(NoticiasIA(bot))
