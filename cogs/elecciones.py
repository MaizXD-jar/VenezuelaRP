"""
cogs/elecciones.py — Elecciones presidenciales del RP, cada 4 semanas de juego.

Son elecciones CORRUPTAS por diseño: hay compra de votos, ventaja del oficialismo,
manipulación del conteo y candidatos que pueden sobornar. El objetivo es que la
política del servidor sea un juego de poder, no una simulación limpia.

Los candidatos son FICTICIOS (personajes propios del servidor). El bot no simula
ni pone declaraciones en boca de políticos reales.
"""
import random

import discord
from discord.ext import commands, tasks
from discord import app_commands

from utils import db
from utils import tiempo_juego

SEMANAS_ENTRE_ELECCIONES = 4
COSTO_CANDIDATURA = 5_000.0
COSTO_COMPRAR_VOTO = 150.0
COSTO_SOBORNO_CNE = 25_000.0

# Candidatos ficticios por defecto (el servidor puede añadir jugadores como candidatos)
CANDIDATOS_NPC = [
    {"id": "npc_oficialismo", "nombre": "Aurelio Bermúdez", "partido": "Frente Patriótico Unido",
     "tipo": "oficialismo", "lema": "Continuidad y estabilidad"},
    {"id": "npc_oposicion", "nombre": "Marisela Contreras", "partido": "Alianza Democrática Nacional",
     "tipo": "oposicion", "lema": "Cambio ya"},
    {"id": "npc_independiente", "nombre": "Régulo Pacheco", "partido": "Movimiento Popular Independiente",
     "tipo": "independiente", "lema": "Ni contigo ni con ellos"},
]

VENTAJA_OFICIALISMO = 0.18  # sesgo estructural a favor de quien ya gobierna


async def _estado_electoral() -> dict:
    return await db.get("estado", "elecciones") or {
        "abiertas": False, "semana_ultima": -SEMANAS_ENTRE_ELECCIONES,
        "candidatos": {}, "votos": {}, "sobornos": {},
    }


async def _guardar(estado: dict):
    await db.set("estado", "elecciones", estado)


class Elecciones(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def start_tasks(self):
        if not self.ciclo_electoral.is_running():
            self.ciclo_electoral.start()

    @tasks.loop(minutes=30)
    async def ciclo_electoral(self):
        """Cada 4 semanas del rol: abre elecciones. Una semana después, las cierra."""
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return
        estado = await _estado_electoral()
        semana = await tiempo_juego.semanas_transcurridas()

        if not estado.get("abiertas"):
            if semana - estado.get("semana_ultima", -99) >= SEMANAS_ENTRE_ELECCIONES:
                await self._abrir(guild, estado, semana)
        else:
            if semana - estado.get("semana_apertura", semana) >= 1:
                await self._cerrar(guild, estado, semana)

    async def _canal_noticias(self, guild):
        from cogs.noticias_ia import CH_NOTICIAS_VZ1
        return guild.get_channel(CH_NOTICIAS_VZ1)

    async def _abrir(self, guild, estado, semana):
        candidatos = {c["id"]: dict(c, votos=0) for c in CANDIDATOS_NPC}
        estado.update({
            "abiertas": True, "semana_apertura": semana,
            "candidatos": candidatos, "votos": {}, "sobornos": {},
        })
        await _guardar(estado)

        gobierno = await db.get("estado", "gobierno_actual")
        embed = discord.Embed(
            title="🗳️ CONVOCATORIA A ELECCIONES PRESIDENCIALES",
            description=(
                f"El Consejo Electoral convoca elecciones. La votación permanece abierta "
                f"**una semana del rol**.\n\n"
                + "\n".join(f"**{c['nombre']}** — *{c['partido']}*\n_{c['lema']}_"
                            for c in CANDIDATOS_NPC)
            ),
            color=discord.Color.gold()
        )
        if gobierno:
            embed.add_field(name="Gobierno saliente",
                            value=f"{gobierno.get('presidente','?')} ({gobierno.get('partido','?')})",
                            inline=False)
        embed.add_field(name="Cómo participar",
                        value="`/votar` — emitir tu voto\n"
                              "`/candidatura` — presentarte como candidato\n"
                              "`/comprar_votos` — (ilegal) comprar apoyo\n"
                              "`/sobornar_cne` — (ilegal) inclinar el conteo",
                        inline=False)
        embed.set_footer(text=await tiempo_juego.fecha_texto())

        canal = await self._canal_noticias(guild)
        if canal:
            try:
                await canal.send(embed=embed)
            except Exception:
                pass

    async def _cerrar(self, guild, estado, semana):
        candidatos = estado.get("candidatos", {})
        if not candidatos:
            estado["abiertas"] = False
            estado["semana_ultima"] = semana
            await _guardar(estado)
            return

        gobierno = await db.get("estado", "gobierno_actual") or {}
        partido_gobierno = gobierno.get("partido")
        sobornos = estado.get("sobornos", {})

        # Conteo "oficial": votos reales + ventaja del oficialismo + sobornos + ruido
        resultados = {}
        for cid, c in candidatos.items():
            base = c.get("votos", 0)
            base += random.randint(80, 400)  # "votos" de NPCs / padrón inflado
            if partido_gobierno and c.get("partido") == partido_gobierno:
                base = int(base * (1 + VENTAJA_OFICIALISMO))
            if c.get("tipo") == "oficialismo" and not partido_gobierno:
                base = int(base * (1 + VENTAJA_OFICIALISMO))
            base += int(sobornos.get(cid, 0) / COSTO_SOBORNO_CNE * 250)
            resultados[cid] = max(0, base)

        total = sum(resultados.values()) or 1
        ganador_id = max(resultados, key=resultados.get)
        ganador = candidatos[ganador_id]

        irregularidades = []
        if sobornos:
            irregularidades.append("denuncias de compra de actas en varios centros")
        if partido_gobierno:
            irregularidades.append("uso de recursos públicos en campaña")
        if random.random() < 0.6:
            irregularidades.append(random.choice([
                "retraso inexplicado en la transmisión de resultados",
                "centros de votación cerrados antes de hora",
                "observadores internacionales sin acceso al conteo",
            ]))

        await db.set("estado", "gobierno_actual", {
            "presidente": ganador["nombre"],
            "partido": ganador["partido"],
            "desde_semana": semana,
            "elegido_con": round(resultados[ganador_id] / total * 100, 1),
        })

        estado["abiertas"] = False
        estado["semana_ultima"] = semana
        estado["ultimo_resultado"] = {
            "ganador": ganador["nombre"], "partido": ganador["partido"],
            "porcentajes": {candidatos[c]["nombre"]: round(v / total * 100, 1) for c, v in resultados.items()},
            "irregularidades": irregularidades,
        }
        await _guardar(estado)

        embed = discord.Embed(
            title="🗳️ RESULTADOS ELECTORALES OFICIALES",
            description=f"El Consejo Electoral proclama presidente a **{ganador['nombre']}** "
                        f"(*{ganador['partido']}*).",
            color=discord.Color.dark_gold()
        )
        for cid, v in sorted(resultados.items(), key=lambda x: -x[1]):
            pct = v / total * 100
            barra = "█" * int(pct / 5)
            embed.add_field(name=candidatos[cid]["nombre"],
                            value=f"{barra} **{pct:.1f}%** ({v:,} votos)", inline=False)
        if irregularidades:
            embed.add_field(name="⚠️ Irregularidades denunciadas",
                            value="\n".join(f"• {i}" for i in irregularidades), inline=False)
        embed.set_footer(text=f"{await tiempo_juego.fecha_texto()} · Próximas elecciones en {SEMANAS_ENTRE_ELECCIONES} semanas")

        canal = await self._canal_noticias(guild)
        if canal:
            try:
                await canal.send(embed=embed)
            except Exception:
                pass

    # ── /votar ───────────────────────────────────────────────────────────────
    @app_commands.command(name="votar", description="🗳️ Vota en las elecciones presidenciales")
    async def votar(self, interaction: discord.Interaction):
        estado = await _estado_electoral()
        if not estado.get("abiertas"):
            return await interaction.response.send_message(
                "❌ No hay elecciones abiertas ahora mismo. Usa `/estado_elecciones`.", ephemeral=True)

        datos = await db.get("personajes", str(interaction.user.id))
        if not datos:
            return await interaction.response.send_message("❌ No tienes personaje.", ephemeral=True)
        if datos.get("muerto"):
            return await interaction.response.send_message("❌ Los muertos no votan... oficialmente.", ephemeral=True)
        if datos.get("edad", 0) < 18:
            return await interaction.response.send_message("🔞 Debes tener 18 años en el rol para votar.", ephemeral=True)
        if str(interaction.user.id) in estado.get("votos", {}):
            return await interaction.response.send_message("❌ Ya votaste en estas elecciones.", ephemeral=True)

        opciones = [
            discord.SelectOption(label=c["nombre"], value=cid, description=c["partido"][:100])
            for cid, c in estado["candidatos"].items()
        ]

        class VotoView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @discord.ui.select(placeholder="Elige tu candidato", options=opciones)
            async def elegir(self, inter: discord.Interaction, select: discord.ui.Select):
                if inter.user.id != interaction.user.id:
                    return await inter.response.send_message("No es tu voto.", ephemeral=True)
                est = await _estado_electoral()
                if str(inter.user.id) in est.get("votos", {}):
                    return await inter.response.send_message("Ya votaste.", ephemeral=True)
                cid = select.values[0]
                est["candidatos"][cid]["votos"] = est["candidatos"][cid].get("votos", 0) + 1
                est.setdefault("votos", {})[str(inter.user.id)] = cid
                await _guardar(est)
                await inter.response.edit_message(
                    content=f"✅ Voto registrado para **{est['candidatos'][cid]['nombre']}**. "
                            f"Tu voto es secreto... en teoría.", view=None)

        await interaction.response.send_message("🗳️ Selecciona tu candidato:", view=VotoView(), ephemeral=True)

    # ── /candidatura ─────────────────────────────────────────────────────────
    @app_commands.command(name="candidatura", description="🗳️ Preséntate como candidato presidencial")
    @app_commands.describe(partido="Nombre de tu partido", lema="Tu lema de campaña")
    async def candidatura(self, interaction: discord.Interaction, partido: str, lema: str):
        estado = await _estado_electoral()
        if not estado.get("abiertas"):
            return await interaction.response.send_message("❌ No hay elecciones abiertas.", ephemeral=True)

        datos = await db.get("personajes", str(interaction.user.id))
        if not datos:
            return await interaction.response.send_message("❌ No tienes personaje.", ephemeral=True)
        if datos.get("edad", 0) < 30:
            return await interaction.response.send_message("❌ Hay que tener al menos 30 años para ser candidato.", ephemeral=True)
        cid = f"jugador_{interaction.user.id}"
        if cid in estado.get("candidatos", {}):
            return await interaction.response.send_message("❌ Ya eres candidato.", ephemeral=True)
        if datos.get("dinero", 0) < COSTO_CANDIDATURA:
            return await interaction.response.send_message(
                f"❌ Inscribir una candidatura cuesta ${COSTO_CANDIDATURA:,.0f}. "
                f"Tienes ${datos.get('dinero',0):,.2f}.", ephemeral=True)

        await db.update("personajes", str(interaction.user.id),
                        {"dinero": round(datos["dinero"] - COSTO_CANDIDATURA, 2)})
        estado["candidatos"][cid] = {
            "id": cid, "nombre": datos["nombre"], "partido": partido[:60],
            "tipo": "jugador", "lema": lema[:100], "votos": 0,
            "user_id": str(interaction.user.id),
        }
        await _guardar(estado)
        await interaction.response.send_message(
            f"✅ **{datos['nombre']}** es candidato presidencial por *{partido}*.\n_{lema}_")

    # ── /comprar_votos ───────────────────────────────────────────────────────
    @app_commands.command(name="comprar_votos", description="💰 [ILEGAL] Compra votos para tu candidatura")
    @app_commands.describe(cantidad="Cuántos votos comprar")
    async def comprar_votos(self, interaction: discord.Interaction, cantidad: int):
        estado = await _estado_electoral()
        if not estado.get("abiertas"):
            return await interaction.response.send_message("❌ No hay elecciones abiertas.", ephemeral=True)
        if cantidad < 1 or cantidad > 500:
            return await interaction.response.send_message("❌ Entre 1 y 500 votos.", ephemeral=True)

        cid = f"jugador_{interaction.user.id}"
        if cid not in estado.get("candidatos", {}):
            return await interaction.response.send_message("❌ No eres candidato. Usa `/candidatura` primero.", ephemeral=True)

        datos = await db.get("personajes", str(interaction.user.id))
        costo = cantidad * COSTO_COMPRAR_VOTO
        if datos.get("dinero", 0) < costo:
            return await interaction.response.send_message(
                f"❌ Comprar {cantidad} votos cuesta ${costo:,.0f}. Tienes ${datos.get('dinero',0):,.2f}.", ephemeral=True)

        await db.update("personajes", str(interaction.user.id), {"dinero": round(datos["dinero"] - costo, 2)})

        # Parte del dinero se lo quedan los intermediarios: no todos los votos llegan
        efectivos = int(cantidad * random.uniform(0.55, 0.9))
        estado["candidatos"][cid]["votos"] = estado["candidatos"][cid].get("votos", 0) + efectivos
        await _guardar(estado)

        pillado = random.random() < 0.25
        msg = (f"💰 Pagaste ${costo:,.0f}. De {cantidad} votos comprados, **{efectivos}** llegaron "
               f"realmente a la urna (el resto se lo quedaron los intermediarios).")
        if pillado:
            msg += "\n\n🚨 **Un periodista lo ha documentado.** Espera que salga en las noticias."
        await interaction.response.send_message(msg, ephemeral=True)

    # ── /sobornar_cne ────────────────────────────────────────────────────────
    @app_commands.command(name="sobornar_cne", description="💼 [ILEGAL] Inclina el conteo a tu favor")
    async def sobornar_cne(self, interaction: discord.Interaction):
        estado = await _estado_electoral()
        if not estado.get("abiertas"):
            return await interaction.response.send_message("❌ No hay elecciones abiertas.", ephemeral=True)

        cid = f"jugador_{interaction.user.id}"
        if cid not in estado.get("candidatos", {}):
            return await interaction.response.send_message("❌ No eres candidato.", ephemeral=True)

        datos = await db.get("personajes", str(interaction.user.id))
        if datos.get("dinero", 0) < COSTO_SOBORNO_CNE:
            return await interaction.response.send_message(
                f"❌ Eso cuesta ${COSTO_SOBORNO_CNE:,.0f}. Tienes ${datos.get('dinero',0):,.2f}.", ephemeral=True)

        await db.update("personajes", str(interaction.user.id), {"dinero": round(datos["dinero"] - COSTO_SOBORNO_CNE, 2)})
        estado.setdefault("sobornos", {})[cid] = estado.get("sobornos", {}).get(cid, 0) + COSTO_SOBORNO_CNE
        await _guardar(estado)

        await interaction.response.send_message(
            f"💼 Has entregado ${COSTO_SOBORNO_CNE:,.0f} a ciertos funcionarios del conteo. "
            f"Nadie promete nada por escrito, pero los números suelen mejorar.", ephemeral=True)

    # ── /estado_elecciones ───────────────────────────────────────────────────
    @app_commands.command(name="estado_elecciones", description="🗳️ Estado de las elecciones y del gobierno")
    async def estado_elecciones(self, interaction: discord.Interaction):
        estado = await _estado_electoral()
        semana = await tiempo_juego.semanas_transcurridas()
        gobierno = await db.get("estado", "gobierno_actual")

        embed = discord.Embed(title="🗳️ Situación política", color=discord.Color.gold())
        if gobierno:
            embed.add_field(
                name="🏛️ Gobierno actual",
                value=f"**{gobierno['presidente']}** ({gobierno['partido']})\n"
                      f"Proclamado con {gobierno.get('elegido_con','?')}% de los votos oficiales",
                inline=False)
        else:
            embed.add_field(name="🏛️ Gobierno actual", value="Aún no se ha celebrado ninguna elección.", inline=False)

        if estado.get("abiertas"):
            votos_emitidos = len(estado.get("votos", {}))
            embed.add_field(name="📊 Elecciones EN CURSO",
                            value=f"{votos_emitidos} votos de jugadores emitidos\n"
                                  f"Candidatos: {len(estado.get('candidatos', {}))}",
                            inline=False)
            for c in estado.get("candidatos", {}).values():
                embed.add_field(name=c["nombre"], value=f"*{c['partido']}*\n_{c.get('lema','')}_", inline=True)
        else:
            faltan = SEMANAS_ENTRE_ELECCIONES - (semana - estado.get("semana_ultima", 0))
            embed.add_field(name="📅 Próximas elecciones",
                            value=f"En ~{max(0, faltan)} semanas del rol", inline=False)

        ultimo = estado.get("ultimo_resultado")
        if ultimo and ultimo.get("irregularidades"):
            embed.add_field(name="⚠️ Última elección — irregularidades",
                            value="\n".join(f"• {i}" for i in ultimo["irregularidades"]), inline=False)

        embed.set_footer(text=await tiempo_juego.fecha_texto())
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Elecciones(bot))
