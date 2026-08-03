"""
cogs/casino.py — Sistema de casino + apuestas desde el teléfono.

- Casino físico (Fontainebleau Miami): tragamonedas, ruleta, dados, blackjack.
  Hay que estar en el canal del casino para jugar.
- Apuestas por teléfono: apuestas deportivas y lotería rápida. Se pueden hacer
  desde cualquier lugar, pero necesitas tener un teléfono en tu inventario.

Requisito para TODO lo de este cog: el personaje debe ser mayor de 18 años
(edad del personaje en el rol). Es ficción, pero se trata igual que cualquier
otro requisito de edad ya existente en el bot (trabajos, etc.).

Diseño de probabilidades: como en un casino real, el valor esperado de casi
todos los juegos es negativo para el jugador (la casa siempre gana a la
larga). Blackjack es el más "justo" (como en la vida real), el resto tiene
más margen para la casa.
"""
import random
import time
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from utils import db

EDAD_MINIMA_CASINO = 18
CANAL_CASINO = "casino-fontainebleau-miami"
APUESTA_MIN = 10.0
APUESTA_MAX = 50_000.0


# ══════════════════════════════════════════════════════════════════════════
# Helpers comunes
# ══════════════════════════════════════════════════════════════════════════
def _tiene_telefono(datos: dict) -> bool:
    inv = datos.get("inventario", [])
    return any("telefono" in i or "smartphone" in i for i in inv)


def _autor(ctx_or_inter):
    return ctx_or_inter.user if isinstance(ctx_or_inter, discord.Interaction) else ctx_or_inter.author


async def _validar_jugador(ctx_or_inter, monto: float, requerir_telefono: bool = False,
                            requerir_casino: bool = False) -> tuple[Optional[dict], Optional[str]]:
    """Valida edad, teléfono/ubicación y el monto de la apuesta. Devuelve (datos, error)."""
    user = _autor(ctx_or_inter)
    datos = await db.get("personajes", str(user.id))
    if not datos:
        return None, "❌ No tienes personaje."

    edad = datos.get("edad", 0)
    if edad < EDAD_MINIMA_CASINO:
        return None, (
            f"🔞 Tu personaje tiene {edad} años. Necesitas **{EDAD_MINIMA_CASINO}+** "
            f"en el rol para apostar — ni el casino ni las apps de apuestas dejan entrar a menores."
        )

    if requerir_telefono and not _tiene_telefono(datos):
        return None, "❌ Necesitas un teléfono para usar esta app. Cómprate uno en la tienda (`smartphone`)."

    if requerir_casino:
        canal_actual = datos.get("canal_actual", "")
        if canal_actual != CANAL_CASINO:
            return None, f"❌ Debes estar físicamente en el casino (`#{CANAL_CASINO}`) para jugar esto. Viaja ahí con `/viajar`."

    if monto < APUESTA_MIN:
        return None, f"❌ La apuesta mínima es ${APUESTA_MIN:,.0f}."
    if monto > APUESTA_MAX:
        return None, f"❌ La apuesta máxima es ${APUESTA_MAX:,.0f}."

    dinero = datos.get("dinero", 0)
    if dinero < monto:
        return None, f"❌ No tienes ${monto:,.2f}. Tienes ${dinero:,.2f} en efectivo."

    return datos, None


async def _cobrar_y_pagar(user_id: int, monto_apostado: float, monto_devuelto: float) -> float:
    """Descuenta la apuesta y acredita lo que se gana (0 si pierde todo). Devuelve el dinero final."""
    key = str(user_id)
    datos = await db.get("personajes", key)
    dinero = datos.get("dinero", 0)
    nuevo = round(dinero - monto_apostado + monto_devuelto, 2)
    await db.update("personajes", key, {"dinero": nuevo})

    stats = await db.get("casino_stats", key) or {"apostado": 0, "ganado": 0, "jugadas": 0, "mayor_ganancia": 0}
    neto = monto_devuelto - monto_apostado
    stats["apostado"] = round(stats.get("apostado", 0) + monto_apostado, 2)
    stats["ganado"] = round(stats.get("ganado", 0) + monto_devuelto, 2)
    stats["jugadas"] = stats.get("jugadas", 0) + 1
    if neto > stats.get("mayor_ganancia", 0):
        stats["mayor_ganancia"] = round(neto, 2)
    await db.set("casino_stats", key, stats)
    return nuevo


def _embed_resultado(titulo: str, descripcion: str, neto: float) -> discord.Embed:
    color = discord.Color.green() if neto > 0 else (discord.Color.greyple() if neto == 0 else discord.Color.red())
    embed = discord.Embed(title=titulo, description=descripcion, color=color)
    if neto > 0:
        embed.add_field(name="Resultado", value=f"🟢 Ganaste ${neto:,.2f}", inline=False)
    elif neto == 0:
        embed.add_field(name="Resultado", value="⚪ Recuperaste tu apuesta, sin ganancia.", inline=False)
    else:
        embed.add_field(name="Resultado", value=f"🔴 Perdiste ${abs(neto):,.2f}", inline=False)
    return embed


# ══════════════════════════════════════════════════════════════════════════
# Blackjack — cartas y lógica
# ══════════════════════════════════════════════════════════════════════════
PALOS = ["♠️", "♥️", "♦️", "♣️"]
VALORES = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def _nueva_baraja() -> list[str]:
    baraja = [f"{v}{p}" for v in VALORES for p in PALOS]
    random.shuffle(baraja)
    return baraja


def _valor_mano(mano: list[str]) -> int:
    total = 0
    ases = 0
    for carta in mano:
        v = carta[:-2]  # quita el palo (2 chars de emoji)
        if v in ("J", "Q", "K"):
            total += 10
        elif v == "A":
            total += 11
            ases += 1
        else:
            total += int(v)
    while total > 21 and ases > 0:
        total -= 10
        ases -= 1
    return total


def _fmt_mano(mano: list[str]) -> str:
    return " ".join(mano)


class BlackjackView(discord.ui.View):
    def __init__(self, user_id: int, monto: float, baraja: list[str], mano_j: list[str], mano_d: list[str]):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.monto = monto
        self.baraja = baraja
        self.mano_j = mano_j
        self.mano_d = mano_d
        self.terminado = False

    async def _finalizar(self, interaction: discord.Interaction, resultado_txt: str, neto: float):
        self.terminado = True
        for child in self.children:
            child.disabled = True
        dinero_final = await _cobrar_y_pagar(self.user_id, self.monto, self.monto + neto)
        embed = _embed_resultado(
            "🃏 Blackjack",
            f"**Tu mano:** {_fmt_mano(self.mano_j)} = {_valor_mano(self.mano_j)}\n"
            f"**Casa:** {_fmt_mano(self.mano_d)} = {_valor_mano(self.mano_d)}\n\n{resultado_txt}",
            neto,
        )
        embed.set_footer(text=f"Efectivo restante: ${dinero_final:,.2f}")
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="🂠 Pedir carta", style=discord.ButtonStyle.blurple)
    async def pedir(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("No es tu partida.", ephemeral=True)
        if self.terminado:
            return
        self.mano_j.append(self.baraja.pop())
        valor = _valor_mano(self.mano_j)
        if valor > 21:
            return await self._finalizar(interaction, "💥 Te pasaste de 21. Pierdes.", -self.monto)
        if valor == 21:
            return await self._resolver_dealer(interaction)

        embed = discord.Embed(
            title="🃏 Blackjack",
            description=f"**Tu mano:** {_fmt_mano(self.mano_j)} = {valor}\n**Casa:** {self.mano_d[0]} 🂠",
            color=discord.Color.blurple(),
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="✋ Plantarse", style=discord.ButtonStyle.gray)
    async def plantarse(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("No es tu partida.", ephemeral=True)
        if self.terminado:
            return
        await self._resolver_dealer(interaction)

    async def _resolver_dealer(self, interaction: discord.Interaction):
        valor_j = _valor_mano(self.mano_j)
        while _valor_mano(self.mano_d) < 17:
            self.mano_d.append(self.baraja.pop())
        valor_d = _valor_mano(self.mano_d)

        blackjack_natural = len(self.mano_j) == 2 and valor_j == 21

        if valor_d > 21 or valor_j > valor_d:
            neto = self.monto * 1.5 if blackjack_natural else self.monto
            txt = "🎉 ¡Ganaste!" + (" ¡Blackjack natural, paga 3 a 2!" if blackjack_natural else "")
        elif valor_j == valor_d:
            neto = 0.0
            txt = "🤝 Empate. Recuperas tu apuesta."
        else:
            neto = -self.monto
            txt = "😔 Gana la casa."

        await self._finalizar(interaction, txt, neto)


# ══════════════════════════════════════════════════════════════════════════
# Cog principal
# ══════════════════════════════════════════════════════════════════════════
class Casino(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── !casino — menú informativo ──────────────────────────────────────────
    @commands.command(name="casino")
    async def casino_menu(self, ctx):
        embed = discord.Embed(
            title="🎰 Casino Fontainebleau — Miami",
            description=(
                f"Debes estar en `#{CANAL_CASINO}` y ser mayor de 18 años en el rol.\n\n"
                "**Juegos disponibles aquí:**\n"
                "🎰 `!tragamonedas <monto>` — 3 símbolos, premios raros\n"
                "🎡 `!ruleta <monto> <rojo|negro|par|impar|0-36>`\n"
                "🎲 `!dados <monto> <1-6|par|impar>`\n"
                "🃏 `!blackjack <monto>` — contra la casa, botones interactivos\n\n"
                "**Desde tu teléfono (en cualquier lugar):**\n"
                "⚽ `!apuesta_deportiva <monto> <equipo>`\n"
                "🎫 `!loteria <monto> <numero 0-99>`\n\n"
                "📊 `!casino_stats` — ver cuánto llevas ganado/perdido"
            ),
            color=discord.Color.dark_gold(),
        )
        embed.set_footer(text="La casa siempre tiene ventaja. Juega con lo que puedas perder — es roleplay, no dinero real.")
        await ctx.send(embed=embed)

    # ── !tragamonedas ────────────────────────────────────────────────────────
    @commands.command(name="tragamonedas", aliases=["slots"])
    async def tragamonedas(self, ctx, monto: float):
        datos, error = await _validar_jugador(ctx, monto, requerir_casino=True)
        if error:
            return await ctx.send(error)

        simbolos = ["🍒"] * 40 + ["🍋"] * 30 + ["🍇"] * 20 + ["💎"] * 8 + ["7️⃣"] * 2
        tirada = [random.choice(simbolos) for _ in range(3)]

        if tirada[0] == tirada[1] == tirada[2]:
            multiplicadores = {"7️⃣": 150, "💎": 40, "🍇": 10, "🍋": 4, "🍒": 2}
            mult = multiplicadores[tirada[0]]
        elif tirada.count("🍒") == 2:
            mult = 1.8
        else:
            mult = 0

        devuelto = round(monto * mult, 2)
        neto = devuelto - monto
        dinero_final = await _cobrar_y_pagar(ctx.author.id, monto, devuelto)

        embed = _embed_resultado(
            "🎰 Tragamonedas",
            f"[ {'  '.join(tirada)} ]",
            neto,
        )
        embed.set_footer(text=f"Efectivo restante: ${dinero_final:,.2f}")
        await ctx.send(embed=embed)

    # ── !ruleta ──────────────────────────────────────────────────────────────
    @commands.command(name="ruleta")
    async def ruleta(self, ctx, monto: float, apuesta: str):
        datos, error = await _validar_jugador(ctx, monto, requerir_casino=True)
        if error:
            return await ctx.send(error)

        apuesta = apuesta.lower()
        numeros_rojos = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        numero = random.randint(0, 36)
        color = "verde" if numero == 0 else ("rojo" if numero in numeros_rojos else "negro")

        gano = False
        mult = 0
        if apuesta.isdigit() and 0 <= int(apuesta) <= 36:
            if int(apuesta) == numero:
                gano, mult = True, 35
        elif apuesta in ("rojo", "negro"):
            if apuesta == color:
                gano, mult = True, 1
        elif apuesta in ("par", "impar") and numero != 0:
            es_par = numero % 2 == 0
            if (apuesta == "par") == es_par:
                gano, mult = True, 1
        else:
            return await ctx.send("❌ Apuesta inválida. Usa: `rojo`, `negro`, `par`, `impar`, o un número de 0 a 36.")

        devuelto = round(monto * (mult + 1), 2) if gano else 0.0
        neto = devuelto - monto
        dinero_final = await _cobrar_y_pagar(ctx.author.id, monto, devuelto)

        emoji_color = {"rojo": "🔴", "negro": "⚫", "verde": "🟢"}[color]
        embed = _embed_resultado(
            "🎡 Ruleta",
            f"Salió **{numero}** {emoji_color} ({color})\nTu apuesta: `{apuesta}`",
            neto,
        )
        embed.set_footer(text=f"Efectivo restante: ${dinero_final:,.2f}")
        await ctx.send(embed=embed)

    # ── !dados ───────────────────────────────────────────────────────────────
    @commands.command(name="dados")
    async def dados(self, ctx, monto: float, apuesta: str):
        datos, error = await _validar_jugador(ctx, monto, requerir_casino=True)
        if error:
            return await ctx.send(error)

        apuesta = apuesta.lower()
        tirada = random.randint(1, 6)

        gano = False
        mult = 0
        if apuesta.isdigit() and 1 <= int(apuesta) <= 6:
            if int(apuesta) == tirada:
                gano, mult = True, 4  # pagaría 5 en probabilidad justa: ventaja de la casa
        elif apuesta in ("par", "impar"):
            es_par = tirada % 2 == 0
            if (apuesta == "par") == es_par:
                gano, mult = True, 0.9  # un poco por debajo de lo justo, como en un casino real
        else:
            return await ctx.send("❌ Apuesta inválida. Usa un número de 1 a 6, o `par`/`impar`.")

        devuelto = round(monto * (mult + 1), 2) if gano else 0.0
        neto = devuelto - monto
        dinero_final = await _cobrar_y_pagar(ctx.author.id, monto, devuelto)

        embed = _embed_resultado("🎲 Dados", f"Salió **{tirada}**\nTu apuesta: `{apuesta}`", neto)
        embed.set_footer(text=f"Efectivo restante: ${dinero_final:,.2f}")
        await ctx.send(embed=embed)

    # ── !blackjack ───────────────────────────────────────────────────────────
    @commands.command(name="blackjack", aliases=["bj"])
    async def blackjack(self, ctx, monto: float):
        datos, error = await _validar_jugador(ctx, monto, requerir_casino=True)
        if error:
            return await ctx.send(error)

        baraja = _nueva_baraja()
        mano_j = [baraja.pop(), baraja.pop()]
        mano_d = [baraja.pop(), baraja.pop()]

        if _valor_mano(mano_j) == 21:
            devuelto = round(monto * 2.5, 2)
            dinero_final = await _cobrar_y_pagar(ctx.author.id, monto, devuelto)
            embed = _embed_resultado(
                "🃏 Blackjack",
                f"**Tu mano:** {_fmt_mano(mano_j)} = 21 🎉\n**Casa:** {_fmt_mano(mano_d)} = {_valor_mano(mano_d)}\n\n¡Blackjack natural! Paga 3 a 2.",
                monto * 1.5,
            )
            embed.set_footer(text=f"Efectivo restante: ${dinero_final:,.2f}")
            return await ctx.send(embed=embed)

        view = BlackjackView(ctx.author.id, monto, baraja, mano_j, mano_d)
        embed = discord.Embed(
            title="🃏 Blackjack",
            description=f"**Tu mano:** {_fmt_mano(mano_j)} = {_valor_mano(mano_j)}\n**Casa:** {mano_d[0]} 🂠",
            color=discord.Color.blurple(),
        )
        await ctx.send(embed=embed, view=view)

    # ── !apuesta_deportiva (teléfono) ────────────────────────────────────────
    EQUIPOS = ["Caracas FC", "Deportivo Táchira", "Zamora FC", "Estudiantes de Mérida",
               "Metropolitanos FC", "Monagas SC", "Deportivo La Guaira", "Carabobo FC"]

    @commands.command(name="apuesta_deportiva", aliases=["apostar_futbol"])
    async def apuesta_deportiva(self, ctx, monto: float, *, equipo: str):
        datos, error = await _validar_jugador(ctx, monto, requerir_telefono=True)
        if error:
            return await ctx.send(error)

        equipo = equipo.strip()
        rival = random.choice([e for e in self.EQUIPOS if e.lower() != equipo.lower()] or self.EQUIPOS)
        if equipo.title() not in self.EQUIPOS and equipo not in self.EQUIPOS:
            return await ctx.send(f"❌ Equipo inválido. Opciones: {', '.join(self.EQUIPOS)}")

        # Probabilidad "real" del equipo elegido de ganar, con margen de casa incorporado en la cuota
        prob_gana = random.uniform(0.30, 0.55)
        cuota = round((1 / prob_gana) * 0.90, 2)  # margen de casa ~10%

        gano = random.random() < prob_gana
        goles_equipo = random.randint(0, 4) if gano else random.randint(0, 2)
        goles_rival = random.randint(0, goles_equipo) if gano else max(goles_equipo + 1, random.randint(1, 3))

        devuelto = round(monto * cuota, 2) if gano else 0.0
        neto = devuelto - monto
        dinero_final = await _cobrar_y_pagar(ctx.author.id, monto, devuelto)

        embed = _embed_resultado(
            "⚽ Apuesta deportiva",
            f"**{equipo}** {goles_equipo} - {goles_rival} **{rival}**\nCuota: {cuota}x",
            neto,
        )
        embed.set_footer(text=f"📱 Apuesta hecha desde el teléfono | Efectivo: ${dinero_final:,.2f}")
        await ctx.send(embed=embed)

    # ── !loteria (teléfono) ──────────────────────────────────────────────────
    @commands.command(name="loteria", aliases=["loteria_rapida"])
    async def loteria(self, ctx, monto: float, numero: int):
        datos, error = await _validar_jugador(ctx, monto, requerir_telefono=True)
        if error:
            return await ctx.send(error)
        if not (0 <= numero <= 99):
            return await ctx.send("❌ El número debe estar entre 0 y 99.")

        ganador = random.randint(0, 99)
        gano = numero == ganador
        devuelto = round(monto * 60, 2) if gano else 0.0  # 1/100 de probabilidad, paga 60x — parecido al margen real de una lotería (RTP ~60%)
        neto = devuelto - monto
        dinero_final = await _cobrar_y_pagar(ctx.author.id, monto, devuelto)

        embed = _embed_resultado(
            "🎫 Lotería rápida",
            f"Tu número: **{numero:02d}** | Número ganador: **{ganador:02d}**",
            neto,
        )
        embed.set_footer(text=f"📱 Ticket comprado desde el teléfono | Efectivo: ${dinero_final:,.2f}")
        await ctx.send(embed=embed)

    # ── !casino_stats ────────────────────────────────────────────────────────
    @commands.command(name="casino_stats")
    async def casino_stats(self, ctx, objetivo: discord.Member = None):
        objetivo = objetivo or ctx.author
        stats = await db.get("casino_stats", str(objetivo.id))
        if not stats:
            return await ctx.send(f"📊 {objetivo.display_name} no ha jugado en el casino todavía.")

        neto_total = round(stats.get("ganado", 0) - stats.get("apostado", 0), 2)
        embed = discord.Embed(title=f"📊 Estadísticas de casino — {objetivo.display_name}",
                               color=discord.Color.gold() if neto_total >= 0 else discord.Color.red())
        embed.add_field(name="🎲 Jugadas", value=str(stats.get("jugadas", 0)), inline=True)
        embed.add_field(name="💰 Apostado total", value=f"${stats.get('apostado', 0):,.2f}", inline=True)
        embed.add_field(name="🏆 Ganado total", value=f"${stats.get('ganado', 0):,.2f}", inline=True)
        embed.add_field(name="📈 Balance neto", value=f"${neto_total:,.2f}", inline=True)
        embed.add_field(name="🎉 Mayor ganancia", value=f"${stats.get('mayor_ganancia', 0):,.2f}", inline=True)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Casino(bot))
