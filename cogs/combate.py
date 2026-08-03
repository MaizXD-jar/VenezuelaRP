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
                          calcular_defensa_total, es_arma_de_fuego, es_arma_ilegal)

CH_POLICIA_AVISO = 1359320808526450780
ROL_POLICIA      = 1359320808526450780
CH_MUERTOS       = 1359320811420520613

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


def _calcular_daño_combate(atacante: dict, defensor: dict, arma: str = None) -> tuple:
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

    critico = ""
    if random.random() < 0.10:
        daño_final = int(daño_final * 1.6)
        critico = " ⚡**¡CRÍTICO!**"

    return daño_final, critico


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
        nombre_a = self.datos_a.get("nombre", "?")
        nombre_d = self.datos_d.get("nombre", "?")
        hp_a = self.datos_a.get("stats", {}).get("hp", 100)
        hp_d = self.datos_d.get("stats", {}).get("hp", 100)
        arma_a = _primera_arma(self.datos_a.get("inventario", {}))
        arma_d = _primera_arma(self.datos_d.get("inventario", {}))

        # Stats "efectivas" (con penalización de lesiones activas) SOLO para el
        # cálculo de daño — el HP real sigue viviendo en hp_a/hp_d por separado.
        stats_a_ef = await lesiones_mod.stats_con_penalizacion(self.atacante_id, self.datos_a.get("stats", {}))
        stats_d_ef = await lesiones_mod.stats_con_penalizacion(self.defensor_id, self.datos_d.get("stats", {}))
        datos_a_combate = {**self.datos_a, "stats": stats_a_ef}
        datos_d_combate = {**self.datos_d, "stats": stats_d_ef}

        log = []
        ronda = 1

        while hp_a > 0 and hp_d > 0 and ronda <= 8:
            daño, crit = _calcular_daño_combate(datos_a_combate, datos_d_combate, arma_a)
            hp_d = max(0, hp_d - daño)
            arma_txt = f" con **{arma_a}**" if arma_a else ""
            log.append(f"R{ronda}: {nombre_a}{arma_txt} → -{daño}HP a {nombre_d}{crit}")
            if hp_d <= 0: break

            daño2, crit2 = _calcular_daño_combate(datos_d_combate, datos_a_combate, arma_d)
            hp_a = max(0, hp_a - daño2)
            arma_txt2 = f" con **{arma_d}**" if arma_d else ""
            log.append(f"R{ronda}: {nombre_d}{arma_txt2} → -{daño2}HP a {nombre_a}{crit2}")
            ronda += 1

        if hp_a <= 0 and hp_d <= 0:
            resultado = "💀 ¡Ambos cayeron! Empate."
        elif hp_a <= 0:
            resultado = f"🏆 **{nombre_d}** ganó!"
        elif hp_d <= 0:
            resultado = f"🏆 **{nombre_a}** ganó!"
        else:
            resultado = f"🏆 **{nombre_a if hp_a > hp_d else nombre_d}** gana por puntos."

        # Resolver caídas: ya no es muerte automática, hay chance de sobrevivir herido.
        if hp_a <= 0:
            hp_a = await self.cog._procesar_caida(self.atacante_id, self.datos_a, interaction.guild, es_tiroteo=False)
        if hp_d <= 0:
            hp_d = await self.cog._procesar_caida(self.defensor_id, self.datos_d, interaction.guild, es_tiroteo=False)

        embed = discord.Embed(title="⚔️ RESULTADO DE LA PELEA", color=0xE74C3C)
        embed.description = "\n".join(log[-6:])
        embed.add_field(name="HP Final", value=f"{nombre_a}: {hp_a} | {nombre_d}: {hp_d}", inline=False)
        embed.add_field(name="🏆 Resultado", value=resultado, inline=False)

        s_a = self.datos_a.get("stats", {}); s_a["hp"] = hp_a
        s_d = self.datos_d.get("stats", {}); s_d["hp"] = hp_d
        await db.update("personajes", str(self.atacante_id), {"stats": s_a})
        await db.update("personajes", str(self.defensor_id), {"stats": s_d})

        if random.random() < 0.15:
            embed.add_field(name="🚔 POLICÍA", value="¡La CPNB llegó al lugar!", inline=False)

        await interaction.followup.send(embed=embed)
        if random.random() < 0.15:
            await _notificar_policia(interaction.guild, interaction.channel, f"Pelea entre {nombre_a} y {nombre_d}.")


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
                daño, crit = _calcular_daño_combate(datos_a_combate, datos_d_combate, arma_a)
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
                    daño2, crit2 = _calcular_daño_combate(datos_d_combate, datos_a_combate, arma_d)
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