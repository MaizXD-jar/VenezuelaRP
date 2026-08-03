"""
cogs/hospital.py — Sistema de hospital para tratar lesiones.

Las lesiones se generan en cogs/combate.py cuando alguien "cae" en una pelea
o tiroteo. Aquí se muestran, se tratan (pagando, en el hospital) o se dejan
sanar solas con el tiempo — con riesgo de muerte si son graves y nunca se
atienden (ver utils/lesiones.py).
"""
import time

import discord
from discord.ext import commands, tasks

from utils import db
from utils import lesiones as lesiones_mod

CANALES_HOSPITAL = ["hospital", "clinica", "emergencia", "ambulatorio", "medic"]
COSTO_INGRESO = 50.0


def _en_hospital(canal_actual: str) -> bool:
    return any(h in canal_actual for h in CANALES_HOSPITAL)


class Hospital(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def start_tasks(self):
        if not self.revisar_lesiones.is_running():
            self.revisar_lesiones.start()

    @tasks.loop(hours=1)
    async def revisar_lesiones(self):
        await lesiones_mod.resolver_vencidas(self.bot)

    # ── !lesiones ────────────────────────────────────────────────────────────
    @commands.command(name="lesiones", aliases=["mis_lesiones", "estado_medico"])
    async def lesiones_cmd(self, ctx, objetivo: discord.Member = None):
        objetivo = objetivo or ctx.author
        datos = await db.get("personajes", str(objetivo.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        activas = await lesiones_mod.lesiones_activas(objetivo.id)
        if not activas:
            return await ctx.send(f"✅ **{datos['nombre']}** no tiene lesiones activas.")

        embed = discord.Embed(title=f"🩹 Lesiones de {datos['nombre']}", color=discord.Color.orange())
        for lesion in activas:
            info = lesiones_mod.LESIONES_TIPOS.get(lesion["tipo"], {})
            restante_h = max(0, (lesion.get("vence_ts", 0) - time.time()) / 3600)
            penal_txt = ", ".join(f"{k} {v:+d}" for k, v in info.get("penalizacion", {}).items())
            riesgo_txt = " ⚠️ riesgo de muerte si no se atiende" if info.get("riesgo_muerte_sin_tratar") else ""
            embed.add_field(
                name=f"{info.get('display', lesion['tipo'])}{riesgo_txt}",
                value=f"Penalización: {penal_txt}\nSana sola en ~{restante_h:.1f}h | Tratamiento: ${info.get('costo_tratamiento',0):,.0f} (en hospital)",
                inline=False
            )
        embed.set_footer(text="!ir_hospital — ingresar para sanar más rápido | !tratar_lesion <tipo> — curar una ya")
        await ctx.send(embed=embed)

    # ── !ir_hospital ─────────────────────────────────────────────────────────
    @commands.command(name="ir_hospital")
    async def ir_hospital(self, ctx):
        """Ingresa al hospital: paga una consulta y reduce a la mitad el tiempo
        restante de todas tus lesiones activas."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        canal_actual = datos.get("canal_actual", "")
        if not _en_hospital(canal_actual):
            return await ctx.send("❌ Debes estar en un hospital/clínica. Viaja ahí con `/viajar`.")

        activas = await lesiones_mod.lesiones_activas(ctx.author.id)
        if not activas:
            return await ctx.send(f"✅ **{datos['nombre']}** no tiene lesiones que tratar.")

        dinero = datos.get("dinero", 0)
        if dinero < COSTO_INGRESO:
            return await ctx.send(f"❌ La consulta cuesta ${COSTO_INGRESO:,.0f}, tienes ${dinero:,.2f}.")

        await db.update("personajes", str(ctx.author.id), {"dinero": round(dinero - COSTO_INGRESO, 2)})
        await lesiones_mod.acortar_lesiones(ctx.author.id, factor=0.5)

        embed = discord.Embed(
            title="🏥 Ingreso hospitalario",
            description=f"**{datos['nombre']}** recibió atención médica. El tiempo de recuperación de todas sus lesiones se redujo a la mitad.",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Consulta: ${COSTO_INGRESO:,.0f} | Usa !lesiones para ver el tiempo restante")
        await ctx.send(embed=embed)

    # ── !tratar_lesion ───────────────────────────────────────────────────────
    @commands.command(name="tratar_lesion")
    async def tratar_lesion(self, ctx, tipo: str):
        """Paga para curar UNA lesión específica al instante. Debes estar en el hospital."""
        tipo = tipo.lower().replace(" ", "_")
        if tipo not in lesiones_mod.LESIONES_TIPOS:
            tipos_txt = ", ".join(f"`{t}`" for t in lesiones_mod.LESIONES_TIPOS)
            return await ctx.send(f"❌ Tipo inválido. Usa: {tipos_txt}")

        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        canal_actual = datos.get("canal_actual", "")
        if not _en_hospital(canal_actual):
            return await ctx.send("❌ Debes estar en un hospital/clínica para recibir tratamiento.")

        activas = await lesiones_mod.lesiones_activas(ctx.author.id)
        if not any(l["tipo"] == tipo for l in activas):
            return await ctx.send(f"❌ No tienes una lesión activa de tipo `{tipo}`.")

        info = lesiones_mod.LESIONES_TIPOS[tipo]
        costo = info["costo_tratamiento"]
        dinero = datos.get("dinero", 0)
        if dinero < costo:
            return await ctx.send(f"❌ El tratamiento cuesta ${costo:,.0f}, tienes ${dinero:,.2f}.")

        await db.update("personajes", str(ctx.author.id), {"dinero": round(dinero - costo, 2)})
        await lesiones_mod.curar_lesion(ctx.author.id, tipo)

        embed = discord.Embed(
            title="🏥 Tratamiento exitoso",
            description=f"**{datos['nombre']}** fue tratado/a de **{info['display']}**.",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Costo: ${costo:,.0f}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Hospital(bot))
