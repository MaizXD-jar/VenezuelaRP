"""
cogs/minijuegos.py — Minijuegos que NO son de apuestas (para eso está el casino).
Trivia paga solo si aciertas, sin arriesgar nada; el duelo de reacción es puro
skill (con apuesta opcional entre los dos jugadores, no contra la casa).
"""
import asyncio
import random
import time

import discord
from discord.ext import commands

from utils import db

RECOMPENSA_TRIVIA = 25.0
COOLDOWN_TRIVIA_SEG = 90

TRIVIA_PREGUNTAS = [
    {"pregunta": "¿Cuál es la capital de Venezuela?",
     "opciones": ["Caracas", "Maracaibo", "Valencia", "Barquisimeto"], "correcta": 0},
    {"pregunta": "¿Cómo se llama la moneda oficial de Venezuela?",
     "opciones": ["Peso", "Bolívar", "Sol", "Colón"], "correcta": 1},
    {"pregunta": "¿Cuál es el plato más asociado con la Navidad venezolana?",
     "opciones": ["Pabellón criollo", "Hallaca", "Arepa", "Cachapa"], "correcta": 1},
    {"pregunta": "¿Cómo se llama la catarata más alta del mundo, ubicada en Venezuela?",
     "opciones": ["Salto Ángel", "Cataratas del Iguazú", "Salto La Llovizna", "Cataratas de Kaieteur"], "correcta": 0},
    {"pregunta": "¿Cuál es el nombre del área metropolitana de Caracas donde queda 'Petare'?",
     "opciones": ["Miranda", "Zulia", "Carabobo", "Táchira"], "correcta": 0},
    {"pregunta": "¿Cómo se llama la comida típica hecha de maíz, rellena y a la plancha o frita?",
     "opciones": ["Tequeño", "Empanada", "Arepa", "Cachapa"], "correcta": 2},
    {"pregunta": "¿Cuál es el deporte más popular en Venezuela?",
     "opciones": ["Fútbol", "Béisbol", "Baloncesto", "Voleibol"], "correcta": 1},
    {"pregunta": "¿Cómo se le llama coloquialmente al dinero en efectivo en Venezuela?",
     "opciones": ["Plata", "Lana", "Reales", "Todas las anteriores"], "correcta": 3},
    {"pregunta": "¿Cuál es el lago más grande de Venezuela?",
     "opciones": ["Lago de Valencia", "Lago de Maracaibo", "Laguna de Tacarigua", "Represa de Guri"], "correcta": 1},
    {"pregunta": "¿Cómo se llama el snack frito hecho de queso envuelto en masa, típico venezolano?",
     "opciones": ["Tequeño", "Empanada", "Cachito", "Golfeado"], "correcta": 0},
]


class DueloReaccionView(discord.ui.View):
    def __init__(self, jugador1: discord.Member, jugador2: discord.Member):
        super().__init__(timeout=15)
        self.jugador1 = jugador1
        self.jugador2 = jugador2
        self.habilitado = False
        self.ganador: discord.Member | None = None
        self.perdedor_por_salida_falsa: discord.Member | None = None
        self.terminado = False

    def _es_jugador(self, user_id: int) -> bool:
        return user_id in (self.jugador1.id, self.jugador2.id)

    @discord.ui.button(label="🖐️ ¡YA!", style=discord.ButtonStyle.green)
    async def presionar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._es_jugador(interaction.user.id):
            return await interaction.response.send_message("No es tu duelo.", ephemeral=True)
        if self.terminado:
            return await interaction.response.send_message("El duelo ya terminó.", ephemeral=True)

        if not self.habilitado:
            self.terminado = True
            self.perdedor_por_salida_falsa = interaction.user
            self.ganador = self.jugador2 if interaction.user.id == self.jugador1.id else self.jugador1
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)
            self.stop()
            return

        self.terminado = True
        self.ganador = interaction.user
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


class Minijuegos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._ultimo_trivia: dict[int, float] = {}

    # ── !trivia ──────────────────────────────────────────────────────────────
    @commands.command(name="trivia")
    async def trivia(self, ctx):
        """Responde una trivia de Venezuela. Solo ganas, nunca pierdes dinero."""
        ahora = time.time()
        ultimo = self._ultimo_trivia.get(ctx.author.id, 0)
        restante = COOLDOWN_TRIVIA_SEG - (ahora - ultimo)
        if restante > 0:
            return await ctx.send(f"⏳ Espera {int(restante)}s antes de jugar trivia otra vez.")

        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        pregunta = random.choice(TRIVIA_PREGUNTAS)
        opciones = list(enumerate(pregunta["opciones"]))
        letras = ["🇦", "🇧", "🇨", "🇩"]

        embed = discord.Embed(
            title="🧠 Trivia Venezuela",
            description=pregunta["pregunta"] + "\n\n" + "\n".join(
                f"{letras[i]} {op}" for i, op in opciones
            ),
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Reacciona con la letra correcta en 15 segundos.")
        msg = await ctx.send(embed=embed)
        for letra in letras[:len(pregunta["opciones"])]:
            await msg.add_reaction(letra)

        self._ultimo_trivia[ctx.author.id] = ahora

        def check(reaction, user):
            return (
                user.id == ctx.author.id
                and reaction.message.id == msg.id
                and str(reaction.emoji) in letras
            )

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=15.0, check=check)
        except asyncio.TimeoutError:
            return await ctx.send(f"⏰ Se acabó el tiempo. La respuesta era **{pregunta['opciones'][pregunta['correcta']]}**.")

        elegida = letras.index(str(reaction.emoji))
        if elegida == pregunta["correcta"]:
            await db.update("personajes", str(ctx.author.id), {"dinero": round(datos.get("dinero", 0) + RECOMPENSA_TRIVIA, 2)})
            await ctx.send(f"✅ ¡Correcto! **{datos['nombre']}** gana ${RECOMPENSA_TRIVIA:,.2f}.")
        else:
            await ctx.send(f"❌ Incorrecto. La respuesta era **{pregunta['opciones'][pregunta['correcta']]}**.")

    # ── !duelo_reaccion ──────────────────────────────────────────────────────
    @commands.command(name="duelo_reaccion", aliases=["duelo"])
    async def duelo_reaccion(self, ctx, oponente: discord.Member, apuesta: float = 0.0):
        """Reta a otro jugador a un duelo de reacción. Apuesta opcional (0 = solo por diversión)."""
        if oponente.id == ctx.author.id:
            return await ctx.send("❌ No puedes retarte a ti mismo.")
        if oponente.bot:
            return await ctx.send("❌ No puedes retar a un bot.")

        datos_a = await db.get("personajes", str(ctx.author.id))
        datos_b = await db.get("personajes", str(oponente.id))
        if not datos_a:
            return await ctx.send("❌ Sin personaje.")
        if not datos_b:
            return await ctx.send(f"❌ {oponente.display_name} no tiene personaje.")

        if apuesta < 0:
            return await ctx.send("❌ Apuesta inválida.")
        if apuesta > 0:
            if datos_a.get("dinero", 0) < apuesta:
                return await ctx.send(f"❌ No tienes ${apuesta:,.2f}.")
            if datos_b.get("dinero", 0) < apuesta:
                return await ctx.send(f"❌ {oponente.display_name} no tiene ${apuesta:,.2f}.")

        aviso = f"⚡ {oponente.mention}, {ctx.author.mention} te reta a un duelo de reacción" + (f" por **${apuesta:,.2f}**" if apuesta > 0 else "") + ".\nCuando aparezca el botón verde, sé el primero en presionarlo. ¡Si presionas antes de tiempo, pierdes automáticamente!"
        await ctx.send(aviso)

        view = DueloReaccionView(ctx.author, oponente)
        msg = await ctx.send("🔴 Prepárense...", view=view)

        await asyncio.sleep(random.uniform(2.5, 6.0))
        if view.terminado:
            # alguien presionó antes de tiempo
            perdedor = view.perdedor_por_salida_falsa
            ganador = view.ganador
            await msg.edit(content=f"❌ **{perdedor.display_name}** presionó antes de tiempo. ¡**{ganador.display_name}** gana por default!")
        else:
            view.habilitado = True
            await msg.edit(content="🟢 **¡YA!**", view=view)
            await view.wait()

            if not view.ganador:
                await msg.edit(content="⏰ Nadie presionó a tiempo. Duelo cancelado.")
                return

            ganador = view.ganador
            perdedor = oponente if ganador.id == ctx.author.id else ctx.author

        if apuesta > 0:
            datos_ganador = await db.get("personajes", str(ganador.id))
            datos_perdedor = await db.get("personajes", str(perdedor.id))
            await db.update("personajes", str(ganador.id), {"dinero": round(datos_ganador.get("dinero", 0) + apuesta, 2)})
            await db.update("personajes", str(perdedor.id), {"dinero": round(datos_perdedor.get("dinero", 0) - apuesta, 2)})
            await ctx.send(f"🏆 **{ganador.display_name}** gana el duelo y se lleva **${apuesta:,.2f}** de {perdedor.display_name}.")
        else:
            await ctx.send(f"🏆 **{ganador.display_name}** gana el duelo (sin apuesta).")


async def setup(bot):
    await bot.add_cog(Minijuegos(bot))
