"""
cogs/banco.py — Sistema bancario: depósitos, retiros, inversiones, hackeo.
"""
import discord
from discord.ext import commands, tasks
import random
import asyncio
import time
from utils import db
from utils.inventario import tiene_telefono

BANCOS = {
    "banco-central-venezuela": {"nombre":"Banco Central de Venezuela","interes_anual":0.05,"comision":0.01},
    "banco-mercantil":         {"nombre":"Banco Mercantil","interes_anual":0.06,"comision":0.015},
    "banco-venezolano-credito":{"nombre":"Banco Venezolano de Crédito","interes_anual":0.04,"comision":0.008},
    "banco-banesco":           {"nombre":"Banesco","interes_anual":0.055,"comision":0.01},
}

# App móvil: cada banco tiene su propia "app" con su marca/colores, como en la vida real.
BANCOS_APP = {
    "banco-central-venezuela": {"app_nombre": "BCV Móvil",        "emoji": "🏛️", "color": 0x8B0000},
    "banco-mercantil":         {"app_nombre": "Mercantil Móvil",  "emoji": "🟠", "color": 0xFF6600},
    "banco-venezolano-credito":{"app_nombre": "BVC en Línea",     "emoji": "🔵", "color": 0x003366},
    "banco-banesco":           {"app_nombre": "BanescoMóvil",     "emoji": "🟢", "color": 0x00A650},
}

INVERSIONES = {
    "petroleo":    {"riesgo": "bajo",  "retorno_min": 0.05, "retorno_max": 0.15, "duracion_horas": 48},
    "crypto":      {"riesgo": "alto",  "retorno_min": -0.40,"retorno_max": 1.50, "duracion_horas": 24},
    "inmuebles":   {"riesgo": "bajo",  "retorno_min": 0.03, "retorno_max": 0.08, "duracion_horas": 72},
    "mercado_negro":{"riesgo":"extremo","retorno_min":-0.80,"retorno_max": 3.00, "duracion_horas": 12},
    "bonos":       {"riesgo": "bajo",  "retorno_min": 0.02, "retorno_max": 0.06, "duracion_horas": 96},
}

class Banco(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pagar_intereses.start()
        self.resolver_inversiones.start()

    def start_tasks(self):
        if not self.pagar_intereses.is_running():
            self.pagar_intereses.start()
        if not self.resolver_inversiones.is_running():
            self.resolver_inversiones.start()

    @tasks.loop(hours=24)
    async def pagar_intereses(self):
        """Paga intereses diarios a cuentas bancarias."""
        cuentas = await db.all("cuentas_banco")
        for uid, cuenta in cuentas.items():
            saldo = cuenta.get("saldo", 0)
            banco_key = cuenta.get("banco", "banco-central-venezuela")
            banco_info = BANCOS.get(banco_key, {})
            interes_diario = banco_info.get("interes_anual", 0.05) / 365
            ganancia = round(saldo * interes_diario, 2)
            if ganancia > 0:
                cuenta["saldo"] = round(saldo + ganancia, 2)
                await db.set("cuentas_banco", uid, cuenta)

    @tasks.loop(minutes=30)
    async def resolver_inversiones(self):
        """Resuelve inversiones que han madurado."""
        inversiones = await db.all("inversiones")
        now = time.time()
        for inv_id, inv in list(inversiones.items()):
            if now < inv.get("vence_ts", float("inf")):
                continue

            tipo = inv.get("tipo")
            monto = inv.get("monto", 0)
            user_id = inv.get("user_id")
            inv_info = INVERSIONES.get(tipo, {})

            retorno = random.uniform(inv_info.get("retorno_min",0), inv_info.get("retorno_max",0.1))
            ganancia = round(monto * retorno, 2)
            total = round(monto + ganancia, 2)

            # Pagar a cuenta bancaria o efectivo
            cuenta = await db.get("cuentas_banco", str(user_id))
            if cuenta:
                cuenta["saldo"] = round(cuenta["saldo"] + total, 2)
                await db.set("cuentas_banco", str(user_id), cuenta)
            else:
                datos = await db.get("personajes", str(user_id))
                if datos:
                    await db.update("personajes", str(user_id), {
                        "dinero": round(datos.get("dinero",0) + total, 2)
                    })

            # Notificar
            guild = self.bot.guilds[0] if self.bot.guilds else None
            if guild:
                member = guild.get_member(int(user_id))
                if member:
                    color = discord.Color.green() if ganancia >= 0 else discord.Color.red()
                    embed = discord.Embed(
                        title="📈 Inversión resuelta",
                        color=color
                    )
                    embed.add_field(name="Tipo", value=tipo, inline=True)
                    embed.add_field(name="Invertido", value=f"${monto:.2f}", inline=True)
                    embed.add_field(name="Retorno", value=f"{'+'if ganancia>=0 else ''}{ganancia:.2f} ({retorno*100:.1f}%)", inline=True)
                    embed.add_field(name="Total recibido", value=f"${total:.2f}", inline=True)
                    try:
                        await member.send(embed=embed)
                    except:
                        pass

            await db.delete("inversiones", inv_id)

    async def _obtener_o_crear_cuenta(self, user_id: int, banco_canal: str) -> dict:
        """Obtiene o crea cuenta bancaria."""
        cuenta = await db.get("cuentas_banco", str(user_id))
        if not cuenta:
            cuenta = {
                "user_id": user_id,
                "saldo": 0.0,
                "banco": banco_canal,
                "creada_ts": time.time(),
                "transacciones": [],
            }
            await db.set("cuentas_banco", str(user_id), cuenta)
        return cuenta

    @commands.command(name="depositar")
    async def depositar(self, ctx, monto: float):
        """Deposita dinero en el banco."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        canal_actual = datos.get("canal_actual", "")
        banco = next((k for k in BANCOS if k in canal_actual), None)
        if not banco:
            return await ctx.send("❌ Debes estar en un banco para depositar.")

        if monto <= 0:
            return await ctx.send("❌ Monto inválido.")

        dinero = datos.get("dinero", 0)
        if dinero < monto:
            return await ctx.send(f"❌ No tienes ${monto:.2f}. Tienes ${dinero:.2f}.")

        cuenta = await self._obtener_o_crear_cuenta(ctx.author.id, banco)
        banco_info = BANCOS[banco]
        comision = round(monto * banco_info["comision"], 2)
        monto_neto = round(monto - comision, 2)

        cuenta["saldo"] = round(cuenta["saldo"] + monto_neto, 2)
        cuenta["transacciones"].append({"tipo":"deposito","monto":monto_neto,"ts":time.time()})
        cuenta["transacciones"] = cuenta["transacciones"][-20:]  # últimas 20

        await db.set("cuentas_banco", str(ctx.author.id), cuenta)
        await db.update("personajes", str(ctx.author.id), {"dinero": round(dinero - monto, 2)})

        embed = discord.Embed(title="🏦 Depósito realizado", color=discord.Color.green())
        embed.add_field(name="Depositado", value=f"${monto:.2f}", inline=True)
        embed.add_field(name="Comisión", value=f"${comision:.2f}", inline=True)
        embed.add_field(name="Neto", value=f"${monto_neto:.2f}", inline=True)
        embed.add_field(name="Saldo bancario", value=f"${cuenta['saldo']:.2f}", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="retirar")
    async def retirar(self, ctx, monto: float):
        """Retira dinero del banco."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        canal_actual = datos.get("canal_actual", "")
        banco = next((k for k in BANCOS if k in canal_actual), None)
        if not banco:
            return await ctx.send("❌ Debes estar en un banco para retirar.")

        if monto <= 0:
            return await ctx.send("❌ Monto inválido.")

        cuenta = await db.get("cuentas_banco", str(ctx.author.id))
        if not cuenta or cuenta.get("saldo", 0) < monto:
            saldo = cuenta.get("saldo",0) if cuenta else 0
            return await ctx.send(f"❌ Saldo insuficiente. Tienes ${saldo:.2f}.")

        cuenta["saldo"] = round(cuenta["saldo"] - monto, 2)
        cuenta["transacciones"].append({"tipo":"retiro","monto":monto,"ts":time.time()})
        await db.set("cuentas_banco", str(ctx.author.id), cuenta)

        dinero = datos.get("dinero", 0)
        await db.update("personajes", str(ctx.author.id), {"dinero": round(dinero + monto, 2)})

        await ctx.send(f"💵 Retiraste **${monto:.2f}**. Efectivo: ${dinero+monto:.2f} | Banco: ${cuenta['saldo']:.2f}")

    @commands.command(name="saldo_banco", aliases=["banco"])
    async def saldo_banco(self, ctx):
        """Muestra tu saldo bancario."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        cuenta = await db.get("cuentas_banco", str(ctx.author.id))
        embed = discord.Embed(title="🏦 Estado de Cuenta", color=discord.Color.gold())
        embed.add_field(name="💵 Efectivo", value=f"${datos.get('dinero',0):.2f}", inline=True)
        if cuenta:
            embed.add_field(name="🏦 Saldo Bancario", value=f"${cuenta.get('saldo',0):.2f}", inline=True)
            embed.add_field(name="Banco", value=BANCOS.get(cuenta.get('banco',''),'banco')['nombre'] if cuenta.get('banco') in BANCOS else "?", inline=True)
            total = datos.get("dinero",0) + cuenta.get("saldo",0)
            embed.add_field(name="💰 Total", value=f"${total:.2f}", inline=True)
        else:
            embed.add_field(name="🏦 Cuenta", value="Sin cuenta bancaria. Ve a un banco.", inline=True)
        embed.add_field(name="💸 Deudas", value=f"${datos.get('deudas',0):.2f}", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="invertir")
    async def invertir(self, ctx, tipo: str, monto: float):
        """Realiza una inversión. Tipos: petroleo, crypto, inmuebles, mercado_negro, bonos"""
        if tipo not in INVERSIONES:
            return await ctx.send(f"❌ Tipo inválido. Usa: {', '.join(INVERSIONES.keys())}")

        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        cuenta = await db.get("cuentas_banco", str(ctx.author.id))
        saldo_banco = cuenta.get("saldo",0) if cuenta else 0
        dinero_efectivo = datos.get("dinero", 0)

        # Pagar desde banco primero, luego efectivo
        if saldo_banco >= monto:
            cuenta["saldo"] = round(saldo_banco - monto, 2)
            await db.set("cuentas_banco", str(ctx.author.id), cuenta)
        elif dinero_efectivo >= monto:
            await db.update("personajes", str(ctx.author.id), {"dinero": round(dinero_efectivo - monto, 2)})
        else:
            total = saldo_banco + dinero_efectivo
            return await ctx.send(f"❌ No tienes suficiente. Necesitas ${monto:.2f}, tienes ${total:.2f}.")

        inv_info = INVERSIONES[tipo]
        import uuid
        inv_id = str(uuid.uuid4())[:8]
        await db.set("inversiones", inv_id, {
            "user_id": ctx.author.id,
            "tipo": tipo,
            "monto": monto,
            "vence_ts": time.time() + inv_info["duracion_horas"] * 3600,
        })

        embed = discord.Embed(title="📈 Inversión realizada", color=discord.Color.blurple())
        embed.add_field(name="Tipo", value=tipo, inline=True)
        embed.add_field(name="Monto", value=f"${monto:.2f}", inline=True)
        embed.add_field(name="Riesgo", value=inv_info["riesgo"].upper(), inline=True)
        embed.add_field(name="Duración", value=f"{inv_info['duracion_horas']}h", inline=True)
        embed.add_field(name="Retorno posible", value=f"{inv_info['retorno_min']*100:.0f}% a {inv_info['retorno_max']*100:.0f}%", inline=True)
        embed.set_footer(text="Serás notificado cuando venza la inversión.")
        await ctx.send(embed=embed)

    @commands.command(name="hackear_banco")
    async def hackear_banco(self, ctx, objetivo: discord.Member):
        """Intenta hackear la cuenta bancaria de otro personaje. (Muy difícil)"""
        datos_h = await db.get("personajes", str(ctx.author.id))
        datos_v = await db.get("personajes", str(objetivo.id))

        if not datos_h or not datos_v:
            return await ctx.send("❌ Sin personaje.")

        inteligencia = datos_h.get("stats",{}).get("inteligencia", 5)
        prob_exito = (inteligencia - 5) / 20  # máx ~50% con int=15

        if random.random() > max(0.02, prob_exito):
            await ctx.send("❌ Hackeo fallido. La seguridad del banco es robusta.")
            # Notificar a la víctima
            try:
                await objetivo.send(f"⚠️ Alguien intentó hackear tu cuenta bancaria. Estás a salvo.")
            except:
                pass
            return

        cuenta_v = await db.get("cuentas_banco", str(objetivo.id))
        if not cuenta_v or cuenta_v.get("saldo",0) <= 0:
            return await ctx.send("❌ Hackeo exitoso, pero la víctima no tiene saldo bancario.")

        # Robar entre 10% y 30%
        porcentaje = random.uniform(0.10, 0.30)
        robado = round(cuenta_v["saldo"] * porcentaje, 2)
        cuenta_v["saldo"] = round(cuenta_v["saldo"] - robado, 2)
        await db.set("cuentas_banco", str(objetivo.id), cuenta_v)

        cuenta_h = await self._obtener_o_crear_cuenta(ctx.author.id, "banco-central-venezuela")
        cuenta_h["saldo"] = round(cuenta_h["saldo"] + robado, 2)
        await db.set("cuentas_banco", str(ctx.author.id), cuenta_h)

        await ctx.send(f"💻 ¡Hackeo exitoso! Robaste **${robado:.2f}** de la cuenta de {datos_v['nombre']}.")
        try:
            await objetivo.send(f"🚨 ¡Tu cuenta fue hackeada! Perdiste **${robado:.2f}**.")
        except:
            pass

    @commands.command(name="historial_banco")
    async def historial_banco(self, ctx):
        """Muestra las últimas transacciones bancarias."""
        cuenta = await db.get("cuentas_banco", str(ctx.author.id))
        if not cuenta:
            return await ctx.send("❌ Sin cuenta bancaria.")

        transacciones = cuenta.get("transacciones", [])[-10:]
        if not transacciones:
            return await ctx.send("Sin transacciones registradas.")

        embed = discord.Embed(title="📋 Historial Bancario", color=discord.Color.gold())
        for t in reversed(transacciones):
            tipo = t.get("tipo","?")
            monto = t.get("monto",0)
            signo = "+" if tipo == "deposito" else "-"
            color_txt = "🟢" if tipo == "deposito" else "🔴"
            embed.add_field(
                name=f"{color_txt} {tipo.title()}",
                value=f"{signo}${monto:.2f}",
                inline=True
            )
        await ctx.send(embed=embed)

    # ── !banco_app — app móvil, la marca depende de tu banco ────────────────
    @commands.command(name="banco_app", aliases=["app_banco"])
    async def banco_app(self, ctx):
        """Abre la app de tu banco desde el teléfono. La app que ves depende de dónde tengas tu cuenta."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        if not tiene_telefono(datos):
            return await ctx.send("❌ Necesitas un teléfono para abrir esta app. Cómprate uno en la tienda (`smartphone`).")

        cuenta = await db.get("cuentas_banco", str(ctx.author.id))
        if not cuenta:
            return await ctx.send("❌ No tienes cuenta bancaria todavía. Ve a un banco y usa `!depositar` para abrir una.")

        banco_key = cuenta.get("banco", "banco-central-venezuela")
        app_info = BANCOS_APP.get(banco_key, BANCOS_APP["banco-central-venezuela"])
        banco_info = BANCOS.get(banco_key, {})

        embed = discord.Embed(
            title=f"{app_info['emoji']} {app_info['app_nombre']}",
            description=f"Cuenta de **{banco_info.get('nombre', banco_key)}**",
            color=app_info["color"]
        )
        embed.add_field(name="💵 Efectivo", value=f"${datos.get('dinero', 0):,.2f}", inline=True)
        embed.add_field(name="🏦 Saldo en cuenta", value=f"${cuenta.get('saldo', 0):,.2f}", inline=True)
        embed.add_field(name="📈 Interés anual", value=f"{banco_info.get('interes_anual', 0)*100:.1f}%", inline=True)

        ultimos = cuenta.get("transacciones", [])[-3:]
        if ultimos:
            resumen = "\n".join(
                f"{'🟢' if t.get('tipo') in ('deposito','transferencia_recibida') else '🔴'} "
                f"{t.get('tipo','?').replace('_',' ').title()}: ${t.get('monto',0):,.2f}"
                for t in reversed(ultimos)
            )
            embed.add_field(name="📋 Últimos movimientos", value=resumen, inline=False)

        embed.set_footer(text="📱 Usa !transferir_banco <@usuario> <monto> para enviar dinero desde aquí, sin ir al banco.")
        await ctx.send(embed=embed)

    # ── !transferir_banco — transferencia bancaria remota (solo con la app) ─
    @commands.command(name="transferir_banco", aliases=["transferencia_bancaria"])
    async def transferir_banco(self, ctx, destinatario: discord.Member, monto: float):
        """Transfiere dinero de TU cuenta bancaria a la de otro jugador, desde el teléfono (no necesitas ir al banco)."""
        if destinatario.id == ctx.author.id:
            return await ctx.send("❌ No puedes transferirte a ti mismo.")
        if monto <= 0:
            return await ctx.send("❌ Monto inválido.")

        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        if not tiene_telefono(datos):
            return await ctx.send("❌ Necesitas un teléfono para usar la app del banco.")

        datos_dest = await db.get("personajes", str(destinatario.id))
        if not datos_dest:
            return await ctx.send(f"❌ {destinatario.display_name} no tiene personaje.")

        cuenta = await db.get("cuentas_banco", str(ctx.author.id))
        if not cuenta or cuenta.get("saldo", 0) < monto:
            saldo = cuenta.get("saldo", 0) if cuenta else 0
            return await ctx.send(f"❌ Saldo insuficiente en tu cuenta. Tienes ${saldo:,.2f}.")

        banco_info = BANCOS.get(cuenta.get("banco", "banco-central-venezuela"), {})
        comision = round(monto * banco_info.get("comision", 0.01), 2)
        monto_neto = round(monto - comision, 2)

        cuenta["saldo"] = round(cuenta["saldo"] - monto, 2)
        cuenta.setdefault("transacciones", []).append({"tipo": "transferencia_enviada", "monto": monto, "ts": time.time()})
        cuenta["transacciones"] = cuenta["transacciones"][-20:]
        await db.set("cuentas_banco", str(ctx.author.id), cuenta)

        cuenta_dest = await self._obtener_o_crear_cuenta(destinatario.id, cuenta.get("banco", "banco-central-venezuela"))
        cuenta_dest["saldo"] = round(cuenta_dest["saldo"] + monto_neto, 2)
        cuenta_dest.setdefault("transacciones", []).append({"tipo": "transferencia_recibida", "monto": monto_neto, "ts": time.time()})
        cuenta_dest["transacciones"] = cuenta_dest["transacciones"][-20:]
        await db.set("cuentas_banco", str(destinatario.id), cuenta_dest)

        app_info = BANCOS_APP.get(cuenta.get("banco", "banco-central-venezuela"), BANCOS_APP["banco-central-venezuela"])
        embed = discord.Embed(
            title=f"{app_info['emoji']} Transferencia enviada",
            description=f"**${monto:,.2f}** a **{datos_dest['nombre']}**",
            color=app_info["color"]
        )
        embed.add_field(name="Comisión", value=f"${comision:,.2f}", inline=True)
        embed.add_field(name="Recibido por el destinatario", value=f"${monto_neto:,.2f}", inline=True)
        embed.add_field(name="Tu saldo restante", value=f"${cuenta['saldo']:,.2f}", inline=True)
        await ctx.send(embed=embed)
        try:
            await destinatario.send(f"💸 Recibiste **${monto_neto:,.2f}** por transferencia bancaria de **{datos['nombre']}**.")
        except Exception:
            pass

async def setup(bot):
    await bot.add_cog(Banco(bot))