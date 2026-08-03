"""
cogs/empresas.py — Sistema de empresas.

Para fundar una empresa necesitas:
1. Capital de constitución (dinero en efectivo)
2. 1 oficina (activo comercial registrado en un sector — sin canal propio)
3. 1 sede (canal de Discord dedicado, tu "casa matriz")

Las empresas generan ingresos pasivos cada cierto tiempo, pagando impuesto
corporativo (varía según el tipo de empresa) que va directo al tesoro
nacional (utils/impuestos.py). El dueño puede retirar capital como
"dividendos", lo cual paga un impuesto aparte.
"""
import re
import time
import random
from typing import Optional

import discord
from discord.ext import commands, tasks

from utils import db
from utils import impuestos
from utils.mapa import SECTORES

# ── Configuración ────────────────────────────────────────────────────────────
CAPITAL_INICIAL_EMPRESA = 20_000.0
N_OFICINAS_POR_SECTOR = 5
N_SEDES_POR_SECTOR = 2

# Precio de oficinas/sedes según el nivel de peligro del sector (1=más seguro/caro, 5=más peligroso/barato)
PRECIOS_OFICINA = {1: 40_000, 2: 25_000, 3: 12_000, 4: 5_000, 5: 1_500}
PRECIOS_SEDE    = {1: 150_000, 2: 90_000, 3: 45_000, 4: 18_000, 5: 6_000}

TIPOS_EMPRESA = {
    "comercio":  {"display": "🛒 Comercio",   "ingreso_base": 800,  "riesgo": "bajo"},
    "industria": {"display": "🏭 Industria",  "ingreso_base": 1500, "riesgo": "medio"},
    "tech":      {"display": "💻 Tecnología", "ingreso_base": 2500, "riesgo": "alto"},
}


def _slug(texto: str) -> str:
    s = texto.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:32] or "empresa"


async def _inicializar_oficinas_sector(sector_key: str) -> dict:
    sector = SECTORES.get(sector_key, {})
    peligro = sector.get("peligro", 3)
    oficinas = await db.get("oficinas", sector_key) or {}
    for i in range(1, N_OFICINAS_POR_SECTOR + 1):
        oid = f"oficina-{i}"
        if oid not in oficinas:
            oficinas[oid] = {
                "id": oid, "sector": sector_key,
                "precio": PRECIOS_OFICINA.get(peligro, 10_000),
                "empresa_id": None,
            }
    await db.set("oficinas", sector_key, oficinas)
    return oficinas


async def _inicializar_sedes_sector(sector_key: str) -> dict:
    sector = SECTORES.get(sector_key, {})
    peligro = sector.get("peligro", 3)
    sedes = await db.get("sedes", sector_key) or {}
    for i in range(1, N_SEDES_POR_SECTOR + 1):
        sid = f"sede-{i}"
        if sid not in sedes:
            sedes[sid] = {
                "id": sid, "sector": sector_key,
                "precio": PRECIOS_SEDE.get(peligro, 40_000),
                "empresa_id": None,
                "canal_id": None,
            }
    await db.set("sedes", sector_key, sedes)
    return sedes


async def _empresa_de_usuario(user_id: int) -> tuple[Optional[str], Optional[dict]]:
    todas = await db.all("empresas")
    for eid, e in todas.items():
        if e.get("dueño") == str(user_id):
            return eid, e
    return None, None


class Empresas(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def start_tasks(self):
        if not self.ciclo_ingresos.is_running():
            self.ciclo_ingresos.start()

    @tasks.loop(hours=6)
    async def ciclo_ingresos(self):
        """Genera ingresos pasivos para cada empresa y cobra el impuesto corporativo."""
        empresas = await db.all("empresas")
        for eid, empresa in empresas.items():
            tipo = empresa.get("tipo", "comercio")
            info_tipo = TIPOS_EMPRESA.get(tipo, TIPOS_EMPRESA["comercio"])

            capital = empresa.get("capital", 0.0)
            n_oficinas = max(1, len(empresa.get("oficinas", [])))
            factor_capital = min(2.0, 1 + capital / 100_000)
            factor_oficinas = 1 + 0.15 * (n_oficinas - 1)
            variacion = random.uniform(0.7, 1.3)

            ingreso_bruto = round(info_tipo["ingreso_base"] * factor_capital * factor_oficinas * variacion, 2)
            tasa = impuestos.tasa_corporativa(tipo)
            monto_impuesto = round(ingreso_bruto * tasa, 2)
            ingreso_neto = round(ingreso_bruto - monto_impuesto, 2)

            empresa["capital"] = round(capital + ingreso_neto, 2)
            empresa["ingresos_totales"] = round(empresa.get("ingresos_totales", 0) + ingreso_bruto, 2)
            empresa["impuestos_pagados"] = round(empresa.get("impuestos_pagados", 0) + monto_impuesto, 2)
            await db.set("empresas", eid, empresa)
            await impuestos.recaudar(monto_impuesto, concepto=f"corporativo_{tipo}")

    # ── !crear_empresa ───────────────────────────────────────────────────────
    @commands.command(name="crear_empresa")
    async def crear_empresa(self, ctx, tipo: str, sector: str, *, nombre: str):
        """Funda una empresa. Uso: !crear_empresa <comercio|industria|tech> <sector> <nombre>"""
        tipo = tipo.lower()
        sector = sector.lower().replace(" ", "-")

        if tipo not in TIPOS_EMPRESA:
            return await ctx.send(f"❌ Tipo inválido. Usa: {', '.join(TIPOS_EMPRESA.keys())}")
        if sector not in SECTORES or SECTORES[sector].get("casas_total", 0) <= 0:
            return await ctx.send(f"❌ Sector `{sector}` no válido para instalar una empresa.")

        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ No tienes personaje.")

        eid_existente, _ = await _empresa_de_usuario(ctx.author.id)
        if eid_existente:
            return await ctx.send(f"❌ Ya eres dueño de una empresa (`{eid_existente}`). Por ahora solo puedes tener una.")

        oficinas = await _inicializar_oficinas_sector(sector)
        sedes = await _inicializar_sedes_sector(sector)

        oficina_libre = next((oid for oid, o in oficinas.items() if not o.get("empresa_id")), None)
        sede_libre = next((sid for sid, s in sedes.items() if not s.get("empresa_id")), None)

        if not oficina_libre:
            return await ctx.send(f"❌ No quedan oficinas disponibles en `{sector}`. Prueba otro sector.")
        if not sede_libre:
            return await ctx.send(f"❌ No quedan sedes disponibles en `{sector}`. Prueba otro sector.")

        precio_oficina = oficinas[oficina_libre]["precio"]
        precio_sede = sedes[sede_libre]["precio"]
        costo_total = CAPITAL_INICIAL_EMPRESA + precio_oficina + precio_sede

        dinero = datos.get("dinero", 0)
        if dinero < costo_total:
            return await ctx.send(
                f"❌ Necesitas ${costo_total:,.2f} en total:\n"
                f"• Capital de constitución: ${CAPITAL_INICIAL_EMPRESA:,.2f}\n"
                f"• Oficina en {sector}: ${precio_oficina:,.2f}\n"
                f"• Sede en {sector}: ${precio_sede:,.2f}\n"
                f"Tienes ${dinero:,.2f}."
            )

        # Crear canal de la sede
        guild = ctx.guild
        nombre_cat_sedes = f"🏢 SEDES - {sector.upper()}"
        cat_sedes = discord.utils.get(guild.categories, name=nombre_cat_sedes)
        if not cat_sedes:
            try:
                cat_sedes = await guild.create_category(nombre_cat_sedes)
            except Exception as e:
                return await ctx.send(f"❌ No se pudo crear la categoría de sedes: {e}")

        eid = _slug(nombre)
        if await db.get("empresas", eid):
            eid = f"{eid}-{ctx.author.id % 10000}"

        nombre_canal = f"sede-{eid}"[:95]
        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False, view_channel=False),
                ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True, view_channel=True),
            }
            canal_sede = await guild.create_text_channel(
                name=nombre_canal, category=cat_sedes, overwrites=overwrites,
                topic=f"🏢 Sede de {nombre} ({TIPOS_EMPRESA[tipo]['display']}) — dueño: {datos.get('nombre','?')}"
            )
        except Exception as e:
            return await ctx.send(f"❌ No se pudo crear el canal de la sede: {e}")

        # Cobrar y registrar todo
        await db.update("personajes", str(ctx.author.id), {"dinero": round(dinero - costo_total, 2)})

        oficinas[oficina_libre]["empresa_id"] = eid
        await db.set("oficinas", sector, oficinas)
        sedes[sede_libre]["empresa_id"] = eid
        sedes[sede_libre]["canal_id"] = canal_sede.id
        await db.set("sedes", sector, sedes)

        empresa = {
            "id": eid,
            "nombre": nombre,
            "tipo": tipo,
            "dueño": str(ctx.author.id),
            "sector": sector,
            "oficinas": [oficina_libre],
            "sede": sede_libre,
            "sede_canal_id": canal_sede.id,
            "empleados": [],
            "capital": CAPITAL_INICIAL_EMPRESA,
            "ingresos_totales": 0.0,
            "impuestos_pagados": 0.0,
            "creada_ts": time.time(),
        }
        await db.set("empresas", eid, empresa)

        embed = discord.Embed(
            title="🏢 ¡Empresa fundada!",
            description=f"**{nombre}** ({TIPOS_EMPRESA[tipo]['display']}) ya está operando en **{sector}**.",
            color=discord.Color.green()
        )
        embed.add_field(name="Capital inicial", value=f"${CAPITAL_INICIAL_EMPRESA:,.2f}", inline=True)
        embed.add_field(name="Oficina", value=oficina_libre, inline=True)
        embed.add_field(name="Sede", value=canal_sede.mention, inline=True)
        embed.add_field(name="Impuesto corporativo", value=f"{impuestos.tasa_corporativa(tipo)*100:.0f}%", inline=True)
        embed.set_footer(text="Los ingresos se generan automáticamente cada 6 horas. Usa !empresa para ver el estado.")
        await ctx.send(embed=embed)
        await canal_sede.send(f"🏢 Bienvenido a la sede de **{nombre}**, {ctx.author.mention}.")

    # ── !empresa — dashboard ─────────────────────────────────────────────────
    @commands.command(name="empresa", aliases=["mi_empresa"])
    async def empresa_info(self, ctx):
        eid, empresa = await _empresa_de_usuario(ctx.author.id)
        if not empresa:
            return await ctx.send("❌ No tienes empresa. Usa `!crear_empresa <tipo> <sector> <nombre>`.")

        info_tipo = TIPOS_EMPRESA.get(empresa["tipo"], {})
        embed = discord.Embed(
            title=f"{info_tipo.get('display','🏢')} {empresa['nombre']}",
            color=discord.Color.blurple()
        )
        embed.add_field(name="📍 Sector", value=empresa["sector"], inline=True)
        embed.add_field(name="💰 Capital actual", value=f"${empresa.get('capital',0):,.2f}", inline=True)
        embed.add_field(name="🏢 Oficinas", value=str(len(empresa.get("oficinas", []))), inline=True)
        embed.add_field(name="👥 Empleados", value=str(len(empresa.get("empleados", []))) or "0", inline=True)
        embed.add_field(name="📈 Ingresos totales", value=f"${empresa.get('ingresos_totales',0):,.2f}", inline=True)
        embed.add_field(name="🧾 Impuestos pagados", value=f"${empresa.get('impuestos_pagados',0):,.2f}", inline=True)
        embed.add_field(name="Impuesto corporativo", value=f"{impuestos.tasa_corporativa(empresa['tipo'])*100:.0f}%", inline=True)
        canal = ctx.guild.get_channel(empresa.get("sede_canal_id"))
        embed.add_field(name="🏛️ Sede", value=canal.mention if canal else "?", inline=True)
        embed.set_footer(text="Los ingresos se generan cada 6h automáticamente.")
        await ctx.send(embed=embed)

    # ── !abrir_sucursal ──────────────────────────────────────────────────────
    @commands.command(name="abrir_sucursal")
    async def abrir_sucursal(self, ctx, sector: str):
        """Compra una oficina adicional en otro sector para aumentar tus ingresos."""
        sector = sector.lower().replace(" ", "-")
        eid, empresa = await _empresa_de_usuario(ctx.author.id)
        if not empresa:
            return await ctx.send("❌ No tienes empresa.")
        if sector not in SECTORES or SECTORES[sector].get("casas_total", 0) <= 0:
            return await ctx.send(f"❌ Sector `{sector}` no válido.")

        datos = await db.get("personajes", str(ctx.author.id))
        oficinas_sector = await _inicializar_oficinas_sector(sector)
        oficina_libre = next((oid for oid, o in oficinas_sector.items() if not o.get("empresa_id")), None)
        if not oficina_libre:
            return await ctx.send(f"❌ No quedan oficinas libres en `{sector}`.")

        precio = oficinas_sector[oficina_libre]["precio"]
        dinero = datos.get("dinero", 0)
        if dinero < precio:
            return await ctx.send(f"❌ Necesitas ${precio:,.2f}, tienes ${dinero:,.2f}.")

        await db.update("personajes", str(ctx.author.id), {"dinero": round(dinero - precio, 2)})
        oficinas_sector[oficina_libre]["empresa_id"] = eid
        await db.set("oficinas", sector, oficinas_sector)

        empresa.setdefault("oficinas", []).append(f"{sector}:{oficina_libre}")
        await db.set("empresas", eid, empresa)

        await ctx.send(f"🏢 Nueva sucursal abierta: **{oficina_libre}** en **{sector}** por ${precio:,.2f}. Más oficinas = más ingresos por ciclo.")

    # ── !contratar / !despedir ───────────────────────────────────────────────
    @commands.command(name="contratar")
    async def contratar(self, ctx, empleado: discord.Member):
        eid, empresa = await _empresa_de_usuario(ctx.author.id)
        if not empresa:
            return await ctx.send("❌ No tienes empresa.")
        if str(empleado.id) in empresa.get("empleados", []):
            return await ctx.send(f"❌ {empleado.display_name} ya trabaja ahí.")
        datos_emp = await db.get("personajes", str(empleado.id))
        if not datos_emp:
            return await ctx.send(f"❌ {empleado.display_name} no tiene personaje.")

        empresa.setdefault("empleados", []).append(str(empleado.id))
        await db.set("empresas", eid, empresa)
        await ctx.send(f"✅ **{datos_emp['nombre']}** ahora trabaja en **{empresa['nombre']}**.")

    @commands.command(name="despedir")
    async def despedir(self, ctx, empleado: discord.Member):
        eid, empresa = await _empresa_de_usuario(ctx.author.id)
        if not empresa:
            return await ctx.send("❌ No tienes empresa.")
        if str(empleado.id) not in empresa.get("empleados", []):
            return await ctx.send(f"❌ {empleado.display_name} no trabaja ahí.")

        empresa["empleados"].remove(str(empleado.id))
        await db.set("empresas", eid, empresa)
        await ctx.send(f"👋 {empleado.display_name} fue despedido de **{empresa['nombre']}**.")

    # ── !depositar_empresa / !retirar_empresa ───────────────────────────────
    @commands.command(name="depositar_empresa")
    async def depositar_empresa(self, ctx, monto: float):
        eid, empresa = await _empresa_de_usuario(ctx.author.id)
        if not empresa:
            return await ctx.send("❌ No tienes empresa.")
        if monto <= 0:
            return await ctx.send("❌ Monto inválido.")
        datos = await db.get("personajes", str(ctx.author.id))
        dinero = datos.get("dinero", 0)
        if dinero < monto:
            return await ctx.send(f"❌ No tienes ${monto:,.2f}.")

        await db.update("personajes", str(ctx.author.id), {"dinero": round(dinero - monto, 2)})
        empresa["capital"] = round(empresa.get("capital", 0) + monto, 2)
        await db.set("empresas", eid, empresa)
        await ctx.send(f"✅ Inyectaste ${monto:,.2f} al capital de **{empresa['nombre']}**. Capital actual: ${empresa['capital']:,.2f}")

    @commands.command(name="retirar_empresa")
    async def retirar_empresa(self, ctx, monto: float):
        """Retira capital de tu empresa como dividendos (paga impuesto a dividendos)."""
        eid, empresa = await _empresa_de_usuario(ctx.author.id)
        if not empresa:
            return await ctx.send("❌ No tienes empresa.")
        if monto <= 0:
            return await ctx.send("❌ Monto inválido.")
        capital = empresa.get("capital", 0)
        if capital < monto:
            return await ctx.send(f"❌ Tu empresa solo tiene ${capital:,.2f} de capital.")

        impuesto_div = round(monto * impuestos.IMPUESTO_DIVIDENDOS, 2)
        neto = round(monto - impuesto_div, 2)

        empresa["capital"] = round(capital - monto, 2)
        await db.set("empresas", eid, empresa)

        datos = await db.get("personajes", str(ctx.author.id))
        await db.update("personajes", str(ctx.author.id), {"dinero": round(datos.get("dinero", 0) + neto, 2)})
        await impuestos.recaudar(impuesto_div, concepto="dividendos")

        await ctx.send(
            f"💵 Retiraste ${monto:,.2f} de **{empresa['nombre']}**.\n"
            f"Impuesto a dividendos ({impuestos.IMPUESTO_DIVIDENDOS*100:.0f}%): -${impuesto_div:,.2f}\n"
            f"Recibiste neto: **${neto:,.2f}**"
        )


async def setup(bot):
    await bot.add_cog(Empresas(bot))
