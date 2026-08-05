"""
cogs/combate.py — Sistema de combate.
FIXED: !curar (curar a otro), !curarse (curarse a sí mismo), ambos requieren objetos.
!armas_tienda ELIMINADO — usar mercado negro o tienda.
"""
import discord
from discord.ext import commands
import random
import asyncio
from utils import db
from utils import lesiones as lesiones_mod
from utils import muerte as muerte_mod
from utils.armas import (TODAS_LAS_ARMAS, EQUIPO_DEFENSIVO, get_daño,
                          calcular_defensa_total, es_arma_de_fuego, es_arma_ilegal,
                          es_arma_cortante)

CH_POLICIA_AVISO = 1359320808526450780
ROL_POLICIA      = 1359320808526450780
CH_MUERTOS       = 1359320811420520613

# Curso que hay que tener completado para pelear con más soltura (patadas
# efectivas, mejores bloqueos y esquivas). Se otorga al terminar
# "autodefensa" en /estudiar (ver cogs/educacion.py).
CURSO_ARTE_MARCIAL = "autodefensa"

# Probabilidad BASE de que llegue la policía cuando hay una pelea. Sube si
# hay arma de por medio (más aún si es de fuego) o si alguien resulta
# apuñalado.
PROB_POLICIA_PELEA_BASE = 0.30
PROB_POLICIA_PELEA_ARMA = 0.45
PROB_POLICIA_PELEA_APUÑALADO = 0.60

# ── MOVIMIENTOS DE COMBATE CUERPO A CUERPO ───────────────────────────────────
MOVIMIENTOS = {
    "golpear":  {"emoji": "🥊", "label": "Golpear",  "style": discord.ButtonStyle.danger},
    "patada":   {"emoji": "🦵", "label": "Patada",   "style": discord.ButtonStyle.danger},
    "bloquear": {"emoji": "🛡️", "label": "Bloquear", "style": discord.ButtonStyle.primary},
    "esquivar": {"emoji": "💨", "label": "Esquivar", "style": discord.ButtonStyle.success},
}


def _tiene_arte_marcial(datos: dict) -> bool:
    """True si el personaje completó el curso de autodefensa: sabe pelear
    con más técnica (patadas de verdad, mejores bloqueos/esquivas)."""
    return CURSO_ARTE_MARCIAL in (datos.get("certificados") or [])

# ── ÍTEMS DE CURACIÓN Y SUS EFECTOS ──────────────────────────────────────────
ITEMS_CURACION = {
    "vendaje":           {"hp": 20,  "msg": "🩹 Aplicaste un vendaje."},
    "kit_medico":        {"hp": 50,  "msg": "🏥 Usaste el kit médico."},
    "suero_oral":        {"hp": 10,  "msg": "💧 Administraste suero oral."},
    "antibioticos":      {"hp": 15,  "msg": "💊 Tomaste antibióticos."},
    "morfina":           {"hp": 35,  "msg": "💉 Morfina administrada."},
    "sangre_tipo_o":     {"hp": 60,  "msg": "🩸 Transfusión realizada."},
    "torniquete":        {"hp": 25,  "msg": "🩹 Torniquete aplicado. Hemorragia controlada."},
    "agua_oxigenada":    {"hp": 8,   "msg": "🫧 Herida desinfectada con agua oxigenada."},
    "gasa_esteril":      {"hp": 12,  "msg": "🩺 Gasa estéril aplicada sobre la herida."},
    "botiquin_hogar":    {"hp": 30,  "msg": "🏥 Usaste el botiquín del hogar."},
    "jeringa":           {"hp": 5,   "msg": "💉 Inyección básica aplicada."},
}

CANALES_HOSPITAL = ["hospital", "clinica", "emergencia", "ambulatorio", "medic"]


async def _notificar_policia(guild, canal, mensaje):
    ch_pol = guild.get_channel(CH_POLICIA_AVISO)
    if ch_pol:
        rol_pol = guild.get_role(ROL_POLICIA)
        ping = rol_pol.mention if rol_pol else "@CPNB"
        await ch_pol.send(f"🚨 {ping} **INCIDENTE:** {mensaje}\n📍 {canal.mention if canal else '?'}")


def _calcular_daño_combate(atacante: dict, defensor: dict, arma: str = None,
                            movimiento: str = "golpear", entrenado: bool = False) -> tuple:
    """Devuelve (daño_final, texto_extra, apuñalado: bool)."""
    stats_a = atacante.get("stats", {})
    stats_d = defensor.get("stats", {})
    fuerza = stats_a.get("fuerza", 5)
    tecnica = stats_a.get("tecnica", 3)
    agilidad_d = stats_d.get("agilidad", 5)

    daño_arma = get_daño(arma) if arma else 0
    base = fuerza * 2 + tecnica + daño_arma
    reduccion_agilidad = agilidad_d * 0.5
    inv_d = defensor.get("inventario", {})
    defensa_equipo = calcular_defensa_total(list(inv_d.keys()))
    daño_final = max(1, int((base - reduccion_agilidad) * (1 - defensa_equipo / 100) + random.randint(-3, 5)))

    # La patada pega más fuerte si sabes pelear (autodefensa); si la intentas
    # sin haber entrenado, sale peor que un golpe normal.
    if movimiento == "patada":
        daño_final = int(daño_final * (1.35 if entrenado else 0.75))

    texto_extra = ""
    apuñalado = False
    if random.random() < 0.10:
        daño_final = int(daño_final * 1.6)
        texto_extra = " ⚡**¡CRÍTICO!**"

    # Cuchillo/navaja/machete: alta probabilidad de clavar una puñalada extra.
    if arma and es_arma_cortante(arma) and random.random() < 0.55:
        apuñalado = True
        daño_final = int(daño_final * 1.4)
        texto_extra += " 🔪**¡APUÑALADO!**"

    return max(1, daño_final), texto_extra, apuñalado


def _primera_arma(inventario: dict) -> str:
    for item in inventario:
        if item in TODAS_LAS_ARMAS:
            return item
    return None


def _primer_item_curacion(inventario: dict) -> tuple[str, dict] | tuple[None, None]:
    """Retorna el primer ítem de curación disponible en el inventario."""
    for item, cantidad in inventario.items():
        if item in ITEMS_CURACION and cantidad > 0:
            return item, ITEMS_CURACION[item]
    return None, None


class HuirView(discord.ui.View):
    def __init__(self, user_id, atacante_id):
        super().__init__(timeout=15)
        self.user_id = user_id
        self.atacante_id = atacante_id
        self.huyo = False

    @discord.ui.button(label="🏃 ¡HUIR!", style=discord.ButtonStyle.green)
    async def huir(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("No es tu combate.", ephemeral=True)
        self.huyo = True
        await interaction.response.send_message("🏃 Intentas huir...", ephemeral=False)
        self.stop()

    @discord.ui.button(label="⚔️ Seguir peleando", style=discord.ButtonStyle.red)
    async def continuar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("No es tu combate.", ephemeral=True)
        self.huyo = False
        await interaction.response.send_message("⚔️ Sigues en el combate.", ephemeral=False)
        self.stop()


class MovimientoView(discord.ui.View):
    """Cada ronda de una pelea cuerpo a cuerpo: los DOS combatientes eligen en
    secreto su movimiento (golpear, patada, bloquear o esquivar) con botones.
    En cuanto ambos han elegido (o se acaba el tiempo), la vista se resuelve
    y el que faltó por elegir asume 'golpear' por defecto."""

    def __init__(self, atacante_id: int, defensor_id: int, timeout: float = 20.0):
        super().__init__(timeout=timeout)
        self.atacante_id = atacante_id
        self.defensor_id = defensor_id
        self.elecciones: dict[int, str] = {}
        self._evento = asyncio.Event()
        for clave, info in MOVIMIENTOS.items():
            self.add_item(self._crear_boton(clave, info))

    def _crear_boton(self, clave: str, info: dict):
        boton = discord.ui.Button(label=info["label"], emoji=info["emoji"], style=info["style"])

        async def callback(interaction: discord.Interaction, clave=clave):
            if interaction.user.id not in (self.atacante_id, self.defensor_id):
                return await interaction.response.send_message("No es tu combate.", ephemeral=True)
            if interaction.user.id in self.elecciones:
                return await interaction.response.send_message("Ya elegiste tu movimiento este asalto.", ephemeral=True)
            self.elecciones[interaction.user.id] = clave
            await interaction.response.send_message(
                f"{info['emoji']} Eliges **{info['label']}**.", ephemeral=True)
            if len(self.elecciones) >= 2:
                self._evento.set()
                self.stop()

        boton.callback = callback
        return boton

    async def esperar_elecciones(self):
        try:
            await asyncio.wait_for(self._evento.wait(), timeout=self.timeout)
        except asyncio.TimeoutError:
            pass
        self.elecciones.setdefault(self.atacante_id, "golpear")
        self.elecciones.setdefault(self.defensor_id, "golpear")
        return self.elecciones[self.atacante_id], self.elecciones[self.defensor_id]


class AceptarPeleaView(discord.ui.View):
    def __init__(self, atacante_id, defensor_id, datos_a, datos_d, cog):
        super().__init__(timeout=60)
        self.atacante_id = atacante_id
        self.defensor_id = defensor_id
        self.datos_a = datos_a
        self.datos_d = datos_d
        self.cog = cog

    @discord.ui.button(label="✅ Aceptar pelea", style=discord.ButtonStyle.green)
    async def aceptar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.defensor_id:
            return await interaction.response.send_message("No es tu desafío.", ephemeral=True)
        key = tuple(sorted([self.atacante_id, self.defensor_id]))
        self.cog.peleas_activas[key] = True
        await self._resolver_pelea(interaction)
        self.cog.peleas_activas.pop(key, None)
        self.stop()

    @discord.ui.button(label="❌ Rechazar", style=discord.ButtonStyle.red)
    async def rechazar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.defensor_id:
            return await interaction.response.send_message("No es tu desafío.", ephemeral=True)
        await interaction.response.send_message("❌ Pelea rechazada.")
        self.stop()

    async def _resolver_pelea(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.cog.resolver_pelea_interactiva(
            interaction.channel, interaction.guild,
            self.atacante_id, self.defensor_id, self.datos_a, self.datos_d,
            enviar=interaction.followup.send,
        )


class Combate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.peleas_activas = {}

    async def _manejar_muerte(self, user_id: int, datos: dict, guild, causa: str = ""):
        await muerte_mod.procesar_muerte(self.bot, user_id, datos, causa=causa, guild=guild)

    async def _procesar_caida(self, user_id: int, datos: dict, guild, es_tiroteo: bool) -> int:
        """Se llama cuando alguien llega a 0 HP. Ya no es muerte automática:
        se tira una probabilidad de muerte inmediata; si sobrevive, queda
        gravemente herido (lesión seria) y en HP crítico en vez de morir.
        Devuelve el HP final (0 si murió, un número pequeño si sobrevivió)."""
        nombre = datos.get("nombre", "?")

        if es_tiroteo:
            prob_muerte = 0.35
            pesos_lesion = [("herida_bala", 45), ("hemorragia", 35), ("herida_critica", 20)]
        else:
            prob_muerte = 0.08
            pesos_lesion = [("contusion", 40), ("hueso_roto", 45), ("hemorragia", 10), ("herida_critica", 5)]

        if random.random() < prob_muerte:
            await self._manejar_muerte(user_id, datos, guild)
            return 0

        tipos = [t for t, _ in pesos_lesion]
        pesos = [p for _, p in pesos_lesion]
        tipo_lesion = random.choices(tipos, weights=pesos, k=1)[0]
        await lesiones_mod.agregar_lesion(user_id, tipo_lesion)
        info = lesiones_mod.LESIONES_TIPOS[tipo_lesion]

        hp_critico = random.randint(1, 8)
        if guild:
            member = guild.get_member(user_id)
            aviso = (
                f"🚑 **{nombre}** queda gravemente herido/a — **{info['display']}**. "
                f"Necesita ir a un hospital (`!ir_hospital`) o sanará solo/a en "
                f"~{info['duracion_horas']}h (con riesgo de morir si no se atiende)."
            )
            if member:
                try:
                    await member.send(aviso)
                except Exception:
                    pass
        return hp_critico

    async def resolver_pelea_interactiva(self, canal, guild, atacante_id: int, defensor_id: int,
                                          datos_a: dict, datos_d: dict, enviar=None,
                                          intro: str = None) -> discord.Embed:
        """Pelea cuerpo a cuerpo ronda a ronda: en cada asalto AMBOS combatientes
        eligen su movimiento (golpear/patada/bloquear/esquivar) con botones.
        Quien tiene el curso de autodefensa pelea con más técnica: patadas más
        fuertes y mejores bloqueos/esquivas. Si alguno lleva cuchillo/navaja/
        machete, hay alta probabilidad de que conecte una puñalada extra.
        `enviar` es la función para mandar el mensaje final (interaction.followup.send
        o ctx.send); si no se da, se usa canal.send."""
        enviar = enviar or canal.send
        nombre_a = datos_a.get("nombre", "?")
        nombre_d = datos_d.get("nombre", "?")
        hp_a = datos_a.get("stats", {}).get("hp", 100)
        hp_d = datos_d.get("stats", {}).get("hp", 100)
        arma_a = _primera_arma(datos_a.get("inventario", {}))
        arma_d = _primera_arma(datos_d.get("inventario", {}))
        entrenado_a = _tiene_arte_marcial(datos_a)
        entrenado_d = _tiene_arte_marcial(datos_d)

        stats_a_ef = await lesiones_mod.stats_con_penalizacion(atacante_id, datos_a.get("stats", {}))
        stats_d_ef = await lesiones_mod.stats_con_penalizacion(defensor_id, datos_d.get("stats", {}))
        datos_a_combate = {**datos_a, "stats": stats_a_ef}
        datos_d_combate = {**datos_d, "stats": stats_d_ef}

        log = []
        hubo_apuñalada = False
        hubo_arma = bool(arma_a or arma_d)
        ronda = 1

        if intro:
            try:
                await canal.send(intro)
            except Exception:
                pass

        while hp_a > 0 and hp_d > 0 and ronda <= 6:
            vista = MovimientoView(atacante_id, defensor_id)
            mov_msg = await canal.send(
                f"**Ronda {ronda}** — {nombre_a} vs {nombre_d}: elijan su movimiento "
                f"(20s, si no eligen se asume Golpear).", view=vista)
            mov_a, mov_d = await vista.esperar_elecciones()
            try:
                await mov_msg.delete()
            except Exception:
                pass

            def _resolver_uno(atk_datos, def_datos, atk_mov, def_mov, arma_atk, entrenado_atk, nombre_atk, nombre_def):
                if atk_mov not in ("golpear", "patada"):
                    return None  # no ataca este asalto (bloquea/esquiva sin iniciativa)
                daño, extra, apuñalado = _calcular_daño_combate(
                    atk_datos, def_datos, arma_atk, movimiento=atk_mov, entrenado=entrenado_atk)
                # El defensor reacciona:
                if def_mov == "bloquear":
                    # Bloquear frena bien un golpe, pero una patada lo atraviesa más.
                    reduccion = 0.35 if atk_mov == "patada" else (0.65 if _tiene_arte_marcial(def_datos) else 0.5)
                    daño = max(1, int(daño * (1 - reduccion)))
                    extra += " 🛡️(bloqueado en parte)"
                elif def_mov == "esquivar":
                    prob_esquiva = min(0.65, def_datos.get("stats", {}).get("agilidad", 5) / 18
                                        + (0.12 if _tiene_arte_marcial(def_datos) else 0))
                    if atk_mov == "patada":
                        prob_esquiva *= 0.7
                    if random.random() < prob_esquiva:
                        return (0, " 💨¡ESQUIVADO!", False, nombre_atk, nombre_def, atk_mov)
                return (daño, extra, apuñalado, nombre_atk, nombre_def, atk_mov)

            resultados = []
            r1 = _resolver_uno(datos_a_combate, datos_d_combate, mov_a, mov_d, arma_a, entrenado_a, nombre_a, nombre_d)
            if r1:
                resultados.append(r1)
            r2 = _resolver_uno(datos_d_combate, datos_a_combate, mov_d, mov_a, arma_d, entrenado_d, nombre_d, nombre_a)
            if r2:
                resultados.append(r2)

            if not resultados:
                log.append(f"R{ronda}: ambos se estudian sin atacar (🛡️/💨).")

            for daño, extra, apuñalado, nombre_atk, nombre_def, mov in resultados:
                emoji_mov = MOVIMIENTOS[mov]["emoji"]
                if nombre_atk == nombre_a:
                    hp_d = max(0, hp_d - daño)
                else:
                    hp_a = max(0, hp_a - daño)
                if apuñalado:
                    hubo_apuñalada = True
                log.append(f"R{ronda}: {emoji_mov} {nombre_atk} → -{daño}HP a {nombre_def}{extra}")

            ronda += 1

        if hp_a <= 0 and hp_d <= 0:
            resultado = "💀 ¡Ambos cayeron! Empate."
        elif hp_a <= 0:
            resultado = f"🏆 **{nombre_d}** ganó!"
        elif hp_d <= 0:
            resultado = f"🏆 **{nombre_a}** ganó!"
        else:
            resultado = f"🏆 **{nombre_a if hp_a > hp_d else nombre_d}** gana por puntos."

        if hp_a <= 0:
            hp_a = await self._procesar_caida(atacante_id, datos_a, guild, es_tiroteo=False)
        if hp_d <= 0:
            hp_d = await self._procesar_caida(defensor_id, datos_d, guild, es_tiroteo=False)

        embed = discord.Embed(title="⚔️ RESULTADO DE LA PELEA", color=0xE74C3C)
        embed.description = "\n".join(log[-10:])
        embed.add_field(name="HP Final", value=f"{nombre_a}: {hp_a} | {nombre_d}: {hp_d}", inline=False)
        embed.add_field(name="🏆 Resultado", value=resultado, inline=False)

        s_a = datos_a.get("stats", {}); s_a["hp"] = hp_a
        s_d = datos_d.get("stats", {}); s_d["hp"] = hp_d
        await db.update("personajes", str(atacante_id), {"stats": s_a})
        await db.update("personajes", str(defensor_id), {"stats": s_d})

        # Cuanto más grave la pelea, más probable que llegue la policía.
        prob_policia = PROB_POLICIA_PELEA_BASE
        if hubo_arma:
            prob_policia = PROB_POLICIA_PELEA_ARMA
        if hubo_apuñalada:
            prob_policia = PROB_POLICIA_PELEA_APUÑALADO
        llega_policia = random.random() < prob_policia
        if llega_policia:
            embed.add_field(name="🚔 POLICÍA", value="¡La CPNB llegó al lugar!", inline=False)

        await enviar(embed=embed)
        if llega_policia:
            await _notificar_policia(guild, canal, f"Pelea entre {nombre_a} y {nombre_d}.")
        return embed

    @commands.command(name="pelear")
    async def pelear(self, ctx, oponente: discord.Member):
        """Inicia una pelea. Ambos deben estar en el mismo canal."""
        if oponente.id == ctx.author.id:
            return await ctx.send("❌ No puedes pelearte contigo mismo.")
        datos_a = await db.get("personajes", str(ctx.author.id))
        datos_d = await db.get("personajes", str(oponente.id))
        if not datos_a: return await ctx.send("❌ Sin personaje.")
        if not datos_d: return await ctx.send(f"❌ {oponente.display_name} no tiene personaje.")
        if datos_a.get("ubicacion") != datos_d.get("ubicacion"):
            return await ctx.send("❌ Deben estar en el mismo sector.")
        key = tuple(sorted([ctx.author.id, oponente.id]))
        if key in self.peleas_activas:
            return await ctx.send("❌ Ya hay una pelea activa entre ustedes.")

        arma_a = _primera_arma(datos_a.get("inventario", {}))
        arma_d = _primera_arma(datos_d.get("inventario", {}))
        embed = discord.Embed(title="⚔️ ¡DESAFÍO!", description=f"**{datos_a['nombre']}** reta a **{datos_d['nombre']}**", color=0xE74C3C)
        embed.add_field(name=datos_a['nombre'], value=f"HP: {datos_a['stats'].get('hp',100)} | Arma: {arma_a or 'Ninguna'}", inline=True)
        embed.add_field(name=datos_d['nombre'], value=f"HP: {datos_d['stats'].get('hp',100)} | Arma: {arma_d or 'Ninguna'}", inline=True)
        view = AceptarPeleaView(ctx.author.id, oponente.id, datos_a, datos_d, self)
        await ctx.send(f"{oponente.mention}", embed=embed, view=view)

    @commands.command(name="disparar")
    async def disparar(self, ctx, objetivo: discord.Member):
        """Dispara a alguien con arma de fuego."""
        datos_a = await db.get("personajes", str(ctx.author.id))
        datos_d = await db.get("personajes", str(objetivo.id))
        if not datos_a: return await ctx.send("❌ Sin personaje.")
        if not datos_d: return await ctx.send("❌ El objetivo no tiene personaje.")

        arma = _primera_arma(datos_a.get("inventario", {}))
        if not arma or not es_arma_de_fuego(arma):
            return await ctx.send("❌ No tienes arma de fuego. Consíguela en el mercado negro.")
        if datos_a.get("ubicacion") != datos_d.get("ubicacion"):
            return await ctx.send("❌ Debes estar en el mismo sector.")

        await ctx.send(f"🔫 **{datos_a['nombre']}** saca su **{arma}** y apunta a **{datos_d['nombre']}**...")
        await asyncio.sleep(1)
        await self._resolver_tiroteo(ctx, ctx.author, objetivo, datos_a, datos_d, arma)

    async def _resolver_tiroteo(self, ctx, atacante, defensor, datos_a, datos_d, arma_a):
        nombre_a = datos_a.get("nombre", "?")
        nombre_d = datos_d.get("nombre", "?")
        hp_a = datos_a.get("stats", {}).get("hp", 100)
        hp_d = datos_d.get("stats", {}).get("hp", 100)
        arma_d = _primera_arma(datos_d.get("inventario", {}))

        # Stats "efectivas" (con penalización de lesiones activas) SOLO para el
        # cálculo de puntería/daño — el HP real sigue viviendo en hp_a/hp_d.
        stats_a_ef = await lesiones_mod.stats_con_penalizacion(atacante.id, datos_a.get("stats", {}))
        stats_d_ef = await lesiones_mod.stats_con_penalizacion(defensor.id, datos_d.get("stats", {}))
        datos_a_combate = {**datos_a, "stats": stats_a_ef}
        datos_d_combate = {**datos_d, "stats": stats_d_ef}

        log_embed = discord.Embed(title="🔫 TIROTEO EN CURSO", color=0x8B0000)
        log_lines = []
        ronda = 1
        fin_razon = ""

        while hp_a > 0 and hp_d > 0 and ronda <= 10:
            prob_acierto = min(0.85, (stats_a_ef.get("tecnica", 3) + 5) / 20)
            if random.random() < prob_acierto:
                daño, crit, _ap = _calcular_daño_combate(datos_a_combate, datos_d_combate, arma_a)
                hp_d = max(0, hp_d - daño)
                log_lines.append(f"💥 R{ronda}: **{nombre_a}** dispara ({arma_a}) → -{daño}HP {crit}")
            else:
                log_lines.append(f"💨 R{ronda}: **{nombre_a}** dispara y **falla**.")

            if hp_d <= 0:
                fin_razon = f"💀 **{nombre_d}** fue abatido."
                break

            if arma_d and es_arma_de_fuego(arma_d):
                prob_d = min(0.75, (stats_d_ef.get("tecnica", 3) + 5) / 20)
                if random.random() < prob_d:
                    daño2, crit2, _ap2 = _calcular_daño_combate(datos_d_combate, datos_a_combate, arma_d)
                    hp_a = max(0, hp_a - daño2)
                    log_lines.append(f"💥 R{ronda}: **{nombre_d}** responde ({arma_d}) → -{daño2}HP {crit2}")
                else:
                    log_lines.append(f"💨 R{ronda}: **{nombre_d}** responde y **falla**.")
            else:
                log_lines.append(f"🏃 R{ronda}: **{nombre_d}** busca cobertura.")

            if hp_a <= 0:
                fin_razon = f"💀 **{nombre_a}** fue abatido."
                break

            if ronda % 3 == 0 and hp_d > 0:
                huir_view = HuirView(defensor.id, atacante.id)
                await ctx.send(f"⚠️ {defensor.mention} — ¿Intentas huir o sigues el tiroteo?", view=huir_view)
                await huir_view.wait()
                if huir_view.huyo:
                    agilidad = stats_d_ef.get("agilidad", 5)
                    if random.random() < (agilidad / 20):
                        log_lines.append(f"🏃 **{nombre_d}** logra escapar!")
                        fin_razon = f"🏃 **{nombre_d}** huyó del tiroteo."
                        break
                    else:
                        log_lines.append(f"❌ **{nombre_d}** intenta huir pero falla.")

            ronda += 1

        if not fin_razon:
            fin_razon = f"🏆 **{nombre_a if hp_a > hp_d else nombre_d}** sobrevive."

        # Resolver caídas: ya no es muerte automática, hay chance de sobrevivir herido.
        if hp_a <= 0:
            hp_a = await self._procesar_caida(atacante.id, datos_a, ctx.guild, es_tiroteo=True)
        if hp_d <= 0:
            hp_d = await self._procesar_caida(defensor.id, datos_d, ctx.guild, es_tiroteo=True)

        log_embed.description = "\n".join(log_lines[-8:])
        log_embed.add_field(name="HP Final", value=f"{nombre_a}: {hp_a} | {nombre_d}: {hp_d}", inline=False)
        log_embed.add_field(name="Resultado", value=fin_razon, inline=False)

        s_a = datos_a.get("stats", {}); s_a["hp"] = hp_a
        s_d = datos_d.get("stats", {}); s_d["hp"] = hp_d
        await db.update("personajes", str(atacante.id), {"stats": s_a})
        await db.update("personajes", str(defensor.id), {"stats": s_d})

        await ctx.send(embed=log_embed)

        arma_es_ilegal = es_arma_ilegal(arma_a) or (arma_d and es_arma_ilegal(arma_d))
        urgencia = "🚨🚨 ARMA ILEGAL" if arma_es_ilegal else "🚨"
        await _notificar_policia(ctx.guild, ctx.channel, f"{urgencia} Tiroteo reportado. {nombre_a} vs {nombre_d}.")

    # ── !asesinato — intento de asesinato sigiloso ───────────────────────────
    @commands.command(name="asesinato", aliases=["asesinar"])
    async def asesinato(self, ctx, objetivo: discord.Member):
        """Intenta un asesinato sigiloso con un arma blanca oculta. Si sale mal,
        el objetivo se da cuenta y la cosa termina en una pelea abierta cuerpo
        a cuerpo (con mucha más probabilidad de que llegue la policía)."""
        if objetivo.id == ctx.author.id:
            return await ctx.send("❌ No puedes asesinarte a ti mismo.")
        datos_a = await db.get("personajes", str(ctx.author.id))
        datos_d = await db.get("personajes", str(objetivo.id))
        if not datos_a: return await ctx.send("❌ Sin personaje.")
        if not datos_d: return await ctx.send(f"❌ {objetivo.display_name} no tiene personaje.")
        if datos_a.get("ubicacion") != datos_d.get("ubicacion"):
            return await ctx.send("❌ Deben estar en el mismo sector.")

        arma = _primera_arma(datos_a.get("inventario", {}))
        if not arma or not es_arma_cortante(arma):
            return await ctx.send(
                "❌ Necesitas un arma blanca oculta (navaja, cuchillo, daga, machete...) "
                "para intentar un asesinato sigiloso."
            )
        key = tuple(sorted([ctx.author.id, objetivo.id]))
        if key in self.peleas_activas:
            return await ctx.send("❌ Ya hay un enfrentamiento activo entre ustedes.")

        stats_a_ef = await lesiones_mod.stats_con_penalizacion(ctx.author.id, datos_a.get("stats", {}))
        stats_d_ef = await lesiones_mod.stats_con_penalizacion(objetivo.id, datos_d.get("stats", {}))

        # Probabilidad de sigilo: técnica + agilidad del atacante contra la
        # percepción (agilidad + inteligencia) del objetivo.
        sigilo = stats_a_ef.get("tecnica", 3) * 1.2 + stats_a_ef.get("agilidad", 5)
        percepcion = stats_d_ef.get("agilidad", 5) + stats_d_ef.get("inteligencia", 5) * 0.5
        prob_exito = max(0.10, min(0.85, 0.5 + (sigilo - percepcion) / 30))

        await ctx.send(f"🔪 **{datos_a['nombre']}** se acerca sigilosamente a **{datos_d['nombre']}**, arma en mano...")
        await asyncio.sleep(1.5)

        self.peleas_activas[key] = True
        try:
            if random.random() < prob_exito:
                # Éxito: golpe letal por sorpresa, mucha más probabilidad de
                # muerte que en una pelea normal (es un ataque sorpresa).
                hp_d_final = await self._procesar_caida(
                    objetivo.id, datos_d, ctx.guild, es_tiroteo=False)
                # Sobrescribe la probabilidad "de pelea" con una más letal:
                # si sobrevivió con el roll normal, hay una segunda oportunidad
                # de que el golpe sorpresa igual sea mortal.
                if hp_d_final > 0 and random.random() < 0.5:
                    await self._manejar_muerte(objetivo.id, datos_d, ctx.guild, causa=f"asesinato con {arma}")
                    hp_d_final = 0
                stats_d = datos_d.get("stats", {}); stats_d["hp"] = hp_d_final
                await db.update("personajes", str(objetivo.id), {"stats": stats_d})

                embed = discord.Embed(
                    title="🔪 Asesinato sigiloso",
                    description=(f"**{datos_a['nombre']}** clava el **{arma}** en **{datos_d['nombre']}** "
                                 f"sin que nadie se dé cuenta a tiempo."),
                    color=0x2C2F33
                )
                embed.add_field(name="Resultado", value="💀 Fallecido" if hp_d_final <= 0 else f"🚑 Gravemente herido/a ({hp_d_final} HP)", inline=False)
                await ctx.send(embed=embed)
                if random.random() < 0.20:
                    await _notificar_policia(ctx.guild, ctx.channel,
                        f"🚨 Posible asesinato: encontraron a {datos_d['nombre']} malherido/a cerca de {ctx.channel.mention}.")
            else:
                # Fracaso: el objetivo se da cuenta y esto se convierte en pelea.
                await ctx.send(embed=discord.Embed(
                    description=(f"⚠️ **{datos_d['nombre']}** se da cuenta justo a tiempo y esquiva la puñalada — "
                                 f"¡el intento de asesinato se convierte en una pelea abierta!"),
                    color=discord.Color.orange()
                ))
                await self.resolver_pelea_interactiva(ctx.channel, ctx.guild, ctx.author.id, objetivo.id, datos_a, datos_d)
                # Un intento de asesinato fallido siempre acaba con la policía en camino.
                await _notificar_policia(ctx.guild, ctx.channel,
                    f"🚨🚨 INTENTO DE ASESINATO fallido: {datos_a['nombre']} contra {datos_d['nombre']}.")
        finally:
            self.peleas_activas.pop(key, None)

    # ── !curarse — se cura a sí mismo con ítems ────────────────────────────────
    @commands.command(name="curarse")
    async def curarse(self, ctx, item: str = None):
        """Cúrate a ti mismo usando un ítem médico del inventario.
        Uso: !curarse [item] — si no especificas, usa el primero disponible."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        stats = datos.get("stats", {})
        hp = stats.get("hp", 100)
        hp_max = stats.get("hp_max", 100)

        if hp >= hp_max:
            return await ctx.send("✅ Ya tienes HP al máximo.")

        inv = datos.get("inventario", {})

        if item:
            item = item.lower().replace(" ", "_")
            if item not in ITEMS_CURACION:
                items_disp = ", ".join(f"`{k}`" for k in ITEMS_CURACION.keys())
                return await ctx.send(f"❌ `{item}` no es un ítem de curación. Válidos: {items_disp}")
            if inv.get(item, 0) <= 0:
                return await ctx.send(f"❌ No tienes **{item}** en el inventario.")
            efecto = ITEMS_CURACION[item]
        else:
            item, efecto = _primer_item_curacion(inv)
            if not item:
                items_txt = ", ".join(f"`{k}`" for k in ITEMS_CURACION.keys())
                return await ctx.send(
                    f"❌ No tienes ítems de curación en el inventario.\n"
                    f"Puedes necesitar: {items_txt}"
                )

        # Aplicar curación
        hp_nuevo = min(hp_max, hp + efecto["hp"])
        stats["hp"] = hp_nuevo
        inv[item] -= 1
        if inv[item] <= 0:
            del inv[item]

        await db.update("personajes", str(ctx.author.id), {"stats": stats, "inventario": inv})

        embed = discord.Embed(
            title=f"🩹 {datos['nombre']} se cura",
            description=f"{efecto['msg']}\n**HP:** {hp} → **{hp_nuevo}**/{hp_max} (+{efecto['hp']})",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Ítem usado: {item} | Quedan en inventario: {inv.get(item, 0)}")
        await ctx.send(embed=embed)

    # ── !descansar / !cama — curación gratis, pero solo si estás SOLO ──────────
    @commands.command(name="descansar", aliases=["cama", "dormir"])
    async def descansar(self, ctx):
        """Descansa (echarte en la cama, sentarte a solas, etc.) para recuperar
        HP gratis, SIN necesidad de items — pero solo funciona si no hay
        ningún otro personaje en tu mismo canal ahora mismo. Tiene un
        enfriamiento de 2 horas reales."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        if datos.get("muerto"):
            return await ctx.send("❌ Tu personaje está muerto.")

        canal_actual = datos.get("canal_actual", "")
        if ctx.channel.name != canal_actual:
            return await ctx.send(f"❌ Debes estar en tu canal actual (`{canal_actual}`) para descansar ahí.")

        # ¿Hay alguien más (con personaje) en este mismo canal ahora mismo?
        todos = await db.all("personajes")
        otros = [
            uid for uid, d in todos.items()
            if uid != str(ctx.author.id) and not d.get("muerto")
            and d.get("canal_actual") == canal_actual
        ]
        if otros:
            return await ctx.send("❌ No estás solo en este canal — no puedes descansar tranquilo con gente cerca.")

        import time as _time
        ahora = _time.time()
        ultimo = datos.get("ultimo_descanso_ts", 0)
        ESPERA = 2 * 3600
        if ahora - ultimo < ESPERA:
            restante = int((ESPERA - (ahora - ultimo)) / 60)
            return await ctx.send(f"⏳ Ya descansaste hace poco. Vuelve a intentarlo en ~{restante} min.")

        stats = datos.get("stats", {})
        hp = stats.get("hp", 100)
        hp_max = stats.get("hp_max", 100)
        if hp >= hp_max:
            await db.update("personajes", str(ctx.author.id), {"ultimo_descanso_ts": ahora})
            return await ctx.send("✅ Ya tienes el HP al máximo. De todos modos, un buen descanso nunca sobra.")

        curacion = max(10, int((hp_max - hp) * 0.35))
        hp_nuevo = min(hp_max, hp + curacion)
        stats["hp"] = hp_nuevo
        await db.update("personajes", str(ctx.author.id), {"stats": stats, "ultimo_descanso_ts": ahora})

        await ctx.send(embed=discord.Embed(
            description=f"🛌 **{datos['nombre']}** descansa a solas un buen rato.\n"
                        f"**HP:** {hp} → **{hp_nuevo}**/{hp_max} (+{hp_nuevo-hp})",
            color=discord.Color.blurple()
        ))

    # ── !curar — cura a otra persona con ítems ─────────────────────────────────
    @commands.command(name="curar")
    async def curar(self, ctx, objetivo: discord.Member, item: str = None):
        """Cura a otra persona usando un ítem médico de TU inventario.
        Uso: !curar @usuario [item]"""
        datos_curador = await db.get("personajes", str(ctx.author.id))
        datos_obj = await db.get("personajes", str(objetivo.id))

        if not datos_curador:
            return await ctx.send("❌ Sin personaje.")
        if not datos_obj:
            return await ctx.send(f"❌ {objetivo.display_name} no tiene personaje.")

        # Deben estar en el mismo sector
        if datos_curador.get("ubicacion") != datos_obj.get("ubicacion"):
            return await ctx.send("❌ Debes estar en el mismo sector que el objetivo.")

        stats_obj = datos_obj.get("stats", {})
        hp = stats_obj.get("hp", 100)
        hp_max = stats_obj.get("hp_max", 100)

        if hp >= hp_max:
            return await ctx.send(f"✅ **{datos_obj['nombre']}** ya tiene HP al máximo.")

        inv_curador = datos_curador.get("inventario", {})

        if item:
            item = item.lower().replace(" ", "_")
            if item not in ITEMS_CURACION:
                return await ctx.send(f"❌ `{item}` no es un ítem de curación válido.")
            if inv_curador.get(item, 0) <= 0:
                return await ctx.send(f"❌ No tienes **{item}** en tu inventario.")
            efecto = ITEMS_CURACION[item]
        else:
            item, efecto = _primer_item_curacion(inv_curador)
            if not item:
                return await ctx.send(
                    f"❌ No tienes ítems de curación en el inventario.\n"
                    f"Compra: vendaje, kit_medico, torniquete, etc."
                )

        # Si es morfina/inyecciones, bonus si hay hospital cerca
        canal_actual = datos_curador.get("canal_actual", "")
        en_hospital = any(h in canal_actual for h in CANALES_HOSPITAL)
        hp_bonus = efecto["hp"]
        if en_hospital and item in ("morfina", "kit_medico", "sangre_tipo_o"):
            hp_bonus = int(hp_bonus * 1.3)

        hp_nuevo = min(hp_max, hp + hp_bonus)
        stats_obj["hp"] = hp_nuevo

        inv_curador[item] -= 1
        if inv_curador[item] <= 0:
            del inv_curador[item]

        await db.update("personajes", str(objetivo.id), {"stats": stats_obj})
        await db.update("personajes", str(ctx.author.id), {"inventario": inv_curador})

        embed = discord.Embed(
            title=f"🏥 {datos_curador['nombre']} cura a {datos_obj['nombre']}",
            description=f"{efecto['msg']}\n**HP de {datos_obj['nombre']}:** {hp} → **{hp_nuevo}**/{hp_max} (+{hp_bonus})",
            color=discord.Color.green()
        )
        if en_hospital:
            embed.add_field(name="🏥 Bonus hospitalario", value="El equipo médico del lugar aumentó la eficacia.", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="entrenar")
    async def entrenar(self, ctx, stat: str):
        """Entrena una estadística en gym."""
        stats_validas = ["fuerza", "agilidad", "resistencia", "tecnica", "inteligencia", "carisma"]
        if stat.lower() not in stats_validas:
            return await ctx.send(f"❌ Stats: {', '.join(stats_validas)}")
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos: return await ctx.send("❌ Sin personaje.")
        canal = datos.get("canal_actual", "")
        if not any(x in canal for x in ["gym", "boxeo", "muay", "deporte", "cancha", "campo", "crossfit"]):
            return await ctx.send("❌ Debes estar en un gym o área deportiva.")
        costo = 5.0
        dinero = datos.get("dinero", 0)
        if dinero < costo: return await ctx.send(f"❌ Costo: ${costo}. Tienes ${dinero:.2f}.")
        stats = datos.get("stats", {})
        val_actual = stats.get(stat.lower(), 5)
        if val_actual >= 30: return await ctx.send(f"❌ Límite alcanzado en {stat} ({val_actual}).")
        mejora = random.randint(1, 2)
        stats[stat.lower()] = val_actual + mejora
        if stat.lower() == "resistencia":
            stats["hp_max"] = stats.get("hp_max", 100) + mejora * 5
        await db.update("personajes", str(ctx.author.id), {"stats": stats, "dinero": round(dinero - costo, 2)})
        await ctx.send(f"💪 **{stat}**: {val_actual} → {val_actual + mejora} (+{mejora}) | Costo: ${costo}")

    @commands.command(name="items_curacion")
    async def items_curacion_lista(self, ctx):
        """Lista todos los ítems de curación disponibles."""
        embed = discord.Embed(title="🩹 Ítems de Curación", color=discord.Color.green())
        for nombre, info in ITEMS_CURACION.items():
            embed.add_field(
                name=f"`{nombre}`",
                value=f"+{info['hp']} HP — {info['msg'][:50]}",
                inline=True
            )
        embed.set_footer(text="!curarse [item] — curarte | !curar @usuario [item] — curar a otro")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Combate(bot))